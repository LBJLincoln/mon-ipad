# Research Proposal: Auto-Trigger Calibration Fitting Every 50 Generations

**Date:** 2026-04-06  
**Brain Cycle:** 68  
**Priority:** HIGH — Known gap from CLAUDE.md: "Probability calibration remains a stub"  
**Expected Brier Impact:** -0.003 to -0.008 (based on NBA calibration ECE baseline of 0.2758)

---

## Problem

The calibration infrastructure in `calibration/isotonic_calibrator.py` and `calibration/conformal.py` is fully implemented but **never automatically triggered**. The `fit_and_export()` method requires explicit invocation on the HF Space, which doesn't happen in the evolution loop.

As a result:
- `data/calibration-map.json` either doesn't exist or is stale (identity calibrator)
- All 6 islands are using raw model probabilities without post-hoc calibration
- The `_apply_cal()` function in `hf-space/app.py` falls back to identity when the map is missing
- ECE baseline is 0.2758 (raw) — calibration could cut this significantly

## Evidence

From `calibration/isotonic_calibrator.py`:
```python
def fit_and_export(self):
    """Runs isotonic regression on historical data... exports JSON artifact 
    (requires HF Space environment)"""
```

From `hf-space/app.py`:
```python
_CAL_MAP_PATH = Path("data/calibration-map.json")

def _apply_cal(raw_prob: float, cal_map) -> float:
    """Apply piecewise-linear calibration. Falls back to identity if cal_map is None."""
```

From CLAUDE.md: *"Probability calibration remains a stub requiring fitting on HF Spaces"*

## Proposed Fix

Add automatic calibration fitting to the HF Space evolution loop every 50 generations when ≥200 Supabase samples are available:

```python
# In hf-space/app.py — inside the main evolution loop
# Add after generation evaluation:

CALIBRATION_FIT_INTERVAL = 50  # Refit every 50 generations

def maybe_refit_calibration(generation: int, cal_map_path: Path):
    """Auto-trigger calibration fitting if interval reached and enough data."""
    if generation % CALIBRATION_FIT_INTERVAL != 0:
        return
    try:
        from calibration.isotonic_calibrator import IsotonicPostCalibrator
        cal = IsotonicPostCalibrator.from_backtest()  # Queries Supabase
        if not cal.is_identity():
            cal.save(cal_map_path)
            print(f"[CAL] Refit at gen {generation} — calibration map updated")
        else:
            print(f"[CAL] Skipped gen {generation} — insufficient Supabase data (<200 samples)")
    except Exception as e:
        print(f"[CAL] Fit failed at gen {generation}: {e}")
```

## Expected Impact

Based on research findings (MDPI 2025, stacked ensemble NBA):
- Isotonic calibration on 200+ samples typically reduces ECE by 30-50%
- Brier score improvement of -0.003 to -0.008 on calibrated predictions
- Current raw ECE baseline: 0.2758 → target ECE < 0.05

## Port to Political Alpha

Same fix applies to `nomos-political-alpha/features/political_calibration.py`. Once validated in NBA:
1. Copy `maybe_refit_calibration()` to political HF Space app.py
2. Use `from_backtest()` against `political_predictions` Supabase table
3. Refit interval: 100 generations (political has fewer samples)

## Implementation Steps

1. Read `hf-space/app.py` fully (large file — use offset/limit)
2. Locate the main generation loop
3. Add `maybe_refit_calibration(generation, _CAL_MAP_PATH)` call
4. Deploy to S10 first (exploitation island) — monitor Brier delta for 1 cycle
5. If positive, deploy to all islands

## Notes

- Rule: 1 fix per iteration — implement in D2 Engineering cycle only
- Tag experiment in Supabase with `feature_engine_version = "v3.1-51cat+cal-autofit"`
- Revert if Brier regresses by >0.001 vs baseline
