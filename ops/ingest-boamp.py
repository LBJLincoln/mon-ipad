#!/usr/bin/env python3
"""
BOAMP Ingestion Daemon — Public Procurement Notices for BTP Sector.
===================================================================
Fetches procurement notices from the BOAMP OpenDataSoft API, filters for
BTP/construction (type_marche=TRAVAUX), and stores them in Supabase +
Pinecone for the BTP sector pipeline.

BOAMP = Bulletin Officiel des Annonces des Marches Publics
~150-200K notices/year, public open data (licence ouverte v2.0).

Data source: https://boamp-datadila.opendatasoft.com/api/explore/v2.1/
API docs: https://boamp.fr/pages/api-boamp/

Architecture:
  1. Query BOAMP API for recent BTP procurement notices
  2. Filter by construction keywords + type_marche=TRAVAUX
  3. Build rich chunks with structured metadata
  4. Store in Supabase sector_documents (sector=btp)
  5. Upsert to Pinecone E5 integrated embedding index
  6. Track progress in data/ingest/boamp-state.json

Usage:
  source .env.local
  python3 ops/ingest-boamp.py                          # One-shot
  python3 ops/ingest-boamp.py --daemon --interval 600  # 10min daemon
  python3 ops/ingest-boamp.py --batch-size 100         # Larger batches
  python3 ops/ingest-boamp.py --dry-run                # Preview only
  python3 ops/ingest-boamp.py --status                 # Show stats
  python3 ops/ingest-boamp.py --days 30                # Last 30 days
  nohup python3 ops/ingest-boamp.py --daemon > data/ingest/boamp-daemon.log 2>&1 &
"""

# -- Force IPv4 globally (IPv6 broken on this VM) ----------------------------
import socket
from socket import AF_INET

_original_getaddrinfo = socket.getaddrinfo


def _ipv4_getaddrinfo(host, port, family=0, type_=0, proto=0, flags=0):
    return _original_getaddrinfo(host, port, AF_INET, type_, proto, flags)


socket.getaddrinfo = _ipv4_getaddrinfo

# -- Standard imports ---------------------------------------------------------
import argparse
import hashlib
import json
import os
import signal
import ssl
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

# -- Force line-buffered output -----------------------------------------------
try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

# -- Load .env.local ---------------------------------------------------------
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

# -- SSL context (permissive for government APIs) -----------------------------
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE

# =============================================================================
# CONFIGURATION
# =============================================================================

# BOAMP API (OpenDataSoft)
BOAMP_API_BASE = "https://boamp-datadila.opendatasoft.com/api/explore/v2.1"
BOAMP_DATASET = "boamp"
BOAMP_RECORDS_URL = f"{BOAMP_API_BASE}/catalog/datasets/{BOAMP_DATASET}/records"

# Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://ayqviqmxifzmhphiqfmj.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_API_KEY", "")
SUPABASE_TABLE = "sector_documents"

# Pinecone (E5 integrated embedding index)
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY", "")
# Hardcoded to sectors-e5-multilingual (not PINECONE_HOST env which points to legacy sota-rag)
PINECONE_HOST = "https://sectors-e5-multilingual-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
PINECONE_NAMESPACE = "sectors"

# Data dirs
DATA_DIR = REPO_ROOT / "data" / "ingest"
STATE_FILE = DATA_DIR / "boamp-state.json"
LOG_FILE = DATA_DIR / "boamp.jsonl"
PID_FILE = DATA_DIR / "boamp.pid"

# Processing config
DEFAULT_BATCH_SIZE = 50
DEFAULT_INTERVAL = 600  # 10 minutes
DEFAULT_DAYS = 14  # look back 14 days by default
RATE_LIMIT_DELAY = 1.0  # 1 req/sec to be polite
HTTP_TIMEOUT = 30
PINECONE_TIMEOUT = 15

# BTP filter: type_marche includes TRAVAUX or descriptors match construction
# These CPV/descriptor codes are BTP-related
BTP_DESCRIPTOR_CODES = {
    "33",   # Batiment
    "34",   # Batiment (industrie)
    "48",   # Charpente metallique
    "59",   # Cloisons, faux-plafonds
    "78",   # Demolition
    "80",   # Electricite (batiment)
    "91",   # Etancheite
    "97",   # Fondations speciales
    "104",  # Genie civil
    "118",  # Installation thermique
    "141",  # Maconnerie
    "159",  # Menuiserie
    "176",  # Peinture (travaux)
    "191",  # Plomberie
    "204",  # Revetements de sols
    "232",  # Terrassement
    "243",  # Travaux publics
    "247",  # VRD
    "264",  # Peinture (travaux)
    "271",  # Ravalement
    "308",  # Revetements de sols
    "1",    # Amiante (desamiantage)
}

# BTP keywords for text matching (objet field)
BTP_KEYWORDS = [
    "travaux", "construction", "batiment", "bâtiment", "renovation", "rénovation",
    "rehabilitation", "réhabilitation", "maconnerie", "maçonnerie", "toiture",
    "couverture", "etancheite", "étanchéité", "charpente", "menuiserie",
    "plomberie", "electricite", "électricité", "fondation", "terrassement",
    "demolition", "démolition", "voirie", "assainissement", "genie civil",
    "génie civil", "vrd", "amenagement", "aménagement", "isolation",
    "chauffage", "climatisation", "peinture", "ravalement", "facade", "façade",
    "ascenseur", "cloison", "faux-plafond", "carrelage", "parquet",
    "serrurerie", "bardage", "beton", "béton", "coffrage", "ferraillage",
    "chantier", "ouvrage", "infrastructure", "pont", "route",
    "desamiantage", "désamiantage", "restructuration", "extension",
    "surelevation", "surélévation", "dalle", "mur", "plancher",
    "ecole", "école", "gymnase", "piscine", "creche", "crèche",
    "logement", "hlm", "habitat", "residence", "résidence",
]

# Graceful shutdown
_shutdown_requested = False


def _signal_handler(signum, frame):
    global _shutdown_requested
    _shutdown_requested = True
    log("Shutdown signal received, finishing current batch...", "WARN")


signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)


# =============================================================================
# LOGGING
# =============================================================================

def log(msg, level="INFO"):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ts_short = ts[11:19]
    prefix = {"INFO": "+", "WARN": "!", "ERROR": "X", "OK": "v", "SKIP": "-"}.get(level, " ")
    print(f"[{ts_short}] [{prefix}] {msg}", flush=True)

    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        entry = {"ts": ts, "level": level, "msg": msg, "source": "boamp"}
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


# =============================================================================
# HTTP UTILITIES
# =============================================================================

def http_request(url, data=None, headers=None, method="GET", timeout=HTTP_TIMEOUT):
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


# =============================================================================
# BOAMP API CLIENT
# =============================================================================

def fetch_boamp_notices(offset=0, limit=50, since_date=None):
    """
    Fetch procurement notices from BOAMP OpenDataSoft API.
    Filters: type_marche=TRAVAUX (construction) and recent dates.

    Returns (records_list, total_count, error_string).
    """
    if since_date is None:
        since_date = (datetime.now(timezone.utc) - timedelta(days=DEFAULT_DAYS)).strftime("%Y-%m-%d")

    # Build ODS query — filter for TRAVAUX and recent
    where_clause = (
        f"dateparution >= '{since_date}'"
        f" AND type_marche LIKE 'TRAVAUX'"
    )

    params = {
        "limit": limit,
        "offset": offset,
        "where": where_clause,
        "order_by": "dateparution DESC",
        "select": (
            "idweb,objet,nomacheteur,dateparution,datelimitereponse,"
            "datefindiffusion,descripteur_libelle,descripteur_code,"
            "code_departement,type_marche,famille_libelle,"
            "nature_libelle,procedure_libelle,url_avis,donnees,gestion"
        ),
    }

    url = BOAMP_RECORDS_URL + "?" + urllib.parse.urlencode(params)
    status, body, err = http_request(url, timeout=HTTP_TIMEOUT)

    if err:
        return [], 0, f"BOAMP API error: {err}"

    if status != 200:
        body_str = body.decode("utf-8", errors="replace")[:300] if body else "empty"
        return [], 0, f"BOAMP HTTP {status}: {body_str}"

    try:
        data = json.loads(body.decode("utf-8"))
        records = data.get("results", [])
        total = data.get("total_count", 0)
        return records, total, None
    except Exception as e:
        return [], 0, f"JSON parse error: {e}"


# =============================================================================
# NOTICE PARSING & ENRICHMENT
# =============================================================================

def parse_notice(raw):
    """
    Parse a raw BOAMP record into a structured BTP notice dict.
    Extracts rich metadata from the gestion/donnees JSON blobs.
    """
    notice_id = raw.get("idweb", "")
    objet = raw.get("objet", "").strip()
    buyer = raw.get("nomacheteur", "").strip()
    date_pub = raw.get("dateparution", "")
    date_limit = raw.get("datelimitereponse", "")
    date_end = raw.get("datefindiffusion", "")
    descriptors = raw.get("descripteur_libelle", []) or []
    descriptor_codes = raw.get("descripteur_code", []) or []
    departments = raw.get("code_departement", []) or []
    type_marche = raw.get("type_marche", []) or []
    famille = raw.get("famille_libelle", "")
    nature = raw.get("nature_libelle", "")
    procedure = raw.get("procedure_libelle", "")
    url_avis = raw.get("url_avis", "")

    # Parse nested JSON blobs for additional details
    cpv_code = ""
    description = ""
    duration = ""
    contact_name = ""
    contact_email = ""
    contact_tel = ""
    siret = ""
    city = ""
    postal_code = ""
    lieu_execution = ""
    identifiant_interne = ""
    url_doc = ""
    complementary_info = ""

    try:
        donnees_str = raw.get("donnees", "")
        if donnees_str and isinstance(donnees_str, str):
            donnees = json.loads(donnees_str)
            # Navigate the nested structure (varies by schema version)
            for key in donnees:
                section = donnees[key]
                if not isinstance(section, dict):
                    continue

                # Organisation info
                org = section.get("organisme", {})
                if isinstance(org, dict):
                    siret = org.get("codeIdentificationNational", siret) or ""
                    city = org.get("ville", city) or ""
                    postal_code = org.get("cp", postal_code) or ""

                # Initial section (most data lives here)
                initial = section.get("initial", {})
                if not isinstance(initial, dict):
                    continue

                # Communication
                comm = initial.get("communication", {})
                if isinstance(comm, dict):
                    url_doc = comm.get("urlDocConsul", "") or ""
                    identifiant_interne = comm.get("identifiantInterne", "") or ""
                    contact_name = comm.get("nomContact", "") or ""
                    contact_email = comm.get("adresseMailContact", "") or ""
                    contact_tel = comm.get("telContact", "") or ""

                # Nature du marche
                nat = initial.get("natureMarche", {})
                if isinstance(nat, dict):
                    description = nat.get("description", "") or ""
                    lieu_execution = nat.get("lieuExecution", "") or ""
                    duration = nat.get("dureeMois", "") or ""
                    cpv_obj = nat.get("codeCPV", {})
                    if isinstance(cpv_obj, dict):
                        principal = cpv_obj.get("objetPrincipal", {})
                        if isinstance(principal, dict):
                            cpv_code = principal.get("classPrincipale", "") or ""

                # Complementary info
                info_comp = initial.get("informComplementaire", {})
                if isinstance(info_comp, dict):
                    complementary_info = info_comp.get("autresInformComplementaire", "") or ""

    except (json.JSONDecodeError, TypeError, AttributeError):
        pass

    # Build amount range estimation from famille
    amount_range = ""
    if "90" in famille.lower() and "seuil" in famille.lower():
        amount_range = "90K-seuils EUR"
    elif "europ" in famille.lower():
        amount_range = ">seuils europeens"
    elif "mapa" in famille.lower():
        amount_range = "<90K EUR"

    # Location from departments
    location = ""
    if departments:
        dept_str = ", ".join(str(d) for d in departments[:5])
        if lieu_execution:
            location = f"{lieu_execution} (dept {dept_str})"
        else:
            location = f"Departement(s): {dept_str}"

    return {
        "notice_id": notice_id,
        "title": objet,
        "buyer": buyer,
        "date_publication": date_pub,
        "date_limit": date_limit,
        "date_end_diffusion": date_end,
        "descriptors": descriptors,
        "descriptor_codes": descriptor_codes,
        "departments": departments,
        "type_marche": type_marche,
        "famille": famille,
        "nature": nature,
        "procedure": procedure,
        "url_avis": url_avis,
        "cpv_code": cpv_code,
        "description": description or objet,
        "duration_months": duration,
        "contact_name": contact_name,
        "contact_email": contact_email,
        "contact_tel": contact_tel,
        "siret": siret,
        "city": city,
        "postal_code": postal_code,
        "lieu_execution": location,
        "identifiant_interne": identifiant_interne,
        "url_document": url_doc,
        "amount_range": amount_range,
        "complementary_info": complementary_info,
    }


def is_btp_relevant(notice):
    """
    Check if a notice is BTP-relevant beyond type_marche=TRAVAUX.
    Uses descriptor codes and keyword matching.
    Returns (is_relevant, confidence_score).
    """
    score = 0.0

    # type_marche=TRAVAUX already gives 0.5
    if any("TRAVAUX" in str(t).upper() for t in notice.get("type_marche", [])):
        score += 0.5

    # Descriptor codes matching
    codes = set(str(c) for c in notice.get("descriptor_codes", []))
    btp_matches = codes & BTP_DESCRIPTOR_CODES
    if btp_matches:
        score += min(0.3, len(btp_matches) * 0.1)

    # Keyword matching in title/description
    text_lower = (notice.get("title", "") + " " + notice.get("description", "")).lower()
    keyword_hits = sum(1 for kw in BTP_KEYWORDS if kw in text_lower)
    if keyword_hits > 0:
        score += min(0.3, keyword_hits * 0.05)

    return score >= 0.5, round(score, 2)


def build_chunk_text(notice):
    """
    Build a rich text chunk from a parsed notice.
    This is what gets embedded in Pinecone for semantic search.
    """
    parts = []

    # Title/Object
    parts.append(f"Avis de marche public BTP: {notice['title']}")
    parts.append("")

    # Buyer
    if notice["buyer"]:
        parts.append(f"Acheteur: {notice['buyer']}")

    # Location
    if notice["lieu_execution"]:
        parts.append(f"Lieu d'execution: {notice['lieu_execution']}")
    elif notice["city"]:
        parts.append(f"Ville: {notice['city']} ({notice['postal_code']})")

    # Description
    if notice["description"] and notice["description"] != notice["title"]:
        parts.append(f"Description: {notice['description']}")

    # Procedure & Nature
    if notice["procedure"]:
        parts.append(f"Procedure: {notice['procedure']}")
    if notice["nature"]:
        parts.append(f"Nature: {notice['nature']}")
    if notice["famille"]:
        parts.append(f"Categorie: {notice['famille']}")

    # Dates
    parts.append(f"Date de publication: {notice['date_publication']}")
    if notice["date_limit"]:
        dl = notice["date_limit"][:10] if len(notice["date_limit"]) > 10 else notice["date_limit"]
        parts.append(f"Date limite de reponse: {dl}")

    # Descriptors (BTP specialties)
    if notice["descriptors"]:
        parts.append(f"Specialites: {', '.join(notice['descriptors'])}")

    # CPV Code
    if notice["cpv_code"]:
        parts.append(f"Code CPV: {notice['cpv_code']}")

    # Duration
    if notice["duration_months"]:
        parts.append(f"Duree: {notice['duration_months']} mois")

    # Amount range
    if notice["amount_range"]:
        parts.append(f"Tranche: {notice['amount_range']}")

    # SIRET
    if notice["siret"]:
        parts.append(f"SIRET acheteur: {notice['siret']}")

    # Contact
    if notice["contact_name"] or notice["contact_email"]:
        contact = notice["contact_name"]
        if notice["contact_email"]:
            contact += f" ({notice['contact_email']})"
        parts.append(f"Contact: {contact}")

    # Complementary info (often has useful details)
    if notice["complementary_info"]:
        info = notice["complementary_info"][:500]
        parts.append(f"Informations complementaires: {info}")

    # Reference
    parts.append("")
    parts.append(f"Reference: BOAMP {notice['notice_id']}")
    if notice["url_avis"]:
        parts.append(f"Source: {notice['url_avis']}")

    return "\n".join(parts)


def build_metadata(notice, relevance_score):
    """Build rich metadata dict for Supabase and Pinecone."""
    return {
        "source": "boamp",
        "source_type": "api",
        "notice_id": f"BOAMP-{notice['notice_id']}",
        "title": notice["title"][:500],
        "buyer": notice["buyer"][:300],
        "cpv_codes": [notice["cpv_code"]] if notice["cpv_code"] else [],
        "descriptors": notice["descriptors"][:10],
        "amount_range": notice["amount_range"],
        "date_publication": notice["date_publication"],
        "date_limit": notice["date_limit"][:10] if notice["date_limit"] else "",
        "location": notice["lieu_execution"][:200],
        "departments": notice["departments"][:10],
        "procedure": notice["procedure"],
        "nature": notice["nature"],
        "famille": notice["famille"],
        "duration_months": notice["duration_months"],
        "siret": notice["siret"],
        "url_avis": notice["url_avis"][:500],
        "url_document": notice["url_document"][:500],
        "identifiant_interne": notice["identifiant_interne"][:100],
        "full_reference": f"BOAMP-{notice['notice_id']} -- {notice['title'][:100]}",
        "btp_relevance": relevance_score,
        "has_entities": False,
        "entity_count": 0,
        "enriched": "false",
        "phase": "ingested",
        "ingestion_source": "ingest-boamp-v1",
    }


# =============================================================================
# STORAGE: SUPABASE
# =============================================================================

def supabase_upsert(doc_id, chunk_text, notice, metadata_dict):
    """
    Upsert a BOAMP notice to Supabase sector_documents.
    Uses Prefer: resolution=merge-duplicates for idempotent upserts.
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        return False, "SUPABASE_API_KEY not set"

    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}"

    row = {
        "id": doc_id,
        "sector": "btp",
        "dataset_name": "boamp-procurement",
        "pipeline": "standard",
        "question": notice["title"][:500],
        "answer": (
            f"Avis de marche public publie au BOAMP le {notice['date_publication']}. "
            f"Acheteur: {notice['buyer']}. "
            f"Procedure: {notice['procedure']}. "
            f"{'Date limite: ' + notice['date_limit'][:10] + '. ' if notice['date_limit'] else ''}"
            f"Reference: BOAMP-{notice['notice_id']}."
        )[:5000],
        "context": chunk_text[:30000],
        "metadata": json.dumps(metadata_dict, ensure_ascii=False),
        "tenant_id": "btp",
    }

    payload = json.dumps(row, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Prefer": "resolution=merge-duplicates",
    }

    status, body, err = http_request(url, data=payload, headers=headers,
                                      method="POST", timeout=HTTP_TIMEOUT)

    if status in (200, 201, 204):
        return True, None
    if status == 409:
        return True, None  # Duplicate = fine

    body_str = ""
    try:
        body_str = body.decode("utf-8")[:200]
    except Exception:
        pass
    return False, f"HTTP {status}: {err or ''} {body_str}"


def supabase_register(doc_id, notice, chunk_text):
    """
    Register in document_registry for tracking (best-effort).
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        return

    url = f"{SUPABASE_URL}/rest/v1/document_registry"
    content_hash = hashlib.md5(chunk_text[:5000].encode()).hexdigest()

    row = {
        "sector": "btp",
        "source_type": "api",
        "source_url": notice["url_avis"][:1000],
        "title": notice["title"][:500],
        "char_count": len(chunk_text),
        "language": "fr",
        "quality_score": 0.8,
        "processing_status": "ingested",
        "content_hash": content_hash,
        "discovered_at": datetime.now(timezone.utc).isoformat(),
        "metadata": json.dumps({
            "source": "boamp",
            "notice_id": notice["notice_id"],
            "buyer": notice["buyer"][:200],
        }, ensure_ascii=False),
    }

    payload = json.dumps(row, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Prefer": "resolution=merge-duplicates",
    }

    try:
        http_request(url, data=payload, headers=headers, method="POST", timeout=15)
    except Exception:
        pass  # Best-effort


# =============================================================================
# STORAGE: PINECONE (E5 Integrated Embedding)
# =============================================================================

def pinecone_upsert(doc_id, chunk_text, metadata_dict):
    """
    Upsert a record to Pinecone E5 integrated embedding index.
    The index handles embedding automatically from the 'text' field.
    """
    if not PINECONE_API_KEY:
        return False, "PINECONE_API_KEY not set"

    url = f"{PINECONE_HOST}/records/namespaces/{PINECONE_NAMESPACE}/upsert"

    record = {
        "_id": doc_id,
        "text": chunk_text[:8000],  # E5 context window
        "sector": "btp",
        "source": "boamp",
        "notice_id": metadata_dict.get("notice_id", ""),
        "buyer": metadata_dict.get("buyer", "")[:200],
        "date_publication": metadata_dict.get("date_publication", ""),
        "location": metadata_dict.get("location", "")[:200],
    }

    payload = json.dumps(record, ensure_ascii=False).encode("utf-8")
    headers = {
        "Api-Key": PINECONE_API_KEY,
        "Content-Type": "application/json",
    }

    for attempt in range(3):
        status, body, err = http_request(url, data=payload, headers=headers,
                                          method="POST", timeout=PINECONE_TIMEOUT)
        if status in (200, 201):
            return True, None
        if status == 409:
            return True, None  # Duplicate
        if status == 429:
            wait = min(2 ** attempt + 0.5, 5)
            time.sleep(wait)
            continue
        if attempt == 2:
            body_str = ""
            try:
                body_str = body.decode("utf-8")[:200]
            except Exception:
                pass
            return False, f"HTTP {status}: {err or ''} {body_str}"
        time.sleep(0.5)

    return False, "max retries exceeded"


# =============================================================================
# STATE MANAGEMENT
# =============================================================================

def load_state():
    """Load ingestion state from file."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text("utf-8"))
        except Exception:
            pass
    return {
        "created": datetime.now(timezone.utc).isoformat(),
        "total_ingested": 0,
        "total_skipped": 0,
        "total_errors": 0,
        "total_duplicates": 0,
        "total_cycles": 0,
        "supabase_ok": 0,
        "pinecone_ok": 0,
        "last_notice_date": "",
        "seen_ids": [],
        "by_department": {},
        "by_descriptor": {},
        "last_cycle": None,
    }


def save_state(state):
    """Save ingestion state to file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    # Keep seen_ids manageable (last 10K)
    if len(state.get("seen_ids", [])) > 10000:
        state["seen_ids"] = state["seen_ids"][-10000:]
    tmp = str(STATE_FILE) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False, default=str)
    os.replace(tmp, str(STATE_FILE))


def print_status(state):
    """Print ingestion status."""
    print(f"\n{'=' * 60}", flush=True)
    print(f"  BOAMP INGESTION -- STATUS", flush=True)
    print(f"{'=' * 60}", flush=True)
    print(f"  Total ingested:   {state['total_ingested']}", flush=True)
    print(f"  Total skipped:    {state['total_skipped']}", flush=True)
    print(f"  Total duplicates: {state['total_duplicates']}", flush=True)
    print(f"  Total errors:     {state['total_errors']}", flush=True)
    print(f"  Total cycles:     {state['total_cycles']}", flush=True)
    print(f"  Supabase OK:      {state['supabase_ok']}", flush=True)
    print(f"  Pinecone OK:      {state['pinecone_ok']}", flush=True)
    print(f"  Last notice date: {state.get('last_notice_date', '?')}", flush=True)
    print(f"  Seen IDs cached:  {len(state.get('seen_ids', []))}", flush=True)
    print(f"  Created:          {state.get('created', '?')}", flush=True)
    print(f"  Last updated:     {state.get('last_updated', '?')}", flush=True)

    if state.get("by_department"):
        print(f"\n  Top departments:", flush=True)
        sorted_deps = sorted(state["by_department"].items(), key=lambda x: x[1], reverse=True)
        for dept, count in sorted_deps[:10]:
            print(f"    Dept {dept:>3s}: {count:4d} notices", flush=True)

    if state.get("by_descriptor"):
        print(f"\n  Top BTP specialties:", flush=True)
        sorted_desc = sorted(state["by_descriptor"].items(), key=lambda x: x[1], reverse=True)
        for desc, count in sorted_desc[:10]:
            print(f"    {desc:30s}: {count:4d}", flush=True)

    if state.get("last_cycle"):
        lc = state["last_cycle"]
        print(f"\n  Last cycle:", flush=True)
        print(f"    Time:     {lc.get('started', '?')}", flush=True)
        print(f"    Fetched:  {lc.get('fetched', 0)}", flush=True)
        print(f"    Ingested: {lc.get('ingested', 0)}", flush=True)
        print(f"    Skipped:  {lc.get('skipped', 0)}", flush=True)
        print(f"    Errors:   {lc.get('errors', 0)}", flush=True)
        print(f"    Duration: {lc.get('elapsed_s', 0):.1f}s", flush=True)

    print(f"{'=' * 60}\n", flush=True)


# =============================================================================
# INGESTION CYCLE
# =============================================================================

def ingest_one_notice(raw, state, dry_run=False):
    """
    Process a single BOAMP notice through the full pipeline.
    Returns (status, doc_id).
    """
    notice = parse_notice(raw)
    notice_id = notice["notice_id"]

    # Check if already seen
    if notice_id in state.get("seen_ids", []):
        return "duplicate", notice_id

    # Check BTP relevance
    is_relevant, relevance_score = is_btp_relevant(notice)
    if not is_relevant:
        return "not_btp", notice_id

    # Build chunk text and metadata
    chunk_text = build_chunk_text(notice)
    if len(chunk_text) < 100:
        return "too_short", notice_id

    metadata = build_metadata(notice, relevance_score)
    doc_id = f"boamp-{notice_id}"

    if dry_run:
        log(f"  [DRY] {notice_id} | {notice['buyer'][:30]} | {notice['title'][:60]}", "INFO")
        return "dry_run", doc_id

    # Store in Supabase
    supa_ok, supa_err = supabase_upsert(doc_id, chunk_text, notice, metadata)
    if supa_ok:
        state["supabase_ok"] = state.get("supabase_ok", 0) + 1
    else:
        log(f"  Supabase error: {supa_err}", "WARN")

    # Store in Pinecone
    pine_ok, pine_err = pinecone_upsert(doc_id, chunk_text, metadata)
    if pine_ok:
        state["pinecone_ok"] = state.get("pinecone_ok", 0) + 1
    else:
        log(f"  Pinecone error: {pine_err}", "WARN")

    # Register in document_registry (best-effort)
    supabase_register(doc_id, notice, chunk_text)

    # Track seen ID
    if "seen_ids" not in state:
        state["seen_ids"] = []
    state["seen_ids"].append(notice_id)

    # Track departments
    for dept in notice.get("departments", [])[:3]:
        dept_str = str(dept)
        state.setdefault("by_department", {})[dept_str] = state.get("by_department", {}).get(dept_str, 0) + 1

    # Track descriptors
    for desc in notice.get("descriptors", [])[:5]:
        state.setdefault("by_descriptor", {})[desc] = state.get("by_descriptor", {}).get(desc, 0) + 1

    # Update last notice date
    if notice["date_publication"]:
        if not state.get("last_notice_date") or notice["date_publication"] > state["last_notice_date"]:
            state["last_notice_date"] = notice["date_publication"]

    if supa_ok or pine_ok:
        return "ingested", doc_id
    else:
        return "error", doc_id


def run_cycle(batch_size, days, state, dry_run=False):
    """
    Run one ingestion cycle:
    1. Fetch BOAMP notices (paginated)
    2. Filter and ingest each one
    3. Update state
    """
    global _shutdown_requested

    cycle_start = time.time()
    cycle_num = state["total_cycles"] + 1
    since_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

    print(f"\n{'=' * 60}", flush=True)
    print(f"  BOAMP INGESTION CYCLE #{cycle_num}", flush=True)
    print(f"  Batch: {batch_size} | Since: {since_date} | Dry: {dry_run}", flush=True)
    print(f"  Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC", flush=True)
    print(f"{'=' * 60}", flush=True)

    # Fetch notices (paginated)
    all_notices = []
    offset = 0
    page_size = min(batch_size, 100)  # ODS max is 100 per page

    while len(all_notices) < batch_size and not _shutdown_requested:
        log(f"Fetching BOAMP page offset={offset} limit={page_size}...", "INFO")
        records, total, err = fetch_boamp_notices(
            offset=offset, limit=page_size, since_date=since_date
        )

        if err:
            log(f"BOAMP API error: {err}", "ERROR")
            break

        if not records:
            log(f"No more records (total available: {total})", "INFO")
            break

        all_notices.extend(records)
        offset += page_size
        log(f"Fetched {len(records)} records (total this cycle: {len(all_notices)}, "
            f"available: {total})", "OK")

        if offset >= total:
            break

        # Rate limiting
        time.sleep(RATE_LIMIT_DELAY)

    if not all_notices:
        log("No BOAMP notices fetched", "SKIP")
        state["total_cycles"] = cycle_num
        state["last_cycle"] = {
            "started": datetime.now(timezone.utc).isoformat(),
            "fetched": 0, "ingested": 0, "skipped": 0, "errors": 0,
            "elapsed_s": round(time.time() - cycle_start, 1),
        }
        save_state(state)
        return state

    log(f"Processing {len(all_notices)} BOAMP notices...", "INFO")

    # Process each notice
    cycle_ingested = 0
    cycle_skipped = 0
    cycle_errors = 0
    cycle_duplicates = 0

    for i, raw in enumerate(all_notices):
        if _shutdown_requested:
            log("Shutdown requested -- stopping batch", "WARN")
            break

        notice_id = raw.get("idweb", "?")
        objet = (raw.get("objet") or "")[:50]

        try:
            status_str, doc_id = ingest_one_notice(raw, state, dry_run=dry_run)
        except Exception as e:
            log(f"  EXCEPTION processing {notice_id}: {e}", "ERROR")
            traceback.print_exc()
            status_str = "error"
            cycle_errors += 1
            continue

        if status_str == "ingested":
            cycle_ingested += 1
            if (cycle_ingested % 10) == 0:
                log(f"  [{i+1}/{len(all_notices)}] Ingested {cycle_ingested} | "
                    f"{notice_id} | {objet}", "OK")
        elif status_str == "duplicate":
            cycle_duplicates += 1
        elif status_str in ("not_btp", "too_short"):
            cycle_skipped += 1
        elif status_str == "dry_run":
            cycle_ingested += 1
        else:
            cycle_errors += 1

        # Rate limiting between storage operations
        if not dry_run and status_str == "ingested":
            time.sleep(0.2)  # 200ms between upserts

    # Update state
    if not dry_run:
        state["total_ingested"] += cycle_ingested
        state["total_skipped"] += cycle_skipped
        state["total_errors"] += cycle_errors
        state["total_duplicates"] += cycle_duplicates
    state["total_cycles"] = cycle_num

    elapsed = time.time() - cycle_start
    state["last_cycle"] = {
        "started": datetime.now(timezone.utc).isoformat(),
        "fetched": len(all_notices),
        "ingested": cycle_ingested,
        "skipped": cycle_skipped,
        "duplicates": cycle_duplicates,
        "errors": cycle_errors,
        "elapsed_s": round(elapsed, 1),
    }

    save_state(state)

    # Print cycle summary
    print(f"\n{'=' * 60}", flush=True)
    print(f"  CYCLE #{cycle_num} COMPLETE ({elapsed:.1f}s)", flush=True)
    print(f"{'=' * 60}", flush=True)
    print(f"  Fetched:    {len(all_notices)}", flush=True)
    print(f"  Ingested:   {cycle_ingested}", flush=True)
    print(f"  Skipped:    {cycle_skipped} (not BTP or too short)", flush=True)
    print(f"  Duplicates: {cycle_duplicates}", flush=True)
    print(f"  Errors:     {cycle_errors}", flush=True)
    if not dry_run:
        print(f"  TOTALS:     {state['total_ingested']} ingested, "
              f"{state['total_duplicates']} dups, "
              f"{state['total_errors']} errors", flush=True)
    print(f"{'=' * 60}", flush=True)

    return state


# =============================================================================
# MAIN / CLI
# =============================================================================

def main():
    global _shutdown_requested
    parser = argparse.ArgumentParser(
        description="BOAMP Ingestion -- Public Procurement Notices for BTP Sector"
    )
    parser.add_argument(
        "--daemon", action="store_true",
        help="Run as daemon with continuous cycles"
    )
    parser.add_argument(
        "--interval", type=int, default=DEFAULT_INTERVAL,
        help=f"Cycle interval in seconds (default: {DEFAULT_INTERVAL})"
    )
    parser.add_argument(
        "--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
        help=f"Notices per cycle (default: {DEFAULT_BATCH_SIZE})"
    )
    parser.add_argument(
        "--days", type=int, default=DEFAULT_DAYS,
        help=f"Look back N days (default: {DEFAULT_DAYS})"
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Show ingestion stats and exit"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Fetch and parse but don't store (preview mode)"
    )
    args = parser.parse_args()

    # Status mode
    if args.status:
        state = load_state()
        print_status(state)
        return

    # Validate config
    missing = []
    if not SUPABASE_KEY:
        missing.append("SUPABASE_API_KEY")
    if not PINECONE_API_KEY:
        missing.append("PINECONE_API_KEY")

    if missing and not args.dry_run:
        log(f"FATAL: Missing env vars: {', '.join(missing)}. Run: source .env.local", "ERROR")
        sys.exit(1)

    # Create data dir and save PID
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))

    # Print startup banner
    print(f"\n{'=' * 60}", flush=True)
    print(f"  BOAMP INGESTION V1.0 -- BTP Procurement Notices", flush=True)
    print(f"{'=' * 60}", flush=True)
    print(f"  Mode:       {'Daemon' if args.daemon else 'One-shot'}", flush=True)
    print(f"  Interval:   {args.interval}s ({args.interval / 60:.0f}min)", flush=True)
    print(f"  Batch:      {args.batch_size} notices/cycle", flush=True)
    print(f"  Days:       {args.days} days lookback", flush=True)
    print(f"  Dry run:    {args.dry_run}", flush=True)
    print(f"  Supabase:   {SUPABASE_URL}", flush=True)
    print(f"  Pinecone:   {PINECONE_HOST[:60]}...", flush=True)
    print(f"  State:      {STATE_FILE}", flush=True)
    print(f"  Log:        {LOG_FILE}", flush=True)
    print(f"  PID:        {os.getpid()}", flush=True)
    print(f"  API:        {BOAMP_RECORDS_URL}", flush=True)
    print(f"  Started:    {datetime.now(timezone.utc).isoformat()}", flush=True)
    print(f"{'=' * 60}\n", flush=True)

    state = load_state()

    if args.daemon:
        log(f"Starting BOAMP daemon -- {args.interval}s cycles, "
            f"batch={args.batch_size}, days={args.days}", "INFO")

        consecutive_empty = 0
        while not _shutdown_requested:
            try:
                state = run_cycle(args.batch_size, args.days, state, dry_run=args.dry_run)
            except Exception as e:
                log(f"Cycle error: {e}", "ERROR")
                traceback.print_exc()

            if _shutdown_requested:
                break

            # Check if cycle was empty
            lc = state.get("last_cycle", {})
            if lc.get("ingested", 0) == 0 and lc.get("fetched", 0) == 0:
                consecutive_empty += 1
            else:
                consecutive_empty = 0

            # Adaptive backoff: slow down after 3 empty cycles
            if consecutive_empty >= 3:
                wait_time = min(args.interval * 3, 3600)
                log(f"No new notices for {consecutive_empty} cycles -- "
                    f"sleeping {wait_time}s (3x interval, max 1h)", "INFO")
            else:
                wait_time = args.interval

            log(f"Next cycle in {wait_time}s ({wait_time / 60:.1f}min)...", "INFO")

            try:
                sleep_end = time.time() + wait_time
                while time.time() < sleep_end and not _shutdown_requested:
                    time.sleep(min(5, sleep_end - time.time()))
            except KeyboardInterrupt:
                _shutdown_requested = True

        log("BOAMP daemon stopped gracefully", "OK")
    else:
        # One-shot mode
        state = run_cycle(args.batch_size, args.days, state, dry_run=args.dry_run)

    # Clean up PID
    try:
        PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass

    log("BOAMP Ingestion finished", "OK")


if __name__ == "__main__":
    main()
