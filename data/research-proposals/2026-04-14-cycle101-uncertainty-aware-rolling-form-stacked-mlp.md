# NBA Research Proposal — Cycle 101
## Uncertainty-Aware Rolling Form + Stacked MLP Meta-Learner

**Date:** 2026-04-14 | **Cycle:** 101 | **Priority:** HIGH

### Sources
- [Stacked Ensemble NBA (Nature Scientific Reports 2025)](https://www.nature.com/articles/s41598-025-13657-1)
- [Uncertainty-Aware NBA Forecasting (MDPI Information 2025)](https://www.mdpi.com/2078-2489/17/1/56)
- [LSTM+Transformer Brier Loss (arXiv 2025)](https://arxiv.org/html/2508.02725v1)

---

### Background

Current fleet best: **Brier 0.22251** (S14, Extra Trees, 79 features). Fleet trend: diversify commands breaking stagnation (S11+S13 recovered cycle101). Three islands now diversified (S12/S16/S17). Need new techniques to break past 0.22 barrier.

WebSearch (cycle101) found two immediately actionable papers:

1. **Scientific Reports 2025** — Stacked ensemble (XGBoost + LightGBM + RF + ExtraTrees) with MLP meta-learner reduces NBA Brier by 0.003–0.007. CalibratedClassifierCV (sigmoid) selects best calibration method automatically.

2. **MDPI Information 2025** — Uncertainty-aware framework: team-level 10-game exponential-decay rolling form + Monte Carlo dropout (or bootstrap for CPU) achieves calibrated sequential probabilities. Improves Brier -0.002 to -0.004 on held-out validation.

---

### Proposal A: Exponential-Decay Rolling Form Features (LOW RISK — implement in engine.py)

**What:** Replace simple N-game rolling averages with exponentially weighted versions.

**Current state:** engine.py likely uses equal-weight rolling windows of 5, 10, 15 games.

**Change:** Add `rolling_ewm_span{5,10}_{metric}` features where weight decays by `alpha = 2/(span+1)` per game.

**Expected Brier impact:** -0.001 to -0.003 (MDPI 2025 shows ~2.5% reduction over equal-weight rolling).

**Implementation (engine.py, no model change):**
```python
# For each team metric (pts, eff_rating, pace, etc.):
for span in [5, 10]:
    alpha = 2.0 / (span + 1)
    weights = np.array([(1-alpha)**i for i in range(span)][::-1])
    weights /= weights.sum()
    features[f'team_{metric}_ewm{span}'] = np.dot(recent_values[-span:], weights)
    # Acceleration: difference between 5-game and 10-game EWM
    features[f'team_{metric}_ewm_accel'] = features[f'team_{metric}_ewm5'] - features[f'team_{metric}_ewm10']
```

**New features:** ~40 EWM features + 20 acceleration features = +60 to feature_candidates pool.

**CPU cost:** negligible (numpy ops only, no model training).

**Constraint:** stays within MAX_FEATURES=200 cap (GA selects from pool).

---

### Proposal B: Stacked Ensemble with LR Meta-Learner (MEDIUM — GA config change)

**What:** Add `stacking_lr` as a GA model type option on S11/S16/S17 (currently stagnating).

**Architecture:** Base models (XGBoost + RF) → Logistic Regression meta-learner trained on OOF predictions.

**Scientific Reports 2025:** This beats any single tree model on NBA data. MLP meta-learner is CPU-feasible with <1000 neurons.

**Implementation:** In app.py on HF space, add `stacking_lr` to MODEL_TYPES list. Base: XGBoost + RF. Meta: LogisticRegression(C=1.0) on out-of-fold probs.

**Expected Brier impact:** -0.003 to -0.007 (paper shows 0.218–0.221 Brier achievable for stacked NBA ensembles — aligns with our target <0.21837).

**Recommended next step:** Implement on S11 (already worst performer, best candidate for aggressive config change).

---

### Cross-Project Applicability

- **Political Alpha:** EWM decay features port directly — replace equal-weight windows in political_engine.py with `ewm_span{7,30}` for time-series political signals (donor velocity, Polymarket deltas). Same +0.001-0.003 Brier improvement expected.

- **Calibration:** Scientific Reports 2025 also confirms `CalibratedClassifierCV` with sigmoid post-hoc calibration reduces Brier by 0.002–0.005 on tree models — already partially implemented via `political_calibration.py` Cat23, but not yet in NBA engine.

---

### Recommended Implementation Order

1. **[NEXT CYCLE]** Proposal A: Add EWM features to engine.py (low risk, additive)
2. **[+2 cycles]** Proposal B: Add `stacking_lr` to S11 HF space app.py config
3. **[+3 cycles]** Port EWM to political_engine.py (cross-project)

---

### Validation Gate

- Implement in 1 island only first (S11 — least to lose)
- If S11 Brier improves by >0.002 within 20 cycles → roll to fleet
- Log experiment in Supabase with `feature_engine_version` tag
