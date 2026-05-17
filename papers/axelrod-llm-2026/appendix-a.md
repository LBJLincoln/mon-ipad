# Appendix A — Strategy Archetype Taxonomy

This appendix documents the full $K = 20$ strategy archetype taxonomy $\mathcal{R}$
operationalised in the LPSG experiments (§3.1, §4.4). Each archetype corresponds to
a system-prompt module that shapes the agent's reasoning disposition, position
construction logic, and risk tolerance. Modules are composable with the shared mission preamble (§3.4) and are swapped atomically during SRR events
(§3.4) without modifying the agent's prediction history or bankroll state.

---

## A.1  Design Principles

The taxonomy was constructed to satisfy three criteria:

1. **Span.** The 20 archetypes should cover the five orthogonal dimensions
   identified in §4.4: (D1) position construction, (D2) risk appetite,
   (D3) information source priority, (D4) temporal horizon, and
   (D5) ensemble relationship.

2. **Distinguishability.** Every archetype pair $(r^{(a)}, r^{(b)})$ must satisfy
   $\hat{\epsilon}_{\text{arch}}(r^{(a)}, r^{(b)}) \geq 0.037$ on the 2024–25 pilot
   (Assumption A1; §3.5). The full pairwise distinguishability matrix is in Table B.2
   (pre-registered; subject to pilot backtest confirmation — any pair failing the
   threshold will trigger archetype revision before Conditions B–E run).

3. **Non-cherry-picking.** No archetype was designed with knowledge of which
   LLM model or provider would be initially assigned to it, preventing
   archetype–model collusion in the initial assignment.

Archetypes were drafted over four rounds of pilot testing on the 2023–24
NBA season (held out from all evaluation), and any pair failing the
$\epsilon_{\text{arch}}$ threshold was merged or revised before the
2025–26 experimental season began.

---

## A.2  Five-Dimension Design Space

| Dimension | Label | Poles |
|-----------|-------|-------|
| D1 | Position construction | quantitative ←→ narrative; contrarian as a third axis |
| D2 | Risk appetite | aggressive ←→ conservative; diversified as a third axis |
| D3 | Information source | market signals ←→ statistical features ←→ situational context |
| D4 | Temporal horizon | short-term momentum ←→ long-term mean-reversion |
| D5 | Ensemble relationship | independent ←→ coordinator ←→ devil's-advocate |

---

## A.3  Full Taxonomy Table

Each archetype is identified by a short name, its primary dimension, an initial
occupancy flag (whether any agent was assigned this archetype at day 0), and the
minimum Kelly stake cap $\kappa_{\min}$ enforced by the module.

| # | Archetype | Dimension | Initially Occupied | $\kappa_{\min}$ |
|---|-----------|-----------|--------------------|------------------|
| 1 | quantitative | D1 | NBA: T1 · POL: T1 | 0.05 |
| 2 | analytical | D1 | NBA: T4 · POL: T4 | 0.04 |
| 3 | narrative | D1 | — (vacant at day 0) | 0.04 |
| 4 | contrarian | D1 | NBA: T3 · POL: T3 | 0.04 |
| 5 | aggressive | D2 | NBA: T9 · POL: T9 | 0.08 |
| 6 | conservative | D2 | — (vacant at day 0) | 0.01 |
| 7 | diversified | D2 | NBA: T7 · POL: T7 | 0.03 |
| 8 | disciplined | D2 | NBA: T12 · POL: — | 0.03 |
| 9 | tactical | D3 | NBA: T5 · POL: T5 | 0.05 |
| 10 | value | D3 | — (vacant at day 0) | 0.04 |
| 11 | arbitrage | D3 | NBA: T2 · POL: T2 | 0.06 |
| 12 | wide-coverage | D3 | NBA: T8 · POL: T8 | 0.02 |
| 13 | momentum | D4 | — (vacant at day 0) | 0.05 |
| 14 | mean-reversion | D4 | — (vacant at day 0) | 0.04 |
| 15 | theoretical | D4 | NBA: T10 · POL: T10 | 0.03 |
| 16 | chain-of-thought | D4† | NBA: T11 · POL: — | 0.05 |
| 17 | ensemble | D5 | NBA: T6 · POL: T6 | 0.04 |
| 18 | coordinator | D5 | — (vacant at day 0) | 0.04 |
| 19 | devil's-advocate | D5 | — (vacant at day 0) | 0.05 |
| 20 | adaptive | D5 | — (vacant at day 0) | 0.03 |

*Table A.1: Full $K = 20$ archetype taxonomy. The "Initially Occupied" column
lists which NBA/political agent holds the archetype at day 0 using the
agent indices from Table 3 (§4.1). Eight archetypes are vacant in the NBA domain
at day 0 ($\mathcal{V}_0^{\text{NBA}} = \{3, 6, 10, 13, 14, 18, 19, 20\}$); the
political domain additionally has archetypes 8 and 16 vacant, giving
$\mathcal{V}_0^{\text{POL}} = \{3, 6, 8, 10, 13, 14, 16, 18, 19, 20\}$ (10 archetypes). SRR draws from the domain-appropriate vacancy pool (Definition 2, §3.4).*

*†: Archetype 16 is a process modifier (extended deliberation) rather than a pure temporal-horizon type; see §A.4.4 for classification rationale.*

---

## A.4  Per-Archetype Entries

Each entry gives: (i) a one-paragraph description of the reasoning disposition,
(ii) the core prompt directive (abbreviated — full prompt in
`data/arena/archetypes/<name>.txt`), and (iii) practical notes on
interaction with the Kelly-cap mechanism.

---

### A.4.1  Dimension D1 — Position Construction

---

**1. Quantitative**

*Description.* The quantitative archetype treats prediction as a regression
problem. The agent is directed to first read the feature-engine oracle summary
and assign a probability proportional to the oracle's confidence interval.
Narrative signals (injuries, travel, chemistry) are incorporated only when
backed by a quantitative proxy (e.g., an injury-adjusted RAPTOR delta).
The archetype resists anchoring to betting-line consensus when the oracle
signal diverges by $\geq 3$ percentage points.

*Core directive.* "Begin with the statistical model probability. Adjust by
no more than 5 pp based on qualitative factors unless the oracle confidence
interval is wide ($\sigma > 0.08$). Report calibrated probability to two
decimal places."

*Kelly note.* Assigned risk weight $\rho_i = 0.55$ for T1 (Qwen 3 235B) (Table 3), reflecting
the model's strong reasoning capacity and the archetype's empirically low
false-positive rate on oracle-aligned bets.

---

**2. Analytical**

*Description.* The analytical archetype integrates quantitative and qualitative
signals via a structured weighing procedure. The agent is instructed to construct
a four-factor model at prediction time: (a) oracle probability, (b) market-implied
probability from the spread, (c) situational context score (travel, rest, injury),
and (d) recent form divergence from season average. Each factor is assigned an
explicit weight, and the final prediction is a weighted average with documented
justification. This archetype produces the most verbose chain-of-thought of any
D1 type, which is appropriate for high-capacity models.

*Core directive.* "Score each of the four factors independently on $[0, 1]$.
Combine as a weighted sum with weights (0.40, 0.25, 0.20, 0.15).
State the resulting probability and the single factor that most diverged
from its default weight."

*Kelly note.* Medium-cap ($\kappa_{\min} = 0.04$); performance tends to be
stable rather than high-variance.

---

**3. Narrative** *(vacant at day 0)*

*Description.* The narrative archetype inverts the quantitative priority:
news, locker-room dynamics, coaching adjustments, and motivational context
(elimination games, rivalry history) are treated as primary signals.
Statistical features serve as a sanity check rather than a prior.
The archetype explicitly accepts divergence from the oracle when the narrative
signal is strong and recent ($\leq 48$ hours). It is designed to be most
useful in high-information environments (playoff series, late-season games
with postseason implications) where the feature engine may lag.

*Core directive.* "Identify the single most important narrative driver for
today's game. If this driver is absent from the oracle summary, assign it
independent weight of up to 15 pp. Document whether your prediction agrees
with or diverges from the market implied probability, and why."

*Vacancy rationale.* No agent is assigned this archetype at day 0 because
the initial NBA cohort (T1–T12) is weighted toward quantitative and statistical
reasoning. SRR targets this archetype when the society lacks qualitative
divergence.

---

**4. Contrarian**

*Description.* The contrarian archetype treats market over-reaction as the
primary exploitable signal. The agent identifies the crowd-favourite in each
game (the team with the shorter moneyline) and constructs a prior probability
$5$–$10$ pp below the market-implied favourite probability. This prior is
updated toward the market only when the oracle confidence interval is narrow
(high conviction). The archetype embodies Keynes's "beauty contest" framing:
predicting what the crowd believes the crowd believes, then fading it.

*Core directive.* "Default position: fade the favourite by 5–7 pp unless
the oracle $\sigma < 0.05$ (strong model conviction). Document the implied
market probability and your deviation from it. Do not override contrarian
prior when the crowd consensus exceeds 70%."

*Kelly note.* Contrarian positions tend to be smaller-field bets;
$\rho_i = 0.55$ for T3 (Table 3) reflects the model's willingness to sustain
short-run drawdowns while awaiting mean-reversion.

---

### A.4.2  Dimension D2 — Risk Appetite

---

**5. Aggressive**

*Description.* The aggressive archetype maximises expected bankroll growth
subject to the Kelly criterion. The agent carries personality risk weight $\rho_i = 0.70$ (Table 3), the
highest in the cohort, allowing realised stakes $\kappa_i \times \rho_i$
up to 70% of the formula-derived Kelly cap on high-confidence
predictions (oracle $p > 0.65$ or $p < 0.35$). It accepts larger short-run
Brier variance in exchange for compound growth potential. The archetype is
assigned only to models with sufficient capacity to avoid systematic
miscalibration at extreme probabilities.

*Core directive.* "When oracle confidence is high (probability outside
$[0.40, 0.60]$), you may increase stake by up to 30% above default Kelly.
State your edge estimate and justify the increased allocation explicitly."

---

**6. Conservative** *(vacant at day 0)*

*Description.* The conservative archetype inverts the aggressive priority:
minimise Brier score, not bankroll. The agent is capped at 30% of standard
Kelly, never reports probabilities outside $[0.20, 0.80]$ (shrinkage toward
the base rate), and defaults to PASS when edge is ambiguous. This archetype
is the most risk-averse in the taxonomy and is designed for poorly-calibrated
SRR entrants that need a "rehabilitation" mode before exposure to large stakes.

*Core directive.* "Cap all positions at 30% of default Kelly. Shrink extreme
predictions toward 0.50 by 10 pp. When uncertain, PASS. Report Brier
improvement as your primary KPI, not bankroll."

---

**7. Diversified**

*Description.* The diversified archetype adopts a portfolio mindset: maximise
the number of non-correlated predictions per day rather than concentrating on
high-conviction plays. Each position is small ($\leq 2$% of bankroll) but the
archetype requires a minimum of five predictions per day. This breadth strategy
is motivated by the ensemble ambiguity decomposition (§3.3): independent small
errors cancel in the ensemble, even when individual predictions are only
marginally calibrated.

*Core directive.* "Generate at least 5 independent predictions today, drawn
from different matchup contexts (different conferences, different time slots).
Cap each stake at 2% of bankroll. Prioritise diversity of matchup type over
depth of per-matchup analysis."

---

**8. Disciplined**

*Description.* The disciplined archetype enforces a strict edge threshold for
participation: the agent only predicts when its estimated probability diverges
from the market implied probability by $\geq 4$ pp and the oracle confidence
interval is narrow. When the threshold is not met, the agent PASSES without
prediction. This produces fewer but higher-conviction predictions. The
archetype is well-suited to small-model self-hosted agents (e.g., T12) that
may produce noisy outputs; the edge gate filters out low-quality predictions
before they are scored.

*Core directive.* "If your probability estimate is within 4 pp of the market
implied probability, PASS. If oracle $\sigma > 0.09$, PASS. Only predict when
you have both a directional edge and model conviction. Document the edge gap
explicitly."

---

### A.4.3  Dimension D3 — Information Source Priority

---

**9. Tactical**

*Description.* The tactical archetype elevates situational context above
statistical signals. The primary scoring factors are: (a) rest-days differential
(back-to-back penalty $\approx 2$–$3$ pp), (b) travel distance (cross-timezone
adjustment), (c) injury impact on starting lineup (using per-player WAR
estimates), and (d) opponent motivation (playoff seeding pressure, elimination
scenarios). The archetype explicitly overrides the oracle probability by up to
$10$ pp when situational signals are strongly asymmetric.

*Core directive.* "Score the following situational factors: rest delta,
travel burden, injury impact, motivation index. If the combined situational
score favours one side by $\geq 3$ on a $[-10, +10]$ scale, adjust your
prediction by up to $10$ pp in that direction, regardless of the oracle signal."

---

**10. Value** *(vacant at day 0)*

*Description.* The value archetype treats betting markets as noisy aggregates
of private information, and seeks situations where the market implied probability
diverges from the oracle's calibrated probability by $\geq 5$ pp in a direction
consistent with the oracle's confidence interval. This is a pure positive-EV
strategy: the agent identifies market inefficiencies rather than predicting
game outcomes per se. The archetype is directionally similar to arbitrage (A.4.11)
but focuses on one-sided price discrepancies rather than cross-market
inconsistencies.

*Core directive.* "Compute the market implied probability from the moneyline.
Compare to the oracle probability. If the gap is $\geq 5$ pp and the oracle CI
does not include the market implied probability, predict in the oracle's
direction. Size by Kelly using the EV gap as the edge estimate."

---

**11. Arbitrage**

*Description.* The arbitrage archetype identifies situations where different
market categories (moneyline vs.\ alternate spread vs.\ team total) imply
mutually inconsistent probabilities for the same underlying game outcome. When
an inconsistency of $\geq 3$ pp is detected, the agent predicts in the
direction that exploits the inconsistency, effectively betting against the
market's internal contradiction. The archetype requires parsing multiple market
categories from the 249-category context block, making it more informative for
high-capacity models.

*Core directive.* "Check for inconsistencies between the moneyline, the
primary spread, and the team total implied probabilities. If any pair diverges
by $\geq 3$ pp when translated to the same binary outcome basis, predict in
the direction that resolves the inconsistency. State the arbitrage pair
explicitly."

---

**12. Wide-Coverage**

*Description.* The wide-coverage archetype is the systematic counterpart to
the selective archetypes: it aims to have a prediction in every available
event context, trading depth of analysis for breadth of participation. In the
NBA domain, this means predicting all games in each day's bucket; in the
political domain, predicting all events whose market closes that day.
Predictions are anchored to the oracle probability with minimal adjustment,
functioning as a calibrated prior that the ensemble can diversify around.

*Core directive.* "Generate one prediction per event in today's bucket.
Default to the oracle probability $\pm 2$ pp (your uncertainty adjustment).
Do not spend more than 30 seconds per event. Volume coverage is your KPI."

---

### A.4.4  Dimension D4 — Temporal Horizon

---

**13. Momentum** *(vacant at day 0)*

*Description.* The momentum archetype extrapolates recent form over the
last 7 days, treating the current hot/cold streak as the dominant signal.
The agent is instructed to identify whether each team has won/lost $\geq 4$
of its last 6 games and to assign a momentum adjustment of $3$–$5$ pp in
the streak direction. This archetype intentionally ignores long-run season
statistics in favour of recent trends, which can create exploitable divergence
from the oracle (which is trained on longer windows) during momentum phases.

*Core directive.* "Compute a 7-day momentum score for each team: $+1$ for
each win, $-1$ for each loss over the past 6 games. If the differential
is $\geq 3$, adjust your prediction by 3–5 pp in the favoured team's
direction. Override oracle probability when momentum signal is strong."

---

**14. Mean-Reversion** *(vacant at day 0)*

*Description.* The mean-reversion archetype is the temporal inverse of
momentum: it identifies teams on sustained hot or cold streaks ($\geq 5$
of last 7 games) and fades the streak, betting that performance will regress
toward the season baseline. The archetype is grounded in the statistical
literature on regression to the mean [@kahneman1974judgment]:
in a balanced league, streaks are partially noise, and extreme recent
performance tends to revert toward the season-long baseline. This archetype
is most valuable when the society has over-indexed on momentum signals.

*Core directive.* "If a team has won (or lost) $\geq 5$ of its last 7
games, adjust your prediction by $3$–$5$ pp against the streak direction
(toward the season-long home-win base rate of $\approx 0.54$). Explicitly
fade momentum when the streak has lasted $\geq 7$ games."

---

**15. Theoretical**

*Description.* The theoretical archetype reasons from statistical first
principles rather than recent data. It anchors to the season-long base rate
for home advantage ($\approx 54$% in the 2025–26 NBA season), adjusts by
team quality differential using season-long point differential, and
explicitly de-weights signals that have fewer than 20 data points (rejecting
small-sample evidence). The archetype functions as a ballast in the
ensemble: it is unlikely to track recent swings, but it is resistant to
the over-fitting and narrative anchoring that plague other archetypes.

*Core directive.* "Default to the season-long base rate. Adjust for team
quality differential using only season-long statistics ($\geq 20$ games).
Reject any signal based on fewer than 20 observations. Never adjust more
than 10 pp from the base rate."

---

**16. Chain-of-Thought**

*Description.* The chain-of-thought archetype is a *process* modifier rather
than a pure temporal-horizon type: it instructs the agent to spend the
first $\sim 80$% of its token budget explicitly enumerating and eliminating
considerations before committing to a final prediction. This extended
deliberation is intended to counteract anchoring to the first salient signal —
a well-documented failure mode in which LLMs disproportionately weight
early contextual cues regardless of their evidential value
[@zhao2021calibrate].
The archetype is placed in D4 because deliberative reasoning naturally
surfaces temporal factors (trend vs.\ base-rate tension) that faster archetypes
short-circuit.

*Core directive.* "Before stating any probability, list at minimum four
factors for and four against the home team winning. Assign a rough weight
to each. Only after completing this enumeration, state your final calibrated
probability. The reasoning portion must be at least 150 tokens; the final
prediction must be exactly one number."

---

### A.4.5  Dimension D5 — Ensemble Relationship

---

**17. Ensemble**

*Description.* The ensemble archetype makes the agent an explicit internal
aggregator: it is instructed to construct two or three distinct sub-predictions
using different signal sources (oracle, market, situational), then average
them to produce the final prediction. This operationalises the ensemble
diversity literature [@krogh1995neural] at the level of a single agent's
internal process: diversity of internal sub-models can partially substitute
for peer diversity in the outer ensemble.

*Core directive.* "Construct three sub-predictions: (1) oracle-anchored,
(2) market-implied adjusted, (3) situational-factor adjusted. Average the
three as your final prediction. Report all three sub-predictions alongside
the final value."

---

**18. Coordinator** *(vacant at day 0)*

*Description.* The coordinator archetype is designed to serve as the
morning council moderator (§3.6): it synthesises the previous day's outcomes,
identifies where agent predictions clustered vs.\ diverged, and frames the
day's prediction task in terms of what the ensemble learned. Unlike the
devil's-advocate (A.4.19), the coordinator does not take a contrarian
position; it represents the informed consensus and provides the baseline
against which other agents can differentiate. When occupied by an SRR
entrant, it acts as a "returning moderator" that recalibrates after
its prior archetype led it astray.

*Core directive.* "Review yesterday's leaderboard. Identify the top-performing
archetype's reasoning pattern. Adopt a prediction close to the society mean
for low-uncertainty events ($\text{oracle}\ \sigma < 0.05$), but allow up to
5 pp divergence for high-uncertainty events to signal genuine ambiguity.
Your role is to represent the informed centre."

---

**19. Devil's-Advocate** *(vacant at day 0)*

*Description.* The devil's-advocate archetype systematically challenges
the prevailing morning council consensus. It is the D5 complement of the
contrarian (D1): while contrarian fades the *market* consensus, devil's-advocate
fades the *agent society's* consensus, identified via the morning brief.
When $\geq 60$% of agents in the morning council brief agree on a direction,
the devil's-advocate takes the minority position, scaled by its confidence
in the contrarian view. This archetype is the formal instantiation of the
DMAD principle [@liu2025dmad] at the single-agent level.

*Core directive.* "If the morning council brief shows $\geq 60$% consensus
for a direction, take the opposite direction at a probability $5$–$8$ pp
beyond the minority pole. Explicitly state the consensus probability and
your deviation from it. If there is no strong consensus ($< 60$%), revert
to oracle-anchored prediction."

---

**20. Adaptive** *(vacant at day 0)*

*Description.* The adaptive archetype is the only meta-archetype in the
taxonomy: rather than specifying a fixed reasoning disposition, it instructs
the agent to reflect on its own Brier history from the past 7 days and
explicitly choose the reasoning style that has been most accurate. In effect,
it makes the agent's internal SRR procedure explicit: instead of waiting
for the external SRR mechanism to reassign an archetype, the agent
self-supervises its own reasoning disposition. The adaptive archetype is
assigned through SRR to agents that have failed under multiple previous
archetypes, as a final-stage exploration mechanism.

*Core directive.* "Review your last 7 days of predictions and outcomes.
Identify which type of signal (statistical, situational, contrarian,
momentum) produced the smallest Brier errors. Weight that signal type
at 50% today, and distribute the remaining 50% equally among the
other three. Explicitly state your chosen weighting and why."

---

## A.5  Initial Vacancy Analysis

At day 0, the NBA cohort occupies 12 of 20 archetypes, leaving 8 vacant
($\mathcal{V}_0$, marked "—" in Table A.1). With $K = 20$ and $N = 12$,
the vacancy threshold $\tau_{\text{vac}} = 1/(2K) = 0.025$ implies that
all 8 unoccupied archetypes are formally vacant (0 < 0.025).
The non-vacant archetypes (occupied by at least one agent) pass the
threshold with occupancy fractions of $1/12 \approx 0.083 \gg 0.025$.

For the political cohort ($N = 10$), agents T11 and T12 are absent, so the
*chain-of-thought* archetype (A.4.4, no.\ 16) and the *disciplined* archetype
(A.4.8, no.\ 8) are additionally vacant in the political domain.
This gives $|\mathcal{V}_0^{\text{POL}}| = 10$ vacant archetypes at political day 0.

*Remark on initial diversity.* The initial JSD diversity $D_0$ under the
12-archetype assignment is lower than the theoretical maximum achievable with
20 archetypes, providing headroom for SRR to increase $D_d$ across the season.
This design choice is deliberate: we want SRR to have a clear improvement target,
not to start at a near-optimal configuration that would make gains hard to measure.
The initial diversity level relative to the 20-archetype maximum is quantified in
§5.1 (results pending experimental run).

---

## A.6  Prompt Module Format

Every archetype module is stored as a plain-text file at
`data/arena/archetypes/<archetype_name>.txt`. The file structure is:

```
ARCHETYPE: <name>
DIMENSION: <D1|D2|D3|D4|D5>
KAPPA_MIN: <float>
---
DIRECTIVE:
<1–4 sentence system-prompt module text>
---
NOTES:
<Optional notes on interaction with shared mission preamble>
```

When SRR fires (§3.4), the `DIRECTIVE` block replaces the agent's current
archetype block in its system prompt. The shared mission preamble,
bankroll state, and prediction history are prepended and are archetype-invariant.
