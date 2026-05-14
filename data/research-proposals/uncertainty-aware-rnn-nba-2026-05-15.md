# Research Proposal: Uncertainty-Aware RNN with Monte Carlo Dropout for NBA Prediction

**Detected:** fire-112 EVEN cycle WebSearch  
**Date:** 2026-05-15  
**Priority:** HIGH  
**Source:** MDPI Information 17(1):56, January 2026  
**URL:** https://www.mdpi.com/2078-2489/17/1/56  

## Finding

A January 2026 paper introduces an uncertainty-aware forecasting framework for NBA game outcomes:
- **Architecture:** Recurrent neural network (RNN) backbone + Monte Carlo (MC) dropout for calibrated uncertainty quantification
- **Features:** team-level performance metrics + rolling-form indicators + spatial shot-chart embeddings
- **Evaluation:** Brier score, log-loss, AUC, ECE/MCE calibration metrics
- **Key result:** LR and XGBoost achieve **Brier ~0.20** on 2024 season (their baseline)
- **GPU target:** RNN+MC-dropout achieves further improvement below 0.20

Separate finding: CNN model achieves Brier **0.221** on NBA outcomes (MDPI Computation 2026).

## Relevance to Fleet

| Model | Brier | Notes |
|-------|-------|-------|
| Our fleet best (S15 GA) | 0.22012 | CPU tree-based, 9551 games |
| S15 Pareto candidate (fire-112) | **0.21896** | ET 200f, CONFIRMED 2nd fire |
| CNN (2026 SOTA) | 0.221 | GPU, beats our old fleet best |
| LR/XGBoost baseline (2026 SOTA) | **~0.20** | Tree-based/linear — matches our approach |
| RNN+MC-dropout (2026 SOTA) | < 0.20 | GPU required |

Critical: the SOTA LR/XGBoost baseline (~0.20) is achievable with our approach. The gap from 0.22012 → 0.20 is ~0.02 Brier points — within reach by adding rolling-form indicators and shot-chart spatial features.

## Actionable Recommendations

### Immediate (CPU islands, no GPU needed)
1. **Confirm LR in all islands** (vm-add-logistic-regression-model-pool, priority=50) — S13 has LR confirmed; add to S14/S15/S18/S22 + all 5 POL islands. This paper reconfirms LR Brier~0.20 is achievable.
2. **Rolling-form indicators** — audit engine.py for rolling win%, rolling ATS%, rolling Brier from last N games. Add if missing (likely already in 7213 features).
3. **Spatial shot-chart zone features** — NEW category. Add shooting zone percentages (paint/mid-range/3pt by zone) as feature category to engine.py. Our engine currently lacks zone-level shot distribution.

### GPU-only target (Kaggle/Colab)
4. **RNN+MC-dropout experiment** — Train PyTorch RNN with dropout=0.3, MC sampling N=50 at inference. Target: Brier < 0.20 on 9551-game holdout. Calibration output: ECE/reliability diagrams for Kelly sizing.
5. **Uncertainty → Kelly** — MC dropout gives predictive uncertainty per game. High-uncertainty games → reduce Kelly fraction. Low-uncertainty → increase. Cross to NBA TF Kelly override formula.

### Feature engineering (engine.py)
6. **Shot chart zones:** Add `shot_zone_pct_restricted_area`, `shot_zone_pct_mid_range`, `shot_zone_pct_corner_3`, `shot_zone_pct_above_break_3` per team per game window (5/10/20 game rolling). Estimated +12-16 features per team = +24-32 per game.
7. **Rolling-form momentum:** If not present — add rolling 5/10/20 game win-streak, cover-streak, Brier trend (rolling prediction error from oracle).

## Cross-Port to Political

- The uncertainty quantification approach (MC dropout → calibrated probabilities) is directly applicable to political prediction.
- Political feature engineering analog: rolling polling accuracy, rolling model Brier — already may be in political_engine.py (blocked by placeholder).

## Expected Impact

- LR confirmed: should reduce fleet best from 0.22012 toward 0.215-0.220 with proper rolling features
- Shot-chart zones: estimated -0.005 to -0.010 Brier improvement (new signal category)
- RNN+MC-dropout (GPU): path to < 0.20 (5+ Brier points improvement from fleet best)

## Status
- [ ] vm-add-logistic-regression-model-pool (P50) — assign to all islands  
- [ ] Shot-chart zone feature design — add to engine.py backlog  
- [ ] GPU experiment: RNN+MC-dropout — Kaggle session  
