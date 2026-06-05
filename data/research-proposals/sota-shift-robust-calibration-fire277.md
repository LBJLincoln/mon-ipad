# SOTA: Shift-Robust Calibration for NBA Temporal Distribution Shift

**Fire**: fire-277 ODD | **Date**: 2026-06-06T00h | **Priority**: 120
**Paper**: arXiv:2603.06733 (Mar 2026) — "Calibrated Credit Intelligence: Shift-Robust and Fair Risk Scoring with Bayesian Uncertainty and Gradient Boosting"

---

## Key Finding

3-layer calibration pipeline reduces calibration error by ~15-30% under temporal distribution shift vs. static isotonic calibration:

1. **Bayesian neural risk scorer** — MC dropout uncertainty quantification (epistemic uncertainty)
2. **Fairness-constrained gradient boosting calibrator** — maintains ECE across temporal/contextual subgroups
3. **Shift-aware fusion layer** — weights models by inverse KL-divergence from current test distribution

The core insight: isotonic calibration fitted on regular-season data systematically miscalibrates on playoff games (different pace, rest, venue distribution). The shift-aware fusion layer detects this drift and re-weights accordingly.

---

## NBA Relevance

Current fleet problems mapped to paper findings:

| Fleet Issue | Paper Solution |
|------------|---------------|
| S22 ET-0.2191 validated on regular season → playoffs? | Layer 3: KL-div game-context weighting |
| evo4 RF-0.22007 back-to-back miscalibration | Layer 2: subgroup (back_to_back × venue) calibration |
| 45+ consecutive resets evicting fleet-best candidates | Layer 1: Bayesian uncertainty bands gate before promotion |
| S18 stacking domination masking ET-0.21974 | Layer 3: shift-flagged island down-weighting |
| predict_today.py equal-weight island fusion | Layer 3: replace with KL-div island weights |

---

## Application 1: Shift-Aware Island Fusion (predict_today.py)

Replace equal-weight rank-fusion with inverse-KL-divergence island weighting:

```python
from scipy.special import rel_entr
import numpy as np

def compute_kl_weight(island_train_dist: np.ndarray, game_context_dist: np.ndarray) -> float:
    """Weight island by inverse KL-div from its training distribution to today's game context."""
    eps = 1e-9
    kl = np.sum(rel_entr(game_context_dist + eps, island_train_dist + eps))
    return 1.0 / (kl + 1e-6)

def shift_aware_fusion(predictions: dict, island_dists: dict, today_game_features: np.ndarray) -> np.ndarray:
    """Fuse island predictions weighted by distribution proximity to today's games."""
    today_dist = extract_game_context_distribution(today_game_features)
    weights = {island: compute_kl_weight(dist, today_dist) for island, dist in island_dists.items()}
    total_w = sum(weights.values())
    weights = {k: v / total_w for k, v in weights.items()}
    return sum(weights[i] * predictions[i] for i in predictions)
```

**Implementation**: ~50 lines in `predict_today.py`. Only dependency: `scipy.special.rel_entr` (already installed).

---

## Application 2: Season-Phase Drift Metrics in /api/export

Add `shift_calibration_metrics` to export response:

```json
{
  "shift_calibration": {
    "regular_season_ece": 0.018,
    "playoff_ece": 0.031,
    "back_to_back_ece": 0.024,
    "away_game_ece": 0.022,
    "drift_magnitude_kl": 0.042,
    "shift_flag": "PLAYOFF_DRIFT_DETECTED",
    "recommended_weight_adjustment": -0.15
  }
}
```

This enables the cloud brain to flag islands with high `drift_magnitude_kl` and down-weight them in predict_today.py fusion automatically.

---

## Application 3: Bayesian Uncertainty Gate Before Fleet-Best Promotion

Before promoting S22 ET-0.2191 or evo4 RF-0.22007 as production fleet-best:

```python
from sklearn.calibration import CalibratedClassifierCV

def compute_bayesian_uncertainty(model, X_test, n_passes=100):
    """MC dropout uncertainty estimation (Layer 1 of pipeline)."""
    predictions = []
    model.train()  # Enable dropout
    for _ in range(n_passes):
        with torch.no_grad():
            predictions.append(model(X_test).sigmoid().cpu().numpy())
    mean_pred = np.mean(predictions, axis=0)
    uncertainty = np.std(predictions, axis=0)
    return mean_pred, uncertainty

# Gate: promote only if lower 95% CI still below fleet-best threshold
lower_ci = mean_pred - 1.96 * uncertainty
if np.mean(lower_ci) < FLEET_BEST_GATE:  # 0.22012
    promote_to_production(model)
else:
    log_warning("Uncertainty too high: model may not reliably beat fleet-best")
```

For sklearn RF/ET models: use bootstrap sampling (100 bag subsamples) as MC dropout analog.

---

## Application 4: POL Island Port

Political elections have extreme distribution shift between election types:
- Primary vs. general vs. runoff elections have fundamentally different competitive dynamics
- Presidential vs. midterm cycles differ in turnout, base rates, late-breaking momentum
- Special elections are extreme outliers (small N, high uncertainty)

```python
# political_engine.py shift-aware fusion
ELECTION_TYPE_DIST = {
    "primary": compute_feature_distribution(primaries_df),
    "general": compute_feature_distribution(generals_df),
    "runoff": compute_feature_distribution(runoffs_df),
}

def get_pol_island_weight(island_id, today_election_type):
    island_dist = ISLAND_TRAINING_DIST[island_id]
    today_dist = ELECTION_TYPE_DIST[today_election_type]
    return compute_kl_weight(island_dist, today_dist)
```

P4 LGB-0.2491 candidate validation: must pass shift-calibration test for general election context before production promotion.

---

## Implementation Plan

| File | Change | Lines | Dependencies |
|------|--------|-------|-------------|
| `predict_today.py` | compute_kl_weight() + shift-aware fusion | ~50 | scipy only |
| `hf-space/app.py` | shift_calibration_metrics to /api/export | ~20 | numpy only |
| `calibration/isotonic_calibrator.py` | bayesian_uncertainty_bands() wrapper | ~40 | sklearn |
| `features/political_engine.py` | election_type shift-aware calibration | ~30 | scipy |

Total: ~140 lines across 4 files. No new dependencies beyond existing scipy/sklearn stack.

---

## Expected Impact

- **0.001-0.002 Brier** vs. static isotonic calibration (from paper: 15-30% ECE reduction)
- **Largest gain**: late-season (playoff) predictions — training distribution diverges most here
- **Island weighting**: reduces miscalibration under heterogeneous island training sets
- **Synergy with fire-268 priority=124**: collective miscalibration paper provides ECE gate; this paper provides KL-div weights

---

## Synergies with Research Pipeline

| Priority | Paper | Synergy |
|---------|-------|---------|
| 123 | PFWCP per-island density ratio weighting | Layer 3 is complementary — PFWCP handles CP coverage, KL-div handles calibration |
| 124 | Collective miscalibration Brier-weighted fusion | Layer 2 is same concept — implement together |
| 106 | Multi-scale CP | Shift-aware calibration as additional temporal scale |
| 119 | Universal Portfolio OCP | Drift weights improve portfolio allocation quality |
| 131 | CP as Universal Calibration Standard | Layer 2 can wrap CP calibrator instead of GB |

---

## Work Queue Reference
- VM implementation: `vm-research-shift-robust-calibration-fire260` (priority=120)
- Cloud synthesis: this document (fire-277 ODD, 2026-06-06T00h)
- Next step: VM implements compute_kl_weight() in predict_today.py (~50 lines)
