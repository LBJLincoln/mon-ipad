#!/usr/bin/env python3
"""
Nomos42 Karpathy Arena — HF Space
===================================
Runs the Karpathy iteration loop + Arena backtest entirely on HF Space CPU.
No VM dependency. No external APIs. Self-contained.

Tabs:
  1. Karpathy Loop  — continuous iteration, mutate -> train -> measure Brier -> keep if better
  2. Arena Simulator — 11 strategies x 6 models x synthetic season
  3. Metrics         — live stats, best config JSON, improvement history
"""

import copy
import hashlib
import json
import math
import random
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import gradio as gr
import numpy as np
import pandas as pd
from sklearn.ensemble import (
    ExtraTreesClassifier,
    GradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.metrics import brier_score_loss

# ──────────────────────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────────────────────

N_GAMES = 5000
N_FEATURES = 150
N_TRAIN = 4000
N_VAL = 500          # last 500 games held out
MAX_FEATURES_CAP = 120

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
BOUNDS = {
    "n_estimators": (50, 400),
    "max_depth": (4, 20),
    "min_samples_leaf": (1, 20),
    "max_features_ratio": (0.05, 0.80),
}

# Arena constants
ARENA_N_GAMES = 1000          # synthetic season length
ARENA_SEED = 99

# ──────────────────────────────────────────────────────────────
# SHARED STATE (thread-safe via GIL + simple dict swap)
# ──────────────────────────────────────────────────────────────

state = {
    "best_config": None,
    "best_brier": 1.0,
    "iterations": 0,
    "improvements": 0,
    "log": [],           # list of log line strings (newest first)
    "history": [],       # list of {"iter", "brier", "best_brier", "improved", "mutation"}
    "running": False,
    "start_time": None,
    "arena_result": None,    # cached arena leaderboard
    "arena_running": False,
    "data_ready": False,
}

# Synthetic data — generated once at startup
_X: Optional[np.ndarray] = None
_y: Optional[np.ndarray] = None
_feature_names: Optional[List[str]] = None


# ──────────────────────────────────────────────────────────────
# SYNTHETIC DATA
# ──────────────────────────────────────────────────────────────

def generate_synthetic_data(
    n_games: int = 5000,
    n_features: int = 150,
    seed: int = 42,
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """
    Synthetic NBA-like data with realistic properties.
    ~30 informative features, correlated pairs, ~1% NaN.
    Achievable Brier: ~0.23 (similar to real data floor).
    """
    rng = np.random.RandomState(seed)
    feature_names = [f"feat_{i:03d}" for i in range(n_features)]

    X = rng.randn(n_games, n_features).astype(np.float32)

    # 30 informative features
    n_informative = min(30, n_features)
    true_weights = np.zeros(n_features)
    informative_idx = rng.choice(n_features, n_informative, replace=False)
    true_weights[informative_idx] = rng.randn(n_informative) * 0.5

    # Logistic target with noise
    logit = X @ true_weights + rng.randn(n_games) * 1.5
    prob = 1.0 / (1.0 + np.exp(-logit))
    y = (rng.rand(n_games) < prob).astype(np.float64)

    # Correlated pairs
    for i in range(0, n_features - 1, 2):
        X[:, i + 1] += X[:, i] * rng.uniform(0.1, 0.5)

    # Sparse NaN
    nan_mask = rng.rand(n_games, n_features) < 0.01
    X[nan_mask] = np.nan
    X = np.nan_to_num(X, nan=0.0)

    return X, y, feature_names


def init_data() -> None:
    global _X, _y, _feature_names
    _X, _y, _feature_names = generate_synthetic_data(N_GAMES, N_FEATURES, seed=42)
    state["data_ready"] = True


# ──────────────────────────────────────────────────────────────
# CONFIG HELPERS
# ──────────────────────────────────────────────────────────────

def _clamp(val, lo, hi):
    return max(lo, min(hi, val))


def default_config(n_total: int) -> Dict[str, Any]:
    n_feat = min(80, n_total)
    indices = sorted(random.sample(range(n_total), n_feat))
    return {
        "model_type": "extra_trees",
        "n_estimators": 150,
        "max_depth": 12,
        "min_samples_leaf": 5,
        "max_features_ratio": 0.3,
        "feature_indices": indices,
        "n_features": n_feat,
        "best_brier": 1.0,
        "iteration": 0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def mutate_config(
    config: Dict[str, Any], n_total: int
) -> Tuple[Dict[str, Any], str]:
    """Mutate exactly one thing. Returns (new_config, description)."""
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
        available = set(range(n_total)) - indices
        n_add = min(5, len(available))
        if n_add > 0:
            new = random.sample(sorted(available), n_add)
            indices.update(new)
            desc = f"add {n_add} features (now {len(indices)})"
        else:
            desc = "add_features: skipped (no available)"

    elif mutation == "remove_features":
        if len(indices) > 15:
            n_rm = min(5, len(indices) - 15)
            to_remove = random.sample(sorted(indices), n_rm)
            indices -= set(to_remove)
            desc = f"remove {n_rm} features (now {len(indices)})"
        else:
            desc = "remove_features: skipped (too few)"

    elif mutation == "swap_features":
        available = set(range(n_total)) - indices
        n_swap = min(10, len(indices) - 15, len(available))
        if n_swap > 0:
            to_remove = random.sample(sorted(indices), n_swap)
            to_add = random.sample(sorted(available), n_swap)
            indices -= set(to_remove)
            indices.update(to_add)
            desc = f"swap {n_swap} features (total {len(indices)})"
        else:
            desc = "swap_features: skipped"
    else:
        desc = f"unknown mutation: {mutation}"

    # Enforce cap
    if len(indices) > MAX_FEATURES_CAP:
        indices = set(sorted(indices)[:MAX_FEATURES_CAP])

    cfg["feature_indices"] = sorted(indices)
    cfg["n_features"] = len(cfg["feature_indices"])
    return cfg, desc


# ──────────────────────────────────────────────────────────────
# MODEL BUILD + EVALUATE
# ──────────────────────────────────────────────────────────────

def build_model(config: Dict[str, Any]):
    common = {
        "n_estimators": config["n_estimators"],
        "max_depth": config["max_depth"],
        "min_samples_leaf": config["min_samples_leaf"],
        "max_features": config["max_features_ratio"],
        "random_state": 42,
    }
    mt = config["model_type"]
    if mt == "random_forest":
        return RandomForestClassifier(**common, n_jobs=2)
    elif mt == "extra_trees":
        return ExtraTreesClassifier(**common, n_jobs=2)
    elif mt == "gradient_boosting":
        return GradientBoostingClassifier(
            n_estimators=min(config["n_estimators"], 200),
            max_depth=min(config["max_depth"], 8),
            min_samples_leaf=config["min_samples_leaf"],
            max_features=config["max_features_ratio"],
            learning_rate=0.1,
            subsample=0.8,
            random_state=42,
        )
    raise ValueError(f"Unknown model_type: {mt}")


def evaluate_config(
    config: Dict[str, Any],
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
) -> float:
    """Train and return Brier score. Returns 1.0 on failure."""
    try:
        idx = config["feature_indices"]
        if not idx:
            return 1.0
        Xtr = np.nan_to_num(X_train[:, idx], nan=0.0, posinf=0.0, neginf=0.0)
        Xva = np.nan_to_num(X_val[:, idx], nan=0.0, posinf=0.0, neginf=0.0)
        model = build_model(config)
        model.fit(Xtr, y_train)
        proba = model.predict_proba(Xva)
        y_prob = proba[:, 1] if proba.shape[1] == 2 else proba[:, 0]
        y_prob = np.clip(y_prob, 0.001, 0.999)
        return float(brier_score_loss(y_val, y_prob))
    except Exception as e:
        return 1.0


# ──────────────────────────────────────────────────────────────
# BACKGROUND KARPATHY LOOP
# ──────────────────────────────────────────────────────────────

_loop_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()


def _add_log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    state["log"].insert(0, f"[{ts}] {msg}")
    if len(state["log"]) > 200:
        state["log"] = state["log"][:200]


def _karpathy_worker() -> None:
    """Runs forever (1 iteration per ~30-60s). Stopped via _stop_event."""
    global _X, _y

    # Wait for data
    while not state["data_ready"] and not _stop_event.is_set():
        time.sleep(1)
    if _stop_event.is_set():
        return

    n_total = _X.shape[1]
    X_train = _X[:N_TRAIN]
    y_train = _y[:N_TRAIN]
    X_val = _X[N_TRAIN: N_TRAIN + N_VAL]
    y_val = _y[N_TRAIN: N_TRAIN + N_VAL]

    # Init config if not set
    if state["best_config"] is None:
        cfg = default_config(n_total)
        _add_log("Evaluating baseline config...")
        brier = evaluate_config(cfg, X_train, y_train, X_val, y_val)
        cfg["best_brier"] = brier
        state["best_config"] = cfg
        state["best_brier"] = brier
        _add_log(f"Baseline Brier: {brier:.5f}")

    state["running"] = True
    state["start_time"] = time.time()

    while not _stop_event.is_set():
        t0 = time.time()
        current_cfg = state["best_config"]
        best_brier = state["best_brier"]

        candidate, mut_desc = mutate_config(current_cfg, n_total)
        score = evaluate_config(candidate, X_train, y_train, X_val, y_val)
        elapsed = time.time() - t0

        state["iterations"] += 1
        i = state["iterations"]
        improved = score < best_brier

        if improved:
            delta = best_brier - score
            state["improvements"] += 1
            candidate["best_brier"] = score
            candidate["iteration"] = i
            candidate["timestamp"] = datetime.now(timezone.utc).isoformat()
            state["best_config"] = candidate
            state["best_brier"] = score
            _add_log(
                f"[{i}] IMPROVED {mut_desc} | "
                f"Brier: {best_brier:.5f} -> {score:.5f} (delta=-{delta:.5f}) | "
                f"{elapsed:.1f}s"
            )
        else:
            if i % 5 == 0:
                _add_log(
                    f"[{i}] {mut_desc} | "
                    f"Brier: {score:.5f} (best: {best_brier:.5f}) | "
                    f"{elapsed:.1f}s"
                )

        state["history"].append({
            "iter": i,
            "brier": round(score, 6),
            "best_brier": round(state["best_brier"], 6),
            "improved": improved,
            "mutation": mut_desc,
            "model": candidate["model_type"],
            "n_features": candidate["n_features"],
        })
        # Keep history bounded
        if len(state["history"]) > 500:
            state["history"] = state["history"][-500:]

        # Pace: don't spin-loop on HF CPU
        sleep_remaining = max(0, 5 - elapsed)  # minimum 5s between iters
        _stop_event.wait(timeout=sleep_remaining)

    state["running"] = False


def start_loop() -> None:
    global _loop_thread
    if _loop_thread and _loop_thread.is_alive():
        return
    _stop_event.clear()
    _loop_thread = threading.Thread(target=_karpathy_worker, daemon=True)
    _loop_thread.start()


def stop_loop() -> None:
    _stop_event.set()


# ──────────────────────────────────────────────────────────────
# ARENA SIMULATOR
# ──────────────────────────────────────────────────────────────

ARENA_MODELS = {
    "tabicl":        {"brier": 0.2157, "noise": 0.015},
    "catboost":      {"brier": 0.2204, "noise": 0.020},
    "xgboost":       {"brier": 0.2205, "noise": 0.020},
    "lightgbm":      {"brier": 0.2208, "noise": 0.022},
    "extra_trees":   {"brier": 0.2225, "noise": 0.025},
    "random_forest": {"brier": 0.2245, "noise": 0.028},
}

ARENA_STRATEGIES = {
    "full_kelly":          {"family": "kelly",      "fraction": 1.0,  "min_edge": 0.02, "max_pct": 0.25},
    "half_kelly":          {"family": "kelly",      "fraction": 0.5,  "min_edge": 0.02, "max_pct": 0.15},
    "quarter_kelly":       {"family": "kelly",      "fraction": 0.25, "min_edge": 0.03, "max_pct": 0.08},
    "flat_2pct":           {"family": "flat",       "bet_pct": 0.02,  "min_edge": 0.01, "max_pct": 0.02},
    "flat_5pct":           {"family": "flat",       "bet_pct": 0.05,  "min_edge": 0.02, "max_pct": 0.05},
    "confidence_scaled":   {"family": "confidence",               "min_edge": 0.02, "max_pct": 0.20},
    "value_hunter":        {"family": "value",                    "min_edge": 0.05, "max_pct": 0.12},
    "underdog_specialist": {"family": "underdog",  "min_odds": 2.2,  "min_edge": 0.03, "max_pct": 0.08},
    "totals_expert":       {"family": "kelly",      "fraction": 0.5,  "min_edge": 0.02, "max_pct": 0.15},
    "first_half_sniper":   {"family": "kelly",      "fraction": 0.5,  "min_edge": 0.02, "max_pct": 0.15},
    "full_blast":          {"family": "full_blast",               "min_edge": 0.01, "max_pct": 1.00},
}


def _kelly_size(p: float, odds: float, fraction: float = 1.0) -> float:
    b = odds - 1
    if b <= 0:
        return 0.0
    edge = p * b - (1 - p)
    if edge <= 0:
        return 0.0
    return max(0.0, (edge / b) * fraction)


def _get_bet_size(strat_name: str, prob: float, odds: float, bankroll: float) -> float:
    cfg = ARENA_STRATEGIES[strat_name]
    edge = prob * (odds - 1) - (1 - prob)
    if edge < cfg["min_edge"]:
        return 0.0
    if cfg["family"] == "underdog" and odds < cfg.get("min_odds", 2.2):
        return 0.0
    max_bet = bankroll * cfg["max_pct"]
    if cfg["family"] == "kelly":
        bet = _kelly_size(prob, odds, cfg["fraction"]) * bankroll
    elif cfg["family"] == "flat":
        bet = bankroll * cfg["bet_pct"]
    elif cfg["family"] == "confidence":
        conf = (abs(prob - 0.5) * 2) ** 2
        bet = conf * max_bet
    elif cfg["family"] in ("value", "underdog"):
        bet = _kelly_size(prob, odds, 0.5) * bankroll
    elif cfg["family"] == "full_blast":
        bet = bankroll
    else:
        bet = bankroll * 0.02
    return min(max(bet, 0.0), max_bet)


def _model_prob(model_name: str, implied_prob: float, seed_val: str) -> float:
    noise_std = ARENA_MODELS[model_name]["noise"]
    h = int(hashlib.md5(f"{model_name}_{seed_val}".encode()).hexdigest()[:8], 16)
    u1 = (h % 10000) / 10000.0 + 0.0001
    u2 = ((h // 10000) % 10000) / 10000.0 + 0.0001
    noise = math.sqrt(-2 * math.log(u1)) * math.cos(2 * math.pi * u2) * noise_std
    return max(0.05, min(0.95, implied_prob + noise))


def _gen_synthetic_season(n_games: int, seed: int) -> List[Dict]:
    """Generate synthetic NBA season data with realistic odds."""
    rng = np.random.RandomState(seed)
    games = []
    teams = [
        "BOS", "NYK", "MIL", "CLE", "OKC", "DEN", "MIN", "LAL",
        "MIA", "PHI", "IND", "ATL", "GSW", "PHX", "LAC", "MEM",
        "HOU", "DAL", "SAC", "NOP",
    ]
    for i in range(n_games):
        home_idx, away_idx = rng.choice(len(teams), 2, replace=False)
        home = teams[home_idx]
        away = teams[away_idx]
        # Realistic moneyline: home team is slight favourite ~57% of time
        home_win_prob = rng.uniform(0.40, 0.70)
        home_ml_dec = 1.0 / home_win_prob * 0.95   # 5% vig
        away_ml_dec = 1.0 / (1 - home_win_prob) * 0.95
        total = rng.uniform(208, 232)
        spread = (home_win_prob - 0.5) * 20
        home_won = rng.rand() < home_win_prob
        home_score = rng.randint(95, 130)
        away_score = rng.randint(95, 130) if not home_won else rng.randint(85, int(home_score))
        games.append({
            "game_id": i,
            "home": home,
            "away": away,
            "home_win_prob_true": home_win_prob,
            "home_won": bool(home_won),
            "home_score": int(home_score),
            "away_score": int(away_score),
            "ml_home_dec": round(home_ml_dec, 3),
            "ml_away_dec": round(away_ml_dec, 3),
            "spread_home": round(spread, 1),
            "total": round(total, 1),
        })
    return games


def run_arena_simulation(n_games: int = ARENA_N_GAMES) -> List[Dict]:
    """
    Run 11 strategies x 6 models x synthetic season.
    Returns leaderboard sorted by final bankroll.
    """
    games = _gen_synthetic_season(n_games, seed=ARENA_SEED)

    competitors = {}
    for m in ARENA_MODELS:
        for s in ARENA_STRATEGIES:
            k = f"{m}__{s}"
            competitors[k] = {
                "model": m, "strategy": s,
                "bankroll": 100.0, "peak": 100.0,
                "bets": 0, "wins": 0, "losses": 0,
                "total_wagered": 0.0,
                "max_drawdown": 0.0,
                "daily_returns": [],
                "active": True,
            }

    for game in games:
        implied_home = 1.0 / game["ml_home_dec"]
        seed_val = f"{game['game_id']}_{game['home']}_{game['away']}"

        for comp_key, comp in competitors.items():
            if not comp["active"]:
                continue
            m = comp["model"]
            s = comp["strategy"]
            cfg = ARENA_STRATEGIES[s]
            start_br = comp["bankroll"]
            day_pnl = 0.0

            prob = _model_prob(m, implied_home, seed_val)
            home_won = game["home_won"]

            bets_available = {
                "ml_home": (game["ml_home_dec"], home_won),
                "ml_away": (game["ml_away_dec"], not home_won),
            }
            margin = game["home_score"] - game["away_score"]
            bets_available["spread_home"] = (1.91, margin > -game["spread_home"])
            bets_available["spread_away"] = (1.91, margin <= -game["spread_home"])
            game_total = game["home_score"] + game["away_score"]
            bets_available["total_over"] = (1.91, game_total > game["total"])
            bets_available["total_under"] = (1.91, game_total <= game["total"])

            bet_probs = {
                "ml_home": prob,
                "ml_away": 1 - prob,
                "spread_home": 0.52 + (prob - 0.5) * 0.3,
                "spread_away": 0.48 + (0.5 - prob) * 0.3,
                "total_over": 0.50 + (prob - 0.5) * 0.15,
                "total_under": 0.50 - (prob - 0.5) * 0.15,
            }

            is_full_blast = (cfg["family"] == "full_blast")
            candidates = []

            for bet_type, (bet_odds, bet_won) in bets_available.items():
                bp = bet_probs.get(bet_type, 0.5)
                if is_full_blast:
                    edge = bp * (bet_odds - 1) - (1 - bp)
                    if edge >= cfg["min_edge"]:
                        candidates.append((edge, bet_odds, bet_won))
                    continue

                bet_size = _get_bet_size(s, bp, bet_odds, comp["bankroll"])
                if bet_size < 0.01 or bet_size > comp["bankroll"]:
                    continue
                comp["bets"] += 1
                comp["total_wagered"] += bet_size
                if bet_won:
                    profit = bet_size * (bet_odds - 1)
                    comp["bankroll"] += profit
                    comp["wins"] += 1
                    day_pnl += profit
                else:
                    comp["bankroll"] -= bet_size
                    comp["losses"] += 1
                    day_pnl -= bet_size

            if is_full_blast and candidates and comp["bankroll"] >= 0.01:
                candidates.sort(reverse=True)
                _, best_odds, best_won = candidates[0]
                bet_size = comp["bankroll"]
                comp["bets"] += 1
                comp["total_wagered"] += bet_size
                if best_won:
                    profit = bet_size * (best_odds - 1)
                    comp["bankroll"] += profit
                    comp["wins"] += 1
                    day_pnl += profit
                else:
                    comp["bankroll"] -= bet_size
                    comp["losses"] += 1
                    day_pnl -= bet_size

            if comp["bankroll"] > comp["peak"]:
                comp["peak"] = comp["bankroll"]
            if comp["peak"] > 0:
                dd = 1 - comp["bankroll"] / comp["peak"]
                comp["max_drawdown"] = max(comp["max_drawdown"], dd)
            if start_br > 0:
                comp["daily_returns"].append(day_pnl / start_br)
            if comp["bankroll"] < 5.0:
                comp["active"] = False

    # Final metrics
    results = []
    for k, c in competitors.items():
        roi = (c["bankroll"] - 100) / 100 * 100
        rets = c["daily_returns"]
        if rets and len(rets) > 1:
            avg_r = sum(rets) / len(rets)
            std_r = (sum((r - avg_r) ** 2 for r in rets) / max(1, len(rets))) ** 0.5
            sharpe = avg_r / std_r * math.sqrt(252) if std_r > 0 else 0.0
        else:
            sharpe = 0.0
        win_rate = c["wins"] / max(1, c["bets"]) * 100
        results.append({
            "name": k,
            "model": c["model"],
            "strategy": c["strategy"],
            "bankroll": round(c["bankroll"], 2),
            "roi_pct": round(roi, 2),
            "sharpe": round(sharpe, 2),
            "bets": c["bets"],
            "wins": c["wins"],
            "losses": c["losses"],
            "win_rate": round(win_rate, 1),
            "max_drawdown": round(c["max_drawdown"] * 100, 1),
            "active": c["active"],
        })

    results.sort(key=lambda x: x["bankroll"], reverse=True)
    return results


# ──────────────────────────────────────────────────────────────
# GRADIO UI HELPERS
# ──────────────────────────────────────────────────────────────

def _fmt_config(cfg: Optional[Dict]) -> str:
    if cfg is None:
        return "No config yet — loop starting..."
    display = {k: v for k, v in cfg.items() if k != "feature_indices"}
    display["feature_indices_count"] = cfg.get("n_features", 0)
    return json.dumps(display, indent=2)


def _log_text() -> str:
    if not state["log"]:
        return "Loop starting — first iteration takes ~15s..."
    return "\n".join(state["log"][:80])


def _status_text() -> str:
    i = state["iterations"]
    imp = state["improvements"]
    brier = state["best_brier"]
    rate = imp / max(1, i) * 100
    elapsed = ""
    if state["start_time"]:
        secs = int(time.time() - state["start_time"])
        m, s = divmod(secs, 60)
        h, m = divmod(m, 60)
        elapsed = f"  |  Uptime: {h:02d}:{m:02d}:{s:02d}"
    running = "RUNNING" if state["running"] else "STOPPED"
    return (
        f"Status: {running}{elapsed}\n"
        f"Iterations: {i}  |  Improvements: {imp}  |  Rate: {rate:.1f}%\n"
        f"Best Brier: {brier:.5f}  |  Target: < 0.20000\n"
        f"Gap to target: {max(0, brier - 0.20):.5f}"
    )


def _history_table() -> List[List]:
    rows = []
    for h in reversed(state["history"][-50:]):
        flag = "YES" if h["improved"] else ""
        rows.append([
            h["iter"],
            f"{h['brier']:.5f}",
            f"{h['best_brier']:.5f}",
            flag,
            h["model"],
            h["n_features"],
            h["mutation"],
        ])
    return rows


def _arena_table(results: List[Dict]) -> List[List]:
    rows = []
    for i, r in enumerate(results[:30]):
        active = "YES" if r["active"] else "BUST"
        rows.append([
            i + 1,
            r["name"],
            r["model"],
            r["strategy"],
            f"${r['bankroll']:.2f}",
            f"{r['roi_pct']:+.1f}%",
            f"{r['sharpe']:.2f}",
            r["bets"],
            f"{r['win_rate']:.1f}%",
            f"{r['max_drawdown']:.1f}%",
            active,
        ])
    return rows


def _best_per_strategy(results: List[Dict]) -> List[List]:
    seen = {}
    for r in results:
        s = r["strategy"]
        if s not in seen:
            seen[s] = r
    rows = []
    for s, r in sorted(seen.items(), key=lambda x: x[1]["bankroll"], reverse=True):
        rows.append([s, r["model"], f"${r['bankroll']:.2f}", f"{r['roi_pct']:+.1f}%", f"{r['sharpe']:.2f}"])
    return rows


# ──────────────────────────────────────────────────────────────
# GRADIO APP
# ──────────────────────────────────────────────────────────────

def refresh_karpathy():
    """Called by auto-refresh timer on Tab 1."""
    return (
        _status_text(),
        _log_text(),
        _history_table(),
        _fmt_config(state["best_config"]),
    )


def refresh_metrics():
    """Called by auto-refresh timer on Tab 3."""
    i = state["iterations"]
    imp = state["improvements"]
    brier = state["best_brier"]
    rate = imp / max(1, i) * 100

    brier_trend = ""
    h = state["history"]
    if len(h) >= 2:
        recent = h[-20:]
        best_in_window = min(x["best_brier"] for x in recent)
        oldest_in_window = recent[0]["best_brier"]
        delta = oldest_in_window - best_in_window
        brier_trend = f"Last 20 iters: -{delta:.5f} improvement"

    metrics_text = (
        f"=== LIVE METRICS ===\n\n"
        f"Best Brier:       {brier:.5f}\n"
        f"Target:           0.20000\n"
        f"Gap:              {max(0, brier - 0.20):.5f}\n\n"
        f"Iterations:       {i}\n"
        f"Improvements:     {imp}\n"
        f"Improvement rate: {rate:.1f}%\n\n"
        f"{brier_trend}\n\n"
        f"=== BEST CONFIG ===\n\n"
        f"{_fmt_config(state['best_config'])}"
    )

    imp_chart = []
    for entry in state["history"][-100:]:
        imp_chart.append([entry["iter"], entry["best_brier"]])

    return metrics_text, imp_chart


def run_arena_bg():
    """Run arena in background, update state."""
    if state["arena_running"]:
        return "Arena already running..."
    state["arena_running"] = True
    try:
        results = run_arena_simulation(ARENA_N_GAMES)
        state["arena_result"] = results
        return "Arena complete."
    except Exception as e:
        return f"Arena error: {e}"
    finally:
        state["arena_running"] = False


def get_arena_results():
    r = state["arena_result"]
    if r is None:
        return "Arena not run yet. Click 'Run Arena Simulation'.", [], []
    top = r[0]
    summary = (
        f"Arena: {ARENA_N_GAMES} synthetic games | 11 strategies x 6 models = 66 competitors\n"
        f"Best: {top['name']} -> ${top['bankroll']:.2f} ({top['roi_pct']:+.1f}% ROI, Sharpe {top['sharpe']:.2f})\n"
        f"Profitable: {sum(1 for x in r if x['bankroll'] > 100)}/66 | "
        f"Active: {sum(1 for x in r if x['active'])}/66"
    )
    return summary, _arena_table(r), _best_per_strategy(r)


# ──────────────────────────────────────────────────────────────
# BUILD UI
# ──────────────────────────────────────────────────────────────

with gr.Blocks(
    title="Nomos42 Karpathy Arena",
    theme=gr.themes.Default(
        primary_hue="green",
        secondary_hue="blue",
    ),
) as demo:
    gr.Markdown(
        """
# Nomos42 Karpathy Arena
**Autonomous Karpathy iteration loop + Arena backtest — runs continuously on HF Spaces CPU.**
Mutate config -> train -> measure Brier -> keep if better -> repeat. Target: Brier < 0.20
        """
    )

    with gr.Tabs():

        # ── TAB 1: KARPATHY LOOP ──────────────────────────────
        with gr.Tab("Karpathy Loop"):
            gr.Markdown("### Continuous Karpathy Iteration Loop\nMutates one config parameter per iteration, keeps improvements.")

            status_box = gr.Textbox(
                label="Loop Status",
                lines=4,
                value=_status_text(),
                interactive=False,
            )

            with gr.Row():
                with gr.Column(scale=2):
                    log_box = gr.Textbox(
                        label="Iteration Log (newest first)",
                        lines=20,
                        value="Loop starting...",
                        interactive=False,
                    )
                with gr.Column(scale=1):
                    config_box = gr.Textbox(
                        label="Best Config",
                        lines=20,
                        value=_fmt_config(None),
                        interactive=False,
                    )

            history_headers = ["Iter", "Brier", "Best Brier", "Improved", "Model", "N Feat", "Mutation"]
            history_tbl = gr.Dataframe(
                headers=history_headers,
                label="Recent Iterations (last 50)",
                value=[],
                row_count=(10, "dynamic"),
            )

            refresh_btn = gr.Button("Refresh Now", variant="secondary")

            def on_refresh():
                return refresh_karpathy()

            refresh_btn.click(
                on_refresh,
                outputs=[status_box, log_box, history_tbl, config_box],
            )

            # Auto-refresh every 30s
            timer1 = gr.Timer(value=30)
            timer1.tick(
                fn=on_refresh,
                outputs=[status_box, log_box, history_tbl, config_box],
            )

        # ── TAB 2: ARENA SIMULATOR ───────────────────────────
        with gr.Tab("Arena Simulator"):
            gr.Markdown(
                f"### Arena: 11 Strategies x 6 Models x {ARENA_N_GAMES} synthetic games\n"
                "Synthetic NBA season — realistic moneyline odds, Kelly/flat/confidence strategies."
            )

            arena_summary = gr.Textbox(
                label="Arena Summary",
                lines=4,
                value="Click 'Run Arena Simulation' to start.",
                interactive=False,
            )

            run_arena_btn = gr.Button("Run Arena Simulation", variant="primary")
            arena_status = gr.Textbox(label="Status", lines=1, value="", interactive=False)

            gr.Markdown("#### Top 30 Competitors")
            arena_headers = ["#", "Name", "Model", "Strategy", "Bankroll", "ROI", "Sharpe", "Bets", "Win%", "MaxDD", "Active"]
            arena_tbl = gr.Dataframe(
                headers=arena_headers,
                label="Leaderboard",
                value=[],
                row_count=(15, "dynamic"),
            )

            gr.Markdown("#### Best Model per Strategy")
            strat_headers = ["Strategy", "Best Model", "Bankroll", "ROI", "Sharpe"]
            strat_tbl = gr.Dataframe(
                headers=strat_headers,
                label="Strategy Winners",
                value=[],
                row_count=(11, "fixed"),
            )

            def on_run_arena():
                status = run_arena_bg()
                summary, tbl, strat = get_arena_results()
                return status, summary, tbl, strat

            run_arena_btn.click(
                on_run_arena,
                outputs=[arena_status, arena_summary, arena_tbl, strat_tbl],
            )

        # ── TAB 3: METRICS ───────────────────────────────────
        with gr.Tab("Metrics"):
            gr.Markdown("### Live Metrics + Best Config JSON")

            metrics_box = gr.Textbox(
                label="Live Metrics",
                lines=20,
                value="Loading...",
                interactive=False,
            )

            gr.Markdown("#### Brier Improvement History (last 100 iterations)")
            brier_plot = gr.LinePlot(
                x="Iteration",
                y="Best Brier",
                title="Best Brier Over Time",
                height=300,
            )

            refresh_metrics_btn = gr.Button("Refresh Metrics", variant="secondary")

            def on_refresh_metrics():
                text, chart_data = refresh_metrics()
                if chart_data:
                    df = pd.DataFrame(chart_data, columns=["Iteration", "Best Brier"])
                else:
                    df = pd.DataFrame({"Iteration": [], "Best Brier": []})
                return text, df

            refresh_metrics_btn.click(
                on_refresh_metrics,
                outputs=[metrics_box, brier_plot],
            )

            timer3 = gr.Timer(value=30)
            timer3.tick(
                fn=on_refresh_metrics,
                outputs=[metrics_box, brier_plot],
            )

    gr.Markdown(
        "---\n"
        "Nomos42 Karpathy Arena | Self-contained on HF Spaces | "
        "No VM dependency | Target: Brier < 0.20"
    )


# ──────────────────────────────────────────────────────────────
# STARTUP
# ──────────────────────────────────────────────────────────────

# Generate data and start background loop before serving
init_data()
start_loop()

if __name__ == "__main__":
    demo.launch()
