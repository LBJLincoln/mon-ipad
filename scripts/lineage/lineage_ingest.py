#!/usr/bin/env python3
"""
lineage_ingest — Cycle 14 Tier 2.C2

Reads the 12 experiment_id-enriched JSONs and pushes a DAG of lineage
events to a local SQLite "lineage.db". This is the Hamilton-UI-compatible
subset — we emit OpenLineage-ish JSON records and store them as rows so
the dashboard can render a bet → feature engine version graph.

If/when Hamilton UI is actually installed (pip install "sf-hamilton[ui,sdk]"),
this script can be pointed at localhost:8242 instead of the local SQLite
via the HAMILTON_UI env var. The SQLite path is the "it works with zero
deps" baseline.

Nodes we emit per experiment_id:
  engine_version → island_config → model_fit → prediction → strategy_gate → bet → pnl

Run:
  python3 scripts/lineage/lineage_ingest.py         # write to ~/.nomos42/lineage.db
  python3 scripts/lineage/lineage_ingest.py --print # dump the last 20 runs
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path("/home/termius/mon-ipad")
DB_DIR = Path(os.environ.get("NOMOS42_LINEAGE_DIR", str(Path.home() / ".nomos42")))
DB_PATH = DB_DIR / "lineage.db"

SOURCES: dict[str, Path] = {
    "council_research":   REPO / "data/departments/council-research-latest.json",
    "council_engineering":REPO / "data/departments/council-engineering-latest.json",
    "council_evolution":  REPO / "data/departments/council-evolution-latest.json",
    "council_evaluation": REPO / "data/departments/council-evaluation-latest.json",
    "council_product":    REPO / "data/departments/council-product-latest.json",
    "council_business":   REPO / "data/departments/council-business-latest.json",
    "council_finance":    REPO / "data/departments/council-finance-latest.json",
    "council_infra":      REPO / "data/departments/council-infra-latest.json",
    "council_cross_repo": REPO / "data/departments/council-cross-repo-latest.json",
    "agent_states_v5":    REPO / "data/arena/agent-states-v5.json",
    "cpcv_gated":         REPO / "data/arena/cpcv-gated-strategies.json",
    "full_season_bt":     REPO / "data/nba-agent/full-season-backtest.json",
}

# Karpathy-DAG node names per source — the lineage view on the dashboard
# renders these as an 8-node chain. Sources map to the closest node.
NODE_OF = {
    "council_research":    "research",
    "council_engineering": "engineering",
    "council_evolution":   "evolution",   # island_config
    "council_evaluation":  "evaluation",
    "council_product":     "product",
    "council_business":    "business",
    "council_finance":     "finance",
    "council_infra":       "infra",
    "council_cross_repo":  "cross_repo",
    "agent_states_v5":     "traders",     # prediction
    "cpcv_gated":          "strategy_gate",
    "full_season_bt":      "pnl",         # bet + pnl
}


def open_db() -> sqlite3.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS runs (
            experiment_id TEXT NOT NULL,
            node          TEXT NOT NULL,
            source        TEXT NOT NULL,
            ingested_at   TEXT NOT NULL,
            generated_at  TEXT,
            payload       TEXT NOT NULL,
            PRIMARY KEY (experiment_id, node, source)
        );
        CREATE INDEX IF NOT EXISTS idx_runs_eid ON runs(experiment_id);
        CREATE INDEX IF NOT EXISTS idx_runs_node ON runs(node);
        CREATE INDEX IF NOT EXISTS idx_runs_ingested ON runs(ingested_at);
    """)
    return conn


def extract_metrics(source_key: str, data: dict) -> dict[str, Any]:
    """Pull a small fixed shape out of each source for the DAG node
    summary row. Everything else goes into the raw payload column."""
    out: dict[str, Any] = {}
    # Department councils
    if source_key.startswith("council_"):
        out["iteration"] = data.get("iteration")
        out["department"] = data.get("department") or source_key.replace("council_", "")
        out["state"] = data.get("state") or data.get("status")
        # Try a few common metric locations
        for k in ("metric_value", "brier_delta", "final_score", "roi", "win_rate"):
            if k in data:
                out[k] = data[k]
    elif source_key == "agent_states_v5":
        out["n_agents"] = len(data) if isinstance(data, dict) else None
    elif source_key == "cpcv_gated":
        if isinstance(data, dict):
            strategies = data.get("strategies", [])
            out["strategies_total"] = len(strategies) if isinstance(strategies, list) else None
            passed = [s for s in strategies if isinstance(s, dict) and s.get("passed")]
            out["strategies_passed"] = len(passed)
    elif source_key == "full_season_bt":
        for k in ("roi_pct", "win_rate", "sharpe", "max_dd", "brier", "total_bets"):
            if k in data:
                out[k] = data[k]
    return out


def ingest_one(conn: sqlite3.Connection, source_key: str, path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"source": source_key, "status": "MISS"}
    try:
        data = json.loads(path.read_text())
    except Exception as e:
        return {"source": source_key, "status": f"ERR:{type(e).__name__}"}
    if not isinstance(data, dict):
        return {"source": source_key, "status": "NOTDICT"}
    eid = data.get("experiment_id")
    if not eid:
        return {"source": source_key, "status": "NOEID"}
    node = NODE_OF.get(source_key, source_key)
    metrics = extract_metrics(source_key, data)
    payload = {
        "metrics": metrics,
        "engine_version": "v3.1-54cat",
        "path": str(path.relative_to(REPO)),
    }
    conn.execute(
        "INSERT OR REPLACE INTO runs(experiment_id,node,source,ingested_at,generated_at,payload) "
        "VALUES (?,?,?,?,?,?)",
        (
            eid,
            node,
            source_key,
            datetime.now(timezone.utc).isoformat(),
            data.get("generated_at") or data.get("updated_at") or "",
            json.dumps(payload, default=str),
        ),
    )
    return {"source": source_key, "status": "OK", "eid": eid, "node": node, "metrics": metrics}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", action="store_true", help="dump the 20 most recent rows")
    args = ap.parse_args()

    conn = open_db()

    if args.print:
        rows = conn.execute(
            "SELECT experiment_id, node, source, generated_at, ingested_at FROM runs "
            "ORDER BY ingested_at DESC LIMIT 20"
        ).fetchall()
        for r in rows:
            print(" | ".join(str(c) for c in r))
        return 0

    print(f"[lineage-ingest] db={DB_PATH}")
    ok = err = miss = 0
    for key, path in SOURCES.items():
        res = ingest_one(conn, key, path)
        status = res["status"]
        if status == "OK":
            ok += 1
            m_str = " ".join(f"{k}={v}" for k, v in (res.get("metrics") or {}).items() if v is not None)
            print(f"  OK   {key:20s} eid={res['eid']} node={res['node']:15s} {m_str[:80]}")
        elif status == "MISS":
            miss += 1
            print(f"  MISS {key}")
        else:
            err += 1
            print(f"  {status:8s} {key}")
    conn.commit()
    conn.close()

    print(f"[lineage-ingest] ok={ok} miss={miss} err={err} db_bytes={DB_PATH.stat().st_size if DB_PATH.exists() else 0}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
