# SOTA Research Proposal — fire-81 (2026-05-11T02h)

## Sources
1. **Nature Scientific Reports 2025** — Stacked ensemble model for NBA game outcome prediction
   https://www.nature.com/articles/s41598-025-13657-1
2. **arXiv 2508.02725** — Forecasting NCAA Basketball Outcomes with Deep Learning: LSTM vs Transformer
   https://arxiv.org/html/2508.02725v1
3. **MDPI 2079-3197/13/10/230** — Machine Learning for Basketball Game Outcomes: NBA and WNBA Leagues
   CNN model Brier 0.221
4. **MDPI 2078-2489/17/1/56** — Uncertainty-Aware Machine Learning for NBA Forecasting (MC-dropout, Brier 0.199)
   (previously noted fire-78, included for reference)

## Key Findings

### 1. Stacked Ensemble with LR Meta-Learner — HIGHEST PRIORITY (CPU-safe)
**Source:** Scientific Reports 2025
**Finding:** Stacked ensemble (NB + AdaBoost + MLP + KNN + XGBoost + DT + LR) with a meta-learner
outperforms any single model for NBA outcome prediction. Meta-learner learns how to combine base model
confidence signals.
**Our gap:** Islands currently run single-model GA (XGBoost / extra_trees / LightGBM / RF). No stacking.
**Proposal:** Add `stacked_ensemble` as a new model_type in island app.py:
- Level-0 base: [xgboost, extra_trees, lightgbm] (all already available)
- Level-1 meta: LogisticRegression(cv=5) — CPU-safe, fast, well-calibrated
- MAX_FEATURES=200 applies to the feature selection feeding level-0
- Use sklearn.ensemble.StackingClassifier
**Expected gain:** 0.5–1.0% Brier improvement (literature baseline ~0.22 → ~0.219).
**CPU-safe:** YES — pure sklearn stack, no GPU needed.
**Implementation target:** S14 first (gen=1283, healthy, catboost already competitive at gen-front).
**After validation:** propagate to S13, S18, S22, P1, P4, P7.

### 2. LSTM / Transformer Sequential Game Features — MEDIUM PRIORITY (GPU required)
**Source:** arXiv 2508.02725
**Finding:** Transformers outperform LSTM for longer basketball game sequences; both significantly outperform
tree models on temporal/sequential features. Pre-training on college basketball data transfers to NBA.
**Our gap:** All islands treat each game as independent. Zero temporal/sequential modeling.
**Proposal:** New GPU burst script `scripts/gpu-burst/transformer-seq-nba.py`:
- Input: rolling 15-game sequence per team (home + away separately)
- Architecture: 2-layer Transformer encoder, d_model=64, 4 heads
- Output: 128-dim embedding per game-pair, precomputed and stored as extra features
- These embeddings fed as additional columns to XGBoost in island GA
**Expected gain:** -0.005 to -0.010 Brier if sequential momentum patterns matter.
**CPU-safe:** NO — training on GPU only (Modal A10G or Lightning.ai T4). Inference embeddings pre-computed.
**Implementation target:** `scripts/gpu-burst/transformer-seq-nba.py` (new).

### 3. CNN Feature Maps — LOW PRIORITY (GPU required)
**Source:** MDPI 2079-3197/13/10/230
**Finding:** CNN treating team stats as 2D spatial feature maps achieved Brier 0.221 for NBA/WNBA.
Interpretation: feature interactions captured spatially.
**Our gap:** No 2D feature representation.
**Proposal:** Reshape 186-feature vector into 14×14 grid (by feature category), train lightweight CNN.
**Expected gain:** Competitive with tree models (Brier ~0.221), not better than our 0.22012 unless combined.
**CPU-safe:** NO.
**Implementation target:** GPU burst Colab notebook (low priority — not better than current best standalone).

## Recommended Action Order

| Priority | Action | CPU-safe | Est. gain | Target |
|----------|--------|----------|-----------|--------|
| 1 | Add `stacked_ensemble` model_type (LR meta on XGB+ET+LGBM) | YES | ~0.001 Brier | S14 → propagate |
| 2 | Combine with `logistic_regression` standalone (already queued vm-add-logistic-regression-model-pool) | YES | 0.199 SOTA | S14 |
| 3 | Transformer sequential features (GPU burst) | NO (GPU) | ~0.005–0.010 | new script |
| 4 | CNN feature maps | NO (GPU) | marginal | Colab |

## Cross-Project Port
These findings apply equally to political islands (P7 worst at 0.25412 with lightgbm):
- Add `stacked_ensemble` to P7 simultaneously with S14 trial
- Political domain: stacking may yield larger gains because features are more heterogeneous

## VM Action Items
- [ ] Add `stacked_ensemble` to S14 app.py MODEL_TYPES (`sklearn.ensemble.StackingClassifier`)
- [ ] Add to P7 app.py simultaneously (cross-project Rotation C)
- [ ] Write `scripts/gpu-burst/transformer-seq-nba.py` for sequence embeddings
- [ ] After S14 validates: propagate to S13, S18, S22, P1, P4
