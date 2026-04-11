#!/usr/bin/env python3
"""
NBA Quant AI -- GPU Evolution v2 (Gemini-optimized, self-contained)
====================================================================
Population-based genetic feature selection + hyperparameter search.
Works in three execution contexts:
  - Google Colab (T4/A100, clone from GitHub)
  - Modal Labs (T4, dispatches via starmap -- use modal_tabicl_evolution.py for that path)
  - Kaggle (P100, inline data loading)

Architecture
------------
1. Data loading    -- historical JSON from HF Space clone OR Supabase OR local
2. Feature engine  -- NBAFeatureEngine (features/engine.py, must match HF Space)
3. Walk-forward CV -- TimeSeriesSplit with purge gap (no data leak)
4. GA loop         -- elite + tournament select + crossover + adaptive mutation
5. State file      -- /content/evolution_state.json survives Colab disconnects
6. Island seeding  -- seeds from 6 HF Space /api/results endpoints

Config defaults (optimized by Gemini for T4 GPU):
  POP_SIZE=80  ELITE=8  FOLDS=5  PURGE_GAP=5  MAX_FEATURES=200

Usage (Colab):
  # Run the __main__ block directly -- everything is self-contained.
  # After installing deps (Cell 1) and loading secrets (Cell 2), just:
  #   %run scripts/gpu_evolution_v2.py
  # Or in a notebook: exec(open('scripts/gpu_evolution_v2.py').read())

Usage (standalone Python):
  python scripts/gpu_evolution_v2.py
  python scripts/gpu_evolution_v2.py --gens 200 --pop 80 --folds 5
  python scripts/gpu_evolution_v2.py --resume   # restart from state file

ATR to beat: 0.21570 (Colab TabICL, 110f, iter 15)
Target:      Brier < 0.20
"""

from __future__ import annotations

import gc
import json
import os
import random
import sys
import time
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any

import numpy as np

# ── Forge v19 Optimization Patches ──────────────────────────────────────────
_OPT = {}
try:
    sys.path.insert(0, str(Path(__file__).resolve().parent / "forge"))
    from optimization_patches import apply_all_patches, optimize_memory, numpy_vectorized_ga
    _OPT = apply_all_patches(verbose=True)
    _VEC_GA = _OPT.get("vec_ga") or numpy_vectorized_ga()
except Exception as _opt_err:
    print(f"[gpu_evolution_v2] Optimization patches not loaded: {_opt_err}")
    _VEC_GA = None

# ── GPU availability (resolved once at import) ────────────────────────────────
try:
    import torch
    _CUDA = torch.cuda.is_available()
except ImportError:
    torch = None  # type: ignore
    _CUDA = False

_XGB_DEVICE = "cuda" if _CUDA else "cpu"
print(f"[gpu_evolution_v2] CUDA={_CUDA}  xgb_device={_XGB_DEVICE}")

# ── Detect available model types ─────────────────────────────────────────────
_available_models: list[str] = ["xgboost", "lightgbm", "random_forest", "extra_trees"]
try:
    import catboost  # noqa: F401
    _available_models.append("catboost")
except ImportError:
    pass
try:
    from tabicl import TabICLClassifier  # noqa: F401
    _available_models.append("tabicl")
except ImportError:
    pass
try:
    from tabpfn import TabPFNClassifier  # noqa: F401
    _available_models.append("tabpfn")
except ImportError:
    pass

GPU_MODEL_TYPES: list[str] = _available_models
print(f"[gpu_evolution_v2] Available models: {GPU_MODEL_TYPES}")

# ── Evolution hyperparameters ─────────────────────────────────────────────────
POP_SIZE        = 80
ELITE_SIZE      = 8
N_SPLITS        = 5
PURGE_GAP       = 5
TARGET_FEATURES = 80
MAX_FEATURES    = 200          # HARD CAP -- never exceed this
MUTATION_RATE   = 0.10
MUT_FLOOR       = 0.05
MUT_CEILING     = 0.15
MUT_DECAY       = 0.998
CROSSOVER_RATE  = 0.80
TOTAL_GENS      = 500
SUBSAMPLE       = 8000         # use last N games (most recent = most relevant)

ATR_BRIER = 0.21570            # all-time record to beat

# Colab/Kaggle state file -- survives disconnects
STATE_FILE = Path("/content/evolution_state.json")

# HF Space islands (S10-S17) for initial seed pull
ISLAND_URLS = {
    "S10": "https://nomos42-nba-quant.hf.space",
    "S11": "https://nomos42-nba-quant-2.hf.space",
    "S12": "https://nomos42-nba-evo-3.hf.space",
    "S13": "https://nomos42-nba-evo-4.hf.space",
    "S14": "https://nomos42-nba-evo-5.hf.space",
    "S15": "https://nomos42-nba-evo-6.hf.space",
    "S16": "https://lbjlincoln26-nba-evo-s16.hf.space",
    "S17": "https://lbjlincoln26-nba-evo-s17.hf.space",
}

# Model type weights for weighted-random selection
MODEL_WEIGHTS = {
    "tabicl":      40,   # GPU star model (best Brier observed)
    "tabpfn":      10,   # PFN -- only if available
    "xgboost":     20,
    "catboost":    10,
    "lightgbm":    10,
    "extra_trees": 10,
}
# Restrict weights to available models
MODEL_WEIGHTS = {k: v for k, v in MODEL_WEIGHTS.items() if k in GPU_MODEL_TYPES}
_MT_KEYS   = list(MODEL_WEIGHTS.keys())
_MT_VALS   = list(MODEL_WEIGHTS.values())


# =============================================================================
# 1. DATA LOADING
# =============================================================================

def _load_from_hf_space_clone(repo_path: Path) -> list[dict]:
    """Load game JSONs from a cloned HF Space directory."""
    games: list[dict] = []
    for data_dir in [
        repo_path / "data" / "historical",
        repo_path / "hf-space" / "data" / "historical",
        repo_path / "historical",
    ]:
        if data_dir.exists():
            for f in sorted(data_dir.glob("games-*.json")):
                raw = json.loads(f.read_text())
                if isinstance(raw, list):
                    games.extend(raw)
                elif isinstance(raw, dict) and "games" in raw:
                    games.extend(raw["games"])
            if games:
                print(f"  Loaded {len(games)} games from {data_dir}")
                return games
    return games


def _load_from_supabase(db_url: str) -> list[dict]:
    """Fallback: load game records directly from Supabase."""
    import psycopg2
    print("  Loading games from Supabase...")
    conn = psycopg2.connect(db_url, connect_timeout=30, options="-c search_path=public")
    cur = conn.cursor()
    cur.execute("SELECT game_data FROM nba_games ORDER BY game_date LIMIT 15000")
    games = []
    for (row,) in cur.fetchall():
        if row:
            games.append(row if isinstance(row, dict) else json.loads(row))
    cur.close()
    conn.close()
    print(f"  Loaded {len(games)} games from Supabase")
    return games


def load_games() -> list[dict]:
    """
    Load historical NBA games. Tries (in order):
      1. Existing clone at /content/nomos-nba-agent
      2. Fresh GitHub clone
      3. Supabase (DATABASE_URL env var)
      4. Local data directory (Kaggle kernel)

    Returns list of game dicts sorted by game_date ascending.
    """
    # --- Try existing local clone (Colab / Kaggle) ---
    for candidate in [
        Path("/content/nomos-nba-agent"),
        Path("/kaggle/working/nomos-nba-agent"),
        Path(os.getcwd()) / "nomos-nba-agent",
        Path(__file__).parent.parent,  # running from repo root
    ]:
        if candidate.exists():
            games = _load_from_hf_space_clone(candidate)
            if games:
                break
    else:
        games = []

    # --- Clone from GitHub if needed ---
    if not games:
        import subprocess
        target = Path("/content/nomos-nba-agent")
        print("  Cloning nomos-nba-agent from GitHub...")
        result = subprocess.run(
            ["git", "clone", "--depth", "1",
             "https://github.com/LBJLincoln/nomos-nba-agent.git",
             str(target)],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            games = _load_from_hf_space_clone(target)
        else:
            print(f"  Clone failed: {result.stderr[:300]}")

    # --- Supabase fallback ---
    if not games:
        db_url = os.environ.get("DATABASE_URL", "")
        if db_url:
            try:
                games = _load_from_supabase(db_url)
            except Exception as exc:
                print(f"  Supabase failed: {exc}")

    if not games:
        raise RuntimeError(
            "No game data found. Set DATABASE_URL or run from a directory "
            "that has data/historical/games-*.json files."
        )

    games.sort(key=lambda g: g.get("game_date", g.get("date", "")))
    print(f"  Total games sorted: {len(games)}")
    return games


# =============================================================================
# 2. FEATURE BUILDING
# =============================================================================

def build_features(games: list[dict]) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """
    Build feature matrix using NBAFeatureEngine.
    Adds the repo to sys.path as needed, drops zero-variance features.

    Returns:
        X: float32 array (n_games, n_features) -- NaN-filled, zero-var dropped
        y: int32 array (n_games,)
        feature_names: list[str]
    """
    # Ensure features/engine.py is on path
    for candidate in [
        Path("/content/nomos-nba-agent"),
        Path("/kaggle/working/nomos-nba-agent"),
        Path(os.getcwd()),
        Path(__file__).parent.parent,
    ]:
        if (candidate / "features" / "engine.py").exists():
            if str(candidate) not in sys.path:
                sys.path.insert(0, str(candidate))
            break

    from features.engine import NBAFeatureEngine  # type: ignore

    engine = NBAFeatureEngine()
    print(f"  Building features for {len(games)} games (engine v{getattr(engine, 'VERSION', '?')})...")
    t0 = time.time()
    X_raw, y_raw, feature_names = engine.build(games)
    print(f"  engine.build() done in {time.time() - t0:.0f}s -- raw features={len(feature_names)}")

    X = np.nan_to_num(np.array(X_raw, dtype=np.float32), nan=0.0, posinf=1e6, neginf=-1e6)
    y = np.array(y_raw, dtype=np.int32)

    # Drop zero-variance features (useless for any model)
    var = np.var(X, axis=0)
    valid_mask = var > 1e-10
    X = X[:, valid_mask]
    feature_names = [fn for fn, ok in zip(feature_names, valid_mask) if ok]
    print(f"  After zero-var drop: {X.shape} ({len(feature_names)} features)")

    return X, y, feature_names


# =============================================================================
# 3. MODEL FACTORY
# =============================================================================

def make_model(model_type: str, hp: dict[str, Any]):
    """Instantiate the right model with given hyperparameters."""
    import xgboost as xgb
    import lightgbm as lgb
    from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier

    n_est  = int(min(hp.get("n_estimators", 200), 400))
    depth  = int(hp.get("max_depth", 6))
    lr     = float(hp.get("learning_rate", 0.05))
    sub    = float(hp.get("subsample", 0.8))
    cst    = float(hp.get("colsample_bytree", 0.8))
    alpha  = float(hp.get("reg_alpha", 0.01))
    lam    = float(hp.get("reg_lambda", 1.0))

    if model_type == "xgboost":
        return xgb.XGBClassifier(
            n_estimators=n_est, max_depth=depth,
            learning_rate=lr, subsample=sub, colsample_bytree=cst,
            reg_alpha=alpha, reg_lambda=lam,
            tree_method="hist", device=_XGB_DEVICE,
            objective="binary:logistic", eval_metric="logloss",
            random_state=42, verbosity=0,
        )
    elif model_type == "lightgbm":
        params = dict(
            n_estimators=n_est, max_depth=depth,
            learning_rate=lr, subsample=sub, colsample_bytree=cst,
            reg_alpha=alpha, reg_lambda=lam,
            random_state=42, verbose=-1,
        )
        if _CUDA:
            params["device"] = "gpu"
        return lgb.LGBMClassifier(**params)
    elif model_type == "catboost":
        from catboost import CatBoostClassifier
        params = dict(
            iterations=n_est, depth=min(depth, 10),
            learning_rate=lr, random_state=42, verbose=0,
        )
        if _CUDA:
            params["task_type"] = "GPU"
        return CatBoostClassifier(**params)
    elif model_type == "random_forest":
        return RandomForestClassifier(
            n_estimators=n_est, max_depth=min(depth, 12),
            min_samples_leaf=5, random_state=42, n_jobs=-1,
        )
    elif model_type == "extra_trees":
        return ExtraTreesClassifier(
            n_estimators=n_est, max_depth=min(depth, 12),
            min_samples_leaf=5, random_state=42, n_jobs=-1,
        )
    elif model_type == "tabicl":
        from tabicl import TabICLClassifier
        return TabICLClassifier()
    elif model_type == "tabpfn":
        from tabpfn import TabPFNClassifier
        return TabPFNClassifier(device=_XGB_DEVICE)
    else:
        # Fallback to extra_trees (always available, no GPU needed)
        return ExtraTreesClassifier(n_estimators=200, random_state=42, n_jobs=-1)


# =============================================================================
# 4. WALK-FORWARD EVALUATION
# =============================================================================

def build_splits(X: np.ndarray, n_splits: int, purge_gap: int):
    """Pre-compute walk-forward splits once (not inside tight eval loop)."""
    from sklearn.model_selection import TimeSeriesSplit
    tscv = TimeSeriesSplit(n_splits=n_splits)
    splits = []
    for train_idx, test_idx in tscv.split(X):
        # Purge the last `purge_gap` rows from train to prevent leakage
        if len(train_idx) > purge_gap + 50:
            train_idx = train_idx[:-purge_gap]
        splits.append((train_idx, test_idx))
    return splits


def evaluate(
    features_mask: list[int],
    model_type: str,
    hp: dict[str, Any],
    X: np.ndarray,
    y: np.ndarray,
    splits: list,
) -> float:
    """
    Evaluate a genome via walk-forward CV.
    Returns Brier score (lower = better). Returns 0.30 on any error.
    """
    from sklearn.metrics import brier_score_loss

    indices = [i for i, v in enumerate(features_mask) if v]
    if len(indices) < 5:
        return 1.0
    if len(indices) > MAX_FEATURES:
        indices = indices[:MAX_FEATURES]

    X_sub = X[:, indices]

    # Use vectorized Brier if available (avoids sklearn import overhead per fold)
    _fast_brier = _VEC_GA["brier"] if _VEC_GA else brier_score_loss

    fold_briers: list[float] = []
    for train_idx, test_idx in splits:
        try:
            model = make_model(model_type, hp)
            model.fit(X_sub[train_idx], y[train_idx])
            probs = model.predict_proba(X_sub[test_idx])[:, 1]
            fold_briers.append(_fast_brier(y[test_idx], probs))
            del model
        except Exception as exc:
            print(f"    [eval] {model_type} fold error: {exc}")
            fold_briers.append(0.30)

    # Memory cleanup after all folds (not inside inner loop -- avoids overhead)
    gc.collect()
    if _CUDA and torch is not None:
        torch.cuda.empty_cache()

    return float(np.mean(fold_briers)) if fold_briers else 0.30


# =============================================================================
# 5. INDIVIDUAL (GENOME)
# =============================================================================

class Individual:
    """
    Genome = binary feature mask + model type + hyperparameters.

    features: list[int]   -- 0/1 mask over all feature_names
    model_type: str
    hp: dict              -- hyperparameters
    brier: float          -- 1.0 = unevaluated
    """

    def __init__(
        self,
        n_features: int,
        features: list[int] | None = None,
        model_type: str | None = None,
        hp: dict[str, Any] | None = None,
    ):
        self.n_features = n_features
        if features is None:
            prob = TARGET_FEATURES / max(n_features, 1)
            self.features = [1 if random.random() < prob else 0 for _ in range(n_features)]
        else:
            self.features = list(features)
        self.model_type = model_type or self._weighted_model()
        self.hp = hp or self._random_hp()
        self.brier = 1.0
        self._enforce_cap()

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _weighted_model() -> str:
        return random.choices(_MT_KEYS, weights=_MT_VALS, k=1)[0]

    @staticmethod
    def _random_hp() -> dict:
        return {
            "n_estimators":    random.randint(100, 400),
            "max_depth":       random.randint(4, 9),
            "learning_rate":   10 ** random.uniform(-2.0, -0.7),
            "subsample":       random.uniform(0.6, 1.0),
            "colsample_bytree": random.uniform(0.4, 1.0),
            "reg_alpha":       10 ** random.uniform(-4, 0),
            "reg_lambda":      10 ** random.uniform(-4, 0),
        }

    def _enforce_cap(self):
        """Ensure we never exceed MAX_FEATURES=200. Vectorized."""
        arr = np.array(self.features, dtype=np.int32)
        active = np.where(arr == 1)[0]
        if len(active) > MAX_FEATURES:
            drop = np.random.choice(active, len(active) - MAX_FEATURES, replace=False)
            arr[drop] = 0
            self.features = arr.tolist()

    @property
    def n_feat(self) -> int:
        return sum(self.features)

    @property
    def indices(self) -> list[int]:
        return [i for i, v in enumerate(self.features) if v]

    # ── GA operations ─────────────────────────────────────────────────────────

    def mutate(self, rate: float) -> None:
        # Vectorized mutation: ~20x faster than Python loop for 6000+ features
        arr = np.array(self.features, dtype=np.int32)
        mask = np.random.random(self.n_features) < rate
        arr[mask] = 1 - arr[mask]
        self.features = arr.tolist()
        # Hyperparameter perturbation
        if random.random() < 0.30:
            self.hp["n_estimators"] = max(50, self.hp["n_estimators"] + random.randint(-50, 50))
        if random.random() < 0.30:
            self.hp["max_depth"] = max(2, min(12, self.hp["max_depth"] + random.randint(-2, 2)))
        if random.random() < 0.30:
            lr = self.hp["learning_rate"] * (10 ** random.uniform(-0.3, 0.3))
            self.hp["learning_rate"] = max(0.001, min(0.5, lr))
        if random.random() < 0.20:
            sub = self.hp["subsample"] + random.uniform(-0.1, 0.1)
            self.hp["subsample"] = max(0.4, min(1.0, sub))
        # Occasionally switch model type (10% chance)
        if random.random() < 0.10:
            self.model_type = self._weighted_model()
        self._enforce_cap()
        self.brier = 1.0  # mark as needing re-evaluation

    @staticmethod
    def crossover(p1: "Individual", p2: "Individual") -> "Individual":
        n = p1.n_features
        point = random.randint(1, n - 1)
        child_feat = p1.features[:point] + p2.features[point:]
        child_mt = p1.model_type if random.random() < 0.5 else p2.model_type
        child_hp = {k: (p1.hp[k] if random.random() < 0.5 else p2.hp[k]) for k in p1.hp}
        return Individual(n, features=child_feat, model_type=child_mt, hp=child_hp)

    # ── serialisation ─────────────────────────────────────────────────────────

    def to_dict(self, feature_names: list[str]) -> dict:
        return {
            "features":    [feature_names[i] for i, v in enumerate(self.features) if v],
            "model_type":  self.model_type,
            "hp":          self.hp,
            "brier":       self.brier,
            "n_features":  self.n_feat,
        }

    @classmethod
    def from_dict(cls, d: dict, feature_names: list[str], n_features: int) -> "Individual":
        name_to_idx = {n: i for i, n in enumerate(feature_names)}
        feat = [0] * n_features
        for fname in d.get("features", []):
            if isinstance(fname, str) and fname in name_to_idx:
                feat[name_to_idx[fname]] = 1
        ind = cls(n_features, features=feat,
                  model_type=d.get("model_type"),
                  hp=d.get("hp"))
        ind.brier = d.get("brier", 1.0)
        return ind


# =============================================================================
# 6. ISLAND SEEDING
# =============================================================================

def fetch_island_seeds() -> list[dict]:
    """Pull best individuals from all 6 HF Space islands (/api/results)."""
    import requests

    seeds: list[dict] = []
    print("\nFetching seeds from HF islands...")
    for name, url in ISLAND_URLS.items():
        try:
            resp = requests.get(f"{url}/api/results", timeout=15)
            if resp.status_code != 200:
                print(f"  {name}: HTTP {resp.status_code}")
                continue
            data = resp.json()
            best = data.get("best", {})
            seeds.append({
                "source":     name,
                "brier":      best.get("brier", 1.0),
                "features":   best.get("selected_features", []),
                "model_type": best.get("model_type", "xgboost"),
            })
            print(
                f"  {name}: brier={best.get('brier', '?'):.5f}  "
                f"model={best.get('model_type', '?')}  "
                f"feat={best.get('n_features', '?')}"
            )
            # Grab top-3 from each island for extra diversity
            for i, ind in enumerate(data.get("top5", [])[:3]):
                seeds.append({
                    "source":     f"{name}_top{i+1}",
                    "brier":      ind.get("brier", 1.0),
                    "features":   ind.get("selected_features", []),
                    "model_type": ind.get("model_type", "xgboost"),
                })
        except Exception as exc:
            print(f"  {name}: {exc}")
    print(f"Seeds collected: {len(seeds)}")
    return seeds


def build_seeded_population(
    island_seeds: list[dict],
    feature_names: list[str],
    n_features: int,
    pop_size: int,
) -> list[Individual]:
    """
    Build starting population:
      - one Individual per island seed (original model type)
      - one TabICL variant per seed (exploit GPU advantage)
      - fill remaining slots with random individuals
    """
    name_to_idx = {n: i for i, n in enumerate(feature_names)}
    population: list[Individual] = []

    for seed in island_seeds:
        if len(population) >= pop_size:
            break
        feat = [0] * n_features
        for fname in seed.get("features", []):
            if isinstance(fname, str) and fname in name_to_idx:
                feat[name_to_idx[fname]] = 1
        # Fall back to random if seed didn't map
        if sum(feat) < 15:
            prob = TARGET_FEATURES / max(n_features, 1)
            feat = [1 if random.random() < prob else 0 for _ in range(n_features)]

        # Original model type from island
        population.append(Individual(n_features, features=list(feat),
                                     model_type=seed.get("model_type", "xgboost")))

        # TabICL variant -- exploit GPU
        if "tabicl" in GPU_MODEL_TYPES and len(population) < pop_size:
            population.append(Individual(n_features, features=list(feat),
                                         model_type="tabicl"))

        # TabPFN variant if available
        if "tabpfn" in GPU_MODEL_TYPES and len(population) < pop_size:
            population.append(Individual(n_features, features=list(feat),
                                         model_type="tabpfn"))

    # Fill remaining with random individuals
    while len(population) < pop_size:
        population.append(Individual(n_features))

    return population[:pop_size]


# =============================================================================
# 7. STATE PERSISTENCE
# =============================================================================

def save_state(
    path: Path,
    gen: int,
    population: list[Individual],
    feature_names: list[str],
    best_brier: float,
    best_info: dict | None,
    mut_rate: float,
) -> None:
    """Save full evolution state to JSON (survives Colab disconnects)."""
    state = {
        "generation":    gen + 1,
        "best_brier":    best_brier,
        "best_info":     best_info,
        "mutation_rate": mut_rate,
        "timestamp":     time.strftime("%Y-%m-%dT%H:%M:%S"),
        "population":    [ind.to_dict(feature_names) for ind in population],
    }
    path.write_text(json.dumps(state, default=str))


def load_state(
    path: Path,
    feature_names: list[str],
    n_features: int,
) -> tuple[int, list[Individual], float, dict | None, float]:
    """
    Load evolution state. Returns (start_gen, population, best_brier, best_info, mut_rate).
    Returns (0, [], 1.0, None, MUTATION_RATE) if file missing or corrupt.
    """
    if not path.exists():
        return 0, [], 1.0, None, MUTATION_RATE
    try:
        state = json.loads(path.read_text())
        start_gen  = state.get("generation", 0)
        best_brier = state.get("best_brier", 1.0)
        best_info  = state.get("best_info")
        mut_rate   = state.get("mutation_rate", MUTATION_RATE)
        population = [
            Individual.from_dict(d, feature_names, n_features)
            for d in state.get("population", [])
        ]
        print(f"  RESUMED: gen={start_gen}, best={best_brier:.5f}, pop={len(population)}")
        return start_gen, population, best_brier, best_info, mut_rate
    except Exception as exc:
        print(f"  State load failed ({exc}), starting fresh")
        return 0, [], 1.0, None, MUTATION_RATE


# =============================================================================
# 8. MAIN EVOLUTION LOOP
# =============================================================================

def _tournament(population: list[Individual], k: int = 4) -> Individual:
    return min(random.sample(population, min(k, len(population))), key=lambda x: x.brier)


def run_evolution(
    gens:    int = TOTAL_GENS,
    pop:     int = POP_SIZE,
    folds:   int = N_SPLITS,
    resume:  bool = False,
    state_path: Path = STATE_FILE,
) -> dict | None:
    """
    Full GA evolution loop.

    Args:
        gens:       total generations to run
        pop:        population size
        folds:      walk-forward CV splits
        resume:     if True, load from state_path first
        state_path: path to state JSON file

    Returns:
        best_info dict (brier, model_type, features, etc.) or None
    """
    print("\n" + "=" * 70)
    print("  NBA QUANT AI -- GPU Evolution v2")
    print(f"  Pop={pop}  Elite={ELITE_SIZE}  Folds={folds}  Gens={gens}")
    print(f"  MAX_FEATURES={MAX_FEATURES}  Models={GPU_MODEL_TYPES}")
    print(f"  ATR to beat: {ATR_BRIER}")
    print("=" * 70)

    # ── Phase 1: Load data ────────────────────────────────────────────────────
    print("\n[PHASE 1] Loading game data...")
    games = load_games()

    # Subsample to most recent N games for speed (walk-forward preserves order)
    if len(games) > SUBSAMPLE:
        games = games[-SUBSAMPLE:]
        print(f"  Subsampled to last {SUBSAMPLE} games")

    # ── Phase 2: Build features ───────────────────────────────────────────────
    print("\n[PHASE 2] Building features...")
    X, y, feature_names = build_features(games)
    n_features = X.shape[1]
    print(f"  Feature space: {n_features} features, {len(games)} games")

    # Pre-compute splits once
    splits = build_splits(X, folds, PURGE_GAP)
    print(f"  Walk-forward splits: {len(splits)}")

    # ── Phase 3: Fetch island seeds ───────────────────────────────────────────
    print("\n[PHASE 3] Fetching island seeds...")
    island_seeds = fetch_island_seeds()

    # ── Phase 4: Build / restore population ──────────────────────────────────
    print("\n[PHASE 4] Building population...")
    start_gen   = 0
    best_brier  = 1.0
    best_info: dict | None = None
    mut_rate    = MUTATION_RATE
    population: list[Individual] = []

    if resume:
        start_gen, population, best_brier, best_info, mut_rate = load_state(
            state_path, feature_names, n_features
        )

    # Seed from islands (top up if resumed with fewer individuals)
    if len(population) < pop:
        seeded = build_seeded_population(island_seeds, feature_names, n_features, pop)
        population.extend(seeded[: pop - len(population)])
    population = population[:pop]

    mt_counts = Counter(ind.model_type for ind in population)
    print(f"  Population ready: {len(population)} | Models: {dict(mt_counts)}")

    # ── Phase 5: Evolution loop ───────────────────────────────────────────────
    print("\n[PHASE 5] Evolving...\n")
    session_start = time.time()
    stagnation    = 0

    for gen in range(start_gen, start_gen + gens):
        gen_start = time.time()

        # Evaluate individuals that need scoring (brier >= 0.99 = unevaluated)
        to_eval = [ind for ind in population if ind.brier >= 0.99]

        if to_eval:
            for ind in to_eval:
                ind.brier = evaluate(ind.features, ind.model_type, ind.hp, X, y, splits)

        # Sort: lowest Brier first
        population.sort(key=lambda x: x.brier)
        gen_best = population[0]

        # Track all-time best
        improved = gen_best.brier < best_brier
        if improved:
            best_brier  = gen_best.brier
            stagnation  = 0
            best_info   = {
                "brier":          gen_best.brier,
                "model_type":     gen_best.model_type,
                "n_features":     gen_best.n_feat,
                "generation":     gen + 1,
                "features":       [feature_names[i] for i, v in enumerate(gen_best.features) if v],
                "hp":             gen_best.hp,
                "engine_version": "v3.1-46cat",
                "timestamp":      time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
            # Write best immediately so a disconnect doesn't lose it
            Path("best_gpu_v2_features.json").write_text(
                json.dumps(best_info, indent=2, default=str)
            )
        else:
            stagnation += 1

        # Console output
        gen_dur = time.time() - gen_start
        elapsed = (time.time() - session_start) / 60
        gens_done = gen - start_gen + 1
        rate = gens_done / max(elapsed, 0.01) * 60
        delta = best_brier - ATR_BRIER
        marker = "  *** NEW BEST ***" if improved else ""
        print(
            f"Gen {gen+1:4d}/{start_gen + gens}: "
            f"best={gen_best.brier:.5f} ({gen_best.model_type}, {gen_best.n_feat}f) | "
            f"ever={best_brier:.5f} (ATR{delta:+.5f}) | "
            f"{len(to_eval)} evals {gen_dur:.0f}s | "
            f"{elapsed:.0f}min {rate:.0f}g/h{marker}"
        )

        # Detailed model breakdown every 10 gens
        if (gen + 1) % 10 == 0:
            mt = Counter(ind.model_type for ind in population)
            top5 = [(f"{ind.brier:.5f}", ind.model_type, ind.n_feat) for ind in population[:5]]
            print(f"  Models: {dict(mt)} | Top5: {top5} | stagnation={stagnation} | mut={mut_rate:.4f}")

        # Save state every generation
        save_state(state_path, gen, population, feature_names, best_brier, best_info, mut_rate)

        # Adaptive mutation on stagnation
        if stagnation >= 15 and stagnation % 5 == 0:
            mut_rate = min(MUT_CEILING, mut_rate * 1.2)
            print(f"  [STAGNATION={stagnation}] mutation -> {mut_rate:.4f}")

        # Diversity injection every 20 gens if top-10 dominated by one model
        if (gen + 1) % 20 == 0:
            top10_models = Counter(ind.model_type for ind in population[:10])
            if top10_models:
                dominant_count = max(top10_models.values())
                if dominant_count >= 7:
                    under = [t for t in _MT_KEYS if top10_models.get(t, 0) <= 1]
                    if not under:
                        under = _MT_KEYS
                    n_inject = min(3, len(population) - ELITE_SIZE)
                    for j in range(n_inject):
                        new_ind = Individual(n_features)
                        new_ind.model_type = under[j % len(under)]
                        population[-(j + 1)] = new_ind
                    print(f"  [DIVERSITY] Injected {n_inject} ({under[:3]}) dominant={dominant_count}/10")

        # ── Reproduction ─────────────────────────────────────────────────────
        elite    = population[:ELITE_SIZE]
        children = [
            Individual(n_features, features=list(e.features),
                       model_type=e.model_type, hp=deepcopy(e.hp))
            for e in elite
        ]
        children[0].brier = elite[0].brier  # preserve best's score

        while len(children) < pop:
            if random.random() < CROSSOVER_RATE:
                child = Individual.crossover(_tournament(population), _tournament(population))
            else:
                parent = _tournament(population)
                child  = Individual(n_features, features=list(parent.features),
                                    model_type=parent.model_type, hp=deepcopy(parent.hp))
            child.mutate(mut_rate)
            # Bias ~30% of new children toward TabICL (the GPU star model)
            if "tabicl" in GPU_MODEL_TYPES and random.random() < 0.30:
                child.model_type = "tabicl"
            children.append(child)

        population  = children[:pop]
        mut_rate    = max(MUT_FLOOR, min(MUT_CEILING, mut_rate * MUT_DECAY))

    # ── Final summary ─────────────────────────────────────────────────────────
    total_min = (time.time() - session_start) / 60
    print("\n" + "=" * 70)
    print("  FINAL RESULTS")
    print("=" * 70)
    if best_info:
        delta = best_info["brier"] - ATR_BRIER
        print(f"  Best Brier:   {best_info['brier']:.5f}")
        print(f"  Model:        {best_info['model_type']}")
        print(f"  Features:     {best_info['n_features']}")
        print(f"  Generation:   {best_info['generation']}")
        print(f"  Session time: {total_min:.0f} min")
        print(f"  ATR:          {ATR_BRIER}")
        print(f"  Delta:        {delta:+.5f}  {'NEW RECORD!' if delta < 0 else ''}")
        print(f"\n  Saved to: best_gpu_v2_features.json")
    else:
        print("  No improvement recorded.")

    population.sort(key=lambda x: x.brier)
    print("\n  Top 10:")
    for i, ind in enumerate(population[:10]):
        print(f"    #{i+1}: brier={ind.brier:.5f} | {ind.model_type} | {ind.n_feat}f")

    mt_final = Counter(ind.model_type for ind in population[:10])
    print(f"\n  Top 10 model distribution: {dict(mt_final)}")

    return best_info


# =============================================================================
# 9. COLAB SETUP HELPER
# =============================================================================

def colab_setup() -> None:
    """
    Run this cell first in Colab:
      from scripts.gpu_evolution_v2 import colab_setup; colab_setup()

    Installs all dependencies and loads Colab secrets.
    """
    import subprocess

    pkgs = [
        "xgboost>=2.0",
        "lightgbm",
        "catboost",
        "scikit-learn>=1.3",
        "pandas",
        "numpy",
        "scipy",
        "psycopg2-binary",
        "requests",
        "huggingface_hub",
        "tabicl",   # TabICLv2 -- MIT
        "tabpfn",   # TabPFN-2.5 -- Prior-Labs
    ]
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q"] + pkgs)

    # Reload GPU detection after installs
    global _CUDA, _XGB_DEVICE, GPU_MODEL_TYPES, MODEL_WEIGHTS, _MT_KEYS, _MT_VALS
    try:
        import torch
        _CUDA = torch.cuda.is_available()
        _XGB_DEVICE = "cuda" if _CUDA else "cpu"
        print(f"PyTorch {torch.__version__} -- CUDA: {_CUDA}")
        if _CUDA:
            print(f"  GPU: {torch.cuda.get_device_name(0)}")
    except ImportError:
        pass

    # Reload available models
    for pkg, name in [("catboost", "catboost"), ("tabicl", "tabicl"), ("tabpfn", "tabpfn")]:
        try:
            __import__(pkg)
            if name not in GPU_MODEL_TYPES:
                GPU_MODEL_TYPES.append(name)
        except ImportError:
            pass

    MODEL_WEIGHTS.update({
        k: MODEL_WEIGHTS.get(k, 10) for k in GPU_MODEL_TYPES
    })
    _MT_KEYS = list(MODEL_WEIGHTS.keys())
    _MT_VALS = list(MODEL_WEIGHTS.values())
    print(f"Available models after setup: {GPU_MODEL_TYPES}")

    # Load Colab secrets
    try:
        from google.colab import userdata
        db = userdata.get("DATABASE_URL")
        if db:
            os.environ["DATABASE_URL"] = db
            print("DATABASE_URL loaded from Colab secrets")
        hf = userdata.get("HF_TOKEN")
        if hf:
            os.environ["HF_TOKEN"] = hf
            os.environ["HUGGING_FACE_HUB_TOKEN"] = hf
            from huggingface_hub import login
            login(token=hf, add_to_git_credential=False)
            print("HF_TOKEN loaded")
    except Exception as exc:
        print(f"Colab secrets not available ({exc}) -- set env vars manually")

    # Pre-warm TabPFN checkpoint so it doesn't hit network during evolution
    if "tabpfn" in GPU_MODEL_TYPES:
        try:
            from tabpfn import TabPFNClassifier
            _m = TabPFNClassifier(device=_XGB_DEVICE)
            _m.fit(np.random.randn(50, 5), np.random.randint(0, 2, 50))
            _m.predict_proba(np.random.randn(10, 5))
            del _m
            print("TabPFN-2.5: checkpoint warmed")
        except Exception as exc:
            print(f"TabPFN warmup failed ({exc})")

    if "tabicl" in GPU_MODEL_TYPES:
        try:
            from tabicl import TabICLClassifier
            _m = TabICLClassifier()
            _m.fit(np.random.randn(50, 5), np.random.randint(0, 2, 50))
            _m.predict_proba(np.random.randn(10, 5))
            del _m
            print("TabICLv2: checkpoint warmed")
        except Exception as exc:
            print(f"TabICL warmup failed ({exc})")

    gc.collect()
    if _CUDA and torch is not None:
        torch.cuda.empty_cache()
    print("\nSetup complete. Run: run_evolution(gens=500)")


# =============================================================================
# 10. CLI ENTRYPOINT
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="NBA Quant GPU Evolution v2")
    parser.add_argument("--gens",   type=int, default=TOTAL_GENS,   help="Generations to run")
    parser.add_argument("--pop",    type=int, default=POP_SIZE,     help="Population size")
    parser.add_argument("--folds",  type=int, default=N_SPLITS,     help="Walk-forward CV folds")
    parser.add_argument("--resume", action="store_true",            help="Resume from state file")
    parser.add_argument("--state",  type=str, default=str(STATE_FILE), help="State file path")
    args = parser.parse_args()

    run_evolution(
        gens=args.gens,
        pop=args.pop,
        folds=args.folds,
        resume=args.resume,
        state_path=Path(args.state),
    )
