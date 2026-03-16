#!/usr/bin/env python3
"""
AMF Ingestion Daemon — Financial Regulatory Publications for Finance Sector.
============================================================================
Fetches publications from the AMF (Autorite des Marches Financiers) via
their RSS feeds, downloads PDFs when available, processes them through
Docling S6, and stores structured chunks in Supabase + Pinecone.

AMF publishes: rapports, recommandations, decisions, sanctions, guides,
positions, controles SPOT — all critical for finance sector expertise.

RSS feeds:
  - /fr/flux-rss/display/25 — Publications (rapports, etudes, guides)
  - /fr/flux-rss/display/31 — Regulation (positions, recommandations)
  - /fr/flux-rss/display/28 — Warnings (alertes, mises en garde)
  - /fr/flux-rss/display/21 — All news and publications

Architecture:
  1. Parse AMF RSS feeds for new publications
  2. Fetch each publication page, extract PDF links
  3. PDF -> Docling S6 for structured text extraction
  4. Non-PDF pages -> direct HTML text extraction
  5. Chunk by section for long documents
  6. Store in Supabase sector_documents (sector=finance)
  7. Upsert to Pinecone E5 integrated embedding index
  8. Track progress in data/ingest/amf-state.json

Usage:
  source .env.local
  python3 ops/ingest-amf.py                          # One-shot
  python3 ops/ingest-amf.py --daemon --interval 600  # 10min daemon
  python3 ops/ingest-amf.py --batch-size 20          # Smaller batches
  python3 ops/ingest-amf.py --dry-run                # Preview only
  python3 ops/ingest-amf.py --status                 # Show stats
  python3 ops/ingest-amf.py --feed all               # All feeds
  nohup python3 ops/ingest-amf.py --daemon > data/ingest/amf-daemon.log 2>&1 &
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
import re
import signal
import ssl
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
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

# -- SSL context (permissive for government sites) ----------------------------
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE

# =============================================================================
# CONFIGURATION
# =============================================================================

# AMF RSS Feeds
AMF_BASE = "https://www.amf-france.org"
AMF_FEEDS = {
    "publications": f"{AMF_BASE}/fr/flux-rss/display/25",  # Reports, studies, guides
    "regulation": f"{AMF_BASE}/fr/flux-rss/display/31",    # Positions, recommendations
    "warnings": f"{AMF_BASE}/fr/flux-rss/display/28",      # Alerts, blacklists
    "all": f"{AMF_BASE}/fr/flux-rss/display/21",           # Everything
}

# Docling S6 (PDF processing)
DOCLING_BASE = "https://lbjlincoln-nomos-docling-api.hf.space"
DOCLING_CONVERT_URL = f"{DOCLING_BASE}/convert-url"
DOCLING_TIMEOUT = 120  # 2 min for PDFs (HF Spaces can be slow)

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
STATE_FILE = DATA_DIR / "amf-state.json"
LOG_FILE = DATA_DIR / "amf.jsonl"
PID_FILE = DATA_DIR / "amf.pid"

# Processing config
DEFAULT_BATCH_SIZE = 50
DEFAULT_INTERVAL = 600  # 10 minutes
RATE_LIMIT_DELAY = 1.0  # 1 req/sec
HTTP_TIMEOUT = 30
PINECONE_TIMEOUT = 15
MAX_CHUNK_SIZE = 4000  # chars per chunk
MIN_CHUNK_SIZE = 200
OVERLAP_SIZE = 200  # chars overlap between chunks

# AMF document type classification
DOC_TYPE_PATTERNS = {
    "rapport": ["rapport", "annual report", "rapports-etudes"],
    "recommandation": ["recommandation", "position-recommandation", "DOC-"],
    "decision": ["decision", "sanction", "commission-des-sanctions"],
    "guide": ["guide", "guide-pratique", "guides"],
    "controle_spot": ["controle", "contrôle", "spot", "controles-spot"],
    "position": ["position", "instruction", "positions"],
    "etude": ["etude", "étude", "analyse", "research", "rapports-etudes-et-analyses"],
    "discours": ["discours", "prise de parole", "prises-de-parole"],
    "lettre": ["lettre", "newsletter"],
    "consultation": ["consultation", "publique"],
}

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
        entry = {"ts": ts, "level": level, "msg": msg, "source": "amf"}
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
    # Add User-Agent for AMF (they may block default Python UA)
    if "User-Agent" not in headers:
        headers["User-Agent"] = (
            "Mozilla/5.0 (compatible; NomosRAG/1.0; +https://nomos-ai.com)"
        )
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
# RSS FEED PARSING
# =============================================================================

def fetch_rss_feed(feed_url):
    """
    Fetch and parse an AMF RSS feed.
    Returns list of dicts with: title, link, pub_date, description, categories.
    """
    status, body, err = http_request(feed_url, timeout=HTTP_TIMEOUT)
    if err:
        return [], f"RSS fetch error: {err}"
    if status != 200:
        return [], f"RSS HTTP {status}"

    try:
        xml_text = body.decode("utf-8", errors="replace")
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        return [], f"XML parse error: {e}"

    items = []
    for item_el in root.findall(".//item"):
        title = ""
        link = ""
        pub_date = ""
        description = ""

        title_el = item_el.find("title")
        if title_el is not None and title_el.text:
            title = unescape(title_el.text.strip())

        link_el = item_el.find("link")
        if link_el is not None and link_el.text:
            link = link_el.text.strip()
            # Remove tracking parameters
            link = re.sub(r'#xts=\d+&xtor=RSS-\d+&type=RSS$', '', link)

        pubdate_el = item_el.find("pubDate")
        if pubdate_el is not None and pubdate_el.text:
            try:
                dt = parsedate_to_datetime(pubdate_el.text.strip())
                pub_date = dt.strftime("%Y-%m-%d")
            except Exception:
                pub_date = pubdate_el.text.strip()[:10]

        desc_el = item_el.find("description")
        if desc_el is not None and desc_el.text:
            description = unescape(desc_el.text.strip())

        # Extract categories from description (AMF puts them there)
        categories = []
        if description:
            # AMF description format: "Category1    Category2    Title text"
            parts = re.split(r'\s{2,}', description)
            # Last part is usually the title repeated, earlier parts are categories
            if len(parts) > 1:
                categories = [p.strip() for p in parts[:-1] if p.strip() and len(p.strip()) > 2]

        if title and link:
            items.append({
                "title": title,
                "link": link,
                "pub_date": pub_date,
                "description": description,
                "categories": categories[:10],
            })

    return items, None


def classify_doc_type(title, link, categories):
    """
    Classify an AMF publication by type.
    Returns doc_type string.
    """
    text = f"{title} {link} {' '.join(categories)}".lower()

    for doc_type, patterns in DOC_TYPE_PATTERNS.items():
        for pattern in patterns:
            if pattern.lower() in text:
                return doc_type

    return "publication"


def extract_reference(title, link):
    """
    Extract AMF reference number from title or URL.
    e.g., DOC-2023-09, or construct one from the URL slug.
    """
    # Look for DOC-XXXX-XX pattern
    match = re.search(r'(DOC-\d{4}-\d{1,2})', title, re.IGNORECASE)
    if match:
        return match.group(1)

    # Look for reference in URL path
    match = re.search(r'(DOC-\d{4}-\d{1,2})', link, re.IGNORECASE)
    if match:
        return match.group(1)

    # Construct from URL slug
    path = urllib.parse.urlparse(link).path
    slug = path.rstrip("/").split("/")[-1] if path else ""
    if slug:
        return f"AMF-{slug[:50]}"

    return ""


# =============================================================================
# CONTENT EXTRACTION
# =============================================================================

def fetch_page_content(url):
    """
    Fetch an AMF publication page and extract text content.
    Returns (text, pdf_urls, error).
    """
    status, body, err = http_request(url, timeout=HTTP_TIMEOUT)
    if err:
        return "", [], f"Page fetch error: {err}"
    if status != 200:
        return "", [], f"Page HTTP {status}"

    html = body.decode("utf-8", errors="replace")

    # Extract PDF links
    pdf_urls = []
    pdf_pattern = re.compile(
        r'href=["\']([^"\']*\.pdf[^"\']*)["\']',
        re.IGNORECASE,
    )
    for match in pdf_pattern.finditer(html):
        pdf_url = match.group(1)
        if not pdf_url.startswith("http"):
            pdf_url = AMF_BASE + pdf_url
        pdf_urls.append(pdf_url)

    # Also look for download links in common AMF patterns
    download_pattern = re.compile(
        r'href=["\']([^"\']*(?:files|download|document)[^"\']*)["\']',
        re.IGNORECASE,
    )
    for match in download_pattern.finditer(html):
        dl_url = match.group(1)
        if dl_url.endswith(".pdf") or "/pdf/" in dl_url:
            if not dl_url.startswith("http"):
                dl_url = AMF_BASE + dl_url
            if dl_url not in pdf_urls:
                pdf_urls.append(dl_url)

    # Extract text content from the page (strip HTML)
    text = extract_text_from_html(html)

    return text, pdf_urls, None


def extract_text_from_html(html):
    """
    Extract meaningful text from an AMF publication HTML page.
    Targets the main content area, strips navigation/menus.
    AMF uses a JS-rendered SPA, so we try multiple extraction strategies.
    """
    # Remove script/style blocks
    html = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', html, flags=re.IGNORECASE)
    html = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', html, flags=re.IGNORECASE)
    html = re.sub(r'<nav[^>]*>[\s\S]*?</nav>', '', html, flags=re.IGNORECASE)
    html = re.sub(r'<header[^>]*>[\s\S]*?</header>', '', html, flags=re.IGNORECASE)
    html = re.sub(r'<footer[^>]*>[\s\S]*?</footer>', '', html, flags=re.IGNORECASE)

    # Strategy 1: Look for AMF-specific content containers
    content_candidates = []
    for pattern in [
        r'<div[^>]*class="[^"]*(?:field--name-body|text-formatted|node__content|article-body|publication-content)[^"]*"[^>]*>([\s\S]*?)</div>',
        r'<article[^>]*>([\s\S]*?)</article>',
        r'<main[^>]*>([\s\S]*?)</main>',
        r'<div[^>]*class="[^"]*(?:content|article|body)[^"]*"[^>]*>([\s\S]*?)</div>',
        r'<div[^>]*id="[^"]*(?:content|main|article)[^"]*"[^>]*>([\s\S]*?)</div>',
    ]:
        for m in re.finditer(pattern, html, re.IGNORECASE):
            candidate = m.group(1)
            if len(candidate) > 100:
                content_candidates.append(candidate)

    # Use the longest content candidate, or fall back to full HTML
    if content_candidates:
        html = max(content_candidates, key=len)

    # Strategy 2: Extract from meta tags (AMF pages have rich meta)
    meta_texts = []
    for meta_pattern in [
        r'<meta[^>]*name="description"[^>]*content="([^"]+)"',
        r'<meta[^>]*property="og:description"[^>]*content="([^"]+)"',
        r'<meta[^>]*name="abstract"[^>]*content="([^"]+)"',
    ]:
        meta_match = re.search(meta_pattern, html, re.IGNORECASE)
        if meta_match:
            meta_texts.append(unescape(meta_match.group(1).strip()))

    # Convert common block elements to newlines
    html = re.sub(r'<(?:p|div|br|h[1-6]|li|tr)[^>]*>', '\n', html, flags=re.IGNORECASE)
    html = re.sub(r'</(?:p|div|h[1-6]|li|tr|td|th)>', '\n', html, flags=re.IGNORECASE)

    # Strip remaining HTML tags
    text = re.sub(r'<[^>]+>', ' ', html)

    # Clean up whitespace
    text = unescape(text)
    lines = []
    for line in text.split("\n"):
        line = re.sub(r'\s+', ' ', line).strip()
        if line and len(line) > 3:
            lines.append(line)

    result = "\n".join(lines)

    # If main extraction yielded little, prepend meta descriptions
    if len(result) < MIN_CHUNK_SIZE and meta_texts:
        result = "\n".join(meta_texts) + "\n\n" + result

    return result


def process_pdf_via_docling(pdf_url):
    """
    Send a PDF URL to Docling S6 for structured text extraction.
    Returns (extracted_text, error).
    """
    payload = json.dumps({
        "url": pdf_url,
        "extract_tables": True,
        "extract_images": False,
    }).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
    }

    log(f"  Sending PDF to Docling S6: {pdf_url[:80]}...", "INFO")
    status, body, err = http_request(
        DOCLING_CONVERT_URL, data=payload, headers=headers,
        method="POST", timeout=DOCLING_TIMEOUT,
    )

    if err:
        return "", f"Docling error: {err}"
    if status != 200:
        body_str = body.decode("utf-8", errors="replace")[:200] if body else "empty"
        return "", f"Docling HTTP {status}: {body_str}"

    try:
        result = json.loads(body.decode("utf-8"))
        # Docling returns various formats; look for markdown or text
        text = result.get("markdown", "") or result.get("text", "") or result.get("content", "")
        if not text and isinstance(result, dict):
            # Try to concatenate all text-like fields
            for key in ["pages", "sections", "chunks"]:
                if key in result and isinstance(result[key], list):
                    parts = []
                    for item in result[key]:
                        if isinstance(item, str):
                            parts.append(item)
                        elif isinstance(item, dict):
                            parts.append(
                                item.get("text", "") or item.get("content", "") or item.get("markdown", "")
                            )
                    text = "\n\n".join(p for p in parts if p)
                    break
        return text, None
    except Exception as e:
        return "", f"Docling parse error: {e}"


# =============================================================================
# CHUNKING
# =============================================================================

def chunk_text(text, title="", max_size=MAX_CHUNK_SIZE, overlap=OVERLAP_SIZE):
    """
    Chunk a long text into manageable pieces.
    Tries to split on section headers first, then paragraphs, then by size.
    Returns list of (chunk_text, section_label).
    """
    if not text or len(text) < MIN_CHUNK_SIZE:
        return [(text, "")] if text else []

    # If text fits in one chunk, return as-is
    if len(text) <= max_size:
        return [(text, "")]

    # Try to split on section headers (## or numbered sections like I., II., III.)
    section_pattern = re.compile(
        r'\n(?=(?:#{1,3}\s|[IVX]+\.\s|\d+\.\s|\d+\.\d+\s|[A-Z][a-z]+ \d+\s*[:\-]))',
    )
    sections = section_pattern.split(text)

    chunks = []
    current_chunk = ""
    current_section = ""

    for section in sections:
        section = section.strip()
        if not section:
            continue

        # Extract section header
        header_match = re.match(r'^(#{1,3}\s*.*?|[IVX]+\.\s*.*?|\d+\.\d*\s*.*?)[\n\r]', section)
        section_label = header_match.group(1).strip()[:100] if header_match else ""

        if len(current_chunk) + len(section) <= max_size:
            current_chunk += ("\n\n" if current_chunk else "") + section
            if section_label:
                current_section = section_label
        else:
            # Save current chunk
            if current_chunk and len(current_chunk) >= MIN_CHUNK_SIZE:
                chunks.append((current_chunk, current_section))

            # If section itself is too long, split by paragraphs
            if len(section) > max_size:
                paragraphs = section.split("\n\n")
                current_chunk = ""
                current_section = section_label

                for para in paragraphs:
                    para = para.strip()
                    if not para:
                        continue

                    if len(current_chunk) + len(para) <= max_size:
                        current_chunk += ("\n\n" if current_chunk else "") + para
                    else:
                        if current_chunk and len(current_chunk) >= MIN_CHUNK_SIZE:
                            chunks.append((current_chunk, current_section))
                        # If a single paragraph is too long, hard-split
                        if len(para) > max_size:
                            for i in range(0, len(para), max_size - overlap):
                                sub = para[i:i + max_size]
                                if len(sub) >= MIN_CHUNK_SIZE:
                                    chunks.append((sub, current_section))
                            current_chunk = ""
                        else:
                            current_chunk = para
            else:
                current_chunk = section
                current_section = section_label

    # Don't forget the last chunk
    if current_chunk and len(current_chunk) >= MIN_CHUNK_SIZE:
        chunks.append((current_chunk, current_section))

    # If chunking failed (e.g., no section headers), fall back to simple splitting
    if not chunks and text:
        for i in range(0, len(text), max_size - overlap):
            sub = text[i:i + max_size]
            if len(sub) >= MIN_CHUNK_SIZE:
                chunks.append((sub, ""))

    return chunks


# =============================================================================
# STORAGE: SUPABASE
# =============================================================================

def supabase_upsert(doc_id, chunk_text_content, pub_item, metadata_dict):
    """
    Upsert an AMF publication chunk to Supabase sector_documents.
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        return False, "SUPABASE_API_KEY not set"

    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}"

    row = {
        "id": doc_id,
        "sector": "finance",
        "dataset_name": "amf-publications",
        "pipeline": "standard",
        "question": pub_item["title"][:500],
        "answer": (
            f"Publication AMF: {pub_item['title'][:200]}. "
            f"Type: {metadata_dict.get('doc_type', 'publication')}. "
            f"Date: {pub_item.get('pub_date', '')}. "
            f"Reference: {metadata_dict.get('reference', '')}."
        )[:5000],
        "context": chunk_text_content[:30000],
        "metadata": json.dumps(metadata_dict, ensure_ascii=False),
        "tenant_id": "finance",
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
        return True, None

    body_str = ""
    try:
        body_str = body.decode("utf-8")[:200]
    except Exception:
        pass
    return False, f"HTTP {status}: {err or ''} {body_str}"


def supabase_register(doc_id, pub_item, chunk_text_content, metadata_dict):
    """Register in document_registry for tracking (best-effort)."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return

    url = f"{SUPABASE_URL}/rest/v1/document_registry"
    content_hash = hashlib.md5(chunk_text_content[:5000].encode()).hexdigest()

    row = {
        "sector": "finance",
        "source_type": "api",
        "source_url": pub_item["link"][:1000],
        "title": pub_item["title"][:500],
        "char_count": len(chunk_text_content),
        "language": "fr",
        "quality_score": 0.85,
        "processing_status": "ingested",
        "content_hash": content_hash,
        "discovered_at": datetime.now(timezone.utc).isoformat(),
        "metadata": json.dumps({
            "source": "amf",
            "doc_type": metadata_dict.get("doc_type", ""),
            "reference": metadata_dict.get("reference", ""),
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
        pass


# =============================================================================
# STORAGE: PINECONE
# =============================================================================

def pinecone_upsert(doc_id, chunk_text_content, metadata_dict):
    """
    Upsert a record to Pinecone E5 integrated embedding index.
    """
    if not PINECONE_API_KEY:
        return False, "PINECONE_API_KEY not set"

    url = f"{PINECONE_HOST}/records/namespaces/{PINECONE_NAMESPACE}/upsert"

    record = {
        "_id": doc_id,
        "text": chunk_text_content[:8000],
        "sector": "finance",
        "source": "amf",
        "doc_type": metadata_dict.get("doc_type", ""),
        "reference": metadata_dict.get("reference", "")[:200],
        "date": metadata_dict.get("date", ""),
        "title": metadata_dict.get("title", "")[:200],
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
            return True, None
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
        "total_chunks": 0,
        "total_skipped": 0,
        "total_errors": 0,
        "total_duplicates": 0,
        "total_pdfs_processed": 0,
        "total_cycles": 0,
        "supabase_ok": 0,
        "pinecone_ok": 0,
        "seen_urls": [],
        "by_doc_type": {},
        "by_feed": {},
        "last_cycle": None,
    }


def save_state(state):
    """Save ingestion state to file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    # Keep seen_urls manageable
    if len(state.get("seen_urls", [])) > 5000:
        state["seen_urls"] = state["seen_urls"][-5000:]
    tmp = str(STATE_FILE) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False, default=str)
    os.replace(tmp, str(STATE_FILE))


def print_status(state):
    """Print ingestion status."""
    print(f"\n{'=' * 60}", flush=True)
    print(f"  AMF INGESTION -- STATUS", flush=True)
    print(f"{'=' * 60}", flush=True)
    print(f"  Total publications: {state['total_ingested']}", flush=True)
    print(f"  Total chunks:       {state['total_chunks']}", flush=True)
    print(f"  PDFs processed:     {state['total_pdfs_processed']}", flush=True)
    print(f"  Skipped:            {state['total_skipped']}", flush=True)
    print(f"  Duplicates:         {state['total_duplicates']}", flush=True)
    print(f"  Errors:             {state['total_errors']}", flush=True)
    print(f"  Total cycles:       {state['total_cycles']}", flush=True)
    print(f"  Supabase OK:        {state['supabase_ok']}", flush=True)
    print(f"  Pinecone OK:        {state['pinecone_ok']}", flush=True)
    print(f"  Seen URLs cached:   {len(state.get('seen_urls', []))}", flush=True)
    print(f"  Created:            {state.get('created', '?')}", flush=True)
    print(f"  Last updated:       {state.get('last_updated', '?')}", flush=True)

    if state.get("by_doc_type"):
        print(f"\n  By document type:", flush=True)
        sorted_types = sorted(state["by_doc_type"].items(), key=lambda x: x[1], reverse=True)
        for dtype, count in sorted_types:
            print(f"    {dtype:25s}: {count:4d}", flush=True)

    if state.get("by_feed"):
        print(f"\n  By feed:", flush=True)
        for feed, count in state["by_feed"].items():
            print(f"    {feed:25s}: {count:4d}", flush=True)

    if state.get("last_cycle"):
        lc = state["last_cycle"]
        print(f"\n  Last cycle:", flush=True)
        print(f"    Time:       {lc.get('started', '?')}", flush=True)
        print(f"    Feed items: {lc.get('feed_items', 0)}", flush=True)
        print(f"    Ingested:   {lc.get('ingested', 0)}", flush=True)
        print(f"    Chunks:     {lc.get('chunks', 0)}", flush=True)
        print(f"    Skipped:    {lc.get('skipped', 0)}", flush=True)
        print(f"    Errors:     {lc.get('errors', 0)}", flush=True)
        print(f"    Duration:   {lc.get('elapsed_s', 0):.1f}s", flush=True)

    print(f"{'=' * 60}\n", flush=True)


# =============================================================================
# INGESTION PIPELINE
# =============================================================================

def build_chunk_metadata(pub_item, chunk_idx, total_chunks, section_label, doc_type, reference, has_pdf):
    """Build rich metadata for a single chunk."""
    return {
        "source": "amf",
        "source_type": "rss",
        "reference": reference,
        "title": pub_item["title"][:500],
        "section": section_label[:200],
        "date": pub_item.get("pub_date", ""),
        "doc_type": doc_type,
        "categories": pub_item.get("categories", [])[:10],
        "url": pub_item["link"][:500],
        "chunk_index": chunk_idx,
        "total_chunks": total_chunks,
        "has_pdf": has_pdf,
        "full_reference": (
            f"AMF {reference} -- {pub_item['title'][:100]}"
            f"{', ' + section_label if section_label else ''}"
        ),
        "has_entities": False,
        "entity_count": 0,
        "enriched": "false",
        "phase": "ingested",
        "ingestion_source": "ingest-amf-v1",
    }


def ingest_one_publication(pub_item, feed_name, state, dry_run=False):
    """
    Process a single AMF publication through the full pipeline.
    Returns (status, chunks_created).
    """
    title = pub_item["title"]
    link = pub_item["link"]
    pub_date = pub_item.get("pub_date", "")
    categories = pub_item.get("categories", [])

    # Check if already seen
    if link in state.get("seen_urls", []):
        return "duplicate", 0

    # Classify document type
    doc_type = classify_doc_type(title, link, categories)
    reference = extract_reference(title, link)

    if dry_run:
        log(f"  [DRY] {doc_type:15s} | {pub_date} | {title[:60]}", "INFO")
        return "dry_run", 0

    log(f"  Processing: [{doc_type}] {title[:60]}...", "INFO")

    # Fetch the publication page
    page_text, pdf_urls, page_err = fetch_page_content(link)
    if page_err:
        log(f"  Page fetch error: {page_err}", "WARN")

    # Try to process PDFs via Docling first (richer content)
    full_text = ""
    has_pdf = False

    if pdf_urls:
        # Take the first PDF (usually the main document)
        # Filter for likely main document PDFs (not thumbnails)
        main_pdfs = [u for u in pdf_urls if not any(
            x in u.lower() for x in ["thumbnail", "vignette", "icon", "logo"]
        )]

        if main_pdfs:
            pdf_url = main_pdfs[0]
            log(f"  Found PDF: {pdf_url[:80]}...", "INFO")

            # Check PDF size first (HEAD request)
            try:
                head_req = urllib.request.Request(pdf_url, method="HEAD")
                head_req.add_header("User-Agent", "NomosRAG/1.0")
                head_resp = urllib.request.urlopen(head_req, timeout=10, context=_ssl_ctx)
                content_length = int(head_resp.headers.get("Content-Length", 0))
                if content_length > 50 * 1024 * 1024:  # > 50MB
                    log(f"  PDF too large ({content_length / 1024 / 1024:.0f}MB), skipping Docling", "WARN")
                else:
                    pdf_text, pdf_err = process_pdf_via_docling(pdf_url)
                    if pdf_err:
                        log(f"  Docling error: {pdf_err}", "WARN")
                    elif pdf_text and len(pdf_text) > MIN_CHUNK_SIZE:
                        full_text = pdf_text
                        has_pdf = True
                        state["total_pdfs_processed"] = state.get("total_pdfs_processed", 0) + 1
                        log(f"  Docling extracted {len(pdf_text)} chars from PDF", "OK")
            except Exception as e:
                log(f"  PDF HEAD/Docling error: {e}", "WARN")

    # Fall back to page text if no PDF content
    if not full_text and page_text:
        full_text = page_text

    # Fallback: if both Docling and HTML failed, build content from RSS metadata
    # AMF publications are too valuable to skip entirely
    if not full_text or len(full_text) < MIN_CHUNK_SIZE:
        description = pub_item.get("description", "")
        categories_str = ", ".join(categories) if categories else ""
        fallback_parts = [
            f"Publication AMF: {title}",
            f"Type: {doc_type}",
            f"Date: {pub_date}",
        ]
        if reference:
            fallback_parts.append(f"Reference: {reference}")
        if categories_str:
            fallback_parts.append(f"Domaines: {categories_str}")
        if description:
            # Clean up the RSS description (remove repeated category tags)
            clean_desc = re.sub(r'\s{2,}', ' | ', description).strip()
            fallback_parts.append(f"Description: {clean_desc}")
        if pdf_urls:
            fallback_parts.append(f"Document PDF disponible: {pdf_urls[0][:200]}")
        fallback_parts.append(f"Source: {link}")

        full_text = "\n".join(fallback_parts)
        if len(full_text) < 50:
            log(f"  Insufficient content even with fallback ({len(full_text)} chars)", "SKIP")
            return "too_short", 0
        log(f"  Using RSS metadata fallback ({len(full_text)} chars)", "INFO")

    # Chunk the text
    chunks = chunk_text(full_text, title=title)
    if not chunks:
        return "no_chunks", 0

    log(f"  Chunking: {len(full_text)} chars -> {len(chunks)} chunks", "INFO")

    # Store each chunk
    chunks_stored = 0
    for idx, (chunk_content, section_label) in enumerate(chunks):
        if _shutdown_requested:
            break

        # Build document ID (deterministic)
        chunk_id_str = f"amf:{link}:{idx}"
        doc_id = f"amf-{hashlib.md5(chunk_id_str.encode()).hexdigest()[:20]}-{idx}"

        # Prepend title and reference for better embedding context
        enriched_chunk = (
            f"AMF — {title}\n"
            f"Type: {doc_type} | Date: {pub_date} | Reference: {reference}\n"
            f"{f'Section: {section_label}' if section_label else ''}\n\n"
            f"{chunk_content}"
        ).strip()

        metadata = build_chunk_metadata(
            pub_item, idx, len(chunks), section_label, doc_type, reference, has_pdf
        )

        # Supabase upsert
        supa_ok, supa_err = supabase_upsert(doc_id, enriched_chunk, pub_item, metadata)
        if supa_ok:
            state["supabase_ok"] = state.get("supabase_ok", 0) + 1
        else:
            log(f"  Supabase chunk {idx} error: {supa_err}", "WARN")

        # Pinecone upsert
        pine_ok, pine_err = pinecone_upsert(doc_id, enriched_chunk, metadata)
        if pine_ok:
            state["pinecone_ok"] = state.get("pinecone_ok", 0) + 1
        else:
            log(f"  Pinecone chunk {idx} error: {pine_err}", "WARN")

        if supa_ok or pine_ok:
            chunks_stored += 1

        # Small delay between chunk upserts
        time.sleep(0.1)

    # Register first chunk in document_registry (best-effort)
    if chunks:
        supabase_register(
            f"amf-{hashlib.md5(f'amf:{link}:0'.encode()).hexdigest()[:20]}-0",
            pub_item, chunks[0][0], build_chunk_metadata(
                pub_item, 0, len(chunks), "", doc_type, reference, has_pdf
            )
        )

    # Track seen URL
    if "seen_urls" not in state:
        state["seen_urls"] = []
    state["seen_urls"].append(link)

    # Track doc type
    state.setdefault("by_doc_type", {})[doc_type] = state.get("by_doc_type", {}).get(doc_type, 0) + 1

    # Track feed
    state.setdefault("by_feed", {})[feed_name] = state.get("by_feed", {}).get(feed_name, 0) + 1

    if chunks_stored > 0:
        log(f"  Stored {chunks_stored}/{len(chunks)} chunks for: {title[:50]}", "OK")
        return "ingested", chunks_stored
    else:
        return "error", 0


def run_cycle(batch_size, feed_name, state, dry_run=False):
    """
    Run one ingestion cycle:
    1. Fetch AMF RSS feed(s)
    2. Process each publication
    3. Update state
    """
    global _shutdown_requested

    cycle_start = time.time()
    cycle_num = state["total_cycles"] + 1

    print(f"\n{'=' * 60}", flush=True)
    print(f"  AMF INGESTION CYCLE #{cycle_num}", flush=True)
    print(f"  Batch: {batch_size} | Feed: {feed_name} | Dry: {dry_run}", flush=True)
    print(f"  Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC", flush=True)
    print(f"{'=' * 60}", flush=True)

    # Determine which feeds to fetch
    if feed_name == "all":
        feeds_to_fetch = list(AMF_FEEDS.items())
    elif feed_name in AMF_FEEDS:
        feeds_to_fetch = [(feed_name, AMF_FEEDS[feed_name])]
    else:
        log(f"Unknown feed: {feed_name}", "ERROR")
        return state

    # Fetch all RSS items
    all_items = []
    for fname, furl in feeds_to_fetch:
        log(f"Fetching AMF feed: {fname}...", "INFO")
        items, err = fetch_rss_feed(furl)
        if err:
            log(f"Feed {fname} error: {err}", "WARN")
            continue
        log(f"Feed {fname}: {len(items)} items", "OK")

        # Tag each item with its feed source
        for item in items:
            item["_feed"] = fname

        all_items.extend(items)
        time.sleep(RATE_LIMIT_DELAY)

    if not all_items:
        log("No RSS items fetched", "SKIP")
        state["total_cycles"] = cycle_num
        state["last_cycle"] = {
            "started": datetime.now(timezone.utc).isoformat(),
            "feed_items": 0, "ingested": 0, "chunks": 0,
            "skipped": 0, "errors": 0,
            "elapsed_s": round(time.time() - cycle_start, 1),
        }
        save_state(state)
        return state

    # Deduplicate by URL (feeds may overlap)
    seen_links = set()
    unique_items = []
    for item in all_items:
        if item["link"] not in seen_links:
            seen_links.add(item["link"])
            unique_items.append(item)

    # Limit to batch size
    items_to_process = unique_items[:batch_size]
    log(f"Processing {len(items_to_process)} unique publications "
        f"(from {len(all_items)} total feed items)...", "INFO")

    # Process each publication
    cycle_ingested = 0
    cycle_chunks = 0
    cycle_skipped = 0
    cycle_errors = 0
    cycle_duplicates = 0

    for i, item in enumerate(items_to_process):
        if _shutdown_requested:
            log("Shutdown requested -- stopping batch", "WARN")
            break

        try:
            status_str, chunks_created = ingest_one_publication(
                item, item.get("_feed", "unknown"), state, dry_run=dry_run
            )
        except Exception as e:
            log(f"  EXCEPTION: {e}", "ERROR")
            traceback.print_exc()
            status_str = "error"
            chunks_created = 0
            cycle_errors += 1
            continue

        if status_str == "ingested" or status_str == "dry_run":
            cycle_ingested += 1
            cycle_chunks += chunks_created
        elif status_str == "duplicate":
            cycle_duplicates += 1
        elif status_str in ("too_short", "no_chunks"):
            cycle_skipped += 1
        else:
            cycle_errors += 1

        # Rate limiting between publications (page fetches + Docling)
        if not dry_run:
            time.sleep(RATE_LIMIT_DELAY)

    # Update state
    if not dry_run:
        state["total_ingested"] += cycle_ingested
        state["total_chunks"] += cycle_chunks
        state["total_skipped"] += cycle_skipped
        state["total_errors"] += cycle_errors
        state["total_duplicates"] += cycle_duplicates
    state["total_cycles"] = cycle_num

    elapsed = time.time() - cycle_start
    state["last_cycle"] = {
        "started": datetime.now(timezone.utc).isoformat(),
        "feed_items": len(all_items),
        "unique_items": len(unique_items),
        "ingested": cycle_ingested,
        "chunks": cycle_chunks,
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
    print(f"  Feed items:   {len(all_items)} ({len(unique_items)} unique)", flush=True)
    print(f"  Ingested:     {cycle_ingested} publications", flush=True)
    print(f"  Chunks:       {cycle_chunks} stored", flush=True)
    print(f"  Skipped:      {cycle_skipped} (too short or no content)", flush=True)
    print(f"  Duplicates:   {cycle_duplicates}", flush=True)
    print(f"  Errors:       {cycle_errors}", flush=True)
    if not dry_run:
        print(f"  TOTALS:       {state['total_ingested']} pubs, "
              f"{state['total_chunks']} chunks, "
              f"{state['total_errors']} errors", flush=True)
    print(f"{'=' * 60}", flush=True)

    return state


# =============================================================================
# MAIN / CLI
# =============================================================================

def main():
    global _shutdown_requested
    parser = argparse.ArgumentParser(
        description="AMF Ingestion -- Financial Regulatory Publications for Finance Sector"
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
        help=f"Publications per cycle (default: {DEFAULT_BATCH_SIZE})"
    )
    parser.add_argument(
        "--feed", choices=list(AMF_FEEDS.keys()) + ["all"], default="publications",
        help="Which AMF RSS feed to use (default: publications)"
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
    print(f"  AMF INGESTION V1.0 -- Financial Regulatory Publications", flush=True)
    print(f"{'=' * 60}", flush=True)
    print(f"  Mode:       {'Daemon' if args.daemon else 'One-shot'}", flush=True)
    print(f"  Interval:   {args.interval}s ({args.interval / 60:.0f}min)", flush=True)
    print(f"  Batch:      {args.batch_size} pubs/cycle", flush=True)
    print(f"  Feed:       {args.feed}", flush=True)
    print(f"  Dry run:    {args.dry_run}", flush=True)
    print(f"  Supabase:   {SUPABASE_URL}", flush=True)
    print(f"  Pinecone:   {PINECONE_HOST[:60]}...", flush=True)
    print(f"  Docling:    {DOCLING_BASE}", flush=True)
    print(f"  State:      {STATE_FILE}", flush=True)
    print(f"  Log:        {LOG_FILE}", flush=True)
    print(f"  PID:        {os.getpid()}", flush=True)
    print(f"  Started:    {datetime.now(timezone.utc).isoformat()}", flush=True)
    print(f"{'=' * 60}\n", flush=True)

    state = load_state()

    if args.daemon:
        log(f"Starting AMF daemon -- {args.interval}s cycles, "
            f"batch={args.batch_size}, feed={args.feed}", "INFO")

        consecutive_empty = 0
        while not _shutdown_requested:
            try:
                state = run_cycle(args.batch_size, args.feed, state, dry_run=args.dry_run)
            except Exception as e:
                log(f"Cycle error: {e}", "ERROR")
                traceback.print_exc()

            if _shutdown_requested:
                break

            # Check if cycle was empty
            lc = state.get("last_cycle", {})
            if lc.get("ingested", 0) == 0:
                consecutive_empty += 1
            else:
                consecutive_empty = 0

            # Adaptive backoff after 3 empty cycles
            if consecutive_empty >= 3:
                wait_time = min(args.interval * 3, 3600)
                log(f"No new publications for {consecutive_empty} cycles -- "
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

        log("AMF daemon stopped gracefully", "OK")
    else:
        # One-shot mode
        state = run_cycle(args.batch_size, args.feed, state, dry_run=args.dry_run)

    # Clean up PID
    try:
        PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass

    log("AMF Ingestion finished", "OK")


if __name__ == "__main__":
    main()
