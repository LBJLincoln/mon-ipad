# SOTA Proposal: Market-Making as Multi-Agent LLM Coordination Framework

**Fire:** 198 (EVEN WebSearch)
**Paper:** arXiv:2511.17621 — "From Competition to Coordination: Market Making as a Scalable Framework for Safe and Aligned Multi-Agent LLM Systems" (Feb 2026)
**Relevance:** Validates TF Axelrod Mech A (Common Knowledge Broadcast) as a belief-propagation / price-discovery mechanism. Proposes extending TF Mech D+ with an explicit market-maker role.

---

## Paper Summary

The paper models multi-agent LLM coordination as a **prediction market** where:
- Each agent posts probabilistic bids/asks on shared outcomes
- A market-maker role aggregates peer posteriors into a consensus price
- Agents update beliefs via the consensus price (Bayesian belief propagation)
- The system converges toward truthful equilibrium with O(√T) regret (same bound as arXiv:2406.04062)

Key results:
- Market-making eliminates strategic manipulation incentives absent in Axelrod IPD
- Convergence speed proportional to agent count (scales well with 12-17 agents)
- Belief divergence from consensus price → natural KL-divergence signal for Mech C

---

## Validation of Existing TF Architecture

The Common Knowledge Broadcast (Mech A, fire-122) IS a degenerate market-making mechanism:
- CK block = consensus "price" posted at day-end
- Each agent's DMAD DIVERGE/AGREE response = implicit bid/ask relative to consensus
- `compute_consensus_distance(KL)` in Mech C = divergence from consensus price

This paper retroactively validates the entire Axelrod A→C pipeline as a well-grounded market-making system.

---

## Proposed Extension: Market-Maker Agent (Mech D+)

Add a **non-betting market-maker role** to the TF:
- One agent per day designated as market-maker (rotate by trailing performance inverse)
- Market-maker does NOT bet; instead aggregates peer probability estimates into a calibrated consensus
- Consensus probability injected into CK block as `MARKET_PRICE[game] = p_consensus` 
- Agents that bet against market price must justify divergence (already required by DMAD)
- Market-maker scored by Brier score of consensus forecast (not P&L)

**Expected benefit:** Reduces groupthink (consensus price reveals true central tendency) while preserving DMAD diversity pressure.

---

## Implementation Notes

### Target files
- `scripts/arena/hf-llm-trading-floor/app.py` — add `MarketMakerRole` class
- `scripts/arena/hf-political-trading-floor/app.py` — parity

### Key functions to add
```python
def designate_market_maker(state: Dict, day_date: str) -> str:
    """Returns tid of market-maker for today (inverse performance rotation)."""
    ...

def aggregate_market_price(allocations_by_agent: Dict, game_id: str) -> float:
    """Weighted-average probability across all agents for game_id outcome."""
    ...

def build_market_price_block(day_date: str, prev_allocations: Dict) -> str:
    """Formats MARKET_PRICE[...] block for injection into CK broadcast."""
    ...
```

### Scoring
Market-maker scored separately: `market_maker_brier = brier_score(consensus_probs, outcomes)`
Add `market_maker_brier` to Axelrod log (Mech C dataset).

---

## Blockers
- `do_not_push_hf_space_yet` — code changes must wait for HF push approval
- NBA TF 503 DOWN 135+d, POL TF IDLE 45+d — no live environment to test

## Priority
`vm-research-market-making-multi-llm-fire198` — priority=94 (after LLM strategic fingerprints fire-196)
