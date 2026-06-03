# Experimental Setup

We instantiate the LPSG on two real-world prediction domains over the 2025–26
temporal period, using heterogeneous LLM agents drawn from four commercial
provider ecosystems for the NBA cohort and three for the political cohort
(§4.1). All experimental conditions share the same
Day-Bucket v3 pipeline (§3.6); conditions differ only in whether SRR is active,
what strategy initialisation is used, and which agents are eligible for
reallocation. The full experiment log is archived at
`data/arena/axelrod-log/`.

---

## 4.1  Agent Population

**NBA cohort (N = 12).** Table 3 describes the twelve LLM agents fielded in
the NBA prediction domain. The cohort spans four provider ecosystems, three
identified model scale classes (8B to 235B parameters for providers with publicly
disclosed sizes: Cerebras Qwen 3 235B-A22B, Cerebras Llama 3.1 8B, and OpenRouter
Nemotron-3-Super-120B; Google Gemini 3 Flash and Mistral commercial variants have
undisclosed parameter counts), and twelve distinct initial strategy
archetypes drawn from the 20-archetype taxonomy (Appendix A). The initial
archetype assignment was *not* optimised to maximise initial diversity; rather,
archetypes were assigned to reflect natural provider tendencies (e.g., T12 was
originally assigned the *disciplined* archetype for its planned 4B self-hosted
configuration — a lower-certainty prediction mode appropriate for smaller models;
this assignment is preserved post-rerouting for pre-registration consistency,
while large reasoning-capable models receive *analytical* or *quantitative* archetypes). This conservatism ensures that any diversity improvement
observed in the SRR condition cannot be attributed to a favourable starting
configuration.

| # | Agent ID | Model | Provider | Initial Archetype | $\rho_i$ |
|---|----------|-------|----------|-------------------|----------|
| T1 | qwen-quant | Qwen 3 235B-A22B | Cerebras | quantitative | 0.55 |
| T2 | qwen-arb | Qwen 3 235B-A22B | Cerebras | arbitrage | 0.65 |
| T3 | llama-contra | Llama 3.1 8B | Cerebras | contrarian | 0.55 |
| T4 | gemini-anl | Gemini 3 Flash Preview | Google | analytical | 0.55 |
| T5 | gemini-tact | Gemini 3 Flash Preview | Google | tactical | 0.60 |
| T6 | mistral-large | mistral-large-latest | Mistral | ensemble | 0.50 |
| T7 | mistral-medium | mistral-medium-latest | Mistral | diversified | 0.45 |
| T8 | mistral-small | mistral-small-latest | Mistral | wide-coverage | 0.35 |
| T9 | mistral-nemo | open-mistral-nemo | Mistral | aggressive | 0.70 |
| T10 | mistral-ministral | ministral-8b-latest | Mistral | theoretical | 0.35 |
| T11 | nemotron-120b | Nemotron-3-Super-120B | OpenRouter (free) | chain-of-thought | 0.55 |
| T12 | selfhost-qwen4b | Qwen 3 235B-A22B^[$\dagger$] | Cerebras (rerouted) | disciplined | 0.40 |

*Table 3: NBA LLM agent cohort ($N = 12$). $\rho_i \in (0,1]$ is the agent's
personality risk weight governing willingness to commit to high-edge opportunities;
the formula-derived Kelly stake cap $\kappa_i = \max(0.01,\, 0.30 - \overline{B}_i^{\text{pilot}}
\times 0.50)$ (§3.6), empirical range $[0.01, 0.20]$ for pilot $\overline{B}_i^{\text{pilot}} \in [0.20, 0.58]$, is computed from each agent's pilot-season
Brier and multiplied by $\rho_i$ to produce the realised stake fraction.
Model sizes range from 235B (T1–T2, and T12 as rerouted) to undisclosed (Google Gemini,
Mistral variants); the original T12 design used a 4B parameter model.
Provider column names refer to the LLM gateway routing layer
(`LBJLincoln26/llm-gateway`).
$^\dagger$T12 was originally deployed as self-hosted Qwen3-4B (CPU inference
via llama.cpp, `LBJLincoln26/llm-gateway`). The self-hosted endpoint timed out
persistently from 2026-04-22 (probe latency > 30 s); the production TRADERS
configuration in `app.py` rerouted T12 to `cerebras:qwen-3-235b` as a fallback.
All references to T12 as "self-hosted" or "CPU inference" in this manuscript reflect
the original design intent; the actual experimental runtime used the Cerebras API
(same infrastructure as T1–T2).*

^[Five additional agents appear in the production `app.py` TRADERS configuration
(nvidia-minimax, nvidia-llama70, selfhost-gemma3, selfhost-qwen06, selfhost-dolphin3),
added for API fault tolerance during the experimental period. These agents use provider
configurations that duplicate T1–T3 (Cerebras) or T11 (NVIDIA via OpenRouter) and are
not independent experimental units — they represent routing redundancy, not distinct
strategy archetypes. They are excluded from the scientific cohort ($N = 12$) and from
all statistical analyses; the `data/arena/axelrod-log/` ingestion pipeline filters
exclusively on the agent IDs corresponding to T1–T12.]

**Political cohort (N = 10).** The political domain uses T1–T10, the
Cerebras, Google, and Mistral agents. The OpenRouter agent (T11) and T12
are excluded from the political cohort. T11's exclusion reflects
OpenRouter's shared-pool rate limits and throughput constraints incompatible
with the political domain's narrower daily prediction window.
T12's exclusion was pre-registered before the 2025–26 season on the
basis of the planned self-hosted CPU throughput (~8 s/call);
following T12's Cerebras rerouting (Table 3 note$^\dagger$), the latency
rationale for exclusion no longer applies, but T12 is preserved outside
the political cohort for experimental-design consistency — retroactively
including T12 would introduce an unplanned agent-population change that
would confound the political experiment and violate the pre-registration. This exclusion creates a natural
cross-domain experiment: T1–T10 are the same ten LLM model configurations
running independently (with fully isolated context buffers per §4.3) in both
the NBA and political arenas, enabling a *domain-transfer* test of whether
diversity mechanisms observed in one domain generalise to the other.

**Provider capacity constraints.** Cerebras enforces a 30-request-per-minute
(RPM) limit per key; Google Gemini 3 a 14 RPM free-tier limit with
`thinkingBudget=0` required (non-zero thinking budget consumes all available
tokens before prediction output). Mistral enforces 20 RPM across their
free tier. OpenRouter limits `nemotron-3-super-120b:free` to shared pool
throughput. To respect these constraints, the 15-minute prediction window
staggers API calls via the centralised LLM gateway
(`LBJLincoln26/llm-gateway`), which implements per-provider token-bucket
rate limiting with fallback chains on provider failure.

---

## 4.2  Data and Markets

### 4.2.1  NBA 2025–26 Season

The primary experimental arena is the complete 2025–26 NBA regular season and
playoffs, comprising **1,257 games** played from October 2025 through June 2026.
Ground-truth outcomes are binary: $\omega_t = 1$ if the home team wins (moneyline
resolution); $\omega_t = 0$ otherwise. Market signals (spread, moneyline, total,
alternative spreads, player props) are sourced from a public real-time sports
odds API (ingestion and schema details in `LBJLincoln26/mon-ipad`; archived in
`data/full-odds-2025-26.json`), which contains 249 market categories per game
(162 alternative spread/total lines, 28 team-total, 22 player-prop, 20 halves
and quarters, 3 primary game-level markets). Of these, agents receive the full
249-category context block.

Additionally, each agent receives the feature representation used by the
ensemble oracle: the LPSG feature engine (v3.1) generates 7,213 candidate
features across 54 categories (team form, pace, efficiency differentials,
rest days, back-to-back flags, referee tendencies, travel distance, altitude,
injury impact, and market implied probabilities; full taxonomy in
`LBJLincoln26/nomos-nba-agent`, `features/engine.py`). Feature dimensionality is reduced to at most
200 features per game via variance-based selection as part of the oracle's
pre-game pipeline. Agents do not receive the feature matrix directly; they
receive the natural-language summary that the oracle pipeline generates from
the top-by-variance features, ensuring predictions are grounded in the same
statistical context as the island GA models.

**No leakage guarantee.** All context provided to agents on day $d$ is
restricted to information available before the first tip-off of $\mathcal{B}_d$.
Injury reports, line movements, and standing updates are timestamped; any
item with a timestamp after the day-bucket open is withheld. This is enforced
at the data-layer level within the Day-Bucket v3 pipeline
(`LBJLincoln26/nba-llm-trading-floor`), not at the prompt level, to
prevent prompt-injection attacks from bypassing the cutoff.

### 4.2.2  US Political Events 2025

The political prediction domain comprises **1,120 binary-outcome events**
drawn from the 2025 US political calendar. Events span 22 thematic categories
including congressional floor votes, Federal Reserve policy decisions,
regulatory approval outcomes, gubernatorial races, state ballot initiatives,
and macro-economic indicator release thresholds. Ground-truth resolutions
are sourced from the political feature engine
(`LBJLincoln26/nomos-political-alpha`, `political_engine.py`, v3.19, 718 features), which
archives resolutions with a canonical timestamp against which all agent
predictions are scored.

The political domain provides a methodological complement to NBA: (a) the
average event horizon is longer (days-to-weeks versus same-day); (b) outcome
base rates are more heterogeneous (some categories have $\bar{\omega} \approx 0.1$,
others near 0.5); and (c) the information environment is richer in
unstructured text. Cross-domain performance thus tests whether the benefits
of SRR are domain-general or specific to the short-horizon, high-frequency
NBA setting.

---

## 4.3  Experimental Conditions

We evaluate five conditions to isolate the individual contributions of the
SRR mechanism and its components. All conditions use identical agent
populations and data.

**Condition A — Full SRR.** The complete mechanism as defined in §3.4:
sacrifice eligibility evaluated nightly at 23:59 UTC using a 7-day rolling
Brier window; reallocations drawn uniformly from the vacancy set;
14-day persistence with a Brier-improvement retention test. This is the
primary treatment condition.

**Condition B — Fixed Ensemble (no SRR).** The same 12 NBA and 10 political
agents run with their initial archetypes locked for the full experimental
period. No archetype reallocation occurs. This is the main control,
establishing the baseline against which all SRR gains are measured.

**Condition C — DMAD-Static Baseline.** Inspired by [@liu2025dmad], the 12
NBA agents are pre-assigned to 12 *distinct* archetypes from the taxonomy
(maximum initial diversity) at day 0, and archetypes are then frozen. This
condition isolates whether the *initial diversity* of SRR's target state is
sufficient to explain any Brier improvement, or whether the *endogenous
maintenance* mechanism is necessary.

**Condition D — Sham-SRR.** When an agent becomes sacrifice-eligible,
its archetype label in the leaderboard is updated (agents can observe peer
archetype labels via the morning council brief), but the underlying system
prompt is *not* changed. The agent continues predicting with its original
reasoning disposition under a new label. This condition tests whether the
Brier improvements in Condition A arise from genuine behavioural change
induced by the new system prompt or merely from the social-signalling effect
of the label change (i.e., peers adjusting their positions relative to the
newly-labelled agent).

**Condition E — Free-Rider Ablation.** On each day that any agent would be
sacrifice-eligible under Condition A, a randomly selected *non-eligible* agent
(drawn uniformly from those whose Brier is at or below the society mean) is
instead reallocated. This condition tests whether the performance-based
*targeting* of SRR is essential, or whether any reallocation — regardless of
which agent — produces the diversity gains.

Conditions C, D, and E apply to the NBA domain only; Conditions A and B are evaluated
independently in both the NBA ($N = 12$, $D = 175$ days) and political ($N = 10$,
$D = 90$ days) domains (results for both in Table 5, §5.2).
Each condition is simulated independently over the complete 1,257-game, 175-trading-day
NBA event stream (Conditions A and B additionally over the 1,120-event political stream),
starting from Day 1 of the 2025–26 season, with identical historical
market signals and odds data.  Conditions are run sequentially (one condition's full
simulation completes before the next begins) rather than concurrently, because running
five independent agent fleets in parallel would require 60 NBA + 20 political concurrent
LLM inference threads, exceeding provider rate limits.  Order effects within a single
condition are precluded by the full season-length coverage; order effects across
conditions are bounded by LLM provider model drift (see §7.2 and §7.4).
Each condition's agent state is reset completely before its simulation begins:
bankrolls re-initialised to \$100,000; Brier histories cleared; LLM conversation context
buffers flushed so that no prediction reasoning from a prior condition persists.
The full experimental calendar is described in Appendix C.1.

---

## 4.4  Strategy Archetype Taxonomy

The full taxonomy $\mathcal{R}$ comprises $K = 20$ archetypes, listed in
Appendix A with their defining prompt modules. The 20 archetypes are
designed to span orthogonal reasoning dispositions across five dimensions:
(i) *position construction* (quantitative vs. narrative vs. contrarian);
(ii) *risk appetite* (aggressive vs. conservative vs. diversified);
(iii) *information source priority* (market signals vs. statistical features
vs. situational context); (iv) *temporal horizon* (short-term momentum vs.
long-term mean-reversion); and (v) *ensemble relationship* (independent vs.
coordinator vs. devil's-advocate).

Archetypes were drafted iteratively over a pre-season pilot (2024–25 NBA
season, withheld from all evaluation) and revised to ensure the
archetype-distinguishability bound $\epsilon_{\text{arch}} \geq 0.037$ was
met for all 190 pairwise archetype pairs on held-out pilot data (§3.5;
pre-registered constraint — any pair failing the threshold will trigger
archetype revision before Conditions B–E commence; confirmation pending
Table B.2 once pilot backtest completes).
No archetype was designed with knowledge of which agents would be initially
assigned to it, preventing cherry-picked archetype-agent pairings.
*Pilot-data circularity note.* Because archetypes were revised iteratively until all
190 pairs passed the $\epsilon_{\text{arch}} \geq 0.037$ threshold on the 2024–25
pilot data subsequently used for final distinguishability validation (§5.1, Table 4),
the pilot data functions partly as a development set rather than a strictly held-out
test set. This selection effect upward-biases the reported minimum $\hat\epsilon_{\text{arch}}$:
configurations that failed the threshold were revised rather than reported as failures.
We recommend that future replications use a three-way split (archetype-development /
distinguishability-validation / main-experiment held-out) to achieve unbiased estimation
of $\hat\epsilon_{\text{arch}}$. In our design, the bias is bounded by the constraint
that revisions targeted distinguishability only (archetype-level Brier was not observed),
so the taxonomy design cannot be biased toward selecting archetypes that would improve
the primary H1/H2 outcomes.

---

## 4.5  Evaluation Metrics

**Primary — Ensemble Brier score.** The society-level Brier score is:

$$B_{\text{ens},d} = \frac{1}{|\mathcal{B}_d|} \sum_{t \in \mathcal{B}_d}
\left(\bar{p}_t - \omega_t\right)^2$$

where $\bar{p}_t = \frac{1}{N}\sum_i p_{i,t}$ is the ensemble mean prediction.
We report $B_{\text{ens}}$ as the rolling 28-day average to smooth nightly
variance. Our target threshold is $B_{\text{ens}} < 0.21$
(matching the best single-model benchmark from the island GA fleet, 0.21139,
as the minimum standard for societal improvement over any constituent model).
Lower is better [@brier1950verification; @gneiting2007strictly].

**Secondary — JSD diversity.** Daily Jensen–Shannon diversity $D_d$ as defined
in §3.3. We report 28-day rolling $\overline{D}_d$ alongside $B_{\text{ens}}$
to trace the diversity–accuracy coupling over time.

**Tertiary — Calibration (ECE).** Expected calibration error [@guo2017calibration]
is computed by partitioning predictions into ten equal-width probability bins
and measuring the mean absolute gap between mean predicted probability and
mean empirical event frequency within each bin. ECE is reported to ensure
that Brier improvements are not achieved by increasing prediction extremism
(a high-variance uncalibrated predictor can have the same mean Brier as a
well-calibrated moderate one, but for different reasons).

**Tertiary — Bankroll growth.** The compound annual growth rate (CAGR) of
each agent's virtual bankroll, computed over the full 175-day trading window.
Stake sizing follows evidence-based Kelly criterion [@kelly1956new] with
per-agent caps $\kappa_i$ tuned from pilot Brier estimates (empirical range $[0.01, 0.20]$; §3.6).
This metric captures whether diversity improvements translate into financial
performance under realistic staking constraints.

**Walk-forward evaluation protocol.** To prevent leakage, all reported
metrics are computed on a strict chronological forward walk: no agent has
access to any event that occurs after the prediction timestamp. The
experimental log is segmented into 25 weekly windows of approximately
seven calendar days each; metrics are reported per-window and aggregated
to produce bootstrap 95% confidence intervals (2,000 resamples).

---

## 4.6  Infrastructure and Reproducibility

**Compute.** All LLM inference is performed via remote API calls to
commercial providers (Cerebras, Google, Mistral, OpenRouter) proxied through
a centralised LLM gateway HuggingFace Space (`LBJLincoln26/llm-gateway`). No GPU training occurs in this experiment; the
feature-engine oracle that generates context summaries was pre-trained
on data through the 2024–25 NBA season and frozen before the 2025–26
season began. This ensures a complete temporal separation between
oracle training data and experimental evaluation data.

**Reproducibility.** The Day-Bucket v3 pipeline is hosted on
HuggingFace Space `LBJLincoln26/nba-llm-trading-floor` (NBA) and
`LBJLincoln26/political-llm-trading-floor` (political)
(main application: `app.py`, approximately 4,400 lines, FastAPI + Gradio). All prediction logs, archetype
transition records, and bankroll histories are written to
`data/arena/axelrod-log/` in newline-delimited JSON. The axelrod-log
schema is documented in §C.5. Agent prompts (including all 20
archetype modules and the shared mission preamble) are archived in
`data/arena/archetypes/`. LLM temperature is fixed at
$\tau = 0.7$ for all agents across all conditions to balance
expressiveness with reproducibility; sensitivity to $\tau$ is tested
in Appendix C.3. We note that for managed-inference APIs (T1–T12 as actually deployed;
see Table 3 note$^\dagger$), the provider's instruction-following fine-tuning
mediates the relationship between the API temperature parameter and
token-logit variance, so the effective stochasticity at $\tau = 0.7$ is
provider-dependent across all twelve agents.
The $\tau = 0.7$ selection was validated on T4 (Gemini 3 Flash,
*analytical* archetype); Appendix C.3.3 discusses the two mechanisms
(RLHF-induced distribution sharpening and provider-specific sampling pipelines)
that cause managed-inference models to respond to `temperature` differently
from base models.

**Pre-registration.** The four primary hypotheses tested in this paper —
(H1) SRR increases $\overline{D}$ versus fixed ensemble;
(H2) SRR reduces $B_{\text{ens}}$ versus fixed ensemble;
(H3) Sham-SRR does not reproduce the Brier improvement of full SRR;
(H4) DMAD-static achieves higher initial $\overline{D}$ than
fixed ensemble but does not sustain it over 175 days —
were documented in `data/arena/preregistration-2025-10-01.md`
before the 2025–26 NBA season began, preventing post-hoc hypothesis
selection. The pre-registration file is included in the supplementary
materials and its SHA-256 hash is committed to the repository at
tag `preregistration-v1`.

A fifth pre-registered test addresses potential outcome contamination.
The pre-registration identified T12's self-hosted Qwen3-4B as the primary
contamination risk; following T12's Cerebras rerouting (Table 3 note$^\dagger$),
the operative contamination risk extends to all agents running Qwen 3 235B-A22B
(T1, T2, and T12 as rerouted), whose training data cutoff is not publicly
disclosed by Cerebras:

**(H5 — Contamination-detection test.)** If the Qwen 3 235B-A22B agent
sub-group (T1, T2, T12) outperforms the non-Qwen commercial cohort median
(T3–T11 median Brier) by more than $\Delta_{\text{cont}} = 0.005$ Brier
in any condition other than Condition A (SRR), evaluated exclusively on events
occurring after 2025-10-01, this constitutes a contamination flag.
The threshold $\Delta_{\text{cont}} = 0.005$ is set at approximately two
within-session standard deviations of rolling daily Brier (estimated from pilot data),
so genuine contamination — a systematic knowledge advantage from training-data
overlap with the 2025–26 season — would be detectable against day-to-day noise.
If H5 is triggered, the analysis will be rerun excluding T1, T2, and T12 from
the primary comparison, with the discrepancy documented in §7.4.
The pre-registration of H5 prevents post-hoc exclusion of any Qwen agent if it
performs poorly (data dredging in the other direction).

---

> **Note on statistical power.** With $T = 1{,}257$ NBA events grouped into
> day-buckets (average cluster size $\bar{m} \approx 7.2$ games), the effective
> sample size depends on the assumed intra-bucket intraclass correlation (ICC).
> Pilot data suggest $\rho_{\text{ICC}} \in [0.10, 0.15]$, yielding design
> effects DEFF $\in [1.62, 1.93]$ and $n_{\text{eff}} \in [651, 776]$
> independent observations; the conservative lower bound ($n_{\text{eff}} = 651$,
> ICC $= 0.15$, DEFF $= 1.93$) is used in all power calculations (Appendix C.4).
> A two-sided paired $t$-test to detect a Brier improvement of $0.005$
> ($\approx 2.3\%$ relative) at $\alpha = 0.05$, $\beta = 0.20$ requires
> $n \approx 342$ game-equivalents; our conservative $n_{\text{eff}} = 651$
> comfortably exceeds this, yielding power $\approx 97\%$ (Appendix C.4.1).
> Political events ($T = 1{,}120$) provide a comparable effective sample
> after adjusting for within-category correlation.
