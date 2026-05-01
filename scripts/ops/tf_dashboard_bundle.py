#!/usr/bin/env python3
"""TF Dashboard Bundle — single JSON the lab-grade dashboard pages fetch.

Aggregates the existing scientific-scorecard layer outputs into one
dashboard-ready bundle:

  data/tf-analytics/dashboard-bundle.json

Read-only over:
  data/audit/rigorous-latest.json    (CI95, ECE, walk-forward, reliability)
  data/audit/scorecard-latest.json   (per-day, per-agent, source purity)
  data/audit/trajectory-latest.md    (parsed for IMPROVING/DEGRADING)
  data/pipeline-health.json          (TF stage + freshness)
  data/ops/itf-position-health.jsonl (last 100 entries — equity time series)
  data/ops/overnight-latest.json     (current fleet snapshot)
  data/ops/tf-baseline-history.jsonl (PASS/FAIL integrity per cycle)
  data/champions/index.json          (champion ledger size per TF)

Schema produced is the contract the new dashboard <KPICard>,
<WalkforwardRibbon>, <ReliabilityDiagram>, <TrustBadgeRow>, and
<EquitySpark> components consume. Versioned so the frontend can detect
schema drift.

Cron suggestion: 51 * * * *  (right after :50 scientific-scorecard)
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
AUDIT = REPO / "data" / "audit"
OPS = REPO / "data" / "ops"
PIPE_HEALTH = REPO / "data" / "pipeline-health.json"
OUT_DIR = REPO / "data" / "tf-analytics"
OUT_FILE = OUT_DIR / "dashboard-bundle.json"
SCHEMA_VERSION = "2026-05-01"


def _read_json(p: Path) -> Any:
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _read_jsonl_tail(p: Path, n: int = 100) -> list[dict]:
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines()[-n:]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def _file_age_seconds(p: Path) -> float | None:
    if not p.exists():
        return None
    return dt.datetime.now(dt.timezone.utc).timestamp() - p.stat().st_mtime


def _trajectory_verdict() -> dict:
    """Parse trajectory-latest.md (small file) for IMPROVING/DEGRADING."""
    p = AUDIT / "trajectory-latest.md"
    out: dict[str, Any] = {"nba": None, "pol": None, "ts": None}
    if not p.exists():
        return out
    txt = p.read_text()
    out["ts"] = re.search(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}", txt)
    out["ts"] = out["ts"].group(0) if out["ts"] else None
    for tf in ("nba", "pol"):
        m = re.search(rf"##\s+{tf.upper()}.*?verdict[:\s]+(\w+)", txt, re.IGNORECASE | re.DOTALL)
        out[tf] = m.group(1).upper() if m else None
    return out


def _baseline_status() -> dict[str, Any]:
    """Last entry in tf-baseline-history.jsonl per TF."""
    p = OPS / "tf-baseline-history.jsonl"
    rows = _read_jsonl_tail(p, n=200)
    by_tf: dict[str, dict] = {}
    for r in rows:
        tf = r.get("tf")
        if tf:
            by_tf[tf] = r
    return by_tf


def _champion_counts() -> dict:
    idx = _read_json(REPO / "data" / "champions" / "index.json")
    if not isinstance(idx, dict):
        return {}
    counts: dict[str, int] = {}
    for tf, agents in idx.items():
        if isinstance(agents, dict):
            counts[tf] = sum(len(snaps) if isinstance(snaps, list) else 1
                             for snaps in agents.values())
        elif isinstance(agents, list):
            counts[tf] = len(agents)
    return counts


def _equity_series(tf: str, n: int = 60) -> list[dict]:
    """ITF equity time series from itf-position-health.jsonl, last n entries."""
    if tf != "itf":
        return []
    rows = _read_jsonl_tail(OPS / "itf-position-health.jsonl", n=n)
    return [
        {
            "ts": r.get("ts"),
            "equity": r.get("equity"),
            "cash": r.get("cash"),
            "long": r.get("long"),
            "short": r.get("short"),
        }
        for r in rows
        if r.get("ts") and r.get("equity") is not None
    ]


def _build_kpi(tf: str, rigorous: dict, scorecard: dict) -> dict:
    """Pack {brier, wr, pnl, ece, n} with CI95 the dashboard <KPICard> consumes."""
    rt = (rigorous or {}).get("tfs", {}).get(tf, {}) if rigorous else {}
    sc = (scorecard or {}).get("tfs", {}).get(tf, {}) if scorecard else {}
    if not rt.get("ok"):
        return {"ok": False, "reason": rt.get("reason", "no rigorous data")}
    return {
        "ok": True,
        "n_bets": rt.get("n_bets"),
        "n_days": rt.get("n_days"),
        "brier": rt.get("brier"),  # {lo, mid, hi}
        "wr": rt.get("wr"),
        "pnl": rt.get("pnl"),
        "ece": rt.get("ece"),
        "fleet_pnl_window": sc.get("fleet_pnl_window"),
        "fleet_max_dd_window": sc.get("fleet_max_dd_window"),
        "source_purity_direct": sc.get("source_purity_direct"),
    }


def _build_per_tf(tf: str, rigorous: dict, scorecard: dict,
                  pipe: dict, traj: dict, baseline: dict, champ: dict) -> dict:
    rt = (rigorous or {}).get("tfs", {}).get(tf, {}) if rigorous else {}
    sc = (scorecard or {}).get("tfs", {}).get(tf, {}) if scorecard else {}
    pipe_tf = (pipe or {}).get("trading_floors", {}).get(tf, {}) if pipe else {}

    return {
        "tf": tf,
        "stage": pipe_tf.get("stage"),
        "running": pipe_tf.get("running"),
        "last_decision_age_h": pipe_tf.get("last_decision_age_h"),
        "kpi": _build_kpi(tf, rigorous, scorecard),
        "calibration_buckets": rt.get("reliability", []),  # [{bucket, n, avg_predicted, avg_actual, gap}]
        "walk_forward": rt.get("walk_forward", []),         # [{start_day, end_day, n, brier}]
        "per_agent": rt.get("per_agent", []),               # [{tid, n, wr, brier, pnl}]
        "per_day": sc.get("per_day", []),                   # [{day, bets, wins, pnl}]
        "trust_signals": {
            "baseline_pass": baseline.get(tf, {}).get("ok"),
            "leakage_score": baseline.get(tf, {}).get("leakage"),
            "lockstep_score": baseline.get(tf, {}).get("lockstep"),
            "walkforward_status": baseline.get(tf, {}).get("walkforward"),
            "source_purity_pct": (sc.get("source_purity_direct") or 0) * 100,
            "trajectory_verdict": traj.get(tf),  # IMPROVING / DEGRADING / null
        },
        "champions_count": champ.get(tf, 0),
        "equity_series": _equity_series(tf),  # only itf has rich live equity
    }


def main() -> int:
    rigorous = _read_json(AUDIT / "rigorous-latest.json")
    scorecard = _read_json(AUDIT / "scorecard-latest.json")
    pipe = _read_json(PIPE_HEALTH)
    traj = _trajectory_verdict()
    baseline = _baseline_status()
    champ = _champion_counts()
    overnight = _read_json(OPS / "overnight-latest.json")

    bundle = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "freshness": {
            "rigorous_age_s": _file_age_seconds(AUDIT / "rigorous-latest.json"),
            "scorecard_age_s": _file_age_seconds(AUDIT / "scorecard-latest.json"),
            "pipeline_health_age_s": _file_age_seconds(PIPE_HEALTH),
        },
        "cross_tf_test": (rigorous or {}).get("cross_tf_test"),
        "tfs": {
            tf: _build_per_tf(tf, rigorous, scorecard, pipe, traj, baseline, champ)
            for tf in ("nba", "pol", "itf", "pqtf")
        },
        "overnight_snapshot": overnight,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(bundle, indent=2, default=str))
    print(f"dashboard-bundle written: {OUT_FILE} ({OUT_FILE.stat().st_size} bytes)")
    for tf in bundle["tfs"]:
        kpi = bundle["tfs"][tf]["kpi"]
        if kpi.get("ok"):
            b = kpi["brier"]
            print(f"  {tf.upper()}: brier={b['mid']:.4f} CI[{b['lo']:.4f},{b['hi']:.4f}] n_bets={kpi['n_bets']}")
        else:
            print(f"  {tf.upper()}: SKIP ({kpi.get('reason')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
