#!/usr/bin/env python3
"""
NBA Quant AI — Karpathy Autoresearch Loop (Kaggle GPU)
======================================================
Pattern: github.com/karpathy/autoresearch
- Each iteration: modify config → train 5min → measure Brier → keep if better
- 12 iterations/hour, ~100/session (9h Kaggle limit)
- Checkpoints to Kaggle output for resume across sessions
- Seeds from live HF Space evolution islands

Target: Beat ATR 0.21570 (Colab TabICL v1, 110f, iter 15)
Cycle 14: TabICLv2 added (arXiv:2602.11139, Feb 2026). Expected Brier delta -0.004.
"""

import os, sys, json, time, gc, math, random, traceback
import numpy as np
from pathlib import Path
from datetime import datetime
from sklearn.metrics import brier_score_loss
from sklearn.model_selection import TimeSeriesSplit

# ── Paths ──
WORK = Path("/kaggle/working")
CACHE = WORK / "nba-quant-gpu"
CACHE.mkdir(exist_ok=True)
STATE_FILE = CACHE / "karpathy_state.json"
RESULTS_FILE = CACHE / "result.json"
LOG_FILE = CACHE / "experiment_log.jsonl"
ISLAND_ELO_FILE = CACHE / "island_elo.json"  # Cycle 13: autoevolve Island Elo

# ── Secrets ──
HF_TOKEN = os.environ.get("HF_TOKEN", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not HF_TOKEN:
    print("HF_TOKEN: not set -- add to Kaggle Secrets")
if not DATABASE_URL:
    print("DATABASE_URL: not set -- add to Kaggle Secrets")

# ══════════════════════════════════════════════════════════
# CELL 1: SETUP (runs on CPU, ~30 min first time for features)
# ══════════════════════════════════════════════════════════

print("Installing deps...")
# Cycle 14: --upgrade pulls TabICLv2 (arXiv:2602.11139, Feb 2026) which
# beats RealTabPFN-2.5 without tuning, runs 10x faster, and targets ~-0.004
# Brier vs v1. Package is github.com/soda-inria/tabicl.
os.system("pip install -q --upgrade xgboost lightgbm catboost psycopg2-binary tabicl nba_api 2>/dev/null")

import xgboost as xgb
import lightgbm as lgbm
from catboost import CatBoostClassifier
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier

# TabICLv2 — import guarded so the loop still runs if the v2 weights
# aren't cached yet (first Kaggle session downloads ~800 MB)
HAS_TABICL_V2 = False
try:
    from tabicl import TabICLClassifier  # type: ignore
    import tabicl as _tabicl  # type: ignore
    _tabicl_ver = getattr(_tabicl, "__version__", "unknown")
    HAS_TABICL_V2 = True
    print(f"TabICL version: {_tabicl_ver} (HAS_TABICL_V2={HAS_TABICL_V2})")
except Exception as _e:
    print(f"TabICL import failed: {type(_e).__name__}: {_e} — falling back to tree-only")

# ── GPU detection ──
import subprocess
HAS_GPU = False
try:
    result = subprocess.run(["nvidia-smi"], capture_output=True, text=True, timeout=5)
    HAS_GPU = result.returncode == 0
except Exception:
    pass
print(f"GPU available: {HAS_GPU}")

# Clone feature engine from HF Space (GitHub private repos don't work on Kaggle)
REPO_DIR = WORK / "nba-quant-space"
if not REPO_DIR.exists():
    print("Cloning feature engine from HF Space...")
    ret = os.system(f"git clone --depth 1 https://user:{HF_TOKEN}@huggingface.co/spaces/Nomos42/nba-quant {REPO_DIR}")
    if ret != 0:
        print("Clone failed, trying alternate space...")
        os.system(f"git clone --depth 1 https://user:{HF_TOKEN}@huggingface.co/spaces/Nomos42/nba-quant-2 {REPO_DIR}")
sys.path.insert(0, str(REPO_DIR))

# Build or load feature cache
FEATURE_CACHE = CACHE / "features_cache_v38.npz"
if FEATURE_CACHE.exists():
    print(f"Loading cached features from {FEATURE_CACHE}")
    data = np.load(FEATURE_CACHE, allow_pickle=True)
    X, y, feature_names = data["X"], data["y"], list(data["feature_names"])
    print(f"Loaded: {X.shape}")
else:
    print("Building features (~30 min)...")
    t0 = time.time()
    try:
        # HF Space API: load games, then build features
        sys.path.insert(0, str(REPO_DIR))
        from features.engine import NBAFeatureEngine

        # Try local JSON first, then Supabase
        games = []
        for hist_dir in [REPO_DIR / "data" / "historical"]:
            if hist_dir.exists():
                for f in sorted(hist_dir.glob("games-*.json")):
                    raw = json.loads(f.read_text())
                    games.extend(raw if isinstance(raw, list) else raw.get("games", []))
                if games: print(f"Loaded {len(games)} games from {hist_dir}")

        if not games and DATABASE_URL:
            print("No local data — loading from Supabase...")
            import psycopg2
            conn = psycopg2.connect(DATABASE_URL, connect_timeout=30, options="-c search_path=public")
            cur = conn.cursor()
            cur.execute("SELECT game_data FROM nba_games ORDER BY game_date LIMIT 15000")
            for row in cur.fetchall():
                if row[0]: games.append(row[0] if isinstance(row[0], dict) else json.loads(row[0]))
            cur.close(); conn.close()
            print(f"Loaded {len(games)} games from Supabase")

        if not games:
            raise ValueError("No game data (local or Supabase)! Set DATABASE_URL in Kaggle Secrets.")

        games.sort(key=lambda g: g.get("game_date", g.get("date", "")))
        engine = NBAFeatureEngine()
        X, y, feature_names = engine.build(games)
        X = np.nan_to_num(np.array(X, dtype=np.float64))
        y = np.array(y, dtype=np.int32)
        np.savez_compressed(FEATURE_CACHE, X=X, y=y, feature_names=np.array(feature_names))
        print(f"Built & cached: {X.shape} in {time.time()-t0:.0f}s")
    except Exception as e:
        print(f"Feature build failed: {e}")
        raise

# Subsample to last N games for speed
MAX_GAMES = 6000
if X.shape[0] > MAX_GAMES:
    X = X[-MAX_GAMES:]
    y = y[-MAX_GAMES:]
print(f"Ready: {X.shape} ({len(feature_names)} features)")

# ══════════════════════════════════════════════════════════
# CELL 2: KARPATHY AUTORESEARCH ENGINE
# ══════════════════════════════════════════════════════════

# ═══ IMMUTABLE EVALUATION HARNESS (prepare.py equivalent) ═══

def evaluate(features_mask, model_type, hp, timeout=120):
    """Evaluate one individual. Returns Brier score (lower = better).
    THIS FUNCTION IS IMMUTABLE — agent cannot change it."""
    try:
        # Select features
        selected = np.where(features_mask)[0]
        if len(selected) < 5 or len(selected) > 200:
            return 1.0

        X_sub = X[:, selected]

        # Walk-forward split
        tscv = TimeSeriesSplit(n_splits=2)
        briers = []

        for train_idx, test_idx in tscv.split(X_sub):
            model = make_model(model_type, hp)

            t0 = time.time()
            model.fit(X_sub[train_idx], y[train_idx])
            if time.time() - t0 > timeout:
                return 1.0  # Timeout

            probs = model.predict_proba(X_sub[test_idx])[:, 1]
            briers.append(brier_score_loss(y[test_idx], probs))

        return float(np.mean(briers))
    except Exception as e:
        return 1.0

def make_model(model_type, hp):
    """Create model from type + hyperparams."""
    if model_type == "xgboost":
        return xgb.XGBClassifier(
            max_depth=hp.get("depth", 6), learning_rate=hp.get("lr", 0.1),
            n_estimators=hp.get("n_est", 200), random_state=42,
            eval_metric="logloss", verbosity=0, tree_method="hist",
            device="cuda" if xgb.build_info()["USE_CUDA"] else "cpu"
        )
    elif model_type == "xgboost_brier":
        def brier_obj(y_true, y_pred):
            grad = 2 * (y_pred - y_true)
            hess = np.full_like(grad, 2.0)
            return grad, hess
        return xgb.XGBClassifier(
            max_depth=hp.get("depth", 6), learning_rate=hp.get("lr", 0.1),
            n_estimators=hp.get("n_est", 200), random_state=42,
            objective=brier_obj, verbosity=0, tree_method="hist",
            device="cuda" if xgb.build_info()["USE_CUDA"] else "cpu"
        )
    elif model_type == "lightgbm":
        return lgbm.LGBMClassifier(
            max_depth=hp.get("depth", 6), learning_rate=hp.get("lr", 0.1),
            n_estimators=hp.get("n_est", 200), random_state=42,
            verbose=-1, device="gpu" if HAS_GPU else "cpu"
        )
    elif model_type == "catboost":
        return CatBoostClassifier(
            depth=min(hp.get("depth", 6), 10), learning_rate=hp.get("lr", 0.1),
            iterations=hp.get("n_est", 200), random_state=42,
            verbose=0, task_type="GPU" if HAS_GPU else "CPU"
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
    elif model_type == "tabicl_v2":
        # Cycle 14: TabICLv2 (arXiv:2602.11139, Feb 2026).
        # Drop-in sklearn-compatible tabular foundation model. Beats tuned
        # XGBoost/CatBoost/LightGBM on ~80% of TabArena datasets without
        # any tuning. n_estimators maps to the ensemble of context windows,
        # softmax_temperature controls confidence sharpness.
        if not HAS_TABICL_V2:
            # Fall back to xgboost_brier so evolve loop never stalls on
            # missing deps
            return xgb.XGBClassifier(
                max_depth=6, learning_rate=0.1, n_estimators=200,
                random_state=42, verbosity=0, tree_method="hist",
            )
        return TabICLClassifier(
            n_estimators=min(hp.get("n_est", 8), 16),  # v2 uses small ensemble
            softmax_temperature=hp.get("lr", 0.9),     # reuse lr slot for T
            random_state=42,
            device="cuda" if HAS_GPU else "cpu",
        )
    else:
        return xgb.XGBClassifier(verbosity=0, random_state=42)


# ═══ KARPATHY LOOP: MODIFIABLE CONFIG (evolve_train.py equivalent) ═══

# CONFIG — This is what the agent modifies each iteration
CONFIG = {
    "population_size": 30,
    "iteration_budget_sec": 300,  # 5 minutes per iteration
    "mutation_rate": 0.09,
    "crossover_rate": 0.80,
    "target_features": 63,
    # Cycle 14: tabicl_v2 added with 15% weight (steal from xgboost + extra_trees).
    # Paper expects -0.004 Brier; Karpathy loop will validate on real data and
    # the evolve operator will adaptively drift weights toward whichever models
    # actually win on this season's features.
    "model_types": ["xgboost", "xgboost_brier", "tabicl_v2", "extra_trees", "catboost", "lightgbm", "random_forest"],
    "model_weights": [0.20, 0.18, 0.15, 0.15, 0.12, 0.10, 0.10],
    "hp_ranges": {
        "depth": (4, 10),
        "lr": (0.01, 0.3),
        "n_est": (100, 500),
    },
}

# ─── ISLAND ELO (Cycle 13 — github.com/MrTsepa/autoevolve pattern) ──────────
# Each individual carries an `origin_island` tag (S10..S15 or "random"). After
# every iteration we run a Bradley-Terry round-robin over each island's best
# individual: lower-Brier wins, Elo updates with K=24. The next session uses
# softmax(Elo / 100) to weight how many initial population slots each island
# contributes — high-Elo islands get over-represented in the seed population,
# low-Elo islands fade. Expected -0.002 Brier per repo-scout cycle 13.
ELO_K = 24.0
ELO_DEFAULT = 1500.0
ISLAND_NAMES = ("S10", "S11", "S12", "S13", "S14", "S15", "random")

def load_island_elo():
    if ISLAND_ELO_FILE.exists():
        try:
            raw = json.loads(ISLAND_ELO_FILE.read_text())
            return {k: float(raw.get(k, ELO_DEFAULT)) for k in ISLAND_NAMES}
        except (OSError, json.JSONDecodeError):
            pass
    return {k: ELO_DEFAULT for k in ISLAND_NAMES}

def save_island_elo(elo, n_matches=0, last_iter=0):
    payload = {k: round(v, 1) for k, v in elo.items()}
    payload["_meta"] = {
        "n_matches": int(n_matches),
        "last_iter": int(last_iter),
        "k_factor": ELO_K,
        "updated_at": datetime.now().isoformat(),
        "ref": "github.com/MrTsepa/autoevolve",
    }
    ISLAND_ELO_FILE.write_text(json.dumps(payload, indent=2))

def update_island_elo(elo, population):
    """Round-robin Bradley-Terry update. Each island's best individual is
    its champion; lower Brier wins. Returns number of pairwise matches run."""
    champions = {}
    for ind in population:
        if ind.get("brier", 1.0) >= 0.99:
            continue
        isl = ind.get("origin_island", "random")
        if isl not in champions or ind["brier"] < champions[isl]["brier"]:
            champions[isl] = ind
    if len(champions) < 2:
        return 0
    isls = list(champions.keys())
    n_matches = 0
    for i in range(len(isls)):
        for j in range(i + 1, len(isls)):
            a, b = isls[i], isls[j]
            ra, rb = elo[a], elo[b]
            ea = 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))
            sa = 1.0 if champions[a]["brier"] < champions[b]["brier"] else 0.0
            elo[a] = ra + ELO_K * (sa - ea)
            elo[b] = rb + ELO_K * ((1.0 - sa) - (1.0 - ea))
            n_matches += 1
    return n_matches

def softmax_island_weights(elo):
    """Softmax over Elo / 100 — sharper than raw rating, smoother than greedy."""
    keys = [k for k in ISLAND_NAMES if k != "random"]
    scaled = np.array([elo.get(k, ELO_DEFAULT) / 100.0 for k in keys])
    scaled -= scaled.max()  # numerical stability
    weights = np.exp(scaled)
    weights /= weights.sum()
    return dict(zip(keys, weights))


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
    return {"mask": mask, "model_type": model_type, "hp": hp, "brier": 1.0,
            "origin_island": "random"}

def mutate(ind):
    """Mutate an individual."""
    new = {"mask": ind["mask"].copy(), "model_type": ind["model_type"],
           "hp": dict(ind["hp"]), "brier": 1.0,
           "origin_island": ind.get("origin_island", "random")}

    # Feature mutation
    n_flip = max(1, int(CONFIG["mutation_rate"] * np.sum(new["mask"])))
    for _ in range(n_flip):
        idx = random.randint(0, len(new["mask"]) - 1)
        new["mask"][idx] = not new["mask"][idx]

    # Ensure feature count in range
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

    # HP mutation (20% chance)
    if random.random() < 0.2:
        new["hp"]["depth"] = max(4, min(10, new["hp"]["depth"] + random.choice([-1, 0, 1])))
        new["hp"]["lr"] = max(0.01, min(0.3, new["hp"]["lr"] * random.uniform(0.8, 1.2)))

    # Model mutation (25% chance — prevents monoculture)
    if random.random() < 0.25:
        new["model_type"] = np.random.choice(CONFIG["model_types"], p=CONFIG["model_weights"])

    return new

def crossover(p1, p2):
    """Uniform crossover. Child inherits origin_island from the better parent
    (lower Brier wins) so Elo stays attributed to the genuinely productive
    island lineage."""
    child = {"mask": np.zeros_like(p1["mask"]), "brier": 1.0}
    for i in range(len(child["mask"])):
        child["mask"][i] = p1["mask"][i] if random.random() < CONFIG["crossover_rate"] else p2["mask"][i]
    child["model_type"] = p1["model_type"] if random.random() < 0.5 else p2["model_type"]
    child["hp"] = dict(p1["hp"] if random.random() < 0.5 else p2["hp"])
    better = p1 if p1.get("brier", 1.0) <= p2.get("brier", 1.0) else p2
    child["origin_island"] = better.get("origin_island", "random")
    return child

def load_state():
    """Load checkpoint state."""
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text())
        # Reconstruct masks
        for ind in state.get("population", []):
            ind["mask"] = np.array(ind["mask"], dtype=bool)
        return state
    return None

def save_state(state):
    """Save checkpoint state."""
    s = dict(state)
    s["population"] = [
        {**ind, "mask": ind["mask"].tolist()} for ind in state["population"]
    ]
    STATE_FILE.write_text(json.dumps(s, indent=2))

def log_experiment(iteration, best_brier, n_evals, duration, improved):
    """Append to experiment log (JSONL)."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "iteration": iteration,
        "best_brier": best_brier,
        "n_evals": n_evals,
        "duration_sec": round(duration, 1),
        "improved": improved,
        "config": {k: v for k, v in CONFIG.items() if k != "model_types"},
    }
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")

def fetch_island_seeds(max_retries=3, retry_delay=60):
    """Seed population from live HF Space evolution islands.
    Retries if spaces are still rebuilding (gen 0).
    Falls back to /api/checkpoint/best if /api/best returns 404."""
    # Primary URLs use /api/best; fallback to /api/checkpoint/best (Fix 3)
    spaces = [
        ("S10", "https://nomos42-nba-quant.hf.space/api/best",
                "https://nomos42-nba-quant.hf.space/api/checkpoint/best"),
        ("S11", "https://nomos42-nba-quant-2.hf.space/api/best",
                "https://nomos42-nba-quant-2.hf.space/api/checkpoint/best"),
        ("S12", "https://nomos42-nba-evo-3.hf.space/api/best",
                "https://nomos42-nba-evo-3.hf.space/api/checkpoint/best"),
        ("S13", "https://nomos42-nba-evo-4.hf.space/api/best",
                "https://nomos42-nba-evo-4.hf.space/api/checkpoint/best"),
        ("S14", "https://nomos42-nba-evo-5.hf.space/api/best",
                "https://nomos42-nba-evo-5.hf.space/api/checkpoint/best"),
        ("S15", "https://nomos42-nba-evo-6.hf.space/api/best",
                "https://nomos42-nba-evo-6.hf.space/api/checkpoint/best"),
        ("S16", "https://lbjlincoln26-nba-evo-s16.hf.space/api/best",
                "https://lbjlincoln26-nba-evo-s16.hf.space/api/checkpoint/best"),
        ("S17", "https://lbjlincoln26-nba-evo-s17.hf.space/api/best",
                "https://lbjlincoln26-nba-evo-s17.hf.space/api/checkpoint/best"),
    ]
    import urllib.request, ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    def _fetch_url(url):
        """Fetch JSON from url, return (data, status_code). Returns (None, code) on error."""
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Nomos42-Kaggle/1.0"})
            with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                return json.loads(resp.read()), resp.status
        except urllib.error.HTTPError as e:
            return None, e.code
        except Exception:
            return None, 0

    for attempt in range(max_retries):
        seeds = []
        for name, primary_url, fallback_url in spaces:
            try:
                data, status = _fetch_url(primary_url)
                if data is None and status == 404:
                    # Fix 3: /api/best not found — try /api/checkpoint/best
                    print(f"  {name}: /api/best → 404, trying /api/checkpoint/best")
                    data, status = _fetch_url(fallback_url)
                if data is None:
                    print(f"  {name}: OFFLINE (status={status})")
                    continue
                if data.get("brier", 1.0) < 0.99:
                    mask = np.zeros(X.shape[1], dtype=bool)
                    for idx in data.get("features", []):
                        if 0 <= idx < X.shape[1]:
                            mask[idx] = True
                    if np.sum(mask) >= 5:  # Valid seed
                        seeds.append({
                            "mask": mask,
                            "model_type": data.get("model_type", "xgboost"),
                            "hp": data.get("hp", {"depth": 6, "lr": 0.1, "n_est": 200}),
                            "brier": float(data.get("brier", 1.0)),
                            "origin_island": name,  # Cycle 13: Elo attribution
                        })
                        print(f"  {name}: brier={data.get('brier', '?')}, features={np.sum(mask)}, model={data.get('model_type', '?')}")
                    else:
                        print(f"  {name}: too few features ({np.sum(mask)}), skipping")
                else:
                    print(f"  {name}: gen 0 / no valid best yet")
            except Exception as e:
                print(f"  {name}: ERROR ({type(e).__name__}: {e})")

        if seeds:
            print(f"Seeds fetched: {len(seeds)}/6 islands (attempt {attempt+1})")
            return seeds
        elif attempt < max_retries - 1:
            print(f"No seeds yet (attempt {attempt+1}/{max_retries}), retrying in {retry_delay}s...")
            time.sleep(retry_delay)

    print(f"No seeds after {max_retries} attempts — using random initialization")
    return seeds

# ══════════════════════════════════════════════════════════
# PUSH-BACK: Send best Kaggle individual to S10 island (Fix 1)
# ══════════════════════════════════════════════════════════

S10_URL = "https://nomos42-nba-quant.hf.space"

def push_best_to_s10(best_ind, best_brier, iteration):
    """Push the Kaggle session's best individual to S10 via /api/config.
    This closes the GPU→island feedback loop so CPU evolution benefits from
    GPU-found hyperparams and feature sets immediately.
    Gracefully handles sleeping/restarting spaces."""
    import urllib.request, ssl

    features = [int(i) for i in np.where(best_ind["mask"])[0]]
    hp = best_ind.get("hp", {})

    # Save result JSON for manual download from Kaggle output
    result = {
        "best_brier": best_brier,
        "features": features,
        "n_features": len(features),
        "model_type": best_ind.get("model_type", "xgboost"),
        "hp": hp,
        "iteration": iteration,
        "source": "kaggle-karpathy",
        "timestamp": datetime.now().isoformat(),
    }
    RESULTS_FILE.write_text(json.dumps(result, indent=2))
    print(f"[PUSH] Saved best result to {RESULTS_FILE}")

    # POST to S10 /api/config — inject the best GA params as seeds
    # /api/config accepts: mutation_rate, target_features, crossover_rate, etc.
    # We use target_features to nudge S10 toward the winning feature count.
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    target_features = min(len(features), 150)  # cap at S10's MAX_FEATURES guard
    config_payload = json.dumps({
        "target_features": target_features,
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            f"{S10_URL}/api/config",
            data=config_payload, method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            resp_data = json.loads(resp.read())
        print(f"[PUSH] S10 /api/config updated: target_features={target_features} → {resp_data}")
    except Exception as e:
        print(f"[PUSH] S10 /api/config failed (space may be sleeping): {type(e).__name__}: {e}")

    # Also write to RESULTS_FILE so S10 can be manually seeded from Kaggle output
    print(f"[PUSH] GPU push-back complete — Brier={best_brier:.5f}, {len(features)}f, {best_ind.get('model_type','?')}")


# ══════════════════════════════════════════════════════════
# CELL 3: RUN THE KARPATHY LOOP
# ══════════════════════════════════════════════════════════

def run_karpathy_loop():
    """Main loop: iterate until session ends."""

    # ── ISLAND ELO load (Cycle 13) ──
    island_elo = load_island_elo()
    elo_summary = " ".join(f"{k}={int(v)}" for k, v in island_elo.items() if k != "random")
    print(f"Island Elo (resumed): {elo_summary}")

    # Load or initialize state
    state = load_state()
    if state:
        population = state["population"]
        # Backfill origin_island for legacy checkpoints (pre-Cycle 13)
        for ind in population:
            ind.setdefault("origin_island", "random")
        best_ever = state["best_ever"]
        iteration = state["iteration"]
        print(f"Resumed from iteration {iteration}, best_ever={best_ever:.5f}")
    else:
        # Initialize population with island seeds, weighted by Elo
        print("Initializing population (Elo-weighted)...")
        seeds = fetch_island_seeds()
        seeds_by_island = {}
        for s in seeds:
            seeds_by_island.setdefault(s["origin_island"], []).append(s)

        # Build weighted starter population: each island contributes
        # ~softmax(Elo)*pop_size slots, drawn (with replacement) from its
        # available seeds. Falls back to random for missing/empty islands.
        weights = softmax_island_weights(island_elo)
        pop_size = CONFIG["population_size"]
        population = []
        for isl, w in weights.items():
            n_slots = max(1, int(round(w * pop_size * 0.85)))  # leave ~15% for random/random
            pool = seeds_by_island.get(isl, [])
            if pool:
                for _ in range(n_slots):
                    src = random.choice(pool)
                    population.append({**src, "mask": src["mask"].copy(), "hp": dict(src["hp"]), "brier": 1.0,
                                       "origin_island": isl})
        # Pad with randoms if under target
        while len(population) < pop_size:
            population.append(random_individual())
        # Trim if over (rounding overshoot)
        population = population[:pop_size]
        weight_summary = " ".join(f"{k}={v:.2f}" for k, v in weights.items())
        print(f"  Elo-weighted seeds: {weight_summary} → pop={len(population)}")

        best_ever = min(ind["brier"] for ind in population if ind["brier"] < 1.0) if any(ind["brier"] < 1.0 for ind in population) else 1.0
        iteration = 0

    SESSION_LIMIT = 9 * 3600  # 9 hours
    session_start = time.time()
    stagnation_counter = 0
    last_improvement_iter = iteration

    print(f"\n{'='*70}")
    print(f"  NBA QUANT AI — KARPATHY AUTORESEARCH LOOP")
    print(f"  Pop={CONFIG['population_size']} | Budget={CONFIG['iteration_budget_sec']}s/iter")
    print(f"  ATR to beat: 0.21570 | Current best: {best_ever:.5f}")
    print(f"  Session limit: {SESSION_LIMIT/3600:.0f}h")
    print(f"{'='*70}\n")

    while time.time() - session_start < SESSION_LIMIT:
        iteration += 1
        iter_start = time.time()
        n_evals = 0
        improved = False

        # ── EVALUATE unevaluated individuals ──
        for ind in population:
            if ind["brier"] >= 0.99:
                ind["brier"] = evaluate(ind["mask"], ind["model_type"], ind["hp"])
                n_evals += 1
                if time.time() - iter_start > CONFIG["iteration_budget_sec"]:
                    break

        # ── SELECTION + REPRODUCTION ──
        # Sort by brier (lower = better)
        population.sort(key=lambda x: x["brier"])

        # ── ISLAND ELO update (Cycle 13 — autoevolve Bradley-Terry) ──
        # Run round-robin among per-island champions, then persist.
        n_matches = update_island_elo(island_elo, population)
        if n_matches > 0 and iteration % 5 == 0:
            elo_str = " ".join(f"{k}={int(v)}" for k, v in sorted(island_elo.items()) if k != "random")
            print(f"  [ISLAND ELO] {n_matches} matches | {elo_str}")

        # Check for new best
        if population[0]["brier"] < best_ever:
            best_ever = population[0]["brier"]
            improved = True
            stagnation_counter = 0
            last_improvement_iter = iteration
        else:
            stagnation_counter += 1

        # Tournament selection + offspring
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

        # ── ADAPTIVE MUTATION on stagnation ──
        if stagnation_counter >= 15:
            CONFIG["mutation_rate"] = min(0.20, CONFIG["mutation_rate"] * 1.3)
            print(f"  [STAGNATION] {stagnation_counter} iters without improvement, mutation→{CONFIG['mutation_rate']:.3f}")
        elif improved:
            CONFIG["mutation_rate"] = max(0.06, CONFIG["mutation_rate"] * 0.95)

        # ── DIVERSITY INJECTION every 20 iterations ──
        if iteration % 20 == 0:
            # Check model diversity in top 10
            top10_models = {}
            for ind in population[:10]:
                top10_models[ind["model_type"]] = top10_models.get(ind["model_type"], 0) + 1
            dominant = max(top10_models.values()) if top10_models else 0

            if dominant >= 7:  # >70% monoculture
                # Force inject 5 diverse individuals replacing worst
                inject_types = [t for t in CONFIG["model_types"]
                               if top10_models.get(t, 0) <= 1]
                if not inject_types:
                    inject_types = CONFIG["model_types"]

                for j in range(min(5, len(population) - elite_size)):
                    new_ind = random_individual()
                    new_ind["model_type"] = inject_types[j % len(inject_types)]
                    population[-(j+1)] = new_ind
                print(f"  [DIVERSITY] Injected {min(5, len(population)-elite_size)} diverse individuals (dominant={dominant}/10)")

        # ── LOG ──
        duration = time.time() - iter_start
        best_model = population[0]["model_type"]
        best_nf = int(np.sum(population[0]["mask"]))
        tag = "*** NEW BEST ***" if improved else ""

        elapsed_min = (time.time() - session_start) / 60
        rate = iteration / max(elapsed_min / 60, 0.01)
        remaining = (SESSION_LIMIT - (time.time() - session_start)) / 3600

        print(f"Iter {iteration}: best={best_ever:.5f} ({best_model}, {best_nf}f) | "
              f"{n_evals} evals {duration:.0f}s | {elapsed_min:.0f}min {rate:.0f}iter/h ~{remaining:.1f}h left {tag}")

        if iteration % 10 == 0:
            models = {}
            for ind in population[:10]:
                models[ind["model_type"]] = models.get(ind["model_type"], 0) + 1
            top5 = [(f"{ind['brier']:.5f}", ind['model_type'], int(np.sum(ind['mask'])))
                    for ind in population[:5]]
            diversity = len(models)
            pop_briers = [ind["brier"] for ind in population if ind["brier"] < 1.0]
            spread = max(pop_briers) - min(pop_briers) if len(pop_briers) > 1 else 0
            print(f"  Top10 models: {models} | Diversity: {diversity}/6 | Spread: {spread:.5f}")
            print(f"  Top5: {top5} | Stagnation: {stagnation_counter} | Mut: {CONFIG['mutation_rate']:.3f}")

        log_experiment(iteration, best_ever, n_evals, duration, improved)

        # ── CHECKPOINT every 10 iterations ──
        if iteration % 10 == 0:
            save_state({
                "population": population,
                "best_ever": best_ever,
                "iteration": iteration,
                "timestamp": datetime.now().isoformat(),
            })
            save_island_elo(island_elo, n_matches=n_matches, last_iter=iteration)
            # Also save result.json (Karpathy pattern)
            RESULTS_FILE.write_text(json.dumps({
                "best_brier": best_ever,
                "iteration": iteration,
                "model_type": population[0]["model_type"],
                "n_features": int(np.sum(population[0]["mask"])),
                "features": [int(i) for i in np.where(population[0]["mask"])[0]],
                "hp": population[0]["hp"],
                "timestamp": datetime.now().isoformat(),
            }, indent=2))

        gc.collect()

    # Final save
    save_state({
        "population": population,
        "best_ever": best_ever,
        "iteration": iteration,
        "timestamp": datetime.now().isoformat(),
    })
    save_island_elo(island_elo, n_matches=n_matches, last_iter=iteration)

    print(f"\n{'='*70}")
    print(f"  SESSION COMPLETE: {iteration} iterations, best={best_ever:.5f}")
    print(f"{'='*70}")

    # Fix 1: Push best individual back to S10 island to close GPU→CPU feedback loop
    best_ind = population[0]
    push_best_to_s10(best_ind, best_ever, iteration)

# Run!
run_karpathy_loop()
