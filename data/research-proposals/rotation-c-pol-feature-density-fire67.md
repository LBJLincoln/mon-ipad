# Rotation C: POL Feature Density Reduction — NBA Cross-Port
**fire-67 | 2026-05-09T06h | Rotation C: Port NBA Techniques to Political**

## Observation

NBA fleet best S15 (brier=0.22012) selects **75 features from 3,377 candidates = 2.2% density**.
POL islands select **16–27% of their 272-feature pool** (45–72 features).

| Island | Features | Pool | Density | Best Brier | Sharpe |
|--------|----------|------|---------|------------|--------|
| S15 NBA (fleet best) | 75 | 3,377 | **2.2%** | 0.22012 | **9.21** |
| P1 | 72 | 272 | 26.5% | 0.2499 | — |
| P4 (fleet best) | 71 | 272 | 26.1% | 0.24904 | — |
| P5 | 58 | 272 | 21.3% | 0.24993 | 0.17 |
| P7 (weakest) | 45 | 272 | 16.5% | 0.25412 | — |

NBA Sharpe = 9.21 vs POL Sharpe = 0.17 — **53× gap** despite using same model families.

## Hypothesis

POL GA maintains too many features relative to pool size.
- With 272 features, selecting 45–72 means seeing 16–27% of all available signals.
- With correlated political features (polls, sentiment, incumbency), this inflates variance.
- NBA at 2.2% selection forces sparsity → reduces correlation noise → better calibration.

## SOTA Support

- **Springer IJ Data Sci 2025**: LightGBM/XGBoost SOTA for political prediction — 272 is NOT high-dim; aggressive pruning appropriate.
- **MDPI Electronics 12/21 2023**: Extra Trees Classifier leads for financial market prediction — excels with sparse, decorrelated feature sets.
- **XGBoost+SHAP (PMC 11265715)**: Top ~5% of features carry 80% signal — SHAP-guided pruning.

## Action Plan

**Target**: P7 (weakest, 16.5% density, brier=0.25412, lightgbm)
**Change**: Reduce MAX_FEATURES target from ~45 to **15–20 features** (5–8% of 272 pool)

**Methods** (in order of preference):
1. POST `/api/config` to `lbjlincoln-political-alpha-7.hf.space`:  
   `{"max_features_target": 18, "min_features": 10}`
2. VM: Patch space GA init config in app.py `_GA_CONFIG`
3. Observe next diversify event — check if random init with lower feature counts improves

**Expected Delta**: −0.002 Brier (conservative), Sharpe improvement
**Risk**: Low — P7 is weakest island; regression self-corrects in GA

## Blockers

- political_engine.py placeholder: **does NOT block** — feature density is a GA hyperparameter
- Extra_trees injection: still blocked until VM restores political_engine.py
- Data starvation (272f vs 3377f): primary ceiling; this addresses secondary overfitting

## Next Steps

After P7 confirmed: apply density reduction to P1/P2/P5 in subsequent cycles.

## Related

- fire-66 Rotation B: extra_trees S15 Pareto best 0.21841 — injection blocked by placeholder
- S15 /api/best confirmed fire-67: RF 75f, 3377 pool, brier=0.22012, ROI=32.42%, Sharpe=9.21
- fire-67 concrete improvement: this proposal + S14 stag=20 diversify alert added to VM work-queue
