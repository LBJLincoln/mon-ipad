#!/usr/bin/env python3
"""Daily scientific digest — single-file morning briefing.

Pulls the freshest output of every monitoring system:
  - baseline check PASS/FAIL per TF
  - scorecard (WR, Brier, source purity)
  - rigorous validation (CI95, ECE, walk-forward stability)
  - cross-LLM view (which LLM leads across markets)
  - improvement cycle actions in the last 24h
  - champion preserve (any agent crossed $500 threshold)

Output: data/audit/digest-<YYYY-MM-DD>.md  (one per day, committed)

Cron: 0 6 * * *   (every morning 06:00 UTC)
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
AUDIT = REPO / "data" / "audit"
OPS = REPO / "data" / "ops"


def _read_json(p: Path) -> dict:
    try: return json.loads(p.read_text())
    except Exception: return {}


def _jsonl_tail(p: Path, n: int = 50) -> list[dict]:
    if not p.exists(): return []
    lines = p.read_text().splitlines()[-n:]
    out = []
    for line in lines:
        try: out.append(json.loads(line))
        except Exception: continue
    return out


def main() -> int:
    today = dt.date.today().isoformat()
    now = dt.datetime.now(dt.timezone.utc)

    # Data sources
    baseline = _read_json(OPS / "tf-baseline-latest.json")
    scorecard_md = (AUDIT / "scorecard-latest.md").read_text() if (AUDIT / "scorecard-latest.md").exists() else ""
    rigorous_md = (AUDIT / "rigorous-latest.md").read_text() if (AUDIT / "rigorous-latest.md").exists() else ""
    cross_llm = _read_json(AUDIT / "cross-llm-latest.json")
    improvement_hist = _jsonl_tail(OPS / "tf-improvement-history.jsonl", 200)
    champions = _read_json(REPO / "data" / "champions" / "index.json")

    # Trim improvements to last 24h applied
    cutoff = now - dt.timedelta(hours=24)
    applied_24h = []
    for e in improvement_hist:
        if not e.get("applied"): continue
        try:
            t = dt.datetime.fromisoformat(e["ts"])
        except Exception: continue
        if t > cutoff: applied_24h.append(e)

    # Build the markdown
    lines = [
        f"# Daily Scientific Digest — {today}",
        f"Generated: {now.strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## Integrity gate (tf_baseline_check)",
    ]
    if baseline.get("overall"):
        lines.append(f"**Overall: {baseline['overall']}**")
        for tf in ("nba", "pol", "itf"):
            x = baseline.get(tf, {})
            fails = [n for n, c in (x.get("checks") or {}).items() if not c.get("ok")]
            lines.append(f"- {tf.upper()}: {x.get('status', '?')}" + (f"  failing: {fails}" if fails else ""))
    else:
        lines.append("_(no baseline data)_")
    lines.append("")

    # Rigorous (preferred — CI95 + ECE included)
    lines.append("## Rigorous validation (bootstrap CI95 + ECE)")
    if rigorous_md:
        # Extract just the headline metrics per TF
        in_tf = None
        for l in rigorous_md.splitlines():
            if l.startswith("## ") and "VALIDATION" not in l.upper():
                in_tf = l.strip()
                lines.append("")
                lines.append(l)
            elif in_tf and l.startswith("- "):
                # Keep only the 5 headline lines per TF (window/Brier/WR/PnL/ECE)
                if any(k in l for k in ("window:", "**Brier**", "**Win rate**", "**PnL**", "**ECE**")):
                    lines.append(l)
            elif l.startswith("## Cross-TF"):
                in_tf = None
                lines.append("")
                lines.append(l)
            elif l.startswith("- ") and "significant" in l:
                lines.append(l)
    else:
        lines.append("_(no rigorous data)_")
    lines.append("")

    # Cross-LLM top
    lines.append("## LLM leaderboard (cross-market)")
    top = (cross_llm.get("by_llm") or [])[:5]
    if top:
        lines.append("| LLM | Total $ | TFs | WR | Bets |")
        lines.append("|---|---:|---|---:|---:|")
        for s in top:
            wr = s.get("wr_combined")
            wr_s = f"{wr:.1%}" if wr is not None else "-"
            lines.append(f"| `{s['llm']}` | ${s['total_bankroll']:.0f} | {','.join(s['tfs_present'])} | {wr_s} | {s.get('total_bets','-')} |")
    else:
        lines.append("_(no cross-llm data)_")
    lines.append("")

    # Improvement actions in 24h
    lines.append("## Auto-improvement cycle — changes applied (last 24h)")
    if applied_24h:
        lines.append("| TF | agent | action | kelly_from → kelly_to | reason |")
        lines.append("|---|---|---|---|---|")
        for e in applied_24h[-20:]:
            lines.append(
                f"| {e.get('tf','?')} | `{e.get('tid','?')}` | {e.get('decision','?')} | "
                f"{e.get('current_kelly')} → {e.get('proposed_kelly')} | {e.get('reason','')[:60]} |"
            )
    else:
        lines.append("_no kelly changes applied in last 24h (system stable or below signal threshold)_")
    lines.append("")

    # Champions (any agent > $500 threshold ever captured)
    lines.append("## Champion-preserve ledger")
    chs = champions.get("champions", []) if isinstance(champions, dict) else []
    if chs:
        lines.append(f"{len(chs)} historical champion snapshots preserved.")
        for c in chs[-5:]:
            lines.append(f"- `{c.get('tid','?')}` ({c.get('tf','?')}) bankroll=${c.get('bankroll',0):.0f} at {c.get('captured_at','')[:16]}")
    else:
        lines.append("_no agent has crossed the $500 threshold yet — still early_")
    lines.append("")

    # Path to $1M math
    lines.append("## Path to $1M — honest math")
    for tf in ("nba", "pol"):
        x = baseline.get(tf, {})
        details = (x.get("details") or {})
        # crude fleet estimate from monoculture "avg"
        avg = ((details.get("monoculture") or {}).get("evidence") or {}).get("avg")
        if avg is not None:
            fleet = avg * 17
            lines.append(f"- {tf.upper()}: current fleet ≈ ${fleet:.0f} from $1700 seed. To $1M/agent = {1000000/max(avg,1):.0f}× from current.")
    itf_bank = ((baseline.get("itf") or {}).get("details") or {}).get("equity_parity", {}).get("evidence", {})
    if itf_bank.get("fleet_equity"):
        fe = itf_bank["fleet_equity"]
        lines.append(f"- ITF: ${fe:,.0f} Alpaca equity. To $1M = {1_000_000/max(fe,1):.1f}×.")
    lines.append("- PQTF: $602K frozen (static).")
    lines.append("")

    lines.append("---")
    lines.append("*Auto-generated by scripts/ops/daily_scientific_digest.py*")

    out = AUDIT / f"digest-{today}.md"
    out.write_text("\n".join(lines))
    # Also update a symlink-like "latest"
    (AUDIT / "digest-latest.md").write_text("\n".join(lines))
    print(f"digest written: {out}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
