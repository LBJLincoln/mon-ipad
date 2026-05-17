# Research Proposal — fire-126 (EVEN WebSearch) 2026-05-18

## Query
NBA game prediction machine learning Brier score SOTA 2026 ensemble methods

## Sources
- [IEEE 2026 — Comparing Machine Learning Methods for NBA Game Outcome Prediction](https://ieeexplore.ieee.org/document/11030489/)
- [MDPI Computers 2026 — Machine Learning for Basketball Game Outcomes: NBA and WNBA](https://www.mdpi.com/2079-3197/13/10/230)
- [Nature Sci Reports 2025 — Stacked ensemble model for NBA game outcome prediction](https://www.nature.com/articles/s41598-025-13657-1)
- [MDPI Information 2026 — Uncertainty-Aware Machine Learning for NBA Forecasting](https://www.mdpi.com/2078-2489/17/1/56)
- [arXiv 2508.02725 — LSTM+Transformer NCAA Brier=0.1589](https://arxiv.org/html/2508.02725v1)

## Key Findings

### LR Brier=0.199 (10th confirmation)
Logistic Regression achieves Brier=0.199 consistently across 2025-2026 studies. 10th confirmation. Priority: `vm-add-logistic-regression-model-pool` (work-queue priority=50).

### NEW: IEEE 2026 — Head-to-Head ML Comparison
"Comparing Machine Learning Methods for NBA Game Outcome Prediction" (IEEE Xplore 2026). SVM accuracy=0.7749, AutoGluon=0.7738, DNN=0.7726. LightGBM closest to XGBoost. Classification > regression for outcome prediction. Confirms our ensemble direction.

### NEW: MC Dropout RNN Uncertainty-Aware (MDPI Information 2026)
RNN with Monte Carlo dropout integrates team-level metrics, rolling-form indicators, and **spatial shot-chart embeddings**. Estimated Brier < 0.21. Key insight: uncertainty quantification can improve Kelly sizing (high-uncertainty predictions → smaller Kelly). Shot-chart spatial embeddings = novel feature dimension not yet in our engine.

### SHAP Top Features (10th confirmation)
ELO = #1 AND #2 SHAP features (team_elo_5_y, team_elo) across 10 studies. `vm-add-elo-ratings-engine` priority CONFIRMED MAX. Next: home_next, 2PA, FG, TRB.

### Stacked Ensemble (Sci Reports 2025)
NB+AdaBoost+MLP+KNN+XGB+DT+LR stacked ensemble. `vm-add-adaboost-naive-bayes` queued. MLP needs GPU.

## Proposed Experiments (Priority Order)

### P1: Elo Ratings Feature Category
Add rolling Elo (team_elo_current, team_elo_5game_rolling, elo_delta_home_away, elo_home_advantage_adj) to features/engine.py. After `engine-parity-sync`. SHAP confirms ELO = global top-2. Expected Brier improvement: ~0.003-0.005.

### P2: Uncertainty-Aware Kelly Calibration
Use ensemble variance or MC dropout to compute prediction uncertainty per game. Map uncertainty → Kelly adjustment. High-uncertainty games get smaller Kelly fraction. Could improve P&L quality without changing Brier. Implement as post-processing in TF agent Kelly calculation.

### P3: Shot-Chart Spatial Embeddings
MDPI 2026 uses spatial shot-chart embeddings (team shooting zones). NBA Stats API has zone data. Could add 20-40 new features. Lower priority — after Elo.

### P4: AutoGluon Benchmark
IEEE 2026 shows AutoGluon accuracy=0.7738. AutoML that stacks many models. Test on Kaggle P100 as upper-bound benchmark. CPU too slow for HF Spaces.

## Fleet Observation
S14 CatBoost-200f-0.21888 at gen=84 (fresh restart) = second consecutive fresh-restart immediately finding pareto-level candidates. Pattern: ET-200f and CatBoost-200f are the dominant attractors — islands converge to these within 30-100 generations regardless of starting point. Cross-fleet: 5/6 NBA islands showing ET-200f or CatBoost-200f as pareto leaders.

## Loss Analysis
S22 factory reboot (CatBoost-0.21818 all-time record LOST) reinforces the urgent need for automated checkpointing. Recommend: VM implement auto-checkpoint cron that exports pareto_best when brier < 0.2185, every 30 minutes, without waiting for cloud brain detection.
