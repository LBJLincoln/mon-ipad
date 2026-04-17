#!/usr/bin/env python3
"""
NBA / Political Alpha -- Lightning AI GPU Burst (10 min max)
=============================================================
Generic burst runner for Lightning AI T4/A10G GPUs.
Supports both NBA (Brier score) and Political Alpha (signal accuracy) modes.

Run on Lightning AI:
    1. Create new Studio (T4 or A10G GPU)
    2. Upload or clone this file
    3. Set env vars: HF_TOKEN, GITHUB_TOKEN, MODE=nba|political
    4. python lightning-burst.py

Lightning AI specifics:
    - Working dir: /teamspace/studios/this_studio/
    - Persistent storage: /teamspace/studios/this_studio/
    - GPU: T4 (free) or A10G (paid)
    - 22h session limit (this burst uses 10 min)
    - Pre-installed: Python 3.10, pip, git

10 min burst: fast validation of promising configs from HF islands.
Pattern: seed -> mutate single param -> measure -> keep/revert -> repeat.
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

MAX_DURATION_SECONDS = 600  # 10 minutes hard cap
IMPROVEMENT_THRESHOLD = 0.00005

# Mode: "nba" or "political" -- set via env var or change here
MODE = os.environ.get("BURST_MODE", "nba")  # "nba" or "political"

# Mode-specific config
MODE_CONFIG = {
    "nba": {
        "metric": "brier",  # Lower is better
        "metric_direction": "minimize",
        "atr": 0.21570,
        "target_features": 63,
        "subsample": 4000,
        "result_filename": "latest-lightning-nba-result.json",
    },
    "political": {
        "metric": "signal_accuracy",  # Higher is better
        "metric_direction": "maximize",
        "atr": 0.72,  # Current best accuracy
        "target_features": 50,
        "subsample": 3000,
        "result_filename": "latest-lightning-political-result.json",
    },
}

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

# Evolution parameters (smaller for 10 min burst)
POPULATION_SIZE = 20
ITERATION_BUDGET_SEC = 120  # 2 min per iteration
MUTATION_RATE = 0.09
CROSSOVER_RATE = 0.80
MAX_FEATURES = 200

MODEL_TYPES = ["xgboost", "catboost", "lightgbm", "extra_trees"]
MODEL_WEIGHTS = [0.30, 0.25, 0.20, 0.25]

HP_RANGES = {
    "depth": (4, 10),
    "lr": (0.01, 0.3),
    "n_est": (100, 400),
}

# Lightning AI paths
WORK = Path("/teamspace/studios/this_studio")
if not WORK.exists():
    WORK = Path.cwd()  # Fallback for local testing

REPO_DIR = WORK / "nba-quant-space"
CACHE_DIR = WORK / "burst-cache"
FEATURE_CACHE = CACHE_DIR / f"features_cache_{MODE}.npz"
RESULTS_FILE = CACHE_DIR / f"burst_result_{MODE}.json"
LOG_FILE = CACHE_DIR / f"burst_log_{MODE}.jsonl"


# ══════════════════════════════════════════════════════════
# SETUP
# ══════════════════════════════════════════════════════════

def setup():
    """Install deps and clone source."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    print("[SETUP] Installing dependencies...")
    os.system("pip install -q xgboost lightgbm catboost scikit-learn psycopg2-binary 2>/dev/null")

    hf_token = os.environ.get("HF_TOKEN", "")

    if REPO_DIR.exists():
        print("[SETUP] Pulling latest...")
        subprocess.run(["git", "-C", str(REPO_DIR), "pull", "--ff-only"], capture_output=True)
    else:
        print("[SETUP] Cloning from HF Space...")
        clone_url = f"https://user:{hf_token}@huggingface.co/spaces/Nomos42/nba-quant"
        ret = subprocess.run(
            ["git", "clone", "--depth", "1", clone_url, str(REPO_DIR)],
            capture_output=True, text=True,
        )
        if ret.returncode != 0:
            clone_url = f"https://user:{hf_token}@huggingface.co/spaces/Nomos42/nba-quant-2"
            subprocess.run(
                ["git", "clone", "--depth", "1", clone_url, str(REPO_DIR)],
                capture_output=True, text=True, check=True,
            )

    sys.path.insert(0, str(REPO_DIR))
    print("[SETUP] Done.")


def build_features():
    """Build or load feature matrix (NBA or Political mode)."""
    cfg = MODE_CONFIG[MODE]

    if FEATURE_CACHE.exists():
        print(f"[FEATURES] Loading cached {MODE} features...")
        data = np.load(str(FEATURE_CACHE), allow_pickle=True)
        X, y, feature_names = data["X"], data["y"], list(data["feature_names"])
        y_margin = data["y_margin"] if "y_margin" in data else np.zeros(len(y), dtype=np.int32)
        y_total = data["y_total"] if "y_total" in data else np.full(len(y), 225, dtype=np.int32)
        print(f"[FEATURES] Loaded: {X.shape}")
        return X, y, feature_names, y_margin, y_total

    print(f"[FEATURES] Building {MODE} features...")
    t0 = time.time()

    try:
        if MODE == "nba":
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
                        print(f"[FEATURES] Loaded {len(games)} games from JSON")

            if not games:
                db_url = os.environ.get("DATABASE_URL", "")
                if db_url:
                    import psycopg2
                    conn = psycopg2.connect(db_url, connect_timeout=30, options="-c search_path=public")
                    cur = conn.cursor()
                    cur.execute("SELECT game_data FROM nba_games ORDER BY game_date LIMIT 15000")
                    for row in cur.fetchall():
                        if row[0]:
                            games.append(row[0] if isinstance(row[0], dict) else json.loads(row[0]))
                    cur.close()
                    conn.close()

            if not games:
                raise ValueError("No game data available")

            games.sort(key=lambda g: g.get("game_date", g.get("date", "")))
            engine = NBAFeatureEngine()
            X, y, feature_names = engine.build(games)
            y_margin = getattr(engine, 'y_margin', np.zeros(len(y), dtype=np.int32))
            y_total = getattr(engine, 'y_total', np.full(len(y), 225, dtype=np.int32))

        elif MODE == "political":
            # Political mode: load from political alpha feature engine if available
            pol_engine_path = REPO_DIR / "political" / "features"
            if pol_engine_path.exists():
                sys.path.insert(0, str(REPO_DIR / "political"))
                from features.engine import PoliticalFeatureEngine
                engine = PoliticalFeatureEngine()
                X, y, feature_names = engine.build()
            else:
                # Fallback: synthetic political data for testing
                print("[FEATURES] Political engine not found, generating synthetic data...")
                rng = np.random.RandomState(42)
                n_samples, n_features = 3000, 200
                feature_names = [f"pol_feat_{i:03d}" for i in range(n_features)]
                X = rng.randn(n_samples, n_features).astype(np.float32)
                weights = np.zeros(n_features)
                informative = rng.choice(n_features, 25, replace=False)
                weights[informative] = rng.randn(25) * 0.4
                logit = X @ weights + rng.randn(n_samples) * 1.2
                prob = 1.0 / (1.0 + np.exp(-logit))
                y = (rng.rand(n_samples) < prob).astype(np.float64)
        else:
            raise ValueError(f"Unknown mode: {MODE}")

        X = np.nan_to_num(np.array(X, dtype=np.float64))
        y = np.array(y, dtype=np.int32)

        try:
            y_margin
        except NameError:
            y_margin = np.zeros(len(y), dtype=np.int32)
        try:
            y_total
        except NameError:
            y_total = np.full(len(y), 225, dtype=np.int32)
        np.savez_compressed(str(FEATURE_CACHE), X=X, y=y, feature_names=np.array(feature_names),
                            y_margin=y_margin, y_total=y_total)
        print(f"[FEATURES] Built & cached: {X.shape} in {time.time()-t0:.0f}s")
        return X, y, feature_names, y_margin, y_total

    except Exception as e:
        print(f"[FEATURES] Build failed: {e}")
        traceback.print_exc()
        raise


# ══════════════════════════════════════════════════════════
# MODEL FACTORY + EVALUATION
# ══════════════════════════════════════════════════════════

def make_model(model_type: str, hp: Dict[str, Any]):
    """Create model. Auto-detect GPU availability."""
    import xgboost as xgb
    import lightgbm as lgbm
    from catboost import CatBoostClassifier
    from sklearn.ensemble import ExtraTreesClassifier

    try:
        has_cuda = xgb.build_info().get("USE_CUDA", False)
    except Exception:
        has_cuda = False

    if model_type == "xgboost":
        return xgb.XGBClassifier(
            max_depth=hp.get("depth", 6), learning_rate=hp.get("lr", 0.1),
            n_estimators=hp.get("n_est", 200), random_state=42,
            eval_metric="logloss", verbosity=0, tree_method="hist",
            device="cuda" if has_cuda else "cpu",
        )
    elif model_type == "lightgbm":
        return lgbm.LGBMClassifier(
            max_depth=hp.get("depth", 6), learning_rate=hp.get("lr", 0.1),
            n_estimators=hp.get("n_est", 200), random_state=42,
            verbose=-1, device="gpu" if has_cuda else "cpu",
        )
    elif model_type == "catboost":
        return CatBoostClassifier(
            depth=min(hp.get("depth", 6), 10), learning_rate=hp.get("lr", 0.1),
            iterations=hp.get("n_est", 200), random_state=42,
            verbose=0, task_type="GPU" if has_cuda else "CPU",
        )
    elif model_type == "extra_trees":
        return ExtraTreesClassifier(
            n_estimators=hp.get("n_est", 200), max_depth=hp.get("depth", None),
            random_state=42, n_jobs=-1,
        )
    else:
        return xgb.XGBClassifier(verbosity=0, random_state=42)


def evaluate(X_data, y_data, features_mask, model_type, hp, timeout=90):
    """
    Evaluate one individual. Returns metric score.
    NBA: Brier score (lower = better)
    Political: 1 - accuracy (lower = better, for consistent selection logic)
    Returns 1.0 on failure. IMMUTABLE.
    """
    from sklearn.model_selection import TimeSeriesSplit
    from sklearn.metrics import brier_score_loss, accuracy_score

    try:
        selected = np.where(features_mask)[0]
        if len(selected) < 5 or len(selected) > MAX_FEATURES:
            return 1.0

        X_sub = X_data[:, selected]
        tscv = TimeSeriesSplit(n_splits=2)
        scores = []

        for train_idx, test_idx in tscv.split(X_sub):
            model = make_model(model_type, hp)
            t0 = time.time()
            model.fit(X_sub[train_idx], y_data[train_idx])
            if time.time() - t0 > timeout:
                return 1.0

            probs = model.predict_proba(X_sub[test_idx])
            probs = probs[:, 1] if probs.shape[1] == 2 else probs[:, 0]
            probs = np.clip(probs, 0.001, 0.999)

            if MODE == "nba":
                scores.append(brier_score_loss(y_data[test_idx], probs))
            elif MODE == "political":
                # For political: return 1 - accuracy so lower is still better
                preds = (probs >= 0.5).astype(int)
                acc = accuracy_score(y_data[test_idx], preds)
                scores.append(1.0 - acc)

        return float(np.mean(scores))
    except Exception:
        return 1.0


# ══════════════════════════════════════════════════════════
# GENETIC OPERATORS
# ══════════════════════════════════════════════════════════

def random_individual(n_features: int) -> Dict[str, Any]:
    cfg = MODE_CONFIG[MODE]
    mask = np.zeros(n_features, dtype=bool)
    target = min(cfg["target_features"], n_features)
    selected = np.random.choice(n_features, size=target, replace=False)
    mask[selected] = True
    model_type = np.random.choice(MODEL_TYPES, p=MODEL_WEIGHTS)
    hp = {
        "depth": random.randint(*HP_RANGES["depth"]),
        "lr": round(random.uniform(*HP_RANGES["lr"]), 3),
        "n_est": random.randint(*HP_RANGES["n_est"]),
    }
    return {"mask": mask, "model_type": model_type, "hp": hp, "score": 1.0}


def mutate(ind: Dict[str, Any], mutation_rate: float) -> Dict[str, Any]:
    cfg = MODE_CONFIG[MODE]
    new = {
        "mask": ind["mask"].copy(),
        "model_type": ind["model_type"],
        "hp": dict(ind["hp"]),
        "score": 1.0,
    }
    n_flip = max(1, int(mutation_rate * np.sum(new["mask"])))
    for _ in range(n_flip):
        idx = random.randint(0, len(new["mask"]) - 1)
        new["mask"][idx] = not new["mask"][idx]

    n_selected = int(np.sum(new["mask"]))
    target = cfg["target_features"]
    while n_selected > min(target * 1.5, MAX_FEATURES):
        on_indices = np.where(new["mask"])[0]
        new["mask"][np.random.choice(on_indices)] = False
        n_selected -= 1
    while n_selected < max(target * 0.5, 10):
        off_indices = np.where(~new["mask"])[0]
        if len(off_indices) == 0:
            break
        new["mask"][np.random.choice(off_indices)] = True
        n_selected += 1

    if random.random() < 0.2:
        new["hp"]["depth"] = max(4, min(10, new["hp"]["depth"] + random.choice([-1, 0, 1])))
        new["hp"]["lr"] = round(max(0.01, min(0.3, new["hp"]["lr"] * random.uniform(0.8, 1.2))), 3)
        new["hp"]["n_est"] = max(100, min(400, new["hp"]["n_est"] + random.choice([-50, 0, 50])))

    if random.random() < 0.25:
        new["model_type"] = np.random.choice(MODEL_TYPES, p=MODEL_WEIGHTS)

    return new


def crossover(p1: Dict[str, Any], p2: Dict[str, Any]) -> Dict[str, Any]:
    child = {"mask": np.zeros_like(p1["mask"]), "score": 1.0}
    for i in range(len(child["mask"])):
        child["mask"][i] = p1["mask"][i] if random.random() < CROSSOVER_RATE else p2["mask"][i]
    child["model_type"] = p1["model_type"] if random.random() < 0.5 else p2["model_type"]
    child["hp"] = dict(p1["hp"] if random.random() < 0.5 else p2["hp"])
    return child


# ══════════════════════════════════════════════════════════
# HF ISLAND SEEDING + RESULT PUSHING
# ══════════════════════════════════════════════════════════

def fetch_island_seeds(n_features: int) -> List[Dict[str, Any]]:
    """Seed from HF islands (NBA mode only, political uses random init)."""
    if MODE != "nba":
        return []

    seeds = []
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    for name, base_url in HF_ISLANDS.items():
        try:
            url = f"{base_url}/api/best"
            req = urllib.request.Request(url, headers={"User-Agent": "Nomos42-LightningBurst/1.0"})
            with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
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
                            "score": float(data.get("brier", 1.0)),
                        })
                        print(f"  [SEED] {name}: brier={data.get('brier', '?')}")
        except Exception as e:
            print(f"  [SEED] {name}: failed ({e})")

    print(f"[SEED] Total seeds: {len(seeds)}")
    return seeds


def push_results(result: Dict[str, Any]) -> bool:
    """Push results to GitHub."""
    github_token = os.environ.get("GITHUB_TOKEN", "")
    if not github_token:
        print("[PUSH] No GITHUB_TOKEN -- skipping")
        return False

    try:
        push_dir = WORK / "mon-ipad-push"
        if not push_dir.exists():
            clone_url = f"https://{github_token}@github.com/{GITHUB_REPO}.git"
            subprocess.run(
                ["git", "clone", "--depth", "1", clone_url, str(push_dir)],
                capture_output=True, text=True, timeout=60, check=True,
            )

        cfg = MODE_CONFIG[MODE]
        result_path = push_dir / "data" / "gpu-burst" / cfg["result_filename"]
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

        metric_name = cfg["metric"]
        metric_val = result.get("best_score", result.get("best_brier", "?"))
        msg = (
            f"gpu-burst: lightning {MODE} {metric_name}={metric_val} "
            f"({result['model_type']}, {result['n_features']}f, "
            f"{result['iterations']} iters)"
        )
        ret = subprocess.run(
            ["git", "-C", str(push_dir), "commit", "-m", msg],
            capture_output=True, text=True,
        )
        if ret.returncode != 0:
            return False

        subprocess.run(
            ["git", "-C", str(push_dir), "push", "origin", GITHUB_BRANCH],
            capture_output=True, text=True, timeout=60, check=True,
        )
        print(f"[PUSH] Pushed: {msg}")
        return True
    except Exception as e:
        print(f"[PUSH] Failed: {e}")
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
    """Main burst: 10 min evolution then push if improved."""
    cfg = MODE_CONFIG[MODE]
    burst_start = time.time()

    # Step 1: Setup
    setup()
    X, y, feature_names, y_margin, y_total = build_features()
    n_features = X.shape[1]

    if X.shape[0] > cfg["subsample"]:
        X = X[-cfg["subsample"]:]
        y = y[-cfg["subsample"]:]
        y_margin = y_margin[-cfg["subsample"]:]
        y_total = y_total[-cfg["subsample"]:]
    print(f"[BURST] {MODE.upper()} mode | Data: {X.shape}")

    # Step 2: Seed population
    seeds = fetch_island_seeds(n_features)
    population = seeds[:POPULATION_SIZE]
    while len(population) < POPULATION_SIZE:
        population.append(random_individual(n_features))

    best_ever = min(
        (ind["score"] for ind in population if ind["score"] < 1.0),
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
    print(f"  LIGHTNING AI GPU BURST -- {MODE.upper()} EVOLUTION")
    print(f"  Pop={POPULATION_SIZE} | Metric={cfg['metric']}")
    print(f"  ATR: {cfg['atr']} | Seed best: {best_ever:.5f}")
    print(f"  Setup: {elapsed_setup:.0f}s | Remaining: {remaining:.0f}s")
    print(f"{'='*70}\n")

    send_telegram_alert(
        f"Lightning {MODE.upper()} Burst Started\n"
        f"Seed best: {best_ever:.5f}\n"
        f"Budget: {MAX_DURATION_SECONDS}s"
    )

    # Step 3: Evolution loop
    while time.time() - burst_start < MAX_DURATION_SECONDS:
        iteration += 1
        iter_start = time.time()
        n_evals = 0
        improved = False

        for ind in population:
            if ind["score"] >= 0.99:
                ind["score"] = evaluate(X, y, ind["mask"], ind["model_type"], ind["hp"])
                n_evals += 1
                total_evals += 1
                if time.time() - iter_start > ITERATION_BUDGET_SEC:
                    break

        population.sort(key=lambda x: x["score"])

        if population[0]["score"] < best_ever - IMPROVEMENT_THRESHOLD:
            best_ever = population[0]["score"]
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

        if stagnation >= 10:
            mutation_rate = min(0.20, mutation_rate * 1.3)
        elif improved:
            mutation_rate = max(0.06, mutation_rate * 0.95)

        # Log
        duration = time.time() - iter_start
        remaining = MAX_DURATION_SECONDS - (time.time() - burst_start)
        best_nf = int(np.sum(population[0]["mask"]))
        tag = "*** NEW BEST ***" if improved else ""

        # Convert score to display metric
        if MODE == "political":
            display_metric = 1.0 - best_ever  # Show as accuracy
        else:
            display_metric = best_ever

        print(
            f"Iter {iteration}: {cfg['metric']}={display_metric:.5f} "
            f"({population[0]['model_type']}, {best_nf}f) | "
            f"{n_evals} evals {duration:.0f}s | "
            f"{remaining:.0f}s left {tag}"
        )

        log_experiment({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "iteration": iteration,
            "best_score": best_ever,
            "display_metric": display_metric,
            "n_evals": n_evals,
            "mode": MODE,
            "platform": "lightning",
        })

        gc.collect()

    # Step 4: Finalize
    total_time = time.time() - burst_start
    best_ind = population[0]
    best_features = [int(i) for i in np.where(best_ind["mask"])[0]]

    if MODE == "political":
        display_best = 1.0 - best_ever
        display_initial = 1.0 - initial_best
    else:
        display_best = best_ever
        display_initial = initial_best

    result = {
        "best_score": best_ever,
        "best_brier": best_ever if MODE == "nba" else None,
        "best_accuracy": 1.0 - best_ever if MODE == "political" else None,
        "initial_best": initial_best,
        "improvement": round(initial_best - best_ever, 6),
        "model_type": best_ind["model_type"],
        "hp": best_ind["hp"],
        "features": best_features,
        "n_features": len(best_features),
        "iterations": iteration,
        "total_evals": total_evals,
        "total_time_sec": round(total_time, 1),
        "platform": "lightning",
        "mode": MODE,
        "metric": cfg["metric"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    RESULTS_FILE.write_text(json.dumps(result, indent=2))

    print(f"\n{'='*70}")
    print(f"  BURST COMPLETE ({MODE.upper()})")
    print(f"  Iterations: {iteration} | Evals: {total_evals}")
    print(f"  Best {cfg['metric']}: {display_best:.5f}")
    print(f"  Improvement: {result['improvement']:.6f}")
    print(f"  Model: {best_ind['model_type']}, {len(best_features)}f")
    print(f"  Time: {total_time:.0f}s")
    print(f"{'='*70}")

    if best_ever < initial_best - IMPROVEMENT_THRESHOLD:
        print("\n[RESULT] Improvement found -- pushing...")
        push_results(result)
        if MODE == "nba":
            # Update S10 with new best
            try:
                payload = json.dumps({
                    "best_brier": best_ever,
                    "features": best_features,
                    "model_type": best_ind["model_type"],
                    "hp": best_ind["hp"],
                    "source": "lightning-burst",
                }).encode("utf-8")
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                req = urllib.request.Request(
                    f"{HF_ISLANDS['S10']}/api/config",
                    data=payload, method="POST",
                    headers={"Content-Type": "application/json"},
                )
                urllib.request.urlopen(req, timeout=15, context=ctx)
            except Exception:
                pass

        send_telegram_alert(
            f"Lightning {MODE.upper()} Burst -- IMPROVED\n"
            f"{cfg['metric']}: {display_initial:.5f} -> {display_best:.5f}\n"
            f"Model: {best_ind['model_type']}, {len(best_features)}f"
        )
    else:
        print("\n[RESULT] No improvement -- discarding.")
        send_telegram_alert(
            f"Lightning {MODE.upper()} Burst -- No improvement\n"
            f"Best: {display_best:.5f}"
        )

    return result


# ══════════════════════════════════════════════════════════
# RUN
# ══════════════════════════════════════════════════════════

if __name__ == "__main__":
    result = run_burst()
