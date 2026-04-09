#!/usr/bin/env python3
"""
Nomos42 -- HF Inference Eval Loop (replaces Colab manual notebook)
==================================================================
Karpathy autoresearch pattern using HF Inference API as the "GPU":
  mutate config -> ask LLM to score/select -> measure on island CPU -> keep if better

This is the automated replacement for "colab" in the orchestrator.
It runs on the VM (CPU only for feature mutation), uses HF Inference LLMs
for experiment selection guidance, and evaluates on live HF islands.

Priority path:
  1. Generate N mutation candidates (CPU, just index manipulation)
  2. Use LLM council (Gemma/Qwen) to rank them intelligently
  3. Evaluate top 3 candidates on HF island /api/evaluate (CPU, free)
  4. Keep if improved, push to GitHub

This is NOT GPU training. It's intelligent Karpathy-style search.
Budget: ~10 min, unlimited runs, zero cost.

Usage:
    python3 scripts/gpu-burst/hf-inference-eval.py
    python3 scripts/gpu-burst/hf-inference-eval.py --iterations 30
    python3 scripts/gpu-burst/hf-inference-eval.py --dry-run

Cron (dispatched by compute-orchestrator at 18:00 UTC):
    Handled by compute-orchestrator.py -- do not add direct cron entry.
"""

import argparse
import json
import os
import random
import ssl
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

# ══════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════

REPO_ROOT = Path("/home/termius/mon-ipad")
RESULT_DIR = REPO_ROOT / "data" / "gpu-burst"
KARPATHY_DIR = REPO_ROOT / "data" / "karpathy"
LOG_FILE = RESULT_DIR / "hf-inference-eval-log.jsonl"
RESULT_FILE = RESULT_DIR / "latest-colab-result.json"  # Named 'colab' for orchestrator compat
BEST_CONFIG_PATH = KARPATHY_DIR / "nba-best-config.json"

ATR_BRIER = 0.21570
IMPROVEMENT_THRESHOLD = 0.00005
MAX_FEATURES = 200
TARGET_FEATURES = 63
N_TOTAL_FEATURES = 6253

HF_ISLANDS = {
    "S10": "https://nomos42-nba-quant.hf.space",
    "S11": "https://nomos42-nba-quant-2.hf.space",
    "S12": "https://nomos42-nba-evo-3.hf.space",
    "S13": "https://nomos42-nba-evo-4.hf.space",
    "S14": "https://nomos42-nba-evo-5.hf.space",
    "S15": "https://nomos42-nba-evo-6.hf.space",
}

# HF Inference API models (working as of Apr 2026)
HF_MODELS = [
    "google/gemma-3-27b-it",
    "Qwen/Qwen2.5-72B-Instruct",
    "meta-llama/Llama-3.1-8B-Instruct",
    "Qwen/Qwen2.5-7B-Instruct",
]

MODEL_TYPES = ["xgboost", "catboost", "lightgbm", "extra_trees", "random_forest"]
MODEL_WEIGHTS = [0.3, 0.2, 0.2, 0.2, 0.1]

MUTATION_RATES = [0.05, 0.09, 0.12, 0.18, 0.25]
SWAP_SIZES = [3, 5, 8, 12, 20]


# ══════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════

def ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str, level: str = "INFO"):
    print(f"[{ts()}] [{level}] {msg}")


def _ssl_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def http_get(url: str, token: str = "", timeout: int = 20) -> Optional[dict]:
    headers = {"User-Agent": "Nomos42-HFEval/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as resp:
            return json.loads(resp.read())
    except Exception as e:
        log(f"GET {url}: {e}", "WARN")
        return None


def http_post(url: str, payload: dict, token: str = "", timeout: int = 60) -> Optional[dict]:
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json", "User-Agent": "Nomos42-HFEval/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        req = urllib.request.Request(url, data=data, method="POST", headers=headers)
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as resp:
            return json.loads(resp.read())
    except Exception as e:
        log(f"POST {url}: {e}", "WARN")
        return None


def send_telegram(message: str):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("ADMIN_TELEGRAM_ID", "")
    if not token or not chat_id:
        return
    try:
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": message}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage", data=data
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def append_log(entry: dict):
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


# ══════════════════════════════════════════════════════════
# CONFIG MANAGEMENT
# ══════════════════════════════════════════════════════════

def load_best_config() -> dict:
    """Load best known config."""
    if BEST_CONFIG_PATH.exists():
        try:
            cfg = json.loads(BEST_CONFIG_PATH.read_text())
            log(f"Loaded best config: brier={cfg.get('best_brier', '?')}, "
                f"n_features={cfg.get('n_features', '?')}")
            return cfg
        except Exception:
            pass
    log("No best config found — using defaults", "WARN")
    return {
        "model_type": "xgboost",
        "n_estimators": 200,
        "max_depth": 6,
        "learning_rate": 0.1,
        "feature_indices": list(range(TARGET_FEATURES)),
        "n_features": TARGET_FEATURES,
        "best_brier": ATR_BRIER,
        "iteration": 0,
    }


def save_best_config(cfg: dict):
    BEST_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    BEST_CONFIG_PATH.write_text(json.dumps(cfg, indent=2))
    log(f"Saved new best config: brier={cfg.get('best_brier', '?')}")


# ══════════════════════════════════════════════════════════
# ISLAND SEEDING
# ══════════════════════════════════════════════════════════

def fetch_island_seeds() -> List[dict]:
    """Pull best configs from live HF islands."""
    seeds = []
    for name, base_url in HF_ISLANDS.items():
        data = http_get(f"{base_url}/api/best", timeout=15)
        if data and float(data.get("brier", 1.0)) < 0.99:
            seeds.append({
                "source": name,
                "brier": float(data.get("brier", 1.0)),
                "feature_indices": data.get("features", []),
                "model_type": data.get("model_type", "xgboost"),
                "hp": data.get("hp", {}),
            })
            log(f"Seed {name}: brier={data.get('brier', '?')}")
        else:
            log(f"Seed {name}: unavailable", "WARN")
    return seeds


# ══════════════════════════════════════════════════════════
# MUTATION ENGINE (CPU only — no ML, pure index manipulation)
# ══════════════════════════════════════════════════════════

def mutate_config(base: dict, mutation_rate: float, swap_size: int) -> dict:
    """Mutate a config on CPU — zero ML, just index shuffling."""
    features = list(base.get("feature_indices", list(range(TARGET_FEATURES))))

    n_remove = max(1, int(len(features) * mutation_rate))
    n_add = n_remove + random.choice([-swap_size, 0, swap_size])
    n_add = max(0, min(n_add, MAX_FEATURES - len(features) + n_remove))

    features_set = set(features)
    remove_candidates = random.sample(features, min(n_remove, len(features)))
    for f in remove_candidates:
        features_set.discard(f)

    available = [i for i in range(N_TOTAL_FEATURES) if i not in features_set]
    if available and n_add > 0:
        to_add = random.sample(available, min(n_add, len(available)))
        features_set.update(to_add)

    new_features = sorted(features_set)
    if len(new_features) > MAX_FEATURES:
        new_features = sorted(random.sample(new_features, MAX_FEATURES))

    new_model = base.get("model_type", "xgboost")
    if random.random() < 0.25:
        new_model = random.choices(MODEL_TYPES, weights=MODEL_WEIGHTS)[0]

    new_n_est = base.get("n_estimators", 200)
    new_depth = base.get("max_depth", 6)
    new_lr = base.get("learning_rate", 0.1)
    if random.random() < 0.20:
        new_n_est = max(100, min(500, new_n_est + random.choice([-50, 0, 50])))
    if random.random() < 0.20:
        new_depth = max(4, min(10, new_depth + random.choice([-1, 0, 1])))
    if random.random() < 0.20:
        new_lr = round(max(0.01, min(0.3, (new_lr or 0.1) * random.uniform(0.8, 1.25))), 4)

    return {
        "model_type": new_model,
        "n_estimators": new_n_est,
        "max_depth": new_depth,
        "min_samples_leaf": base.get("min_samples_leaf", 5),
        "max_features_ratio": base.get("max_features_ratio", 0.4),
        "learning_rate": new_lr,
        "feature_indices": new_features,
        "n_features": len(new_features),
        "parent_brier": float(base.get("best_brier", 1.0)),
        "mutation_rate": mutation_rate,
        "swap_size": swap_size,
        "timestamp": ts(),
    }


# ══════════════════════════════════════════════════════════
# LLM COUNCIL RANKING (HF Inference API)
# Uses LLM to intelligently rank mutation candidates
# ══════════════════════════════════════════════════════════

def llm_rank_candidates(candidates: List[dict], baseline_brier: float, token: str) -> List[int]:
    """Use LLM to rank candidates by likely improvement potential.
    Returns sorted indices (best first). Falls back to random order on failure.
    """
    if not token:
        return list(range(len(candidates)))

    prompt = f"""You are an NBA prediction ML expert. Current best Brier score: {baseline_brier:.5f} (target: 0.20000).

I have {len(candidates)} mutation candidates. Rank them by likely Brier improvement potential (best first).

Candidates:
"""
    for i, c in enumerate(candidates):
        prompt += (
            f"\n{i+1}. model={c['model_type']}, "
            f"features={c['n_features']}f (target=63), "
            f"mut_rate={c.get('mutation_rate', '?')}, "
            f"swap={c.get('swap_size', '?')}, "
            f"n_est={c.get('n_estimators', '?')}, "
            f"depth={c.get('max_depth', '?')}"
        )

    prompt += "\n\nReply with ONLY the ranking as comma-separated numbers, e.g.: 3,1,4,2"

    # Try each model
    for model_id in HF_MODELS[:2]:  # Only try top 2 models for speed
        url = f"https://api-inference.huggingface.co/models/{model_id}/v1/chat/completions"
        payload = {
            "model": model_id,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 50,
            "temperature": 0.1,
        }
        resp = http_post(url, payload, token=token, timeout=20)
        if resp:
            try:
                content = resp["choices"][0]["message"]["content"].strip()
                # Parse "3,1,4,2" -> [2, 0, 3, 1] (0-indexed)
                ranking_1indexed = [int(x.strip()) for x in content.split(",") if x.strip().isdigit()]
                ranking_0indexed = [r - 1 for r in ranking_1indexed if 1 <= r <= len(candidates)]
                # Fill in any missing indices
                all_indices = set(range(len(candidates)))
                missing = [i for i in range(len(candidates)) if i not in ranking_0indexed]
                ranking_0indexed += missing
                log(f"LLM ({model_id.split('/')[-1]}) ranking: {ranking_0indexed}")
                return ranking_0indexed
            except Exception as e:
                log(f"LLM parse error: {e}", "WARN")

    log("LLM ranking failed — using default order", "WARN")
    return list(range(len(candidates)))


# ══════════════════════════════════════════════════════════
# ISLAND EVALUATION (CPU on HF Space)
# ══════════════════════════════════════════════════════════

def evaluate_on_islands(config: dict) -> Optional[float]:
    """Evaluate config on live HF islands via /api/evaluate endpoint.
    Returns best Brier across responding islands, or None if all fail.
    """
    payload = {
        "features": config.get("feature_indices", []),
        "model_type": config.get("model_type", "xgboost"),
        "n_estimators": config.get("n_estimators", 200),
        "max_depth": config.get("max_depth", 6),
        "learning_rate": config.get("learning_rate", 0.1),
    }

    briers = []
    # Try islands in order, stop after first 2 responses (speed)
    for name, base_url in list(HF_ISLANDS.items())[:4]:
        resp = http_post(f"{base_url}/api/evaluate", payload, timeout=90)
        if resp:
            b = float(resp.get("brier", 1.0))
            if 0.0 < b < 0.99:
                briers.append(b)
                log(f"  Island {name}: brier={b:.5f}")
                if len(briers) >= 2:
                    break  # Have enough data points

    return min(briers) if briers else None


# ══════════════════════════════════════════════════════════
# PUSH RESULTS
# ══════════════════════════════════════════════════════════

def push_to_github(result: dict) -> bool:
    """Push new best config to GitHub via git."""
    import subprocess

    github_token = os.environ.get("GITHUB_TOKEN", "")
    if not github_token:
        log("No GITHUB_TOKEN — skipping GitHub push", "WARN")
        return False

    try:
        repo_dir = REPO_ROOT
        subprocess.run(
            ["git", "-C", str(repo_dir), "config", "user.email", "nomos42@users.noreply.github.com"],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo_dir), "config", "user.name", "Nomos42 HF-Eval"],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo_dir), "add",
             str(BEST_CONFIG_PATH), str(RESULT_FILE)],
            check=True, capture_output=True,
        )
        msg = (
            f"gpu-burst: hf-eval brier={result.get('best_brier', '?'):.5f} "
            f"({result.get('model_type', '?')}, {result.get('n_features', '?')}f, "
            f"iter {result.get('iteration', '?')})"
        )
        ret = subprocess.run(
            ["git", "-C", str(repo_dir), "commit", "-m", msg],
            capture_output=True, text=True,
        )
        if ret.returncode != 0:
            log(f"Nothing to commit: {ret.stderr[:100]}", "WARN")
            return False

        ret = subprocess.run(
            ["git", "-C", str(repo_dir), "push", "origin", "main"],
            capture_output=True, text=True, timeout=60,
        )
        if ret.returncode == 0:
            log(f"Pushed to GitHub: {msg}")
            return True
        else:
            log(f"Push failed: {ret.stderr[:200]}", "WARN")
            return False
    except Exception as e:
        log(f"GitHub push error: {e}", "ERROR")
        return False


def update_island_config(result: dict):
    """Send new best config to S10 /api/config."""
    payload = {
        "best_brier": result.get("best_brier", 1.0),
        "features": result.get("feature_indices", []),
        "model_type": result.get("model_type", "xgboost"),
        "hp": {
            "depth": result.get("max_depth", 6),
            "lr": result.get("learning_rate", 0.1),
            "n_est": result.get("n_estimators", 200),
        },
        "source": "hf-inference-eval",
        "timestamp": ts(),
    }
    resp = http_post(f"{HF_ISLANDS['S10']}/api/config", payload, timeout=20)
    if resp:
        log("Updated S10 island config")


# ══════════════════════════════════════════════════════════
# MAIN EVAL LOOP
# ══════════════════════════════════════════════════════════

def run_eval_loop(n_iterations: int = 20, dry_run: bool = False) -> dict:
    """
    Main Karpathy-style eval loop:
      1. Load best config
      2. Generate N candidates (CPU mutation)
      3. LLM council ranks them
      4. Evaluate top-K on island CPU
      5. Keep if improved
      Repeat for n_iterations.
    """
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    start_time = time.time()

    token = os.environ.get("HF_TOKEN", "")

    log("=" * 60)
    log("HF INFERENCE EVAL LOOP (Karpathy pattern)")
    log(f"Iterations: {n_iterations} | Dry run: {dry_run}")
    log("=" * 60)

    # Load base config
    base = load_best_config()
    baseline_brier = float(base.get("best_brier", ATR_BRIER))
    log(f"Baseline: brier={baseline_brier:.5f}")

    # Seed from islands
    seeds = fetch_island_seeds()
    if seeds:
        best_seed = min(seeds, key=lambda s: s.get("brier", 1.0))
        if best_seed["brier"] < baseline_brier:
            log(f"Better seed from {best_seed['source']}: {best_seed['brier']:.5f}")
            base["feature_indices"] = best_seed.get("feature_indices", base["feature_indices"])
            base["model_type"] = best_seed.get("model_type", base["model_type"])
            baseline_brier = best_seed["brier"]

    best_brier_found = baseline_brier
    best_candidate = None
    total_evals = 0
    improvements = 0

    for iteration in range(1, n_iterations + 1):
        elapsed = time.time() - start_time
        log(f"\n--- Iteration {iteration}/{n_iterations} ({elapsed:.0f}s elapsed) ---")

        # Generate 6 candidates with varied mutation strategies
        n_candidates = 6
        candidates = []
        for i in range(n_candidates):
            mut_rate = MUTATION_RATES[i % len(MUTATION_RATES)]
            swap = SWAP_SIZES[i % len(SWAP_SIZES)]
            candidates.append(mutate_config(base, mut_rate, swap))

        # LLM council ranks them (intelligently selects which to evaluate)
        ranking = llm_rank_candidates(candidates, best_brier_found, token)
        top_k = 3  # Evaluate top 3 ranked candidates

        if dry_run:
            log(f"DRY RUN: would evaluate top {top_k} of {n_candidates} candidates")
            continue

        # Evaluate top-K ranked candidates
        iter_improved = False
        for rank_i in range(min(top_k, len(ranking))):
            cand_idx = ranking[rank_i]
            if cand_idx >= len(candidates):
                continue
            candidate = candidates[cand_idx]
            total_evals += 1

            log(f"Evaluating candidate {rank_i+1} (rank {cand_idx+1}): "
                f"{candidate['n_features']}f, {candidate['model_type']}, "
                f"mut={candidate.get('mutation_rate', '?')}")

            brier = evaluate_on_islands(candidate)

            if brier is None:
                log(f"  Evaluation failed (islands unreachable)", "WARN")
                append_log({
                    "ts": ts(), "iteration": iteration,
                    "candidate": cand_idx, "status": "eval_failed",
                })
                continue

            log(f"  Result: {brier:.5f} "
                f"({'BETTER' if brier < best_brier_found else 'worse'} "
                f"vs {best_brier_found:.5f})")

            append_log({
                "ts": ts(), "iteration": iteration,
                "candidate": cand_idx, "brier": brier,
                "model_type": candidate["model_type"],
                "n_features": candidate["n_features"],
                "mutation_rate": candidate.get("mutation_rate"),
                "improved": brier < best_brier_found,
            })

            if brier < best_brier_found - IMPROVEMENT_THRESHOLD:
                best_brier_found = brier
                best_candidate = candidate.copy()
                best_candidate["best_brier"] = brier
                iter_improved = True
                improvements += 1
                log(f"  *** NEW BEST: {brier:.5f} ***")
                # Use this as new base for next iteration
                base = best_candidate.copy()

        if not iter_improved:
            log(f"  No improvement this iteration")

    # Finalize
    total_time = time.time() - start_time
    result = {
        "platform": "hf_inference_eval",
        "timestamp": ts(),
        "baseline_brier": baseline_brier,
        "best_brier": best_brier_found,
        "improvement": round(baseline_brier - best_brier_found, 6),
        "improved": best_candidate is not None,
        "iterations": n_iterations,
        "total_evals": total_evals,
        "improvements_found": improvements,
        "total_time_sec": round(total_time, 1),
    }

    if best_candidate:
        result.update({
            "model_type": best_candidate.get("model_type", "?"),
            "n_features": best_candidate.get("n_features", 0),
            "feature_indices": best_candidate.get("feature_indices", []),
            "max_depth": best_candidate.get("max_depth", 6),
            "learning_rate": best_candidate.get("learning_rate", 0.1),
            "n_estimators": best_candidate.get("n_estimators", 200),
        })

        log(f"\nIMPROVEMENT: {baseline_brier:.5f} -> {best_brier_found:.5f} "
            f"(delta={result['improvement']:.6f})")

        iter_num = base.get("iteration", 0) + 1
        best_candidate["iteration"] = iter_num
        save_best_config(best_candidate)

        if not dry_run:
            update_island_config(best_candidate)
            push_to_github(result)
            send_telegram(
                f"HF Eval Loop -- IMPROVED\n"
                f"Brier: {baseline_brier:.5f} -> {best_brier_found:.5f}\n"
                f"Model: {best_candidate.get('model_type', '?')}, "
                f"{best_candidate.get('n_features', '?')}f\n"
                f"Iter {iter_num} | {n_iterations} loops | {total_time:.0f}s"
            )
        result["status"] = "improved"
    else:
        log(f"\nNo improvement found (best: {best_brier_found:.5f})")
        result["status"] = "no_improvement"

    # Save result
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_FILE.write_text(json.dumps(result, indent=2))

    log(f"\n{'='*60}")
    log(f"EVAL LOOP COMPLETE")
    log(f"  Iterations: {n_iterations} | Evals: {total_evals}")
    log(f"  Best Brier: {best_brier_found:.5f} | Improvements: {improvements}")
    log(f"  Time: {total_time:.0f}s")
    log(f"{'='*60}")

    return result


# ══════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="HF Inference Eval Loop — automated Karpathy pattern"
    )
    parser.add_argument("--iterations", type=int, default=20,
                        help="Number of eval iterations (default: 20)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show mutations without evaluating")
    args = parser.parse_args()

    # Load env
    env_file = REPO_ROOT / ".env.local"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[7:]
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and val and key not in os.environ:
                os.environ[key] = val

    result = run_eval_loop(n_iterations=args.iterations, dry_run=args.dry_run)
    sys.exit(0 if result.get("status") in ("improved", "no_improvement") else 1)


if __name__ == "__main__":
    main()
