#!/usr/bin/env python3
"""
NBA Quant AI — Karpathy Iteration Loop (CPU/GPU)
==================================================
Real autonomous iteration: mutate one thing -> train -> measure Brier -> keep if better.

Usage:
    python3 nba_iterate.py                      # 100 iterations, CPU subsample
    python3 nba_iterate.py --iterations 500     # 500 iterations
    python3 nba_iterate.py --gpu                # Full dataset (GPU mode)
    python3 nba_iterate.py --verbose            # Debug logging

Metric: Brier score on 200-game holdout (CPU) or full holdout (GPU)
Target: < 0.20 Brier
"""

import os
import sys
import json
import time
import copy
import random
import argparse
import logging
from pathlib import Path
from datetime import datetime, timezone

import numpy as np

# Add parent to path for karpathy_utils
sys.path.insert(0, str(Path(__file__).parent))
from karpathy_utils import (
    load_best_config,
    save_config,
    mutate_config,
    evaluate_config,
    log_iteration,
    save_history,
    telegram_alert,
    load_or_create_cached_data,
    generate_synthetic_data,
    setup_logging,
    default_config,
)

# ── Paths ──
ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data" / "karpathy"
LOG_DIR = ROOT / "logs" / "karpathy"
CONFIG_PATH = DATA_DIR / "nba-best-config.json"
HISTORY_PATH = DATA_DIR / "nba-history.json"
CACHE_PATH = DATA_DIR / "nba_cached_data.npz"

# ── CPU Mode Constants ──
CPU_TRAIN_GAMES = 3500
CPU_VAL_GAMES = 700
CPU_TOTAL = CPU_TRAIN_GAMES + CPU_VAL_GAMES
CPU_MAX_FEATURES = 200
CPU_TIMEOUT = 180  # 3 min max per eval

# ── GPU Mode Constants ──
GPU_VAL_RATIO = 0.15
GPU_MAX_FEATURES = 500
GPU_TIMEOUT = 60  # 1 min max per eval

log = logging.getLogger("karpathy")


def load_real_nba_data() -> tuple:
    """
    Try to load real NBA data from available sources.

    Priority:
    1. Cached .npz file
    2. Feature engine from hf-space (if available)
    3. Raw game JSON files
    4. Fall back to synthetic data
    """
    # 1. Check cache first
    if CACHE_PATH.exists():
        try:
            data = np.load(CACHE_PATH, allow_pickle=True)
            X, y = data["X"], data["y"]
            feature_names = list(data["feature_names"])
            log.info(f"Loaded cached NBA data: {X.shape[0]} games x {X.shape[1]} features")
            return X, y, feature_names
        except Exception as e:
            log.warning(f"Cache corrupt: {e}")

    # 2. Try loading from feature engine
    engine_path = ROOT / "hf-space" / "features"
    if engine_path.exists():
        try:
            sys.path.insert(0, str(ROOT / "hf-space"))
            from features.engine import NBAFeatureEngine

            # Load game data from available JSON files
            games = []
            data_dirs = [
                ROOT.parent / "nomos-nba-agent" / "data" / "historical",
                ROOT / "hf-space" / "data" / "historical",
                ROOT / "nba-quant-space" / "data" / "historical",
                ROOT / "data" / "historical-odds",
            ]
            for d in data_dirs:
                if d.exists():
                    for f in sorted(d.glob("games-*.json")):
                        try:
                            raw = json.loads(f.read_text())
                            if isinstance(raw, list):
                                games.extend(raw)
                            elif isinstance(raw, dict) and "games" in raw:
                                games.extend(raw["games"])
                        except Exception:
                            continue

            if games:
                log.info(f"Building features from {len(games)} games...")
                engine = NBAFeatureEngine()
                X, y, feature_names = engine.build(games)
                X = np.nan_to_num(np.array(X, dtype=np.float32))
                y = np.array(y, dtype=np.float64)

                # Cache for next time
                DATA_DIR.mkdir(parents=True, exist_ok=True)
                np.savez_compressed(
                    CACHE_PATH, X=X, y=y,
                    feature_names=np.array(feature_names),
                )
                log.info(f"Built and cached: {X.shape}")
                return X, y, feature_names
        except Exception as e:
            log.warning(f"Feature engine failed: {e}")

    # 3. Fall back to synthetic data
    log.info("No real data available — generating synthetic NBA data")
    log.info("To use real data, ensure hf-space/features/engine.py and game JSON files exist")
    X, y, feature_names = generate_synthetic_data(
        n_games=CPU_TOTAL + 1000,  # Extra for GPU mode
        n_features=CPU_MAX_FEATURES,
        seed=42,
    )

    # Cache it
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        CACHE_PATH, X=X, y=y,
        feature_names=np.array(feature_names),
    )
    return X, y, feature_names


def run_karpathy_loop(iterations: int, gpu: bool, verbose: bool) -> None:
    """Main Karpathy iteration loop."""

    # Setup logging
    date_str = datetime.now().strftime("%Y-%m-%d")
    log_file = LOG_DIR / f"nba-{date_str}.log"
    setup_logging(str(log_file), verbose)

    log.info("=" * 60)
    log.info("NBA KARPATHY ITERATION LOOP")
    log.info(f"Mode: {'GPU' if gpu else 'CPU'}")
    log.info(f"Iterations: {iterations}")
    log.info("=" * 60)

    # Load data
    t0 = time.time()
    X_all, y_all, feature_names = load_real_nba_data()
    n_total_features = X_all.shape[1]
    log.info(f"Data loaded in {time.time() - t0:.1f}s: {X_all.shape[0]} games x {n_total_features} features")

    # Split into train/val
    if gpu:
        n_val = int(len(y_all) * GPU_VAL_RATIO)
        n_train = len(y_all) - n_val
        max_features = min(GPU_MAX_FEATURES, n_total_features)
        timeout = GPU_TIMEOUT
    else:
        # CPU: subsample for speed
        total = min(CPU_TOTAL, len(y_all))
        n_val = min(CPU_VAL_GAMES, total // 5)
        n_train = total - n_val
        max_features = min(CPU_MAX_FEATURES, n_total_features)
        timeout = CPU_TIMEOUT

    # Use last N games as validation (temporal split, no leakage)
    X_train = X_all[:n_train]
    y_train = y_all[:n_train]
    X_val = X_all[n_train : n_train + n_val]
    y_val = y_all[n_train : n_train + n_val]

    log.info(f"Train: {X_train.shape[0]} games | Val: {X_val.shape[0]} games")
    log.info(f"Max features per config: {max_features}")

    # Load or create starting config
    config = load_best_config(str(CONFIG_PATH), n_total_features)

    # Ensure feature indices are within bounds
    config["feature_indices"] = [
        i for i in config["feature_indices"] if i < n_total_features
    ]
    config["n_features"] = len(config["feature_indices"])

    # If no features, create defaults
    if config["n_features"] < 10:
        config = default_config(n_total_features)

    # Evaluate starting config to get baseline
    log.info("Evaluating baseline config...")
    baseline_brier = evaluate_config(config, X_train, y_train, X_val, y_val, timeout)
    if config.get("best_brier", 1.0) >= 1.0:
        config["best_brier"] = baseline_brier
    log.info(f"Baseline Brier: {baseline_brier:.5f}")
    log.info(f"Best known Brier: {config['best_brier']:.5f}")

    # Iteration history
    history = []
    improvements = 0
    best_brier = config["best_brier"]
    start_brier = best_brier
    start_time = time.time()
    jsonl_log = LOG_DIR / f"nba-iterations-{date_str}.jsonl"

    # Alert on start
    telegram_alert(
        f"*NBA Karpathy Loop Started*\n"
        f"Mode: {'GPU' if gpu else 'CPU'}\n"
        f"Iterations: {iterations}\n"
        f"Baseline Brier: {baseline_brier:.5f}\n"
        f"Train: {n_train} | Val: {n_val} games"
    )

    # ── MAIN LOOP ──
    no_improve_count = 0
    for i in range(1, iterations + 1):
        iter_start = time.time()

        # Anti-stagnation: escalating exploration when stuck
        if no_improve_count >= 20:
            # HARD RESET: reseed 70% of features randomly
            log.info(f"[STAGNATION] {no_improve_count} iterations stuck — HARD RESET (reseed 70% features)")
            n_keep = max(15, len(config.get("feature_indices", [])) // 3)
            kept = sorted(np.random.choice(config["feature_indices"], n_keep, replace=False).tolist()) if config.get("feature_indices") else []
            n_new = min(max_features - n_keep, n_total_features - n_keep)
            available = sorted(set(range(n_total_features)) - set(kept))
            new_feats = sorted(np.random.choice(available, min(n_new, len(available)), replace=False).tolist())
            config["feature_indices"] = sorted(kept + new_feats)
            config["n_features"] = len(config["feature_indices"])
            no_improve_count = 0
        elif no_improve_count >= 10:
            # MEDIUM SHAKE: swap 30 features + change model
            log.info(f"[STAGNATION] {no_improve_count} iterations stuck — swapping 30 features + model change")

        # Mutate (with larger swaps when stagnating)
        if no_improve_count >= 10:
            # Force large swap mutation instead of random choice
            candidate = copy.deepcopy(config)
            indices = set(candidate.get("feature_indices", []))
            available = sorted(set(range(n_total_features)) - indices)
            n_swap = min(30, len(indices) - 15, len(available))
            if n_swap > 0:
                to_remove = sorted(np.random.choice(sorted(indices), n_swap, replace=False).tolist())
                to_add = sorted(np.random.choice(available, n_swap, replace=False).tolist())
                indices -= set(to_remove)
                indices.update(to_add)
            candidate["feature_indices"] = sorted(indices)
            candidate["n_features"] = len(candidate["feature_indices"])
            # Also try a different model
            models = ["extra_trees", "random_forest", "lightgbm", "catboost", "xgboost", "gradient_boosting"]
            candidate["model_type"] = random.choice([m for m in models if m != config["model_type"]])
            mutation_desc = f"STAGNATION swap {n_swap} features + model -> {candidate['model_type']}"
        else:
            candidate, mutation_desc = mutate_config(config, n_total_features)

        # Enforce max features cap
        if len(candidate["feature_indices"]) > max_features:
            candidate["feature_indices"] = sorted(
                np.random.choice(
                    candidate["feature_indices"], max_features, replace=False
                ).tolist()
            )
            candidate["n_features"] = max_features

        # Evaluate
        score = evaluate_config(candidate, X_train, y_train, X_val, y_val, timeout)
        elapsed = time.time() - iter_start
        improved = score < best_brier

        if improved:
            improvements += 1
            no_improve_count = 0
            delta = best_brier - score
            log.info(
                f"[{i}/{iterations}] IMPROVED {mutation_desc} | "
                f"Brier: {best_brier:.5f} -> {score:.5f} (delta={delta:.5f}) | "
                f"{elapsed:.1f}s"
            )

            # Update best
            best_brier = score
            config = candidate
            config["best_brier"] = best_brier
            config["iteration"] = i

            # Save
            save_config(config, str(CONFIG_PATH))

            # Alert on significant improvement (> 0.001)
            if delta > 0.001:
                telegram_alert(
                    f"*NBA Karpathy: Significant Improvement!*\n"
                    f"Iteration {i}/{iterations}\n"
                    f"Brier: {best_brier + delta:.5f} -> {best_brier:.5f}\n"
                    f"Delta: -{delta:.5f}\n"
                    f"Mutation: {mutation_desc}\n"
                    f"Model: {config['model_type']}, Features: {config['n_features']}"
                )
        else:
            no_improve_count += 1
            if i % 10 == 0 or verbose:
                log.info(
                    f"[{i}/{iterations}] no improvement (stuck={no_improve_count}) | {mutation_desc} | "
                    f"Brier: {score:.5f} (best: {best_brier:.5f}) | {elapsed:.1f}s"
                )

        # Record history
        entry = {
            "iteration": i,
            "brier": round(score, 6),
            "best_brier": round(best_brier, 6),
            "improved": improved,
            "mutation": mutation_desc,
            "model_type": candidate["model_type"],
            "n_features": candidate["n_features"],
            "elapsed_seconds": round(elapsed, 1),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        history.append(entry)

        # Log to JSONL
        log_iteration(i, score, improved, mutation_desc, candidate, str(jsonl_log))

        # Periodic saves
        if i % 25 == 0:
            save_history(history, str(HISTORY_PATH))
            total_elapsed = time.time() - start_time
            rate = i / (total_elapsed / 60)
            log.info(
                f"--- Checkpoint {i}/{iterations} | Best: {best_brier:.5f} | "
                f"Improvements: {improvements} | Rate: {rate:.1f} iter/min ---"
            )

    # ── FINAL REPORT ──
    total_time = time.time() - start_time
    total_delta = start_brier - best_brier

    save_history(history, str(HISTORY_PATH))
    save_config(config, str(CONFIG_PATH))

    report = (
        f"\n{'=' * 60}\n"
        f"NBA KARPATHY LOOP — FINAL REPORT\n"
        f"{'=' * 60}\n"
        f"Iterations:    {iterations}\n"
        f"Improvements:  {improvements} ({improvements/iterations*100:.1f}%)\n"
        f"Start Brier:   {start_brier:.5f}\n"
        f"Final Brier:   {best_brier:.5f}\n"
        f"Total Delta:   {'-' if total_delta > 0 else '+'}{abs(total_delta):.5f}\n"
        f"Best Model:    {config['model_type']}\n"
        f"Best Features: {config['n_features']}\n"
        f"Total Time:    {total_time/60:.1f} min\n"
        f"Avg Iter:      {total_time/iterations:.1f}s\n"
        f"Rate:          {iterations/(total_time/60):.1f} iter/min\n"
        f"Config:        {CONFIG_PATH}\n"
        f"History:       {HISTORY_PATH}\n"
        f"Log:           {log_file}\n"
        f"{'=' * 60}"
    )
    log.info(report)

    # Final Telegram summary
    telegram_alert(
        f"*NBA Karpathy Loop Complete*\n"
        f"Iterations: {iterations}\n"
        f"Improvements: {improvements}\n"
        f"Brier: {start_brier:.5f} -> {best_brier:.5f}\n"
        f"Delta: {'-' if total_delta > 0 else '+'}{abs(total_delta):.5f}\n"
        f"Model: {config['model_type']}, Features: {config['n_features']}\n"
        f"Time: {total_time/60:.1f} min ({iterations/(total_time/60):.1f} iter/min)"
    )


def main():
    parser = argparse.ArgumentParser(
        description="NBA Karpathy Iteration Loop — autonomous model improvement"
    )
    parser.add_argument(
        "--iterations", "-n", type=int, default=100,
        help="Number of iterations to run (default: 100)",
    )
    parser.add_argument(
        "--gpu", action="store_true",
        help="GPU mode: use full dataset instead of CPU subsample",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    run_karpathy_loop(args.iterations, args.gpu, args.verbose)


if __name__ == "__main__":
    main()
