#!/usr/bin/env python3
"""
LLM-as-Judge Re-scorer — Post-processes eval results with LLM evaluation.

Reads raw eval results from logs/continuous-eval/raw-*.json,
re-scores each answer using LLM-as-judge via LiteLLM proxy,
and outputs corrected accuracy matrix.

Usage:
  source .env.local
  python3 eval/llm-judge-rescore.py                          # Rescore latest cycle
  python3 eval/llm-judge-rescore.py --cycle 1                # Rescore specific cycle
  python3 eval/llm-judge-rescore.py --input raw-results.json # Rescore from file
  python3 eval/llm-judge-rescore.py --concurrency 2          # Limit parallel LLM calls
"""

import json
import os
import sys
import time
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib import request, error
from collections import defaultdict
from threading import Lock
from glob import glob

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(REPO_ROOT, "logs", "continuous-eval")
RESULTS_FILE = os.path.join(REPO_ROOT, "docs", "sector-accuracy-llm.json")

# ─── LLM backends ────────────────────────────────────────────────────────
LITELLM_URL = "https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/chat/completions"
LITELLM_KEY = os.environ.get("LITELLM_MASTER_KEY", "sk-litellm-nomos-2026")
LITELLM_MODEL = "gemma-27b"

# OpenRouter fallback
OR_KEYS = []
for k in ["OPENROUTER_API_KEY", "OPENROUTER_KEY_SPARE", "OPENROUTER_KEY_GRAPH",
          "OPENROUTER_KEY_STANDARD", "OPENROUTER_KEY_QUANTITATIVE"]:
    v = os.environ.get(k, "")
    if v:
        OR_KEYS.append(v)

_lock = Lock()
_or_idx = 0
_stats = {"llm_calls": 0, "llm_pass": 0, "llm_fail": 0, "fallback": 0}


def _next_or_key():
    global _or_idx
    with _lock:
        key = OR_KEYS[_or_idx % len(OR_KEYS)]
        _or_idx += 1
        return key


def llm_judge_single(question, expected, answer, sector):
    """Call LLM to judge a single answer. Returns (pass, score, reasoning)."""
    if not answer or len(answer) < 10:
        return False, 0, "empty answer"

    prompt = f"""You are an expert evaluator for a {sector} sector AI assistant.

Question: {question}

Expected answer should contain: "{expected}"

Actual answer: {answer[:800]}

Evaluate:
1. Does it correctly address the question? (0-40 pts)
2. Does it contain "{expected}" or equivalent/synonym? (0-30 pts)
3. Is it factually accurate? (0-30 pts)

Respond in EXACTLY this JSON format, nothing else:
{{"pass": true/false, "score": 0-100, "reason": "one sentence"}}"""

    # Try LiteLLM first, then OpenRouter
    backends = []
    if LITELLM_KEY:
        backends.append((LITELLM_URL, LITELLM_MODEL, LITELLM_KEY))
    for _ in range(min(2, len(OR_KEYS))):
        backends.append(("https://openrouter.ai/api/v1/chat/completions",
                         "google/gemma-3-27b-it:free", _next_or_key()))

    for url, model, key in backends:
        payload = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "max_tokens": 150,
        }).encode()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        }
        try:
            req = request.Request(url, data=payload, headers=headers, method="POST")
            with request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
                content = data["choices"][0]["message"]["content"].strip()
                if "```" in content:
                    content = content.split("```")[1].strip()
                    if content.startswith("json"):
                        content = content[4:].strip()
                result = json.loads(content)
                return bool(result.get("pass", False)), int(result.get("score", 0)), str(result.get("reason", ""))[:200]
        except error.HTTPError as e:
            if e.code == 429:
                time.sleep(2)
                continue
            return None, None, f"HTTP {e.code}"
        except Exception as e:
            continue

    return None, None, "all backends failed"


def rescore_result(item):
    """Re-score a single eval result with LLM judge."""
    question = item.get("question", "")
    expected = ""  # Need to look up from dataset
    answer = item.get("answer_preview", "")
    sector = item.get("sector", "unknown")
    old_passed = item.get("passed", False)

    # Load expected from dataset
    dataset_path = os.path.join(REPO_ROOT, "sectors", "eval-datasets", "sector-full-eval.json")
    try:
        with open(dataset_path) as f:
            ds = json.load(f)
        for q in ds["questions"]:
            if q["id"] == item.get("id"):
                expected = q.get("expected_contains", "")
                break
    except Exception:
        pass

    if not expected or not answer:
        return {**item, "llm_pass": old_passed, "llm_score": item.get("quality_score", 0),
                "llm_reasoning": "no expected/answer", "judge": "fallback"}

    passed, score, reasoning = llm_judge_single(question, expected, answer, sector)

    with _lock:
        _stats["llm_calls"] += 1
        if passed is None:
            _stats["fallback"] += 1
            return {**item, "llm_pass": old_passed, "llm_score": item.get("quality_score", 0),
                    "llm_reasoning": reasoning, "judge": "fallback"}
        if passed:
            _stats["llm_pass"] += 1
        else:
            _stats["llm_fail"] += 1

    return {**item, "llm_pass": passed, "llm_score": score,
            "llm_reasoning": reasoning, "judge": "llm"}


def main():
    parser = argparse.ArgumentParser(description="LLM-as-Judge re-scorer")
    parser.add_argument("--cycle", type=int, default=0, help="Cycle number to rescore (0=latest)")
    parser.add_argument("--input", type=str, help="Direct path to raw results JSON")
    parser.add_argument("--concurrency", type=int, default=3, help="Parallel LLM calls")
    args = parser.parse_args()

    # Find input file
    if args.input:
        input_file = args.input
    else:
        raw_files = sorted(glob(os.path.join(LOG_DIR, "raw-*.json")))
        if not raw_files:
            print("ERROR: No raw result files found. Run continuous-sector-eval.py first.")
            sys.exit(1)
        if args.cycle > 0:
            input_file = os.path.join(LOG_DIR, f"raw-{args.cycle:04d}.json")
        else:
            input_file = raw_files[-1]

    print(f"Loading raw results from: {input_file}")
    with open(input_file) as f:
        results = json.load(f)

    # Filter to results with answers
    scoreable = [r for r in results if r.get("answer_preview") and len(r["answer_preview"]) > 10]
    print(f"Total results: {len(results)} | Scoreable: {len(scoreable)}")

    if not scoreable:
        print("No scoreable results. Exiting.")
        return

    # Re-score with LLM
    print(f"Re-scoring with LLM judge (concurrency={args.concurrency})...")
    t0 = time.time()
    rescored = []

    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = {executor.submit(rescore_result, r): r for r in scoreable}
        done = 0
        for future in as_completed(futures):
            result = future.result()
            rescored.append(result)
            done += 1
            if done % 10 == 0:
                sys.stdout.write(f"\r  [{done}/{len(scoreable)}] LLM calls: {_stats['llm_calls']} | "
                                 f"pass: {_stats['llm_pass']} | fail: {_stats['llm_fail']} | "
                                 f"fallback: {_stats['fallback']}")
                sys.stdout.flush()

    elapsed = time.time() - t0
    print(f"\n\nDone in {elapsed:.0f}s")
    print(f"Stats: {json.dumps(_stats)}")

    # Compute LLM-judged accuracy matrix
    sector_pipeline_pass = defaultdict(lambda: defaultdict(list))
    sector_pipeline_score = defaultdict(lambda: defaultdict(list))

    for r in rescored:
        sector = r.get("sector", "unknown")
        pipeline = r.get("pipeline", "standard")
        sector_pipeline_pass[sector][pipeline].append(r.get("llm_pass", r.get("passed", False)))
        sector_pipeline_score[sector][pipeline].append(r.get("llm_score", r.get("quality_score", 0)))

    # Also add non-scoreable results as failures
    non_scoreable = [r for r in results if r not in scoreable]
    for r in non_scoreable:
        sector = r.get("sector", "unknown")
        pipeline = r.get("pipeline", "standard")
        sector_pipeline_pass[sector][pipeline].append(False)
        sector_pipeline_score[sector][pipeline].append(0)

    print("\n" + "=" * 70)
    print("  LLM-JUDGED ACCURACY MATRIX")
    print("=" * 70)
    print(f"  {'Sector':<15} {'Standard':>10} {'Graph':>10} {'Quant':>10} {'Orch':>10}")
    print("  " + "-" * 55)

    matrix = {}
    for sector in ["finance", "btp", "juridique", "industrie"]:
        matrix[sector] = {}
        row = f"  {sector:<15}"
        for pipeline in ["standard", "graph", "quantitative", "orchestrator"]:
            passes = sector_pipeline_pass.get(sector, {}).get(pipeline, [])
            if passes:
                pct = round(sum(passes) / len(passes) * 100, 1)
                matrix[sector][pipeline] = pct
                row += f" {pct:>9.1f}%"
            else:
                matrix[sector][pipeline] = None
                row += f" {'—':>10}"
        print(row)

    # Quality scores
    print(f"\n  {'QUALITY (0-100)':<15}")
    print(f"  {'Sector':<15} {'Standard':>10} {'Graph':>10} {'Quant':>10} {'Orch':>10}")
    print("  " + "-" * 55)
    quality = {}
    for sector in ["finance", "btp", "juridique", "industrie"]:
        quality[sector] = {}
        row = f"  {sector:<15}"
        for pipeline in ["standard", "graph", "quantitative", "orchestrator"]:
            scores = sector_pipeline_score.get(sector, {}).get(pipeline, [])
            if scores:
                avg = round(sum(scores) / len(scores), 1)
                quality[sector][pipeline] = avg
                row += f" {avg:>10.1f}"
            else:
                quality[sector][pipeline] = None
                row += f" {'—':>10}"
        print(row)

    # Save
    output = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "judge": "llm",
        "model": LITELLM_MODEL,
        "matrix": matrix,
        "quality": quality,
        "stats": _stats,
        "elapsed_seconds": round(elapsed, 1),
    }
    with open(RESULTS_FILE, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n  Results saved to {RESULTS_FILE}")

    # Also save rescored details
    detail_file = os.path.join(LOG_DIR, f"llm-rescored-{os.path.basename(input_file)}")
    with open(detail_file, "w") as f:
        json.dump(rescored, f, indent=2, ensure_ascii=False)
    print(f"  Details saved to {detail_file}")


if __name__ == "__main__":
    main()
