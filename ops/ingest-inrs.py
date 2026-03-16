#!/usr/bin/env python3
"""
INRS Document Ingestion — Production pipeline for workplace safety PDFs.
========================================================================
Ingests 600+ INRS publications (Institut National de Recherche et de Securite)
into the Industrie sector RAG pipeline. These are authoritative French documents
on workplace safety, chemical risks, ergonomics, industrial hygiene, etc.

Architecture:
  1. CATALOG  — Scrape INRS publication catalog, extract PDF references
  2. DOWNLOAD — Fetch PDFs to /tmp (one at a time, RAM constraints)
  3. EXTRACT  — Send to Docling S6 for text extraction (fallback: pdfplumber)
  4. CHUNK    — Section-aware chunking (500-1500 chars, by chapter/heading)
  5. STORE    — Supabase sector_documents + Pinecone E5 + Neo4j enrichment
  6. TRACK    — Per-PDF progress in data/ingest/inrs-state.json

Usage:
  source .env.local
  python3 ops/ingest-inrs.py --catalog-only                 # Build catalog
  python3 ops/ingest-inrs.py --batch-size 5                 # Ingest 5 PDFs
  python3 ops/ingest-inrs.py --batch-size 10 --dry-run      # Preview
  python3 ops/ingest-inrs.py --theme chimique                # Filter by theme
  python3 ops/ingest-inrs.py --status                        # Show progress
  python3 ops/ingest-inrs.py --daemon --interval 600         # 10min cycles
  nohup python3 ops/ingest-inrs.py --daemon --interval 600 --batch-size 5 > data/ingest/inrs.log 2>&1 &
"""

# ── Force IPv4 globally (IPv6 broken on this VM) ─────────────────────────
import socket
from socket import AF_INET

_original_getaddrinfo = socket.getaddrinfo


def _ipv4_getaddrinfo(host, port, family=0, type_=0, proto=0, flags=0):
    return _original_getaddrinfo(host, port, AF_INET, type_, proto, flags)


socket.getaddrinfo = _ipv4_getaddrinfo

# ── Standard imports ─────────────────────────────────────────────────────
import argparse
import hashlib
import json
import os
import re
import signal
import ssl
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ── Force line-buffered output ───────────────────────────────────────────
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

# ── SSL context (permissive for government PDFs) ────────────────────────
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE

# =========================================================================
# CONFIGURATION
# =========================================================================

# INRS
INRS_BASE = "https://www.inrs.fr"
INRS_SEARCH_URL = f"{INRS_BASE}/publications/recherche-catalogue-toutes-les-nouveautes.html"
INRS_DELAY = 2.0  # seconds between requests to inrs.fr (respectful crawling)
INRS_USER_AGENT = "Mozilla/5.0 (compatible; Nomos-INRS-Ingest/1.0; +https://nomos.ai)"

# Docling S6
DOCLING_BASE = os.environ.get("DOCLING_URL", "https://lbjlincoln-nomos-docling-api.hf.space")
DOCLING_CONVERT_URL = f"{DOCLING_BASE}/convert-url"
DOCLING_HEALTH_URL = f"{DOCLING_BASE}/health"
DOCLING_TIMEOUT = 600  # CPU-basic is slow

# Pinecone E5 integrated embedding
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY", "")
PINECONE_HOST = "https://sectors-e5-multilingual-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
PINECONE_UPSERT_URL = f"{PINECONE_HOST}/records/namespaces/sectors/upsert"
PINECONE_TIMEOUT = 20

# Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://ayqviqmxifzmhphiqfmj.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_API_KEY", "")
SUPABASE_TABLE = "sector_documents"

# Neo4j (for enrichment)
NEO4J_URI = os.environ.get("NEO4J_URI", "neo4j+s://38c949a2.databases.neo4j.io")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "")

# LiteLLM (for entity extraction)
LITELLM_URL = os.environ.get("LITELLM_PROXY_URL",
    "https://lbjlincoln-nomos-rag-engine-7.hf.space")
LITELLM_CHAT_URL = f"{LITELLM_URL}/v1/chat/completions"
LITELLM_KEY = os.environ.get("LITELLM_MASTER_KEY", "sk-litellm-nomos-2026")

# Paths
DATA_DIR = REPO_ROOT / "data" / "ingest"
CATALOG_FILE = DATA_DIR / "inrs-catalog.json"
STATE_FILE = DATA_DIR / "inrs-state.json"
LOG_FILE = DATA_DIR / "inrs.jsonl"
PID_FILE = DATA_DIR / "inrs.pid"

# Processing
SECTOR = "industrie"
MAX_FILE_SIZE_MB = 10
CHUNK_TARGET_MIN = 500
CHUNK_TARGET_MAX = 1500
CHUNK_OVERLAP = 100
MIN_CHUNK_LEN = 80
MAX_TEXT_FOR_E5 = 1500
PINECONE_DELAY = 0.05
DOCLING_COOLDOWN = 5
DEFAULT_BATCH_SIZE = 5
DEFAULT_INTERVAL = 600

# Graceful shutdown
_shutdown_requested = False


def _signal_handler(signum, frame):
    global _shutdown_requested
    _shutdown_requested = True
    log("Shutdown signal received, finishing current PDF...", "WARN")


signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)


# =========================================================================
# LOGGING
# =========================================================================

def log(msg, level="INFO"):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ts_short = ts[11:19]
    prefix = {"INFO": "+", "WARN": "!", "ERROR": "X", "OK": "v", "SKIP": "-"}.get(level, " ")
    print(f"[{ts_short}] [{prefix}] {msg}", flush=True)

    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        entry = {"ts": ts, "level": level, "msg": msg}
        with open(LOG_FILE, "a") as f:
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


# =========================================================================
# INRS CATALOG — Top 200+ important publications (curated + scraped)
# =========================================================================

# Priority INRS ED publications for Industrie sector (curated top 50+)
# These are the most referenced guides in French workplace safety
CURATED_INRS_PUBLICATIONS = [
    # -- Risques chimiques --
    {"ref": "ED 6547", "title": "Guide de prevention des risques chimiques", "theme": "risques_chimiques"},
    {"ref": "ED 984", "title": "Les melanges explosifs — Gaz et vapeurs", "theme": "risques_chimiques"},
    {"ref": "ED 6027", "title": "Agents chimiques CMR — Reperer pour prevenir", "theme": "risques_chimiques"},
    {"ref": "ED 6150", "title": "Risque chimique — Fiche ou notice de poste", "theme": "risques_chimiques"},
    {"ref": "ED 6015", "title": "Stockage des produits chimiques au laboratoire", "theme": "risques_chimiques"},
    {"ref": "ED 753", "title": "Les valeurs limites d'exposition professionnelle", "theme": "risques_chimiques"},
    {"ref": "ED 6306", "title": "Agents chimiques — Guide d'evaluation des risques", "theme": "risques_chimiques"},
    {"ref": "ED 6197", "title": "Solvants — Guide de prevention", "theme": "risques_chimiques"},
    # -- TMS / Ergonomie --
    {"ref": "ED 6161", "title": "Troubles musculosquelettiques — Demarche de prevention", "theme": "tms_ergonomie"},
    {"ref": "ED 6226", "title": "Methode d'analyse des manutentions manuelles", "theme": "tms_ergonomie"},
    {"ref": "ED 6291", "title": "TMS du membre superieur — Guide pour les preventeurs", "theme": "tms_ergonomie"},
    {"ref": "ED 6318", "title": "Conception des postes de travail — Ergonomie", "theme": "tms_ergonomie"},
    {"ref": "ED 862", "title": "Les activites de manutention manuelle", "theme": "tms_ergonomie"},
    {"ref": "ED 131", "title": "Gestes et postures de securite dans le travail", "theme": "tms_ergonomie"},
    # -- Machines / Equipements --
    {"ref": "ED 6122", "title": "Securite des machines — Prevenir les risques mecaniques", "theme": "machines"},
    {"ref": "ED 6110", "title": "Consignation et deconsignation", "theme": "machines"},
    {"ref": "ED 6129", "title": "Chariots automoteurs — Conduite en securite", "theme": "machines"},
    {"ref": "ED 6177", "title": "Equipements de protection individuelle", "theme": "machines"},
    {"ref": "ED 6321", "title": "Machines portatives — Prevention des risques", "theme": "machines"},
    {"ref": "ED 6270", "title": "Robots industriels et collaboratifs", "theme": "machines"},
    # -- Bruit --
    {"ref": "ED 6035", "title": "Bruit — Demarche de prevention", "theme": "bruit"},
    {"ref": "ED 6347", "title": "Insonorisation des locaux de travail", "theme": "bruit"},
    {"ref": "ED 997", "title": "Le bruit en milieu de travail", "theme": "bruit"},
    {"ref": "ED 6103", "title": "Evaluation des risques lies au bruit", "theme": "bruit"},
    # -- Risques psychosociaux --
    {"ref": "ED 6011", "title": "Stress au travail — Guide pour les entreprises", "theme": "rps"},
    {"ref": "ED 6012", "title": "Harcelement et violences internes au travail", "theme": "rps"},
    {"ref": "ED 6070", "title": "Evaluation des risques psychosociaux", "theme": "rps"},
    {"ref": "ED 6349", "title": "Agir sur les risques psychosociaux", "theme": "rps"},
    # -- Incendie / ATEX --
    {"ref": "ED 990", "title": "Les extincteurs d'incendie portatifs", "theme": "incendie_atex"},
    {"ref": "ED 945", "title": "ATEX — Les atmospheres explosives", "theme": "incendie_atex"},
    {"ref": "ED 6030", "title": "Incendie sur le lieu de travail — Prevention", "theme": "incendie_atex"},
    {"ref": "ED 6369", "title": "Prevention du risque ATEX en entreprise", "theme": "incendie_atex"},
    # -- Risque electrique --
    {"ref": "ED 6127", "title": "Risque electrique — Prevention", "theme": "risque_electrique"},
    {"ref": "ED 6313", "title": "Habilitation electrique — Qui est concerne", "theme": "risque_electrique"},
    {"ref": "ED 6424", "title": "Secteur logistique — Risques electriques", "theme": "risque_electrique"},
    # -- Ventilation / Aeration --
    {"ref": "ED 695", "title": "Guide pratique de ventilation — Principes generaux", "theme": "ventilation"},
    {"ref": "ED 657", "title": "Assainissement de l'air des locaux de travail", "theme": "ventilation"},
    {"ref": "ED 6298", "title": "Ventilation des espaces confines", "theme": "ventilation"},
    # -- Document unique / Evaluation des risques --
    {"ref": "ED 887", "title": "Evaluation des risques professionnels", "theme": "evaluation_risques"},
    {"ref": "ED 840", "title": "Document unique d'evaluation des risques", "theme": "evaluation_risques"},
    {"ref": "ED 886", "title": "Principes generaux de prevention", "theme": "evaluation_risques"},
    {"ref": "ED 6230", "title": "Demarche de prevention des risques professionnels", "theme": "evaluation_risques"},
    {"ref": "ED 6389", "title": "Plan de prevention — Interventions entreprises exterieures", "theme": "evaluation_risques"},
    # -- Chutes / Travail en hauteur --
    {"ref": "ED 6110", "title": "Travail en hauteur — Prevention des chutes", "theme": "chutes_hauteur"},
    {"ref": "ED 6196", "title": "Echafaudages — Prevention des risques", "theme": "chutes_hauteur"},
    {"ref": "ED 6233", "title": "Garde-corps — Conception et utilisation", "theme": "chutes_hauteur"},
    # -- Amiante --
    {"ref": "ED 6091", "title": "Amiante — Obligations et prevention", "theme": "amiante"},
    {"ref": "ED 6262", "title": "Interventions sur materiaux amiantiferes", "theme": "amiante"},
    # -- Risques biologiques --
    {"ref": "ED 6034", "title": "Les risques biologiques en milieu professionnel", "theme": "risques_biologiques"},
    {"ref": "ED 6360", "title": "Prevention des zoonoses en milieu professionnel", "theme": "risques_biologiques"},
    # -- Organisation du travail / Management SST --
    {"ref": "ED 6413", "title": "Systeme de management de la sante-securite ISO 45001", "theme": "management_sst"},
    {"ref": "ED 6179", "title": "Accueil des nouveaux embauches en securite", "theme": "management_sst"},
    {"ref": "ED 6481", "title": "Analyser les accidents du travail", "theme": "management_sst"},
    {"ref": "ED 6175", "title": "Arbre des causes — Methode d'analyse", "theme": "management_sst"},
    # -- Secteurs specifiques --
    {"ref": "ED 6438", "title": "Transport routier de marchandises", "theme": "secteurs_specifiques"},
    {"ref": "ED 6188", "title": "Aide a domicile — Sante et securite", "theme": "secteurs_specifiques"},
    {"ref": "ED 4337", "title": "Maintenance industrielle — Accueil securite", "theme": "secteurs_specifiques"},
    {"ref": "ED 6557", "title": "Unites de methanisation et compostage", "theme": "secteurs_specifiques"},
    {"ref": "ED 6483", "title": "Prevention dans la grande distribution", "theme": "secteurs_specifiques"},
    {"ref": "ED 6402", "title": "Environnement sonore en bureaux ouverts", "theme": "secteurs_specifiques"},
    # -- TJ series (Aide-memoire juridique) --
    {"ref": "TJ 5", "title": "Aide-memoire juridique — Les accidents du travail", "theme": "juridique_sst"},
    {"ref": "TJ 13", "title": "Aide-memoire juridique — Duree du travail", "theme": "juridique_sst"},
    {"ref": "TJ 16", "title": "Aide-memoire juridique — Le CHSCT/CSE", "theme": "juridique_sst"},
    {"ref": "TJ 20", "title": "Aide-memoire juridique — Amiante", "theme": "juridique_sst"},
    {"ref": "TJ 24", "title": "Aide-memoire juridique — Risques psychosociaux", "theme": "juridique_sst"},
    # -- Additional high-value ED --
    {"ref": "ED 6485", "title": "Troubles de l'attention — Prevenir les accidents", "theme": "rps"},
    {"ref": "ED 4455", "title": "BTP — Accueil securite", "theme": "secteurs_specifiques"},
    {"ref": "ED 4467", "title": "Hotellerie-Restauration — Accueil securite", "theme": "secteurs_specifiques"},
    {"ref": "ED 4440", "title": "Retrait des detecteurs de fumee a chambre d'ionisation", "theme": "incendie_atex"},
    {"ref": "ED 950", "title": "Conception des lieux et situations de travail", "theme": "evaluation_risques"},
    {"ref": "ED 6187", "title": "Agents biologiques — Classification", "theme": "risques_biologiques"},
    {"ref": "ED 6148", "title": "Nanomateriaux — Prevention des risques", "theme": "risques_chimiques"},
    {"ref": "ED 6244", "title": "Rayonnements optiques — Prevention", "theme": "rayonnements"},
    {"ref": "ED 6088", "title": "Rayonnements ionisants — Guide de prevention", "theme": "rayonnements"},
]

# Map of INRS themes for catalog enrichment
INRS_THEMES = {
    "risques_chimiques": "Risques chimiques",
    "tms_ergonomie": "TMS et ergonomie",
    "machines": "Machines et equipements",
    "bruit": "Bruit",
    "rps": "Risques psychosociaux",
    "incendie_atex": "Incendie et ATEX",
    "risque_electrique": "Risque electrique",
    "ventilation": "Ventilation",
    "evaluation_risques": "Evaluation des risques",
    "chutes_hauteur": "Chutes et travail en hauteur",
    "amiante": "Amiante",
    "risques_biologiques": "Risques biologiques",
    "management_sst": "Management SST",
    "secteurs_specifiques": "Secteurs specifiques",
    "juridique_sst": "Aide-memoire juridique SST",
    "rayonnements": "Rayonnements",
}


def build_pdf_url(ref):
    """Build the INRS PDF download URL from a reference number.

    INRS PDF URL pattern: /dam/inrs/CataloguePapier/{TYPE}/TI-{TYPE}-{NUM}.pdf
    Examples:
      ED 6547 -> /dam/inrs/CataloguePapier/ED/TI-ED-6547.pdf
      TJ 5    -> /dam/inrs/CataloguePapier/TJ/TI-TJ-5.pdf
    """
    ref = ref.strip()
    # Parse reference: "ED 6547" -> type="ED", num="6547"
    parts = ref.split(None, 1)
    if len(parts) != 2:
        return None
    doc_type = parts[0].upper()
    doc_num = parts[1].strip()
    return f"{INRS_BASE}/dam/inrs/CataloguePapier/{doc_type}/TI-{doc_type}-{doc_num}.pdf"


def url_hash(url):
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]


# =========================================================================
# CATALOG BUILDING
# =========================================================================

def scrape_inrs_page(page_url, page_num=1):
    """Scrape an INRS search results page to extract publication info.

    Returns list of dicts: [{ref, title, pdf_url, doc_type, theme}, ...]
    """
    headers = {
        "User-Agent": INRS_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "fr-FR,fr;q=0.9",
    }

    status, body, err = http_request(page_url, headers=headers, timeout=30)
    if err:
        log(f"INRS page {page_num} fetch failed: {err}", "ERROR")
        return [], False

    if status != 200:
        log(f"INRS page {page_num} returned HTTP {status}", "ERROR")
        return [], False

    html = body.decode("utf-8", errors="replace")
    publications = []

    # Extract PDF links and references from HTML
    # Pattern: /dam/inrs/CataloguePapier/ED/TI-ED-XXXX.pdf
    pdf_pattern = re.compile(
        r'href="(/dam/inrs/CataloguePapier/(\w+)/TI-(\w+[-\w]*?)\.pdf)"',
        re.IGNORECASE,
    )

    # Also try to extract titles near PDF links
    # The INRS HTML typically has title in an <a> or <h3> near the PDF link
    title_pattern = re.compile(
        r'<(?:a|h3|h4|span)[^>]*class="[^"]*(?:titre|title|nom)[^"]*"[^>]*>'
        r'(?:<[^>]+>)*\s*([^<]+)',
        re.IGNORECASE,
    )

    # Extract all PDF references from the page
    seen_refs = set()
    for match in pdf_pattern.finditer(html):
        pdf_path = match.group(1)
        doc_type = match.group(2).upper()
        raw_ref = match.group(3)  # e.g., "ED-6547" or "TJ-5"

        # Build reference string
        if raw_ref.startswith(doc_type + "-"):
            num = raw_ref[len(doc_type) + 1:]
            ref = f"{doc_type} {num}"
        else:
            ref = raw_ref.replace("-", " ")

        if ref in seen_refs:
            continue
        seen_refs.add(ref)

        pdf_url = f"{INRS_BASE}{pdf_path}"

        publications.append({
            "ref": ref,
            "title": "",  # Will be filled from catalog or curated list
            "pdf_url": pdf_url,
            "doc_type": doc_type,
            "theme": "",
        })

    # Check if there is a "next page" link
    has_next = "Suivant" in html or f"pagine({page_num + 1})" in html

    return publications, has_next


def build_catalog(max_pages=20):
    """Build the full INRS catalog from curated list + web scraping.

    Returns catalog dict with all publications.
    """
    catalog = {
        "created": datetime.now(timezone.utc).isoformat(),
        "source": "INRS (Institut National de Recherche et de Securite)",
        "url": "https://www.inrs.fr/publications.html",
        "publications": {},
        "stats": {
            "total": 0,
            "by_theme": {},
            "by_type": {},
        },
    }

    # Phase 1: Load curated publications (guaranteed high-quality)
    log(f"Loading {len(CURATED_INRS_PUBLICATIONS)} curated INRS publications...", "INFO")
    for pub in CURATED_INRS_PUBLICATIONS:
        ref = pub["ref"]
        pdf_url = build_pdf_url(ref)
        if not pdf_url:
            continue

        doc_type = ref.split()[0].upper()
        catalog["publications"][ref] = {
            "ref": ref,
            "title": pub["title"],
            "pdf_url": pdf_url,
            "doc_type": doc_type,
            "theme": pub.get("theme", ""),
            "theme_label": INRS_THEMES.get(pub.get("theme", ""), ""),
            "source": "curated",
            "priority": "high",
        }

    log(f"Curated: {len(catalog['publications'])} publications loaded", "OK")

    # Phase 2: Scrape INRS website for additional publications
    log("Scraping INRS catalog for additional publications...", "INFO")
    scraped_count = 0

    # Scrape the "toutes les nouveautes" pages + a keyword search
    search_urls = [
        (f"{INRS_BASE}/publications/recherche-catalogue-toutes-les-nouveautes.html", "nouveautes"),
    ]

    for base_url, label in search_urls:
        for page in range(1, max_pages + 1):
            # INRS uses form POST for pagination, but we can try GET params
            page_url = base_url
            if page > 1:
                # The pagination uses JavaScript form submission; we try the
                # base URL which shows page 1. For deeper scraping we would
                # need a headless browser. The curated list covers top docs.
                break

            log(f"Scraping {label} page {page}...", "INFO")
            pubs, has_next = scrape_inrs_page(page_url, page)

            for pub in pubs:
                ref = pub["ref"]
                if ref not in catalog["publications"]:
                    catalog["publications"][ref] = {
                        "ref": ref,
                        "title": pub.get("title", ""),
                        "pdf_url": pub["pdf_url"],
                        "doc_type": pub.get("doc_type", "ED"),
                        "theme": "",
                        "theme_label": "",
                        "source": "scraped",
                        "priority": "normal",
                    }
                    scraped_count += 1

            time.sleep(INRS_DELAY)

            if not has_next:
                break

    log(f"Scraped: {scraped_count} additional publications", "OK")

    # Phase 3: Compute stats
    for ref, pub in catalog["publications"].items():
        theme = pub.get("theme", "unknown") or "unknown"
        doc_type = pub.get("doc_type", "ED")

        catalog["stats"]["by_theme"][theme] = catalog["stats"]["by_theme"].get(theme, 0) + 1
        catalog["stats"]["by_type"][doc_type] = catalog["stats"]["by_type"].get(doc_type, 0) + 1

    catalog["stats"]["total"] = len(catalog["publications"])
    catalog["last_updated"] = datetime.now(timezone.utc).isoformat()

    # Save catalog
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = str(CATALOG_FILE) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)
    os.replace(tmp, str(CATALOG_FILE))

    log(f"Catalog saved: {catalog['stats']['total']} publications -> {CATALOG_FILE}", "OK")
    return catalog


def load_catalog():
    """Load existing catalog or build it."""
    if CATALOG_FILE.exists():
        try:
            data = json.loads(CATALOG_FILE.read_text("utf-8"))
            if data.get("publications"):
                return data
        except Exception:
            pass
    return build_catalog()


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
        "processed_refs": {},  # ref -> {status, chunks, ts, ...}
        "stats": {
            "total_processed": 0,
            "total_chunks": 0,
            "total_vectors": 0,
            "total_supabase": 0,
            "total_errors": 0,
            "total_skipped": 0,
            "cycles": 0,
        },
    }


def save_state(state):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    tmp = str(STATE_FILE) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False, default=str)
    os.replace(tmp, str(STATE_FILE))


# =========================================================================
# PDF DOWNLOAD
# =========================================================================

def download_pdf(pdf_url, max_size_mb=MAX_FILE_SIZE_MB):
    """Download a PDF to /tmp. Returns (filepath, size_bytes, error).

    Cleans up on error. Caller must clean up on success.
    """
    headers = {
        "User-Agent": INRS_USER_AGENT,
        "Accept": "application/pdf",
    }

    # Check file size first with HEAD
    try:
        req = urllib.request.Request(pdf_url, method="HEAD", headers=headers)
        resp = urllib.request.urlopen(req, timeout=15, context=_ssl_ctx)
        content_length = resp.headers.get("Content-Length")
        if content_length and int(content_length) > max_size_mb * 1024 * 1024:
            return None, 0, f"PDF too large: {int(content_length) / (1024*1024):.1f}MB"
    except Exception:
        pass  # HEAD failed, try download anyway

    # Generate temp filename
    fname = f"inrs-{url_hash(pdf_url)}.pdf"
    filepath = Path("/tmp") / fname

    try:
        req = urllib.request.Request(pdf_url, headers=headers)
        resp = urllib.request.urlopen(req, timeout=120, context=_ssl_ctx)

        # Stream download with size limit
        max_bytes = max_size_mb * 1024 * 1024
        chunks = []
        total_read = 0

        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            total_read += len(chunk)
            if total_read > max_bytes:
                return None, 0, f"PDF exceeds {max_size_mb}MB during download"
            chunks.append(chunk)

        with open(filepath, "wb") as f:
            for chunk in chunks:
                f.write(chunk)

        return str(filepath), total_read, None

    except Exception as e:
        # Cleanup on error
        try:
            filepath.unlink(missing_ok=True)
        except Exception:
            pass
        return None, 0, f"Download error: {type(e).__name__}: {str(e)[:200]}"


def cleanup_pdf(filepath):
    """Delete a PDF from /tmp."""
    try:
        Path(filepath).unlink(missing_ok=True)
    except Exception:
        pass


# =========================================================================
# PDF EXTRACTION — Docling S6 + fallback
# =========================================================================

def extract_via_docling(pdf_url):
    """Send PDF URL to Docling S6 for extraction.

    Returns (text, metadata_dict, error_string).
    """
    payload = json.dumps({
        "url": pdf_url,
        "chunk_size": 1500,
        "chunk_overlap": 100,
    }).encode("utf-8")

    headers = {"Content-Type": "application/json"}

    start = time.time()
    status, body, err = http_request(
        DOCLING_CONVERT_URL, data=payload, headers=headers,
        method="POST", timeout=DOCLING_TIMEOUT,
    )
    elapsed = time.time() - start

    if err:
        return None, {"elapsed_s": round(elapsed, 1)}, f"Docling error: {err}"

    try:
        data = json.loads(body.decode("utf-8"))
    except Exception as e:
        return None, {"elapsed_s": round(elapsed, 1)}, f"Docling JSON parse: {e}"

    if data.get("status") == "error":
        return None, {"elapsed_s": round(elapsed, 1)}, f"Docling: {data.get('error', 'unknown')}"

    text = data.get("full_text", "") or data.get("markdown", "") or data.get("text", "")
    meta = {
        "num_pages": data.get("num_pages", 0),
        "num_tables": data.get("num_tables", 0),
        "text_chars": len(text),
        "elapsed_s": round(elapsed, 1),
        "chunks_from_docling": len(data.get("chunks", [])),
    }

    return text, meta, None


def extract_via_pdfplumber(filepath):
    """Fallback: extract text from local PDF using pdfplumber.

    Returns (text, metadata_dict, error_string).
    """
    try:
        import pdfplumber
    except ImportError:
        # Try PyPDF2 as second fallback
        return extract_via_pypdf2(filepath)

    try:
        text_parts = []
        num_pages = 0
        with pdfplumber.open(filepath) as pdf:
            num_pages = len(pdf.pages)
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

        full_text = "\n\n".join(text_parts)
        meta = {
            "num_pages": num_pages,
            "text_chars": len(full_text),
            "extraction_method": "pdfplumber",
        }
        return full_text, meta, None

    except Exception as e:
        return None, {}, f"pdfplumber error: {type(e).__name__}: {str(e)[:200]}"


def extract_via_pypdf2(filepath):
    """Second fallback: extract text using PyPDF2.

    Returns (text, metadata_dict, error_string).
    """
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        return None, {}, "Neither pdfplumber nor PyPDF2 installed"

    try:
        reader = PdfReader(filepath)
        text_parts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

        full_text = "\n\n".join(text_parts)
        meta = {
            "num_pages": len(reader.pages),
            "text_chars": len(full_text),
            "extraction_method": "PyPDF2",
        }
        return full_text, meta, None

    except Exception as e:
        return None, {}, f"PyPDF2 error: {type(e).__name__}: {str(e)[:200]}"


# =========================================================================
# SECTION-AWARE CHUNKING
# =========================================================================

def detect_sections(text):
    """Detect section/chapter boundaries in INRS documents.

    INRS documents typically use:
    - Numbered chapters: "1. Introduction", "2. Evaluation des risques"
    - Unnumbered sections with uppercase or bold markers
    - Page breaks indicated by form feeds or multiple newlines

    Returns list of (section_title, start_pos, end_pos).
    """
    sections = []

    # Patterns for section detection (French INRS conventions)
    section_patterns = [
        # "Chapitre 3 — Evaluation des risques"
        re.compile(r'^(Chapitre\s+\d+[\s.:\-—]+.{5,80})$', re.MULTILINE),
        # "3. Evaluation des risques" or "3 Evaluation des risques"
        re.compile(r'^(\d+[\.\)]\s+[A-Z\xc0-\xd6\xd8-\xde].{5,80})$', re.MULTILINE),
        # "3.2 Mesures de prevention" (subsections)
        re.compile(r'^(\d+\.\d+[\.\)]*\s+[A-Z\xc0-\xd6\xd8-\xde].{5,80})$', re.MULTILINE),
        # "INTRODUCTION", "CONCLUSION", "ANNEXE" (uppercase section headers)
        re.compile(r'^([A-Z\xc0-\xd6\xd8-\xde][A-Z\xc0-\xd6\xd8-\xde\s]{4,60})$', re.MULTILINE),
        # "I. Introduction" (Roman numerals)
        re.compile(r'^((?:I{1,3}|IV|V|VI{0,3}|IX|X)[\.\)]\s+.{5,80})$', re.MULTILINE),
    ]

    matches = []
    for pattern in section_patterns:
        for m in pattern.finditer(text):
            title = m.group(1).strip()
            # Filter out false positives (too short, looks like a sentence fragment)
            if len(title) < 5 or title.count(" ") > 15:
                continue
            matches.append((m.start(), title))

    # Sort by position, deduplicate nearby matches
    matches.sort(key=lambda x: x[0])
    filtered = []
    for pos, title in matches:
        if filtered and pos - filtered[-1][0] < 50:
            # Keep the one with the more descriptive title
            if len(title) > len(filtered[-1][1]):
                filtered[-1] = (pos, title)
            continue
        filtered.append((pos, title))

    # Build sections with start/end positions
    for i, (pos, title) in enumerate(filtered):
        end_pos = filtered[i + 1][0] if i + 1 < len(filtered) else len(text)
        sections.append((title, pos, end_pos))

    return sections


def chunk_by_sections(text, ref, title, theme, num_pages=0):
    """Chunk text by detected sections, falling back to sliding window.

    Each chunk includes rich INRS metadata for RAG retrieval.
    Returns list of chunk dicts.
    """
    if not text or len(text) < MIN_CHUNK_LEN:
        return []

    # Clean text
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    text = re.sub(r'\n\s*Page \d+ (?:of|sur|/) \d+\s*\n', '\n', text)
    text = re.sub(r'(?:\xa9|Copyright).*?\d{4}.*?\n', '', text, flags=re.IGNORECASE)
    text = text.strip()

    sections = detect_sections(text)
    chunks = []

    if sections and len(sections) >= 2:
        # Section-based chunking
        for section_title, start, end in sections:
            section_text = text[start:end].strip()
            if len(section_text) < MIN_CHUNK_LEN:
                continue

            # If section is too long, split into sub-chunks
            if len(section_text) > CHUNK_TARGET_MAX * 2:
                sub_chunks = _sliding_window_chunks(section_text)
                for i, sub in enumerate(sub_chunks):
                    chunk_section = section_title
                    if len(sub_chunks) > 1:
                        chunk_section = f"{section_title} (partie {i+1}/{len(sub_chunks)})"
                    chunks.append(_make_chunk_dict(
                        sub, ref, title, theme, chunk_section, num_pages, start, end,
                    ))
            else:
                chunks.append(_make_chunk_dict(
                    section_text, ref, title, theme, section_title, num_pages, start, end,
                ))
    else:
        # Fallback: sliding window chunking
        sub_chunks = _sliding_window_chunks(text)
        for i, sub in enumerate(sub_chunks):
            section_label = f"Section {i+1}/{len(sub_chunks)}"
            chunks.append(_make_chunk_dict(
                sub, ref, title, theme, section_label, num_pages, 0, len(text),
            ))

    return chunks


def _sliding_window_chunks(text):
    """Split text into overlapping chunks of CHUNK_TARGET_MIN to CHUNK_TARGET_MAX chars."""
    if len(text) <= CHUNK_TARGET_MAX:
        return [text] if len(text) >= MIN_CHUNK_LEN else []

    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = start + CHUNK_TARGET_MAX

        if end >= text_len:
            chunk = text[start:].strip()
            if len(chunk) >= MIN_CHUNK_LEN:
                chunks.append(chunk)
            break

        # Prefer splitting at paragraph or sentence boundary
        candidate = text[start:end]
        para_break = candidate.rfind('\n\n')
        if para_break > CHUNK_TARGET_MIN * 0.6:
            end = start + para_break + 2
        else:
            for sep in ['. ', '.\n', '? ', '!\n', ';\n', ' ; ']:
                sent_break = candidate.rfind(sep)
                if sent_break > CHUNK_TARGET_MIN * 0.6:
                    end = start + sent_break + len(sep)
                    break

        chunk = text[start:end].strip()
        if len(chunk) >= MIN_CHUNK_LEN:
            chunks.append(chunk)

        start = end - CHUNK_OVERLAP
        if start <= (end - CHUNK_TARGET_MAX):
            start = end

    return chunks


def _make_chunk_dict(text, ref, title, theme, section, num_pages, start_pos, end_pos):
    """Build a chunk dict with full INRS metadata."""
    # Estimate page range from character positions
    chars_per_page = max(1, (end_pos or 1))  # avoid div by zero
    if num_pages > 0:
        chars_per_page = max(1, end_pos / num_pages) if end_pos > 0 else 2000
        page_start = max(1, int(start_pos / chars_per_page) + 1)
        page_end = min(num_pages, int(end_pos / chars_per_page) + 1)
        page_range = f"p.{page_start}-{page_end}" if page_start != page_end else f"p.{page_start}"
    else:
        page_range = ""

    # Truncate text for E5 embedding
    embed_text = text[:MAX_TEXT_FOR_E5]

    theme_label = INRS_THEMES.get(theme, theme)
    full_reference = f"INRS {ref}"
    if title:
        full_reference += f" — {title}"
    if section:
        full_reference += f", {section}"

    return {
        "text": embed_text,
        "full_text": text,
        "metadata": {
            "source": "INRS",
            "reference": ref,
            "title": title,
            "section": section,
            "page_range": page_range,
            "theme": theme,
            "theme_label": theme_label,
            "full_reference": full_reference,
            "doc_type": ref.split()[0] if ref else "ED",
            "sector": SECTOR,
        },
    }


# =========================================================================
# STORAGE — Supabase + Pinecone + Neo4j
# =========================================================================

def store_chunk_supabase(chunk, chunk_idx, ref):
    """Insert a chunk into Supabase sector_documents."""
    if not SUPABASE_KEY:
        return False, "SUPABASE_API_KEY not set"

    meta = chunk["metadata"]
    doc_id = f"inrs-{url_hash(ref)}-{chunk_idx:03d}"

    row = {
        "id": doc_id,
        "sector": SECTOR,
        "dataset_name": "inrs",
        "pipeline": "inrs-ingest",
        "question": f"[INRS {meta.get('reference', '')}] {meta.get('section', '')}",
        "answer": "",
        "context": chunk["full_text"][:10000],
        "metadata": {
            "source": "inrs",
            "reference": meta.get("reference", ""),
            "title": meta.get("title", ""),
            "section": meta.get("section", ""),
            "page_range": meta.get("page_range", ""),
            "theme": meta.get("theme", ""),
            "theme_label": meta.get("theme_label", ""),
            "full_reference": meta.get("full_reference", ""),
            "doc_type": meta.get("doc_type", "ED"),
            "has_entities": False,
            "entity_count": 0,
            "phase": "inrs-ingest",
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        },
        "tenant_id": SECTOR,
    }

    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

    payload = json.dumps(row, ensure_ascii=False).encode("utf-8")
    status, body, err = http_request(url, data=payload, headers=headers,
                                      method="POST", timeout=30)
    if err:
        return False, f"Supabase: {err}"
    if status not in (200, 201, 204):
        body_str = body.decode("utf-8", errors="replace")[:200] if body else "empty"
        return False, f"Supabase HTTP {status}: {body_str}"

    return True, None


def store_chunk_pinecone(chunk, chunk_idx, ref):
    """Upsert a chunk into Pinecone E5 integrated embedding index."""
    if not PINECONE_API_KEY:
        return False, "PINECONE_API_KEY not set"

    meta = chunk["metadata"]
    record_id = f"inrs-{url_hash(ref)}-{chunk_idx:03d}"

    record = {
        "_id": record_id,
        "text": chunk["text"],
        "sector": SECTOR,
        "source": "inrs",
        "reference": meta.get("reference", ""),
        "title": meta.get("title", "")[:200],
        "section": meta.get("section", "")[:200],
        "theme": meta.get("theme", ""),
        "full_reference": meta.get("full_reference", "")[:300],
    }

    data = json.dumps(record, ensure_ascii=False).encode("utf-8")
    headers = {
        "Api-Key": PINECONE_API_KEY,
        "Content-Type": "application/json",
    }

    for attempt in range(3):
        status, body, err = http_request(
            PINECONE_UPSERT_URL, data=data, headers=headers,
            method="POST", timeout=PINECONE_TIMEOUT,
        )
        if status in (200, 201):
            return True, None
        if status == 409:
            return True, None  # Already exists
        if status == 429:
            time.sleep(min(2 ** attempt + 0.5, 5))
            continue
        if attempt == 2:
            err_text = body.decode("utf-8", errors="replace")[:200] if body else str(err)
            return False, f"Pinecone HTTP {status}: {err_text}"
        time.sleep(0.5)

    return False, "Pinecone max retries"


def store_chunks(chunks, ref):
    """Store all chunks for a document in both Supabase and Pinecone.

    Returns (supabase_count, pinecone_count, errors).
    """
    sb_ok = 0
    pc_ok = 0
    errors = 0

    for i, chunk in enumerate(chunks):
        # Supabase
        ok, err = store_chunk_supabase(chunk, i, ref)
        if ok:
            sb_ok += 1
        else:
            if err:
                log(f"    Supabase chunk {i}: {err}", "WARN")
            errors += 1

        # Pinecone
        ok, err = store_chunk_pinecone(chunk, i, ref)
        if ok:
            pc_ok += 1
        else:
            if err:
                log(f"    Pinecone chunk {i}: {err}", "WARN")
            errors += 1

        # Small delay to avoid rate limits
        if PINECONE_DELAY > 0:
            time.sleep(PINECONE_DELAY)

    return sb_ok, pc_ok, errors


# =========================================================================
# NEO4J ENRICHMENT (entity extraction via LiteLLM)
# =========================================================================

def enrich_document_neo4j(ref, title, chunks_text):
    """Extract entities from INRS document and store in Neo4j.

    Uses LiteLLM for entity extraction, then stores via Neo4j Bolt driver.
    Returns (entity_count, error_string).
    """
    if not NEO4J_PASSWORD or not LITELLM_KEY:
        return 0, "NEO4J_PASSWORD or LITELLM_KEY not set"

    # Combine first few chunks for entity extraction
    content = "\n\n".join(chunks_text[:3])[:3000]

    # LLM entity extraction
    payload = json.dumps({
        "model": "smart",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an expert in French workplace safety and industrial hygiene (SST). "
                    "Extract all named entities from this INRS document excerpt.\n\n"
                    "For each entity, provide:\n"
                    "- name: the entity name\n"
                    "- type: one of [Standard, Regulation, Chemical, Equipment, Process, "
                    "Concept, Organization, Risk, Protection_Measure, Location]\n"
                    "- description: one-line description in French\n\n"
                    "Examples: ISO 45001, Code du travail L4121-1, CMR, EPI, DUER, CHSCT, "
                    "ventilation locale, document unique, amiante chrysotile, ATEX zone 1\n\n"
                    "Return ONLY a JSON array: [{\"name\": \"...\", \"type\": \"...\", "
                    "\"description\": \"...\"}]\nIf none found: []"
                ),
            },
            {
                "role": "user",
                "content": f"INRS Document: {ref} — {title}\n\nContent:\n{content}",
            },
        ],
        "temperature": 0.1,
        "max_tokens": 1500,
    }).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LITELLM_KEY}",
    }

    status, body, err = http_request(
        LITELLM_CHAT_URL, data=payload, headers=headers,
        method="POST", timeout=60,
    )

    if err or status != 200:
        return 0, f"LLM error: {err or f'HTTP {status}'}"

    # Parse entities
    entities = []
    try:
        result = json.loads(body.decode("utf-8"))
        content_text = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        content_text = content_text.strip()
        if content_text.startswith("```"):
            lines = content_text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content_text = "\n".join(lines).strip()
        parsed = json.loads(content_text)
        if isinstance(parsed, list):
            entities = parsed
        elif isinstance(parsed, dict) and "entities" in parsed:
            entities = parsed["entities"]
    except Exception:
        # Try regex extraction
        m = re.search(r'\[[\s\S]*?\]', content_text if 'content_text' in dir() else "")
        if m:
            try:
                entities = json.loads(m.group())
            except Exception:
                pass

    if not entities:
        return 0, None  # No entities but not an error

    # Store in Neo4j
    try:
        from neo4j import GraphDatabase
    except ImportError:
        return len(entities), "neo4j driver not installed"

    doc_id = f"inrs-{url_hash(ref)}"
    driver = None
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        with driver.session() as session:
            session.run(
                """
                MERGE (d:SectorDocument {id: $doc_id})
                SET d.title = $title,
                    d.sector = $sector,
                    d.source = 'INRS',
                    d.reference = $ref,
                    d.enriched = true,
                    d.enrichment_ts = datetime(),
                    d.entity_count = $count
                """,
                doc_id=doc_id, title=title[:200], sector=SECTOR,
                ref=ref, count=len(entities),
            )

            stored = 0
            for ent in entities[:20]:
                name = (ent.get("name") or "").strip()
                etype = (ent.get("type") or "Concept").strip()
                desc = (ent.get("description") or "").strip()
                if not name or len(name) < 2:
                    continue
                session.run(
                    """
                    MERGE (e:Entity {name: $name, type: $type})
                    SET e.description = $description,
                        e.sector = $sector,
                        e.source = 'INRS',
                        e.updated_at = datetime()
                    WITH e
                    MATCH (d:SectorDocument {id: $doc_id})
                    MERGE (d)-[:MENTIONS]->(e)
                    """,
                    name=name, type=etype, description=desc[:500],
                    sector=SECTOR, doc_id=doc_id,
                )
                stored += 1

        return stored, None

    except Exception as e:
        return 0, f"Neo4j: {type(e).__name__}: {str(e)[:200]}"
    finally:
        if driver:
            try:
                driver.close()
            except Exception:
                pass


# =========================================================================
# PROCESS ONE PDF
# =========================================================================

def process_one_pdf(pub, state, dry_run=False):
    """Process a single INRS PDF through the full pipeline.

    Returns result dict.
    """
    ref = pub["ref"]
    title = pub.get("title", "")
    pdf_url = pub.get("pdf_url", "")
    theme = pub.get("theme", "")

    result = {
        "ref": ref,
        "title": title[:60],
        "status": "pending",
        "chunks": 0,
        "supabase": 0,
        "pinecone": 0,
        "entities": 0,
        "error": None,
    }

    if not pdf_url:
        result["status"] = "no_url"
        result["error"] = f"No PDF URL for {ref}"
        return result

    if dry_run:
        result["status"] = "dry_run"
        log(f"  [DRY] {ref}: {title[:50]} — {pdf_url}", "SKIP")
        return result

    # Step 1: Extract text via Docling
    log(f"  Extracting via Docling S6...", "INFO")
    text, docling_meta, docling_err = extract_via_docling(pdf_url)

    filepath = None  # Track local file for cleanup

    if docling_err:
        log(f"  Docling failed: {docling_err}", "WARN")

        # Fallback: download + local extraction
        log(f"  Falling back to local PDF extraction...", "INFO")
        filepath, file_size, dl_err = download_pdf(pdf_url)

        if dl_err:
            log(f"  Download failed: {dl_err}", "ERROR")
            result["status"] = "download_error"
            result["error"] = dl_err
            return result

        log(f"  Downloaded: {file_size / 1024:.0f}KB -> {filepath}", "OK")

        text, local_meta, local_err = extract_via_pdfplumber(filepath)
        if local_err:
            text, local_meta, local_err = extract_via_pypdf2(filepath)

        if local_err or not text:
            cleanup_pdf(filepath)
            result["status"] = "extraction_error"
            result["error"] = local_err or "No text extracted"
            return result

        docling_meta = local_meta
        log(f"  Local extraction OK: {local_meta.get('text_chars', 0):,} chars, "
            f"{local_meta.get('num_pages', '?')} pages", "OK")
    else:
        log(f"  Docling OK: {docling_meta.get('text_chars', 0):,} chars, "
            f"{docling_meta.get('num_pages', '?')} pages, "
            f"{docling_meta.get('elapsed_s', '?')}s", "OK")

    # Verify text quality
    if not text or len(text.strip()) < 200:
        if filepath:
            cleanup_pdf(filepath)
        result["status"] = "insufficient_text"
        result["error"] = f"Text too short: {len(text or '')} chars"
        return result

    # Step 2: Section-aware chunking
    num_pages = docling_meta.get("num_pages", 0)
    chunks = chunk_by_sections(text, ref, title, theme, num_pages)

    if not chunks:
        if filepath:
            cleanup_pdf(filepath)
        result["status"] = "no_chunks"
        result["error"] = "Chunking produced 0 chunks"
        return result

    result["chunks"] = len(chunks)
    log(f"  Chunked: {len(chunks)} chunks ({CHUNK_TARGET_MIN}-{CHUNK_TARGET_MAX} chars target)", "OK")

    # Step 3: Store in Supabase + Pinecone
    log(f"  Storing {len(chunks)} chunks (Supabase + Pinecone)...", "INFO")
    sb_ok, pc_ok, store_errors = store_chunks(chunks, ref)
    result["supabase"] = sb_ok
    result["pinecone"] = pc_ok

    log(f"  Storage: Supabase={sb_ok}/{len(chunks)}, Pinecone={pc_ok}/{len(chunks)}, "
        f"errors={store_errors}", "OK" if store_errors == 0 else "WARN")

    # Step 4: Neo4j enrichment (entity extraction)
    log(f"  Enriching via LLM + Neo4j...", "INFO")
    chunks_text = [c["full_text"] for c in chunks]
    entity_count, enrich_err = enrich_document_neo4j(ref, title, chunks_text)
    result["entities"] = entity_count

    if enrich_err:
        log(f"  Enrichment: {enrich_err}", "WARN")
    else:
        log(f"  Enrichment OK: {entity_count} entities", "OK")

    # Cleanup
    if filepath:
        cleanup_pdf(filepath)

    result["status"] = "ok"
    return result


# =========================================================================
# INGESTION CYCLE
# =========================================================================

def run_cycle(catalog, state, batch_size, theme_filter=None, dry_run=False):
    """Run one ingestion cycle: process batch_size unprocessed PDFs."""
    global _shutdown_requested

    cycle_start = time.time()
    cycle_num = state["stats"]["cycles"] + 1

    # Get unprocessed publications (priority: curated first, then scraped)
    unprocessed = []
    for ref, pub in catalog.get("publications", {}).items():
        if ref in state.get("processed_refs", {}):
            status = state["processed_refs"][ref].get("status", "")
            if status == "ok":
                continue  # Already successfully processed
        if theme_filter and pub.get("theme", "") != theme_filter:
            continue
        unprocessed.append(pub)

    # Sort: curated (priority=high) first
    unprocessed.sort(key=lambda p: (0 if p.get("priority") == "high" else 1, p.get("ref", "")))

    # Take batch
    batch = unprocessed[:batch_size]

    print(f"\n{'=' * 60}", flush=True)
    print(f"  INRS INGESTION — Cycle #{cycle_num}", flush=True)
    print(f"  Batch: {len(batch)}/{len(unprocessed)} remaining", flush=True)
    print(f"  Total catalog: {len(catalog.get('publications', {}))}", flush=True)
    print(f"  Already processed: {sum(1 for r in state.get('processed_refs', {}).values() if r.get('status') == 'ok')}", flush=True)
    if theme_filter:
        print(f"  Theme filter: {theme_filter}", flush=True)
    print(f"  Mode: {'DRY RUN' if dry_run else 'LIVE'}", flush=True)
    print(f"  Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC", flush=True)
    print(f"{'=' * 60}", flush=True)

    if not batch:
        log("No unprocessed INRS publications remaining", "SKIP")
        state["stats"]["cycles"] = cycle_num
        save_state(state)
        return state

    # Process each PDF
    cycle_ok = 0
    cycle_chunks = 0
    cycle_vectors = 0
    cycle_supabase = 0
    cycle_entities = 0
    cycle_errors = 0

    for i, pub in enumerate(batch):
        if _shutdown_requested:
            log("Shutdown requested — stopping batch", "WARN")
            break

        ref = pub["ref"]
        title = pub.get("title", "")[:50]

        print(f"\n--- [{i+1}/{len(batch)}] {ref}: {title} ---", flush=True)
        log(f"Processing: {ref} — {title}", "INFO")

        try:
            result = process_one_pdf(pub, state, dry_run=dry_run)
        except Exception as e:
            log(f"  EXCEPTION: {e}", "ERROR")
            traceback.print_exc()
            result = {
                "ref": ref, "status": "exception",
                "error": str(e)[:200], "chunks": 0,
                "supabase": 0, "pinecone": 0, "entities": 0,
            }

        # Update state
        state["processed_refs"][ref] = {
            "status": result["status"],
            "chunks": result.get("chunks", 0),
            "supabase": result.get("supabase", 0),
            "pinecone": result.get("pinecone", 0),
            "entities": result.get("entities", 0),
            "error": result.get("error"),
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }

        if result["status"] == "ok":
            cycle_ok += 1
            cycle_chunks += result.get("chunks", 0)
            cycle_vectors += result.get("pinecone", 0)
            cycle_supabase += result.get("supabase", 0)
            cycle_entities += result.get("entities", 0)
        elif result["status"] != "dry_run":
            cycle_errors += 1

        # Save state after each PDF (crash recovery)
        save_state(state)

        # Delay between PDFs (Docling cooldown + INRS respect)
        if i < len(batch) - 1 and result["status"] != "dry_run":
            time.sleep(DOCLING_COOLDOWN)

    # Update global stats
    state["stats"]["total_processed"] += cycle_ok
    state["stats"]["total_chunks"] += cycle_chunks
    state["stats"]["total_vectors"] += cycle_vectors
    state["stats"]["total_supabase"] += cycle_supabase
    state["stats"]["total_errors"] += cycle_errors
    state["stats"]["cycles"] = cycle_num

    elapsed = time.time() - cycle_start
    save_state(state)

    # Print summary
    print(f"\n{'=' * 60}", flush=True)
    print(f"  CYCLE #{cycle_num} COMPLETE ({elapsed:.0f}s)", flush=True)
    print(f"{'=' * 60}", flush=True)
    print(f"  PDFs processed:  {cycle_ok}/{len(batch)}", flush=True)
    print(f"  Chunks created:  {cycle_chunks}", flush=True)
    print(f"  Supabase rows:   {cycle_supabase}", flush=True)
    print(f"  Pinecone vectors:{cycle_vectors}", flush=True)
    print(f"  Neo4j entities:  {cycle_entities}", flush=True)
    print(f"  Errors:          {cycle_errors}", flush=True)
    print(f"  TOTALS:          {state['stats']['total_processed']} PDFs, "
          f"{state['stats']['total_chunks']} chunks, "
          f"{state['stats']['total_vectors']} vectors", flush=True)
    remaining = len(unprocessed) - len(batch)
    print(f"  Remaining:       {remaining} PDFs", flush=True)
    print(f"{'=' * 60}", flush=True)

    return state


# =========================================================================
# STATUS DISPLAY
# =========================================================================

def print_status(catalog, state):
    """Print current ingestion status."""
    stats = state.get("stats", {})
    processed_refs = state.get("processed_refs", {})

    ok_count = sum(1 for r in processed_refs.values() if r.get("status") == "ok")
    err_count = sum(1 for r in processed_refs.values() if r.get("status") not in ("ok", "dry_run", None))
    total_catalog = len(catalog.get("publications", {}))

    print(f"\n{'=' * 60}", flush=True)
    print(f"  INRS INGESTION STATUS", flush=True)
    print(f"{'=' * 60}", flush=True)
    print(f"  Catalog:         {total_catalog} publications", flush=True)
    print(f"  Processed OK:    {ok_count}", flush=True)
    print(f"  Errors:          {err_count}", flush=True)
    print(f"  Remaining:       {total_catalog - ok_count - err_count}", flush=True)
    print(f"  Total chunks:    {stats.get('total_chunks', 0)}", flush=True)
    print(f"  Total vectors:   {stats.get('total_vectors', 0)}", flush=True)
    print(f"  Total Supabase:  {stats.get('total_supabase', 0)}", flush=True)
    print(f"  Cycles:          {stats.get('cycles', 0)}", flush=True)
    print(f"  Created:         {state.get('created', '?')}", flush=True)
    print(f"  Last updated:    {state.get('last_updated', '?')}", flush=True)

    # By theme
    if catalog.get("stats", {}).get("by_theme"):
        print(f"\n  By theme:", flush=True)
        for theme, count in sorted(catalog["stats"]["by_theme"].items()):
            theme_ok = sum(
                1 for ref, r in processed_refs.items()
                if r.get("status") == "ok" and
                catalog.get("publications", {}).get(ref, {}).get("theme") == theme
            )
            label = INRS_THEMES.get(theme, theme)
            print(f"    {label:35s}  {theme_ok:3d}/{count:3d}", flush=True)

    # Recent errors
    recent_errors = [
        (ref, r) for ref, r in processed_refs.items()
        if r.get("status") not in ("ok", "dry_run", None)
    ]
    if recent_errors:
        print(f"\n  Recent errors (last 5):", flush=True)
        for ref, r in recent_errors[-5:]:
            print(f"    {ref:12s} — {r.get('status', '?')}: {(r.get('error') or '?')[:60]}", flush=True)

    print(f"{'=' * 60}\n", flush=True)


# =========================================================================
# CLI / MAIN
# =========================================================================

def main():
    global _shutdown_requested

    parser = argparse.ArgumentParser(
        description="INRS Document Ingestion — Production pipeline for workplace safety PDFs"
    )
    parser.add_argument(
        "--catalog-only", action="store_true",
        help="Build/refresh the INRS catalog and exit"
    )
    parser.add_argument(
        "--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
        help=f"PDFs per cycle (default: {DEFAULT_BATCH_SIZE})"
    )
    parser.add_argument(
        "--daemon", action="store_true",
        help="Run as daemon with continuous cycles"
    )
    parser.add_argument(
        "--interval", type=int, default=DEFAULT_INTERVAL,
        help=f"Daemon cycle interval in seconds (default: {DEFAULT_INTERVAL})"
    )
    parser.add_argument(
        "--theme", type=str, default=None,
        help="Filter by INRS theme (e.g., chimique, tms, machines, bruit, rps)"
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Show ingestion progress and exit"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be processed without actually ingesting"
    )
    parser.add_argument(
        "--rebuild-catalog", action="store_true",
        help="Force rebuild the INRS catalog from web + curated list"
    )
    args = parser.parse_args()

    # Resolve theme filter (allow partial match)
    theme_filter = None
    if args.theme:
        theme_input = args.theme.lower().strip()
        for theme_key in INRS_THEMES:
            if theme_input in theme_key:
                theme_filter = theme_key
                break
        if not theme_filter:
            log(f"Unknown theme: {args.theme}", "ERROR")
            print(f"Available themes: {', '.join(INRS_THEMES.keys())}", flush=True)
            sys.exit(1)

    # Status mode
    if args.status:
        catalog = load_catalog()
        state = load_state()
        print_status(catalog, state)
        return

    # Catalog-only mode
    if args.catalog_only or args.rebuild_catalog:
        catalog = build_catalog()
        print(f"\nCatalog: {catalog['stats']['total']} publications", flush=True)
        print(f"By type: {json.dumps(catalog['stats']['by_type'])}", flush=True)
        print(f"By theme: {json.dumps(catalog['stats']['by_theme'], indent=2)}", flush=True)
        print(f"Saved to: {CATALOG_FILE}", flush=True)
        return

    # Validate config
    missing = []
    if not SUPABASE_KEY:
        missing.append("SUPABASE_API_KEY")
    if not PINECONE_API_KEY:
        missing.append("PINECONE_API_KEY")
    if missing:
        log(f"FATAL: Missing env vars: {', '.join(missing)}. Run: source .env.local", "ERROR")
        sys.exit(1)

    if not NEO4J_PASSWORD:
        log("WARN: NEO4J_PASSWORD not set — Neo4j enrichment will be skipped", "WARN")

    # Create data dir and save PID
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))

    # Load catalog (build if needed)
    if args.rebuild_catalog or not CATALOG_FILE.exists():
        catalog = build_catalog()
    else:
        catalog = load_catalog()

    state = load_state()

    # Print startup banner
    print(f"\n{'=' * 60}", flush=True)
    print(f"  INRS DOCUMENT INGESTION", flush=True)
    print(f"{'=' * 60}", flush=True)
    print(f"  Mode:       {'Daemon' if args.daemon else 'One-shot'}", flush=True)
    print(f"  Batch:      {args.batch_size} PDFs/cycle", flush=True)
    print(f"  Interval:   {args.interval}s ({args.interval / 60:.0f}min)", flush=True)
    print(f"  Catalog:    {catalog['stats']['total']} publications", flush=True)
    print(f"  Processed:  {sum(1 for r in state.get('processed_refs', {}).values() if r.get('status') == 'ok')}", flush=True)
    if theme_filter:
        print(f"  Theme:      {theme_filter} ({INRS_THEMES.get(theme_filter, '')})", flush=True)
    print(f"  Sector:     {SECTOR}", flush=True)
    print(f"  Docling:    {DOCLING_BASE}", flush=True)
    print(f"  Pinecone:   sectors-e5-multilingual / sectors", flush=True)
    print(f"  Supabase:   {SUPABASE_URL}", flush=True)
    print(f"  Neo4j:      {NEO4J_URI}", flush=True)
    print(f"  PID:        {os.getpid()}", flush=True)
    print(f"  Log:        {LOG_FILE}", flush=True)
    print(f"  Started:    {datetime.now(timezone.utc).isoformat()}", flush=True)
    print(f"{'=' * 60}\n", flush=True)

    if args.daemon:
        log(f"Starting INRS daemon — {args.interval}s cycles, "
            f"batch={args.batch_size}", "INFO")

        while not _shutdown_requested:
            try:
                state = run_cycle(catalog, state, args.batch_size,
                                  theme_filter=theme_filter, dry_run=args.dry_run)
            except Exception as e:
                log(f"Cycle error: {e}", "ERROR")
                traceback.print_exc()

            if _shutdown_requested:
                break

            # Check if everything is processed
            ok_count = sum(1 for r in state.get("processed_refs", {}).values()
                          if r.get("status") == "ok")
            total = len(catalog.get("publications", {}))
            if ok_count >= total:
                log(f"All {total} INRS publications processed. Daemon stopping.", "OK")
                break

            log(f"Next cycle in {args.interval}s ({args.interval / 60:.1f}min)...", "INFO")
            try:
                sleep_end = time.time() + args.interval
                while time.time() < sleep_end and not _shutdown_requested:
                    time.sleep(min(5, sleep_end - time.time()))
            except KeyboardInterrupt:
                _shutdown_requested = True

        log("INRS daemon stopped", "OK")
    else:
        # One-shot mode
        state = run_cycle(catalog, state, args.batch_size,
                          theme_filter=theme_filter, dry_run=args.dry_run)

    # Clean up PID
    try:
        PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass

    log("INRS Ingestion finished", "OK")


if __name__ == "__main__":
    main()
