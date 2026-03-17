#!/usr/bin/env python3
"""
Tavily Mass Ingest — Search web for BTP + Industrie domain content and upsert to E5.

Uses Tavily's advanced search to find authoritative French-language content,
chunks the raw_content, and upserts to Pinecone E5 integrated embedding index.

Usage:
  source .env.local
  python3 ops/tavily-mass-ingest.py --sector btp
  python3 ops/tavily-mass-ingest.py --sector industrie
  python3 ops/tavily-mass-ingest.py --sector all
  python3 ops/tavily-mass-ingest.py --sector btp --dry-run
  python3 ops/tavily-mass-ingest.py --sector btp --max-queries 5
"""

import argparse
import hashlib
import json
import os
import re
import socket
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# ── Force line buffering for nohup ────────────────────────────
try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

# ── Force IPv4 globally ──────────────────────────────────────
_original_getaddrinfo = socket.getaddrinfo
def _ipv4_getaddrinfo(host, port, family=0, type_=0, proto=0, flags=0):
    return _original_getaddrinfo(host, port, socket.AF_INET, type_, proto, flags)
socket.getaddrinfo = _ipv4_getaddrinfo

# ── Config ────────────────────────────────────────────────────
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY", "")
PINECONE_HOST = "https://sectors-e5-multilingual-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
NAMESPACE = "sectors"
UPSERT_URL = f"{PINECONE_HOST}/records/namespaces/{NAMESPACE}/upsert"
TAVILY_URL = "https://api.tavily.com/search"

PROGRESS_DIR = Path(os.path.expanduser("~/mon-ipad/data/ingest"))
PROGRESS_FILE = PROGRESS_DIR / "tavily-mass-progress.json"

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
MIN_CHUNK_LEN = 80
MAX_TEXT_FOR_E5 = 1500  # E5 integrated max useful length

TAVILY_DELAY = 1.2      # seconds between Tavily requests (rate limit)
PINECONE_DELAY = 0.025   # seconds between Pinecone upserts (50 req/sec)

# ── Search Queries ────────────────────────────────────────────
BTP_QUERIES = [
    "DTU 31.2 ossature bois construction",
    "permis de construire étapes procédure",
    "normes parasismiques Eurocode 8 France",
    "CCTP marché public travaux rédaction",
    "RE2020 obligations réglementation environnementale",
    "DTU couverture toiture étanchéité",
    "fondations profondes techniques pieux",
    "béton armé eurocode 2 calcul",
    "isolation thermique bâtiment RT2012",
    "sécurité chantier BTP réglementation",
    "AFNOR normes construction bâtiment",
    "diagnostic amiante plomb DPE",
    "marché public BOAMP appel offre",
    "assurance décennale garantie construction",
    "plan local urbanisme PLU permis",
]

INDUSTRIE_QUERIES = [
    "ISO 9001 démarche qualité certification",
    "AMDEC analyse défaillance criticité",
    "fiche données sécurité FDS rédaction",
    "lean manufacturing principes gaspillage",
    "maintenance préventive planification équipement",
    "ISO 14001 environnement management",
    "Six Sigma DMAIC amélioration continue",
    "HACCP sécurité alimentaire",
    "norme ISO 45001 santé sécurité travail",
    "gestion stock méthode kanban",
    "TPM maintenance productive totale",
    "audit qualité processus certification",
    "REACH substances chimiques réglementation",
    "contrôle non destructif CND ultrasons",
    "automatisation industrielle 4.0 IoT",
]

FINANCE_QUERIES = [
    "IFRS normes comptables internationales",
    "ratio financier analyse entreprise",
    "bilan comptable actif passif explication",
    "marché obligataire taux d intérêt France",
    "gestion de portefeuille diversification risque",
    "analyse fondamentale actions bourse",
    "réglementation bancaire Bâle III IV",
    "fiscalité entreprise impôt société France",
    "fusion acquisition due diligence",
    "trésorerie entreprise cash flow gestion",
    "audit financier commissaire aux comptes",
    "crédit scoring notation financière",
    "assurance vie épargne placement",
    "fintech blockchain finance décentralisée",
    "ESG investissement responsable critères",
]

JURIDIQUE_QUERIES = [
    "code civil responsabilité contractuelle articles",
    "droit du travail licenciement procédure France",
    "RGPD protection données personnelles conformité",
    "droit des sociétés SAS SARL statuts",
    "propriété intellectuelle brevet marque dépôt",
    "contentieux commercial tribunal procédure",
    "droit immobilier bail commercial résiliation",
    "droit fiscal contrôle redressement",
    "droit de la concurrence pratiques anticoncurrentielles",
    "procédure collective sauvegarde liquidation judiciaire",
    "contrat de travail clause non concurrence",
    "droit administratif marché public recours",
    "médiation arbitrage résolution litiges",
    "droit pénal des affaires abus de biens sociaux",
    "conformité compliance entreprise loi Sapin II",
]

SECTOR_QUERIES = {
    "btp": BTP_QUERIES,
    "industrie": INDUSTRIE_QUERIES,
    "finance": FINANCE_QUERIES,
    "juridique": JURIDIQUE_QUERIES,
}


# ── Utilities ─────────────────────────────────────────────────

def short_hash(text: str) -> str:
    """8-char hash of text for deduplication."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:8]


def clean_text(text: str) -> str:
    """Clean raw web content for chunking."""
    if not text:
        return ""
    # Remove excessive whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    # Remove common web artifacts
    text = re.sub(r'Cookie[s]?.*?(?:accepter|refuser|paramétrer).*?\n', '', text, flags=re.IGNORECASE)
    text = re.sub(r'(?:Partager|Share)[\s:]*(?:Facebook|Twitter|LinkedIn|Email).*?\n', '', text, flags=re.IGNORECASE)
    text = re.sub(r'(?:©|Copyright).*?\d{4}.*?\n', '', text, flags=re.IGNORECASE)
    # Remove navigation-like lines (very short lines that are just menu items)
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        # Keep lines that are substantive (>20 chars or part of a list)
        if len(stripped) > 20 or stripped.startswith(('-', '•', '*', '–')) or re.match(r'^\d+[\.\)]', stripped):
            cleaned_lines.append(line)
        elif len(stripped) > 5 and not re.match(r'^(Menu|Accueil|Contact|Recherche|Connexion|Inscription|Panier|Mon compte)$', stripped, re.IGNORECASE):
            cleaned_lines.append(line)
    text = '\n'.join(cleaned_lines)
    return text.strip()


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
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
            # Try sentence boundary
            for sep in ['. ', '.\n', '? ', '!\n', ';\n']:
                sent_break = candidate.rfind(sep)
                if sent_break > chunk_size * 0.4:
                    end = start + sent_break + len(sep)
                    break

        chunk = text[start:end].strip()
        if len(chunk) >= MIN_CHUNK_LEN:
            chunks.append(chunk)

        # Move forward with overlap
        start = end - overlap
        if start <= (end - chunk_size):  # prevent infinite loop
            start = end

    return chunks


def extract_domain(url: str) -> str:
    """Extract domain name from URL."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "")
        return domain
    except Exception:
        return "unknown"


# ── API Functions ─────────────────────────────────────────────

def tavily_search(query: str) -> list[dict]:
    """Search Tavily and return results with raw_content."""
    payload = json.dumps({
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "advanced",
        "max_results": 10,
        "include_raw_content": True,
    }).encode("utf-8")

    req = urllib.request.Request(
        TAVILY_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("results", [])
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8")[:200]
        except Exception:
            pass
        print(f"  [ERROR] Tavily HTTP {e.code}: {body}")
        return []
    except Exception as e:
        print(f"  [ERROR] Tavily request failed: {e}")
        return []


def pinecone_upsert(record_id: str, text: str, sector: str, source: str) -> bool:
    """Upsert a single record to Pinecone E5 integrated embedding index."""
    # Truncate text for E5
    if len(text) > MAX_TEXT_FOR_E5:
        text = text[:MAX_TEXT_FOR_E5]

    payload = json.dumps({
        "_id": record_id,
        "text": text,
        "sector": sector,
        "source": source,
    }).encode("utf-8")

    req = urllib.request.Request(
        UPSERT_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Api-Key": PINECONE_API_KEY,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return True
    except urllib.error.HTTPError as e:
        if e.code == 409:
            # Already exists — skip silently
            return True
        body = ""
        try:
            body = e.read().decode("utf-8")[:200]
        except Exception:
            pass
        print(f"  [ERROR] Pinecone upsert {record_id}: HTTP {e.code} {body}")
        return False
    except Exception as e:
        print(f"  [ERROR] Pinecone upsert {record_id}: {e}")
        return False


def get_index_stats() -> dict:
    """Get current E5 index vector count."""
    payload = json.dumps({}).encode("utf-8")
    req = urllib.request.Request(
        f"{PINECONE_HOST}/describe_index_stats",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Api-Key": PINECONE_API_KEY,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  [WARN] Could not get index stats: {e}")
        return {}


# ── Main Ingestion Logic ─────────────────────────────────────

def load_progress() -> dict:
    """Load progress file."""
    if PROGRESS_FILE.exists():
        try:
            return json.loads(PROGRESS_FILE.read_text())
        except Exception:
            pass
    return {
        "started": datetime.now(timezone.utc).isoformat(),
        "sectors": {},
    }


def save_progress(progress: dict):
    """Save progress file."""
    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    progress["last_updated"] = datetime.now(timezone.utc).isoformat()
    PROGRESS_FILE.write_text(json.dumps(progress, indent=2, ensure_ascii=False))


def save_chunk_jsonl(sector: str, chunk: str, source: str, title: str, url: str):
    """Save chunk as JSONL record for Neo4j enrichment."""
    datasets_dir = Path.home() / "rag-data-ingestion" / "datasets" / "sectors" / sector
    datasets_dir.mkdir(parents=True, exist_ok=True)
    jsonl_file = datasets_dir / "tavily_web.jsonl"
    record = {
        "id": hashlib.md5(chunk[:200].encode()).hexdigest()[:16],
        "dataset": "tavily_web",
        "sector": sector,
        "text": chunk,
        "title": title,
        "source": source,
        "url": url,
    }
    with open(jsonl_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def ingest_sector(sector: str, queries: list[str], dry_run: bool = False, max_queries: int = 0) -> dict:
    """Run all queries for a sector, chunk results, upsert to E5."""
    stats = {
        "sector": sector,
        "queries_run": 0,
        "queries_total": len(queries),
        "results_found": 0,
        "results_with_content": 0,
        "chunks_created": 0,
        "chunks_upserted": 0,
        "chunks_failed": 0,
        "urls_processed": [],
        "errors": [],
        "started": datetime.now(timezone.utc).isoformat(),
    }

    if max_queries > 0:
        queries = queries[:max_queries]
        stats["queries_total"] = len(queries)

    seen_urls = set()
    seen_hashes = set()

    print(f"\n{'='*70}")
    print(f"  SECTOR: {sector.upper()}")
    print(f"  Queries: {len(queries)}")
    print(f"  Mode: {'DRY RUN' if dry_run else 'LIVE UPSERT'}")
    print(f"{'='*70}\n")

    for qi, query in enumerate(queries):
        print(f"\n[{qi+1}/{len(queries)}] Query: \"{query}\"")
        stats["queries_run"] += 1

        results = tavily_search(query)
        print(f"  Found {len(results)} results")
        stats["results_found"] += len(results)

        if not results:
            time.sleep(TAVILY_DELAY)
            continue

        for ri, result in enumerate(results):
            url = result.get("url", "")
            title = result.get("title", "")[:100]
            raw_content = result.get("raw_content", "") or ""
            content = result.get("content", "") or ""

            # Use raw_content if available, fall back to content
            text = raw_content if len(raw_content) > len(content) else content

            if not text or len(text) < MIN_CHUNK_LEN:
                continue

            # Skip duplicate URLs
            if url in seen_urls:
                continue
            seen_urls.add(url)
            stats["results_with_content"] += 1

            domain = extract_domain(url)
            cleaned = clean_text(text)
            chunks = chunk_text(cleaned)

            if not chunks:
                continue

            print(f"  [{ri}] {title[:55]} | {len(cleaned):,} chars → {len(chunks)} chunks")
            stats["urls_processed"].append({
                "url": url[:200],
                "title": title,
                "domain": domain,
                "text_len": len(cleaned),
                "chunks": len(chunks),
            })

            for ci, chunk in enumerate(chunks):
                chunk_hash = short_hash(chunk)

                # Skip duplicate content
                if chunk_hash in seen_hashes:
                    continue
                seen_hashes.add(chunk_hash)

                record_id = f"tavily-{sector}-{chunk_hash}-{ci:03d}"
                source = f"tavily-{domain}"

                stats["chunks_created"] += 1

                if dry_run:
                    stats["chunks_upserted"] += 1
                    continue

                ok = pinecone_upsert(record_id, chunk, sector, source)
                if ok:
                    stats["chunks_upserted"] += 1
                    # Also save as JSONL for Neo4j enrichment
                    try:
                        save_chunk_jsonl(sector, chunk, source, title, url)
                    except Exception:
                        pass
                else:
                    stats["chunks_failed"] += 1
                    stats["errors"].append(record_id)

                time.sleep(PINECONE_DELAY)

        # Rate limit Tavily
        time.sleep(TAVILY_DELAY)

    stats["finished"] = datetime.now(timezone.utc).isoformat()
    stats["duration_s"] = round(
        (datetime.fromisoformat(stats["finished"]) - datetime.fromisoformat(stats["started"])).total_seconds(), 1
    )

    print(f"\n{'─'*50}")
    print(f"  SECTOR {sector.upper()} COMPLETE")
    print(f"  Queries:       {stats['queries_run']}/{stats['queries_total']}")
    print(f"  Results:       {stats['results_found']} found, {stats['results_with_content']} with content")
    print(f"  Chunks:        {stats['chunks_created']} created, {stats['chunks_upserted']} upserted, {stats['chunks_failed']} failed")
    print(f"  Duration:      {stats['duration_s']}s")
    print(f"  Unique URLs:   {len(seen_urls)}")
    print(f"{'─'*50}")

    return stats


def main():
    parser = argparse.ArgumentParser(description="Tavily mass ingest for BTP + Industrie sectors")
    parser.add_argument("--sector", required=True, choices=["btp", "industrie", "finance", "juridique", "all"],
                        help="Sector to ingest (btp, industrie, or all)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without upserting")
    parser.add_argument("--max-queries", type=int, default=0, help="Limit number of queries (0=all)")
    args = parser.parse_args()

    if not TAVILY_API_KEY:
        print("ERROR: TAVILY_API_KEY not set. Run: source .env.local")
        sys.exit(1)
    if not PINECONE_API_KEY:
        print("ERROR: PINECONE_API_KEY not set. Run: source .env.local")
        sys.exit(1)

    # Pre-flight: show index stats
    print("=" * 70)
    print("  TAVILY MASS INGEST — Sector Domain Content")
    print(f"  Started: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 70)

    stats_before = get_index_stats()
    vectors_before = stats_before.get("totalVectorCount", "?")
    print(f"\n  E5 Index: {vectors_before} vectors (before)\n")

    progress = load_progress()
    sectors_to_run = list(SECTOR_QUERIES.keys()) if args.sector == "all" else [args.sector]

    all_stats = {}
    for sector in sectors_to_run:
        queries = SECTOR_QUERIES[sector]
        sector_stats = ingest_sector(sector, queries, dry_run=args.dry_run, max_queries=args.max_queries)
        all_stats[sector] = sector_stats
        progress["sectors"][sector] = sector_stats

    save_progress(progress)

    # Post-flight: show final index stats
    if not args.dry_run:
        time.sleep(2)  # wait for index to update
    stats_after = get_index_stats()
    vectors_after = stats_after.get("totalVectorCount", "?")

    print(f"\n{'='*70}")
    print(f"  FINAL SUMMARY")
    print(f"{'='*70}")
    print(f"  E5 Vectors: {vectors_before} → {vectors_after}")
    if isinstance(vectors_before, int) and isinstance(vectors_after, int):
        print(f"  Net new vectors: +{vectors_after - vectors_before}")
    total_chunks = sum(s["chunks_upserted"] for s in all_stats.values())
    total_errors = sum(s["chunks_failed"] for s in all_stats.values())
    print(f"  Total chunks upserted: {total_chunks}")
    print(f"  Total errors: {total_errors}")
    print(f"  Progress saved: {PROGRESS_FILE}")
    print(f"  Finished: {datetime.now(timezone.utc).isoformat()}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
