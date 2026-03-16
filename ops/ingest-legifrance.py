#!/usr/bin/env python3
"""
Legifrance Ingestion Pipeline — French Law into Sector RAG
============================================================
Ingests articles from France's 74 legal codes via DILA Open Data (LEGI).

Data source: https://echanges.dila.gouv.fr/OPENDATA/LEGI/
  - Freemium_legi_global_*.tar.gz  = full snapshot (~1.1GB compressed)
  - LEGI_YYYYMMDD-*.tar.gz         = daily incremental deltas (1-10MB)

Architecture:
  1. DISCOVER  — List available DILA archives, select global or incremental
  2. STREAM    — Stream tar.gz entries without full extraction (low RAM)
  3. PARSE     — Extract article XML → structured metadata + text
  4. STORE     — Supabase (sector_documents) + Pinecone (E5 vectors)
  5. ENRICH    — Neo4j entity graph via LiteLLM extraction

Each article becomes one chunk with full legal metadata:
  - code_name, article_ref, partie, livre, titre, chapitre, section
  - date_version, full_reference, etat (VIGUEUR/MODIFIE/ABROGE)

Usage:
  source .env.local
  python3 ops/ingest-legifrance.py --codes travail,civil --dry-run
  python3 ops/ingest-legifrance.py --codes travail --batch-size 50
  python3 ops/ingest-legifrance.py --codes all --batch-size 100
  python3 ops/ingest-legifrance.py --status
  python3 ops/ingest-legifrance.py --daemon --interval 600 --codes all
  python3 ops/ingest-legifrance.py --use-incremental --days 7
  nohup python3 ops/ingest-legifrance.py --daemon --codes all > data/ingest/legifrance.log 2>&1 &
"""

# ── Force IPv4 globally (IPv6 broken on this VM) ────────────────────────
import socket
from socket import AF_INET

_original_getaddrinfo = socket.getaddrinfo


def _ipv4_getaddrinfo(host, port, family=0, type_=0, proto=0, flags=0):
    return _original_getaddrinfo(host, port, AF_INET, type_, proto, flags)


socket.getaddrinfo = _ipv4_getaddrinfo

# ── Standard imports ────────────────────────────────────────────────────
import argparse
import hashlib
import html
import io
import json
import os
import re
import signal
import ssl
import sys
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

# ── Force line-buffered output ──────────────────────────────────────────
try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

# ── Load .env.local ─────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / ".env.local"
if ENV_FILE.exists():
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k = k.strip().lstrip("export").strip()
                v = v.strip().strip('"').strip("'")
                if k and v:
                    os.environ.setdefault(k, v)

# ── SSL context (permissive for government sites) ───────────────────────
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE

# =========================================================================
# CONFIGURATION
# =========================================================================

# DILA Open Data
DILA_BASE_URL = "https://echanges.dila.gouv.fr/OPENDATA/LEGI/"

# Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://ayqviqmxifzmhphiqfmj.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_API_KEY", "")
SUPABASE_TABLE = "sector_documents"

# Pinecone E5 integrated embedding
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY", "")
PINECONE_HOST = "https://sectors-e5-multilingual-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
PINECONE_NAMESPACE = "sectors"

# Neo4j
NEO4J_URI = os.environ.get("NEO4J_URI", "neo4j+s://38c949a2.databases.neo4j.io")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "")

# LiteLLM S7
LITELLM_URL = os.environ.get("LITELLM_PROXY_URL",
    "https://lbjlincoln-nomos-rag-engine-7.hf.space")
LITELLM_CHAT_URL = f"{LITELLM_URL}/v1/chat/completions"
LITELLM_KEY = os.environ.get("LITELLM_MASTER_KEY", "sk-litellm-nomos-2026")

# Data dirs
DATA_DIR = REPO_ROOT / "data" / "ingest"
STATE_FILE = DATA_DIR / "legifrance-state.json"
LOG_FILE = DATA_DIR / "legifrance.jsonl"
PID_FILE = DATA_DIR / "legifrance.pid"

# Processing config
DEFAULT_BATCH_SIZE = 50
DEFAULT_INTERVAL = 600   # 10 minutes
REQUEST_DELAY = 0.05     # 50ms between Pinecone upserts
SUPABASE_BATCH_SIZE = 25 # rows per Supabase POST
SUPABASE_TIMEOUT = 30
PINECONE_TIMEOUT = 15
MAX_TEXT_LEN = 2000      # max chars for embedding text
MIN_TEXT_LEN = 20        # skip articles shorter than this
INTER_BATCH_DELAY = 1.0  # seconds between batches

SECTORS = ["finance", "btp", "juridique", "industrie"]

# Graceful shutdown
_shutdown_requested = False


def _signal_handler(signum, frame):
    global _shutdown_requested
    _shutdown_requested = True
    log("Shutdown signal received, finishing current batch...", "WARN")


signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)

# =========================================================================
# TOP 10 CODES FOR ETIs — LEGITEXT IDs + sector mapping
# =========================================================================
# These LEGITEXT IDs are the official identifiers used in the LEGI database.
# The path pattern is: code_en_vigueur/LEGI/TEXT/{id_path}/LEGITEXT{id}/

CODES_REGISTRY = {
    "travail": {
        "legitext": "LEGITEXT000006072050",
        "name": "Code du travail",
        "short": "C. trav.",
        "sector": "juridique",
        "priority": 1,
        "est_articles": 10000,
    },
    "civil": {
        "legitext": "LEGITEXT000006070721",
        "name": "Code civil",
        "short": "C. civ.",
        "sector": "juridique",
        "priority": 2,
        "est_articles": 2881,
    },
    "commerce": {
        "legitext": "LEGITEXT000005634379",
        "name": "Code de commerce",
        "short": "C. com.",
        "sector": "juridique",
        "priority": 3,
        "est_articles": 7178,
    },
    "construction": {
        "legitext": "LEGITEXT000006074096",
        "name": "Code de la construction et de l'habitation",
        "short": "CCH",
        "sector": "btp",
        "priority": 4,
        "est_articles": 4500,
    },
    "environnement": {
        "legitext": "LEGITEXT000006074220",
        "name": "Code de l'environnement",
        "short": "C. envir.",
        "sector": "industrie",
        "priority": 5,
        "est_articles": 5000,
    },
    "consommation": {
        "legitext": "LEGITEXT000006069565",
        "name": "Code de la consommation",
        "short": "C. conso.",
        "sector": "juridique",
        "priority": 6,
        "est_articles": 3000,
    },
    "impots": {
        "legitext": "LEGITEXT000006069577",
        "name": "Code general des impots",
        "short": "CGI",
        "sector": "finance",
        "priority": 7,
        "est_articles": 4000,
    },
    "sante": {
        "legitext": "LEGITEXT000006072665",
        "name": "Code de la sante publique",
        "short": "CSP",
        "sector": "industrie",
        "priority": 8,
        "est_articles": 8000,
    },
    "urbanisme": {
        "legitext": "LEGITEXT000006074075",
        "name": "Code de l'urbanisme",
        "short": "C. urb.",
        "sector": "btp",
        "priority": 9,
        "est_articles": 3000,
    },
    "monetaire": {
        "legitext": "LEGITEXT000006072026",
        "name": "Code monetaire et financier",
        "short": "CMF",
        "sector": "finance",
        "priority": 10,
        "est_articles": 5000,
    },
}

# Extended codes for completeness (lower priority)
CODES_EXTENDED = {
    "penal": {
        "legitext": "LEGITEXT000006070719",
        "name": "Code penal",
        "short": "C. pen.",
        "sector": "juridique",
        "priority": 11,
        "est_articles": 1500,
    },
    "procedure_civile": {
        "legitext": "LEGITEXT000006070716",
        "name": "Code de procedure civile",
        "short": "CPC",
        "sector": "juridique",
        "priority": 12,
        "est_articles": 2000,
    },
    "securite_sociale": {
        "legitext": "LEGITEXT000006073189",
        "name": "Code de la securite sociale",
        "short": "CSS",
        "sector": "juridique",
        "priority": 13,
        "est_articles": 5000,
    },
    "propriete_intellectuelle": {
        "legitext": "LEGITEXT000006069414",
        "name": "Code de la propriete intellectuelle",
        "short": "CPI",
        "sector": "juridique",
        "priority": 14,
        "est_articles": 1500,
    },
    "energie": {
        "legitext": "LEGITEXT000023983208",
        "name": "Code de l'energie",
        "short": "C. energ.",
        "sector": "industrie",
        "priority": 15,
        "est_articles": 2000,
    },
}

# Merge all codes
ALL_CODES = {**CODES_REGISTRY, **CODES_EXTENDED}


# =========================================================================
# LOGGING
# =========================================================================

def log(msg, level="INFO"):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ts_short = ts[11:19]
    prefix = {"INFO": "+", "WARN": "!", "ERROR": "X", "OK": "v", "SKIP": "-"}.get(level, " ")
    print(f"[{ts_short}] [{prefix}] {msg}", flush=True)

    # Append to JSONL log
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        entry = {"ts": ts, "level": level, "msg": msg}
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


# =========================================================================
# HTTP UTILITIES
# =========================================================================

def http_request(url, data=None, headers=None, method="GET", timeout=30):
    """HTTP request via urllib. Returns (status, body_bytes, error_string)."""
    if headers is None:
        headers = {}
    headers.setdefault("User-Agent", "Nomos-Legifrance-Ingest/1.0 (legal-AI-research)")
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        resp = urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx)
        body = resp.read()
        return resp.status, body, None
    except urllib.error.HTTPError as e:
        body = b""
        try:
            body = e.read()
        except Exception:
            pass
        return e.code, body, f"HTTP {e.code}"
    except Exception as e:
        return 0, b"", f"{type(e).__name__}: {str(e)[:200]}"


def supabase_request(path, method="GET", data=None, params=None, headers_extra=None):
    """Make authenticated Supabase REST API request."""
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params, safe=".,*()=")

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    if headers_extra:
        headers.update(headers_extra)

    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data else None
    status, resp_body, err = http_request(url, data=body, headers=headers,
                                           method=method, timeout=SUPABASE_TIMEOUT)
    if err:
        return None, err

    if status in (200, 201, 204):
        if resp_body:
            try:
                return json.loads(resp_body.decode("utf-8")), None
            except Exception:
                return None, None  # 204 no content is OK
        return None, None

    body_str = resp_body.decode("utf-8", errors="replace")[:300] if resp_body else "empty"
    return None, f"HTTP {status}: {body_str}"


# =========================================================================
# STATE MANAGEMENT
# =========================================================================

def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text("utf-8"))
        except Exception:
            pass
    return {
        "created": datetime.now(timezone.utc).isoformat(),
        "version": "1.0",
        "cycles": 0,
        "totals": {
            "articles_parsed": 0,
            "articles_stored_supabase": 0,
            "articles_stored_pinecone": 0,
            "articles_enriched": 0,
            "articles_skipped": 0,
            "errors": 0,
        },
        "codes_progress": {},
        "last_archive": None,
        "processed_article_ids": [],
    }


def save_state(state):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    # Cap the processed_article_ids to avoid unbounded growth
    if len(state.get("processed_article_ids", [])) > 200000:
        state["processed_article_ids"] = state["processed_article_ids"][-100000:]
    tmp = str(STATE_FILE) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False, default=str)
    os.replace(tmp, str(STATE_FILE))


# =========================================================================
# DILA ARCHIVE DISCOVERY
# =========================================================================

def list_dila_archives():
    """List available LEGI archives from DILA open data server."""
    status, body, err = http_request(DILA_BASE_URL, timeout=30)
    if err:
        log(f"Failed to list DILA archives: {err}", "ERROR")
        return []

    html_text = body.decode("utf-8", errors="replace")
    # Parse the Apache directory listing
    archives = []
    for match in re.finditer(r'href="((?:Freemium_legi_global|LEGI)_[^"]+\.tar\.gz)"', html_text):
        filename = match.group(1)
        # Extract size from the listing
        size_match = re.search(re.escape(filename) + r'</a>\s+[\d-]+\s+[\d:]+\s+([\d.]+[KMG])', html_text)
        size_str = size_match.group(1) if size_match else "?"
        is_global = filename.startswith("Freemium")

        # Extract date from filename
        date_match = re.search(r'(\d{8})', filename)
        date_str = date_match.group(1) if date_match else ""

        archives.append({
            "filename": filename,
            "url": DILA_BASE_URL + filename,
            "is_global": is_global,
            "date": date_str,
            "size": size_str,
        })

    return sorted(archives, key=lambda a: a.get("date", ""), reverse=True)


def select_archives(archives, use_incremental=False, days=7, use_global=False):
    """Select which archives to process."""
    if use_global:
        # Find the global archive
        globals_ = [a for a in archives if a["is_global"]]
        if globals_:
            return [globals_[0]]
        log("No global archive found", "ERROR")
        return []

    if use_incremental:
        # Select recent incremental archives
        today = datetime.now(timezone.utc)
        cutoff = today.strftime("%Y%m%d")
        # Go back N days
        from datetime import timedelta
        cutoff_date = (today - timedelta(days=days)).strftime("%Y%m%d")

        incrementals = [
            a for a in archives
            if not a["is_global"] and a["date"] >= cutoff_date
        ]
        return sorted(incrementals, key=lambda a: a["date"])

    # Default: use the global archive (most complete)
    globals_ = [a for a in archives if a["is_global"]]
    if globals_:
        return [globals_[0]]

    # Fallback to recent incrementals
    incrementals = [a for a in archives if not a["is_global"]]
    return sorted(incrementals, key=lambda a: a["date"])[-30:]


# =========================================================================
# XML PARSING — Article extraction from LEGI XML
# =========================================================================

def strip_html_tags(text):
    """Remove HTML tags and decode entities, preserving text content."""
    if not text:
        return ""
    # Replace <br/> and <p> with newlines
    text = re.sub(r'<br\s*/?\s*>', '\n', text)
    text = re.sub(r'</p>', '\n', text)
    text = re.sub(r'<p[^>]*>', '', text)
    # Remove all other tags
    text = re.sub(r'<[^>]+>', '', text)
    # Decode HTML entities
    text = html.unescape(text)
    # Normalize whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()
    return text


def extract_hierarchy(contexte_elem):
    """Extract the nested TM hierarchy from CONTEXTE element.
    Returns dict with partie, livre, titre, chapitre, section.
    """
    hierarchy = {
        "partie": "",
        "livre": "",
        "titre": "",
        "chapitre": "",
        "section": "",
        "sous_section": "",
    }

    if contexte_elem is None:
        return hierarchy

    # Find all nested TITRE_TM elements
    titles = []
    for tm in contexte_elem.iter("TITRE_TM"):
        title_text = (tm.text or "").strip()
        if title_text:
            titles.append(title_text)

    # Map titles to hierarchy levels based on their content
    for title in titles:
        title_lower = title.lower()
        if "partie" in title_lower and not hierarchy["partie"]:
            hierarchy["partie"] = title
        elif title_lower.startswith("livre") or "livre " in title_lower:
            hierarchy["livre"] = title
        elif title_lower.startswith("titre") or "titre " in title_lower:
            hierarchy["titre"] = title
        elif title_lower.startswith("chapitre") or "chapitre " in title_lower:
            hierarchy["chapitre"] = title
        elif title_lower.startswith("sous-section") or "sous-section" in title_lower:
            hierarchy["sous_section"] = title
        elif title_lower.startswith("section") or "section " in title_lower:
            hierarchy["section"] = title

    return hierarchy


def parse_article_xml(xml_bytes, target_legitexts):
    """
    Parse a LEGI article XML.
    Returns article dict or None if not a target code article.

    Target format:
    {
        "article_id": "LEGIARTI000043346904",
        "code_legitext": "LEGITEXT000006069565",
        "code_name": "Code de la consommation",
        "article_num": "R521-1",
        "etat": "VIGUEUR",
        "date_debut": "2021-04-11",
        "date_fin": "2023-09-22",
        "text": "L'autorite administrative...",
        "hierarchy": {...},
        "full_reference": "Art. R521-1 du Code de la consommation",
        "nature": "CODE",
    }
    """
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return None

    if root.tag != "ARTICLE":
        return None

    # Extract basic metadata
    meta_commun = root.find(".//META_COMMUN")
    meta_article = root.find(".//META_ARTICLE")

    if meta_commun is None or meta_article is None:
        return None

    article_id = _text(meta_commun, "ID")
    if not article_id:
        return None

    # Check if this belongs to a target code
    contexte = root.find("CONTEXTE")
    if contexte is None:
        return None

    texte_elem = contexte.find("TEXTE")
    if texte_elem is None:
        return None

    code_cid = texte_elem.get("cid", "")
    nature = texte_elem.get("nature", "")

    # Only process CODE articles (not DECRET, LOI, etc.)
    if nature != "CODE":
        return None

    # Check if this code is in our target list
    if code_cid not in target_legitexts:
        return None

    # Extract article details
    article_num = _text(meta_article, "NUM")
    etat = _text(meta_article, "ETAT")
    date_debut = _text(meta_article, "DATE_DEBUT")
    date_fin = _text(meta_article, "DATE_FIN")

    # Only keep VIGUEUR (in force) articles by default
    # MODIFIE articles are old versions, ABROGE are repealed
    if etat not in ("VIGUEUR", "MODIFIE", "MODIFIE_MORT_NE"):
        return None

    # Extract code name from TITRE_TXT
    code_name = ""
    for titre_txt in texte_elem.findall("TITRE_TXT"):
        code_name = titre_txt.get("c_titre_court", "") or (titre_txt.text or "").strip()
        if code_name:
            break

    # Extract hierarchy (Partie/Livre/Titre/Chapitre/Section)
    hierarchy = extract_hierarchy(contexte)

    # Extract article text from BLOC_TEXTUEL/CONTENU
    bloc = root.find(".//BLOC_TEXTUEL/CONTENU")
    raw_html = ""
    if bloc is not None:
        # Get all text including nested elements
        raw_html = ET.tostring(bloc, encoding="unicode", method="html")
        # Remove the outer <CONTENU> wrapper
        raw_html = re.sub(r'^<CONTENU[^>]*>', '', raw_html)
        raw_html = re.sub(r'</CONTENU>$', '', raw_html)

    text = strip_html_tags(raw_html)

    if not text or len(text) < MIN_TEXT_LEN:
        return None

    # Build full reference string
    if article_num:
        full_reference = f"Art. {article_num} du {code_name}" if code_name else f"Art. {article_num}"
    else:
        full_reference = f"Article {article_id}"

    # Extract NOTA if present
    nota_elem = root.find(".//NOTA/CONTENU")
    nota = ""
    if nota_elem is not None:
        nota_html = ET.tostring(nota_elem, encoding="unicode", method="html")
        nota = strip_html_tags(nota_html)

    # Extract cross-references (LIENS)
    liens = []
    for lien in root.findall(".//LIENS/LIEN"):
        lien_text = (lien.text or "").strip()
        if lien_text:
            liens.append(lien_text[:200])

    return {
        "article_id": article_id,
        "code_legitext": code_cid,
        "code_name": code_name,
        "article_num": article_num or "",
        "etat": etat,
        "date_debut": date_debut,
        "date_fin": date_fin,
        "text": text,
        "nota": nota[:500] if nota else "",
        "hierarchy": hierarchy,
        "full_reference": full_reference,
        "nature": nature,
        "liens_count": len(liens),
        "liens_sample": liens[:5],
    }


def _text(elem, tag):
    """Get text content of a child element, or empty string."""
    child = elem.find(tag) if elem is not None else None
    return (child.text or "").strip() if child is not None else ""


# =========================================================================
# STREAMING TAR.GZ PROCESSOR
# =========================================================================

def stream_archive_articles(archive_url, target_legitexts, state, batch_size=50,
                            only_vigueur=True, max_articles=0):
    """
    Stream a LEGI tar.gz archive and yield batches of parsed articles.
    Processes entries one at a time without extracting to disk.

    Yields: list of article dicts (batch_size at a time)
    """
    global _shutdown_requested

    processed_ids = set(state.get("processed_article_ids", []))
    log(f"Streaming archive: {archive_url.split('/')[-1]}", "INFO")
    log(f"Target codes: {len(target_legitexts)} LEGITEXT IDs", "INFO")
    log(f"Already processed: {len(processed_ids):,} articles", "INFO")

    # Build the LEGITEXT path fragments we are looking for
    # Articles live under: code_en_vigueur/LEGI/TEXT/.../LEGITEXT{id}/article/
    target_path_fragments = set()
    for lt in target_legitexts:
        target_path_fragments.add(lt)

    # Download and stream the tarball
    try:
        req = urllib.request.Request(archive_url)
        req.add_header("User-Agent", "Nomos-Legifrance-Ingest/1.0")
        response = urllib.request.urlopen(req, timeout=300, context=_ssl_ctx)
    except Exception as e:
        log(f"Failed to download archive: {e}", "ERROR")
        return

    # Wrap in a streaming tar reader
    try:
        # Read into memory in chunks to avoid storing the whole file
        # For the global archive (1.1GB), we use streaming
        fileobj = response
        tar = tarfile.open(fileobj=fileobj, mode="r|gz")
    except Exception as e:
        log(f"Failed to open tar stream: {e}", "ERROR")
        return

    batch = []
    total_entries = 0
    total_articles = 0
    total_code_articles = 0
    total_skipped = 0
    start_time = time.time()

    try:
        for entry in tar:
            if _shutdown_requested:
                log("Shutdown requested, yielding final batch", "WARN")
                break

            total_entries += 1

            # Progress logging every 10000 entries
            if total_entries % 10000 == 0:
                elapsed = time.time() - start_time
                rate = total_entries / elapsed if elapsed > 0 else 0
                log(f"  Progress: {total_entries:,} entries, {total_code_articles:,} code articles, "
                    f"{rate:.0f} entries/s", "INFO")

            # Only process files, not directories
            if not entry.isfile():
                continue

            # Only process LEGIARTI XML files (articles)
            name = entry.name
            if not name.endswith(".xml"):
                continue
            if "/article/" not in name or "LEGIARTI" not in name:
                continue

            # Quick path filter: must contain a target LEGITEXT ID
            match_found = False
            for frag in target_path_fragments:
                if frag in name:
                    match_found = True
                    break
            if not match_found:
                continue

            total_articles += 1

            # Extract and parse the XML
            try:
                f = tar.extractfile(entry)
                if f is None:
                    continue
                xml_bytes = f.read()
                f.close()
            except Exception:
                continue

            article = parse_article_xml(xml_bytes, target_legitexts)
            if article is None:
                continue

            # Filter by etat if requested
            if only_vigueur and article["etat"] != "VIGUEUR":
                total_skipped += 1
                continue

            # Skip already processed
            if article["article_id"] in processed_ids:
                total_skipped += 1
                continue

            total_code_articles += 1
            batch.append(article)

            if len(batch) >= batch_size:
                yield batch
                batch = []

                # Check max articles limit
                if max_articles > 0 and total_code_articles >= max_articles:
                    log(f"Reached max articles limit: {max_articles}", "INFO")
                    break

    except Exception as e:
        log(f"Error streaming archive: {e}", "ERROR")
    finally:
        try:
            tar.close()
        except Exception:
            pass
        try:
            response.close()
        except Exception:
            pass

    # Yield remaining batch
    if batch:
        yield batch

    elapsed = time.time() - start_time
    log(f"Archive complete: {total_entries:,} entries, {total_articles:,} article XMLs, "
        f"{total_code_articles:,} target code articles ({total_skipped:,} skipped), "
        f"{elapsed:.0f}s", "OK")


# =========================================================================
# STORAGE — Supabase
# =========================================================================

def store_supabase_batch(articles, code_key):
    """
    Store a batch of articles in Supabase sector_documents.
    Returns (success_count, error_count).
    """
    if not SUPABASE_KEY:
        log("SUPABASE_API_KEY not set, skipping Supabase storage", "WARN")
        return 0, len(articles)

    code_info = ALL_CODES.get(code_key, {})
    sector = code_info.get("sector", "juridique")

    rows = []
    for article in articles:
        # Map code to sector
        art_sector = sector
        for ck, cv in ALL_CODES.items():
            if cv["legitext"] == article["code_legitext"]:
                art_sector = cv["sector"]
                break

        # Build the context (article text with full reference header)
        context_parts = [article["full_reference"]]
        hier = article.get("hierarchy", {})
        hier_parts = [v for v in [
            hier.get("partie", ""),
            hier.get("livre", ""),
            hier.get("titre", ""),
            hier.get("chapitre", ""),
            hier.get("section", ""),
        ] if v]
        if hier_parts:
            context_parts.append(" > ".join(hier_parts))
        context_parts.append("")
        context_parts.append(article["text"])
        if article.get("nota"):
            context_parts.append(f"\nNota: {article['nota']}")
        context = "\n".join(context_parts)

        metadata = {
            "source": "legifrance",
            "source_type": "dila_opendata",
            "code_name": article["code_name"],
            "code_legitext": article["code_legitext"],
            "article_ref": article["article_num"],
            "article_id": article["article_id"],
            "etat": article["etat"],
            "date_debut": article["date_debut"],
            "date_fin": article["date_fin"],
            "full_reference": article["full_reference"],
            "hierarchy": article["hierarchy"],
            "nature": article["nature"],
            "liens_count": article.get("liens_count", 0),
            "has_entities": False,
            "entity_count": 0,
            "enriched": "false",
        }

        # Build deterministic ID from article_id
        doc_id = f"legi-{article['article_id']}"

        rows.append({
            "id": doc_id,
            "sector": art_sector,
            "dataset_name": f"legifrance-{article['code_name'].lower().replace(' ', '-')}",
            "pipeline": "legifrance-ingest",
            "question": "",
            "answer": "",
            "context": context[:10000],  # Cap at 10K chars
            "metadata": metadata,
            "tenant_id": art_sector,
        })

    # Batch insert via POST with upsert preference
    success = 0
    errors = 0

    for i in range(0, len(rows), SUPABASE_BATCH_SIZE):
        chunk = rows[i:i + SUPABASE_BATCH_SIZE]

        url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal,resolution=merge-duplicates",
        }
        payload = json.dumps(chunk, ensure_ascii=False).encode("utf-8")

        status, body, err = http_request(url, data=payload, headers=headers,
                                          method="POST", timeout=SUPABASE_TIMEOUT)
        if err:
            log(f"  Supabase batch error: {err}", "ERROR")
            errors += len(chunk)
        elif status in (200, 201, 204):
            success += len(chunk)
        else:
            body_str = body.decode("utf-8", errors="replace")[:200] if body else ""
            log(f"  Supabase HTTP {status}: {body_str}", "ERROR")
            errors += len(chunk)

    return success, errors


# =========================================================================
# STORAGE — Pinecone E5 integrated embedding
# =========================================================================

def store_pinecone_batch(articles):
    """
    Store articles in Pinecone via the E5 integrated embedding endpoint.
    Each article becomes one vector with the article text as embedding input.
    Returns (success_count, error_count).
    """
    if not PINECONE_API_KEY:
        log("PINECONE_API_KEY not set, skipping Pinecone storage", "WARN")
        return 0, len(articles)

    url = f"{PINECONE_HOST}/records/namespaces/{PINECONE_NAMESPACE}/upsert"
    headers = {
        "Api-Key": PINECONE_API_KEY,
        "Content-Type": "application/json",
    }

    success = 0
    errors = 0

    for article in articles:
        if _shutdown_requested:
            break

        # Build the embedding text: reference + hierarchy + article text
        hier = article.get("hierarchy", {})
        hier_str = " > ".join([v for v in [
            hier.get("partie", ""),
            hier.get("livre", ""),
            hier.get("titre", ""),
            hier.get("chapitre", ""),
            hier.get("section", ""),
        ] if v])

        text_parts = [article["full_reference"]]
        if hier_str:
            text_parts.append(hier_str)
        text_parts.append(article["text"])
        embed_text = " | ".join(text_parts)

        # Cap text length for E5
        if len(embed_text) > MAX_TEXT_LEN:
            embed_text = embed_text[:MAX_TEXT_LEN]

        # Determine sector
        art_sector = "juridique"
        for ck, cv in ALL_CODES.items():
            if cv["legitext"] == article["code_legitext"]:
                art_sector = cv["sector"]
                break

        record = {
            "_id": f"legi-{article['article_id']}",
            "text": embed_text,
            "sector": art_sector,
            "source": "legifrance",
            "code_name": article["code_name"],
            "article_ref": article["article_num"],
            "full_reference": article["full_reference"],
            "etat": article["etat"],
            "date_debut": article.get("date_debut", ""),
        }

        payload = json.dumps(record).encode("utf-8")

        for attempt in range(3):
            status, body, err = http_request(url, data=payload, headers=headers,
                                              method="POST", timeout=PINECONE_TIMEOUT)
            if status in (200, 201):
                success += 1
                break
            elif status == 409:
                # Already exists — count as success
                success += 1
                break
            elif status == 429:
                # Rate limited — exponential backoff
                wait = min(2 ** attempt + 0.5, 5)
                time.sleep(wait)
                continue
            elif attempt == 2:
                errors += 1
                err_text = body.decode("utf-8", errors="replace")[:100] if body else str(err)
                if errors <= 5:
                    log(f"  Pinecone error for {article['article_id']}: {err_text}", "WARN")
                break
            else:
                time.sleep(0.5)

        if REQUEST_DELAY > 0:
            time.sleep(REQUEST_DELAY)

    return success, errors


# =========================================================================
# ENRICHMENT — Neo4j via LiteLLM entity extraction
# =========================================================================

def enrich_batch_neo4j(articles, max_enrich=10):
    """
    Enrich a subset of articles with Neo4j entity extraction.
    Only enriches up to max_enrich articles per batch to control LLM costs.
    Returns enriched_count.
    """
    if not NEO4J_PASSWORD or not LITELLM_KEY:
        return 0

    enriched = 0
    for article in articles[:max_enrich]:
        if _shutdown_requested:
            break

        sector = "juridique"
        for ck, cv in ALL_CODES.items():
            if cv["legitext"] == article["code_legitext"]:
                sector = cv["sector"]
                break

        # LLM entity extraction
        prompt_payload = json.dumps({
            "model": "smart",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        f"Tu es un expert juridique francais specialise dans le droit ({sector}). "
                        f"Extrais les entites cles de cet article de loi. "
                        f"Retourne UNIQUEMENT un tableau JSON: "
                        f'[{{"name": "...", "type": "...", "description": "..."}}]\n'
                        f"Types possibles: LAW, REGULATION, CONCEPT, ORGANIZATION, PERSON, METRIC, LOCATION.\n"
                        f"Si aucune entite, retourne: []"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Code: {article['code_name']}\n"
                        f"Article: {article['full_reference']}\n\n"
                        f"{article['text'][:2000]}"
                    ),
                },
            ],
            "temperature": 0.1,
            "max_tokens": 800,
        }).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LITELLM_KEY}",
        }

        status, body, err = http_request(
            LITELLM_CHAT_URL, data=prompt_payload, headers=headers,
            method="POST", timeout=60,
        )

        if status != 200:
            continue

        # Parse entities from LLM response
        entities = []
        try:
            result = json.loads(body.decode("utf-8"))
            content_text = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            # Strip markdown code blocks
            content_text = content_text.strip()
            if content_text.startswith("```"):
                lines = content_text.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                content_text = "\n".join(lines).strip()
            # Try to parse JSON
            m = re.search(r'\[[\s\S]*?\]', content_text)
            if m:
                entities = json.loads(m.group())
        except Exception:
            pass

        if not entities:
            continue

        # Store in Neo4j
        try:
            from neo4j import GraphDatabase
            driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
            with driver.session() as session:
                # Create article node
                session.run(
                    """
                    MERGE (a:LegalArticle {id: $id})
                    SET a.code_name = $code_name,
                        a.article_ref = $article_ref,
                        a.sector = $sector,
                        a.full_reference = $full_ref,
                        a.enriched = true,
                        a.enrichment_ts = datetime()
                    """,
                    id=article["article_id"],
                    code_name=article["code_name"],
                    article_ref=article["article_num"],
                    sector=sector,
                    full_ref=article["full_reference"],
                )

                for ent in entities[:15]:
                    name = (ent.get("name", "") or "")[:150]
                    etype = (ent.get("type", "CONCEPT") or "CONCEPT")[:50]
                    desc = (ent.get("description", "") or "")[:300]
                    if name and len(name) >= 2:
                        session.run(
                            """
                            MERGE (e:Entity {name: $name, type: $type})
                            SET e.description = $desc, e.sector = $sector
                            WITH e
                            MATCH (a:LegalArticle {id: $art_id})
                            MERGE (a)-[:MENTIONS]->(e)
                            """,
                            name=name, type=etype, desc=desc,
                            sector=sector, art_id=article["article_id"],
                        )

            driver.close()
            enriched += 1
        except ImportError:
            log("neo4j driver not installed, skipping enrichment", "WARN")
            return enriched
        except Exception as e:
            log(f"  Neo4j error: {e}", "WARN")

        time.sleep(1)  # Rate limit LLM calls

    return enriched


# =========================================================================
# MAIN INGESTION CYCLE
# =========================================================================

def run_cycle(codes_to_process, state, batch_size=50, dry_run=False,
              only_vigueur=True, use_incremental=False, days=7,
              max_articles=0, skip_pinecone=False, skip_supabase=False,
              skip_enrich=False):
    """
    Run one full ingestion cycle.
    """
    global _shutdown_requested

    cycle_num = state["cycles"] + 1
    cycle_start = time.time()

    # Build set of target LEGITEXT IDs
    target_legitexts = set()
    code_names = {}
    for code_key in codes_to_process:
        info = ALL_CODES.get(code_key)
        if info:
            target_legitexts.add(info["legitext"])
            code_names[info["legitext"]] = code_key

    if not target_legitexts:
        log("No valid codes to process", "ERROR")
        return state

    print(f"\n{'=' * 70}", flush=True)
    print(f"  LEGIFRANCE INGESTION — Cycle {cycle_num}", flush=True)
    print(f"{'=' * 70}", flush=True)
    print(f"  Codes:     {', '.join(codes_to_process)}", flush=True)
    print(f"  Mode:      {'DRY RUN' if dry_run else 'LIVE'}", flush=True)
    print(f"  Filter:    {'VIGUEUR only' if only_vigueur else 'All states'}", flush=True)
    print(f"  Batch:     {batch_size} articles/batch", flush=True)
    print(f"  Storage:   {'Supabase' if not skip_supabase else '-'} | "
          f"{'Pinecone' if not skip_pinecone else '-'} | "
          f"{'Neo4j' if not skip_enrich else '-'}", flush=True)
    if max_articles > 0:
        print(f"  Max:       {max_articles} articles", flush=True)
    print(f"  Started:   {datetime.now(timezone.utc).isoformat()}", flush=True)
    print(f"{'=' * 70}", flush=True)

    # Discover archives
    log("Discovering DILA archives...", "INFO")
    archives = list_dila_archives()
    if not archives:
        log("No archives found", "ERROR")
        return state

    log(f"Found {len(archives)} archives ({sum(1 for a in archives if a['is_global'])} global, "
        f"{sum(1 for a in archives if not a['is_global'])} incremental)", "INFO")

    selected = select_archives(archives, use_incremental=use_incremental, days=days)
    if not selected:
        log("No archives selected", "ERROR")
        return state

    for arc in selected:
        log(f"  Selected: {arc['filename']} ({arc['size']})", "INFO")

    # Process each archive
    cycle_stats = {
        "articles_parsed": 0,
        "articles_stored_supabase": 0,
        "articles_stored_pinecone": 0,
        "articles_enriched": 0,
        "articles_skipped": 0,
        "errors_supabase": 0,
        "errors_pinecone": 0,
        "codes_seen": {},
    }

    for archive in selected:
        if _shutdown_requested:
            break

        log(f"\nProcessing: {archive['filename']} ({archive['size']})", "INFO")

        batch_num = 0
        for batch in stream_archive_articles(
            archive["url"],
            target_legitexts,
            state,
            batch_size=batch_size,
            only_vigueur=only_vigueur,
            max_articles=max_articles,
        ):
            if _shutdown_requested:
                break

            batch_num += 1
            log(f"  Batch {batch_num}: {len(batch)} articles", "INFO")

            # Track codes seen
            for art in batch:
                code_key = code_names.get(art["code_legitext"], "unknown")
                if code_key not in cycle_stats["codes_seen"]:
                    cycle_stats["codes_seen"][code_key] = 0
                cycle_stats["codes_seen"][code_key] += 1

            cycle_stats["articles_parsed"] += len(batch)

            if dry_run:
                # Just log what we found
                for art in batch[:3]:
                    log(f"    {art['full_reference']} [{art['etat']}] ({len(art['text'])} chars)", "SKIP")
                if len(batch) > 3:
                    log(f"    ... and {len(batch) - 3} more", "SKIP")
                continue

            # Store in Supabase
            if not skip_supabase:
                sb_ok, sb_err = store_supabase_batch(batch, codes_to_process[0])
                cycle_stats["articles_stored_supabase"] += sb_ok
                cycle_stats["errors_supabase"] += sb_err
                if sb_ok > 0:
                    log(f"    Supabase: {sb_ok} stored, {sb_err} errors", "OK")

            # Store in Pinecone
            if not skip_pinecone:
                pc_ok, pc_err = store_pinecone_batch(batch)
                cycle_stats["articles_stored_pinecone"] += pc_ok
                cycle_stats["errors_pinecone"] += pc_err
                if pc_ok > 0:
                    log(f"    Pinecone: {pc_ok} stored, {pc_err} errors", "OK")

            # Enrich via Neo4j (limited per batch)
            if not skip_enrich:
                enriched = enrich_batch_neo4j(batch, max_enrich=5)
                cycle_stats["articles_enriched"] += enriched
                if enriched > 0:
                    log(f"    Neo4j: {enriched} enriched", "OK")

            # Track processed article IDs
            new_ids = [art["article_id"] for art in batch]
            state.setdefault("processed_article_ids", []).extend(new_ids)

            # Update per-code progress
            for art in batch:
                code_key = code_names.get(art["code_legitext"], "unknown")
                if code_key not in state.get("codes_progress", {}):
                    state["codes_progress"][code_key] = {
                        "articles_processed": 0,
                        "last_article": "",
                        "last_updated": "",
                    }
                state["codes_progress"][code_key]["articles_processed"] += 1
                state["codes_progress"][code_key]["last_article"] = art["full_reference"]
                state["codes_progress"][code_key]["last_updated"] = datetime.now(timezone.utc).isoformat()

            # Save state after each batch
            save_state(state)

            # Inter-batch delay
            time.sleep(INTER_BATCH_DELAY)

        state["last_archive"] = archive["filename"]

    # Update global totals
    state["cycles"] = cycle_num
    for k in ["articles_parsed", "articles_stored_supabase", "articles_stored_pinecone",
              "articles_enriched"]:
        state["totals"][k] = state["totals"].get(k, 0) + cycle_stats.get(k, 0)
    state["totals"]["errors"] = state["totals"].get("errors", 0) + \
        cycle_stats.get("errors_supabase", 0) + cycle_stats.get("errors_pinecone", 0)

    save_state(state)

    # Print summary
    elapsed = time.time() - cycle_start
    print(f"\n{'=' * 70}", flush=True)
    print(f"  CYCLE {cycle_num} COMPLETE ({elapsed:.0f}s / {elapsed / 60:.1f}min)", flush=True)
    print(f"{'=' * 70}", flush=True)
    print(f"  Articles parsed:    {cycle_stats['articles_parsed']:,}", flush=True)
    print(f"  Stored Supabase:    {cycle_stats['articles_stored_supabase']:,}", flush=True)
    print(f"  Stored Pinecone:    {cycle_stats['articles_stored_pinecone']:,}", flush=True)
    print(f"  Enriched Neo4j:     {cycle_stats['articles_enriched']:,}", flush=True)
    print(f"  Errors (SB+PC):     {cycle_stats['errors_supabase'] + cycle_stats['errors_pinecone']:,}", flush=True)
    if cycle_stats["codes_seen"]:
        print(f"  Codes breakdown:", flush=True)
        for code, count in sorted(cycle_stats["codes_seen"].items(), key=lambda x: -x[1]):
            print(f"    {code:25s}  {count:,} articles", flush=True)
    print(f"\n  LIFETIME TOTALS:", flush=True)
    print(f"    Parsed:   {state['totals']['articles_parsed']:,}", flush=True)
    print(f"    Supabase: {state['totals']['articles_stored_supabase']:,}", flush=True)
    print(f"    Pinecone: {state['totals']['articles_stored_pinecone']:,}", flush=True)
    print(f"    Enriched: {state['totals']['articles_enriched']:,}", flush=True)
    print(f"    Errors:   {state['totals']['errors']:,}", flush=True)
    print(f"  State: {STATE_FILE}", flush=True)
    print(f"{'=' * 70}", flush=True)

    return state


# =========================================================================
# STATUS DISPLAY
# =========================================================================

def show_status(state):
    """Print ingestion status."""
    print(f"\n{'=' * 70}", flush=True)
    print(f"  LEGIFRANCE INGESTION — STATUS", flush=True)
    print(f"{'=' * 70}", flush=True)
    print(f"  Created:           {state.get('created', '?')}", flush=True)
    print(f"  Last updated:      {state.get('last_updated', '?')}", flush=True)
    print(f"  Cycles completed:  {state.get('cycles', 0)}", flush=True)
    print(f"  Last archive:      {state.get('last_archive', 'none')}", flush=True)
    print(f"  Processed IDs:     {len(state.get('processed_article_ids', [])):,}", flush=True)

    t = state.get("totals", {})
    print(f"\n  TOTALS:", flush=True)
    print(f"    Articles parsed:    {t.get('articles_parsed', 0):,}", flush=True)
    print(f"    Stored Supabase:    {t.get('articles_stored_supabase', 0):,}", flush=True)
    print(f"    Stored Pinecone:    {t.get('articles_stored_pinecone', 0):,}", flush=True)
    print(f"    Enriched Neo4j:     {t.get('articles_enriched', 0):,}", flush=True)
    print(f"    Errors:             {t.get('errors', 0):,}", flush=True)

    cp = state.get("codes_progress", {})
    if cp:
        print(f"\n  CODE PROGRESS:", flush=True)
        for code_key in sorted(cp.keys()):
            info = ALL_CODES.get(code_key, {})
            p = cp[code_key]
            est = info.get("est_articles", "?")
            processed = p.get("articles_processed", 0)
            pct = f"{processed / est * 100:.1f}%" if isinstance(est, int) and est > 0 else "?"
            print(f"    {code_key:25s}  {processed:6,} / ~{est:>6} ({pct:>6})  "
                  f"last: {p.get('last_article', '')[:40]}", flush=True)
    else:
        print(f"\n  No code progress recorded yet.", flush=True)

    # Show available codes
    print(f"\n  AVAILABLE CODES (top 10 + 5 extended):", flush=True)
    for code_key in sorted(ALL_CODES.keys(), key=lambda k: ALL_CODES[k]["priority"]):
        info = ALL_CODES[code_key]
        sector = info["sector"]
        name = info["name"]
        est = info["est_articles"]
        in_progress = code_key in cp
        marker = ">>>" if in_progress else "   "
        print(f"    {marker} {code_key:25s}  {name:45s}  sector={sector:12s}  ~{est:,} articles", flush=True)

    print(f"{'=' * 70}\n", flush=True)


# =========================================================================
# CLI
# =========================================================================

def main():
    global _shutdown_requested

    parser = argparse.ArgumentParser(
        description="Legifrance Ingestion — French law into sector RAG via DILA Open Data"
    )
    parser.add_argument(
        "--codes",
        default="travail",
        help="Comma-separated code keys to ingest (default: travail). "
             "Use 'all' for top 10, 'extended' for all 15. "
             "Available: " + ", ".join(sorted(ALL_CODES.keys())),
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Articles per batch (default: {DEFAULT_BATCH_SIZE})",
    )
    parser.add_argument(
        "--max-articles",
        type=int,
        default=0,
        help="Max total articles to process (0 = unlimited, default: 0)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse articles but do not store them",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show ingestion progress and exit",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run as daemon with continuous cycles",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_INTERVAL,
        help=f"Daemon cycle interval in seconds (default: {DEFAULT_INTERVAL})",
    )
    parser.add_argument(
        "--use-incremental",
        action="store_true",
        help="Use daily incremental archives instead of global snapshot",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days of incremental archives to process (default: 7)",
    )
    parser.add_argument(
        "--all-states",
        action="store_true",
        help="Include MODIFIE and ABROGE articles (default: VIGUEUR only)",
    )
    parser.add_argument(
        "--skip-pinecone",
        action="store_true",
        help="Skip Pinecone vector storage",
    )
    parser.add_argument(
        "--skip-supabase",
        action="store_true",
        help="Skip Supabase document storage",
    )
    parser.add_argument(
        "--skip-enrich",
        action="store_true",
        help="Skip Neo4j enrichment",
    )
    parser.add_argument(
        "--reset-state",
        action="store_true",
        help="Reset state file (re-process all articles)",
    )
    args = parser.parse_args()

    # Status mode
    if args.status:
        state = load_state()
        show_status(state)
        return

    # Parse code list
    if args.codes == "all":
        codes_to_process = sorted(CODES_REGISTRY.keys(), key=lambda k: CODES_REGISTRY[k]["priority"])
    elif args.codes == "extended":
        codes_to_process = sorted(ALL_CODES.keys(), key=lambda k: ALL_CODES[k]["priority"])
    else:
        codes_to_process = [c.strip() for c in args.codes.split(",") if c.strip()]
        invalid = [c for c in codes_to_process if c not in ALL_CODES]
        if invalid:
            print(f"ERROR: Unknown code(s): {', '.join(invalid)}", flush=True)
            print(f"Available: {', '.join(sorted(ALL_CODES.keys()))}", flush=True)
            sys.exit(1)

    # Validate config
    has_storage = False
    if SUPABASE_KEY and not args.skip_supabase:
        has_storage = True
    if PINECONE_API_KEY and not args.skip_pinecone:
        has_storage = True

    if not has_storage and not args.dry_run:
        log("WARNING: No storage configured (SUPABASE_API_KEY and PINECONE_API_KEY both missing). "
            "Use --dry-run or set environment variables.", "WARN")

    # Reset state if requested
    if args.reset_state:
        if STATE_FILE.exists():
            STATE_FILE.unlink()
            log("State file reset", "INFO")

    # Create data dir and save PID
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))

    state = load_state()

    # Print startup banner
    print(f"\n{'=' * 70}", flush=True)
    print(f"  LEGIFRANCE INGESTION PIPELINE v1.0", flush=True)
    print(f"  Source: DILA Open Data (echanges.dila.gouv.fr/OPENDATA/LEGI/)", flush=True)
    print(f"{'=' * 70}", flush=True)
    print(f"  Codes:     {', '.join(codes_to_process)} ({len(codes_to_process)} codes)", flush=True)
    est_total = sum(ALL_CODES.get(c, {}).get("est_articles", 0) for c in codes_to_process)
    print(f"  Est. articles: ~{est_total:,}", flush=True)
    print(f"  Mode:      {'Daemon' if args.daemon else 'One-shot'}"
          f"{'  (DRY RUN)' if args.dry_run else ''}", flush=True)
    print(f"  Archive:   {'Incremental' if args.use_incremental else 'Global snapshot'}", flush=True)
    print(f"  Filter:    {'All states' if args.all_states else 'VIGUEUR only'}", flush=True)
    print(f"  Batch:     {args.batch_size} articles/batch", flush=True)
    print(f"  Supabase:  {'OK' if SUPABASE_KEY else 'NOT SET'}"
          f"{'  (SKIP)' if args.skip_supabase else ''}", flush=True)
    print(f"  Pinecone:  {'OK' if PINECONE_API_KEY else 'NOT SET'}"
          f"{'  (SKIP)' if args.skip_pinecone else ''}", flush=True)
    print(f"  Neo4j:     {'OK' if NEO4J_PASSWORD else 'NOT SET'}"
          f"{'  (SKIP)' if args.skip_enrich else ''}", flush=True)
    print(f"  State:     {STATE_FILE}", flush=True)
    print(f"  Log:       {LOG_FILE}", flush=True)
    print(f"  PID:       {os.getpid()}", flush=True)
    print(f"  Started:   {datetime.now(timezone.utc).isoformat()}", flush=True)
    print(f"{'=' * 70}\n", flush=True)

    if args.daemon:
        log(f"Starting Legifrance daemon — {args.interval}s cycles", "INFO")

        while not _shutdown_requested:
            try:
                state = run_cycle(
                    codes_to_process, state,
                    batch_size=args.batch_size,
                    dry_run=args.dry_run,
                    only_vigueur=not args.all_states,
                    use_incremental=args.use_incremental,
                    days=args.days,
                    max_articles=args.max_articles,
                    skip_pinecone=args.skip_pinecone,
                    skip_supabase=args.skip_supabase,
                    skip_enrich=args.skip_enrich,
                )
            except Exception as e:
                log(f"Cycle error: {e}", "ERROR")
                import traceback
                traceback.print_exc()

            if _shutdown_requested:
                break

            log(f"Next cycle in {args.interval}s ({args.interval / 60:.0f}min)...", "INFO")

            try:
                sleep_end = time.time() + args.interval
                while time.time() < sleep_end and not _shutdown_requested:
                    time.sleep(min(5, sleep_end - time.time()))
            except KeyboardInterrupt:
                _shutdown_requested = True

        log("Legifrance daemon stopped gracefully", "OK")
    else:
        # One-shot mode
        state = run_cycle(
            codes_to_process, state,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
            only_vigueur=not args.all_states,
            use_incremental=args.use_incremental,
            days=args.days,
            max_articles=args.max_articles,
            skip_pinecone=args.skip_pinecone,
            skip_supabase=args.skip_supabase,
            skip_enrich=args.skip_enrich,
        )

    # Clean up PID
    try:
        PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass

    log("Legifrance Ingestion finished", "OK")


if __name__ == "__main__":
    main()
