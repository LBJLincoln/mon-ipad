"""Modal A10G specialization — CPCV walk-forward + DSR gate.

Why this beats Karpathy mutate-loop on A10G:
  - Karpathy is already covered by Lightning T4 (free) + 21 HF islands (CPU pool).
  - CPCV (Combinatorial Purged CV) needs ~5-min sustained compute per run and
    GH Actions (free 6h budget) chokes on it. Modal A10G paid ($0.18/burst) is
    the right fit: serverless A10G, no quota, exactly 5-10 min per call.
  - DSR (Deflated Sharpe Ratio) gate filters out lucky configs from CPCV results.

Output: data/gpu-burst/modal-cpcv-latest.json
        {ts, n_splits, brier_mean, brier_std, dsr, sharpe, gate_passed}
        Also appended to data/gpu-burst/cpcv-history.jsonl

Trigger: modal run scripts/gpu-burst/modal-cpcv.py
         GH Action: 15 */4 * * *
"""
from __future__ import annotations
import modal
from pathlib import Path

app = modal.App("nomos42-cpcv")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "scikit-learn==1.5.2",
        "numpy>=1.26",
        "pandas>=2.2",
        "lightgbm>=4.5",
        "xgboost>=2.1",
        "catboost>=1.2",
        "requests",
        # CPCV implemented inline below — skfolio/cvxpy dropped to avoid cp.trace import TypeError.
    )
)

@app.function(
    gpu="a10g",
    image=image,
    timeout=600,
    secrets=[modal.Secret.from_name("nomos42-secrets")],
)
def cpcv_burst():
    """Run CPCV across the canonical hold-out window. Emit DSR gate verdict."""
    import json, os, urllib.request
    from datetime import datetime, timezone
    from itertools import combinations
    import numpy as np
    from sklearn.metrics import brier_score_loss
    import lightgbm as lgb

    def combinatorial_purged_splits(n_samples, n_folds=10, n_test_folds=2,
                                    embargo=5, purge=5):
        """Inline CPCV (Lopez de Prado): enumerate all C(n_folds, n_test_folds)
        test compositions, purge `purge` rows around each test block and embargo
        `embargo` rows after. Yields (train_idx, test_idx)."""
        bounds = np.array_split(np.arange(n_samples), n_folds)
        for combo in combinations(range(n_folds), n_test_folds):
            test = np.concatenate([bounds[i] for i in combo])
            mask = np.ones(n_samples, dtype=bool)
            for i in combo:
                blk = bounds[i]
                lo = max(0, blk[0] - purge)
                hi = min(n_samples, blk[-1] + 1 + embargo)
                mask[lo:hi] = False
            train = np.where(mask)[0]
            yield train, test

    GH_TOKEN = os.environ.get("GITHUB_TOKEN")
    if not GH_TOKEN:
        return {"error": "GITHUB_TOKEN missing"}

    # Pull canonical bet-level record from raw GitHub. Repo is private so
    # GITHUB_TOKEN is required; raw.githubusercontent.com honors bearer auth.
    raw = "https://raw.githubusercontent.com/LBJLincoln/mon-ipad/main/data/arena/trading-floor-v5-latest.json"
    req = urllib.request.Request(raw, headers={"Authorization": f"Bearer {GH_TOKEN}"})
    try:
        data = json.loads(urllib.request.urlopen(req, timeout=30).read())
    except Exception as e:
        return {"error": f"fetch failed: {e}"}

    bets = data.get("bets") or data.get("trades") or data.get("predictions") or []
    if len(bets) < 200:
        return {"error": f"only {len(bets)} bets in hold-out, need 200+"}

    # Feature matrix from real bet rows. Fields vary across sources; we
    # accept (prob, edge, odds, stake) as a robust superset.
    def _f(b, k, default=0.5):
        v = b.get(k, default)
        try: return float(v)
        except (TypeError, ValueError): return default
    X = np.array([[
        _f(b, "prob", 0.5),
        _f(b, "edge", 0.0),
        _f(b, "odds", 2.0),
        _f(b, "stake", 1.0),
    ] for b in bets])
    y = np.array([1 if (b.get("won") or b.get("home_won") or (b.get("pnl", 0) > 0)) else 0 for b in bets])
    if y.sum() == 0 or y.sum() == len(y):
        return {"error": f"degenerate y: all {y[0]} across {len(y)} rows"}

    briers = []
    for train_idx, test_idx in combinatorial_purged_splits(len(y), n_folds=10, n_test_folds=2, purge=5, embargo=5):
        if len(train_idx) < 50 or len(test_idx) < 20:
            continue
        m = lgb.LGBMClassifier(n_estimators=200, max_depth=4, verbose=-1)
        m.fit(X[train_idx], y[train_idx])
        p = m.predict_proba(X[test_idx])[:, 1]
        briers.append(brier_score_loss(y[test_idx], p))

    mean = float(np.mean(briers))
    std = float(np.std(briers))
    sharpe = (0.25 - mean) / std if std > 0 else 0.0  # higher = better (lower brier)
    n_trials = len(briers)
    # Bailey & Lopez de Prado DSR (2014, simplified)
    z = sharpe * np.sqrt(n_trials)
    dsr = float(1 / (1 + np.exp(-z)))
    gate_passed = (mean < 0.225 and dsr > 0.95)

    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "task": "cpcv-walkforward-dsr",
        "n_splits": n_trials,
        "brier_mean": mean,
        "brier_std": std,
        "sharpe_proxy": sharpe,
        "dsr": dsr,
        "gate_passed": gate_passed,
    }

@app.local_entrypoint()
def main():
    """Called by GH Action: writes result to data/gpu-burst/."""
    import json
    from datetime import datetime, timezone
    result = cpcv_burst.remote()
    out = Path(__file__).resolve().parents[2] / "data" / "gpu-burst"
    out.mkdir(parents=True, exist_ok=True)
    (out / "modal-cpcv-latest.json").write_text(json.dumps(result, indent=2))
    with (out / "cpcv-history.jsonl").open("a") as f:
        f.write(json.dumps(result) + "\n")
    print(json.dumps(result, indent=2))
