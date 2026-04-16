# 5. Results

This section reports the empirical evaluation of the LPSG framework on the
full 2025-26 NBA season (1,257 games) and the 2025-26 US political event
corpus (1,120 events). Numerical entries marked `[auto]` are filled
automatically from `data/arena/axelrod-log/` once the full-season run
resolves; the surrounding analysis, hypotheses, and statistical protocol
are pre-registered (§4.7) and do not depend on the numerical values.
All confidence intervals are paired bootstrap at 95% coverage unless
noted, and all p-values are Holm–Bonferroni adjusted across the six
pairwise baseline comparisons.

---

## 5.1 Main Result — Full LPSG vs Baselines

Table 4 reports the primary endpoints on the NBA corpus: ensemble Brier
score, end-of-season Kelly bankroll ROI (starting at \$100 per agent),
mean collective Jensen–Shannon divergence $\mathrm{JS}(t)$, ensemble
ambiguity $A(t)$, and win rate on placed bets.

| Configuration | Ensemble Brier ↓ | Kelly ROI (%) ↑ | JS (nats) ↑ | Ambiguity $A$ ↑ | Bets | Win rate |
|---|---:|---:|---:|---:|---:|---:|
| **Full LPSG (ours)** | `[auto]` | `[auto]` | `[auto]` | `[auto]` | `[auto]` | `[auto]` |
| No-SRR (ablation) | `[auto]` | `[auto]` | `[auto]` | `[auto]` | `[auto]` | `[auto]` |
| No-CK (ablation) | `[auto]` | `[auto]` | `[auto]` | `[auto]` | `[auto]` | `[auto]` |
| No-Pacts (ablation) | `[auto]` | `[auto]` | `[auto]` | `[auto]` | `[auto]` | `[auto]` |
| DMAD-style [@liu2025dmad] | `[auto]` | `[auto]` | `[auto]` | `[auto]` | `[auto]` | `[auto]` |
| Fixed-ensemble | `[auto]` | `[auto]` | `[auto]` | `[auto]` | `[auto]` | `[auto]` |
| Single-model-best | `[auto]` | `[auto]` | — | — | `[auto]` | `[auto]` |
| Market-consensus | `[auto]` | — | — | — | — | — |

*Table 4. Primary endpoints on the NBA corpus (1,257 games). Arrows indicate
the favorable direction. Bold = Full LPSG vs the strongest ablation row.
Statistical significance ($p < 0.01$, Holm–Bonferroni corrected) is marked
in the auto-fill with an asterisk on the Brier column. The Political
corpus appears in Table 5.*

Table 5 (political corpus, same structure) appears in Appendix D for space.

**Primary hypothesis (pre-registered).** Full LPSG strictly dominates all
six ablation/baseline configurations on ensemble Brier, with the effect
attributable primarily to the combined action of Mech A (common-knowledge
broadcast) and Mech B (SRR). The No-SRR row isolates the contribution of
Mech B. The No-CK row isolates the contribution of Mech A.

**Result interpretation (outline, pre-registered direction).** Conditional on
the sign of the SRR effect matching Proposition 2 (§3.7), we expect
$\Delta\mathrm{Brier}_{\text{Full} - \text{No-SRR}} < 0$ and
$\Delta A_{\text{Full} - \text{No-SRR}} > 0$. The magnitude of these
effects, and their relative contribution vs common-knowledge broadcast,
is the central empirical question we answer in §6.

---

## 5.2 SRR Activity and Archetype Dynamics

Figure 1 (to be rendered from `data/arena/axelrod-log/nba/*.jsonl`) shows
the time-series of:

- (a) *Daily SRR firing rate*: number of agents sacrificed per day;
- (b) *Archetype occupancy*: count of agents per archetype $\tau$ as a
  function of day $t$;
- (c) *Consensus distance distribution*: the $L^1$ distance between each
  agent's per-day allocation and the society-mean allocation.

Summary statistics:

- Mean SRR firings per day: `[auto]` ± `[auto]` (std across days).
- Median agent tenure per archetype before re-sacrifice: `[auto]` days.
- Fraction of days with at least one SRR firing: `[auto]`.
- Archetypes with highest mean occupancy: `[auto]` (top 3).
- Archetypes with lowest mean occupancy: `[auto]` (bottom 3).

We expect, consistent with Proposition 1, that no archetype has occupancy
$= N$ on any day (no pure-imitation equilibrium).

---

## 5.3 Common-Knowledge Broadcast Effect

The No-CK ablation removes the day-end common-knowledge block while
preserving all other mechanisms. We compare Full LPSG against No-CK on:

- Ensemble Brier: difference `[auto]` (95% CI `[auto]`, $p=$`[auto]`).
- Coordination-on-pacts: fraction of proposed pacts that are honored:
  Full `[auto]` vs No-CK `[auto]`.
- Reputation dynamics: mean absolute reputation score at end of season:
  Full `[auto]` vs No-CK `[auto]`.

The theoretical prediction is that common-knowledge broadcast enables
the reputation-mediated indirect-reciprocity dynamics of Mech D; without
it, pacts should collapse to pairwise-only coordination, yielding lower
honor rates.

---

## 5.4 Coalition Pact Evolution (Mech D)

Figure 2 plots the cumulative count of proposed pacts, honored pacts, and
broken pacts over the season. Summary endpoints:

- Total pacts proposed (Full LPSG): `[auto]`.
- Honor rate: `[auto]` ± `[auto]`%.
- Agents ever accumulating positive reputation: `[auto]` / 12.
- Strongest cooperative pair (by shared-honor count): `[auto]` + `[auto]`
  (`[auto]` shared honors).
- Most defected-against agent (highest `pact_broken` count received):
  `[auto]`.

The cooperative structure that emerges is compared against Axelrod's
original Tit-for-Tat finding in §6.3.

---

## 5.5 Calibration Diagnostics

Figure 3 shows 10-bin reliability diagrams for (a) the best individual agent
by Brier, and (b) the Full LPSG ensemble. We report expected calibration
error (ECE) and the Brier decomposition (reliability / resolution /
uncertainty).

| Metric | Best agent | Full LPSG ensemble |
|---|---:|---:|
| Brier | `[auto]` | `[auto]` |
| Reliability ↓ | `[auto]` | `[auto]` |
| Resolution ↑ | `[auto]` | `[auto]` |
| Uncertainty | `[auto]` | `[auto]` |
| ECE (10-bin) ↓ | `[auto]` | `[auto]` |

The pre-registered prediction is that the ensemble improves on reliability
(calibration) by averaging out individual-agent miscalibration while
preserving resolution (the informativeness of predictions). This is the
Krogh–Vedelsby [@krogh1995neural] decomposition applied to calibration.

---

## 5.6 Diversity–Accuracy Coupling

Figure 4 scatters per-day $\mathrm{JS}(t)$ against per-day ensemble Brier.
A negative slope in this scatter is the *direct empirical validation* of
Proposition 2 (§3.7): diversity, measured as JS divergence, is associated
with lower ensemble Brier.

| | Estimate (95% CI) | $p$ |
|---|---:|---:|
| Slope of $\mathrm{JS}(t)$ on Brier (per-day) | `[auto]` | `[auto]` |
| Spearman $\rho$ (JS vs $-$Brier) | `[auto]` | `[auto]` |
| Granger causality test (JS → Brier, lag 1) | `[auto]` F, $p=$`[auto]` | — |

Negative slope and positive Spearman indicate that diversity *precedes*
accuracy gains (not vice versa). We report the per-day residuals in
Appendix D.

---

## 5.7 Between-Seed Robustness

Full LPSG was run $n=5$ times with identical data and identical LLM
settings, varying only the SRR sampling RNG seed. We report the between-run
standard deviation on the primary endpoints:

| Endpoint | Full LPSG mean | Between-run std | Coeff. of variation |
|---|---:|---:|---:|
| Ensemble Brier | `[auto]` | `[auto]` | `[auto]` |
| Kelly ROI | `[auto]` | `[auto]` | `[auto]` |
| Mean JS divergence | `[auto]` | `[auto]` | `[auto]` |
| SRR firings / day | `[auto]` | `[auto]` | `[auto]` |

Low coefficient of variation ($< 0.10$) is the pre-registered criterion
for *stable* SRR behavior; values exceeding this threshold would indicate
that results are sensitive to the SRR sampling stream and require
stochastic averaging for reliable inference.

---

## 5.8 Summary of Findings

Table 6 condenses the six headline effects for §6 discussion.

| Claim | Supporting row | $\Delta$ direction | Significance |
|---|---|---:|---:|
| SRR improves ensemble Brier | §5.1 row 1 vs row 2 | `[auto]` | `[auto]` |
| CK broadcast improves Brier | §5.1 row 1 vs row 3 | `[auto]` | `[auto]` |
| Pacts increase honor rate | §5.4 | `[auto]` | `[auto]` |
| SRR increases diversity | §5.2 + §5.6 | `[auto]` | `[auto]` |
| Diversity precedes accuracy (Granger) | §5.6 | `[auto]` | `[auto]` |
| Results stable across seeds | §5.7 CV | `[auto]` | — |

Interpretation of this synthesis, and its connection to Axelrod's
original cooperation findings, constitutes §6.
