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

$$\sigma_i : \mathcal{R} \times \mathcal{X} \times \mathcal{H} \;\to\; \bigcup_{m \geq 1} \mathcal{P}\!\left([0,1]^m\right)$$

where $\mathcal{H}$ is the space of agent-private histories and $\mathcal{P}(\cdot)$
denotes the set of Borel probability measures over its argument. The output dimension
$m = |\mathcal{B}_d|$ (the number of events on day $d$) is encoded in the context
observation $x_d \in \mathcal{X}$, so $\sigma_i$ is a family of functions parametrised
by the day's event count; the finite-set notation $\Delta(\mathcal{R})$ is used below
for the discrete archetype simplex. In practice, $\sigma_i$ is implemented by prompting
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

**Relation to the Axelrod IPD.** The LPSG shares the population-dynamics framing
of Axelrod's tournament — fitness-ranked strategy competition in a repeated multi-agent
setting under selection pressure for collective performance — but it does not contain the
classical IPD as a literal degenerate case. In the IPD, the payoff matrix satisfies
$T > R > P > S$ [@axelrod1980effective], creating a bilateral cooperation–defection
tension absent from any proper-scoring-rule game: under the Brier score (or any
strictly proper rule), truthful belief reporting is individually dominant regardless
of peer actions [@gneiting2007strictly], so the defection incentive that drives the
IPD's Nash equilibrium at mutual defection does not arise in the LPSG.
Our Lemma 1 and Proposition 2 therefore require proofs tailored to the
proper-scoring-rule setting, and do not follow from classical IPD cooperation results.
The two frameworks are best understood as *complementary generalisations* of Axelrod's
tournament: the LPSG extends its scope from static automata and matrix payoffs to
reasoning LLM agents and proper-scoring-rule payoffs, while retaining the
population-diversity concern that motivated Axelrod's original enquiry into which
strategy archetypes survive co-evolution. (§2.1 notes two further limiting features of
the original tournament that prevent direct transfer: binary action space and fixed automata.)

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
[@krogh1995neural; @brown2005diversity]:

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

For each event $t$, the per-event $\text{JSD}_t$ is a strictly monotone function of
the per-event $\text{Amb}_t = \frac{1}{N}\sum_i(p_{i,t}-\bar{p}_t)^2$ for Bernoulli
predictions in the operating range $\bar{p}_t \in [0.24, 0.76]$, $\text{Amb}_t \leq 0.04$
(proof: Appendix B.1, via Taylor expansion of $H$ around $\bar{p}_t$; range
pre-registered, formal verification pending Table 4, §5.1).
Averaging over events $t \in \mathcal{B}_d$, increasing the day-level average $D_d$
is therefore equivalent to reducing $B_{\text{ens},d}$ holding $\frac{1}{N}\sum_i B_{i,d}$ fixed.
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
Since $N = 12 < K = 20$, at least $K - N = 8$ archetypes are always vacant regardless of the
current archetype distribution; the prerequisite $\mathcal{V}_d \neq \emptyset$ in Definition 2
is therefore *guaranteed* throughout our experimental regime. The conditional "if
$\mathcal{V}_d \neq \emptyset$" in Definition 2 is retained for notational completeness in the
general-population ($N \geq K$) case.

**SRR rule.**

> **Definition 2 (Sacrificial Role Reallocation).** If agent $i$ is sacrifice-eligible
> at day $d$ and $\mathcal{V}_d \neq \emptyset$:
>
> 1. Draw $r^* \sim \text{Uniform}(\mathcal{V}_d)$.
> 2. Update agent $i$'s archetype: $r_i \leftarrow r^*$.
> 3. Rewrite agent $i$'s system prompt to reflect archetype $r^*$.
> 4. Persist for $W_{\text{persist}} = 14$ days; agent $i$ is ineligible for further SRR events during this window (sacrifice-eligibility is suspended from day $d$ through day $d + W_{\text{persist}} - 1$).
> 5. *Retention test* — executes at the start of the step-6 SRR check on day $d + W_{\text{persist}}$, before fresh sacrifice-eligibility is evaluated for that day: if $\overline{B}_{i,d+W_{\text{persist}}} < \overline{B}_{i,d} - \epsilon_{\text{keep}}$, retain $r^*$; else revert to $r_i^{(\text{pre})}$, the archetype held by agent $i$ immediately before this SRR event. Fresh sacrifice-eligibility is then evaluated under the archetype in force after the retention test resolves. (Note: $r_i^{(\text{pre})}$ may itself differ from the agent's initial archetype if multiple SRR events have occurred; each event stores its own pre-event archetype for potential reversal.)^[An alternative design stores the agent's *initial* archetype $r_i^{(0)}$ as the permanent reversal target ("home base"), rather than the immediately-prior archetype. This prevents multi-SRR drift — successive failed reallocations cannot move an agent progressively further from its original reasoning disposition — but it discards any beneficial intermediate transitions that would otherwise be retained by the immediately-prior design. Because the 14-day persistence window ($W_{\text{persist}}$) limits the rate of SRR events to at most $\lfloor D / 14 \rfloor \approx 12$ events per agent over a 175-day season, multi-SRR chains deeper than two hops are rare in practice. A sensitivity analysis comparing the two reversal targets (immediately-prior vs.\ home-base) is reported in §C.2.3.]

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
take differentiated positions [@zhang2026arena].^[*Assumption sequencing note.*
Assumptions A1–A4 are used in Lemma 1. Assumptions A5 (no spontaneous recovery)
and A6 (vacant-archetype expected Brier) are not needed until Proposition 2 and
are therefore introduced after the Lemma 1 proof to preserve narrative flow.]

**Assumption A3 (Archetype-shift event-independence).** The expected absolute
prediction shift induced by drawing a vacant archetype uniformly at random is
approximately constant across event contexts:

$$\sup_{x_t \in \mathcal{X}}\;\mathbb{E}_{r^* \sim \text{Unif}(\mathcal{V}_d)}\!\left[|\Delta p(r^*\!, x_t)|\right]
\;\leq\; \mathbb{E}[|\Delta p|]\;\cdot\;(1 + \eta_{\text{A3}})$$

for a small slack $\eta_{\text{A3}} \geq 0$.
This holds when archetype-induced prediction shifts do not concentrate on a small
subset of event types — a condition verified if A1 ($\epsilon_{\text{arch}} \geq 0.037$)
holds uniformly across the event distribution rather than only in aggregate.
A3 is empirically testable from the pilot backtest by stratifying
$\hat{\epsilon}_{\text{arch}}$ by event type; we report this stratification in
Table B.2 (pending pilot data).

**Assumption A4 (Pilot Brier bound).** The population-average expected absolute
centroid deviation satisfies:

$$\mathbb{E}_t\!\left[\frac{1}{N}\sum_{j=1}^N |p_{j,t} - \bar{p}_t|\right] \;\leq\; 0.014$$

This bound is **pre-registered** and will be verified against the 2024–25 pilot season
holdout backtest (§5.1, Table 4; verification pending pilot run completion).
The value 0.014 is a design-stage estimate from informal pilot inspection;
the formal verification must precede the start of Conditions B–E.
A4 is not implied by A1–A3 alone; it provides the numerical threshold required
for the Case 2 arithmetic in the Lemma 1 proof. Should the empirical pilot value
exceed 0.014, the lemma still holds provided
$\mathbb{E}[|\delta_i|] < \frac{(N-1)}{2N}\epsilon_{\text{arch}} = \frac{11}{24}\times 0.037 \approx 0.017$;
values in $(0.014, 0.017)$ tighten the numerical margin but do not overturn the result.
Should the empirical value exceed 0.017, the proof requires revision (the Case 2 inequality
reverses); archetype revision would be triggered before the main conditions run.

> **Lemma 1 (SRR increases expected diversity).** Under A1, A2, A3, and A4, an SRR event
> at day $d$ strictly increases $\mathbb{E}[D_{d+1}]$.

*Proof.* Let agent $i$ be sacrifice-eligible, $\Delta p = p_{i,t}' - p_{i,t}$,
and $\delta_i = p_{i,t} - \bar{p}_t$ (deviation from the **full-population** centroid
$\bar{p}_t = \frac{1}{N}\sum_j p_{j,t}$).
*Centroid note:* $\delta_i$ here is always the full-population deviation, not the
sub-population deviation $p_{i,t} - \bar{p}_t^{\mathcal{C}}$ used in Proposition 2's
Claim 1 Ambiguity decomposition.  The two quantities are distinct: the vacancy set
$\mathcal{V}_d$ and the archetype shift $\Delta p$ are defined with respect to the full
population, so the Lemma 1 arithmetic (including the Case 2 bound) consistently uses
$\bar{p}_t$ (full-population) throughout — even when the lemma is applied to the
coalition sub-population $\mathcal{C}$ in Proposition 2.
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

$$\Delta\text{Amb}_t \;\geq\; \frac{(\Delta p)^2(N-1)}{N^2} \;\geq\; 0$$

The second inequality holds in every realization since $(\Delta p)^2 \geq 0$ always.
Case 1 therefore contributes a non-negative term to $\mathbb{E}[\Delta\text{Amb}_t]$.
(Note: the step $\geq \frac{\epsilon_{\text{arch}}^2(N-1)}{N^2} > 0$ would require
$|\Delta p| \geq \epsilon_{\text{arch}}$ per-realization, which A1 guarantees only
in expectation; the per-realization lower bound is $0$, which is all that is needed here.
The strict positivity $\mathbb{E}[\Delta\text{Amb}_t] > 0$ over all events is established
by the combined bound below, using $\mathbb{E}[(\Delta p)^2] \geq \epsilon_{\text{arch}}^2$.)

*Case 2* ($\delta_i\Delta p < 0$, i.e.\ the new archetype moves the prediction toward
the centroid):

$$\Delta\text{Amb}_t = |\Delta p|\!\left[\frac{|\Delta p|(N-1)}{N^2} - \frac{2|\delta_i|}{N}\right]$$

This is positive whenever $|\delta_i| < \frac{|\Delta p|(N-1)}{2N}$.
By A2, $\mathbb{E}[|\delta_i|] \leq \mathbb{E}\!\left[\frac{1}{N}\sum_j |p_{j,t}-\bar{p}_t|\right]$ —
the expected centroid deviation of a sacrifice-eligible agent is bounded above by the
population-average expected absolute deviation.  By Assumption A4,
$\mathbb{E}_t[\frac{1}{N}\sum_j|p_{j,t}-\bar{p}_t|] \leq 0.014$, yielding
$\mathbb{E}[|\delta_i|] \leq 0.014$ as the quantitative bound used below
(A2 provides the structural direction; A4 furnishes the pilot-verified numerical threshold).
The conclusion $\mathbb{E}[\Delta\text{Amb}_t] > 0$ follows by taking a lower bound on the cross-term.
Since $\delta_i\Delta p \geq -|\delta_i||\Delta p|$ always (with equality only when the product is negative),
the worst-case sign of the cross-term yields:

$$\mathbb{E}[\Delta\text{Amb}_t] \;\geq\; \frac{N-1}{N^2}\mathbb{E}[(\Delta p)^2] - \frac{2}{N}\mathbb{E}[|\delta_i||\Delta p|]$$

It is sufficient to show this lower bound is positive.
We bound the cross-term via Assumption A3.  Conditional on event context $x_t$,
the archetype draw $r^* \sim \text{Uniform}(\mathcal{V}_d)$ is independent of
the pre-SRR deviation $\delta_i(x_t)$ (which is determined before the draw).
Therefore:

$$\mathbb{E}[|\delta_i||\Delta p|] = \mathbb{E}_{x_t}\!\bigl[|\delta_i(x_t)|\cdot\mathbb{E}_{r^*}\!\bigl[|\Delta p(r^*\!,x_t)|\bigr]\bigr]
\;\leq\; \mathbb{E}[|\delta_i|]\cdot\sup_{x_t}\mathbb{E}_{r^*}[|\Delta p(r^*\!,x_t)|]$$

Under A3, $\sup_{x_t}\mathbb{E}_{r^*}[|\Delta p(r^*, x_t)|] \leq \mathbb{E}[|\Delta p|]\cdot(1+\eta_{\text{A3}})$,
yielding the *exact* cross-term bound (no approximation):
$\mathbb{E}[|\delta_i||\Delta p|] \leq (1+\eta_{\text{A3}})\,\mathbb{E}[|\delta_i|]\cdot\mathbb{E}[|\Delta p|]$.
By Jensen's inequality applied to the convex function $f(x) = x^2$,
$\mathbb{E}[(\Delta p)^2] \geq (\mathbb{E}[|\Delta p|])^2$; factoring $\mathbb{E}[|\Delta p|]$
out of the lower bound then yields the exact sufficient condition:

$$\frac{N-1}{N}\mathbb{E}[|\Delta p|] > 2(1+\eta_{\text{A3}})\,\mathbb{E}[|\delta_i|]$$

Since $\mathbb{E}[|\Delta p|] \geq \epsilon_{\text{arch}} = 0.037$ (A1) and
$\mathbb{E}[|\delta_i|] \leq 0.014$ (A4), the LHS $\geq \frac{11}{12}\times 0.037 = 0.03392$
and the RHS $= 0.028(1+\eta_{\text{A3}})$. The inequality holds iff
$\eta_{\text{A3}} < 0.03392/0.028 - 1 = 0.211$; pilot data must confirm
$\eta_{\text{A3}} < 0.211$ before Conditions B–E (pre-submission checklist item 12,
bound tightened from earlier stated 0.22). $\checkmark$

Combining Cases 1 and 2: taking the expectation over the joint distribution of
$(r^*, \delta_i)$ — which mixes Case 1 realisations ($\delta_i\Delta p \geq 0$,
each contributing a non-negative per-realisation term) and Case 2 realisations
($\delta_i\Delta p < 0$, whose negative cross-term is bounded by the combined
expression above) — the established lower bound yields $\mathbb{E}[\Delta\text{Amb}_t] > 0$.

Appendix B.1 establishes a *pointwise derivative lower bound* on the JSD–Ambiguity
relationship throughout the pre-registered operating range
$\bar{p}_t \in [0.24, 0.76]$, $\text{Amb}_t \leq 0.04$ (formal verification pending Table 4, §5.1):

$$\frac{\partial\,\text{JSD}_t}{\partial\,\text{Amb}_t}\bigg|_{\bar{p}_t} \;\geq\; 0.495 \;>\; 0$$

This bound yields a *pathwise* inequality that holds for *every* realisation of the
archetype draw $r^*$, regardless of the sign of $\Delta\text{Amb}_t$:

$$\Delta\text{JSD}_t \;\geq\; 0.495\;\Delta\text{Amb}_t$$

because $\text{JSD}_t$ moves from $\text{Amb}_t$ to $\text{Amb}_t + \Delta\text{Amb}_t$ along
a path where $\frac{\partial\,\text{JSD}}{\partial s} \geq 0.495$ everywhere in the
operating range.^[This invocation of B.1 is stronger than pointwise monotonicity alone:
monotonicity gives $\text{JSD}(\text{Amb}') > \text{JSD}(\text{Amb})$ when $\text{Amb}' > \text{Amb}$,
but cannot bound $\mathbb{E}[\text{JSD}(\text{Amb}')]$ from a bound on $\mathbb{E}[\text{Amb}']$
without convexity of JSD in Amb (which holds only locally). The derivative lower bound,
by contrast, yields $\Delta\text{JSD}_t \geq 0.495\,\Delta\text{Amb}_t$ pathwise — valid
for all realisations, including those where $\Delta\text{Amb}_t < 0$.]
Taking expectations over the archetype draw:

$$\mathbb{E}[\Delta\text{JSD}_t] \;\geq\; 0.495\;\mathbb{E}[\Delta\text{Amb}_t] \;>\; 0$$

Averaging linearly over events $t \in \mathcal{B}_d$ gives $\mathbb{E}[\Delta D_{d+1}] > 0$. $\square$

**Assumption A5 (No spontaneous recovery).** In the absence of an archetype change,
a sacrifice-eligible agent's expected Brier over the next $W_{\text{persist}}$ days
is at least $\bar{B}_d + \delta_{\text{sac}}/2$ (partial persistence of the performance
deficit). This assumption excludes pure mean-reversion scenarios and is empirically
testable via the Sham-SRR control (§4.3).

**Assumption A6 (Vacant-archetype expected Brier).** For a sacrifice-eligible agent
$i$ at day $d$ drawing archetype $r^* \sim \text{Uniform}(\mathcal{V}_d)$, the
expected individual Brier satisfies:

$$\mathbb{E}_{r^*}\!\left[B_{i,d+1}^{\text{SRR}}\right] \;\leq\; \bar{B}_d$$

Vacant archetypes are those not currently occupied in the population; because the
sacrifice-eligible agent's current archetype has been demonstrated to underperform
($\overline{B}_{i,d} \geq \bar{B}_d + \delta_{\text{sac}}$), switching to an as-yet-untested
strategy is, in expectation, no worse than the current society mean. A6 is pre-registered
and empirically testable via the within-agent matched-pairs analysis (§4.3, §5.4); if
violated for a specific agent–archetype pair, the retention test (Definition 2, step 5)
reverts the assignment, bounding practical impact.

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
*Timing note:* SRR fires at step 6 — after day-$d$ predictions (step 2) and
scoring (step 4) — so day-$d$ Brier is identical under both the SRR and deviation
conditions.  The non-trivial comparison concerns expected ensemble Brier from
day $d+1$ onwards, where the archetype assignments from SRR take effect.
Apply the Brier ambiguity decomposition to the coalition sub-ensemble $\mathcal{C}$
at day $d+1$:

$$B_{\text{ens},d+1}^{\mathcal{C}} = \frac{1}{|\mathcal{C}|}\sum_{i\in\mathcal{C}} B_{i,d+1} - \text{Amb}_{d+1}^{\mathcal{C}},
\quad \text{Amb}_{d+1}^{\mathcal{C}} = \frac{1}{|\mathcal{B}_{d+1}|}\sum_{t}\frac{1}{|\mathcal{C}|}\sum_{i\in\mathcal{C}}(p_{i,t} - \bar{p}_t^{\mathcal{C}})^2$$

*Case $|\mathcal{C}|=1$:* With a single agent, $\text{Amb}_{d+1}^{\mathcal{C}} \equiv 0$ identically.
The decomposition yields $B_{\text{ens},d+1}^{\mathcal{C}} = B_{i,d+1}$, so ensemble and individual
Brier coincide; any claim about ensemble-Brier improvement requires individual-Brier
improvement, which is addressed in Claim 2 below.

*Case $|\mathcal{C}|\geq 2$:* We bound both terms of the decomposition at day $d+1$.

*Ambiguity term.* A coalition refusing SRR forgoes the within-coalition
Ambiguity increase that the mechanism provides.  Under SRR, eligible agents in
$\mathcal{C}$ draw archetype assignments from $\mathcal{V}_d$, differentiating their
day-$(d+1)$ predictions from one another and increasing $\text{Amb}_{d+1}^{\mathcal{C}}$.  Under
deviation, coalition members retain their current archetypes, so
$\text{Amb}_{d+1}^{\mathcal{C},\text{deviation}} = \text{Amb}_{d+1}^{\mathcal{C},\text{pre}}$.
Applying the Lemma 1 argument to the sub-population $\mathcal{C}$ (Assumptions A1,
A2, A3, A4 each apply because $\mathcal{C} \subseteq \mathcal{I}_d^{\text{elig}}$
and the archetype-distinguishability and centroid-deviation bounds hold
agent-uniformly; specifically, A4's bound of 0.014 applies to each $i \in \mathcal{C}$
individually — by A2, $\mathbb{E}[|\delta_i|] \leq \mathbb{E}[\frac{1}{N}\sum_j|\delta_j|]$,
which A4 caps at 0.014 for all sacrifice-eligible agents, so the sub-population centroid
deviation satisfies $\mathbb{E}_t[\frac{1}{|\mathcal{C}|}\sum_{j\in\mathcal{C}}
|p_{j,t}-\bar{p}_t^{\mathcal{C}}|] \leq 0.014$ by the convexity of absolute value
and the per-agent bound) yields:

$$\mathbb{E}\!\left[\text{Amb}_{d+1}^{\mathcal{C},\text{SRR}}\right] > \mathbb{E}\!\left[\text{Amb}_{d+1}^{\mathcal{C},\text{deviation}}\right]$$

*Mean individual Brier term.* At day $d+1$, individual Brier depends on day-$(d+1)$
predictions, which are generated from the archetype in force after SRR.  By Claim 2
(invoked here via forward reference; see the proof ordering note below):
deviation keeps every eligible agent in the same archetype that produced above-mean
Brier (A5: the performance deficit persists), so
$\mathbb{E}[\overline{B}_{d+1}^{\mathcal{C},\text{deviation}}] \geq \bar{B}_d + \delta_{\text{sac}}/2 > \bar{B}_d$.
Under SRR, each agent $i \in \mathcal{C}$ independently draws a new archetype
$r^*_i \sim \text{Uniform}(\mathcal{V}_d)$ (with $\mathcal{V}_d$ updated sequentially
per Definition 2, §3.4); by Assumption A6 applied to each $i \in \mathcal{C}$,
$\mathbb{E}[B_{i,d+1}^{\text{SRR}}] \leq \bar{B}_d$ for every $i \in \mathcal{C}$.
Since $\bar{B}_d < \bar{B}_d + \delta_{\text{sac}}/2 \leq \mathbb{E}[\overline{B}_{d+1}^{\mathcal{C},\text{deviation}}]$,
every SRR coalition member's expected individual Brier strictly undercuts the
corresponding deviation agent's.
Therefore:

$$\mathbb{E}\!\left[\overline{B}_{d+1}^{\mathcal{C},\text{deviation}}\right] \;\geq\;
\mathbb{E}\!\left[\overline{B}_{d+1}^{\mathcal{C},\text{SRR}}\right]$$

*Combining at day $d+1$.* Applying $B_{\text{ens},d+1}^{\mathcal{C}} = \overline{B}_{d+1}^{\mathcal{C}} - \text{Amb}_{d+1}^{\mathcal{C}}$:

$$\mathbb{E}\!\left[B_{\text{ens},d+1}^{\mathcal{C},\text{deviation}}\right] \;=\;
\mathbb{E}\!\left[\overline{B}_{d+1}^{\mathcal{C},\text{deviation}}\right] -
\mathbb{E}\!\left[\text{Amb}_{d+1}^{\mathcal{C},\text{deviation}}\right]
\;\geq\;
\mathbb{E}\!\left[\overline{B}_{d+1}^{\mathcal{C},\text{SRR}}\right] -
\mathbb{E}\!\left[\text{Amb}_{d+1}^{\mathcal{C},\text{SRR}}\right]
\;=\; \mathbb{E}\!\left[B_{\text{ens},d+1}^{\mathcal{C},\text{SRR}}\right]$$

Coalition expected ensemble Brier at day $d+1$ is therefore weakly *worse* under
deviation for $|\mathcal{C}| \geq 2$. Combined with the $|\mathcal{C}|=1$ case,
Claim 1 holds for all $\mathcal{C} \subseteq \mathcal{I}_d^{\text{elig}}$.

*(Proof ordering note: Claim 2 is presented after Claim 1 for intuitive flow —
ensemble before individual — but the mean-individual-Brier bound above logically
invokes Claim 2. The argument is not circular: the Claim 2 result depends only on
A5 and the sacrifice-eligibility definition, which are independent of Claim 1.)*

**Claim 2 (Individual Brier of deviating agents does not decrease in expectation).**
Each sacrifice-eligible agent $i \in \mathcal{C}$ satisfies
$\overline{B}_{i,d} \geq \bar{B}_d + \delta_{\text{sac}}$ by definition of
sacrifice-eligibility.  Refusing SRR leaves agent $i$ in the same strategy
archetype that generated this performance deficit.  By Assumption A5, in the
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
(Figure 1; `LBJLincoln26/nba-llm-trading-floor`).

**Morning council (09:00 ET, Eastern Time; UTC−5/−4 seasonal).** A *moderator* agent circulates a
structured morning brief: yesterday's outcomes, current bankroll standings,
and any flagged anomalies. All 12 NBA agents and 10 political agents receive
this brief as a shared prefix before generating independent predictions.
The moderator role rotates weekly (Axelrod-style round-robin) **within each
domain separately**: the 12-agent NBA cohort (T1–T12) rotates independently of
the 10-agent political cohort (T1–T10), both sequences beginning with T1 (Qwen 3
235B-A22B) in Week 1. This per-domain design ensures that T12 (selfhost-qwen4b,
Qwen 3 235B-A22B as rerouted; §4.1 Table 3 note$^\dagger$) never moderates a political morning council for which
it generates no predictions — preventing an architecturally inconsistent brief
produced by a model outside the political prediction cohort. For the NBA council,
moderating capacity spans 235B (T1, T2, and T12 as rerouted), 120B (T11),
and 8B (T3); Mistral T6–T10 and Google Gemini sizes are undisclosed
by provider (see §4.1). For the political council, moderating capacity spans T1–T10 (235B
down to the smallest Mistral commercial variant; sizes undisclosed). This is a
minor confound: all agents receive an identical structured morning brief template
regardless of moderator identity, so the confound is bounded to the quality of
free-text synthesis in the brief body.

**Prediction window.** Each agent generates predictions independently
and asynchronously over a 15-minute window. Predictions are sealed;
no agent can observe another's current-day output until the end-of-day broadcast.

**Bankroll and Kelly allocation.** Each agent maintains a virtual bankroll
initialised at \$100,000 USD-equivalent. Stake sizing is governed by three
distinct parameters: (a) the **Kelly cap** $\kappa_i = \max(0.01,\, 0.30 -
\overline{B}_i^{\text{pilot}} \times 0.50)$, a Brier-derived per-agent ceiling on the
stake fraction^[The formula's mathematical range is $[0.01, 0.30]$ (maximum
at $\overline{B}_i^{\text{pilot}} = 0$); the empirical operating range is $[0.01, 0.20]$ given
our observed pilot Brier $\overline{B}_i^{\text{pilot}} \geq 0.20$. Derivation and inverse-calibration
probation criterion in §6.5.], where $\overline{B}_i^{\text{pilot}}$ is the agent's mean Brier
over the final $W_\kappa = 28$ days of the held-out 2024–25 pilot season (see Table 2 for
$W_\kappa$) — a *static pre-season constant*, fixed before the 2025–26 season begins and not
updated in-season. Note: $\overline{B}_i^{\text{pilot}}$ is distinct from the live rolling Brier
$\overline{B}_{i,d}$ (window $W = 7$; §3.1, §3.4), which drives sacrifice-eligibility evaluation;
(b) the **personality risk weight** $\rho_i \in (0, 1]$, an agent-specific
scalar that scales realised stake between the archetype floor and the Kelly
ceiling (values in Table 3, §4.1); and (c) the **archetype minimum floor**
$\kappa_{\min}^{(r_i)}$, an archetype-level stake floor that prevents
SRR reassignment from silencing an agent when $\kappa_i$ is temporarily
low (values in Table A.1, Appendix A.3; range $[0.01, 0.08]$).

The **realised stake fraction** on day $d$ is:

$$s_i = \max\!\left(\kappa_{\min}^{(r_i)},\; \rho_i \cdot \kappa_i\right)$$

**Bankroll update.** After all events in $\mathcal{B}_d$ resolve, each agent's virtual
bankroll $V_{i,d}$ (notation: $V$ for virtual value; distinct from the patience
window scalar $W$ defined in §3.4) updates as:

$$V_{i,d} = \begin{cases}
V_{i,d-1} \cdot \left(1 + \dfrac{s_i}{|\mathcal{B}_d^+|}\displaystyle\sum_{t \in \mathcal{B}_d^+} g_{i,t}\right) & \text{if } |\mathcal{B}_d^+| \geq 1 \\[8pt]
V_{i,d-1} & \text{if } |\mathcal{B}_d^+| = 0
\end{cases}$$

The $|\mathcal{B}_d^+| = 0$ case (agent's predictions match market odds on every event) leaves the bankroll unchanged; the sum is empty and no stake is committed.
$\mathcal{B}_d^+ = \{t \in \mathcal{B}_d : p_{i,t} \neq q_t\}$ is the subset of
day-$d$ events on which the agent places a bet, and $g_{i,t}$ is the signed net return
per unit staked on event $t$.  Here $s_i$ is the agent's *daily budget fraction*:
the agent allocates a total stake of $s_i \cdot V_{i,d-1}$ across all bet-placing events,
with per-event allocation $\frac{s_i}{|\mathcal{B}_d^+|} \cdot V_{i,d-1}$.
(This normalization bounds total daily exposure at $s_i \cdot V_{i,d-1}$ regardless
of game count, preventing negative bankrolls even on days with $|\mathcal{B}_d| = 15$
games. Without it, a per-event stake of $s_i$ on each of 10 games at $s_i = 0.14$
would yield total exposure 140\% of bankroll — producing a negative balance if all bets lost.)
The agent bets on outcome $\omega = 1$ if $p_{i,t} > q_t$, on $\omega = 0$ if
$p_{i,t} < q_t$, where $q_t$ is the market-implied probability from the published
moneyline; if $p_{i,t} = q_t$ no bet is placed ($t \notin \mathcal{B}_d^+$).
The signed net return is:

$$g_{i,t} = \begin{cases}
\dfrac{1 - q_t}{q_t} & \text{correct bet on outcome } \omega=1 \;(p_{i,t} > q_t) \\[6pt]
\dfrac{q_t}{1 - q_t} & \text{correct bet on outcome } \omega=0 \;(p_{i,t} < q_t) \\[6pt]
-1 & \text{incorrect bet (either direction)} \\[6pt]
0 & \text{no bet placed} \;(p_{i,t} = q_t, \; t \notin \mathcal{B}_d^+)
\end{cases}$$

The first line is decimal odds minus 1 for a home-win bet; the second is decimal
odds minus 1 for an away-win bet. The two correct-bet returns are not generally
equal: when $q_t = 0.6$ (a 60\% market favourite), a correct away-bet returns
$0.6/0.4 = 1.5$ per unit staked versus $0.4/0.6 \approx 0.67$ for a correct
home-bet, reflecting the higher implied difficulty of the contrarian position.
For an incorrect bet: $g_{i,t} = -1$ (unit loss on the per-event allocation $\frac{s_i}{|\mathcal{B}_d^+|} V_{i,d-1}$).  The full vig-adjusted formula,
including the sportsbook's overround correction, is implemented in
`LBJLincoln26/mon-ipad`, `scripts/arena/bankroll.py`, and documented in §C.5.

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
supersedes the probation ceiling; this is by design — even probation agents must
place financially meaningful bets, preventing them from becoming pure
zero-cost observers who predict but never stake.^[The floor does *not* affect
the equal-weighted ensemble mean prediction $\bar{p}_t = \frac{1}{N}\sum_i p_{i,t}$
(§3.3), which is independent of stake fractions. A probation agent contributes its
prediction $p_{i,t}$ to $\bar{p}_t$ with weight $1/N$ regardless of whether
$s_i = \kappa_{\min}$ or $s_i = 0$. The floor's function is financial,
not predictive: it ensures the agent maintains minimum exposure in the betting
pool, so that the Kelly bankroll-update dynamics remain meaningful and the
agent cannot costlessly free-ride on the ensemble's collective accuracy.]

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
| $V_0$ | Initial virtual bankroll per agent | \$100,000 |
| $\kappa_i$ | Agent Kelly cap (pilot Brier-derived, static) | $\max(0.01,\; 0.30 - 0.50\overline{B}_i^{\text{pilot}})$; empirical range $[0.01, 0.20]$ (§3.6) |
| $W_\kappa$ | Pilot rolling window for Kelly cap (days) | 28 |
| $\delta_{\text{sac}}$ | Sacrifice threshold (Brier above mean) | 0.02 |
| $W$ | Patience window / live rolling Brier window (days) | 7 |
| $W_{\text{persist}}$ | Reallocation persistence (days) | 14 |
| $\tau_{\text{vac}}$ | Vacancy threshold | $1/(2K) = 0.025$ |
| $\rho_i$ | Personality risk weight (agent-level) | $[0.35, 0.70]$ (actual per Table 3; design floor: 0.30) |
| $\kappa_{\min}^{(r)}$ | Archetype minimum stake floor | $[0.01, 0.08]$ (Table A.1) |
| $\epsilon_{\text{keep}}$ | Retain threshold (Brier improvement) | 0.005 |
| $\epsilon_{\text{arch}}$ | Archetype distinguishability lower bound | 0.037 (empirical) |

*Table 2: LPSG hyperparameters. Values for $\delta_{\text{sac}}$, $W$, and $\tau_{\text{vac}}$ were
selected on a held-out 2024–25 season pilot; see Appendix C.2 for sensitivity analysis.
Notation note: $\overline{B}_i^{\text{pilot}}$ (Kelly cap) is a static pre-season constant
computed over a $W_\kappa = 28$-day pilot window; distinct from $\overline{B}_{i,d}$
(live rolling Brier, $W = 7$ days), which drives sacrifice-eligibility evaluation (§3.4).*

---

> **Note on causal identification.** The SRR mechanism introduces a
> selection bias: agents that undergo SRR are definitionally those
> with the worst recent performance. Any subsequent Brier improvement
> could reflect mean-reversion rather than the archetype change.
> We address this via three controls: (1) an SRR *sham* condition
> in which eligible agents receive a new archetype label but an
> *identical* system prompt (testing whether the label change alone
> drives effects); (2) a *free-rider* ablation in which, on days that
> any agent would be sacrifice-eligible under Condition A, a randomly
> selected *non-eligible* agent (at or below the society mean Brier) is
> instead reallocated — testing whether the performance-based *targeting*
> of SRR is essential, rather than reallocation per se (full definition in
> §4.3); and (3) a matched pairs analysis comparing each SRR agent to a
> non-eligible agent with the same pre-intervention Brier trajectory.
> All three controls are described in §4.3 and results in §5.3.
