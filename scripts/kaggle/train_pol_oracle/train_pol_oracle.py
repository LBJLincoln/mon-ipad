"""Kaggle kernel: train POL oracle RF. Mirrors scripts/kaggle/train_nba_oracle."""
import json, os, pickle, time, glob
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.model_selection import KFold
from sklearn.metrics import brier_score_loss

OUT_DIR = "/kaggle/working"
os.makedirs(OUT_DIR, exist_ok=True)

t0 = time.time()
cfg_path = None; npz_path = None
for p in glob.iglob("/kaggle/input/**", recursive=True):
    if p.endswith("political-best-config.json"): cfg_path = p
    elif p.endswith("political_cached_data.npz"): npz_path = p
assert cfg_path and npz_path, f"cfg={cfg_path} npz={npz_path}"
print(f"cfg: {cfg_path}  npz: {npz_path}")

cfg = json.load(open(cfg_path))
arr = np.load(npz_path, allow_pickle=True)
X_all = arr["X"].astype(np.float32); y = arr["y"].astype(np.int32); fn = arr["feature_names"]
feat_idx = [i for i in cfg["feature_indices"] if 0 <= i < X_all.shape[1]]
X = X_all[:, feat_idx]
print(f"X={X.shape} y_mean={float(y.mean()):.4f}")
print(f"target brier: {cfg['best_brier']:.5f}")

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
    briers.append(float(brier_score_loss(y[te], p)))
    print(f"  fold {fold}: brier={briers[-1]:.5f}")
brier_mean = float(np.mean(briers))
print(f"CV mean: {brier_mean:.5f} | target: {cfg['best_brier']:.5f} | delta {brier_mean - cfg['best_brier']:+.5f}")

iso = IsotonicRegression(out_of_bounds="clip"); iso.fit(oof, y)
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
    "config": cfg, "n_samples": int(X.shape[0]),
    "trained_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "trained_on": "kaggle",
}
with open(f"{OUT_DIR}/pol-oracle.pkl", "wb") as f: pickle.dump(bundle, f)
summary = {k: v for k, v in bundle.items() if k not in ("model", "calibrator")}
with open(f"{OUT_DIR}/summary.json", "w") as f: json.dump(summary, f, indent=2, default=str)
print(f"done in {time.time()-t0:.1f}s, pickle {os.path.getsize(f'{OUT_DIR}/pol-oracle.pkl')/1024:.0f} KB")
