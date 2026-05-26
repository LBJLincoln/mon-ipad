# SOTA Research Proposal: Strategic Intelligence in LLMs via Evolutionary Game Theory

**Source:** arXiv:2507.02618  
**Title:** Strategic Intelligence in LLMs: Evidence from Evolutionary Game Theory  
**Authors:** Payne & Alloui-Cros (King's College London + University of Oxford)  
**Published:** July 2025  
**Detected:** fire-196 (2026-05-30T22h) EVEN WebSearch  
**Work-queue ID:** vm-research-llm-strategic-fingerprints-fire196 (priority=93)  

---

## Summary

First evolutionary Iterated Prisoner's Dilemma (IPD) tournament run entirely with frontier LLMs pitted against canonical game-theoretic strategies (Tit-for-Tat, Grim Trigger, Always-Defect, Always-Cooperate). Key contribution: LLMs do not play a single fixed strategy — they exhibit distinctive **provider-level strategic fingerprints** that persist across game variants.

### Key Findings

1. **Gemini models are strategically ruthless**: dominant defection bias, swift retaliation, low forgiveness rate. In evolutionary pressure conditions, Gemini agents trend toward Grim-Trigger-adjacent behavior.
2. **OpenAI models are more cooperative**: higher cooperation initiation rate, more forgiving after defection, closer to Tit-for-Tat profile.
3. **Strategic fingerprints are provider-level, not model-level**: behavior persists across Gemini Flash vs Pro, GPT-4o vs GPT-4o-mini — provider identity is the primary predictor of strategic posture.
4. **Shadow of the future matters**: termination probability varied at 10% / 25% / 75%. Higher termination probability (shorter horizon) suppresses cooperation in all LLMs. Lower termination probability restores cooperative equilibria — directly analogous to multi-day Axelrod tournament horizon effects.
5. **Mutation regime testing**: persistent mutation (equivalent to archetype reassignment) confirms strategic fingerprints are stable attractors, not transient.

---

## Relevance to TF Axelrod Mechanics

### Direct Mapping: Mech B (Sacrificial Role Reallocation)

Mech B assigns bottom-3 agents (by 7-day trailing bankroll) to `SACRIFICIAL_PROMPT[D]` forcing unused strategy archetypes. This paper provides empirical grounding for **provider-biased archetype assignment**:

- **Gemini agents → adversarial archetypes**: `sharps_fade`, `reverse_line_movement`, `divisional_hate`, `ref_bias_per_team` (NBA) / adversarial political archetypes (POL). Gemini's defection fingerprint maps naturally to contrarian/fade positions.
- **OpenAI agents → cooperative archetypes**: `sharps_follow`, `closing_line_value_only`, `pythagorean_divergence` (NBA) / consensus-tracking political archetypes (POL). OpenAI's cooperation fingerprint maps to trend-following / consensus positions.
- **Anthropic agents → mixed/adaptive archetypes**: No direct fingerprint data in paper; assign centrist archetypes, track empirically.

### Direct Mapping: compute_consensus_distance (KL divergence)

The paper's cooperation/defection measurement is essentially a behavioral divergence metric — the same conceptual operation as `compute_consensus_distance` (ε-smoothed KL divergence from peer consensus). Provider-stratified `peer_consensus_distance` distributions should show Gemini agents systematically farther from consensus (defectors diverge from group).

### Shadow of the Future → Multi-Day Tournament Horizon

Termination probability in IPD = inverse of remaining tournament days in TF. As the season nears end (fewer days remaining), the paper predicts LLM cooperation should decrease — betting behavior should become more aggressive/contrarian. Consider adding `days_remaining_in_season` to the `COMMON_KNOWLEDGE[D]` block (Mech A) so agents can modulate cooperation vs defection based on horizon.

---

## Proposed Implementation

### Phase 1 — Metadata (no TF push required)

Add `provider_strategic_profile` to agent metadata in both NBA TF and POL TF app.py:

```python
PROVIDER_STRATEGIC_PROFILE = {
    "gemini": "defector",      # Payne+Alloui-Cros 2025: ruthless, retaliatory
    "openai": "cooperator",    # Payne+Alloui-Cros 2025: cooperative, forgiving
    "anthropic": "adaptive",   # no data; empirical tracking
    "mistral": "adaptive",     # no data
    "meta": "adaptive",        # no data
}
```

### Phase 2 — Mech B Archetype Bias (requires TF push — BLOCKED by do_not_push_hf_space_yet)

In `assign_sacrificial_archetypes()`, weight archetype assignment by provider strategic profile:

```python
def assign_sacrificial_archetypes(agents, day_bankrolls, window=7):
    bottom3 = get_bottom3_by_trailing_bankroll(agents, day_bankrolls, window)
    for agent in bottom3:
        profile = PROVIDER_STRATEGIC_PROFILE.get(agent["provider"], "adaptive")
        if profile == "defector":
            archetype_pool = ADVERSARIAL_ARCHETYPES  # contrarian/fade
        elif profile == "cooperator":
            archetype_pool = COOPERATIVE_ARCHETYPES  # consensus/follow
        else:
            archetype_pool = AXELROD_ARCHETYPES  # full pool
        agent["archetype_assigned"] = random.choice(archetype_pool)
        agent["was_sacrificed"] = True
```

### Phase 3 — Provider-Stratified Analytics (Mech C / post-mortem log)

In `write_axelrod_log()`, add `provider_strategic_profile` to each agent's JSONL entry. This enables post-hoc analysis of:
- Per-provider bankroll trajectory
- Per-provider `peer_consensus_distance` distribution
- Cooperation vs defection rate by provider (cooperation proxy: distance from consensus)

---

## NBA Archetype Split by Profile

```python
ADVERSARIAL_ARCHETYPES_NBA = [
    'sharps_fade', 'reverse_line_movement', 'divisional_hate',
    'ref_bias_per_team', 'road_favorite_fade', 'back_to_back_fade',
    'national_tv_effect', 'revenge_narrative'
]

COOPERATIVE_ARCHETYPES_NBA = [
    'sharps_follow', 'closing_line_value_only', 'pythagorean_divergence',
    'shot_chart_mismatch', 'pace_inefficiency', 'rest_differential',
    'injury_arbitrage', 'steam_chase'
]
```

---

## Dependencies

- Mech B implementation (BLOCKED: do_not_push_hf_space_yet)
- Provider field in agent config (already present in TF agent definitions)
- No new ML infrastructure required; pure prompt/metadata change

## Priority

- Work-queue: `vm-research-llm-strategic-fingerprints-fire196` (priority=93)
- Unblocked portion (Phase 1 metadata design): can be implemented in app.py locally without TF push
- Blocked portion (Phase 2 runtime): requires HF Space push approval

## Citation

```
@article{payne2025strategic,
  title={Strategic Intelligence in LLMs: Evidence from Evolutionary Game Theory},
  author={Payne, [first name] and Alloui-Cros, [first name]},
  journal={arXiv preprint arXiv:2507.02618},
  year={2025}
}
```
