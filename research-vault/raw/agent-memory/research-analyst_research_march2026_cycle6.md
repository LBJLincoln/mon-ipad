---
name: Research Cycle 6 — State-of-Art NBA Prediction Deep Sweep
description: March 28 2026 cycle 6: Montrucchio 2026 shot-chart NBA paper (Brier 0.199), Brier loss training, 5y-Elo, Venn-Abers, referee features, Kelly tournament ensemble, Brier-to-ROI framework
type: project
---

# Research Cycle 6 — March 28 2026
## Focus: What is state-of-art and how far are we?

## KEY FINDING: Academic State-of-Art is Brier 0.199-0.202 (non-market)

Best published NBA prediction paper (2026):
- **Montrucchio, Barbierato, Gatti (2026)** — "Uncertainty-Aware Machine Learning for NBA Forecasting in Digital Betting Markets"
- Published: January 8, 2026, Information (MDPI), doi:10.3390/info17010056
- LR Brier=0.199, XGBoost Brier=0.202 on 2024 test season
- Key differentiator: shot-chart CNN embeddings (48x48 grid, 3 conv blocks, 128-dim, PCA to 20 components)
- Training ≤2022, val=2023, test=2024 (strict chronological split)
- EV>1.1 threshold + 0.3-Kelly, moneylines only generate profit
- **Our ATR=0.2157 is only 0.0157 behind best published non-market result**

## Brier-to-ROI Framework (no closed-form, but reference points exist)
- Random baseline: Brier=0.250, ROI=-4.5%
- Academic trees (best public): Brier=0.221, ROI=-1% to +2%
- Our system (TabICL 110f): Brier=0.2157, ROI=+2% to +5% estimated
- Montrucchio XGBoost + shot charts: Brier=0.202, ROI=+3% to +6%
- Closing line (market): Brier≈0.195, ROI=0% by definition
- ESPN BPI: Brier=0.075 BUT uses closing line as input (circular, not a fair benchmark)
- **Key insight: game selection matters more than global Brier. Bet only where model diverges from market by >5% AND model is more accurate**

## Priority Action List (ranked)
1. **Brier loss training objective** for XGBoost in Karpathy loop (-0.002, 2h) — Habib 2025 + Walsh & Joshi 2024
2. **Shot-chart xEFG features (Cat38)** via nba_api ShotChartDetail (free data) (-0.003, 8h) — Montrucchio 2026
3. **5-year decay Elo** (h_elo_5y, a_elo_5y) — SHAP #2 most important feature (-0.002, 3h) — Alves & Barbosa 2025
4. **Ridge-Kelly portfolio** for multi-game nights with cvxpy (ROI +2.5%, 5h)
5. **Venn-Abers calibration** (pip install venn-abers) (-0.001, 1h) — arXiv:2502.05676
6. **Referee features** from Covers.com + NBA L2M reports (-0.001, 6h)
7. **Kelly bankroll-weighted ensemble** (Beuoy 2026, arXiv:2602.09982) (-0.002, 5h)

## Cumulative Expected Improvement
- Conservative (50% realization): -0.0065 → Brier 0.2092
- Full realization: -0.013 → Brier 0.2027
- Breaking 0.200 requires shot-chart + Brier loss + 5y-Elo all delivering simultaneously

## New Papers Found
- Alves & Barbosa (Oct 2025, Computation MDPI): NBA/WNBA ML, CNN Brier=0.221, team_elo_5_y is SHAP #2 feature
- Rios et al. (Dec 2025, arXiv:2512.08591): Long-sequence LSTM NBA, 72.35% accuracy, 9840-game dataset
- Habib (Aug 2025, arXiv:2508.02725): NCAA LSTM with Brier loss = 0.1589 (best non-market basketball Brier found)
- Beuoy (Feb 2026, arXiv:2602.09982): Kelly as Bayesian model evaluation, Kelly >> Brier at detecting wrong models
- Van der Laan & Alaa (Feb 2025, arXiv:2502.05676): Generalized Venn-Abers with finite-sample calibration guarantees
- Belasen et al. (2025, SAGE Sports Econ): NBA referee L2M report analysis, home bias reduced but measurable

## Why: The gap from 0.2157 to 0.200 requires new FEATURES not better models
- Best academic model architecture is already XGBoost/LR (same as our system)
- The differentiator in Montrucchio 2026 is shot-chart spatial features
- Long-sequence LSTM adds temporal depth but Montrucchio found LSTM < XGBoost on Brier
- Conclusion: feature engineering (shot quality, 5y-Elo, referee) is the path, not architecture change
