#!/usr/bin/env python3
"""
Migrate data.json from flat question list to iteration-aware v2 format.

v2 adds:
- iterations[]: grouped test runs with metadata + per-question results
- question_registry{}: unique questions with cross-iteration history
- quick_tests[]: endpoint smoke test results
- Preserves: databases, workflow_changes, db_snapshots, pipelines
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from copy import deepcopy

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_FILE = os.path.join(REPO_ROOT, "docs", "data.json")
BACKUP_FILE = os.path.join(REPO_ROOT, "docs", "data-v1-backup.json")

# Question files for full text lookup
QUESTIONS_FILES = [
    os.path.join(REPO_ROOT, "datasets", "phase-1", "standard-orch-50x2.json"),
    os.path.join(REPO_ROOT, "datasets", "phase-1", "graph-quant-50x2.json"),
]


def load_full_questions():
    """Load full question text and metadata from source files."""
    registry = {}
    for path in QUESTIONS_FILES:
        if not os.path.exists(path):
            continue
        with open(path) as f:
            raw = json.load(f)
        qs = raw.get("questions", raw) if isinstance(raw, dict) else raw
        for q in qs:
            if not isinstance(q, dict):
                continue
            qid = q.get("id", "")
            registry[qid] = {
                "id": qid,
                "question": q.get("question", ""),
                "expected": q.get("expected_answer", q.get("expected", "")),
                "expected_detail": q.get("expected_detail", ""),
                "rag_type": q.get("rag_target", ""),
                "category": q.get("category", ""),
                "entities": q.get("entities", []),
                "tables": q.get("tables", []),
            }
    return registry


def parse_ts(ts):
    return datetime.fromisoformat(ts.replace("Z", ""))


def group_into_iterations(questions):
    """Group questions into iterations based on time gaps > 20 minutes."""
    if not questions:
        return []
    sorted_qs = sorted(questions, key=lambda q: q["timestamp"])
    iterations = []
    current_batch = []

    for q in sorted_qs:
        if current_batch:
            gap = (parse_ts(q["timestamp"]) - parse_ts(current_batch[-1]["timestamp"])).total_seconds()
            if gap > 1200:  # 20 min gap = new iteration
                iterations.append(current_batch)
                current_batch = []
        current_batch.append(q)

    if current_batch:
        iterations.append(current_batch)

    return iterations


def build_iteration(batch, iter_num, workflow_changes):
    """Build an iteration object from a batch of questions."""
    iter_id = f"iter-{iter_num:03d}"

    # Compute per-pipeline stats
    by_type = defaultdict(lambda: {"tested": 0, "correct": 0, "errors": 0, "latencies": [], "f1_scores": []})
    for q in batch:
        rt = q["rag_type"]
        by_type[rt]["tested"] += 1
        if q.get("correct"):
            by_type[rt]["correct"] += 1
        if q.get("error"):
            by_type[rt]["errors"] += 1
        if q.get("latency_ms", 0) > 0:
            by_type[rt]["latencies"].append(q["latency_ms"])
        if q.get("f1", 0) > 0:
            by_type[rt]["f1_scores"].append(q["f1"])

    results_summary = {}
    for rt, info in by_type.items():
        lats = sorted(info["latencies"])
        results_summary[rt] = {
            "tested": info["tested"],
            "correct": info["correct"],
            "errors": info["errors"],
            "accuracy_pct": round(info["correct"] / info["tested"] * 100, 1) if info["tested"] > 0 else 0,
            "avg_latency_ms": int(sum(lats) / len(lats)) if lats else 0,
            "p95_latency_ms": lats[int(len(lats) * 0.95)] if len(lats) > 1 else (lats[0] if lats else 0),
            "avg_f1": round(sum(info["f1_scores"]) / len(info["f1_scores"]), 4) if info["f1_scores"] else 0,
        }

    # Find relevant workflow changes (within 2 hours before iteration start)
    iter_start = parse_ts(batch[0]["timestamp"])
    relevant_changes = []
    for wc in workflow_changes:
        wc_time = parse_ts(wc["timestamp"])
        if 0 <= (iter_start - wc_time).total_seconds() <= 7200:
            relevant_changes.append(wc["description"])

    # Build question list for this iteration
    iter_questions = []
    for q in batch:
        iter_questions.append({
            "id": q["id"],
            "rag_type": q["rag_type"],
            "correct": bool(q.get("correct", False)),
            "f1": round(q.get("f1", 0), 4),
            "latency_ms": int(q.get("latency_ms", 0)),
            "answer": q.get("answer", "")[:500],
            "expected": q.get("expected", "")[:300],
            "match_type": q.get("match_type", ""),
            "error": q.get("error"),
            "error_type": q.get("error_type"),
            "timestamp": q["timestamp"],
        })

    return {
        "id": iter_id,
        "number": iter_num,
        "timestamp_start": batch[0]["timestamp"],
        "timestamp_end": batch[-1]["timestamp"],
        "label": f"Iteration {iter_num}",
        "description": "",
        "changes_applied": relevant_changes,
        "results_summary": results_summary,
        "total_tested": len(batch),
        "total_correct": sum(1 for q in batch if q.get("correct")),
        "overall_accuracy_pct": round(sum(1 for q in batch if q.get("correct")) / len(batch) * 100, 1) if batch else 0,
        "questions": iter_questions,
    }


def build_question_registry(iterations, full_questions):
    """Build a registry of unique questions with cross-iteration history."""
    registry = {}

    for iteration in iterations:
        for q in iteration["questions"]:
            qid = q["id"]
            if qid not in registry:
                # Get full info from source files
                src = full_questions.get(qid, {})
                registry[qid] = {
                    "id": qid,
                    "question": src.get("question", q.get("question", "")),
                    "expected": src.get("expected", q.get("expected", "")),
                    "expected_detail": src.get("expected_detail", ""),
                    "rag_type": src.get("rag_type", q.get("rag_type", "")),
                    "category": src.get("category", ""),
                    "entities": src.get("entities", []),
                    "tables": src.get("tables", []),
                    "runs": [],
                }

            registry[qid]["runs"].append({
                "iteration_id": iteration["id"],
                "iteration_number": iteration["number"],
                "correct": q["correct"],
                "f1": q["f1"],
                "latency_ms": q["latency_ms"],
                "match_type": q["match_type"],
                "error": q.get("error"),
                "error_type": q.get("error_type"),
                "answer": q.get("answer", ""),
                "timestamp": q["timestamp"],
            })

    # Add computed fields
    for qid, info in registry.items():
        runs = info["runs"]
        if runs:
            info["total_runs"] = len(runs)
            info["pass_count"] = sum(1 for r in runs if r["correct"])
            info["pass_rate"] = round(info["pass_count"] / len(runs), 3)
            info["current_status"] = "pass" if runs[-1]["correct"] else ("error" if runs[-1].get("error") else "fail")
            info["last_tested"] = runs[-1]["timestamp"]
            info["best_f1"] = max(r["f1"] for r in runs)
            info["trend"] = "improving" if len(runs) >= 2 and runs[-1]["correct"] and not runs[0]["correct"] else (
                "regressing" if len(runs) >= 2 and not runs[-1]["correct"] and runs[0]["correct"] else "stable"
            )

    return registry


def migrate():
    """Main migration: v1 flat format → v2 iteration-aware format."""
    print("Loading data.json...")
    with open(DATA_FILE) as f:
        v1 = json.load(f)

    # Backup v1
    print(f"Backing up to {BACKUP_FILE}...")
    with open(BACKUP_FILE, "w") as f:
        json.dump(v1, f, indent=2, ensure_ascii=False)

    # Load full question texts
    print("Loading full question metadata from source files...")
    full_questions = load_full_questions()
    print(f"  Loaded {len(full_questions)} question definitions")

    # Group into iterations
    print("Grouping questions into iterations...")
    batches = group_into_iterations(v1.get("questions", []))
    print(f"  Found {len(batches)} iterations")

    # Add labels/descriptions based on known history
    iteration_labels = {
        1: ("Initial subset test", "First eval run: ~50q subset across all 4 pipelines (10-15 per pipeline)"),
        2: ("Full 200q baseline", "Complete baseline evaluation of all 200 questions. Graph JS syntax fix deployed. topK increased for Standard."),
        3: ("Post-improvement retest", "Re-test after model changes + embedding fallback. Free-model compatibility fixes deployed."),
    }

    # Build iterations
    iterations = []
    for i, batch in enumerate(batches, 1):
        iteration = build_iteration(batch, i, v1.get("workflow_changes", []))
        label, desc = iteration_labels.get(i, (f"Iteration {i}", ""))
        iteration["label"] = label
        iteration["description"] = desc
        iterations.append(iteration)
        tested = iteration["total_tested"]
        correct = iteration["total_correct"]
        acc = iteration["overall_accuracy_pct"]
        print(f"  Iter {i}: {tested}q, {correct} correct ({acc}%)")

    # Build question registry
    print("Building question registry...")
    question_registry = build_question_registry(iterations, full_questions)
    print(f"  {len(question_registry)} unique questions tracked")

    # Count trends
    improving = sum(1 for q in question_registry.values() if q.get("trend") == "improving")
    regressing = sum(1 for q in question_registry.values() if q.get("trend") == "regressing")
    stable = sum(1 for q in question_registry.values() if q.get("trend") == "stable")
    print(f"  Trends: {improving} improving, {regressing} regressing, {stable} stable")

    # Build pipeline trend data
    pipeline_trends = {}
    for rt in ["standard", "graph", "quantitative", "orchestrator"]:
        trend = []
        for iteration in iterations:
            rs = iteration["results_summary"].get(rt)
            if rs:
                trend.append({
                    "iteration_id": iteration["id"],
                    "iteration_number": iteration["number"],
                    "accuracy_pct": rs["accuracy_pct"],
                    "tested": rs["tested"],
                    "errors": rs["errors"],
                    "avg_latency_ms": rs["avg_latency_ms"],
                })
        pipeline_trends[rt] = trend

    # Build v2 data structure
    v2 = {
        "meta": {
            "version": "2.0",
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "status": "idle",
            "project": "Multi-RAG Orchestrator SOTA 2026",
            "phase": "Phase 1 — Baseline (200q)",
            "total_unique_questions": len(question_registry),
            "total_test_runs": sum(len(q["runs"]) for q in question_registry.values()),
            "total_iterations": len(iterations),
            "total_cost_usd": 0,
        },
        "iterations": iterations,
        "question_registry": question_registry,
        "pipelines": {
            "standard": {
                "endpoint": "http://34.136.180.66:5678/webhook/rag-multi-index-v3",
                "target_accuracy": 85.0,
                "trend": pipeline_trends.get("standard", []),
            },
            "graph": {
                "endpoint": "http://34.136.180.66:5678/webhook/ff622742-6d71-4e91-af71-b5c666088717",
                "target_accuracy": 70.0,
                "trend": pipeline_trends.get("graph", []),
            },
            "quantitative": {
                "endpoint": "http://34.136.180.66:5678/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
                "target_accuracy": 85.0,
                "trend": pipeline_trends.get("quantitative", []),
            },
            "orchestrator": {
                "endpoint": "http://34.136.180.66:5678/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0",
                "target_accuracy": 70.0,
                "trend": pipeline_trends.get("orchestrator", []),
            },
        },
        "workflow_changes": v1.get("workflow_changes", []),
        "databases": v1.get("databases", {}),
        "db_snapshots": v1.get("db_snapshots", []),
        "execution_logs": v1.get("execution_logs", []),
        "quick_tests": [],
        "history": v1.get("history", []),
    }

    # Save v2
    print(f"\nSaving v2 data.json ({len(json.dumps(v2))//1024} KB)...")
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(v2, f, indent=2, ensure_ascii=False)
    os.replace(tmp, DATA_FILE)

    print("Migration complete.")
    return v2


if __name__ == "__main__":
    migrate()
