#!/usr/bin/env python3
"""
NBA Quant AI -- Modal A10G/A100 GPU Burst (10 min max)
=======================================================
Karpathy autoresearch pattern on Modal serverless GPUs.
Uses Modal's @app.function decorator for serverless execution.

Usage:
    modal run scripts/gpu-burst/modal-burst.py                     # Default: A10G, 10 min
    modal run scripts/gpu-burst/modal-burst.py --gpu a100          # A100 GPU
    modal run scripts/gpu-burst/modal-burst.py --timeout 300       # 5 min burst
    modal run scripts/gpu-burst/modal-burst.py::check_status       # Check last result

Secrets required (Modal dashboard -> Secrets -> nomos42-secrets):
    HF_TOKEN, GITHUB_TOKEN, DATABASE_URL (optional),
    TELEGRAM_BOT_TOKEN (optional), ADMIN_TELEGRAM_ID (optional)

Cost estimate:
    A10G: ~$1.10/hr -> $0.18 for 10 min burst
    A100: ~$3.73/hr -> $0.62 for 10 min burst

Target: Beat ATR 0.21570 (Colab TabICL, 110f, iter 15)
"""

from __future__ import annotations

import json
import os
import random
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

import modal

# ══════════════════════════════════════════════════════════
# MODAL APP + IMAGES
# ══════════════════════════════════════════════════════════

app = modal.App("nba-gpu-burst")

vol = modal.Volume.from_name("nba-burst-state", create_if_missing=True)
VOLUME_MOUNT = "/data"

gpu_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git")
    .pip_install(
        "xgboost>=2.0", "lightgbm", "catboost", "scikit-learn",
        "numpy", "pandas", "requests", "huggingface_hub",
        "psycopg2-binary",
    )
)

cpu_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("numpy", "requests")
)

# ══════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════

MAX_DURATION_SECONDS = 600  # 10 minutes default
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

POPULATION_SIZE = 24
ITERATION_BUDGET_SEC = 120
MUTATION_RATE = 0.09
CROSSOVER_RATE = 0.80
TARGET_FEATURES = 63
MAX_FEATURES = 200
SUBSAMPLE_GAMES = 5000

MODEL_TYPES = ["xgboost", "xgboost_brier", "catboost", "lightgbm", "extra_trees"]
MODEL_WEIGHTS = [0.25, 0.20, 0.20, 0.15, 0.20]

HP_RANGES = {
    "depth": (4, 10),
    "lr": (0.01, 0.3),
    "n_est": (100, 400),
}

# Volume paths
CACHE_FILE = f"{VOLUME_MOUNT}/features_cache.npz"
STATE_FILE = f"{VOLUME_MOUNT}/burst_state.json"
RESULT_FILE = f"{VOLUME_MOUNT}/burst_result.json"
LOG_FILE = f"{VOLUME_MOUNT}/burst_log.jsonl"


# ══════════════════════════════════════════════════════════
# HELPER: BUILD FEATURE CACHE (runs once, cached in Volume)
# ══════════════════════════════════════════════════════════

@app.function(
    gpu="A10G",
    image=gpu_image,
    volumes={VOLUME_MOUNT: vol},
    secrets=[modal.Secret.from_name("nomos42-secrets")],
    timeout=1800,
    retries=0,
)
def build_feature_cache() -> dict:
    """Build feature cache from HF Space data. Run once per engine version."""
    import gc
    import subprocess
    import sys

    import numpy as np

    cache_path = Path(CACHE_FILE)
    if cache_path.exists():
        cached = np.load(str(cache_path), allow_pickle=True)
        shape = tuple(cached["X"].shape)
        return {"cached": True, "shape": shape, "n_features": len(cached["feature_names"])}

    print("[CACHE] Building features from HF Space...")
    t0 = time.time()

    repo_dir = Path("/tmp/nba-quant-space")
    if not repo_dir.exists():
        hf_token = os.environ.get("HF_TOKEN", "")
        clone_url = f"https://user:{hf_token}@huggingface.co/spaces/Nomos42/nba-quant"
        ret = subprocess.run(
            ["git", "clone", "--depth", "1", clone_url, str(repo_dir)],
            capture_output=True, text=True,
        )
        if ret.returncode != 0:
            clone_url = f"https://user:{hf_token}@huggingface.co/spaces/Nomos42/nba-quant-2"
            subprocess.run(
                ["git", "clone", "--depth", "1", clone_url, str(repo_dir)],
                capture_output=True, text=True, check=True,
            )

    sys.path.insert(0, str(repo_dir))

    # Load games
    games = []
    for data_dir in [repo_dir / "data" / "historical"]:
        if data_dir.exists():
            for f in sorted(data_dir.glob("games-*.json")):
                raw = json.loads(f.read_text())
                if isinstance(raw, list):
                    games.extend(raw)
                elif isinstance(raw, dict) and "games" in raw:
                    games.extend(raw["games"])
            if games:
                print(f"[CACHE] Loaded {len(games)} games from local JSON")

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
            print(f"[CACHE] Loaded {len(games)} from Supabase")

    if not games:
        raise ValueError("No game data. Set DATABASE_URL in Modal secrets.")

    games.sort(key=lambda g: g.get("game_date", g.get("date", "")))
    from features.engine import NBAFeatureEngine
    engine = NBAFeatureEngine()
    X, y, feature_names = engine.build(games)
    X = np.nan_to_num(np.array(X, dtype=np.float64))
    y = np.array(y, dtype=np.int32)
    y_margin = getattr(engine, 'y_margin', np.zeros(len(y), dtype=np.int32))
    y_total = getattr(engine, 'y_total', np.full(len(y), 225, dtype=np.int32))

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(str(cache_path), X=X, y=y, feature_names=np.array(feature_names),
                        y_margin=y_margin, y_total=y_total)
    vol.commit()

    elapsed = time.time() - t0
    print(f"[CACHE] Built: {X.shape} in {elapsed:.0f}s")
    return {"cached": False, "shape": tuple(X.shape), "n_features": len(feature_names), "time": elapsed}


# ══════════════════════════════════════════════════════════
# CORE: GPU BURST EVOLUTION
# ══════════════════════════════════════════════════════════

@app.function(
    gpu="A10G",
    image=gpu_image,
    volumes={VOLUME_MOUNT: vol},
    secrets=[modal.Secret.from_name("nomos42-secrets")],
    timeout=1800,  # 30 min safety margin for setup + evolution
    retries=0,
)
def run_burst(max_duration: int = MAX_DURATION_SECONDS) -> dict:
    """
    Main GPU burst: evolve population for max_duration seconds.
    Seeds from HF islands, runs genetic evolution, returns result dict.
    """
    import gc
    import ssl
    import subprocess
    import urllib.request

    import numpy as np
    from sklearn.metrics import brier_score_loss
    from sklearn.model_selection import TimeSeriesSplit

    burst_start = time.time()

    # ── Load features from Volume ──
    cache_path = Path(CACHE_FILE)
    if not cache_path.exists():
        print("[BURST] Feature cache not found -- building first...")
        build_feature_cache.remote()
        vol.reload()

    if not cache_path.exists():
        return {"error": "Feature cache not available after build attempt"}

    data = np.load(str(cache_path), allow_pickle=True)
    X, y, feature_names = data["X"], data["y"], list(data["feature_names"])
    n_features = X.shape[1]

    if X.shape[0] > SUBSAMPLE_GAMES:
        X = X[-SUBSAMPLE_GAMES:]
        y = y[-SUBSAMPLE_GAMES:]
    print(f"[BURST] Data: {X.shape} ({n_features} total features)")

    # ── Model factory ──
    def _make_model(model_type, hp):
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
        elif model_type == "xgboost_brier":
            def brier_obj(y_true, y_pred):
                grad = 2 * (y_pred - y_true)
                hess = np.full_like(grad, 2.0)
                return grad, hess
            return xgb.XGBClassifier(
                max_depth=hp.get("depth", 6), learning_rate=hp.get("lr", 0.1),
                n_estimators=hp.get("n_est", 200), random_state=42,
                objective=brier_obj, verbosity=0, tree_method="hist",
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

    # ── Evaluation (immutable) ──
    def _evaluate(features_mask, model_type, hp, timeout=90):
        try:
            selected = np.where(features_mask)[0]
            if len(selected) < 5 or len(selected) > MAX_FEATURES:
                return 1.0

            X_sub = X[:, selected]
            tscv = TimeSeriesSplit(n_splits=2)
            briers = []

            for train_idx, test_idx in tscv.split(X_sub):
                model = _make_model(model_type, hp)
                t0 = time.time()
                model.fit(X_sub[train_idx], y[train_idx])
                if time.time() - t0 > timeout:
                    return 1.0

                probs = model.predict_proba(X_sub[test_idx])
                probs = probs[:, 1] if probs.shape[1] == 2 else probs[:, 0]
                probs = np.clip(probs, 0.001, 0.999)
                briers.append(brier_score_loss(y[test_idx], probs))

            return float(np.mean(briers))
        except Exception:
            return 1.0

    # ── Genetic operators ──
    def _random_individual():
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

    def _mutate(ind, mutation_rate):
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
            on_idx = np.where(new["mask"])[0]
            new["mask"][np.random.choice(on_idx)] = False
            n_selected -= 1
        while n_selected < max(TARGET_FEATURES * 0.5, 10):
            off_idx = np.where(~new["mask"])[0]
            if len(off_idx) == 0:
                break
            new["mask"][np.random.choice(off_idx)] = True
            n_selected += 1

        if random.random() < 0.2:
            new["hp"]["depth"] = max(4, min(10, new["hp"]["depth"] + random.choice([-1, 0, 1])))
            new["hp"]["lr"] = round(max(0.01, min(0.3, new["hp"]["lr"] * random.uniform(0.8, 1.2))), 3)
            new["hp"]["n_est"] = max(100, min(400, new["hp"]["n_est"] + random.choice([-50, 0, 50])))

        if random.random() < 0.25:
            new["model_type"] = np.random.choice(MODEL_TYPES, p=MODEL_WEIGHTS)
        return new

    def _crossover(p1, p2):
        child = {"mask": np.zeros_like(p1["mask"]), "brier": 1.0}
        for i in range(len(child["mask"])):
            child["mask"][i] = p1["mask"][i] if random.random() < CROSSOVER_RATE else p2["mask"][i]
        child["model_type"] = p1["model_type"] if random.random() < 0.5 else p2["model_type"]
        child["hp"] = dict(p1["hp"] if random.random() < 0.5 else p2["hp"])
        return child

    # ── Seed from HF islands ──
    seeds = []
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    for name, base_url in HF_ISLANDS.items():
        try:
            url = f"{base_url}/api/best"
            req = urllib.request.Request(url, headers={"User-Agent": "Nomos42-ModalBurst/1.0"})
            with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                d = json.loads(resp.read())
                if d.get("brier", 1.0) < 0.99:
                    mask = np.zeros(n_features, dtype=bool)
                    for idx in d.get("features", []):
                        if 0 <= idx < n_features:
                            mask[idx] = True
                    if np.sum(mask) >= 5:
                        seeds.append({
                            "mask": mask,
                            "model_type": d.get("model_type", "xgboost"),
                            "hp": d.get("hp", {"depth": 6, "lr": 0.1, "n_est": 200}),
                            "brier": float(d.get("brier", 1.0)),
                        })
                        print(f"  [SEED] {name}: brier={d.get('brier', '?')}")
        except Exception as e:
            print(f"  [SEED] {name}: failed ({e})")

    print(f"[SEED] Total seeds: {len(seeds)}")

    # ── Initialize population ──
    population = seeds[:POPULATION_SIZE]
    while len(population) < POPULATION_SIZE:
        population.append(_random_individual())

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

    print(f"\n{'='*70}")
    print(f"  MODAL A10G GPU BURST -- NBA EVOLUTION")
    print(f"  Pop={POPULATION_SIZE} | Budget={max_duration}s")
    print(f"  ATR: {ATR_BRIER:.5f} | Seed best: {best_ever:.5f}")
    print(f"  Setup: {elapsed_setup:.0f}s")
    print(f"{'='*70}\n")

    # ── Evolution loop ──
    while time.time() - burst_start < max_duration:
        iteration += 1
        iter_start = time.time()
        n_evals = 0
        improved = False

        for ind in population:
            if ind["brier"] >= 0.99:
                ind["brier"] = _evaluate(ind["mask"], ind["model_type"], ind["hp"])
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
                child = _crossover(p1, p2)
                child = _mutate(child, mutation_rate)
            else:
                parent = random.choice(elite)
                child = _mutate(parent, mutation_rate)
            offspring.append(child)

        population = elite + offspring

        if stagnation >= 10:
            mutation_rate = min(0.20, mutation_rate * 1.3)
        elif improved:
            mutation_rate = max(0.06, mutation_rate * 0.95)

        # Diversity injection
        if iteration % 15 == 0:
            top_models = Counter(ind["model_type"] for ind in population[:10])
            dominant = max(top_models.values()) if top_models else 0
            if dominant >= 7:
                for j in range(min(4, len(population) - elite_size)):
                    new_ind = _random_individual()
                    new_ind["model_type"] = MODEL_TYPES[j % len(MODEL_TYPES)]
                    population[-(j + 1)] = new_ind

        duration = time.time() - iter_start
        remaining = max_duration - (time.time() - burst_start)
        best_nf = int(np.sum(population[0]["mask"]))
        tag = "*** NEW BEST ***" if improved else ""

        print(
            f"Iter {iteration}: brier={best_ever:.5f} "
            f"({population[0]['model_type']}, {best_nf}f) | "
            f"{n_evals} evals {duration:.0f}s | "
            f"{remaining:.0f}s left {tag}"
        )

        # Log to volume
        log_entry = {
            "timestamp": time.time(),
            "iteration": iteration,
            "best_brier": best_ever,
            "n_evals": n_evals,
            "improved": improved,
        }
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

        gc.collect()

    # ── Finalize ──
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
        "platform": "modal_a10g",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "atr_brier": ATR_BRIER,
        "beat_atr": best_ever < ATR_BRIER,
    }

    # Save to volume
    Path(RESULT_FILE).write_text(json.dumps(result, indent=2))
    vol.commit()

    print(f"\n{'='*70}")
    print(f"  MODAL BURST COMPLETE")
    print(f"  Iterations: {iteration} | Evals: {total_evals}")
    print(f"  Best Brier: {best_ever:.5f} ({best_ind['model_type']}, {len(best_features)}f)")
    print(f"  Improvement: {result['improvement']:.6f}")
    print(f"  Beat ATR ({ATR_BRIER}): {'YES' if result['beat_atr'] else 'NO'}")
    print(f"  Time: {total_time:.0f}s | Cost: ~${total_time/3600 * 1.10:.2f}")
    print(f"{'='*70}")

    # Push to GitHub if improved
    if best_ever < initial_best - IMPROVEMENT_THRESHOLD:
        github_token = os.environ.get("GITHUB_TOKEN", "")
        if github_token:
            try:
                push_dir = Path("/tmp/mon-ipad-push")
                if not push_dir.exists():
                    clone_url = f"https://{github_token}@github.com/{GITHUB_REPO}.git"
                    subprocess.run(
                        ["git", "clone", "--depth", "1", clone_url, str(push_dir)],
                        capture_output=True, text=True, timeout=60, check=True,
                    )

                import subprocess
                result_path = push_dir / "data" / "gpu-burst" / "latest-modal-result.json"
                result_path.parent.mkdir(parents=True, exist_ok=True)
                result_path.write_text(json.dumps(result, indent=2))

                subprocess.run(
                    ["git", "-C", str(push_dir), "config", "user.email",
                     "nomos42@users.noreply.github.com"], check=True)
                subprocess.run(
                    ["git", "-C", str(push_dir), "config", "user.name",
                     "Nomos42 GPU Burst"], check=True)
                subprocess.run(
                    ["git", "-C", str(push_dir), "add", str(result_path)], check=True)

                msg = (
                    f"gpu-burst: modal A10G brier={best_ever:.5f} "
                    f"({best_ind['model_type']}, {len(best_features)}f, "
                    f"{iteration} iters)"
                )
                subprocess.run(
                    ["git", "-C", str(push_dir), "commit", "-m", msg],
                    capture_output=True, text=True,
                )
                subprocess.run(
                    ["git", "-C", str(push_dir), "push", "origin", GITHUB_BRANCH],
                    capture_output=True, text=True, timeout=60,
                )
                print(f"[PUSH] Pushed to GitHub: {msg}")
            except Exception as e:
                print(f"[PUSH] Failed: {e}")

        # Update HF Space S10 — nudge target_features toward GPU-found optimum
        # /api/config accepts: pop_size, mutation_rate, target_features, crossover_rate, etc.
        # We set target_features so the CPU island converges toward the winning feature count.
        try:
            target_features = min(len(best_features), 150)  # cap within space guard
            payload = json.dumps({
                "target_features": target_features,
            }).encode("utf-8")
            import urllib.request, ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(
                f"{HF_ISLANDS['S10']}/api/config",
                data=payload, method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                resp_data = json.loads(resp.read())
            print(f"[HF] Updated S10 config: target_features={target_features} → {resp_data}")
        except Exception as e:
            print(f"[HF] S10 /api/config failed (space may be sleeping): {type(e).__name__}: {e}")

    # Telegram alert
    try:
        import urllib.request, urllib.parse
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.environ.get("ADMIN_TELEGRAM_ID", "")
        if token and chat_id:
            improved_str = "IMPROVED" if best_ever < initial_best - IMPROVEMENT_THRESHOLD else "No improvement"
            msg = (
                f"Modal A10G Burst -- {improved_str}\n"
                f"Brier: {initial_best:.5f} -> {best_ever:.5f}\n"
                f"Model: {best_ind['model_type']}, {len(best_features)}f\n"
                f"Iters: {iteration}, Cost: ~${total_time/3600 * 1.10:.2f}"
            )
            data = urllib.parse.urlencode({"chat_id": chat_id, "text": msg}).encode("utf-8")
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{token}/sendMessage", data=data)
            urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass

    return result


# ══════════════════════════════════════════════════════════
# STATUS CHECK (CPU, no GPU cost)
# ══════════════════════════════════════════════════════════

@app.function(
    image=cpu_image,
    volumes={VOLUME_MOUNT: vol},
    timeout=60,
)
def check_status() -> dict:
    """Check last burst result and log stats. No GPU cost."""
    import numpy as np

    vol.reload()
    result_path = Path(RESULT_FILE)
    log_path = Path(LOG_FILE)

    status = {"has_result": False, "has_log": False, "has_cache": False}

    if result_path.exists():
        status["has_result"] = True
        status["last_result"] = json.loads(result_path.read_text())

    if log_path.exists():
        status["has_log"] = True
        lines = log_path.read_text().strip().split("\n")
        status["log_entries"] = len(lines)
        if lines:
            last = json.loads(lines[-1])
            status["last_log"] = last

    cache_path = Path(CACHE_FILE)
    if cache_path.exists():
        status["has_cache"] = True
        cached = np.load(str(cache_path), allow_pickle=True)
        status["cache_shape"] = list(cached["X"].shape)

    print(json.dumps(status, indent=2, default=str))
    return status


# ══════════════════════════════════════════════════════════
# LOCAL ENTRYPOINT
# ══════════════════════════════════════════════════════════

@app.local_entrypoint()
def main(
    gpu: str = "A10G",
    timeout: int = MAX_DURATION_SECONDS,
    rebuild_cache: bool = False,
):
    """
    Local entrypoint for modal run.

    Args:
        gpu: GPU type (A10G or A100)
        timeout: Burst duration in seconds (default 600)
        rebuild_cache: Force rebuild feature cache
    """
    print(f"NBA GPU Burst on Modal ({gpu})")
    print(f"Timeout: {timeout}s")

    if rebuild_cache:
        print("Rebuilding feature cache...")
        cache_result = build_feature_cache.remote()
        print(f"Cache: {cache_result}")

    print("Running burst...")
    result = run_burst.remote(max_duration=timeout)

    print(f"\nResult: brier={result.get('best_brier', '?')}")
    print(f"Improvement: {result.get('improvement', '?')}")
    print(f"Beat ATR: {result.get('beat_atr', '?')}")

    return result
