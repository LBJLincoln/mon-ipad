"""NBA Oracle Space — serves the trained RF pickle at /api/predict.

Loads nba-oracle.pkl from the dataset LBJLincoln26/nba-oracle-model at
startup. Exposes /api/predict in the same shape the NBA TF already expects
from the island oracles, so it's a drop-in replacement for the evo-4 URL.

Runs on HF free CPU tier. Idle when not queried.
"""
from __future__ import annotations

import io
import os
import pickle
import time
from typing import Any, Dict, List

import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

# ---- state ---------------------------------------------------------------
_BUNDLE: Dict[str, Any] | None = None
_STATE: Dict[str, Any] = {
    "loaded_at": None,
    "source": "LBJLincoln26/nba-oracle-model/nba-oracle.pkl",
    "cv_brier_mean": None,
    "target_brier": None,
    "n_features": None,
    "n_samples": None,
    "load_err": None,
}


def _load_bundle() -> None:
    """Fetch pickle from HF dataset at startup. Fail-open — health tag it."""
    global _BUNDLE
    try:
        from huggingface_hub import hf_hub_download
        tok = os.environ.get("HF_TOKEN") or None
        path = hf_hub_download(
            repo_id="LBJLincoln26/nba-oracle-model",
            filename="nba-oracle.pkl",
            repo_type="dataset",
            token=tok,
        )
        with open(path, "rb") as f:
            _BUNDLE = pickle.load(f)
        _STATE["loaded_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        _STATE["cv_brier_mean"] = _BUNDLE.get("cv_brier_mean")
        _STATE["target_brier"] = _BUNDLE.get("target_brier")
        _STATE["n_features"] = _BUNDLE.get("n_features") or len(_BUNDLE.get("feature_indices") or [])
        _STATE["n_samples"] = _BUNDLE.get("n_samples")
        _STATE["load_err"] = None
        print(f"[oracle] bundle loaded: CV Brier={_STATE['cv_brier_mean']} n_feat={_STATE['n_features']}", flush=True)
    except Exception as e:
        _STATE["load_err"] = f"{type(e).__name__}: {e}"
        print(f"[oracle] LOAD FAILED: {_STATE['load_err']}", flush=True)


# ---- feature synthesis ---------------------------------------------------
# The RF was trained on 6452 engineered features from the production engine.
# The incoming /api/predict requests only give us {home_team, away_team}.
# For a drop-in oracle replacement we return the prior fleet-level prediction
# (home_win_prob ≈ y_mean) UNLESS full features are passed in; in that case
# we slice feature_indices and predict properly.
# This matches the existing S18/evo-4 behavior: they also just return a base
# prediction when features aren't provided.

def _predict_one(game: Dict[str, Any]) -> Dict[str, Any]:
    if _BUNDLE is None:
        return {"error": "bundle_not_loaded", "home_win_prob": 0.5, "calibrated": False}

    features = game.get("features")
    if features is None:
        # Fallback: use base rate from training set
        # Training set home_win rate ≈ 0.554 per our earlier probe
        p_raw = 0.554
        p_cal = float(_BUNDLE["calibrator"].transform([p_raw])[0])
        return {
            "home_team": game.get("home_team"),
            "away_team": game.get("away_team"),
            "home_win_prob": round(p_cal, 4),
            "away_win_prob": round(1 - p_cal, 4),
            "raw_home_win_prob": round(p_raw, 4),
            "calibrated": True,
            "confidence": 0.0,
            "kelly_stake": 0.0,
            "model_type": "random_forest",
            "features_used": _STATE["n_features"],
            "brier_cv": _STATE["cv_brier_mean"],
            "note": "base-rate fallback (no features supplied)",
        }
    # Features path: slice by feature_indices, predict
    try:
        X_full = np.asarray(features, dtype=np.float32).reshape(1, -1)
        X = X_full[:, _BUNDLE["feature_indices"]]
        p_raw = float(_BUNDLE["model"].predict_proba(X)[0, 1])
        p_cal = float(_BUNDLE["calibrator"].transform([p_raw])[0])
        conf = float(abs(p_cal - 0.5) * 2)
        return {
            "home_team": game.get("home_team"),
            "away_team": game.get("away_team"),
            "home_win_prob": round(p_cal, 4),
            "away_win_prob": round(1 - p_cal, 4),
            "raw_home_win_prob": round(p_raw, 4),
            "calibrated": True,
            "confidence": round(conf, 4),
            "kelly_stake": 0.0,
            "model_type": "random_forest",
            "features_used": _STATE["n_features"],
            "brier_cv": _STATE["cv_brier_mean"],
        }
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}", "home_win_prob": 0.5}


# ---- FastAPI -------------------------------------------------------------
app = FastAPI(title="NBA Oracle", version="1.0")


@app.on_event("startup")
def _startup() -> None:
    _load_bundle()


@app.get("/")
def root() -> Dict[str, Any]:
    return {
        "service": "nba-oracle",
        "state": _STATE,
        "endpoints": ["/api/predict", "/api/status"],
    }


@app.get("/api/status")
def api_status() -> Dict[str, Any]:
    return {
        "running": _BUNDLE is not None,
        "brier_cv": _STATE["cv_brier_mean"],
        "target_brier": _STATE["target_brier"],
        "n_features": _STATE["n_features"],
        "loaded_at": _STATE["loaded_at"],
        "err": _STATE["load_err"],
    }


@app.get("/api/best")
def api_best() -> Dict[str, Any]:
    if _BUNDLE is None:
        return {"error": _STATE["load_err"] or "bundle not loaded"}
    return {
        "brier": _STATE["cv_brier_mean"],
        "model_type": "random_forest",
        "features": _BUNDLE.get("feature_indices", [])[:20],  # head only
        "n_features": _STATE["n_features"],
        "loaded_at": _STATE["loaded_at"],
    }


@app.post("/api/predict")
async def api_predict(request: Request) -> JSONResponse:
    body = await request.json()
    games = body.get("games") or []
    if not games:
        return JSONResponse({"error": "no games to predict — provide 'games' array"}, status_code=400)
    preds = [_predict_one(g) for g in games]
    meta = {
        "type": "random_forest",
        "brier_cv": _STATE["cv_brier_mean"],
        "features": _STATE["n_features"],
        "generation": 1,
    }
    return JSONResponse({
        "predictions": preds,
        "model": meta,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })
