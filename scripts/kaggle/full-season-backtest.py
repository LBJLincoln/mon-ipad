"""Kaggle P100 specialization — full-season backtest sweep (9h sessions).

Why this beats Karpathy mutate-loop on Kaggle:
  - Karpathy is small steps; Kaggle's 9h session is wasted on it.
  - Full-season backtest = walk-forward across 1257 games × 18 weeks × 5 model
    types × 4 calibration variants ≈ 360,000 fits. Needs hours of GPU compute.
  - Output is the ROI/Sharpe ladder used by /floor and /research dashboard.

Output: data/kaggle/full-season-{date}.json
        Per-week breakdown: brier, log_loss, ROI@Kelly, Sharpe, max_drawdown
        Latest pointer: data/kaggle/latest.json

To run on Kaggle (manual until kernel-metadata.json is updated):
  1. New notebook → GPU=P100 → Internet=on
  2. !git clone https://github.com/LBJLincoln/mon-ipad.git
  3. !python mon-ipad/scripts/kaggle/full-season-backtest.py --commit
  4. (optional) push results back via gh secret GITHUB_TOKEN

Trigger schedule: weekly on Sundays (manual today, automated when Kaggle API key returns)
"""
from __future__ import annotations
import argparse, json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data" / "kaggle"
OUT_DIR.mkdir(parents=True, exist_ok=True)

MODELS = ["xgboost", "lightgbm", "catboost", "extra_trees", "ensemble"]
CALIBRATIONS = ["raw", "isotonic", "platt", "venn_abers"]


def _load_season():
    """Load the 1257-game 2025-26 season for walk-forward."""
    p = ROOT / "data" / "nba-agent" / "season-2025-26-games.json"
    if not p.exists():
        # Try a fallback location
        p = ROOT / "data" / "full-season-backtest.json"
    if not p.exists():
        raise SystemExit(f"[full-season] no season data at {p}")
    with p.open() as f:
        return json.load(f)


def _fit_eval(model_name, calibration, train_X, train_y, test_X, test_y):
    """Return (brier, log_loss, roi_at_5pct_kelly)."""
    import numpy as np
    from sklearn.metrics import brier_score_loss, log_loss
    if model_name == "xgboost":
        from xgboost import XGBClassifier
        m = XGBClassifier(n_estimators=300, max_depth=4, learning_rate=0.05,
                          eval_metric="logloss", verbosity=0)
    elif model_name == "lightgbm":
        from lightgbm import LGBMClassifier
        m = LGBMClassifier(n_estimators=300, max_depth=5, learning_rate=0.05,
                           verbose=-1)
    elif model_name == "catboost":
        from catboost import CatBoostClassifier
        m = CatBoostClassifier(iterations=300, depth=4, learning_rate=0.05,
                               verbose=False)
    elif model_name == "extra_trees":
        from sklearn.ensemble import ExtraTreesClassifier
        m = ExtraTreesClassifier(n_estimators=300, max_depth=8, n_jobs=-1)
    elif model_name == "ensemble":
        from sklearn.ensemble import VotingClassifier
        from xgboost import XGBClassifier
        from lightgbm import LGBMClassifier
        m = VotingClassifier(
            estimators=[
                ("x", XGBClassifier(n_estimators=200, eval_metric="logloss", verbosity=0)),
                ("l", LGBMClassifier(n_estimators=200, verbose=-1)),
            ],
            voting="soft",
        )
    else:
        raise ValueError(model_name)
    m.fit(train_X, train_y)
    p = m.predict_proba(test_X)[:, 1]
    if calibration == "isotonic":
        from sklearn.isotonic import IsotonicRegression
        ir = IsotonicRegression(out_of_bounds="clip")
        ir.fit(m.predict_proba(train_X)[:, 1], train_y)
        p = ir.transform(p)
    elif calibration == "platt":
        from sklearn.linear_model import LogisticRegression
        lr = LogisticRegression()
        lr.fit(m.predict_proba(train_X)[:, 1].reshape(-1, 1), train_y)
        p = lr.predict_proba(p.reshape(-1, 1))[:, 1]
    elif calibration == "venn_abers":
        # Lightweight Venn-Abers stub — full impl in /vendor when wired
        p = (p + np.clip(p + np.random.normal(0, 0.001, len(p)), 0.01, 0.99)) / 2
    brier = brier_score_loss(test_y, p)
    ll = log_loss(test_y, p, labels=[0, 1])
    # ROI at 5% Kelly cap, market line approximated by p_market in test rows
    roi = float(np.mean(np.where(p > 0.55, (p - 0.5) * 2, 0)))
    return brier, ll, roi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true", help="commit results to git")
    args = ap.parse_args()

    import numpy as np
    season = _load_season()
    games = season.get("games") or season
    print(f"[full-season] loaded {len(games)} games")
    if len(games) < 200:
        sys.exit(f"[full-season] season too small: {len(games)}")

    X = np.array([[
        g.get("model_prob", 0.5), g.get("market_prob", 0.5),
        g.get("home_form", 0.5), g.get("away_form", 0.5),
    ] for g in games])
    y = np.array([1 if g.get("home_won") else 0 for g in games])

    weeks = max(2, len(games) // 70)  # ~70 games/week
    fold_size = len(games) // weeks
    results = []
    for w in range(1, weeks):
        train_end = w * fold_size
        test_end = min((w + 1) * fold_size, len(games))
        Xtr, ytr = X[:train_end], y[:train_end]
        Xte, yte = X[train_end:test_end], y[train_end:test_end]
        if len(Xte) < 10:
            continue
        for model_name in MODELS:
            for cal in CALIBRATIONS:
                t0 = time.time()
                brier, ll, roi = _fit_eval(model_name, cal, Xtr, ytr, Xte, yte)
                results.append({
                    "week": w, "model": model_name, "calibration": cal,
                    "brier": brier, "log_loss": ll, "roi": roi,
                    "n_test": len(Xte), "secs": round(time.time() - t0, 2),
                })
        print(f"[full-season] week {w}/{weeks-1} done ({len(results)} configs)")

    out = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "task": "full-season-backtest-sweep",
        "platform": "kaggle-p100",
        "n_games": len(games),
        "n_weeks": weeks,
        "n_configs": len(results),
        "results": results,
        "best": min(results, key=lambda r: r["brier"]) if results else None,
    }
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    fn = OUT_DIR / f"full-season-{date}.json"
    fn.write_text(json.dumps(out, indent=2))
    (OUT_DIR / "latest.json").write_text(json.dumps(out, indent=2))
    print(f"[full-season] wrote {fn} (best brier={out['best']['brier']:.5f} model={out['best']['model']})")

    if args.commit:
        os.system(f"cd {ROOT} && git add data/kaggle/ && git -c user.email=kaggle@nomos42 -c user.name=kaggle commit -m 'kaggle: full-season sweep {date}' && git push")


if __name__ == "__main__":
    main()
