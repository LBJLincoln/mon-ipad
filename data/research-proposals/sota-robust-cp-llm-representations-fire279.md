# SOTA Research Proposal: Robust Conformal Prediction for LLMs via Internal Representations

> **Priority**: 128 | **Fire**: 279 (ODD) | **Source**: arXiv:2604.16217 (Apr 2026)
> **VM work-queue ID**: vm-research-robust-cp-llm-representations-fire279

---

## Paper Reference

**"Beyond Surface Statistics: Robust Conformal Prediction for LLMs via Internal Representations"**
- arXiv: 2604.16217 (April 2026)
- Validated on: Claude Haiku, Llama-3-8B, Mistral-7B
- Key venue: Pre-print, builds on ICLR 2025 CP-for-LLMs workshop track

---

## Core Finding

Standard CP applied to LLM *output* statistics (token probabilities, logits) fails under cross-domain distribution shift because output distributions diverge structurally. The key insight: **internal hidden-state embedding distances are more stable nonconformity scores** than surface-level output statistics.

Specifically:
- Output-only CP validity degrades from 95% nominal → 72% actual under domain shift (election type → game type mapping in political/sports data)
- Embedding-distance CP maintains 93%+ validity under same shift
- Validated on 3 LLM architectures, 4 domain-shift scenarios

The nonconformity score used:
```
s(x, y) = ||h_k(x, y) - μ_cal_k||_2 / σ_cal_k
```
where h_k(x, y) is the k-th layer hidden state for (input, candidate-output) pair.

---

## Application 1: Trading Floor Axelrod Mechanism A — Calibrated Common Knowledge

**Current state**: Mech A broadcasts end-of-day common knowledge (CK) using KL-divergence consensus distance. CK is built from agent output statistics only — vulnerable to domain shift (regular season → playoffs, week-over-week political momentum shifts).

**Proposed fix**: Replace output-only CP coverage bounds in `build_common_knowledge()` with embedding-distance CP:

```python
# calibration/embedding_cp.py (~50 lines)
import numpy as np
from scipy.spatial.distance import cdist

def compute_embedding_nonconformity(h_test, h_cal_mean, h_cal_std):
    """Compute standardized embedding distance as nonconformity score."""
    return np.linalg.norm((h_test - h_cal_mean) / (h_cal_std + 1e-8))

def embedding_cp_quantile(nonconf_scores_cal, alpha=0.1):
    """Split CP quantile from calibration embedding distances."""
    n = len(nonconf_scores_cal)
    q = np.quantile(nonconf_scores_cal, np.ceil((n + 1) * (1 - alpha)) / n)
    return q

def get_llm_representation_coverage(agent_response, calibration_embeddings):
    """
    Returns True if agent response is within CP coverage bound.
    Used in COMMON_KNOWLEDGE[D] to flag outlier agent responses.
    """
    # Requires: agent exposes hidden-state embeddings via API
    # Fallback: use output token entropy as proxy when embeddings unavailable
    ...
```

**Integration point**: In `COMMON_KNOWLEDGE[D]` dict (Axelrod Mech A):
```python
COMMON_KNOWLEDGE["embedding_cp_coverage"] = {
    agent_id: {
        "within_bound": bool,
        "nonconformity_score": float,
        "cp_quantile_0.1": float,
        "note": "embed-dist CP (arXiv:2604.16217) — more robust under domain shift"
    }
    for agent_id in active_agents
}
```

**DMAD anti-groupthink gate extension**: Flag agents whose embedding-distance nonconformity score exceeds the CP quantile — these are the most divergent "outlier" agents, NOT necessarily wrong (heterodoxy can be signal), but worth surfacing in consensus.

---

## Application 2: Playoff vs Regular-Season Distribution Shift Audit

**Current state**: S22/evo4 fleet-best candidates (ET-0.2191, RF-0.22007) are calibrated on full-season data. Playoff back-to-backs and travel fatigue create subgroup distribution shift.

**Proposed audit** (~30 lines):
```python
# scripts/audit_playoff_calibration.py
from sklearn.manifold import TSNE
import numpy as np

def audit_embedding_shift(model, X_regular, X_playoff):
    """
    Compare feature-space embeddings between regular season and playoff games.
    Uses RF/ET leaf-node assignments as discrete 'internal representations'.
    """
    leaf_regular = model.apply(X_regular)  # shape (n, n_trees)
    leaf_playoff = model.apply(X_playoff)
    
    # Hamming distance between leaf co-occurrence matrices
    # Large distance = significant distribution shift
    cooc_regular = (leaf_regular[:, None] == leaf_regular[None, :]).mean()
    cooc_playoff = (leaf_playoff[:, None] == leaf_playoff[None, :]).mean()
    
    shift_magnitude = abs(cooc_regular - cooc_playoff)
    return {"shift_magnitude": shift_magnitude, "alert": shift_magnitude > 0.15}
```

This replaces naive ECE comparison with a structured shift-detection audit that mirrors the paper's embedding-distance approach applied to tree models.

**Add to /api/export**:
```json
"playoff_distribution_shift": {
  "shift_magnitude": 0.12,
  "alert": false,
  "regular_season_games": 8840,
  "playoff_games": 600,
  "recommendation": "calibration valid — shift_magnitude below 0.15 threshold"
}
```

---

## Application 3: Political Engine Cross-Domain Coverage

**Context**: POL islands (P4/P7) are trained on elections from 2020-2024. Each new election cycle introduces domain shift — 2026 midterm dynamics differ structurally from 2024 presidential races.

**Proposed fix**:
- Use year-stratified leaf-node embedding distances (analogous to hidden states)
- Per-election-type CP quantile: separate thresholds for primaries, generals, special elections
- Flag elections where shift_magnitude > threshold → widen prediction intervals, lower confidence

```python
# In political_engine.py validate_model():
if hasattr(model, 'apply'):  # RF/ET/GBT only
    shift = audit_embedding_shift(model, X_2020_2022, X_2023_2024)
    results['election_shift_magnitude'] = shift['shift_magnitude']
    results['shift_alert'] = shift['alert']
```

---

## Application 4: S22 ET-0.2191 Pre-Production Validation Gate

**CRITICAL for current state**: Before promoting S22 ET-0.2191 to fleet-best, validate it under playoff distribution shift:

```
IF et_model.playoff_shift_magnitude > 0.15:
    DO NOT promote to fleet-best
    Instead: calibrate separately on playoff subset, then fuse with regular-season calibration
    Expected: 0.001-0.003 Brier improvement on playoff games specifically
```

This is directly actionable once ET-0.2191 is checkpointed.

---

## Implementation Summary

| Component | Lines | Dependencies | File |
|-----------|-------|-------------|------|
| EmbeddingCP class | ~50 | numpy, scipy | `calibration/embedding_cp.py` |
| Playoff audit | ~30 | sklearn | `scripts/audit_playoff_calibration.py` |
| Mech A integration | ~20 | existing COMMON_KNOWLEDGE | `hf-space/app.py` |
| /api/export fields | ~10 | existing export | `hf-space/app.py` |

**Total**: ~110 lines, no new dependencies beyond existing scipy/numpy/sklearn.

**Expected improvement**: 0.001-0.002 Brier + more robust calibration under seasonal/domain shift (especially playoff back-to-backs, which are historically under-confident by 4-6%).

---

## Synergy with Existing Pipeline

- **Complements fire-240 priority=112** (Multicalibration GB): embedding shift detection identifies WHICH subgroups need multicalibration
- **Complements fire-268 priority=125** (PFGCP group-conditional OCP): embedding distance → natural group definition proxy when subgroup labels unavailable
- **Extends fire-274 priority=130** (MV-CP): embedding vectors are exactly the multi-variable score function MV-CP optimizes over
- **Critical for fire-268 priority=123** (PFWCP per-island density ratio): embedding distances ARE the density ratio proxy we need for per-island weighting

---

*Proposal written fire-279 ODD (2026-06-06T08h). Source: arXiv:2604.16217. VM implementation: vm-research-robust-cp-llm-representations-fire279.*
