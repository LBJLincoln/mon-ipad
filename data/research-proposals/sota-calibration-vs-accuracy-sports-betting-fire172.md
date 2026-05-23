# SOTA Research Proposal — Calibration vs Accuracy Model Selection for Sports Betting

**Source:** arXiv:2303.06021 — "Machine learning for sports betting: should model selection be based on accuracy or calibration?"
**Fire:** fire-172 (EVEN WebSearch, 2026-05-26T22h)
**Priority:** 34 (work-queue: vm-add-ece-pareto-objective)

## Summary

This paper directly addresses whether sports prediction models should be optimized for classification accuracy or calibration (Brier/log-loss). The answer is unambiguous: calibration-focused model selection consistently outperforms accuracy-based selection in betting contexts. This directly validates our GA's use of Brier score as primary fitness objective, but also reveals that *explicit calibration constraints* can push further beyond current Brier targets.

## Key Findings

- Calibration-optimized models outperform accuracy-optimized models on both ROI and Brier score in sports betting
- LightGBM and XGBoost produce systematically overconfident raw probabilities; they require explicit post-hoc calibration
- Isotonic regression and Platt scaling as post-processing layers measurably improve Brier scores for tree-based models
- Logistic regression (inherently well-calibrated) achieves Brier ~0.199 as tabular baseline on NBA games (MDPI 2079-3197 same search batch) — our LR models are confirmed active in S22 (fire-172 summary)
- ECE (Expected Calibration Error) and MCE (Maximum Calibration Error) as explicit secondary objectives force GA toward calibration-aware evolution

## Actionable Improvements for Nomos42

### 1. Add ECE as 4th Pareto Objective
- Current GA Pareto front: {brier, roi, sharpe}
- Enhancement: add ECE (Expected Calibration Error) as 4th objective, minimize simultaneously
- Rationale: prevents XGBoost/LightGBM from dominating Pareto via accuracy gains while remaining poorly calibrated
- Implementation: add `compute_ece(y_true, y_pred, n_bins=10)` in `evaluate_individual()` — use sklearn `calibration_curve`
- Target islands: S18 (LightGBM-38f composite top), S22 (RF-48f + ET-0.21877 candidate)
- Expected improvement: 0.002-0.004 Brier on LightGBM/XGBoost pareto candidates

### 2. Post-GA Calibration Layer (CalibratedClassifierCV)
- Apply `sklearn.calibration.CalibratedClassifierCV(method='isotonic', cv='prefit')` after GA selects best individual
- Cross-reference: pairs with Venn-Abers (arXiv:2605.03816, fire-158) and split conformal (arXiv:2510.07185, fire-168)
- Target: S18 LightGBM/XGBoost pareto candidates + S22 ET candidate (when confirmed)
- Implementation: add `calibrate_model()` wrapper in engine.py post-fit step
- Expected improvement: 0.001-0.003 Brier, guaranteed marginal coverage

### 3. LR Baseline Monitoring
- Paper and MDPI 2079-3197 baseline: LR achieves Brier ~0.199 on NBA — better than our current fleet best of 0.22012
- Key question: what features does that LR use? Rolling 5-game form + home/away is likely sufficient for a 0.199 LR
- Action: when S22/S18 LR candidates surface in pareto, record their feature sets specifically
- Fire-172 S22 summary confirms LR "maintaining stability" — extract LR pareto_best from /api/export when accessible

## Port to Political Alpha

- Add ECE as 4th Pareto objective to `political_engine.py`
- Same post-GA calibration layer for P1/P2/P5/P7 (xgboost_brier models)
- Expected: 0.001-0.003 Brier improvement on POL islands
- Blocked by: all POL islands sleeping; execute on wake

## Priority & Dependencies

- Work-queue item: `vm-add-ece-pareto-objective` (priority=34)
- After: `engine-parity-sync` (priority=40) — engine.py must be synced first between mon-ipad and nomos-nba-agent
- Combine with: `vm-add-venn-abers-calibration` (priority=32) in same implementation batch
- Combine with: `vm-add-split-conformal-calibration` (priority=33)

## References

- arXiv:2303.06021: "Machine learning for sports betting: should model selection be based on accuracy or calibration?"
- MDPI 2079-3197/13/10/230: "Machine Learning for Basketball Game Outcomes: NBA and WNBA Leagues" (LR Brier~0.199 baseline)
- arXiv:2605.03816 (Venn-Abers calibration, fire-158)
- arXiv:2510.07185 (split conformal calibration MAPIE, fire-168)
- MDPI/2078-2489/17/1/56 (MC dropout RNN Brier=0.206, fire-166)
