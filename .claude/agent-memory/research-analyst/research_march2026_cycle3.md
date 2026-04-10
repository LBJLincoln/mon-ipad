---
name: research_march2026_cycle3
description: March 26 2026 deep research cycle v3 — calibration breakthrough, TabICLv2 update, new feature evidence, Kelly upgrade, conformal prediction
type: project
---

Research completed: 2026-03-26
Output file: /home/termius/nomos-nba-agent/data/results/crew-research.json (cycle march-2026-deep-sweep-v3)

## Top Actionable Findings This Cycle

### 1. CRITICAL: Replace Isotonic with Beta or Venn-Abers Calibration (2h, -0.003 Brier)
arXiv:2601.19944 "Classifier Calibration at Scale" (Jan 19, 2026): comprehensive study of 21 classifiers
including XGBoost/CatBoost/LightGBM/ExtraTrees on TabArena-v0.1. Finding: isotonic regression and
Platt scaling SYSTEMATICALLY DEGRADE proper scoring performance for modern tree ensembles. Venn-Abers
and Beta calibration consistently outperform. This explains exactly why our xgboost_cal (0.2240) is
worse than uncalibrated (0.2206). Fix: pip install betacal venn-abers. Test both, use whichever is
lower. 2-hour effort, highest priority.

### 2. TabICLv2 Now Surpasses RealTabPFN-2.5 (4h, -0.006 Brier via evolution)
arXiv:2602.11139 (Feb 2026): TabICLv2 beats RealTabPFN-2.5 on TabArena AND TALENT benchmarks without
any tuning. Substantially outperforms tuned XGBoost/CatBoost. 10.6x faster than TabPFN-2.5 on H100.
pip install tabicl. from tabicl import TabICLClassifier. Our Colab fold 4 already hit Brier 0.21222
with an earlier version. Deploy as primary GPU evolution model in Colab — run 50-gen evolution with
TabICLv2 as objective. GitHub: soda-inria/tabicl. Open weights (unlike TabPFN-2.5).

### 3. XStacking: SHAP Values as Meta-Features (6h, -0.003 Brier)
"XStacking" (Information Fusion 2025, ScienceDirect, github.com/LeMGarouani/XStacking): enrich stacking
meta-learner input with SHAP-based feature importance scores from base learners alongside OOF predictions.
Equal or better on 16/17 classification datasets. +2.6-5.9% precision gains. Implementation: concatenate
[OOF_pred_i, mean_SHAP_i] for each base learner as meta-features (10 features instead of 5). Meta-learner
sees not just "what each model predicts" but "why it predicts that."

### 4. Three New Feature Categories with Validated Evidence

A. Separate Offensive + Defensive Ratings (MDPI Computation 2025):
   Combining into net_rating LOSES information. O-rating and D-rating carry different predictive signals
   at different game stages. Add: h_ortg_{5,10}, h_drtg_{5,10}, a_ortg_{5,10}, a_drtg_{5,10} + diffs.

B. Travel Distance + Timezone Features (JCSM 2021, replicated 25K matches 2024):
   4% win probability reduction per 500km road travel (p=0.038). Eastward travel worse than westward
   (p=0.024, circadian disruption). New features: h_travel_km, a_travel_km, h_tz_shift, a_tz_shift,
   h_cumulative_km_7d. Build arena_gps.json (30 arenas) + haversine distance computation.

C. Referee Crew Stats (SAGE Journal of Sports Economics, 2025):
   Referees make 23-42% fewer incorrect calls for visiting team underdogs (crowd effect). Specific crews
   show 12-15% home-foul-rate variance. Referee assignments announced 2-3h before tipoff on NBA.com.
   Features: h_crew_home_win_pct, h_crew_foul_diff. Almost zero public models use this — hidden alpha.

### 5. MOVDA delta_MOV Residual as New Feature (2h, -0.002 Brier)
MOVDA already deployed. New 3 features: h_movda_delta_mov_5 (rolling 5-game mean of how much team
over/underperformed their expected MOV). movda_delta_mov_diff = h - a versions. Captures "hot/cold"
teams performing above/below their rating-implied spread — invisible to current model.

### 6. Ridge Kelly Criterion for Correlated Bets (5h, +0.015 ROI)
Hakobyan & Lototsky (arXiv:2503.17927, March 2025): Kelly with risk-aversion parameter gamma.
Formula: f* = argmax[gr(f) - gamma*vr(f)]. For correlated same-night NBA bets: compute covariance
matrix, apply correlation discount f_adj = f_kelly * (1 - rho). Key result: f=0.2 gives 90% variance
reduction vs 30% growth sacrifice. Practical: cap total nightly exposure at 5% bankroll.

### 7. Conformal Prediction via MAPIE v1 (6h, bet-sizing signal)
MAPIE v1 (scikit-learn-contrib, redesigned 2025): SplitConformalClassifier produces prediction intervals
with guaranteed coverage. Use interval width as bet-sizing signal: width < 0.05 = full Kelly, > 0.10 = no
bet. NeurIPS 2025 paper (poster #115699) shows ensemble conformal aggregation produces 15-30% tighter
intervals than individual model conformal while maintaining coverage. pip install mapie.

## Market Microstructure Alpha

- CLV (Closing Line Value): track our bets vs Pinnacle closing line. Positive CLV > 0 confirms edge.
- Steam detection: if 2+ books move same direction within 5 minutes by 1+ point, that is sharp steam.
- Reverse line movement: >60% bets on Team A but line moves toward Team B = sharp on Team B. Use as feature.
- Injury market lag: Pinnacle adjusts within minutes, DraftKings takes 15-30 minutes. Window to bet soft books.
- Season-end rest: teams with clinched seedings rest starters. Books price on records not motivation.

## Papers by Priority (Impact / Effort)

High impact, easy effort (do first):
1. arXiv:2601.19944 — Beta/Venn-Abers calibration swap (2h, -0.003)
2. arXiv:2602.11139 — TabICLv2 Colab evolution (4h, -0.006)
3. MOVDA delta_MOV residual (2h, -0.002)
4. Separate O/D rating features (4h, -0.002)
5. LightGBM hyperparameter fix (2h, -0.002)

Medium impact, medium effort:
6. XStacking meta-learner with SHAP (6h, -0.003)
7. eFG%/TS% features (4h, -0.003)
8. Travel distance + timezone features (8h, -0.002)
9. Ridge Kelly criterion (5h, +0.015 ROI)

Longer term (high effort):
10. Referee crew stats (10h, -0.002)
11. MAPIE conformal bet-sizing (6h, +0.01 ROI)
12. Bi-objective NSGA-II GA (12h, -0.004)
13. Real-time in-game model (20h, -0.015)
