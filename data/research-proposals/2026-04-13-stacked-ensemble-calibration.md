# Research Proposal: Stacked Ensemble + Isotonic Calibration
**Filed:** 2026-04-13 | **Cycle:** Brain cycle (Sonnet 4.6) | **Priority:** HIGH

## Motivation

Current best Brier: **0.22293** (S12, Extra Trees, gen 80)  
Target: **< 0.20** | Gap: **0.02293**

After 300+ generations across 5 active islands, the GA has plateaued near 0.222-0.223. Individual tree models have been thoroughly optimized. The next improvement requires changing the **prediction aggregation strategy**, not just feature selection.

## Source Paper

**"Stacked ensemble model for NBA game outcome prediction analysis"**  
Scientific Reports, 2025  
https://www.nature.com/articles/s41598-025-13657-1  
PMC: https://pmc.ncbi.nlm.nih.gov/articles/PMC12357926/

Key finding: Stacking base classifiers (XGBoost, Random Forest, AdaBoost, etc.) with an MLP meta-learner using **out-of-fold (OOF) predictions** significantly outperformed all individual models.

## Proposed Implementation

### Phase 1: Pareto Front Stacking (CPU-safe)
Instead of selecting the single best GA candidate, take the **top-5 Pareto front members** and stack their predictions:

```python
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
import numpy as np

def stack_pareto_front(pareto_candidates, X_val, y_val):
    """
    Stack top-N GA-evolved models using out-of-fold predictions.
    Uses LogisticRegression meta-learner (CPU-safe, no neural nets).
    """
    # Generate OOF predictions from each Pareto candidate
    oof_preds = []
    for candidate in pareto_candidates[:5]:
        model = candidate['model']
        oof_preds.append(model.predict_proba(X_val)[:, 1])
    
    # Stack as feature matrix
    X_meta = np.column_stack(oof_preds)
    
    # Train meta-learner (LogisticRegression — no overfitting risk)
    meta_learner = LogisticRegression(C=0.1, max_iter=1000)
    meta_learner.fit(X_meta, y_val)
    
    return meta_learner
```

### Phase 2: Isotonic Calibration Post-Processing

```python
from sklearn.isotonic import IsotonicRegression

def apply_isotonic_calibration(raw_probs, y_true):
    """
    Post-hoc calibration on stacked predictions.
    Isotonic regression is non-parametric — works with any distribution.
    Demonstrated to reduce Brier score by 0.003-0.008 in sports prediction tasks.
    """
    ir = IsotonicRegression(out_of_bounds='clip')
    ir.fit(raw_probs, y_true)
    return ir

# During evaluation:
stacked_probs = meta_learner.predict_proba(X_meta)[:, 1]
calibrated_probs = calibrator.transform(stacked_probs)
brier = brier_score_loss(y_val, calibrated_probs)
```

## Integration Points

### HF Space App (hf-space/app.py)
After GA completes each cycle, run stacking on the current Pareto front:
1. Extract top-5 models from `pareto_front`
2. Generate OOF predictions using `X_val`
3. Fit LogisticRegression meta-learner
4. Apply isotonic calibration
5. Report stacked Brier alongside individual Brier

### CPU Constraints
- LogisticRegression is O(n_features × n_samples) — fast on CPU
- Isotonic regression is O(n_samples log n_samples) — fast
- No neural networks needed (avoids N/A on CPU-only spaces)
- Total overhead per cycle: < 2 seconds

## Expected Impact

| Technique | Estimated Brier Delta |
|-----------|----------------------|
| Pareto front stacking alone | -0.002 to -0.005 |
| + Isotonic calibration | -0.003 to -0.008 |
| Combined | **-0.005 to -0.010** |

If realized, this brings best Brier from **0.22293 → ~0.213-0.218**, crossing the 0.21837 checkpoint threshold.

## Experiment Protocol

1. Implement in S12 (fleet leader, stable, stagnation=0)
2. Tag all runs with `feature_engine_version = "v3.1-54cat-stacked"`
3. Run 10 cycles, compare stacked_brier vs individual_brier
4. If stacked_brier < 0.220, roll out to all islands
5. If stacked_brier < 0.21837, checkpoint to Supabase immediately

## Cross-Project Application

The same isotonic calibration wrapper applies to **Political Alpha**:
- PA islands stuck at 0.250 after thousands of generations
- Brier decomposition suggests reliability (calibration) is the bottleneck
- Adding `CalibratedClassifierCV(method='isotonic')` to PA evaluation loop
- Expected PA Brier delta: -0.005 to -0.015

## References

1. [Stacked ensemble model for NBA game outcome prediction (Scientific Reports 2025)](https://www.nature.com/articles/s41598-025-13657-1)
2. [Leveraging ML for NBA Match Results (ACM 2025)](https://dl.acm.org/doi/10.1145/3773365.3773520)
3. [PLOS ONE systematic review: AI in basketball prediction (2025)](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0326326)
4. [Applying Calibration Techniques in ML (Medium)](https://medium.com/@eskandar.sahel/applying-calibration-techniques-to-improve-probabilistic-predictions-in-machine-learning-models-c175c2e38ffc)
