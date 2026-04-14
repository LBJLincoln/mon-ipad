# NBA Research Proposal: Uncertainty-Aware Calibration + Shot Quality Proxies
**Cycle:** 100 | **Date:** 2026-04-14 | **Priority:** HIGH

## Research Basis
WebSearch results from 2025-2026 literature identify two actionable improvements:
1. **Uncertainty-Aware ML** (MDPI 2025, DOI: 2078-2489/17/1/56) — calibrated probability intervals improve Brier score
2. **Shot Quality Proxies** (no GPU required) — True Shooting %, paint/perimeter split differentials

## Proposed Improvements

### A. Conformal Prediction Calibration (Priority 1)
**Problem:** Current calibration (isotonic, Platt, Venn-Abers) applied per-model. Fleet lacks unified calibration strategy.
**Proposal:** Implement conformal prediction intervals using split conformal method:
```python
# In calibration layer of island code:
def conformal_calibrate(probs, y_calib, alpha=0.1):
    """Split conformal calibration for probability outputs."""
    scores = np.abs(y_calib - probs)  # nonconformity scores
    threshold = np.quantile(scores, 1 - alpha)
    return np.clip(probs, threshold, 1 - threshold)  # calibrated bounds
```
**Expected Brier Impact:** 0.001-0.003 reduction (literature shows 10-15% calibration improvement)
**Implementation Target:** Island init/evaluation loop (CPU-compatible)

### B. Shot Quality Proxies as Features (Priority 2)
**Problem:** Engine has per-100 stats but lacks shot *quality* differential between teams
**Proposal:** Add to Cat 56 (new category):
- `true_shooting_diff` = home_TS% - away_TS% (TS% = pts / (2 × (FGA + 0.44×FTA)))
- `paint_shot_rate_diff` = home_paint_FGA/FGA - away_paint_FGA/FGA
- `free_throw_rate_diff` = home_FTA/FGA - away_FTA/FGA (proxy for rim pressure)
- `three_point_attempt_rate_diff` = home_3PA/FGA - away_3PA/FGA
- `effective_fg_pct_diff` = home_eFG% - away_eFG% (eFG = (FGM + 0.5×3PM)/FGA)
**Data Source:** Already in engine (cat 3: PACE & EFFICIENCY, cat 4: SCORING PROFILE)
**Approach:** These features are computable from existing data — just need explicit differential features
**Expected Brier Impact:** 0.001-0.002 (marginal, but diversifies feature set)

### C. ELO Decay Features (Priority 3)
**Problem:** Current ELO in Cat 24 (POWER RATING COMPOSITES) uses static multi-Elo. No temporal decay.
**Proposal:** Add time-decay ELO: `elo_decay(t) = elo_initial * exp(-lambda * t)` where t = games played since peak
- Captures teams that peaked mid-season (trade deadline effects)
- `elo_peak_decay_diff` = how far each team is from their season peak
**Expected Brier Impact:** 0.001 (small but novel signal)

## Recommendation
Implement A (Conformal Calibration) first. It's a calibration-layer change that can be tested in a fork.
B and C are feature engine additions — defer to cycle 101 after A is validated.

## Sources
- [Uncertainty-Aware ML for NBA Forecasting](https://www.mdpi.com/2078-2489/17/1/56)
- [SHAP + XGBoost NBA Analysis](https://pmc.ncbi.nlm.nih.gov/articles/PMC11265715/)
- [AI Techniques Systematic Review](https://pmc.ncbi.nlm.nih.gov/articles/PMC12200876/)
