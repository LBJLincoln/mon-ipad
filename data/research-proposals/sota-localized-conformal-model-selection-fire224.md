# SOTA Research Proposal: Localized Conformal Model Selection

**Source:** arXiv:2602.19284  
**Title:** Localized conformal model selection  
**Authors:** Yuhao Wang (Tsinghua University + Shanghai Qizhi Institute), Tengyao Wang (London School of Economics)  
**Submitted:** February 2026  
**Fire:** fire-224 (EVEN WebSearch, 2026-06-04T16h)  
**Work-queue:** vm-research-localized-conformal-model-selection-fire224 (priority=105)

---

## Summary

Proposes a framework for **localized conformal model selection** integrating local adaptivity with post-selection validity for distribution-free prediction. Core innovation: symmetric model selection across calibration points using upper/lower surrogate intervals, constructing a data-dependent safe index set that (a) contains the oracle model and (b) preserves exchangeability.

**Key guarantee:** Exact finite-sample marginal coverage while adapting to spatial heterogeneity and model complexity.

**Simulation results:** Substantial reductions in interval width vs. the best fixed model, especially in heterogeneous and low-noise settings.

---

## Application to Nomos42

### Immediate: Pareto Model Selection by Game-Condition Clusters

Current GA pareto archives in S18/S22 contain models selected by global Brier loss alone. Apply localized CP to select the best model from the pareto front based on locally valid coverage across game-condition subgroups:

| Cluster Dimension | Feature | Why it matters |
|---|---|---|
| Rest days | 0 / 1 / 2+ | Back-to-back games have systematically different win rates |
| Home/Away | is_home | Home advantage is a nonlinear effect |
| Travel distance | travel_dist_mi | Road-trip fatigue |
| Division matchup | same_division | Different average game tightness |

1. Partition calibration set into K=8 clusters by game conditions
2. For each pareto model, compute localized CP interval width per cluster
3. Select model with minimum average cluster interval width while maintaining coverage >= 1-alpha = 0.9

### Medium: Locally-Adjusted Brier Gate

Replace the global `best_brier < 0.22085` checkpoint gate with a localized check:
- If localized CP model selection identifies a pareto member as optimal for >=6/8 game clusters, treat as checkpoint candidate even if `best_brier` shows field lag
- Addresses the field-lag problem documented in Rule#4 (1-3 fire lag)

### Long-term: Port to POL Islands

Apply same localization to political prediction with political-event clusters (election type, district geography, candidate incumbency) when POL islands wake.

---

## Implementation Sketch

```python
from mapie.classification import MapieClassifier
from sklearn.cluster import KMeans
import numpy as np

# 1. Build game-condition clusters on calibration set
cluster_features = ['rest_days', 'is_home', 'travel_dist_norm', 'same_division']
kmeans = KMeans(n_clusters=8, random_state=42).fit(X_cal[cluster_features])
cluster_labels = kmeans.labels_

# 2. For each pareto model, compute per-cluster interval width
def localized_interval_width(model, X_cal, y_cal, cluster_labels, alpha=0.1):
    widths = []
    for k in np.unique(cluster_labels):
        mask = cluster_labels == k
        if mask.sum() < 30:
            continue
        mapie = MapieClassifier(estimator=model, method='score', cv='prefit')
        mapie.fit(X_cal[mask], y_cal[mask])
        _, intervals = mapie.predict(X_cal[mask], alpha=alpha)
        widths.append(np.mean(intervals[:, 1, 0] - intervals[:, 0, 0]))
    return np.mean(widths)

# 3. Select best pareto model
best_model = min(pareto_models,
                 key=lambda m: localized_interval_width(m, X_cal, y_cal, cluster_labels))
```

---

## Related Work Queue Items
- vm-add-split-conformal-calibration (priority=33): split conformal wrapper for pareto models
- vm-research-stacked-conformal-prediction-fire216 (priority=102): conformalizes stacked ensembles
- vm-add-adaptive-conformal-betting (priority=37): parameter-free adaptive CP
- vm-add-bootstrap-ci-brier (priority=38): bootstrap CIs on checkpoint decisions (PMC12818272)
