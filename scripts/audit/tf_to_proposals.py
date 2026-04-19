#!/usr/bin/env python3
"""
TF-TO-PROPOSALS BRIDGE — analysis → DR FRANKENSTEIN implementation queue
=========================================================================
Reads post-mortem reports (nba/pol/pqtf-report.md), ALERT.json, and
tf-analytics/summary.json; emits data/research/tf-proposals-YYYY-MM-DD.json
as a prioritised list of engine-improvement proposals.

Rules:
  - Max 10 proposals per run.
  - Dedupe against yesterday's file (by lowercased title substring match).
  - Priority 1 = scientific integrity (leakage / lockstep / calibration).
  - Priority 2 = Brier-reducing feature / calibration (est_brier_delta <= -0.001).
  - Priority 3 = PnL-improving strategy (TF fleet-level).
  - Priority 4 = diversification / anti-groupthink.
  - Priority 5 = cosmetic / logging.
  - Every entry MUST cite a source_finding pointing to a specific section.

Usage:
  python3 scripts/audit/tf_to_proposals.py
  python3 scripts/audit/tf_to_proposals.py --date 2026-04-19  # override date
"""

import argparse
import json
import math
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
ANALYSIS_DIR = ROOT / "data" / "tf-analysis"
AUDIT_DIR = ROOT / "data" / "audit"
ANALYTICS_DIR = ROOT / "data" / "tf-analytics"
OUT_DIR = ROOT / "data" / "research"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_json(path: Path) -> object:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return None


def _read_text(path: Path) -> str:
    if path.exists():
        return path.read_text()
    return ""


def _fuzzy_match(title: str, existing_titles: list[str]) -> bool:
    """Return True if title is a near-duplicate of any existing title."""
    t = title.lower()
    words_t = set(re.split(r"\W+", t))
    for et in existing_titles:
        words_e = set(re.split(r"\W+", et.lower()))
        if not words_t or not words_e:
            continue
        overlap = len(words_t & words_e) / max(len(words_t), len(words_e))
        if overlap >= 0.60:
            return True
    return False


def _load_yesterday_titles(today: str) -> list[str]:
    """Load proposal titles from yesterday's file for dedup."""
    try:
        dt = datetime.strptime(today, "%Y-%m-%d") - timedelta(days=1)
        yesterday = dt.strftime("%Y-%m-%d")
    except ValueError:
        return []
    fp = OUT_DIR / f"tf-proposals-{yesterday}.json"
    data = _read_json(fp)
    if isinstance(data, list):
        return [p.get("title", "") for p in data if p.get("status") == "pending"]
    return []


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Alert-driven proposals (priority 1 — scientific integrity)
# ---------------------------------------------------------------------------

def proposals_from_alerts(alerts: list[dict], existing: list[str]) -> list[dict]:
    props: list[dict] = []
    seen_checks: set[str] = set()

    for alert in alerts:
        severity = alert.get("severity", "")
        floor = alert.get("floor", "")
        check = alert.get("check", "")
        detail = alert.get("detail", {})
        at = alert.get("at", "")
        key = f"{floor}/{check}"
        if key in seen_checks:
            continue
        seen_checks.add(key)

        if check == "lockstep":
            worst = detail.get("worst_share", 0) if isinstance(detail, dict) else 0
            title = f"Fix {floor.upper()} TF DMAD lockstep (Jaccard {worst:.2f})"
            if _fuzzy_match(title, existing):
                continue
            per_day_info = ""
            if isinstance(detail, dict) and detail.get("per_day"):
                worst_day = max(detail["per_day"], key=lambda d: d.get("share_pct", 0))
                per_day_info = (f"day {worst_day.get('day', '?')}: "
                                f"{worst_day.get('share_10', 0)}/{worst_day.get('total', 0)} bets shared "
                                f"({worst_day.get('share_pct', 0):.1%})")
            props.append({
                "title": title,
                "rationale": (
                    f"{floor.upper()} TF agents are choosing identical bets (worst Jaccard={worst:.2f}). "
                    f"DMAD divergence forcing is insufficient. Increasing per-agent jitter amplitude "
                    f"or adding a mandatory ETF/game exclusion zone should reduce lockstep below 0.50."
                ),
                "target_file": f"scripts/arena/hf-{'llm' if floor in ('nba','pol') else 'political-quant'}-trading-floor/app.py",
                "est_brier_delta": None,
                "est_sharpe_delta": 0.10,
                "priority": 1,
                "source_finding": f"ALERT.json {severity} {floor}/{check} at {at} — {per_day_info}",
                "status": "pending",
                "created": _now_iso(),
            })

        elif check == "wr" and severity == "critical":
            flags = detail.get("flags", []) if isinstance(detail, dict) else []
            wr_max = max((f.get("wr", 0) for f in flags), default=0)
            title = f"Investigate {floor.upper()} TF WR outlier ({wr_max:.0%} WR on {len(flags)} agents)"
            if _fuzzy_match(title, existing):
                continue
            props.append({
                "title": title,
                "rationale": (
                    f"Critical WR outlier detected: {len(flags)} agents at ≥100% win-rate over 20 bets on {floor}. "
                    f"This matches the pre-fix $13K leakage pattern (excess_return used as signal). "
                    f"Verify that post-filter walk-forward does NOT use future outcome fields."
                ),
                "target_file": f"scripts/arena/hf-{'llm' if floor in ('nba','pol') else 'political-quant'}-trading-floor/app.py",
                "est_brier_delta": None,
                "est_sharpe_delta": None,
                "priority": 1,
                "source_finding": (
                    f"ALERT.json {severity} {floor}/{check} at {at} — "
                    f"{flags[0].get('tid','?')} WR={flags[0].get('wr',0):.0%} n={flags[0].get('n',0)}"
                    if flags else f"ALERT.json {severity} {floor}/{check} at {at}"
                ),
                "status": "pending",
                "created": _now_iso(),
            })

        elif check == "source":
            direct_ratio = detail.get("direct_ratio", 1.0) if isinstance(detail, dict) else 1.0
            if direct_ratio < 0.10:
                title = f"Boost {floor.upper()} TF LLM direct-bet ratio (now {direct_ratio:.1%})"
                if _fuzzy_match(title, existing):
                    continue
                counts = detail.get("counts", {}) if isinstance(detail, dict) else {}
                props.append({
                    "title": title,
                    "rationale": (
                        f"LLMs are nearly silent: only {direct_ratio:.1%} of bets are direct LLM choices; "
                        f"post-filter does the rest ({counts}). "
                        f"This defeats the agent-heterogeneity goal. Lowering post-filter dominance "
                        f"or raising minimum direct-bets-per-day to 5 would force genuine reasoning."
                    ),
                    "target_file": f"scripts/arena/hf-{'llm' if floor in ('nba','pol') else 'political-quant'}-trading-floor/app.py",
                    "est_brier_delta": None,
                    "est_sharpe_delta": 0.05,
                    "priority": 2,
                    "source_finding": (
                        f"ALERT.json {severity} {floor}/{check} at {at} — "
                        f"direct_ratio={direct_ratio:.1%}, counts={counts}"
                    ),
                    "status": "pending",
                    "created": _now_iso(),
                })

        elif check == "leakage" and severity == "critical":
            title = f"CRITICAL: {floor.upper()} TF thesis↔outcome leakage re-detected"
            if _fuzzy_match(title, existing):
                continue
            props.append({
                "title": title,
                "rationale": (
                    f"Leakage detected on {floor}. The thesis field contains a numeric value that "
                    f"correlates >0.80 with resolved excess_return/pnl_pct. This is the $13K bug class. "
                    f"Remove any field that embeds future-outcome data into the prompt or signal calculation."
                ),
                "target_file": f"scripts/arena/hf-{'llm' if floor in ('nba','pol') else 'political-quant'}-trading-floor/app.py",
                "est_brier_delta": None,
                "est_sharpe_delta": None,
                "priority": 1,
                "source_finding": f"ALERT.json {severity} {floor}/{check} at {at} — {detail}",
                "status": "pending",
                "created": _now_iso(),
            })

    return props


# ---------------------------------------------------------------------------
# Report-driven proposals (priority 3-4 — strategy + diversification)
# ---------------------------------------------------------------------------

def proposals_from_nba_report(report: str, existing: list[str]) -> list[dict]:
    props: list[dict] = []
    if not report:
        return props

    # Pattern: top survivors all use "post-filter: N picks (max edge +8.0%)"
    postfilter_winners = re.findall(
        r"\| \d+ \| `(\S+)` \|[^|]+\|[^|]+\| 0\.0% \|", report
    )
    if len(postfilter_winners) >= 3:
        title = "NBA TF: top survivors rely on post-filter, not LLM reasoning"
        if not _fuzzy_match(title, existing):
            names = ", ".join(postfilter_winners[:3])
            props.append({
                "title": title,
                "rationale": (
                    f"The top 3 NBA TF agents ({names}) all have 0% drawdown and "
                    f"their peak-rationales read 'post-filter: N picks'. This means "
                    f"genuine LLM reasoning has no demonstrated edge over the walk-forward baseline. "
                    f"The STRUCTURAL DIVERGE mandate should be tightened: require LLMs to "
                    f"select at least 3 direct bets from outside the post-filter top-5."
                ),
                "target_file": "scripts/arena/hf-llm-trading-floor/app.py",
                "est_brier_delta": None,
                "est_sharpe_delta": 0.08,
                "priority": 3,
                "source_finding": (
                    f"nba-report.md Leaderboard section — {names} at 0% drawdown "
                    f"with peak-rationales 'post-filter: N picks (max edge +8.0%)'"
                ),
                "status": "pending",
                "created": _now_iso(),
            })

    # Pattern: crashes mention "eighth_kelly sizing on teasers" or ml_home
    ml_home_crash = re.search(r"ml_home\b", report)
    if ml_home_crash:
        title = "NBA TF: ml_home fabricated fallback still appears in crash rationales"
        if not _fuzzy_match(title, existing):
            props.append({
                "title": title,
                "rationale": (
                    "The text 'ml_home' appears in a crash day rationale. ml_home was the "
                    "FORBIDDEN fabricated fallback category (removed in commit 412fc6a19). "
                    "Verify the removal is live on HF Space and not still being generated "
                    "by a cached model or older app.py version."
                ),
                "target_file": "scripts/arena/hf-llm-trading-floor/app.py",
                "est_brier_delta": None,
                "est_sharpe_delta": None,
                "priority": 1,
                "source_finding": "nba-report.md Top crashes section — 'ml_home' keyword in crash rationale",
                "status": "pending",
                "created": _now_iso(),
            })

    # High variance agents: drawdown > 50%
    high_dd_agents = re.findall(r"`(\S+)` \| \$[\d,.]+\s*\| \$[\d,.]+\s*\| ([\d.]+)%", report)
    brutal_dd = [(m[0], float(m[1])) for m in high_dd_agents if float(m[1]) > 55]
    if len(brutal_dd) >= 3:
        names = ", ".join(f"{a}({d:.0f}%)" for a, d in brutal_dd[:3])
        title = "NBA TF: Kelly cap too loose — multiple agents >55% drawdown"
        if not _fuzzy_match(title, existing):
            props.append({
                "title": title,
                "rationale": (
                    f"Agents {names} show >55% drawdown from peak. "
                    f"Reducing the tiered Kelly cap (currently 2%/5%/10%) or adding "
                    f"a hard 25%-of-bankroll daily loss stop would preserve capital "
                    f"through losing streaks while keeping compounding for winners."
                ),
                "target_file": "scripts/arena/hf-llm-trading-floor/app.py",
                "est_brier_delta": None,
                "est_sharpe_delta": 0.12,
                "priority": 3,
                "source_finding": f"nba-report.md Leaderboard — {names} drawdown_from_peak > 55%",
                "status": "pending",
                "created": _now_iso(),
            })

    return props


def proposals_from_pol_report(report: str, existing: list[str]) -> list[dict]:
    props: list[dict] = []
    if not report:
        return props

    # Pattern: "tier-pad: 37 events" in top gainers = lockstep artifact
    tier_pad_count = len(re.findall(r"tier-pad:", report))
    if tier_pad_count >= 5:
        title = "POL TF: tier-pad lockstep artifacts dominate top-gainer list"
        if not _fuzzy_match(title, existing):
            props.append({
                "title": title,
                "rationale": (
                    f"Found {tier_pad_count} 'tier-pad' occurrences in pol-report.md. "
                    f"These are post-filter injections (not genuine LLM picks) that cause "
                    f"all agents to bet identically on high-event days. "
                    f"Commit 482698f34 claims to have killed this — verify the fix is live "
                    f"on the HF Space and that tier-pad no longer appears in new day-XXX.json files."
                ),
                "target_file": "scripts/arena/hf-political-trading-floor/app.py",
                "est_brier_delta": None,
                "est_sharpe_delta": 0.15,
                "priority": 1,
                "source_finding": (
                    f"pol-report.md Top gainers + peak-rationales sections — "
                    f"{tier_pad_count} tier-pad injections found, e.g. d22 'tier-pad: 37 events'"
                ),
                "status": "pending",
                "created": _now_iso(),
            })

    # Pattern: All peaks at day 29 = suspiciously correlated
    day29_peaks = len(re.findall(r"\| 29 \|", report))
    if day29_peaks >= 10:
        title = "POL TF: all agents peak on same day (day-29 concentration risk)"
        if not _fuzzy_match(title, existing):
            props.append({
                "title": title,
                "rationale": (
                    f"{day29_peaks} agents share peak_day=29, indicating a single big-event "
                    f"day drove the whole fleet's best result simultaneously. This is a "
                    f"diversification failure: if that event had resolved the other way, "
                    f"it would have been a fleet-wide catastrophe. "
                    f"Add a per-event notional cap (e.g. max 20% of daily deployment on one event)."
                ),
                "target_file": "scripts/arena/hf-political-trading-floor/app.py",
                "est_brier_delta": None,
                "est_sharpe_delta": 0.10,
                "priority": 4,
                "source_finding": (
                    f"pol-report.md Leaderboard — {day29_peaks} agents with peak_day=29"
                ),
                "status": "pending",
                "created": _now_iso(),
            })

    # Uniform crashes at day 40
    day40_crashes = len(re.findall(r"d40.*?-30\.", report))
    if day40_crashes >= 3:
        title = "POL TF: coordinated -30% fleet crash on day-40 (single-event exposure)"
        if not _fuzzy_match(title, existing):
            props.append({
                "title": title,
                "rationale": (
                    f"{day40_crashes} agents crashed ~-30% on day-40. This uniform loss "
                    f"suggests all agents were on the same side of a single event ('tier-pad: 4 events'). "
                    f"Enforce a per-day max-event-concentration rule: no single political event "
                    f"can represent >15% of fleet daily notional."
                ),
                "target_file": "scripts/arena/hf-political-trading-floor/app.py",
                "est_brier_delta": None,
                "est_sharpe_delta": 0.12,
                "priority": 3,
                "source_finding": (
                    f"pol-report.md Top crashes — {day40_crashes} agents at -30% on d40 2026-03-20 "
                    f"with rationale 'tier-pad: 4 events'"
                ),
                "status": "pending",
                "created": _now_iso(),
            })

    return props


def proposals_from_pqtf_report(report: str, existing: list[str]) -> list[dict]:
    props: list[dict] = []
    if not report:
        return props

    # Check lockstep status
    lockstep_match = re.search(r"Max session-Jaccard:\s*([\d.]+).*?Status:\s*\*\*(\w+)\*\*", report)
    if lockstep_match:
        jaccard_max = float(lockstep_match.group(1))
        status = lockstep_match.group(2)
        if status in ("WARN", "CRITICAL"):
            title = f"PQTF: session-Jaccard lockstep {status.lower()} ({jaccard_max:.3f})"
            if not _fuzzy_match(title, existing):
                props.append({
                    "title": title,
                    "rationale": (
                        f"PQTF session-Jaccard={jaccard_max:.3f} ({status}). "
                        f"Multiple agents are entering the same ETF+direction on the same session. "
                        f"Increase the blake2b per-agent jitter amplitude on the options engine, "
                        f"or add an ETF exclusion zone so no two agents can both open the "
                        f"same leg type on the same underlying within 1 session."
                    ),
                    "target_file": "scripts/arena/hf-political-quant-trading-floor/engine.py",
                    "est_brier_delta": None,
                    "est_sharpe_delta": 0.10,
                    "priority": 4,
                    "source_finding": (
                        f"pqtf-report.md Session-Jaccard section — "
                        f"max={jaccard_max:.3f}, status={status}"
                    ),
                    "status": "pending",
                    "created": _now_iso(),
                })

    # Check multi-leg usage — if vertical/iron_condor/straddle/butterfly are 0
    multi_leg_missing: list[str] = []
    for leg in ("vertical", "iron_condor", "straddle", "butterfly"):
        m = re.search(rf"\*\*{leg}\*\*.*?(\d+) positions", report)
        if not m or int(m.group(1)) == 0:
            multi_leg_missing.append(leg)

    if len(multi_leg_missing) >= 2:
        missing_str = ", ".join(multi_leg_missing)
        title = f"PQTF: multi-leg strategies unused ({missing_str})"
        if not _fuzzy_match(title, existing):
            props.append({
                "title": title,
                "rationale": (
                    f"PQTF Phase 2 wired {missing_str} but 0 positions of these types appear "
                    f"in the analytics. The engine may be falling back to single-leg only "
                    f"due to a parsing failure or the LLM not producing multi-leg JSON. "
                    f"Add a prompt example with explicit iron_condor/straddle syntax and "
                    f"verify the spreads.py parser handles these structures."
                ),
                "target_file": "scripts/arena/hf-political-quant-trading-floor/spreads.py",
                "est_brier_delta": None,
                "est_sharpe_delta": 0.15,
                "priority": 3,
                "source_finding": (
                    f"pqtf-report.md Multi-leg strategy breakdown — "
                    f"{missing_str} each showing 0 positions"
                ),
                "status": "pending",
                "created": _now_iso(),
            })

    # Check for negative-Sharpe agents
    neg_sharpe = re.findall(r"`(\S+)`: Sharpe=(-[\d.]+),", report)
    if neg_sharpe:
        names = ", ".join(f"{a}(Sharpe={s})" for a, s in neg_sharpe[:2])
        title = f"PQTF: negative Sharpe agents ({names})"
        if not _fuzzy_match(title, existing):
            props.append({
                "title": title,
                "rationale": (
                    f"PQTF agents {names} have negative Sharpe ratios, meaning risk-adjusted "
                    f"returns are below zero. Review their position sizing — they may be "
                    f"over-sizing IV-expansion bets near event dates. "
                    f"Introduce a per-agent VaR-based position cap (already tracked as avg_var_95) "
                    f"that reduces notional when Sharpe drops below 0 over a 10-day window."
                ),
                "target_file": "scripts/arena/hf-political-quant-trading-floor/engine.py",
                "est_brier_delta": None,
                "est_sharpe_delta": 0.20,
                "priority": 3,
                "source_finding": f"pqtf-report.md Sharpe ranking — {names}",
                "status": "pending",
                "created": _now_iso(),
            })

    return props


def proposals_from_analytics(analytics: dict, existing: list[str]) -> list[dict]:
    """Extract diversification proposals from tf-analytics/summary.json."""
    props: list[dict] = []
    if not analytics:
        return props

    tfs = analytics.get("tfs", {})
    for floor, data in tfs.items():
        fleet = data.get("fleet", {})
        jaccard_max = fleet.get("jaccard_fleet_max", 0.0) or 0.0
        jaccard_mean = fleet.get("jaccard_fleet_mean", 0.0) or 0.0

        if floor == "pqtf":
            # Separate PQTF proposal track
            if jaccard_mean < 0.05 and fleet.get("n_agents", 0) > 0:
                title = "PQTF: near-zero session-Jaccard (agents too uncorrelated?)"
                if not _fuzzy_match(title, existing):
                    props.append({
                        "title": title,
                        "rationale": (
                            f"PQTF fleet Jaccard mean={jaccard_mean:.3f} is near zero. "
                            f"While low correlation is generally good, near-zero may indicate "
                            f"agents are ignoring each other's signals entirely (no coalition pacts). "
                            f"Review pact count: if <2 pacts/day fleet-wide, the mandatory coalition "
                            f"prompt may be broken."
                        ),
                        "target_file": "scripts/arena/hf-political-quant-trading-floor/engine.py",
                        "est_brier_delta": None,
                        "est_sharpe_delta": 0.05,
                        "priority": 5,
                        "source_finding": (
                            f"tf-analytics/summary.json tfs.pqtf.fleet — "
                            f"jaccard_fleet_mean={jaccard_mean:.3f}, "
                            f"jaccard_fleet_max={jaccard_max:.3f}"
                        ),
                        "status": "pending",
                        "created": _now_iso(),
                    })
        elif floor in ("nba", "pol"):
            if jaccard_mean > 0.60:
                title = f"{floor.upper()} TF analytics: fleet Jaccard still elevated ({jaccard_mean:.2f})"
                if not _fuzzy_match(title, existing):
                    day_wr = fleet.get("day_fleet_wr", None)
                    props.append({
                        "title": title,
                        "rationale": (
                            f"{floor.upper()} fleet Jaccard={jaccard_mean:.2f} in analytics summary. "
                            f"Day WR={day_wr}. "
                            f"Agents are still converging despite DMAD jitter. "
                            f"Consider raising blake2b jitter amplitude from 0.30 → 0.50, "
                            f"or adding a category-ban list so each agent excludes 20% of categories."
                        ),
                        "target_file": f"scripts/arena/hf-{'llm' if floor in ('nba','pol') else 'political-quant'}-trading-floor/app.py",
                        "est_brier_delta": None,
                        "est_sharpe_delta": 0.08,
                        "priority": 4,
                        "source_finding": (
                            f"tf-analytics/summary.json tfs.{floor}.fleet — "
                            f"jaccard_fleet_mean={jaccard_mean:.2f}, day_fleet_wr={day_wr}"
                        ),
                        "status": "pending",
                        "created": _now_iso(),
                    })

    return props


# ---------------------------------------------------------------------------
# Main assembly
# ---------------------------------------------------------------------------

def run(today: str) -> list[dict]:
    yesterday_titles = _load_yesterday_titles(today)

    # Load inputs
    alerts = _read_json(AUDIT_DIR / "ALERT.json") or []
    analytics = _read_json(ANALYTICS_DIR / "summary.json") or {}
    nba_report = _read_text(ANALYSIS_DIR / "nba-report.md")
    pol_report = _read_text(ANALYSIS_DIR / "pol-report.md")
    pqtf_report = _read_text(ANALYSIS_DIR / "pqtf-report.md")

    all_props: list[dict] = []

    # Gather from each source
    all_props.extend(proposals_from_alerts(alerts, yesterday_titles + [p["title"] for p in all_props]))
    all_props.extend(proposals_from_nba_report(nba_report, yesterday_titles + [p["title"] for p in all_props]))
    all_props.extend(proposals_from_pol_report(pol_report, yesterday_titles + [p["title"] for p in all_props]))
    all_props.extend(proposals_from_pqtf_report(pqtf_report, yesterday_titles + [p["title"] for p in all_props]))
    all_props.extend(proposals_from_analytics(analytics, yesterday_titles + [p["title"] for p in all_props]))

    # Sort: priority ASC, then abs(brier_delta) DESC (None treated as 0)
    def sort_key(p: dict):
        bd = p.get("est_brier_delta")
        brier_sort = abs(bd) if bd is not None else 0.0
        return (p.get("priority", 5), -brier_sort)

    all_props.sort(key=sort_key)

    # Assign sequential IDs, cap at 10
    result = []
    for i, prop in enumerate(all_props[:10], 1):
        prop["id"] = f"tf-{today}-{i:02d}"
        result.append(prop)

    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    args = ap.parse_args()

    today = args.date
    print(f"[tf_to_proposals] running for {today}")

    proposals = run(today)
    out_path = OUT_DIR / f"tf-proposals-{today}.json"
    out_path.write_text(json.dumps(proposals, indent=2, default=str))
    print(f"[tf_to_proposals] wrote {len(proposals)} proposals → {out_path}")
    for p in proposals:
        print(f"  P{p['priority']} [{p['id']}] {p['title']}")


if __name__ == "__main__":
    main()
