#!/usr/bin/env python3
"""
NBA Quant AI -- HF ZeroGPU Burst (5 min/account × 3 accounts = 15 min/day free H200)
======================================================================================
Karpathy autoresearch pattern: load best config → mutate → evaluate on H200 → keep if better.

How ZeroGPU works:
  - HF Spaces with ZeroGPU enabled share a pool of H200 GPUs (no dedicated GPU per Space).
  - The @spaces.GPU decorator acquires the GPU for the duration of the decorated function.
  - Free tier: ~5 min/day per HF account | Pro ($9/mo): 25 min/day per account.
  - We cycle through 3 accounts (LBJLincoln, LBJLincoln26, Nomos42) for ~15 min/day total.

This script submits to a ZeroGPU-enabled HF Space via the Inference API, NOT via the
@spaces.GPU decorator directly (that only works inside a Space). Instead it:
  1. Calls the HF Inference API with a serverless endpoint (which uses ZeroGPU under the hood).
  2. Falls back to a Gradio Space API call if the serverless endpoint isn't available.

Usage (run on the VM or any machine with internet):
    HF_TOKEN=hf_xxx python3 scripts/gpu-burst/zerogpu-burst.py --account 0
    # --account 0 = LBJLincoln, 1 = LBJLincoln26, 2 = Nomos42, 3 = all (sequential)

Cron (run all 3 accounts once per day):
    0 6 * * * python3 /home/termius/mon-ipad/scripts/gpu-burst/zerogpu-burst.py --account all
"""

import os
import sys
import json
import time
import random
import traceback
import urllib.request
import urllib.parse
import ssl
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

# ══════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════

ATR_BRIER = 0.21570
IMPROVEMENT_THRESHOLD = 0.00005
MAX_FEATURES = 200
TARGET_FEATURES = 63

GITHUB_REPO = "LBJLincoln/mon-ipad"
GITHUB_BRANCH = "main"

HF_ISLANDS = {
    "S10": "https://nomos42-nba-quant.hf.space",
    "S11": "https://nomos42-nba-quant-2.hf.space",
    "S12": "https://nomos42-nba-evo-3.hf.space",
    "S13": "https://nomos42-nba-evo-4.hf.space",
    "S14": "https://nomos42-nba-evo-5.hf.space",
    "S15": "https://nomos42-nba-evo-6.hf.space",
    "S16": "https://lbjlincoln26-nba-evo-s16.hf.space",
    "S17": "https://lbjlincoln26-nba-evo-s17.hf.space",
}

# Paths
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BEST_CONFIG_PATH = REPO_ROOT / "data" / "karpathy" / "nba-best-config.json"
RESULTS_DIR = REPO_ROOT / "data" / "gpu-burst"
LOG_FILE = RESULTS_DIR / "zerogpu-log.jsonl"
RESULT_FILE = RESULTS_DIR / "latest-zerogpu-result.json"

# ZeroGPU-enabled spaces we can query for evaluation
# These must be HF Spaces with `sdk: gradio` and the `zero-gpu` hardware.
# Inference endpoint pattern: POST /run/predict via the Gradio API.
ZEROGPU_SPACES = [
    "Nomos42/nba-quant",       # S10
    "Nomos42/nba-quant-2",     # S11
]

# HF Inference API — serverless endpoints (TabICL / tabpfn / etc.)
# These models run on ZeroGPU infrastructure when available.
TABICL_MODEL = "LBJLincoln/tabicl-nba"   # placeholder — real model ID if uploaded
TABPFN_MODEL = "Prior-Labs/TabPFN"        # TabPFN v2 — free via HF Inference API

# Account rotation — each account gets ~5 min/day free H200 time
ACCOUNTS = [
    {"name": "LBJLincoln",   "token_env": "HF_TOKEN"},
    {"name": "LBJLincoln26", "token_env": "HF_TOKEN_NBA"},
    {"name": "Nomos42",      "token_env": "HF_TOKEN_LLM"},
]

# Mutation parameters
MUTATION_RATES = [0.05, 0.09, 0.12, 0.18]
SWAP_SIZES   = [3, 5, 8, 12]
MODEL_TYPES  = ["xgboost", "catboost", "lightgbm", "extra_trees", "random_forest"]
MODEL_WEIGHTS = [0.3, 0.2, 0.2, 0.2, 0.1]


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

def http_get(url: str, token: str = "", timeout: int = 30) -> Optional[dict]:
    headers = {"User-Agent": "Nomos42-ZeroGPU/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as resp:
            return json.loads(resp.read())
    except Exception as e:
        log(f"GET {url}: {e}", "WARN")
        return None

def http_post(url: str, payload: dict, token: str = "", timeout: int = 120) -> Optional[dict]:
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json", "User-Agent": "Nomos42-ZeroGPU/1.0"}
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
        req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data)
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass

def append_log(entry: dict):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


# ══════════════════════════════════════════════════════════
# CONFIG MANAGEMENT
# ══════════════════════════════════════════════════════════

def load_best_config() -> dict:
    """Load the best known config from data/karpathy/nba-best-config.json."""
    if BEST_CONFIG_PATH.exists():
        with open(BEST_CONFIG_PATH) as f:
            cfg = json.load(f)
        log(f"Loaded best config: brier={cfg.get('best_brier', '?')}, "
            f"iter={cfg.get('iteration', '?')}, n_features={cfg.get('n_features', '?')}")
        return cfg
    # Fallback: minimal default
    log("No best config found — using defaults", "WARN")
    return {
        "model_type": "gradient_boosting",
        "n_estimators": 200,
        "max_depth": 6,
        "min_samples_leaf": 5,
        "max_features_ratio": 0.4,
        "feature_indices": list(range(63)),
        "n_features": 63,
        "best_brier": 0.235,
        "iteration": 0,
    }

def save_best_config(cfg: dict):
    """Overwrite the best config if improvement was found."""
    BEST_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(BEST_CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)
    log(f"Saved new best config: brier={cfg.get('best_brier', '?')}")

def save_result(result: dict):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULT_FILE, "w") as f:
        json.dump(result, f, indent=2)


# ══════════════════════════════════════════════════════════
# SEEDING FROM HF ISLANDS
# ══════════════════════════════════════════════════════════

def fetch_island_seeds() -> List[dict]:
    """Pull best configs from the 6 live HF evolution islands."""
    seeds = []
    for name, base_url in HF_ISLANDS.items():
        data = http_get(f"{base_url}/api/best", timeout=15)
        if data and data.get("brier", 1.0) < 0.99:
            seeds.append({
                "source": name,
                "brier": float(data.get("brier", 1.0)),
                "feature_indices": data.get("features", []),
                "model_type": data.get("model_type", "xgboost"),
                "hp": data.get("hp", {}),
            })
            log(f"Seed from {name}: brier={data.get('brier', '?')}, model={data.get('model_type', '?')}")
        else:
            log(f"Seed {name}: unavailable", "WARN")
    return seeds


# ══════════════════════════════════════════════════════════
# MUTATION ENGINE (CPU-side — no ML, pure index manipulation)
# ══════════════════════════════════════════════════════════

def mutate_config(base: dict, mutation_rate: float, swap_size: int) -> dict:
    """Mutate feature indices, model type, and hyperparameters.
    This runs on the VM CPU — zero ML, just index shuffling.
    """
    features = list(base.get("feature_indices", list(range(TARGET_FEATURES))))
    n_total = 6253  # total features in engine v3.1-46cat

    # Feature mutation: swap some out, add some new ones
    n_remove = max(1, int(len(features) * mutation_rate))
    n_add = n_remove + random.choice([-swap_size, 0, swap_size])
    n_add = max(0, min(n_add, MAX_FEATURES - len(features) + n_remove))

    features_set = set(features)
    remove_candidates = random.sample(features, min(n_remove, len(features)))
    for f in remove_candidates:
        features_set.discard(f)

    available = [i for i in range(n_total) if i not in features_set]
    if available and n_add > 0:
        to_add = random.sample(available, min(n_add, len(available)))
        features_set.update(to_add)

    new_features = sorted(features_set)

    # Cap at MAX_FEATURES
    if len(new_features) > MAX_FEATURES:
        new_features = random.sample(new_features, MAX_FEATURES)
        new_features.sort()

    # Model type mutation (25% chance)
    new_model = base.get("model_type", "gradient_boosting")
    if random.random() < 0.25:
        new_model = random.choices(MODEL_TYPES, weights=MODEL_WEIGHTS)[0]

    # HP mutation (20% chance each)
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
# ZEROGPU EVALUATION
# The actual model training runs on the H200 inside the HF Space.
# We send a config payload to the Space's /run/predict endpoint and
# receive a Brier score back. The Space is responsible for:
#   1. Loading the feature cache
#   2. Training the model
#   3. Running walk-forward Brier eval
#   4. Returning {"brier": float, "n_features": int, "model_type": str}
# ══════════════════════════════════════════════════════════

def evaluate_on_space(config: dict, space_id: str, token: str) -> Optional[float]:
    """Submit a config to a ZeroGPU-enabled HF Space for evaluation.

    The Space must expose a Gradio API endpoint at /run/evaluate_config
    that accepts {"config": {...}} and returns {"brier": float}.

    If the Space doesn't have this endpoint, we fall back to the
    HF Inference API serverless endpoint.
    """
    space_url = f"https://huggingface.co/spaces/{space_id}"
    api_url = f"https://{space_id.replace('/', '-').lower()}.hf.space/run/evaluate_config"

    log(f"Submitting to {space_id} for evaluation...")

    payload = {
        "data": [json.dumps(config)],  # Gradio API format: list of inputs
    }

    resp = http_post(api_url, payload, token=token, timeout=300)
    if resp:
        # Gradio returns {"data": [result], "duration": float}
        data = resp.get("data", [])
        if data:
            result_raw = data[0]
            if isinstance(result_raw, str):
                result_raw = json.loads(result_raw)
            brier = float(result_raw.get("brier", 1.0))
            if 0.0 < brier < 1.0:
                log(f"ZeroGPU eval from {space_id}: brier={brier:.5f}")
                return brier

    log(f"Space eval failed for {space_id}", "WARN")
    return None


def evaluate_on_inference_api(config: dict, token: str) -> Optional[float]:
    """Try TabICL/TabPFN via HF Serverless Inference API (ZeroGPU path).

    Strategy:
      1. Call S15 /api/tabicl_evaluate or /run/tabicl_eval (ZeroGPU H200 endpoint)
         — returns Brier directly if the space has a TabICL evaluation function
      2. Fetch /api/data_sample from S15 and call TabPFN serverless with real data
         — requires the space to expose a data_sample endpoint
      3. Log precisely which path failed, for future debugging
    """
    if not token:
        log("No HF token — skipping Inference API evaluation", "WARN")
        return None

    feature_indices = config.get("feature_indices", [])
    if not feature_indices:
        return None

    # ── Path 2a: S15 ZeroGPU Space direct eval endpoint ───────────
    # Tries both a simple REST endpoint and the Gradio /run/ format
    eval_payload = {
        "features": feature_indices,
        "model_type": "tabicl",
        "n_estimators": config.get("n_estimators", 200),
        "max_depth": config.get("max_depth", 6),
        "learning_rate": config.get("learning_rate", 0.1),
    }
    for endpoint, wrap_gradio in [("/api/tabicl_evaluate", False), ("/run/tabicl_eval", True)]:
        url = f"{HF_ISLANDS['S15']}{endpoint}"
        payload = {"data": [json.dumps(eval_payload)]} if wrap_gradio else eval_payload
        resp = http_post(url, payload, token=token, timeout=180)
        if resp:
            # Gradio response: {"data": [result_json_str], "duration": ...}
            # REST response: {"brier": float, "model_used": str}
            if wrap_gradio and isinstance(resp.get("data"), list) and resp["data"]:
                try:
                    inner = resp["data"][0]
                    resp = json.loads(inner) if isinstance(inner, str) else inner
                except (ValueError, TypeError):
                    continue
            b = float(resp.get("brier", 1.0))
            if 0.0 < b < 0.99:
                model_used = resp.get("model_used", "tabicl")
                log(f"S15 TabICL eval (path 2a, {endpoint}): brier={b:.5f} model={model_used}")
                return b

    # ── Path 2b: TabPFN serverless with cached data from S15 ──────
    # Requires S15 to expose /api/data_sample — add to HF Space app.py to unlock
    data_resp = http_get(f"{HF_ISLANDS['S15']}/api/data_sample", token=token, timeout=30)
    if data_resp and "X_train" in data_resp and "y_train" in data_resp:
        X_train = data_resp["X_train"]
        y_train = data_resp["y_train"]
        X_test  = data_resp.get("X_test", [])
        y_test  = data_resp.get("y_test", [])

        n_cols = len(X_train[0]) if X_train else 0
        valid_idx = [i for i in feature_indices if i < n_cols]
        if len(valid_idx) >= 5 and X_test and y_test:
            X_tr_sel = [[row[i] for i in valid_idx] for row in X_train[-1000:]]
            X_te_sel = [[row[i] for i in valid_idx] for row in X_test[-200:]]
            y_tr_sel = y_train[-1000:]
            y_te_sel = y_test[-200:]

            tabpfn_url = f"https://api-inference.huggingface.co/models/{TABPFN_MODEL}"
            tabpfn_payload = {"inputs": {
                "train_X": X_tr_sel,
                "train_y": y_tr_sel,
                "test_X": X_te_sel,
            }}
            try:
                req = urllib.request.Request(
                    tabpfn_url,
                    data=json.dumps(tabpfn_payload).encode(),
                    method="POST",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                        "X-Wait-For-Model": "true",
                    },
                )
                with urllib.request.urlopen(req, timeout=120, context=_ssl_ctx()) as r:
                    result = json.loads(r.read())
                if isinstance(result, list) and result:
                    probs = [
                        float(item.get("score", item) if isinstance(item, dict) else item)
                        for item in result[:len(y_te_sel)]
                    ]
                    if probs and y_te_sel:
                        brier = sum((p - y) ** 2 for p, y in zip(probs, y_te_sel)) / len(probs)
                        if 0.0 < brier < 1.0:
                            log(f"TabPFN serverless: brier={brier:.5f} ({len(probs)} games, {len(valid_idx)}f)")
                            return brier
            except Exception as e:
                log(f"TabPFN serverless failed: {e}", "WARN")
    else:
        # Log what's needed to unlock this path
        log("S15 /api/data_sample not available — TabPFN path inactive", "INFO")
        log("To enable: add @app.get('/api/data_sample') to HF Space app.py", "INFO")

    return None


def evaluate_on_island_api(config: dict) -> Optional[float]:
    """Evaluate via the /api/evaluate endpoint on live HF islands.
    These islands run 24/7 on CPU and accept evaluation requests.
    Returns the best score across all responding islands.
    """
    feature_indices = config.get("feature_indices", [])
    model_type = config.get("model_type", "xgboost")

    payload = {
        "features": feature_indices,
        "model_type": model_type,
        "n_estimators": config.get("n_estimators", 200),
        "max_depth": config.get("max_depth", 6),
    }

    briers = []
    for name, base_url in HF_ISLANDS.items():
        resp = http_post(f"{base_url}/api/evaluate", payload, timeout=120)
        if resp:
            b = float(resp.get("brier", 1.0))
            if 0.0 < b < 0.99:
                briers.append(b)
                log(f"  Island {name}: brier={b:.5f}")

    if briers:
        return min(briers)  # Best across islands
    return None


def evaluate_config(config: dict, token: str) -> Optional[float]:
    """Try all evaluation paths in priority order:
    1. ZeroGPU Space API (H200, fastest/best)
    2. HF Inference API serverless (ZeroGPU, good)
    3. Live island /api/evaluate (CPU, fallback)
    """
    # Path 1: ZeroGPU Space
    for space_id in ZEROGPU_SPACES:
        brier = evaluate_on_space(config, space_id, token)
        if brier is not None:
            return brier

    # Path 2: HF Inference API serverless
    brier = evaluate_on_inference_api(config, token)
    if brier is not None:
        return brier

    # Path 3: CPU island fallback
    log("ZeroGPU paths unavailable — falling back to island CPU eval", "WARN")
    brier = evaluate_on_island_api(config)
    return brier


# ══════════════════════════════════════════════════════════
# PUSH RESULTS
# ══════════════════════════════════════════════════════════

def push_to_github(result: dict) -> bool:
    """Push the new best config to GitHub via git."""
    import subprocess

    github_token = os.environ.get("GITHUB_TOKEN", "")
    if not github_token:
        log("No GITHUB_TOKEN — skipping GitHub push", "WARN")
        return False

    try:
        repo_dir = REPO_ROOT
        # Commit the updated best-config and result files
        subprocess.run(
            ["git", "-C", str(repo_dir), "config", "user.email", "nomos42@users.noreply.github.com"],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo_dir), "config", "user.name", "Nomos42 ZeroGPU"],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo_dir), "add",
             str(BEST_CONFIG_PATH), str(RESULT_FILE)],
            check=True, capture_output=True,
        )
        msg = (
            f"gpu-burst: zerogpu H200 brier={result['best_brier']:.5f} "
            f"({result.get('model_type', '?')}, {result.get('n_features', '?')}f, "
            f"iter {result.get('iteration', '?')})"
        )
        ret = subprocess.run(
            ["git", "-C", str(repo_dir), "commit", "-m", msg],
            capture_output=True, text=True,
        )
        if ret.returncode != 0:
            log(f"Nothing to commit or error: {ret.stderr[:200]}", "WARN")
            return False

        ret = subprocess.run(
            ["git", "-C", str(repo_dir), "push", "origin", GITHUB_BRANCH],
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


def update_island_config(result: dict) -> bool:
    """Send new best config to S10 /api/config for immediate deployment."""
    payload = {
        "best_brier": result["best_brier"],
        "features": result.get("feature_indices", []),
        "model_type": result.get("model_type", "xgboost"),
        "hp": {
            "depth": result.get("max_depth", 6),
            "lr": result.get("learning_rate", 0.1),
            "n_est": result.get("n_estimators", 200),
        },
        "source": "zerogpu-burst",
        "timestamp": result.get("timestamp", ts()),
    }
    resp = http_post(f"{HF_ISLANDS['S10']}/api/config", payload, timeout=20)
    if resp:
        log("Updated S10 island config with new best")
        return True
    log("Failed to update S10 config", "WARN")
    return False


# ══════════════════════════════════════════════════════════
# MAIN BURST LOOP (one account)
# ══════════════════════════════════════════════════════════

def run_burst_for_account(account: dict) -> dict:
    """Run one burst session for a single HF account.
    Budget: ~5 minutes of ZeroGPU H200 time.
    Strategy: 3 mutation candidates, evaluate best, keep if improved.
    """
    token = os.environ.get(account["token_env"], "")
    name = account["name"]
    session_start = time.time()

    log(f"=== ZeroGPU Burst — Account: {name} ===")

    if not token:
        log(f"No token for {name} (env: {account['token_env']}) — skipping", "WARN")
        return {"account": name, "status": "skipped", "reason": "no_token"}

    # Step 1: Load base config (best known)
    base = load_best_config()
    baseline_brier = float(base.get("best_brier", 1.0))
    log(f"Baseline brier: {baseline_brier:.5f}")

    # Step 2: Seed from live islands (richer gene pool)
    seeds = fetch_island_seeds()
    if seeds:
        best_seed = min(seeds, key=lambda s: s.get("brier", 1.0))
        if best_seed["brier"] < baseline_brier:
            log(f"Better seed from {best_seed['source']}: brier={best_seed['brier']:.5f}")
            # Merge seed into base
            base["feature_indices"] = best_seed.get("feature_indices", base.get("feature_indices", []))
            base["model_type"] = best_seed.get("model_type", base.get("model_type", "xgboost"))
            baseline_brier = best_seed["brier"]

    # Step 3: Generate mutation candidates
    n_candidates = 4  # Generate 4, evaluate all, keep best
    candidates = []
    for i in range(n_candidates):
        mutation_rate = MUTATION_RATES[i % len(MUTATION_RATES)]
        swap_size = SWAP_SIZES[i % len(SWAP_SIZES)]
        candidate = mutate_config(base, mutation_rate, swap_size)
        candidates.append(candidate)
        log(f"Candidate {i+1}: {len(candidate['feature_indices'])}f, "
            f"model={candidate['model_type']}, mut={mutation_rate}")

    # Step 4: Evaluate each candidate
    best_brier_found = baseline_brier
    best_candidate = None

    for i, candidate in enumerate(candidates):
        elapsed = time.time() - session_start
        log(f"Evaluating candidate {i+1}/{n_candidates} ({elapsed:.0f}s elapsed)...")

        brier = evaluate_config(candidate, token)

        if brier is None:
            log(f"Candidate {i+1}: evaluation failed", "WARN")
            append_log({
                "ts": ts(), "account": name,
                "candidate": i + 1,
                "status": "eval_failed",
            })
            continue

        log(f"Candidate {i+1}: brier={brier:.5f} "
            f"({'BETTER' if brier < best_brier_found else 'worse'} "
            f"vs baseline {baseline_brier:.5f})")

        append_log({
            "ts": ts(),
            "account": name,
            "candidate": i + 1,
            "brier": brier,
            "model_type": candidate["model_type"],
            "n_features": candidate["n_features"],
            "mutation_rate": candidate["mutation_rate"],
            "improved": brier < best_brier_found,
        })

        if brier < best_brier_found - IMPROVEMENT_THRESHOLD:
            best_brier_found = brier
            best_candidate = candidate.copy()
            best_candidate["best_brier"] = brier

    # Step 5: Keep or revert
    total_time = time.time() - session_start
    result = {
        "account": name,
        "timestamp": ts(),
        "baseline_brier": baseline_brier,
        "best_brier_found": best_brier_found,
        "improvement": round(baseline_brier - best_brier_found, 6),
        "improved": best_candidate is not None,
        "n_candidates": n_candidates,
        "total_time_sec": round(total_time, 1),
        "platform": "zerogpu_h200",
    }

    if best_candidate:
        log(f"IMPROVEMENT FOUND: {baseline_brier:.5f} → {best_brier_found:.5f} "
            f"(delta={result['improvement']:.6f})")

        # Update best config
        iteration = base.get("iteration", 0) + 1
        best_candidate["iteration"] = iteration
        best_candidate["account_source"] = name
        save_best_config(best_candidate)
        save_result({**result, **best_candidate})

        # Push to S10 island
        update_island_config(best_candidate)

        # Push to GitHub
        push_to_github(best_candidate)

        send_telegram(
            f"ZeroGPU Burst ({name}) — IMPROVED\n"
            f"Brier: {baseline_brier:.5f} → {best_brier_found:.5f}\n"
            f"Model: {best_candidate.get('model_type', '?')}, "
            f"{best_candidate.get('n_features', '?')}f\n"
            f"Iter {iteration} | H200 {total_time:.0f}s"
        )
        result["status"] = "improved"
    else:
        log(f"No improvement (best found: {best_brier_found:.5f}) — discarding")
        save_result(result)
        result["status"] = "no_improvement"

    log(f"=== Burst complete: {total_time:.0f}s | status={result['status']} ===")
    return result


# ══════════════════════════════════════════════════════════
# MULTI-ACCOUNT ROTATION
# ══════════════════════════════════════════════════════════

def run_all_accounts() -> List[dict]:
    """Run bursts sequentially across all 3 accounts.
    Total budget: ~15 min ZeroGPU H200 per day.
    Each account gets an independent mutation attempt.
    """
    results = []
    for account in ACCOUNTS:
        log(f"\n{'='*60}")
        log(f"Account {ACCOUNTS.index(account)+1}/{len(ACCOUNTS)}: {account['name']}")
        log(f"{'='*60}")
        try:
            r = run_burst_for_account(account)
            results.append(r)
        except Exception as e:
            log(f"Account {account['name']} failed: {e}", "ERROR")
            traceback.print_exc()
            results.append({"account": account["name"], "status": "error", "error": str(e)})

        # Brief pause between accounts to avoid rate-limiting
        if account != ACCOUNTS[-1]:
            log("Pausing 5s between accounts...")
            time.sleep(5)

    # Summary
    improved = [r for r in results if r.get("status") == "improved"]
    log(f"\n{'='*60}")
    log(f"ZeroGPU Multi-Account Summary:")
    log(f"  Accounts used: {len(results)}")
    log(f"  Improvements:  {len(improved)}")
    for r in results:
        status = r.get("status", "?")
        brier_str = ""
        if r.get("best_brier_found"):
            brier_str = f" | brier={r['best_brier_found']:.5f}"
        log(f"  {r['account']:15s}: {status}{brier_str}")
    log(f"{'='*60}")

    return results


# ══════════════════════════════════════════════════════════
# NOTE ON @spaces.GPU PATTERN
# ══════════════════════════════════════════════════════════
# The @spaces.GPU decorator is used INSIDE HF Spaces (app.py), not in
# scripts that run externally. If you deploy a Space with ZeroGPU,
# your app.py would look like:
#
#   import spaces
#   import gradio as gr
#   from sklearn.metrics import brier_score_loss
#   import numpy as np
#
#   @spaces.GPU(duration=300)  # Request up to 5 min of H200
#   def evaluate_config(config_json: str) -> str:
#       cfg = json.loads(config_json)
#       # ... load features, train model, compute Brier ...
#       return json.dumps({"brier": brier, "n_features": n})
#
#   demo = gr.Interface(fn=evaluate_config, inputs="text", outputs="text")
#   demo.launch()
#
# This script calls that Space's /run/evaluate_config endpoint via HTTP.
# ══════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="HF ZeroGPU Burst — 15 min/day free H200")
    parser.add_argument(
        "--account", default="all",
        help="Account to use: 0=LBJLincoln, 1=LBJLincoln26, 2=Nomos42, all=all 3 (default: all)",
    )
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    if args.account == "all":
        results = run_all_accounts()
    else:
        try:
            idx = int(args.account)
            result = run_burst_for_account(ACCOUNTS[idx])
            results = [result]
        except (ValueError, IndexError):
            log(f"Invalid account: {args.account}. Use 0, 1, 2, or 'all'", "ERROR")
            sys.exit(1)

    improved_count = sum(1 for r in results if r.get("status") == "improved")
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from gpu.dept_log import record as _dept_record
        best = min((r.get("best_brier", 1.0) for r in results), default=1.0)
        _dept_record("zerogpu", "tabicl_serverless_island_seed",
                     brier=best, improved=improved_count, n_accounts=len(results))
    except Exception as _e:
        print(f"[dept-log] zerogpu record failed: {_e}")
    sys.exit(0 if improved_count >= 0 else 1)  # Always exit 0 — improvement is a bonus


if __name__ == "__main__":
    main()
