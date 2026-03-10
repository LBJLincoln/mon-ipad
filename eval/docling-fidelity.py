#!/usr/bin/env python3
"""
Docling Fidelity Test Suite — Measures extraction quality of the Docling HF Space
on real sector documents (Finance, BTP, Juridique, Industrie).

Tests text completeness, table detection, page consistency, chunk quality,
and processing speed. Computes a weighted fidelity score per document.

Usage:
  python3 eval/docling-fidelity.py                      # Test with default URLs
  python3 eval/docling-fidelity.py --url "https://..."   # Test specific URL
  python3 eval/docling-fidelity.py --report              # Show latest results
  python3 eval/docling-fidelity.py --sector finance      # Test one sector only
  python3 eval/docling-fidelity.py --timeout 180         # Custom timeout per doc
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    print("FATAL: 'requests' library required. Install with: pip install requests")
    sys.exit(1)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCLING_BASE = os.environ.get(
    "DOCLING_URL", "https://lbjlincoln-nomos-docling-api.hf.space"
)
RESULTS_PATH = os.path.join(REPO_ROOT, "data", "eval", "docling-fidelity.json")
DEFAULT_TIMEOUT = 120  # seconds per document

# ── Fidelity score weights ──────────────────────────────────────────────
W_TEXT = 0.4
W_TABLE = 0.2
W_PAGE = 0.2
W_CHUNK = 0.2
FIDELITY_TARGET = 0.80

# ── Default test documents (real sector PDFs from Tavily research) ──────
# Selected from sectors/real-documents-to-ingest.json — high-priority, official PDFs
DEFAULT_TEST_DOCS = [
    {
        "url": "https://www.banque-france.fr/system/files/2025-04/Methodologie_situation_entreprises.pdf",
        "sector": "finance",
        "title": "Situation financiere des entreprises en France — Banque de France",
        "expected_tables": 1,  # methodology doc, likely has some tables
        "expected_min_pages": 2,
    },
    {
        "url": "https://totalenergies.com/sites/default/files/atoms/files/rapport-financier-annuel-2018-total-capital-international.pdf",
        "sector": "finance",
        "title": "Rapport financier annuel 2018 — TotalEnergies",
        "expected_tables": 5,  # annual report, many financial tables
        "expected_min_pages": 10,
    },
    {
        "url": "https://www.ecologie.gouv.fr/sites/default/files/documents/guide_re2020_version_janvier_2024.pdf",
        "sector": "btp",
        "title": "Guide RE 2020 — Ministere de la Transition ecologique",
        "expected_tables": 2,
        "expected_min_pages": 5,
    },
    {
        "url": "https://boutique.cstb.fr/getattachment/9ba6ea42-de49-44a5-b56c-b5e567cc035b/Liste-DTU-Fevrier-2026.pdf",
        "sector": "btp",
        "title": "Liste des DTU en vigueur — CSTB (Fevrier 2026)",
        "expected_tables": 3,  # DTU list is essentially a big table
        "expected_min_pages": 5,
    },
    {
        "url": "https://www.medef.com/uploads/media/default/0020/01/14977-14970-medef-guide-rebond-web.pdf",
        "sector": "juridique",
        "title": "Prevention des difficultes des entreprises — MEDEF",
        "expected_tables": 1,
        "expected_min_pages": 5,
    },
    {
        "url": "https://www.bts-g-pme.com/cours/d1-grcf/c4-contrat-commerciaux/c4-a-contrat-commerciaux.pdf",
        "sector": "juridique",
        "title": "Contrats commerciaux — BTS G-PME",
        "expected_tables": 1,
        "expected_min_pages": 2,
    },
    {
        "url": "https://www.strategie-plan.gouv.fr/files/files/Publications/2020/politiques%20industrielles/fs-2020-rapport-politique_industrielle-novembre.pdf",
        "sector": "industrie",
        "title": "Rapport politiques industrielles en France — France Strategie",
        "expected_tables": 3,
        "expected_min_pages": 10,
    },
]


# ── Health check ────────────────────────────────────────────────────────

def check_health(timeout=15):
    """Check if the Docling HF Space is up and responding."""
    url = f"{DOCLING_BASE}/health"
    try:
        resp = requests.get(url, timeout=timeout)
        if resp.status_code == 200:
            return True, resp.json() if resp.text.strip() else {}
        return False, {"status_code": resp.status_code}
    except requests.exceptions.ConnectionError:
        return False, {"error": "Connection refused — Space may be sleeping"}
    except requests.exceptions.Timeout:
        return False, {"error": f"Timeout after {timeout}s — Space cold starting?"}
    except Exception as e:
        return False, {"error": str(e)[:200]}


# ── Document conversion ────────────────────────────────────────────────

def convert_url(url, timeout=DEFAULT_TIMEOUT):
    """Send a URL to Docling for conversion. Returns (result_dict, elapsed_s, error)."""
    endpoint = f"{DOCLING_BASE}/convert-url"
    payload = {"url": url}
    try:
        start = time.time()
        resp = requests.post(endpoint, json=payload, timeout=timeout)
        elapsed = time.time() - start

        if resp.status_code == 200:
            data = resp.json()
            return data, elapsed, None
        elif resp.status_code == 503:
            return None, elapsed, f"503 Service Unavailable — Space cold starting (waited {elapsed:.1f}s)"
        elif resp.status_code == 504:
            return None, elapsed, f"504 Gateway Timeout — PDF too large or Space overloaded"
        else:
            body_preview = resp.text[:300] if resp.text else "(empty)"
            return None, elapsed, f"HTTP {resp.status_code}: {body_preview}"
    except requests.exceptions.Timeout:
        return None, timeout, f"Request timed out after {timeout}s"
    except requests.exceptions.ConnectionError:
        return None, 0, "Connection refused — Space may be down"
    except Exception as e:
        return None, 0, str(e)[:300]


# ── Fidelity scoring ───────────────────────────────────────────────────

def score_text_completeness(data):
    """
    Score 0.0-1.0: Is the extracted text reasonably complete?
    Heuristic: >100 chars per page on average = good extraction.
    """
    full_text = data.get("full_text", "")
    pages = data.get("pages", [])
    num_pages = data.get("num_pages", 0) or max(len(pages), 1)

    if not full_text:
        return 0.0

    chars_per_page = len(full_text) / num_pages

    # Scoring tiers:
    # >= 500 chars/page = 1.0 (rich content)
    # >= 200 chars/page = 0.8 (decent)
    # >= 100 chars/page = 0.6 (sparse but present)
    # >= 50  chars/page = 0.3 (very sparse)
    # < 50   chars/page = 0.1 (almost empty)
    if chars_per_page >= 500:
        score = 1.0
    elif chars_per_page >= 200:
        score = 0.8
    elif chars_per_page >= 100:
        score = 0.6
    elif chars_per_page >= 50:
        score = 0.3
    else:
        score = 0.1

    # Bonus: check that individual pages have content (not all in one blob)
    if pages:
        pages_with_text = sum(1 for p in pages if len(p.get("text", "")) > 20)
        page_coverage = pages_with_text / len(pages)
        # Blend: 70% chars-per-page score + 30% page coverage
        score = score * 0.7 + page_coverage * 0.3

    return round(min(score, 1.0), 3)


def score_table_detection(data, expected_tables=0):
    """
    Score 0.0-1.0: Are tables detected?
    If expected_tables > 0, score based on how close we got.
    If expected_tables == 0, give 1.0 if any tables found, 0.5 otherwise.
    """
    num_tables = data.get("num_tables", 0)
    tables = data.get("tables", [])
    actual = max(num_tables, len(tables))

    if expected_tables <= 0:
        # No expectation — give credit for finding any tables
        return 1.0 if actual > 0 else 0.5

    if actual == 0:
        return 0.0

    # Ratio of found vs expected (cap at 1.0)
    ratio = min(actual / expected_tables, 1.0)

    # Also check table quality — tables should have some content
    if tables:
        non_empty = sum(1 for t in tables if t and (
            isinstance(t, dict) and (t.get("text", "") or t.get("html", "") or t.get("data"))
            or isinstance(t, str) and len(t) > 5
        ))
        quality = non_empty / len(tables) if tables else 0
        return round(ratio * 0.6 + quality * 0.4, 3)

    return round(ratio, 3)


def score_page_consistency(data):
    """
    Score 0.0-1.0: Does num_pages match len(pages)?
    Also checks that pages are numbered correctly.
    """
    num_pages = data.get("num_pages", 0)
    pages = data.get("pages", [])

    if num_pages == 0 and len(pages) == 0:
        return 0.0  # Nothing extracted

    if num_pages == 0 or len(pages) == 0:
        # One is missing but the other exists
        return 0.3

    # Check count match
    count_match = 1.0 if num_pages == len(pages) else max(0.0, 1.0 - abs(num_pages - len(pages)) / max(num_pages, len(pages)))

    # Check page numbering sequence
    if pages:
        page_numbers = [p.get("page_number", 0) for p in pages if isinstance(p, dict)]
        if page_numbers:
            expected_seq = list(range(1, len(page_numbers) + 1))
            seq_match = sum(1 for a, b in zip(page_numbers, expected_seq) if a == b) / len(expected_seq)
        else:
            seq_match = 0.5  # Pages exist but no numbers — partial credit
    else:
        seq_match = 0.0

    return round(count_match * 0.6 + seq_match * 0.4, 3)


def score_chunk_quality(data):
    """
    Score 0.0-1.0: Are chunks present, non-empty, and of reasonable length?
    """
    chunks = data.get("chunks", [])

    if not chunks:
        # No chunks returned — might not be a feature of this endpoint
        # Give partial credit if full_text exists (chunking just not done)
        if data.get("full_text", ""):
            return 0.5
        return 0.0

    total = len(chunks)
    if total == 0:
        return 0.0

    # Check chunk properties
    non_empty = 0
    good_length = 0  # > 50 chars
    very_short = 0   # < 10 chars

    for chunk in chunks:
        text = ""
        if isinstance(chunk, str):
            text = chunk
        elif isinstance(chunk, dict):
            text = chunk.get("text", "") or chunk.get("content", "") or str(chunk)

        if text.strip():
            non_empty += 1
        if len(text.strip()) > 50:
            good_length += 1
        if len(text.strip()) < 10:
            very_short += 1

    non_empty_ratio = non_empty / total
    good_length_ratio = good_length / total
    very_short_penalty = very_short / total

    score = (
        non_empty_ratio * 0.4 +
        good_length_ratio * 0.5 +
        (1.0 - very_short_penalty) * 0.1
    )
    return round(min(score, 1.0), 3)


def compute_fidelity(text_score, table_score, page_score, chunk_score):
    """Weighted fidelity score, 0.0-1.0."""
    return round(
        text_score * W_TEXT +
        table_score * W_TABLE +
        page_score * W_PAGE +
        chunk_score * W_CHUNK,
        3,
    )


# ── Main test runner ───────────────────────────────────────────────────

def test_document(doc, timeout=DEFAULT_TIMEOUT):
    """Test a single document and return its fidelity metrics."""
    url = doc["url"]
    sector = doc.get("sector", "unknown")
    title = doc.get("title", url.split("/")[-1])
    expected_tables = doc.get("expected_tables", 0)
    expected_min_pages = doc.get("expected_min_pages", 1)

    print(f"\n  [{sector.upper()}] {title}")
    print(f"    URL: {url[:100]}{'...' if len(url) > 100 else ''}")

    data, elapsed, error = convert_url(url, timeout=timeout)

    result = {
        "url": url,
        "sector": sector,
        "title": title,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "processing_time_s": round(elapsed, 2),
    }

    if error:
        print(f"    ERROR: {error}")
        result.update({
            "status": "error",
            "error": error,
            "fidelity": 0.0,
            "scores": {
                "text_completeness": 0.0,
                "table_detection": 0.0,
                "page_consistency": 0.0,
                "chunk_quality": 0.0,
            },
            "metrics": {},
        })
        return result

    # Status from Docling response
    docling_status = data.get("status", "unknown")
    if docling_status != "success":
        print(f"    Docling status: {docling_status}")
        if docling_status == "error":
            docling_error = data.get("error", "unknown error")
            print(f"    Docling error: {docling_error}")
            result.update({
                "status": "docling_error",
                "error": docling_error,
                "fidelity": 0.0,
                "scores": {
                    "text_completeness": 0.0,
                    "table_detection": 0.0,
                    "page_consistency": 0.0,
                    "chunk_quality": 0.0,
                },
                "metrics": {},
            })
            return result

    # Extract raw metrics
    full_text = data.get("full_text", "")
    pages = data.get("pages", [])
    tables = data.get("tables", [])
    chunks = data.get("chunks", [])
    num_pages = data.get("num_pages", 0) or len(pages)
    num_tables = data.get("num_tables", 0) or len(tables)
    docling_time = data.get("processing_time_s", elapsed)

    metrics = {
        "full_text_chars": len(full_text),
        "num_pages": num_pages,
        "num_pages_returned": len(pages),
        "num_tables": num_tables,
        "num_tables_returned": len(tables),
        "num_chunks": len(chunks),
        "chars_per_page": round(len(full_text) / max(num_pages, 1), 1),
        "processing_time_s": round(docling_time, 2) if isinstance(docling_time, (int, float)) else round(elapsed, 2),
        "time_per_page_s": round(elapsed / max(num_pages, 1), 2),
    }

    # Compute sub-scores
    text_score = score_text_completeness(data)
    table_score = score_table_detection(data, expected_tables)
    page_score = score_page_consistency(data)
    chunk_score = score_chunk_quality(data)
    fidelity = compute_fidelity(text_score, table_score, page_score, chunk_score)

    scores = {
        "text_completeness": text_score,
        "table_detection": table_score,
        "page_consistency": page_score,
        "chunk_quality": chunk_score,
    }

    # Print results
    status_icon = "[+]" if fidelity >= FIDELITY_TARGET else "[-]"
    print(f"    {status_icon} Fidelity: {fidelity:.3f} (target >= {FIDELITY_TARGET})")
    print(f"        Text: {text_score:.2f} | Tables: {table_score:.2f} | "
          f"Pages: {page_score:.2f} | Chunks: {chunk_score:.2f}")
    print(f"        {metrics['full_text_chars']:,} chars | "
          f"{metrics['num_pages']} pages | "
          f"{metrics['num_tables']} tables | "
          f"{metrics['num_chunks']} chunks | "
          f"{metrics['processing_time_s']}s")

    # Warnings
    if num_pages < expected_min_pages:
        print(f"        WARN: Expected >= {expected_min_pages} pages, got {num_pages}")
    if metrics["chars_per_page"] < 100:
        print(f"        WARN: Only {metrics['chars_per_page']:.0f} chars/page — sparse extraction")

    result.update({
        "status": "ok",
        "error": None,
        "fidelity": fidelity,
        "scores": scores,
        "metrics": metrics,
    })
    return result


def run_tests(docs, timeout=DEFAULT_TIMEOUT):
    """Run fidelity tests on a list of documents."""
    print("=" * 60)
    print("  DOCLING FIDELITY TEST SUITE")
    print(f"  Endpoint: {DOCLING_BASE}")
    print(f"  Documents: {len(docs)}")
    print(f"  Timeout: {timeout}s per document")
    print("=" * 60)

    # Health check first
    print("\n  Health check...")
    healthy, health_info = check_health()
    if not healthy:
        print(f"  WARN: Docling Space not responding — {health_info.get('error', 'unknown')}")
        print("  Will attempt tests anyway (Space may wake on first request)...")
    else:
        print("  Docling Space is UP")

    results = []
    for doc in docs:
        result = test_document(doc, timeout=timeout)
        results.append(result)
        # Small delay between documents to avoid overwhelming cpu-basic Space
        if doc != docs[-1]:
            time.sleep(2)

    return results


def summarize(results):
    """Print and return summary statistics."""
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)

    ok_results = [r for r in results if r["status"] == "ok"]
    err_results = [r for r in results if r["status"] != "ok"]

    if not ok_results:
        print("  No successful conversions — all documents failed.")
        return {"overall_fidelity": 0.0, "pass_rate": 0.0}

    fidelities = [r["fidelity"] for r in ok_results]
    overall = round(sum(fidelities) / len(fidelities), 3)
    passing = sum(1 for f in fidelities if f >= FIDELITY_TARGET)

    # Per-sector breakdown
    sectors = {}
    for r in ok_results:
        s = r["sector"]
        if s not in sectors:
            sectors[s] = []
        sectors[s].append(r["fidelity"])

    print(f"\n  Overall fidelity: {overall:.3f} (target >= {FIDELITY_TARGET})")
    print(f"  Pass rate: {passing}/{len(ok_results)} documents above target")
    if err_results:
        print(f"  Errors: {len(err_results)} documents failed")

    print(f"\n  Per-sector averages:")
    for sector, scores in sorted(sectors.items()):
        avg = round(sum(scores) / len(scores), 3)
        icon = "[+]" if avg >= FIDELITY_TARGET else "[-]"
        print(f"    {icon} {sector:12s}: {avg:.3f} ({len(scores)} docs)")

    print(f"\n  Per-document:")
    for r in results:
        if r["status"] == "ok":
            icon = "[+]" if r["fidelity"] >= FIDELITY_TARGET else "[-]"
            print(f"    {icon} {r['fidelity']:.3f}  {r['sector']:10s}  {r['title'][:50]}")
        else:
            print(f"    [!] ERROR  {r['sector']:10s}  {r['title'][:50]}")
            print(f"              {r.get('error', 'unknown')[:70]}")

    # Sub-score averages
    sub_scores = {"text_completeness": [], "table_detection": [], "page_consistency": [], "chunk_quality": []}
    for r in ok_results:
        for key in sub_scores:
            sub_scores[key].append(r["scores"].get(key, 0))

    print(f"\n  Sub-score averages:")
    for key, values in sub_scores.items():
        avg = round(sum(values) / len(values), 3) if values else 0
        print(f"    {key:25s}: {avg:.3f}")

    summary = {
        "overall_fidelity": overall,
        "pass_rate": round(passing / len(ok_results), 3),
        "total_docs": len(results),
        "ok_docs": len(ok_results),
        "error_docs": len(err_results),
        "sector_averages": {s: round(sum(v) / len(v), 3) for s, v in sectors.items()},
        "sub_score_averages": {k: round(sum(v) / len(v), 3) for k, v in sub_scores.items() if v},
    }
    return summary


def save_results(results, summary):
    """Save results to JSON file."""
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "docling_endpoint": DOCLING_BASE,
        "fidelity_target": FIDELITY_TARGET,
        "weights": {
            "text_completeness": W_TEXT,
            "table_detection": W_TABLE,
            "page_consistency": W_PAGE,
            "chunk_quality": W_CHUNK,
        },
        "summary": summary,
        "documents": results,
    }

    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n  Results saved to: {RESULTS_PATH}")


def show_report():
    """Display the latest saved results."""
    if not os.path.exists(RESULTS_PATH):
        print(f"No results file found at {RESULTS_PATH}")
        print("Run the test first: python3 eval/docling-fidelity.py")
        sys.exit(1)

    with open(RESULTS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    print("=" * 60)
    print("  DOCLING FIDELITY — LATEST REPORT")
    print(f"  Generated: {data.get('generated_at', 'unknown')}")
    print(f"  Endpoint:  {data.get('docling_endpoint', 'unknown')}")
    print("=" * 60)

    summary = data.get("summary", {})
    print(f"\n  Overall fidelity: {summary.get('overall_fidelity', 0):.3f}")
    print(f"  Pass rate: {summary.get('pass_rate', 0):.1%}")
    print(f"  Documents: {summary.get('ok_docs', 0)} OK / {summary.get('error_docs', 0)} errors")

    sector_avgs = summary.get("sector_averages", {})
    if sector_avgs:
        print(f"\n  Sector averages:")
        for sector, avg in sorted(sector_avgs.items()):
            icon = "[+]" if avg >= FIDELITY_TARGET else "[-]"
            print(f"    {icon} {sector:12s}: {avg:.3f}")

    sub_avgs = summary.get("sub_score_averages", {})
    if sub_avgs:
        print(f"\n  Sub-score averages:")
        for key, avg in sub_avgs.items():
            print(f"    {key:25s}: {avg:.3f}")

    docs = data.get("documents", [])
    if docs:
        print(f"\n  Per-document:")
        for r in docs:
            if r.get("status") == "ok":
                icon = "[+]" if r["fidelity"] >= FIDELITY_TARGET else "[-]"
                print(f"    {icon} {r['fidelity']:.3f}  {r.get('sector', '?'):10s}  "
                      f"{r.get('title', '?')[:45]}  ({r.get('processing_time_s', 0):.1f}s)")
            else:
                print(f"    [!] ERROR  {r.get('sector', '?'):10s}  "
                      f"{r.get('title', '?')[:45]}")


# ── CLI ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Docling Fidelity Test Suite — measure extraction quality on real sector PDFs"
    )
    parser.add_argument("--url", type=str, help="Test a specific URL instead of defaults")
    parser.add_argument("--sector", type=str, help="Filter default docs by sector (finance, btp, juridique, industrie)")
    parser.add_argument("--report", action="store_true", help="Show latest saved results")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help=f"Timeout per document in seconds (default: {DEFAULT_TIMEOUT})")
    parser.add_argument("--endpoint", type=str, help="Override Docling endpoint URL")
    args = parser.parse_args()

    if args.endpoint:
        global DOCLING_BASE
        DOCLING_BASE = args.endpoint.rstrip("/")

    if args.report:
        show_report()
        return

    # Build document list
    if args.url:
        docs = [{
            "url": args.url,
            "sector": "custom",
            "title": args.url.split("/")[-1][:60] or "custom-document",
            "expected_tables": 0,
            "expected_min_pages": 1,
        }]
    else:
        docs = DEFAULT_TEST_DOCS
        if args.sector:
            sector = args.sector.lower()
            docs = [d for d in docs if d["sector"] == sector]
            if not docs:
                print(f"No default documents for sector '{sector}'.")
                print(f"Available sectors: {sorted(set(d['sector'] for d in DEFAULT_TEST_DOCS))}")
                sys.exit(1)

    # Run tests
    results = run_tests(docs, timeout=args.timeout)
    summary = summarize(results)
    save_results(results, summary)

    # Exit code based on overall fidelity
    if summary.get("overall_fidelity", 0) >= FIDELITY_TARGET:
        print(f"\n  PASS — Overall fidelity {summary['overall_fidelity']:.3f} >= {FIDELITY_TARGET}")
    else:
        print(f"\n  BELOW TARGET — Overall fidelity {summary.get('overall_fidelity', 0):.3f} < {FIDELITY_TARGET}")
        sys.exit(1)


if __name__ == "__main__":
    main()
