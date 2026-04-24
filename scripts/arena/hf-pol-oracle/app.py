"""POL Oracle Space — serves RF pickle from HF dataset LBJLincoln26/pol-oracle-model."""
import os, pickle, time
import numpy as np
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

_BUNDLE = None
_STATE = {"loaded_at": None, "cv_brier_mean": None, "n_features": None, "load_err": None}


def _load_bundle():
    global _BUNDLE
    try:
        from huggingface_hub import hf_hub_download
        tok = os.environ.get("HF_TOKEN") or None
        path = hf_hub_download(
            repo_id="LBJLincoln26/pol-oracle-model",
            filename="pol-oracle.pkl", repo_type="dataset", token=tok,
        )
        with open(path, "rb") as f: _BUNDLE = pickle.load(f)
        _STATE["loaded_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        _STATE["cv_brier_mean"] = _BUNDLE.get("cv_brier_mean")
        _STATE["n_features"] = _BUNDLE.get("n_samples") and len(_BUNDLE.get("feature_indices") or [])
        print(f"[pol-oracle] loaded: CV Brier={_STATE['cv_brier_mean']}", flush=True)
    except Exception as e:
        _STATE["load_err"] = f"{type(e).__name__}: {e}"
        print(f"[pol-oracle] LOAD FAILED: {_STATE['load_err']}", flush=True)


app = FastAPI(title="POL Oracle", version="1.0")


@app.on_event("startup")
def _startup(): _load_bundle()


@app.get("/")
def root(): return {"service": "pol-oracle", "state": _STATE, "endpoints": ["/api/predict", "/api/status", "/api/best"]}


@app.get("/api/status")
def api_status():
    return {"running": _BUNDLE is not None, "brier_cv": _STATE["cv_brier_mean"],
            "n_features": _STATE["n_features"], "loaded_at": _STATE["loaded_at"], "err": _STATE["load_err"]}


@app.get("/api/best")
def api_best():
    if _BUNDLE is None: return {"error": _STATE["load_err"] or "not loaded"}
    return {"brier": _STATE["cv_brier_mean"], "model_type": "random_forest",
            "features": (_BUNDLE.get("feature_indices") or [])[:20],
            "n_features": _STATE["n_features"], "loaded_at": _STATE["loaded_at"]}


@app.post("/api/predict")
async def api_predict(request: Request):
    body = await request.json()
    events = body.get("events") or []
    if not events:
        return JSONResponse({"error": "no events to predict -- provide 'events' array"}, status_code=400)
    preds = []
    for ev in events:
        if _BUNDLE is None:
            preds.append({"error": "bundle not loaded", "p_yes": 0.5})
            continue
        features = ev.get("features")
        if features is None:
            # Base rate fallback for POL = 0.554 (train set mean)
            p_raw = 0.554
            p_cal = float(_BUNDLE["calibrator"].transform([p_raw])[0])
            preds.append({
                "event_id": ev.get("event_id"),
                "p_yes": round(p_cal, 4), "p_no": round(1 - p_cal, 4),
                "raw_p_yes": round(p_raw, 4), "calibrated": True,
                "confidence": 0.0, "model_type": "random_forest",
                "features_used": _STATE["n_features"],
                "brier_cv": _STATE["cv_brier_mean"],
                "note": "base-rate fallback (no features supplied)",
            })
        else:
            try:
                X_full = np.asarray(features, dtype=np.float32).reshape(1, -1)
                X = X_full[:, _BUNDLE["feature_indices"]]
                p_raw = float(_BUNDLE["model"].predict_proba(X)[0, 1])
                p_cal = float(_BUNDLE["calibrator"].transform([p_raw])[0])
                preds.append({
                    "event_id": ev.get("event_id"),
                    "p_yes": round(p_cal, 4), "p_no": round(1 - p_cal, 4),
                    "raw_p_yes": round(p_raw, 4), "calibrated": True,
                    "confidence": round(abs(p_cal - 0.5) * 2, 4),
                    "model_type": "random_forest",
                    "features_used": _STATE["n_features"],
                    "brier_cv": _STATE["cv_brier_mean"],
                })
            except Exception as e:
                preds.append({"error": f"{type(e).__name__}: {e}", "p_yes": 0.5})
    return JSONResponse({
        "predictions": preds,
        "model": {"type": "random_forest", "brier_cv": _STATE["cv_brier_mean"], "features": _STATE["n_features"]},
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })
