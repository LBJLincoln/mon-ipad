#!/usr/bin/env python3
"""
Expert Discovery — Continuous Expert Document & Q&A Discovery Engine
=====================================================================
Uses Exa.AI to discover REAL expert-level documents across 4 sectors
(finance, btp, juridique, industrie) and generates expert-grade Q&A pairs
via LiteLLM proxy for RAG evaluation.

Pipeline:
  1. Exa.AI searches with sector-specific expert queries (10+ per sector)
  2. Filter & deduplicate discovered documents
  3. LiteLLM (smart model group → llama-70b/qwen/gemini) generates expert Q&A
  4. Saves everything to data/eval/expert-discovery/

Usage:
  source .env.local
  python3 eval/expert-discovery.py                          # Full cycle, all sectors
  python3 eval/expert-discovery.py --sector finance         # Single sector
  python3 eval/expert-discovery.py --sector all --loop 3600 # Continuous every hour
  python3 eval/expert-discovery.py --discover-only          # Only discover docs
  python3 eval/expert-discovery.py --generate-only          # Only gen Q&A from existing
  python3 eval/expert-discovery.py --report                 # Show summary stats
  python3 eval/expert-discovery.py --max-queries 5          # Limit queries per sector
  python3 eval/expert-discovery.py --dry-run                # No LLM calls, just search
"""

# ─── IPv4 monkey-patch (GCP VM has broken IPv6) ──────────────────────────
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
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# ─── Force line buffering for nohup ──────────────────────────────────────
try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

# ─── Paths ───────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "eval" / "expert-discovery"
DOCS_FILE = DATA_DIR / "discovered-documents.json"
QA_FILE = DATA_DIR / "expert-qa-pairs.json"
PROGRESS_FILE = DATA_DIR / "discovery-progress.json"
HISTORY_FILE = DATA_DIR / "run-history.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)

# ─── SSL context (permissive for HF Spaces) ─────────────────────────────
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE

# ─── ANSI colors ─────────────────────────────────────────────────────────
class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"


# ─── Config ──────────────────────────────────────────────────────────────
EXA_API_KEY = os.environ.get("EXA_API_KEY", "")
EXA_URL = "https://api.exa.ai/search"
EXA_DELAY = 1.5  # seconds between Exa.AI requests (rate limit)

LITELLM_URL = "https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/chat/completions"
LITELLM_KEY = "sk-litellm-nomos-2026"
LITELLM_MODEL = "smart"
LITELLM_TIMEOUT = 90  # seconds

# Fallback: Groq direct (if LiteLLM is down)
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"
_GROQ_KEYS = []
for _k, _v in sorted(os.environ.items()):
    if _k.startswith("GROQ_API_KEY") and _v and not _k.endswith("QUANTITATIVE"):
        _GROQ_KEYS.append(_v)
_groq_idx = 0

SECTORS = ["finance", "btp", "juridique", "industrie"]

MIN_CONTENT_LENGTH = 200  # minimum chars of useful content per document
MAX_CONTENT_FOR_QA = 6000  # max chars to send to LLM for Q&A generation
MAX_QA_PER_DOC = 5  # max Q&A pairs to generate per document
MAX_PDF_SIZE = 10485760  # 10MB max PDF size for Docling processing

# ─── Redis / Upstash config ──────────────────────────────────────────────
UPSTASH_REDIS_REST_URL = "https://dynamic-frog-47846.upstash.io"
UPSTASH_REDIS_REST_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")

# ═══════════════════════════════════════════════════════════════════════════
#  SECTOR-SPECIFIC TAVILY SEARCH QUERIES (10+ per sector)
# ═══════════════════════════════════════════════════════════════════════════

SECTOR_QUERIES = {
    "finance": [
        # IFRS & Accounting Standards
        "IFRS 9 instruments financiers classification evaluation depreciation",
        "IFRS 16 contrats location comptabilisation normes",
        "IFRS 17 contrats assurance norme comptable 2025",
        # SEC & Regulatory
        "SEC 10-K annual report filing requirements format",
        "Basel III ratio fonds propres exigences prudentielles banques",
        "AMF rapport annuel marches financiers regulation France",
        # Corporate Finance
        "rapport annuel CAC40 TotalEnergies LVMH resultats financiers",
        "analyse financiere ratio endettement liquidite solvabilite entreprise",
        "valorisation entreprise DCF actualisation flux tresorerie methodes",
        # Risk & Compliance
        "gestion risque credit marche operationnel banque reglementation",
        "Solvabilite II directive assurance capital requis Europe",
        "audit financier commissaire comptes normes ISA procedures",
        # Market Analysis
        "produits derives options futures swaps evaluation pricing",
        "marche obligataire taux interet courbe rendement analyse",
        "private equity LBO due diligence valorisation fonds investissement",
    ],
    "btp": [
        # DTU & Construction Standards
        "DTU 31.2 construction ossature bois charpente normes techniques",
        "DTU 13.3 dallage beton sol fondations superficielles norme",
        "DTU 40.11 couverture ardoises toiture etancheite",
        # Eurocodes
        "Eurocode 2 calcul structures beton arme dimensionnement",
        "Eurocode 8 construction parasismique zonage sismique France",
        "Eurocode 5 calcul structures bois dimensionnement charges",
        # CCTP & Public Markets
        "CCTP modele marche public travaux batiment cahier charges",
        "BOAMP appel offres marche public construction procedure",
        "DPGF detail quantitatif estimatif travaux prix unitaires",
        # Building Regulations
        "RE2020 reglementation environnementale batiment neuf exigences 2025",
        "NF DTU 20.1 maconnerie parpaing briques construction murs",
        "diagnostic technique immobilier amiante plomb DPE obligations",
        # Technical Methods
        "fondations profondes pieux micropieux techniques realisation sol",
        "isolation thermique interieure exterieure ITE materiaux performance",
        "AFNOR NF P03-001 marche prive travaux batiment contrat",
    ],
    "juridique": [
        # Civil Law
        "code civil article 1240 responsabilite delictuelle conditions reparation",
        "code civil contrat vente obligations vendeur acheteur garantie",
        "droit obligations contractuelles inexecution resolution resiliation code civil",
        # Court Decisions
        "jurisprudence Cour cassation chambre commerciale arret 2024 2025",
        "jurisprudence Conseil Etat contentieux administratif recours exces pouvoir",
        "arret CJUE droit europeen preliminaire prejudicielle jurisprudence",
        # RGPD & Data Protection
        "RGPD reglement general protection donnees personnelles principes obligations",
        "CNIL sanctions RGPD amende entreprise traitement donnees 2024",
        "delegue protection donnees DPO missions obligations RGPD",
        # Business Law
        "droit societes SARL SAS creation statuts formalites juridiques",
        "contrat travail CDI CDD rupture licenciement indemnites procedure",
        "procedure collective redressement liquidation judiciaire sauvegarde entreprise",
        # Specialized
        "droit propriete intellectuelle brevet marque depot protection INPI",
        "contentieux commercial tribunal procedure recouvrement creances injonction",
        "bail commercial 3-6-9 renouvellement revision loyer indemnite eviction",
    ],
    "industrie": [
        # ISO Standards
        "ISO 9001 2015 systeme management qualite exigences certification audit",
        "ISO 14001 management environnemental certification norme 2015",
        "ISO 45001 sante securite travail management SST norme",
        # Quality & Safety Methods
        "AMDEC analyse modes defaillance effets criticite methode industrielle",
        "fiche donnees securite FDS substances chimiques REACH CLP",
        "lean manufacturing six sigma DMAIC amelioration continue production",
        # Maintenance
        "maintenance preventive predictive conditionnelle TPM equipement industriel",
        "GMAO gestion maintenance assistee ordinateur planification intervention",
        "controle non destructif CND ultrasons radiographie magnetoscopie ressuage",
        # Industry 4.0
        "industrie 4.0 IoT capteurs connectes usine intelligente digitalisation",
        "automatisation robotique industrielle cobotique programmation automate",
        "HACCP securite alimentaire analyse dangers points critiques normes",
        # Process & Regulation
        "REACH enregistrement evaluation autorisation substances chimiques Europe",
        "norme ATEX zones explosion equipement protection atmospheres explosibles",
        "audit qualite interne processus non conformite actions correctives ISO",
    ],
}

# ─── Sector-specific terminology for LLM prompt ─────────────────────────
SECTOR_TERMINOLOGY = {
    "finance": {
        "domain": "Finance, Comptabilite, Audit, Marches Financiers",
        "key_terms": [
            "IFRS", "fonds propres", "ratio de solvabilite", "DCF",
            "amortissement", "provision", "juste valeur", "consolidation",
            "risque de credit", "VaR", "EBITDA", "flux de tresorerie",
            "bilan", "compte de resultat", "capitaux propres",
        ],
        "doc_types": [
            "normes IFRS", "rapports annuels", "filings SEC", "reglementations Basel III",
            "rapports AMF", "analyses financieres", "prospectus",
        ],
        "expert_examples": [
            "Quelle est la difference entre le modele des pertes attendues (ECL) sous IFRS 9 et l'ancien modele IAS 39 ?",
            "Comment calculer le ratio CET1 selon Basel III et quels sont les seuils reglementaires ?",
        ],
    },
    "btp": {
        "domain": "Batiment, Travaux Publics, Construction, Genie Civil",
        "key_terms": [
            "DTU", "Eurocode", "CCTP", "RE2020", "resistance thermique",
            "charge admissible", "ferraillage", "enrobage", "retrait",
            "fissuration", "etancheite", "isolation", "fondation",
            "parasismique", "coefficient de securite",
        ],
        "doc_types": [
            "DTU normes", "Eurocodes", "CCTP", "AFNOR standards",
            "BOAMP appels d'offres", "guides techniques CSTB",
        ],
        "expert_examples": [
            "Quelles sont les exigences de l'Eurocode 2 pour l'enrobage minimal des armatures en fonction de la classe d'exposition ?",
            "Comment determiner la classe energetique d'un batiment neuf selon la RE2020 ?",
        ],
    },
    "juridique": {
        "domain": "Droit Civil, Commercial, Social, Administratif",
        "key_terms": [
            "responsabilite civile", "obligation contractuelle", "dommages-interets",
            "clause resolutoire", "prescription", "competence juridictionnelle",
            "vice cache", "garantie decennale", "mise en demeure",
            "action en justice", "recours", "jurisprudence", "arret",
            "cassation", "tribunal",
        ],
        "doc_types": [
            "Code civil", "jurisprudence Cour de Cassation", "RGPD",
            "contrats-types", "codes (commerce, travail)", "arrets",
        ],
        "expert_examples": [
            "Quelles sont les conditions de mise en oeuvre de la responsabilite delictuelle selon l'article 1240 du Code civil ?",
            "Quelle est la portee de l'arret de la Cour de cassation sur la requalification des CDD en CDI ?",
        ],
    },
    "industrie": {
        "domain": "Industrie, Qualite, Securite, Maintenance, Production",
        "key_terms": [
            "ISO 9001", "non-conformite", "audit interne", "AMDEC",
            "criticite", "IPR", "maintenance preventive", "taux de rendement",
            "TRS", "OEE", "kanban", "5S", "Kaizen",
            "FDS", "EPI", "ATEX", "REACH",
        ],
        "doc_types": [
            "normes ISO", "procedures AMDEC", "fiches de securite FDS",
            "manuels de maintenance", "rapports d'audit qualite",
        ],
        "expert_examples": [
            "Comment calculer l'Indice de Priorite de Risque (IPR) dans une analyse AMDEC et quels sont les seuils d'action ?",
            "Quelles sont les exigences documentaires de l'ISO 9001:2015 pour le controle des processus ?",
        ],
    },
}


# ═══════════════════════════════════════════════════════════════════════════
#  UTILITIES
# ═══════════════════════════════════════════════════════════════════════════

def _ts():
    """ISO timestamp."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ts_short():
    """Short timestamp for display."""
    return datetime.now().strftime("%H:%M:%S")


def _log(msg, level="INFO"):
    """Print with timestamp and level."""
    ts = _ts_short()
    colors = {
        "INFO": C.WHITE, "OK": C.GREEN, "WARN": C.YELLOW,
        "ERROR": C.RED, "SKIP": C.DIM, "STAGE": C.CYAN,
    }
    prefix = {"INFO": "+", "OK": "v", "WARN": "!", "ERROR": "X", "SKIP": "-", "STAGE": "="}
    color = colors.get(level, C.WHITE)
    pfx = prefix.get(level, " ")
    print(f"{C.DIM}[{ts}]{C.RESET} {color}[{pfx}]{C.RESET} {msg}", flush=True)


def _url_hash(url):
    """Short stable hash for a URL."""
    return hashlib.sha256(url.encode()).hexdigest()[:12]


def _content_hash(text):
    """Short hash for deduplication of content."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:10]


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
    tmp = str(path) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    os.replace(tmp, str(path))


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


def clean_web_content(text):
    """Clean raw web content for analysis."""
    if not text:
        return ""
    # Remove excessive whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    # Remove common web artifacts
    text = re.sub(r'Cookie[s]?.*?(?:accepter|refuser|parametrer).*?\n', '', text, flags=re.IGNORECASE)
    text = re.sub(r'(?:Partager|Share)[\s:]*(?:Facebook|Twitter|LinkedIn|Email).*?\n', '', text, flags=re.IGNORECASE)
    text = re.sub(r'(?:©|Copyright).*?\d{4}.*?\n', '', text, flags=re.IGNORECASE)
    # Remove navigation-like lines
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if len(stripped) > 20 or stripped.startswith(('-', '*', '–')) or re.match(r'^\d+[\.\)]', stripped):
            cleaned_lines.append(line)
        elif len(stripped) > 5 and not re.match(
            r'^(Menu|Accueil|Contact|Recherche|Connexion|Inscription|Panier|Mon compte|Fermer|Ouvrir)$',
            stripped, re.IGNORECASE
        ):
            cleaned_lines.append(line)
    return '\n'.join(cleaned_lines).strip()


def extract_domain(url):
    """Extract domain name from URL."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc.replace("www.", "")
    except Exception:
        return "unknown"


# ═══════════════════════════════════════════════════════════════════════════
#  PHASE 1 — EXA.AI DOCUMENT DISCOVERY
# ═══════════════════════════════════════════════════════════════════════════

class ExaDiscovery:
    """Discovers expert-level documents via Exa.AI search API."""

    def __init__(self, sectors=None, max_queries=0):
        self.sectors = sectors or SECTORS
        self.max_queries = max_queries
        self.docs_db = _load_json(DOCS_FILE, default={"metadata": {}, "sectors": {}})
        # Ensure structure
        if "sectors" not in self.docs_db:
            self.docs_db["sectors"] = {}
        for s in SECTORS:
            if s not in self.docs_db["sectors"]:
                self.docs_db["sectors"][s] = []

    def save(self):
        self.docs_db["metadata"]["last_updated"] = _ts()
        _save_json(DOCS_FILE, self.docs_db)

    def _doc_exists(self, sector, url):
        """Check if a URL is already in the registry."""
        return any(d["url"] == url for d in self.docs_db["sectors"].get(sector, []))

    def _filter_url_by_head(self, url):
        """
        HEAD request to check PDF validity and size.
        Returns (accepted: bool, metadata: dict) with content_type, size info.
        - SKIP if Content-Type is not application/pdf (or octet-stream for ambiguous)
        - SKIP if Content-Length > 10MB
        - SKIP if URL doesn't end in .pdf and Content-Type isn't PDF
        """
        meta = {"url": url, "filtered": True, "filter_reason": None,
                "content_type": None, "content_length": None, "size_mb": None}

        try:
            req = urllib.request.Request(url, method="HEAD")
            req.add_header("User-Agent", "Mozilla/5.0 (compatible; NomosBot/1.0)")
            with urllib.request.urlopen(req, timeout=15, context=_ssl_ctx) as resp:
                content_type = (resp.headers.get("Content-Type", "") or "").lower().strip()
                content_length_str = resp.headers.get("Content-Length", "")
                content_length = int(content_length_str) if content_length_str.isdigit() else None

                meta["content_type"] = content_type
                meta["content_length"] = content_length
                if content_length is not None:
                    meta["size_mb"] = round(content_length / 1048576, 2)

                is_pdf_url = url.lower().rstrip("/").endswith(".pdf")
                is_pdf_type = "application/pdf" in content_type
                is_octet = "application/octet-stream" in content_type

                # Accept: PDF content type, or octet-stream (ambiguous) for .pdf URLs
                if not is_pdf_type and not (is_octet and is_pdf_url):
                    if not is_pdf_url:
                        meta["filter_reason"] = "not_pdf"
                        size_str = f"{meta['size_mb']}MB" if meta["size_mb"] is not None else "unknown"
                        _log(f"SKIP: {url} (size: {size_str}, type: {content_type})", "SKIP")
                        return False, meta

                # Check size limit
                if content_length is not None and content_length > MAX_PDF_SIZE:
                    meta["filter_reason"] = "too_large"
                    _log(f"SKIP: {url} (size: {meta['size_mb']}MB, type: {content_type})", "SKIP")
                    return False, meta

                # Accepted
                meta["filtered"] = False
                size_str = f"{meta['size_mb']}MB" if meta["size_mb"] is not None else "unknown"
                _log(f"OK: {url} (size: {size_str})", "OK")
                return True, meta

        except urllib.error.HTTPError as e:
            meta["filter_reason"] = f"http_error_{e.code}"
            _log(f"SKIP: {url} (HEAD HTTP {e.code})", "SKIP")
            return False, meta
        except Exception as e:
            # On HEAD failure (timeout, DNS, etc.), accept the URL anyway
            # — better to let Docling try than to silently drop
            meta["filter_reason"] = f"head_failed: {type(e).__name__}"
            meta["filtered"] = False
            _log(f"OK: {url} (HEAD failed: {type(e).__name__}, accepting anyway)", "WARN")
            return True, meta

    def _push_to_redis_queue(self, sector, accepted_docs):
        """
        Push accepted document URLs to Redis queue for Docling processing.
        Uses Upstash REST API (VM can't resolve Upstash DNS via redis:// but
        HTTPS works via IPv4 monkey-patch).
        Queue name: docling:queue:{sector}
        """
        if not accepted_docs:
            return

        token = UPSTASH_REDIS_REST_TOKEN
        if not token:
            _log("Redis unavailable, skipping queue push (UPSTASH_REDIS_REST_TOKEN not set)", "WARN")
            return

        queued = 0
        queue_name = f"docling:queue:{sector}"

        try:
            # Try importing redis module first
            try:
                import redis as redis_mod
                redis_url = os.environ.get("REDIS_URL", "")
                if redis_url:
                    r = redis_mod.from_url(redis_url, socket_timeout=10,
                                           socket_connect_timeout=10)
                    for doc in accepted_docs:
                        payload = json.dumps({
                            "url": doc["url"],
                            "sector": sector,
                            "title": doc.get("title", ""),
                            "discovered_at": _ts(),
                        }, ensure_ascii=False)
                        r.rpush(queue_name, payload)
                        queued += 1
                    _log(f"Queued {queued} docs to Redis {queue_name}", "OK")
                    return
            except Exception:
                pass  # Fall through to Upstash REST API

            # Upstash REST API fallback
            for doc in accepted_docs:
                payload = json.dumps({
                    "url": doc["url"],
                    "sector": sector,
                    "title": doc.get("title", ""),
                    "discovered_at": _ts(),
                }, ensure_ascii=False)

                # Upstash REST: POST with JSON body using pipeline command
                rest_url = f"{UPSTASH_REDIS_REST_URL}"
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                }
                # Upstash REST API expects array of command parts
                cmd_body = json.dumps(["RPUSH", queue_name, payload])
                status, body, err = _http_request(
                    rest_url, method="POST", data=cmd_body,
                    headers=headers, timeout=15,
                )
                if status == 200 and not err:
                    queued += 1
                else:
                    _log(f"Redis REST push failed: {err or f'HTTP {status}'}", "WARN")
                    break  # Stop trying on first failure

            if queued > 0:
                _log(f"Queued {queued} docs to Redis {queue_name}", "OK")
            else:
                _log("Redis unavailable, skipping queue push", "WARN")

        except Exception as e:
            _log(f"Redis unavailable, skipping queue push ({type(e).__name__}: {e})", "WARN")

    def _exa_search(self, query, sector):
        """Execute an Exa.AI search and return results."""
        payload = {
            "query": query,
            "numResults": 8,
            "type": "auto",
            "contents": {"text": True},
        }

        status, body, err = _http_request(
            EXA_URL, method="POST", data=payload,
            headers={"Content-Type": "application/json", "x-api-key": EXA_API_KEY},
            timeout=60,
        )

        if err or status != 200:
            _log(f"[{sector}] Exa.AI error for '{query[:40]}...': {err or f'HTTP {status}'}", "ERROR")
            return []

        try:
            data = json.loads(body)
            return data.get("results", [])
        except json.JSONDecodeError:
            _log(f"[{sector}] Invalid JSON from Exa.AI", "ERROR")
            return []

    def discover_sector(self, sector):
        """Run all Tavily queries for a sector, return list of new documents."""
        queries = SECTOR_QUERIES.get(sector, [])
        if self.max_queries > 0:
            queries = queries[:self.max_queries]

        _log(f"{'='*60}", "STAGE")
        _log(f"SECTOR: {sector.upper()} | {len(queries)} queries", "STAGE")
        _log(f"{'='*60}", "STAGE")

        new_docs = []
        seen_urls = {d["url"] for d in self.docs_db["sectors"].get(sector, [])}
        seen_hashes = set()

        for qi, query in enumerate(queries):
            _log(f"[{sector}] [{qi+1}/{len(queries)}] Query: \"{query[:60]}...\"")

            results = self._exa_search(query, sector)
            valid_count = 0

            for result in results:
                url = result.get("url", "")
                title = result.get("title", "")[:150]
                raw_content = result.get("raw_content", "") or ""
                content = result.get("content", "") or ""

                # Use raw_content if available, fall back to content
                # Exa.AI returns text in result["text"]; also check raw_content/content for compat
                exa_text = result.get("text", "") or ""
                text = exa_text if exa_text else (raw_content if len(raw_content) > len(content) else content)
                text = clean_web_content(text)

                if not text or len(text) < MIN_CONTENT_LENGTH:
                    continue
                if url in seen_urls:
                    continue

                # Deduplicate by content hash
                ch = _content_hash(text[:500])
                if ch in seen_hashes:
                    continue
                seen_hashes.add(ch)
                seen_urls.add(url)

                # ─── PDF size/format filter (HEAD request) ────────────
                is_pdf_url = url.lower().rstrip("/").endswith(".pdf")
                accepted, filter_meta = self._filter_url_by_head(url) if is_pdf_url else (True, {})

                domain = extract_domain(url)
                doc_entry = {
                    "url": url,
                    "title": title,
                    "domain": domain,
                    "content": text[:MAX_CONTENT_FOR_QA],
                    "content_length": len(text),
                    "query": query,
                    "sector": sector,
                    "hash": _url_hash(url),
                    "content_hash": ch,
                    "discovered_at": _ts(),
                    "qa_generated": False,
                    "qa_count": 0,
                    "pdf_filter": filter_meta if filter_meta else None,
                    "pdf_accepted": accepted,
                }

                if not accepted:
                    # Document failed PDF filter — record it but don't count as valid
                    doc_entry["skipped"] = True
                    self.docs_db["sectors"][sector].append(doc_entry)
                    continue

                new_docs.append(doc_entry)
                self.docs_db["sectors"][sector].append(doc_entry)
                valid_count += 1

            if valid_count > 0:
                _log(f"[{sector}] Found {valid_count} new docs from '{query[:40]}...'", "OK")

            # Rate limit Exa.AI
            time.sleep(EXA_DELAY)

        self.save()

        # ─── Push accepted docs to Redis queue for Docling ────────────
        pdf_docs = [d for d in new_docs if d.get("pdf_accepted", True)
                     and d["url"].lower().rstrip("/").endswith(".pdf")]
        if pdf_docs:
            self._push_to_redis_queue(sector, pdf_docs)

        return new_docs

    def discover_all(self):
        """Discover documents for all configured sectors."""
        _log("=" * 70, "STAGE")
        _log("PHASE 1: EXPERT DOCUMENT DISCOVERY (Exa.AI)", "STAGE")
        _log("=" * 70, "STAGE")

        total_new = 0
        stats = {}

        for sector in self.sectors:
            new_docs = self.discover_sector(sector)
            total_docs = len(self.docs_db["sectors"].get(sector, []))
            stats[sector] = {"new": len(new_docs), "total": total_docs}
            total_new += len(new_docs)
            _log(f"[{sector}] +{len(new_docs)} new | {total_docs} total documents", "OK")

        _log(f"Discovery complete: +{total_new} new documents across {len(self.sectors)} sectors", "OK")
        return stats

    def get_docs_without_qa(self, sector=None):
        """Get discovered documents that don't have Q&A generated yet."""
        results = []
        sectors = [sector] if sector else self.sectors
        for s in sectors:
            for doc in self.docs_db["sectors"].get(s, []):
                if not doc.get("qa_generated", False):
                    results.append((s, doc))
        return results

    def mark_qa_generated(self, sector, url, qa_count):
        """Mark a document as having Q&A generated."""
        for doc in self.docs_db["sectors"].get(sector, []):
            if doc["url"] == url:
                doc["qa_generated"] = True
                doc["qa_count"] = qa_count
                doc["qa_generated_at"] = _ts()
                self.save()
                return True
        return False

    def stats(self):
        """Return discovery stats."""
        stats = {}
        for sector in SECTORS:
            docs = self.docs_db["sectors"].get(sector, [])
            stats[sector] = {
                "total_docs": len(docs),
                "with_qa": sum(1 for d in docs if d.get("qa_generated")),
                "without_qa": sum(1 for d in docs if not d.get("qa_generated")),
                "total_content_chars": sum(d.get("content_length", 0) for d in docs),
                "domains": list(set(d.get("domain", "") for d in docs))[:10],
            }
        return stats


# ═══════════════════════════════════════════════════════════════════════════
#  PHASE 2 — EXPERT Q&A GENERATION (LiteLLM Proxy)
# ═══════════════════════════════════════════════════════════════════════════

class ExpertQAGenerator:
    """Generates expert-grade Q&A pairs from discovered documents via LiteLLM."""

    def __init__(self):
        self.qa_db = _load_json(QA_FILE, default={"metadata": {}, "sectors": {}})
        if "sectors" not in self.qa_db:
            self.qa_db["sectors"] = {}
        for s in SECTORS:
            if s not in self.qa_db["sectors"]:
                self.qa_db["sectors"][s] = []
        self.llm_failures = 0
        self.use_groq_fallback = False

    def save(self):
        self.qa_db["metadata"]["last_updated"] = _ts()
        total = sum(len(self.qa_db["sectors"].get(s, [])) for s in SECTORS)
        self.qa_db["metadata"]["total_qa_pairs"] = total
        _save_json(QA_FILE, self.qa_db)

    def _build_system_prompt(self, sector):
        """Build a sector-specific, model-aware system prompt for Q&A generation."""
        term = SECTOR_TERMINOLOGY.get(sector, {})
        domain = term.get("domain", sector.upper())
        key_terms = ", ".join(term.get("key_terms", []))
        doc_types = ", ".join(term.get("doc_types", []))
        examples = term.get("expert_examples", [])
        examples_text = "\n".join(f"  - {ex}" for ex in examples)

        # MODEL-AWARE: explicit format instructions since smart group routes to
        # llama-70b / qwen / gemini which need structured guidance
        return f"""Tu es un generateur de questions d'evaluation expert pour un systeme RAG (Retrieval-Augmented Generation) specialise dans le secteur : {domain}.

OBJECTIF : Generer des paires question-reponse de niveau EXPERT qui testent la comprehension profonde du domaine, PAS des questions superficielles.

TERMINOLOGIE SECTORIELLE A UTILISER :
{key_terms}

TYPES DE DOCUMENTS DU SECTEUR :
{doc_types}

EXEMPLES DE QUESTIONS EXPERT ATTENDUES :
{examples_text}

REGLES STRICTES :
1. Les questions doivent tester une comprehension PROFONDE, pas un simple rappel de faits
2. Chaque reponse doit contenir des FAITS SPECIFIQUES, des chiffres, des articles de loi, ou des references techniques
3. Utiliser la TERMINOLOGIE PROFESSIONNELLE correcte du secteur
4. Les questions doivent etre en FRANCAIS (sauf si le document est en anglais)
5. Varier les niveaux de difficulte : moyen et difficile
6. Chaque question doit avoir des mots-cles de verification

FORMAT DE SORTIE (JSON STRICT — tu DOIS repondre UNIQUEMENT avec ce JSON, rien d'autre) :
```json
{{
  "questions": [
    {{
      "question": "La question experte ici",
      "expected_answer": "La reponse detaillee avec faits specifiques, chiffres, references",
      "keywords": ["mot_cle_1", "mot_cle_2", "mot_cle_3", "mot_cle_4"],
      "difficulty": "hard",
      "reasoning": "Pourquoi cette question teste la comprehension experte"
    }}
  ]
}}
```

IMPORTANT POUR LE FORMAT :
- Reponds UNIQUEMENT avec le bloc JSON, pas de texte avant ou apres
- Genere entre 2 et {MAX_QA_PER_DOC} questions par document
- Chaque question doit avoir au moins 3 mots-cles de verification
- La difficulte doit etre "medium" ou "hard"
- Le champ "reasoning" explique ce que la question teste"""

    def _build_user_prompt(self, sector, doc):
        """Build user prompt with document content."""
        title = doc.get("title", "Document inconnu")
        content = doc.get("content", "")[:MAX_CONTENT_FOR_QA]
        domain = doc.get("domain", "")

        return f"""SECTEUR : {sector.upper()}
DOCUMENT : {title}
SOURCE : {domain}
LONGUEUR : {doc.get('content_length', len(content))} caracteres

--- CONTENU DU DOCUMENT ---
{content}
--- FIN DU CONTENU ---

Genere des questions d'evaluation experte basees sur ce document.
Les questions doivent etre repondables a partir du contenu fourni.
Utilise la terminologie professionnelle du secteur {sector}.
Reponds UNIQUEMENT avec le JSON structure comme indique dans les instructions."""

    def _call_litellm(self, system_prompt, user_prompt):
        """Call LiteLLM proxy. Falls back to Groq direct if proxy is down."""
        global _groq_idx

        # Try LiteLLM proxy first
        if not self.use_groq_fallback:
            payload = {
                "model": LITELLM_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": 3000,
                "temperature": 0.4,
            }

            headers = {
                "Authorization": f"Bearer {LITELLM_KEY}",
                "Content-Type": "application/json",
            }

            status, body, err = _http_request(
                LITELLM_URL, method="POST", data=payload,
                headers=headers, timeout=LITELLM_TIMEOUT,
            )

            if status == 200 and not err:
                try:
                    data = json.loads(body)
                    content = data["choices"][0]["message"]["content"]
                    model_used = data.get("model", LITELLM_MODEL)
                    return content, model_used, None
                except (json.JSONDecodeError, KeyError, IndexError) as e:
                    return None, None, f"LiteLLM parse error: {e}"

            # LiteLLM failed — check if it's a 401/down situation
            if status in (0, 401, 403, 502, 503, 504):
                _log(f"LiteLLM proxy unavailable ({err or f'HTTP {status}'}), switching to Groq direct", "WARN")
                self.use_groq_fallback = True
            else:
                return None, None, f"LiteLLM error: {err or f'HTTP {status}: {body[:200]}'}"

        # Groq direct fallback
        if not _GROQ_KEYS:
            return None, None, "No Groq API keys configured and LiteLLM is down"

        key = _GROQ_KEYS[_groq_idx % len(_GROQ_KEYS)]
        _groq_idx += 1

        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": 3000,
            "temperature": 0.4,
        }

        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

        # Rate limit Groq (1 req/sec)
        time.sleep(1.2)

        status, body, err = _http_request(
            GROQ_URL, method="POST", data=payload,
            headers=headers, timeout=60,
        )

        if err or status != 200:
            # Try another key on 429
            if status == 429 and len(_GROQ_KEYS) > 1:
                time.sleep(3)
                key2 = _GROQ_KEYS[_groq_idx % len(_GROQ_KEYS)]
                _groq_idx += 1
                headers["Authorization"] = f"Bearer {key2}"
                status, body, err = _http_request(
                    GROQ_URL, method="POST", data=payload,
                    headers=headers, timeout=60,
                )
                if err or status != 200:
                    return None, None, f"Groq retry failed: {err or f'HTTP {status}'}"
            else:
                return None, None, f"Groq error: {err or f'HTTP {status}: {body[:200]}'}"

        try:
            data = json.loads(body)
            content = data["choices"][0]["message"]["content"]
            model_used = data.get("model", GROQ_MODEL)
            return content, model_used, None
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            return None, None, f"Groq parse error: {e}"

    def _parse_qa_response(self, raw_text, sector, doc):
        """Parse LLM JSON response into structured Q&A pairs."""
        doc_hash = doc.get("hash", _url_hash(doc.get("url", "")))
        doc_title = doc.get("title", "Unknown")

        # Extract JSON from the response (handle markdown code blocks)
        json_text = raw_text.strip()
        # Remove markdown code fences if present
        if "```json" in json_text:
            match = re.search(r'```json\s*(.*?)\s*```', json_text, re.DOTALL)
            if match:
                json_text = match.group(1)
        elif "```" in json_text:
            match = re.search(r'```\s*(.*?)\s*```', json_text, re.DOTALL)
            if match:
                json_text = match.group(1)

        # Try to find JSON object in the text
        if not json_text.startswith("{"):
            brace_start = json_text.find("{")
            if brace_start >= 0:
                json_text = json_text[brace_start:]
            else:
                # Try line-by-line fallback parsing
                return self._parse_qa_fallback(raw_text, sector, doc_hash, doc_title)

        # Ensure we have the closing brace
        last_brace = json_text.rfind("}")
        if last_brace >= 0:
            json_text = json_text[:last_brace + 1]

        try:
            data = json.loads(json_text)
        except json.JSONDecodeError:
            # Try fixing common JSON issues
            json_text = json_text.replace("'", '"')
            json_text = re.sub(r',\s*}', '}', json_text)
            json_text = re.sub(r',\s*]', ']', json_text)
            try:
                data = json.loads(json_text)
            except json.JSONDecodeError:
                _log(f"[{sector}] Failed to parse JSON from LLM response", "WARN")
                return self._parse_qa_fallback(raw_text, sector, doc_hash, doc_title)

        questions_raw = data.get("questions", [])
        if not isinstance(questions_raw, list):
            return []

        qa_pairs = []
        for i, q in enumerate(questions_raw):
            if not isinstance(q, dict):
                continue
            question_text = q.get("question", "").strip()
            answer_text = q.get("expected_answer", q.get("answer", "")).strip()
            if not question_text or not answer_text:
                continue

            keywords = q.get("keywords", [])
            if isinstance(keywords, str):
                keywords = [k.strip() for k in keywords.split(",") if k.strip()]

            difficulty = q.get("difficulty", "medium").lower()
            if difficulty not in ("easy", "medium", "hard"):
                difficulty = "medium"

            qa_id = f"disc-{sector[:3]}-{doc_hash}-{i+1:02d}"
            qa_pair = {
                "id": qa_id,
                "question": question_text,
                "expected_answer": answer_text,
                "keywords": keywords[:6],
                "difficulty": difficulty,
                "reasoning": q.get("reasoning", ""),
                "sector": sector,
                "source_doc": doc_title,
                "source_url": doc.get("url", ""),
                "source_domain": doc.get("domain", ""),
                "source_hash": doc_hash,
                "generated_at": _ts(),
                "category": "expert-discovery",
            }
            qa_pairs.append(qa_pair)

        return qa_pairs

    def _parse_qa_fallback(self, raw_text, sector, doc_hash, doc_title):
        """Fallback parser: try to extract Q&A from unstructured text."""
        qa_pairs = []
        lines = raw_text.strip().split("\n")

        current_q = None
        current_a = None
        idx = 0

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Try Q: A: format
            if line.startswith("Q:") or line.startswith("Question:") or line.startswith("**Q"):
                if current_q and current_a:
                    idx += 1
                    qa_pairs.append({
                        "id": f"disc-{sector[:3]}-{doc_hash}-fb{idx:02d}",
                        "question": current_q,
                        "expected_answer": current_a,
                        "keywords": [],
                        "difficulty": "medium",
                        "reasoning": "fallback parsed",
                        "sector": sector,
                        "source_doc": doc_title,
                        "source_hash": doc_hash,
                        "generated_at": _ts(),
                        "category": "expert-discovery-fallback",
                    })
                current_q = re.sub(r'^(?:Q:|Question:|\*\*Q[^*]*\*\*:?)\s*', '', line).strip()
                current_a = None
            elif (line.startswith("A:") or line.startswith("Answer:") or line.startswith("**A")) and current_q:
                current_a = re.sub(r'^(?:A:|Answer:|\*\*A[^*]*\*\*:?)\s*', '', line).strip()

        # Don't forget the last pair
        if current_q and current_a:
            idx += 1
            qa_pairs.append({
                "id": f"disc-{sector[:3]}-{doc_hash}-fb{idx:02d}",
                "question": current_q,
                "expected_answer": current_a,
                "keywords": [],
                "difficulty": "medium",
                "reasoning": "fallback parsed",
                "sector": sector,
                "source_doc": doc_title,
                "source_hash": doc_hash,
                "generated_at": _ts(),
                "category": "expert-discovery-fallback",
            })

        return qa_pairs

    def generate_for_doc(self, sector, doc):
        """Generate expert Q&A for a single document."""
        title = doc.get("title", "Unknown")[:60]
        _log(f"[{sector}] Generating Q&A: {title}")

        content = doc.get("content", "")
        if not content or len(content) < MIN_CONTENT_LENGTH:
            _log(f"[{sector}] Content too short for Q&A generation ({len(content)} chars)", "SKIP")
            return 0

        system_prompt = self._build_system_prompt(sector)
        user_prompt = self._build_user_prompt(sector, doc)

        raw_response, model_used, error = self._call_litellm(system_prompt, user_prompt)

        if error:
            self.llm_failures += 1
            _log(f"[{sector}] LLM error: {error}", "ERROR")
            if self.llm_failures >= 5:
                _log("Too many LLM failures (5+), stopping Q&A generation", "ERROR")
                return -1  # Signal to stop
            return 0

        qa_pairs = self._parse_qa_response(raw_response, sector, doc)

        if not qa_pairs:
            _log(f"[{sector}] No valid Q&A pairs parsed from LLM response", "WARN")
            return 0

        # Deduplicate against existing Q&A
        existing_qs = {
            q["question"].lower()[:80]
            for q in self.qa_db["sectors"].get(sector, [])
        }
        new_pairs = []
        for qa in qa_pairs:
            if qa["question"].lower()[:80] not in existing_qs:
                new_pairs.append(qa)
                existing_qs.add(qa["question"].lower()[:80])

        if new_pairs:
            self.qa_db["sectors"][sector].extend(new_pairs)
            self.save()

        backend = f" (via {model_used})" if model_used else ""
        _log(f"[{sector}] Generated {len(new_pairs)} Q&A pairs from '{title}'{backend}", "OK")
        return len(new_pairs)

    def generate_all(self, discovery):
        """Generate Q&A for all docs without Q&A."""
        _log("=" * 70, "STAGE")
        _log("PHASE 2: EXPERT Q&A GENERATION (LiteLLM/Groq)", "STAGE")
        _log("=" * 70, "STAGE")

        pending = discovery.get_docs_without_qa()
        if not pending:
            _log("No documents pending Q&A generation", "SKIP")
            return {}

        _log(f"Generating Q&A for {len(pending)} documents...")

        stats = {}
        total_qa = 0

        for sector, doc in pending:
            count = self.generate_for_doc(sector, doc)

            if count == -1:
                # Too many failures, stop
                break

            if count > 0:
                discovery.mark_qa_generated(sector, doc["url"], count)
                total_qa += count

            if sector not in stats:
                stats[sector] = {"docs_processed": 0, "qa_generated": 0}
            stats[sector]["docs_processed"] += 1
            stats[sector]["qa_generated"] += max(0, count)

        _log(f"Q&A generation complete: {total_qa} new pairs from {len(pending)} documents", "OK")
        return stats

    def stats(self):
        """Return Q&A stats."""
        stats = {}
        for sector in SECTORS:
            pairs = self.qa_db["sectors"].get(sector, [])
            stats[sector] = {
                "total_qa": len(pairs),
                "hard": sum(1 for q in pairs if q.get("difficulty") == "hard"),
                "medium": sum(1 for q in pairs if q.get("difficulty") == "medium"),
                "with_keywords": sum(1 for q in pairs if len(q.get("keywords", [])) >= 3),
                "sources": len(set(q.get("source_hash", "") for q in pairs)),
            }
        return stats


# ═══════════════════════════════════════════════════════════════════════════
#  REPORTING
# ═══════════════════════════════════════════════════════════════════════════

def print_report():
    """Print comprehensive summary report."""
    docs_db = _load_json(DOCS_FILE, default={"sectors": {}})
    qa_db = _load_json(QA_FILE, default={"sectors": {}})

    print(f"\n{C.BOLD}{'='*70}{C.RESET}")
    print(f"{C.BOLD}  EXPERT DISCOVERY REPORT{C.RESET}")
    print(f"{C.BOLD}  Generated: {_ts()}{C.RESET}")
    print(f"{C.BOLD}{'='*70}{C.RESET}")

    total_docs = 0
    total_qa = 0

    for sector in SECTORS:
        docs = docs_db.get("sectors", {}).get(sector, [])
        qa_pairs = qa_db.get("sectors", {}).get(sector, [])
        total_docs += len(docs)
        total_qa += len(qa_pairs)

        with_qa = sum(1 for d in docs if d.get("qa_generated"))
        hard_qs = sum(1 for q in qa_pairs if q.get("difficulty") == "hard")
        medium_qs = sum(1 for q in qa_pairs if q.get("difficulty") == "medium")
        domains = list(set(d.get("domain", "") for d in docs))[:8]

        color = C.GREEN if len(qa_pairs) >= 10 else C.YELLOW if len(qa_pairs) > 0 else C.RED
        print(f"\n  {C.BOLD}{C.CYAN}{sector.upper()}{C.RESET}")
        print(f"    Documents:  {len(docs)} discovered, {with_qa} with Q&A")
        print(f"    Q&A Pairs:  {color}{len(qa_pairs)}{C.RESET} (hard: {hard_qs}, medium: {medium_qs})")
        print(f"    Domains:    {', '.join(domains[:5])}")

        # Show sample questions
        if qa_pairs:
            print(f"    Sample Q:   {qa_pairs[0].get('question', '')[:80]}...")

    print(f"\n  {C.BOLD}TOTALS{C.RESET}")
    print(f"    Documents:  {total_docs}")
    print(f"    Q&A Pairs:  {total_qa}")
    print(f"    Data Dir:   {DATA_DIR}")

    # Show files
    print(f"\n  {C.BOLD}FILES{C.RESET}")
    for f in [DOCS_FILE, QA_FILE, PROGRESS_FILE]:
        if f.exists():
            size = f.stat().st_size
            print(f"    {f.name}: {size:,} bytes")
        else:
            print(f"    {f.name}: (not found)")

    print(f"\n{'='*70}\n")


def save_run_history(discovery_stats, qa_stats, duration_s):
    """Append run to history file."""
    history = _load_json(HISTORY_FILE, default={"runs": []})
    if "runs" not in history:
        history["runs"] = []

    run = {
        "timestamp": _ts(),
        "duration_s": round(duration_s, 1),
        "discovery": discovery_stats,
        "qa_generation": qa_stats,
    }
    history["runs"].append(run)

    # Keep last 50 runs
    history["runs"] = history["runs"][-50:]
    _save_json(HISTORY_FILE, history)


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════

def run_cycle(sectors, max_queries=0, discover_only=False, generate_only=False, dry_run=False):
    """Run one full discovery + Q&A generation cycle."""
    start_time = time.time()

    _log("=" * 70, "STAGE")
    _log(f"EXPERT DISCOVERY CYCLE — {_ts()}", "STAGE")
    _log(f"Sectors: {', '.join(sectors)} | Max queries: {max_queries or 'all'}", "STAGE")
    _log(f"Mode: {'DRY RUN' if dry_run else 'discover-only' if discover_only else 'generate-only' if generate_only else 'FULL CYCLE'}", "STAGE")
    _log("=" * 70, "STAGE")

    discovery = TavilyDiscovery(sectors=sectors, max_queries=max_queries)
    generator = ExpertQAGenerator()

    discovery_stats = {}
    qa_stats = {}

    # Phase 1: Discovery
    if not generate_only:
        discovery_stats = discovery.discover_all()

    # Phase 2: Q&A Generation
    if not discover_only and not dry_run:
        qa_stats = generator.generate_all(discovery)

    # Summary
    duration = time.time() - start_time
    total_new_docs = sum(s.get("new", 0) for s in discovery_stats.values())
    total_new_qa = sum(s.get("qa_generated", 0) for s in qa_stats.values())

    _log("=" * 70, "STAGE")
    _log("CYCLE COMPLETE", "STAGE")
    _log("=" * 70, "STAGE")
    _log(f"Duration:     {duration:.1f}s")
    _log(f"New docs:     {total_new_docs}")
    _log(f"New Q&A:      {total_new_qa}")

    # Per-sector summary
    for sector in sectors:
        d = discovery_stats.get(sector, {})
        q = qa_stats.get(sector, {})
        total_docs = len(discovery.docs_db["sectors"].get(sector, []))
        total_qa = len(generator.qa_db["sectors"].get(sector, []))
        _log(f"  {sector.upper():12s}: {d.get('new', 0):3d} new docs ({total_docs} total), {q.get('qa_generated', 0):3d} new Q&A ({total_qa} total)")

    _log(f"Data saved:   {DATA_DIR}")

    # Save run history
    save_run_history(discovery_stats, qa_stats, duration)

    return total_new_docs, total_new_qa


def main():
    parser = argparse.ArgumentParser(
        description="Expert Discovery — Continuous expert document & Q&A discovery engine"
    )
    parser.add_argument(
        "--sector", default="all",
        choices=["finance", "btp", "juridique", "industrie", "all"],
        help="Sector to discover (default: all)"
    )
    parser.add_argument(
        "--loop", type=int, default=0,
        help="Loop interval in seconds (0 = single run)"
    )
    parser.add_argument(
        "--max-queries", type=int, default=0,
        help="Limit number of Tavily queries per sector (0 = all)"
    )
    parser.add_argument(
        "--discover-only", action="store_true",
        help="Only discover documents, skip Q&A generation"
    )
    parser.add_argument(
        "--generate-only", action="store_true",
        help="Only generate Q&A from already discovered docs"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Discover only, no LLM calls"
    )
    parser.add_argument(
        "--report", action="store_true",
        help="Show summary report and exit"
    )
    args = parser.parse_args()

    # Report mode
    if args.report:
        print_report()
        return

    # Validate environment
    if not TAVILY_API_KEY and not args.generate_only:
        print(f"{C.RED}ERROR: TAVILY_API_KEY not set. Run: source .env.local{C.RESET}")
        sys.exit(1)

    if not args.discover_only and not args.dry_run:
        if not _GROQ_KEYS:
            _log("WARNING: No Groq API keys found. LiteLLM proxy must be UP for Q&A generation.", "WARN")

    sectors = SECTORS if args.sector == "all" else [args.sector]

    print(f"\n{C.BOLD}{C.CYAN}")
    print(f"  ╔══════════════════════════════════════════════════════════════╗")
    print(f"  ║         EXPERT DISCOVERY ENGINE v1.0                        ║")
    print(f"  ║         Tavily Search + LiteLLM Q&A Generation             ║")
    print(f"  ╚══════════════════════════════════════════════════════════════╝{C.RESET}\n")

    if args.loop > 0:
        cycle = 0
        while True:
            cycle += 1
            _log(f"{'='*40} CYCLE {cycle} {'='*40}", "STAGE")
            try:
                new_docs, new_qa = run_cycle(
                    sectors,
                    max_queries=args.max_queries,
                    discover_only=args.discover_only,
                    generate_only=args.generate_only,
                    dry_run=args.dry_run,
                )
                _log(f"Cycle {cycle} done: +{new_docs} docs, +{new_qa} Q&A. Sleeping {args.loop}s...", "OK")
            except KeyboardInterrupt:
                _log("Interrupted by user", "WARN")
                break
            except Exception as e:
                _log(f"Cycle {cycle} error: {e}", "ERROR")
                traceback.print_exc()

            try:
                time.sleep(args.loop)
            except KeyboardInterrupt:
                _log("Interrupted during sleep", "WARN")
                break
    else:
        try:
            run_cycle(
                sectors,
                max_queries=args.max_queries,
                discover_only=args.discover_only,
                generate_only=args.generate_only,
                dry_run=args.dry_run,
            )
        except KeyboardInterrupt:
            _log("Interrupted by user", "WARN")
        except Exception as e:
            _log(f"Fatal error: {e}", "ERROR")
            traceback.print_exc()
            sys.exit(1)

    # Print final report
    print_report()


if __name__ == "__main__":
    main()
