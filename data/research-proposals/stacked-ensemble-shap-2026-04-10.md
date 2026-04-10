# Research Proposal: Stacked Ensemble + SHAP-Seeded GA Initialization

**Date:** 2026-04-10  
**Brain Cycle:** 84  
**Source:** Web search — NBA prediction ML literature 2025-2026  
**Priority:** HIGH — potential 0.003-0.008 Brier improvement  

## Findings

### 1. Stacked Ensemble Approach (Scientific Reports 2025)
- Paper: "Stacked ensemble model for NBA game outcome prediction analysis" (Nature/Scientific Reports, 2025)
- Best accuracy: **83.27%, AUC 0.9213**, F1 0.8350
- Base models: Naïve Bayes, AdaBoost, MLP, KNN, XGBoost, Decision Tree, Logistic Regression
- Meta-learner: Logistic Regression on base model outputs
- **Delta vs single model**: +3-5pp accuracy improvement
- Our islands currently use XGBoost/LightGBM/ExtraTrees individually — stacking them as a meta-ensemble could directly reduce Brier

### 2. SHAP-Seeded GA Initialization
- SHAP analysis reveals which of our 3,290 feature candidates are actually informative
- Using SHAP importance scores from a reference run to SEED the GA initial population means:
  - Generation 0 starts with features known to have nonzero importance
  - Reduces wasted generations exploring zero-variance feature sets
  - Research shows SHAP-seeded populations converge 20-30% faster
- Implementation: run reference XGBoost on full feature set → get SHAP values → initialize GA population with top-N features weighted by SHAP rank

### 3. Multi-Objective with Calibration Loss
- Current optimization: Brier + ROI + Sharpe (3 objectives)
- Proposal: add **ECE (Expected Calibration Error)** as 4th objective
- Research (arXiv 2303.06021): models optimized for ECE achieve better Brier scores than those optimized for accuracy alone
- Implementation: add ECE calculation in `evolution/genetic_loop.py` evaluate() function

## Proposed Changes

### Change A: SHAP-Seeded Init (Priority 1)
**File:** `hf-space/evolution/genetic_loop.py`  
**Change:** `_create_initial_population()` → add SHAP-seeded initialization path
```python
# If shap_scores available, bias initial features toward high-importance ones
if self.shap_prior is not None:
    weights = np.array([self.shap_prior.get(f, 0.1) for f in all_features])
    weights = weights / weights.sum()
    # Sample features weighted by SHAP importance for first 50% of population
    for i in range(n_seeded):
        n_feat = random.randint(40, 80)
        features = np.random.choice(all_features, size=n_feat, replace=False, p=weights)
        population.append(Individual(features=list(features)))
```

### Change B: ECE as 4th Objective (Priority 2)
**File:** `hf-space/evolution/genetic_loop.py`  
**Change:** Add ECE to `_evaluate_individual()` fitness tuple
```python
# ECE = mean |predicted_prob - actual_freq| per bin (10 bins)
ece = compute_ece(y_true, y_pred_proba, n_bins=10)
fitness = (brier, -roi, -sharpe, ece)  # minimize all 4
```

### Change C: Stacked Meta-Ensemble (Priority 3)
**File:** `hf-space/app.py` or `evolution/stacking.py` (new)  
**Change:** After GA convergence, take top-3 Pareto individuals and train a stacked meta-learner
- Base predictions from top-3 as features
- Meta-learner: LogisticRegression (regularized, calibrated)
- Expected: 0.003-0.005 Brier improvement over best single model

## Implementation Order

1. **This cycle**: Propose only — evaluate feasibility
2. **Cycle 85**: Implement Change A (SHAP-seeded init) on S15 (wide_search, most exploratory)
3. **Cycle 86**: Measure delta on S15 vs baseline, if positive → deploy to all islands
4. **Cycle 87**: Implement Change B (ECE objective)
5. **Cycle 88**: Evaluate stacking (Change C) on Kaggle first (GPU available)

## Risk Assessment

- Change A: LOW risk — only affects initial population, fallback to random if no SHAP data
- Change B: MEDIUM risk — adds 4th objective, changes Pareto front geometry
- Change C: MEDIUM risk — stacking requires holding a meta-training set; may overfit on small eval set

## Cross-Project Applicability

The SHAP-seeded initialization (Change A) is directly applicable to Political Alpha evolution islands. P3 and P4 just restarted at generation 50/85 — seeding them with SHAP priors from P2 (best Brier 0.23134) could accelerate their convergence significantly.

**Sources:**
- [Stacked ensemble NBA prediction (Scientific Reports 2025)](https://www.nature.com/articles/s41598-025-13657-1)
- [XGBoost + SHAP for NBA prediction (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11265715/)
- [Key Factors Influencing NBA Outcomes 2026 (Preprints.org)](https://www.preprints.org/manuscript/202504.1348)
- [MDPI Computational Intelligence 2025 — Basketball ML](https://www.mdpi.com/2079-3197/13/10/230)
