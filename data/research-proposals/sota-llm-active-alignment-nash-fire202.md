# SOTA Research Proposal: LLM Active Alignment via Nash Equilibrium

**Source:** arXiv:2602.06836 — "LLM Active Alignment: A Nash Equilibrium Perspective" (Feb 2026)
**Detected:** fire-202 EVEN WebSearch (2026-06-01T00h)
**Priority:** 96

## Core Finding

LLM populations, when allowed to observe each other's outputs (common knowledge), can converge to a Nash equilibrium where certain prediction regions are systematically ignored — "epistemic exclusion." Any individual agent deviating from the consensus bears reputation cost; the equilibrium is self-reinforcing even when the excluded predictions have positive EV.

## Direct Mapping to Axelrod TF

| Nash paper concept | Axelrod TF mechanism |
|---|---|
| Epistemic exclusion | Groupthink on consensus picks → some games never get a dissenting bet |
| Active alignment perturbation | Mech B sacrificial reallocation — breaks the Nash attractor by forcing archetype diversity |
| Nash equilibrium characterization | DMAD anti-groupthink gate (Mech A) measures KL-distance from consensus; but KL alone doesn't catch excluded zones |
| Coverage gap metric (proposed) | `coverage_gap` = fraction of games/events where ALL agents agree direction — societal DMAD failure signal |

## Proposed Implementation

### Add `coverage_gap` to Mech C post-mortem log (day-N.jsonl)

```python
def compute_coverage_gap(day_bets: list[dict]) -> float:
    """Fraction of games where all agents bet the same direction (zero dissent)."""
    from collections import defaultdict
    game_directions = defaultdict(set)
    for bet in day_bets:
        game_directions[bet["game_id"]].add(bet["pick"])  # e.g. "home" / "away"
    no_dissent = sum(1 for dirs in game_directions.values() if len(dirs) == 1)
    return no_dissent / max(len(game_directions), 1)
```

### Thresholds
- `coverage_gap < 0.2` → healthy epistemic diversity (target)
- `coverage_gap 0.2–0.3` → WATCH, increase Mech B sacrifice rate
- `coverage_gap > 0.3` → DMAD societal failure, trigger emergency archetype rotation

### Nash equilibrium validation metric
Track per-agent `nash_deviation_distance` = KL(agent_picks || society_consensus). If all agents cluster near 0, the society has converged to a groupthink Nash attractor — Mech B should fire regardless of bankroll ranking.

## Expected Impact
- Quantifies DMAD effectiveness as a single scalar per day
- Provides paper dataset primary metric for Mech A validation
- Guides Mech B trigger sensitivity (supplement bankroll-rank trigger with coverage_gap trigger)

## Implementation Path
1. Add `coverage_gap` and `nash_deviation_distance` to Mech C day-N.jsonl schema
2. Surface in Gradio dashboard as "Society Epistemic Diversity" chart
3. Backfill from existing Mech A logs if available

## References
- arXiv:2602.06836 (Nash equilibrium in LLM populations)
- arXiv:2406.04062 (ICML 2024, online learning in prediction markets — O(√T) regret)
- arXiv:2511.17621 (market-making multi-agent LLM coordination)
