#!/usr/bin/env python3
"""STRATEGIE Agent — Market intelligence, competitive analysis, roadmap prioritization.

Analyzes our positioning, competitor landscape, and recommends strategic priorities.
Uses LiteLLM for AI analysis of market data.
"""

import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from base import load_env, llm_call, log_event, http_get, run_agent_loop, telegram_notify
from pathlib import Path

CATEGORY = "strategie"
BASE_DIR = Path("/home/termius/mon-ipad")


def collect_current_metrics():
    """Gather current state from health files and eval data."""
    metrics = {}

    # Health status
    try:
        with open(BASE_DIR / "data" / "health-status.json") as f:
            health = json.load(f)
            metrics["e5_vectors"] = health.get("e5_vectors", "?")
            metrics["pipelines"] = health.get("pipelines", {})
    except Exception:
        metrics["health"] = "unavailable"

    # Eval data
    import glob
    eval_files = sorted(glob.glob(str(BASE_DIR / "data" / "eval" / "blast-*.json")))
    if eval_files:
        try:
            with open(eval_files[-1]) as f:
                latest_eval = json.load(f)
                metrics["latest_eval"] = {
                    "timestamp": latest_eval.get("timestamp", "?"),
                    "results": latest_eval.get("results", {}),
                }
        except Exception:
            pass

    # Sector data counts
    try:
        with open(BASE_DIR / "data" / "eval" / "blast-state.json") as f:
            state = json.load(f)
            metrics["eval_questions_total"] = state.get("total_generated", 0)
    except Exception:
        pass

    return metrics


def analyze_positioning():
    """Use LLM to analyze our strategic position."""
    metrics = collect_current_metrics()

    prompt = f"""Analyse la position strategique de Nomos AI (assistant IA expert sectoriel).

METRIQUES ACTUELLES:
{json.dumps(metrics, indent=2, default=str)[:2000]}

PRODUIT: 4 pipelines RAG (Standard, Graph, Quant, Orchestrator) sur 4 secteurs (Finance, BTP, Juridique, Industrie).
INFRA: 9 HF Spaces, LiteLLM proxy 13 providers, Supabase + Neo4j + Pinecone.
MONETISATION: Stripe (3 plans $20/$50/$200), Whop, Gumroad, marketplace. Revenue actuel: $0.
SITES: 8 pages sur nomos42.vercel.app.
COMPETITION: Perplexity (general), Harvey (juridique), Bloomberg GPT (finance).

ANALYSE en JSON:
{{
  "forces": ["..."],
  "faiblesses": ["..."],
  "opportunites": ["..."],
  "menaces": ["..."],
  "priorite_1": "action la plus impactante",
  "priorite_2": "...",
  "priorite_3": "...",
  "score_pret_marche": 0-100,
  "recommandation": "..."
}}"""

    response = llm_call(
        prompt,
        system="Tu es un consultant strategie McKinsey. Reponds en JSON pur uniquement.",
        max_tokens=2000,
    )

    try:
        cleaned = response.replace("```json", "").replace("```", "").strip()
        return json.loads(cleaned)
    except Exception:
        return {"raw_analysis": response[:1500]}


def check_roadmap_alignment():
    """Check if current work aligns with strategic priorities."""
    roadmap_file = BASE_DIR / "technicals" / "PROJECT-ROADMAP.md"
    state_file = BASE_DIR / "directives" / "PROJECT-STATE.md"

    roadmap = ""
    if roadmap_file.exists():
        roadmap = roadmap_file.read_text()[:2000]

    state = ""
    if state_file.exists():
        state = state_file.read_text()[:2000]

    if not roadmap and not state:
        return {"alignment": "no_data"}

    prompt = f"""Compare la roadmap avec l'etat actuel. Identifie les ecarts.

ROADMAP (extrait):
{roadmap[:1000]}

ETAT ACTUEL (extrait):
{state[:1000]}

Reponds en JSON: {{"alignment_score": 0-100, "gaps": ["..."], "on_track": ["..."], "recommendation": "..."}}"""

    response = llm_call(prompt, system="Analyste projet. JSON pur.", max_tokens=800)
    try:
        return json.loads(response.replace("```json", "").replace("```", "").strip())
    except Exception:
        return {"raw": response[:500]}


def tick():
    """One strategy cycle."""
    print("  Analyzing strategic positioning...")
    positioning = analyze_positioning()

    print("  Checking roadmap alignment...")
    alignment = check_roadmap_alignment()

    report = {
        "positioning": positioning,
        "alignment": alignment,
    }

    # Alert on critical findings
    score = positioning.get("score_pret_marche", 0)
    if isinstance(score, (int, float)):
        print(f"  Market readiness: {score}/100")
        if score < 30:
            telegram_notify(
                f"[STRATEGIE] Market readiness LOW: {score}/100\n"
                f"Priorite: {positioning.get('priorite_1', '?')}\n"
                f"Recommandation: {positioning.get('recommandation', '?')[:200]}",
                silent=True,
            )

    return report


if __name__ == "__main__":
    run_agent_loop(CATEGORY, tick, interval=21600)  # Every 6 hours
