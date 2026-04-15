# Cross-Island Pareto Front Knowledge Distillation
**Date:** 2026-04-15
**Status:** proposed
**Author:** brain[4h] cycle 2026-04-15T16:00Z
**Priority:** HIGH — potential 0.003–0.005 Brier improvement

## Problem

All 6 NBA islands evolve independently, occasionally migrating 3 individuals every 3 generations. The Pareto front on each island contains 9–23 top solutions, but the **cross-island Pareto front** (global non-dominated set) is never directly exploited. Fleet best Brier today: **0.22251** (S14 extra_trees). Target: **0.21837**.

## Insight

The 6 islands currently converge to different local optima:
- S10: XGBoost, 18 features → Brier 0.2271
- S11: Extra Trees, 25 features → Brier 0.22486
- S12: XGBoost, 41 features → Brier 0.22334
- S13: RF, 42 features → Brier 0.22326
- S14: Extra Trees, 79 features → Brier 0.22251 ← BEST
- S15: LightGBM, 71 features → Brier 0.22328

Each island's top performer uses different feature subsets and model types. **Combining chromosomes from different islands' Pareto fronts via targeted crossover** could escape all 6 local optima simultaneously.

## Proposed Implementation

### Step 1: Global Pareto Aggregation (via `/api/brier-trend`)
Every 12 cycles (≈2h), the brain fetches top-5 individuals from each island's Pareto front via `/api/recent-runs`. This gives a **global pool of 30 diverse solutions**.

### Step 2: Cross-Island Chromosome Crossover
From the global pool, select pairs maximizing **feature diversity** (Hamming distance in feature selection mask):
```python
def cross_island_crossover(ind_a, ind_b, alpha=0.3):
    """Uniform crossover biased toward keeping shared high-signal features."""
    shared = ind_a.features & ind_b.features
    a_only = ind_a.features - shared
    b_only = ind_b.features - shared
    child_features = shared | sample(a_only, int(len(a_only)*alpha)) | sample(b_only, int(len(b_only)*alpha))
    # Inherit model_type from better-Brier parent
    child_model = ind_a.model_type if ind_a.brier < ind_b.brier else ind_b.model_type
    return Individual(features=child_features, model_type=child_model)
```

### Step 3: Inject into Island with Highest Stagnation
When any island stagnation_counter > 10, inject 5 cross-island offspring into that island's population, replacing the 5 worst individuals.

### Step 4: Breadcrumb Logging
Log each injection to Supabase `nba_experiments` with:
- `source_islands`: list of donor islands
- `offspring_brier`: measured Brier after 3 generations
- `feature_engine_version`: current ENGINE_VERSION

## Expected Impact

Literature (Holland 1975, Whitley 1994, island model GA theory): Cross-island recombination maintains **population diversity** and **escapes local optima** 2–3× faster than migration alone. Our islands share 3,335 feature candidates — diverse feature subsets from different model specialists should combine synergistically.

Conservative estimate: **0.002–0.005 Brier improvement** within 50 generations of injection.

## Implementation Location

- `hf-space/app.py`: Add `cross_island_injection(stagnation_trigger=10)` to the main cycle loop
- `hf-space/app.py`: Expose `/api/inject-features` endpoint already exists — use it
- New endpoint: `/api/pareto-front` → returns top-5 Pareto individuals as JSON for cross-island harvesting
- Brain cycle: every 12h, POST cross-island chromosomes to stagnating islands

## Effort

**Medium** — 1–2 hours coding. The `/api/inject-features` endpoint exists. Need:
1. `/api/pareto-front` GET endpoint on each island (~20 lines)
2. Brain logic to fetch, crossover, and inject (~50 lines)

## Risk

Low — injection is additive (only replaces worst individuals). No existing code is modified. Can be reverted by simply not calling the endpoint.

## Cross-Project Note

The same cross-island distillation applies to Political Alpha (4 islands). After NBA validation, port to `nomos-political-alpha/hf-space/app.py`.
