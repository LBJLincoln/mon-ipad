#!/usr/bin/env python3
"""
Agentic Analyzer — Reads data.json (v2) and produces structured analysis.

Designed to be consumed by both humans (GitHub Step Summary) and AI agents.
Outputs:
  - Regression detection (questions that went from pass to fail)
  - Error pattern analysis (grouped by error_type)
  - Flaky question detection (pass_rate < 0.5 across 3+ runs)
  - Pipeline gap analysis (vs target accuracy)
  - Improvement suggestions (data-driven, not speculative)

Usage:
  python analyzer.py                    # Print analysis to stdout
  python analyzer.py --output-summary   # Markdown for GitHub Step Summary
  python analyzer.py --json             # JSON output for AI agent consumption
"""

import json
import os
import sys
from collections import defaultdict

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(REPO_ROOT, "docs", "data.json")


def load_data():
    with open(DATA_FILE) as f:
        return json.load(f)


def analyze_regressions(data):
    """Find questions that regressed between last two iterations."""
    iters = data.get("iterations", [])
    if len(iters) < 2:
        return {"regressions": [], "fixes": [], "has_data": False}

    prev = iters[-2]
    curr = iters[-1]

    prev_map = {q["id"]: q for q in prev.get("questions", [])}
    curr_map = {q["id"]: q for q in curr.get("questions", [])}

    regressions = []
    fixes = []
    common_ids = set(prev_map.keys()) & set(curr_map.keys())

    for qid in common_ids:
        p = prev_map[qid]
        c = curr_map[qid]
        if p.get("correct") and not c.get("correct"):
            regressions.append({
                "id": qid,
                "rag_type": c.get("rag_type", ""),
                "prev_f1": p.get("f1", 0),
                "curr_f1": c.get("f1", 0),
                "error": c.get("error"),
                "error_type": c.get("error_type"),
                "prev_answer": str(p.get("answer", ""))[:100],
                "curr_answer": str(c.get("answer", ""))[:100],
            })
        elif not p.get("correct") and c.get("correct"):
            fixes.append({
                "id": qid,
                "rag_type": c.get("rag_type", ""),
                "prev_f1": p.get("f1", 0),
                "curr_f1": c.get("f1", 0),
            })

    return {
        "regressions": regressions,
        "fixes": fixes,
        "has_data": True,
        "prev_iteration": prev.get("label", prev.get("id", "")),
        "curr_iteration": curr.get("label", curr.get("id", "")),
        "common_questions": len(common_ids),
    }


def analyze_error_patterns(data):
    """Group errors by type across the latest iteration."""
    iters = data.get("iterations", [])
    if not iters:
        return {}

    latest = iters[-1]
    by_type = defaultdict(list)
    for q in latest.get("questions", []):
        if q.get("error"):
            et = q.get("error_type", "UNKNOWN") or "UNKNOWN"
            by_type[et].append({
                "id": q["id"],
                "rag_type": q.get("rag_type", ""),
                "error": str(q.get("error", ""))[:100],
            })

    return dict(by_type)


def analyze_flaky_questions(data):
    """Find questions with inconsistent results across iterations."""
    reg = data.get("question_registry", {})
    flaky = []
    for qid, info in reg.items():
        runs = info.get("runs", [])
        if len(runs) >= 2:
            pass_rate = info.get("pass_rate", 1.0)
            if 0.1 < pass_rate < 0.9:
                flaky.append({
                    "id": qid,
                    "rag_type": info.get("rag_type", ""),
                    "question": str(info.get("question", ""))[:80],
                    "pass_rate": pass_rate,
                    "total_runs": len(runs),
                    "pass_count": info.get("pass_count", 0),
                })
    return sorted(flaky, key=lambda x: x["pass_rate"])


def analyze_pipeline_gaps(data):
    """Compare current accuracy vs targets."""
    pipes = data.get("pipelines", {})
    gaps = []

    # Use question_registry as source of truth for accuracy
    reg = data.get("question_registry", {})
    pipe_stats = {}
    for qid, qdata in reg.items():
        rt = qdata.get("rag_type", "")
        runs = qdata.get("runs", [])
        if not runs or not rt:
            continue
        if rt not in pipe_stats:
            pipe_stats[rt] = {"tested": 0, "correct": 0, "errors": 0}
        pipe_stats[rt]["tested"] += 1
        last = runs[-1]
        if last.get("correct"):
            pipe_stats[rt]["correct"] += 1
        if last.get("error"):
            pipe_stats[rt]["errors"] += 1

    for name, pipe in pipes.items():
        target = pipe.get("target_accuracy", 85)
        stats = pipe_stats.get(name, {"tested": 0, "correct": 0, "errors": 0})
        acc = round(stats["correct"] / stats["tested"] * 100, 1) if stats["tested"] > 0 else 0

        # Check if plateaued from trend data
        plateaued = False
        trend = pipe.get("trend", [])
        if len(trend) >= 2:
            recent = [t.get("accuracy_pct", 0) for t in trend[-2:]]
            plateaued = abs(recent[0] - recent[1]) < 1.0

        gap = target - acc
        gaps.append({
            "pipeline": name,
            "current_accuracy": acc,
            "target_accuracy": target,
            "gap_pp": round(gap, 1),
            "on_target": gap <= 0,
            "plateaued": plateaued,
            "latest_errors": stats["errors"],
            "latest_tested": stats["tested"],
            "error_rate": round(stats["errors"] / stats["tested"] * 100, 1) if stats["tested"] > 0 else 0,
        })

    return sorted(gaps, key=lambda x: -x["gap_pp"])


def generate_suggestions(regressions, error_patterns, flaky, gaps):
    """Generate data-driven improvement suggestions."""
    suggestions = []

    # Regression-based
    if regressions.get("regressions"):
        reg_count = len(regressions["regressions"])
        reg_types = defaultdict(int)
        for r in regressions["regressions"]:
            reg_types[r["rag_type"]] += 1
        worst_pipe = max(reg_types, key=reg_types.get)
        suggestions.append({
            "priority": "HIGH",
            "area": worst_pipe,
            "suggestion": f"Investigate {reg_count} regressions (most in {worst_pipe}). Revert recent changes if regression is widespread.",
            "data": f"{reg_count} questions regressed between {regressions.get('prev_iteration', '?')} and {regressions.get('curr_iteration', '?')}",
        })

    # Error-pattern-based
    for err_type, items in error_patterns.items():
        if len(items) >= 3:
            affected_pipes = set(i["rag_type"] for i in items)
            suggestions.append({
                "priority": "HIGH" if len(items) >= 5 else "MEDIUM",
                "area": ", ".join(affected_pipes),
                "suggestion": f"Fix {err_type} errors ({len(items)} occurrences). Concentrated in: {', '.join(affected_pipes)}",
                "data": f"{err_type}: {len(items)} errors",
            })

    # Gap-based
    for gap in gaps:
        if gap["gap_pp"] > 10 and not gap["on_target"]:
            suggestions.append({
                "priority": "HIGH" if gap["gap_pp"] > 20 else "MEDIUM",
                "area": gap["pipeline"],
                "suggestion": f"{gap['pipeline']} is {gap['gap_pp']}pp below target ({gap['current_accuracy']}% vs {gap['target_accuracy']}%). "
                              f"{'Accuracy plateaued — try different approach.' if gap['plateaued'] else 'Continue current improvement path.'}",
                "data": f"Gap: {gap['gap_pp']}pp, Error rate: {gap['error_rate']}%",
            })

    # Flaky-based
    if len(flaky) >= 3:
        suggestions.append({
            "priority": "MEDIUM",
            "area": "stability",
            "suggestion": f"{len(flaky)} flaky questions detected (pass rate 20-80% across 3+ runs). Investigate non-determinism in pipelines.",
            "data": f"Flaky IDs: {', '.join(f['id'] for f in flaky[:5])}",
        })

    return sorted(suggestions, key=lambda x: {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(x["priority"], 3))


def output_markdown(data, regressions, error_patterns, flaky, gaps, suggestions):
    """Generate Markdown report for GitHub Step Summary."""
    lines = []
    lines.append("## Agentic Evaluation Analysis")
    lines.append("")

    # Meta
    meta = data.get("meta", {})
    lines.append(f"**Phase:** {meta.get('phase', 'N/A')}")
    lines.append(f"**Iterations:** {meta.get('total_iterations', 0)}")
    lines.append(f"**Questions:** {meta.get('total_unique_questions', 0)} unique, {meta.get('total_test_runs', 0)} total runs")
    lines.append("")

    # Pipeline status
    lines.append("### Pipeline Status")
    lines.append("")
    lines.append("| Pipeline | Accuracy | Target | Gap | Error Rate | Status |")
    lines.append("|----------|----------|--------|-----|------------|--------|")
    for g in gaps:
        status = "ON TARGET" if g["on_target"] else ("PLATEAUED" if g["plateaued"] else "IMPROVING")
        lines.append(f"| {g['pipeline']} | {g['current_accuracy']}% | {g['target_accuracy']}% | {g['gap_pp']}pp | {g['error_rate']}% | {status} |")
    lines.append("")

    # Regressions
    if regressions.get("regressions"):
        lines.append(f"### Regressions ({len(regressions['regressions'])})")
        lines.append("")
        lines.append("| ID | Pipeline | Prev F1 | Curr F1 | Error |")
        lines.append("|----|----------|---------|---------|-------|")
        for r in regressions["regressions"]:
            lines.append(f"| {r['id']} | {r['rag_type']} | {r['prev_f1']:.3f} | {r['curr_f1']:.3f} | {r.get('error_type', '-')} |")
        lines.append("")

    if regressions.get("fixes"):
        lines.append(f"### Fixes ({len(regressions['fixes'])})")
        lines.append("")
        lines.append("| ID | Pipeline | Prev F1 | Curr F1 |")
        lines.append("|----|----------|---------|---------|")
        for f in regressions["fixes"]:
            lines.append(f"| {f['id']} | {f['rag_type']} | {f['prev_f1']:.3f} | {f['curr_f1']:.3f} |")
        lines.append("")

    # Error patterns
    if error_patterns:
        lines.append("### Error Patterns")
        lines.append("")
        for err_type, items in sorted(error_patterns.items(), key=lambda x: -len(x[1])):
            lines.append(f"- **{err_type}**: {len(items)} errors — {', '.join(set(i['rag_type'] for i in items))}")
        lines.append("")

    # Flaky questions
    if flaky:
        lines.append(f"### Flaky Questions ({len(flaky)})")
        lines.append("")
        for f in flaky[:10]:
            lines.append(f"- `{f['id']}` ({f['rag_type']}): {f['pass_count']}/{f['total_runs']} pass rate ({f['pass_rate']:.0%})")
        lines.append("")

    # Suggestions
    if suggestions:
        lines.append("### Improvement Suggestions")
        lines.append("")
        for s in suggestions:
            lines.append(f"- [{s['priority']}] **{s['area']}**: {s['suggestion']}")
            lines.append(f"  - Data: {s['data']}")
        lines.append("")

    return "\n".join(lines)


def output_json(regressions, error_patterns, flaky, gaps, suggestions):
    """Generate JSON output for AI agent consumption."""
    return json.dumps({
        "regressions": regressions,
        "error_patterns": {k: len(v) for k, v in error_patterns.items()},
        "flaky_questions": flaky,
        "pipeline_gaps": gaps,
        "suggestions": suggestions,
        "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z",
    }, indent=2)


def main():
    data = load_data()
    regressions = analyze_regressions(data)
    error_patterns = analyze_error_patterns(data)
    flaky = analyze_flaky_questions(data)
    gaps = analyze_pipeline_gaps(data)
    suggestions = generate_suggestions(regressions, error_patterns, flaky, gaps)

    if "--json" in sys.argv:
        print(output_json(regressions, error_patterns, flaky, gaps, suggestions))
    else:
        md = output_markdown(data, regressions, error_patterns, flaky, gaps, suggestions)
        print(md)

    # Set GitHub Actions output for regression detection
    if regressions.get("regressions"):
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write("has_regressions=true\n")
        with open("/tmp/regression_report.md", "w") as f:
            f.write(f"# Regression Report\n\n")
            f.write(f"**{len(regressions['regressions'])} questions regressed** between ")
            f.write(f"{regressions.get('prev_iteration', '?')} and {regressions.get('curr_iteration', '?')}\n\n")
            for r in regressions["regressions"]:
                f.write(f"- `{r['id']}` ({r['rag_type']}): F1 {r['prev_f1']:.3f} -> {r['curr_f1']:.3f}")
                if r.get("error_type"):
                    f.write(f" [{r['error_type']}]")
                f.write("\n")
        iters = data.get("iterations", [])
        with open("/tmp/iter_num", "w") as f:
            f.write(str(iters[-1].get("number", "?") if iters else "?"))


if __name__ == "__main__":
    main()
