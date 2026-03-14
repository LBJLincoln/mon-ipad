#!/usr/bin/env python3
"""AMELIORATION Agent — Karpathy-style continuous improvement.

Identifies weakest metrics, proposes improvements, tracks progress over time.
Uses LLM to analyze patterns and suggest fixes.
"""

import json
import os
import sys
import glob
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from base import load_env, llm_call, telegram_notify, log_event, run_agent_loop
from pathlib import Path

CATEGORY = "amelioration"
BASE_DIR = Path("/home/termius/mon-ipad")


def collect_all_metrics():
    """Gather metrics from all other agents and eval data."""
    metrics = {}

    # Latest eval scores
    score_file = BASE_DIR / "data" / "agents" / "test_eval" / "last_scores.json"
    if score_file.exists():
        try:
            with open(score_file) as f:
                metrics["pipeline_scores"] = json.load(f)
        except Exception:
            pass

    # Business data
    biz_log = BASE_DIR / "data" / "agents" / "business" / "events.jsonl"
    if biz_log.exists():
        try:
            lines = biz_log.read_text().strip().split("\n")
            if lines:
                latest = json.loads(lines[-1])
                metrics["business"] = latest.get("summary", {})
        except Exception:
            pass

    # Admin credential status
    admin_log = BASE_DIR / "data" / "agents" / "admin" / "events.jsonl"
    if admin_log.exists():
        try:
            lines = admin_log.read_text().strip().split("\n")
            if lines:
                latest = json.loads(lines[-1])
                metrics["credentials_ok"] = latest.get("credentials_ok", 0)
                metrics["credentials_total"] = latest.get("credentials_total", 0)
        except Exception:
            pass

    # Product health
    produit_log = BASE_DIR / "data" / "agents" / "produit" / "events.jsonl"
    if produit_log.exists():
        try:
            lines = produit_log.read_text().strip().split("\n")
            if lines:
                latest = json.loads(lines[-1])
                metrics["product"] = latest.get("summary", {})
        except Exception:
            pass

    # Eval blast data
    blast_files = sorted(glob.glob(str(BASE_DIR / "data" / "eval" / "blast-*.json")))
    if blast_files:
        try:
            with open(blast_files[-1]) as f:
                blast = json.load(f)
                metrics["latest_blast"] = {
                    "timestamp": blast.get("timestamp", "?"),
                    "total_questions": blast.get("total_generated", 0),
                }
        except Exception:
            pass

    # Health status
    try:
        with open(BASE_DIR / "data" / "health-status.json") as f:
            health = json.load(f)
            metrics["vectors"] = health.get("e5_vectors", "?")
    except Exception:
        pass

    return metrics


def identify_weakest():
    """Find the weakest metric to improve."""
    metrics = collect_all_metrics()
    weaknesses = []

    # Check pipeline scores
    scores = metrics.get("pipeline_scores", {})
    for pipeline, score in scores.items():
        if score < 0.80:
            weaknesses.append({
                "area": "pipeline_accuracy",
                "detail": f"{pipeline}: {score:.0%}",
                "severity": 1.0 - score,
                "pipeline": pipeline,
            })

    # Check revenue
    biz = metrics.get("business", {})
    mrr = biz.get("mrr_usd", 0)
    if mrr == 0:
        weaknesses.append({
            "area": "revenue",
            "detail": "MRR = $0 — no paying customers",
            "severity": 1.0,
        })

    # Check credential health
    creds_ok = metrics.get("credentials_ok", 0)
    creds_total = metrics.get("credentials_total", 1)
    if creds_total > 0 and creds_ok < creds_total:
        weaknesses.append({
            "area": "infrastructure",
            "detail": f"Credentials: {creds_ok}/{creds_total} OK",
            "severity": (creds_total - creds_ok) / creds_total,
        })

    # Check product health
    product = metrics.get("product", {})
    sites_up = product.get("sites_up", 0)
    sites_total = product.get("sites_total", 1)
    if sites_total > 0 and sites_up < sites_total:
        weaknesses.append({
            "area": "product_health",
            "detail": f"Sites: {sites_up}/{sites_total} UP",
            "severity": (sites_total - sites_up) / sites_total,
        })

    # Sort by severity
    weaknesses.sort(key=lambda w: w["severity"], reverse=True)
    return weaknesses, metrics


def propose_improvement(weaknesses, metrics):
    """Use LLM to propose specific improvement action."""
    if not weaknesses:
        return {"action": "All metrics healthy. Continue monitoring.", "priority": "low"}

    top = weaknesses[0]
    prompt = f"""En tant qu'ingenieur ML senior, propose UNE action concrete pour ameliorer cette metrique:

FAIBLESSE: {top['area']} — {top['detail']} (severite: {top['severity']:.2f})

CONTEXTE:
{json.dumps(metrics, indent=2, default=str)[:2000]}

Reponds en JSON:
{{
  "action": "description precise de l'action",
  "expected_impact": "+X% sur quelle metrique",
  "effort": "faible/moyen/eleve",
  "commands": ["commandes bash a executer"],
  "files_to_modify": ["chemins des fichiers"],
  "priority": "critique/haute/moyenne/basse"
}}"""

    response = llm_call(
        prompt,
        system="Ingenieur ML. JSON pur uniquement.",
        max_tokens=1000,
    )

    try:
        return json.loads(response.replace("```json", "").replace("```", "").strip())
    except Exception:
        return {"raw_suggestion": response[:500]}


def tick():
    """One improvement cycle."""
    print("  Collecting all metrics...")
    weaknesses, metrics = identify_weakest()

    if weaknesses:
        print(f"  Top weakness: {weaknesses[0]['area']} — {weaknesses[0]['detail']}")
    else:
        print("  No weaknesses detected")

    print("  Generating improvement proposal...")
    proposal = propose_improvement(weaknesses, metrics)

    report = {
        "weaknesses_count": len(weaknesses),
        "top_weaknesses": weaknesses[:5],
        "proposal": proposal,
        "metrics_snapshot": {k: v for k, v in metrics.items() if k != "latest_blast"},
    }

    # Alert with proposal
    if weaknesses:
        action = proposal.get("action", "?")
        priority = proposal.get("priority", "?")
        top = weaknesses[0]
        telegram_notify(
            f"[AMELIORATION] Top faiblesse: {top['area']}\n"
            f"Detail: {top['detail']}\n"
            f"Action: {action[:200]}\n"
            f"Priorite: {priority}",
            silent=True,
        )

    return report


if __name__ == "__main__":
    run_agent_loop(CATEGORY, tick, interval=7200)  # Every 2 hours
