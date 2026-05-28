# SOTA: Coordination as Architectural Layer for LLM-Based Multi-Agent Systems

**Source:** arXiv:2605.03310 (May 2026, Maksym Nechepurenko & Pavel Shuvalov, Devnull FZCO)
**Title:** "Coordination as an Architectural Layer for LLM-Based Multi-Agent Systems: An Information-Controlled Empirical Study on Prediction Markets"
**Added:** fire-218 (2026-06-03T16h)

## Key Findings

1. **Failure root cause:** 41–87% of multi-agent LLM failures in production originate from coordination defects (specification/coordination issues), NOT from base-model capability limitations.
2. **Coordination as architecture:** Coordination should be a configurable architectural layer, separable from agent logic and information access — enabling principled system design.
3. **Empirical study:** 100 Polymarket binary markets resolved after model training cutoff (claude-opus-4-6). Fixed LLM, fixed tools, fixed per-call output cap, fixed prompt template across 5 reference coordination configurations.
4. **Results:** Murphy calibration signatures, cost–quality Pareto frontier, category-conditioned analysis, bootstrap power-projection. 3/5 pre-specified predictions upheld in direction; 2 configurations dominate the Pareto frontier.

## Applications to Nomos42 TF

### Application 1 — Validate Mech A as Coordination Fix
The 41–87% failure rate from coordination defects directly validates the Axelrod CK broadcast (Mech A) as a structural fix. CK[D] provides the "coordination layer" separating agent logic from shared market belief.

### Application 2 — Murphy Score Audit Field (Mech C)
Add `murphy_score_d` to the Mech C post-mortem log (`data/arena/axelrod-log/day-N.jsonl`). Murphy scoring measures calibration quality of probabilistic predictions — directly applicable to each agent's daily probability estimates.

### Application 3 — Cost–Quality Pareto for Agent Configurations
Add `cost_per_alpha_unit` (LLM tokens / realized edge) to Mech C log. Builds the empirical cost-quality frontier for Mech B archetype configurations (maps to paper's 5 reference coordination configurations).

### Application 4 — Coordination Configuration Ablation
The 5 reference coordination configurations map to Mech A/B/C on/off states:
- Config 1: No CK (Mech A off, B off, C off)
- Config 2: CK only (Mech A on, B off, C off)
- Config 3: CK + roles (Mech A on, B on, C off)
- Config 4: Full Axelrod (Mech A+B+C on)
- Config 5: Full Axelrod + bias-inverse (A+B+C + fire-212 h̃ correction)
Run ablation when TF spaces go live and publish Murphy signatures.

## Work-Queue Entry
- ID: `vm-research-coordination-layer-llm-fire218`
- Priority: 103
- Target: Mech C post-mortem log — add `murphy_score_d` + `cost_per_alpha_unit`
- Blocked by: do_not_push_hf_space_yet + NBA-503-DOWN + POL-IDLE
