#!/usr/bin/env python3
"""
NBA Quant AI -- Kaggle P100 GPU Burst (30 min max)
===================================================
Karpathy autoresearch pattern: seed from 6 HF islands -> evolve -> measure -> push if better.

Run on Kaggle:
    1. Create new notebook, enable GPU (P100)
    2. Add secrets: HF_TOKEN, GITHUB_TOKEN, DATABASE_URL (optional)
    3. Paste this file as a single cell or upload as utility script
    4. Run

Kaggle-specific:
    - Working directory: /kaggle/working/
    - Output directory: /kaggle/working/ (persists after session)
    - P100 GPU with 16GB VRAM
    - 9h session limit (this burst uses 30 min)
    - Internet must be enabled in notebook settings

Target: Beat ATR 0.21570 (Colab TabICL, 110f, iter 15)
"""

import os
import sys
import json
import time
import gc
import random
import traceback
import subprocess
import ssl
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any

import numpy as np

# ══════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════

MAX_DURATION_SECONDS = 1800  # 30 minutes burst
METRIC = "brier"
IMPROVEMENT_THRESHOLD = 0.00005
ATR_BRIER = 0.21570

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

# Evolution parameters
POPULATION_SIZE = 30
ITERATION_BUDGET_SEC = 300
MUTATION_RATE = 0.09
CROSSOVER_RATE = 0.80
TARGET_FEATURES = 63
MAX_FEATURES = 200
SUBSAMPLE_GAMES = 6000

MODEL_TYPES = ["xgboost", "xgboost_brier", "catboost", "lightgbm", "extra_trees", "random_forest"]
MODEL_WEIGHTS = [0.25, 0.20, 0.15, 0.10, 0.20, 0.10]

HP_RANGES = {
    "depth": (4, 10),
    "lr": (0.01, 0.3),
    "n_est": (100, 500),
}

# Kaggle-specific paths
WORK = Path("/kaggle/working")
REPO_DIR = WORK / "nba-quant-space"
CACHE_DIR = WORK / "nba-burst-cache"
FEATURE_CACHE = CACHE_DIR / "features_cache.npz"
STATE_FILE = CACHE_DIR / "burst_state.json"
RESULTS_FILE = CACHE_DIR / "burst_result.json"
LOG_FILE = CACHE_DIR / "burst_log.jsonl"

# Kaggle secrets (populated automatically from notebook settings)
HF_TOKEN = ""
GITHUB_TOKEN = ""
DATABASE_URL = ""

try:
    from kaggle_secrets import UserSecretsClient
    _secrets = UserSecretsClient()
    HF_TOKEN = _secrets.get_secret("HF_TOKEN") or ""
    GITHUB_TOKEN = _secrets.get_secret("GITHUB_TOKEN") or ""
    DATABASE_URL = _secrets.get_secret("DATABASE_URL") or ""
except Exception:
    HF_TOKEN = os.environ.get("HF_TOKEN", "")
    GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
    DATABASE_URL = os.environ.get("DATABASE_URL", "")


# ══════════════════════════════════════════════════════════
# SETUP
# ══════════════════════════════════════════════════════════

def setup():
    """Install deps and clone feature engine from HF Space."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    print("[SETUP] Installing GPU ML dependencies...")
    os.system("pip install -q xgboost lightgbm catboost psycopg2-binary 2>/dev/null")

    if REPO_DIR.exists():
        print("[SETUP] Repo exists, pulling latest...")
        subprocess.run(["git", "-C", str(REPO_DIR), "pull", "--ff-only"], capture_output=True)
    else:
        print("[SETUP] Cloning feature engine from HF Space...")
        clone_url = f"https://user:{HF_TOKEN}@huggingface.co/spaces/Nomos42/nba-quant"
        ret = subprocess.run(
            ["git", "clone", "--depth", "1", clone_url, str(REPO_DIR)],
            capture_output=True, text=True,
        )
        if ret.returncode != 0:
            print(f"[SETUP] Primary clone failed: {ret.stderr[:200]}")
            print("[SETUP] Trying S11...")
            clone_url = f"https://user:{HF_TOKEN}@huggingface.co/spaces/Nomos42/nba-quant-2"
            subprocess.run(
                ["git", "clone", "--depth", "1", clone_url, str(REPO_DIR)],
                capture_output=True, text=True, check=True,
            )

    sys.path.insert(0, str(REPO_DIR))
    print("[SETUP] Done.")


def build_features():
    """Build or load cached feature matrix."""
    if FEATURE_CACHE.exists():
        print("[FEATURES] Loading cached features...")
        data = np.load(str(FEATURE_CACHE), allow_pickle=True)
        X, y, feature_names = data["X"], data["y"], list(data["feature_names"])
        print(f"[FEATURES] Loaded: {X.shape}")
        return X, y, feature_names

    print("[FEATURES] Building features from scratch...")
    t0 = time.time()

    try:
        from features.engine import NBAFeatureEngine

        games = []
        for data_dir in [REPO_DIR / "data" / "historical"]:
            if data_dir.exists():
                for f in sorted(data_dir.glob("games-*.json")):
                    raw = json.loads(f.read_text())
                    if isinstance(raw, list):
                        games.extend(raw)
                    elif isinstance(raw, dict) and "games" in raw:
                        games.extend(raw["games"])
                if games:
                    print(f"[FEATURES] Loaded {len(games)} games from local JSON")

        if not games and DATABASE_URL:
            print("[FEATURES] Loading from Supabase...")
            import psycopg2
            conn = psycopg2.connect(DATABASE_URL, connect_timeout=30, options="-c search_path=public")
            cur = conn.cursor()
            cur.execute("SELECT game_data FROM nba_games ORDER BY game_date LIMIT 15000")
            for row in cur.fetchall():
                if row[0]:
                    games.append(row[0] if isinstance(row[0], dict) else json.loads(row[0]))
            cur.close()
            conn.close()
            print(f"[FEATURES] Loaded {len(games)} games from Supabase")

        if not games:
            raise ValueError("No game data. Set DATABASE_URL in Kaggle Secrets.")

        games.sort(key=lambda g: g.get("game_date", g.get("date", "")))
        engine = NBAFeatureEngine()
        X, y, feature_names = engine.build(games)
        X = np.nan_to_num(np.array(X, dtype=np.float64))
        y = np.array(y, dtype=np.int32)

        np.savez_compressed(str(FEATURE_CACHE), X=X, y=y, feature_names=np.array(feature_names))
        print(f"[FEATURES] Built & cached: {X.shape} in {time.time()-t0:.0f}s")
        return X, y, feature_names

    except Exception as e:
        print(f"[FEATURES] Build failed: {e}")
        traceback.print_exc()
        raise


# ══════════════════════════════════════════════════════════
# MODEL FACTORY + EVALUATION
# ══════════════════════════════════════════════════════════

def make_model(model_type: str, hp: Dict[str, Any]):
    """Create GPU-accelerated model. P100 supports CUDA for XGBoost/CatBoost/LightGBM."""
    import xgboost as xgb
    import lightgbm as lgbm
    from catboost import CatBoostClassifier
    from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier

    if model_type == "xgboost":
        return xgb.XGBClassifier(
            max_depth=hp.get("depth", 6), learning_rate=hp.get("lr", 0.1),
            n_estimators=hp.get("n_est", 200), random_state=42,
            eval_metric="logloss", verbosity=0,
            tree_method="hist", device="cuda",
        )
    elif model_type == "xgboost_brier":
        def brier_obj(y_true, y_pred):
            grad = 2 * (y_pred - y_true)
            hess = np.full_like(grad, 2.0)
            return grad, hess
        return xgb.XGBClassifier(
            max_depth=hp.get("depth", 6), learning_rate=hp.get("lr", 0.1),
            n_estimators=hp.get("n_est", 200), random_state=42,
            objective=brier_obj, verbosity=0,
            tree_method="hist", device="cuda",
        )
    elif model_type == "lightgbm":
        return lgbm.LGBMClassifier(
            max_depth=hp.get("depth", 6), learning_rate=hp.get("lr", 0.1),
            n_estimators=hp.get("n_est", 200), random_state=42,
            verbose=-1, device="gpu",
        )
    elif model_type == "catboost":
        return CatBoostClassifier(
            depth=min(hp.get("depth", 6), 10), learning_rate=hp.get("lr", 0.1),
            iterations=hp.get("n_est", 200), random_state=42,
            verbose=0, task_type="GPU",
        )
    elif model_type == "extra_trees":
        return ExtraTreesClassifier(
            n_estimators=hp.get("n_est", 200), max_depth=hp.get("depth", None),
            random_state=42, n_jobs=-1,
        )
    elif model_type == "random_forest":
        return RandomForestClassifier(
            n_estimators=hp.get("n_est", 200), max_depth=hp.get("depth", None),
            random_state=42, n_jobs=-1,
        )
    else:
        return xgb.XGBClassifier(verbosity=0, random_state=42, device="cuda")


def evaluate(X_data, y_data, features_mask, model_type, hp, timeout=120):
    """Walk-forward Brier evaluation. Returns 1.0 on failure. IMMUTABLE."""
    from sklearn.model_selection import TimeSeriesSplit
    from sklearn.metrics import brier_score_loss

    try:
        selected = np.where(features_mask)[0]
        if len(selected) < 5 or len(selected) > MAX_FEATURES:
            return 1.0

        X_sub = X_data[:, selected]
        tscv = TimeSeriesSplit(n_splits=2)
        briers = []

        for train_idx, test_idx in tscv.split(X_sub):
            model = make_model(model_type, hp)
            t0 = time.time()
            model.fit(X_sub[train_idx], y_data[train_idx])
            if time.time() - t0 > timeout:
                return 1.0

            probs = model.predict_proba(X_sub[test_idx])
            probs = probs[:, 1] if probs.shape[1] == 2 else probs[:, 0]
            probs = np.clip(probs, 0.001, 0.999)
            briers.append(brier_score_loss(y_data[test_idx], probs))

        return float(np.mean(briers))
    except Exception:
        return 1.0


# ══════════════════════════════════════════════════════════
# GENETIC OPERATORS
# ══════════════════════════════════════════════════════════

def random_individual(n_features: int) -> Dict[str, Any]:
    mask = np.zeros(n_features, dtype=bool)
    target = min(TARGET_FEATURES, n_features)
    selected = np.random.choice(n_features, size=target, replace=False)
    mask[selected] = True
    model_type = np.random.choice(MODEL_TYPES, p=MODEL_WEIGHTS)
    hp = {
        "depth": random.randint(*HP_RANGES["depth"]),
        "lr": round(random.uniform(*HP_RANGES["lr"]), 3),
        "n_est": random.randint(*HP_RANGES["n_est"]),
    }
    return {"mask": mask, "model_type": model_type, "hp": hp, "brier": 1.0}


def mutate(ind: Dict[str, Any], mutation_rate: float) -> Dict[str, Any]:
    new = {
        "mask": ind["mask"].copy(),
        "model_type": ind["model_type"],
        "hp": dict(ind["hp"]),
        "brier": 1.0,
    }
    n_flip = max(1, int(mutation_rate * np.sum(new["mask"])))
    for _ in range(n_flip):
        idx = random.randint(0, len(new["mask"]) - 1)
        new["mask"][idx] = not new["mask"][idx]

    n_selected = int(np.sum(new["mask"]))
    while n_selected > min(TARGET_FEATURES * 1.5, MAX_FEATURES):
        on_indices = np.where(new["mask"])[0]
        new["mask"][np.random.choice(on_indices)] = False
        n_selected -= 1
    while n_selected < max(TARGET_FEATURES * 0.5, 10):
        off_indices = np.where(~new["mask"])[0]
        if len(off_indices) == 0:
            break
        new["mask"][np.random.choice(off_indices)] = True
        n_selected += 1

    if random.random() < 0.2:
        new["hp"]["depth"] = max(4, min(10, new["hp"]["depth"] + random.choice([-1, 0, 1])))
        new["hp"]["lr"] = round(max(0.01, min(0.3, new["hp"]["lr"] * random.uniform(0.8, 1.2))), 3)
        new["hp"]["n_est"] = max(100, min(500, new["hp"]["n_est"] + random.choice([-50, 0, 50])))

    if random.random() < 0.25:
        new["model_type"] = np.random.choice(MODEL_TYPES, p=MODEL_WEIGHTS)

    return new


def crossover(p1: Dict[str, Any], p2: Dict[str, Any]) -> Dict[str, Any]:
    child = {"mask": np.zeros_like(p1["mask"]), "brier": 1.0}
    for i in range(len(child["mask"])):
        child["mask"][i] = p1["mask"][i] if random.random() < CROSSOVER_RATE else p2["mask"][i]
    child["model_type"] = p1["model_type"] if random.random() < 0.5 else p2["model_type"]
    child["hp"] = dict(p1["hp"] if random.random() < 0.5 else p2["hp"])
    return child


# ══════════════════════════════════════════════════════════
# HF ISLAND SEEDING + RESULT PUSHING
# ══════════════════════════════════════════════════════════

def fetch_island_seeds(n_features: int) -> List[Dict[str, Any]]:
    """Seed population from live HF Space evolution islands."""
    seeds = []
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    for name, base_url in HF_ISLANDS.items():
        try:
            url = f"{base_url}/api/best"
            req = urllib.request.Request(url, headers={"User-Agent": "Nomos42-KaggleBurst/1.0"})
            with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                data = json.loads(resp.read())
                if data.get("brier", 1.0) < 0.99:
                    mask = np.zeros(n_features, dtype=bool)
                    for idx in data.get("features", []):
                        if 0 <= idx < n_features:
                            mask[idx] = True
                    if np.sum(mask) >= 5:
                        seeds.append({
                            "mask": mask,
                            "model_type": data.get("model_type", "xgboost"),
                            "hp": data.get("hp", {"depth": 6, "lr": 0.1, "n_est": 200}),
                            "brier": float(data.get("brier", 1.0)),
                        })
                        print(f"  [SEED] {name}: brier={data.get('brier', '?')}, "
                              f"model={data.get('model_type', '?')}")
        except Exception as e:
            print(f"  [SEED] {name}: failed ({e})")

    print(f"[SEED] Total seeds: {len(seeds)}")
    return seeds


def push_results(result: Dict[str, Any]) -> bool:
    """Push burst results to GitHub and save to Kaggle output."""
    # Always save to Kaggle output (persists after session ends)
    output_path = WORK / "burst_result.json"
    output_path.write_text(json.dumps(result, indent=2))
    print(f"[OUTPUT] Saved to {output_path}")

    if not GITHUB_TOKEN:
        print("[PUSH] No GITHUB_TOKEN -- skipping GitHub push")
        return False

    try:
        # Clone main repo for push (different from HF space clone)
        push_dir = WORK / "mon-ipad-push"
        if not push_dir.exists():
            clone_url = f"https://{GITHUB_TOKEN}@github.com/{GITHUB_REPO}.git"
            subprocess.run(
                ["git", "clone", "--depth", "1", clone_url, str(push_dir)],
                capture_output=True, text=True, timeout=60, check=True,
            )

        result_path = push_dir / "data" / "gpu-burst" / "latest-kaggle-result.json"
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps(result, indent=2))

        subprocess.run(
            ["git", "-C", str(push_dir), "config", "user.email", "nomos42@users.noreply.github.com"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(push_dir), "config", "user.name", "Nomos42 GPU Burst"],
            check=True,
        )
        subprocess.run(["git", "-C", str(push_dir), "add", str(result_path)], check=True)

        msg = (
            f"gpu-burst: kaggle P100 brier={result['best_brier']:.5f} "
            f"({result['model_type']}, {result['n_features']}f, "
            f"{result['iterations']} iters)"
        )
        ret = subprocess.run(
            ["git", "-C", str(push_dir), "commit", "-m", msg],
            capture_output=True, text=True,
        )
        if ret.returncode != 0:
            print(f"[PUSH] Nothing to commit: {ret.stderr[:200]}")
            return False

        ret = subprocess.run(
            ["git", "-C", str(push_dir), "push", "origin", GITHUB_BRANCH],
            capture_output=True, text=True, timeout=60,
        )
        if ret.returncode == 0:
            print(f"[PUSH] Pushed to GitHub: {msg}")
            return True
        else:
            print(f"[PUSH] Push failed: {ret.stderr[:200]}")
            return False

    except Exception as e:
        print(f"[PUSH] Failed: {e}")
        return False


def update_hf_space_config(result: Dict[str, Any], space_url: str) -> bool:
    """Update HF Space config via API."""
    try:
        payload = json.dumps({
            "best_brier": result["best_brier"],
            "features": result["features"],
            "model_type": result["model_type"],
            "hp": result["hp"],
            "source": "kaggle-burst",
            "timestamp": result["timestamp"],
        }).encode("utf-8")

        url = f"{space_url}/api/config"
        req = urllib.request.Request(
            url, data=payload, method="POST",
            headers={"Content-Type": "application/json", "User-Agent": "Nomos42-KaggleBurst/1.0"},
        )
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            if resp.status == 200:
                print(f"[HF] Updated {space_url}")
                return True
    except Exception as e:
        print(f"[HF] Config update failed: {e}")
    return False


def log_experiment(entry: Dict[str, Any]):
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def send_telegram_alert(message: str):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("ADMIN_TELEGRAM_ID", "")
    if not token or not chat_id:
        return
    try:
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": message}).encode("utf-8")
        req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data)
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


# ══════════════════════════════════════════════════════════
# MAIN BURST LOOP
# ══════════════════════════════════════════════════════════

def run_burst():
    """Main burst: evolve for MAX_DURATION_SECONDS then push results."""
    burst_start = time.time()

    # Step 1: Setup
    setup()
    X, y, feature_names = build_features()
    n_features = X.shape[1]

    if X.shape[0] > SUBSAMPLE_GAMES:
        X = X[-SUBSAMPLE_GAMES:]
        y = y[-SUBSAMPLE_GAMES:]
    print(f"[BURST] Data ready: {X.shape}")

    # Step 2: Seed population
    print("[BURST] Fetching seeds from HF islands...")
    seeds = fetch_island_seeds(n_features)

    population = seeds[:POPULATION_SIZE]
    while len(population) < POPULATION_SIZE:
        population.append(random_individual(n_features))

    best_ever = min(
        (ind["brier"] for ind in population if ind["brier"] < 1.0),
        default=1.0,
    )
    initial_best = best_ever
    mutation_rate = MUTATION_RATE
    iteration = 0
    stagnation = 0
    total_evals = 0

    elapsed_setup = time.time() - burst_start
    remaining = MAX_DURATION_SECONDS - elapsed_setup

    print(f"\n{'='*70}")
    print(f"  KAGGLE P100 GPU BURST -- NBA EVOLUTION")
    print(f"  Pop={POPULATION_SIZE} | Budget={ITERATION_BUDGET_SEC}s/iter")
    print(f"  ATR: {ATR_BRIER:.5f} | Seed best: {best_ever:.5f}")
    print(f"  Setup: {elapsed_setup:.0f}s | Remaining: {remaining:.0f}s")
    print(f"{'='*70}\n")

    send_telegram_alert(
        f"Kaggle P100 Burst Started\n"
        f"Seed best: {best_ever:.5f} | ATR: {ATR_BRIER}\n"
        f"Budget: {MAX_DURATION_SECONDS}s"
    )

    # Step 3: Evolution loop
    while time.time() - burst_start < MAX_DURATION_SECONDS:
        iteration += 1
        iter_start = time.time()
        n_evals = 0
        improved = False

        # Evaluate unevaluated
        for ind in population:
            if ind["brier"] >= 0.99:
                ind["brier"] = evaluate(X, y, ind["mask"], ind["model_type"], ind["hp"])
                n_evals += 1
                total_evals += 1
                if time.time() - iter_start > ITERATION_BUDGET_SEC:
                    break

        population.sort(key=lambda x: x["brier"])

        if population[0]["brier"] < best_ever - IMPROVEMENT_THRESHOLD:
            best_ever = population[0]["brier"]
            improved = True
            stagnation = 0
        else:
            stagnation += 1

        elite_size = max(2, POPULATION_SIZE // 5)
        elite = population[:elite_size]
        offspring = []

        while len(offspring) < POPULATION_SIZE - elite_size:
            if random.random() < CROSSOVER_RATE and len(elite) >= 2:
                p1, p2 = random.sample(elite, 2)
                child = crossover(p1, p2)
                child = mutate(child, mutation_rate)
            else:
                parent = random.choice(elite)
                child = mutate(parent, mutation_rate)
            offspring.append(child)

        population = elite + offspring

        # Adaptive mutation
        if stagnation >= 15:
            mutation_rate = min(0.20, mutation_rate * 1.3)
        elif improved:
            mutation_rate = max(0.06, mutation_rate * 0.95)

        # Diversity injection
        if iteration % 20 == 0:
            top_models = {}
            for ind in population[:10]:
                top_models[ind["model_type"]] = top_models.get(ind["model_type"], 0) + 1
            dominant = max(top_models.values()) if top_models else 0
            if dominant >= 7:
                for j in range(min(5, len(population) - elite_size)):
                    new_ind = random_individual(n_features)
                    new_ind["model_type"] = MODEL_TYPES[j % len(MODEL_TYPES)]
                    population[-(j + 1)] = new_ind

        # Log
        duration = time.time() - iter_start
        elapsed_total = time.time() - burst_start
        remaining = MAX_DURATION_SECONDS - elapsed_total
        best_nf = int(np.sum(population[0]["mask"]))
        tag = "*** NEW BEST ***" if improved else ""

        print(
            f"Iter {iteration}: best={best_ever:.5f} "
            f"({population[0]['model_type']}, {best_nf}f) | "
            f"{n_evals} evals {duration:.0f}s | "
            f"{remaining:.0f}s left {tag}"
        )

        log_experiment({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "iteration": iteration,
            "best_brier": best_ever,
            "n_evals": n_evals,
            "duration_sec": round(duration, 1),
            "improved": improved,
            "platform": "kaggle_p100",
        })

        gc.collect()

    # Step 4: Finalize
    total_time = time.time() - burst_start
    best_ind = population[0]
    best_features = [int(i) for i in np.where(best_ind["mask"])[0]]

    result = {
        "best_brier": best_ever,
        "initial_best": initial_best,
        "improvement": round(initial_best - best_ever, 6),
        "model_type": best_ind["model_type"],
        "hp": best_ind["hp"],
        "features": best_features,
        "n_features": len(best_features),
        "iterations": iteration,
        "total_evals": total_evals,
        "total_time_sec": round(total_time, 1),
        "platform": "kaggle_p100",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "atr_brier": ATR_BRIER,
        "beat_atr": best_ever < ATR_BRIER,
    }

    RESULTS_FILE.write_text(json.dumps(result, indent=2))

    print(f"\n{'='*70}")
    print(f"  BURST COMPLETE")
    print(f"  Iterations: {iteration} | Evals: {total_evals}")
    print(f"  Best Brier: {best_ever:.5f} ({best_ind['model_type']}, {len(best_features)}f)")
    print(f"  Improvement: {result['improvement']:.6f}")
    print(f"  Beat ATR ({ATR_BRIER}): {'YES' if result['beat_atr'] else 'NO'}")
    print(f"  Total time: {total_time:.0f}s")
    print(f"{'='*70}")

    if best_ever < initial_best - IMPROVEMENT_THRESHOLD:
        print("\n[RESULT] Improvement found -- pushing results...")
        push_results(result)
        update_hf_space_config(result, HF_ISLANDS["S10"])
        send_telegram_alert(
            f"Kaggle P100 Burst -- IMPROVED\n"
            f"Brier: {initial_best:.5f} -> {best_ever:.5f}\n"
            f"Model: {best_ind['model_type']}, {len(best_features)}f\n"
            f"Iters: {iteration}"
        )
    else:
        print("\n[RESULT] No improvement -- discarding.")
        send_telegram_alert(
            f"Kaggle P100 Burst -- No improvement\n"
            f"Best: {best_ever:.5f} (seed: {initial_best:.5f})\n"
            f"Iters: {iteration}"
        )

    return result


# ══════════════════════════════════════════════════════════
# RUN
# ══════════════════════════════════════════════════════════

if __name__ == "__main__":
    result = run_burst()
