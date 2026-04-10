---
name: research_march2026_cycle4
description: March 26 2026 research cycle 4 — AF-NSGA-II sparse init, CRLS fine-tuning, NGBoost CRPS, TabPFN Beta, LightGBM DART fix, calibration-first model selection, post-COVID home advantage decay
type: project
---

Research completed: 2026-03-26
Output file: /home/lahargnedebartoli/nomos-nba-agent/data/results/crew-research.json (cycle march-2026-deep-sweep-v4)

## New Findings This Cycle (Cycle 4 — additive to Cycle 3)

### 1. AF-NSGA-II Sparse Initialization (Jan 2026, MDPI Electronics)
Paper: "An Improved Adaptive NSGA-II with Multiple Filtering for High-Dimensional Feature Selection"
URL: https://www.mdpi.com/2079-9292/15/1/236
Key: Three innovations — ReliefF+MIC+Fisher entropy-weighted sparse initialization (most important), adaptive crossover via Hamming distance with OPHD probability matrix, feature-weighted mutation.
Results: 55-70% HV improvement over NSGA-II, 80% average IGD reduction on 10 gene datasets (2308-12600 features).
Application: Ablation proves sparse initialization > adaptive crossover. Implement in genetic_loop_v3.py first.
pip install skrebate (ReliefF). mutual_info_classif (MIC proxy), f_classif (Fisher) already in sklearn.
Expected Brier delta: -0.003, effort 8h.

### 2. CRLS Fine-Tuning for TabICLv2 / TabPFN (March 2026, arXiv:2603.08206)
Title: "Distributional Regression with Tabular Foundation Models: Evaluating Probabilistic Predictions via Proper Scoring Rules"
Authors: Jonas Landsgesell, Pascal Knoll
VERY FRESH — March 2026. Fine-tune realTabPFNv2.5 with CRLS (Continuous Ranked Logarithmic Scoring Rule) instead of default MSE. CRLS gives MORE weight to events predicted unlikely — penalizes crude mean errors hardest.
Fine-tuning API: lr=1e-5, 600 epochs, early stopping=20, zero default loss weights to apply custom scoring exclusively.
Also tested: Beta-Energy Score (beta=1.8), tabICLv2 with quantile estimation.
Scope: regression tasks only (not binary classification directly), but CRLS can be adapted for Bernoulli outputs.
Expected Brier delta: -0.004, effort 10h.

### 3. TabPFN Beta Method (Bagging + Encoder Fine-Tuning) (Feb 2025, arXiv:2502.02527)
Title: "TabPFN Unleashed: A Scalable and Effective Solution to Tabular Classification Problems"
Authors: Si-Yang Liu, Han-Jia Ye
Beta method simultaneously reduces bias AND variance (prior methods focus only on one). Lightweight encoder + bootstrapped sampling + multiple encoders.
Tested on 200+ benchmark classification datasets. Competitive with SOTA.
Application: Apply Beta fine-tuning wrapper to our TabPFN usage in Colab. Reduces fold variance (our fold 4 hits 0.21222 but mean is ~0.223 — variance reduction would pull mean down).
Expected Brier delta: -0.003, effort 6h.

### 4. NGBoost Bernoulli CRPS as LightGBM Replacement (2025 comparative review)
Paper: "From Point to Probabilistic Gradient Boosting" (Eur Actuarial J 2025, arXiv:2412.14916)
NGBoost with Bernoulli distribution directly optimizes CRPS proper scoring rule for binary outcomes.
Our LightGBM hit anomalous 0.2394 — NGBoost as replacement is low-risk/high-reward.
pip install ngboost. from ngboost import NGBClassifier; from ngboost.distns import Bernoulli; clf = NGBClassifier(Dist=Bernoulli, n_estimators=500).
Also DART mode in LightGBM: boosting_type='dart', drop_rate=0.1 — better calibration via dropout.
Expected Brier delta: -0.003 (NGBoost) or -0.015 fix (LightGBM DART from 0.2394).

### 5. Calibration-First Model Selection (Walsh & Joshi, NBA-specific)
Paper: arXiv:2303.06021 — NBA-specific empirical study.
Calibration-optimized selection: +34.69% avg ROI. Accuracy-optimized: -35.17%.
Our Brier-first optimization is CORRECT. But should add ECE as co-objective in GA:
Bi-objective GA: minimize(Brier, ECE) rather than just minimize(Brier).
Expected ROI delta: large (validated on NBA data). Expected Brier delta: -0.002.

### 6. Post-COVID Home Advantage Decay (2025 preprint)
Finding: Fans contribute only ~2.2 additional home wins/season (post-2021 analysis).
Implication: Static home court feature may be overweighted in pre-COVID trained models.
Action: Check if our model accuracy on home favorites has declined post-2022. If yes, downweight is_home or use rolling_home_win_pct_current_season instead.
Expected Brier delta: -0.001, effort 3h.

### 7. NBA Referee Betting Line Paper (SAGE 2025)
Journal: Journal of Sports Economics (SAGE 2025)
URL: https://journals.sagepub.com/doi/10.1177/15270025251369447
Confirms: No bias in called fouls, but significant in-group bias in NON-CALLED fouls (favors home team). Betting lines are set incorporating these systematic patterns. Smart bettors who know referee-specific tendencies can exploit deviations.
Feature: h_crew_home_win_pct, h_crew_foul_diff — referee assignments on nba.com 2-3h before tipoff.

## Updated Priority Matrix (Combining Cycles 3+4)

Immediate (<2h, high confidence):
1. LightGBM DART fix (0.2394 -> ~0.223, purely fixing broken model)
2. Beta calibration / Venn-Abers swap (arXiv:2601.19944, -0.003)
3. NGBoost Bernoulli CRPS test (-0.003)

This week (2-6h):
4. TabICLv2 50-gen Colab evolution (-0.006)
5. eFG%/TS% + ORTG/DRTG features Cat38 (-0.004 combined)
6. MOVDA delta_MOV residual Cat40 (-0.002)
7. Bi-objective GA (Brier+ECE or Brier+feature_count) (-0.002 to -0.004)

Next sprint (8-16h):
8. AF-NSGA-II sparse initialization in GA (-0.003)
9. Travel distance + timezone features Cat39 (-0.002)
10. XStacking SHAP meta-features (-0.003)
11. TabPFN Beta fine-tuning (-0.003)
12. CRLS fine-tuning for TabICLv2 (-0.004)

## Path to < 0.20 Brier

Current: 0.21867
Step 1 (LightGBM fix + Venn-Abers + NGBoost): -0.018 realistic -> ~0.2007 (close)
Step 2 (TabICLv2 evolution + new features): -0.008 -> ~0.1927 (target broken)

Realistic: 0.21867 - 0.017 (60% efficiency) = 0.20167 after step 1.
Breaking 0.20 requires TabICLv2 Colab evolution OR AF-NSGA-II improvement to push further.
