#!/usr/bin/env python3
"""
Laptop Evolution Worker — Nomos42 NBA Quant AI
================================================
Lightweight CPU evolution node for Acer Aspire A315 (i3, 3.8GB WSL RAM).
Runs tree-based models only (extra_trees, random_forest, lightgbm, xgboost).
Seeds from live HF Space islands, reports results via JSON checkpoint.

Usage:
    source /home/nomos/nomos42-evo/venv/bin/activate
    python3 /home/nomos/nomos42-evo/laptop_evolution_worker.py

Design constraints:
  - MAX 3GB RAM usage (WSL gets 3.8GB)
  - MAX 4000 games (reduce memory footprint)
  - MAX 150 features per individual (CPU speed)
  - Prefer extra_trees/random_forest (fast on CPU, no GPU needed)
  - 10-minute iteration budget (slow CPU)
  - Checkpoint every 5 iterations
"""

import os
import sys
import json
import time
import gc
import math
import random
import traceback
import urllib.request
import ssl
import numpy as np
from pathlib import Path
from datetime import datetime
from sklearn.metrics import brier_score_loss
from sklearn.model_selection import TimeSeriesSplit

# ── Paths ──
WORK = Path("/home/nomos/nomos42-evo")
DATA_DIR = WORK / "data"
CHECKPOINT_DIR = WORK / "checkpoints"
RESULTS_DIR = WORK / "results"
STATE_FILE = CHECKPOINT_DIR / "laptop_state.json"
RESULTS_FILE = RESULTS_DIR / "laptop_best.json"
LOG_FILE = RESULTS_DIR / "laptop_log.jsonl"
FEATURE_CACHE = DATA_DIR / "features_cache.npz"

for d in [DATA_DIR, CHECKPOINT_DIR, RESULTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── Feature Engine ──
FEATURE_ENGINE_DIR = WORK / "features"
HF_TOKEN = os.environ.get("HF_TOKEN", "")

def setup_feature_engine():
    """Clone feature engine from HF Space if not present."""
    engine_file = FEATURE_ENGINE_DIR / "engine.py"
    if engine_file.exists():
        print(f"Feature engine found: {engine_file}")
        return True

    if not HF_TOKEN:
        print("WARNING: HF_TOKEN not set. Cannot clone feature engine.")
        print("Set it: export HF_TOKEN=your_token")
        return False

    print("Cloning feature engine from HF Space...")
    repo_dir = WORK / "_hf_clone"
    spaces = [
        "https://user:{token}@huggingface.co/spaces/Nomos42/nba-quant",
        "https://user:{token}@huggingface.co/spaces/Nomos42/nba-quant-2",
    ]
    for space_url in spaces:
        url = space_url.format(token=HF_TOKEN)
        ret = os.system(f"git clone --depth 1 {url} {repo_dir} 2>/dev/null")
        if ret == 0 and (repo_dir / "features" / "engine.py").exists():
            os.system(f"cp -r {repo_dir}/features/* {FEATURE_ENGINE_DIR}/")
            os.system(f"rm -rf {repo_dir}")
            print("Feature engine cloned successfully.")
            return True
        os.system(f"rm -rf {repo_dir}")

    print("ERROR: Could not clone feature engine from any HF Space.")
    return False


def build_features():
    """Build or load feature matrix."""
    global X, y, feature_names

    if FEATURE_CACHE.exists():
        print(f"Loading cached features from {FEATURE_CACHE}")
        data = np.load(FEATURE_CACHE, allow_pickle=True)
        X, y, feature_names = data["X"], data["y"], list(data["feature_names"])
        print(f"Loaded: {X.shape}")
        return True

    # Need to build from scratch
    sys.path.insert(0, str(WORK))
    try:
        from features.engine import NBAFeatureEngine
    except ImportError as e:
        print(f"Cannot import feature engine: {e}")
        return False

    # Load games from Supabase
    DATABASE_URL = os.environ.get("DATABASE_URL", "")
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL not set. Cannot build features.")
        print("Set it: export DATABASE_URL='postgresql://...'")
        return False

    print("Loading games from Supabase...")
    import psycopg2
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=30, options="-c search_path=public")
    cur = conn.cursor()
    cur.execute("SELECT game_data FROM nba_games ORDER BY game_date LIMIT 10000")
    games = []
    for row in cur.fetchall():
        if row[0]:
            games.append(row[0] if isinstance(row[0], dict) else json.loads(row[0]))
    cur.close()
    conn.close()
    print(f"Loaded {len(games)} games from Supabase")

    if not games:
        print("ERROR: No games found.")
        return False

    games.sort(key=lambda g: g.get("game_date", g.get("date", "")))

    print("Building features (this may take 15-30 min on laptop)...")
    t0 = time.time()
    engine = NBAFeatureEngine()
    X_raw, y_raw, feature_names = engine.build(games)
    X = np.nan_to_num(np.array(X_raw, dtype=np.float32))  # float32 to save RAM
    y = np.array(y_raw, dtype=np.int32)
    np.savez_compressed(FEATURE_CACHE, X=X, y=y, feature_names=np.array(feature_names))
    print(f"Built & cached: {X.shape} in {time.time()-t0:.0f}s")
    return True


# ── ML Models (CPU only) ──
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier

def make_model(model_type, hp):
    """Create model — CPU-optimized."""
    n_jobs = 2  # Laptop has 2 cores / 4 threads, leave some headroom
    if model_type == "extra_trees":
        return ExtraTreesClassifier(
            n_estimators=hp.get("n_est", 150),
            max_depth=hp.get("depth", None),
            random_state=42, n_jobs=n_jobs,
        )
    elif model_type == "random_forest":
        return RandomForestClassifier(
            n_estimators=hp.get("n_est", 150),
            max_depth=hp.get("depth", None),
            random_state=42, n_jobs=n_jobs,
        )
    elif model_type == "xgboost":
        import xgboost as xgb
        return xgb.XGBClassifier(
            max_depth=hp.get("depth", 6),
            learning_rate=hp.get("lr", 0.1),
            n_estimators=hp.get("n_est", 150),
            random_state=42, eval_metric="logloss",
            verbosity=0, tree_method="hist",
            nthread=n_jobs,
        )
    elif model_type == "lightgbm":
        import lightgbm as lgbm
        return lgbm.LGBMClassifier(
            max_depth=hp.get("depth", 6),
            learning_rate=hp.get("lr", 0.1),
            n_estimators=hp.get("n_est", 150),
            random_state=42, verbose=-1,
            n_jobs=n_jobs,
        )
    else:
        # Default to extra_trees
        return ExtraTreesClassifier(
            n_estimators=150, random_state=42, n_jobs=n_jobs,
        )


# ── Evaluation ──
def evaluate(features_mask, model_type, hp, timeout=180):
    """Evaluate one individual. Returns Brier score (lower = better).
    Timeout is generous (180s) for slow CPU."""
    try:
        selected = np.where(features_mask)[0]
        if len(selected) < 5 or len(selected) > 150:
            return 1.0

        X_sub = X[:, selected]

        tscv = TimeSeriesSplit(n_splits=2)
        briers = []

        for train_idx, test_idx in tscv.split(X_sub):
            model = make_model(model_type, hp)
            t0 = time.time()
            model.fit(X_sub[train_idx], y[train_idx])
            if time.time() - t0 > timeout:
                return 1.0
            probs = model.predict_proba(X_sub[test_idx])[:, 1]
            briers.append(brier_score_loss(y[test_idx], probs))

        return float(np.mean(briers))
    except Exception as e:
        print(f"    Eval error: {e}")
        return 1.0


# ── Genetic Operators ──
CONFIG = {
    "population_size": 20,       # Small pop for slow CPU
    "iteration_budget_sec": 600, # 10 min per iteration
    "mutation_rate": 0.10,
    "crossover_rate": 0.80,
    "target_features": 55,       # Fewer features = faster eval
    "model_types": ["extra_trees", "random_forest", "xgboost", "lightgbm"],
    "model_weights": [0.35, 0.25, 0.20, 0.20],
    "hp_ranges": {
        "depth": (4, 10),
        "lr": (0.01, 0.3),
        "n_est": (80, 300),
    },
    "node_name": "laptop-aspire",
}


def random_individual():
    """Create random individual."""
    n_features = X.shape[1]
    target = CONFIG["target_features"]
    mask = np.zeros(n_features, dtype=bool)
    selected = np.random.choice(n_features, size=min(target, n_features), replace=False)
    mask[selected] = True
    model_type = np.random.choice(CONFIG["model_types"], p=CONFIG["model_weights"])
    hp = {
        "depth": random.randint(*CONFIG["hp_ranges"]["depth"]),
        "lr": round(random.uniform(*CONFIG["hp_ranges"]["lr"]), 3),
        "n_est": random.randint(*CONFIG["hp_ranges"]["n_est"]),
    }
    return {"mask": mask, "model_type": model_type, "hp": hp, "brier": 1.0}


def mutate(ind):
    """Mutate an individual."""
    new = {"mask": ind["mask"].copy(), "model_type": ind["model_type"],
           "hp": dict(ind["hp"]), "brier": 1.0}

    n_flip = max(1, int(CONFIG["mutation_rate"] * np.sum(new["mask"])))
    for _ in range(n_flip):
        idx = random.randint(0, len(new["mask"]) - 1)
        new["mask"][idx] = not new["mask"][idx]

    # Ensure feature count in range [10, 150]
    n_selected = np.sum(new["mask"])
    while n_selected > 150:
        on_indices = np.where(new["mask"])[0]
        new["mask"][np.random.choice(on_indices)] = False
        n_selected -= 1
    while n_selected < 10:
        off_indices = np.where(~new["mask"])[0]
        if len(off_indices) == 0:
            break
        new["mask"][np.random.choice(off_indices)] = True
        n_selected += 1

    # HP mutation (20% chance)
    if random.random() < 0.2:
        new["hp"]["depth"] = max(4, min(10, new["hp"]["depth"] + random.choice([-1, 0, 1])))
        new["hp"]["lr"] = max(0.01, min(0.3, new["hp"]["lr"] * random.uniform(0.8, 1.2)))
        new["hp"]["n_est"] = max(80, min(300, new["hp"]["n_est"] + random.choice([-20, 0, 20])))

    # Model mutation (20% chance)
    if random.random() < 0.20:
        new["model_type"] = np.random.choice(CONFIG["model_types"], p=CONFIG["model_weights"])

    return new


def crossover(p1, p2):
    """Uniform crossover."""
    child = {"mask": np.zeros_like(p1["mask"]), "brier": 1.0}
    for i in range(len(child["mask"])):
        child["mask"][i] = p1["mask"][i] if random.random() < 0.5 else p2["mask"][i]
    child["model_type"] = p1["model_type"] if random.random() < 0.5 else p2["model_type"]
    child["hp"] = dict(p1["hp"] if random.random() < 0.5 else p2["hp"])
    return child


# ── Island Seeds ──
def fetch_island_seeds():
    """Seed population from live HF Space evolution islands."""
    spaces = [
        ("S10", "https://nomos42-nba-quant.hf.space/api/best"),
        ("S11", "https://nomos42-nba-quant-2.hf.space/api/best"),
        ("S12", "https://nomos42-nba-evo-3.hf.space/api/best"),
        ("S13", "https://nomos42-nba-evo-4.hf.space/api/best"),
        ("S14", "https://nomos42-nba-evo-5.hf.space/api/best"),
        ("S15", "https://nomos42-nba-evo-6.hf.space/api/best"),
        ("S16", "https://lbjlincoln26-nba-evo-s16.hf.space/api/best"),
        ("S17", "https://lbjlincoln26-nba-evo-s17.hf.space/api/best"),
    ]
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    seeds = []
    for name, url in spaces:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Nomos42-Laptop/1.0"})
            with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                data = json.loads(resp.read())
                if data.get("brier", 1.0) < 0.99:
                    mask = np.zeros(X.shape[1], dtype=bool)
                    for idx in data.get("features", []):
                        if 0 <= idx < X.shape[1]:
                            mask[idx] = True
                    if np.sum(mask) >= 5:
                        seeds.append({
                            "mask": mask,
                            "model_type": data.get("model_type", "extra_trees"),
                            "hp": data.get("hp", {"depth": 6, "lr": 0.1, "n_est": 150}),
                            "brier": float(data.get("brier", 1.0)),
                        })
                        print(f"  {name}: brier={data.get('brier', '?')}, features={np.sum(mask)}, model={data.get('model_type', '?')}")
                    else:
                        print(f"  {name}: too few features, skipping")
                else:
                    print(f"  {name}: no valid best yet")
        except Exception as e:
            print(f"  {name}: OFFLINE ({e})")

    print(f"Seeds: {len(seeds)}/6 islands")
    return seeds


# ── State Management ──
def load_state():
    """Load checkpoint."""
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text())
        for ind in state.get("population", []):
            ind["mask"] = np.array(ind["mask"], dtype=bool)
        return state
    return None


def save_state(state):
    """Save checkpoint."""
    s = dict(state)
    s["population"] = [
        {**ind, "mask": ind["mask"].tolist()} for ind in state["population"]
    ]
    STATE_FILE.write_text(json.dumps(s, indent=2))


def save_result(population, best_ever, iteration):
    """Save best result for VM to pick up."""
    best = population[0]
    result = {
        "best_brier": best_ever,
        "iteration": iteration,
        "model_type": best["model_type"],
        "n_features": int(np.sum(best["mask"])),
        "features": [int(i) for i in np.where(best["mask"])[0]],
        "hp": best["hp"],
        "node": CONFIG["node_name"],
        "timestamp": datetime.now().isoformat(),
    }
    RESULTS_FILE.write_text(json.dumps(result, indent=2))


def log_experiment(iteration, best_brier, n_evals, duration, improved):
    """Append to experiment log."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "iteration": iteration,
        "best_brier": best_brier,
        "n_evals": n_evals,
        "duration_sec": round(duration, 1),
        "improved": improved,
        "node": CONFIG["node_name"],
    }
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


# ── Main Loop ──
def run_evolution():
    """Main evolution loop — runs until killed."""

    # Load or initialize
    state = load_state()
    if state:
        population = state["population"]
        best_ever = state["best_ever"]
        iteration = state["iteration"]
        print(f"Resumed from iteration {iteration}, best_ever={best_ever:.5f}")
    else:
        print("Initializing population from island seeds...")
        seeds = fetch_island_seeds()
        population = seeds[:CONFIG["population_size"]]
        while len(population) < CONFIG["population_size"]:
            population.append(random_individual())
        best_ever = min((ind["brier"] for ind in population if ind["brier"] < 1.0), default=1.0)
        iteration = 0

    session_start = time.time()
    stagnation = 0

    print(f"\n{'='*60}")
    print(f"  LAPTOP EVOLUTION NODE — {CONFIG['node_name']}")
    print(f"  Pop={CONFIG['population_size']} | Budget={CONFIG['iteration_budget_sec']}s")
    print(f"  Models: {CONFIG['model_types']}")
    print(f"  Features: {X.shape[1]} available, target {CONFIG['target_features']}")
    print(f"  Games: {X.shape[0]}")
    print(f"  Best so far: {best_ever:.5f}")
    print(f"{'='*60}\n")

    while True:
        iteration += 1
        iter_start = time.time()
        n_evals = 0
        improved = False

        # Evaluate unevaluated
        for ind in population:
            if ind["brier"] >= 0.99:
                ind["brier"] = evaluate(ind["mask"], ind["model_type"], ind["hp"])
                n_evals += 1
                if time.time() - iter_start > CONFIG["iteration_budget_sec"]:
                    break

        # Sort by brier
        population.sort(key=lambda x: x["brier"])

        # Check for improvement
        if population[0]["brier"] < best_ever:
            best_ever = population[0]["brier"]
            improved = True
            stagnation = 0
        else:
            stagnation += 1

        # Selection + reproduction
        elite_size = max(2, CONFIG["population_size"] // 5)
        elite = population[:elite_size]

        offspring = []
        while len(offspring) < CONFIG["population_size"] - elite_size:
            if random.random() < CONFIG["crossover_rate"]:
                p1, p2 = random.sample(elite, 2)
                child = crossover(p1, p2)
                child = mutate(child)
            else:
                parent = random.choice(elite)
                child = mutate(parent)
            offspring.append(child)

        population = elite + offspring

        # Adaptive mutation
        if stagnation >= 10:
            CONFIG["mutation_rate"] = min(0.20, CONFIG["mutation_rate"] * 1.2)
        elif improved:
            CONFIG["mutation_rate"] = max(0.06, CONFIG["mutation_rate"] * 0.95)

        # Log
        duration = time.time() - iter_start
        elapsed_h = (time.time() - session_start) / 3600
        tag = "*** NEW BEST ***" if improved else ""
        best_model = population[0]["model_type"]
        best_nf = int(np.sum(population[0]["mask"]))

        print(f"Iter {iteration}: best={best_ever:.5f} ({best_model}, {best_nf}f) | "
              f"{n_evals} evals {duration:.0f}s | {elapsed_h:.1f}h elapsed | stag={stagnation} {tag}")

        log_experiment(iteration, best_ever, n_evals, duration, improved)

        # Checkpoint every 5 iterations
        if iteration % 5 == 0:
            save_state({
                "population": population,
                "best_ever": best_ever,
                "iteration": iteration,
                "timestamp": datetime.now().isoformat(),
            })
            save_result(population, best_ever, iteration)

            # Print summary
            models = {}
            for ind in population[:10]:
                models[ind["model_type"]] = models.get(ind["model_type"], 0) + 1
            print(f"  Top10 models: {models} | Mut: {CONFIG['mutation_rate']:.3f}")

        # Re-seed from islands every 50 iterations
        if iteration % 50 == 0:
            print("  Re-seeding from HF islands...")
            new_seeds = fetch_island_seeds()
            if new_seeds:
                # Replace worst individuals with new seeds
                for i, seed in enumerate(new_seeds[:3]):
                    population[-(i+1)] = seed
                print(f"  Injected {min(3, len(new_seeds))} fresh seeds")

        gc.collect()


# ══════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("NBA Quant AI — Laptop Evolution Worker")
    print(f"Node: {CONFIG['node_name']}")
    print(f"Time: {datetime.now().isoformat()}")
    print()

    # Setup feature engine
    if not setup_feature_engine():
        print("\nFATAL: Feature engine not available.")
        print("Either set HF_TOKEN or copy features/engine.py manually.")
        sys.exit(1)

    # Build/load features
    if not build_features():
        print("\nFATAL: Cannot build features.")
        print("Set DATABASE_URL or provide features_cache.npz")
        sys.exit(1)

    # Subsample for laptop memory constraints
    MAX_GAMES = 4000
    if X.shape[0] > MAX_GAMES:
        X = X[-MAX_GAMES:]
        y = y[-MAX_GAMES:]
        print(f"Subsampled to last {MAX_GAMES} games: {X.shape}")

    # Run evolution
    try:
        run_evolution()
    except KeyboardInterrupt:
        print("\n\nStopped by user. State saved at last checkpoint.")
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        traceback.print_exc()
