# Research Proposal: Uncertainty Quantification + DAS Spatial Features for NBA Prediction

**Fire:** fire-104 EVEN | **Date:** 2026-05-13 | **Author:** cloud-brain-sonnet4-6

## SOTA Sources This Cycle

1. **Montrucchio, Barbierato, Gatti (2026) — "Uncertainty-Aware Machine Learning for NBA Forecasting in Digital Betting Markets"** *(Information journal)*
   - LR achieves Brier=0.199 as best tabular baseline (reconfirms MDPI 2026 finding from fire-103)
   - Key innovation: Brier score decomposition into reliability + resolution + uncertainty components
   - Uncertainty quantification guides model selection and calibration

2. **Bischofberger, Baca (2026) — "Dangerous accessible space: a unified model of space and value in team sports"** *(Journal of Big Data)*
   - Spatial-value unified model: combines court positioning with shot quality
   - Reduces log-loss vs. features that don't model spatial context
   - Features: shot quality scores, court zone occupancy rates, transition probabilities

3. **Klemp et al. (2026) — "ML in performance analysis in invasion games"** *(Journal of Sports Sciences)*
   - Comprehensive review confirms Brier + ECE as 2026 standard evaluation
   - Best results: multi-feature ensembles + isotonic calibration post-processing
   - Calibration matters more than raw accuracy for probability prediction tasks

## Actionable Proposals (CPU Islands, No GPU Required)

### Proposal A: Logistic Regression Addition (Highest Priority)
- **Evidence:** LR Brier=0.199 confirmed by 2 independent 2026 papers
- **Action:** Add `logistic_regression` to MODEL_TYPES on P2, P4, P5, P7 (POL) and verify S15, S22 (NBA)
- **VM task:** vm-add-logistic-regression-model-pool (priority 50)
- **Expected gain:** Potential 0.001-0.005 Brier improvement if LR discovers features poorly represented by tree models

### Proposal B: Brier Decomposition for Stagnation Detection
- **Evidence:** Montrucchio 2026 shows Brier decomposition reveals calibration vs. resolution failures
- **Action:** Add Brier decomposition tracking to island GA evaluation loop:
  - reliability component: calibration quality
  - resolution component: discriminative power
  - uncertainty component: base rate entropy
- **Implication:** Current stagnation (stag counter) only tracks aggregate Brier. Islands could stagnate in resolution while improving calibration — early diversify trigger on resolution stagnation would be more precise
- **Implementation:** Post-evaluate each population member with `brier_decompose()` from sklearn → add to individual metadata

### Proposal C: DAS Spatial Feature Category
- **Evidence:** Bischofberger & Baca 2026 show spatial-value features reduce log-loss across team sports
- **Proposed features for features/engine.py (new category 55):**
  - `zone_attack_rate_{zone}`: fraction of possessions attacking each court zone (5 zones)
  - `shot_quality_index_{team}`: possession-weighted shot quality (eFG context-adjusted)
  - `transition_rate_{home/away}`: fast break possession rate
  - `paint_vs_perimeter_ratio`: inside scoring tendency
  - `contested_shot_rate`: defensive pressure metric
- **Feasibility:** All derivable from existing box score / tracking data in data pipeline
- **Expected count:** ~15-20 new features, within feature engine capacity
- **Prerequisite:** vm-restart-political-data-crons + engine-parity-sync

### Proposal D: Isotonic Calibration Post-Processing on Islands
- **Evidence:** Klemp et al. 2026 confirm calibration post-processing as top technique
- **Current state:** Oracle Space uses isotonic calibration (0.22054 calibrated Brier)
- **Action:** Apply same isotonic calibration wrapper to island ensemble output before Brier eval
- **Expected gain:** Historical oracle result: raw 0.22169 → calibrated 0.22054 (-0.00115)
- **Caution:** Islands already optimize for Brier directly; calibration post-hoc may conflict with objective function

## Cross-Project Port Insight (STEP 5)

LightGBM dominance in POL (P2/P4/P7 all showing 0.249 with LightGBM at ~108-117 features) vs.
NBA (extra_trees S14, random_forest S15) suggests different optimal algorithms by domain:

- **Political domain:** Sparse high-dimensional features (272 candidates) → LightGBM leaf-wise growth excels
- **NBA domain:** Dense mid-dimensional features (3377 candidates, 57-75f optimal) → RF/ET depth excels

**Port recommendation:** NBA islands that haven't tried LightGBM at 100+ features should be tested.
S22 (extra_trees 44f) is the best candidate — add lightgbm to S22 MODEL_TYPES and observe
if 100-150f LightGBM candidates emerge in Pareto front.

## Priority Ranking

| # | Proposal | Effort | Expected Gain | VM Required? |
|---|----------|--------|---------------|---------------|
| 1 | LR addition to MODEL_TYPES | Low | High (SOTA proven) | YES (P50) |
| 2 | DAS spatial features | Medium | Medium-High | YES (engine.py) |
| 3 | Brier decomposition stagnation | Medium | Medium | YES (island code) |
| 4 | Isotonic calibration post-proc | Low | Low-Medium | YES (island code) |

All proposals require VM execution. Cloud brain role: document, prioritize, escalate.
