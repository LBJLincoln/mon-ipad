#!/usr/bin/env python3
"""TEST/EVAL Agent — Continuous pipeline testing, accuracy tracking, regression detection.

Wraps existing eval scripts and adds regression guard.
"""

import json
import os
import subprocess
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from base import load_env, telegram_notify, log_event, http_post, run_agent_loop, ctx
from pathlib import Path

CATEGORY = "test_eval"
BASE_DIR = Path("/home/termius/mon-ipad")

# Accuracy thresholds — alert if below
THRESHOLDS = {
    "standard": 0.80,
    "graph": 0.60,
    "quantitative": 0.40,
    "orchestrator": 0.70,
}

# Track last known scores for regression detection
SCORE_FILE = BASE_DIR / "data" / "agents" / "test_eval" / "last_scores.json"


def run_quick_eval(pipeline="standard", questions=5):
    """Run quick eval via pipeline webhook."""
    questions_data = []

    # Load questions from eval datasets
    for sector in ["finance", "btp", "juridique", "industrie"]:
        q_file = BASE_DIR / "sectors" / "eval-datasets" / f"{sector}-questions.json"
        if q_file.exists():
            try:
                with open(q_file) as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        questions_data.extend(data[:2])  # 2 per sector
            except Exception:
                pass

    if not questions_data:
        # Fallback hardcoded questions
        questions_data = [
            {"question": "Quel est le ratio de solvabilite Bale III ?", "sector": "finance"},
            {"question": "Quelle est la norme NF DTU 20.1 ?", "sector": "btp"},
            {"question": "Quelles sont les obligations RGPD ?", "sector": "juridique"},
            {"question": "Qu'est-ce que l'AMDEC ?", "sector": "industrie"},
            {"question": "Comment calculer le PER d'une entreprise ?", "sector": "finance"},
        ]

    # Select pipeline webhook
    webhooks = {
        "standard": "https://lbjlincoln-nomos-rag-engine.hf.space/webhook/rag-multi-index-v3",
        "graph": "https://lbjlincoln-nomos-rag-engine.hf.space/webhook/ff622742-6d71-4e91-af71-b5c666088717",
        "quantitative": "https://lbjlincoln-nomos-rag-engine.hf.space/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
        "orchestrator": "https://lbjlincoln-nomos-rag-engine.hf.space/webhook/orchestrator-v2",
    }

    webhook = webhooks.get(pipeline, webhooks["standard"])
    results = []
    correct = 0

    for q in questions_data[:questions]:
        question = q.get("question", q) if isinstance(q, dict) else q
        sector = q.get("sector", "finance") if isinstance(q, dict) else "finance"

        resp = http_post(webhook, {"question": question, "tenant_id": sector}, timeout=60)

        got_answer = False
        if resp.get("ok") and resp.get("body"):
            answer = resp["body"].get("response") or resp["body"].get("answer") or resp["body"].get("output", "")
            got_answer = bool(answer and len(str(answer)) > 20)

        results.append({
            "question": question[:80],
            "sector": sector,
            "got_answer": got_answer,
            "status": resp.get("status", 0),
        })
        if got_answer:
            correct += 1

    accuracy = correct / max(len(results), 1)
    return {"pipeline": pipeline, "correct": correct, "total": len(results), "accuracy": accuracy, "details": results}


def check_regression(current_scores):
    """Compare current scores with last known scores."""
    last_scores = {}
    if SCORE_FILE.exists():
        try:
            with open(SCORE_FILE) as f:
                last_scores = json.load(f)
        except Exception:
            pass

    regressions = []
    for pipeline, score in current_scores.items():
        last = last_scores.get(pipeline, 0)
        if last > 0 and score < last - 0.10:  # 10% drop = regression
            regressions.append({
                "pipeline": pipeline,
                "was": last,
                "now": score,
                "drop": last - score,
            })

    # Save current scores
    SCORE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SCORE_FILE, "w") as f:
        json.dump(current_scores, f)

    return regressions


def tick():
    """One eval cycle."""
    all_scores = {}
    all_results = {}

    for pipeline in ["standard", "orchestrator"]:  # Quick: just 2 pipelines, 3 questions each
        print(f"  Evaluating {pipeline}...")
        result = run_quick_eval(pipeline, questions=3)
        all_results[pipeline] = result
        all_scores[pipeline] = result["accuracy"]
        print(f"  {pipeline}: {result['accuracy']:.0%} ({result['correct']}/{result['total']})")

    # Check for regressions
    regressions = check_regression(all_scores)

    # Check against thresholds
    alerts = []
    for pipeline, score in all_scores.items():
        threshold = THRESHOLDS.get(pipeline, 0.5)
        if score < threshold:
            alerts.append(f"{pipeline}: {score:.0%} < {threshold:.0%}")

    report = {
        "scores": all_scores,
        "results": all_results,
        "regressions": regressions,
        "threshold_alerts": alerts,
    }

    # Alert on regressions
    if regressions:
        reg_text = "\n".join(f"  {r['pipeline']}: {r['was']:.0%} → {r['now']:.0%} (↓{r['drop']:.0%})" for r in regressions)
        telegram_notify(f"[TEST/EVAL] REGRESSION DETECTED!\n{reg_text}")

    if alerts:
        telegram_notify(f"[TEST/EVAL] Below threshold:\n" + "\n".join(f"  {a}" for a in alerts), silent=True)

    return report


if __name__ == "__main__":
    run_agent_loop(CATEGORY, tick, interval=1800)  # Every 30 minutes
