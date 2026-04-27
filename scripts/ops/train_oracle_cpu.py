#!/usr/bin/env python3
"""CPU TabICL Oracle training — VM fallback when Kaggle GPU quota is exhausted.

Loads the enriched cache from local data/karpathy/nba_cached_data.npz, runs
the same CPCV sweep as the Kaggle script, pushes the bundle to HF, promotes
if Brier improves vs current production.

TabICL on CPU is ~5-8x slower than T4 — running 3 ctx × 3 temp × 10 folds
will take ~3-4 hrs on this 2-core VM. To stay within budget we narrow:
  - 2 ctx values (1024, 2048) instead of 3
  - 2 temps (0.95, 1.0) instead of 3
  - n_estimators=1, single-precision

Total: 4 configs × 10 folds = 40 fits, ~90-120 min.

Usage: HF_TOKEN_NBA=... python3 scripts/ops/train_oracle_cpu.py
"""
from __future__ import annotations
import os, sys, json, pickle, time
from pathlib import Path
from datetime import datetime, timezone

REPO = Path(__file__).resolve().parents[2]
NPZ_LOCAL = REPO / "data" / "karpathy" / "nba_cached_data.npz"
PKL_OUT = REPO / "data" / "karpathy" / f"tabicl-cpu-{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H-%M-%SZ')}.pkl"

import numpy as np
from sklearn.metrics import brier_score_loss
from sklearn.model_selection import StratifiedKFold
from sklearn.isotonic import IsotonicRegression


def main() -> int:
    if not NPZ_LOCAL.exists():
        print(f"ERR: cache missing at {NPZ_LOCAL}", file=sys.stderr)
        return 1
    data = np.load(NPZ_LOCAL, allow_pickle=True)
    X_full = data["X"]
    y = data["y"]
    feat_names = list(data["feature_names"])
    X_full = np.nan_to_num(X_full, nan=0.0, posinf=0.0, neginf=0.0)
    print(f"cache: X={X_full.shape} y={y.shape} y_mean={y.mean():.3f}")

    # Top 186 features by variance (skip dead ones)
    variances = X_full.var(axis=0)
    alive_idx = np.where(variances > 1e-10)[0]
    print(f"alive features: {len(alive_idx)}/{len(variances)}")
    ranked = sorted(alive_idx, key=lambda i: -variances[i])
    top_idx = ranked[:186]
    X = X_full[:, top_idx].astype(np.float32)
    feat_names_186 = [feat_names[i] for i in top_idx]
    print(f"X selected: {X.shape}")

    try:
        from tabicl import TabICLClassifier
    except ImportError:
        print("Installing tabicl...", file=sys.stderr)
        os.system("pip install --break-system-packages -q tabicl 2>&1 | tail -3")
        from tabicl import TabICLClassifier

    RANDOM_STATE = 1337
    N_FOLDS = 10
    EMBARGO = max(1, int(len(X) * 0.02))
    FOLD_SIZE = len(X) // N_FOLDS

    def cpcv_folds(n):
        for k in range(N_FOLDS):
            lo = k * FOLD_SIZE
            hi = lo + FOLD_SIZE if k < N_FOLDS - 1 else n
            mask = np.ones(n, dtype=bool)
            mask[max(0, lo - EMBARGO):min(n, hi + EMBARGO)] = False
            yield np.where(mask)[0], np.arange(lo, hi)

    sweep = []
    for ctx in [1024, 2048]:
        for temp in [0.95, 1.0]:
            briers = []
            t0 = time.time()
            for tr, te in cpcv_folds(len(X)):
                m = TabICLClassifier(n_estimators=1, softmax_temperature=temp, random_state=RANDOM_STATE)
                sub_tr = tr[-ctx:]
                m.fit(X[sub_tr], y[sub_tr])
                p = m.predict_proba(X[te])[:, 1]
                briers.append(float(brier_score_loss(y[te], p)))
            cv = float(np.mean(briers))
            elapsed = time.time() - t0
            sweep.append({"ctx": ctx, "temp": temp, "cv_brier_mean": cv,
                          "cv_brier_per_fold": briers, "fit_time_sec": elapsed})
            print(f"ctx={ctx} temp={temp:.2f} brier={cv:.5f} ({elapsed:.0f}s)")

    best = min(sweep, key=lambda r: r["cv_brier_mean"])
    print(f"\nBEST: ctx={best['ctx']} temp={best['temp']} brier={best['cv_brier_mean']:.5f}")

    # Isotonic + final model
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    oof = np.zeros(len(X))
    for tr, te in skf.split(X, y):
        sub_tr = tr[-best["ctx"]:] if len(tr) > best["ctx"] else tr
        m = TabICLClassifier(n_estimators=1, softmax_temperature=best["temp"], random_state=RANDOM_STATE)
        m.fit(X[sub_tr], y[sub_tr])
        oof[te] = m.predict_proba(X[te])[:, 1]
    iso = IsotonicRegression(out_of_bounds="clip").fit(oof, y)
    print(f"isotonic: raw_brier={brier_score_loss(y, oof):.5f} calib_brier={brier_score_loss(y, iso.predict(oof)):.5f}")

    final = TabICLClassifier(n_estimators=1, softmax_temperature=best["temp"], random_state=RANDOM_STATE)
    final.fit(X[-best["ctx"]:], y[-best["ctx"]:])

    utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    bundle = {
        "model": final, "calibrator": iso,
        "feature_indices": [int(i) for i in top_idx],
        "feature_names": feat_names_186,
        "cv_brier_mean": best["cv_brier_mean"],
        "cv_brier_per_fold": best["cv_brier_per_fold"],
        "config": {"model_type": "tabicl", "n_features": 186,
                   "ctx_size": best["ctx"], "softmax_temperature": best["temp"],
                   "random_state": RANDOM_STATE, "cpcv_folds": N_FOLDS},
        "n_samples": int(X.shape[0]),
        "trained_at": utc,
        "trained_on": "vm-cpu-tabicl",
        "sweep_results": sweep,
    }
    PKL_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(PKL_OUT, "wb") as f:
        pickle.dump(bundle, f)
    sz_mb = PKL_OUT.stat().st_size / 1024 / 1024
    print(f"pkl saved: {PKL_OUT} ({sz_mb:.1f} MB)")

    tok = os.environ.get("HF_TOKEN_NBA") or os.environ.get("HF_TOKEN")
    if not tok:
        print("WARN: HF_TOKEN_NBA missing — local pkl written, no push")
        return 0
    try:
        from huggingface_hub import HfApi, hf_hub_download
        api = HfApi(token=tok)
        api.create_repo("LBJLincoln26/nba-oracle-archive", repo_type="dataset", private=False, exist_ok=True)
        api.upload_file(path_or_fileobj=str(PKL_OUT),
                        path_in_repo=f"vm-cpu-tabicl-{utc}.pkl",
                        repo_id="LBJLincoln26/nba-oracle-archive", repo_type="dataset",
                        commit_message=f"[vm-cpu-tabicl] Brier {best['cv_brier_mean']:.5f}")
        print(f"archived")
        try:
            cur = json.load(open(hf_hub_download(
                repo_id="LBJLincoln26/nba-oracle-model", filename="summary.json",
                repo_type="dataset", token=tok)))
            cur_brier = float(cur.get("cv_brier_mean", 0.99))
        except Exception:
            cur_brier = 0.99
        print(f"current production: {cur_brier:.5f}")
        if best["cv_brier_mean"] < cur_brier:
            api.upload_file(path_or_fileobj=str(PKL_OUT), path_in_repo="nba-oracle.pkl",
                            repo_id="LBJLincoln26/nba-oracle-model", repo_type="dataset",
                            commit_message=f"[PROMOTE vm-cpu-tabicl] {best['cv_brier_mean']:.5f} (was {cur_brier:.5f})")
            summary = {k: v for k, v in bundle.items() if k not in ("model", "calibrator")}
            summary["promoted_from_brier"] = cur_brier
            api.upload_file(path_or_fileobj=json.dumps(summary, indent=2, default=str).encode(),
                            path_in_repo="summary.json",
                            repo_id="LBJLincoln26/nba-oracle-model", repo_type="dataset",
                            commit_message="[PROMOTE vm-cpu-tabicl] summary")
            print(f"\n*** PROMOTED: {best['cv_brier_mean']:.5f} (was {cur_brier:.5f}) ***")
        else:
            print(f"Not promoted: {best['cv_brier_mean']:.5f} >= {cur_brier:.5f}")
    except Exception as e:
        print(f"push err: {e}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
