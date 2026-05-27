# SOTA Research Proposal: Social Dynamics as Critical Vulnerabilities in LLM Collectives

**Fire:** 204 (EVEN WebSearch)  
**Date:** 2026-06-01T08h  
**Paper:** arXiv:2604.06091 (2026) — "Social Dynamics as Critical Vulnerabilities that Undermine Objective Decision-Making in LLM Collectives"  
**Secondary:** arXiv:2601.05606 (2026) — "Conformity Dynamics in LLM Multi-Agent Systems: The Roles of Topology and Self-Social Weighting"

## Key Findings

### arXiv:2604.06091
Investigates how erroneous peer groups influence a single representative LLM agent in multi-agent systems that adopt human-like social structures (debates, collaborative discussions). Key finding: **when the peer majority is wrong, social dynamics actively override individual agent reasoning** — the collective can degrade a capable individual's EV to match the herd's mistaken consensus.

Direct validation of our DMAD anti-groupthink gate: this paper quantifies exactly the failure mode DMAD prevents. When COMMON_KNOWLEDGE[D] carries a majority-wrong consensus, agents that comply with CK without applying DMAD_DIVERGE annotation will systematically underperform.

### arXiv:2601.05606  
Characterizes conformity dynamics in LLM MAS, showing network topology and self-vs-social weighting jointly shape groupthink efficiency and robustness. Directly relevant to our Axelrod society architecture: the COMMON_KNOWLEDGE broadcast effectively increases social weighting for all agents. Mech B sacrificial rotation breaks conformity attractors by injecting archetype-diverse agents.

## Application to Axelrod-2026

### Mech C Post-Mortem Enhancement (priority = 97)
Add `peer_error_rate_d` field to `data/arena/axelrod-log/day-N.jsonl`:

```python
# In write_axelrod_log():
peer_error_rate_d = compute_peer_error_rate(day_date, agent_logs)
# = fraction of all peer bets in CK[D] that were resolved as losses
# When peer_error_rate_d > 0.30: CK[D] was adversarial (majority-wrong consensus)
```

Add `ck_adversarial_signal: bool` flag:
- `True` when `peer_error_rate_d > 0.30`
- When `ck_adversarial_signal = True`, agents citing CK peers without a contradicting external data source should NOT earn DMAD compliance credit
- This prevents CK-poisoning scenarios where the collective is systematically wrong

### DMAD Gate Amendment
When `ck_adversarial_signal` fires for day D:
- The DMAD gate in day D+1 prompts should include: `WARNING: Yesterday's peer consensus was adversarial (>30% loss rate). Citing peers as justification is INSUFFICIENT for DMAD compliance — must cite external data source.`
- This is the specific defense against the arXiv:2604.06091 vulnerability class

### Topology Insight (arXiv:2601.05606)
- Current Axelrod TF: fully connected topology (all agents see all CK data)
- Risk: high conformity under adversarial consensus
- Mitigation: Mech B sacrificial archetypes effectively act as "structural holes" in the conformity network — Burt network theory applied to LLM societies
- Future experiment: partial CK visibility (agents only see 50% random sample of peers) to reduce topology-induced conformity

## Implementation Priority

- Priority: 97 (after vm-research-llm-active-alignment-nash-fire202 at 96)
- Owner: local-vm
- Blocked by: do_not_push_hf_space_yet (NBA TF 503 DOWN, POL TF IDLE)
- Files to modify: both NBA + POL TF app.py write_axelrod_log() functions
- New field: `peer_error_rate_d` (float, 0.0-1.0) + `ck_adversarial_signal` (bool)
- New DMAD prompt amendment when signal fires

## Expected Impact

- Better paper dataset: distinguish "DMAD compliant days" from "CK-adversarial days" in post-mortem log
- When peer_error_rate_d > 0.3, expect: DMAD_DIVERGE picks to outperform consensus picks by larger margin (validates DMAD gate strength under adversarial conditions)
- Conformity Dynamics (arXiv:2601.05606): topology data (who cited whom) would allow network analysis of conformity propagation in CK — add `ck_cited_peers: list[str]` to each agent's day log for graph-theoretic analysis in the paper
