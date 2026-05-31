# SOTA Proposal: Multicalibration Gradient Boosting for NBA Prediction

**Fire:** 240 (EVEN WebSearch)  
**Source:** arXiv:2602.06773 — "On the Convergence of Multicalibration Gradient Boosting" (Feb 2026)  
**Priority:** 112  
**Work-queue entry:** vm-research-multicalibration-gb-fire240  

## Key Finding

Multicalibration gradient boosting produces approximately multicalibrated predictors deployed at web scale. Convergence rate: O(1/√T) for multicalibration error across iterations; linear rate under smoothness conditions on weak learners. Local quadratic convergence for training loss in adaptive variants.

**Multicalibration** is strictly stronger than standard calibration — it requires calibration to hold simultaneously across a large collection of overlapping subgroups. For NBA: calibration must hold for all combinations of (team tier × venue × fatigue × season phase), not just on average.

## Why This Matters

Current fleet best uses Venn-Abers post-hoc calibration (validated fire-197+), which corrects overall calibration but may leave systematic gaps within subgroups. The S22 ET-200f-0.21875 candidate (fire-240 EXTREME URGENT) and S18 top-performer 0.22061 (fire-240 CHECKPOINT URGENT) both use Venn-Abers — adding multicalibration as an additional correction layer would tighten subgroup gaps and lower overall Brier via Jensen's inequality.

The paper reports deployment at web scale with O(1/√T) convergence, making it practical for the evolution island validation loop.

## Applications

### App 1: Multicalibration GB as Post-Hoc Calibration Layer
- Current pipeline: model → Venn-Abers → prediction
- Proposed: model → Venn-Abers → Multicalibration GB → prediction
- Multicalibration GB trains on residuals from Venn-Abers across NBA subgroups
- Expected: tighter subgroup calibration → improved overall Brier

### App 2: multicalibration_error_max as 5th Pareto Objective
- Add `multicalibration_error_max` (max ECE across subgroups) as new Pareto objective on evolution islands
- NBA subgroups:
  - `team_tier_home`: top-10 home / top-10 away / mid home / mid away / lottery home / lottery away
  - `back_to_back`: True × (home|away)
  - `season_phase`: early (games 1-20) / mid (21-60) / playoff-push (61-82) / playoffs
  - `fatigue_index`: low / medium / high (from schedule_features proposal fire-232)
- Tradeoff with primary Brier objective → naturally selects subgroup-calibrated models in Pareto front

### App 3: NBA Subgroup Calibration Audit
- Compute per-subgroup ECE on S15 RF-75f (fleet best 0.22012) and S22 ET-200f-0.21875 (extreme urgent candidate)
- Identify worst-calibrated subgroups (hypothesis: back-to-back away games, early-season matchups)
- Target multicalibration correction on worst-3 subgroups first for maximum Brier reduction

### App 4: Port to political_engine.py
- POL subgroups: `state_type` (swing/safe/lean) × `incumbency` (open/incumbent/challenger) × `competitive_tier` × `cycle_type` (primary/general/special)
- Multicalibration ensures predictions valid for all voter-segment and demographic analyses

## Technical Details

- **Library:** Custom multicalibration GB (paper algorithm) OR fairlearn `ExponentiatedGradient` with calibrated equalized odds
- **Convergence:** O(1/√T) general; linear rate with smooth weak learners; local quadratic for adaptive variants
- **Group membership:** Soft (probabilistic) group assignment preferred over hard boundaries
- **Integration point:** Post-hoc stage in `validate_model()` after existing Venn-Abers calibration
- **Cost:** O(G × T) where G = number of subgroups, T = boosting rounds — manageable at G=20, T=100

## Expected Improvement

- Brier: 0.001-0.003 (subgroup corrections compound via Jensen's inequality toward lower marginal Brier)
- Guarantee: calibration at group level, not just marginal
- Synergy: Venn-Abers (fire-158) + Multicalibration GB = two-stage calibration with group-level guarantee

## Relationship to Existing Research Pipeline

| Fire | Paper | Synergy with MulticalibGB |
|------|-------|---------------------------|
| fire-158 | Venn-Abers (arXiv:2605.03816) | Pre-stage before multicalib — two-stage stack |
| fire-216 | Stacked CP (arXiv:2505.12578) | Multicalib groups → more valid group-level CP coverage |
| fire-220 | Brier Misconceptions (PMC12818272) | Multicalib directly addresses subgroup-calibration-in-large |
| fire-236 | CRPS objectives (arXiv:2603.29928) | Add CRPS per subgroup as additional group objective |
| fire-230 | Sliding-window CV (arXiv:2506.12183) | Estimate subgroup calibration error per fold |
| fire-232 | Schedule features (IEEE 2024) | fatigue_index subgroup from home_next/fatigue features |

## Implementation Priority

**Priority 112** — higher than discrete tokenization (111). Can be implemented as post-hoc layer on any existing pareto model without retraining the full GA.

## Status

- Proposal written: fire-240 (2026-06-07T08h EVEN)
- VM task: vm-research-multicalibration-gb-fire240 (pending, priority=112)
- BLOCKED: S13/S14/S15 sleeping, S18/S22 /api/export-404; implement when export resumes
