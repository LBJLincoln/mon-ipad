# SOTA Research Proposal: LLM-Agent Interactions on Markets with Information Asymmetries

**Source:** arXiv:2603.08853 (March 2026) — Alexander Erlei & Lukas Meub  
**Fire:** 200 (EVEN WebSearch)  
**Relevance:** Direct validation of Axelrod-2026 Mech A + design insight for Mech B

## Paper Summary

GPT-5.1 agents in credence goods markets characterized by information asymmetry between experts and consumers. Experimental conditions: institutional framework (free market, verifiability, liability), social preferences (default, self-interested, inequity-averse, efficiency-loving), reputation mechanisms — across one-shot and repeated 16-round interactions.

**Key findings:**
1. One-shot interactions: LLM cooperation FAILS — markets break down except under liability rules or efficiency-loving social preferences
2. Repeated interactions: competitive pricing emerges via reputation mechanism; fraud persists without other-regarding preferences
3. LLM consumers focus narrowly on prices rather than strategic incentives → vulnerable to exploitation
4. Social preference alignment critical: "Surplus shifts dramatically toward consumers under social-preference objectives"
5. vs. humans: LLM markets show higher participation, greater concentration, lower prices, polarized fraud patterns

## Validation of TF Design

| Paper Mechanism | TF-Axelrod Analogy |
|---|---|
| Reputation mechanism | COMMON_KNOWLEDGE[D] broadcast (Mech A) |
| Repeated interaction | Multi-day trading floor — same agent society every day |
| Liability rule | Mech B sacrificial role (bottom-3 forced archetype = performance penalty) |
| Social preference injection | AXELROD_CANON collective mission statement |
| Verifiability condition | Post-mortem log (Mech C) — audit trail creates accountability |

The paper validates the core Axelrod-2026 design: COMMON_KNOWLEDGE creates the "reputation + repeated interaction" structure that transforms one-shot failure into cooperative market equilibrium.

## Proposed Extensions (Priority=95)

### Extension 1: Social Preference Profile Injection

Add `social_preference_profile` field to agent system prompt derived from current bankroll rank:
- **Top 3 agents** (efficiency-loving): "Your performance rank is top-3. Adopt an efficiency-loving strategy — maximize collective surplus and cooperate freely with peers who propose pact allocations."
- **Mid agents** (inequity-averse, default): Current DMAD compliance unchanged.
- **Bottom 3 agents** (self-interested + liability): Current Mech B sacrificial role already implements this. Optionally add explicit liability framing.

### Extension 2: Liability Framing in Mech B Sacrificial Prompt

Current Mech B text assigns an archetype. Add:
> "Your prior strategy failed to generate positive EV for the society. This reassignment is the liability mechanism — like a contract clause requiring you to pivot to an unused strategy. Successfully executing the assigned archetype redeems your standing. Failure deepens your sacrificial status next day."

This maps directly to the paper's "liability rule" condition which enables cooperation even in one-shot settings.

### Extension 3: Exploit-Resistance Layer

Paper finding: LLM consumers focus on prices not strategy → vulnerable. TF analog: agents that purely follow COMMON_KNOWLEDGE consensus without strategic evaluation are vulnerable to herding. DMAD anti-groupthink clause already addresses this — but can be strengthened with an explicit "strategic suspicion" prompt for bottom-tier agents.

## Relationship to Existing Research Pipeline

| Prior Proposal | Complementarity |
|---|---|
| arXiv:2511.17621 (Market-Making, fire-198) | Market-maker role = expert in credence goods market |
| arXiv:2507.02618 (EGT fingerprints, fire-196) | Social preference = strategic fingerprint (Gemini ruthless = self-interested) |
| arXiv:2406.04062 (Online Learning, fire-192) | O(√T) regret = equilibrium path to competitive pricing |

## Implementation Priority

Priority=95 (after vm-research-market-making-multi-llm-fire198 priority=94). Implement after TF spaces are active (do_not_push_hf_space_yet lifted).

## Files
- Proposal: data/research-proposals/sota-llm-agents-markets-info-asymmetry-fire200.md (this file)
- Work-queue: vm-research-llm-agents-markets-info-asymmetry-fire200
