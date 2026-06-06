# SOTA: When Individually Calibrated Models Become Collectively Miscalibrated

> fire-283 ODD | arXiv:2605.18858 | Priority=124 | 2026-06-07T00h

## Paper

**"When Individually Calibrated Models Become Collectively Miscalibrated"**
arXiv:2605.18858 (May 2026)

## Key Finding

Even when each island model is individually calibrated (e.g., via isotonic regression or Venn-Abers), their ensemble aggregate can be **systematically miscalibrated** under heterogeneous data distributions. This is not a corner case — it's the expected outcome when:
- Island models are trained on non-i.i.d. data (different evo epochs, different feature subsets)
- Islands use heterogeneous model families (ET, RF, XGB, LGB, CatBoost)
- Islands have different calibration set sizes (S22 has fewer games in calibration window than evo4)

**Root cause**: Equal-weight averaging of heterogeneous calibrated predictors destroys marginal calibration even when each predictor is individually calibrated. The aggregate ECE can be 1.5-3× the individual island ECE.

**Fix**: Brier-score-weighted aggregation replaces equal-weight averaging. The optimal weights minimize aggregate ECE over the convex hull of individual model outputs.

## Direct Relevance to Nomos42 Fleet

Our current predict_today.py uses equal-weight rank fusion across 4+ active islands (S18, S22, evo4, evo5). Each island reports its own brier/ECE, but we never audit the **aggregate** calibration. Given:
- S22 ET-0.2191 (Rule8-CLEAN) vs S18 (stacking-contaminated RULE8 VIOLATION)
- evo4 RF-0.22007 (RULE8-CLEAN) vs evo5 (stacking-contaminated)
- Islands at different cycle counts (S18 c~1011 vs S22 c~497) = different distribution windows

The equal-weight fusion in predict_today.py is almost certainly producing collective miscalibration even if each island passes its individual calibration audit.

## Implementation Plan

### Application 1: Aggregate ECE Audit in predict_today.py (~40 lines)
```python
# calibration/collective_miscalibration.py
from netcal.metrics import ECE
import numpy as np

def audit_collective_calibration(island_probs, island_briers, y_true, n_bins=10):
    """
    Detect collective miscalibration in multi-island ensemble.
    
    Args:
        island_probs: dict {island_id: np.array of probabilities}
        island_briers: dict {island_id: float brier score}
        y_true: np.array ground truth labels
    
    Returns:
        individual_ece: dict per-island ECE
        aggregate_ece_equal: float ECE of equal-weight aggregate
        aggregate_ece_brier_weighted: float ECE of Brier-weighted aggregate
        collective_miscalibration_score: float ratio (aggregate/avg_individual)
    """
    ece = ECE(n_bins)
    individual_ece = {isl: ece.measure(probs, y_true) 
                     for isl, probs in island_probs.items()}
    
    # Equal-weight aggregate
    equal_agg = np.mean(list(island_probs.values()), axis=0)
    aggregate_ece_equal = ece.measure(equal_agg, y_true)
    
    # Brier-score-weighted aggregate (lower Brier = higher weight)
    weights = {isl: 1.0 / brier for isl, brier in island_briers.items()}
    total_w = sum(weights.values())
    brier_agg = sum(w/total_w * island_probs[isl] 
                   for isl, w in weights.items())
    aggregate_ece_brier_weighted = ece.measure(brier_agg, y_true)
    
    avg_individual_ece = np.mean(list(individual_ece.values()))
    collective_score = aggregate_ece_equal / max(avg_individual_ece, 1e-6)
    
    return {
        'individual_ece': individual_ece,
        'aggregate_ece_equal': aggregate_ece_equal,
        'aggregate_ece_brier_weighted': aggregate_ece_brier_weighted,
        'collective_miscalibration_score': collective_score,
        'alert': collective_score > 1.5  # trigger if aggregate > 1.5x individual
    }
```

### Application 2: Add `collective_miscalibration_score` to /api/export
Add to the export response body in both NBA TF app.py:
```json
{
  "collective_miscalibration_score": 1.2,
  "aggregate_ece_equal": 0.045,
  "aggregate_ece_brier_weighted": 0.031,
  "alert": false
}
```
Gate: if score > 1.5 → flag as COLLECTIVE_MISCALIBRATION_ALERT in health-status.json.

### Application 3: Replace equal-weight fusion in predict_today.py (~15 lines)
```python
# predict_today.py — replace equal-weight rank fusion with Brier-weighted
def fuse_island_predictions(island_results):
    """Brier-score-weighted fusion per arXiv:2605.18858."""
    weights = {isl: 1.0 / max(res['best_brier'], 0.001) 
               for isl, res in island_results.items() 
               if res.get('best_brier')}
    total = sum(weights.values())
    fused = {game_id: sum(weights[isl]/total * res['predictions'][game_id] 
                         for isl, res in island_results.items() 
                         if game_id in res['predictions'])
             for game_id in all_game_ids}
    return fused
```

### Application 4: Port to political_engine.py (~20 lines)
Same Brier-weighted fusion for POL islands P4/P5/P7 ensemble in predictions.
Priority: after priority=123 (PFWCP personalized CP), alongside priority=124 (this paper).

## Library Dependencies
```bash
pip install netcal properscoring  # both already in requirements.txt (fire-240 pipeline)
```
No new dependencies needed.

## Integration Gate
1. Implement AFTER fire-282 VM tasks (checkpoint ET-0.2191 + RF-0.22007 first)
2. do_not_push_hf_space_yet — implement locally, DO NOT push to HF Spaces
3. Test: aggregate_ece_brier_weighted < aggregate_ece_equal (verify improvement)
4. Alert threshold: collective_miscalibration_score > 1.5 → flag in health-status.json

## Expected Improvement
- 0.001-0.002 Brier in production ensemble
- Correct aggregate calibration under heterogeneous island distributions
- Especially impactful when RULE8-violating islands (S18, evo5) are excluded from fusion
  — current equal-weight averaging *includes* their miscalibrated outputs

## Work Queue Item
`vm-research-collectively-miscalibrated-fire283` (priority=124)

## Connection to Axelrod Mechanisms
The `collective_miscalibration_score` is a natural addition to `COMMON_KNOWLEDGE[D]` in Axelrod Mech A's day-end broadcast. Each TF agent learns not just individual island quality but ensemble-level calibration health. High collective miscalibration → agents down-weight islands with heterogeneous distributions.
