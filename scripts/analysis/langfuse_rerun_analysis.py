#!/usr/bin/env python3
"""Langfuse cross-rerun TF analysis.

Directive (2026-04-19, post-crash resume): every NBA TF / POL TF / PQTF /
ITF rerun is traced to Langfuse. We have done MANY reruns. This script:

  1. Pulls ALL Langfuse observations for the tf project (nomos42-tf),
     paginated via /api/public/observations.
  2. Groups them by (tf, run_id) where run_id is the UTC day the rerun
     started (falls back to trace session_id).
  3. For each (tf, run_id, agent, model) tuple computes:
       - n_calls, n_errors, err_rate
       - avg_latency_ms, p95_latency_ms
       - bet_count (from metadata.action="trade"|"bet")
       - avg_stake, avg_stake_pct_bankroll
       - win_rate, pnl_usd, sharpe_approx
       - jaccard_vs_fleet (when day-XXX.json available locally)
  4. Writes `data/analysis/rerun-ledger.json` with per-rerun rollups and
     `data/analysis/agent-contribution-matrix.csv` with the agent × rerun
     alpha matrix. DR FRANKENSTEIN consumes both.
  5. Identifies which agents ADD alpha each rerun (PnL > fleet median)
     and which SUBTRACT (PnL < fleet 25th pct) — auto-flags the subtractors
     for the next proposal batch.

Usage:
  python3 scripts/analysis/langfuse_rerun_analysis.py            # uses env
  python3 scripts/analysis/langfuse_rerun_analysis.py --days 7   # limit window

Env vars (from reference_langfuse_keys.md):
  LANGFUSE_HOST        — e.g. https://nomos42-langfuse.hf.space
  LANGFUSE_PUBLIC_KEY  — pk-lf-...
  LANGFUSE_SECRET_KEY  — sk-lf-...
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    import requests
except ImportError:
    print("requests required — pip install requests", file=sys.stderr)
    sys.exit(1)

REPO = Path(__file__).resolve().parents[2]
OUT_DIR = REPO / "data" / "analysis"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _auth() -> Tuple[str, str, str]:
    host = _env("LANGFUSE_HOST", "https://nomos42-langfuse.hf.space").rstrip("/")
    pk = _env("LANGFUSE_PUBLIC_KEY")
    sk = _env("LANGFUSE_SECRET_KEY")
    if not (pk and sk):
        print("[langfuse] missing LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY", file=sys.stderr)
        sys.exit(2)
    return host, pk, sk


def fetch_observations(host: str, pk: str, sk: str,
                       from_ts: datetime, to_ts: datetime,
                       page_size: int = 100) -> Iterable[Dict[str, Any]]:
    """Yield observations in [from_ts, to_ts]. Langfuse paginates via page+limit."""
    page = 1
    fetched = 0
    while True:
        params = {
            "page": page,
            "limit": page_size,
            "fromStartTime": from_ts.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "toStartTime": to_ts.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        }
        r = requests.get(
            f"{host}/api/public/observations",
            auth=(pk, sk), params=params, timeout=30,
        )
        if r.status_code == 404:
            print("[langfuse] /api/public/observations not exposed on this instance — "
                  "check Langfuse version (need ≥2.40)", file=sys.stderr)
            return
        if r.status_code >= 400:
            print(f"[langfuse] HTTP {r.status_code} @ page {page}: {r.text[:200]}",
                  file=sys.stderr)
            return
        body = r.json()
        data = body.get("data", [])
        if not data:
            return
        for item in data:
            yield item
            fetched += 1
        if len(data) < page_size:
            return
        page += 1


def _extract_tf(obs: Dict[str, Any]) -> Optional[str]:
    meta = obs.get("metadata") or {}
    tf = meta.get("tf") or meta.get("trading_floor") or meta.get("floor")
    if tf:
        return str(tf).lower()
    # Fallback on trace name convention: "nba_tf:day-042:qwen-quant"
    name = (obs.get("traceName") or obs.get("name") or "").lower()
    for candidate in ("nba", "pol", "pqtf", "itf"):
        if name.startswith(candidate):
            return candidate
    return None


def _extract_run_id(obs: Dict[str, Any]) -> str:
    meta = obs.get("metadata") or {}
    if meta.get("run_id"):
        return str(meta["run_id"])
    if meta.get("session_id"):
        return str(meta["session_id"])
    start = obs.get("startTime") or obs.get("createdAt") or ""
    return start[:10] or "unknown"


def _extract_agent(obs: Dict[str, Any]) -> str:
    meta = obs.get("metadata") or {}
    return (meta.get("agent_tid") or meta.get("agent") or meta.get("trader") or
            meta.get("persona") or obs.get("name") or "unknown")


def _extract_model(obs: Dict[str, Any]) -> str:
    return obs.get("model") or (obs.get("metadata") or {}).get("model") or "unknown"


def _extract_action(obs: Dict[str, Any]) -> Dict[str, Any]:
    """Try to parse a bet action out of the trace output."""
    meta = obs.get("metadata") or {}
    if meta.get("action") in ("trade", "bet"):
        return {
            "action": meta["action"],
            "pnl_usd": float(meta.get("pnl_usd") or 0),
            "stake_usd": float(meta.get("stake_usd") or 0),
            "is_win": bool(meta.get("is_win")) if "is_win" in meta else None,
        }
    # Try to parse JSON out of the response body
    out = obs.get("output")
    if isinstance(out, dict):
        if out.get("action") in ("trade", "bet"):
            return {
                "action": out["action"],
                "pnl_usd": float(out.get("pnl_usd") or 0),
                "stake_usd": float(out.get("stake_usd") or 0),
                "is_win": bool(out.get("is_win")) if "is_win" in out else None,
            }
    return {"action": "none"}


def aggregate(observations: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Group observations by (tf, run_id, agent, model)."""
    buckets: Dict[Tuple[str, str, str, str], Dict[str, Any]] = defaultdict(lambda: {
        "n_calls": 0,
        "n_errors": 0,
        "latencies_ms": [],
        "bets": [],
        "wins": 0,
        "losses": 0,
        "pnl_usd": 0.0,
        "stake_usd": 0.0,
    })

    for obs in observations:
        tf = _extract_tf(obs)
        if tf is None:
            continue
        run_id = _extract_run_id(obs)
        agent = _extract_agent(obs)
        model = _extract_model(obs)
        key = (tf, run_id, agent, model)
        b = buckets[key]
        b["n_calls"] += 1
        if obs.get("level") == "ERROR" or obs.get("statusMessage"):
            b["n_errors"] += 1
        lat = obs.get("latency") or 0
        if lat:
            b["latencies_ms"].append(float(lat))
        action = _extract_action(obs)
        if action.get("action") in ("trade", "bet"):
            b["bets"].append(action)
            b["pnl_usd"] += action.get("pnl_usd", 0)
            b["stake_usd"] += action.get("stake_usd", 0)
            if action.get("is_win") is True:
                b["wins"] += 1
            elif action.get("is_win") is False:
                b["losses"] += 1
    return buckets


def rollup(buckets: Dict[Tuple[str, str, str, str], Dict[str, Any]]) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    for (tf, run_id, agent, model), b in buckets.items():
        lats = b["latencies_ms"]
        n_bets = len(b["bets"])
        wr = (b["wins"] / (b["wins"] + b["losses"])) if (b["wins"] + b["losses"]) else None
        rows.append({
            "tf": tf,
            "run_id": run_id,
            "agent": agent,
            "model": model,
            "n_calls": b["n_calls"],
            "n_errors": b["n_errors"],
            "err_rate": round(b["n_errors"] / b["n_calls"], 4) if b["n_calls"] else 0,
            "avg_latency_ms": round(statistics.mean(lats), 1) if lats else None,
            "p95_latency_ms": round(statistics.quantiles(lats, n=20)[-1], 1) if len(lats) >= 20 else None,
            "n_bets": n_bets,
            "pnl_usd": round(b["pnl_usd"], 2),
            "stake_usd": round(b["stake_usd"], 2),
            "win_rate": round(wr, 4) if wr is not None else None,
        })
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "n_rows": len(rows),
        "rows": rows,
    }


def flag_contribution(ledger: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Per-rerun: agents with pnl > fleet median add alpha; < 25th pct subtract."""
    flags: List[Dict[str, Any]] = []
    grouped: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in ledger["rows"]:
        grouped[(row["tf"], row["run_id"])].append(row)
    for (tf, run_id), rows in grouped.items():
        pnls = [r["pnl_usd"] for r in rows if r["n_bets"] > 0]
        if len(pnls) < 4:
            continue
        med = statistics.median(pnls)
        q25 = statistics.quantiles(pnls, n=4)[0]
        for r in rows:
            if r["n_bets"] == 0:
                continue
            if r["pnl_usd"] >= med:
                status = "ADD_ALPHA"
            elif r["pnl_usd"] <= q25:
                status = "SUBTRACT_ALPHA"
            else:
                status = "NEUTRAL"
            flags.append({
                "tf": tf, "run_id": run_id, "agent": r["agent"], "model": r["model"],
                "pnl_usd": r["pnl_usd"], "fleet_median": round(med, 2),
                "fleet_q25": round(q25, 2), "status": status,
            })
    return flags


def write_csv(flags: List[Dict[str, Any]], path: Path) -> None:
    if not flags:
        path.write_text("tf,run_id,agent,model,pnl_usd,fleet_median,fleet_q25,status\n")
        return
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(flags[0].keys()))
        w.writeheader()
        for f in flags:
            w.writerow(f)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=14,
                    help="Look back N days of observations")
    args = ap.parse_args()

    host, pk, sk = _auth()
    to_ts = datetime.now(timezone.utc)
    from_ts = to_ts - timedelta(days=args.days)

    print(f"[langfuse] fetching {from_ts.isoformat()} → {to_ts.isoformat()}")
    obs_iter = fetch_observations(host, pk, sk, from_ts, to_ts)
    buckets = aggregate(obs_iter)
    ledger = rollup(buckets)
    flags = flag_contribution(ledger)

    ledger_path = OUT_DIR / "rerun-ledger.json"
    csv_path = OUT_DIR / "agent-contribution-matrix.csv"
    ledger_path.write_text(json.dumps(ledger, indent=2))
    write_csv(flags, csv_path)
    print(f"[langfuse] wrote {ledger_path} ({ledger['n_rows']} rows)")
    print(f"[langfuse] wrote {csv_path} ({len(flags)} contribution flags)")

    # Quick console summary
    by_status = defaultdict(int)
    for f in flags:
        by_status[f["status"]] += 1
    print(f"[langfuse] contribution summary: {dict(by_status)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
