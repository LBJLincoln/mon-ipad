# Research Proposal: LSTM + Brier Loss for NBA Prediction

**Date:** 2026-04-18  
**Cycle:** Brain cycle-12  
**Source:** WebSearch NBA SOTA 2026

## SOTA Findings

| Model | Brier Score | Notes |
|-------|-------------|-------|
| LSTM + Brier loss | **0.1589** | MDPI uncertainty-aware paper (2025-2026) |
| CNN | 0.221 | Comparative study |
| Transformer + BCE | Best AUC 0.8473 | Discriminative, not calibrated |
| Our fleet best (S14) | **0.22041** | CatBoost 200f, tree-based GA |

Gap to SOTA: ~0.062 Brier points (28% improvement possible).

## Key Techniques

1. **LSTM + Brier loss** — Sequential game data (rolling form) trained with Brier scoring rule directly instead of BCE. Provides calibrated probabilities.
2. **Monte Carlo Dropout** — Uncertainty quantification at inference. Allows confidence intervals per prediction.
3. **Rolling-form features** — Last 10-game rolling averages replace static season stats.
4. **Shot-chart embeddings** — Spatial shot distribution as auxiliary features (requires box-score data).
5. **Isotonic calibration** — Post-hoc Platt/isotonic scaling on tree outputs (already in S20 island via 2604.07355).

## Recommendations for Fleet

### Immediate (tree islands, no GPU needed)
- **Port to S20 (isotonic_cpcv)**: Add isotonic recalibration layer on top of GA-evolved tree models. Expected: -0.002 to -0.005 Brier.
- **Port to Political P6/P8**: Logistic regression with Brier loss objective already available — switch from log-loss to Brier. P2's logistic model at 0.24949 may improve.

### Medium-term (ZeroGPU / Modal burst)
- Run LSTM + Brier loss on ZeroGPU H200 (6h free). Use rolling 10-game sequences as input.
- Compare against S14's 0.22041 as baseline. If better → new checkpoint.

### Long-term
- Add shot-chart spatial features to feature engine (v3.2). Estimated +20 new features.
- Transformer with Brier loss (replacing LSTM) for attention over game sequence.

## References
- [Uncertainty-Aware ML for NBA Forecasting](https://www.mdpi.com/2078-2489/17/1/56)
- [Stacked Ensemble for NBA](https://www.nature.com/articles/s41598-025-13657-1)
- [XGBoost + SHAP for NBA](https://pmc.ncbi.nlm.nih.gov/articles/PMC11265715/)
- [LSTM vs Transformer NCAA](https://arxiv.org/html/2508.02725v1)
