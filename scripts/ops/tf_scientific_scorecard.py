#!/usr/bin/env python3
"""TF Scientific Scorecard — single-shot snapshot per TF of the metrics that
matter for scientific rigour: WR, calibration (mean confidence vs WR),
source purity (direct vs fallback), day-by-day variance, max DD.

Writes data/audit/scorecard-<ts>.json + data/audit/scorecard-latest.md
on every run. Meant to cron every 4h so the history is a proof log.

NOT a p&l chaser. A scientific-rigour reporter. The baseline_check already
answers PASS/FAIL on integrity; this answers "is the edge real and stable".
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT_DIR = REPO / "data" / "audit"
OUT_DIR.mkdir(parents=True, exist_ok=True)

WINDOW_DAYS = 10
HTTP_TIMEOUT = 15

SPACES = {
    "nba": "LBJLincoln26/nba-llm-trading-floor",
    "pol": "LBJLincoln26/political-llm-trading-floor",
}


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _hf_headers() -> dict[str, str]:
    tok = os.environ.get("HF_TOKEN_NBA") or os.environ.get("HF_TOKEN") or ""
    return {"Authorization": f"Bearer {tok}"} if tok else {}


def _http_get_json(url: str) -> tuple[object | None, str]:
    try:
        req = urllib.request.Request(url, headers=_hf_headers())
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
            return json.loads(r.read()), ""
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def _recent_days_from_hub(tf: str) -> list[dict]:
    repo = SPACES[tf]
    tree, _ = _http_get_json(f"https://huggingface.co/api/spaces/{repo}/tree/main?recursive=true")
    if not isinstance(tree, list):
        return []
    paths = sorted(
        str(f.get("path"))
        for f in tree
        if isinstance(f, dict)
        and str(f.get("path", "")).startswith("data/decisions/day-")
        and str(f.get("path", "")).endswith(".json")
    )[-WINDOW_DAYS:]
    out = []
    for p in paths:
        d, _ = _http_get_json(f"https://huggingface.co/spaces/{repo}/resolve/main/{urllib.parse.quote(p)}")
        if isinstance(d, dict):
            out.append(d)
    return out


def _brier(confidence: float, won: bool) -> float:
    # confidence is agent-declared probability [0,1]; brier = (conf - outcome)^2.
    outcome = 1.0 if won else 0.0
    return (confidence - outcome) ** 2


def _scorecard(tf: str) -> dict:
    days = _recent_days_from_hub(tf)
    if not days:
        return {"tf": tf, "ok": False, "reason": "no day files available"}

    # Aggregate
    per_day = []  # [(day_idx, bets, wins, pnl_fleet)]
    sources: dict[str, int] = {}
    confs_used = 0
    brier_sum = 0.0
    n_bets = 0
    total_wins = 0
    total_losses = 0
    fleet_bankrolls_last = None
    fleet_bankrolls_first = None
    per_tid_bets: dict[str, dict] = {}

    for day in days:
        day_n = day.get("day_idx")
        day_bets = day_wins = 0
        day_pnl = 0.0
        for tid, a in (day.get("agents") or {}).items():
            per_tid_bets.setdefault(tid, {"bets": 0, "wins": 0, "pnl": 0.0})
            for b in (a.get("allocations") or []):
                n_bets += 1
                day_bets += 1
                per_tid_bets[tid]["bets"] += 1
                won = b.get("won")
                if won is True:
                    total_wins += 1; day_wins += 1
                    per_tid_bets[tid]["wins"] += 1
                elif won is False:
                    total_losses += 1
                try:
                    pnl = float(b.get("profit") or b.get("pnl") or 0.0)
                except Exception:
                    pnl = 0.0
                day_pnl += pnl
                per_tid_bets[tid]["pnl"] += pnl
                src = b.get("source") or b.get("provider_status") or "unknown"
                sources[str(src)] = sources.get(str(src), 0) + 1
                c = b.get("confidence")
                if c is not None and won is not None:
                    try:
                        cv = float(c)
                        if 0.0 <= cv <= 1.0:
                            brier_sum += _brier(cv, bool(won))
                            confs_used += 1
                    except Exception:
                        pass
        # fleet bankrolls at day end
        fleet_total = sum(float(a.get("bankroll_after") or 0.0) for a in (day.get("agents") or {}).values())
        if fleet_bankrolls_first is None and fleet_total > 0:
            fleet_bankrolls_first = fleet_total
        if fleet_total > 0:
            fleet_bankrolls_last = fleet_total
        per_day.append({"day": day_n, "bets": day_bets, "wins": day_wins, "pnl": round(day_pnl, 2)})

    wr = total_wins / max(1, total_wins + total_losses)
    brier = brier_sum / max(1, confs_used) if confs_used else None
    # Max drawdown on day-PnL cumulative
    cum = 0.0
    peak = 0.0
    max_dd = 0.0
    for d in per_day:
        cum += d["pnl"]
        peak = max(peak, cum)
        max_dd = max(max_dd, peak - cum)

    direct_total = sources.get("llm_ok", 0) + sources.get("direct", 0)
    source_purity = direct_total / max(1, sum(sources.values()))

    # Per-agent brief
    agent_summary = sorted(
        [{"tid": tid, **v, "wr": v["wins"] / max(1, v["bets"])} for tid, v in per_tid_bets.items()],
        key=lambda r: -r.get("pnl", 0),
    )[:20]

    return {
        "tf": tf,
        "ok": True,
        "window_days_actual": len(days),
        "total_bets": n_bets,
        "wr_overall": round(wr, 4),
        "wr_sample": f"{total_wins}W/{total_losses}L",
        "brier_mean": round(brier, 4) if brier is not None else None,
        "brier_samples": confs_used,
        "source_purity_direct": round(source_purity, 4),
        "source_counts": sources,
        "fleet_pnl_window": round((fleet_bankrolls_last or 0) - (fleet_bankrolls_first or 0), 2)
            if (fleet_bankrolls_first and fleet_bankrolls_last) else None,
        "fleet_max_dd_window": round(max_dd, 2),
        "per_day": per_day,
        "per_agent_top5": agent_summary[:5],
        "per_agent_bottom5": agent_summary[-5:],
    }


def _markdown(sc_by_tf: dict) -> str:
    now = _now().strftime("%Y-%m-%d %H:%M UTC")
    out = [f"# TF Scientific Scorecard -- {now}", ""]
    for tf, s in sc_by_tf.items():
        if not s.get("ok"):
            out.append(f"## {tf.upper()} -- SKIP ({s.get('reason')})"); out.append("")
            continue
        out.append(f"## {tf.upper()}")
        out.append("")
        out.append(f"- window: last {s['window_days_actual']} days, {s['total_bets']} bets")
        out.append(f"- win rate: **{s['wr_overall']:.2%}** ({s['wr_sample']})")
        if s.get("brier_mean") is not None:
            out.append(f"- Brier score: **{s['brier_mean']:.4f}** (over {s['brier_samples']} confidence-tagged bets; lower=better calibrated)")
        out.append(f"- source purity: **{s['source_purity_direct']:.1%}** direct LLM (vs fallback)")
        if s.get("fleet_pnl_window") is not None:
            out.append(f"- fleet PnL in window: **${s['fleet_pnl_window']:+.2f}**  (max DD ${s['fleet_max_dd_window']:.2f})")
        out.append("")
        out.append("| day | bets | W | PnL |")
        out.append("|---|---:|---:|---:|")
        for d in s["per_day"][-10:]:
            out.append(f"| {d['day']} | {d['bets']} | {d['wins']} | ${d['pnl']:+.2f} |")
        out.append("")
        out.append("Top 5 agents (window):")
        for a in s["per_agent_top5"]:
            out.append(f"- `{a['tid']}` bets={a['bets']} W={a['wins']} WR={a['wr']:.2%} PnL=${a['pnl']:+.2f}")
        out.append("")
    return "\n".join(out)


def main() -> int:
    sc_by_tf = {tf: _scorecard(tf) for tf in SPACES}
    ts = _now()
    ts_str = ts.strftime("%Y-%m-%dT%H%MZ")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"ts": ts.isoformat(), "tfs": sc_by_tf}, indent=2, default=str)
    (OUT_DIR / f"scorecard-{ts_str}.json").write_text(payload)
    (OUT_DIR / "scorecard-latest.md").write_text(_markdown(sc_by_tf))
    # Fixed-name latest JSON for the dashboard to fetch — pairs with the MD.
    (OUT_DIR / "scorecard-latest.json").write_text(payload)
    print(f"ts={ts.isoformat()} scored tfs={list(SPACES)}")
    for tf, s in sc_by_tf.items():
        if s.get("ok"):
            print(f"  {tf.upper()}: bets={s['total_bets']} wr={s['wr_overall']:.2%} brier={s.get('brier_mean')} pnl_window=${s.get('fleet_pnl_window')}")
        else:
            print(f"  {tf.upper()}: SKIP ({s.get('reason')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
