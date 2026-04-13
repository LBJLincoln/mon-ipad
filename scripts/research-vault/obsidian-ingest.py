#!/usr/bin/env python3
"""
Obsidian Karpathy Brain — Deep Ingest
======================================
Ingests structured experiment data into research-vault/raw/ for compilation.

Unlike the basic ingest.py (which copies .md files), this script:
  1. Parses JSON experiment results and extracts learnings
  2. Converts Karpathy iteration history into per-mutation analysis
  3. Ingests arena backtest results with strategy performance
  4. Tracks what-worked vs what-didn't across all data sources
  5. Builds raw/karpathy/ articles that were previously empty

Sources:
  - data/karpathy/*.json              → mutation history, patterns
  - data/scientific-results/*.json    → political experiment metrics
  - data/arena/cpcv-gated-strategies  → strategy performance
  - data/arena/lessons-learned.json   → trader lessons
  - data/arena/agent-states-v5.json   → live agent performance
  - data/monitoring/drift-*.json      → calibration health
  - data/nba-agent/full-season-backtest.json → bankroll/ROI
  - data/infra-status.json            → fleet health (island Brier scores)
  - data/departments/council-*        → department outputs

Usage:
  python3 scripts/research-vault/obsidian-ingest.py           # Full deep ingest
  python3 scripts/research-vault/obsidian-ingest.py --stats   # Show what would be ingested
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

ROOT = Path("/home/termius/mon-ipad")
RAW_DIR = ROOT / "research-vault" / "raw"


def ensure_dirs():
    for subdir in ["karpathy", "experiments", "scientific", "arena-docs",
                   "councils", "political", "learnings"]:
        (RAW_DIR / subdir).mkdir(parents=True, exist_ok=True)


# ── 1. Karpathy iteration history → mutation pattern analysis ──

def ingest_karpathy_deep():
    """Parse nba-history.json and political-history.json into per-mutation articles."""
    count = 0
    karp_dir = ROOT / "data" / "karpathy"
    if not karp_dir.exists():
        return count

    for domain in ["nba", "political"]:
        history_file = karp_dir / f"{domain}-history.json"
        config_file = karp_dir / f"{domain}-best-config.json"

        if not history_file.exists():
            continue

        try:
            history = json.loads(history_file.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        if not isinstance(history, list) or not history:
            continue

        # Load best config
        best_config = {}
        if config_file.exists():
            try:
                best_config = json.loads(config_file.read_text())
            except (json.JSONDecodeError, OSError):
                pass

        # ── Article 1: Mutation effectiveness analysis ──
        mutation_stats = defaultdict(lambda: {"tried": 0, "improved": 0, "brier_deltas": []})
        for entry in history:
            mut = entry.get("mutation", "unknown")
            # Normalize mutation type
            mut_type = _classify_mutation(mut)
            mutation_stats[mut_type]["tried"] += 1
            if entry.get("improved"):
                mutation_stats[mut_type]["improved"] += 1
            brier = entry.get("brier", 0)
            best = entry.get("best_brier", 0)
            if brier and best:
                mutation_stats[mut_type]["brier_deltas"].append(brier - best)

        lines = [
            f"# Karpathy {domain.upper()} — Mutation Effectiveness Analysis",
            f"",
            f"> Auto-generated from {len(history)} iterations on {_now()}",
            f"> Best Brier: {best_config.get('best_brier', 'N/A')}",
            f"> Current model: {best_config.get('model_type', 'N/A')}",
            f"> Current features: {best_config.get('n_features', 'N/A')}",
            f"",
            f"## Mutation Type Effectiveness",
            f"",
            f"| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |",
            f"|---------------|-------|----------|----------|-----------------|",
        ]

        for mut_type, stats in sorted(mutation_stats.items(),
                                        key=lambda x: x[1]["improved"], reverse=True):
            tried = stats["tried"]
            improved = stats["improved"]
            hit_rate = improved / tried * 100 if tried > 0 else 0
            deltas = stats["brier_deltas"]
            avg_delta = sum(deltas) / len(deltas) if deltas else 0
            lines.append(
                f"| {mut_type} | {tried} | {improved} | {hit_rate:.0f}% | {avg_delta:+.5f} |"
            )

        # ── Article 2: Stagnation analysis ──
        streak = 0
        for entry in reversed(history):
            if not entry.get("improved"):
                streak += 1
            else:
                break
        total_improved = sum(1 for e in history if e.get("improved"))

        lines.extend([
            f"",
            f"## Stagnation Analysis",
            f"",
            f"- Total iterations: {len(history)}",
            f"- Total improvements: {total_improved}",
            f"- Improvement rate: {total_improved/len(history)*100:.1f}%",
            f"- Current no-improve streak: {streak}",
            f"- Stuck in local minimum: {'YES' if streak >= 5 else 'NO'}",
            f"",
        ])

        # ── Article 3: Model comparison ──
        model_results = defaultdict(list)
        for entry in history:
            mt = entry.get("model_type", "unknown")
            model_results[mt].append(entry.get("brier", 1.0))

        lines.extend([
            f"## Model Type Comparison",
            f"",
            f"| Model | Tries | Best Brier | Avg Brier | Worst Brier |",
            f"|-------|-------|------------|-----------|-------------|",
        ])
        for model, briers in sorted(model_results.items()):
            lines.append(
                f"| {model} | {len(briers)} | {min(briers):.5f} | "
                f"{sum(briers)/len(briers):.5f} | {max(briers):.5f} |"
            )

        # ── Article 4: Feature count analysis ──
        feat_results = defaultdict(list)
        for entry in history:
            nf = entry.get("n_features", 0)
            bucket = f"{(nf // 10) * 10}-{(nf // 10) * 10 + 9}"
            feat_results[bucket].append(entry.get("brier", 1.0))

        lines.extend([
            f"",
            f"## Feature Count vs Brier",
            f"",
            f"| Feature Range | Tries | Best Brier | Avg Brier |",
            f"|---------------|-------|------------|-----------|",
        ])
        for bucket, briers in sorted(feat_results.items()):
            lines.append(
                f"| {bucket} | {len(briers)} | {min(briers):.5f} | "
                f"{sum(briers)/len(briers):.5f} |"
            )

        # ── Article 5: What to try next (recommendations) ──
        lines.extend([
            f"",
            f"## Data-Driven Recommendations",
            f"",
        ])

        # Find best-performing mutation type
        best_mut = max(mutation_stats.items(),
                       key=lambda x: x[1]["improved"] / max(x[1]["tried"], 1),
                       default=("none", {"tried": 0, "improved": 0}))
        worst_mut = min(mutation_stats.items(),
                        key=lambda x: x[1]["improved"] / max(x[1]["tried"], 1),
                        default=("none", {"tried": 0, "improved": 0}))

        if best_mut[1]["tried"] > 0:
            lines.append(
                f"- BEST mutation type: **{best_mut[0]}** "
                f"({best_mut[1]['improved']}/{best_mut[1]['tried']} hit rate)"
            )
        if worst_mut[1]["tried"] > 0:
            lines.append(
                f"- WORST mutation type: **{worst_mut[0]}** "
                f"({worst_mut[1]['improved']}/{worst_mut[1]['tried']} hit rate) — avoid"
            )

        if streak >= 5:
            lines.append(f"- STUCK: {streak} iterations without improvement")
            lines.append(f"- ACTION: Try a diversity move (change_model or large swap_features)")
        elif streak >= 3:
            lines.append(f"- SLOWING: {streak} iterations without improvement")
            lines.append(f"- ACTION: Switch from hyperparameter to feature mutations or vice versa")

        # Check if one model dominates
        if model_results:
            best_model = min(model_results.items(),
                            key=lambda x: min(x[1]))
            lines.append(f"- Best model type: **{best_model[0]}** (best Brier {min(best_model[1]):.5f})")

        content = "\n".join(lines)
        out_path = RAW_DIR / "karpathy" / f"{domain}-mutation-analysis.md"
        out_path.write_text(content)
        count += 1

    # ── Iteration log analysis ──
    log_file = karp_dir / "iteration-log.jsonl"
    if log_file.exists():
        try:
            entries = []
            for line in log_file.read_text().strip().split("\n"):
                if line.strip():
                    entries.append(json.loads(line))
        except (json.JSONDecodeError, OSError):
            entries = []

        if entries:
            lines = [
                f"# Karpathy Iteration Log Summary",
                f"",
                f"> {len(entries)} sessions logged as of {_now()}",
                f"",
                f"## Session Outcomes",
                f"",
                f"| Timestamp | Domain | Mutation | Decision | Brier After |",
                f"|-----------|--------|----------|----------|-------------|",
            ]
            for e in entries[-20:]:  # Last 20 sessions
                ts = e.get("timestamp", "?")[:19]
                dom = e.get("domain", "?")
                mut = e.get("mutation", "?")[:30]
                dec = e.get("decision", "?")
                metric = e.get("metric_after", e.get("metric_before", "?"))
                if isinstance(metric, float):
                    metric = f"{metric:.5f}"
                lines.append(f"| {ts} | {dom} | {mut} | {dec} | {metric} |")

            # Aggregate stats
            kept = sum(1 for e in entries if e.get("decision") == "KEEP")
            reverted = sum(1 for e in entries if e.get("decision") == "REVERT")
            lines.extend([
                f"",
                f"## Aggregate",
                f"- Sessions: {len(entries)}",
                f"- KEEP: {kept} ({kept/len(entries)*100:.0f}%)",
                f"- REVERT: {reverted} ({reverted/len(entries)*100:.0f}%)",
            ])

            content = "\n".join(lines)
            out_path = RAW_DIR / "karpathy" / "iteration-log-summary.md"
            out_path.write_text(content)
            count += 1

    return count


def _classify_mutation(mutation_str: str) -> str:
    """Classify a mutation description string into a type."""
    m = mutation_str.lower()
    if "model:" in m or "model ->" in m or "change_model" in m:
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


# ── 2. Scientific experiment results ──

def ingest_scientific_deep():
    """Parse JSON experiment results into structured learning articles."""
    count = 0
    sci_dir = ROOT / "data" / "scientific-results"
    if not sci_dir.exists():
        return count

    for json_file in sorted(sci_dir.glob("*.json")):
        try:
            data = json.loads(json_file.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        lines = [f"# Experiment: {json_file.stem}", ""]

        # Extract key metrics
        if isinstance(data, dict):
            meta = data.get("meta", data.get("metadata", data))
            if isinstance(meta, dict):
                for k in ["timestamp", "model_brier", "total_trades", "roi_pct",
                           "sharpe", "win_rate", "categories_tested"]:
                    if k in meta:
                        lines.append(f"- {k}: {meta[k]}")

            # Extract trader results
            traders = data.get("traders", data.get("results", {}))
            if isinstance(traders, dict) and traders:
                lines.extend(["", "## Trader Performance", ""])
                for name, info in list(traders.items())[:10]:
                    if isinstance(info, dict):
                        roi = info.get("roi_pct", info.get("roi", "?"))
                        sharpe = info.get("sharpe", "?")
                        bets = info.get("total_bets", info.get("bets", "?"))
                        lines.append(f"- **{name}**: ROI {roi}%, Sharpe {sharpe}, Bets {bets}")

            # Extract category performance
            cats = data.get("categories", data.get("category_performance", {}))
            if isinstance(cats, dict) and cats:
                lines.extend(["", "## Category Performance", ""])
                for cat, info in list(cats.items())[:15]:
                    if isinstance(info, dict):
                        wr = info.get("win_rate", "?")
                        vol = info.get("volume", info.get("bets", "?"))
                        lines.append(f"- {cat}: WR {wr}, Volume {vol}")

        content = "\n".join(lines)
        if len(content) > 100:
            out_path = RAW_DIR / "scientific" / f"{json_file.stem}-analysis.md"
            out_path.write_text(content)
            count += 1

    return count


# ── 3. Arena strategy analysis ──

def ingest_arena_deep():
    """Extract strategy learnings from arena data."""
    count = 0

    # CPCV gated strategies
    cpcv_file = ROOT / "data" / "arena" / "cpcv-gated-strategies.json"
    if cpcv_file.exists():
        try:
            data = json.loads(cpcv_file.read_text())
        except (json.JSONDecodeError, OSError):
            data = {}

        if isinstance(data, dict):
            n_passed = data.get("n_passed", 0)
            n_rejected = data.get("n_rejected", 0)
            gate = data.get("gate", {})
            passed = data.get("passed", {})
            rejected = data.get("rejected_top10_by_dsr", {})

            lines = [
                f"# CPCV Strategy Gate — Analysis",
                f"",
                f"> Generated {_now()}",
                f"",
                f"## Gate Configuration",
                f"- Min bets: {gate.get('min_bets', '?')}",
                f"- DSR p-value max: {gate.get('dsr_p_value_max', '?')}",
                f"- PBO max: {gate.get('pbo_max', '?')}",
                f"",
                f"## Results",
                f"- Passed: {n_passed}",
                f"- Rejected: {n_rejected}",
                f"- Pass rate: {n_passed/(n_passed+n_rejected)*100:.0f}%" if (n_passed+n_rejected) > 0 else "- Pass rate: N/A",
                f"",
            ]

            if passed:
                lines.extend(["## Passed Strategies", ""])
                for name, info in passed.items():
                    if isinstance(info, dict):
                        lines.append(
                            f"- **{info.get('name', name)}**: DSR {info.get('dsr', '?')}, "
                            f"ROI {info.get('roi_mean_pct', '?')}%, "
                            f"Sharpe {info.get('sr_mean', '?')}"
                        )

            if rejected:
                lines.extend(["", "## Top Rejected (potential with tuning)", ""])
                for name, info in list(rejected.items())[:5]:
                    if isinstance(info, dict):
                        lines.append(
                            f"- **{info.get('name', name)}**: DSR {info.get('dsr', '?')}, "
                            f"p={info.get('dsr_p_value', '?')}, "
                            f"ROI {info.get('roi_mean_pct', '?')}%"
                        )

            lines.extend([
                "",
                "## Key Learning",
                "",
                f"{'ZERO strategies pass CPCV gate' if n_passed == 0 else f'{n_passed} strategies pass'}.",
            ])

            if n_passed == 0:
                lines.extend([
                    "This indicates:",
                    "- Current model predictions lack sufficient edge for profitable betting",
                    "- Strategy optimization alone cannot overcome model weakness",
                    "- Priority: improve Brier score (model accuracy) before tuning strategies",
                    "- DSR negative = Sharpe ratios not stable across folds = overfitting to history",
                ])

            content = "\n".join(lines)
            out_path = RAW_DIR / "learnings" / "cpcv-gate-analysis.md"
            out_path.write_text(content)
            count += 1

    # Lessons learned
    lessons_file = ROOT / "data" / "arena" / "lessons-learned.json"
    if lessons_file.exists():
        try:
            data = json.loads(lessons_file.read_text())
        except (json.JSONDecodeError, OSError):
            data = {}

        if isinstance(data, dict):
            lines = [
                f"# Arena Lessons Learned",
                f"",
                f"> From {data.get('from_iterations', '?')} iterations, "
                f"{data.get('from_generations', '?')} generations",
                f"",
            ]

            insights = data.get("key_insights", [])
            if insights:
                lines.extend(["## Key Insights", ""])
                for i, insight in enumerate(insights, 1):
                    lines.append(f"{i}. {insight}")

            optimal = data.get("optimal_params", {})
            if optimal:
                lines.extend(["", "## Optimal Parameters", ""])
                for k, v in optimal.items():
                    lines.append(f"- **{k}**: {v}")

            personality = data.get("personality_lessons", {})
            if personality:
                lines.extend(["", "## Personality Lessons", ""])
                for name, lesson in personality.items():
                    lines.append(f"- **{name}**: {lesson}")

            model_rank = data.get("model_rankings", {})
            if model_rank:
                insight = model_rank.get("insight", "")
                if insight:
                    lines.extend(["", "## Model Ranking Insight", "", insight])

            content = "\n".join(lines)
            out_path = RAW_DIR / "learnings" / "arena-lessons-learned.md"
            out_path.write_text(content)
            count += 1

    return count


# ── 4. Fleet health snapshot ──

def ingest_fleet_health():
    """Convert infra-status.json into a fleet performance article."""
    count = 0
    infra_file = ROOT / "data" / "infra-status.json"
    if not infra_file.exists():
        return count

    try:
        data = json.loads(infra_file.read_text())
    except (json.JSONDecodeError, OSError):
        return count

    spaces = data.get("hf_spaces", {})
    if not spaces:
        return count

    nba_islands = {}
    pol_islands = {}
    for name, info in spaces.items():
        if isinstance(info, dict):
            brier = info.get("brier", "?")
            gen = info.get("gen", "?")
            status = info.get("status", "?")
            if "nba" in name.lower():
                nba_islands[name] = {"brier": brier, "gen": gen, "status": status}
            elif "pol" in name.lower():
                pol_islands[name] = {"brier": brier, "gen": gen, "status": status}

    lines = [
        f"# Fleet Health Snapshot",
        f"",
        f"> Captured at {data.get('timestamp', _now())}",
        f"",
    ]

    if nba_islands:
        lines.extend(["## NBA Islands", "", "| Island | Brier | Gen | Status |",
                       "|--------|-------|-----|--------|"])
        briers = []
        for name, info in sorted(nba_islands.items()):
            b = info['brier']
            lines.append(f"| {name} | {b} | {info['gen']} | {info['status']} |")
            try:
                briers.append(float(b))
            except (ValueError, TypeError):
                pass

        if briers:
            lines.extend([
                f"",
                f"- Fleet best: {min(briers):.5f}",
                f"- Fleet avg: {sum(briers)/len(briers):.5f}",
                f"- Fleet worst: {max(briers):.5f}",
                f"- Fleet spread: {max(briers)-min(briers):.5f}",
            ])

    if pol_islands:
        lines.extend(["", "## Political Islands", "", "| Island | Brier | Gen | Status |",
                       "|--------|-------|-----|--------|"])
        for name, info in sorted(pol_islands.items()):
            lines.append(f"| {name} | {info['brier']} | {info['gen']} | {info['status']} |")

    content = "\n".join(lines)
    out_path = RAW_DIR / "learnings" / "fleet-health-snapshot.md"
    out_path.write_text(content)
    count += 1
    return count


# ── 5. Drift / calibration health ──

def ingest_drift_monitoring():
    """Convert drift monitoring data into a calibration health article."""
    count = 0
    mon_dir = ROOT / "data" / "monitoring"
    if not mon_dir.exists():
        return count

    lines = [f"# Calibration & Drift Monitoring", f"", f"> Snapshot at {_now()}", ""]

    for fname in ["drift-summary.json", "drift-calibration.json", "drift-data.json", "drift-concept.json"]:
        fpath = mon_dir / fname
        if not fpath.exists():
            continue
        try:
            data = json.loads(fpath.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        lines.append(f"## {fname.replace('.json', '').replace('-', ' ').title()}")
        lines.append("")

        if isinstance(data, dict):
            for k, v in data.items():
                if k == "generated_at":
                    continue
                if isinstance(v, dict):
                    lines.append(f"### {k}")
                    for kk, vv in v.items():
                        lines.append(f"- {kk}: {vv}")
                else:
                    lines.append(f"- **{k}**: {v}")
        lines.append("")

    content = "\n".join(lines)
    if len(content) > 150:
        out_path = RAW_DIR / "learnings" / "calibration-drift-status.md"
        out_path.write_text(content)
        count += 1

    return count


# ── 6. Backtest bankroll performance ──

def ingest_backtest_performance():
    """Extract key performance metrics from full-season-backtest.json."""
    count = 0
    bt_file = ROOT / "data" / "nba-agent" / "full-season-backtest.json"
    if not bt_file.exists():
        return count

    try:
        data = json.loads(bt_file.read_text())
    except (json.JSONDecodeError, OSError):
        return count

    lines = [
        f"# Season Backtest Performance",
        f"",
        f"> Generated {data.get('generated_at', _now())}",
        f"",
        f"## Key Metrics",
        f"",
        f"- Initial bankroll: ${data.get('display_initial_bankroll', 0):,.0f}",
        f"- Final bankroll: ${data.get('display_final_bankroll', 0):,.0f}",
        f"- ROI: {data.get('roi_pct', 0):.1f}%",
        f"- Total bets: {data.get('total_bets', 0)}",
        f"- Win rate: {data.get('win_rate', 0):.1f}%",
        f"- Sharpe: {data.get('sharpe', 0)}",
        f"- Max drawdown: {data.get('max_dd', 0):.2%}",
        f"- Brier: {data.get('brier', 0):.5f}",
        f"- Strategy: {data.get('strategy', 'unknown')}",
        f"",
        f"## Data Quality",
        f"",
        f"- Synthesized trades: {data.get('synthesized_trades', 'unknown')}",
        f"- Real games sourced: {data.get('real_games_sourced', 'unknown')}",
        f"- Real games available: {data.get('real_games_available', 0)}",
        f"",
    ]

    # Analyze trade patterns if available
    trades = data.get("trades", [])
    if trades and isinstance(trades, list):
        winning_teams = defaultdict(int)
        losing_teams = defaultdict(int)
        for t in trades:
            if not isinstance(t, dict):
                continue
            team = t.get("bet_team", "?")
            if t.get("won"):
                winning_teams[team] += 1
            else:
                losing_teams[team] += 1

        lines.extend([
            f"## Trade Analysis ({len(trades)} trades)",
            f"",
        ])

        if winning_teams:
            top_winners = sorted(winning_teams.items(), key=lambda x: x[1], reverse=True)[:5]
            lines.append("Top winning teams: " + ", ".join(
                f"{t} ({n}W)" for t, n in top_winners
            ))

        if losing_teams:
            top_losers = sorted(losing_teams.items(), key=lambda x: x[1], reverse=True)[:5]
            lines.append("Top losing teams: " + ", ".join(
                f"{t} ({n}L)" for t, n in top_losers
            ))

    content = "\n".join(lines)
    out_path = RAW_DIR / "learnings" / "season-backtest-performance.md"
    out_path.write_text(content)
    count += 1
    return count


# ── 7. Department council outputs ──

def ingest_councils_deep():
    """Extract structured learnings from council JSON outputs."""
    count = 0
    dept_dir = ROOT / "data" / "departments"
    if not dept_dir.exists():
        return count

    all_councils = []
    for json_file in sorted(dept_dir.glob("council-*-latest.json")):
        try:
            data = json.loads(json_file.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        all_councils.append(data)

    if not all_councils:
        return count

    lines = [
        f"# Department Council Summary",
        f"",
        f"> {len(all_councils)} departments reporting as of {_now()}",
        f"",
        f"| Department | Status | Stall Streak | Brier Delta | Duration |",
        f"|------------|--------|-------------|-------------|----------|",
    ]

    for c in all_councils:
        dept = c.get("department", "?")
        status = c.get("verified_status", c.get("status", "?"))
        stall = c.get("stall_streak", 0)
        bd = c.get("brier_delta", 0)
        dur = c.get("duration_seconds", 0)
        lines.append(f"| {dept} | {status} | {stall} | {bd:+.6f} | {dur}s |")

    # Analysis
    stalled = [c for c in all_councils if c.get("stall_streak", 0) >= 2]
    successful = [c for c in all_councils
                  if c.get("verified_status") == "success"
                  and c.get("brier_delta", 0) < 0]

    lines.extend([
        f"",
        f"## Analysis",
        f"",
        f"- Active departments: {len(all_councils)}",
        f"- Stalled (2+ streak): {len(stalled)}",
        f"- Producing improvements: {len(successful)}",
    ])

    if stalled:
        lines.append(f"- Stalled depts: {', '.join(c.get('department', '?') for c in stalled)}")

    content = "\n".join(lines)
    out_path = RAW_DIR / "councils" / "department-summary.md"
    out_path.write_text(content)
    count += 1
    return count


# ── Helpers ──

def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def show_stats():
    """Show what would be ingested."""
    print("=== Deep Ingest Sources ===\n")

    checks = [
        ("Karpathy NBA history", ROOT / "data" / "karpathy" / "nba-history.json"),
        ("Karpathy Political history", ROOT / "data" / "karpathy" / "political-history.json"),
        ("Karpathy iteration log", ROOT / "data" / "karpathy" / "iteration-log.jsonl"),
        ("Scientific results", ROOT / "data" / "scientific-results"),
        ("CPCV strategies", ROOT / "data" / "arena" / "cpcv-gated-strategies.json"),
        ("Lessons learned", ROOT / "data" / "arena" / "lessons-learned.json"),
        ("Agent states v5", ROOT / "data" / "arena" / "agent-states-v5.json"),
        ("Fleet status", ROOT / "data" / "infra-status.json"),
        ("Drift monitoring", ROOT / "data" / "monitoring"),
        ("Season backtest", ROOT / "data" / "nba-agent" / "full-season-backtest.json"),
        ("Dept councils", ROOT / "data" / "departments"),
    ]

    for name, path in checks:
        exists = path.exists()
        if exists and path.is_file():
            size = path.stat().st_size
            print(f"  {'OK' if exists else 'MISSING':7s} {name:30s} ({size:,} bytes)")
        elif exists and path.is_dir():
            files = list(path.glob("*.json")) + list(path.glob("*.jsonl"))
            print(f"  {'OK' if exists else 'MISSING':7s} {name:30s} ({len(files)} JSON files)")
        else:
            print(f"  {'MISSING':7s} {name}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Obsidian Deep Ingest")
    parser.add_argument("--stats", action="store_true")
    args = parser.parse_args()

    if args.stats:
        show_stats()
        return

    print(f"[deep-ingest] Starting at {_now()}")

    ensure_dirs()

    sources = [
        ("karpathy-deep", ingest_karpathy_deep),
        ("scientific-deep", ingest_scientific_deep),
        ("arena-deep", ingest_arena_deep),
        ("fleet-health", ingest_fleet_health),
        ("drift-monitoring", ingest_drift_monitoring),
        ("backtest-perf", ingest_backtest_performance),
        ("councils-deep", ingest_councils_deep),
    ]

    total = 0
    for name, func in sources:
        count = func()
        total += count
        print(f"  {name:25s}: {count} articles")

    print(f"[deep-ingest] Total: {total} articles generated")
    return total


if __name__ == "__main__":
    main()
