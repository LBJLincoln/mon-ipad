# Multi-Agent Conformal Prediction with Personalized Statistical Validity
> arXiv:2606.00717 (June 2026) | Priority=123 | Written fire-268 EVEN

## Paper
"Multi-Agent Conformal Prediction with Personalized Statistical Validity"
arXiv:2606.00717, June 2026.

## Core Finding
Proposes personalized federated weighted conformal prediction (PFWCP): combines
local density ratio weighting with weighted quantile aggregation to correct for
agent/island heterogeneity while preserving privacy. Achieves asymptotically valid
marginal AND calibration-conditional coverage guarantees per participating agent,
with a one-shot communication protocol (no iterative rounds).

Key insight: standard conformal prediction pooled across heterogeneous agents
yields *collectively* valid but *individually* miscalibrated intervals. PFWCP fixes
this by assigning each agent/island a local density ratio weight that corrects for
distribution shift between that island's training distribution and the deployment
distribution.

## Direct Applications to Nomos42

### Application 1 — Island-Personalized Conformal Sets in predict_today.py
Replace current rank-fusion ensemble (which treats all islands as equally calibrated)
with PFWCP: each island (S15, S18, S22, evo4, evo5) gets a local density ratio weight
w_i = p_test(x) / p_train_i(x) estimated via nearest-neighbour density ratio on the
calibration split. The final prediction set is the weighted quantile aggregation.
Expected: better-calibrated game-level probability intervals, tighter Brier.

### Application 2 — Agent-Level Personalized Coverage in TF
The 17 NBA TF agents and 17 POL TF agents each see different market micro-structure
data. PFWCP provides per-agent coverage guarantee: each agent's prediction interval
is valid for THAT agent's data distribution, not the pooled one.
Integrate into build_common_knowledge(): add `personal_cp_coverage` field per agent
so COMMON_KNOWLEDGE[D] includes each agent's calibration bound → DMAD-aware betting.

### Application 3 — One-Shot Cross-Island Calibration Aggregation
For multi-island Pareto fusion: use PFWCP's one-shot aggregation (no iterative
refinement needed) to merge calibration sets from all active islands before
predict_today.py inference. This eliminates the 30-50 line custom weighted-quantile
averaging currently used.

### Application 4 — Port to political_engine.py
POL islands (P4, P7) have heterogeneous training distributions (different election
years, state-level vs. national races). PFWCP corrects for this: each POL island
gets a local weight based on its training year distribution vs. target election date.

## Implementation
Library: No new deps — implemented in ~100 lines using scipy (density ratio) +
numpy (weighted quantile). The PFWCP aggregation step replaces the loop in
`predict_today.py` lines ~150-200.

## Synergies with Existing Pipeline
- Complements arXiv:2602.19284 (priority=105, Localized CP Model Selection)
- Extends arXiv:2502.05565 (priority=106, Multi-Scale CP) to the multi-agent setting
- Directly validates Axelrod Mech A (COMMON_KNOWLEDGE) by providing per-agent
  calibration bounds as shareable context
- Synergizes with arXiv:2602.16537 (priority=117, drift-adaptive CP) by weighting
  islands by drift magnitude

## Expected Improvement
0.001-0.002 Brier (from better island-personalized calibration)
+ coverage guarantee per island (not just pooled)
+ no additional training cost (post-hoc, one-shot)

## Work Queue Item
`vm-research-multi-agent-cp-personalized-fire268` (priority=123)
