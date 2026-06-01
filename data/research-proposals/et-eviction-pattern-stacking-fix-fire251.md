# ET Eviction Pattern: Stacking Contamination Fix — fire-251

**Date:** 2026-06-09 | **Fire:** 251 | **Parity:** ODD (no WebSearch)
**Author:** Cloud Brain fire-251 (pattern analysis)
**Status:** VM ACTION REQUIRED — implement before S22 ~c78 reset (13 cycles from c65)

## Finding: 4 Consecutive ET Eviction Pattern on S22

### Pattern Summary
Every S22 run where a promising ExtraTrees-200f candidate (below fleet best 0.22012) appears
in the early generations, that candidate is lost before the next auto-reset. This has happened
4 consecutive times:

| Run | Best ET Candidate | Status |
|-----|------------------|--------|
| Run 1 (pre-wipe) | ET-200f-0.21841 gen=566 fire-61 | Lost (Pareto fleet best at time) |
| Run 2 (pre-wipe) | ET-200f-0.21875 fire-228 | LOST in 2nd total wipe fire-243 |
| Run 3 (current) | ET-200f-0.21983 fire-249 POTENTIAL FLEET BEST | CONFIRMED LOST fire-251 c=65/g=194 |
| Run 3 (post-eviction) | XGB-200f-0.22343 | Current best, above fleet best |

### Root Cause Hypothesis
Stacking is present in MODEL_TYPES and persists in the reset reseed pool. At each auto-reset
(every 25 cycles), the bottom 60% of population is reseeded. If stacking remains in the
model type sampling weights, stacking individuals enter the population and compete for Pareto
slots. Since stacking has a high composite fitness (good ROI/Sharpe despite poor Brier=0.247),
it can displace ET candidates from the Pareto front.

Evidence:
- fire-249: stacking-47f×2 entries rank-0 in S22 pareto at same generation as ET-0.21983
- fire-251: ET-0.21983 gone, stacking-47f×2 still in top5 — stacking outlived ET
- Same pattern on S18: stacking-37f reinjected at c192 (fire-230) and persists 23+ resets

## Recommended Fix

**Immediate (VM):**
```bash
# S22: Edit MODEL_TYPES in app.py on TESTforge42/nba-evo-s22 HF Space
# Remove 'stacking' from MODEL_TYPES list before ~c78 reset (13 cycles)
# S18: Same — remove 'stacking' before ~c717 reset (21 cycles from c696)
```

**Code Fix (app.py) — NEVER_RESEED guard:**
```python
# In hard reset reseed logic, add guard to prevent stacking reinjection
NEVER_RESEED_TYPES = {'stacking'}
reseed_pool = [ind for ind in population 
               if ind.model_type not in NEVER_RESEED_TYPES]
# Sample from reseed_pool instead of full population
```

**Monitoring:**
- After removing stacking: watch if ET candidates re-emerge in pareto at c65-c78
- If ET-200f appears below 0.22085 before c78: DO NOT evict at reset, use /api/export immediately
- If ET-200f appears above 0.22085: still checkpoint (Rule#3 exception for 4-eviction pattern)

## Expected Impact
- Break 4-consecutive ET eviction pattern
- Allow ET-200f to persist through next reset
- Probability: ET-200f below 0.22012 reachable in S22 run 3 (currently showing XGB-0.22343)
- Fleet best improvement potential: 2-4bp below 0.22012

## Port to Political Alpha
When POL islands wake:
- Pre-emptively exclude stacking from reseed pool on ALL POL islands
- LightGBM-105f (P1 ALL-TIME POL RECORD) is the POL analog to ET-200f NBA fleet best
- Same eviction risk applies: stacking may displace LightGBM from pareto on reset
