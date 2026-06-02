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
model and provider (T1–T2: Cerebras Qwen 3 235B; T3: Cerebras Llama 3.1 8B; T4–T5: Google Gemini 3 Flash;
T6–T10: Mistral family; T11: OpenRouter Nemotron-120B; T12: Cerebras Qwen 3 235B (originally self-hosted; see §4.1 Table 3 note$^\dagger$));
(ii) initial strategy archetype; and (iii) SRR history accumulated over the
175-day experimental period.

Clean attribution of performance differences to any single factor requires
holding the others constant — a condition that cannot be fully satisfied with
a heterogeneous agent cohort. If qwen-arb (T2, Cerebras 235B, *arbitrage*)
outperforms mistral-small (T8, Mistral, size undisclosed per §4.1, *wide-coverage*), this difference
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

## 7.2  Sequential Condition Design and Provider Drift

Our five conditions are each simulated over the complete 1,257-game,
175-trading-day event stream, with identical historical market signals and
odds data (§4.3).  Because all conditions begin from Day 1 of the 2025–26
season with fully reset agent state, the within-season temporal confounds
that plague partial-season crossover designs — sportsbook calibration drift,
accumulating agent context, or in-season form trends — do not apply: every
condition's Day $k$ processes exactly the same historical event data, odds,
and oracle feature context.

The operative confound in a sequentially-simulated multi-condition study is
instead **LLM provider model drift**: because each condition's simulation
invokes the LLM APIs at a different calendar time (Condition A during the
live 2025–26 season, Conditions B–E thereafter in replay order), the
underlying model weights served by `mistral-large-latest`, `gemini-3-flash-preview`,
or `cerebras/qwen-3-235b-a22b-instruct-2507` may silently change between
simulation runs without user notification.  A model update between Condition A
and Condition B would introduce a version confound that is inseparable from
the SRR-vs-fixed experimental manipulation: if Condition B agents call a
sharper model than Condition A, any Brier difference is partly attributable
to model drift rather than the archetype-fixing manipulation.

We document provider drift via the response-hash protocol described in §7.4
(probing each endpoint with a fixed query at the start of each condition's
simulation and archiving the hash).  Hash stability across conditions serves
as circumstantial evidence that model weights did not change; a hash change
triggers a notation in the experimental log and a sensitivity analysis
excluding the affected agent.  As with provider non-stationarity generally
(§7.4), no agent in the actual experimental configuration is fully immune
to this confound: T12's self-hosted endpoint was rerouted to Cerebras
(§4.1 Table 3 note$^\dagger$), removing the only fully isolated reference
agent. Systematic model-family-correlated discrepancies (e.g., all three
Qwen 235B agents T1, T2, T12 diverging jointly) in the per-agent analysis
(§5.6) serve as circumstantial evidence of drift.

A distinct and potentially more severe risk is **outcome contamination**.
Conditions B–E are simulated after the 2025–26 NBA season concludes;
any LLM provider that issued a post-season training update may have
incorporated 2025–26 game outcomes into its model weights — the very
outcomes the model is asked to "predict" from the simulated historical
feature context.  This is not provider drift in the sense of changed
reasoning behaviour: it is the model having partial access to the answers
in its parametric memory.  Three factors bound this risk: (a) the context
block is feature-grounded (engineered statistics via the island GA oracle),
giving the model's parametric recall less traction than a raw game-narrative
prompt; (b) the feature-grounded context block is consistent across all conditions,
reducing parametric-recall traction regardless of training cutoff; and (c) the hash-probe protocol detects endpoint weight
changes, enabling post-hoc flagging.  A strong signal of contamination
would be an anomalously large T12-vs-commercial Brier gap in Conditions
B–E relative to Condition A; we report this comparison explicitly in §5.6.

**Temporal lifecycle scope.** Lee et al. [@lee2026timeseek] find that agentic LLM
forecasters are most competitive early in a prediction market's lifecycle and on
high-uncertainty events, but substantially less competitive near resolution or on
strong-consensus markets. Our pre-tip-off prediction window — sealed predictions
generated during the 15-minute morning council window (§3.6), always before the
game begins — places agents exclusively in the early-lifecycle, high-uncertainty
regime where LLM skill is highest. Results should not be extrapolated to late-lifecycle
settings (e.g., in-game live markets) where the TimeSeek findings suggest structural
disadvantage for LLM-based forecasters.

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

No agent in the actual experimental configuration is fully immune to provider
non-stationarity: T12's self-hosted endpoint was rerouted to the Cerebras API
(§4.1 Table 3 note$^\dagger$), so T12 is subject to the same provider
model-drift risk as T1–T2. Systematic deviations from expected per-agent
SRR-response patterns — particularly if model-family-correlated (e.g., all
Qwen 235B agents T1, T2, T12 showing joint divergence) — are flagged in the
per-agent analysis (§5.6) as consistent with, though not exclusively explained
by, provider drift across the Cerebras endpoint.

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
were sourced from public sports odds feeds (ingestion scripts in
`LBJLincoln26/mon-ipad`) and official league statistics. Political event data are drawn from
publicly recorded government documents, regulatory filings, and official
election results — all in the public domain under federal law. No
personal data about individual athletes, politicians, bettors, or
prediction-market participants is collected, stored, or processed.
The feature engine (v3.1; `LBJLincoln26/nomos-nba-agent`, `features/engine.py`)
does not use personally identifiable information.

**LLM inference costs and environmental impact.** The 12-agent NBA
and 10-agent political ensembles generate approximately 24–48
LLM API calls per day across both domains (12 NBA agents × 1 day-bucket
call/day + 10 political agents × 1 day-bucket call/day + 2 morning council
calls = 24 primary calls/day; up to approximately 48 calls/day when primary
providers fail and fallback providers are invoked). The day-bucket
architecture (§3.6) processes all events on a given calendar day through a
single LLM inference call per agent — not one call per game or per event —
capping the per-day inference budget regardless of how many games are
scheduled (§3.6). Total calls over the 175-day experimental period are thus
approximately 4,200–8,400, using
the free and low-cost commercial tiers of Cerebras, Google, Mistral, and
OpenRouter. All
providers offer these tiers on shared GPU infrastructure whose carbon
intensity reflects grid averages for their respective data centre locations.
T12 routes through the Cerebras API (see §4.1 Table 3 note$^\dagger$);
all twelve agents' inference calls run on shared GPU infrastructure.
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
via append-only JSON prediction logs (`data/arena/axelrod-log/`), the
archetype transition records documented in §C.5, and a programmatic
commit gate that enforces repository-level review before any agent
system-prompt modification is persisted — all archived in the public
repository upon acceptance.

**Reproducibility and openness.** Upon acceptance, code (licensed under
MIT), data (`data/arena/axelrod-log/` in newline-delimited JSON), agent
prompts (`data/arena/archetypes/`), and the pre-registration document
will be made publicly available at `github.com/LBJLincoln/mon-ipad`.
LLM provider API keys are not published; researchers wishing to replicate
must supply their own credentials. T12 currently routes through the Cerebras
API (§4.1 Table 3 note$^\dagger$); replicating T12's actual experimental
behaviour requires Cerebras API access. The original self-hosted Qwen3-4B
reference build is available on HuggingFace Hub for researchers who wish to
validate the intended self-hosted configuration independently.

---

## 7.8  Bankroll Broadcast Scope: Design Choice and Information Architecture

The day-end broadcast (Definition 1, step 5) currently disseminates cumulative bankroll
standings alongside archetype labels. This creates the partial prediction-inference
risk described in the §3.2 broadcast-step footnote: a sufficiently informed observer
seeing a large bankroll increment can infer a large stake fraction, and with knowledge
of the archetype's floor $\kappa_{\min}^{(r_j)}$ could partially recover the realised
stake $s_j$ and hence the direction and rough magnitude of agent $j$'s prediction for
the preceding day.

An alternative design would broadcast only (i) archetype labels $\{r_j\}_{j\in\mathcal{I}}$
and (ii) rank-order standings, omitting bankroll magnitudes entirely. This fully
eliminates the stake-size inference channel but at two functional costs: (a) agents
could no longer compute absolute Kelly-weight contributions of peers to the ensemble
mean prediction $\bar{p}_t$; and (b) the implicit Bayesian model averaging property
of the ensemble (§6.5) would become invisible to individual agents, potentially
degrading the quality of morning council summaries (§3.6) and the SRR incentive
calculation (the sacrifice-eligibility check requires comparing $\overline{B}_{i,d}$
to the society mean $\bar{B}_d$, which does not require bankroll magnitudes, but
the Kelly-weighting framing of §6.5 assumes agents observe the bankroll distribution
to identify dominant contributors).

The three-factor bound in the §3.2 footnote argues leakage is partial and approximate
in the current design: (a) $\overline{B}_{j,d}$, which determines $\kappa_j$, is
private and changes daily; (b) the broadcast reports cumulative totals rather than
marginal daily increments; and (c) the personality risk weight $\rho_j$ is never
broadcast. Recovering exact stake fractions requires simultaneous knowledge of
$\kappa_j$, $\rho_j$, and $\kappa_{\min}^{(r_j)}$ — at least two of which are either
private or daily-varying. Partial inference (e.g., inferring whether an agent bet
*heavily* on a game without recovering the exact probability) is possible for an
adversarially informed agent but does not constitute common-knowledge prediction
sharing in Aumann's sense.

We retain the bankroll-magnitude broadcast in Condition A because: (a) the three-factor
bound limits leakage to a one-sided direction signal rather than a precise probability
recovery; (b) agents require absolute bankroll data to compute the ensemble mean
prediction $\bar{p}_t$ used in the morning council brief; and (c) omitting magnitudes
would prevent agents from identifying the highest-weight peers when formulating
the council brief, weakening the collaborative council-discussion quality.
The rank-only design is a viable alternative for deployments where prediction-inference
risk is a primary constraint; we recommend evaluating it in follow-on replications
via a sixth condition (Condition F: Rank-Only Broadcast) and report this as a
pre-submission recommendation.

---

> **Acknowledgement of open questions.** Several questions raised in this
> section — whether SRR benefits transfer to continuous-outcome domains,
> whether provider non-stationarity confounds the longitudinal trends,
> whether the taxonomy designer's prior knowledge biases the vacancy
> dynamics, and whether the rank-only broadcast design preserves SRR efficacy —
> cannot be resolved within the current experimental design.
> We flag them as priority targets for follow-on replication studies.
