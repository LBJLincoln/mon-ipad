# Parameter-Free and Group Conditional Online Conformal Prediction

**Fire:** 268 EVEN | **Priority:** 123 | **Status:** proposed
**arXiv:** 2606.00419 (Jun 2026)
**Expected Brier Improvement:** 0.001–0.002

---

## Paper Summary

"Parameter-Free and Group Conditional Online Conformal Prediction" (Jun 2026) introduces an online conformal prediction algorithm that:

1. **Parameter-free**: No hyperparameter tuning required — the algorithm self-adapts its coverage threshold to the observed data stream without requiring learning rates, window sizes, or other user-specified parameters.
2. **Group-conditional**: Achieves simultaneous conditional coverage across multiple groups (subpopulations) without requiring prior knowledge of group structure at calibration time.
3. **Online**: Valid in the online (sequential) prediction setting with marginal and group-conditional coverage guarantees.

Key theoretical contribution: a multiplicative-weights-style adaptation that jointly optimizes coverage across all groups while remaining parameter-free. This extends prior work on Adaptive Conformal Inference (ACI) by removing the need to specify learning rate α.

---

## Why This Matters for Nomos42

**Current fleet gap**: Our islands use either:
- Fixed split-conformal calibration (no adaptation to drift)
- ACI with hand-tuned learning rate (requires hyperparameter search)

Neither achieves simultaneous group-conditional coverage (e.g., home games vs. away games vs. back-to-back games have systematically different prediction difficulty).

**This paper closes both gaps simultaneously**: one algorithm, no tuning, group-conditional guarantees.

---

## Applications

### Application 1: NBA Group-Conditional Calibration (engine.py)
Add `GroupConditionalOCP` calibrator to `calibration/isotonic_calibrator.py`:
```python
groups = {
    'venue': game['is_home'],
    'back_to_back': game['back_to_back'],
    'season_phase': game['season_phase'],  # early/mid/late/playoffs
    'fatigue_index': game['fatigue_index'] > 0.5
}
calibrator = GroupConditionalOCP(groups=groups, parameter_free=True)
calibrator.fit(cal_scores, cal_labels)
coverage_sets = calibrator.predict(test_scores)
```
Expected: tighter prediction intervals per game context → better Brier calibration.

### Application 2: Add `group_coverage_gap` as New Pareto Objective
Extend NSGA-II in `hf-space/app.py` with 9th objective:
- `group_coverage_gap` = max group coverage deviation from nominal α
- Islands minimize coverage_gap simultaneously with Brier + ROI + Sharpe + ECE
- This discriminates between models that calibrate well on average vs. across all game types.

### Application 3: Universal Calibrator Across All Islands
Share a single GroupConditionalOCP calibrator fitted on ensemble predictions from S18/S22/evo4/evo5 combined:
- No separate per-island calibration needed
- Parameter-free adaptation handles each island's drift rate automatically
- Add to `predict_today.py` ensemble layer

### Application 4: POL Island Port
Apply to political predictions:
- Groups: `state_type` (battleground vs. safe), `incumbency` (incumbent vs. challenger), `competitive_tier` (R+5, D+5, toss-up), `cycle_type` (midterm vs. presidential)
- Group-conditional coverage prevents systematic under-coverage on battleground states

### Application 5: /api/export Metric Addition
Add to `hf-space/app.py` export endpoint:
```json
{
  "group_conditional_coverage": {
    "home": 0.894,
    "away": 0.901,
    "back_to_back": 0.887,
    "playoffs": 0.912,
    "max_gap": 0.025
  }
}
```

---

## Implementation Plan

1. **VM Step 1** (~60 lines): Implement `GroupConditionalOCP` class in `calibration/isotonic_calibrator.py`
   - Multiplicative-weights update over group coverage gaps
   - Parameter-free threshold adaptation per group
   - No new dependencies (uses scipy/numpy)

2. **VM Step 2** (~20 lines): Add `group_coverage_gap` metric to `hf-space/app.py` validation loop

3. **VM Step 3** (~15 lines): Add NSGA-II 9th objective in evolution loop

4. **VM Step 4** (~30 lines): Port to `features/political_engine.py`

5. **VM Step 5** (~20 lines): Add group metrics to `/api/export`

**Total**: ~145 lines across 4 files. No new dependencies.

---

## Synergies

- **arXiv:2506.05583** (priority=121): Complements subpopulation-adaptive CP — this paper is parameter-free; that paper handles unknown groups. Together: fully automated group discovery + parameter-free adaptation.
- **arXiv:2602.16537** (priority=117): Drift-detection conformal prediction. Parameter-free group-CP + drift detection = robust online calibration under non-stationary + group-heterogeneous NBA streams.
- **arXiv:2605.20515** (priority=118): Corrupted feedback. Parameter-free + group-conditional + corruption-robust = complete online CP stack.

---

## Expected Results

- **Brier improvement**: 0.001–0.002 (better group calibration → more honest probability estimates)
- **Coverage improvement**: from ~89% marginal to 89% ± 2% per group (group-conditional)
- **No hyperparameter search**: saves ~10 iterations per island per season
- **POL benefit**: battleground state coverage guaranteed to match national coverage

---

*Written by cloud-brain-fire-268 (2026-06-04T12h). VM: implement after priority=0 checkpoint items.*
