#!/usr/bin/env python3
"""
Obsidian Karpathy Brain — Wiki Builder
=======================================
Builds wiki/learnings/ articles from structured analysis in raw/learnings/
and raw/karpathy/. Unlike compile.py (which uses keyword matching to
classify raw files into topic articles), this script builds
ACTIONABLE LEARNING articles from structured data.

Output: wiki/learnings/*.md — articles the brain reads for mutation decisions.

Three kinds of articles:
  1. what-works.md — Empirically proven techniques and strategies
  2. what-fails.md — Things that have been tried and failed
  3. current-state.md — Where we are right now (fleet, Brier, bankroll)

Usage:
  python3 scripts/research-vault/wiki-builder.py
  python3 scripts/research-vault/wiki-builder.py --dry-run
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

ROOT = Path("/home/termius/mon-ipad")
VAULT = ROOT / "research-vault"
WIKI_LEARNINGS = VAULT / "wiki" / "learnings"
RAW_LEARNINGS = VAULT / "raw" / "learnings"
RAW_KARPATHY = VAULT / "raw" / "karpathy"


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _load_json(path: Path, default=None):
    if default is None:
        default = {}
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return default


def build_what_works():
    """Build wiki/learnings/what-works.md — empirically validated techniques."""
    lines = [
        "# What Works — Empirically Validated",
        "",
        f"> Auto-generated from experiment data on {_now()}",
        "> Only includes findings backed by measured improvement",
        "",
    ]

    # 1. From karpathy mutation analysis
    for domain in ["nba", "political"]:
        raw_file = RAW_KARPATHY / f"{domain}-mutation-analysis.md"
        if not raw_file.exists():
            continue

        content = raw_file.read_text()

        # Parse mutation table
        lines.append(f"## {domain.upper()} — Mutation Effectiveness")
        lines.append("")

        # Extract lines between "Mutation Type Effectiveness" and next ##
        in_table = False
        for line in content.split("\n"):
            if "Mutation Type Effectiveness" in line:
                in_table = True
                continue
            if in_table and line.startswith("## "):
                break
            if in_table and line.strip():
                lines.append(line)

        lines.append("")

    # 2. From arena lessons
    lessons_file = ROOT / "data" / "arena" / "lessons-learned.json"
    lessons = _load_json(lessons_file)

    insights = lessons.get("key_insights", [])
    if insights:
        lines.extend(["## Arena — Proven Insights", ""])
        for i, insight in enumerate(insights, 1):
            lines.append(f"{i}. {insight}")
        lines.append("")

    optimal = lessons.get("optimal_params", {})
    if optimal:
        lines.extend(["## Arena — Optimal Parameters", ""])
        for k, v in optimal.items():
            lines.append(f"- **{k}**: {v}")
        lines.append("")

    # 3. From backtest
    bt = _load_json(ROOT / "data" / "nba-agent" / "full-season-backtest.json")
    if bt:
        roi = bt.get("roi_pct", 0)
        wr = bt.get("win_rate", 0)
        sharpe = bt.get("sharpe", 0)
        strategy = bt.get("strategy", "unknown")
        brier = bt.get("brier", 0)

        lines.extend([
            "## Current Best Strategy (Backtest)",
            "",
            f"- Strategy: **{strategy}**",
            f"- ROI: {roi:.1f}%",
            f"- Win rate: {wr:.1f}%",
            f"- Sharpe: {sharpe}",
            f"- Brier: {brier:.5f}" if isinstance(brier, float) else f"- Brier: {brier}",
            "",
        ])

    # 4. From best configs
    for domain in ["nba", "political"]:
        cfg = _load_json(ROOT / "data" / "karpathy" / f"{domain}-best-config.json")
        if cfg:
            lines.extend([
                f"## {domain.upper()} — Best Known Config",
                "",
                f"- Model: **{cfg.get('model_type', '?')}**",
                f"- n_estimators: {cfg.get('n_estimators', '?')}",
                f"- max_depth: {cfg.get('max_depth', '?')}",
                f"- min_samples_leaf: {cfg.get('min_samples_leaf', '?')}",
                f"- max_features_ratio: {cfg.get('max_features_ratio', '?')}",
                f"- n_features: {cfg.get('n_features', '?')}",
                f"- Best Brier: {cfg.get('best_brier', '?')}",
                "",
            ])

    content = "\n".join(lines)
    out_path = WIKI_LEARNINGS / "what-works.md"
    out_path.write_text(content)
    return out_path


def build_what_fails():
    """Build wiki/learnings/what-fails.md — things that don't work."""
    lines = [
        "# What Fails — Avoid These",
        "",
        f"> Auto-generated from experiment data on {_now()}",
        "> Only includes findings backed by measured failure",
        "",
    ]

    # 1. Worst strategies from arena
    lessons = _load_json(ROOT / "data" / "arena" / "lessons-learned.json")
    worst = lessons.get("worst_strategies", [])
    if worst:
        lines.extend(["## Eliminated Strategies", ""])
        for s in worst:
            lines.append(f"- {s}")
        lines.append("")

    # 2. CPCV gate failures
    cpcv = _load_json(ROOT / "data" / "arena" / "cpcv-gated-strategies.json")
    if cpcv.get("n_passed", -1) == 0:
        n_rejected = cpcv.get("n_rejected", 0)
        lines.extend([
            "## CPCV Gate: ALL Strategies Rejected",
            "",
            f"Out of {n_rejected} strategies tested, ZERO pass the CPCV gate.",
            "This means no strategy has stable risk-adjusted returns across fold permutations.",
            "",
            "**Implication**: Model accuracy (Brier) must improve before strategies can be profitable.",
            "Optimizing strategy parameters on a weak model is polishing a turd.",
            "",
        ])

        # List rejected strategies
        rejected = cpcv.get("rejected_top10_by_dsr", {})
        if rejected:
            lines.extend(["### Top Rejected Strategies", ""])
            for name, info in list(rejected.items())[:5]:
                if isinstance(info, dict):
                    lines.append(
                        f"- **{info.get('name', name)}**: DSR {info.get('dsr', '?'):.3f}, "
                        f"p={info.get('dsr_p_value', '?'):.4f}"
                    )
            lines.append("")

    # 3. Karpathy mutations that never work
    for domain in ["nba", "political"]:
        history_file = ROOT / "data" / "karpathy" / f"{domain}-history.json"
        if not history_file.exists():
            continue
        try:
            history = json.loads(history_file.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        if not history:
            continue

        # Find mutation types with 0% improvement rate
        mutation_stats = defaultdict(lambda: {"tried": 0, "improved": 0})
        for entry in history:
            mut = entry.get("mutation", "unknown").lower()
            mut_type = _classify_mutation(mut)
            mutation_stats[mut_type]["tried"] += 1
            if entry.get("improved"):
                mutation_stats[mut_type]["improved"] += 1

        zero_hit = [(k, v) for k, v in mutation_stats.items()
                    if v["improved"] == 0 and v["tried"] >= 3]

        if zero_hit:
            lines.extend([f"## {domain.upper()} — Never-Improving Mutations", ""])
            for mut_type, stats in zero_hit:
                lines.append(f"- **{mut_type}**: tried {stats['tried']} times, "
                             f"ZERO improvements. Skip this.")
            lines.append("")

    # 4. Models that consistently underperform
    for domain in ["nba", "political"]:
        history_file = ROOT / "data" / "karpathy" / f"{domain}-history.json"
        if not history_file.exists():
            continue
        try:
            history = json.loads(history_file.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        model_briers = defaultdict(list)
        for entry in history:
            mt = entry.get("model_type", "unknown")
            b = entry.get("brier", 1.0)
            model_briers[mt].append(b)

        if len(model_briers) > 1:
            best_model = min(model_briers.items(), key=lambda x: min(x[1]))
            worst_models = [(m, bs) for m, bs in model_briers.items()
                           if min(bs) > min(best_model[1]) + 0.01 and len(bs) >= 2]

            if worst_models:
                lines.extend([f"## {domain.upper()} — Underperforming Models", ""])
                for model, briers in worst_models:
                    lines.append(
                        f"- **{model}**: best={min(briers):.5f}, avg={sum(briers)/len(briers):.5f} "
                        f"(vs champion {best_model[0]} best={min(best_model[1]):.5f})"
                    )
                lines.append("")

    # 5. Personality failures
    personality = lessons.get("personality_lessons", {})
    if personality:
        lines.extend(["## Personality Anti-Patterns", ""])
        for name, lesson in personality.items():
            if any(word in lesson.lower() for word in ["dangerous", "death", "ruin", "slow", "mediocre"]):
                lines.append(f"- **{name}**: {lesson}")
        lines.append("")

    content = "\n".join(lines)
    out_path = WIKI_LEARNINGS / "what-fails.md"
    out_path.write_text(content)
    return out_path


def build_current_state():
    """Build wiki/learnings/current-state.md — snapshot of where we are."""
    lines = [
        "# Current State — System Snapshot",
        "",
        f"> Auto-generated on {_now()}",
        "",
    ]

    # 1. Best Brier scores
    nba_cfg = _load_json(ROOT / "data" / "karpathy" / "nba-best-config.json")
    pol_cfg = _load_json(ROOT / "data" / "karpathy" / "political-best-config.json")
    bt = _load_json(ROOT / "data" / "nba-agent" / "full-season-backtest.json")

    lines.extend([
        "## Brier Scores",
        "",
        f"- NBA Karpathy best: {nba_cfg.get('best_brier', 'N/A')}",
        f"- Political Karpathy best: {pol_cfg.get('best_brier', 'N/A')}",
        f"- Backtest live Brier: {bt.get('brier', 'N/A')}",
        f"- TARGET: 0.20000",
        f"- ALL-TIME BEST: 0.21570 (Colab TabICL, 110f, iter 15)",
        "",
    ])

    # 2. Fleet status
    infra = _load_json(ROOT / "data" / "infra-status.json")
    spaces = infra.get("hf_spaces", {})
    nba_briers = []
    for name, info in spaces.items():
        if "nba" in name.lower() and isinstance(info, dict):
            try:
                nba_briers.append((name, float(info.get("brier", 0))))
            except (ValueError, TypeError):
                pass

    if nba_briers:
        nba_briers.sort(key=lambda x: x[1])
        lines.extend([
            "## Fleet Performance (NBA Islands)",
            "",
            f"| Island | Brier |",
            f"|--------|-------|",
        ])
        for name, b in nba_briers:
            lines.append(f"| {name} | {b:.5f} |")
        lines.extend([
            "",
            f"- Fleet champion: {nba_briers[0][0]} ({nba_briers[0][1]:.5f})",
            f"- Fleet average: {sum(b for _, b in nba_briers)/len(nba_briers):.5f}",
            "",
        ])

    # 3. Karpathy loop state
    for domain in ["nba", "political"]:
        history_file = ROOT / "data" / "karpathy" / f"{domain}-history.json"
        if not history_file.exists():
            continue
        try:
            history = json.loads(history_file.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        if not history:
            continue

        streak = 0
        for entry in reversed(history):
            if not entry.get("improved"):
                streak += 1
            else:
                break
        total_improved = sum(1 for e in history if e.get("improved"))

        lines.extend([
            f"## {domain.upper()} Karpathy Loop",
            "",
            f"- Total iterations: {len(history)}",
            f"- Improvements: {total_improved}",
            f"- Improvement rate: {total_improved/len(history)*100:.1f}%",
            f"- No-improve streak: {streak}",
            f"- Local minimum: {'YES' if streak >= 5 else 'NO'}",
            "",
        ])

    # 4. Bankroll
    if bt:
        lines.extend([
            "## Bankroll",
            "",
            f"- Initial: ${bt.get('display_initial_bankroll', 0):,.0f}",
            f"- Current: ${bt.get('display_final_bankroll', 0):,.0f}",
            f"- ROI: {bt.get('roi_pct', 0):.1f}%",
            f"- Bets: {bt.get('total_bets', 0)}",
            f"- Win rate: {bt.get('win_rate', 0):.1f}%",
            "",
        ])

    # 5. Calibration health
    drift = _load_json(ROOT / "data" / "monitoring" / "drift-summary.json")
    if drift:
        recal = drift.get("recalibration_needed", False)
        ece = drift.get("metrics", {}).get("rolling_ece", "?")
        lines.extend([
            "## Calibration Health",
            "",
            f"- Recalibration needed: {'YES' if recal else 'NO'}",
            f"- Rolling ECE: {ece}",
            f"- State: {drift.get('state', '?')}",
            "",
        ])

    # 6. Department health
    dept_dir = ROOT / "data" / "departments"
    if dept_dir.exists():
        councils = []
        for f in dept_dir.glob("council-*-latest.json"):
            try:
                councils.append(json.loads(f.read_text()))
            except (json.JSONDecodeError, OSError):
                pass

        if councils:
            lines.extend(["## Department Health", ""])
            for c in sorted(councils, key=lambda x: x.get("department", "")):
                dept = c.get("department", "?")
                status = c.get("verified_status", c.get("status", "?"))
                stall = c.get("stall_streak", 0)
                marker = " [STALLED]" if stall >= 2 else ""
                lines.append(f"- {dept}: {status}{marker}")
            lines.append("")

    content = "\n".join(lines)
    out_path = WIKI_LEARNINGS / "current-state.md"
    out_path.write_text(content)
    return out_path


def _classify_mutation(mutation_str: str) -> str:
    m = mutation_str.lower()
    if "model:" in m or "model ->" in m:
        return "change_model"
    if "n_estimators" in m:
        return "change_n_estimators"
    if "max_depth" in m:
        return "change_max_depth"
    if "min_samples_leaf" in m:
        return "change_min_samples_leaf"
    if "max_features_ratio" in m:
        return "change_max_features_ratio"
    if "add" in m and "feature" in m:
        return "add_features"
    if "remove" in m and "feature" in m:
        return "remove_features"
    if "swap" in m and "feature" in m:
        return "swap_features"
    return "other"


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Wiki Builder — Learnings Layer")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print(f"[wiki-builder] Starting at {_now()}")

    WIKI_LEARNINGS.mkdir(parents=True, exist_ok=True)

    articles = [
        ("what-works", build_what_works),
        ("what-fails", build_what_fails),
        ("current-state", build_current_state),
    ]

    for name, builder in articles:
        if args.dry_run:
            print(f"  Would build: wiki/learnings/{name}.md")
            continue
        path = builder()
        size = path.stat().st_size if path.exists() else 0
        print(f"  Built: {path.relative_to(ROOT)} ({size:,} bytes)")

    print(f"[wiki-builder] Done")


if __name__ == "__main__":
    main()
