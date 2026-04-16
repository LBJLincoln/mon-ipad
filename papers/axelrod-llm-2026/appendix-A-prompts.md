# Appendix A — Prompt Templates

This appendix documents the ten archetype prompt templates $\pi_\tau$ for
$\tau \in \{1, \ldots, 10\}$ referenced in §3.4.1 and §4.2.3. The full
runtime-assembled prompt for agent $a_i$ on day $t$ consists of five
concatenated blocks:

1. `AXELROD_CANON` — fixed preamble (§3.6) reminding the agent of the
   cooperation rules.
2. `COMMON_KNOWLEDGE[t-1]` — day-$t-1$ resolution, leaderboard, reputation
   (Mech A, §3.3).
3. `ARCHETYPE[π_i^{(t)}]` — current archetype template (this appendix).
4. `CONTEXT[t]` — day-$t$ event bundle with odds, team stats, prior
   polling, etc.
5. `OUTPUT_SCHEMA` — JSON schema the agent must emit.

---

## A.1 Archetype Templates (source of truth)

The canonical templates are embedded in the implementation at
`scripts/arena/hf-llm-trading-floor/app.py` (NBA) and
`scripts/arena/hf-political-trading-floor/app.py` (political). They are
identical across corpora except for domain-specific examples. The
templates are released under the same license as the paper.

Each template opens with a one-sentence role description, followed by
a bullet list of reasoning principles and worked examples. Template
length is held to $200–400$ tokens to leave budget for `COMMON_KNOWLEDGE`
and `CONTEXT`.

| $\tau$ | Key principle | Example first-line |
|---|---|---|
| $\tau_1$ | Base-rate before evidence | "Begin every evaluation by stating the long-run base rate for home-team wins in similar matchups." |
| $\tau_2$ | Oppose consensus when edge permits | "When market consensus exceeds 70% confidence, actively look for reasons the consensus is wrong." |
| $\tau_3$ | Narrow calibration to odds midpoint | "Your predictions should rarely exceed $\pm 5$ percentage points from the book median." |
| $\tau_4$ | Weight recent form | "Give higher weight to the previous five games than to full-season averages." |
| $\tau_5$ | Discount recent streaks | "A five-game winning streak is usually reversion-to-mean fodder, not signal." |
| $\tau_6$ | Reason from biography | "Consider the coach's history, player motivations, and rivalry context before quantitative factors." |
| $\tau_7$ | Arbitrage across markets | "Look for inconsistencies between spread, moneyline, and total implied probabilities." |
| $\tau_8$ | Equal-risk allocation | "Size every bet so that its expected variance is equal; no bet exceeds 2× the next-smallest bet's variance." |
| $\tau_9$ | Require multiple signals | "Bet only when at least three independent signals (form, matchup, motivation) agree." |
| $\tau_{10}$ | High-variance, high-confidence | "Take the biggest stakes on your strongest convictions; hold cash otherwise." |

---

## A.2 Common-Knowledge Broadcast Format

The broadcast on day $t+1$ is assembled as:

```
=== COMMON KNOWLEDGE — Day {t} resolution ===
Games today: {k_t} games resolved.
Leaderboard (top-5): {top5 by bankroll}
Bottom 3: {bot3 by bankroll}
Reputation changes: {tid}: pact_honored +{n} / pact_broken +{m} (for each)
Collective JS divergence (yesterday): {JS(t-1):.3f} nats
Your rank yesterday: {rank_i}

=== END COMMON KNOWLEDGE ===
```

---

## A.3 Output Schema

Each agent emits:

```json
{
  "day_strategy": "2-sentence summary of today's approach",
  "allocations": [
    {
      "event_id": "nba_20251021_bos_at_phi",
      "probability_home": 0.68,
      "stake_pct": 0.04,
      "rationale": "short free-text rationale (1-2 sentences)"
    }, ...
  ],
  "coalition_proposal": "optional free-text coalition-pact proposal",
  "reputation_notes": "optional commentary on peer reputation"
}
```

Parsing is robust to (a) markdown-fenced JSON blocks, (b) prefix/suffix
free-text, and (c) partial missing fields (see §4.3.3).
