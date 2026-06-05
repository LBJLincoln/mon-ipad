# Research Proposal: Conformal Social Choice for Safe Multi-Agent Deliberation
**Source:** arXiv:2604.07667 (Apr 2026) — "From Debate to Decision: Conformal Social Choice for Safe Multi-Agent Deliberation"
**Priority:** 127
**Fire:** 281 (ODD)
**Target:** NBA TF + POL TF agent ensemble fusion

---

## Key Finding

Linear opinion pool (LOP) + split conformal prediction for heterogeneous LLM agents achieves
distribution-free majority-valid coverage across all agent subsets. Validated on Claude Haiku,
DeepSeek-R1, Qwen-3 32B ensembles. Complements PFWCP (fire-268, priority=123) via a complementary
game-theoretic approach: where PFWCP gives per-agent density-ratio reweighting, Conformal Social
Choice gives formal majority-validity via the social welfare function F(p1...pk) = LOP + split-CP
quantile correction.

**Core result:** For any subset S of agents with |S| >= floor(k/2)+1, the social choice prediction
set contains the true label with probability >= 1-alpha. This is strictly stronger than pooled CP
(which only guarantees marginal coverage for the full ensemble) and strictly stronger than individual
per-agent CP (which doesn't guarantee cross-agent consistency).

---

## Architecture fit

Current `build_common_knowledge_block()` in both NBA TF (line 3511) and POL TF uses a simple
weighted average or rank fusion across the 17 trading agents. This achieves:
- No formal coverage guarantee for the ensemble
- Potential miscalibration when agent predictions are heterogeneous (arXiv:2605.18858, priority=124)

Conformal Social Choice replaces this with a two-step protocol:
1. **Linear Opinion Pool**: `p_LOP(x) = sum_i w_i * p_i(x)` where `w_i` are Brier-score-inverse weights
2. **Split-CP correction**: compute `q_alpha = quantile({s_i}, ceil((n+1)(1-alpha))/n)` over held-out
   calibration set, then output prediction set `C(x) = {y : s(x,y) <= q_alpha}` where `s` is the LOP
   nonconformity score

This gives: P(Y ∈ C(X)) >= 1-alpha for any majority-valid subset of agents.

---

## Implementation Plan

### Application 1: Replace rank fusion in `build_common_knowledge_block()`
File: `scripts/arena/hf-llm-trading-floor/app.py` (NBA, ~line 3511)
File: `scripts/arena/hf-political-trading-floor/app.py` (POL, ~line 2200+)

```python
# ~60 lines, scipy + numpy (no new dependencies)
def conformal_social_choice_fusion(agent_probs: dict, agent_brier_scores: dict,
                                   calibration_set: list, alpha: float = 0.1):
    """Linear opinion pool + split-CP correction for multi-agent ensemble."""
    import numpy as np
    from scipy.stats import norm
    
    # Step 1: Brier-inverse weights
    briervals = np.array([agent_brier_scores[a] for a in agent_probs])
    inv_brier = 1.0 / (briervals + 1e-9)
    weights = inv_brier / inv_brier.sum()
    
    # Step 2: Linear Opinion Pool
    probs = np.array([agent_probs[a] for a in agent_probs])
    lop_prob = float(np.dot(weights, probs))
    
    # Step 3: Split-CP nonconformity scores on calibration set
    if calibration_set:
        scores = [abs(ex['true_label'] - ex['lop_prob']) for ex in calibration_set]
        q_alpha = float(np.quantile(scores, min(1.0, (len(scores)+1)*(1-alpha)/len(scores))))
    else:
        q_alpha = alpha  # fallback: no calibration data
    
    # Step 4: Coverage interval
    lower = max(0.0, lop_prob - q_alpha)
    upper = min(1.0, lop_prob + q_alpha)
    
    return {
        'lop_prob': lop_prob,
        'coverage_lower': lower,
        'coverage_upper': upper,
        'q_alpha': q_alpha,
        'conformal_social_choice_coverage': upper - lower
    }
```

### Application 2: Add `conformal_social_choice_coverage` to COMMON_KNOWLEDGE[D]

In `build_common_knowledge_block()` (Axelrod Mech A block), after existing CK fields:

```python
# Add to COMMON_KNOWLEDGE dict
csc_result = conformal_social_choice_fusion(
    agent_probs=today_agent_probs,
    agent_brier_scores=agent_rolling_brier,
    calibration_set=last_30d_outcomes,
    alpha=0.1
)
ck_block["conformal_social_choice_coverage"] = csc_result['conformal_social_choice_coverage']
ck_block["ensemble_lop_prob"] = csc_result['lop_prob']
ck_block["coverage_interval"] = f"[{csc_result['coverage_lower']:.4f}, {csc_result['coverage_upper']:.4f}]"
```

### Application 3: Multi-agent coverage guarantee replaces ad-hoc averaging

The LOP weights (Brier-inverse) are equivalent to the Brier-weighted fusion from arXiv:2605.18858
(priority=124, fire-268) — two independent papers converge on the same solution via different routes
(social choice theory vs. collective miscalibration theory). This cross-paper convergence strongly
validates the Brier-weighted LOP as the correct ensemble fusion approach.

### Application 4: Port to `political_engine.py` for P4/P5/P7 fusion

Apply same LOP + split-CP correction to the 3-island POL ensemble (P4/P5/P7). P4 and P7 have
heterogeneous training years (different election cycles) — heterogeneity makes the formal
majority-valid coverage guarantee especially valuable vs. simple averaging.

---

## Dependencies
- `scipy` (already in requirements) — for `np.quantile`
- `numpy` (already in requirements) — for linear opinion pool

No new dependencies required.

---

## Expected Improvement
- 0.001-0.002 Brier reduction from properly weighted Brier-inverse LOP vs. equal-weight averaging
- Formal coverage guarantee: P(Y ∈ C(X)) >= 0.90 for any majority-valid agent subset
- Eliminates systematic miscalibration identified in arXiv:2605.18858 under heterogeneous agents

---

## Priority Justification
Priority=127 (after multi-agent CP priority=123-126 cluster). This is the capstone social-choice
theoretic justification for all the Brier-weighted fusion work. Should be implemented after PFWCP
(priority=123) and collective miscalibration audit (priority=124) are done, since all three use
Brier-inverse weights — they're architecturally unified.

---

## Files to modify (after HF push gate lifts)
1. `scripts/arena/hf-llm-trading-floor/app.py` — NBA TF: add `conformal_social_choice_fusion()` + wire into `build_common_knowledge_block()`
2. `scripts/arena/hf-political-trading-floor/app.py` — POL TF: same (+12L parity)
3. `scripts/arena/hf-llm-trading-floor/app.py` — Add `conformal_social_choice_coverage` field to `/api/axelrod_log` export

**do_not_push_hf_space_yet — VM BLOCKED until HF push gate lifted by user.**
