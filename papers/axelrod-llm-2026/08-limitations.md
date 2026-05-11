# Limitations and Ethics

A rigorous paper must account precisely for the gap between its claims and the
evidence it can marshal. We organise this accounting into methodological
limitations that bear on the internal validity of our claims, scope limitations
that bear on external generalisability, and ethical considerations that bear
on responsible deployment of the techniques we describe.

---

## 7.1  Attribution: Concurrent Sources of Variation

The fundamental attribution problem in our experimental design is that agents
differ simultaneously along at least three dimensions: (i) underlying language
model and provider (T1–T2: Cerebras 235B; T4–T5: Google Gemini 3 Flash;
T6–T10: Mistral family; T11: OpenRouter Nemotron-120B; T12: self-hosted Qwen3-4B);
(ii) initial strategy archetype; and (iii) SRR history accumulated over the
175-day experimental period.

Clean attribution of performance differences to any single factor requires
holding the others constant — a condition that cannot be fully satisfied with
a heterogeneous agent cohort. If qwen-arb (T2, Cerebras 235B, *arbitrage*)
outperforms mistral-small (T8, Mistral ~8B, *wide-coverage*), this difference
plausibly reflects model scale, provider quality, archetype assignment, SRR
history, or any combination of the four. Our ablation conditions (§4.3)
partially address this by holding the agent population fixed across conditions —
all five conditions run the same 12 agents — but the attribution problem within
any single condition remains unresolved.

The strongest within-design control is the *within-agent* comparison: each
agent's Brier before and after an SRR event, estimated via the matched-pairs
analysis described in §4.3. This controls for all time-invariant agent
characteristics (model identity, initial archetype tendency) and isolates
the effect of the archetype change itself. However, this within-agent estimator
is susceptible to mean-reversion bias: agents are identified for SRR precisely
because their recent Brier is elevated above the population mean, so some
subsequent improvement would be expected under any intervention, including
no change. We address mean-reversion directly via the Sham-SRR condition (D)
and the matched-pairs control (§4.3); neither fully eliminates the concern,
but together they bound the mean-reversion contribution.

---

## 7.2  Sequential Condition Design and Temporal Confounds

Our five conditions are run sequentially on the same chronological event
stream, not in a fully randomised within-season design. This choice was
motivated by two hard constraints: (a) running five parallel agent fleets
simultaneously would require 60 NBA + 50 political concurrent LLM inference
threads, exceeding the combined rate limits of our five provider ecosystems;
and (b) the SRR mechanism requires a minimum of seven days before any agent
becomes sacrifice-eligible ($W = 7$ patience window), making crossover designs
shorter than one week uninformative.

The sequential design introduces a temporal confound: later conditions could
benefit from systematic changes in the prediction environment over the
season. Two specific sources of temporal variation are plausible:

**Sportsbook calibration drift.** Odds markets become sharper as the season
progresses and sportsbooks accumulate more data on team tendencies.
A later condition therefore faces a higher market-line quality baseline,
making it harder to achieve meaningful Brier improvement over the baseline
— a conservative bias against conditions run later in the season.

**Agent calibration drift.** Agents whose prompts include historical context
accumulate progressively more season-specific information as the season
advances. Conditions run later have access to richer context, which could
improve predictions independent of the experimental manipulation.

We partially control for temporal confounds by normalising each condition's
Brier against a simultaneously computed *market baseline* (the Brier score
of predicting the market-implied probability for each event, computed in
the same temporal window as the condition). Brier improvement relative to
the market baseline is expected to be more temporally stable than absolute
Brier, since both the agent's and the market's calibration improve over time.
We cannot fully rule out residual temporal confounding and acknowledge this
as a limitation that a fully parallelised multi-fleet design would address
at the cost of provider rate-limit violations.

---

## 7.3  Virtual Financial Stakes

All bankrolls in this experiment are virtual: no real capital is at risk.
This is a deliberate design choice — running 12 agents with real money across
1,257 NBA games and 1,120 political events would require regulatory compliance
across US betting jurisdictions and raise ethical concerns about AI-mediated
gambling — but it creates an external validity question.

Do LLM agents predict differently when they (or their operators) face real
financial consequences? Two competing effects are plausible:

First, real stakes might *improve* prediction quality through stronger feedback:
a human overseer monitoring a real-money system would intervene more aggressively
on systematic underperformance, effectively acting as a meta-SRR mechanism
that we cannot replicate with virtual bankrolls.

Second, real stakes might *degrade* prediction quality by introducing risk
aversion: operators might suppress high-variance predictions (e.g., contrarian
archetypes) in favour of consensus-aligned "safe" positions, reducing the very
diversity that SRR targets. The Prediction Arena results [@zhang2026arena],
which use real money and find consistent losses, do not resolve this question
because they do not implement a diversity-maintenance mechanism.

We treat the virtual-stakes design as conservative for our primary claim
(ensemble Brier improvement through diversity): if SRR increases diversity
and reduces ensemble Brier in a virtual system, a real-stakes system would,
if anything, have stronger incentives to adopt the mechanism. However, we
note that the Kelly stake-sizing and bankroll-growth results (§5.6) should
be interpreted solely as illustrations of the mechanism's
financial-calibration properties, not as projections of real trading performance.

---

## 7.4  LLM Provider Non-Stationarity

Commercial LLM providers update their base models on undisclosed schedules
without notifying API users. An agent calling `mistral-large-latest` in
October 2025 may access a materially different underlying model than the same
endpoint in April 2026. This non-stationarity is not specific to our
experiment — it affects every LLM system operating over extended periods —
but it is particularly consequential for a study whose primary findings are
longitudinal trends over 175 days.

We document provider model versions by recording the SHA-256 hash of each
agent's response to a fixed probe question ("What is the probability that the
home team wins in an NBA game where the market spread is $-5$?") at the start
of each 30-day window (archived at `data/arena/axelrod-log/provider-hashes.jsonl`).
Significant changes in this hash serve as circumstantial evidence of model
drift. However, a model update could produce identical probe responses
for this simple query while altering predictions for complex game contexts
in ways our probe does not detect.

The self-hosted agent T12 (Qwen3-4B, frozen at a specific model version in
`LBJLincoln26/llm-gateway`) is the only agent fully immune to provider
non-stationarity. If T12 shows systematically different SRR-response patterns
than T1–T11, this difference is consistent with — though not exclusively
explained by — provider drift confounding the commercial agent results.
We flag this as a factor for inspection in the per-agent analysis (§5.6).

---

## 7.5  Archetype Taxonomy Design Choices

The 20-archetype taxonomy $\mathcal{R}$ was designed by the research team
responsible for the experiment. Despite pre-registration before the 2025–26
season began (tag `preregistration-v1`), the taxonomy was constructed with
knowledge of which reasoning dispositions tend to perform well in
prediction markets — knowledge that could inadvertently bias the SRR
mechanism toward favourable outcomes if vacant archetypes happen to be
those the designers expected to be high-value.

We note three partial mitigations: (a) archetype assignments were not
optimised to maximise initial diversity (§4.1 explicitly states this);
(b) the 20-archetype validation on the withheld 2024–25 pilot data
confirms distinguishability ($\epsilon_{\text{arch}} \geq 0.037$) without
testing archetype-level Brier — validity was assessed by whether archetypes
produce different predictions, not by whether they produce better predictions;
and (c) the Sham-SRR condition (D) tests whether any reallocation benefit
arises from the prompt change or from peer-knowledge of the new label,
which would surface a demand-characteristic effect if present.

A fully debiased evaluation would require the archetype taxonomy to be
designed by an independent team with no knowledge of the experimental
hypotheses. We recommend this for future replications and note that the
DMAD mental-set library [@liu2025dmad] provides an externally designed
candidate taxonomy that could be used directly.

---

## 7.6  Scope and Generalisability

Our experimental domains — NBA game prediction and US political event markets
— were selected for properties that make causal inference tractable: clean
binary outcomes, transparent exogenous ground truth, and rich numerical
context available before each event. These properties are not universal,
and the LPSG framework requires modification for domains where they do not hold.

**Continuous-outcome domains.** The Brier score is defined for binary outcomes.
In domains where outcomes are real-valued (stock returns, inflation forecasts),
a proper scoring rule for continuous distributions (e.g., the continuous
ranked probability score [@gneiting2007strictly]) would replace the Brier score,
and the JSD diversity metric would need adaptation to continuous marginal
distributions.

**Reflexive markets.** Our framework assumes agent predictions do not
influence the ground truth — NBA game outcomes are unaffected by how many
LLM agents bet on them. In financial markets with genuine price impact,
agent predictions become reflexive [@soros1987alchemy]: large ensembles
trading the same signals can move prices, alter the information content of
the market line, and invalidate the assumption that $x_d$ (the morning context)
is exogenous to the agents' predictions. Our results do not extend to
reflexive markets without explicit price-impact modelling.

**Small day-buckets.** JSD diversity is computed per day-bucket (§3.3).
Domains with one or two events per day provide noisy daily JSD estimates;
the 28-day rolling smoothing in §4.5 partially addresses this, but domains
with very sparse event calendars would require longer rolling windows or
event-stratified diversity metrics.

**Agent population scale.** Our $N = 12$ NBA and $N = 10$ political agents
constitute a small population relative to institutional prediction markets
or large-scale multi-agent deployments. The vacancy threshold
$\tau_{\text{vac}} = 1/(2K) = 0.025$ and sacrifice threshold
$\delta_{\text{sac}} = 0.02$ were calibrated for this scale (Appendix C.2).
For $N = 100$ or $N = 1000$ agents, the population dynamics would enter
a qualitatively different regime where the uniform-vacancy assumption
may not be the right objective — a richer diversity target (e.g., entropy
of the population distribution over $\mathcal{R}$) might be more appropriate.

---

## 7.7  Ethical Considerations

**Dual-use and market manipulation.** The LPSG framework and SRR mechanism
could be deployed to coordinate a large number of LLM agents for
financial market prediction at scale. Our 12-agent system, with its
hypothetical $100,000 per-agent virtual bankroll, is negligible relative
to the liquidity of major NBA betting markets or Kalshi/Polymarket.
However, an ensemble scaled to hundreds of agents with real capital
could constitute a coordinated market participant subject to regulatory
scrutiny under US Commodity Futures Trading Commission (CFTC) rules
governing prediction markets and under applicable gaming regulations
for sports betting. We do not advocate for real-money deployment of
this system without appropriate legal review.

**Data collection and privacy.** All NBA data used in this experiment
were sourced from public odds feeds (ingested via `scripts/bloomberg/`)
and official league statistics. Political event data are drawn from
publicly recorded government documents, regulatory filings, and official
election results — all in the public domain under federal law. No
personal data about individual athletes, politicians, bettors, or
prediction-market participants is collected, stored, or processed.
The feature engine (v3.1, `features/engine.py`) does not use personally
identifiable information.

**LLM inference costs and environmental impact.** The 12-agent NBA
and 10-agent political ensembles generate approximately 200–400
LLM API calls per day across both domains (12 agents × ~10 games/day NBA
+ 10 agents × ~10 events/day political + morning council overhead), using
the free and low-cost commercial tiers of Cerebras, Google, Mistral, and
OpenRouter. All
providers offer these tiers on shared GPU infrastructure whose carbon
intensity reflects grid averages for their respective data centre locations.
The self-hosted agent (T12) runs on a CPU-only HuggingFace Space.
Using published emission factors for GPU inference
[@lannelongue2021green], total estimated carbon footprint over the
175-day experimental period is below 10 kg CO$_2$-equivalent —
comparable to driving a typical petrol car approximately 60 km.

**Agent autonomy and human oversight.** All agent predictions in this
experiment are recorded but no real bets are placed autonomously. A human
operator reviews the `data/arena/axelrod-log/` records and retains the
ability to halt, modify, or suspend any agent at any time. The SRR mechanism
modifies agent system prompts programmatically, but every such modification
is logged, reversible, and subject to the $W_{\text{persist}} = 14$ day
review window before the new archetype is confirmed. We operate under the
principle that autonomous mechanisms affecting agent behaviour require
complete audit trails, and our implementation satisfies this requirement
via the `data/ops/quarantine.json` and safe-commit protocols described
in the project documentation.

**Reproducibility and openness.** Upon acceptance, code (licensed under
MIT), data (`data/arena/axelrod-log/` in newline-delimited JSON), agent
prompts (`data/arena/archetypes/`), and the pre-registration document
will be made publicly available at `github.com/LBJLincoln/mon-ipad`.
LLM provider API keys are not published; researchers wishing to replicate
must supply their own credentials. The self-hosted model (T12, Qwen3-4B)
is available on HuggingFace Hub and requires only CPU compute, enabling
full-stack replication without commercial API access for the open-weights
component of the agent cohort.

---

> **Acknowledgement of open questions.** Several questions raised in this
> section — whether SRR benefits transfer to continuous-outcome domains,
> whether provider non-stationarity confounds the longitudinal trends,
> and whether the taxonomy designer's prior knowledge biases the vacancy
> dynamics — cannot be resolved within the current experimental design.
> We flag them as priority targets for follow-on replication studies.
