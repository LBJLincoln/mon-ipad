"""Kaggle kernel: train NBA oracle RF from Kaggle-dataset-delivered training data.

Input: /kaggle/input/nba-oracle-training-data/{nba_cached_data.npz, nba-best-config.json}
Output: /kaggle/working/nba-oracle.pkl + summary.json

No GitHub secret required. No HF secret required. Pure CPU training.
VM pulls the output via `kaggle kernels output` after completion, then
uploads to HF dataset from VM-side where HF_TOKEN_NBA is already wired.
"""
import json, os, pickle, time, io
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.model_selection import KFold
from sklearn.metrics import brier_score_loss

import glob
OUT_DIR = "/kaggle/working"
os.makedirs(OUT_DIR, exist_ok=True)

t0 = time.time()
print("=== discover data ===")
for p in glob.glob("/kaggle/input/**", recursive=True)[:40]:
    print(f"  {p}")
# Auto-locate the two files anywhere under /kaggle/input
cfg_path = None; npz_path = None
for p in glob.iglob("/kaggle/input/**", recursive=True):
    if p.endswith("nba-best-config.json"): cfg_path = p
    elif p.endswith("nba_cached_data.npz"): npz_path = p
if not (cfg_path and npz_path):
    raise RuntimeError(f"missing inputs. cfg={cfg_path} npz={npz_path}")
print(f"cfg_path: {cfg_path}")
print(f"npz_path: {npz_path}")

print("\n=== load data ===")
cfg = json.load(open(cfg_path))
arr = np.load(npz_path, allow_pickle=True)
X_all = arr["X"].astype(np.float32)
y     = arr["y"].astype(np.int32)
fn    = arr["feature_names"]
print(f"  X={X_all.shape} y_mean={float(y.mean()):.4f}")
print(f"  config: model={cfg['model_type']} n_est={cfg['n_estimators']} target_brier={cfg['best_brier']:.5f}")

feat_idx = [i for i in cfg["feature_indices"] if 0 <= i < X_all.shape[1]]
X = X_all[:, feat_idx]

print("\n=== 5-fold CV Brier ===")
kf = KFold(n_splits=5, shuffle=True, random_state=42)
briers, oof = [], np.zeros(len(y))
for fold, (tr, te) in enumerate(kf.split(X)):
    clf = RandomForestClassifier(
        n_estimators=cfg["n_estimators"], max_depth=cfg["max_depth"],
        min_samples_leaf=cfg["min_samples_leaf"],
        max_features=cfg["max_features_ratio"],
        n_jobs=-1, random_state=42,
    )
    clf.fit(X[tr], y[tr])
    p = clf.predict_proba(X[te])[:, 1]
    oof[te] = p
    b = float(brier_score_loss(y[te], p))
    briers.append(b)
    print(f"  fold {fold}: brier={b:.5f}")
brier_mean = float(np.mean(briers))
print(f"\nCV mean: {brier_mean:.5f} | target: {cfg['best_brier']:.5f} | delta {brier_mean - cfg['best_brier']:+.5f}")

iso = IsotonicRegression(out_of_bounds="clip"); iso.fit(oof, y)

print("\n=== full-data fit ===")
final = RandomForestClassifier(
    n_estimators=cfg["n_estimators"], max_depth=cfg["max_depth"],
    min_samples_leaf=cfg["min_samples_leaf"],
    max_features=cfg["max_features_ratio"],
    n_jobs=-1, random_state=42,
)
final.fit(X, y)

bundle = {
    "model": final, "calibrator": iso,
    "feature_indices": feat_idx,
    "feature_names": [str(fn[i]) for i in feat_idx],
    "cv_brier_mean": brier_mean,
    "cv_brier_per_fold": briers,
    "target_brier": float(cfg["best_brier"]),
    "config": cfg,
    "n_samples": int(X.shape[0]),
    "trained_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "trained_on": "kaggle",
}
pk_path = f"{OUT_DIR}/nba-oracle.pkl"
with open(pk_path, "wb") as f:
    pickle.dump(bundle, f)
print(f"pickled {os.path.getsize(pk_path)/1024:.0f} KB in {time.time() - t0:.1f}s")

summary = {k: v for k, v in bundle.items() if k not in ("model", "calibrator")}
with open(f"{OUT_DIR}/summary.json", "w") as f:
    json.dump(summary, f, indent=2, default=str)
print("done")
