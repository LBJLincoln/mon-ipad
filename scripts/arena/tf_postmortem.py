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

Outputs:
  data/tf-analysis/<fleet>-summary.json   — per-agent trajectory + stats
  data/tf-analysis/<fleet>-peaks.json     — top 10 bankroll jumps with rationale
  data/tf-analysis/<fleet>-crashes.json   — top 10 drawdowns with rationale
  data/tf-analysis/<fleet>-report.md      — human-readable comparison
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = ROOT / "data" / "tf-analysis"
OUT_DIR.mkdir(parents=True, exist_ok=True)

FLEETS = {
    "nba": {
        "space": "LBJLincoln26/nba-llm-trading-floor",
        "url": "https://huggingface.co/spaces/LBJLincoln26/nba-llm-trading-floor",
    },
    "pol": {
        "space": "LBJLincoln26/political-llm-trading-floor",
        "url": "https://huggingface.co/spaces/LBJLincoln26/political-llm-trading-floor",
    },
}


def _get_json(url: str, timeout: int = 20):
    req = Request(url, headers={"User-Agent": "tf-postmortem/1.0"})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def list_day_files(space: str) -> list[str]:
    api = f"https://huggingface.co/api/spaces/{space}/tree/main/data/decisions?recursive=true"
    try:
        tree = _get_json(api)
    except (URLError, HTTPError) as e:
        print(f"[{space}] listing failed: {e}", file=sys.stderr)
        return []
    return sorted(f["path"] for f in tree if f.get("type") == "file"
                  and f["path"].endswith(".json"))


def load_day(space: str, path: str) -> dict | None:
    raw = f"https://huggingface.co/spaces/{space}/raw/main/{path}"
    try:
        return _get_json(raw)
    except (URLError, HTTPError):
        return None


def extract_raw_strategy(raw_preview: str) -> str:
    """raw_preview starts with LLM JSON. Pull day_strategy field."""
    if not raw_preview:
        return ""
    m = re.search(r'"day_strategy"\s*:\s*"([^"]{1,400})', raw_preview)
    return m.group(1) if m else raw_preview[:200]


def analyze_fleet(fleet: str, top: int = 10) -> dict:
    space = FLEETS[fleet]["space"]
    print(f"[{fleet}] fetching day file index from {space}...")
    paths = list_day_files(space)
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
        day = load_day(space, path)
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fleet", choices=["nba", "pol", "both"], default="both")
    ap.add_argument("--top", type=int, default=10)
    args = ap.parse_args()

    fleets = ["nba", "pol"] if args.fleet == "both" else [args.fleet]
    for f in fleets:
        try:
            analyze_fleet(f, top=args.top)
        except Exception as e:
            print(f"[{f}] FAILED: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
