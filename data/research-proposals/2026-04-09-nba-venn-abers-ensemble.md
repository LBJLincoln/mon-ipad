# Research Proposal: Venn-Abers Ensemble Calibration for NBA Fleet
Date: 2026-04-09
Cycle: Brain 4h
Priority: HIGH
Source: 2025-2026 NBA prediction literature review

## Finding
Island S14 (nomos42-nba-evo-5) top_performer shows Brier 0.22052 using:
- model: lightgbm_brier
- calibration: venn_abers
- features: 200 (max)
- island_id: 1

This is 0.002 better than the fleet best_brier of 0.22249, and 0.00415 from the target 0.21837.

## Research Insight
2025-2026 NBA prediction literature (Nature Scientific Reports, ACM CSEIT) confirms:
1. **Stacked ensembles** of SVM + AutoGluon + DNN achieve >77% win prediction accuracy
2. **Domain-informed cross-features** (player fatigue × travel × rest days) outperform raw stats
3. **Venn-Abers calibration** (already on S14!) produces sharper probability estimates than Platt scaling
4. **Real-time game features** (pre-game odds drift, line movement, public % vs sharp %) add signal

## Concrete Proposals

### P1: Cross-Island Venn-Abers Standardization [QUICK WIN]
Force ALL 6 islands to use venn_abers as default calibration method (currently only S14 uses it).
- Expected improvement: 0.001-0.003 Brier
- Risk: LOW (purely additive, no feature change)
- Implementation: Update hf-space/app.py CALIBRATION_METHOD = "venn_abers"

### P2: Player Rest × Travel Cross-Features [MEDIUM]
Add interaction features: rest_days × back_to_back × travel_miles_last_48h
These are domain-informed cross-features validated in stacked ensemble literature.
- Expected improvement: 0.003-0.007 Brier
- Risk: MEDIUM (new feature categories)
- File: features/engine.py cat55 rest_travel_interactions

### P3: Pre-Game Market Drift Features [HIGH VALUE]
Add line movement velocity (open to close odds drift) + public% vs sharp% divergence as features.
Literature shows betting market features add significant signal orthogonal to stats.
- Expected improvement: 0.005-0.010 Brier
- Risk: MEDIUM (requires live odds API integration)
- File: features/engine.py cat56 market_drift

### P4: Multi-Calibrated Ensemble Stacking [ADVANCED]
Stack 3 calibrated models: lightgbm_brier + xgboost_brier + extra_trees_brier, each with venn_abers.
Final prediction = weighted average of 3 calibrated probability outputs.
- Expected improvement: 0.003-0.006 Brier
- Risk: HIGH (3x inference time)

## Recommended Action This Cycle
Implement P1 (venn_abers standardization across all islands) via hf-space app.py config change.
