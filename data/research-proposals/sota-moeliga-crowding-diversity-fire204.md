# SOTA: MOELIGA — Crowding-Based Fitness Sharing for MOEA Feature Selection

**Source:** arXiv:2603.20934 (March 2026)
**Fire:** 204 (EVEN)
**Priority:** 97
**Work-queue ID:** vm-research-moeliga-fire204

## Problem This Solves

Our islands repeatedly show Pareto front shrinkage between resets:
- S22: pareto 48 → 13 → 20 → 11 → 9 → 15 → 10 (fire-204)
- S18: pareto 16 → 12 → 9 → 16 → 10 → 8 (fire-204)

This indicates the GA loses Pareto diversity through selection pressure and resets.
The current Pareto non-domination sort does not actively penalize clustering.

## MOELIGA Key Innovations

1. **Crowding-based fitness sharing**: Penalizes solutions too close in objective space,
   maintaining spread across the Pareto front.
2. **Sigmoid transformation**: Enhances diversity by redistributing fitness pressure
   across objective dimensions non-linearly.
3. **Local improvement step**: Hybrid local search per Pareto individual after each
   generation — improves each elite without full re-evaluation.
4. **Result**: Identifies smaller feature subsets with superior classification performance
   across 14 benchmark datasets vs NSGA-II and standard MOEA baselines.

## Application to Our Fleet

### Immediate (S18 + S22, active islands)
- Add **crowding distance** as a tie-breaker in the Pareto non-domination sort inside
  `evaluate_individual()` (or post-selection in `run_island_evolution()`).
- This penalizes overrepresentation in one region of (Brier, ROI, Sharpe) space.
- Expected: prevents pareto collapse (15→10→8 pattern); retains diverse candidates.

### Medium-term (all islands on wake)
- Add sigmoid-transformed fitness sharing coefficients to mutation probability:
  solutions in dense Pareto regions get higher mutation rates.
- Port to `political_engine.py` for POL islands.

## Implementation Sketch

```python
# In app.py island evolution loop, after Pareto ranking:
def crowding_distance(pareto_front, objectives=["brier", "roi", "sharpe"]):
    """NSGA-II style crowding distance for Pareto front maintenance."""
    n = len(pareto_front)
    if n < 3:
        return [float('inf')] * n
    distances = [0.0] * n
    for obj in objectives:
        vals = sorted(range(n), key=lambda i: pareto_front[i][obj])
        distances[vals[0]] = distances[vals[-1]] = float('inf')
        obj_range = pareto_front[vals[-1]][obj] - pareto_front[vals[0]][obj]
        if obj_range == 0:
            continue
        for i in range(1, n-1):
            distances[vals[i]] += (
                pareto_front[vals[i+1]][obj] - pareto_front[vals[i-1]][obj]
            ) / obj_range
    return distances

# Keep top-K from Pareto front by crowding distance (prefer spread)
def select_pareto_diverse(pareto_front, k):
    dists = crowding_distance(pareto_front)
    ranked = sorted(range(len(pareto_front)), key=lambda i: -dists[i])
    return [pareto_front[i] for i in ranked[:k]]
```

## Connection to Our Findings

- S22 `top_pareto_solutions.best_brier=0.21873` (fire-204): a below-fleet-best ET model
  survived despite performance cliff. This is EXACTLY crowding distance at work —
  ET explores a different region of objective space from LightGBM/RF clusters.
- MOELIGA crowding would formalize this: explicitly preserve ET/LR/LightGBM diverse
  representatives rather than relying on accidental survival.
- Validates why Pareto front shrinks when stacking dominates (stacking clusters in
  high-Brier low-ROI region → crowding penalty would diversify away from it).

## Expected Improvement

- More stable Pareto front size (avoid 15→10→8 oscillation)
- Better exploration → higher probability of finding sub-0.22012 models
- Estimate: +3-6 stable Pareto individuals per fire on average
- Pareto min candidate retention improved (key for fleet-best detection)

## Interaction with Rule #8 (No Stacking)

Crowding distance would naturally suppress stacking if stacking models cluster
in the same Brier/ROI/Sharpe region — the crowding penalty would reduce their
fitness relative to diverse alternatives (ET, LightGBM, RF) that spread the front.
This provides an indirect evolutionary pressure against monoculture stacking.

## References
- arXiv:2603.20934: MOELIGA (March 2026)
- NSGA-II: Deb et al. (2002) — foundational crowding distance
- Related proposal: arXiv:2501.14310 (Jan 2025) — permutation-based MOEA feature
  selection (PSEFS-MOEA) — complementary approach using permutation operators
