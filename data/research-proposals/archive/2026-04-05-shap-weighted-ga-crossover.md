# SHAP-Weighted GA Crossover for Feature Selection

**Date:** 2026-04-05  
**Source:** PMC12357926 (stacked ensemble NBA prediction) + Nature s41598-025-13657-1  
**Priority:** HIGH — could close 0.002–0.005 Brier gap  
**Cycle:** Brain cycle 65 (every-other-cycle research)

## Problem

Current GA crossover is uniform: any feature from parent A or parent B is equally likely to be inherited. This ignores the signal that some features are consistently high-importance across diverse individuals and should be preserved.

Observation: S15 (extra_trees, wide search) reaches best_brier=0.22098 with 64 features. The PMC study found that `home_next`, `team_elo_5_y`, and `team_elo` are the 3 highest-importance features across ALL model types — suggesting that certain features should have protected status in crossover.

## Proposed Fix

**SHAP-biased crossover**: During crossover, compute SHAP importance for each feature in the population's top-10 individuals. Features ranked in the top-20% of SHAP importance receive a 2× higher probability of being inherited from the better parent.

```python
# In evolution/genetic_loop.py — crossover function
def shap_biased_crossover(parent_a, parent_b, shap_importance_scores, bias_factor=2.0):
    """
    Features with SHAP rank in top-20% get bias_factor more likely to come from better parent.
    parent_a = better performer (lower Brier)
    """
    child_features = []
    sorted_feats = sorted(shap_importance_scores.items(), key=lambda x: -x[1])
    top_20pct = set(f for f, _ in sorted_feats[:int(len(sorted_feats) * 0.2)])
    
    for feat in all_feature_candidates:
        in_a = feat in parent_a.features
        in_b = feat in parent_b.features
        if in_a == in_b:
            child_features.append(feat) if in_a else None
        else:
            # Biased coin flip
            if feat in top_20pct:
                p_from_a = bias_factor / (1 + bias_factor)  # 0.667 if bias=2.0
            else:
                p_from_a = 0.5
            if random.random() < p_from_a:
                if in_a: child_features.append(feat)
            else:
                if in_b: child_features.append(feat)
    return child_features
```

## SHAP Computation Schedule

Run SHAP on the top-10 Pareto individuals every 10 generations. Cache in `evolution_state['shap_scores']`. Cost: ~5-15 seconds per SHAP run on CPU (tree shap is O(n_features²) but fast for <200 features).

```python
if generation % 10 == 0:
    top_individuals = pareto_front[:10]
    shap_scores = compute_shap_importance(top_individuals, X_val, y_val)
    evolution_state['shap_scores'] = shap_scores
```

## Expected Impact

- From PMC study: teams with `home_next` + `team_elo_5_y` features 3–5% better calibration
- Estimated Brier improvement: **-0.002 to -0.005** (conservative)
- Risk: slight loss of diversity if bias is too strong — mitigated by `bias_factor=2.0` (not a hard lock)

## Implementation Target

- File: `hf-space/evolution/genetic_loop.py` (all 6 islands)
- Also update: `nomos-nba-agent/evolution/genetic_loop.py` for parity
- Test on S15 (wide search) first — already has highest mutation so best balance

## Protected Feature Candidates (from PMC + our own runs)

Based on S15 best individual (extra_trees, gen 1, Brier 0.22098):
1. Home court advantage features (Cat6 or Cat10)
2. ELO-based rolling ratings (Cat17 advanced rolling)
3. Recent win streak / momentum (Cat5)
4. Opponent-adjusted efficiency differentials (Cat7)
5. Rest differential (Cat6)

## Cross-Project Note

Political Alpha can use the same technique for its Cat3 market features (momentum features consistently important across models per the insider trading literature).

---
**Status:** PROPOSED  
**Next step:** Implement in `hf-space/evolution/genetic_loop.py` on S15 first  
**Estimated effort:** 2–3 hours engineering
