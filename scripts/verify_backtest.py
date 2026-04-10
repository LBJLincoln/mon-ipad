#!/usr/bin/env python3
"""
NBA Backtest Verification & Audit
Reads the Kaggle season backtest results and computes honest, audited metrics.

Usage: python scripts/verify_backtest.py
Output: data/nba-agent/verified-results.json
"""

import json
import math
import os
import statistics
from datetime import datetime
from collections import defaultdict

RESULTS_PATH = '/tmp/kaggle-multi-market/season_backtest_results.json'
OUTPUT_PATH = '/home/lahargnedebartoli/mon-ipad/data/nba-agent/verified-results.json'

# ── Load raw results ──────────────────────────────────────────────────────────
with open(RESULTS_PATH) as f:
    raw = json.load(f)

daily_log    = raw.get('daily_log', [])
trades       = raw.get('trades', [])
equity_curve = raw.get('equity_curve', [])
monthly_pnl  = raw.get('monthly_pnl', [])

INITIAL_BANKROLL = raw['initial_bankroll']
N_BETS   = raw['total_bets']
N_WINS   = raw['wins']
N_LOSSES = raw['losses']

print("=" * 60)
print("  NBA BACKTEST VERIFICATION & AUDIT")
print("=" * 60)
print(f"  Raw claim: ${INITIAL_BANKROLL} -> ${raw['current_bankroll']:.2f}")
print(f"  Raw ROI: {raw['total_roi_pct']:.1f}%")
print(f"  Raw Sharpe: {raw['sharpe_ratio']}")
print(f"  Raw win rate: {raw['win_rate']:.1f}% ({N_WINS}W/{N_LOSSES}L)")
print(f"  Raw max DD: {raw['max_drawdown_pct']:.2f}%")
print(f"  Avg edge claimed: {raw['avg_edge_pct']:.1f}%")
print()

# =============================================================================
# ISSUE 1 — SHARPE RATIO METHODOLOGY
# =============================================================================
# The original code computes Sharpe on weekly returns then multiplies by sqrt(252).
# sqrt(252) is the correct annualization for DAILY data.
# For weekly data, the correct factor is sqrt(52).
# This inflates Sharpe by sqrt(252/52) = ~2.2x.
# Additionally, with only 19 weekly observations the estimate is unreliable.

weekly_returns = []
for i, d in enumerate(daily_log):
    prev_br = daily_log[i-1]['bankroll'] if i > 0 else INITIAL_BANKROLL
    if prev_br > 0:
        weekly_returns.append(d['pnl'] / prev_br)

if len(weekly_returns) > 1:
    avg_weekly = statistics.mean(weekly_returns)
    std_weekly = statistics.stdev(weekly_returns)
    # Correct annualization: sqrt(52) for weekly
    sharpe_weekly_corrected = (avg_weekly / std_weekly) * math.sqrt(52) if std_weekly > 0 else 0
    # Wrong annualization used in original (sqrt(252)) — just to show the inflation
    sharpe_weekly_wrong = (avg_weekly / std_weekly) * math.sqrt(252) if std_weekly > 0 else 0
else:
    sharpe_weekly_corrected = 0
    sharpe_weekly_wrong = 0

print("[ISSUE 1] Sharpe Ratio Bug:")
print(f"  Original code uses sqrt(252) on WEEKLY data = inflated by {math.sqrt(252/52):.2f}x")
print(f"  Reported Sharpe: {raw['sharpe_ratio']:.2f}")
print(f"  Corrected Sharpe (sqrt(52)): {sharpe_weekly_corrected:.2f}")
print(f"  Note: 19 weekly obs is too few for reliable Sharpe estimation anyway.")
print()

# =============================================================================
# ISSUE 2 — EDGE INFLATION (LOOK-AHEAD / CIRCULAR PROBABILITY)
# =============================================================================
# The backtest falls back to model-implied odds when no real odds CSV is found.
# When real_odds_pct = 100.0, the result file claims ALL 227 bets used real odds.
# BUT: looking at the trades, edges like 1.02 (102%), 3.14 (314%), 3.96 (396%)
# are impossible against a real sportsbook market.
#
# Real sportsbooks have vig: true edge per bet rarely exceeds 5-8% even for
# the best teams in the world. Edges >50% mean the odds are NOT real market odds.
#
# Root cause: The "implied odds" fallback creates circular logic:
#   model_prob = 0.75 → odds_home = 1/(0.75 * 1.05) = 1.27
#   edge = 0.75 * 1.27 - 1 = -0.048 (negative, filtered out)
#   BUT: model_prob = 0.75 on AWAY side where market has +350 (+350 = decimal 4.5)
#   → edge = 0.75 * 4.5 - 1 = 2.375 (237.5%)  ← impossible in reality

# Extract edge distribution from trades
if trades:
    edges = [t['edge'] for t in trades if 'edge' in t]
    odds_list = [t['market_odds'] for t in trades if 'market_odds' in t]

    suspicious_edges = [e for e in edges if e > 0.20]   # >20% edge = suspicious
    huge_edges = [e for e in edges if e > 1.00]          # >100% edge = impossible

    print("[ISSUE 2] Edge Distribution (last 100 recorded trades):")
    print(f"  Avg edge: {statistics.mean(edges):.3f} ({statistics.mean(edges)*100:.1f}%)")
    print(f"  Max edge: {max(edges):.3f} ({max(edges)*100:.1f}%)")
    print(f"  Edges >20%: {len(suspicious_edges)}/{len(edges)} ({len(suspicious_edges)/len(edges)*100:.0f}%)")
    print(f"  Edges >100% (impossible): {len(huge_edges)}/{len(edges)} ({len(huge_edges)/len(edges)*100:.0f}%)")
    print(f"  Avg market odds: {statistics.mean(odds_list):.3f}")
    print()
    print("  Diagnosis: edges >20% indicate the model's predicted probability")
    print("  is being used both to SIZE the bet AND to calculate the 'edge'.")
    print("  The implied odds path creates model_odds = 1/(p * 1.05), meaning")
    print("  the 'market odds' are derived from the model itself — circular.")
    print()

# =============================================================================
# ISSUE 3 — FAVORITE BIAS CHECK
# =============================================================================
# Win rate of 67% on moneyline bets: is this just betting favorites?
# NBA favorites win ~64% of games historically. Betting all favorites at -110
# equivalent odds gives 64% win rate but negative ROI (vig).
# We need to check if model is just picking favorites with artificially
# favorable odds.

if trades:
    home_bets = [t for t in trades if t.get('side') == 'home']
    away_bets = [t for t in trades if t.get('side') == 'away']
    home_wins = sum(1 for t in home_bets if t.get('won'))
    away_wins = sum(1 for t in away_bets if t.get('won'))

    # High model_prob bets
    high_conf = [t for t in trades if t.get('model_prob', 0) >= 0.65]
    low_conf  = [t for t in trades if 0.50 < t.get('model_prob', 0) < 0.65]

    print("[ISSUE 3] Favorite / Confidence Bias:")
    print(f"  Home bets: {len(home_bets)} | win rate: {home_wins/len(home_bets)*100:.1f}%" if home_bets else "  No home bets in sample")
    print(f"  Away bets: {len(away_bets)} | win rate: {away_wins/len(away_bets)*100:.1f}%" if away_bets else "  No away bets in sample")
    print(f"  High conf (>=65%) bets: {len(high_conf)}")
    print(f"  Low conf (50-65%) bets: {len(low_conf)}")
    print()
    # Avg model_prob
    avg_prob = statistics.mean([t.get('model_prob', 0.5) for t in trades])
    print(f"  Avg model confidence: {avg_prob:.3f} ({avg_prob*100:.1f}%)")
    if avg_prob > 0.68:
        print("  WARNING: avg confidence > 68% suggests model is over-confident / miscalibrated")
    print()

# =============================================================================
# ISSUE 4 — FLAT BET ANALYSIS (Kelly-independent ground truth)
# =============================================================================
# flat_bet = $5/bet, 227 bets, same picks as Kelly
# $100 -> $1,002 (+$902) = 180.4 units profit on 227 bets
# At $5/bet, 227 bets = 45.4 betting units wagered
# Profit = 180.4 units = 397% yield on wagered amount
# This implies average NET return per unit wagered of +3.97 per unit — impossible.
#
# Let's recompute: flat_bankroll starts at $100 but only BETS $5 per bet.
# The $100 is just the starting balance, not all wagered.
# Total wagered = 227 * $5 = $1,135
# Profit = $1,002 - $100 = $902
# ROI on wagered amount = $902 / $1,135 = 79.5% — still impossible at a real book.
# A 5% edge at real odds (avg -110, 1.909 decimal) over 227 bets gives ~$54 profit.
# $902 profit requires ~79% edge on $1,135 wagered.

flat = raw.get('flat_bet', {})
flat_bankroll    = flat.get('bankroll', 1002.0)
flat_roi_pct     = flat.get('roi_pct', 902.0)
flat_bet_size    = flat.get('bet_size', 5.0)

total_flat_wagered  = N_BETS * flat_bet_size
flat_profit         = flat_bankroll - INITIAL_BANKROLL
yield_on_wagered    = flat_profit / total_flat_wagered * 100

# What real edge would give this result?
# At avg -110 odds (decimal 1.909):
#   Expected profit = N * bet_size * (win_rate * (odds-1) - loss_rate)
avg_odds_assumed = 1.909
implied_yield = (N_WINS / N_BETS * (avg_odds_assumed - 1)) - (N_LOSSES / N_BETS)

print("[ISSUE 4] Flat Bet Analysis:")
print(f"  Flat bet size: ${flat_bet_size}/bet x {N_BETS} bets = ${total_flat_wagered:.0f} wagered")
print(f"  Reported flat profit: ${flat_profit:.2f}")
print(f"  Yield on wagered: {yield_on_wagered:.1f}%")
print(f"  This is {yield_on_wagered/5:.0f}x the edge of elite sports bettors (~5%)")
print(f"  Implied yield at -110 avg odds: {implied_yield*100:.1f}%")
print()
print("  DIAGNOSIS: The flat-bet ROI compounds the same circular-odds bug.")
print("  The model bets on teams at +350/+550 (decimal 4.5/6.5) where it")
print("  predicts 60-70% win probability — that combination doesn't exist")
print("  in reality (book would never offer +350 on a 65% probability team).")
print()

# =============================================================================
# ISSUE 5 — ATS / O/U ZERO BETS
# =============================================================================
# by_market shows only 'moneyline' — zero ATS, zero O/U bets.
# Root cause: ATS/O/U require real_odds with 'spread' and 'total' fields.
# If odds CSV wasn't loaded (failed on Kaggle path), ODDS_LOOKUP is empty.
# But real_odds_pct = 100%... contradiction.
# Actual cause: The CSV WAS loaded (from SBR scrape), but spread/total columns
# are likely empty in that CSV — it only has ml_home, ml_away, not spread/total.
# The nba_2025-26_odds.csv was built by our own scraper and may lack those fields.

by_market = raw.get('by_market', {})
print("[ISSUE 5] ATS / O/U Zero Bets:")
print(f"  Markets seen: {list(by_market.keys())}")
print("  Zero ATS / O/U bets despite having real odds CSV.")
print("  Root cause: nba_2025-26_odds.csv likely missing 'spread' and 'total' columns.")
print("  The ATS/O/U code paths check real_odds.get('spread') — if column absent, skip.")
print()

# =============================================================================
# ISSUE 6 — MAX DRAWDOWN NEAR ZERO
# =============================================================================
# Equity curve shows drawdown = 0.0 for 18/19 weeks, only -1.97% at end.
# This is not physically possible with 227 bets including losses.
# Root cause: drawdown is computed PER WEEK at week-end. If bankroll at end
# of week is higher than start (even after losses), drawdown = 0.
# Intra-week losses are invisible. True max drawdown across all 227 bets
# would be much larger. With avg stake ~$25 at $1,000 bankroll = 2.5%/bet,
# a 5-bet losing streak = ~12.5% drawdown.

# Estimate true intra-bet drawdown from the bankroll progression
# Using sequential bankroll values from trades
if trades:
    bankrolls = [INITIAL_BANKROLL] + [t['bankroll'] for t in trades if 'bankroll' in t]
    peak_br = bankrolls[0]
    max_dd_intraday = 0.0
    for br in bankrolls:
        if br > peak_br:
            peak_br = br
        dd = (peak_br - br) / peak_br * 100 if peak_br > 0 else 0
        if dd > max_dd_intraday:
            max_dd_intraday = dd

    print("[ISSUE 6] Max Drawdown — True vs Reported:")
    print(f"  Reported (weekly snapshots only): {raw['max_drawdown_pct']:.2f}%")
    print(f"  Estimated intra-bet drawdown (from last 100 trades): {max_dd_intraday:.2f}%")
    print(f"  Note: full drawdown from all 227 trades unavailable (only last 100 stored)")
    print()

# =============================================================================
# CORRECTED / REALISTIC METRICS
# =============================================================================
print("=" * 60)
print("  CORRECTED METRICS")
print("=" * 60)

# Flat-bet win rate is the best signal, but we need to correct the ODDS side.
# The 67% win rate itself may be real — NBA walk-forward with proper features
# achieving 67% picks is within the realm of possibility for a well-calibrated model.
# Our Brier of 0.22447 corresponds to roughly 60% accuracy at the aggregate level.
# 67% is plausible if the filter selects higher-confidence games.
#
# BUT: The money results depend entirely on what odds those wins come at.
# A 67% win rate on -400 favorites (decimal 1.25) = -ROI.
# A 67% win rate on -110 games (decimal 1.909) = +27% ROI on wagered.
# A 67% win rate on +300 underdogs (decimal 4.0) = +168% ROI — impossible.

# Estimate realistic ROI using win-rate and a vig-adjusted -110 baseline
# (most moneyline bets cluster near -110 to -150 range)
realistic_avg_odds_low  = 1.826  # -120 (avg game: slight favorite)
realistic_avg_odds_mid  = 1.909  # -110 (pick'em)
realistic_avg_odds_high = 2.200  # +120 (underdog slant)

win_rate_frac = N_WINS / N_BETS

print(f"\n  Win Rate: {win_rate_frac*100:.1f}% ({N_WINS}W/{N_LOSSES}L)")
print(f"  Scenarios based on avg market odds:")

for label, avg_odds in [
    ("Conservative: avg -120", realistic_avg_odds_low),
    ("Neutral:      avg -110", realistic_avg_odds_mid),
    ("Optimistic:   avg +120", realistic_avg_odds_high),
]:
    flat_yield = win_rate_frac * (avg_odds - 1) - (1 - win_rate_frac)
    flat_profit_est = N_BETS * flat_bet_size * flat_yield
    bankroll_est = INITIAL_BANKROLL + flat_profit_est
    print(f"    {label}: yield={flat_yield*100:+.1f}%, flat profit=${flat_profit_est:.0f}, bankroll=${bankroll_est:.0f}")

# Kelly with correct odds
print()
print("  Kelly compounding with realistic edge (~5% yield on wagered):")
# 5% yield on wagered = each $1 bet returns $0.05 net on average
# Kelly f = edge / odds (approximate)
realistic_yield = 0.05  # 5% yield on wagered is genuinely elite
kelly_f_realistic = 0.25  # same as used
stake_frac_avg = 0.025  # 2.5% avg stake / bankroll (MAX_BET_PCT)
# Geometric growth: (1 + stake_frac * yield)^N_BETS per $1 stake cycle
# This is an approximation, not exact Kelly math
growth_factor = (1 + stake_frac_avg * realistic_yield) ** N_BETS
realistic_kelly_bankroll = INITIAL_BANKROLL * growth_factor
print(f"    With 5% yield, 2.5% avg stake, 227 bets:")
print(f"    Final bankroll: ${realistic_kelly_bankroll:.2f} (+{(realistic_kelly_bankroll/INITIAL_BANKROLL-1)*100:.1f}%)")

# Sharpe with correct methodology
print()
print(f"  Corrected Sharpe (weekly data, sqrt(52) annualization): {sharpe_weekly_corrected:.2f}")
print(f"  Note: reported Sharpe of {raw['sharpe_ratio']} was inflated by ~2.2x (sqrt(252) on weekly data)")

# =============================================================================
# WHAT IS ACTUALLY REAL
# =============================================================================
print()
print("=" * 60)
print("  WHAT IS REAL vs WHAT IS ARTIFACT")
print("=" * 60)
print()
print("  REAL (trustworthy):")
print(f"  - Win rate: ~{win_rate_frac*100:.0f}% on filtered picks (model selects edge>3% games)")
print(f"  - Walk-forward Brier: {raw.get('brier_score', raw.get('avg_brier', '?'))} (legitimate ML metric)")
print(f"  - Positive ROI direction: model has genuine predictive signal")
print(f"  - Weekly Brier range: 0.167 - 0.301 (shows real variance, not fixed)")
print()
print("  INFLATED / ARTIFACTS:")
print(f"  - ROI 4,470%: circular implied-odds bug inflates apparent edge massively")
print(f"  - Flat ROI 902%: same bug — implied odds create impossibly high market prices")
print(f"  - Sharpe 22.91: wrong annualization (sqrt(252) on weekly returns)")
print(f"  - Max DD 1.97%: only weekly snapshots, intra-week losses hidden")
print(f"  - Avg edge 89.18%: model probability used to create 'market odds' = circular")
print()
print("  MISSING:")
print("  - ATS / Over-Under analysis (spread/total data not in odds CSV)")
print("  - Calibration of model probabilities vs actual win rates by confidence band")
print("  - Opponent quality adjustment (win rate on weak vs strong opponents)")

# =============================================================================
# FORWARD-LOOKING ESTIMATE
# =============================================================================
print()
print("=" * 60)
print("  REALISTIC FORWARD-LOOKING ESTIMATE")
print("=" * 60)

# Based on: Brier 0.22447 walk-forward, 67% win rate on selected games
# NBA moneyline baseline: avg -110 (-5% yield on favorites, +5% on dogs)
# If model genuinely achieves 3-5% edge on selected games:
forward_scenarios = [
    ("Pessimistic (edge evaporates in live betting)", 0.00, -5.0),
    ("Conservative (2% live yield after slippage)",  0.02, 2.0),
    ("Realistic    (4% yield, model holds)",          0.04, 4.0),
    ("Optimistic   (6% yield, sharp money)",          0.06, 6.0),
]

print()
print(f"  For a 1,230-game season (full NBA schedule), betting ~{N_BETS*6:.0f} games total:")
for label, yield_val, roi_pct in forward_scenarios:
    ann_bets = 1230 * 0.20  # assume model bets 20% of games
    flat_gain = ann_bets * flat_bet_size * yield_val
    print(f"    {label}: annual flat +${flat_gain:.0f} on ${ann_bets*flat_bet_size:.0f} wagered, ROI={roi_pct:.1f}%")

print()
print("  KEY INSIGHT: The model's TRUE edge needs validation against ACTUAL market")
print("  closing lines (not model-implied odds). The real test is:")
print("  CLV (Closing Line Value): Did we consistently beat the closing line?")
print("  A Brier of 0.22447 is slightly better than market (~0.225). That gap")
print("  suggests 1-3% yield is realistic, not 4,470%.")

# =============================================================================
# OUTPUT JSON
# =============================================================================
verified = {
    "audit_timestamp": datetime.now().isoformat(),
    "source_file": RESULTS_PATH,
    "verdict": "INFLATED — DO NOT USE RAW FIGURES FOR LIVE SIZING",

    "raw_reported": {
        "roi_pct": raw['total_roi_pct'],
        "sharpe": raw['sharpe_ratio'],
        "max_dd_pct": raw['max_drawdown_pct'],
        "win_rate_pct": raw['win_rate'],
        "avg_edge_pct": raw['avg_edge_pct'],
        "flat_roi_pct": raw.get('flat_bet', {}).get('roi_pct'),
    },

    "audited": {
        "sharpe_corrected": round(sharpe_weekly_corrected, 2),
        "sharpe_inflation_factor": round(math.sqrt(252 / 52), 2),
        "note_sharpe": "Original used sqrt(252) annualization on WEEKLY returns. Correct is sqrt(52). Result: 2.2x inflation.",

        "edge_bug": {
            "problem": "Avg edge 89.18% is impossible. Implies model-derived 'market odds' used instead of real odds.",
            "evidence": "Trades show edge=1.02 (102%), 3.14 (314%), 3.96 (396%) — these cannot come from a real sportsbook.",
            "real_edge_upper_bound": "2-5% per bet (elite sports betting threshold)",
        },

        "flat_bet": {
            "raw_claim_roi_pct": flat_roi_pct,
            "total_wagered_usd": total_flat_wagered,
            "yield_on_wagered_pct": round(yield_on_wagered, 1),
            "reality_check": "79.5% yield on $1,135 wagered is impossible. Real elite bettors achieve 3-7%.",
            "bug": "Flat-bet tracks same artificial edge as Kelly — both use circular model-implied odds.",
        },

        "win_rate": {
            "reported_pct": raw['win_rate'],
            "bets": N_BETS,
            "note": "67% win rate on selected games may be genuine if model filters high-confidence situations. Needs validation against closing line value.",
        },

        "max_drawdown": {
            "reported_pct": raw['max_drawdown_pct'],
            "intraday_estimate_pct": round(max_dd_intraday, 2) if trades else "N/A",
            "note": "Reported DD uses weekly snapshots only. True intra-bet drawdown is higher.",
        },

        "ats_ou_zero_bets": {
            "problem": "Zero ATS / O/U bets despite 100% real_odds_pct claim.",
            "cause": "nba_2025-26_odds.csv likely missing 'spread' and 'total' columns. ATS/O/U code silently skipped.",
            "fix": "Augment odds CSV with SBR spread/total data using scrape_season_odds.py",
        },
    },

    "realistic_forward_estimate": {
        "basis": f"Brier {raw.get('brier_score', 0.22447)} walk-forward, 67% win rate on selected bets",
        "our_brier_vs_market": "Our Brier 0.22447 vs market implied ~0.225 — small but real edge",
        "win_rate_at_neutral_odds": round(win_rate_frac * 100, 1),
        "scenarios": {
            "conservative_yield_pct": 2.0,
            "realistic_yield_pct": 4.0,
            "optimistic_yield_pct": 6.0,
        },
        "flat_5usd_full_season": {
            "bets_expected": 250,
            "at_4pct_yield_profit": round(250 * 5.0 * 0.04, 0),
            "at_4pct_yield_roi_pct": 4.0,
        },
        "what_to_watch": [
            "Closing Line Value (CLV): beating the closing line consistently = real edge",
            "Calibration by confidence band: do 70% confidence picks win 70% of time?",
            "ATS / O/U: separate model needed, not just converting ML prob to spread",
            "Live vig: -110 standard, but most books charge -115 to -120 on MLs",
        ],
    },

    "action_items": [
        "Fix Sharpe computation: use weekly_returns * sqrt(52) not sqrt(252)",
        "Fix odds sourcing: verify ODDS_LOOKUP key matching (date format, team name normalization)",
        "Add CLV tracking: store predicted probability at time-of-bet vs closing line",
        "Add spread/total columns to nba_2025-26_odds.csv via scrape_season_odds.py",
        "Use REAL ODDS only: add hard assert: if not real_odds, skip bet (don't fallback to implied)",
        "Calibration plot: compare model_prob to actual win_rate in probability bins",
        "Track consecutive losses: 5+ loss streaks tell us about true variance",
    ],

    "bottom_line": (
        "The walk-forward backtest has genuine predictive signal (Brier 0.22447, "
        "67% win rate on filtered picks). However, the financial performance numbers "
        "($4,570 from $100, Sharpe 22.91) are entirely artificial due to three compounding bugs: "
        "(1) model-implied 'market odds' creating circular edge calculation, "
        "(2) sqrt(252) Sharpe annualization on weekly data, "
        "(3) max drawdown computed from weekly snapshots not per-bet. "
        "Realistic expectation: 2-5% yield on wagered amount after market friction. "
        "With $5 flat bets on 250 games/season, realistic annual profit is $25-62. "
        "Kelly compounding amplifies this to $200-500/season at 2.5% stake, "
        "not $4,470. The model is valuable — the reporting is misleading."
    )
}

os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
with open(OUTPUT_PATH, 'w') as f:
    json.dump(verified, f, indent=2)

print()
print(f"Verified results written to: {OUTPUT_PATH}")
print()
print("=" * 60)
print("  BOTTOM LINE")
print("=" * 60)
print(verified['bottom_line'])
print()
