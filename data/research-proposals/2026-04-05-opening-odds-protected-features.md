# Research Proposal: Opening-Line Odds as Protected GA Features

**Date:** 2026-04-05  
**Cycle:** 64  
**Source:** WebSearch — MDPI Information 2026, Scientific Reports 2025, sports-ai.dev  
**Status:** proposed  
**Priority:** HIGH — targets 0.00322 Brier gap to checkpoint  

---

## Problem

Current best fleet Brier: 0.22159 (S15). Checkpoint threshold: 0.21837. Gap: 0.00322.

The GA feature selection treats all 3,285 candidates equally — including betting market features that encode aggregate market intelligence about injuries, roster moves, and travel.

## Research Findings

### Finding 1: Betting Market Signals as Protected Features (MDPI 2026)

**Source:** "Uncertainty-Aware Machine Learning for NBA Forecasting in Digital Betting Markets" (MDPI Information, Jan 2026)

The MDPI 2026 paper achieved AUC = 0.95 (vs 0.76 for market-only variants) using a fused model that includes bookmaker-derived signals as *input features*, not just for evaluation.

**Key implementation insight:** Using OPENING LINE odds (not closing line) avoids lookahead bias. Closing line already incorporates sharp money that correlates with the target.

**Proposed features to protect:**
```python
PROTECTED_MARKET_FEATURES = [
    "implied_prob_home_open",     # Opening line home implied probability
    "implied_prob_away_open",     # Opening line away implied probability  
    "spread_open",                # Opening point spread
    "total_open",                 # Opening over/under
    "overround_open",             # Opening vig (market confidence indicator)
    "line_movement_home",         # Open→close movement (sharp money signal)
    "line_movement_spread",       # Spread movement open→close
]
```

**Why protect these?** The GA can currently exclude market features to reduce model complexity. But these features are orthogonal to the model's own signal (confirmed by market-only variant achieving flat ROI). Protecting them ensures they're always in the population.

### Finding 2: Calibration Selection Per Model (cmunch1 / sports-ai.dev)

For gradient boosting (XGBoost, CatBoost) — the overconfident model problem:
- Isotonic regression was empirically tested and **hurts** Brier by +0.003 to +0.007 (already documented in app.py line 1316)
- **lr_platt** (already implemented) is the correct approach: fit base model → apply Platt on temporal hold-out
- Key finding: ensure calibration method is **selected per model type** in the GA
  - XGBoost → prefer lr_platt (empirically validated)
  - CatBoost → prefer lr_platt or none (already well-calibrated)
  - ExtraTrees → prefer none or beta (less overconfident)

**Actionable change:** Update calibration weights per model type in `init_individual()`:
```python
if hp.get("model_type") in ("xgboost", "xgboost_brier"):
    cal_weights = [5, 15, 20, 20, 15, 25]   # boost lr_platt for XGBoost
elif hp.get("model_type") == "catboost":
    cal_weights = [40, 10, 15, 15, 10, 10]   # more "none" for CatBoost (already calibrated)
else:  # extra_trees, random_forest, lightgbm
    cal_weights = [25, 15, 25, 20, 10, 5]    # default
```

### Finding 3: Stacked Ensemble with MLP Meta-Learner (Scientific Reports 2025)

**Source:** "Stacked ensemble model for NBA game outcome prediction analysis" (PMC12357926, 2025)

Using MLP (2 hidden layers, 50 neurons each) as meta-learner outperformed logistic regression meta-learner, achieving 83.27% accuracy and AUC = 0.9213.

**For predict_today.py:** Currently aggregates island predictions via rank-based fusion. A trained MLP meta-learner stacking the 6 island probability outputs could improve Brier by an estimated 0.001-0.003.

**Implementation plan:**
1. Collect island predictions for last 500 games (from Supabase `nba_experiments`)
2. Train MLP(50, 50) meta-learner on island raw probabilities → actual outcome
3. Apply at predict_today.py inference time

**Blocker:** Requires Supabase predictions data. Check if `nba_experiments` has enough historical probability outputs.

### Finding 4: Directional Travel Features (STATUS: Already Implemented)

The 25,000-game study finding (east→west = 63.5% win, west→east = 55.0%) is already addressed in the engine:
- `timezone_circadian_impact` (Cat feature, line 944)
- `circadian_disruption` (rolling, line 1104)
- `venue_travel_direction` (line 1271)

**Verdict:** No action needed — directional travel already in feature pool.

---

## Recommended Actions (Prioritized)

| Priority | Action | Files | Estimated Brier Impact |
|----------|--------|-------|----------------------|
| 1 | Protect 5-7 opening-line market features in GA (add `PROTECTED_FEATURES` set, never exclude in crossover/mutation) | hf-space/app.py | −0.001 to −0.003 |
| 2 | Model-type-specific calibration weights in `init_individual()` | hf-space/app.py | −0.0005 to −0.001 |
| 3 | MLP meta-learner in predict_today.py (requires historical data audit) | predict_today.py | −0.001 to −0.003 |

**Next step for priority 1:** Check which market features from odds_market.py are currently in the 3,285-candidate pool, identify their feature name prefixes, and add them to a `PROTECTED_FEATURES` frozenset in init/mutate/crossover.

### Finding 5: Four Factors Differentials — Bench + Clutch Splits (NBAstuffer / PMC XGBoost+SHAP 2025)

SHAP analyses across 2025-2026 literature consistently surface differential Four Factors over 20-game windows as top features. Two underused high-value splits are **bench net rating differential** and **clutch net rating differential** (last 5 mins within 5 pts).

**Status check needed:** Verify whether `bench_net_rating_diff` and `clutch_net_rating_diff` are in the current 3,285-candidate pool. If not, add them to the engine.

**Implementation:**
```python
# In features/engine.py — add to existing team stats categories
"bench_net_rating_diff",        # Second-unit quality differential (starters excl.)
"bench_net_rating_diff_r10",    # 10-game rolling
"clutch_net_rating_diff",       # ±5pts last 5min net rating differential  
"clutch_net_rating_diff_r10",
"clutch_fg_pct_diff",           # Clutch FG% differential
```

Expected Brier impact: −0.0005 to −0.001 (moderate, not transformative — worth adding to pool).

---

## Recommended Actions (Prioritized)

| Priority | Action | Files | Estimated Brier Impact |
|----------|--------|-------|----------------------|
| 1 | Protect 5-7 opening-line market features in GA (add `PROTECTED_FEATURES` set, never exclude in crossover/mutation) | hf-space/app.py | −0.001 to −0.003 |
| 2 | Model-type-specific calibration weights in `init_individual()` | hf-space/app.py | −0.0005 to −0.001 |
| 3 | Check/add bench_net_rating_diff + clutch_net_rating_diff to feature pool | features/engine.py | −0.0005 to −0.001 |
| 4 | MLP meta-learner in predict_today.py (requires historical data audit) | predict_today.py | −0.001 to −0.003 |

**Next step for priority 1:** Check which market features from odds_market.py are currently in the 3,285-candidate pool, identify their feature name prefixes, and add them to a `PROTECTED_FEATURES` frozenset in init/mutate/crossover.

---

## Notes

- Isotonic calibration: empirically shown to hurt Brier in this system (+0.003 to +0.007) — do NOT add
- Temperature scaling: not tested, could be tried but likely redundant given lr_platt
- All circadian/directional travel features already implemented — no gap there
- MLP meta-learner: high potential but requires Supabase historical prediction data audit first
