#!/usr/bin/env python3
"""
brier_proxy.py — Cached Brier proxy metric for Hermes councils.

Three modes:

1. Baseline mode (no args): 5-fold LR CV on data/proxy/holdout.json. Result
   is CACHED in data/proxy/baseline_cache.json keyed on a SHA1 of the holdout.
   First call ~100s (sklearn cold import dominates on 1vCPU VM). Subsequent
   calls ~0.8s until the holdout file changes.

2. Predictions mode (--predictions path.json): read a JSON file mapping
   {"game_id": float_prob_home_win} and score those predictions against the
   cached outcomes. Missing game_ids → 0.5 (uninformed prior). Use this when
   a council can generate explicit per-game probabilities.

3. Compare mode (--before a.json --after b.json): score both prediction files
   and return delta (negative = improvement). Exit code 0 if after <= before,
   otherwise 1. THIS IS THE MODE THAT SHOULD DRIVE KEEP/REVERT.

──────────────────────────────────────────────────────────────────────────
⚠ HONEST LIMITATION (2026-04-11 audit):

`baseline_cv` mode is a CONSTANT function of the holdout file. If you call
it before and after a council iteration, the delta is ALWAYS 0 (unless the
council itself rewrites data/proxy/holdout.json, which none currently do).
A Paperclip runner calling only baseline_cv can NEVER trigger a revert.

To make Paperclip actually gate keep/revert, the council must produce a
predictions file (e.g. data/proxy/council_preds.json) and Paperclip must
call this script in --before/--after compare mode against before/after
versions of that file. Until councils output predictions, Paperclip's
baseline_cv mode is effectively a syntax/crash gate only — it catches
commits that broke the holdout loader, nothing else.
──────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOLDOUT_PATH = ROOT / "data" / "proxy" / "holdout.json"
CACHE_PATH = ROOT / "data" / "proxy" / "baseline_cache.json"


def brier(probs: list[float], labels: list[int]) -> float:
    return sum((p - y) ** 2 for p, y in zip(probs, labels)) / len(labels)


def load_holdout() -> dict:
    if not HOLDOUT_PATH.exists():
        print(f"[proxy] holdout missing at {HOLDOUT_PATH}. "
              f"Run scripts/build_proxy_holdout.py first.", file=sys.stderr)
        sys.exit(2)
    return json.loads(HOLDOUT_PATH.read_text())


def holdout_hash() -> str:
    """SHA1 of the raw holdout file bytes. Used as the baseline cache key."""
    return hashlib.sha1(HOLDOUT_PATH.read_bytes()).hexdigest()[:16]


def read_cached_baseline(h: str) -> float | None:
    if not CACHE_PATH.exists():
        return None
    try:
        cache = json.loads(CACHE_PATH.read_text())
        if cache.get("hash") == h:
            return float(cache["brier"])
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        pass
    return None


def write_cached_baseline(h: str, brier_value: float) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps({
        "hash": h,
        "brier": brier_value,
        "cached_at": time.time(),
    }))


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

    # Baseline mode — 5-fold CV LogReg, CACHED by holdout hash.
    # Rationale: the CV result is a deterministic function of the holdout
    # file. If the holdout hasn't changed, there's nothing to recompute and
    # paying sklearn's ~100s cold-import on this 1vCPU VM is wasteful. Cache
    # invalidates automatically when build_proxy_holdout.py rewrites the file.
    h = holdout_hash()
    cached = read_cached_baseline(h)
    if cached is not None:
        brier_cv = cached
        from_cache = True
    else:
        brier_cv = fit_logreg_cv(holdout["X"], holdout["y"])
        write_cached_baseline(h, brier_cv)
        from_cache = False
    elapsed = time.time() - start
    result = {
        "mode": "baseline_cv",
        "brier": round(brier_cv, 6),
        "n_games": holdout["n_games"],
        "home_win_rate": holdout["home_win_rate"],
        "feature_dim": len(holdout["feature_names"]),
        "elapsed_sec": round(elapsed, 3),
        "cached": from_cache,
        "holdout_hash": h,
    }
    if args.json:
        print(json.dumps(result))
    else:
        print(f"[proxy] baseline 5-fold CV LogReg brier={brier_cv:.5f} "
              f"(n={holdout['n_games']}, {elapsed:.2f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
