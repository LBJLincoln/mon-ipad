#!/usr/bin/env python3
"""
NBA Quant AI -- TabICL GPU Evolution on Modal
==============================================
Evolved from the Karpathy autoresearch pattern. Dispatches individual
evaluations to Modal T4 GPU workers in parallel via starmap.

TabICL is the star model (50% of population) -- it achieved Brier 0.22184
in initial tests and 0.21570 on Colab (ATR). Tree models provide diversity
and feature selection pressure.

Architecture:
  LOCAL (VM)                       MODAL (GPU)
  +-----------+                    +------------------+
  | Evolution |  -- starmap -->    | evaluate_individual() x N |
  | loop      |  <-- Brier ---    | T4 GPU, 120s timeout      |
  +-----------+                    +------------------+
       |
       v
  State JSON (local + Volume)

Usage:
  modal run scripts/modal_tabicl_evolution.py                    # fresh run (T4, 200 gens)
  modal run scripts/modal_tabicl_evolution.py --gens 500         # 500 generations
  modal run scripts/modal_tabicl_evolution.py --resume           # resume from local state
  modal run scripts/modal_tabicl_evolution.py --volume-resume    # resume from Modal Volume
  modal run scripts/modal_tabicl_evolution.py --rebuild-cache    # force rebuild features
  modal run scripts/modal_tabicl_evolution.py::check_status      # check evolution state

Modal free tier: $30/mo compute credits.
T4 GPU: ~$0.59/hr. Estimated cost: ~$0.50-2.00 per 200-gen run.

Target: Beat ATR 0.21570 (Colab TabICL, 110f, iter 15)
"""

from __future__ import annotations

import json
import os
import random
import time
from collections import Counter
from pathlib import Path
from typing import Any

import modal

# ── Modal app + persistent volume ────────────────────────────────────────────
app = modal.App("nba-tabicl-evolution")

# Volume persists feature cache (~50MB) + evolution state across runs
vol = modal.Volume.from_name("nba-evolution-state", create_if_missing=True)

VOLUME_MOUNT = "/data"

# ── Container images ─────────────────────────────────────────────────────────
# GPU image: TabICL + all ML deps + feature engine from HF Space
gpu_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git")
    .pip_install(
        # GPU ML
        "torch",
        "tabicl",
        # Tree models (pinned to SOTA versions, Apr 2026)
        "xgboost>=3.0",
        "lightgbm>=4.0",
        "catboost>=1.2",
        "scikit-learn>=1.5",
        # Data
        "numpy",
        "pandas",
        "scipy",
        # Utilities
        "requests",
        "huggingface_hub",
        "psycopg2-binary",
    )
)

# Lightweight CPU image for status checks
cpu_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("numpy")
)

# ── Volume paths ─────────────────────────────────────────────────────────────
CACHE_FILE = f"{VOLUME_MOUNT}/features_cache_v3_43cat.npz"
STATE_FILE = f"{VOLUME_MOUNT}/tabicl_evolution_state.json"
BEST_FILE  = f"{VOLUME_MOUNT}/best_tabicl_features.json"
LOG_FILE   = f"{VOLUME_MOUNT}/tabicl_experiment_log.jsonl"

# ── Evolution hyperparameters ────────────────────────────────────────────────
TARGET_FEATURES  = 60
MAX_FEATURES     = 200
CROSSOVER_RATE   = 0.80
MUT_FLOOR        = 0.05
MUT_CEILING      = 0.15
MUT_DECAY        = 0.998
SUBSAMPLE        = 6000
PURGE_GAP        = 5

# TabICL gets 50% weight -- the whole point of GPU evolution
MODEL_WEIGHTS = {
    "tabicl":      50,
    "xgboost":     15,
    "catboost":    10,
    "lightgbm":    10,
    "extra_trees": 15,
}

# Platform configs
PLATFORM_CONFIGS = {
    "modal_t4":   {"POP": 24, "FOLDS": 2, "GENS": 200, "ELITE": 4, "TIMEOUT": 120},
    "modal_a10g": {"POP": 40, "FOLDS": 3, "GENS": 500, "ELITE": 6, "TIMEOUT": 150},
}

# HF Space URLs for seeding
ISLANDS = {
    "S10": "https://nomos42-nba-quant.hf.space",
    "S11": "https://nomos42-nba-quant-2.hf.space",
    "S12": "https://nomos42-nba-evo-3.hf.space",
    "S13": "https://nomos42-nba-evo-4.hf.space",
    "S14": "https://nomos42-nba-evo-5.hf.space",
    "S15": "https://nomos42-nba-evo-6.hf.space",
}

ATR_BRIER = 0.21570  # Current all-time record (Colab TabICL, 110f, iter 15)


# =============================================================================
# REMOTE GPU FUNCTIONS (run on Modal T4 workers)
# =============================================================================

@app.function(
    gpu="T4",
    image=gpu_image,
    volumes={VOLUME_MOUNT: vol},
    secrets=[modal.Secret.from_name("nomos42-secrets")],
    timeout=3600,  # 60 min: 43-cat engine on 9k+ games can take 25-45 min first time
    retries=0,     # don't retry on timeout -- would double charges
)
def build_feature_cache() -> dict:
    """Build feature cache from HF Space historical data. Run once per engine version.

    Clones the HF Space (which has historical JSON + feature engine), builds
    the full feature matrix, and saves to Volume as compressed .npz.
    """
    import gc
    import json
    import subprocess
    import sys
    import time
    from pathlib import Path

    import numpy as np

    cache_path = Path(CACHE_FILE)
    if cache_path.exists():
        cached = np.load(str(cache_path), allow_pickle=True)
        shape = tuple(cached["X"].shape)
        n_feat = len(cached["feature_names"])
        print(f"Cache exists: {shape}, {n_feat} features")
        return {"cached": True, "shape": shape, "n_features": n_feat}

    print("Building features from HF Space...")
    t0 = time.time()

    # Clone from HF Space (has both engine + historical data)
    repo_dir = Path("/tmp/nba-quant-space")
    if not repo_dir.exists():
        hf_token = os.environ.get("HF_TOKEN", "")
        clone_url = f"https://user:{hf_token}@huggingface.co/spaces/Nomos42/nba-quant"
        result = subprocess.run(
            ["git", "clone", "--depth", "1", clone_url, str(repo_dir)],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"Clone failed: {result.stderr}")
            # Try alternate space
            clone_url = f"https://user:{hf_token}@huggingface.co/spaces/Nomos42/nba-quant-2"
            subprocess.run(["git", "clone", "--depth", "1", clone_url, str(repo_dir)], check=True)

    sys.path.insert(0, str(repo_dir))

    # Load games from historical JSON
    games = []
    for data_dir in [repo_dir / "data" / "historical", repo_dir / "hf-space" / "data" / "historical"]:
        if data_dir.exists():
            for f in sorted(data_dir.glob("games-*.json")):
                raw = json.loads(f.read_text())
                if isinstance(raw, list):
                    games.extend(raw)
                elif isinstance(raw, dict) and "games" in raw:
                    games.extend(raw["games"])
            if games:
                print(f"Loaded {len(games)} games from {data_dir}")
                break

    # Fallback: Supabase
    if not games:
        db_url = os.environ.get("DATABASE_URL", "")
        if db_url:
            print("Loading from Supabase...")
            import psycopg2
            conn = psycopg2.connect(db_url, connect_timeout=30, options="-c search_path=public")
            cur = conn.cursor()
            cur.execute("SELECT game_data FROM nba_games ORDER BY game_date LIMIT 15000")
            for row in cur.fetchall():
                if row[0]:
                    games.append(row[0] if isinstance(row[0], dict) else json.loads(row[0]))
            cur.close()
            conn.close()
            print(f"Loaded {len(games)} games from Supabase")

    if not games:
        raise RuntimeError("No game data found (local or Supabase). Check HF_TOKEN and DATABASE_URL secrets.")

    games.sort(key=lambda g: g.get("game_date", g.get("date", "")))
    print(f"Sorted {len(games)} games. Importing feature engine...")

    from features.engine import NBAFeatureEngine
    engine = NBAFeatureEngine()
    print(f"Engine loaded. Building {len(games)} games (v3.0-43cat)...")
    t_build = time.time()
    X_raw, y_raw, feature_names = engine.build(games)
    print(f"engine.build() done in {time.time() - t_build:.0f}s, raw features={len(feature_names)}")

    X = np.nan_to_num(np.array(X_raw, dtype=np.float32))
    y = np.array(y_raw, dtype=np.int32)

    # Drop zero-variance features
    variances = np.var(X, axis=0)
    valid = variances > 1e-10
    X = X[:, valid]
    feature_names = [fn for fn, v in zip(feature_names, valid) if v]

    # Save to Volume
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(str(cache_path), X=X, y=y, feature_names=np.array(feature_names))
    vol.commit()

    elapsed = time.time() - t0
    print(f"Cache built: {X.shape} in {elapsed:.0f}s")
    gc.collect()
    return {"cached": False, "shape": tuple(X.shape), "n_features": len(feature_names), "elapsed_sec": elapsed}


@app.function(
    image=cpu_image,
    volumes={VOLUME_MOUNT: vol},
    timeout=60,
)
def get_feature_names() -> tuple[list[str], int]:
    """Return (feature_names, n_rows) from cached feature matrix. CPU-only."""
    import numpy as np
    vol.reload()
    cached = np.load(CACHE_FILE, allow_pickle=True)
    return cached["feature_names"].tolist(), int(cached["X"].shape[0])


@app.function(
    gpu="T4",
    image=gpu_image,
    volumes={VOLUME_MOUNT: vol},
    timeout=300,
    retries=0,  # bad genome should stay penalized, not rerun
)
def evaluate_individual(
    features_indices: list[int],
    model_type: str,
    hp: dict[str, Any],
    n_features_total: int,
    n_folds: int = 2,
) -> float:
    """Evaluate one individual on T4 GPU. Returns Brier score (lower = better).

    This is the hot path -- called POP_SIZE times per generation via starmap.
    Each call gets its own GPU worker with per-second billing.
    """
    import gc
    import signal
    import sys
    from pathlib import Path

    import numpy as np
    from sklearn.metrics import brier_score_loss
    from sklearn.model_selection import TimeSeriesSplit

    # Load feature cache from Volume
    cache_path = Path(CACHE_FILE)
    if not cache_path.exists():
        vol.reload()
        if not cache_path.exists():
            raise RuntimeError("Feature cache missing. Run build_feature_cache() first.")

    cached = np.load(str(cache_path), allow_pickle=True)
    X_full = cached["X"]
    y_full = cached["y"]

    # Subsample: last N games (more recent = more relevant)
    if X_full.shape[0] > SUBSAMPLE:
        X = X_full[-SUBSAMPLE:]
        y = y_full[-SUBSAMPLE:]
    else:
        X = X_full
        y = y_full

    # Guard rails
    if len(features_indices) < 5:
        return 1.0
    indices = features_indices[:MAX_FEATURES]
    X_sub = X[:, indices].astype(np.float32)

    # Walk-forward splits with purge gap
    tscv = TimeSeriesSplit(n_splits=n_folds)
    splits = [
        (tr[:-PURGE_GAP] if len(tr) > PURGE_GAP + 50 else tr, te)
        for tr, te in tscv.split(X)
    ]

    # Model factory
    import torch
    _xgb_device = "cuda" if torch.cuda.is_available() else "cpu"

    def make_model(mtype, params):
        import xgboost as xgb
        import lightgbm as lgb
        from sklearn.ensemble import ExtraTreesClassifier

        n_est = min(params.get("n_estimators", 200), 300)
        depth = params.get("max_depth", 6)
        lr = params.get("learning_rate", 0.05)
        sub = params.get("subsample", 0.8)
        cst = params.get("colsample_bytree", 0.8)

        if mtype == "tabicl":
            from tabicl import TabICLClassifier
            return TabICLClassifier()
        elif mtype == "xgboost":
            return xgb.XGBClassifier(
                n_estimators=n_est, max_depth=depth,
                learning_rate=lr, subsample=sub, colsample_bytree=cst,
                tree_method="hist", device=_xgb_device,
                random_state=42, verbosity=0,
                objective="binary:logistic", eval_metric="logloss",
            )
        elif mtype == "lightgbm":
            return lgb.LGBMClassifier(
                n_estimators=n_est, max_depth=depth,
                learning_rate=lr, subsample=sub, colsample_bytree=cst,
                random_state=42, verbose=-1,
            )
        elif mtype == "catboost":
            from catboost import CatBoostClassifier
            return CatBoostClassifier(
                iterations=n_est, depth=min(depth, 10),
                learning_rate=lr, random_state=42, verbose=0,
            )
        elif mtype == "extra_trees":
            return ExtraTreesClassifier(
                n_estimators=n_est, max_depth=min(depth, 12),
                min_samples_leaf=5, random_state=42, n_jobs=-1,
            )
        else:
            return ExtraTreesClassifier(n_estimators=200, random_state=42, n_jobs=-1)

    # Timeout via SIGALRM
    class _Timeout(Exception):
        pass

    def _handler(sig, frame):
        raise _Timeout()

    eval_timeout = int(hp.get("_timeout", 120))
    old_handler = signal.signal(signal.SIGALRM, _handler)
    signal.alarm(eval_timeout)

    try:
        fold_briers = []
        for train_idx, test_idx in splits:
            model = make_model(model_type, hp)
            model.fit(X_sub[train_idx], y[train_idx])
            probs = model.predict_proba(X_sub[test_idx])[:, 1]
            fold_briers.append(brier_score_loss(y[test_idx], probs))
            del model

        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        return float(np.mean(fold_briers))

    except _Timeout:
        signal.signal(signal.SIGALRM, old_handler)
        gc.collect()
        return 0.30  # timeout penalty

    except Exception as exc:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)
        print(f"Eval error ({model_type}, {len(indices)}f): {exc}")
        return 0.30


@app.function(
    image=cpu_image,
    volumes={VOLUME_MOUNT: vol},
    timeout=60,
)
def upload_state_to_volume(state_json: str, best_json: str) -> None:
    """Write state + best JSON to Modal Volume for crash recovery."""
    from pathlib import Path
    Path(STATE_FILE).write_text(state_json)
    if best_json:
        Path(BEST_FILE).write_text(best_json)
    vol.commit()
    print("Volume checkpoint saved.")


@app.function(
    image=cpu_image,
    volumes={VOLUME_MOUNT: vol},
    timeout=30,
)
def download_state_from_volume() -> tuple[str, str]:
    """Return (state_json, best_json) from Volume for cross-machine resume."""
    from pathlib import Path
    vol.reload()
    state_json = Path(STATE_FILE).read_text() if Path(STATE_FILE).exists() else ""
    best_json = Path(BEST_FILE).read_text() if Path(BEST_FILE).exists() else ""
    return state_json, best_json


# =============================================================================
# LOCAL HELPERS (run on the VM that executes `modal run`)
# =============================================================================

def _weighted_model_type() -> str:
    types = list(MODEL_WEIGHTS.keys())
    weights = list(MODEL_WEIGHTS.values())
    return random.choices(types, weights=weights, k=1)[0]


def _random_hp() -> dict:
    return {
        "n_estimators": random.randint(100, 300),
        "max_depth": random.randint(4, 9),
        "learning_rate": 10 ** random.uniform(-2.0, -0.7),
        "subsample": random.uniform(0.6, 1.0),
        "colsample_bytree": random.uniform(0.4, 1.0),
    }


class Individual:
    """Genome = binary feature mask + model type + hyperparameters."""

    def __init__(self, n_features, features=None, model_type=None, hp=None):
        self.n_features = n_features
        if features is None:
            prob = TARGET_FEATURES / max(n_features, 1)
            self.features = [1 if random.random() < prob else 0 for _ in range(n_features)]
        else:
            self.features = list(features)
        self.model_type = model_type or _weighted_model_type()
        self.hp = hp or _random_hp()
        self.brier = 1.0
        self._enforce_cap()

    @property
    def indices(self):
        return [i for i, v in enumerate(self.features) if v]

    @property
    def n_feat(self):
        return sum(self.features)

    def _enforce_cap(self):
        idx = self.indices
        if len(idx) > MAX_FEATURES:
            for i in random.sample(idx, len(idx) - MAX_FEATURES):
                self.features[i] = 0

    def mutate(self, rate):
        for i in range(self.n_features):
            if random.random() < rate:
                self.features[i] = 1 - self.features[i]
        if random.random() < 0.25:
            self.hp["n_estimators"] = max(50, min(300, self.hp["n_estimators"] + random.randint(-50, 50)))
        if random.random() < 0.25:
            self.hp["max_depth"] = max(2, min(10, self.hp["max_depth"] + random.randint(-2, 2)))
        if random.random() < 0.25:
            self.hp["learning_rate"] = max(0.001, min(0.3, self.hp["learning_rate"] * 10 ** random.uniform(-0.3, 0.3)))
        if random.random() < 0.08:
            self.model_type = _weighted_model_type()
        self._enforce_cap()
        self.brier = 1.0

    @staticmethod
    def crossover(p1, p2):
        n = p1.n_features
        point = random.randint(1, n - 1)
        child_feat = p1.features[:point] + p2.features[point:]
        child_mt = p1.model_type if random.random() < 0.5 else p2.model_type
        child_hp = {k: p1.hp[k] if random.random() < 0.5 else p2.hp[k] for k in p1.hp}
        return Individual(n, features=child_feat, model_type=child_mt, hp=child_hp)

    def to_dict(self, feature_names):
        return {
            "features": [feature_names[i] for i, v in enumerate(self.features) if v],
            "model_type": self.model_type,
            "hp": self.hp,
            "brier": self.brier,
        }

    @classmethod
    def from_dict(cls, d, feature_names, n_features):
        name_to_idx = {n: i for i, n in enumerate(feature_names)}
        feat = [0] * n_features
        for fname in d.get("features", []):
            if isinstance(fname, str) and fname in name_to_idx:
                feat[name_to_idx[fname]] = 1
        ind = cls(n_features, features=feat, model_type=d.get("model_type"), hp=d.get("hp"))
        ind.brier = d.get("brier", 1.0)
        return ind


def _tournament(pop, k=4):
    return min(random.sample(pop, min(k, len(pop))), key=lambda x: x.brier)


def _fetch_island_seeds():
    """Pull best individuals from all 6 HF Spaces."""
    import requests

    seeds = []
    print("\nFetching seeds from HF islands...")
    for name, url in ISLANDS.items():
        try:
            resp = requests.get(f"{url}/api/results", timeout=10)
            if resp.status_code != 200:
                print(f"  {name}: HTTP {resp.status_code}")
                continue
            data = resp.json()
            best = data.get("best", {})
            seeds.append({
                "source": name,
                "brier": best.get("brier", 1.0),
                "features": best.get("selected_features", []),
                "model_type": best.get("model_type", "xgboost"),
            })
            print(
                f"  {name}: brier={best.get('brier', '?'):.5f}  "
                f"model={best.get('model_type', '?')}  "
                f"feat={best.get('n_features', '?')}"
            )
            # Also grab top2 from each island
            for i, ind in enumerate(data.get("top5", [])[:2]):
                seeds.append({
                    "source": f"{name}_top{i+1}",
                    "brier": ind.get("brier", 1.0),
                    "features": ind.get("selected_features", []),
                    "model_type": ind.get("model_type", "xgboost"),
                })
        except Exception as exc:
            print(f"  {name}: {exc}")
    print(f"Seeds collected: {len(seeds)}")
    return seeds


def _save_state(path, gen, population, feature_names, best_brier, best_info, mut_rate):
    """Save evolution state to local JSON."""
    pop_data = [ind.to_dict(feature_names) for ind in population]
    state = {
        "generation": gen + 1,
        "best_brier": best_brier,
        "best_info": best_info,
        "mutation_rate": mut_rate,
        "population": pop_data,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    Path(path).write_text(json.dumps(state, default=str))


# =============================================================================
# STATUS CHECK (can run independently)
# =============================================================================

@app.function(image=cpu_image, volumes={VOLUME_MOUNT: vol}, timeout=30)
def check_status() -> dict:
    """Check current evolution status from Volume."""
    from pathlib import Path
    vol.reload()
    state_path = Path(STATE_FILE)
    best_path = Path(BEST_FILE)

    result = {"status": "no_state"}
    if state_path.exists():
        state = json.loads(state_path.read_text())
        result = {
            "status": "ok",
            "generation": state.get("generation", 0),
            "best_brier": state.get("best_brier", 1.0),
            "mutation_rate": state.get("mutation_rate", 0.10),
            "timestamp": state.get("timestamp", "unknown"),
            "pop_size": len(state.get("population", [])),
        }
        if state.get("best_info"):
            info = state["best_info"]
            result["best_model"] = info.get("model_type", "unknown")
            result["best_n_features"] = info.get("n_features", 0)
        delta = result.get("best_brier", 1.0) - ATR_BRIER
        result["delta_vs_atr"] = f"{delta:+.5f}"
        print(f"Generation: {result['generation']}")
        print(f"Best Brier: {result.get('best_brier', '?'):.5f}")
        print(f"Best Model: {result.get('best_model', '?')}")
        print(f"Best Features: {result.get('best_n_features', '?')}")
        print(f"Delta vs ATR ({ATR_BRIER}): {result['delta_vs_atr']}")
        print(f"Last update: {result['timestamp']}")
    else:
        print("No evolution state found. Run the evolution first.")

    if best_path.exists():
        best = json.loads(best_path.read_text())
        result["best_file"] = best
        print(f"\nBest features file exists: brier={best.get('brier', '?')}")

    return result


# =============================================================================
# MAIN EVOLUTION LOOP (runs locally, dispatches GPU evals to Modal)
# =============================================================================

@app.local_entrypoint()
def main(
    resume: bool = False,
    volume_resume: bool = False,
    gens: int = 0,
    platform: str = "modal_t4",
    rebuild_cache: bool = False,
    pop_size: int = 0,
) -> None:
    """Main evolution loop.

    Arguments:
      --resume         : resume from local state file
      --volume-resume  : pull state from Modal Volume (new machine)
      --gens N         : override generation count (default: from platform config)
      --platform STR   : modal_t4 or modal_a10g
      --rebuild-cache  : force rebuild feature cache
      --pop-size N     : override population size
    """
    import numpy as np

    cfg = PLATFORM_CONFIGS.get(platform, PLATFORM_CONFIGS["modal_t4"])
    POP_SIZE = pop_size if pop_size > 0 else cfg["POP"]
    N_FOLDS = cfg["FOLDS"]
    TOTAL_GENS = gens if gens > 0 else cfg["GENS"]
    ELITE_SIZE = cfg["ELITE"]
    EVAL_TIMEOUT = cfg["TIMEOUT"]
    MUTATION_RATE = 0.10

    print("=" * 70)
    print("  NBA QUANT AI -- TabICL GPU Evolution (Modal)")
    print(f"  Platform={platform}  Pop={POP_SIZE}  Folds={N_FOLDS}  Gens={TOTAL_GENS}")
    print(f"  ATR to beat: {ATR_BRIER} (Colab TabICL, 110f, iter 15)")
    print(f"  TabICL weight: {MODEL_WEIGHTS['tabicl']}%  |  Tree diversity: {100 - MODEL_WEIGHTS['tabicl']}%")
    print("=" * 70)

    # 1. Ensure feature cache exists on Volume
    if rebuild_cache:
        print("\nForce-rebuilding feature cache on GPU worker...")
    else:
        print("\nChecking feature cache...")
    cache_result = build_feature_cache.remote()
    print(f"Cache: {cache_result}")

    # 2. Load feature metadata locally (names only, not the full matrix)
    feature_names, n_rows = get_feature_names.remote()
    n_features = len(feature_names)
    print(f"Feature space: {n_features} features, {n_rows} games")

    # 3. Fetch island seeds
    island_seeds = _fetch_island_seeds()

    # 4. Build or restore population
    population = []
    best_ever_brier = 1.0
    best_ever_info = None
    start_gen = 0
    mut_rate = MUTATION_RATE

    local_state = Path("tabicl_evolution_state.json")

    # Pull from Volume if requested
    if volume_resume and not local_state.exists():
        print("\nPulling state from Modal Volume...")
        state_json, best_json = download_state_from_volume.remote()
        if state_json:
            local_state.write_text(state_json)
            print("Volume state downloaded.")
        if best_json:
            Path("best_tabicl_features.json").write_text(best_json)

    if (resume or volume_resume) and local_state.exists():
        try:
            state = json.loads(local_state.read_text())
            start_gen = state.get("generation", 0)
            best_ever_brier = state.get("best_brier", 1.0)
            best_ever_info = state.get("best_info")
            mut_rate = state.get("mutation_rate", MUTATION_RATE)
            for saved in state.get("population", []):
                ind = Individual.from_dict(saved, feature_names, n_features)
                population.append(ind)
            print(f"RESUMED: gen={start_gen}, best={best_ever_brier:.5f}, pop={len(population)}")
        except Exception as exc:
            print(f"State load failed ({exc}), starting fresh")
            population = []

    # Seed from islands
    name_to_idx = {n: i for i, n in enumerate(feature_names)}
    if len(population) < POP_SIZE:
        for seed in island_seeds:
            if len(population) >= POP_SIZE:
                break
            feat = [0] * n_features
            for fname in seed.get("features", []):
                if isinstance(fname, str) and fname in name_to_idx:
                    feat[name_to_idx[fname]] = 1
            if sum(feat) < 15:
                prob = TARGET_FEATURES / max(n_features, 1)
                feat = [1 if random.random() < prob else 0 for _ in range(n_features)]
            # TabICL variant of every seed -- the GPU advantage
            population.append(Individual(n_features, features=feat, model_type="tabicl"))
            if len(population) < POP_SIZE:
                population.append(
                    Individual(n_features, features=list(feat), model_type=seed.get("model_type", "xgboost"))
                )

        while len(population) < POP_SIZE:
            population.append(Individual(n_features))
        population = population[:POP_SIZE]

    mt_counts = Counter(ind.model_type for ind in population)
    print(f"\nPopulation ready: {len(population)} | Models: {dict(mt_counts)}")

    # 5. Evolution loop
    session_start = time.time()
    gens_this_session = 0
    stagnation = 0

    for gen in range(start_gen, TOTAL_GENS):
        gen_start = time.time()

        # Identify individuals needing evaluation
        to_eval = [ind for ind in population if ind.brier >= 0.99]

        if to_eval:
            # Dispatch ALL evals to Modal GPU workers in parallel via starmap
            print(f"Gen {gen + 1}/{TOTAL_GENS}: dispatching {len(to_eval)} evals to T4 GPU...", end="", flush=True)

            eval_args = [
                (
                    ind.indices,
                    ind.model_type,
                    {**ind.hp, "_timeout": EVAL_TIMEOUT},
                    n_features,
                    N_FOLDS,
                )
                for ind in to_eval
            ]

            # starmap returns results in order
            brier_scores = list(evaluate_individual.starmap(eval_args))

            for ind, score in zip(to_eval, brier_scores):
                ind.brier = score
        else:
            print(f"Gen {gen + 1}/{TOTAL_GENS}: all pre-evaluated", end="", flush=True)

        # Sort: best first
        population.sort(key=lambda x: x.brier)

        # Track best ever
        gen_best = population[0]
        improved = gen_best.brier < best_ever_brier
        if improved:
            best_ever_brier = gen_best.brier
            stagnation = 0
            best_ever_info = {
                "brier": gen_best.brier,
                "model_type": gen_best.model_type,
                "n_features": gen_best.n_feat,
                "generation": gen + 1,
                "features": [feature_names[i] for i, v in enumerate(gen_best.features) if v],
                "hp": gen_best.hp,
                "platform": platform,
                "engine_version": "v3.0-43cat",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            Path("best_tabicl_features.json").write_text(
                json.dumps(best_ever_info, indent=2, default=str)
            )
        else:
            stagnation += 1

        gen_dur = time.time() - gen_start
        elapsed = (time.time() - session_start) / 60
        gens_this_session += 1
        rate = gens_this_session / max(elapsed, 0.1) * 60

        marker = "  *** NEW BEST ***" if improved else ""
        delta = best_ever_brier - ATR_BRIER
        print(
            f"  best={gen_best.brier:.5f} ({gen_best.model_type}, {gen_best.n_feat}f)"
            f" | ever={best_ever_brier:.5f} (ATR{delta:+.5f})"
            f" | {len(to_eval)} evals {gen_dur:.0f}s"
            f" | {elapsed:.0f}min {rate:.0f}g/h{marker}"
        )

        # Detailed log every 10 gens
        if (gen + 1) % 10 == 0:
            mt = Counter(ind.model_type for ind in population)
            top5 = [(f"{ind.brier:.5f}", ind.model_type, ind.n_feat) for ind in population[:5]]
            print(f"  Models: {dict(mt)} | Top5: {top5}")
            print(f"  Stagnation: {stagnation} | Mutation rate: {mut_rate:.4f}")

        # Save state locally every gen
        _save_state(
            str(local_state), gen, population, feature_names,
            best_ever_brier, best_ever_info, mut_rate,
        )

        # Sync to Modal Volume every 10 gens (async)
        if (gen + 1) % 10 == 0:
            state_json = local_state.read_text()
            best_json = json.dumps(best_ever_info, indent=2, default=str) if best_ever_info else ""
            upload_state_to_volume.spawn(state_json, best_json)

        # Adaptive mutation on stagnation
        if stagnation >= 15:
            mut_rate = min(MUT_CEILING, mut_rate * 1.2)
            if stagnation % 15 == 0:
                print(f"  [STAGNATION] {stagnation} gens, mutation -> {mut_rate:.4f}")

        # Diversity injection every 20 gens
        if (gen + 1) % 20 == 0:
            top10_models = Counter(ind.model_type for ind in population[:10])
            dominant = max(top10_models.values()) if top10_models else 0
            if dominant >= 7:
                inject_types = [t for t in MODEL_WEIGHTS if top10_models.get(t, 0) <= 1]
                if not inject_types:
                    inject_types = list(MODEL_WEIGHTS.keys())
                n_inject = min(3, len(population) - ELITE_SIZE)
                for j in range(n_inject):
                    new_ind = Individual(n_features)
                    new_ind.model_type = inject_types[j % len(inject_types)]
                    population[-(j + 1)] = new_ind
                print(f"  [DIVERSITY] Injected {n_inject} (dominant={dominant}/10)")

        # Selection + Reproduction
        elite = population[:ELITE_SIZE]
        children = []

        # Elites carry over unchanged
        for e in elite:
            c = Individual(n_features, features=list(e.features), model_type=e.model_type, hp=dict(e.hp))
            c.brier = e.brier
            children.append(c)

        # Fill rest via crossover/mutation
        while len(children) < POP_SIZE:
            if random.random() < CROSSOVER_RATE:
                child = Individual.crossover(_tournament(population), _tournament(population))
            else:
                p = _tournament(population)
                child = Individual(n_features, features=list(p.features), model_type=p.model_type, hp=dict(p.hp))
            child.mutate(mut_rate)
            # Force TabICL for ~40% of new children (GPU advantage)
            if random.random() < 0.40:
                child.model_type = "tabicl"
            children.append(child)

        population = children[:POP_SIZE]
        mut_rate = max(MUT_FLOOR, min(MUT_CEILING, mut_rate * MUT_DECAY))

    # 6. Final save + summary
    _save_state(
        str(local_state), TOTAL_GENS - 1, population, feature_names,
        best_ever_brier, best_ever_info, mut_rate,
    )
    # Final sync to volume
    state_json = local_state.read_text()
    best_json = json.dumps(best_ever_info, indent=2, default=str) if best_ever_info else ""
    upload_state_to_volume.remote(state_json, best_json)

    total_time = (time.time() - session_start) / 60
    estimated_cost = total_time / 60 * 0.59 * POP_SIZE / 4  # rough T4 cost estimate

    print("\n" + "=" * 70)
    print("  FINAL RESULTS")
    print("=" * 70)

    if best_ever_info:
        delta = best_ever_info["brier"] - ATR_BRIER
        print(f"  Best Brier:    {best_ever_info['brier']:.5f}")
        print(f"  Model:         {best_ever_info['model_type']}")
        print(f"  Features:      {best_ever_info['n_features']}")
        print(f"  Generation:    {best_ever_info['generation']}")
        print(f"  Session gens:  {gens_this_session}")
        print(f"  Session time:  {total_time:.0f} min")
        print(f"  Est. cost:     ~${estimated_cost:.2f}")
        print(f"\n  ATR:           {ATR_BRIER} (Colab TabICL)")
        print(f"  Delta vs ATR:  {delta:+.5f}  {'NEW RECORD!' if delta < 0 else ''}")
        print(f"\n  Best features: best_tabicl_features.json")
        print(f"  Inject into HF islands via POST /api/config on S10-S15")

    population.sort(key=lambda x: x.brier)
    print("\n  Top 10:")
    for i, ind in enumerate(population[:10]):
        print(f"    #{i+1}: brier={ind.brier:.5f} | {ind.model_type} | {ind.n_feat}f")

    mt_final = Counter(ind.model_type for ind in population[:10])
    print(f"\n  Top 10 model distribution: {dict(mt_final)}")
