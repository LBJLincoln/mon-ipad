# Research Proposal: MLP Meta-Learner Specifics + Brier Decomposition Optimization

**Date:** 2026-04-10  
**Brain Cycle:** 85  
**Source:** PMC12357926 (Scientific Reports 2025 — Stacked Ensemble NBA), arXiv 2504.04906 (Brier score misconceptions)  
**Priority:** HIGH — implementation of Cycle84 Change A + new finding on Brier components  
**Status:** ACTIONABLE — implement on S15 this cycle per Cycle84 roadmap

---

## New Finding: MLP Meta-Learner Architecture (PMC12357926)

The best-performing NBA stacking ensemble uses:
- **Base learners**: XGBoost, KNN, AdaBoost, Naïve Bayes, Logistic Regression, Decision Tree (6 heterogeneous models)
- **Meta-learner**: MLP with **2 hidden layers × 50 neurons each** (NOT logistic regression as Cycle84 assumed)
- **Result**: Accuracy 83.27%, AUC 0.9213, F1 0.8350
- **Key**: heterogeneous diversity in base learners is more important than the meta-learner choice

**Implication for our system**: Our Pareto front already has 14-19 non-dominated solutions per island with XGBoost, LightGBM, ExtraTrees, CatBoost diversity. The stacking step should use a **small MLP (2×50)** not Logistic Regression as originally proposed.

---

## New Finding: Brier Score Decomposition (arXiv 2504.04906)

The Brier score decomposes as:
```
BS = Calibration_Component + Resolution_Component - Uncertainty
```

Where:
- **Calibration** = mean |predicted_prob - actual_freq| per bin (ECE proxy)
- **Resolution** = model's ability to discriminate outcomes (related to AUC)

**Critical insight**: A model can improve Brier by improving EITHER component independently. Current system optimizes Brier as a whole — explicitly separating and targeting both components could unlock additional gains.

**Our current gap**: Best fleet Brier = 0.22249 (S11). Target = 0.21837. Gap = 0.00412.
- If gap is primarily calibration: isotonic post-calibration would close most of it
- If gap is primarily resolution: better features/more data needed
- Recommended: compute decomposition on current best model to identify which component to attack

---

## Implementation Plan (Cycle 85 → 88)

### This Cycle (85): Brier Decomposition Diagnostic
**File**: `eval/evaluate_predictions.py` or `scripts/departments/evaluation/`  
**Action**: Add decomposition calculation to understand where our 0.00412 gap comes from

```python
def brier_decompose(y_true, y_pred, n_bins=10):
    """Decompose Brier score into calibration + resolution - uncertainty."""
    bins = np.linspace(0, 1, n_bins + 1)
    calibration = 0.0
    resolution = 0.0
    uncertainty = np.var(y_true)  # base rate variance
    
    bar_y = np.mean(y_true)  # overall mean
    for i in range(n_bins):
        mask = (y_pred >= bins[i]) & (y_pred < bins[i+1])
        if mask.sum() == 0:
            continue
        n_k = mask.sum()
        bar_f_k = y_pred[mask].mean()    # mean predicted prob in bin
        bar_y_k = y_true[mask].mean()    # mean actual outcome in bin
        calibration += n_k * (bar_f_k - bar_y_k) ** 2
        resolution  += n_k * (bar_y_k - bar_y) ** 2
    
    n = len(y_true)
    return calibration/n, resolution/n, uncertainty
```

### Next Cycle (86): SHAP-Seeded Init on S15 (from Cycle84 plan)
**File**: `hf-space/evolution/genetic_loop_v3.py`  
**Action**: Implement SHAP-seeded `_create_initial_population()` as specified in Cycle84 proposal  
**Expected**: 20-30% faster convergence, potentially break through 0.21837 barrier

### Cycle 87: MLP Meta-Learner Post-Processing
**File**: `hf-space/app.py`  
**Action**: After island evolution, take top-3 Pareto individuals → stack with MLP(50, 50) meta-learner  
**Architecture**: XGBoost + LightGBM + ExtraTrees base → MLP meta  
**Expected**: 0.003-0.005 Brier improvement on top of best individual (0.22249 → ~0.218x)

### Cycle 88: Deploy to All Islands if Cycle87 Delta Positive
**Action**: Update all 6 island configs to use stacked meta-learner for final predictions

---

## Most Important Features (PMC12357926 SHAP Analysis)

For NBA games specifically:
1. **2PA** (two-point attempts) — negative when high (low-efficiency offense)
2. **FG** (field goals made) — positive
3. **TRB** (total rebounds) — positive
4. **FGA** (field goal attempts) — negative when excessive

**Cross-check with our features**: Our Cat1 (Rolling Performance) and Cat2 (Four Factors) already capture FG%, TRB, FGA. The key differentiator is **shot selection quality** (2PA vs 3PA ratio), which should be in Cat3 (Scoring Profile). If not present, add `shot_selection_2pa_ratio` to Cat60.

---

## Cross-Project Applicability

- **Political Alpha**: Brier decomposition diagnostic equally applicable to P1/P2 (Brier 0.2497/0.23134)
- P2's calibration component likely worse than P1's since P2 runs in bootstrap mode (312 synthetic events)
- **Action**: Run decomposition on both political islands to guide improvement direction

---

## Sources
- [Stacked Ensemble NBA PMC12357926](https://pmc.ncbi.nlm.nih.gov/articles/PMC12357926/) — MLP 2×50 meta-learner, AUC 0.9213
- [Brier Score Decomposition arXiv 2504.04906](https://arxiv.org/html/2504.04906v3) — calibration vs resolution components
- [XGBoost+SHAP NBA PMC11265715](https://pmc.ncbi.nlm.nih.gov/articles/PMC11265715/) — SHAP feature importance
- [PLOS One AI Basketball Review 2025](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0326326) — systematic review
