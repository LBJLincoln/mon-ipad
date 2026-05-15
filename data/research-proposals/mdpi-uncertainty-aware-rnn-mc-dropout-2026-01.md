# Research Proposal: Uncertainty-Aware RNN + Monte Carlo Dropout for NBA Prediction

**Source:** MDPI Informatics, January 2026  
**URL:** https://www.mdpi.com/2078-2489/17/1/56  
**Title:** Uncertainty-Aware Machine Learning for NBA Forecasting in Digital Betting Markets  
**Detected:** fire-114 (EVEN cycle), 2026-05-16T06:00:00Z  
**Priority:** HIGH — Brier=0.199 beats our current CV best of 0.22054

## Key Results

| Model | Brier Score | Notes |
|-------|------------|-------|
| Logistic Regression | **0.199** | Best result — with uncertainty calibration |
| XGBoost | 0.202 | Second best |
| RNN + MC Dropout | ~0.20 | Uncertainty-aware sequential model |
| Our current best (CV) | 0.22054 | TabICL, isotonic-calibrated |
| Our fleet GA best | 0.22012 | S15 ET-200f |
| Our Pareto candidate | 0.21896 | S15 ET-200f (unconfirmed, field-lag) |

## Architecture Details

- **Method:** Recurrent neural network with Monte Carlo (MC) dropout for uncertainty quantification
- **Features used:**
  - Team-level performance metrics (rolling averages)
  - Rolling-form indicators (last N games momentum)
  - Spatial shot-chart embeddings (court zone shot distributions)
- **Key innovation:** Sequential probability calibration using MC dropout — generates probability distributions, not point estimates
- **Calibration:** Full ECE analysis, reliability diagrams

## Relevance to Nomos42

### Immediate (GPU burst compatible)
1. **Logistic Regression baseline at Brier=0.199** — This is a MAJOR signal. Our islands already have LR in model pool (S13 confirmed gen=684). The Jan 2026 paper suggests LR can match neural approaches with proper feature engineering. Priority: confirm LR Brier on our dataset.
2. **Rolling-form indicators** — Our engine.py v3.1 (54 categories, 7213 features) already has rolling stats. The paper's 0.199 LR result suggests these features are highly informative when properly calibrated.
3. **Shot-chart embeddings** — Not in our current engine. Would require zone-level shot data (available via bbref/ESPN). Add as new feature category.

### Medium-term (ZeroGPU / Modal burst)
4. **RNN + MC Dropout** — GPU-only (not runnable on CPU islands). Target for zerogpu-burst.py or modal-burst.py. Architecture:
   - Sequence length: last 10 games per team
   - Hidden size: 128-256
   - MC dropout: p=0.2, N=50 forward passes at inference
   - Output: mean + std of win probability
5. **Uncertainty as calibration signal** — MC dropout std could replace isotonic calibration or complement it. High std → shrink Kelly stake.

## Implementation Plan

### Phase 1 — Validate LR on our data (VM, no GPU)
```bash
# On VM, using existing data
python scripts/quick-experiments/lr_brier_baseline.py \
  --data data/nba_cached_data.npz \
  --features 200 \
  --calibration isotonic \
  --output data/experiments/lr-baseline-2026-05.json
```
Expected: Brier in 0.20-0.22 range. If <0.22, add LR as primary model type to all islands urgently.

### Phase 2 — Shot-chart embeddings feature engineering
- Scrape zone-level shot distributions via `LBJLincoln/nomos-browser-nba`
- Add `shot_zone_*` categories to features/engine.py (after engine-parity-sync)
- Expected: 30-50 new features per team per game

### Phase 3 — RNN+MC Dropout on GPU burst
- Add `scripts/gpu-burst/rnn_mc_dropout_burst.py`
- Target: ZeroGPU H200 (15 min free/day) or Modal A10G
- Sequence: team last-10-game rolling stats → LSTM → MC dropout head
- Compare against TabICL baseline (our 0.21139 holdout)

## Cross-Project Notes

- **Political Alpha:** Rolling-form + uncertainty calibration directly applicable. POL Brier target is 0.245 (fleet best P4=0.24992). LR baseline on political data would set a clear floor.
- **Engine parity:** Shot-chart features require engine-parity-sync first (Rule #2).
- **S15 SHAP first:** Before adding new features, run SHAP on ET-200f-0.21896 to understand which of our 200 existing features matter most. May reveal we already have shot-zone proxies.

## Related SOTA

| Paper | Brier | Method | Date |
|-------|-------|--------|------|
| MDPI Informatics Jan 2026 | 0.199 | LR + uncertainty-aware RNN+MC dropout | 2026-01 |
| MDPI Computation Oct 2025 | 0.221 | CNN (NBA+WNBA) | 2025-10 |
| BMC Sports Sci 2026 | N/A | SHAP KPI framework | 2026 |
| Sci Reports 2025 | N/A | Stacked ensemble (NB+AdaBoost+MLP+KNN+XGB+DT+LR) | 2025 |
| arXiv:2508.02725 | 0.1589 | LSTM+Brier (NCAA) — GPU target | 2025 |
| RNN+MC dropout MDPI Info | ~0.20 | Already in fire-112 notes |

## Action Items for VM

- [ ] `vm-add-logistic-regression-model-pool` (priority=50) — LR Brier=0.199 confirms urgency
- [ ] `vm-shap-feature-analysis-s15` (priority=80) — before adding shot-chart features
- [ ] Add `scripts/gpu-burst/rnn_mc_dropout_burst.py` (new task, post-SHAP)
- [ ] Add shot-chart zone features to engine.py (after engine-parity-sync)
