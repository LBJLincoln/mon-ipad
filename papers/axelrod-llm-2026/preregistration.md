# Pre-Registration Document — Axelrod-LLM Experimental Evaluation

**Frozen on:** 2026-04-16 (prior to first full-season experimental run).
**Git hash at freeze:** `df0d0d72c` (§3 complete, paper branch
`paper/axelrod-cycle2`).
**Subsequent analysis that *changes* anything below must be clearly
labeled post-hoc in §6.**

---

## Scope

This document pre-registers the experimental protocol for the evaluation
of the LPSG framework described in §3 of the accompanying paper. The
purpose is to prevent post-hoc shaping of hypotheses or analyses to fit
observed data.

## Frozen Components

### 1. Mechanisms
Four mechanisms, as specified in §3.3–§3.6:
- **A**: Common-knowledge broadcast of day-end resolution, leaderboard,
  reputation, and collective JS divergence.
- **B**: Sacrificial Role Reallocation with window $W = 7$, threshold
  $\epsilon = 1.0$, Boltzmann $\beta = 2.0$, taxonomy size $M = 10$.
- **C**: Per-day post-mortem logging of all agent decisions to
  `data/arena/axelrod-log/{nba,political}/day-NNN.jsonl`.
- **D**: Coalition pacts + reputation, with `pact_honored` and
  `pact_broken` counters visible in next-day broadcast.

### 2. Archetype Taxonomy (M = 10)
The ten archetypes listed in §3.4.1 are frozen. Adding or removing an
archetype constitutes a separate experiment, not a variation of this one.

### 3. Evaluation Metrics
- Primary: Ensemble Brier score; end-of-season Kelly bankroll ROI.
- Secondary: Mean collective Jensen–Shannon divergence; Krogh–Vedelsby
  ambiguity $A(t)$; win rate on placed bets.
- Diagnostic: 10-bin reliability, ECE, Brier decomposition (reliability /
  resolution / uncertainty).

### 4. Baseline Configurations
Eight baseline/ablation configurations, as enumerated in Table 3 of §4.5.
Adding or removing a baseline, or modifying a baseline's mechanism set,
requires separate pre-registration.

### 5. Datasets
- NBA: full 2025-26 regular season (1,257 games, 2025-10-21 through
  2026-04-12).
- Political: 2025-26 US event stream (1,120 events, 2025-10-01 through
  2026-04-10).

No in-domain train/evaluation split; all evaluation is forward-walking
and causal (agents see only day-$t$ context when predicting day-$t$
events).

### 6. Agent Pool
12 NBA and 10 political agents as specified in Table 2 (§4.2). The pool
is identical across all baseline configurations; only the mechanism set
differs. Provider selection, model version pins, and Axelrod-1980 seed
mapping are frozen at this document's freeze time.

### 7. Statistical Protocol
- Paired bootstrap at $B = 10{,}000$ resamples, per-day resampling level.
- Holm–Bonferroni correction across the six primary comparisons.
- Reported 95% CIs and Holm-adjusted $p$-values for all pairwise tests.
- Pre-registered family-wise error rate $\alpha = 0.05$.

### 8. Between-Seed Replication
Full LPSG is replicated $n = 5$ times with different SRR sampling seeds.
No other configuration is replicated — only the primary configuration
has between-seed variance reported.

### 9. Hypothesis Direction
All six primary comparisons are one-sided: Full LPSG is pre-registered to
weakly dominate each ablation on Brier. Two-sided significance is
reported but the primary evidence is directional.

### 10. Exclusion Rules
- Days with zero placed bets across all agents are excluded from Brier
  computation for all configurations (not just LPSG).
- Games/events where the LLM failure rate exceeds 30% of agents are
  flagged but included; results are reported with and without these
  "degraded" days.
- No other data-dependent exclusion is pre-registered.

## Analysis Plan

### 10.1 Primary Analysis
Table 4 of §5.1, with all eight configurations and their pairwise
comparisons against Full LPSG. No data-dependent modification of Table 4
structure is permitted under this pre-registration.

### 10.2 Secondary Analyses (pre-registered)
- Time-series plots (Figures 1–4) as specified in §5.2–§5.6.
- Between-seed variance table (§5.7).

### 10.3 Post-Hoc Analyses
Any analysis not listed above, if reported, will be clearly labeled
**(post-hoc)** in §6 and will not be cited as confirmatory evidence of
the primary hypothesis.

## Release

This document is released at `papers/axelrod-llm-2026/preregistration.md`
on the paper branch `paper/axelrod-cycle2` at freeze time. Any
substantive modification after freeze is recorded in this document's git
history and noted explicitly in the published paper.
