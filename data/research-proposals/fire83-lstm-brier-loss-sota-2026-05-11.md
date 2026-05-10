# SOTA Research Proposal — fire-83 (2026-05-11T10h)

## Key Finding: LSTM + Brier Loss = 0.1589 Brier Score

**Source:** arXiv:2508.02725 — "Forecasting NCAA Basketball Outcomes with Deep Learning: A Comparative Study of LSTM and Transformer Models"

**Metric:** LSTM trained with **Brier loss** achieves Brier score **0.1589** on NCAA basketball holdout.
Transformer with BCE achieves best AUC (0.8473) but worse calibration.

**Why this matters:** Our target is sub-0.20 Brier. LSTM+Brier-loss reaches **0.1589** — that is the path.

---

## Landscape Snapshot (confirmed 2026-05-11)

| Model | Brier | Source |
|-------|-------|--------|
| LSTM + Brier loss | **0.1589** | arXiv 2508.02725 (NCAA) |
| Logistic Regression + isotonic | 0.199 | MDPI comparative 2026 |
| XGBoost + isotonic | 0.202 | MDPI comparative 2026 |
| CNN | 0.221 | MDPI 2078-2489/17/1/56 |
| **Our fleet best (S15 RF)** | **0.22012** | fire-83 live |
| MC-dropout RNN | sub-0.22 | MDPI 2078-2489/17/1/56 |

---

## Actionable Paths

### Path 1 — GPU Burst: LSTM + Brier Loss (HIGH VALUE)

**Target:** Modal A10G or Lightning T4 (both active via GH Actions)

**Implementation:**
- Add `train_lstm_brier` function to `scripts/gpu-burst/modal-burst.py`
- Architecture: LSTM(hidden=128, layers=2) + dropout(0.3) + FC(1) + sigmoid
- Loss: MSE on probabilities (= Brier loss) instead of BCE
- Features: use current engine.py v3.1 feature set (~200 features, reduce to 50-100 via LASSO pre-filter)
- Temporal split: train ≤ 2023-24, val = 2024-25 early, test = 2024-25 late + 2025-26
- Key: Brier-loss training is the differentiator vs. standard cross-entropy

**Expected Brier:** 0.19-0.21 (gap vs. 0.22012 = ~10% improvement)

**Caveat:** NCAA vs. NBA — NBA has more parity, slightly harder. Expect 0.20-0.21 rather than 0.1589.

### Path 2 — CPU Islands: xgboost_brier + isotonic_temporal (IMMEDIATE)

**Current fleet best (S15) uses random_forest + isotonic.** The S18 xgboost_brier (0.22315) approaches S15 (0.22012).

**Hypothesis:** `xgboost_brier` + `isotonic_temporal` calibration (S15 method) combined could beat 0.22012.
- S15 uses RF + isotonic_temporal → 0.22012
- S18 uses xgboost_brier + sigmoid → 0.22315
- **Try xgboost_brier + isotonic_temporal** — this combo hasn't appeared in fleet best yet

**Action:** VM should ensure `xgboost_brier` + `isotonic_temporal` is a valid combination in island mutation space (check engine.py calibration logic).

### Path 3 — AutoGluon Ensemble (MEDIUM TERM)

**Finding:** AutoGluon achieved 0.7738 accuracy (2nd only to SVM 0.7749) in comparative study.

AutoGluon auto-selects: LightGBM, XGBoost, CatBoost, RF, NN, stacking — all in one sweep.

**Action:** Add AutoGluon experiment to GPU burst (Modal A10G):
```python
from autogluon.tabular import TabularPredictor
predictor = TabularPredictor(label='home_win', eval_metric='brier')
predictor.fit(train_data, presets='best_quality', time_limit=3600)
```
**Expected:** AutoGluon stack likely reaches 0.21-0.22 without manual tuning, potentially finding feature interactions missed by single-model GA.

---

## Recommendation Priority

1. **IMMEDIATE (VM):** Add `xgboost_brier + isotonic_temporal` as a valid calibration combination in island config. Cost: ~10 lines of code change in app.py calibration block.
2. **NEXT GPU BURST (Modal A10G):** Add LSTM + Brier loss experiment to modal-burst.py. Est. ~200 lines. Expected sub-0.21.
3. **MEDIUM TERM:** AutoGluon sweep on Modal A10G to benchmark ensemble ceiling.

---

## Notes on CPU Island Constraints

- Rule #8: No neural models on CPU islands → LSTM not deployable on HF Spaces
- LSTM results are GPU-burst only or Kaggle P100 targets
- CPU-optimal path remains: xgboost_brier + extra_trees + isotonic_temporal + stacked_ensemble (LR meta, non-neural)
- S15 post-hard-reset has stacking survivor dominance (see vm-remove-stacking-s15 work-queue item) — fix this before testing new calibration combos on S15

## Sources
- arXiv:2508.02725: https://arxiv.org/html/2508.02725v1
- MDPI MC-dropout RNN: https://www.mdpi.com/2078-2489/17/1/56
- Scientific Reports stacked ensemble: https://www.nature.com/articles/s41598-025-13657-1
- MDPI comparative (LR 0.199, XGB 0.202): https://www.mdpi.com/2079-3197/13/10/230
