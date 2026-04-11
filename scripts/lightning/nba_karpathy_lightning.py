#!/usr/bin/env python3
"""
NBA Quant AI — Karpathy Autoresearch Loop (Lightning.ai GPU)
============================================================
Adapted from scripts/kaggle/nba_karpathy_loop.py for Lightning.ai T4 GPU.

Key differences from Kaggle:
  - Paths: /teamspace/studios/this_studio/ instead of /kaggle/working/
  - Longer sessions: up to 22h (vs Kaggle 9h)
  - Auto-checkpoint every 10 iterations
  - Credit-efficient: auto-stop after --max-hours
  - Uploads best result to HF Space for cross-pollination

Usage (runs ON Lightning GPU — launched by launch_karpathy.py):
    python3 nba_karpathy_lightning.py --iterations 200 --max-hours 4

Credit budget:
    T4 = ~$0.10/hr free tier | 22h/account/month
    Each iteration ~25s → ~144 iter/hr
    4h burst = ~576 iterations = ~$0.40 credits
"""

import os, sys, json, time, gc, math, random, traceback, argparse
import numpy as np
from pathlib import Path
from datetime import datetime
from sklearn.metrics import brier_score_loss
from sklearn.model_selection import TimeSeriesSplit

# ── Parse args ──
parser = argparse.ArgumentParser()
parser.add_argument("--iterations", type=int, default=200)
parser.add_argument("--max-hours", type=float, default=4.0)
args = parser.parse_args()

# ── Paths (Lightning) ──
WORK = Path("/teamspace/studios/this_studio")
if not WORK.exists():
    WORK = Path(".")  # Fallback for local testing
CACHE = WORK / "nba-quant-gpu"
CACHE.mkdir(exist_ok=True)
STATE_FILE = CACHE / "karpathy_state.json"
RESULTS_FILE = CACHE / "result.json"
LOG_FILE = CACHE / "experiment_log.jsonl"

# ── Secrets (from env or Lightning secrets) ──
HF_TOKEN = os.environ.get("HF_TOKEN", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "")

print(f"=== Lightning Karpathy Loop ===")
print(f"Iterations: {args.iterations}, Max hours: {args.max_hours}")
print(f"Work dir: {WORK}")
print(f"HF_TOKEN: {'set' if HF_TOKEN else 'NOT SET'}")
print(f"DATABASE_URL: {'set' if DATABASE_URL else 'NOT SET'}")
print()

# ── Install deps ──
print("Installing deps...")
os.system("pip install -q xgboost lightgbm catboost scikit-learn psycopg2-binary nba_api 2>/dev/null")

import xgboost as xgb
import lightgbm as lgbm
from catboost import CatBoostClassifier
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier

# ── Clone feature engine from HF Space ──
REPO_DIR = WORK / "nba-quant-space"
if not REPO_DIR.exists():
    print("Cloning feature engine from HF Space...")
    ret = os.system(f"git clone --depth 1 https://user:{HF_TOKEN}@huggingface.co/spaces/Nomos42/nba-quant {REPO_DIR}")
    if ret != 0:
        os.system(f"git clone --depth 1 https://user:{HF_TOKEN}@huggingface.co/spaces/Nomos42/nba-quant-2 {REPO_DIR}")
sys.path.insert(0, str(REPO_DIR))

# ── Build or load features ──
FEATURE_CACHE = CACHE / "features_cache_v38.npz"
if FEATURE_CACHE.exists():
    print(f"Loading cached features...")
    data = np.load(FEATURE_CACHE, allow_pickle=True)
    X, y, feature_names = data["X"], data["y"], list(data["feature_names"])
    print(f"Loaded: {X.shape}")
else:
    print("Building features (~30 min first time)...")
    t0 = time.time()
    from features.engine import NBAFeatureEngine

    games = []
    for hist_dir in [REPO_DIR / "data" / "historical"]:
        if hist_dir.exists():
            for f in sorted(hist_dir.glob("games-*.json")):
                raw = json.loads(f.read_text())
                games.extend(raw if isinstance(raw, list) else raw.get("games", []))
            if games: print(f"Loaded {len(games)} games from {hist_dir}")

    if not games and DATABASE_URL:
        print("Loading from Supabase...")
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=30)
        cur = conn.cursor()
        cur.execute("SELECT game_data FROM nba_games ORDER BY game_date LIMIT 15000")
        for row in cur.fetchall():
            if row[0]: games.append(row[0] if isinstance(row[0], dict) else json.loads(row[0]))
        cur.close(); conn.close()
        print(f"Loaded {len(games)} games from Supabase")

    if not games:
        raise ValueError("No game data! Set DATABASE_URL or ensure HF Space has data.")

    games.sort(key=lambda g: g.get("game_date", g.get("date", "")))
    engine = NBAFeatureEngine()
    X, y, feature_names = engine.build(games)
    X = np.nan_to_num(np.array(X, dtype=np.float64))
    y = np.array(y, dtype=np.int32)
    np.savez_compressed(FEATURE_CACHE, X=X, y=y, feature_names=np.array(feature_names))
    print(f"Built & cached: {X.shape} in {time.time()-t0:.0f}s")

MAX_GAMES = 6000
if X.shape[0] > MAX_GAMES:
    X = X[-MAX_GAMES:]
    y = y[-MAX_GAMES:]
print(f"Ready: {X.shape} ({len(feature_names)} features)")

# ══════════════════════════════════════════════════════════
# EVALUATION HARNESS (immutable)
# ══════════════════════════════════════════════════════════

def make_model(model_type, hp):
    if model_type == "xgboost":
        return xgb.XGBClassifier(
            max_depth=hp.get("depth", 6), learning_rate=hp.get("lr", 0.1),
            n_estimators=hp.get("n_est", 200), random_state=42,
            eval_metric="logloss", verbosity=0, tree_method="hist",
            device="cuda" if xgb.build_info().get("USE_CUDA") else "cpu"
        )
    elif model_type == "lightgbm":
        return lgbm.LGBMClassifier(
            max_depth=hp.get("depth", 6), learning_rate=hp.get("lr", 0.1),
            n_estimators=hp.get("n_est", 200), random_state=42,
            verbose=-1, device="gpu"
        )
    elif model_type == "catboost":
        return CatBoostClassifier(
            depth=min(hp.get("depth", 6), 10), learning_rate=hp.get("lr", 0.1),
            iterations=hp.get("n_est", 200), random_state=42,
            verbose=0, task_type="GPU"
        )
    elif model_type == "extra_trees":
        return ExtraTreesClassifier(
            n_estimators=hp.get("n_est", 200), max_depth=hp.get("depth", None),
            random_state=42, n_jobs=-1
        )
    elif model_type == "random_forest":
        return RandomForestClassifier(
            n_estimators=hp.get("n_est", 200), max_depth=hp.get("depth", None),
            random_state=42, n_jobs=-1
        )
    else:
        return xgb.XGBClassifier(verbosity=0, random_state=42)

def evaluate(features_mask, model_type, hp, timeout=120):
    try:
        selected = np.where(features_mask)[0]
        if len(selected) < 5 or len(selected) > 200:
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
    except Exception:
        return 1.0

# ══════════════════════════════════════════════════════════
# EVOLUTION ENGINE
# ══════════════════════════════════════════════════════════

CONFIG = {
    "population_size": 30,
    "iteration_budget_sec": 300,
    "mutation_rate": 0.09,
    "crossover_rate": 0.80,
    "target_features": 63,
    "model_types": ["xgboost", "extra_trees", "catboost", "lightgbm", "random_forest"],
    "model_weights": [0.30, 0.25, 0.20, 0.15, 0.10],
    "hp_ranges": {"depth": (4, 10), "lr": (0.01, 0.3), "n_est": (100, 500)},
}

def random_individual():
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
    new = {"mask": ind["mask"].copy(), "model_type": ind["model_type"],
           "hp": dict(ind["hp"]), "brier": 1.0}
    n_flip = max(1, int(CONFIG["mutation_rate"] * np.sum(new["mask"])))
    for _ in range(n_flip):
        idx = random.randint(0, len(new["mask"]) - 1)
        new["mask"][idx] = not new["mask"][idx]
    n_selected = np.sum(new["mask"])
    target = CONFIG["target_features"]
    while n_selected > min(target * 1.5, 200):
        on_indices = np.where(new["mask"])[0]
        new["mask"][np.random.choice(on_indices)] = False
        n_selected -= 1
    while n_selected < max(target * 0.5, 10):
        off_indices = np.where(~new["mask"])[0]
        if len(off_indices) == 0: break
        new["mask"][np.random.choice(off_indices)] = True
        n_selected += 1
    if random.random() < 0.2:
        new["hp"]["depth"] = max(4, min(10, new["hp"]["depth"] + random.choice([-1, 0, 1])))
        new["hp"]["lr"] = max(0.01, min(0.3, new["hp"]["lr"] * random.uniform(0.8, 1.2)))
    if random.random() < 0.25:
        new["model_type"] = np.random.choice(CONFIG["model_types"], p=CONFIG["model_weights"])
    return new

def crossover(p1, p2):
    child = {"mask": np.zeros_like(p1["mask"]), "brier": 1.0}
    for i in range(len(child["mask"])):
        child["mask"][i] = p1["mask"][i] if random.random() < CONFIG["crossover_rate"] else p2["mask"][i]
    child["model_type"] = p1["model_type"] if random.random() < 0.5 else p2["model_type"]
    child["hp"] = dict(p1["hp"] if random.random() < 0.5 else p2["hp"])
    return child

def load_state():
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text())
        for ind in state.get("population", []):
            ind["mask"] = np.array(ind["mask"], dtype=bool)
        return state
    return None

def save_state(state):
    s = dict(state)
    s["population"] = [{**ind, "mask": ind["mask"].tolist()} for ind in state["population"]]
    STATE_FILE.write_text(json.dumps(s, indent=2))

def fetch_island_seeds():
    seeds = []
    spaces = [
        "https://nomos42-nba-quant.hf.space/api/best",
        "https://nomos42-nba-quant-2.hf.space/api/best",
        "https://nomos42-nba-evo-3.hf.space/api/best",
        "https://nomos42-nba-evo-4.hf.space/api/best",
        "https://nomos42-nba-evo-5.hf.space/api/best",
        "https://nomos42-nba-evo-6.hf.space/api/best",
        "https://lbjlincoln26-nba-evo-s16.hf.space/api/best",
        "https://lbjlincoln26-nba-evo-s17.hf.space/api/best",
    ]
    import urllib.request
    for url in spaces:
        try:
            req = urllib.request.urlopen(url, timeout=10)
            data = json.loads(req.read())
            if "features" in data and "model_type" in data:
                mask = np.zeros(X.shape[1], dtype=bool)
                for idx in data["features"][:200]:
                    if idx < X.shape[1]:
                        mask[idx] = True
                if np.sum(mask) >= 5:
                    seeds.append({
                        "mask": mask,
                        "model_type": data["model_type"],
                        "hp": data.get("hp", {"depth": 6, "lr": 0.1, "n_est": 200}),
                        "brier": data.get("brier", 1.0),
                    })
        except Exception:
            pass
    return seeds

# ══════════════════════════════════════════════════════════
# MAIN KARPATHY LOOP
# ══════════════════════════════════════════════════════════

state = load_state()
if state:
    population = state["population"]
    best_brier = state["best_brier"]
    iteration = state["iteration"]
    print(f"Resumed: iter {iteration}, best {best_brier:.5f}, pop {len(population)}")
else:
    population = [random_individual() for _ in range(CONFIG["population_size"])]
    seeds = fetch_island_seeds()
    if seeds:
        for i, seed in enumerate(seeds[:len(population)//3]):
            population[i] = seed
        print(f"Seeded {min(len(seeds), len(population)//3)} from HF islands")
    best_brier = 1.0
    iteration = 0

start_time = time.time()
max_seconds = args.max_hours * 3600

print(f"\n{'='*60}")
print(f"KARPATHY LOOP START — {args.iterations} iterations, {args.max_hours}h max")
print(f"Population: {len(population)}, Features: {X.shape[1]}")
print(f"{'='*60}\n")

for it in range(iteration, iteration + args.iterations):
    elapsed = time.time() - start_time
    if elapsed > max_seconds:
        print(f"\n=== TIME LIMIT ({args.max_hours}h) — stopping to save credits ===")
        break

    t0 = time.time()

    # Evaluate unevaluated individuals
    for ind in population:
        if ind["brier"] >= 1.0:
            ind["brier"] = evaluate(ind["mask"], ind["model_type"], ind["hp"])

    # Sort by fitness
    population.sort(key=lambda x: x["brier"])
    current_best = population[0]["brier"]
    improved = current_best < best_brier

    if improved:
        best_brier = current_best
        print(f"  *** NEW BEST: {best_brier:.5f} ({population[0]['model_type']}, "
              f"{np.sum(population[0]['mask'])} features) ***")

    # Selection + reproduction
    elite_n = max(3, len(population) // 5)
    elite = population[:elite_n]
    offspring = list(elite)  # Keep elite

    while len(offspring) < CONFIG["population_size"]:
        if random.random() < 0.7:
            # Crossover
            p1, p2 = random.sample(elite, 2)
            child = crossover(p1, p2)
            offspring.append(mutate(child))
        else:
            # Mutation only
            parent = random.choice(elite)
            offspring.append(mutate(parent))

    population = offspring
    duration = time.time() - t0

    # Progress
    hours_left = (max_seconds - elapsed) / 3600
    iter_rate = (it - iteration + 1) / max(elapsed, 1) * 3600
    print(f"[{it+1}] best={best_brier:.5f} | pop_best={current_best:.5f} | "
          f"{duration:.1f}s | {elapsed/3600:.1f}h elapsed | "
          f"~{hours_left:.1f}h left | {iter_rate:.0f} iter/hr"
          f"{' ★' if improved else ''}")

    # Log
    entry = {
        "timestamp": datetime.now().isoformat(),
        "iteration": it + 1,
        "best_brier": best_brier,
        "duration_sec": round(duration, 1),
        "improved": improved,
        "platform": "lightning",
    }
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")

    # Checkpoint every 10 iterations
    if (it + 1) % 10 == 0:
        save_state({
            "population": population,
            "best_brier": best_brier,
            "iteration": it + 1,
            "platform": "lightning",
            "timestamp": datetime.now().isoformat(),
        })

    gc.collect()

# Final save
save_state({
    "population": population,
    "best_brier": best_brier,
    "iteration": it + 1 if 'it' in dir() else iteration,
    "platform": "lightning",
    "timestamp": datetime.now().isoformat(),
})

# Save results summary
total_time = time.time() - start_time
result = {
    "best_brier": best_brier,
    "iterations_completed": it + 1 - iteration if 'it' in dir() else 0,
    "total_time_hours": round(total_time / 3600, 2),
    "iter_per_hour": round((it + 1 - iteration) / max(total_time / 3600, 0.01), 0) if 'it' in dir() else 0,
    "best_model": population[0]["model_type"] if population else "?",
    "best_features": int(np.sum(population[0]["mask"])) if population else 0,
    "platform": "lightning",
    "timestamp": datetime.now().isoformat(),
}
RESULTS_FILE.write_text(json.dumps(result, indent=2))

print(f"\n{'='*60}")
print(f"DONE — Best Brier: {best_brier:.5f}")
print(f"Time: {total_time/3600:.2f}h | Rate: {result['iter_per_hour']} iter/hr")
print(f"{'='*60}")
