#!/usr/bin/env python3
"""
Eval Runner V2 — Intelligent Document-Driven RAG Evaluation System
===================================================================
An end-to-end evaluation pipeline that:
  1. Discovers real expert documents (PDFs) from authoritative sources per sector
  2. Processes them via Docling (HF Space PDF extraction)
  3. Generates expert-grade test questions from extracted content (Groq LLM)
  4. Tests all RAG pipelines with those questions
  5. Scores answers against source documents
  6. Continuously improves the eval dataset

Unlike basic test runners, this system builds its own ground truth from real
domain documents — the gold standard for RAG evaluation.

Usage:
  source .env.local
  python3 eval/eval-runner-v2.py                          # Full cycle
  python3 eval/eval-runner-v2.py --discover               # Only discover new docs
  python3 eval/eval-runner-v2.py --process                # Only process via Docling
  python3 eval/eval-runner-v2.py --generate               # Only generate questions
  python3 eval/eval-runner-v2.py --test                   # Only test pipelines
  python3 eval/eval-runner-v2.py --sector finance         # Single sector
  python3 eval/eval-runner-v2.py --loop 3600              # Continuous (every hour)
  python3 eval/eval-runner-v2.py --report                 # Show latest summary
"""

# ─── IPv4 monkey-patch (required for HF Spaces) ──────────────────────────
import socket
from socket import AF_INET

_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_only(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, AF_INET, type, proto, flags)


socket.getaddrinfo = _ipv4_only

# ─── Stdlib imports ──────────────────────────────────────────────────────
import argparse
import hashlib
import json
import os
import re
import ssl
import sys
import time
import traceback
import urllib.error
import urllib.request
from datetime import datetime, timezone
from threading import Lock

# ─── Paths ───────────────────────────────────────────────────────────────
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(REPO_ROOT, "data", "eval")

DOC_REGISTRY_FILE = os.path.join(DATA_DIR, "doc-registry.json")
EXPERT_QUESTIONS_FILE = os.path.join(DATA_DIR, "expert-questions.json")
EVAL_SUMMARY_FILE = os.path.join(DATA_DIR, "eval-summary.json")

for d in [DATA_DIR]:
    os.makedirs(d, exist_ok=True)

# ─── SSL context (disable verification for HF Spaces) ───────────────────
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE

# ─── Groq API key rotation ──────────────────────────────────────────────
_GROQ_KEYS = []
for _k, _v in sorted(os.environ.items()):
    if _k.startswith("GROQ_API_KEY") and _v:
        _GROQ_KEYS.append(_v)
if not _GROQ_KEYS:
    _gk = os.environ.get("GROQ_API_KEY", "")
    if _gk:
        _GROQ_KEYS.append(_gk)

_groq_lock = Lock()
_groq_idx = 0
_last_groq_call = 0.0


def _next_groq_key():
    global _groq_idx
    with _groq_lock:
        if not _GROQ_KEYS:
            return ""
        key = _GROQ_KEYS[_groq_idx % len(_GROQ_KEYS)]
        _groq_idx += 1
        return key


def _rate_limit_groq():
    """Enforce max 1 Groq call per second."""
    global _last_groq_call
    with _groq_lock:
        now = time.time()
        elapsed = now - _last_groq_call
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        _last_groq_call = time.time()


# ─── Infrastructure ─────────────────────────────────────────────────────
SPACES = {
    "S1": "https://lbjlincoln-nomos-rag-engine.hf.space",
    "S2": "https://lbjlincoln26-nomos-rag-engine-2.hf.space",
    "S3": "https://lbjlincoln-nomos-rag-engine-3.hf.space",
    "S4": "https://lbjlincoln26-nomos-rag-engine-4.hf.space",
    "S5": "https://lbjlincoln-nomos-rag-engine-5.hf.space",
    "S9": "https://lbjlincoln-nomos-rag-engine-9.hf.space",
}

WEBHOOK_PATHS = {
    "standard": "/webhook/rag-multi-index-v3",
    "graph": "/webhook/ff622742-6d71-4e91-af71-b5c666088717",
    "quantitative": "/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
    "orchestrator": "/webhook/orchestrator-v2",
}

# Which spaces host which pipelines
PIPELINE_SPACES = {
    "standard": ["S1", "S2", "S3", "S4", "S5", "S9"],
    "graph": ["S1"],
    "quantitative": ["S9"],
    "orchestrator": ["S1"],
}

DOCLING_URL = "https://lbjlincoln-nomos-docling-api.hf.space/convert-url"
DOCLING_HEALTH = "https://lbjlincoln-nomos-docling-api.hf.space/health"

SECTORS = ["finance", "btp", "juridique", "industrie"]

# ─── Curated seed documents per sector ───────────────────────────────────
# Each entry: url, title, type (pdf), sector
# Start with 3-5 known-good, freely accessible PDFs per sector
SEED_DOCUMENTS = {
    "finance": [
        {
            "url": "https://www.ecb.europa.eu/pub/pdf/annrep/ecb.annualreport2023~ea2ca6a91e.en.pdf",
            "title": "ECB Annual Report 2023",
            "type": "pdf",
        },
        {
            "url": "https://www.banque-france.fr/system/files/2025-04/Methodologie_situation_entreprises.pdf",
            "title": "Situation financiere des entreprises — Banque de France",
            "type": "pdf",
        },
        {
            "url": "https://totalenergies.com/sites/default/files/atoms/files/rapport-financier-annuel-2018-total-capital-international.pdf",
            "title": "Rapport financier annuel 2018 — TotalEnergies",
            "type": "pdf",
        },
        {
            "url": "https://www.amf-france.org/sites/institutionnel/files/private/2023-07/Rapport%20annuel%20AMF%202022.pdf",
            "title": "Rapport annuel AMF 2022",
            "type": "pdf",
        },
        {
            "url": "https://www.bis.org/publ/bcbs239.pdf",
            "title": "BIS BCBS 239 — Principles for risk data aggregation",
            "type": "pdf",
        },
    ],
    "btp": [
        {
            "url": "https://www.ecologie.gouv.fr/sites/default/files/documents/guide_re2020_version_janvier_2024.pdf",
            "title": "Guide RE 2020 — Ministere de la Transition ecologique",
            "type": "pdf",
        },
        {
            "url": "https://boutique.cstb.fr/getattachment/9ba6ea42-de49-44a5-b56c-b5e567cc035b/Liste-DTU-Fevrier-2026.pdf",
            "title": "Liste des DTU en vigueur — CSTB",
            "type": "pdf",
        },
        {
            "url": "https://www.ademe.fr/wp-content/uploads/2022/01/guide-pratique-isoler-sa-maison.pdf",
            "title": "Guide pratique — Isoler sa maison (ADEME)",
            "type": "pdf",
        },
        {
            "url": "https://www.qualibat.com/wp-content/uploads/2023/01/Guide-Qualibat-RGE-2023.pdf",
            "title": "Guide Qualibat RGE 2023",
            "type": "pdf",
        },
    ],
    "juridique": [
        {
            "url": "https://www.medef.com/uploads/media/default/0020/01/14977-14970-medef-guide-rebond-web.pdf",
            "title": "Prevention des difficultes des entreprises — MEDEF",
            "type": "pdf",
        },
        {
            "url": "https://www.cnil.fr/sites/cnil/files/2023-01/guide_pratique_rgpd_-_securite_des_donnees_personnelles_-_nouvelle_edition_2023.pdf",
            "title": "Guide RGPD securite des donnees — CNIL 2023",
            "type": "pdf",
        },
        {
            "url": "https://www.bts-g-pme.com/cours/d1-grcf/c4-contrat-commerciaux/c4-a-contrat-commerciaux.pdf",
            "title": "Contrats commerciaux — BTS G-PME",
            "type": "pdf",
        },
        {
            "url": "https://www.conseil-constitutionnel.fr/sites/default/files/as/root/bank_mm/pdf/Conseil/Constitutions/constitution_francaise_texte_integral_20080723.pdf",
            "title": "Constitution francaise — texte integral",
            "type": "pdf",
        },
    ],
    "industrie": [
        {
            "url": "https://www.strategie-plan.gouv.fr/files/files/Publications/2020/politiques%20industrielles/fs-2020-rapport-politique_industrielle-novembre.pdf",
            "title": "Rapport politiques industrielles — France Strategie",
            "type": "pdf",
        },
        {
            "url": "https://www.inrs.fr/media.html?refINRS=ED%206481",
            "title": "INRS ED 6481 — Fiche securite",
            "type": "pdf",
        },
        {
            "url": "https://www.iso.org/files/live/sites/isoorg/files/store/en/PUB100080.pdf",
            "title": "ISO 9001 — Quality management principles",
            "type": "pdf",
        },
    ],
}

# =========================================================================
#  UTILITIES
# =========================================================================


def _ts():
    """ISO timestamp."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ts_file():
    """Timestamp for filenames."""
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _url_hash(url):
    """Short stable hash for a URL."""
    return hashlib.sha256(url.encode()).hexdigest()[:12]


def _http_request(url, method="GET", data=None, headers=None, timeout=60):
    """
    Generic HTTP request using stdlib only.
    Returns (status_code, response_body_str, error_str_or_None).
    """
    hdrs = headers or {}
    if data is not None and isinstance(data, (dict, list)):
        data = json.dumps(data).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    elif data is not None and isinstance(data, str):
        data = data.encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, body, None
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        return e.code, body, f"HTTP {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return 0, "", f"URLError: {e.reason}"
    except Exception as e:
        return 0, "", f"{type(e).__name__}: {str(e)[:300]}"


def _load_json(path, default=None):
    """Load JSON file, return default if missing/corrupt."""
    if default is None:
        default = {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _save_json(path, data):
    """Atomically save JSON file."""
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    os.replace(tmp, path)


def _log(msg, level="INFO"):
    """Print with timestamp and level."""
    ts = datetime.now().strftime("%H:%M:%S")
    prefix = {"INFO": "+", "WARN": "!", "ERROR": "X", "OK": "v", "SKIP": "-"}.get(
        level, " "
    )
    print(f"[{ts}] [{prefix}] {msg}", flush=True)


# =========================================================================
#  PHASE 1 — DOCUMENT DISCOVERY
# =========================================================================


class DocumentDiscovery:
    """Manages the document registry and discovers new documents."""

    def __init__(self, sectors=None):
        self.sectors = sectors or SECTORS
        self.registry = _load_json(DOC_REGISTRY_FILE, default={})
        # Ensure all sectors exist
        for s in SECTORS:
            if s not in self.registry:
                self.registry[s] = []

    def save(self):
        _save_json(DOC_REGISTRY_FILE, self.registry)

    def _doc_exists(self, sector, url):
        """Check if a URL is already in the registry."""
        return any(d["url"] == url for d in self.registry.get(sector, []))

    def seed(self):
        """Add seed documents to the registry (idempotent)."""
        added = 0
        for sector in self.sectors:
            seeds = SEED_DOCUMENTS.get(sector, [])
            for doc in seeds:
                if not self._doc_exists(sector, doc["url"]):
                    entry = {
                        "url": doc["url"],
                        "title": doc.get("title", "Unknown"),
                        "type": doc.get("type", "pdf"),
                        "status": "discovered",
                        "discovered_at": _ts(),
                        "hash": _url_hash(doc["url"]),
                        "chunks": 0,
                        "questions_generated": 0,
                        "extract_length": 0,
                        "error": None,
                    }
                    self.registry[sector].append(entry)
                    added += 1
                    _log(f"[{sector}] Registered: {doc.get('title', doc['url'][:60])}")
        self.save()
        return added

    def discover(self):
        """
        Main discovery: seeds + any additional URL sources.
        Extensible: add web search, sitemap parsing, etc.
        """
        _log("=== Phase 1: Document Discovery ===")
        added = self.seed()
        # Future: add web-search-based discovery here
        # e.g., search for "filetype:pdf site:ecb.europa.eu annual report"
        total = sum(len(docs) for docs in self.registry.values())
        _log(f"Discovery complete: {added} new, {total} total documents")
        return added

    def get_unprocessed(self, sector=None):
        """Get documents that haven't been processed yet."""
        results = []
        sectors = [sector] if sector else self.sectors
        for s in sectors:
            for doc in self.registry.get(s, []):
                if doc.get("status") in ("discovered", "failed"):
                    results.append((s, doc))
        return results

    def get_processed(self, sector=None):
        """Get documents that have been successfully processed."""
        results = []
        sectors = [sector] if sector else self.sectors
        for s in sectors:
            for doc in self.registry.get(s, []):
                if doc.get("status") == "processed":
                    results.append((s, doc))
        return results

    def get_without_questions(self, sector=None):
        """Get processed documents that don't have questions generated yet."""
        results = []
        sectors = [sector] if sector else self.sectors
        for s in sectors:
            for doc in self.registry.get(s, []):
                if (
                    doc.get("status") == "processed"
                    and doc.get("questions_generated", 0) == 0
                ):
                    results.append((s, doc))
        return results

    def update_doc(self, sector, url, updates):
        """Update a document entry in the registry."""
        for doc in self.registry.get(sector, []):
            if doc["url"] == url:
                doc.update(updates)
                self.save()
                return True
        return False

    def stats(self):
        """Return registry stats."""
        stats = {}
        for sector in SECTORS:
            docs = self.registry.get(sector, [])
            stats[sector] = {
                "total": len(docs),
                "discovered": sum(1 for d in docs if d.get("status") == "discovered"),
                "processed": sum(1 for d in docs if d.get("status") == "processed"),
                "failed": sum(1 for d in docs if d.get("status") == "failed"),
                "with_questions": sum(
                    1 for d in docs if d.get("questions_generated", 0) > 0
                ),
            }
        return stats


# =========================================================================
#  PHASE 2 — DOCLING PROCESSING
# =========================================================================


class DoclingProcessor:
    """Sends documents to the Docling HF Space for PDF extraction."""

    def __init__(self, timeout=180, max_extract_chars=15000):
        self.timeout = timeout
        self.max_extract_chars = max_extract_chars
        self.extracts_dir = os.path.join(DATA_DIR, "extracts")
        os.makedirs(self.extracts_dir, exist_ok=True)

    def check_health(self):
        """Check if Docling Space is alive."""
        status, body, err = _http_request(DOCLING_HEALTH, timeout=15)
        if status == 200:
            _log("Docling Space: UP", "OK")
            return True
        _log(f"Docling Space: DOWN ({err or f'HTTP {status}'})", "ERROR")
        return False

    def process_document(self, sector, doc):
        """
        Send a document URL to Docling and extract content.
        Returns (extracted_text, num_chunks, error).
        """
        url = doc["url"]
        title = doc.get("title", url[:60])
        _log(f"[{sector}] Processing: {title}")

        payload = {"url": url}
        start = time.time()
        status, body, err = _http_request(
            DOCLING_URL, method="POST", data=payload, timeout=self.timeout
        )
        elapsed = time.time() - start

        if err or status != 200:
            error_msg = err or f"HTTP {status}"
            # Specific error handling
            if status == 504 or (err and "timeout" in err.lower()):
                error_msg = f"Timeout ({elapsed:.0f}s) — PDF too large or Space overloaded"
            elif status == 503:
                error_msg = f"503 — Space cold starting (waited {elapsed:.0f}s)"
            elif status == 413:
                error_msg = "413 — PDF too large for Docling"

            _log(f"[{sector}] FAILED: {title} — {error_msg}", "ERROR")
            return None, 0, error_msg

        # Parse response
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            _log(f"[{sector}] FAILED: {title} — Invalid JSON response", "ERROR")
            return None, 0, "Invalid JSON from Docling"

        # Extract text from various Docling response formats
        full_text = ""
        if isinstance(data, dict):
            # Try common Docling response fields
            full_text = (
                data.get("markdown", "")
                or data.get("full_text", "")
                or data.get("text", "")
                or data.get("content", "")
            )
            # If pages array, concatenate
            if not full_text and "pages" in data:
                pages = data["pages"]
                if isinstance(pages, list):
                    full_text = "\n\n".join(
                        p.get("text", "") or p.get("content", "")
                        for p in pages
                        if isinstance(p, dict)
                    )
            # If result wrapper
            if not full_text and "result" in data:
                result = data["result"]
                if isinstance(result, dict):
                    full_text = result.get("markdown", "") or result.get("text", "")
                elif isinstance(result, str):
                    full_text = result
        elif isinstance(data, str):
            full_text = data

        if not full_text or len(full_text.strip()) < 50:
            _log(
                f"[{sector}] FAILED: {title} — Extracted text too short ({len(full_text)} chars)",
                "ERROR",
            )
            return None, 0, f"Extraction too short: {len(full_text)} chars"

        # Truncate for question generation (keep manageable size)
        extract = full_text[: self.max_extract_chars]

        # Count approximate chunks (by paragraphs/sections)
        chunks = len(re.split(r"\n{2,}", extract.strip()))

        # Save extract to file for reference
        extract_path = os.path.join(
            self.extracts_dir, f"{sector}_{doc.get('hash', _url_hash(url))}.md"
        )
        with open(extract_path, "w") as f:
            f.write(f"# {title}\n")
            f.write(f"# Source: {url}\n")
            f.write(f"# Extracted: {_ts()}\n")
            f.write(f"# Length: {len(full_text)} chars, {chunks} chunks\n\n")
            f.write(full_text[:50000])  # Save up to 50K chars

        _log(
            f"[{sector}] OK: {title} — {len(full_text)} chars, {chunks} chunks, {elapsed:.1f}s",
            "OK",
        )
        return extract, chunks, None

    def process_all(self, discovery):
        """Process all unprocessed documents."""
        _log("=== Phase 2: Docling Processing ===")

        if not self.check_health():
            _log(
                "Docling Space is down — skipping processing. Try again later.", "WARN"
            )
            return 0

        unprocessed = discovery.get_unprocessed()
        if not unprocessed:
            _log("No unprocessed documents found", "SKIP")
            return 0

        _log(f"Processing {len(unprocessed)} documents...")
        processed = 0

        for sector, doc in unprocessed:
            extract, chunks, error = self.process_document(sector, doc)

            if error:
                discovery.update_doc(
                    sector,
                    doc["url"],
                    {
                        "status": "failed",
                        "error": error,
                        "last_attempt": _ts(),
                    },
                )
            else:
                discovery.update_doc(
                    sector,
                    doc["url"],
                    {
                        "status": "processed",
                        "chunks": chunks,
                        "extract_length": len(extract),
                        "processed_at": _ts(),
                        "error": None,
                    },
                )
                processed += 1

            # Be polite: wait between documents
            time.sleep(2)

        _log(
            f"Processing complete: {processed}/{len(unprocessed)} succeeded", "OK"
        )
        return processed


# =========================================================================
#  PHASE 3 — EXPERT QUESTION GENERATION
# =========================================================================


class QuestionGenerator:
    """Uses Groq LLM to generate expert evaluation questions from extracted content."""

    SYSTEM_PROMPT = """You are an expert question generator for RAG (Retrieval-Augmented Generation) evaluation.

Given a document extract from a specific sector, generate 2-3 expert-level questions that:
1. Test DEEP domain knowledge (not surface-level)
2. Require specific facts, numbers, dates, or technical terms from the source
3. Would distinguish an expert system from a generic chatbot
4. Cover different difficulty levels (medium and hard)

CRITICAL RULES:
- Questions MUST be answerable from the provided document extract
- Each expected answer MUST contain specific verifiable facts from the document
- Include 3-5 keywords that MUST appear in a correct answer
- If the document is in French, generate questions in French
- If the document is in English, generate questions in English

Output format (STRICT — one question per line, exactly this format):
Q: [question text] | A: [expected answer with specific facts] | K: [keyword1, keyword2, keyword3] | D: [medium|hard] | L: [fr|en]

Example:
Q: Quel est le taux directeur de la BCE en decembre 2023 et comment a-t-il evolue sur l'annee ? | A: Le taux directeur principal est de 4.50% en decembre 2023, apres 6 hausses consecutives depuis juillet 2022 pour lutter contre l'inflation. | K: 4.50, taux directeur, inflation, hausse | D: hard | L: fr"""

    def __init__(self, model="llama-3.3-70b-versatile"):
        self.model = model
        self.questions_db = _load_json(EXPERT_QUESTIONS_FILE, default={})
        # Ensure structure
        for s in SECTORS:
            if s not in self.questions_db:
                self.questions_db[s] = []

    def save(self):
        _save_json(EXPERT_QUESTIONS_FILE, self.questions_db)

    def _call_groq(self, system_prompt, user_prompt, max_tokens=2000):
        """Call Groq API with rate limiting and key rotation."""
        _rate_limit_groq()
        key = _next_groq_key()
        if not key:
            return None, "No Groq API keys configured"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.3,
        }

        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

        status, body, err = _http_request(
            "https://api.groq.com/openai/v1/chat/completions",
            method="POST",
            data=payload,
            headers=headers,
            timeout=60,
        )

        if err or status != 200:
            # Retry with different key on 429
            if status == 429:
                time.sleep(2)
                _rate_limit_groq()
                key2 = _next_groq_key()
                headers["Authorization"] = f"Bearer {key2}"
                status, body, err = _http_request(
                    "https://api.groq.com/openai/v1/chat/completions",
                    method="POST",
                    data=payload,
                    headers=headers,
                    timeout=60,
                )
                if err or status != 200:
                    return None, f"Groq retry failed: {err or f'HTTP {status}'}"
            else:
                return None, err or f"HTTP {status}: {body[:200]}"

        try:
            data = json.loads(body)
            content = data["choices"][0]["message"]["content"]
            return content, None
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            return None, f"Parse error: {e}"

    def _parse_questions(self, raw_text, sector, doc_hash, doc_title):
        """Parse LLM output into structured question objects."""
        questions = []
        lines = raw_text.strip().split("\n")

        for line in lines:
            line = line.strip()
            if not line.startswith("Q:"):
                continue

            # Parse: Q: ... | A: ... | K: ... | D: ... | L: ...
            parts = {}
            current_key = None
            current_val = []

            for segment in line.split("|"):
                segment = segment.strip()
                for prefix in ["Q:", "A:", "K:", "D:", "L:"]:
                    if segment.startswith(prefix):
                        if current_key:
                            parts[current_key] = " ".join(current_val).strip()
                        current_key = prefix.rstrip(":")
                        current_val = [segment[len(prefix) :].strip()]
                        break
                else:
                    if current_key:
                        current_val.append(segment)

            if current_key:
                parts[current_key] = " ".join(current_val).strip()

            if "Q" not in parts or "A" not in parts:
                continue

            # Parse keywords
            keywords = []
            if "K" in parts:
                keywords = [k.strip() for k in parts["K"].split(",") if k.strip()]

            difficulty = parts.get("D", "medium").lower()
            if difficulty not in ("easy", "medium", "hard"):
                difficulty = "medium"

            language = parts.get("L", "fr").lower()
            if language not in ("fr", "en"):
                language = "fr"

            q_id = f"auto-{sector[:3]}-{doc_hash}-{len(questions) + 1:02d}"
            question = {
                "id": q_id,
                "question": parts["Q"],
                "expected_answer": parts["A"],
                "keywords": keywords,
                "difficulty": difficulty,
                "language": language,
                "sector": sector,
                "source_doc": doc_title,
                "source_hash": doc_hash,
                "generated_at": _ts(),
                "category": "auto-generated",
            }
            questions.append(question)

        return questions

    def generate_for_document(self, sector, doc):
        """Generate expert questions from a processed document's extract."""
        doc_hash = doc.get("hash", _url_hash(doc["url"]))
        title = doc.get("title", "Unknown")
        _log(f"[{sector}] Generating questions: {title}")

        # Load the extract
        extract_path = os.path.join(self.extracts_dir, f"{sector}_{doc_hash}.md")
        if not os.path.exists(extract_path):
            _log(f"[{sector}] No extract found for {title}", "WARN")
            return 0

        with open(extract_path, "r") as f:
            extract = f.read()

        # Remove metadata header (lines starting with #)
        content_lines = []
        past_header = False
        for line in extract.split("\n"):
            if past_header:
                content_lines.append(line)
            elif not line.startswith("#"):
                past_header = True
                content_lines.append(line)
        content = "\n".join(content_lines).strip()

        if len(content) < 100:
            _log(f"[{sector}] Extract too short for question generation", "WARN")
            return 0

        # Truncate to fit context window (keep ~8K chars for the prompt)
        content = content[:8000]

        user_prompt = f"""Sector: {sector.upper()}
Document title: {title}

--- DOCUMENT EXTRACT ---
{content}
--- END ---

Generate 2-3 expert questions based on this document. Remember:
- Questions must be answerable from the extract above
- Include specific facts, numbers, or technical terms in the expected answer
- Use the document's language (French if French document, English if English)"""

        raw_response, error = self._call_groq(self.SYSTEM_PROMPT, user_prompt)
        if error:
            _log(f"[{sector}] Groq error: {error}", "ERROR")
            return 0

        questions = self._parse_questions(raw_response, sector, doc_hash, title)
        if not questions:
            _log(f"[{sector}] No valid questions parsed from LLM response", "WARN")
            return 0

        # Check for duplicates (by question text similarity)
        existing_qs = {q["question"].lower()[:80] for q in self.questions_db.get(sector, [])}
        new_questions = []
        for q in questions:
            if q["question"].lower()[:80] not in existing_qs:
                new_questions.append(q)
                existing_qs.add(q["question"].lower()[:80])

        self.questions_db[sector].extend(new_questions)
        self.save()

        _log(
            f"[{sector}] Generated {len(new_questions)} new questions from {title}",
            "OK",
        )
        return len(new_questions)

    @property
    def extracts_dir(self):
        return os.path.join(DATA_DIR, "extracts")

    def generate_all(self, discovery):
        """Generate questions for all processed documents without questions."""
        _log("=== Phase 3: Expert Question Generation ===")

        if not _GROQ_KEYS:
            _log("No Groq API keys — cannot generate questions", "ERROR")
            return 0

        candidates = discovery.get_without_questions()
        if not candidates:
            _log("No documents need question generation", "SKIP")
            return 0

        _log(f"Generating questions for {len(candidates)} documents...")
        total_generated = 0

        for sector, doc in candidates:
            count = self.generate_for_document(sector, doc)
            if count > 0:
                discovery.update_doc(
                    sector,
                    doc["url"],
                    {"questions_generated": count},
                )
                total_generated += count
            # Rate limit between docs
            time.sleep(1)

        _log(f"Question generation complete: {total_generated} new questions", "OK")
        return total_generated

    def stats(self):
        """Return question bank stats."""
        stats = {}
        for sector in SECTORS:
            qs = self.questions_db.get(sector, [])
            stats[sector] = {
                "total": len(qs),
                "hard": sum(1 for q in qs if q.get("difficulty") == "hard"),
                "medium": sum(1 for q in qs if q.get("difficulty") == "medium"),
                "easy": sum(1 for q in qs if q.get("difficulty") == "easy"),
                "fr": sum(1 for q in qs if q.get("language") == "fr"),
                "en": sum(1 for q in qs if q.get("language") == "en"),
            }
        return stats


# =========================================================================
#  PHASE 4 — PIPELINE TESTING
# =========================================================================


class PipelineTester:
    """Tests all RAG pipelines with generated questions."""

    def __init__(self, timeout=90, max_retries=2):
        self.timeout = timeout
        self.max_retries = max_retries
        self._rr_counters = {}

    def _get_endpoint(self, pipeline, space=None):
        """Build endpoint URL for a pipeline + space."""
        if space:
            host = SPACES.get(space, SPACES["S1"])
        else:
            # Round-robin across available spaces
            available = PIPELINE_SPACES.get(pipeline, ["S1"])
            idx = self._rr_counters.get(pipeline, 0)
            self._rr_counters[pipeline] = idx + 1
            space_key = available[idx % len(available)]
            host = SPACES[space_key]
        path = WEBHOOK_PATHS.get(pipeline, WEBHOOK_PATHS["standard"])
        return f"{host}{path}"

    def test_question(self, question, pipeline="standard", space=None):
        """
        Send a question to a pipeline and return the result.
        Returns dict with: answer, latency_ms, sources, error, space_used.
        """
        endpoint = self._get_endpoint(pipeline, space)
        query = question.get("question", question.get("query", ""))
        sector = question.get("sector", "finance")

        payload = {
            "query": query,
            "tenant_id": "benchmark",
            "top_k": 10,
            "include_sources": True,
            "benchmark_mode": True,
        }

        # Add sector filter for Standard pipeline
        if pipeline == "standard":
            payload["sector"] = sector

        result = {
            "question_id": question.get("id", "unknown"),
            "question": query,
            "pipeline": pipeline,
            "space": space or "round-robin",
            "endpoint": endpoint,
            "answer": "",
            "sources": [],
            "latency_ms": 0,
            "error": None,
            "timestamp": _ts(),
        }

        for attempt in range(self.max_retries + 1):
            start = time.time()
            status, body, err = _http_request(
                endpoint, method="POST", data=payload, timeout=self.timeout
            )
            latency = int((time.time() - start) * 1000)
            result["latency_ms"] = latency

            if err or status != 200:
                if attempt < self.max_retries and status in (502, 503, 504):
                    time.sleep(3 * (attempt + 1))
                    continue
                result["error"] = err or f"HTTP {status}"
                return result

            # Parse response
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                result["error"] = f"Invalid JSON (len={len(body)})"
                return result

            # Handle various response formats
            if isinstance(data, dict):
                result["answer"] = (
                    data.get("answer", "")
                    or data.get("response", "")
                    or data.get("result", "")
                    or data.get("text", "")
                    or ""
                )
                result["sources"] = data.get("sources", [])

                # Check for empty/error answers
                if not result["answer"] or result["answer"].strip().lower() in (
                    "no answer",
                    "error",
                    "",
                ):
                    # Try nested structures
                    if "output" in data and isinstance(data["output"], dict):
                        result["answer"] = data["output"].get("answer", "")
                        result["sources"] = data["output"].get("sources", [])
            elif isinstance(data, list) and len(data) > 0:
                first = data[0]
                if isinstance(first, dict):
                    result["answer"] = first.get("answer", "") or first.get(
                        "response", ""
                    )
                    result["sources"] = first.get("sources", [])
                elif isinstance(first, str):
                    result["answer"] = first
            elif isinstance(data, str):
                result["answer"] = data

            return result

        return result

    def check_space_health(self, space_key):
        """Quick health check on a Space."""
        host = SPACES.get(space_key, "")
        if not host:
            return False
        status, _, err = _http_request(f"{host}/healthz", timeout=10)
        return status == 200

    def test_all(self, questions_db, sector=None, pipelines=None, max_per_sector=10):
        """
        Test all questions against all pipelines.
        Returns list of result dicts.
        """
        _log("=== Phase 4: Pipeline Testing ===")

        if pipelines is None:
            pipelines = ["standard", "graph", "quantitative", "orchestrator"]

        # Health-check spaces first
        _log("Checking Space health...")
        healthy_spaces = {}
        for key in SPACES:
            alive = self.check_space_health(key)
            healthy_spaces[key] = alive
            status_str = "UP" if alive else "DOWN"
            _log(f"  {key}: {status_str}", "OK" if alive else "WARN")

        # Filter pipelines by healthy spaces
        active_pipelines = []
        for p in pipelines:
            required_spaces = PIPELINE_SPACES.get(p, ["S1"])
            if any(healthy_spaces.get(s, False) for s in required_spaces):
                active_pipelines.append(p)
            else:
                _log(f"Pipeline '{p}' skipped — no healthy spaces", "WARN")

        if not active_pipelines:
            _log("No pipelines available — all spaces down", "ERROR")
            return []

        # Gather questions
        sectors = [sector] if sector else SECTORS
        all_questions = []
        for s in sectors:
            qs = questions_db.get(s, [])
            if max_per_sector and len(qs) > max_per_sector:
                # Prioritize: hard first, then medium, then easy
                hard = [q for q in qs if q.get("difficulty") == "hard"]
                medium = [q for q in qs if q.get("difficulty") == "medium"]
                easy = [q for q in qs if q.get("difficulty") == "easy"]
                selected = (hard + medium + easy)[:max_per_sector]
                all_questions.extend(selected)
            else:
                all_questions.extend(qs)

        if not all_questions:
            _log("No questions available for testing", "WARN")
            return []

        _log(
            f"Testing {len(all_questions)} questions across {len(active_pipelines)} pipelines"
        )
        total_tests = len(all_questions) * len(active_pipelines)
        _log(f"Total tests: {total_tests}")

        results = []
        test_num = 0

        for pipeline in active_pipelines:
            _log(f"\n--- Pipeline: {pipeline} ---")
            pipeline_results = []

            for q in all_questions:
                test_num += 1
                q_text = q.get("question", "")[:60]
                sector_tag = q.get("sector", "?")

                _log(
                    f"  [{test_num}/{total_tests}] [{sector_tag}] {q_text}..."
                )

                result = self.test_question(q, pipeline=pipeline)

                if result["error"]:
                    _log(
                        f"    ERROR: {result['error'][:80]} ({result['latency_ms']}ms)",
                        "ERROR",
                    )
                else:
                    answer_preview = result["answer"][:60].replace("\n", " ")
                    _log(
                        f"    OK: \"{answer_preview}...\" ({result['latency_ms']}ms)",
                        "OK",
                    )

                pipeline_results.append(result)
                results.append(result)

                # Small delay between tests
                time.sleep(0.5)

            # Pipeline summary
            ok = sum(1 for r in pipeline_results if not r["error"])
            avg_lat = (
                sum(r["latency_ms"] for r in pipeline_results if not r["error"])
                / max(ok, 1)
            )
            _log(
                f"  Pipeline {pipeline}: {ok}/{len(pipeline_results)} OK, avg {avg_lat:.0f}ms"
            )

        return results


# =========================================================================
#  PHASE 5 — SCORING & ANALYSIS
# =========================================================================


class Scorer:
    """Scores pipeline answers against expected answers and keywords."""

    @staticmethod
    def normalize(text):
        """Normalize text for matching: lowercase, strip formatting from numbers."""
        if not text:
            return ""
        t = text.lower()
        # Remove commas/spaces in numbers (6,745 -> 6745)
        t = re.sub(r"(\d)[,\s](\d)", r"\1\2", t)
        t = re.sub(r"(\d)\s+(\d)", r"\1\2", t)
        t = t.replace("$", "").replace("%", "").replace("\u20ac", "")
        return t

    @staticmethod
    def score_keywords(answer, keywords):
        """
        Score 0.0-1.0: how many expected keywords appear in the answer.
        """
        if not keywords or not answer:
            return 0.0
        answer_norm = Scorer.normalize(answer)
        hits = sum(1 for kw in keywords if Scorer.normalize(kw) in answer_norm)
        return hits / len(keywords)

    @staticmethod
    def score_factual(answer, expected_answer):
        """
        Score 0.0-1.0: factual overlap between answer and expected.
        Uses token-level intersection.
        """
        if not answer or not expected_answer:
            return 0.0

        def tokenize(text):
            return set(re.findall(r"\b\w+\b", Scorer.normalize(text)))

        answer_tokens = tokenize(answer)
        expected_tokens = tokenize(expected_answer)

        if not expected_tokens:
            return 0.0

        overlap = answer_tokens & expected_tokens
        # Weighted: prefer longer meaningful tokens
        meaningful = {t for t in overlap if len(t) > 2}
        expected_meaningful = {t for t in expected_tokens if len(t) > 2}

        if not expected_meaningful:
            return len(overlap) / len(expected_tokens)

        return len(meaningful) / len(expected_meaningful)

    @staticmethod
    def score_citation(answer, sources):
        """
        Score 0.0-1.0: does the answer cite specific sources?
        """
        if not answer:
            return 0.0

        score = 0.0

        # Check for source references in the answer text
        citation_patterns = [
            r"selon\s+(?:le|la|l'|les)",
            r"d'apr[eè]s\s+",
            r"source\s*:",
            r"r[eé]f[eé]rence",
            r"article\s+\d+",
            r"page\s+\d+",
            r"chapitre\s+",
            r"section\s+",
            r"according\s+to",
            r"\[.*?\]",  # bracket references
            r"\(.*?(?:20\d{2}|p\.\s*\d+).*?\)",  # parenthetical with year/page
        ]
        citation_hits = sum(
            1 for p in citation_patterns if re.search(p, answer, re.IGNORECASE)
        )
        score += min(citation_hits / 3.0, 0.5)

        # Check for source metadata
        if sources and isinstance(sources, list):
            if len(sources) > 0:
                score += 0.3
            if len(sources) >= 3:
                score += 0.2

        return min(score, 1.0)

    @staticmethod
    def score_completeness(answer, expected_answer):
        """
        Score 0.0-1.0: is the answer sufficiently detailed?
        """
        if not answer:
            return 0.0

        answer_len = len(answer.strip())
        expected_len = len(expected_answer.strip()) if expected_answer else 200

        # Very short answers score poorly
        if answer_len < 20:
            return 0.1
        if answer_len < 50:
            return 0.3

        # Decent length
        ratio = min(answer_len / max(expected_len, 100), 2.0)
        if ratio >= 0.5:
            return min(0.5 + ratio * 0.25, 1.0)
        return ratio

    @staticmethod
    def score_language(answer, expected_language):
        """
        Score 0.0-1.0: does the answer match the expected language?
        Simple heuristic: check for French/English markers.
        """
        if not answer or not expected_language:
            return 0.5

        # French markers
        fr_words = {"le", "la", "les", "des", "une", "est", "dans", "pour", "avec", "qui", "que", "sur", "par"}
        # English markers
        en_words = {"the", "is", "are", "was", "were", "have", "has", "with", "for", "this", "that", "from"}

        words = set(re.findall(r"\b\w+\b", answer.lower()))
        fr_score = len(words & fr_words)
        en_score = len(words & en_words)

        if expected_language == "fr":
            return 1.0 if fr_score > en_score else 0.3
        elif expected_language == "en":
            return 1.0 if en_score > fr_score else 0.3
        return 0.5

    def score_result(self, result, question):
        """
        Compute all scores for a single test result.
        Returns dict with individual and overall scores.
        """
        answer = result.get("answer", "")
        expected = question.get("expected_answer", "")
        keywords = question.get("keywords", [])
        language = question.get("language", "fr")
        sources = result.get("sources", [])

        if result.get("error"):
            return {
                "keyword_score": 0.0,
                "factual_score": 0.0,
                "citation_score": 0.0,
                "completeness_score": 0.0,
                "language_score": 0.0,
                "overall_score": 0.0,
                "error": True,
            }

        kw = self.score_keywords(answer, keywords)
        fa = self.score_factual(answer, expected)
        ci = self.score_citation(answer, sources)
        co = self.score_completeness(answer, expected)
        la = self.score_language(answer, language)

        # Weighted overall: factual accuracy most important
        overall = (
            kw * 0.30  # Keywords: core factual check
            + fa * 0.30  # Factual overlap
            + ci * 0.15  # Citation quality
            + co * 0.15  # Completeness
            + la * 0.10  # Language match
        )

        return {
            "keyword_score": round(kw, 3),
            "factual_score": round(fa, 3),
            "citation_score": round(ci, 3),
            "completeness_score": round(co, 3),
            "language_score": round(la, 3),
            "overall_score": round(overall, 3),
            "error": False,
        }

    def score_all(self, results, questions_db):
        """Score all test results. Returns scored results + summary."""
        _log("=== Phase 5: Scoring & Analysis ===")

        # Build question lookup
        q_lookup = {}
        for sector_qs in questions_db.values():
            for q in sector_qs:
                q_lookup[q.get("id", "")] = q

        scored_results = []
        for r in results:
            q_id = r.get("question_id", "")
            question = q_lookup.get(q_id, {})
            scores = self.score_result(r, question)
            scored = {**r, **scores, "sector": question.get("sector", "unknown")}
            scored_results.append(scored)

        # Compute summary
        summary = self._compute_summary(scored_results)

        return scored_results, summary

    def _compute_summary(self, scored_results):
        """Compute aggregate summary from scored results."""
        summary = {
            "timestamp": _ts(),
            "total_tests": len(scored_results),
            "total_errors": sum(1 for r in scored_results if r.get("error")),
            "by_pipeline": {},
            "by_sector": {},
            "by_sector_pipeline": {},
            "overall": {},
        }

        # Group by pipeline
        by_pipeline = {}
        for r in scored_results:
            p = r.get("pipeline", "unknown")
            if p not in by_pipeline:
                by_pipeline[p] = []
            by_pipeline[p].append(r)

        for p, rs in by_pipeline.items():
            ok = [r for r in rs if not r.get("error")]
            summary["by_pipeline"][p] = {
                "total": len(rs),
                "ok": len(ok),
                "errors": len(rs) - len(ok),
                "avg_overall": round(
                    sum(r["overall_score"] for r in ok) / max(len(ok), 1), 3
                ),
                "avg_keyword": round(
                    sum(r["keyword_score"] for r in ok) / max(len(ok), 1), 3
                ),
                "avg_factual": round(
                    sum(r["factual_score"] for r in ok) / max(len(ok), 1), 3
                ),
                "avg_citation": round(
                    sum(r["citation_score"] for r in ok) / max(len(ok), 1), 3
                ),
                "avg_latency_ms": round(
                    sum(r["latency_ms"] for r in ok) / max(len(ok), 1)
                ),
                "error_rate": round((len(rs) - len(ok)) / max(len(rs), 1), 3),
            }

        # Group by sector
        by_sector = {}
        for r in scored_results:
            s = r.get("sector", "unknown")
            if s not in by_sector:
                by_sector[s] = []
            by_sector[s].append(r)

        for s, rs in by_sector.items():
            ok = [r for r in rs if not r.get("error")]
            summary["by_sector"][s] = {
                "total": len(rs),
                "ok": len(ok),
                "avg_overall": round(
                    sum(r["overall_score"] for r in ok) / max(len(ok), 1), 3
                ),
                "avg_keyword": round(
                    sum(r["keyword_score"] for r in ok) / max(len(ok), 1), 3
                ),
                "avg_factual": round(
                    sum(r["factual_score"] for r in ok) / max(len(ok), 1), 3
                ),
            }

        # Cross: sector x pipeline
        for r in scored_results:
            key = f"{r.get('sector', '?')}_{r.get('pipeline', '?')}"
            if key not in summary["by_sector_pipeline"]:
                summary["by_sector_pipeline"][key] = {"scores": [], "errors": 0}
            if r.get("error"):
                summary["by_sector_pipeline"][key]["errors"] += 1
            else:
                summary["by_sector_pipeline"][key]["scores"].append(
                    r["overall_score"]
                )

        # Flatten cross-section
        for key, data in summary["by_sector_pipeline"].items():
            scores = data["scores"]
            summary["by_sector_pipeline"][key] = {
                "count": len(scores),
                "errors": data["errors"],
                "avg_overall": round(
                    sum(scores) / max(len(scores), 1), 3
                )
                if scores
                else 0.0,
            }

        # Overall
        all_ok = [r for r in scored_results if not r.get("error")]
        if all_ok:
            summary["overall"] = {
                "avg_overall": round(
                    sum(r["overall_score"] for r in all_ok) / len(all_ok), 3
                ),
                "avg_keyword": round(
                    sum(r["keyword_score"] for r in all_ok) / len(all_ok), 3
                ),
                "avg_factual": round(
                    sum(r["factual_score"] for r in all_ok) / len(all_ok), 3
                ),
                "avg_citation": round(
                    sum(r["citation_score"] for r in all_ok) / len(all_ok), 3
                ),
                "avg_latency_ms": round(
                    sum(r["latency_ms"] for r in all_ok) / len(all_ok)
                ),
                "success_rate": round(len(all_ok) / max(len(scored_results), 1), 3),
            }

        return summary


# =========================================================================
#  REPORTING
# =========================================================================


def print_report(summary, detailed_results=None):
    """Print a formatted evaluation report."""
    print("\n" + "=" * 72)
    print("  EVAL RUNNER V2 — RESULTS REPORT")
    print("=" * 72)
    print(f"  Timestamp: {summary.get('timestamp', 'N/A')}")
    print(
        f"  Total tests: {summary.get('total_tests', 0)} | Errors: {summary.get('total_errors', 0)}"
    )

    # Overall
    ov = summary.get("overall", {})
    if ov:
        print(f"\n  OVERALL:")
        print(f"    Score:    {ov.get('avg_overall', 0):.1%}")
        print(f"    Keyword:  {ov.get('avg_keyword', 0):.1%}")
        print(f"    Factual:  {ov.get('avg_factual', 0):.1%}")
        print(f"    Citation: {ov.get('avg_citation', 0):.1%}")
        print(f"    Latency:  {ov.get('avg_latency_ms', 0):.0f}ms")
        print(f"    Success:  {ov.get('success_rate', 0):.1%}")

    # By pipeline
    bp = summary.get("by_pipeline", {})
    if bp:
        print(f"\n  BY PIPELINE:")
        header = f"  {'Pipeline':<16} {'Score':>8} {'Keyword':>8} {'Factual':>8} {'Citation':>8} {'Latency':>8} {'OK/Total':>10}"
        print(header)
        print("  " + "-" * len(header.strip()))
        for p in sorted(bp.keys()):
            d = bp[p]
            print(
                f"  {p:<16} {d.get('avg_overall',0):>7.1%} {d.get('avg_keyword',0):>7.1%} "
                f"{d.get('avg_factual',0):>7.1%} {d.get('avg_citation',0):>7.1%} "
                f"{d.get('avg_latency_ms',0):>7.0f}ms {d.get('ok',0):>3}/{d.get('total',0):<3}"
            )

    # By sector
    bs = summary.get("by_sector", {})
    if bs:
        print(f"\n  BY SECTOR:")
        header = f"  {'Sector':<16} {'Score':>8} {'Keyword':>8} {'Factual':>8} {'OK/Total':>10}"
        print(header)
        print("  " + "-" * len(header.strip()))
        for s in sorted(bs.keys()):
            d = bs[s]
            print(
                f"  {s:<16} {d.get('avg_overall',0):>7.1%} {d.get('avg_keyword',0):>7.1%} "
                f"{d.get('avg_factual',0):>7.1%} {d.get('ok',0):>3}/{d.get('total',0):<3}"
            )

    # Sector x Pipeline matrix
    bsp = summary.get("by_sector_pipeline", {})
    if bsp:
        print(f"\n  SECTOR x PIPELINE MATRIX (avg_overall):")
        pipelines_in_matrix = sorted(set(k.split("_")[-1] for k in bsp.keys()))
        sectors_in_matrix = sorted(set(k.rsplit("_", 1)[0] for k in bsp.keys()))

        header = f"  {'Sector':<14}" + "".join(f" {p:<14}" for p in pipelines_in_matrix)
        print(header)
        print("  " + "-" * len(header.strip()))
        for s in sectors_in_matrix:
            row = f"  {s:<14}"
            for p in pipelines_in_matrix:
                key = f"{s}_{p}"
                d = bsp.get(key, {})
                val = d.get("avg_overall", 0)
                errs = d.get("errors", 0)
                if d.get("count", 0) > 0:
                    row += f" {val:>6.1%} ({d['count']}){' ' * max(0, 5 - len(str(d['count'])))}"
                elif errs > 0:
                    row += f" {'ERR':>6} ({errs}){' ' * max(0, 5 - len(str(errs)))}"
                else:
                    row += f" {'---':>6}       "
            print(row)

    print("\n" + "=" * 72)

    # Show worst performing questions if detailed results available
    if detailed_results:
        ok_results = [r for r in detailed_results if not r.get("error") and r.get("overall_score", 1.0) < 0.3]
        if ok_results:
            ok_results.sort(key=lambda r: r.get("overall_score", 0))
            print("\n  WORST PERFORMING (score < 30%):")
            for r in ok_results[:5]:
                q = r.get("question", "")[:55]
                print(
                    f"    [{r.get('sector','?')}/{r.get('pipeline','?')}] {r.get('overall_score',0):.0%} — {q}..."
                )
        print()


# =========================================================================
#  MAIN ORCHESTRATOR
# =========================================================================


class EvalRunnerV2:
    """Main orchestrator: ties together all phases."""

    def __init__(self, args):
        self.args = args
        self.sector = args.sector if hasattr(args, "sector") else None
        self.discovery = DocumentDiscovery(
            sectors=[self.sector] if self.sector else None
        )
        self.processor = DoclingProcessor(
            timeout=getattr(args, "docling_timeout", 180)
        )
        self.generator = QuestionGenerator()
        self.tester = PipelineTester(
            timeout=getattr(args, "test_timeout", 90)
        )
        self.scorer = Scorer()

    def run_discover(self):
        """Phase 1 only."""
        return self.discovery.discover()

    def run_process(self):
        """Phase 2 only."""
        return self.processor.process_all(self.discovery)

    def run_generate(self):
        """Phase 3 only."""
        return self.generator.generate_all(self.discovery)

    def run_test(self):
        """Phase 4+5: test and score."""
        pipelines = None
        if hasattr(self.args, "pipelines") and self.args.pipelines:
            pipelines = [p.strip() for p in self.args.pipelines.split(",")]

        max_per = getattr(self.args, "max_questions", 10)

        results = self.tester.test_all(
            self.generator.questions_db,
            sector=self.sector,
            pipelines=pipelines,
            max_per_sector=max_per,
        )

        if not results:
            _log("No test results to score", "WARN")
            return [], {}

        scored, summary = self.scorer.score_all(results, self.generator.questions_db)

        # Save results
        ts = _ts_file()
        results_file = os.path.join(DATA_DIR, f"eval-results-{ts}.json")
        _save_json(results_file, scored)
        _save_json(EVAL_SUMMARY_FILE, summary)

        _log(f"Results saved: {results_file}")
        _log(f"Summary saved: {EVAL_SUMMARY_FILE}")

        print_report(summary, scored)

        return scored, summary

    def run_report(self):
        """Show latest summary."""
        summary = _load_json(EVAL_SUMMARY_FILE, default={})
        if not summary:
            _log("No eval summary found. Run a full cycle first.", "WARN")
            return

        # Also try to load latest detailed results
        import glob as globmod
        pattern = os.path.join(DATA_DIR, "eval-results-*.json")
        files = sorted(globmod.glob(pattern))
        detailed = None
        if files:
            detailed = _load_json(files[-1], default=[])

        print_report(summary, detailed)

        # Also show registry and question stats
        disc = DocumentDiscovery()
        print("  DOCUMENT REGISTRY:")
        for sector, stats in disc.stats().items():
            print(
                f"    {sector}: {stats['total']} total, "
                f"{stats['processed']} processed, "
                f"{stats['with_questions']} with questions"
            )

        gen = QuestionGenerator()
        print("\n  QUESTION BANK:")
        for sector, stats in gen.stats().items():
            print(
                f"    {sector}: {stats['total']} questions "
                f"(hard={stats['hard']}, medium={stats['medium']}, easy={stats['easy']})"
            )
        print()

    def run_full(self):
        """Full cycle: discover -> process -> generate -> test -> score."""
        _log("=" * 60)
        _log("EVAL RUNNER V2 — FULL CYCLE")
        _log("=" * 60)
        start = time.time()

        # Phase 1
        self.run_discover()

        # Phase 2
        self.run_process()

        # Phase 3
        self.run_generate()

        # Phase 4+5
        scored, summary = self.run_test()

        elapsed = time.time() - start
        _log(f"\nFull cycle complete in {elapsed:.0f}s")

        return scored, summary

    def run_loop(self, interval_seconds):
        """Continuous loop."""
        _log(f"Starting continuous eval loop (interval={interval_seconds}s)")
        cycle = 0
        while True:
            cycle += 1
            _log(f"\n{'='*60}")
            _log(f"CYCLE {cycle}")
            _log(f"{'='*60}")
            try:
                self.run_full()
            except KeyboardInterrupt:
                _log("Interrupted by user")
                break
            except Exception as e:
                _log(f"Cycle {cycle} failed: {e}", "ERROR")
                traceback.print_exc()

            _log(f"Next cycle in {interval_seconds}s...")
            try:
                time.sleep(interval_seconds)
            except KeyboardInterrupt:
                _log("Interrupted by user")
                break


# =========================================================================
#  CLI
# =========================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Eval Runner V2 — Intelligent Document-Driven RAG Evaluation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 eval/eval-runner-v2.py                          # Full cycle
  python3 eval/eval-runner-v2.py --discover               # Discover docs only
  python3 eval/eval-runner-v2.py --process                # Process via Docling
  python3 eval/eval-runner-v2.py --generate               # Generate questions
  python3 eval/eval-runner-v2.py --test                   # Test pipelines
  python3 eval/eval-runner-v2.py --sector finance         # Single sector
  python3 eval/eval-runner-v2.py --loop 3600              # Continuous hourly
  python3 eval/eval-runner-v2.py --report                 # Show results
        """,
    )

    # Phase selectors (mutually exclusive with full cycle)
    phase_group = parser.add_argument_group("Phase Selection")
    phase_group.add_argument(
        "--discover", action="store_true", help="Only discover new documents"
    )
    phase_group.add_argument(
        "--process", action="store_true", help="Only process unprocessed docs via Docling"
    )
    phase_group.add_argument(
        "--generate", action="store_true", help="Only generate questions from processed docs"
    )
    phase_group.add_argument(
        "--test", action="store_true", help="Only test existing questions against pipelines"
    )
    phase_group.add_argument(
        "--report", action="store_true", help="Show latest evaluation results"
    )

    # Filters
    filter_group = parser.add_argument_group("Filters")
    filter_group.add_argument(
        "--sector",
        choices=SECTORS,
        help="Run for a single sector only",
    )
    filter_group.add_argument(
        "--pipelines",
        type=str,
        help="Comma-separated pipeline names (e.g., standard,graph)",
    )

    # Options
    opts_group = parser.add_argument_group("Options")
    opts_group.add_argument(
        "--loop",
        type=int,
        metavar="SECONDS",
        help="Run continuously with given interval",
    )
    opts_group.add_argument(
        "--max-questions",
        type=int,
        default=10,
        help="Max questions per sector for testing (default: 10)",
    )
    opts_group.add_argument(
        "--docling-timeout",
        type=int,
        default=180,
        help="Docling processing timeout in seconds (default: 180)",
    )
    opts_group.add_argument(
        "--test-timeout",
        type=int,
        default=90,
        help="Pipeline test timeout in seconds (default: 90)",
    )

    args = parser.parse_args()

    # Sanity checks
    if not _GROQ_KEYS:
        _log("WARNING: No GROQ_API_KEY found — question generation will fail", "WARN")
        _log("Run: source .env.local", "WARN")

    runner = EvalRunnerV2(args)

    # Route to the right phase
    if args.report:
        runner.run_report()
    elif args.loop:
        runner.run_loop(args.loop)
    elif args.discover:
        runner.run_discover()
        # Show stats
        for sector, s in runner.discovery.stats().items():
            _log(
                f"  {sector}: {s['total']} docs ({s['processed']} processed, {s['discovered']} pending)"
            )
    elif args.process:
        runner.run_process()
    elif args.generate:
        runner.run_generate()
        # Show stats
        for sector, s in runner.generator.stats().items():
            _log(f"  {sector}: {s['total']} questions")
    elif args.test:
        runner.run_test()
    else:
        # Full cycle
        runner.run_full()


if __name__ == "__main__":
    main()
