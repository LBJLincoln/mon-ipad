# SOTA Research Proposal: Distributed Information Failure in Multi-Agent LLMs

**fire-206 EVEN WebSearch | arXiv:2505.11556 | 2026-06-01T16h**

## Source

"Systematic Failures in Collective Reasoning under Distributed Information in Multi-Agent LLMs"
arXiv:2505.11556 (2025)

## Key Finding

Multi-agent LLMs achieve only **30.1%** accuracy under distributed information vs **80.7%** for single agents with complete information. Root cause: agents fail to recognize "latent information asymmetry" — they don't know what peers know that they don't.

## Axelrod Relevance

**Direct validation of Mech A (COMMON_KNOWLEDGE broadcast):**

Without CK[D], each agent operates like a node in a distributed system with no shared state. The 30.1% failure mode maps exactly to the scenario where agents receive private signals (their own research/priors) but have no broadcast mechanism. CK[D] eliminates this asymmetry by prepending all day-D agent bets to day D+1 prompts.

**Secondary validation of DMAD gate:**

When agents share incomplete/biased information, collective accuracy collapses. DMAD-DIVERGE forces agents to surface disagreement rather than silently assume consensus — directly countering the "latent information asymmetry" failure mode.

## Proposed Implementation

### New Mech C metric: `info_asymmetry_score_d`

```python
# In write_axelrod_log() — Mech C post-mortem log
# info_asymmetry_score_d = fraction of agent bets in day D that had zero overlap with any peer's bets
# High score = agents operating in informational silos despite CK broadcast
# → CK quality failure indicator
# threshold: info_asymmetry_score_d > 0.4 → flag as ck_broadcast_failure
```

**Logic:**
1. After all bets are in for day D, build the union of all {game: bet_direction} pairs per agent
2. For each agent A, compute `peer_union = union(all other agents' bets)`
3. `isolated_fraction_A = |A.bets - peer_union| / |A.bets|`
4. `info_asymmetry_score_d = mean(isolated_fraction_A for all A)`

**Interpretation:**
- Score = 0.0: every agent bet on at least one game that a peer also bet on (good CK coverage)
- Score = 1.0: every agent's bets are unique to them (CK broadcast failure — agents are in silos)
- Threshold 0.4: suggests CK[D-1] failed to synchronize information across agents

### Integration with existing Mech C metrics

Add to `write_axelrod_log()` post-mortem entry alongside existing metrics:
```json
{
  "day": "D",
  "info_asymmetry_score_d": 0.12,
  "ck_broadcast_failure": false,
  "peer_error_rate_d": 0.28,
  "coverage_gap": 0.05
}
```

## Related Mech C Metrics (cumulative fire-206)

| Metric | Source | Fire | Description |
|--------|--------|------|-------------|
| `coverage_gap` | arXiv:2602.06836 | fire-202 | Fraction of games with zero dissenting bets; >0.3 = DMAD societal failure |
| `peer_error_rate_d` | arXiv:2604.06091 | fire-204 | Fraction of CK[D] peer picks that lost; >0.3 → `ck_adversarial_signal` |
| `info_asymmetry_score_d` | arXiv:2505.11556 | fire-206 | Fraction of agent bets with zero peer overlap; >0.4 → `ck_broadcast_failure` |

## Work-Queue Item

`vm-research-distributed-info-failure-multi-llm-fire206` (priority=98, owner=local-vm)

## Blocked By

Mech C schema push blocked by `do_not_push_hf_space_yet` gate. Implement in TF app.py when HF push gate opens.

## Related Research

- fire-202: arXiv:2602.06836 — LLM Active Alignment: Nash equilibrium; `coverage_gap` metric
- fire-204: arXiv:2604.06091 — Social Dynamics as Critical Vulnerabilities; `peer_error_rate_d` metric
- fire-198: arXiv:2511.17621 — Market-Making Multi-Agent LLM Coordination
