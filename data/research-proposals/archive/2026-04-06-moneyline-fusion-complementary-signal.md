# NBA Research Proposal: Moneyline Implied Probability Fusion as Protected Feature

**Date:** 2026-04-06  
**Source:** MDPI Jan 2026 — "Uncertainty-Aware Machine Learning for NBA Forecasting in Digital Betting Markets"  
**Priority:** HIGH — directly addresses Brier gap from 0.22x to <0.21  
**Type:** Feature Engineering + Calibration  

## Finding

The MDPI 2026 paper demonstrates that **market and non-market information carry complementary predictive content**. When closing moneyline implied probabilities (isotonic-regression calibrated) are added as a feature to non-market ML models, the fused model achieves the strongest overall performance — outperforming either source alone.

Key: an isotonic-regression calibration of implied probabilities from closing moneylines represents the "best-possible probabilistic forecaster using only market information." Combining it with our feature-engineered GA model yields synergistic gains.

## Proposed Action

### 1. Add Closing-Line Implied Probability as Protected Feature Candidate

In `features/engine.py` Category 3 (Market/Odds features), add:

```python
# Closing moneyline implied probability (isotonic-calibrated)
# Source: odds_analyzer.py closing_line_home / closing_line_away
cl_home_raw = odds.get("closing_line_home_prob", 0.5)
cl_away_raw = odds.get("closing_line_away_prob", 0.5)

# Vig-adjusted (remove overround)
cl_total = cl_home_raw + cl_away_raw
cl_home_adj = cl_home_raw / cl_total if cl_total > 0 else 0.5
cl_away_adj = cl_away_raw / cl_total if cl_total > 0 else 0.5

features.append(cl_home_adj); names.append("mkt_closing_line_home_adj")
features.append(cl_away_adj); names.append("mkt_closing_line_away_adj")

# Log-odds of closing line (better for ML)
cl_logit = math.log(cl_home_adj / (1 - cl_home_adj + 1e-9))
features.append(cl_logit); names.append("mkt_closing_line_logit")

# Line movement: closing vs opening (sharp money signal)
op_home_raw = odds.get("opening_line_home_prob", cl_home_raw)
line_move = cl_home_adj - (op_home_raw / (op_home_raw + (1 - op_home_raw)))
features.append(line_move); names.append("mkt_line_movement")
features.append(abs(line_move)); names.append("mkt_abs_line_movement")
features.append(1 if abs(line_move) > 0.05 else 0); names.append("mkt_significant_move_flag")
```

### 2. Make Closing Line a Protected Feature

In the GA config, mark `mkt_closing_line_home_adj` and `mkt_closing_line_logit` as protected features that survive crossover/mutation without risk of dropping. They should always be present in every candidate.

### 3. Calibration: Post-hoc Isotonic on Closing Line

In `calibration/conformal.py`, after final model training, apply isotonic regression to the closing line implied probability to generate a calibrated reference prior, then blend:

```python
# blend_weight learned on val set
prob_fused = alpha * model_prob + (1 - alpha) * calibrated_market_prob
```

## Expected Impact

Based on MDPI 2026 benchmarks:
- Baseline (non-market features only): Brier ~0.222–0.231 (our current fleet range)
- Market features (calibrated moneyline only): Brier ~0.215–0.218
- **Fused model**: Brier **< 0.21** (matches logistic regression baseline of 0.199 from paper)

This is the single most promising path to break the 0.21837 checkpoint threshold.

## Files to Modify

1. `features/engine.py` — add Cat47+ closing-line features (6 new features)
2. `hf-space/features/engine.py` — PARITY (same change required)
3. `calibration/conformal.py` — add market prior blending
4. `ops/odds_analyzer.py` — ensure closing_line_home_prob is stored in game records

## Implementation Complexity: LOW (1 file change + parity)

## References

- [Uncertainty-Aware Machine Learning for NBA Forecasting in Digital Betting Markets](https://www.mdpi.com/2078-2489/17/1/56) — MDPI 2026
- [Integration of XGBoost and SHAP for NBA prediction](https://pmc.ncbi.nlm.nih.gov/articles/PMC11265715/) — PMC 2024
- [Stacked ensemble model for NBA game outcome prediction](https://www.nature.com/articles/s41598-025-13657-1) — Scientific Reports 2025
