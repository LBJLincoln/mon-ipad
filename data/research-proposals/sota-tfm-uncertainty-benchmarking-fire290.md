# SOTA Research Proposal: High Performance, Low Reliability — Uncertainty Benchmarking for Tabular Foundation Models

**Source:** arXiv:2605.28554 (May 27, 2026 — accepted ESANN 2026, April 22-24)
**Authors:** José Lucas De Melo Costa, Fabrice Popineau, Arpad Rimmel, Bich-Liên Doan
**Priority:** 139
**Discovered:** fire-290 EVEN (2026-06-08T04h)
**Related:** arXiv:2602.11139 TabICLv2 (priority=137, fire-286), arXiv:2601.19944 Venn-Abers (priority=134, fire-287)

---

## Key Findings

Tabular Foundation Models (TabICL, TabPFN, TabICLv2) achieve **superior AUC scores** vs GBDTs on the TALENT benchmark (112 datasets) — **but exhibit significantly lower conditional coverage under conformal prediction** (SSCS metric). The performance-reliability gap is a fundamental challenge for TFM deployment in risk-sensitive settings.

> "achieving well-calibrated uncertainty remains a major open challenge for their reliable adoption"

- TFMs outperform GBDTs on predictive accuracy (AUC)
- TFMs **underperform** GBDTs on conditional coverage (SSCS — Size-Stratified Coverage Score)
- Tested across 112 real-world tabular datasets (TALENT benchmark)
- Synthetic controlled experiments confirm the gap intensifies under distribution shift

---

## Applications to Nomos42 Pipeline

### Application 1: TabICLv2 Upgrade Must Include CP Calibration Wrapper
The fire-286 TabICLv2 upgrade (priority=137) assumed raw TabICLv2 Brier improvements would translate to production gains. This paper shows TFMs systematically underperform on conditional coverage — meaning TabICLv2 may achieve 0.2215 CV Brier but be overconfident/underconfident on specific game conditions (back-to-back, playoff, travel-heavy). **Required addition**: wrap TabICLv2 predictions with Venn-Abers (arXiv:2601.19944, priority=134) or split-CP before any fleet-best promotion.

```python
# Implementation in colab/nba_evolution_gpu.ipynb
from crepes import WrapClassifier
tabicl_wrapped = WrapClassifier(tabicl_model)
tabicl_wrapped.fit_calibrate(X_cal, y_cal, method='venn_abers')
# Now tabicl_wrapped.predict_proba() returns calibrated probabilities
brier_calibrated = brier_score_loss(y_test, tabicl_wrapped.predict_proba(X_test)[:,1])
```

### Application 2: Pre-Promotion SSCS Gate for TabICLv2
Before replacing current fleet best (S15 RF-75f, 0.22012) with any TabICL model, require:
- `sscs_score > gbdt_sscs_baseline` — TFM must match or beat the incumbent GBDT on conditional coverage
- Implementation: add `sscs_gate_check()` to engine.py validate_model() (~25 lines, using MAPIE's SplitCP wrapper)

### Application 3: ET/RF/LGB Candidates Are More Reliable Than TabICL
**Critical insight**: Our current S18/S22/evo4/evo5 pareto best candidates (ET/RF/LGB-based GBDTs) are expected to have **better calibrated conditional coverage** than any TabICL upgrade, despite marginally higher Brier. This confirms the correct strategy:
- **Do NOT rush to TabICL** if the Brier gap is small (< 3bp)
- **Current ET-200f/RF-200f candidates below 0.22012 are more reliable for live game prediction**
- Rule: if GBDT fleet-best candidate is within 3bp of TabICL CV Brier → prefer GBDT for conditional reliability

### Application 4: Add SSCS as New Pareto Objective
Replace or supplement current Pareto objectives with SSCS (conditional coverage quality):
- Current: Brier + ROI + Sharpe + ECE (4 objectives)
- Proposed: add SSCS as 5th objective alongside Brier
- Implementation: SSCS via MAPIE's conditional coverage evaluation (~40 lines)
- Gate: `sscs > 0.80` for fleet-best promotion

### Application 5: Port to political_engine.py
Political rare-event predictions (state races, primaries) are exactly the domain where conditional coverage failures are most costly — P4's LGB80f-0.24904 candidate should also pass SSCS gate before fleet-best promotion.

---

## Implementation Plan

```python
# calibration/sscs_calibrator.py (~60 lines, MAPIE)
from mapie.classification import MapieClassifier
from mapie.metrics import classification_ssc

def compute_sscs(model, X_cal, y_cal, X_test, y_test, alpha=0.10):
    """Compute Size-Stratified Coverage Score for conditional coverage assessment."""
    mapie_clf = MapieClassifier(estimator=model, method="lac", cv="prefit")
    mapie_clf.fit(X_cal, y_cal)
    _, y_ps = mapie_clf.predict(X_test, alpha=alpha)
    sscs = classification_ssc(y_test, y_ps)
    return sscs

# In validate_model() — engine.py
sscs = compute_sscs(model, X_cal, y_cal, X_val, y_val)
results['sscs'] = sscs
if sscs < 0.80:
    results['sscs_gate_failed'] = True  # Do not promote
```

**Dependencies:** `mapie` (already in pipeline for ACI work), `crepes` (for Venn-Abers)

---

## Expected Impact

- **Prevents regression**: Blocks promoting TabICLv2 models that look good on Brier but fail conditional coverage in production
- **Validates GBDT strategy**: Confirms that S18/S22 ET/RF candidates below 0.22012 are more reliable for production than premature TabICL migration
- **Estimated conservative improvement**: 0-2bp Brier (no regression from false promotions) + better live game calibration in edge cases
- **Strategic value**: HIGH — prevents 1-2bp live regression from overconfident TFM deployment

---

## Priority Assessment

**Priority 139** — Slightly above Yates Brier decomposition (138) because:
1. Directly validates existing S18/S22/evo4/evo5 GBDT-first strategy
2. Creates necessary gate for fire-286 TabICLv2 upgrade (prevents deployment of poorly calibrated model)
3. Short implementation (~60 lines) with high leverage — single gate check prevents potential regression

---

## Work Queue Entry

```
vm-research-tfm-uncertainty-benchmarking-fire290 (priority=139)
Research arXiv:2605.28554. TFMs have higher AUC but LOWER conditional coverage than GBDTs.
Implementation:
(1) Add sscs_gate_check() to calibration/sscs_calibrator.py (~60 lines, MAPIE)
(2) Require sscs_score > gbdt_sscs_baseline before TabICLv2 fleet-best promotion
(3) Add sscs as 5th Pareto objective to NSGA-II loop
(4) Wrap fire-286 TabICLv2 Colab model with Venn-Abers before Brier comparison
(5) Port to political_engine.py — gate for P4/P7 candidates
Proposal: data/research-proposals/sota-tfm-uncertainty-benchmarking-fire290.md
```
