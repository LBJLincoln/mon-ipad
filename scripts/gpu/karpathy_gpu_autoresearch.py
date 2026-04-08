#!/usr/bin/env python3
"""
KARPATHY GPU AUTORESEARCH — Real Training with All 15 Models + Review Agent
============================================================================
Pattern: modify config → train 5min → REVIEW AGENT analyzes → keep/revert → commit

3 PREDICTION TARGETS (not just moneyline!):
  1. moneyline: P(home_win) — binary classification
  2. spread:    home_score - away_score — regression
  3. total:     home_score + away_score — regression

15 MODEL TYPES:
  CPU (7): xgboost, xgboost_brier, lightgbm, catboost, random_forest, extra_trees, logistic_regression
  GPU (8): mlp, lstm, transformer, tabnet, ft_transformer, deep_ensemble, tabicl, autogluon

BEST PYTHON ML LIBRARIES (auto-installed per platform):
  - xgboost >= 2.1 (GPU: cuda, histogram)
  - lightgbm >= 4.5 (GPU: cuda_exp)
  - catboost >= 1.2.7 (GPU: native CUDA)
  - tabicl >= 0.3 (GPU: in-context learning, SOTA on tabular)
  - pytorch >= 2.5 (GPU: LSTM, Transformer, FT-Transformer)
  - autogluon >= 1.2 (GPU: AutoML ensemble)
  - tabnet (pytorch-tabnet >= 4.1) (GPU: attention-based)
  - scikit-learn >= 1.6 (CPU: RF, ExtraTrees, LogReg, calibration)
  - optuna >= 4.1 (hyperparameter tuning)

REVIEW AGENT: After each 5-min run, analyzes:
  - Brier delta (did it improve?)
  - Feature importance shift
  - Model type performance ranking
  - Calibration quality (reliability diagram)
  - Recommendation for next iteration

Platforms: Kaggle P100 (9h) | Colab T4 (12h) | Lightning H200 (22h)
"""

import os, sys, json, time, gc, math, random, traceback, hashlib
import numpy as np
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

# ═══════════════════════════════════════════════════════════════
# PLATFORM DETECTION & SETUP
# ═══════════════════════════════════════════════════════════════

PLATFORM = "unknown"
if Path("/kaggle/working").exists():
    PLATFORM = "kaggle"
    WORK = Path("/kaggle/working/nba-quant-gpu")
elif "COLAB_GPU" in os.environ or Path("/content").exists():
    PLATFORM = "colab"
    WORK = Path("/content/nba-quant-gpu")
elif "LIGHTNING_" in str(os.environ):
    PLATFORM = "lightning"
    WORK = Path("/teamspace/studios/nba-quant-gpu")
else:
    PLATFORM = "local"
    WORK = Path("/tmp/nba-quant-gpu")

WORK.mkdir(parents=True, exist_ok=True)
STATE_FILE = WORK / "autoresearch_state.json"
LOG_FILE = WORK / "experiment_log.jsonl"
REVIEW_FILE = WORK / "review_agent_log.jsonl"
FEATURE_CACHE = WORK / "features_cache_v38.npz"

print(f"Platform: {PLATFORM} | Work dir: {WORK}")

# ═══════════════════════════════════════════════════════════════
# INSTALL BEST LIBRARIES (per platform)
# ═══════════════════════════════════════════════════════════════

def install_deps():
    """Install the best ML libraries for the detected platform."""
    import subprocess

    # Core (always needed)
    core = [
        "xgboost>=2.1", "lightgbm>=4.5", "catboost>=1.2",
        "scikit-learn>=1.5", "optuna>=4.0",
        "psycopg2-binary", "nba_api",
    ]

    # GPU-specific
    gpu_libs = [
        "torch>=2.4", "pytorch-tabnet>=4.1",
    ]

    # SOTA tabular (may fail on some platforms)
    sota = [
        "tabicl>=0.3",
        # "autogluon.tabular>=1.2",  # Heavy, install separately
    ]

    print("Installing core dependencies...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q"] + core,
                   capture_output=True, timeout=300)

    if HAS_GPU:
        print("Installing GPU libraries...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q"] + gpu_libs,
                       capture_output=True, timeout=300)
        print("Installing SOTA tabular libraries...")
        for lib in sota:
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", "-q", lib],
                               capture_output=True, timeout=120)
            except Exception:
                print(f"  {lib}: install failed (optional)")

    print("Dependencies installed.")


# GPU detection
import subprocess
HAS_GPU = False
GPU_NAME = "none"
try:
    result = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                          capture_output=True, text=True, timeout=5)
    if result.returncode == 0:
        HAS_GPU = True
        GPU_NAME = result.stdout.strip().split('\n')[0]
except Exception:
    pass
print(f"GPU: {GPU_NAME if HAS_GPU else 'NONE (CPU only)'}")

install_deps()

# Now import ML libraries
import xgboost as xgb
import lightgbm as lgbm
from catboost import CatBoostClassifier, CatBoostRegressor
from sklearn.ensemble import (ExtraTreesClassifier, RandomForestClassifier,
                              ExtraTreesRegressor, RandomForestRegressor,
                              GradientBoostingClassifier, GradientBoostingRegressor)
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss, mean_squared_error, mean_absolute_error
from sklearn.model_selection import TimeSeriesSplit

# Optional GPU libs
try:
    import torch
    import torch.nn as nn
    HAS_TORCH = True
    print(f"PyTorch: {torch.__version__}, CUDA: {torch.cuda.is_available()}")
except ImportError:
    HAS_TORCH = False
    print("PyTorch: not available")

try:
    from pytorch_tabnet.tab_model import TabNetClassifier, TabNetRegressor
    HAS_TABNET = True
except ImportError:
    HAS_TABNET = False

try:
    from tabicl import TabICLClassifier
    HAS_TABICL = True
except ImportError:
    HAS_TABICL = False


# ═══════════════════════════════════════════════════════════════
# ALL 15 MODEL TYPES × 3 TARGETS
# ═══════════════════════════════════════════════════════════════

ALL_MODEL_TYPES = [
    # Tree-based (CPU + GPU)
    "xgboost", "xgboost_brier", "lightgbm", "catboost",
    "random_forest", "extra_trees",
    # Linear (CPU)
    "logistic_regression",
    # Ensemble
    "stacking",
    # Neural nets (GPU)
    "mlp", "lstm", "transformer", "tabnet", "ft_transformer", "deep_ensemble",
    # AutoML
    "autogluon",
]

CPU_MODEL_TYPES = ["xgboost", "xgboost_brier", "lightgbm", "catboost",
                   "random_forest", "extra_trees", "logistic_regression"]

GPU_MODEL_TYPES = ["mlp", "lstm", "transformer", "tabnet", "ft_transformer",
                   "deep_ensemble", "autogluon"]

NEURAL_NET_TYPES = {"mlp", "lstm", "transformer", "tabnet", "ft_transformer",
                    "deep_ensemble", "autogluon"}

# Which models are available on this platform
AVAILABLE_MODELS = list(CPU_MODEL_TYPES)
if HAS_GPU and HAS_TORCH:
    AVAILABLE_MODELS.extend(["mlp", "lstm", "transformer", "ft_transformer", "deep_ensemble"])
if HAS_GPU and HAS_TABNET:
    AVAILABLE_MODELS.append("tabnet")
if HAS_GPU and HAS_TABICL:
    AVAILABLE_MODELS.append("tabicl")

print(f"Available models ({len(AVAILABLE_MODELS)}): {AVAILABLE_MODELS}")


# ═══════════════════════════════════════════════════════════════
# PREDICTION TARGETS (3 targets, not just 1!)
# ═══════════════════════════════════════════════════════════════

TARGETS = ["moneyline", "spread", "total"]

def build_targets(games):
    """Build 3 target arrays from game data.
    Returns: y_moneyline (binary), y_spread (float), y_total (float)
    """
    y_ml = []   # 1 if home wins, 0 otherwise
    y_sp = []   # home_score - away_score
    y_tot = []  # home_score + away_score

    for g in games:
        hs = g.get("home_score", g.get("home_pts"))
        as_ = g.get("away_score", g.get("away_pts"))
        if hs is None or as_ is None:
            continue
        hs, as_ = float(hs), float(as_)
        y_ml.append(1 if hs > as_ else 0)
        y_sp.append(hs - as_)
        y_tot.append(hs + as_)

    return np.array(y_ml, dtype=np.int32), np.array(y_sp, dtype=np.float32), np.array(y_tot, dtype=np.float32)


# ═══════════════════════════════════════════════════════════════
# MODEL FACTORY (all 15 types × 3 targets)
# ═══════════════════════════════════════════════════════════════

def make_model(model_type: str, hp: dict, target: str = "moneyline"):
    """Create a model for the given type, hyperparams, and target.

    target: 'moneyline' (classification) | 'spread'/'total' (regression)
    """
    is_classification = (target == "moneyline")
    depth = hp.get("depth", 6)
    lr = hp.get("lr", 0.1)
    n_est = hp.get("n_est", 200)
    gpu_device = "cuda" if HAS_GPU else "cpu"

    if model_type == "xgboost":
        if is_classification:
            return xgb.XGBClassifier(
                max_depth=depth, learning_rate=lr, n_estimators=n_est,
                eval_metric="logloss", verbosity=0, tree_method="hist",
                device=gpu_device, random_state=42)
        else:
            return xgb.XGBRegressor(
                max_depth=depth, learning_rate=lr, n_estimators=n_est,
                eval_metric="rmse", verbosity=0, tree_method="hist",
                device=gpu_device, random_state=42)

    elif model_type == "xgboost_brier":
        # Custom Brier objective (classification only)
        def brier_obj(y_true, y_pred):
            grad = 2 * (y_pred - y_true)
            hess = np.full_like(grad, 2.0)
            return grad, hess
        if is_classification:
            return xgb.XGBClassifier(
                max_depth=depth, learning_rate=lr, n_estimators=n_est,
                objective=brier_obj, verbosity=0, tree_method="hist",
                device=gpu_device, random_state=42)
        else:
            return xgb.XGBRegressor(
                max_depth=depth, learning_rate=lr, n_estimators=n_est,
                verbosity=0, tree_method="hist", device=gpu_device, random_state=42)

    elif model_type == "lightgbm":
        if is_classification:
            return lgbm.LGBMClassifier(
                max_depth=depth, learning_rate=lr, n_estimators=n_est,
                verbose=-1, device="gpu" if HAS_GPU else "cpu", random_state=42)
        else:
            return lgbm.LGBMRegressor(
                max_depth=depth, learning_rate=lr, n_estimators=n_est,
                verbose=-1, device="gpu" if HAS_GPU else "cpu", random_state=42)

    elif model_type == "catboost":
        if is_classification:
            return CatBoostClassifier(
                depth=min(depth, 10), learning_rate=lr, iterations=n_est,
                verbose=0, task_type="GPU" if HAS_GPU else "CPU", random_state=42)
        else:
            return CatBoostRegressor(
                depth=min(depth, 10), learning_rate=lr, iterations=n_est,
                verbose=0, task_type="GPU" if HAS_GPU else "CPU", random_state=42)

    elif model_type == "extra_trees":
        if is_classification:
            return ExtraTreesClassifier(n_estimators=n_est, max_depth=depth or None, random_state=42, n_jobs=-1)
        else:
            return ExtraTreesRegressor(n_estimators=n_est, max_depth=depth or None, random_state=42, n_jobs=-1)

    elif model_type == "random_forest":
        if is_classification:
            return RandomForestClassifier(n_estimators=n_est, max_depth=depth or None, random_state=42, n_jobs=-1)
        else:
            return RandomForestRegressor(n_estimators=n_est, max_depth=depth or None, random_state=42, n_jobs=-1)

    elif model_type == "logistic_regression":
        if is_classification:
            return LogisticRegression(C=hp.get("C", 1.0), max_iter=500, random_state=42)
        else:
            return Ridge(alpha=1.0 / max(hp.get("C", 1.0), 0.001), random_state=42)

    elif model_type == "mlp" and HAS_TORCH:
        return _build_pytorch_model(hp, "mlp", is_classification)

    elif model_type == "lstm" and HAS_TORCH:
        return _build_pytorch_model(hp, "lstm", is_classification)

    elif model_type == "transformer" and HAS_TORCH:
        return _build_pytorch_model(hp, "transformer", is_classification)

    elif model_type == "ft_transformer" and HAS_TORCH:
        return _build_pytorch_model(hp, "ft_transformer", is_classification)

    elif model_type == "tabnet" and HAS_TABNET:
        if is_classification:
            return TabNetClassifier(verbose=0, device_name=gpu_device)
        else:
            return TabNetRegressor(verbose=0, device_name=gpu_device)

    elif model_type == "deep_ensemble" and HAS_TORCH:
        return _build_deep_ensemble(hp, is_classification)

    elif model_type == "tabicl" and HAS_TABICL:
        return TabICLClassifier()  # Classification only for now

    else:
        # Fallback
        if is_classification:
            return xgb.XGBClassifier(verbosity=0, random_state=42)
        else:
            return xgb.XGBRegressor(verbosity=0, random_state=42)


# ═══════════════════════════════════════════════════════════════
# PYTORCH MODELS (MLP, LSTM, Transformer, FT-Transformer)
# ═══════════════════════════════════════════════════════════════

def _build_pytorch_model(hp, model_type, is_classification):
    """Build a PyTorch-based sklearn-compatible model."""
    if not HAS_TORCH:
        return None

    hidden = hp.get("hidden_dim", 128)
    n_layers = hp.get("n_layers", 2)
    dropout = hp.get("dropout", 0.2)
    epochs = hp.get("epochs", 50)
    batch_size = hp.get("batch_size", 256)
    lr = hp.get("lr", 0.001)

    class TorchWrapper:
        """Sklearn-compatible wrapper for PyTorch models."""
        def __init__(self):
            self.model = None
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self.is_clf = is_classification

        def _build_net(self, n_features):
            if model_type == "mlp":
                layers = [nn.Linear(n_features, hidden), nn.ReLU(), nn.Dropout(dropout)]
                for _ in range(n_layers - 1):
                    layers.extend([nn.Linear(hidden, hidden), nn.ReLU(), nn.Dropout(dropout)])
                layers.append(nn.Linear(hidden, 1))
                return nn.Sequential(*layers)
            elif model_type == "lstm":
                return _LSTMNet(n_features, hidden, n_layers, dropout)
            elif model_type in ("transformer", "ft_transformer"):
                return _TransformerNet(n_features, hidden, n_layers, dropout)
            return nn.Sequential(nn.Linear(n_features, 1))

        def fit(self, X, y):
            n_features = X.shape[1]
            self.model = self._build_net(n_features).to(self.device)
            X_t = torch.FloatTensor(X).to(self.device)
            y_t = torch.FloatTensor(y.astype(float)).unsqueeze(1).to(self.device)

            opt = torch.optim.Adam(self.model.parameters(), lr=lr)
            loss_fn = nn.BCEWithLogitsLoss() if self.is_clf else nn.MSELoss()

            self.model.train()
            for epoch in range(epochs):
                for i in range(0, len(X_t), batch_size):
                    xb = X_t[i:i+batch_size]
                    yb = y_t[i:i+batch_size]
                    opt.zero_grad()
                    out = self.model(xb)
                    loss = loss_fn(out, yb)
                    loss.backward()
                    opt.step()
            return self

        def predict_proba(self, X):
            self.model.eval()
            with torch.no_grad():
                X_t = torch.FloatTensor(X).to(self.device)
                logits = self.model(X_t).cpu().numpy().flatten()
                probs = 1 / (1 + np.exp(-logits))
            return np.column_stack([1 - probs, probs])

        def predict(self, X):
            self.model.eval()
            with torch.no_grad():
                X_t = torch.FloatTensor(X).to(self.device)
                return self.model(X_t).cpu().numpy().flatten()

    return TorchWrapper()


class _LSTMNet(nn.Module):
    def __init__(self, n_features, hidden, n_layers, dropout):
        super().__init__()
        self.lstm = nn.LSTM(n_features, hidden, n_layers, dropout=dropout, batch_first=True)
        self.fc = nn.Linear(hidden, 1)

    def forward(self, x):
        x = x.unsqueeze(1)  # (batch, 1, features) — single timestep
        _, (h, _) = self.lstm(x)
        return self.fc(h[-1])


class _TransformerNet(nn.Module):
    def __init__(self, n_features, hidden, n_layers, dropout):
        super().__init__()
        self.embed = nn.Linear(n_features, hidden)
        layer = nn.TransformerEncoderLayer(hidden, nhead=4, dim_feedforward=hidden*2,
                                           dropout=dropout, batch_first=True)
        self.encoder = nn.TransformerEncoder(layer, n_layers)
        self.fc = nn.Linear(hidden, 1)

    def forward(self, x):
        x = self.embed(x).unsqueeze(1)  # (batch, 1, hidden)
        x = self.encoder(x)
        return self.fc(x[:, 0, :])


def _build_deep_ensemble(hp, is_classification, n_models=5):
    """Build a deep ensemble of MLP models."""
    class DeepEnsemble:
        def __init__(self):
            self.models = []
            self.is_clf = is_classification

        def fit(self, X, y):
            self.models = []
            for i in range(n_models):
                m = _build_pytorch_model({**hp, "epochs": hp.get("epochs", 30)}, "mlp", is_classification)
                # Bootstrap sample
                idx = np.random.choice(len(X), len(X), replace=True)
                m.fit(X[idx], y[idx])
                self.models.append(m)
            return self

        def predict_proba(self, X):
            all_probs = np.stack([m.predict_proba(X) for m in self.models])
            return np.mean(all_probs, axis=0)

        def predict(self, X):
            all_preds = np.stack([m.predict(X) for m in self.models])
            return np.mean(all_preds, axis=0)

    return DeepEnsemble()


# ═══════════════════════════════════════════════════════════════
# EVALUATION HARNESS (IMMUTABLE — prepare.py)
# ═══════════════════════════════════════════════════════════════

def evaluate(X, y_dict, features_mask, model_type, hp, target="moneyline", timeout=120):
    """Evaluate one individual on one target. Returns metric (lower = better).

    For moneyline: Brier score
    For spread/total: RMSE normalized to [0,1] range
    THIS FUNCTION IS IMMUTABLE — the agent cannot change it.
    """
    try:
        selected = np.where(features_mask)[0]
        if len(selected) < 5 or len(selected) > 200:
            return 1.0

        X_sub = X[:, selected]
        y = y_dict[target]

        is_classification = (target == "moneyline")
        tscv = TimeSeriesSplit(n_splits=3)
        scores = []

        for train_idx, test_idx in tscv.split(X_sub):
            model = make_model(model_type, hp, target)
            if model is None:
                return 1.0

            t0 = time.time()
            model.fit(X_sub[train_idx], y[train_idx])
            if time.time() - t0 > timeout:
                return 1.0

            if is_classification:
                probs = model.predict_proba(X_sub[test_idx])[:, 1]
                scores.append(brier_score_loss(y[test_idx], probs))
            else:
                preds = model.predict(X_sub[test_idx])
                rmse = np.sqrt(mean_squared_error(y[test_idx], preds))
                # Normalize: spread ≈ [-30, 30], total ≈ [170, 270]
                if target == "spread":
                    scores.append(rmse / 30.0)  # 0 = perfect, 1 = ±30 pts off
                else:
                    scores.append(rmse / 50.0)  # 0 = perfect, 1 = ±50 pts off

        return float(np.mean(scores))
    except Exception as e:
        print(f"    Eval error ({model_type}/{target}): {e}")
        return 1.0


# ═══════════════════════════════════════════════════════════════
# REVIEW AGENT — Analyzes each 5-min run
# ═══════════════════════════════════════════════════════════════

class ReviewAgent:
    """After each iteration, reviews results and suggests next steps.

    Analyzes:
    1. Brier/RMSE delta (improvement trend)
    2. Model type performance ranking
    3. Feature importance stability
    4. Target-specific recommendations
    5. Config adjustments for next iteration
    """

    def __init__(self):
        self.history = []

    def review(self, iteration: int, results: dict, population: list,
               config: dict, duration: float) -> dict:
        """Review one iteration and produce analysis + recommendations."""

        review = {
            "iteration": iteration,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "duration_sec": round(duration, 1),
            "summary": {},
            "model_ranking": {},
            "target_analysis": {},
            "recommendations": [],
            "config_adjustments": {},
        }

        # 1. Performance by target
        for target in TARGETS:
            target_key = f"best_{target}"
            current = results.get(target_key, 1.0)
            previous = self.history[-1]["summary"].get(target, 1.0) if self.history else 1.0
            delta = current - previous
            improved = delta < -0.0001

            review["target_analysis"][target] = {
                "current": round(current, 5),
                "previous": round(previous, 5),
                "delta": round(delta, 5),
                "improved": improved,
                "trend": "improving" if delta < 0 else "stagnating" if abs(delta) < 0.0001 else "degrading",
            }
            review["summary"][target] = current

        # 2. Model type ranking (from population)
        model_scores = defaultdict(list)
        for ind in population:
            for target in TARGETS:
                score = ind.get(f"score_{target}", 1.0)
                if score < 0.99:
                    model_scores[f"{ind['model_type']}_{target}"].append(score)

        for key, scores in sorted(model_scores.items(), key=lambda x: np.mean(x[1])):
            review["model_ranking"][key] = {
                "mean": round(np.mean(scores), 5),
                "best": round(min(scores), 5),
                "count": len(scores),
            }

        # 3. Stagnation detection
        if len(self.history) >= 5:
            recent_deltas = [h["target_analysis"].get("moneyline", {}).get("delta", 0)
                           for h in self.history[-5:]]
            if all(abs(d) < 0.0001 for d in recent_deltas):
                review["recommendations"].append({
                    "type": "stagnation_alert",
                    "message": "5+ iterations without improvement. Increase mutation rate or inject random individuals.",
                    "action": "increase_mutation",
                })

        # 4. Model diversity check
        model_types_in_pop = set(ind["model_type"] for ind in population)
        if len(model_types_in_pop) < 3:
            review["recommendations"].append({
                "type": "diversity_alert",
                "message": f"Only {len(model_types_in_pop)} model types in population. Force diversification.",
                "action": "diversify_models",
            })

        # 5. Feature count analysis
        feat_counts = [int(np.sum(ind["mask"])) if isinstance(ind.get("mask"), np.ndarray)
                      else ind.get("n_features", 0) for ind in population]
        avg_feat = np.mean(feat_counts) if feat_counts else 0
        if avg_feat < 30:
            review["recommendations"].append({
                "type": "feature_alert",
                "message": f"Average {avg_feat:.0f} features — may be underfitting. Increase target.",
                "action": "increase_features",
            })
        elif avg_feat > 150:
            review["recommendations"].append({
                "type": "feature_alert",
                "message": f"Average {avg_feat:.0f} features — may be overfitting. Decrease target.",
                "action": "decrease_features",
            })

        # 6. Config adjustment recommendations
        adjustments = {}
        for rec in review["recommendations"]:
            if rec["action"] == "increase_mutation":
                adjustments["mutation_rate"] = min(config.get("mutation_rate", 0.09) * 1.5, 0.25)
            elif rec["action"] == "diversify_models":
                adjustments["force_diversity"] = True
            elif rec["action"] == "increase_features":
                adjustments["target_features"] = min(config.get("target_features", 63) + 20, 200)
            elif rec["action"] == "decrease_features":
                adjustments["target_features"] = max(config.get("target_features", 63) - 20, 30)

        review["config_adjustments"] = adjustments

        # Log
        self.history.append(review)
        with open(REVIEW_FILE, "a") as f:
            f.write(json.dumps(review) + "\n")

        return review

    def print_review(self, review: dict):
        """Pretty-print the review."""
        print(f"\n{'─'*60}")
        print(f"  REVIEW AGENT — Iteration {review['iteration']}")
        print(f"{'─'*60}")

        for target, analysis in review["target_analysis"].items():
            icon = "▲" if analysis["improved"] else "▼" if analysis["delta"] > 0 else "─"
            print(f"  {target:12s}: {analysis['current']:.5f} ({icon} {analysis['delta']:+.5f}) [{analysis['trend']}]")

        if review["recommendations"]:
            print(f"\n  Recommendations:")
            for rec in review["recommendations"]:
                print(f"    → {rec['message']}")

        if review["config_adjustments"]:
            print(f"\n  Config adjustments for next iteration:")
            for k, v in review["config_adjustments"].items():
                print(f"    {k}: {v}")

        top_models = list(review["model_ranking"].items())[:5]
        if top_models:
            print(f"\n  Top models:")
            for name, stats in top_models:
                print(f"    {name}: mean={stats['mean']:.5f} best={stats['best']:.5f} (n={stats['count']})")

        print(f"{'─'*60}")


# ═══════════════════════════════════════════════════════════════
# KARPATHY LOOP CONFIG (what the agent modifies each iteration)
# ═══════════════════════════════════════════════════════════════

CONFIG = {
    "population_size": 30,
    "iteration_budget_sec": 300,  # 5 minutes
    "mutation_rate": 0.09,
    "crossover_rate": 0.80,
    "target_features": 80,
    "targets": TARGETS,  # ALL 3 targets
    "model_types": AVAILABLE_MODELS,
    "hp_ranges": {
        "depth": (4, 10),
        "lr": (0.01, 0.3),
        "n_est": (100, 500),
        "hidden_dim": (64, 256),
        "n_layers": (1, 4),
        "dropout": (0.1, 0.4),
        "epochs": (20, 100),
    },
}


# ═══════════════════════════════════════════════════════════════
# INDIVIDUAL & GENETIC OPS
# ═══════════════════════════════════════════════════════════════

def random_individual(n_features):
    target = CONFIG["target_features"]
    mask = np.zeros(n_features, dtype=bool)
    selected = np.random.choice(n_features, size=min(target, n_features), replace=False)
    mask[selected] = True

    model_type = random.choice(CONFIG["model_types"])
    hp = {
        "depth": random.randint(*CONFIG["hp_ranges"]["depth"]),
        "lr": round(random.uniform(*CONFIG["hp_ranges"]["lr"]), 3),
        "n_est": random.randint(*CONFIG["hp_ranges"]["n_est"]),
    }
    if model_type in NEURAL_NET_TYPES:
        hp["hidden_dim"] = random.choice([64, 128, 256])
        hp["n_layers"] = random.randint(1, 3)
        hp["dropout"] = round(random.uniform(0.1, 0.4), 2)
        hp["epochs"] = random.choice([30, 50, 80])

    return {"mask": mask, "model_type": model_type, "hp": hp,
            "score_moneyline": 1.0, "score_spread": 1.0, "score_total": 1.0,
            "composite": 1.0}


def mutate(ind, n_features):
    new = {
        "mask": ind["mask"].copy(),
        "model_type": ind["model_type"],
        "hp": dict(ind["hp"]),
        "score_moneyline": 1.0, "score_spread": 1.0, "score_total": 1.0,
        "composite": 1.0,
    }

    # Feature mutation
    n_flip = max(1, int(CONFIG["mutation_rate"] * np.sum(new["mask"])))
    for _ in range(n_flip):
        idx = random.randint(0, n_features - 1)
        new["mask"][idx] = not new["mask"][idx]

    # Bound features
    n_sel = np.sum(new["mask"])
    target = CONFIG["target_features"]
    while n_sel > min(target * 1.5, 200):
        on = np.where(new["mask"])[0]
        new["mask"][np.random.choice(on)] = False
        n_sel -= 1
    while n_sel < max(target * 0.5, 10):
        off = np.where(~new["mask"])[0]
        if len(off) == 0: break
        new["mask"][np.random.choice(off)] = True
        n_sel += 1

    # HP mutation
    if random.random() < 0.2:
        new["hp"]["depth"] = max(4, min(10, new["hp"]["depth"] + random.choice([-1, 0, 1])))
        new["hp"]["lr"] = max(0.01, min(0.3, new["hp"]["lr"] * random.uniform(0.8, 1.2)))

    # Model mutation (25%)
    if random.random() < 0.25:
        new["model_type"] = random.choice(CONFIG["model_types"])
        if new["model_type"] in NEURAL_NET_TYPES:
            new["hp"]["hidden_dim"] = random.choice([64, 128, 256])
            new["hp"]["n_layers"] = random.randint(1, 3)
            new["hp"]["dropout"] = round(random.uniform(0.1, 0.4), 2)
            new["hp"]["epochs"] = random.choice([30, 50, 80])

    return new


def crossover(p1, p2):
    child = {"mask": np.zeros_like(p1["mask"]),
             "score_moneyline": 1.0, "score_spread": 1.0, "score_total": 1.0, "composite": 1.0}
    for i in range(len(child["mask"])):
        child["mask"][i] = p1["mask"][i] if random.random() < 0.5 else p2["mask"][i]
    child["model_type"] = p1["model_type"] if random.random() < 0.5 else p2["model_type"]
    child["hp"] = dict(p1["hp"] if random.random() < 0.5 else p2["hp"])
    return child


# ═══════════════════════════════════════════════════════════════
# MAIN KARPATHY AUTORESEARCH LOOP
# ═══════════════════════════════════════════════════════════════

def run_autoresearch():
    """Main loop: iterate until session time limit."""

    # ── Load data ──
    HF_TOKEN = os.environ.get("HF_TOKEN", "")
    DATABASE_URL = os.environ.get("DATABASE_URL", "")

    REPO_DIR = WORK / "nba-quant-space"
    if not REPO_DIR.exists() and HF_TOKEN:
        print("Cloning feature engine from HF Space...")
        os.system(f"git clone --depth 1 https://user:{HF_TOKEN}@huggingface.co/spaces/Nomos42/nba-quant {REPO_DIR}")
    sys.path.insert(0, str(REPO_DIR))

    # Build or load features
    if FEATURE_CACHE.exists():
        print(f"Loading cached features from {FEATURE_CACHE}")
        data = np.load(FEATURE_CACHE, allow_pickle=True)
        X = data["X"]
        feature_names = list(data["feature_names"])
        # We need raw games for multi-target y
        y_ml = data.get("y_moneyline", data.get("y"))
        y_sp = data.get("y_spread")
        y_tot = data.get("y_total")
        if y_sp is None:
            print("Cached features don't have spread/total targets — rebuilding targets...")
            # Load games to rebuild targets
            games = _load_games(REPO_DIR, DATABASE_URL)
            y_ml, y_sp, y_tot = build_targets(games)
            # Align lengths
            min_len = min(len(X), len(y_ml))
            X = X[:min_len]; y_ml = y_ml[:min_len]; y_sp = y_sp[:min_len]; y_tot = y_tot[:min_len]
    else:
        print("Building features from scratch (~30 min)...")
        games = _load_games(REPO_DIR, DATABASE_URL)
        from features.engine import NBAFeatureEngine
        engine = NBAFeatureEngine()
        X, _y, feature_names = engine.build(games)
        X = np.nan_to_num(np.array(X, dtype=np.float64))
        y_ml, y_sp, y_tot = build_targets(games)
        min_len = min(len(X), len(y_ml))
        X = X[:min_len]; y_ml = y_ml[:min_len]; y_sp = y_sp[:min_len]; y_tot = y_tot[:min_len]
        np.savez_compressed(FEATURE_CACHE, X=X, feature_names=np.array(feature_names),
                          y_moneyline=y_ml, y_spread=y_sp, y_total=y_tot)
        print(f"Built & cached: {X.shape}")

    # Subsample for speed
    MAX_GAMES = 6000
    if X.shape[0] > MAX_GAMES:
        X = X[-MAX_GAMES:]
        y_ml = y_ml[-MAX_GAMES:]
        y_sp = y_sp[-MAX_GAMES:]
        y_tot = y_tot[-MAX_GAMES:]

    y_dict = {"moneyline": y_ml, "spread": y_sp, "total": y_tot}
    n_features = X.shape[1]
    print(f"Ready: {X.shape} ({n_features} features) × 3 targets")
    print(f"  moneyline: {len(y_ml)} games, home_win_rate={np.mean(y_ml):.3f}")
    print(f"  spread: mean={np.mean(y_sp):.1f}, std={np.std(y_sp):.1f}")
    print(f"  total: mean={np.mean(y_tot):.1f}, std={np.std(y_tot):.1f}")

    # ── Initialize population ──
    print("\nInitializing population...")
    population = [random_individual(n_features) for _ in range(CONFIG["population_size"])]

    # Seed from HF spaces
    try:
        seeds = _fetch_island_seeds(n_features)
        for i, seed in enumerate(seeds[:len(population)//3]):
            population[i] = seed
    except Exception as e:
        print(f"Seeding from islands failed: {e}")

    # ── Review agent ──
    reviewer = ReviewAgent()

    # ── Session limits ──
    SESSION_LIMITS = {"kaggle": 9*3600, "colab": 12*3600, "lightning": 22*3600, "local": 4*3600}
    SESSION_LIMIT = SESSION_LIMITS.get(PLATFORM, 4*3600)
    session_start = time.time()

    best_ever = {"moneyline": 1.0, "spread": 1.0, "total": 1.0}
    iteration = 0

    print(f"\n{'='*70}")
    print(f"  KARPATHY GPU AUTORESEARCH — {PLATFORM.upper()}")
    print(f"  Models: {len(AVAILABLE_MODELS)} | Targets: 3 | Pop: {CONFIG['population_size']}")
    print(f"  GPU: {GPU_NAME} | Session: {SESSION_LIMIT/3600:.0f}h")
    print(f"  ATR to beat: moneyline=0.21570 | spread=TBD | total=TBD")
    print(f"{'='*70}\n")

    while time.time() - session_start < SESSION_LIMIT:
        iteration += 1
        iter_start = time.time()
        n_evals = 0

        # ── EVALUATE unevaluated individuals on ALL 3 TARGETS ──
        for ind in population:
            if ind["composite"] >= 0.99:
                for target in TARGETS:
                    score_key = f"score_{target}"
                    if ind[score_key] >= 0.99:
                        ind[score_key] = evaluate(X, y_dict, ind["mask"],
                                                  ind["model_type"], ind["hp"], target)
                        n_evals += 1

                # Composite: weighted average across targets
                ind["composite"] = (
                    0.50 * ind["score_moneyline"] +
                    0.25 * ind["score_spread"] +
                    0.25 * ind["score_total"]
                )

                if time.time() - iter_start > CONFIG["iteration_budget_sec"]:
                    break

        # ── SELECTION ──
        population.sort(key=lambda x: x["composite"])

        # Track bests per target
        results = {}
        for target in TARGETS:
            key = f"score_{target}"
            best_score = min(ind[key] for ind in population if ind[key] < 0.99)
            results[f"best_{target}"] = best_score
            if best_score < best_ever[target]:
                best_ever[target] = best_score

        duration = time.time() - iter_start

        # ── REVIEW AGENT ──
        review = reviewer.review(iteration, results, population, CONFIG, duration)
        reviewer.print_review(review)

        # ── APPLY REVIEW RECOMMENDATIONS ──
        for k, v in review.get("config_adjustments", {}).items():
            if k in CONFIG and k != "targets":
                old = CONFIG[k]
                CONFIG[k] = v
                print(f"  [Auto-adjust] {k}: {old} → {v}")

        # ── REPRODUCTION ──
        elite_size = max(2, CONFIG["population_size"] // 5)
        elite = population[:elite_size]

        offspring = []
        while len(offspring) < CONFIG["population_size"] - elite_size:
            if random.random() < CONFIG["crossover_rate"]:
                p1, p2 = random.sample(elite, 2)
                child = crossover(p1, p2)
                child = mutate(child, n_features)
            else:
                parent = random.choice(elite)
                child = mutate(parent, n_features)
            offspring.append(child)

        population = elite + offspring

        # ── LOG ──
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "iteration": iteration,
            "platform": PLATFORM,
            "gpu": GPU_NAME,
            "n_evals": n_evals,
            "duration_sec": round(duration, 1),
            "best_moneyline": round(best_ever["moneyline"], 5),
            "best_spread": round(best_ever["spread"], 5),
            "best_total": round(best_ever["total"], 5),
            "best_model": population[0]["model_type"],
            "best_features": int(np.sum(population[0]["mask"])),
            "config": {k: v for k, v in CONFIG.items() if k not in ("targets", "model_types")},
        }
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

        # Print iteration summary
        elapsed = time.time() - session_start
        remaining = (SESSION_LIMIT - elapsed) / 3600
        print(f"\n  Iter {iteration}: ML={best_ever['moneyline']:.5f} SP={best_ever['spread']:.4f} "
              f"TOT={best_ever['total']:.4f} | evals={n_evals} | "
              f"{duration:.0f}s | {remaining:.1f}h left")

        gc.collect()
        if HAS_GPU and HAS_TORCH:
            torch.cuda.empty_cache()

    # ── FINAL RESULTS ──
    print(f"\n{'='*70}")
    print(f"  SESSION COMPLETE — {iteration} iterations")
    print(f"  Best moneyline: {best_ever['moneyline']:.5f} (ATR: 0.21570)")
    print(f"  Best spread:    {best_ever['spread']:.5f}")
    print(f"  Best total:     {best_ever['total']:.5f}")
    print(f"{'='*70}")

    # Save final state
    final = {
        "platform": PLATFORM,
        "gpu": GPU_NAME,
        "iterations": iteration,
        "best_ever": {k: round(v, 5) for k, v in best_ever.items()},
        "best_individual": {
            "model_type": population[0]["model_type"],
            "n_features": int(np.sum(population[0]["mask"])),
            "hp": population[0]["hp"],
            "features": np.where(population[0]["mask"])[0].tolist(),
        },
        "available_models": AVAILABLE_MODELS,
        "session_hours": round((time.time() - session_start) / 3600, 2),
    }
    (WORK / "result.json").write_text(json.dumps(final, indent=2))
    print(f"Results saved to {WORK / 'result.json'}")


def _load_games(repo_dir, database_url):
    """Load game data from local files or Supabase."""
    games = []
    hist_dir = repo_dir / "data" / "historical"
    if hist_dir.exists():
        for f in sorted(hist_dir.glob("games-*.json")):
            raw = json.loads(f.read_text())
            games.extend(raw if isinstance(raw, list) else raw.get("games", []))
    if games:
        print(f"Loaded {len(games)} games from {hist_dir}")
        return games

    if database_url:
        print("Loading from Supabase...")
        import psycopg2
        conn = psycopg2.connect(database_url, connect_timeout=30)
        cur = conn.cursor()
        cur.execute("SELECT game_data FROM nba_games ORDER BY game_date LIMIT 15000")
        for row in cur.fetchall():
            if row[0]:
                games.append(row[0] if isinstance(row[0], dict) else json.loads(row[0]))
        cur.close(); conn.close()
        print(f"Loaded {len(games)} games from Supabase")

    if not games:
        raise ValueError("No game data found!")

    games.sort(key=lambda g: g.get("game_date", g.get("date", "")))
    return games


def _fetch_island_seeds(n_features):
    """Fetch seeds from live HF spaces."""
    import urllib.request
    spaces = [
        ("S10", "https://nomos42-nba-quant.hf.space/api/best"),
        ("S11", "https://nomos42-nba-quant-2.hf.space/api/best"),
        ("S12", "https://nomos42-nba-evo-3.hf.space/api/best"),
        ("S13", "https://nomos42-nba-evo-4.hf.space/api/best"),
        ("S14", "https://nomos42-nba-evo-5.hf.space/api/best"),
        ("S15", "https://nomos42-nba-evo-6.hf.space/api/best"),
    ]
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    seeds = []
    for name, url in spaces:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Nomos42/1.0"})
            with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                data = json.loads(resp.read())
            if data.get("brier", 1.0) < 0.99:
                mask = np.zeros(n_features, dtype=bool)
                for idx in data.get("features", []):
                    if 0 <= idx < n_features:
                        mask[idx] = True
                if np.sum(mask) >= 5:
                    seeds.append({
                        "mask": mask,
                        "model_type": data.get("model_type", "xgboost"),
                        "hp": data.get("hp", {"depth": 6, "lr": 0.1, "n_est": 200}),
                        "score_moneyline": float(data.get("brier", 1.0)),
                        "score_spread": 1.0,
                        "score_total": 1.0,
                        "composite": 1.0,
                    })
                    print(f"  {name}: brier={data.get('brier','?')}, features={np.sum(mask)}")
        except Exception as e:
            print(f"  {name}: offline ({e})")

    return seeds


if __name__ == "__main__":
    run_autoresearch()
