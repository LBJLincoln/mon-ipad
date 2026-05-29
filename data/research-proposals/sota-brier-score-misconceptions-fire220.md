# SOTA Proposal: On Misconceptions About the Brier Score

**Source:** PMC12818272 / DOI:10.1016/j.gloepi.2025.100242  
**Journal:** Global Epidemiology, 2026, Volume 11  
**Fire:** 220 (EVEN WebSearch, 2026-06-04T00h)

---

## Paper Summary

"On Misconceptions about the Brier Score in Binary Prediction Models" identifies and corrects five widespread misunderstandings about the Brier score as a probabilistic evaluation metric for binary classification.

### 5 Key Misconceptions Corrected

1. **Brier = 0 does NOT mean perfect model.** Realistic models have true probabilities within (0,1); a score of zero signals data pathology, not perfection.

2. **Lower score does NOT always mean better model across datasets.** The underlying probability distribution (prevalence/base rate) strongly influences the expected Brier score. Comparing S15 (11,440 games) to S18 (9,551 games) without adjustment is invalid.

3. **Low Brier score does NOT indicate good calibration.** A model can have a low Brier score but still be systematically miscalibrated (e.g., all predictions near 0.5). Calibration and accuracy are distinct dimensions.

4. **Score near ȳ − ȳ² does NOT mean the model is useless.** When true probabilities cluster near the mean incidence, this threshold can represent near-perfect predictions.

5. **Scores CAN exceed ȳ − ȳ².** Random variation from Bernoulli outcomes means observed scores legitimately fluctuate above this naive benchmark.

### Core Insight

Observed Brier score is a function of three components:
- **(I) Underlying true probability distribution** — prevalence, difficulty of the prediction task
- **(II) Prediction accuracy** — the quality of the model's estimates
- **(III) Random Bernoulli variation** — sampling noise from finite game sets

This decomposition means single-point Brier estimates carry non-trivial uncertainty. The paper recommends: bootstrap confidence intervals, calibration-in-the-large companion metrics, and restricting cross-model comparisons to identical populations.

---

## Applications to Nomos42

### Application 1: Bootstrap CIs on Pareto Checkpoint Decisions

Our 0.22085 threshold gate (Rule #5) is a **point estimate** with no uncertainty quantification. A pareto_best of 0.22067 may not be statistically distinguishable from 0.22090 given the Bernoulli noise on ~9500 games.

**Action:** Add bootstrap CI reporting to /api/export output:
```python
# In checkpoint export logic
from sklearn.utils import resample
import numpy as np

def brier_bootstrap_ci(y_true, y_pred, n_bootstrap=1000, ci=0.95):
    scores = []
    for _ in range(n_bootstrap):
        idx = resample(range(len(y_true)), replace=True)
        scores.append(brier_score_loss(y_true[idx], y_pred[idx]))
    alpha = (1 - ci) / 2
    return np.quantile(scores, [alpha, 1 - alpha])
```

Expected CI width: ±0.001–0.003 for ~9500 games. This means 0.22067 ± 0.002 CI = [0.21867, 0.22267] — the true value overlaps fleet best 0.22012 range.

**Work-queue:** vm-add-bootstrap-ci-brier (priority=38)

### Application 2: Same-Population Fleet-Best Comparisons

We currently compare:
- S15 best_brier=0.22012 (11,440 games, different features, different eras)
- S18 pareto_best=0.22067 (9,551 games)
- S22 pareto_best=0.22043 (9,551 games, similar window)

Per the paper: **S18 vs S22 comparisons are valid** (same game window, same data source). **S15 vs S18/S22 comparisons are confounded** by different game counts, eras, and feature sets. Fleet best should note this caveat.

### Application 3: Calibration-in-the-Large Metric

Add mean_predicted_prob vs base_rate to /api/export:
```python
calibration_in_the_large = {
    "mean_predicted": float(y_pred.mean()),
    "base_rate": float(y_true.mean()),
    "delta": float(y_pred.mean() - y_true.mean())  # should be near 0
}
```

This catches systematic over/under-confidence that Brier alone masks. Target: |delta| < 0.005.

### Application 4: Threshold Gate Review

Our 0.22085 gate was set as "fleet best minus ~0.001 buffer." The paper's decomposition suggests this buffer is smaller than the expected Bernoulli variation. Consider widening the checkpoint gate to 0.221 to avoid missing candidates that are statistically tied with fleet best.

---

## Priority

- **vm-add-bootstrap-ci-brier** (priority=38): Add bootstrap CIs to /api/export
- **vm-research-brier-score-misconceptions-fire220** (priority=104): VM review + implement calibration-in-the-large
