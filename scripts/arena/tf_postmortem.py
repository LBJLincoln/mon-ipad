#!/usr/bin/env python3
"""
TF POST-MORTEM ANALYZER — Scientific rationale extraction + pattern mining
==========================================================================
Reads all data/decisions/day-XXX.json files from the NBA + Political TF HF
Spaces, extracts agent rationales, bankroll trajectories, and pact history,
then produces a comparative report identifying what separates winners from
losers.

The answer the user asked for: "vraie experience scientifique permettant
l'amelioration repetee" — this file is the repeatable analysis loop.

Usage:
  python3 scripts/arena/tf_postmortem.py            # both fleets
  python3 scripts/arena/tf_postmortem.py --fleet nba
  python3 scripts/arena/tf_postmortem.py --fleet pol --top 5
  python3 scripts/arena/tf_postmortem.py --fleet pqtf
  python3 scripts/arena/tf_postmortem.py --fleet all   # nba + pol + pqtf

Outputs:
  data/tf-analysis/<fleet>-summary.json   — per-agent trajectory + stats
  data/tf-analysis/<fleet>-peaks.json     — top 10 bankroll jumps with rationale
  data/tf-analysis/<fleet>-crashes.json   — top 10 drawdowns with rationale
  data/tf-analysis/<fleet>-report.md      — human-readable comparison
  (pqtf also writes data/tf-analysis/pqtf-report.md with multi-leg breakdown)
"""

import argparse
import json
import math
import os
import re
import sys
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = ROOT / "data" / "tf-analysis"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Local analytics cache (written every 4h by tf_analytics.py)
PQTF_ANALYTICS_DIR = ROOT / "data" / "tf-analytics" / "pqtf"

FLEETS = {
    "nba": {
        "space": "LBJLincoln26/nba-llm-trading-floor",
        "url": "https://huggingface.co/spaces/LBJLincoln26/nba-llm-trading-floor",
    },
    "pol": {
        "space": "LBJLincoln26/political-llm-trading-floor",
        "url": "https://huggingface.co/spaces/LBJLincoln26/political-llm-trading-floor",
    },
    "pqtf": {
        "space": "LBJLincoln26/political-quant-trading-floor",
        "url": "https://huggingface.co/spaces/LBJLincoln26/political-quant-trading-floor",
    },
}


def _hf_token() -> str:
    """Read HF_TOKEN_NBA (LBJLincoln26 account) from environment, then .env.local."""
    tok = os.environ.get("HF_TOKEN_NBA") or os.environ.get("HF_TOKEN_2") or os.environ.get("HF_TOKEN", "")
    if not tok:
        env_file = ROOT / ".env.local"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("export HF_TOKEN_NBA="):
                    tok = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    return tok


def _get_json(url: str, timeout: int = 20, token: str = ""):
    headers = {"User-Agent": "tf-postmortem/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(url, headers=headers)
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def list_day_files(space: str, token: str = "") -> list[str]:
    api = f"https://huggingface.co/api/spaces/{space}/tree/main/data/decisions?recursive=true"
    try:
        tree = _get_json(api, token=token)
    except (URLError, HTTPError) as e:
        print(f"[{space}] listing failed: {e}", file=sys.stderr)
        return []
    return sorted(f["path"] for f in tree if f.get("type") == "file"
                  and f["path"].endswith(".json"))


def load_day(space: str, path: str, token: str = "") -> dict | None:
    raw = f"https://huggingface.co/spaces/{space}/raw/main/{path}"
    try:
        return _get_json(raw, token=token)
    except (URLError, HTTPError):
        return None


def extract_raw_strategy(raw_preview: str) -> str:
    """raw_preview starts with LLM JSON. Pull day_strategy field."""
    if not raw_preview:
        return ""
    m = re.search(r'"day_strategy"\s*:\s*"([^"]{1,400})', raw_preview)
    return m.group(1) if m else raw_preview[:200]


def analyze_fleet(fleet: str, top: int = 10) -> dict:
    token = _hf_token()
    space = FLEETS[fleet]["space"]
    print(f"[{fleet}] fetching day file index from {space}...")
    paths = list_day_files(space, token=token)
    print(f"[{fleet}] found {len(paths)} day files")
    if not paths:
        return {}

    # Per-agent trajectories: tid -> [(day_idx, date, bankroll_before, bankroll_after, day_strategy, allocs)]
    trajectories: dict[str, list] = {}
    # Events: (fleet, tid, day_idx, delta_pct, bankroll_before, bankroll_after, strategy, allocs_summary)
    jumps: list = []
    crashes: list = []

    # Council plans chronological
    council_timeline: list = []

    for path in paths:
        day = load_day(space, path, token=token)
        if not day:
            continue
        day_idx = day.get("day_idx")
        date = day.get("date")
        council = day.get("council_plan") or {}
        council_timeline.append({
            "day": day_idx, "date": date,
            "summary": council.get("council_summary", "")[:300],
            "focus": council.get("focus_strategies", [])[:3],
        })
        for tid, log in (day.get("agents") or {}).items():
            br_b = float(log.get("bankroll_before") or 0)
            br_a = float(log.get("bankroll_after") or 0)
            strategy = log.get("day_strategy") or ""
            raw_preview = log.get("raw_preview") or ""
            # If day_strategy is "fallback-injection...", try to pull from raw_preview
            if strategy.startswith("fallback-injection"):
                strategy = extract_raw_strategy(raw_preview) or strategy
            allocs = log.get("allocations") or []
            allocs_summary = [
                f"{a.get('game','?')}:{a.get('category','?')}:{round(float(a.get('pct') or 0),3)}"
                for a in allocs[:5]
            ]
            trajectories.setdefault(tid, []).append({
                "day": day_idx, "date": date,
                "bankroll_before": br_b, "bankroll_after": br_a,
                "strategy": strategy[:300],
                "cash_held_pct": log.get("cash_held_pct", 0),
                "n_allocs": len(allocs),
                "allocs": allocs_summary,
            })
            if br_b > 0.01:
                delta_pct = (br_a - br_b) / br_b * 100
                ev = {
                    "tid": tid, "day": day_idx, "date": date,
                    "bankroll_before": br_b, "bankroll_after": br_a,
                    "delta_pct": round(delta_pct, 2),
                    "strategy": strategy[:200],
                    "allocs": allocs_summary,
                }
                if delta_pct >= 10:
                    jumps.append(ev)
                elif delta_pct <= -20:
                    crashes.append(ev)

    jumps.sort(key=lambda e: -e["delta_pct"])
    crashes.sort(key=lambda e: e["delta_pct"])

    # Per-agent summary stats
    summary = {}
    for tid, traj in trajectories.items():
        if not traj:
            continue
        br_values = [t["bankroll_after"] for t in traj]
        br_peak = max(br_values) if br_values else 0
        br_final = br_values[-1] if br_values else 0
        br_start = traj[0].get("bankroll_before", 100) or 100
        drawdown_from_peak = ((br_peak - br_final) / br_peak * 100) if br_peak > 1 else 0
        # Top rationales at peak moments
        peak_days = sorted(traj, key=lambda t: -t["bankroll_after"])[:3]
        summary[tid] = {
            "n_days": len(traj),
            "bankroll_start": round(br_start, 2),
            "bankroll_final": round(br_final, 2),
            "bankroll_peak": round(br_peak, 2),
            "roi_final_pct": round((br_final - br_start) / max(1, br_start) * 100, 1),
            "roi_peak_pct": round((br_peak - br_start) / max(1, br_start) * 100, 1),
            "drawdown_from_peak_pct": round(drawdown_from_peak, 1),
            "peak_day": next((t["day"] for t in traj if t["bankroll_after"] == br_peak), None),
            "peak_rationales": [
                {"day": p["day"], "bankroll": p["bankroll_after"],
                 "strategy": p["strategy"][:300]}
                for p in peak_days
            ],
        }

    ranked = sorted(summary.items(), key=lambda kv: -kv[1]["bankroll_final"])

    result = {
        "fleet": fleet,
        "space": space,
        "n_days_analyzed": len(paths),
        "n_agents": len(summary),
        "agents_by_final_bankroll": ranked,
        "agents_by_peak_bankroll": sorted(summary.items(),
                                          key=lambda kv: -kv[1]["bankroll_peak"]),
    }

    # Write outputs
    (OUT_DIR / f"{fleet}-summary.json").write_text(
        json.dumps(result, indent=2, default=str))
    (OUT_DIR / f"{fleet}-peaks.json").write_text(
        json.dumps(jumps[:top], indent=2, default=str))
    (OUT_DIR / f"{fleet}-crashes.json").write_text(
        json.dumps(crashes[:top], indent=2, default=str))
    (OUT_DIR / f"{fleet}-council-timeline.json").write_text(
        json.dumps(council_timeline, indent=2, default=str))

    # Markdown report
    lines = [
        f"# {fleet.upper()} TF Post-Mortem — {len(paths)} days analyzed",
        f"Space: `{space}`",
        "",
        "## Leaderboard (by final bankroll)",
        "| rank | trader | final | peak | drawdown | peak_day |",
        "|------|--------|-------|------|----------|----------|",
    ]
    for i, (tid, s) in enumerate(ranked[:20], 1):
        lines.append(f"| {i} | `{tid}` | ${s['bankroll_final']:,.2f} "
                     f"| ${s['bankroll_peak']:,.2f} "
                     f"| {s['drawdown_from_peak_pct']}% | {s['peak_day']} |")
    lines += ["", "## Top peak-rationales (what winners thought at their best day)"]
    for tid, s in ranked[:3]:
        lines.append(f"\n### {tid} — peak ${s['bankroll_peak']:,.2f} on day {s['peak_day']}")
        for p in s.get("peak_rationales", [])[:2]:
            lines.append(f"- d{p['day']} (${p['bankroll']:,.2f}): {p['strategy']}")
    lines += ["", f"## Top {top} gainers (single-day jumps ≥+10%)"]
    for j in jumps[:top]:
        lines.append(f"- `{j['tid']}` d{j['day']} {j['date']}: "
                     f"${j['bankroll_before']:.2f}→${j['bankroll_after']:.2f} "
                     f"(+{j['delta_pct']}%) — {j['strategy'][:150]}")
    lines += ["", f"## Top {top} crashes (single-day drops ≤−20%)"]
    for c in crashes[:top]:
        lines.append(f"- `{c['tid']}` d{c['day']} {c['date']}: "
                     f"${c['bankroll_before']:.2f}→${c['bankroll_after']:.2f} "
                     f"({c['delta_pct']}%) — {c['strategy'][:150]}")

    (OUT_DIR / f"{fleet}-report.md").write_text("\n".join(lines))
    print(f"[{fleet}] wrote {OUT_DIR}/{fleet}-*.json + {fleet}-report.md")
    return result


def _sharpe(returns: list[float], ann_factor: float = 252.0) -> float:
    """Annualised Sharpe (daily returns, 0% risk-free)."""
    if len(returns) < 2:
        return 0.0
    n = len(returns)
    mean = sum(returns) / n
    var = sum((r - mean) ** 2 for r in returns) / (n - 1)
    std = math.sqrt(var) if var > 0 else 0.0
    if std == 0:
        return 0.0
    return round((mean / std) * math.sqrt(ann_factor), 3)


def _max_drawdown(bankrolls: list[float]) -> tuple[float, int]:
    """Return (max_dd_pct, recovery_days). recovery_days=-1 if never recovered."""
    if not bankrolls:
        return 0.0, 0
    peak = bankrolls[0]
    max_dd = 0.0
    trough_idx = 0
    peak_idx = 0
    for i, v in enumerate(bankrolls):
        if v > peak:
            peak = v
            peak_idx = i
        dd = (peak - v) / peak * 100 if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
            trough_idx = i
    # time-to-recover from trough
    trough_val = bankrolls[trough_idx]
    recover = -1
    for i in range(trough_idx + 1, len(bankrolls)):
        if bankrolls[i] >= peak:
            recover = i - trough_idx
            break
    return round(max_dd, 1), recover


def analyze_pqtf(top: int = 10) -> dict:
    """
    Analyze PQTF from local tf-analytics cache (data/tf-analytics/pqtf/day-*.json).
    Falls back to HF Space raw files only when local cache is absent (<2 snapshots)
    AND the HF files show real bankroll changes (not a fresh $600 reset).
    Produces data/tf-analysis/pqtf-report.md with multi-leg strategy breakdown.
    """
    token = _hf_token()
    space = FLEETS["pqtf"]["space"]

    # --- 1. Load local analytics snapshots (primary source) ---
    local_days: list[dict] = []
    if PQTF_ANALYTICS_DIR.exists():
        for fp in sorted(PQTF_ANALYTICS_DIR.glob("day-*.json")):
            try:
                local_days.append(json.loads(fp.read_text()))
            except Exception:
                pass
    print(f"[pqtf] {len(local_days)} local analytics snapshots found")

    # --- 2. Supplementary HF fetch only when local is absent ---
    hf_days: list[dict] = []
    if len(local_days) < 2:
        print(f"[pqtf] sparse local data — fetching from HF Space {space}")
        paths = list_day_files(space, token=token)
        print(f"[pqtf] found {len(paths)} day files on HF Space")
        for path in paths[:60]:
            d = load_day(space, path, token=token)
            if not d:
                continue
            # PQTF HF format uses agents_start/agents_end, skip flat-$600 reset days
            ae = d.get("agents_end") or {}
            as_ = d.get("agents_start") or {}
            total_start = sum(float(v) for v in as_.values())
            total_end = sum(float(v) for v in ae.values())
            if abs(total_end - total_start) > 0.01:
                hf_days.append(d)

    # Local analytics takes priority; HF only when no local data
    if local_days:
        raw_days = local_days
        data_source = "local-analytics"
    elif hf_days:
        raw_days = hf_days
        data_source = "hf-live"
    else:
        raw_days = []
        data_source = "none"

    print(f"[pqtf] analyzing {len(raw_days)} day snapshots (source: {data_source})")

    # --- 3. Per-agent accumulation ---
    # Local analytics format: top-level "per_agent" dict + "per_bet" list + "fleet" dict
    # HF live format:         "agents_start"/"agents_end" dicts + "sessions" list of {positions}
    agent_traj: dict[str, list[dict]] = {}
    strategy_counts: dict[str, int] = {
        "vertical": 0, "iron_condor": 0, "straddle": 0, "butterfly": 0,
        "call": 0, "put": 0, "other": 0,
    }
    strategy_pnl: dict[str, float] = {k: 0.0 for k in strategy_counts}

    for snap in sorted(raw_days, key=lambda d: str(d.get("date", "") or d.get("day", ""))):
        day_idx = snap.get("day_idx") or snap.get("day")
        date = str(snap.get("date", ""))

        # ── Local analytics format ──────────────────────────────────────
        per_agent = snap.get("per_agent", {})
        if per_agent:
            for tid, ag in per_agent.items():
                br_s = float(ag.get("bankroll_start") or ag.get("bankroll_before") or 0)
                br_e = float(ag.get("bankroll_end") or ag.get("bankroll_after") or 0)
                daily_ret = ag.get("day_return_pct", 0.0) or (
                    (br_e - br_s) / br_s * 100 if br_s > 0 else 0.0
                )
                agent_traj.setdefault(tid, []).append({
                    "day": day_idx, "date": date,
                    "br_start": br_s, "br_end": br_e,
                    "daily_ret": float(daily_ret),
                    "n_positions": ag.get("n_positions", 0),
                    "n_multi_leg": ag.get("n_multi_leg", 0),
                    "etfs": ag.get("etfs_touched", []),
                    "pacts": ag.get("pacts", 0),
                    "jaccard": float(ag.get("jaccard_vs_fleet_mean", 0.0) or 0.0),
                })
            for bet in snap.get("per_bet", []):
                leg_type = (bet.get("leg_type") or bet.get("type") or "").lower()
                if leg_type in strategy_counts:
                    strategy_counts[leg_type] += 1
                    strategy_pnl[leg_type] += float(bet.get("pnl", 0) or 0)
                elif leg_type:
                    strategy_counts["other"] += 1
            continue

        # ── HF live day file format (agents_start/agents_end + sessions) ──
        agents_start = snap.get("agents_start") or {}
        agents_end = snap.get("agents_end") or {}
        for tid in agents_start:
            br_s = float(agents_start.get(tid) or 0)
            br_e = float(agents_end.get(tid) or br_s)
            daily_ret = (br_e - br_s) / br_s * 100 if br_s > 0 else 0.0
            n_pos = 0
            etfs: list[str] = []
            for sess in snap.get("sessions", []):
                for pos in sess.get("positions", []):
                    if pos.get("trader_id") == tid or pos.get("tid") == tid:
                        n_pos += 1
                        leg_type = (pos.get("leg_type") or pos.get("type") or "").lower()
                        if leg_type in strategy_counts:
                            strategy_counts[leg_type] += 1
                        elif leg_type:
                            strategy_counts["other"] += 1
                        etf = pos.get("etf", "")
                        if etf and etf not in etfs:
                            etfs.append(etf)
            agent_traj.setdefault(tid, []).append({
                "day": day_idx, "date": date,
                "br_start": br_s, "br_end": br_e,
                "daily_ret": daily_ret,
                "n_positions": n_pos,
                "n_multi_leg": 0,
                "etfs": etfs,
                "pacts": 0,
                "jaccard": 0.0,
            })

    if not agent_traj:
        print("[pqtf] no agent trajectories parsed — writing minimal report", file=sys.stderr)

    # --- 4. Per-agent summary stats ---
    summary: dict[str, dict] = {}
    for tid, traj in agent_traj.items():
        if not traj:
            continue
        br_series = [t["br_end"] for t in traj if t["br_end"] > 0]
        br_start = traj[0].get("br_start") or 100.0
        br_final = br_series[-1] if br_series else br_start
        br_peak = max(br_series) if br_series else br_start
        daily_rets = [t["daily_ret"] for t in traj]
        sharpe = _sharpe(daily_rets)
        max_dd, recover = _max_drawdown(br_series)
        peak_days_sorted = sorted(traj, key=lambda t: -(t["br_end"] or 0))[:3]
        roi_pct = (br_final - br_start) / max(1.0, br_start) * 100
        summary[tid] = {
            "n_days": len(traj),
            "bankroll_start": round(br_start, 2),
            "bankroll_final": round(br_final, 2),
            "bankroll_peak": round(br_peak, 2),
            "roi_final_pct": round(roi_pct, 1),
            "roi_peak_pct": round((br_peak - br_start) / max(1.0, br_start) * 100, 1),
            "sharpe": sharpe,
            "max_drawdown_pct": max_dd,
            "drawdown_recovery_days": recover,
            "peak_day": next((t["day"] for t in traj if abs((t["br_end"] or 0) - br_peak) < 0.01), None),
            "peak_rationales": [
                {"day": p["day"], "bankroll": p["br_end"],
                 "etfs": p.get("etfs", []), "n_positions": p.get("n_positions", 0)}
                for p in peak_days_sorted[:2]
            ],
            "total_pacts": sum(t.get("pacts", 0) for t in traj),
            "avg_jaccard": round(
                sum(t.get("jaccard", 0.0) for t in traj) / max(1, len(traj)), 3
            ),
        }

    # --- 5. Session-Jaccard lockstep detection ---
    # Use per-day jaccard_fleet_mean from local snapshots
    jaccard_series = [
        snap["fleet"].get("jaccard_fleet_mean", 0.0)
        for snap in raw_days
        if snap.get("fleet")
    ]
    lockstep_max = max(jaccard_series) if jaccard_series else 0.0
    lockstep_mean = sum(jaccard_series) / len(jaccard_series) if jaccard_series else 0.0
    lockstep_warn = lockstep_max > 0.5
    lockstep_critical = lockstep_max > 0.8

    # --- 6. Write JSON outputs ---
    ranked = sorted(summary.items(), key=lambda kv: -kv[1]["bankroll_final"])
    result = {
        "fleet": "pqtf",
        "space": space,
        "n_days_analyzed": len(raw_days),
        "n_agents": len(summary),
        "strategy_counts": strategy_counts,
        "strategy_pnl": {k: round(v, 2) for k, v in strategy_pnl.items()},
        "lockstep": {
            "jaccard_max": round(lockstep_max, 3),
            "jaccard_mean": round(lockstep_mean, 3),
            "warn": lockstep_warn,
            "critical": lockstep_critical,
        },
        "agents_by_final_bankroll": ranked,
        "agents_by_sharpe": sorted(summary.items(), key=lambda kv: -kv[1]["sharpe"]),
    }
    (OUT_DIR / "pqtf-summary.json").write_text(json.dumps(result, indent=2, default=str))

    # Top single-day gains / losses
    events: list[dict] = []
    for tid, traj in agent_traj.items():
        for t in traj:
            if t["br_start"] > 0.01:
                events.append({"tid": tid, **t})
    peaks_ev = sorted([e for e in events if e["daily_ret"] >= 5], key=lambda e: -e["daily_ret"])
    crashes_ev = sorted([e for e in events if e["daily_ret"] <= -15], key=lambda e: e["daily_ret"])
    (OUT_DIR / "pqtf-peaks.json").write_text(json.dumps(peaks_ev[:top], indent=2, default=str))
    (OUT_DIR / "pqtf-crashes.json").write_text(json.dumps(crashes_ev[:top], indent=2, default=str))

    # --- 7. Markdown report ---
    total_positions = sum(strategy_counts.values())
    lines = [
        f"# PQTF Post-Mortem — {len(raw_days)} days analyzed",
        f"Space: `{space}`",
        f"Agents: {', '.join(sorted(summary.keys()))}",
        "",
        "## Leaderboard (by final bankroll)",
        "| rank | trader | start | final | ROI% | peak | max_dd | sharpe | peak_day |",
        "|------|--------|-------|-------|------|------|--------|--------|----------|",
    ]
    for i, (tid, s) in enumerate(ranked, 1):
        lines.append(
            f"| {i} | `{tid}` | ${s['bankroll_start']:,.0f} "
            f"| ${s['bankroll_final']:,.0f} "
            f"| {s['roi_final_pct']:+.1f}% "
            f"| ${s['bankroll_peak']:,.0f} "
            f"| {s['max_drawdown_pct']}% "
            f"| {s['sharpe']} "
            f"| {s['peak_day']} |"
        )

    lines += ["", "## Sharpe ranking"]
    sharpe_ranked = sorted(summary.items(), key=lambda kv: -kv[1]["sharpe"])
    for tid, s in sharpe_ranked:
        lines.append(f"- `{tid}`: Sharpe={s['sharpe']}, ROI={s['roi_final_pct']:+.1f}%, max_dd={s['max_drawdown_pct']}%"
                     f", recovery={s['drawdown_recovery_days']}d")

    lines += ["", "## Multi-leg strategy breakdown"]
    if total_positions == 0:
        lines.append("No position-level data available in analytics cache.")
    else:
        for leg_type, count in sorted(strategy_counts.items(), key=lambda kv: -kv[1]):
            if count == 0:
                continue
            pnl = strategy_pnl.get(leg_type, 0.0)
            pct = count / total_positions * 100
            lines.append(f"- **{leg_type}**: {count} positions ({pct:.1f}%) — PnL contribution: ${pnl:,.2f}")

    lines += ["", "## Session-Jaccard lockstep detection"]
    lockstep_label = "CRITICAL" if lockstep_critical else ("WARN" if lockstep_warn else "OK")
    lines.append(f"- Max session-Jaccard: {lockstep_max:.3f} — Mean: {lockstep_mean:.3f} — Status: **{lockstep_label}**")
    if lockstep_warn:
        lines.append(f"  - Threshold warn >0.50, critical >0.80. PQTF agents share too many ETF+direction combos.")

    lines += ["", "## Peak-day rationales (top 2 agents)"]
    for tid, s in ranked[:2]:
        lines.append(f"\n### {tid} — peak ${s['bankroll_peak']:,.0f} on day {s['peak_day']}")
        for p in s.get("peak_rationales", []):
            etfs_str = ", ".join(p.get("etfs", []))
            lines.append(f"- d{p['day']} (${p['bankroll']:,.0f}): {p['n_positions']} positions — ETFs: {etfs_str or 'n/a'}")

    lines += ["", f"## Top {top} single-day gainers (≥+5% daily)"]
    for ev in peaks_ev[:top]:
        lines.append(f"- `{ev['tid']}` d{ev['day']} {ev['date']}: "
                     f"${ev['br_start']:,.0f}→${ev['br_end']:,.0f} "
                     f"({ev['daily_ret']:+.2f}%) — {ev.get('n_positions', 0)} positions")

    lines += ["", f"## Top {top} single-day crashes (≤−15% daily)"]
    for ev in crashes_ev[:top]:
        lines.append(f"- `{ev['tid']}` d{ev['day']} {ev['date']}: "
                     f"${ev['br_start']:,.0f}→${ev['br_end']:,.0f} "
                     f"({ev['daily_ret']:+.2f}%) — {ev.get('n_positions', 0)} positions")

    (OUT_DIR / "pqtf-report.md").write_text("\n".join(lines))
    print(f"[pqtf] wrote {OUT_DIR}/pqtf-*.json + pqtf-report.md")
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fleet", choices=["nba", "pol", "both", "pqtf", "all"], default="both")
    ap.add_argument("--top", type=int, default=10)
    args = ap.parse_args()

    if args.fleet == "both":
        targets = ["nba", "pol"]
    elif args.fleet == "all":
        targets = ["nba", "pol", "pqtf"]
    elif args.fleet == "pqtf":
        targets = ["pqtf"]
    else:
        targets = [args.fleet]

    for f in targets:
        try:
            if f == "pqtf":
                analyze_pqtf(top=args.top)
            else:
                analyze_fleet(f, top=args.top)
        except Exception as e:
            import traceback
            print(f"[{f}] FAILED: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)


if __name__ == "__main__":
    main()
