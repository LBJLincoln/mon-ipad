# PolySwarm: Multi-Agent LLM Prediction Market Trading

**Source:** arXiv:2604.03888 (April 4, 2026)
**Title:** "PolySwarm: A Multi-Agent Large Language Model Framework for Prediction Market Trading and Latency Arbitrage"
**Authors:** Rajat M. Barot, Arjun S. Borkhatariya
**Detected:** fire-208 EVEN WebSearch (2026-06-02T00h)

---

## Summary

PolySwarm deploys 50 diverse LLM personas concurrently evaluating binary outcome prediction markets (Polymarket). The system aggregates individual agent estimates through **confidence-weighted Bayesian combination** of swarm consensus with market-implied probabilities, and uses **quarter-Kelly position sizing** for risk-controlled execution.

Critically, the market analysis engine uses **KL divergence and Jensen-Shannon (JS) divergence** to detect cross-market inefficiencies and negation pair mispricings — independently converging on the same metric family used in Nomos TF Mech A `compute_consensus_distance(KL)`.

---

## Direct Relevance to Nomos TF

### 1. Architecture Validation
PolySwarm's 50-agent swarm is architecturally equivalent to Nomos TF's 12 NBA + 10 Political agents. Independent confirmation that multi-agent LLM diversity improves prediction market outcomes over single-agent baselines.

### 2. KL/JS Divergence Validation
PolySwarm's information-theoretic analysis engine uses KL divergence and JS divergence to detect market inefficiencies. This independently validates:
- `compute_consensus_distance(KL)` already implemented in Mech A COMMON_KNOWLEDGE[D]
- KL divergence as the correct metric for measuring agent consensus distance

**JS divergence upgrade**: JS divergence is bounded [0,1] and symmetric, making it more numerically stable than KL when agent distributions are sparse (common when only 3-4 agents bet on a given game/event). Add `js_divergence_d` to Mech C post-mortem log alongside `kl_div_d`.

### 3. Confidence-Weighted Bayesian Swarm Aggregation
Current COMMON_KNOWLEDGE[D] uses simple average consensus. PolySwarm uses confidence-weighted Bayesian combination of swarm consensus with market-implied probabilities.

**Upgrade path for Mech A:**
- Weight each agent's bet in the consensus block by their trailing 7-day accuracy (= bankroll growth factor used in Mech B rank)
- Downweight bottom-3 sacrificial agents' picks in CK[D] since they are by design using untested archetypes
- Formula: `ck_consensus[game] = Σ(w_i × pick_i) / Σ(w_i)` where `w_i = max(bankroll_growth_i_7d, 0.1)` (floor at 0.1 to prevent zero-weight silencing)

### 4. Quarter-Kelly Position Sizing
PolySwarm uses quarter-Kelly sizing for risk control. The current TF uses fixed stake sizing. Quarter-Kelly (bet = 0.25 × edge/odds) is the standard for multi-bet portfolios to avoid Kelly overbetting with correlated outcomes.

**Upgrade path for TF stake calibration:**
- Implement `quarter_kelly_stake(edge, odds, bankroll)` in both NBA + Political TF
- Apply per-agent, not to aggregate swarm

### 5. Latency Arbitrage Module
PolySwarm exploits stale prices using CEX-implied probabilities from log-normal pricing within the human reaction-time window. Less directly applicable to NBA game outcomes (no live line arbitrage), but relevant for:
- Intraday NBA line movement detection
- Closing line value (CLV) tracking — already in `closing_line_value_only` archetype

---

## Implementation Plan

### Phase 1: Add JS divergence to Mech C log (low-effort, high-value)
```python
# In compute_consensus_distance(), add JS alongside KL
from scipy.spatial.distance import jensenshannon
js_dist = jensenshannon(agent_dist_smooth, consensus_dist_smooth)
```

### Phase 2: Confidence-weighted Bayesian COMMON_KNOWLEDGE[D]
Replace in `build_common_knowledge_block()`:
```python
# Current: simple average
consensus_pick = sum(picks) / len(picks)
# New: confidence-weighted
weights = [max(bankroll_growth_7d[tid], 0.1) for tid in trader_ids]
consensus_pick = sum(w*p for w,p in zip(weights, picks)) / sum(weights)
```

### Phase 3: Quarter-Kelly stake calibration
```python
def quarter_kelly_stake(edge_estimate, decimal_odds, bankroll):
    kelly_fraction = (edge_estimate * decimal_odds - (1 - edge_estimate)) / (decimal_odds - 1)
    return max(0, 0.25 * kelly_fraction * bankroll)
```

---

## Expected Impact

- JS divergence in Mech C: enables bounded [0,1] normalized consensus distance metric for paper — no change to agent behavior
- Confidence-weighted CK[D]: better signal quality for top agents; reduces noise from sacrificial-class agents whose archetypes are untested → expected 2-5% improvement in society-level EV
- Quarter-Kelly: reduces variance from overbetting correlated outcomes (NBA games on same night share weather/travel confounders) → reduces ruin probability for individual agents

---

## Work Queue

- `vm-research-polyswarm-multi-agent-llm-fire208` (priority=99)
- Blocked by: `do_not_push_hf_space_yet`
- Depends on: Mech B + Mech C implementation

---

## References

- arXiv:2604.03888: PolySwarm (directly validates TF + KL divergence)
- arXiv:2406.04062 (fire-192): Online Learning in Betting Markets — O(√T) regret, complements quarter-Kelly sizing
- arXiv:2602.06836 (fire-202): LLM Active Alignment Nash Equilibrium — confirms confidence-weighted aggregation breaks Nash groupthink attractors
