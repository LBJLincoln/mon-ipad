# SOTA Research Proposal: Adaptive Conformal Inference by Betting
**Fire:** 188 (EVEN WebSearch) | **Date:** 2026-05-29 | **Work-queue:** vm-add-adaptive-conformal-betting (priority=37)

## Paper
**arXiv:2412.19318** — "Adaptive Conformal Inference by Betting" (December 2024)

## Core Idea
Extends standard conformal prediction using **coin betting** (wealth-process martingale, parameter-free online optimization). Rather than a fixed miscoverage rate α on a static holdout, the betting approach adaptively adjusts coverage as data distribution drifts — ideal for non-stationary sports environments where regular-season and playoff distributions differ significantly.

## Key Advantages over Split Conformal (arXiv:2510.07185 / MAPIE)

| Property | Split Conformal (MAPIE) | Adaptive Conformal Betting |
|----------|------------------------|---------------------------|
| Coverage guarantee | Marginal (fixed α) | **Adaptive (tracks shift)** |
| Parameter tuning | Calibration set size, α | **None — parameter-free** |
| Distribution shift | Static, degrades | Dynamic auto-adjustment |
| Season transitions | Loses calibration | Auto-corrects |
| Implementation | MAPIE library | Pure numpy/scipy |

## Why It Matters for Nomos42

1. **Season-to-playoff regime shift**: Regular-season vs playoff distributions differ (rest patterns, lineup changes, intensity). Static split conformal loses coverage; adaptive coin-betting auto-corrects.

2. **S22 LR-43f validation** (fires 183-188, 6 consecutive): LR-43f Brier=0.22256 persisting through c903+c928 hard resets confirms calibration-focused model wins (arXiv:2303.06021 validated). Adaptive conformal provides the uncertainty interval wrapper for this calibrated model.

3. **ECE synergy** (vm-add-ece-pareto-objective): GA selects calibrated models via ECE Pareto objective; adaptive conformal wraps post-hoc for adaptive coverage guarantee. Two-stage pipeline.

4. **Political alpha**: Political events are highly non-stationary (election cycles, crises, regulatory changes). Adaptive conformal especially valuable for P1/P2/P4/P5/P7 on wake.

5. **No new dependencies**: Pure numpy/scipy — no MAPIE installation required.

## Implementation Sketch

```python
import numpy as np

def wealth_process(scores, alpha_init=0.1):
    """Coin-betting wealth tracker for adaptive conformal."""
    wealth, alphas = 1.0, [alpha_init]
    for score in scores:
        bet = min(wealth * 0.1, wealth - 1e-9)
        wealth = max(wealth + bet * (score - alpha_init), 1e-9)
        alphas.append(np.clip(alpha_init - np.log(max(wealth, 1e-9)) / len(alphas), 0.01, 0.99))
    return alphas

def predict_with_interval(model, X_cal, y_cal, X_test, coverage=0.9):
    cal_probs = model.predict_proba(X_cal)[:, 1]
    scores = np.abs(cal_probs - y_cal)
    alphas = wealth_process(scores)
    q = np.quantile(scores, 1 - alphas[-1])
    test_probs = model.predict_proba(X_test)[:, 1]
    return test_probs, test_probs - q, test_probs + q  # center, lower, upper
```

**Integration:** `engine.py` `evaluate_individual()` — compute adaptive conformal Brier alongside standard Brier as additional metric.

## Target Islands & Expected Gains

| Island | Model | Expected Δ Brier |
|--------|-------|------------------|
| S15 RF-75f (fleet best 0.22012) | Post-GA wrapper | -0.001 to -0.003 |
| S22 LR-43f (dominant 6+ fires) | Interval calibration | -0.001 to -0.003 |
| S18 ET-200f (if checkpointed) | Post-hoc wrap | -0.001 to -0.002 |
| P1/P2/P5/P7 (on wake) | Political calibration | -0.002 to -0.005 |

## Priority Queue Context

| Priority | Item |
|----------|------|
| 32 | vm-add-venn-abers-calibration (arXiv:2605.03816) |
| 33 | vm-add-split-conformal-calibration (arXiv:2510.07185) |
| 34 | vm-add-ece-pareto-objective (arXiv:2303.06021) |
| **37** | **vm-add-adaptive-conformal-betting ← THIS** |
| 36 | vm-add-dual-isotonic-calibration (arXiv:2510.17915) |
| 40 | engine-parity-sync |

## References
- arXiv:2412.19318: Adaptive Conformal Inference by Betting (December 2024)
- arXiv:2510.07185: Split Conformal with MAPIE (fire-168)
- arXiv:2303.06021: Calibration vs Accuracy (fire-172); S22 LR-43f validation fires 183-188
- arXiv:2510.17915: Dual Isotonic Calibration (fire-180)
