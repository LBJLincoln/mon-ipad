# NBA SOTA Research — 2026-04-20 08:00 (Cycle 2)

## Sources
- [Stacked ensemble — Nature/Scientific Reports 2025](https://www.nature.com/articles/s41598-025-13657-1)
- [Uncertainty-aware RNN+MC-dropout — MDPI Info 2026](https://www.mdpi.com/2078-2489/17/1/56)
- [XGBoost+SHAP for NBA — PMC 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC11265715/)
- [Hierarchical GATv2 architecture — Springer 2024](https://link.springer.com/article/10.1007/s44163-024-00201-9)

## Gap Analysis

| Model | Brier | Notes |
|-------|-------|-------|
| Our fleet best (alltime) | 0.22073 | S22 venn_abers, checkpointed |
| Our fleet best (live) | 0.22136 | S13 extra_trees, stagnant |
| SOTA CNN | 0.221 | Comparable |
| SOTA logistic regression | 0.199 | **0.022 gap vs our fleet** |
| Target | < 0.200 | Season goal |

**Key gap:** Published logistic regression achieves 0.199 while our complex tree ensembles plateau at ~0.221. This strongly suggests our feature space has noise overfitting complex non-linear boundaries.

## Novel Techniques This Cycle

### 1. Stacked Ensemble with MLP Meta-Learner (Priority: HIGH)
**Source:** Nature Scientific Reports 2025  
**Method:** Base classifiers (ExtraTrees, CatBoost, LightGBM, XGBoost, RF) → probability outputs → MLP 2-layer meta-learner trained on Brier loss.  
**Key insight:** The meta-learner sees *disagreement patterns* between base models as a signal.  
**CPU feasibility:** MLP (32→16→1) is CPU-feasible. Base models already trained on islands.  
**Estimated gain:** 0.002–0.004 Brier reduction (cross-island Pareto ensemble baseline 0.221 → 0.218)

### 2. Hierarchical GATv2 Player-Synergy Model (Priority: LOW — GPU needed)
**Source:** Springer Discover AI 2024  
**Architecture:** L1 Kalman-filter player ability tracking → L2 GATv2 graph for lineup synergy → L3 team-level effects → L4 game prediction. ~1.4M params.  
**Feasibility:** Requires GPU (ZeroGPU or Modal A10G burst). Script to add: `scripts/gpu-burst/gat-player-synergy.py`.  
**Estimated gain:** 0.010–0.020 if training data includes play-by-play (we have box scores only — partial gain).

### 3. Logistic Regression L1-Sparse Baseline (Priority: HIGH — CPU)
**Insight:** If LR achieves 0.199 published, our GA should be sampling it. Check island configs — are LR/LogisticCV in the model_type pool?  
**Action:** Add `logistic_regression_l1` as explicit model type on S17 (XGBoost-focused) to test if sparse linear model outperforms on our dataset.  
**Implementation:** `model_type = 'logistic_l1'` → `LogisticRegression(penalty='l1', solver='liblinear', C=0.1)`, features pruned to top-30 by MI score.

### 4. Rolling-Form Velocity Features (Priority: MED — already partially covered)
**Source:** MDPI uncertainty-aware paper  
**Features missing from our engine:** `win_rate_last5_velocity` (derivative of 5-game win rate), `elo_momentum` (Elo change slope over 10 games), `back_to_back_streak` (consecutive B2B days).  
**Engine.py status:** Rolling win rate present (cat46), but velocity/momentum derivative not computed.  
**Add to:** `features/engine.py` cat46 section — 3 new features, low compute cost.

## Cross-Project Port (NBA → Political)

The **stacked MLP meta-learner** technique is directly portable to political:  
- 5 political trees (P1-P7) already produce probability outputs  
- Train thin MLP on combined outputs → ensemble political probability  
- Expected gain: 0.001–0.002 on political Brier (0.249 → 0.247)

## Recommended Priority Order

1. Add `logistic_l1` model type to S17 GA pool (1 line change, highest SOTA alignment)
2. Rolling-form velocity features in engine.py (3 features, low risk)
3. Cross-island stacked MLP via GPU burst script
4. GATv2 hierarchy (longer-term, GPU-only)
