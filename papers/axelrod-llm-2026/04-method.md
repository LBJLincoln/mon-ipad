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

This structure places the LPSG in the family of *population games with type
heterogeneity* — specifically Sandholm's (2010) *Bayesian population game*
framework [@sandholm2010population]^[We use 'Bayesian' in Sandholm's sense:
each agent has a fixed private type $(r_i, \mathcal{M}_i)$ that determines
its prediction-generating strategy. This differs from Harsanyi Bayesian games,
where types are drawn from a common prior over a finite type space.
The 'Bayesian' structure in our setting refers instead to the prediction-theoretic
layer: the Brier scoring rule is strictly proper, so optimal prediction
requires each agent to form a genuine posterior over the event outcome.
The game is thus Bayesian in the *calibration* sense (truth-inducing payoffs)
rather than the *incomplete-information* sense (hidden drawn types).] —
in which each agent has a private type (here, the pair $(r_i, \mathcal{M}_i)$)
that determines its strategy mapping, and fitness is determined by the realised
Brier score against exogenous ground truth.
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
> 5. After $W_{\text{persist}}$ days: if $\overline{B}_{i,d+W_{\text{persist}}} < \overline{B}_{i,d} - \epsilon_{\text{keep}}$, retain $r^*$; else revert to $r_i^{(\text{pre})}$, the archetype held by agent $i$ immediately before this SRR event. (Note: $r_i^{(\text{pre})}$ may itself differ from the agent's initial archetype if multiple SRR events have occurred; each event stores its own pre-event archetype for potential reversal.)^[An alternative design stores the agent's *initial* archetype $r_i^{(0)}$ as the permanent reversal target ("home base"), rather than the immediately-prior archetype. This prevents multi-SRR drift — successive failed reallocations cannot move an agent progressively further from its original reasoning disposition — but it discards any beneficial intermediate transitions that would otherwise be retained by the immediately-prior design. Because the 14-day persistence window ($W_{\text{persist}}$) limits the rate of SRR events to at most $\lfloor D / 14 \rfloor \approx 12$ events per agent over a 175-day season, multi-SRR chains deeper than two hops are rare in practice. A sensitivity analysis comparing the two reversal targets (immediately-prior vs.\ home-base) is reported in §C.2.3.]

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

**Assumption A4 (Archetype-shift event-independence).** The expected absolute
prediction shift induced by drawing a vacant archetype uniformly at random is
approximately constant across event contexts:

$$\sup_{x_t \in \mathcal{X}}\;\mathbb{E}_{r^* \sim \text{Unif}(\mathcal{V}_d)}\!\left[|\Delta p(r^*\!, x_t)|\right]
\;\leq\; \mathbb{E}[|\Delta p|]\;\cdot\;(1 + \eta_{\text{A4}})$$

for a small slack $\eta_{\text{A4}} \geq 0$.
This holds when archetype-induced prediction shifts do not concentrate on a small
subset of event types — a condition verified if A1 ($\epsilon_{\text{arch}} \geq 0.037$)
holds uniformly across the event distribution rather than only in aggregate.
A4 is empirically testable from the pilot backtest by stratifying
$\hat{\epsilon}_{\text{arch}}$ by event type; we report this stratification in
Table B.2 (pending pilot data).

**Assumption A5 (Pilot Brier bound).** The population-average expected absolute
centroid deviation satisfies:

$$\mathbb{E}_t\!\left[\frac{1}{N}\sum_{j=1}^N |p_{j,t} - \bar{p}_t|\right] \;\leq\; 0.014$$

This bound is empirically verified from the 2024–25 pilot season holdout backtest
(§5.1, Table 4). A5 is not implied by A1–A4 alone; it provides the numerical
threshold required for the Case 2 arithmetic in the Lemma 1 proof. Should the
pilot bound exceed 0.014, the lemma still holds provided
$\mathbb{E}[|\delta_i|] < \frac{(N-1)}{2N}\epsilon_{\text{arch}} = \frac{11}{24}\times 0.037 \approx 0.017$;
values in $(0.014, 0.017)$ tighten the numerical margin but do not overturn the result.

> **Lemma 1 (SRR increases expected diversity).** Under A1, A2, A4, and A5, an SRR event
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
population-average expected absolute deviation.  By Assumption A5,
$\mathbb{E}_t[\frac{1}{N}\sum_j|p_{j,t}-\bar{p}_t|] \leq 0.014$, yielding
$\mathbb{E}[|\delta_i|] \leq 0.014$ as the quantitative bound used below
(A2 provides the structural direction; A5 furnishes the pilot-verified numerical threshold).
The conclusion $\mathbb{E}[\Delta\text{Amb}_t] > 0$ follows by taking a lower bound on the cross-term.
Since $\delta_i\Delta p \geq -|\delta_i||\Delta p|$ always (with equality only when the product is negative),
the worst-case sign of the cross-term yields:

$$\mathbb{E}[\Delta\text{Amb}_t] \;\geq\; \frac{N-1}{N^2}\mathbb{E}[(\Delta p)^2] - \frac{2}{N}\mathbb{E}[|\delta_i||\Delta p|]$$

It is sufficient to show this lower bound is positive.
We bound the cross-term via Assumption A4.  Conditional on event context $x_t$,
the archetype draw $r^* \sim \text{Uniform}(\mathcal{V}_d)$ is independent of
the pre-SRR deviation $\delta_i(x_t)$ (which is determined before the draw).
Therefore:

$$\mathbb{E}[|\delta_i||\Delta p|] = \mathbb{E}_{x_t}\!\bigl[|\delta_i(x_t)|\cdot\mathbb{E}_{r^*}\!\bigl[|\Delta p(r^*\!,x_t)|\bigr]\bigr]
\;\leq\; \mathbb{E}[|\delta_i|]\cdot\sup_{x_t}\mathbb{E}_{r^*}[|\Delta p(r^*\!,x_t)|]$$

Under A4, $\sup_{x_t}\mathbb{E}_{r^*}[|\Delta p(r^*, x_t)|] \leq \mathbb{E}[|\Delta p|]\cdot(1+\eta_{\text{A4}})
\approx \mathbb{E}[|\Delta p|]$ for small $\eta_{\text{A4}}$, giving
$\mathbb{E}[|\delta_i||\Delta p|] \lesssim \mathbb{E}[|\delta_i|]\cdot\mathbb{E}[|\Delta p|]$.
By Jensen's inequality applied to the convex function $f(x) = x^2$,
$\mathbb{E}[(\Delta p)^2] \geq (\mathbb{E}[|\Delta p|])^2$; factoring $\mathbb{E}[|\Delta p|]$
out of the lower bound then yields the sufficient condition:

$$\frac{N-1}{N}\mathbb{E}[|\Delta p|] > 2\,\mathbb{E}[|\delta_i|]$$

Since $\mathbb{E}[|\Delta p|] \geq \epsilon_{\text{arch}} = 0.037$ (A1) and
$\mathbb{E}[|\delta_i|] \leq 0.014$ (A5), the LHS $\geq \frac{11}{12}\times 0.037 = 0.034$
and the RHS $= 0.028$, giving $0.034 > 0.028$. $\checkmark$

In both cases, $\mathbb{E}[\Delta\text{Amb}_t] > 0$.
By the JSD–Ambiguity monotonicity result (Appendix B.1, valid for
$\bar{p}_t \in [0.15, 0.85]$ and $\text{Amb}_t \leq 0.08$), increasing Ambiguity
strictly increases JSD. Pilot season data confirm that NBA game-day centroids satisfy
$\bar{p}_t \in [0.24, 0.76]$ and day-level Ambiguity $\text{Amb}_d \leq 0.04$ throughout
the 2024–25 season (Table 4, §5.1); the monotonicity regime is therefore satisfied
throughout the experimental range, and the step applies without qualification.
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

*Proof.* We establish two claims and then combine them.

**Claim 1 (Coalition ensemble Brier weakly increases under deviation).**
Apply the Brier ambiguity decomposition to the coalition sub-ensemble $\mathcal{C}$:

$$B_{\text{ens}}^{\mathcal{C}} = \frac{1}{|\mathcal{C}|}\sum_{i\in\mathcal{C}} B_i - \text{Amb}^{\mathcal{C}},
\quad \text{Amb}^{\mathcal{C}} = \frac{1}{|\mathcal{B}_d|}\sum_{t}\frac{1}{|\mathcal{C}|}\sum_{i\in\mathcal{C}}(p_{i,t} - \bar{p}_t^{\mathcal{C}})^2$$

*Case $|\mathcal{C}|=1$:* With a single agent, $\text{Amb}^{\mathcal{C}} \equiv 0$ identically.
The decomposition yields $B_{\text{ens}}^{\mathcal{C}} = B_i$, so ensemble and individual
Brier coincide; any claim about ensemble-Brier improvement requires individual-Brier
improvement, which is addressed in Claim 2 below.

*Case $|\mathcal{C}|\geq 2$:* A coalition refusing SRR forgoes the within-coalition
Ambiguity increase that the mechanism provides.  Under SRR, eligible agents in
$\mathcal{C}$ draw archetype assignments from $\mathcal{V}_d$, differentiating their
predictions from one another and increasing $\text{Amb}^{\mathcal{C}}$.  Under
deviation, coalition members retain their current archetypes, so
$\text{Amb}^{\mathcal{C},\text{deviation}} = \text{Amb}^{\mathcal{C},\text{pre}}$.
Applying the Lemma 1 argument to the sub-population $\mathcal{C}$ (Assumptions A1,
A2, A4, A5 each apply because $\mathcal{C} \subseteq \mathcal{I}_d^{\text{elig}}$
and the archetype-distinguishability and centroid-deviation bounds hold
agent-uniformly; specifically, A5's bound of 0.014 applies to each $i \in \mathcal{C}$
individually — by A2, $\mathbb{E}[|\delta_i|] \leq \mathbb{E}[\frac{1}{N}\sum_j|\delta_j|]$,
which A5 caps at 0.014 for all sacrifice-eligible agents, so the sub-population centroid
deviation satisfies $\mathbb{E}_t[\frac{1}{|\mathcal{C}|}\sum_{j\in\mathcal{C}}
|p_{j,t}-\bar{p}_t^{\mathcal{C}}|] \leq 0.014$ by the convexity of absolute value
and the per-agent bound) yields:

$$\text{Amb}^{\mathcal{C},\text{SRR}} > \text{Amb}^{\mathcal{C},\text{deviation}}$$

Since $B_{\text{ens}}^{\mathcal{C}} = \overline{B}^{\mathcal{C}} - \text{Amb}^{\mathcal{C}}$
and SRR leaves the per-agent mean Brier $\overline{B}^{\mathcal{C}}$ unchanged at
day $d$ (the archetype change takes effect in future predictions; the term
$\overline{B}^{\mathcal{C}}$ is a sample average over past outcomes), strictly
higher Ambiguity under SRR implies:

$$B_{\text{ens}}^{\mathcal{C},\text{deviation}} \;=\; \overline{B}^{\mathcal{C}} - \text{Amb}^{\mathcal{C},\text{deviation}}
\;\geq\; \overline{B}^{\mathcal{C}} - \text{Amb}^{\mathcal{C},\text{SRR}}
\;=\; B_{\text{ens}}^{\mathcal{C},\text{SRR}}$$

Coalition ensemble Brier is therefore weakly *worse* (or equal in the boundary case)
under deviation for $|\mathcal{C}| \geq 2$. Combined with the $|\mathcal{C}|=1$ case,
Claim 1 holds for all $\mathcal{C} \subseteq \mathcal{I}_d^{\text{elig}}$.

**Claim 2 (Individual Brier of deviating agents does not decrease in expectation).**
Each sacrifice-eligible agent $i \in \mathcal{C}$ satisfies
$\overline{B}_{i,d} \geq \bar{B}_d + \delta_{\text{sac}}$ by definition of
sacrifice-eligibility.  Refusing SRR leaves agent $i$ in the same strategy
archetype that generated this performance deficit.  By Assumption A3, in the
absence of an archetype change, the deficit persists: the agent's expected Brier
over the next $W_{\text{persist}}$ days satisfies
$\mathbb{E}[\overline{B}_{i,d+W}] \geq \bar{B}_d + \delta_{\text{sac}}/2 > \bar{B}_d$.
Therefore refusing SRR does not reduce agent $i$'s individual Brier in expectation.

**Combining Claims 1 and 2.** For a deviating coalition $\mathcal{C}$ to
constitute an improvement over $(\sigma^{\text{SRR}})$, it would need to simultaneously
achieve (i) weakly lower coalition ensemble Brier, and (ii) weakly lower individual
Brier for *all* members of $\mathcal{C}$.  Claim 1 shows condition (i) fails (deviation
weakly *raises* coalition ensemble Brier).  Claim 2 shows condition (ii) also fails
(deviation does not reduce any member's expected individual Brier).  Both conditions
must hold jointly for an improving deviation; since neither holds, no coalition can
profitably deviate from $(\sigma^{\text{SRR}})$.  The profile is a Strong Nash
Equilibrium against sacrifice-refusal deviations. $\square$

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

**Bankroll update.** After all events in $\mathcal{B}_d$ resolve, each agent's virtual
bankroll updates as:

$$W_{i,d} = W_{i,d-1} \cdot \left(1 + \sum_{t \in \mathcal{B}_d} s_i \cdot g_{i,t}\right)$$

where $g_{i,t}$ is the signed net return on event $t$.  The agent bets $s_i \cdot W_{i,d-1}$
on its favoured outcome: $\omega = 1$ if $p_{i,t} > q_t$, $\omega = 0$ if
$p_{i,t} < q_t$, where $q_t$ is the market-implied probability derived from the
published moneyline; if $p_{i,t} = q_t$ no bet is placed.  For a correct bet:

$$g_{i,t} = s_i \cdot \frac{1 - q_t}{q_t} \qquad (\text{decimal odds minus one})$$

For an incorrect bet: $g_{i,t} = -s_i$.  The full vig-adjusted formula,
including the sportsbook's overround correction, is implemented in
`scripts/arena/bankroll.py` and referenced in Appendix D (§C.5).

Each agent receives the island GA oracle's pre-game probability estimate for each event
as a calibration reference in its context block (described in §4.2.1); this reference
does not appear in the stake formula above, which depends solely on $\kappa_i$, $\rho_i$,
and $\kappa_{\min}^{(r_i)}$.
Agents whose rolling Brier persistently exceeds 0.32 (i.e., more than 28% above the
$p = 0.5$ random-Bernoulli baseline of 0.25; derivation in §6.5) receive an additional hard cap $\kappa_i \leq 0.03$ — an
*inverse-calibration probation* applied as a post-formula override,
independent of the pilot Brier formula above (diagnostic criterion and
rationale in §6.5, sub-section "Formula derivation and inverse-calibration
probation criterion").
Note: the archetype minimum floor $\kappa_{\min}^{(r_i)}$ is applied *after* the
probation cap, so for archetypes with $\kappa_{\min}^{(r_i)} > 0.03$ the floor
supersedes the probation ceiling; this is by design — even probation agents
must contribute to the ensemble mean prediction $\bar{p}_t$ at a non-trivial level,
preventing them from vanishing from the ensemble entirely.

**End-of-day broadcast.** At 23:59 UTC, resolved outcomes $\Omega_d$ are
broadcast to all agents. Each agent updates its private history $h_{i,d}$.
SRR eligibility is evaluated using the rolling window of the most recent $W = 7$ days.

**SRR execution.** SRR fires at most once per agent per 14-day window.
The archetype update is applied by writing the new archetype identifier to the
agent's runtime persona store (`data/arena/personas/{agent_id}.json`),
which the LLM gateway (`LBJLincoln26/llm-gateway`) polls on every prediction
request before composing the system prompt.^[The environment variable
`AGENT_PERSONA` seeds this store at Space startup but is not re-read at
request time; updates therefore propagate immediately through the per-request
file read without requiring a HuggingFace Space restart.  This design is
necessary because HF Space environment-variable changes take effect only on
restart, which would introduce a 30–90 s latency inconsistent with the
15-minute prediction window.]

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
