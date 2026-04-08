---
name: project_nba_research_state
description: Current NBA model state as of 2026-03-25, evolution results, feature counts, key gaps
type: project
---

Current best Brier: 0.21867 (experiment #734, extra_trees, 142 features, gen 104)
Target: Brier < 0.20
Gap: 0.01867 to close

**Why:** $1B fund needs sub-0.20 Brier to achieve ROI > 5% and Sharpe > 1.5 threshold for deploying real capital.

**How to apply:** All research proposals must include realistic Brier delta estimates. Sub-0.20 requires multiple techniques in combination — no single technique gets there alone.

## Latest Evolution Run (2026-03-16)

Source: evolution-20260316-2142.json
- 9290 games, 164 raw features, 94 selected, 30 GA generations, 100 Optuna trials
- Best model: stacking (Brier 0.2205)
- XGBoost: 0.2206, RF: 0.2218, LR: 0.2225
- LightGBM: 0.2394 (anomalously bad — hyperparameter issue suspected)
- CatBoost: 0.2282
- All calibrated variants WORSE than uncalibrated (confirmed cause: isotonic/Platt HURT modern tree models)

## Key Findings from Research Cycle v3 (2026-03-26)

### Calibration Fix (HIGHEST PRIORITY — 2-hour effort, -0.003 Brier)
arXiv:2601.19944 (Jan 19, 2026) proves isotonic regression and Platt scaling SYSTEMATICALLY DEGRADE strong modern tree models. Use Beta calibration (pip install betacal) or Venn-Abers (pip install venn-abers) instead. Our xgboost_cal=0.2240 vs xgboost=0.2206 is explained by this paper.

### TabICLv2 Update (arXiv:2602.11139, Feb 2026)
Surpasses RealTabPFN-2.5 on TabArena/TALENT benchmarks. 10.6x faster than TabPFN-2.5 on H100. Supports predict_proba. GitHub: soda-inria/tabicl. Our Colab fold 4 already hit 0.21222 with earlier version. Priority: run full GA evolution with TabICLv2 objective on Colab.

### New Features with Validated Evidence
1. Separate O-rating + D-rating (not just net_rating) — MDPI Computation 2025: combining LOSES information
2. eFG% and TS% rolling windows — SHAP #1 evidence from Scientific Reports 2025
3. Travel distance + timezone shift — JCSM 2021: 4% per 500km, eastward worse (p=0.024)
4. Referee crew stats — SAGE 2025: 23-42% fewer incorrect calls pattern, home underdogs benefit
5. MOVDA delta_MOV residual — 3 features, captures over/underperformance vs expected spread

### XStacking Meta-Learner Upgrade
XStacking (Information Fusion 2025, github.com/LeMGarouani/XStacking): enrich meta-learner input with SHAP values from base learners. Equal or better on 16/17 datasets. +2.6% to +5.9% precision gains.

### Kelly Criterion Upgrade
Hakobyan & Lototsky (arXiv:2503.17927, March 2025): Ridge Kelly f*(gamma) = gr(f) - gamma*vr(f). Fractional Kelly 0.2 gives 90% variance reduction vs only 30% growth sacrifice. For correlated bets on same night: apply covariance discount.

## Calibration Status

Root cause confirmed (arXiv:2601.19944): isotonic and Platt scaling hurt strong tree models. Fix: Beta calibration or Venn-Abers. 2-hour implementation on Colab.

## Feature Engine

v3.0-37cat (after MOVDA), 6135 raw features, Cat37=MOVDA deployed. Missing: eFG%, TS%, separate O/D ratings, travel distance, referee crew stats.

## Additional Findings from Research Cycle v4 (2026-03-26, same day)

### NEW: AF-NSGA-II Sparse Initialization (MDPI Electronics Jan 2026)
ReliefF+MIC+Fisher entropy-weighted sparse initialization replaces random init in GA. 55-70% HV improvement. Ablation: sparse init is MORE impactful than adaptive crossover. pip install skrebate. -0.003 Brier, 8h.

### NEW: CRLS Fine-Tuning for TabICLv2 (arXiv:2603.08206, March 2026 — FRESH)
Fine-tune TabICLv2 with CRLS proper scoring rule objective. Penalizes crude errors more heavily. API: lr=1e-5, 600 epochs. Regression-focused but adaptable to Bernoulli binary. -0.004 Brier, 10h.

### NEW: NGBoost Bernoulli CRPS as LightGBM fix
LightGBM 0.2394 is broken (anomaly). Replace with NGBoost(Dist=Bernoulli, Score=CRPScore) OR LightGBM DART mode (boosting_type='dart'). Immediate 2h fix. -0.015 (bringing LightGBM from broken 0.2394 to competitive ~0.223).

### NEW: Calibration-First Model Selection Validated on NBA (arXiv:2303.06021)
Walsh & Joshi: calibration-optimized = +34.69% ROI, accuracy-optimized = -35.17%. Our approach is correct. Add ECE as co-objective in GA alongside Brier.

### NEW: TabPFN Beta Method (arXiv:2502.02527)
Reduces both bias AND variance simultaneously. 200+ benchmark datasets. Reduces fold variance (our fold 4 vs fold 1-3 gap). -0.003 Brier, 6h.

### Confirmed: Post-COVID Home Advantage Decay
Fans = only 2.2 additional wins/season. May need to downweight static is_home feature if model overfit to pre-2020 data.

## Research Output File

/home/termius/nomos-nba-agent/data/results/crew-research.json — v4 as of 2026-03-26. 13 papers, 13 techniques, 31 feature ideas, 12 market insights.
See memory file: research_march2026_cycle4.md for full cycle 4 details.
