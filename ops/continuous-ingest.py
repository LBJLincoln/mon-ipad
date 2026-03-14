#!/usr/bin/env python3
"""
Continuous Ingestion Daemon — runs Exa.AI + fast-ingest in cycles.

Runs as a background daemon on the VM, continuously:
1. Exa.AI web search → chunk → E5 Pinecone (all 4 sectors)
2. HF dataset download → chunk → E5 Pinecone
3. Neo4j enrichment check

Usage:
  source .env.local
  python3 ops/continuous-ingest.py                    # One cycle
  python3 ops/continuous-ingest.py --loop 3600        # Every hour
  python3 ops/continuous-ingest.py --loop 1800 --daemon  # Daemonize
  nohup python3 ops/continuous-ingest.py --loop 3600 > data/ingest/daemon.log 2>&1 &
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Force unbuffered
try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

BASE_DIR = Path(os.path.expanduser("~/mon-ipad"))
OPS_DIR = BASE_DIR / "ops"
DATA_DIR = BASE_DIR / "data" / "ingest"
DATA_DIR.mkdir(parents=True, exist_ok=True)

STATE_FILE = DATA_DIR / "daemon-state.json"

# HF datasets to try ingesting (sector, dataset_id, max_records)
HF_DATASETS = [
    ("finance", "sujet-ai/Sujet-Finance-Instruct-177k", 5000),
    ("finance", "gbharti/finance-alpaca", 3000),
    ("juridique", "manu/french_law", 5000),
    ("industrie", "bigbio/med_qa", 2000),
]


def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"cycles": 0, "total_upserted": 0, "last_cycle": None, "history": []}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str))


def run_exa_sector(sector: str, max_queries: int = 5) -> dict:
    """Run exa-mass-ingest for one sector."""
    log(f"  Exa.AI → {sector} ({max_queries} queries)")
    cmd = [
        sys.executable, str(OPS_DIR / "exa-mass-ingest.py"),
        "--sector", sector,
        "--max-queries", str(max_queries),
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=1800,
            env={**os.environ, "PYTHONUNBUFFERED": "1"}
        )
        output = result.stdout + result.stderr
        # Parse upserted count from output
        upserted = 0
        for line in output.split("\n"):
            if "upserted" in line.lower():
                parts = line.split()
                for i, p in enumerate(parts):
                    if "upserted" in p.lower() and i > 0:
                        try:
                            upserted = int(parts[i - 1].replace(",", ""))
                        except ValueError:
                            pass
            if "Total:" in line or "COMPLETE" in line:
                log(f"    {line.strip()}")
        return {"sector": sector, "upserted": upserted, "ok": result.returncode == 0}
    except subprocess.TimeoutExpired:
        log(f"    TIMEOUT for {sector} (30min limit)")
        return {"sector": sector, "upserted": 0, "ok": False, "error": "timeout"}
    except Exception as e:
        log(f"    ERROR: {e}")
        return {"sector": sector, "upserted": 0, "ok": False, "error": str(e)}


def run_fast_ingest(sector: str = "all") -> dict:
    """Run fast-ingest for local datasets."""
    log(f"  fast-ingest → {sector}")
    cmd = [
        sys.executable, str(OPS_DIR / "fast-ingest.py"),
        "--workers", "8",
        "--skip-existing",
    ]
    if sector != "all":
        cmd.extend(["--sector", sector])
    else:
        cmd.append("--all")

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=900,
            env={**os.environ, "PYTHONUNBUFFERED": "1"}
        )
        output = result.stdout + result.stderr
        upserted = 0
        for line in output.split("\n"):
            if "upserted" in line.lower() or "new" in line.lower():
                log(f"    {line.strip()}")
            if "Total upserted" in line or "Upserted:" in line:
                parts = line.split()
                for p in parts:
                    try:
                        n = int(p.replace(",", ""))
                        if n > upserted:
                            upserted = n
                    except ValueError:
                        pass
        return {"upserted": upserted, "ok": result.returncode == 0}
    except subprocess.TimeoutExpired:
        log(f"    TIMEOUT")
        return {"upserted": 0, "ok": False, "error": "timeout"}
    except Exception as e:
        log(f"    ERROR: {e}")
        return {"upserted": 0, "ok": False, "error": str(e)}


def run_hf_ingest(sector: str, dataset: str, max_records: int) -> dict:
    """Run fast-ingest with HF dataset."""
    log(f"  HF dataset → {dataset} ({max_records} max)")
    cmd = [
        sys.executable, str(OPS_DIR / "fast-ingest.py"),
        "--workers", "8",
        "--skip-existing",
        "--hf-dataset", dataset,
        "--max", str(max_records),
        "--sector", sector,
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=600,
            env={**os.environ, "PYTHONUNBUFFERED": "1"}
        )
        output = result.stdout + result.stderr
        upserted = 0
        for line in output.split("\n"):
            if "upserted" in line.lower() or "Total" in line:
                log(f"    {line.strip()}")
                parts = line.split()
                for p in parts:
                    try:
                        n = int(p.replace(",", ""))
                        if n > upserted:
                            upserted = n
                    except ValueError:
                        pass
        return {"dataset": dataset, "upserted": upserted, "ok": result.returncode == 0}
    except subprocess.TimeoutExpired:
        return {"dataset": dataset, "upserted": 0, "ok": False, "error": "timeout"}
    except Exception as e:
        return {"dataset": dataset, "upserted": 0, "ok": False, "error": str(e)}


def check_pinecone_count() -> int:
    """Quick check of E5 Pinecone vector count."""
    try:
        import urllib.request
        api_key = os.environ.get("PINECONE_API_KEY", "")
        host = "https://sectors-e5-multilingual-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
        req = urllib.request.Request(
            f"{host}/describe_index_stats",
            data=b"{}",
            headers={"Api-Key": api_key, "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data.get("totalRecordCount", data.get("totalVectorCount", 0))
    except Exception:
        return 0


DOCLING_SECTORS = ["finance", "btp", "juridique", "industrie"]


def run_docling_ingest(cycle_num: int, max_docs: int = 3) -> dict:
    """Run Docling S6 PDF processing for discovered documents."""
    sector = DOCLING_SECTORS[(cycle_num - 1) % len(DOCLING_SECTORS)]
    log("  Docling S6 → %s (%d docs max)" % (sector, max_docs))
    cmd = [
        sys.executable, str(OPS_DIR / "docling-s6-ingest.py"),
        "--from-discovered",
        "--sector", sector,
        "--max", str(max_docs),
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=1800,
            env={**os.environ, "PYTHONUNBUFFERED": "1"}
        )
        output = result.stdout + result.stderr
        processed = 0
        for line in output.split("\n"):
            if "processed" in line.lower() or "upserted" in line.lower() or "chunks" in line.lower():
                log("    %s" % line.strip())
            if "SUCCESS" in line:
                processed += 1
        return {"sector": sector, "processed": processed, "ok": result.returncode == 0}
    except subprocess.TimeoutExpired:
        log("    TIMEOUT (30min)")
        return {"sector": sector, "processed": 0, "ok": False, "error": "timeout"}
    except Exception as e:
        log("    ERROR: %s" % str(e))
        return {"sector": sector, "processed": 0, "ok": False, "error": str(e)}


def run_neo4j_enrichment() -> dict:
    """Run Neo4j entity enrichment from JSONL datasets."""
    log("  Neo4j enrichment → populate-neo4j-entities.py")
    cmd = [
        sys.executable, str(OPS_DIR / "populate-neo4j-entities.py"),
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=600,
            env={**os.environ, "PYTHONUNBUFFERED": "1"}
        )
        output = result.stdout + result.stderr
        entities = 0
        for line in output.split("\n"):
            if "TOTAL:" in line or "unique entities" in line:
                log(f"    {line.strip()}")
                parts = line.split()
                for p in parts:
                    try:
                        n = int(p.replace(",", ""))
                        if n > entities:
                            entities = n
                    except ValueError:
                        pass
            if "WRITING TO NEO4J" in line or "Created" in line or "Merged" in line:
                log(f"    {line.strip()}")
        return {"entities": entities, "ok": result.returncode == 0}
    except subprocess.TimeoutExpired:
        log("    TIMEOUT")
        return {"entities": 0, "ok": False, "error": "timeout"}
    except Exception as e:
        log(f"    ERROR: {e}")
        return {"entities": 0, "ok": False, "error": str(e)}


def run_cycle(state: dict, exa_queries: int = 5) -> dict:
    """Run one full ingestion cycle."""
    cycle_start = datetime.now(timezone.utc)
    cycle_num = state["cycles"] + 1
    log(f"═══ CYCLE {cycle_num} ═══")

    vectors_before = check_pinecone_count()
    log(f"  Pinecone vectors before: {vectors_before:,}")

    results = []

    # 1. Fast-ingest local datasets
    r = run_fast_ingest("all")
    results.append({"step": "fast-ingest", **r})

    # 2. Exa.AI for each sector
    for sector in ["finance", "btp", "juridique", "industrie"]:
        r = run_exa_sector(sector, exa_queries)
        results.append({"step": "exa-%s" % sector, **r})

    # 3. HF datasets (one per cycle, rotating)
    hf_idx = (cycle_num - 1) % len(HF_DATASETS)
    sector, dataset, max_rec = HF_DATASETS[hf_idx]
    r = run_hf_ingest(sector, dataset, max_rec)
    results.append({"step": "hf-%s" % sector, **r})

    # 4. Docling S6 PDF processing (3 docs per cycle, rotating sectors)
    r = run_docling_ingest(cycle_num)
    results.append({"step": "docling-s6", **r})

    # 5. Neo4j enrichment (every cycle — reads JSONL, extracts entities)
    r = run_neo4j_enrichment()
    results.append({"step": "neo4j-enrichment", **r})

    vectors_after = check_pinecone_count()
    new_vectors = vectors_after - vectors_before

    cycle_end = datetime.now(timezone.utc)
    elapsed = (cycle_end - cycle_start).total_seconds()

    log(f"  Pinecone vectors after: {vectors_after:,} (+{new_vectors:,})")
    log(f"  Cycle {cycle_num} done in {elapsed:.0f}s")

    cycle_result = {
        "cycle": cycle_num,
        "timestamp": cycle_start.isoformat(),
        "elapsed_s": round(elapsed),
        "vectors_before": vectors_before,
        "vectors_after": vectors_after,
        "new_vectors": new_vectors,
        "results": results,
    }

    # Update state
    state["cycles"] = cycle_num
    state["total_upserted"] += new_vectors
    state["last_cycle"] = cycle_result
    state["history"] = (state.get("history", []) + [cycle_result])[-20:]  # Keep last 20
    save_state(state)

    return cycle_result


def main():
    parser = argparse.ArgumentParser(description="Continuous Ingestion Daemon")
    parser.add_argument("--loop", type=int, default=0, help="Loop interval in seconds (0=one-shot)")
    parser.add_argument("--exa-queries", type=int, default=5, help="Exa.AI queries per sector per cycle")
    parser.add_argument("--daemon", action="store_true", help="Run as background daemon")
    args = parser.parse_args()

    log("Continuous Ingestion Daemon starting")
    log(f"  Mode: {'loop every {0}s'.format(args.loop) if args.loop else 'one-shot'}")
    log(f"  Exa.AI queries/sector: {args.exa_queries}")

    state = load_state()

    if args.loop:
        while True:
            try:
                run_cycle(state, args.exa_queries)
            except Exception as e:
                log(f"  CYCLE ERROR: {e}")
            log(f"  Sleeping {args.loop}s until next cycle...")
            time.sleep(args.loop)
    else:
        run_cycle(state, args.exa_queries)

    log("Daemon stopped")


if __name__ == "__main__":
    main()
