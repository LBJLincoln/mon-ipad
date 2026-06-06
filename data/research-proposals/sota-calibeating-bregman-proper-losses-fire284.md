# SOTA Proposal: Calibeating for General Proper Losses via Bregman Divergence

**Paper:** arXiv:2605.17269 (May 2026)
**Title:** "Calibeating for General Proper Losses: A Bregman Divergence Approach"
**Fire:** fire-284 EVEN (2026-06-07T04h)
**Priority:** 136
**Status:** proposed

---

## Key Finding

Extends "calibeating" — the property of being simultaneously calibrated AND beating any competitor — from the standard Brier/quadratic loss to a large family of proper scoring rules including α-Tsallis losses (α ∈ [1,2]) and all Lipschitz proper losses. The framework uses a Bregman divergence representation of proper losses to show that U-calibeating (simultaneously calibeating for ALL losses in a class) is achievable via regret minimization with O(√T) rate.

**Core result:** A forecaster achieves U-calibeating if and only if it achieves U-calibration — meaning calibration errors uniformly converge to zero across all bounded proper scoring rules. This is a much stronger guarantee than marginal Brier calibration alone.

**Why this matters for Nomos42:** Our fleet currently uses Brier as the sole primary Pareto objective. Research entries 110 (fire-236) and 115 (fire-246) propose adding CRPS/CRLS as additional objectives. U-calibeating provides the theoretical foundation for why multi-objective proper-loss Pareto optimization is the right approach: a model that U-calibeats is provably competitive against any adversary using ANY scoring rule, not just Brier. Before promoting S22 ET-0.2191 (10.2bp below fleet best) and evo4 RF-0.22007 (0.5bp below) to fleet-best status, we should verify they U-calibeat the current fleet best under ALL proper scoring rules simultaneously — otherwise a model with lower Brier may have worse CRPS/log-score in production.

---

## Applications

### Application 1 — Pre-Promotion U-Calibration Audit (immediate)
Add `ucalibration_audit()` to `calibration/isotonic_calibrator.py` (~60 lines):
```python
from properscoring import crps_ensemble, brier_score
from scipy.stats import chi2

def ucalibration_audit(y_true, y_pred, losses=['brier', 'log', 'crps'], alpha=0.05):
    """Test if model U-calibeats across all specified proper losses."""
    results = {}
    for loss in losses:
        score = compute_proper_loss(y_true, y_pred, loss)
        calibration_gap = compute_calibration_gap(y_true, y_pred, loss)
        results[loss] = {'score': score, 'calibration_gap': calibration_gap}
    max_gap = max(r['calibration_gap'] for r in results.values())
    results['u_calibeats'] = max_gap < alpha  # gate: 0.05
    return results
```
Gate: only promote S22 ET-0.2191 and evo4 RF-0.22007 to fleet-best if `u_calibeats=True` across Brier+CRPS+log-score simultaneously.

### Application 2 — Bregman Multi-Objective Pareto Extension
Replace single Brier objective in NSGA-II with Bregman divergence multi-objective:
- Objective 1: Brier (α=2 Tsallis = quadratic)
- Objective 2: CRPS (requires ensemble output)
- Objective 3: log-loss (log-score proper loss)
- Objective 4: α-Tsallis at α=1.5 (interpolates Brier and log-loss)
A model that Pareto-dominates under all 4 Bregman proper losses is provably U-calibrating.
Implementation: ~30 lines in `hf-space/app.py` NSGA-II `objectives` list — add 3 new proper-loss columns to pareto ranking.
Note: gate by do_not_push_hf_space_yet — add to work-queue pending space push approval.

### Application 3 — Replace Isotonic with U-Calibrating Calibrator
Build `BregmanCalibrator` in `calibration/bregman_calibrator.py` (~80 lines):
- Fits isotonic regression jointly under Brier + log-loss + CRPS to minimize Bregman divergence sum
- Stronger theoretical guarantee than single-loss isotonic (proven U-calibrating under mild conditions)
- Directly applicable to S18/S22 pareto models before /api/checkpoint promotion
- Works with crepes + properscoring (already installed)
Expected improvement: 0.001-0.002 Brier + eliminates models that are Brier-calibrated but log-score miscalibrated (detected in evo4 RF pattern fire-276+)

### Application 4 — U-Calibeating Rate Monitor in /api/export
Add `u_calibeating_rate` field to `/api/export` response — computed as max Bregman divergence gap across proper losses at each generation cycle. Add alert threshold: `u_calibeating_rate > 0.10` → flag to brain-status.json.
Complements arXiv:2603.27189 CVI score (priority=132, fire-280) which measures conditional coverage gap; U-calibeating measures universal proper-loss calibration gap.

### Application 5 — Port to political_engine.py
Apply U-calibration audit to P4 LGB-121f-0.2491 before POL fleet-best promotion:
- Rare political races have heavier tails than NBA → log-loss calibration gap is likely larger than Brier gap
- α=1.1 Tsallis loss (near log-loss) appropriate for rare events (election upsets, swing states)
- Gate: u_calibeating_rate < 0.10 for all losses before P4 LGB-121f becomes official POL fleet best
Expected improvement: 0.001-0.003 Brier + prevents promoting models with hidden log-score miscalibration on low-probability political events

---

## Implementation Notes

**Library:** `properscoring` (pip install properscoring — CRPS/CRLS/Brier), `scipy.optimize` for Bregman projection
**No new dependencies** beyond properscoring (already in research pipeline from fire-236)
**Lines:** ~170 total across calibration/ module (~60 audit + ~80 BregmanCalibrator + ~30 Pareto extension)
**Time estimate:** 3h VM session
**Gate:** implement after priority=135 (CalArena Calibration Benchmark) is complete

---

## Connection to Existing Pipeline

- Extends fire-236 (CRPS/CRLS as Pareto objectives, priority=110)
- Extends fire-246 (TabFM conditional density metrics, priority=115)
- Complements fire-280 CPA/CVI audit (priority=132) — CVI tests conditional coverage; U-calibeating tests proper-loss universality
- Complements fire-282 Venn-Abers swap (priority=134) — Venn-Abers is theoretically Brier-optimal but not proven U-calibeating; this proposal adds the universality guarantee
- **Directly gates:** evo4 RF-0.22007 and S22 ET-0.2191 fleet-best promotions → must pass U-calibeating audit before official announcement

---

## Expected Impact

- **Brier:** 0.001-0.003 improvement (eliminating Brier-overfit models that are miscalibrated under CRPS/log)
- **Calibration:** Provably U-calibrating predictions vs. any adversary using any proper scoring rule
- **Process:** Formal gate for fleet-best promotions (prevents false positives where Brier dips below threshold but model regresses in production)
