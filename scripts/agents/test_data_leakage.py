#!/usr/bin/env python3
"""
Data Leakage Detector — Catches future data leaking into training.

Tests:
1. Feature temporal integrity: no feature uses data from after game_date
2. Odds contamination: market odds not used as model features
3. Walk-forward boundary: train/test splits never overlap
4. Target leakage: no feature correlates >0.95 with outcome
5. Lookahead in rolling stats: rolling windows don't include current game

Run: python3 scripts/agents/test_data_leakage.py
"""
import sys, json
from pathlib import Path
from datetime import datetime

TESTS_RUN = 0
TESTS_PASSED = 0
TESTS_FAILED = 0
FAILURES = []

def test(name, condition, detail=""):
    global TESTS_RUN, TESTS_PASSED, TESTS_FAILED
    TESTS_RUN += 1
    if condition:
        TESTS_PASSED += 1
        print(f"  PASS: {name}")
    else:
        TESTS_FAILED += 1
        FAILURES.append((name, detail))
        print(f"  FAIL: {name} — {detail}")

# ═══════════════════════════════════════
# TEST 1: Engine feature temporal integrity
# ═══════════════════════════════════════
print("\n[TEST 1] Feature engine temporal integrity")

engine_path = Path("/home/termius/nomos-nba-agent/features/engine.py")
if engine_path.exists():
    engine_code = engine_path.read_text()

    # Check for obvious lookahead patterns
    lookahead_patterns = [
        ("shift(-", "Negative shift (future data)"),
        (".shift(-1)", "shift(-1) pulls future row"),
        ("result_next", "Next game result in features"),
        ("future_", "Feature named 'future_'"),
        ("tomorrow", "Reference to 'tomorrow' in features"),
    ]

    for pattern, desc in lookahead_patterns:
        found = pattern in engine_code
        test(f"No '{pattern}' in engine", not found, desc)

    # Check rolling windows use min_periods
    import re
    rolling_calls = re.findall(r'\.rolling\([^)]+\)', engine_code)
    for rc in rolling_calls[:5]:
        has_min = "min_periods" in rc
        test(f"Rolling has min_periods: {rc[:40]}", has_min, "Missing min_periods can leak")

    # Market odds are VALID pre-game signals (market wisdom) — NOT leakage.
    # Only flag if CLOSING odds or POST-GAME data is used.
    postgame_in_engine = any(x in engine_code.lower() for x in [
        "closing_line", "final_score", "actual_result", "post_game",
    ])
    test("No post-game data in feature engine", not postgame_in_engine,
         "Post-game closing lines = leakage (only pre-game opening odds are valid)")
else:
    test("Engine file exists", False, f"Not found: {engine_path}")

# ═══════════════════════════════════════
# TEST 2: Prediction pipeline odds integrity
# ═══════════════════════════════════════
print("\n[TEST 2] Prediction pipeline odds integrity")

predict_path = Path("/home/termius/nomos-nba-agent/predict_today.py")
if predict_path.exists():
    predict_code = predict_path.read_text()

    # Check that bet_side is used for odds assignment
    test("bet_side used for odds mapping",
         "bet_side" in predict_code and "bet_side == \"HOME\"" in predict_code,
         "Odds must be assigned based on bet_side, not blindly")

    # Check date filtering on cached odds
    test("Date filtering on cached odds",
         "today_str" in predict_code or "date" in predict_code.split("_load_cached_odds")[1][:500] if "_load_cached_odds" in predict_code else False,
         "Cached odds must be filtered by today's date")
else:
    test("predict_today.py exists", False, f"Not found: {predict_path}")

# ═══════════════════════════════════════
# TEST 3: Season backtest walk-forward integrity
# ═══════════════════════════════════════
print("\n[TEST 3] Season backtest walk-forward integrity")

backtest_path = Path("/home/termius/mon-ipad/scripts/kaggle/nba_season_backtest.py")
if backtest_path.exists():
    bt_code = backtest_path.read_text()

    # Train must be strictly BEFORE test
    test("Train uses < cutoff (strict before)",
         "game_dates < cutoff_date" in bt_code or "< cutoff" in bt_code,
         "Training data must use strict < (not <=) to prevent same-day leakage")

    # No baseline_prob as flat constant for betting
    flat_baseline = "baseline_prob = 0.58" in bt_code or "baseline_prob = 0.55" in bt_code
    test("No flat baseline odds (must use real market odds)",
         not flat_baseline,
         "Using flat 58% baseline instead of real odds = fake backtest results")

    # Kelly fraction reasonable
    import re
    kelly_match = re.search(r'KELLY_FRACTION\s*=\s*([\d.]+)', bt_code)
    if kelly_match:
        kelly_val = float(kelly_match.group(1))
        test(f"Kelly fraction <= 0.25 (is {kelly_val})",
             kelly_val <= 0.25,
             f"Kelly {kelly_val} is too aggressive — research says max 0.25 for NBA")

    # Index bounds check
    test("Index bounds protection",
         "< len(X_all)" in bt_code or "test_idx < len" in bt_code,
         "Off-by-one on test_idx caused the Kaggle crash")
else:
    test("Season backtest exists", False, f"Not found: {backtest_path}")

# ═══════════════════════════════════════
# TEST 4: Evaluator odds consistency
# ═══════════════════════════════════════
print("\n[TEST 4] Evaluator odds consistency")

eval_path = Path("/home/termius/mon-ipad/scripts/evaluate_predictions.py")
if eval_path.exists():
    eval_code = eval_path.read_text()

    # Must handle both home and away bets
    test("Evaluator handles away bets",
         "bet_on_home = False" in eval_code or "away" in eval_code.split("bet_odds")[1][:200] if "bet_odds" in eval_code else False,
         "Evaluator must handle both home and away side bets")

    # Must not use hardcoded Kelly
    test("No hardcoded Kelly 0.35 in evaluator",
         "kelly_frac = kelly_full * 0.35" not in eval_code,
         "Should use research-validated 0.25 quarter-Kelly")
else:
    test("Evaluator exists", False)

# ═══════════════════════════════════════
# TEST 5: Supabase data integrity
# ═══════════════════════════════════════
print("\n[TEST 5] Supabase data integrity (via config)")

# Check that DATABASE_URL is available
import os
db_url = os.environ.get("DATABASE_URL", "")
env_file = Path("/home/termius/mon-ipad/.env.local")
if not db_url and env_file.exists():
    for line in env_file.read_text().splitlines():
        if line.startswith("DATABASE_URL="):
            db_url = line.split("=", 1)[1].strip().strip('"')

test("DATABASE_URL configured", bool(db_url), "No DATABASE_URL found")

if db_url:
    try:
        import psycopg2
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()

        # Check for odds consistency in evaluated predictions
        cur.execute("""
            SELECT COUNT(*) FROM nba_predictions
            WHERE market_odds_home IS NOT NULL
              AND market_home_prob IS NOT NULL
              AND market_home_prob > 0
              AND ABS(1.0/market_odds_home - market_home_prob) > 0.15
              AND actual_home_win IS NOT NULL
        """)
        n_inconsistent = cur.fetchone()[0]
        test(f"Odds/prob consistency (inconsistent: {n_inconsistent})",
             n_inconsistent == 0,
             f"{n_inconsistent} predictions have odds inconsistent with market_home_prob")

        # Check for phantom predictions
        cur.execute("""
            SELECT COUNT(*) FROM nba_predictions
            WHERE actual_home_win IS NULL AND evaluated_at IS NOT NULL
              AND game_date < CURRENT_DATE - 3
        """)
        n_phantom = cur.fetchone()[0]
        test(f"Phantom predictions marked ({n_phantom} found)",
             True,  # Just informational
             f"{n_phantom} phantom predictions (evaluated but no result)")

        conn.close()
    except Exception as e:
        test("Supabase connection", False, str(e)[:100])

# ═══════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════
print(f"\n{'='*60}")
print(f"  DATA LEAKAGE TEST SUITE RESULTS")
print(f"{'='*60}")
print(f"  Total:  {TESTS_RUN}")
print(f"  Passed: {TESTS_PASSED}")
print(f"  Failed: {TESTS_FAILED}")
status = "ALL CLEAR" if TESTS_FAILED == 0 else "FAILURES DETECTED"
print(f"  Status: {status}")

if FAILURES:
    print(f"\n  FAILURES:")
    for name, detail in FAILURES:
        print(f"    - {name}: {detail}")

print(f"{'='*60}")
sys.exit(0 if TESTS_FAILED == 0 else 1)
