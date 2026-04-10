#!/usr/bin/env python3
"""
Political Alpha — Karpathy Iteration Loop (CPU/GPU)
=====================================================
Real autonomous iteration: mutate one thing -> train -> measure Brier -> keep if better.

Usage:
    python3 political_iterate.py                    # 100 iterations, CPU
    python3 political_iterate.py --iterations 500   # 500 iterations
    python3 political_iterate.py --gpu              # Full dataset (GPU mode)
    python3 political_iterate.py --verbose          # Debug logging

Metric: Brier score on 50-event holdout
Target: Best achievable Brier on political event prediction
"""

import os
import sys
import json
import time
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
    generate_synthetic_data,
    setup_logging,
    default_config,
)

# ── Paths ──
ROOT = Path("/home/termius/mon-ipad")
POLITICAL_ROOT = ROOT / "nomos-political-alpha"
DATA_DIR = ROOT / "data" / "karpathy"
LOG_DIR = ROOT / "logs" / "karpathy"
CONFIG_PATH = DATA_DIR / "political-best-config.json"
HISTORY_PATH = DATA_DIR / "political-history.json"
CACHE_PATH = DATA_DIR / "political_cached_data.npz"

# ── CPU Mode Constants ──
CPU_TRAIN_EVENTS = 400
CPU_VAL_EVENTS = 50
CPU_TOTAL = CPU_TRAIN_EVENTS + CPU_VAL_EVENTS
CPU_MAX_FEATURES = 200
CPU_TIMEOUT = 180

# ── GPU Mode Constants ──
GPU_VAL_RATIO = 0.12
GPU_MAX_FEATURES = 400
GPU_TIMEOUT = 60

log = logging.getLogger("karpathy")


def load_real_political_data() -> tuple:
    """
    Try to load real political data from available sources.

    Priority:
    1. Cached .npz file
    2. Political engine from nomos-political-alpha (if available)
    3. Fall back to synthetic data (political-like distribution)
    """
    # 1. Check cache first
    if CACHE_PATH.exists():
        try:
            data = np.load(CACHE_PATH, allow_pickle=True)
            X, y = data["X"], data["y"]
            feature_names = list(data["feature_names"])
            log.info(f"Loaded cached political data: {X.shape[0]} events x {X.shape[1]} features")
            return X, y, feature_names
        except Exception as e:
            log.warning(f"Cache corrupt: {e}")

    # 2. Try loading from political engine
    engine_path = POLITICAL_ROOT / "features" / "political_engine.py"
    if engine_path.exists():
        try:
            sys.path.insert(0, str(POLITICAL_ROOT))
            from features.political_engine import PoliticalFeatureEngine

            # Load event data
            events = []
            data_dir = POLITICAL_ROOT / "data"
            if data_dir.exists():
                for f in sorted(data_dir.glob("events-*.json")):
                    try:
                        raw = json.loads(f.read_text())
                        if isinstance(raw, list):
                            events.extend(raw)
                        elif isinstance(raw, dict) and "events" in raw:
                            events.extend(raw["events"])
                    except Exception:
                        continue

            if events:
                log.info(f"Building political features from {len(events)} events...")
                engine = PoliticalFeatureEngine()
                X, y, feature_names = engine.build(events)
                X = np.nan_to_num(np.array(X, dtype=np.float32))
                y = np.array(y, dtype=np.float64)

                # Cache
                DATA_DIR.mkdir(parents=True, exist_ok=True)
                np.savez_compressed(
                    CACHE_PATH, X=X, y=y,
                    feature_names=np.array(feature_names),
                )
                log.info(f"Built and cached: {X.shape}")
                return X, y, feature_names
        except Exception as e:
            log.warning(f"Political engine failed: {e}")

    # 3. Fall back to synthetic data (political-like)
    log.info("No real political data — generating synthetic political data")
    X, y, feature_names = _generate_political_synthetic(
        n_events=CPU_TOTAL + 200,
        n_features=CPU_MAX_FEATURES,
    )

    # Cache it
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        CACHE_PATH, X=X, y=y,
        feature_names=np.array(feature_names),
    )
    return X, y, feature_names


def _generate_political_synthetic(
    n_events: int = 600,
    n_features: int = 200,
    seed: int = 73,
) -> tuple:
    """
    Generate synthetic political-like data.

    Political events have different characteristics than NBA:
    - Fewer events (hundreds, not thousands)
    - More imbalanced outcomes (incumbents win more)
    - Different feature types (polling, economic, sentiment)
    - Higher noise (politics is less predictable)
    """
    rng = np.random.RandomState(seed)

    # Political feature categories
    categories = [
        "polling", "economic", "sentiment", "incumbency", "fundraising",
        "demographic", "historical", "media", "polymarket", "endorsement",
        "enforcement", "donation", "contract", "trade_policy",
    ]
    features_per_cat = n_features // len(categories)
    remainder = n_features - features_per_cat * len(categories)

    feature_names = []
    for cat in categories:
        for j in range(features_per_cat):
            feature_names.append(f"{cat}_{j:02d}")
    for j in range(remainder):
        feature_names.append(f"extra_{j:02d}")

    # Generate features
    X = rng.randn(n_events, n_features).astype(np.float32)

    # Make ~20 features informative
    n_informative = min(20, n_features)
    true_weights = np.zeros(n_features)
    informative_idx = rng.choice(n_features, n_informative, replace=False)
    true_weights[informative_idx] = rng.randn(n_informative) * 0.4

    # Slightly imbalanced target (55% base rate — like incumbent advantage)
    logit = X @ true_weights + 0.2 + rng.randn(n_events) * 1.8
    prob = 1.0 / (1.0 + np.exp(-logit))
    y = (rng.rand(n_events) < prob).astype(np.float64)

    # Add feature correlations within categories
    for i in range(0, n_features - 1, features_per_cat):
        end = min(i + features_per_cat, n_features)
        for j in range(i + 1, end):
            X[:, j] += X[:, i] * rng.uniform(0.05, 0.3)

    X = np.nan_to_num(X, nan=0.0)

    log.info(
        f"Synthetic political data: {n_events} events x {n_features} features, "
        f"y mean={y.mean():.3f}"
    )
    return X, y, feature_names


def run_karpathy_loop(iterations: int, gpu: bool, verbose: bool) -> None:
    """Main Karpathy iteration loop for political alpha."""

    # Setup logging
    date_str = datetime.now().strftime("%Y-%m-%d")
    log_file = LOG_DIR / f"political-{date_str}.log"
    setup_logging(str(log_file), verbose)

    log.info("=" * 60)
    log.info("POLITICAL ALPHA KARPATHY ITERATION LOOP")
    log.info(f"Mode: {'GPU' if gpu else 'CPU'}")
    log.info(f"Iterations: {iterations}")
    log.info("=" * 60)

    # Load data
    t0 = time.time()
    X_all, y_all, feature_names = load_real_political_data()
    n_total_features = X_all.shape[1]
    log.info(f"Data loaded in {time.time() - t0:.1f}s: {X_all.shape[0]} events x {n_total_features} features")

    # Split into train/val
    if gpu:
        n_val = int(len(y_all) * GPU_VAL_RATIO)
        n_train = len(y_all) - n_val
        max_features = min(GPU_MAX_FEATURES, n_total_features)
        timeout = GPU_TIMEOUT
    else:
        total = min(CPU_TOTAL, len(y_all))
        n_val = min(CPU_VAL_EVENTS, total // 5)
        n_train = total - n_val
        max_features = min(CPU_MAX_FEATURES, n_total_features)
        timeout = CPU_TIMEOUT

    # Temporal split
    X_train = X_all[:n_train]
    y_train = y_all[:n_train]
    X_val = X_all[n_train : n_train + n_val]
    y_val = y_all[n_train : n_train + n_val]

    log.info(f"Train: {X_train.shape[0]} events | Val: {X_val.shape[0]} events")

    # Load or create starting config
    config = load_best_config(str(CONFIG_PATH), n_total_features)
    if config["n_features"] < 10:
        config = default_config(n_total_features)

    # Evaluate baseline
    log.info("Evaluating baseline config...")
    baseline_brier = evaluate_config(config, X_train, y_train, X_val, y_val, timeout)
    if config.get("best_brier", 1.0) >= 1.0:
        config["best_brier"] = baseline_brier
    log.info(f"Baseline Brier: {baseline_brier:.5f}")

    # Iteration state
    history = []
    improvements = 0
    best_brier = config["best_brier"]
    start_brier = best_brier
    start_time = time.time()
    jsonl_log = LOG_DIR / f"political-iterations-{date_str}.jsonl"

    telegram_alert(
        f"*Political Karpathy Loop Started*\n"
        f"Mode: {'GPU' if gpu else 'CPU'}\n"
        f"Iterations: {iterations}\n"
        f"Baseline Brier: {baseline_brier:.5f}\n"
        f"Train: {n_train} | Val: {n_val} events"
    )

    # ── MAIN LOOP ──
    for i in range(1, iterations + 1):
        iter_start = time.time()

        # Mutate
        candidate, mutation_desc = mutate_config(config, n_total_features)

        # Cap features
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
            delta = best_brier - score
            log.info(
                f"[{i}/{iterations}] IMPROVED {mutation_desc} | "
                f"Brier: {best_brier:.5f} -> {score:.5f} (delta={delta:.5f}) | "
                f"{elapsed:.1f}s"
            )

            best_brier = score
            config = candidate
            config["best_brier"] = best_brier
            config["iteration"] = i
            save_config(config, str(CONFIG_PATH))

            if delta > 0.001:
                telegram_alert(
                    f"*Political: Significant Improvement!*\n"
                    f"Iteration {i}/{iterations}\n"
                    f"Brier: {best_brier + delta:.5f} -> {best_brier:.5f}\n"
                    f"Delta: -{delta:.5f}\n"
                    f"Mutation: {mutation_desc}\n"
                    f"Model: {config['model_type']}, Features: {config['n_features']}"
                )
        else:
            if i % 10 == 0 or verbose:
                log.info(
                    f"[{i}/{iterations}] no improvement | {mutation_desc} | "
                    f"Brier: {score:.5f} (best: {best_brier:.5f}) | {elapsed:.1f}s"
                )

        # Record
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
        log_iteration(i, score, improved, mutation_desc, candidate, str(jsonl_log))

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
        f"POLITICAL KARPATHY LOOP — FINAL REPORT\n"
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

    telegram_alert(
        f"*Political Karpathy Loop Complete*\n"
        f"Iterations: {iterations}\n"
        f"Improvements: {improvements}\n"
        f"Brier: {start_brier:.5f} -> {best_brier:.5f}\n"
        f"Delta: {'-' if total_delta > 0 else '+'}{abs(total_delta):.5f}\n"
        f"Model: {config['model_type']}, Features: {config['n_features']}\n"
        f"Time: {total_time/60:.1f} min ({iterations/(total_time/60):.1f} iter/min)"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Political Alpha Karpathy Iteration Loop — autonomous model improvement"
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
