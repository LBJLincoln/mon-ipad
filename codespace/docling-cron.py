#!/usr/bin/env python3
"""
Docling Continuous Ingestion Cron — Expert PDF Discovery + Processing + Storage
================================================================================
Runs every 30 minutes on a GitHub Codespace to:
  1. Discover new expert PDFs via Tavily search (per sector)
  2. Download each PDF to local temp directory
  3. Process with Docling locally (32GB RAM — handles large PDFs)
  4. Chunk extracted text (500-token chunks, 50-token overlap)
  5. Ingest chunks to Pinecone E5, Supabase, and Neo4j
  6. Log everything to codespace/logs/docling-cron.jsonl
  7. Track processed URLs to avoid duplicates

Usage:
  source .env.local
  python3 codespace/docling-cron.py                   # Full run (all sectors)
  python3 codespace/docling-cron.py --sector finance   # Single sector
  python3 codespace/docling-cron.py --dry-run          # Discover only, no processing
  python3 codespace/docling-cron.py --max-pdfs 5       # Limit PDFs per run
  python3 codespace/docling-cron.py --skip-neo4j       # Skip Neo4j ingestion
"""

# ── IPv4 monkey-patch (required — IPv6 broken on VM/Codespace) ────────────
import socket
from socket import AF_INET

_original_getaddrinfo = socket.getaddrinfo


def _ipv4_getaddrinfo(host, port, family=0, type_=0, proto=0, flags=0):
    return _original_getaddrinfo(host, port, AF_INET, type_, proto, flags)


socket.getaddrinfo = _ipv4_getaddrinfo

# ── Standard imports ──────────────────────────────────────────────────────
import argparse
import hashlib
import json
import os
import re
import ssl
import sys
import tempfile
import time
import traceback
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ── Force line buffering for cron/nohup ────────────────────────────────────
try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

# ── SSL context (permissive for government PDFs with outdated certs) ──────
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE

# ==========================================================================
# CONFIGURATION
# ==========================================================================

# API Keys (from .env.local)
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_API_KEY = os.environ.get("SUPABASE_API_KEY", "")
NEO4J_URI = os.environ.get("NEO4J_URI", "")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "")

# Pinecone E5 integrated index
PINECONE_HOST = "https://sectors-e5-multilingual-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
NAMESPACE = "sectors"
PINECONE_UPSERT_URL = f"{PINECONE_HOST}/records/namespaces/{NAMESPACE}/upsert"

# Tavily
TAVILY_URL = "https://api.tavily.com/search"

# Supabase REST
SUPABASE_INSERT_URL = f"{SUPABASE_URL}/rest/v1/sector_documents"

# Neo4j HTTP API (Aura)
# Extract host from neo4j+s:// URI
NEO4J_HTTP_HOST = ""
NEO4J_DB_NAME = ""
if NEO4J_URI:
    _neo4j_host = NEO4J_URI.replace("neo4j+s://", "").replace("neo4j://", "")
    NEO4J_HTTP_HOST = f"https://{_neo4j_host}"
    NEO4J_DB_NAME = _neo4j_host.split(".")[0]

# Paths
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parent
LOG_DIR = SCRIPT_DIR / "logs"
DATA_DIR = SCRIPT_DIR / "data"
TMP_DIR = SCRIPT_DIR / "tmp"
LOG_FILE = LOG_DIR / "docling-cron.jsonl"
PROCESSED_FILE = DATA_DIR / "processed-urls.json"

# Ensure dirs exist
LOG_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)
TMP_DIR.mkdir(parents=True, exist_ok=True)

# Processing limits
MAX_PDFS_PER_RUN = 10
MAX_PDF_SIZE_BYTES = 50 * 1024 * 1024  # 50MB
MAX_TEXT_FOR_E5 = 1500  # Pinecone E5 integrated max useful length
CHUNK_SIZE_CHARS = 2000  # ~500 tokens at 4 chars/token
CHUNK_OVERLAP_CHARS = 200  # ~50 tokens overlap
MIN_CHUNK_LEN = 80
TAVILY_DELAY = 1.5  # seconds between Tavily requests
PINECONE_DELAY = 0.03  # seconds between Pinecone upserts

SECTORS = ["finance", "btp", "juridique", "industrie"]

# ==========================================================================
# TAVILY SEARCH QUERIES — Expert documents per sector
# ==========================================================================
# Each query targets REAL professional PDFs: standards, regulations, reports.
# "filetype:pdf" is implicit in Tavily advanced search when relevant.

SECTOR_QUERIES = {
    "finance": [
        "IFRS norme comptable internationale texte officiel filetype:pdf",
        "AMF rapport annuel autorite marches financiers filetype:pdf",
        "Banque de France rapport stabilite financiere filetype:pdf",
        "rapport annuel financier CAC 40 societe filetype:pdf",
        "reglementation bancaire Bale III CRD exigences fonds propres filetype:pdf",
        "guide audit commissaire aux comptes CNCC filetype:pdf",
        "ACPR rapport prudentiel assurance banque filetype:pdf",
        "norme ISA audit international standard filetype:pdf",
        "directive AIFMD gestion fonds investissement alternatif filetype:pdf",
        "ESMA guidelines MiFID II marches financiers filetype:pdf",
    ],
    "btp": [
        "DTU document technique unifie norme construction filetype:pdf",
        "Eurocode calcul structure beton acier bois filetype:pdf",
        "CCTP cahier clauses techniques particulieres batiment filetype:pdf",
        "AFNOR norme NF construction batiment filetype:pdf",
        "RE2020 reglementation environnementale batiment neuf filetype:pdf",
        "guide technique fondations profondes pieux filetype:pdf",
        "norme parasismique Eurocode 8 zonage sismique France filetype:pdf",
        "DTU 31.2 ossature bois construction murs filetype:pdf",
        "diagnostic technique immobilier DPE amiante plomb filetype:pdf",
        "CSTB avis technique construction innovation filetype:pdf",
    ],
    "juridique": [
        "code civil francais texte officiel articles filetype:pdf",
        "code commerce societe commerciale filetype:pdf",
        "RGPD reglement protection donnees personnelles guide CNIL filetype:pdf",
        "jurisprudence cour cassation arret decision filetype:pdf",
        "code travail droit social contrat salarie filetype:pdf",
        "contrat type CGV conditions generales vente modele filetype:pdf",
        "statuts societe SAS SARL creation entreprise filetype:pdf",
        "directive europeenne transposition droit francais filetype:pdf",
        "guide pratique procedure civile tribunal filetype:pdf",
        "droit immobilier copropriete loi ALUR filetype:pdf",
    ],
    "industrie": [
        "ISO 9001 management qualite exigences certification filetype:pdf",
        "AMDEC analyse modes defaillance effets criticite guide filetype:pdf",
        "fiche donnees securite FDS produit chimique filetype:pdf",
        "ISO 14001 management environnemental SME filetype:pdf",
        "ISO 45001 sante securite travail SST filetype:pdf",
        "maintenance preventive industrielle planification equipement filetype:pdf",
        "lean manufacturing gaspillage kaizen amelioration continue filetype:pdf",
        "norme REACH substances chimiques enregistrement filetype:pdf",
        "controle non destructif CND ultrasons radiographie filetype:pdf",
        "HACCP securite alimentaire analyse risques filetype:pdf",
    ],
}


# ==========================================================================
# LOGGING
# ==========================================================================

def log(msg, level="INFO"):
    """Print with timestamp and write to JSONL log."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    prefix = {"INFO": "+", "WARN": "!", "ERROR": "X", "OK": "v", "SKIP": "-"}.get(level, " ")
    print(f"[{ts}] [{prefix}] {msg}", flush=True)


def log_jsonl(entry):
    """Append a JSON entry to the JSONL log file."""
    entry["timestamp"] = datetime.now(timezone.utc).isoformat()
    try:
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except Exception as e:
        print(f"[WARN] Could not write log: {e}", flush=True)


# ==========================================================================
# PROCESSED URLS TRACKER
# ==========================================================================

def load_processed():
    """Load the processed URLs tracker."""
    if PROCESSED_FILE.exists():
        try:
            return json.loads(PROCESSED_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            pass
    return {
        "urls": {},
        "stats": {
            "total_processed": 0,
            "total_chunks": 0,
            "created": datetime.now(timezone.utc).isoformat(),
        },
    }


def save_processed(data):
    """Save the processed URLs tracker atomically."""
    data["stats"]["last_updated"] = datetime.now(timezone.utc).isoformat()
    tmp = str(PROCESSED_FILE) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    os.replace(tmp, str(PROCESSED_FILE))


def is_processed(data, url):
    """Check if a URL has been processed before."""
    return url in data.get("urls", {})


def mark_processed(data, url, info):
    """Mark a URL as processed."""
    data["urls"][url] = info
    data["stats"]["total_processed"] = len(data["urls"])


# ==========================================================================
# UTILITIES
# ==========================================================================

def short_hash(text):
    """8-char hash for deduplication."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:8]


def url_hash(url):
    """12-char hash for a URL."""
    return hashlib.sha256(url.encode()).hexdigest()[:12]


def clean_text(text):
    """Clean raw web/PDF content for chunking."""
    if not text:
        return ""
    # Remove excessive whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    # Remove common web artifacts
    text = re.sub(r'Cookie[s]?.*?(?:accepter|refuser|parametrer).*?\n', '', text, flags=re.IGNORECASE)
    text = re.sub(r'(?:Partager|Share)[\s:]*(?:Facebook|Twitter|LinkedIn|Email).*?\n', '', text, flags=re.IGNORECASE)
    text = re.sub(r'(?:\u00a9|Copyright).*?\d{4}.*?\n', '', text, flags=re.IGNORECASE)
    # Remove page numbers / headers that repeat
    text = re.sub(r'\n\s*Page \d+ (?:of|sur|/) \d+\s*\n', '\n', text)
    return text.strip()


def chunk_text(text, chunk_size=CHUNK_SIZE_CHARS, overlap=CHUNK_OVERLAP_CHARS):
    """Split text into overlapping chunks, preferring sentence/paragraph boundaries."""
    if not text or len(text) < MIN_CHUNK_LEN:
        return []

    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = start + chunk_size

        if end >= text_len:
            chunk = text[start:].strip()
            if len(chunk) >= MIN_CHUNK_LEN:
                chunks.append(chunk)
            break

        # Try to break at paragraph boundary
        candidate = text[start:end]
        para_break = candidate.rfind('\n\n')
        if para_break > chunk_size * 0.4:
            end = start + para_break + 2
        else:
            # Try sentence boundary (French + English)
            for sep in ['. ', '.\n', '? ', '!\n', ';\n', ' ; ']:
                sent_break = candidate.rfind(sep)
                if sent_break > chunk_size * 0.4:
                    end = start + sent_break + len(sep)
                    break

        chunk = text[start:end].strip()
        if len(chunk) >= MIN_CHUNK_LEN:
            chunks.append(chunk)

        # Move forward with overlap
        start = end - overlap
        if start <= (end - chunk_size):
            start = end

    return chunks


def extract_domain(url):
    """Extract domain name from URL."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc.replace("www.", "")
    except Exception:
        return "unknown"


# ==========================================================================
# API FUNCTIONS
# ==========================================================================

def tavily_search(query, max_results=5):
    """Search Tavily for documents. Returns list of results."""
    payload = json.dumps({
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "advanced",
        "max_results": max_results,
        "include_raw_content": False,  # We only need URLs for PDFs
    }).encode("utf-8")

    req = urllib.request.Request(
        TAVILY_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30, context=_ssl_ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("results", [])
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8")[:200]
        except Exception:
            pass
        log(f"Tavily HTTP {e.code}: {body}", "ERROR")
        return []
    except Exception as e:
        log(f"Tavily request failed: {e}", "ERROR")
        return []


def download_pdf(url, max_size=MAX_PDF_SIZE_BYTES):
    """Download a PDF to temp directory. Returns (local_path, size_bytes) or (None, 0)."""
    filename = f"{url_hash(url)}.pdf"
    local_path = TMP_DIR / filename

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; Nomos-Docling/2.0; +https://nomos.ai)",
                "Accept": "application/pdf,*/*",
            },
        )

        with urllib.request.urlopen(req, timeout=120, context=_ssl_ctx) as resp:
            # Check content length if available
            content_length = resp.headers.get("Content-Length")
            if content_length and int(content_length) > max_size:
                log(f"PDF too large: {int(content_length) / 1024 / 1024:.1f}MB > {max_size / 1024 / 1024:.0f}MB limit", "SKIP")
                return None, 0

            # Stream download with size check
            total = 0
            with open(local_path, "wb") as f:
                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_size:
                        log(f"PDF exceeded {max_size / 1024 / 1024:.0f}MB during download — aborting", "SKIP")
                        f.close()
                        local_path.unlink(missing_ok=True)
                        return None, 0
                    f.write(chunk)

        # Verify it looks like a PDF
        with open(local_path, "rb") as f:
            header = f.read(5)
        if header != b'%PDF-':
            log(f"Downloaded file is not a PDF (header: {header!r})", "SKIP")
            local_path.unlink(missing_ok=True)
            return None, 0

        return str(local_path), total

    except Exception as e:
        log(f"Download failed: {e}", "ERROR")
        if local_path.exists():
            local_path.unlink(missing_ok=True)
        return None, 0


def process_with_docling(pdf_path):
    """Process a PDF with local Docling. Returns (full_text, tables, num_pages) or (None, [], 0)."""
    try:
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.datamodel.base_models import InputFormat

        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True
        pipeline_options.do_table_structure = True

        try:
            from docling.datamodel.pipeline_options import TableFormerMode
            pipeline_options.table_structure_options.mode = TableFormerMode.FAST
        except (ImportError, AttributeError):
            pass

        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
            }
        )

        result = converter.convert(pdf_path)
        doc = result.document
        full_text = doc.export_to_markdown()

        # Extract tables
        tables = []
        try:
            for i, table in enumerate(doc.tables):
                table_data = {"index": i}
                try:
                    table_data["markdown"] = table.export_to_markdown()
                except Exception:
                    try:
                        table_data["text"] = str(table)
                    except Exception:
                        table_data["text"] = "[table extraction failed]"
                tables.append(table_data)
        except Exception:
            pass

        # Count pages
        num_pages = 0
        try:
            md_text = full_text
            page_splits = md_text.split("\n---\n") if "\n---\n" in md_text else [md_text]
            num_pages = len(page_splits)
        except Exception:
            num_pages = 1

        return full_text, tables, num_pages

    except Exception as e:
        log(f"Docling processing failed: {e}", "ERROR")
        log(traceback.format_exc(), "ERROR")
        return None, [], 0


def pinecone_upsert(record_id, text, sector, source, title=""):
    """Upsert a single record to Pinecone E5 integrated embedding index."""
    # Truncate text for E5 max useful length
    if len(text) > MAX_TEXT_FOR_E5:
        text = text[:MAX_TEXT_FOR_E5]

    payload = json.dumps({
        "_id": record_id,
        "text": text,
        "sector": sector,
        "source": source,
        "title": title[:200] if title else "",
    }).encode("utf-8")

    req = urllib.request.Request(
        PINECONE_UPSERT_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Api-Key": PINECONE_API_KEY,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30, context=_ssl_ctx) as resp:
            return True
    except urllib.error.HTTPError as e:
        if e.code == 409:
            return True  # Already exists
        body = ""
        try:
            body = e.read().decode("utf-8")[:200]
        except Exception:
            pass
        log(f"Pinecone upsert {record_id}: HTTP {e.code} {body}", "ERROR")
        return False
    except Exception as e:
        log(f"Pinecone upsert {record_id}: {e}", "ERROR")
        return False


def supabase_insert(sector, title, context, source_url, doc_type="pdf", metadata=None):
    """Insert a document into Supabase sector_documents table."""
    if not SUPABASE_URL or not SUPABASE_API_KEY:
        return False

    row = {
        "sector": sector,
        "title": title[:500] if title else "Untitled",
        "context": context[:10000] if context else "",
        "source": source_url[:1000] if source_url else "",
        "doc_type": doc_type,
        "language": "fr",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    if metadata:
        row["metadata"] = json.dumps(metadata, ensure_ascii=False)

    payload = json.dumps(row, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(
        SUPABASE_INSERT_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "apikey": SUPABASE_API_KEY,
            "Authorization": f"Bearer {SUPABASE_API_KEY}",
            "Prefer": "return=minimal",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30, context=_ssl_ctx) as resp:
            return True
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8")[:300]
        except Exception:
            pass
        # 409 = duplicate (constraint violation) — not an error
        if e.code == 409:
            return True
        log(f"Supabase insert failed: HTTP {e.code} {body}", "ERROR")
        return False
    except Exception as e:
        log(f"Supabase insert failed: {e}", "ERROR")
        return False


def neo4j_create_entity(sector, title, source_url, doc_type="pdf", chunk_count=0):
    """Create a document entity in Neo4j via HTTP Cypher API."""
    if not NEO4J_HTTP_HOST or not NEO4J_PASSWORD:
        return False

    # Neo4j Aura HTTP API endpoint
    query_url = f"{NEO4J_HTTP_HOST}/db/{NEO4J_DB_NAME}/query/v2"

    cypher = """
    MERGE (d:SectorDocument {url: $url})
    ON CREATE SET
        d.title = $title,
        d.sector = $sector,
        d.doc_type = $doc_type,
        d.chunk_count = $chunk_count,
        d.source = 'docling-cron',
        d.created_at = datetime(),
        d.processed = true
    ON MATCH SET
        d.chunk_count = $chunk_count,
        d.last_seen = datetime()
    WITH d
    MERGE (s:Sector {name: $sector})
    MERGE (d)-[:BELONGS_TO]->(s)
    RETURN d.url AS url
    """

    payload = json.dumps({
        "statement": cypher,
        "parameters": {
            "url": source_url[:500],
            "title": title[:300],
            "sector": sector,
            "doc_type": doc_type,
            "chunk_count": chunk_count,
        },
    }).encode("utf-8")

    # Neo4j Aura uses basic auth: username = db name, password = db password
    import base64
    auth_str = base64.b64encode(f"neo4j:{NEO4J_PASSWORD}".encode()).decode()

    req = urllib.request.Request(
        query_url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Basic {auth_str}",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30, context=_ssl_ctx) as resp:
            return True
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8")[:300]
        except Exception:
            pass
        log(f"Neo4j create failed: HTTP {e.code} {body}", "WARN")
        return False
    except Exception as e:
        log(f"Neo4j create failed: {e}", "WARN")
        return False


# ==========================================================================
# DISCOVERY — Find new expert PDFs via Tavily
# ==========================================================================

def discover_pdfs(sectors, processed_data, max_per_sector=3):
    """
    Use Tavily to discover new expert PDFs for each sector.
    Returns list of (sector, url, title) tuples.
    """
    discovered = []

    for sector in sectors:
        queries = SECTOR_QUERIES.get(sector, [])
        if not queries:
            continue

        log(f"[{sector}] Searching for expert PDFs ({len(queries)} queries)...")
        sector_found = 0

        for qi, query in enumerate(queries):
            if sector_found >= max_per_sector:
                break

            results = tavily_search(query, max_results=5)

            for result in results:
                url = result.get("url", "")
                title = result.get("title", "")

                # Only accept PDFs
                is_pdf = (
                    url.lower().endswith(".pdf")
                    or "filetype=pdf" in url.lower()
                    or ".pdf?" in url.lower()
                    or "/pdf/" in url.lower()
                )

                if not is_pdf:
                    continue

                # Skip already processed
                if is_processed(processed_data, url):
                    continue

                # Skip already discovered this run
                if any(d[1] == url for d in discovered):
                    continue

                discovered.append((sector, url, title))
                sector_found += 1
                log(f"  [{sector}] Found: {title[:60]} ({extract_domain(url)})")

                if sector_found >= max_per_sector:
                    break

            time.sleep(TAVILY_DELAY)

        if sector_found == 0:
            log(f"  [{sector}] No new PDFs found this run", "SKIP")

    return discovered


# ==========================================================================
# MAIN PROCESSING PIPELINE
# ==========================================================================

def process_pdf(sector, url, title, processed_data, dry_run=False, skip_neo4j=False):
    """
    Full pipeline for a single PDF:
    Download -> Docling -> Chunk -> Pinecone + Supabase + Neo4j
    Returns stats dict.
    """
    stats = {
        "sector": sector,
        "url": url,
        "title": title,
        "status": "started",
        "download_size": 0,
        "text_length": 0,
        "num_pages": 0,
        "num_tables": 0,
        "num_chunks": 0,
        "pinecone_upserted": 0,
        "supabase_inserted": 0,
        "neo4j_created": 0,
        "errors": [],
        "duration_s": 0,
    }

    t0 = time.time()
    pdf_path = None

    try:
        # Step 1: Download
        log(f"  Downloading: {url[:80]}...")
        pdf_path, size = download_pdf(url)
        if not pdf_path:
            stats["status"] = "download_failed"
            stats["errors"].append("Download failed or file too large/not PDF")
            return stats
        stats["download_size"] = size
        log(f"  Downloaded: {size / 1024:.0f}KB")

        if dry_run:
            stats["status"] = "dry_run"
            log(f"  [DRY RUN] Would process {size / 1024:.0f}KB PDF", "SKIP")
            return stats

        # Step 2: Process with Docling
        log(f"  Processing with Docling...")
        t_docling = time.time()
        full_text, tables, num_pages = process_with_docling(pdf_path)
        docling_time = time.time() - t_docling

        if not full_text or len(full_text) < 100:
            stats["status"] = "extraction_failed"
            stats["errors"].append(f"Docling extracted too little text ({len(full_text or '')} chars)")
            return stats

        stats["text_length"] = len(full_text)
        stats["num_pages"] = num_pages
        stats["num_tables"] = len(tables)
        log(f"  Extracted: {len(full_text):,} chars, {num_pages} pages, {len(tables)} tables ({docling_time:.1f}s)")

        # Step 3: Clean and chunk
        cleaned = clean_text(full_text)
        chunks = chunk_text(cleaned)
        stats["num_chunks"] = len(chunks)

        if not chunks:
            stats["status"] = "no_chunks"
            stats["errors"].append("Text too short for chunking")
            return stats

        log(f"  Chunked: {len(chunks)} chunks ({CHUNK_SIZE_CHARS} chars, {CHUNK_OVERLAP_CHARS} overlap)")

        # Step 4: Ingest to Pinecone E5
        log(f"  Upserting to Pinecone E5...")
        domain = extract_domain(url)
        source_tag = f"docling-{domain}"
        pinecone_ok = 0

        for ci, chunk in enumerate(chunks):
            chunk_hash = short_hash(chunk)
            record_id = f"docling-{sector}-{url_hash(url)}-{ci:04d}"

            ok = pinecone_upsert(record_id, chunk, sector, source_tag, title)
            if ok:
                pinecone_ok += 1

            time.sleep(PINECONE_DELAY)

            # Progress every 50 chunks
            if (ci + 1) % 50 == 0:
                log(f"    Pinecone: {ci + 1}/{len(chunks)} chunks...")

        stats["pinecone_upserted"] = pinecone_ok
        log(f"  Pinecone: {pinecone_ok}/{len(chunks)} chunks upserted")

        # Step 5: Ingest to Supabase
        # Insert the full document (or a representative chunk) as context
        log(f"  Inserting to Supabase...")
        # Insert first chunk as representative context (Supabase has 10K limit on context)
        representative_text = cleaned[:10000]
        sb_ok = supabase_insert(
            sector=sector,
            title=title,
            context=representative_text,
            source_url=url,
            doc_type="pdf",
            metadata={
                "num_chunks": len(chunks),
                "num_pages": num_pages,
                "num_tables": len(tables),
                "text_length": len(full_text),
                "source": source_tag,
                "docling_processed": True,
            },
        )
        if sb_ok:
            stats["supabase_inserted"] = 1
            log(f"  Supabase: 1 document inserted")
        else:
            stats["errors"].append("Supabase insert failed")

        # Step 6: Create entity in Neo4j
        if not skip_neo4j:
            log(f"  Creating Neo4j entity...")
            neo_ok = neo4j_create_entity(
                sector=sector,
                title=title,
                source_url=url,
                doc_type="pdf",
                chunk_count=len(chunks),
            )
            if neo_ok:
                stats["neo4j_created"] = 1
                log(f"  Neo4j: entity created")
            else:
                stats["errors"].append("Neo4j entity creation failed (non-critical)")

        stats["status"] = "success"

    except Exception as e:
        stats["status"] = "error"
        stats["errors"].append(f"{type(e).__name__}: {str(e)[:300]}")
        log(f"  Processing error: {e}", "ERROR")

    finally:
        # Cleanup temp file
        if pdf_path and Path(pdf_path).exists():
            try:
                Path(pdf_path).unlink()
            except Exception:
                pass

        stats["duration_s"] = round(time.time() - t0, 1)

    return stats


# ==========================================================================
# MAIN
# ==========================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Docling continuous ingestion cron — Expert PDF discovery + processing"
    )
    parser.add_argument(
        "--sector",
        choices=SECTORS + ["all"],
        default="all",
        help="Sector to process (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Discover PDFs but do not download/process/ingest",
    )
    parser.add_argument(
        "--max-pdfs",
        type=int,
        default=MAX_PDFS_PER_RUN,
        help=f"Max PDFs to process per run (default: {MAX_PDFS_PER_RUN})",
    )
    parser.add_argument(
        "--max-per-sector",
        type=int,
        default=3,
        help="Max new PDFs to discover per sector (default: 3)",
    )
    parser.add_argument(
        "--skip-neo4j",
        action="store_true",
        help="Skip Neo4j entity creation",
    )
    args = parser.parse_args()

    # Validate API keys
    missing = []
    if not TAVILY_API_KEY:
        missing.append("TAVILY_API_KEY")
    if not PINECONE_API_KEY:
        missing.append("PINECONE_API_KEY")
    if not args.dry_run and not SUPABASE_URL:
        missing.append("SUPABASE_URL")

    if missing:
        log(f"Missing environment variables: {', '.join(missing)}", "ERROR")
        log("Run: source .env.local", "ERROR")
        sys.exit(1)

    sectors = SECTORS if args.sector == "all" else [args.sector]

    # Banner
    print("=" * 70)
    print("  DOCLING CONTINUOUS INGESTION CRON")
    print(f"  Started:  {datetime.now(timezone.utc).isoformat()}")
    print(f"  Sectors:  {', '.join(sectors)}")
    print(f"  Max PDFs: {args.max_pdfs}")
    print(f"  Mode:     {'DRY RUN' if args.dry_run else 'LIVE'}")
    print(f"  Neo4j:    {'SKIP' if args.skip_neo4j else 'ON'}")
    print("=" * 70)
    print("", flush=True)

    # Load processed URLs tracker
    processed_data = load_processed()
    existing_count = len(processed_data.get("urls", {}))
    log(f"Processed URLs tracker: {existing_count} already processed")

    # Phase 1: Discovery
    log("=== Phase 1: Document Discovery ===")
    discovered = discover_pdfs(sectors, processed_data, max_per_sector=args.max_per_sector)
    log(f"Discovered {len(discovered)} new PDFs across {len(sectors)} sectors")

    if not discovered:
        log("No new PDFs to process. Exiting.", "OK")
        log_jsonl({
            "event": "cron_run",
            "status": "no_new_pdfs",
            "sectors": sectors,
            "existing_count": existing_count,
        })
        return

    # Limit total PDFs
    if len(discovered) > args.max_pdfs:
        discovered = discovered[:args.max_pdfs]
        log(f"Limited to {args.max_pdfs} PDFs for this run")

    # Phase 2: Process each PDF
    log(f"\n=== Phase 2: Processing {len(discovered)} PDFs ===")
    run_stats = {
        "total": len(discovered),
        "success": 0,
        "failed": 0,
        "dry_run": 0,
        "total_chunks": 0,
        "total_pinecone": 0,
        "total_supabase": 0,
        "total_neo4j": 0,
        "details": [],
    }

    for i, (sector, url, title) in enumerate(discovered):
        log(f"\n--- [{i + 1}/{len(discovered)}] {sector.upper()}: {title[:50]} ---")

        stats = process_pdf(
            sector=sector,
            url=url,
            title=title,
            processed_data=processed_data,
            dry_run=args.dry_run,
            skip_neo4j=args.skip_neo4j,
        )

        run_stats["details"].append(stats)

        if stats["status"] == "success":
            run_stats["success"] += 1
            run_stats["total_chunks"] += stats["num_chunks"]
            run_stats["total_pinecone"] += stats["pinecone_upserted"]
            run_stats["total_supabase"] += stats["supabase_inserted"]
            run_stats["total_neo4j"] += stats["neo4j_created"]

            # Mark as processed
            mark_processed(processed_data, url, {
                "sector": sector,
                "title": title,
                "chunks": stats["num_chunks"],
                "text_length": stats["text_length"],
                "processed_at": datetime.now(timezone.utc).isoformat(),
            })
            save_processed(processed_data)

        elif stats["status"] == "dry_run":
            run_stats["dry_run"] += 1
        else:
            run_stats["failed"] += 1

        log(f"  Result: {stats['status']} ({stats['duration_s']}s)")

    # Summary
    print(f"\n{'=' * 70}")
    print("  CRON RUN SUMMARY")
    print(f"{'=' * 70}")
    print(f"  PDFs discovered:    {len(discovered)}")
    print(f"  Successfully done:  {run_stats['success']}")
    print(f"  Failed:             {run_stats['failed']}")
    if args.dry_run:
        print(f"  Dry run (skipped):  {run_stats['dry_run']}")
    print(f"  Total chunks:       {run_stats['total_chunks']}")
    print(f"  Pinecone upserted:  {run_stats['total_pinecone']}")
    print(f"  Supabase inserted:  {run_stats['total_supabase']}")
    print(f"  Neo4j entities:     {run_stats['total_neo4j']}")
    print(f"  URLs now tracked:   {len(processed_data.get('urls', {}))}")
    print(f"  Finished:           {datetime.now(timezone.utc).isoformat()}")
    print(f"{'=' * 70}")

    # Log run to JSONL
    log_jsonl({
        "event": "cron_run",
        "status": "completed",
        "sectors": sectors,
        "mode": "dry_run" if args.dry_run else "live",
        "discovered": len(discovered),
        "success": run_stats["success"],
        "failed": run_stats["failed"],
        "total_chunks": run_stats["total_chunks"],
        "pinecone_upserted": run_stats["total_pinecone"],
        "supabase_inserted": run_stats["total_supabase"],
        "neo4j_created": run_stats["total_neo4j"],
        "urls_tracked": len(processed_data.get("urls", {})),
    })

    # Exit with error code if all failed
    if run_stats["success"] == 0 and run_stats["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
