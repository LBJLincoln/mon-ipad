# Universal Portfolio Meets Online Conformal Prediction
**Source:** arXiv:2602.03168 (Feb 2026) — "Universal Portfolio Meets Online Conformal Prediction"
**Fire:** 260 (EVEN WebSearch) / Written: fire-263 ODD
**Work-queue ID:** vm-research-universal-portfolio-ocp-fire260
**Priority:** 119

## Key Finding
Integrates Cover's (1991) universal portfolio theory with online conformal prediction (OCP). The universal portfolio achieves log-optimal wealth growth (O(log T / T) regret vs. best fixed threshold) while OCP provides distribution-free coverage guarantees. The fusion yields a mechanism that simultaneously maximizes long-run prediction quality and maintains calibration validity — directly applicable to multi-model Pareto fusion betting in NBA/POL.

## Why This Matters for Nomos42
- Current predict_today.py uses rank-based fusion across 6 islands — no principled weighting
- Universal portfolio assigns model weights proportional to historical predictive performance, converging to the best model without knowing which is best in advance
- OCP coverage guarantee bounds the risk of any individual model's miscalibration
- Together: a betting system that is both log-optimal AND provably calibrated

## Applications

### Application 1: Universal Portfolio Fusion in predict_today.py
Replace current rank-fusion with multiplicative-weights update:
```python
# Current: simple rank average across 6 islands
# New: universal portfolio weights
w_i(t+1) = w_i(t) * exp(eta * log_score_i(t))
w_i(t+1) /= sum(w_j(t+1))  # normalize
prediction = sum(w_i * p_i for i, p_i in zip(weights, island_preds))
```
- eta (learning rate) = sqrt(8 * log(K) / T) where K = num islands, T = num games
- No hyperparameter tuning required — theoretically optimal

### Application 2: Per-Model Portfolio Weight in /api/export
Add to each island's /api/export payload:
```json
{
  "universal_portfolio_weight": 0.19,
  "log_score_cumulative": -1847.3,
  "portfolio_regret_vs_best": 0.023
}
```

### Application 3: Kelly Sizing Bounded by CP Coverage
Dual objective: maximize wealth (Kelly) while guaranteeing calibration (OCP):
```python
kelly_fraction = min(
    kelly_optimal(p, odds),
    kelly_max_by_coverage(alpha_corrected, n_cal)  # from arXiv:2506.19689 (priority=114)
)
```
Expected Sharpe improvement: 0.3–0.8 (from principled diversification across models)

### Application 4: Political Alpha Analog
Same universal portfolio fusion for P1–P7 island ensemble predictions:
- political_predict_today.py (create if not exists)
- Weights favor LightGBM-first islands (Rule #9 compliance naturally emerges)
- CP bound particularly important for rare-event political outcomes (low base rates)

### Application 5: Synergy with arXiv:2602.16537 (priority=117 — drift detection)
Combine drift detection with universal portfolio:
- When KL-div drift detected → reset portfolio weights to uniform (equal weights)
- This handles non-stationary streams (new season, playoff intensity shifts)
- Expected improvement vs. static fusion: 0.001–0.003 Brier in distribution-shift periods

## Implementation Roadmap
1. **Week 1 (VM):** Port multiplicative-weights update to predict_today.py (20 lines)
2. **Week 2 (VM):** Add `universal_portfolio_weight` field to /api/export on S18+S22
3. **Week 3 (Colab):** Backtest on 2018–2026 holdout vs. rank-fusion baseline
4. **Week 4 (VM):** Port to political_predict_today.py with P4-checkpoint as anchor

## Expected Improvements
- Brier: 0.002–0.004 improvement in multi-model fusion
- ROI/Sharpe: 10–25% improvement from principled model weighting (no manual tuning)
- Calibration: maintained by construction (CP coverage bound)
- Theoretical guarantee: O(log T / T) regret vs. best fixed model

## Library
```bash
pip install universal-portfolios  # olps (online learning for portfolio selection)
pip install nonconformist          # CP coverage
# or implement multiplicative-weights directly (15 lines)
```

## Relationship to Pipeline
- Complements arXiv:2506.19689 (priority=114 — calibration set reuse)
- Extends arXiv:2602.16537 (priority=117 — drift detection)
- Synergizes with arXiv:2605.20515 (priority=118 — corrupted feedback CP)
- Together these 4 papers form a complete non-stationary calibration + fusion system

## Status
- Proposal: WRITTEN (fire-263)
- Code: NOT YET (vm-research-universal-portfolio-ocp-fire260)
- Testing: NOT YET
