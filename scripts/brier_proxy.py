#!/usr/bin/env python3
"""
brier_proxy.py — Cached Brier proxy metric for Hermes councils.

Four modes:

1. Baseline mode (no args, or --json alone): reads the LATEST real backtest
   results from data/arena/backtest-results/backtest-latest.json or
   data/karpathy/nba-best-config.json. Returns the live model Brier — a
   value that actually changes as the evolution loop improves the fleet.

   Priority order for the Brier source:
     a) data/arena/backtest-results/backtest-latest.json  → real_brier / model_brier
     b) data/nba-agent/full-season-backtest.json          → brier field
     c) data/karpathy/nba-best-config.json                → best_brier
     d) data/nba-agent/backtest-results.json              → brier_score
     e) Fallback: 5-fold LogReg CV on data/proxy/holdout.json (CACHED)
        ⚠ This fallback is a constant function of the holdout file. Use only
          when none of the above exist (e.g. fresh VM without a Karpathy run).

2. Predictions mode (--predictions path.json): read a JSON file mapping
   {"game_id": float_prob_home_win} and score those predictions against the
   cached outcomes. Missing game_ids → 0.5 (uninformed prior). Use this when
   a council can generate explicit per-game probabilities.

3. Compare mode (--before a.json --after b.json): score both prediction files
   and return delta (negative = improvement). Exit code 0 if after <= before,
   otherwise 1. THIS IS THE MODE THAT SHOULD DRIVE KEEP/REVERT.

4. Live-compute mode (--compute): compute Brier directly from the per-game
   model_prob + won fields in backtest trade records. More precise than the
   pre-stored scalar but slightly slower (file parsing only, no sklearn).

──────────────────────────────────────────────────────────────────────────
FIX 2026-04-12: The previous baseline_cv mode was a CONSTANT function of
data/proxy/holdout.json. If called before/after a council iteration, delta
was always exactly 0.0, making the Paperclip keep/revert gate useless.

This rewrite switches the default mode to read real backtest data, which
IS updated as the fleet evolves. Councils in hermes-runner.sh also read
data/karpathy/nba-best-config.json directly — that file IS updated by the
Kaggle Karpathy loop, so those deltas are also now meaningful.
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

# Live data sources (checked in priority order)
_BACKTEST_LATEST = ROOT / "data" / "arena" / "backtest-results" / "backtest-latest.json"
_FULL_SEASON = ROOT / "data" / "nba-agent" / "full-season-backtest.json"
_KARPATHY_BEST = ROOT / "data" / "karpathy" / "nba-best-config.json"
_BACKTEST_RESULTS = ROOT / "data" / "nba-agent" / "backtest-results.json"


def brier(probs: list[float], labels: list[int]) -> float:
    return sum((p - y) ** 2 for p, y in zip(probs, labels)) / len(labels)


def read_live_brier() -> tuple[float | None, str, dict]:
    """Read the most current real Brier score from live data files.

    Returns (brier_value, source_description, extra_metadata).
    Returns (None, "not_found", {}) if no live data available.
    """
    # Priority 1: backtest-latest.json (updated every 4h by swarm)
    if _BACKTEST_LATEST.exists():
        try:
            d = json.loads(_BACKTEST_LATEST.read_text())
            b = d.get("real_brier") or d.get("model_brier")
            n = d.get("real_brier_n") or d.get("games_total") or 0
            if b and isinstance(b, (int, float)) and 0 < b < 1:
                return float(b), "backtest-latest", {
                    "n_games": n,
                    "timestamp": d.get("timestamp", ""),
                }
        except (OSError, json.JSONDecodeError, TypeError):
            pass

    # Priority 2: full-season-backtest.json (updated by aggregate_swarm)
    if _FULL_SEASON.exists():
        try:
            d = json.loads(_FULL_SEASON.read_text())
            b = d.get("brier")
            n = d.get("brier_n") or len(d.get("trades", []))
            if b and isinstance(b, (int, float)) and 0 < b < 1:
                return float(b), "full-season-backtest", {
                    "n_games": n,
                    "timestamp": d.get("generated_at", ""),
                }
        except (OSError, json.JSONDecodeError, TypeError):
            pass

    # Priority 3: karpathy best-config (updated by Kaggle Karpathy loop)
    if _KARPATHY_BEST.exists():
        try:
            d = json.loads(_KARPATHY_BEST.read_text())
            b = d.get("best_brier")
            if b and isinstance(b, (int, float)) and 0 < b < 1:
                return float(b), "karpathy-best-config", {
                    "iteration": d.get("iteration", 0),
                    "timestamp": d.get("timestamp", ""),
                }
        except (OSError, json.JSONDecodeError, TypeError):
            pass

    # Priority 4: nba-agent backtest-results.json
    if _BACKTEST_RESULTS.exists():
        try:
            d = json.loads(_BACKTEST_RESULTS.read_text())
            b = d.get("brier_score")
            n = d.get("predictions_evaluated") or d.get("total_bets") or 0
            if b and isinstance(b, (int, float)) and 0 < b < 1:
                return float(b), "backtest-results", {
                    "n_games": n,
                    "timestamp": d.get("last_updated", ""),
                }
        except (OSError, json.JSONDecodeError, TypeError):
            pass

    return None, "not_found", {}


def compute_brier_from_trades() -> tuple[float | None, str, int]:
    """Compute Brier score directly from model_prob + won fields in trade records.

    More precise than a pre-stored scalar because it recomputes from raw data.
    Returns (brier, source, n_games).
    """
    for path, field in [(_FULL_SEASON, "trades"), (_BACKTEST_RESULTS, "trades")]:
        if not path.exists():
            continue
        try:
            d = json.loads(path.read_text())
            trades = d.get(field, [])
            if not trades:
                continue
            valid = [(t["model_prob"], 1 if t["won"] else 0)
                     for t in trades
                     if "model_prob" in t and "won" in t]
            if len(valid) < 5:
                continue
            probs = [v[0] for v in valid]
            labels = [v[1] for v in valid]
            b = brier(probs, labels)
            return float(b), str(path.name), len(valid)
        except (OSError, json.JSONDecodeError, KeyError, TypeError):
            continue
    return None, "not_found", 0


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
    p.add_argument("--compute", action="store_true",
                   help="Compute Brier directly from trade records (model_prob+won)")
    p.add_argument("--baseline-cv", action="store_true",
                   help="Force old 5-fold LogReg CV mode on holdout.json (CONSTANT — only use for regression testing)")
    args = p.parse_args()

    start = time.time()

    # ── Compare mode: score two predictions files ──────────────────────────
    if args.before and args.after:
        holdout = load_holdout()
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

    # ── Predictions score mode ─────────────────────────────────────────────
    if args.predictions:
        holdout = load_holdout()
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

    # ── Direct trade-record compute mode ──────────────────────────────────
    if args.compute:
        b, source, n = compute_brier_from_trades()
        if b is None:
            print("[proxy] no trade records available for compute mode", file=sys.stderr)
            sys.exit(2)
        elapsed = time.time() - start
        result = {
            "mode": "compute",
            "brier": round(b, 6),
            "source": source,
            "n_games": n,
            "elapsed_sec": round(elapsed, 3),
        }
        if args.json:
            print(json.dumps(result))
        else:
            print(f"[proxy] compute brier={b:.5f} (n={n}, source={source}, {elapsed:.2f}s)")
        return 0

    # ── Legacy baseline-cv mode (explicit flag) ────────────────────────────
    if args.baseline_cv:
        holdout = load_holdout()
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
            "warning": "CONSTANT: this value is cached by holdout hash and never changes between council iterations. Use default (live) mode instead.",
        }
        if args.json:
            print(json.dumps(result))
        else:
            print(f"[proxy] baseline 5-fold CV LogReg brier={brier_cv:.5f} "
                  f"(n={holdout['n_games']}, {elapsed:.2f}s, WARNING: constant)")
        return 0

    # ── DEFAULT: Live mode — read real backtest data ───────────────────────
    # This replaces the old baseline_cv default. Reads the freshest real Brier
    # from backtest files updated every 4h. NOT a constant function — the value
    # changes as the fleet evolves, enabling real keep/revert gating.
    #
    # Fallback chain:
    #   backtest-latest.json → full-season-backtest.json → karpathy-best-config
    #   → backtest-results.json → holdout LogReg CV (constant fallback)
    b_live, source, meta = read_live_brier()

    if b_live is not None:
        elapsed = time.time() - start
        result = {
            "mode": "live",
            "brier": round(b_live, 6),
            "source": source,
            "elapsed_sec": round(elapsed, 3),
            **meta,
        }
        if args.json:
            print(json.dumps(result))
        else:
            print(f"[proxy] live brier={b_live:.5f} (source={source}, {elapsed:.2f}s)")
        return 0

    # Last-resort fallback: holdout LogReg CV (still constant but at least
    # returns something rather than crashing when no backtest files exist).
    if not HOLDOUT_PATH.exists():
        print("[proxy] ERROR: no live data and no holdout.json — cannot compute Brier",
              file=sys.stderr)
        sys.exit(2)

    holdout = load_holdout()
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
        "mode": "live_fallback_cv",
        "brier": round(brier_cv, 6),
        "source": "holdout_logreg_cv",
        "n_games": holdout["n_games"],
        "elapsed_sec": round(elapsed, 3),
        "cached": from_cache,
        "holdout_hash": h,
        "warning": "FALLBACK: no live backtest data found. Value is constant until backtest files appear.",
    }
    if args.json:
        print(json.dumps(result))
    else:
        print(f"[proxy] fallback CV brier={brier_cv:.5f} "
              f"(WARNING: constant, no live data found, {elapsed:.2f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
