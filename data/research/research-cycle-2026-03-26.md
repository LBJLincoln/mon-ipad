# Research Cycle — March 26, 2026

## Agents: 5 parallel (repo-scout, research-analyst, evolution-optimizer, market-analyst, feature-engineer)

## CRITICAL FINDINGS

### 1. CALIBRATION IS HURTING US (arXiv:2601.19944)
- Isotonic regression DEGRADES Brier for tree ensembles: +0.0034 worse
- Replace with Beta calibration (`pip install betacal`) or Venn-Abers (`pip install venn-abers`)
- **Expected: -0.003 Brier | Effort: 2h | PRIORITY: IMMEDIATE**

### 2. FEAT=200 UNIVERSAL TAKEOVER (Evolution Optimizer)
- 5/6 islands have 100% of population at feat=200
- Selection bias: feat=200 inflates in-sample ROI/Sharpe, wins tournament selection
- S14 best (0.22093, 67 feat) was displaced by worse feat=200 individuals (0.2252)
- S13 is only island not captured (72% feat=200), only one improving
- **FIX: Add Pareto penalty for n_features > 150 in NSGA-II**

### 3. AF-NSGA-II ADAPTIVE CROSSOVER (MDPI Electronics Jan 2026)
- Sparse initialization from sklearn filters (MI, chi2, f_classif)
- Adaptive crossover: when Hamming similarity > 0.90, switch to block-swap
- Directly fixes population health / convergence issue
- **Expected: -0.003 Brier | Effort: 6h | Deploy to S15 first**

### 4. DISTRIBUTIONAL REGRESSION (arXiv 2603.08206v2)
- binary:logistic ≠ Brier optimization in finite samples
- CRLS objective for TabPFN fine-tuning
- **Expected: -0.003 Brier | Effort: 6h (Colab)**

### 5. NEW FEATURES TO ADD
- Separate O-rating + D-rating (net_rating loses info)
- Travel distance + timezone shift (every 500km = ~4% win prob reduction)
- eFG% and TS% rolling features (SHAP-validated)
- Referee crew stats (2-3h before tipoff)
- MOVDA delta_MOV residual features

## TIER 0 COMBINED POTENTIAL: -0.009 Brier → ~0.2097 (BELOW 0.21!)

## ACTIONS TAKEN
- S10: config push (mut 0.05→0.09)
- S11: 3 experiments submitted (#2533, #2534, #2535)
- S15: recommended restart with seeded S13 individual
- S11/S12/S13: Supabase credentials need fix

## REPOS FOUND
- georgedouzas/sports-betting — pip installable, value bet detection
- pselamy/polymarket-insider-tracker — DBSCAN clustering for whale detection
- LeMGarouani/XStacking — SHAP meta-features for stacking
- betacal (PyPI) — Beta calibration, direct replacement for isotonic
- venn-abers (PyPI) — Probability intervals with finite-sample guarantees
