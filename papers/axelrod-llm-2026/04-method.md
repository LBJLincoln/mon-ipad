# Method

We present the **LLM Prediction Society Game** (LPSG), a formal framework that generalises
Axelrod's iterated Prisoner's Dilemma to (a) LLM agents reasoning over natural language,
(b) a continuous-action prediction market with real-world ground truth,
(c) day-end common-knowledge broadcasts, and (d) an endogenous diversity mechanism —
*Sacrificial Role Reallocation* (SRR). We then prove that SRR strictly increases
expected population diversity and characterise it as a Strong Nash equilibrium refinement.

---

## 3.1 Primitives and Notation

**Agents.** Let $\mathcal{I} = \{1, \ldots, N\}$ be a finite population of $N$ agents.
Each agent $i$ is backed by a large language model $\mathcal{M}_i$, which may be a distinct
model or a distinct instance of the same model with a different system prompt.
Agent $i$ is assigned a *strategy archetype* $r_i \in \mathcal{R}$, where
$\mathcal{R} = \{r^{(1)}, \ldots, r^{(K)}\}$ is a finite taxonomy of $K$ archetypes
(e.g., *quantitative*, *contrarian*, *arbitrage*, *analytical*, *tactical*;
see Appendix A for the full 20-archetype taxonomy used in experiments).

**Events.** Let $\mathcal{E} = \{e_1, e_2, \ldots, e_T\}$ be a sequence of $T$
binary-outcome events with exogenous ground-truth resolutions $\omega_t \in \{0, 1\}$.
Events are grouped into day-buckets $\mathcal{B}_d \subseteq \mathcal{E}$, $d = 1, \ldots, D$,
which partition $\mathcal{E}$ so that $\bigcup_d \mathcal{B}_d = \mathcal{E}$ and
$\mathcal{B}_d \cap \mathcal{B}_{d'} = \emptyset$ for $d \neq d'$.
In our NBA domain, each day-bucket contains all games played on calendar day $d$;
in our political domain, each bucket contains all events whose market closes on day $d$.

**Prediction context.** At the start of day $d$, every agent receives a common-knowledge
context observation $x_d \in \mathcal{X}$, comprising public market signals
(spread, moneyline, total), form statistics, standings, and any available news.
Crucially, $x_d$ does not include peer predictions from day $d$ — only the outcomes
$\Omega_{d-1} = \{\omega_t : t \in \mathcal{B}_{d-1}\}$ of the previous day's events.
This asymmetry — outcome broadcast without prediction broadcast — is the formal mechanism
that prevents common knowledge of beliefs from collapsing all agent posteriors
(cf. Aumann, 1976 [@aumann1976agreeing]; see §6.2 for elaboration).

**Actions.** On day $d$, each agent $i$ reports a probability estimate
$p_{i,t} \in [0, 1]$ for each event $t \in \mathcal{B}_d$.
We write $\mathbf{p}_{i,d} = (p_{i,t})_{t \in \mathcal{B}_d} \in [0,1]^{|\mathcal{B}_d|}$.

**Scoring rule.** Agent performance is evaluated by the Brier score [@brier1950verification],
a strictly proper scoring rule [@gneiting2007strictly]:

$$\text{BS}(p, \omega) = (p - \omega)^2$$

The agent's per-day Brier score is:

$$B_{i,d} = \frac{1}{|\mathcal{B}_d|} \sum_{t \in \mathcal{B}_d} (p_{i,t} - \omega_t)^2$$

and the rolling mean Brier score over the most recent $W$ days is
$\overline{B}_{i,d} = \frac{1}{W}\sum_{\ell=d-W+1}^{d} B_{i,\ell}$.
Society-mean Brier is $\bar{B}_d = \frac{1}{N}\sum_i \overline{B}_{i,d}$.

**Strategy.** Agent $i$'s *strategy* is a stochastic function:

$$\sigma_i : (\mathcal{R} \times \mathcal{X} \times \mathcal{H}) \rightarrow \mathcal{P}([0,1]^{|\mathcal{B}_d|})$$

where $\mathcal{H}$ is the space of agent-private histories and $\mathcal{P}(\cdot)$
denotes the set of Borel probability measures over its argument (the action space
$[0,1]^{|\mathcal{B}_d|}$ is continuous; the finite-set notation $\Delta(\mathcal{R})$
is used below for the discrete archetype simplex). In practice, $\sigma_i$ is implemented by prompting
$\mathcal{M}_i$ with the structured prompt $\Pi(r_i, x_d, h_{i,d-1})$, where
$h_{i,d-1}$ is agent $i$'s private history (own predictions, outcomes seen, bankroll).
The LLM samples a response, which is parsed into the prediction vector $\mathbf{p}_{i,d}$.

**Population state.** At day $d$, the *population archetype state* is:

$$\mathbf{x}_d = \left(\frac{|\{i : r_i = r\}|}{N}\right)_{r \in \mathcal{R}} \in \Delta(\mathcal{R})$$

the empirical distribution of agents over archetypes.

---

## 3.2 The LLM Prediction Society Game

The LPSG is a repeated game with the following structure.

> **Definition 1 (LPSG).** The *LLM Prediction Society Game* is the tuple
> $(\mathcal{I}, \mathcal{R}, \mathcal{E}, \mathcal{X}, \sigma, \text{BS}, \text{CK}, \text{SRR})$
> where $\text{CK}$ denotes the day-end common-knowledge broadcast protocol and
> $\text{SRR}$ is the sacrificial role reallocation mechanism defined in §3.4.
> Within each day $d$, play proceeds as:
>
> 1. **Context receipt.** All agents receive $x_d$ and $\Omega_{d-1}$ simultaneously.
> 2. **Prediction.** Each agent $i$ independently samples $\mathbf{p}_{i,d} \sim \sigma_i(r_i, x_d, h_{i,d-1})$.
> 3. **Resolution.** Outcomes $\omega_t$ are revealed as events $t \in \mathcal{B}_d$ resolve.
> 4. **Score.** $B_{i,d}$ is computed for all $i$.
> 5. **Broadcast.** $\Omega_d$ is broadcast as common knowledge. The current leaderboard — comprising agent archetype labels $\{r_j\}_{j \in \mathcal{I}}$ and cumulative bankroll standings — is also broadcast as common knowledge, enabling each agent to compute the population state $\mathbf{x}_d$ required for SRR vacancy checking (§3.4). Peer predictions $\mathbf{p}_{j,d}$ for $j \neq i$ are NOT broadcast.^[Strictly, broadcasting cumulative bankroll standings could allow partial reverse-engineering of peer stake sizes. We bound this leakage: (a) the rolling Brier $\overline{B}_{j,d}$ that determines each agent's Kelly cap $\kappa_j$ is private and changes daily; (b) the broadcast shows cumulative totals rather than marginal day-over-day increments; and (c) the personality risk weight $\rho_j$ is an internal agent parameter not included in the broadcast. Exact prediction inference therefore requires knowledge of $\kappa_j$, $\rho_j$, and $\kappa_{\min}^{(r_j)}$ simultaneously — all three are either private or daily-varying. The leakage is thus partial and approximate, not exact, and constitutes a minor acknowledged deviation from strict informational separation (see §7.3).]
> 6. **SRR check.** Sacrifice eligibility is evaluated; reallocations execute (§3.4).

This structure places the LPSG in the family of *Bayesian population games*
[@sandholm2010population], in which each agent has a private type
(here, the pair $(r_i, \mathcal{M}_i)$) that determines its strategy mapping,
and fitness is determined by the realised Brier score against exogenous ground truth.
The key departure from classical population games is that fitness depends on
a strictly proper scoring rule rather than a payoff matrix — this ensures that
no agent can improve expected score by misreporting beliefs, giving the game
its *truth-inducing* character [@gneiting2007strictly].

**Relation to the Axelrod IPD.** The classical IPD is recovered as the degenerate
case $K = 1$ (all agents in a single archetype), $|\mathcal{B}_d| = 1$ (single binary
event per round), $T = $ finite tournament length, and strategies restricted to the
two actions $\{0, 1\}$. Our framework generalises along all four dimensions simultaneously.

---

## 3.3 Diversity Metric

We quantify prediction diversity via the *day-$d$ Jensen–Shannon diversity*
[@lin1991divergence]:

$$D_d = \frac{1}{|\mathcal{B}_d|} \sum_{t \in \mathcal{B}_d}
\text{JSD}\!\left(\text{Ber}(p_{1,t}), \ldots, \text{Ber}(p_{N,t})\right)$$

where for $N$ Bernoulli distributions with means $p_1, \ldots, p_N$:

$$\text{JSD}(p_1, \ldots, p_N) = H\!\left(\bar{p}\right) - \frac{1}{N}\sum_{i=1}^N H(p_i)$$

with $\bar{p} = \frac{1}{N}\sum_i p_i$ and $H(p) = -p\log_2 p - (1-p)\log_2(1-p)$
the binary entropy function. JSD is bounded in $[0, 1]$ for $\log_2$ entropy
and equals zero if and only if all agents report identical predictions.

The connection to ensemble accuracy is formalised by the *Brier ambiguity decomposition*
[@brown2005diversity]:

$$\underbrace{B_{\text{ens},t}}_{\text{ensemble Brier}} =
\underbrace{\frac{1}{N}\sum_i B_{i,t}}_{\overline{\text{indiv. Brier}}} -
\underbrace{\frac{1}{N}\sum_i (p_{i,t} - \bar{p}_t)^2}_{\text{Ambiguity}}$$

Since Ambiguity $\geq 0$ always, any mechanism that increases inter-agent prediction
variance without degrading mean individual calibration will reduce ensemble Brier.
Averaging the decomposition over all events $t \in \mathcal{B}_d$ and using the
per-day Brier definitions from §3.1 gives the day-level identity:

$$B_{\text{ens},d} = \frac{1}{N}\sum_i B_{i,d} - \text{Amb}_d, \quad
\text{Amb}_d = \frac{1}{|\mathcal{B}_d|}\sum_{t \in \mathcal{B}_d}
\frac{1}{N}\sum_i (p_{i,t} - \bar{p}_t)^2$$

JSD is a monotone function of this $\text{Amb}_d$ term for Bernoulli predictions in the
operating range $\bar{p}_t \in [0.15, 0.85]$, $\text{Amb} \leq 0.08$
(proof: Appendix B.1, via Taylor expansion of $H$ around $\bar{p}$), so increasing
$D_d$ is equivalent to reducing $B_{\text{ens},d}$ holding $\frac{1}{N}\sum_i B_{i,d}$ fixed.
This motivates $D_d$ as our primary diversity target.

---

## 3.4 Sacrificial Role Reallocation (SRR)

We now define SRR formally.

**Sacrifice eligibility.** Agent $i$ is *sacrifice-eligible* at day $d$ if:

$$\overline{B}_{i,d} - \bar{B}_d > \delta_{\text{sac}} \quad \text{for } W \text{ consecutive days}$$

where $\delta_{\text{sac}} > 0$ is the sacrifice threshold and $W$ is the patience window.
The consecutive-day requirement prevents transient losses from triggering unnecessary
reallocations. We set $\delta_{\text{sac}} = 0.02$ and $W = 7$ based on
cross-validation on the held-out 2024–25 pilot season (both NBA and political
calendars; Appendix C.2).

**Archetype vacancy.** Archetype $r^* \in \mathcal{R}$ is *vacant* at day $d$ if:

$$x_{r^*,d} < \tau_{\text{vac}} \triangleq \frac{1}{2K}$$

i.e., fewer than half the uniform fair-share of agents hold this archetype.
Let $\mathcal{V}_d = \{r \in \mathcal{R} : x_{r,d} < \tau_{\text{vac}}\}$ denote
the vacancy set. *Note (experimental parameters):* With $N = 12$ agents and $K = 20$
archetypes, $\tau_{\text{vac}} = 0.025 < 1/N = 0.083$, so the condition reduces to
$|\{i : r_i = r^*\}| = 0$: an archetype is vacant if and only if no agent currently
holds it. The general $\frac{1}{2K}$ formula is stated for systems where $N \geq 2K$;
in our under-populated regime, vacancy and zero-occupancy coincide (see Appendix A, §A.5).

**SRR rule.**

> **Definition 2 (Sacrificial Role Reallocation).** If agent $i$ is sacrifice-eligible
> at day $d$ and $\mathcal{V}_d \neq \emptyset$:
>
> 1. Draw $r^* \sim \text{Uniform}(\mathcal{V}_d)$.
> 2. Update agent $i$'s archetype: $r_i \leftarrow r^*$.
> 3. Rewrite agent $i$'s system prompt to reflect archetype $r^*$.
> 4. Persist for $W_{\text{persist}} = 14$ days; agent $i$ is ineligible for further SRR events during this window (sacrifice-eligibility is suspended from day $d$ through day $d + W_{\text{persist}} - 1$).
> 5. After $W_{\text{persist}}$ days: if $\overline{B}_{i,d+W_{\text{persist}}} < \overline{B}_{i,d} - \epsilon_{\text{keep}}$, retain $r^*$; else revert to $r_i^{(\text{pre})}$, the archetype held by agent $i$ immediately before this SRR event. (Note: $r_i^{(\text{pre})}$ may itself differ from the agent's initial archetype if multiple SRR events have occurred; each event stores its own pre-event archetype for potential reversal.)

We set $\epsilon_{\text{keep}} = 0.005$ (one-half Brier standard deviation in our
pilot data). SRR is *decentralised*: no central planner is needed. Each agent
executes the eligibility check using only its own Brier history and the population
state $\mathbf{x}_d$ (which is available via the leaderboard broadcast).

**Multiple simultaneous eligibilities.** When $|\{i : i \text{ is sacrifice-eligible at day } d\}| > 1$,
reallocations execute in decreasing order of $\overline{B}_{i,d}$ (worst performer first),
with the vacancy set $\mathcal{V}_d$ recomputed after each individual reallocation to
reflect the updated archetype distribution. This sequential greedy execution ensures
that the agent with the largest performance deficit receives the widest vacancy set,
and prevents two agents from independently drawing the same vacant archetype and
partially defeating the diversity objective.

**Prompt mechanics.** The archetype taxonomy $\mathcal{R}$ is operationalised
as a library of 20 system-prompt modules (Appendix A). When SRR fires,
the agent's system prompt is atomically replaced by composing the shared
mission preamble — a ~300-word statement establishing the collective \$1M
target, mandatory deployment floor, and collaborative protocols,
common to all agents — with the new archetype module.
The agent's prediction history and bankroll state are preserved across the transition —
only the reasoning disposition changes, not the agent's memory.

---

## 3.5 Theoretical Analysis

We now establish two results: (i) SRR strictly increases expected JSD diversity,
and (ii) SRR constitutes an equilibrium refinement in societal Brier space.

**Assumption A1 (Archetype distinguishability).** For all $r \neq r' \in \mathcal{R}$
and all $\mathcal{M}$, the expected absolute prediction difference is bounded below:

$$\mathbb{E}_{x, t}\!\left[|p_{i,t}(\mathcal{M}, r, x) - p_{i,t}(\mathcal{M}, r', x)|\right] \geq \epsilon_{\text{arch}} > 0$$

Assumption A1 is a mild identifiability condition: archetypes that produce
identical expected predictions would be indistinguishable and hence redundant
in the taxonomy. We verify A1 empirically in §5.1 (all $\binom{20}{2} = 190$ pairwise archetype combinations
exhibit $\epsilon_{\text{arch}} \geq 0.037$ on our held-out validation set).

**Assumption A2 (Sacrifice-eligible agents track the population mean).** An agent
that is sacrifice-eligible (persistently above-mean Brier) has predictions that
are, in expectation, *closer* to the population centroid $\bar{p}$ than the
average prediction distance in the population:

$$\mathbb{E}_t\!\left[|p_{i,t} - \bar{p}_t|\right] \leq
\mathbb{E}_t\!\left[\frac{1}{N}\sum_j |p_{j,t} - \bar{p}_t|\right]$$

Assumption A2 formalises the intuition that chronically underperforming agents
are those whose predictions are most similar to the prevailing consensus —
they add the least diversity and hence the least Ambiguity to the ensemble.
This is consistent with the empirical finding that poorly calibrated agents
in correlated prediction markets tend to mirror the favourite rather than
take differentiated positions [@surowiecki2004wisdom].

> **Lemma 1 (SRR increases expected diversity).** Under A1 and A2, an SRR event
> at day $d$ strictly increases $\mathbb{E}[D_{d+1}]$.

*Proof.* Let agent $i$ be sacrifice-eligible, $\Delta p = p_{i,t}' - p_{i,t}$,
and $\delta_i = p_{i,t} - \bar{p}_t$.
By A1, $\mathbb{E}[|\Delta p|] \geq \epsilon_{\text{arch}}$ and hence
$\mathbb{E}[(\Delta p)^2] \geq \epsilon_{\text{arch}}^2 > 0$.

**Exact Ambiguity formula.** Let $\bar{p}_t' = \bar{p}_t + \Delta p/N$.
Expanding $(p_{i,t}' - \bar{p}_t')^2 = (\delta_i + \Delta p(N-1)/N)^2$ and
$(p_{j,t} - \bar{p}_t')^2 = (\delta_j - \Delta p/N)^2$ for $j \neq i$,
summing, and using $\sum_j \delta_j = 0$ (centroid identity), one obtains:

$$\Delta\text{Amb}_t = \frac{(\Delta p)^2(N-1)}{N^2} + \frac{2\delta_i\Delta p}{N}$$

The leading term is always non-negative; the cross-term $\frac{2\delta_i\Delta p}{N}$
can take either sign.  We consider both cases.

*Case 1* ($\delta_i\Delta p \geq 0$, i.e.\ the new archetype moves the agent's prediction
away from or orthogonal to the centroid):

$$\Delta\text{Amb}_t \;\geq\; \frac{(\Delta p)^2(N-1)}{N^2} \;\geq\; \frac{\epsilon_{\text{arch}}^2(N-1)}{N^2} > 0$$

*Case 2* ($\delta_i\Delta p < 0$, i.e.\ the new archetype moves the prediction toward
the centroid):

$$\Delta\text{Amb}_t = |\Delta p|\!\left[\frac{|\Delta p|(N-1)}{N^2} - \frac{2|\delta_i|}{N}\right]$$

This is positive whenever $|\delta_i| < \frac{|\Delta p|(N-1)}{2N}$.
By A2, $\mathbb{E}[|\delta_i|] \leq \mathbb{E}\!\left[\frac{1}{N}\sum_j |p_{j,t}-\bar{p}_t|\right]$ —
the expected centroid deviation of a sacrifice-eligible agent is bounded above by the
population-average expected absolute deviation.  Pilot data (§5.1) estimate this
population average at $0.014$, yielding $\mathbb{E}[|\delta_i|] \leq 0.014$ as the
quantitative bound used below (A2 provides the structural direction; the pilot value
furnishes the numerical threshold).
The conclusion $\mathbb{E}[\Delta\text{Amb}_t] > 0$ follows by taking a lower bound on the cross-term.
Since $\delta_i\Delta p \geq -|\delta_i||\Delta p|$ always (with equality only when the product is negative),
the worst-case sign of the cross-term yields:

$$\mathbb{E}[\Delta\text{Amb}_t] \;\geq\; \frac{N-1}{N^2}\mathbb{E}[(\Delta p)^2] - \frac{2}{N}\mathbb{E}[|\delta_i||\Delta p|]$$

It is sufficient to show this lower bound is positive.
We invoke the independence of $\delta_i$ (the agent's pre-SRR centroid deviation, determined
before SRR draws a new archetype from $\mathcal{V}_d$) and $\Delta p$ (the prediction change
induced by that new archetype, drawn uniformly from $\mathcal{V}_d$ after eligibility is
established). Under this independence, $\mathbb{E}[|\delta_i||\Delta p|] = \mathbb{E}[|\delta_i|]\cdot\mathbb{E}[|\Delta p|]$.
By Jensen's inequality applied to the convex function $f(x) = x^2$,
$\mathbb{E}[(\Delta p)^2] \geq (\mathbb{E}[|\Delta p|])^2$; factoring $\mathbb{E}[|\Delta p|]$
out of the lower bound then yields the sufficient condition:

$$\frac{N-1}{N}\mathbb{E}[|\Delta p|] > 2\,\mathbb{E}[|\delta_i|]$$

Since $\mathbb{E}[|\Delta p|] \geq \epsilon_{\text{arch}} = 0.037$ (A1) and
$\mathbb{E}[|\delta_i|] \leq 0.014$ (A2 + pilot data, §5.1), the LHS $\geq \frac{11}{12}\times 0.037 = 0.034$
and the RHS $= 0.028$, giving $0.034 > 0.028$. $\checkmark$

In both cases, $\mathbb{E}[\Delta\text{Amb}_t] > 0$.
By the JSD–Ambiguity monotonicity result (Appendix B.1, valid for
$\bar{p}_t \in [0.15, 0.85]$ and $\text{Amb}_t \leq 0.08$), increasing Ambiguity
strictly increases JSD.
Averaging over events $t \in \mathcal{B}_d$ gives $\mathbb{E}[\Delta D_{d+1}] > 0$. $\square$

**Assumption A3 (No spontaneous recovery).** In the absence of an archetype change,
a sacrifice-eligible agent's expected Brier over the next $W_{\text{persist}}$ days
is at least $\bar{B}_d + \delta_{\text{sac}}/2$ (partial persistence of the performance
deficit). This assumption excludes pure mean-reversion scenarios and is empirically
testable via the Sham-SRR control (§4.3).

> **Proposition 2 (SRR as equilibrium refinement).** In the LPSG, the strategy
> profile $(\sigma_i^{\text{SRR}})_{i \in \mathcal{I}}$ — where every
> sacrifice-eligible agent executes SRR — is a *Strong Nash Equilibrium*
> [@aumann1959acceptable] against *sacrifice-refusal deviations* in the societal
> Brier minimisation game: no coalition
> $\mathcal{C} \subseteq \mathcal{I}_d^{\text{elig}} = \{i \in \mathcal{I} : i
> \text{ is sacrifice-eligible at day } d\}$ of sacrifice-eligible agents can
> collectively refuse SRR and (weakly) improve the ensemble Brier of $\mathcal{C}$
> while (weakly) reducing individual Brier for all members of $\mathcal{C}$.
> (The qualification "against sacrifice-refusal deviations" restricts the SNE
> to the strategically relevant class: non-eligible agents have no SRR action to
> refuse, so they are not coalition members in this context.)

*Proof sketch.* Apply the Brier ambiguity decomposition to the coalition
sub-ensemble $\mathcal{C}$:

$$B_{\text{ens}}^{\mathcal{C}} = \frac{1}{|\mathcal{C}|}\sum_{i\in\mathcal{C}} B_i - \text{Amb}^{\mathcal{C}},
\quad \text{Amb}^{\mathcal{C}} = \frac{1}{|\mathcal{B}_d|}\sum_{t}\frac{1}{|\mathcal{C}|}\sum_{i\in\mathcal{C}}(p_{i,t} - \bar{p}_t^{\mathcal{C}})^2$$

A coalition deviating from SRR (i.e., sacrifice-eligible agents refusing to
reallocate) forgoes the within-coalition Ambiguity increase that the mechanism
provides: under SRR, eligible agents in $\mathcal{C}$ move to vacant archetypes,
differentiating their predictions from one another and increasing $\text{Amb}^{\mathcal{C}}$;
under deviation, coalition members retain their current consensus archetypes,
leaving $\text{Amb}^{\mathcal{C}}$ at its pre-intervention level.
Applying the Lemma 1 argument to the sub-population $\mathcal{C}$ (which contains
the sacrifice-eligible agents executing or refusing SRR) yields
$\text{Amb}^{\mathcal{C},\text{SRR}} > \text{Amb}^{\mathcal{C},\text{deviation}}$,
so by the coalition-level decomposition above:
$B_{\text{ens}}^{\mathcal{C},\text{deviation}} \geq B_{\text{ens}}^{\mathcal{C},\text{SRR}}$
(coalition ensemble Brier is weakly worse under deviation). Since sacrifice-eligible agents
have $\overline{B}_{i,d} \geq \bar{B}_d + \delta_{\text{sac}}$ by definition,
their individual Brier is above the ensemble mean — refusing SRR does not
improve their individual Brier in expectation (they remain in the same
strategy archetype that produced the deficit, and by Assumption A3,
the deficit persists in expectation). Hence no coalition member
achieves both a reduction in individual Brier and an increase in ensemble Brier
through deviation. The profile $(\sigma^{\text{SRR}})$ is therefore not
improvable by any coalitional deviation in the societal Brier objective. $\square$

*Remark.* Proposition 2 does not claim SRR maximises any single agent's
individual fitness. It claims the *society* cannot improve its collective
accuracy by exempting underperforming agents from the reallocation duty —
a formal analogue of the biological principle that role sacrificers are
stable against invasion by free-riders when societal fitness is the
selection criterion [@nowak2006five].

---

## 3.6 Day-Bucket v3 Architecture

The LPSG is instantiated in a *Day-Bucket v3* pipeline
(Figure 1; implementation at `scripts/arena/hf-llm-trading-floor/`).

**Morning council (09:00 ET, Eastern Time; UTC−5/−4 seasonal).** A *moderator* agent circulates a
structured morning brief: yesterday's outcomes, current bankroll standings,
and any flagged anomalies. All 12 NBA agents and 10 political agents receive
this brief as a shared prefix before generating independent predictions.
The moderator role rotates weekly (Axelrod-style round-robin) across all
agents, beginning with T1 (Qwen 3 235B-A22B) in Week 1; moderating capacity
therefore varies from 235B (T1–T2) to 4B parameters (T12: Qwen3-4B); the
full size breakdown is in §4.1 (T3: Llama 3.1 8B; Mistral T6–T10 sizes are
undisclosed by the provider). This is a minor confound: all agents receive an identical
structured morning brief template regardless of moderator identity, so the
confound is bounded to the quality of free-text synthesis in the brief body.

**Prediction window.** Each agent generates predictions independently
and asynchronously over a 15-minute window. Predictions are sealed;
no agent can observe another's current-day output until the end-of-day broadcast.

**Bankroll and Kelly allocation.** Each agent maintains a virtual bankroll
initialised at \$100,000 USD-equivalent. Stake sizing is governed by three
distinct parameters: (a) the **Kelly cap** $\kappa_i = \max(0.01,\, 0.30 -
\overline{B}_i \times 0.50)$, a Brier-derived per-agent ceiling on the
stake fraction^[The formula's mathematical range is $[0.01, 0.30]$ (maximum
at $\overline{B}_i = 0$); the empirical operating range is $[0.01, 0.20]$ given
our observed pilot Brier $\overline{B}_i \geq 0.20$. Derivation and inverse-calibration
probation criterion in §6.5.], where $\overline{B}_i$ is the rolling 28-day
Brier from the pilot season;
(b) the **personality risk weight** $\rho_i \in (0, 1]$, an agent-specific
scalar that scales realised stake between the archetype floor and the Kelly
ceiling (values in Table 3, §4.1); and (c) the **archetype minimum floor**
$\kappa_{\min}^{(r_i)}$, an archetype-level stake floor that prevents
SRR reassignment from silencing an agent when $\kappa_i$ is temporarily
low (values in Table A.1, Appendix A.3; range $[0.01, 0.08]$).

The **realised stake fraction** on day $d$ is:

$$s_i = \max\!\left(\kappa_{\min}^{(r_i)},\; \rho_i \cdot \kappa_i\right)$$

Each agent receives the island GA oracle's pre-game probability estimate for each event
as a calibration reference in its context block (described in §4.2.1); this reference
does not appear in the stake formula above, which depends solely on $\kappa_i$, $\rho_i$,
and $\kappa_{\min}^{(r_i)}$.
Agents whose rolling Brier persistently exceeds 0.32 (i.e., more than 28% above the
$p = 0.5$ random-Bernoulli baseline of 0.25; derivation in §6.5) receive an additional hard cap $\kappa_i \leq 0.03$ — an
*inverse-calibration probation* applied as a post-formula override,
independent of the pilot Brier formula above (diagnostic criterion and
rationale in §6.5, sub-section "Formula derivation and inverse-calibration
probation criterion," second paragraph).
Note: the archetype minimum floor $\kappa_{\min}^{(r_i)}$ is applied *after* the
probation cap, so for archetypes with $\kappa_{\min}^{(r_i)} > 0.03$ the floor
supersedes the probation ceiling; this is by design — even probation agents
must contribute to the ensemble mean prediction $\bar{p}_t$ at a non-trivial level,
preventing them from vanishing from the ensemble entirely.

**End-of-day broadcast.** At 23:59 UTC, resolved outcomes $\Omega_d$ are
broadcast to all agents. Each agent updates its private history $h_{i,d}$.
SRR eligibility is evaluated using the rolling window of the most recent $W = 7$ days.

**SRR execution.** SRR fires at most once per agent per 14-day window.
The archetype update is applied by modifying the agent's HuggingFace Space
environment variable `AGENT_PERSONA` and issuing a hot-reload of the
system-prompt template (no Space restart required).

---

## 3.7 Summary of Parameters

Table 2 summarises all LPSG hyperparameters and their values in our experiments.

| Symbol | Description | Value |
|--------|-------------|-------|
| $N$ | Number of agents (NBA / political) | 12 / 10 |
| $K$ | Strategy archetypes | 20 |
| $T$ | Total events (NBA / political) | 1,257 / 1,120 |
| $D$ | Total trading days (NBA / political) | 175 / 90 |
| $\kappa_i$ | Agent Kelly cap (Brier-derived) | $\max(0.01,\; 0.30 - 0.50\overline{B}_i)$; empirical range $[0.01, 0.20]$ (§3.6) |
| $\delta_{\text{sac}}$ | Sacrifice threshold (Brier above mean) | 0.02 |
| $W$ | Patience window (days) | 7 |
| $W_{\text{persist}}$ | Reallocation persistence (days) | 14 |
| $\tau_{\text{vac}}$ | Vacancy threshold | $1/(2K) = 0.025$ |
| $\rho_i$ | Personality risk weight (agent-level) | $[0.35, 0.70]$ (actual per Table 3; design floor: 0.30) |
| $\kappa_{\min}^{(r)}$ | Archetype minimum stake floor | $[0.01, 0.08]$ (Table A.1) |
| $\epsilon_{\text{keep}}$ | Retain threshold (Brier improvement) | 0.005 |
| $\epsilon_{\text{arch}}$ | Archetype distinguishability lower bound | 0.037 (empirical) |

*Table 2: LPSG hyperparameters. Values for $\delta_{\text{sac}}$, $W$, and
$\tau_{\text{vac}}$ were selected on a held-out 2024–25 season pilot;
see Appendix C.2 for sensitivity analysis.*

---

> **Note on causal identification.** The SRR mechanism introduces a
> selection bias: agents that undergo SRR are definitionally those
> with the worst recent performance. Any subsequent Brier improvement
> could reflect mean-reversion rather than the archetype change.
> We address this via three controls: (1) an SRR *sham* condition
> in which eligible agents receive a new archetype label but an
> *identical* system prompt (testing whether the label change alone
> drives effects); (2) a *free-rider* ablation in which eligible agents
> are randomly selected for reallocation regardless of performance;
> and (3) a matched pairs analysis comparing each SRR agent to a
> non-eligible agent with the same pre-intervention Brier trajectory.
> All three controls are described in §4.3 and results in §5.3.
