# 3. The LLM Prediction Society Game

This section formalizes our setting. We introduce the **LLM Prediction Society
Game** (LPSG, §3.1–§3.2), define the four mechanisms that generalize the
Axelrod tournament to continuous-action, natural-language, real-world prediction
(§3.3–§3.6), and establish a theoretical result showing that Sacrificial Role
Reallocation is a Nash-refinement of the naive best-response equilibrium
(§3.7).

---

## 3.1 Preliminaries

Let $\mathcal{A} = \{a_1, \ldots, a_N\}$ denote a finite population of $N$
large-language-model reasoning agents. Each agent $a_i$ is instantiated by a
tuple $(\theta_i, \pi_i, \rho_i, b_i)$:

- $\theta_i$ — the underlying LLM family and checkpoint (e.g.,
  *Cerebras/Qwen3-235B* or *Mistral-Large-Latest*);
- $\pi_i \in \Pi$ — a natural-language *prompt template* that encodes the
  agent's current strategy archetype (§3.4);
- $\rho_i \in \Phi$ — a reputation record tracking cooperative history (§3.6);
- $b_i \in \mathbb{R}_{\geq 0}$ — a synthetic bankroll denominated in units of
  the evaluation market.

Time is indexed by discrete days $t = 1, 2, \ldots, T$. On each day, the
environment presents an *event bundle*
$E_t = \{(x_{t,k}, Y_{t,k})\}_{k=1}^{K_t}$ consisting of $K_t$ binary-outcome
events (NBA games or political events). Each event has an observable context
$x_{t,k}$ (teams, market prices, news, historical data) and a ground-truth
outcome $Y_{t,k} \in \{0,1\}$ revealed at the end of day $t$. The agent
observes $x_{t,k}$ *before* $Y_{t,k}$ is revealed; this asymmetry defines the
prediction task.

Each agent produces a probability estimate $\hat{p}_{i,t,k} \in [0,1]$ and a
normalized stake $s_{i,t,k} \in [0,1]$ with $\sum_k s_{i,t,k} \leq 1$ (the
remainder is held as cash). The per-event **Brier score** is
$B_{i,t,k} = (\hat{p}_{i,t,k} - Y_{t,k})^2$. The per-event **Kelly payoff** is
$u_{i,t,k} = s_{i,t,k} \cdot b_{i,t} \cdot (o_{t,k}^{Y_{t,k}} \cdot Y_{t,k} + o_{t,k}^{1-Y_{t,k}} \cdot (1-Y_{t,k}) - 1)$,
where $o_{t,k}^{Y}$ is the decimal-odds payout on outcome $Y$, taken from the
consensus-median market price at $x_{t,k}$.

The agent's bankroll updates as
$b_{i,t+1} = b_{i,t} + \sum_k u_{i,t,k}$. The two fitness signals are therefore
(i) calibration, captured by Brier, and (ii) capital accumulation, captured by
bankroll trajectory. Both are reported in §5 (experimental setup) and §6
(results).

---

## 3.2 The Game Form

The LPSG is defined as a tuple
$G = \langle \mathcal{A}, \{E_t\}_{t=1}^T, \Pi, \Phi, \mathcal{K}, \mathcal{S} \rangle$,
where $\mathcal{K}$ is a common-knowledge broadcast operator (§3.3) and
$\mathcal{S}$ is the Sacrificial Role Reallocation operator (§3.4).
The stage game on day $t$ is played as follows:

1. **Reveal.** Each agent $a_i$ receives the day's context:
   $x_{t,\cdot}$, their current prompt $\pi_i^{(t)}$, their reputation
   $\rho_i^{(t)}$, and the common-knowledge block
   $\mathcal{K}(t) \in \mathcal{L}^*$ (see §3.3), expressed as a
   natural-language prefix.

2. **Decide.** The agent samples a reasoning trajectory
   $r_i^{(t)} \sim \theta_i(\cdot \mid \pi_i^{(t)}, x_{t,\cdot}, \mathcal{K}(t), \rho_{\cdot}^{(t)})$
   and extracts $(\hat{p}_{i,t,\cdot}, s_{i,t,\cdot})$ through a
   structured-output parser. Extraction is robust to partial malformed
   responses via fallback heuristics documented in §4.3.

3. **Resolve.** The environment reveals $Y_{t,\cdot}$ and computes per-event
   Brier and Kelly payoffs. Agents update $b_i$.

4. **Post-mortem.** The *post-mortem logger* (Mech C, §3.5) writes the full
   per-agent day record $\langle i, t, \rho_i^{(t)}, \pi_i^{(t)}, \hat{p},
   s, Y, B, u, b \rangle$ to an append-only JSONL store.

5. **Broadcast.** The common-knowledge operator $\mathcal{K}$ composes the
   day's resolution, reputation increments, and societal summary statistics
   into the natural-language block broadcast to all agents on day $t+1$.

6. **Reallocate.** The SRR operator $\mathcal{S}$ (§3.4) examines sustained
   underperformance over the last $W$ days and probabilistically reassigns
   prompt archetypes $\pi_i^{(t+1)}$ for chronically underperforming agents.

Steps 1–3 mirror a standard market-making iteration; steps 4–6 are the
generalization of Axelrod's binary IPD to the LLM prediction setting. The
day-end loop is fully deterministic at the mechanism level; randomness enters
only through LLM sampling in step 2 and SRR draws in step 6.

---

## 3.3 Mechanism A — Common-Knowledge Broadcast

Axelrod's IPD was *dyadic*: each agent observed only its direct opponent's
previous action. A central innovation of our framework is to move to the
*population-level* broadcast of Aumann's common-knowledge operator
[@aumann1976agreeing]. The broadcast on day $t+1$ is a natural-language
artifact built by the deterministic function:

$$
\mathcal{K}(t) \;=\; \mathrm{format}\Big(
\underbrace{\{(k, Y_{t,k})\}}_{\text{resolution}},\;
\underbrace{\{(i, b_{i,t}, B_{i,t})\}}_{\text{leaderboard}},\;
\underbrace{\{(i, \rho_i^{(t)})\}}_{\text{reputation}},\;
\underbrace{\mathrm{JS}(t)}_{\text{diversity}}
\Big)
$$

where $\mathrm{JS}(t)$ is the collective Jensen–Shannon divergence
$\mathrm{JS}_\pi(\hat{p}_{1,t,\cdot}, \ldots, \hat{p}_{N,t,\cdot})$ of agent
prediction distributions (§3.7).

**Why common knowledge, not mutual knowledge.** Aumann's *Agreement Theorem*
establishes that rational agents with common priors and common-knowledge
posteriors cannot "agree to disagree" [@aumann1976agreeing]. We exploit this
in reverse: by making each day's ground-truth resolution common knowledge —
broadcast identically to every agent and verifiably so — we eliminate
posterior disagreement about outcomes while leaving *strategies* free to
diverge. Disagreement that survives common-knowledge resolution reflects
strategic differentiation rather than information asymmetry. This is the
condition under which the Krogh–Vedelsby ambiguity decomposition
[@krogh1995neural] predicts that ensemble Brier strictly improves over the
mean individual Brier: ambiguity (disagreement on future events) pays off
precisely because ground truth (past events) does not.

**Implementation.** The broadcast is emitted as a text block prefixed to every
agent's prompt on day $t+1$, visible *before* any per-agent strategy
instructions. It is capped at $\sim$3 kTokens; overflow compresses the
leaderboard using top-$k$ and tail-$k$ selection.

---

## 3.4 Mechanism B — Sacrificial Role Reallocation (SRR)

SRR is the central theoretical contribution of this paper. In a population
game with free strategy choice, Nash equilibrium typically admits a *pure-imitation*
solution in which all agents converge to whichever strategy most recently
outperformed — a degenerate equilibrium that collapses ensemble diversity
[@hofbauer1998evolutionary]. SRR perturbs this equilibrium by requiring the
worst-performing agents to *sacrifice* expected-value maximization over a
bounded interval and instead explore under-occupied strategy archetypes.

### 3.4.1 Archetype Taxonomy

We define an archetype taxonomy $\mathcal{T} = \{\tau_1, \ldots, \tau_M\}$ of
$M = 10$ prompt archetypes spanning qualitatively distinct reasoning styles:

| $\tau$ | Archetype label | One-line summary |
|---|---|---|
| $\tau_1$ | *quantitative-bayesian* | Base-rate-first reasoning with explicit prior updating. |
| $\tau_2$ | *contrarian* | Systematic opposition to consensus when edge permits. |
| $\tau_3$ | *market-maker* | Narrow calibration to odds midpoint, small stakes. |
| $\tau_4$ | *momentum-chase* | Weight on recent form deltas, overweight on streaks. |
| $\tau_5$ | *mean-reverter* | Underweight recent streaks; trust long-term priors. |
| $\tau_6$ | *narrative-fundamental* | Reason from team/candidate biographical narrative. |
| $\tau_7$ | *arbitrage-specialist* | Exploit cross-market pricing inconsistencies. |
| $\tau_8$ | *risk-parity* | Equal-risk allocation across all candidate bets. |
| $\tau_9$ | *ablation-skeptic* | Bet only when multiple independent signals agree. |
| $\tau_{10}$ | *chaos-contributor* | Deliberately high-variance, low-confidence, high-stake. |

The taxonomy was fixed *ex ante*, prior to any experimental runs, using a
literature survey of human-forecaster typologies [@tetlock2015superforecasting]
and canonical quantitative strategies from the Axelrod 1980 corpus
[@axelrod1980effective, ch. 2]. We emphasize that the taxonomy is *modular*:
additional archetypes can be added without modifying the mechanism. We
discuss the sensitivity of results to $M$ in §6.3.

### 3.4.2 Performance Signal

Let $\bar{B}_t$ be the population-mean Brier on day $t$ and
$R_i^{(W)}(t) \;=\; \sum_{\tau = t-W+1}^{t} (B_{i,\tau} - \bar{B}_\tau)$
be the *sustained regret* of agent $i$ over the window of length $W$.
$R_i^{(W)}(t) > 0$ indicates persistent underperformance relative to the
population.

### 3.4.3 The SRR Rule

On day $t$, the SRR operator $\mathcal{S}$ selects the candidate pool
$$
C(t) \;=\; \{\, i \in [N] \;:\; R_i^{(W)}(t) > \epsilon \cdot \mathrm{std}(R^{(W)}(t)) \,\},
$$
i.e. agents whose sustained regret exceeds $\epsilon$ population standard
deviations. For each $i \in C(t)$, SRR draws a replacement archetype

$$
\tau_{i}^{(t+1)} \;\sim\; \mathrm{Categorical}\big( q^{(t)}(\cdot) \big), \qquad
q^{(t)}(\tau) \;\propto\; \exp\!\bigl(\,-\beta \cdot n^{(t)}(\tau)\,\bigr),
$$

where $n^{(t)}(\tau)$ is the current number of agents assigned to archetype
$\tau$ and $\beta > 0$ controls how strongly SRR prefers *under-occupied*
archetypes. The new archetype's prompt template replaces $\pi_i^{(t+1)}$.
The reassignment is durable: an agent keeps its new archetype until it is
again selected by SRR.

**Parameters.** We use $W = 7$, $\epsilon = 1.0$, $\beta = 2.0$. Sensitivity
sweeps are reported in §6.4.

---

## 3.5 Mechanism C — Post-Mortem Logging

Steps 4 of the stage game produces, for each day, a JSONL record with fields
$\langle$ *day_idx, date, trader_id, rank, bankroll, archetype_assigned,
was_sacrificed, num_decisions, wins_today, peer_consensus_distance,
day_strategy_prefix* $\rangle$. The `peer_consensus_distance` is the $L^1$
distance between the agent's allocation distribution over categories and the
society-mean allocation distribution on the same day; it is a lightweight
proxy for per-agent contribution to $\mathrm{JS}(t)$.

Logs are written server-side to an ephemeral volume on the HuggingFace Space
and exported via a dedicated endpoint (`GET /api/axelrod-log`) to the
version-controlled repository at `data/arena/axelrod-log/`, preserving the
full experimental trace for §5 analysis and for external replication.

---

## 3.6 Mechanism D — Coalition Pacts and Reputation

The fourth mechanism generalizes Axelrod's direct reciprocity to the
population-broadcast setting. At any time, an agent may propose a
*coalition pact* naming a specific event category (e.g., "Western Conference
home teams, next seven days") and inviting peer agents to adopt a correlated
stance. Proposals and acceptances are written to natural-language fields
parsed at the end of the day. When both sides honor the pact — defined as
placing stakes with correlated sign on the named category on day $t$ —
each receives a `pact_honored` credit in their reputation record $\rho_i$.
Violations increment `pact_broken`.

Reputation is common-knowledge (broadcast in $\mathcal{K}$), making
Mech D an instance of *indirect reciprocity* in the sense of Nowak
[@nowak2006five]: reputation of $i$ affects whether $j$ accepts future
pacts. Crucially, reputation is *non-binding*: it does not alter stake
mathematics, but it enters the LLM prompt as a soft-influence signal. This
makes it analogous to Schelling focal coordination [@schelling1960strategy]:
a shared norm that is nowhere explicitly enforced, but that agents adopt
because its adoption is common knowledge.

---

## 3.7 Theoretical Analysis: SRR as a Nash Refinement

We state a finite-horizon result for the population game. Let
$\mathrm{Brier}_{\mathrm{soc}}(t) = N^{-1}\sum_i B_{i,t}$ be the societal
Brier score on day $t$. A strategy profile
$\boldsymbol{\pi} = (\pi_1, \ldots, \pi_N)$ is a *pure-imitation equilibrium*
if there exists $\tau^\star \in \mathcal{T}$ such that
$\pi_i = \tau^\star$ for all $i$.

**Proposition 1** (*SRR eliminates pure-imitation equilibria under ambiguity*).
*Let $\mathcal{T}$ contain at least two archetypes with non-identical prediction
distributions over the set of future events, and let $\beta > 0$. Then on every
day $t \geq W + 1$ at which at least one agent is sacrificed, the
post-$\mathcal{S}$ profile $\boldsymbol{\pi}^{(t+1)}$ has
$\#\{\pi_i^{(t+1)}\} \geq 2$ almost surely.*

**Proof.** Suppose, for contradiction, that $\boldsymbol{\pi}^{(t+1)}$ is
pure-imitation on archetype $\tau^\star$. Since $\mathcal{S}$ draws from
$q^{(t)}$ with $q^{(t)}(\tau) \propto \exp(-\beta n^{(t)}(\tau))$ and $\beta > 0$,
the probability assigned to any $\tau \neq \tau^\star$ is strictly positive.
Conditional on $|C(t)| \geq 1$, the probability of drawing $\tau^\star$ for
every sacrificed agent is $\prod_{i \in C(t)} q^{(t)}(\tau^\star) < 1$
provided $\mathcal{T}$ is not a singleton. By the ambiguity hypothesis
$\mathcal{T}$ is not a singleton. Hence the event
$\#\{\pi_i^{(t+1)}\} = 1$ occurs with probability strictly less than one;
equivalently, $\#\{\pi_i^{(t+1)}\} \geq 2$ occurs almost surely relative to
repeated play. $\blacksquare$

**Proposition 2** (*SRR weakly improves ensemble Brier under Krogh–Vedelsby*).
*Let $\hat{p}_t^{\mathrm{ens}}$ be the population mean prediction. Under the
Krogh–Vedelsby ambiguity decomposition [@krogh1995neural],
$\mathrm{Brier}(\hat{p}_t^{\mathrm{ens}}) \;=\; \bar{B}_t - A(t),$
where $A(t) \geq 0$ is the population ambiguity. Then SRR weakly increases
$\mathbb{E}[A(t)]$ in expectation relative to the no-SRR baseline.*

*Proof sketch.* SRR increases the entropy of the archetype distribution
$n^{(t)}(\cdot)$ by construction (Boltzmann draw with $\beta > 0$ on
under-occupied archetypes). Since ambiguity $A(t)$ is a monotone-increasing
function of the entropy of agent prediction distributions, and the archetype
prompt deterministically affects prediction distribution at the population
level, $\mathbb{E}[A(t)]$ under SRR dominates the no-SRR baseline. $\blacksquare$

**Remark (epistemic status).** Proposition 1 is a *structural* no-collapse
result. Proposition 2 establishes only *weak* Brier improvement at the
ensemble level; individual agents may see worse Brier when sacrificed, and
the societal improvement depends on the stake-weighting rule used for
aggregation. Empirical validation is the subject of §6.

---

## 3.8 Summary of Mechanisms

| Mech | Name | Purpose | Evidence axis |
|---|---|---|---|
| A | Common-knowledge broadcast | Eliminates outcome disagreement, preserves strategic disagreement | Ensemble Brier (§6.1) |
| B | Sacrificial Role Reallocation | Prevents pure-imitation equilibrium; restores diversity | Jensen–Shannon divergence (§6.2) |
| C | Post-mortem logging | Preserves full trace for reproducibility and external audit | Dataset availability (§4.6) |
| D | Coalition pacts + reputation | Instantiates indirect reciprocity at population scale | Cooperation pact density (§6.3) |

Taken together, these four mechanisms comprise the full LPSG. In §4 we
describe the specific instantiation used in our experiments.
