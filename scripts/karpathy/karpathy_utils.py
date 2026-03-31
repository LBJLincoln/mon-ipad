#!/usr/bin/env python3
"""
Karpathy Iteration Loop — Common Utilities
============================================
Shared mutation, evaluation, logging, and alerting functions
used by both NBA and Political iteration loops.

Pattern: modify config -> run fast test -> measure metric -> keep if better -> repeat
"""

import os
import sys
import json
import copy
import time
import random
import logging
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
from sklearn.metrics import brier_score_loss
from sklearn.ensemble import (
    RandomForestClassifier,
    ExtraTreesClassifier,
    GradientBoostingClassifier,
)

# ── Constants ──
MODEL_TYPES = ["random_forest", "extra_trees", "gradient_boosting"]
MUTATION_TYPES = [
    "change_model",
    "change_n_estimators",
    "change_max_depth",
    "change_min_samples_leaf",
    "change_max_features_ratio",
    "add_features",
    "remove_features",
    "swap_features",
]

# Hyperparameter bounds
BOUNDS = {
    "n_estimators": (50, 500),
    "max_depth": (4, 30),
    "min_samples_leaf": (1, 20),
    "max_features_ratio": (0.05, 0.80),
}

log = logging.getLogger("karpathy")


# ══════════════════════════════════════════════════════════
# CONFIG MANAGEMENT
# ══════════════════════════════════════════════════════════

def default_config(n_total_features: int) -> Dict[str, Any]:
    """Create a sensible default starting config."""
    n_features = min(80, n_total_features)
    indices = sorted(random.sample(range(n_total_features), n_features))
    return {
        "model_type": "extra_trees",
        "n_estimators": 200,
        "max_depth": 12,
        "min_samples_leaf": 5,
        "max_features_ratio": 0.3,
        "feature_indices": indices,
        "n_features": n_features,
        "best_brier": 1.0,
        "iteration": 0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def load_best_config(path: str, n_total_features: int) -> Dict[str, Any]:
    """Load best config from JSON, or create default if missing."""
    p = Path(path)
    if p.exists():
        try:
            cfg = json.loads(p.read_text())
            # Validate feature indices against available features
            cfg["feature_indices"] = [
                i for i in cfg.get("feature_indices", [])
                if 0 <= i < n_total_features
            ]
            cfg["n_features"] = len(cfg["feature_indices"])
            log.info(
                f"Loaded config: model={cfg['model_type']}, "
                f"features={cfg['n_features']}, brier={cfg.get('best_brier', '?')}"
            )
            return cfg
        except (json.JSONDecodeError, KeyError) as e:
            log.warning(f"Bad config at {path}: {e} — using default")
    return default_config(n_total_features)


def save_config(config: Dict[str, Any], path: str) -> None:
    """Save config to JSON atomically."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    config["timestamp"] = datetime.now(timezone.utc).isoformat()
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(config, indent=2))
    tmp.rename(p)


def save_if_better(
    config: Dict[str, Any], score: float, path: str
) -> bool:
    """Save config only if score is strictly better (lower Brier). Returns True if saved."""
    current = load_best_config(path, n_total_features=max(config.get("feature_indices", [0])) + 1)
    if score < current.get("best_brier", 1.0):
        config["best_brier"] = score
        save_config(config, path)
        log.info(f"NEW BEST: {score:.5f} (was {current.get('best_brier', 1.0):.5f})")
        return True
    return False


# ══════════════════════════════════════════════════════════
# MUTATION
# ══════════════════════════════════════════════════════════

def _clamp(val, lo, hi):
    return max(lo, min(hi, val))


def mutate_config(
    config: Dict[str, Any], n_total_features: int
) -> Tuple[Dict[str, Any], str]:
    """
    Mutate exactly ONE thing in the config. Returns (new_config, mutation_description).
    """
    cfg = copy.deepcopy(config)
    mutation = random.choice(MUTATION_TYPES)
    indices = set(cfg.get("feature_indices", []))

    if mutation == "change_model":
        old = cfg["model_type"]
        candidates = [m for m in MODEL_TYPES if m != old]
        cfg["model_type"] = random.choice(candidates)
        desc = f"model: {old} -> {cfg['model_type']}"

    elif mutation == "change_n_estimators":
        old = cfg["n_estimators"]
        delta = random.choice([-100, -50, -25, 25, 50, 100])
        cfg["n_estimators"] = _clamp(old + delta, *BOUNDS["n_estimators"])
        desc = f"n_estimators: {old} -> {cfg['n_estimators']}"

    elif mutation == "change_max_depth":
        old = cfg["max_depth"]
        delta = random.choice([-3, -2, -1, 1, 2, 3])
        cfg["max_depth"] = _clamp(old + delta, *BOUNDS["max_depth"])
        desc = f"max_depth: {old} -> {cfg['max_depth']}"

    elif mutation == "change_min_samples_leaf":
        old = cfg["min_samples_leaf"]
        delta = random.choice([-3, -2, -1, 1, 2, 3])
        cfg["min_samples_leaf"] = _clamp(old + delta, *BOUNDS["min_samples_leaf"])
        desc = f"min_samples_leaf: {old} -> {cfg['min_samples_leaf']}"

    elif mutation == "change_max_features_ratio":
        old = cfg["max_features_ratio"]
        delta = random.choice([-0.1, -0.05, -0.02, 0.02, 0.05, 0.1])
        cfg["max_features_ratio"] = round(
            _clamp(old + delta, *BOUNDS["max_features_ratio"]), 3
        )
        desc = f"max_features_ratio: {old} -> {cfg['max_features_ratio']}"

    elif mutation == "add_features":
        available = set(range(n_total_features)) - indices
        if len(available) >= 5:
            new = random.sample(sorted(available), 5)
            indices.update(new)
            desc = f"add 5 features (now {len(indices)})"
        else:
            desc = "add_features: no features to add, skipped"

    elif mutation == "remove_features":
        if len(indices) > 15:  # Never go below 15 features
            to_remove = random.sample(sorted(indices), min(5, len(indices) - 15))
            indices -= set(to_remove)
            desc = f"remove {len(to_remove)} features (now {len(indices)})"
        else:
            desc = "remove_features: too few features, skipped"

    elif mutation == "swap_features":
        available = set(range(n_total_features)) - indices
        n_swap = min(10, len(indices) - 15, len(available))
        if n_swap > 0:
            to_remove = random.sample(sorted(indices), n_swap)
            to_add = random.sample(sorted(available), n_swap)
            indices -= set(to_remove)
            indices.update(to_add)
            desc = f"swap {n_swap} features (total {len(indices)})"
        else:
            desc = "swap_features: not enough features, skipped"
    else:
        desc = f"unknown mutation {mutation}"

    cfg["feature_indices"] = sorted(indices)
    cfg["n_features"] = len(cfg["feature_indices"])
    return cfg, desc


# ══════════════════════════════════════════════════════════
# MODEL BUILDING
# ══════════════════════════════════════════════════════════

def build_model(config: Dict[str, Any]):
    """Build a sklearn classifier from config dict."""
    model_type = config["model_type"]
    common = {
        "n_estimators": config["n_estimators"],
        "max_depth": config["max_depth"],
        "min_samples_leaf": config["min_samples_leaf"],
        "max_features": config["max_features_ratio"],
        "random_state": 42,
        "n_jobs": -1,
    }

    if model_type == "random_forest":
        return RandomForestClassifier(**common)
    elif model_type == "extra_trees":
        return ExtraTreesClassifier(**common)
    elif model_type == "gradient_boosting":
        # GradientBoosting doesn't support n_jobs, max_features is different
        return GradientBoostingClassifier(
            n_estimators=min(config["n_estimators"], 300),  # Cap for speed
            max_depth=min(config["max_depth"], 8),  # Cap for speed
            min_samples_leaf=config["min_samples_leaf"],
            max_features=config["max_features_ratio"],
            random_state=42,
            learning_rate=0.1,
            subsample=0.8,
        )
    else:
        raise ValueError(f"Unknown model_type: {model_type}")


# ══════════════════════════════════════════════════════════
# EVALUATION
# ══════════════════════════════════════════════════════════

def evaluate_config(
    config: Dict[str, Any],
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    timeout_seconds: int = 180,
) -> float:
    """
    Train model with config, return Brier score on validation set.
    Returns 1.0 on any failure (worst possible Brier).
    """
    try:
        feature_idx = config["feature_indices"]
        if not feature_idx:
            return 1.0

        # Select features
        X_tr = X_train[:, feature_idx]
        X_va = X_val[:, feature_idx]

        # Replace any remaining NaN/inf
        X_tr = np.nan_to_num(X_tr, nan=0.0, posinf=0.0, neginf=0.0)
        X_va = np.nan_to_num(X_va, nan=0.0, posinf=0.0, neginf=0.0)

        # Build and train
        t0 = time.time()
        model = build_model(config)
        model.fit(X_tr, y_train)

        elapsed = time.time() - t0
        if elapsed > timeout_seconds:
            log.warning(f"Training took {elapsed:.0f}s (limit {timeout_seconds}s)")

        # Predict probabilities
        proba = model.predict_proba(X_va)
        if proba.shape[1] == 2:
            y_prob = proba[:, 1]
        else:
            y_prob = proba[:, 0]

        # Clip to avoid extreme probabilities
        y_prob = np.clip(y_prob, 0.001, 0.999)

        brier = brier_score_loss(y_val, y_prob)
        log.debug(
            f"Eval: model={config['model_type']}, feat={len(feature_idx)}, "
            f"brier={brier:.5f}, time={elapsed:.1f}s"
        )
        return brier

    except Exception as e:
        log.error(f"Evaluation failed: {e}")
        return 1.0


# ══════════════════════════════════════════════════════════
# LOGGING
# ══════════════════════════════════════════════════════════

def log_iteration(
    iteration: int,
    score: float,
    improved: bool,
    mutation_desc: str,
    config: Dict[str, Any],
    log_path: str,
) -> None:
    """Append one iteration record to a JSONL log file."""
    p = Path(log_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "iteration": iteration,
        "brier": round(score, 6),
        "improved": improved,
        "mutation": mutation_desc,
        "model_type": config["model_type"],
        "n_features": config["n_features"],
        "n_estimators": config["n_estimators"],
        "max_depth": config["max_depth"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    with open(p, "a") as f:
        f.write(json.dumps(record) + "\n")


def save_history(history: List[Dict], path: str) -> None:
    """Save full iteration history to JSON."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(history, indent=2))


# ══════════════════════════════════════════════════════════
# TELEGRAM ALERTS
# ══════════════════════════════════════════════════════════

def telegram_alert(message: str) -> bool:
    """
    Send a Telegram alert using TELEGRAM_BOT_TOKEN and ADMIN_TELEGRAM_ID env vars.
    Returns True if sent successfully, False otherwise.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("ADMIN_TELEGRAM_ID", "")

    if not token or not chat_id:
        log.debug("Telegram alert skipped: no TELEGRAM_BOT_TOKEN or ADMIN_TELEGRAM_ID")
        return False

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        # Use HTML parse mode — more forgiving than Markdown with special chars
        # Convert *bold* to <b>bold</b> for Telegram HTML
        html_msg = message.replace("*", "").replace("_", "")
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": html_msg,
        }).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        log.warning(f"Telegram alert failed: {e}")
        return False


# ══════════════════════════════════════════════════════════
# DATA LOADING / SYNTHETIC DATA
# ══════════════════════════════════════════════════════════

def generate_synthetic_data(
    n_games: int = 5000,
    n_features: int = 200,
    seed: int = 42,
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """
    Generate synthetic NBA-like data for immediate iteration testing.

    The synthetic data has realistic properties:
    - Features are correlated (not random noise)
    - Target has ~50% base rate (like home win probability)
    - Achievable Brier is ~0.23 (similar to real data)
    - Some features are informative, many are noise
    """
    rng = np.random.RandomState(seed)

    # Create feature names
    feature_names = [f"feat_{i:03d}" for i in range(n_features)]

    # Generate base features
    X = rng.randn(n_games, n_features).astype(np.float32)

    # Make ~30 features informative (correlated with target)
    n_informative = min(30, n_features)
    true_weights = np.zeros(n_features)
    informative_idx = rng.choice(n_features, n_informative, replace=False)
    true_weights[informative_idx] = rng.randn(n_informative) * 0.5

    # Generate target: logistic model + noise
    logit = X @ true_weights + rng.randn(n_games) * 1.5  # Noise for ~0.23 Brier
    prob = 1.0 / (1.0 + np.exp(-logit))
    y = (rng.rand(n_games) < prob).astype(np.float64)

    # Add some realistic feature correlations
    for i in range(0, n_features - 1, 2):
        X[:, i + 1] += X[:, i] * rng.uniform(0.1, 0.5)  # Correlated pairs

    # Add NaN sparingly (like real data)
    nan_mask = rng.rand(n_games, n_features) < 0.01
    X[nan_mask] = np.nan
    X = np.nan_to_num(X, nan=0.0)

    log.info(
        f"Synthetic data: {n_games} games x {n_features} features, "
        f"y mean={y.mean():.3f}, informative={n_informative}"
    )
    return X, y, feature_names


def load_or_create_cached_data(
    cache_path: str,
    n_games: int = 5000,
    n_features: int = 200,
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """Load cached data or create synthetic data for first run."""
    p = Path(cache_path)
    if p.exists():
        try:
            data = np.load(p, allow_pickle=True)
            X = data["X"]
            y = data["y"]
            feature_names = list(data["feature_names"])
            log.info(f"Loaded cached data: {X.shape}")
            return X, y, feature_names
        except Exception as e:
            log.warning(f"Cache corrupt ({e}), regenerating...")

    X, y, feature_names = generate_synthetic_data(n_games, n_features)

    # Save cache
    p.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(p, X=X, y=y, feature_names=np.array(feature_names))
    log.info(f"Saved data cache: {p}")

    return X, y, feature_names


def setup_logging(log_file: str, verbose: bool = False) -> None:
    """Configure logging to both file and console."""
    p = Path(log_file)
    p.parent.mkdir(parents=True, exist_ok=True)

    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s [%(levelname)s] %(message)s"

    logging.basicConfig(
        level=level,
        format=fmt,
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout),
        ],
    )
