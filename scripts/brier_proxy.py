#!/usr/bin/env python3
"""
brier_proxy.py — 30-second Brier proxy metric for Hermes councils.

The councils (D1-D9 department loops) historically could not do keep/revert
because the real Brier eval takes 10+ minutes on the VM. This proxy takes
~2-5 seconds and gives a directionally-correct delta that councils can use
to gate structural changes.

Three modes:

1. Baseline mode (no args): fit a LogisticRegression on data/proxy/holdout.json
   with 5-fold CV, report mean Brier. This is the "reference" baseline every
   council run should beat.

2. Predictions mode (--predictions path.json): read a JSON file mapping
   {"game_id": float_prob_home_win} and score those predictions against the
   cached outcomes. Missing game_ids → 0.5 (uninformed prior). Use this mode
   when a council has a candidate model/config that can generate explicit
   probabilities.

3. Compare mode (--before a.json --after b.json): score both prediction files
   and return delta (negative = improvement). Exit code 0 if after <= before,
   otherwise 1. Use this mode in council scripts to drive keep/revert.

Target runtime: under 30s. Baseline mode on the current 50-game holdout runs
in ~0.3s on the VM.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOLDOUT_PATH = ROOT / "data" / "proxy" / "holdout.json"


def brier(probs: list[float], labels: list[int]) -> float:
    return sum((p - y) ** 2 for p, y in zip(probs, labels)) / len(labels)


def load_holdout() -> dict:
    if not HOLDOUT_PATH.exists():
        print(f"[proxy] holdout missing at {HOLDOUT_PATH}. "
              f"Run scripts/build_proxy_holdout.py first.", file=sys.stderr)
        sys.exit(2)
    return json.loads(HOLDOUT_PATH.read_text())


def fit_logreg_cv(X: list[list[float]], y: list[int], k: int = 5) -> float:
    """5-fold CV Brier using sklearn LogisticRegression. Falls back to a
    closed-form logistic fit if sklearn isn't importable (shouldn't happen
    on VM but belt-and-suspenders)."""
    try:
        import numpy as np
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import KFold
    except ImportError:
        return _fallback_logistic_cv(X, y, k)

    Xa = np.array(X, dtype=np.float64)
    ya = np.array(y, dtype=np.int64)
    kf = KFold(n_splits=k, shuffle=True, random_state=42)
    probs = np.zeros(len(y), dtype=np.float64)
    # Strong L2 regularization (C=0.1) keeps predictions close to prior on
    # small-sample folds so delta signal is stable across runs.
    for tr, te in kf.split(Xa):
        model = LogisticRegression(max_iter=500, C=0.1)
        model.fit(Xa[tr], ya[tr])
        col = list(model.classes_).index(1) if 1 in model.classes_ else 0
        probs[te] = model.predict_proba(Xa[te])[:, col]
    return float(brier(probs.tolist(), y))


def _fallback_logistic_cv(X: list[list[float]], y: list[int], k: int) -> float:
    """Tiny closed-form fallback: use only the ml_home_implied_prob column
    (index 2 in feature_names) as the prediction. Not a real CV, but gives
    a stable baseline if sklearn is missing."""
    probs = [max(0.01, min(0.99, row[2])) for row in X]
    return brier(probs, y)


def score_predictions_file(path: Path, holdout: dict) -> tuple[float, int, int]:
    """Return (brier, matched, total) where matched = games the pred file
    covered and total = games in the holdout."""
    try:
        preds: dict[str, float] = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        print(f"[proxy] failed to read {path}: {e}", file=sys.stderr)
        sys.exit(2)

    ids = holdout["game_ids"]
    y = holdout["y"]
    probs = []
    matched = 0
    for gid, yi in zip(ids, y):
        p = preds.get(gid)
        if p is None:
            p = 0.5
        else:
            matched += 1
        probs.append(float(p))
    return brier(probs, y), matched, len(ids)


def main() -> int:
    p = argparse.ArgumentParser(description="30-second Brier proxy metric")
    p.add_argument("--predictions", type=Path, help="JSON mapping game_id→home_win_prob")
    p.add_argument("--before", type=Path, help="Baseline predictions JSON")
    p.add_argument("--after", type=Path, help="Candidate predictions JSON")
    p.add_argument("--json", action="store_true", help="emit structured JSON")
    args = p.parse_args()

    start = time.time()
    holdout = load_holdout()

    if args.before and args.after:
        b_before, matched_b, total = score_predictions_file(args.before, holdout)
        b_after, matched_a, _ = score_predictions_file(args.after, holdout)
        delta = b_after - b_before
        elapsed = time.time() - start
        result = {
            "mode": "compare",
            "brier_before": round(b_before, 6),
            "brier_after": round(b_after, 6),
            "delta": round(delta, 6),
            "improved": bool(delta < 0),
            "matched_before": matched_b,
            "matched_after": matched_a,
            "n_games": total,
            "elapsed_sec": round(elapsed, 3),
        }
        if args.json:
            print(json.dumps(result))
        else:
            print(f"[proxy] before={b_before:.5f} after={b_after:.5f} "
                  f"delta={delta:+.5f} improved={delta < 0} "
                  f"({elapsed:.2f}s, matched={matched_a}/{total})")
        return 0 if delta <= 0 else 1

    if args.predictions:
        b, matched, total = score_predictions_file(args.predictions, holdout)
        elapsed = time.time() - start
        result = {
            "mode": "score",
            "brier": round(b, 6),
            "matched": matched,
            "n_games": total,
            "elapsed_sec": round(elapsed, 3),
        }
        if args.json:
            print(json.dumps(result))
        else:
            print(f"[proxy] brier={b:.5f} matched={matched}/{total} ({elapsed:.2f}s)")
        return 0

    # Baseline mode — 5-fold CV LogReg
    brier_cv = fit_logreg_cv(holdout["X"], holdout["y"])
    elapsed = time.time() - start
    result = {
        "mode": "baseline_cv",
        "brier": round(brier_cv, 6),
        "n_games": holdout["n_games"],
        "home_win_rate": holdout["home_win_rate"],
        "feature_dim": len(holdout["feature_names"]),
        "elapsed_sec": round(elapsed, 3),
    }
    if args.json:
        print(json.dumps(result))
    else:
        print(f"[proxy] baseline 5-fold CV LogReg brier={brier_cv:.5f} "
              f"(n={holdout['n_games']}, {elapsed:.2f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
