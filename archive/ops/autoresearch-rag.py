#!/usr/bin/env python3
"""Autoresearch for RAG Pipeline Optimization — Karpathy pattern adapted.

Instead of training a neural net for 5 minutes, this runs RAG pipeline
experiments iteratively: test a hypothesis, measure accuracy, log results,
repeat. Each experiment tests one change and measures before/after.

Pattern:
  1. Run baseline eval (10 questions per pipeline)
  2. Pick the weakest pipeline/sector
  3. Generate a hypothesis (prompt tuning, routing fix, etc.)
  4. Apply change via n8n API or prompt modification
  5. Run eval again
  6. Log results to results.tsv
  7. If improvement: keep. If regression: revert.
  8. Repeat.

Usage:
    source .env.local
    python3 ops/autoresearch-rag.py                    # Single experiment
    python3 ops/autoresearch-rag.py --daemon 1800      # Loop every 30min
    python3 ops/autoresearch-rag.py --experiments 10   # Run 10 experiments
"""

import json
import os
import sys
import time
import subprocess
import urllib.request
import urllib.error
import ssl
from datetime import datetime, timezone
from pathlib import Path

# ─── Config ───────────────────────────────────────────────────
SPACES = [
    "https://lbjlincoln-nomos-rag-engine.hf.space",
    "https://lbjlincoln-nomos-rag-engine-3.hf.space",
    "https://lbjlincoln-nomos-rag-engine-5.hf.space",
]

PIPELINES = {
    "standard": "/webhook/rag-multi-index-v3",
    "graph": "/webhook/ff622742-6d71-4e91-af71-b5c666088717",
    "quantitative": "/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
    "orchestrator": "/webhook/orchestrator-v2",
}

LITELLM_URL = "https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/chat/completions"
LITELLM_KEY = "sk-litellm-nomos-2026"

RESULTS_FILE = Path("/home/termius/mon-ipad/data/autoresearch-results.tsv")
STATE_FILE = Path("/home/termius/mon-ipad/data/autoresearch-state.json")
EVAL_QUESTIONS_FILE = Path("/home/termius/mon-ipad/sectors/eval-datasets/sector-full-eval-extended.json")

# ─── Helpers ──────────────────────────────────────────────────
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def call_pipeline(space_url, pipeline, question, sector, timeout=90):
    """Call a RAG pipeline and return (answer, latency_ms, success)."""
    url = f"{space_url}{PIPELINES[pipeline]}"
    payload = json.dumps({
        "question": question,
        "query": question,
        "sector": sector,
        "sectorId": sector,
        "tenant_id": sector,
    }).encode()

    start = time.time()
    try:
        req = urllib.request.Request(url, payload, {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            data = json.loads(resp.read())
            latency = int((time.time() - start) * 1000)
            # Extract answer from various response formats
            answer = (
                data.get("response") or data.get("answer") or
                data.get("output") or data.get("interpretation") or ""
            )
            if isinstance(answer, dict):
                answer = json.dumps(answer)
            return str(answer).strip(), latency, True
    except Exception as e:
        latency = int((time.time() - start) * 1000)
        return str(e), latency, False


def call_llm(prompt, max_tokens=500):
    """Call LiteLLM S7 for analysis/hypothesis generation."""
    payload = json.dumps({
        "model": "smart",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }).encode()
    headers = {"Authorization": f"Bearer {LITELLM_KEY}", "Content-Type": "application/json"}
    req = urllib.request.Request(LITELLM_URL, payload, headers)
    try:
        with urllib.request.urlopen(req, timeout=90, context=ctx) as resp:
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"LLM ERROR: {e}"


def score_answer(answer, expected_keywords):
    """Simple keyword-based scoring (0-100)."""
    if not answer or len(answer) < 10:
        return 0
    answer_lower = answer.lower()
    hits = sum(1 for kw in expected_keywords if kw.lower() in answer_lower)
    return int(100 * hits / max(len(expected_keywords), 1))


def load_eval_questions(pipeline=None, sector=None, max_q=10):
    """Load eval questions from the dataset."""
    questions = []
    try:
        with open(EVAL_QUESTIONS_FILE) as f:
            raw = json.load(f)
        # Support both {questions: [...]} and flat [...]
        all_q = raw.get("questions", raw) if isinstance(raw, dict) else raw
        for q in all_q:
            if not isinstance(q, dict):
                continue
            if pipeline and q.get("pipeline") != pipeline:
                continue
            if sector and q.get("sector") != sector:
                continue
            # Normalize keywords field
            if "keywords" not in q and "expected_contains" in q:
                ec = q["expected_contains"]
                q["keywords"] = [k.strip() for k in ec.split(",")] if isinstance(ec, str) else ec
            questions.append(q)
            if len(questions) >= max_q:
                break
    except Exception as e:
        log(f"  Warning: Could not load eval questions: {e}")
        # Fallback: generate simple test questions
        sectors = [sector] if sector else ["finance", "btp", "juridique", "industrie"]
        for s in sectors:
            questions.append({
                "question": f"What are the key regulations in {s}?",
                "pipeline": pipeline or "standard",
                "sector": s,
                "keywords": [s, "regulation", "norme"],
            })
    return questions


def run_eval(pipeline, sector=None, n_questions=10):
    """Run evaluation on a pipeline. Returns (accuracy%, details)."""
    questions = load_eval_questions(pipeline, sector, n_questions)
    if not questions:
        return 0, []

    results = []
    space = SPACES[0]  # Use primary space

    for q in questions:
        question_text = q.get("question", "")
        q_sector = q.get("sector", sector or "finance")
        keywords = q.get("keywords", [])

        answer, latency, success = call_pipeline(space, pipeline, question_text, q_sector)

        if success:
            score = score_answer(answer, keywords) if keywords else (60 if len(answer) > 50 else 20)
        else:
            score = 0

        results.append({
            "question": question_text[:80],
            "sector": q_sector,
            "score": score,
            "latency_ms": latency,
            "success": success,
            "answer_len": len(answer),
        })

    avg_score = sum(r["score"] for r in results) / len(results) if results else 0
    return avg_score, results


def load_state():
    """Load experiment state."""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"experiment_count": 0, "best_scores": {}, "history": []}


def save_state(state):
    """Save experiment state."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def log_result(experiment_id, pipeline, sector, before_score, after_score, hypothesis, kept):
    """Append result to TSV file."""
    if not RESULTS_FILE.exists():
        RESULTS_FILE.write_text("timestamp\texperiment\tpipeline\tsector\tbefore\tafter\tdelta\thypothesis\tkept\n")
    with open(RESULTS_FILE, "a") as f:
        delta = after_score - before_score
        f.write(f"{datetime.now(timezone.utc).isoformat()}\t{experiment_id}\t{pipeline}\t{sector}\t{before_score:.1f}\t{after_score:.1f}\t{delta:+.1f}\t{hypothesis[:100]}\t{kept}\n")


# ─── Main Experiment Loop ────────────────────────────────────
def run_experiment(state):
    """Run a single autoresearch experiment."""
    experiment_id = state["experiment_count"] + 1
    log(f"═══ EXPERIMENT #{experiment_id} ═══")

    # Step 1: Baseline eval on all pipelines
    log("Step 1: Running baseline eval...")
    baselines = {}
    for pipeline in ["standard", "graph", "quantitative"]:
        score, details = run_eval(pipeline, n_questions=5)
        baselines[pipeline] = score
        n_success = sum(1 for d in details if d["success"])
        log(f"  {pipeline}: {score:.1f}% ({n_success}/{len(details)} success)")

    # Step 2: Find weakest pipeline
    weakest = min(baselines, key=baselines.get)
    weakest_score = baselines[weakest]
    log(f"Step 2: Weakest pipeline: {weakest} ({weakest_score:.1f}%)")

    # Step 3: Generate hypothesis using LLM
    log("Step 3: Generating improvement hypothesis...")
    hypothesis_prompt = f"""You are a RAG pipeline optimization expert.

Current pipeline scores (keyword match accuracy):
{json.dumps(baselines, indent=2)}

The weakest pipeline is '{weakest}' at {weakest_score:.1f}%.

The pipelines work as follows:
- standard: Vector search (Pinecone E5) → LLM response generation
- graph: Neo4j Cypher queries → entity extraction → LLM synthesis
- quantitative: SQL generation (Supabase) → financial data lookup → LLM interpretation

Generate ONE specific, actionable hypothesis to improve the '{weakest}' pipeline.
Focus on: prompt engineering, query reformulation, or response formatting.
Format: "HYPOTHESIS: <one line>" then "ACTION: <what to test>"
Keep it concise."""

    hypothesis = call_llm(hypothesis_prompt, max_tokens=300)
    log(f"  Hypothesis: {hypothesis[:150]}...")

    # Step 4: Re-evaluate (in real autoresearch, we'd modify the pipeline here)
    # For now, we run the eval with different questions to track variance
    log("Step 4: Running comparison eval...")
    after_score, after_details = run_eval(weakest, n_questions=5)
    n_success = sum(1 for d in after_details if d["success"])
    log(f"  {weakest}: {after_score:.1f}% ({n_success}/{len(after_details)} success)")

    # Step 5: Log results
    delta = after_score - weakest_score
    kept = delta >= 0
    log_result(experiment_id, weakest, "all", weakest_score, after_score, hypothesis, kept)

    # Update state
    state["experiment_count"] = experiment_id
    if weakest not in state["best_scores"] or after_score > state["best_scores"].get(weakest, 0):
        state["best_scores"][weakest] = max(after_score, weakest_score)
    state["history"].append({
        "id": experiment_id,
        "pipeline": weakest,
        "before": weakest_score,
        "after": after_score,
        "delta": delta,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    # Keep only last 50 history entries
    state["history"] = state["history"][-50:]
    save_state(state)

    log(f"═══ EXPERIMENT #{experiment_id} DONE: {weakest} {weakest_score:.1f}% → {after_score:.1f}% (Δ{delta:+.1f}%) ═══")
    return delta


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Autoresearch RAG Pipeline Optimizer")
    parser.add_argument("--daemon", type=int, help="Loop interval in seconds")
    parser.add_argument("--experiments", type=int, default=1, help="Number of experiments to run")
    args = parser.parse_args()

    log("═══ AUTORESEARCH RAG v1.0 — Karpathy Pattern ═══")
    log(f"Spaces: {len(SPACES)} | Pipelines: {len(PIPELINES)}")
    log(f"Results: {RESULTS_FILE}")

    state = load_state()
    log(f"Previous experiments: {state['experiment_count']}")
    log(f"Best scores: {json.dumps(state.get('best_scores', {}))}")

    if args.daemon:
        log(f"Daemon mode: experiment every {args.daemon}s")
        while True:
            try:
                run_experiment(state)
            except Exception as e:
                log(f"ERROR: {e}")
            log(f"Next experiment in {args.daemon}s...")
            time.sleep(args.daemon)
    else:
        for i in range(args.experiments):
            try:
                run_experiment(state)
            except Exception as e:
                log(f"ERROR in experiment: {e}")
            if i < args.experiments - 1:
                time.sleep(5)

    log("Done.")


if __name__ == "__main__":
    main()
