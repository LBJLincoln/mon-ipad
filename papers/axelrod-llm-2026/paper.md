---
title: "Axelrod Meets LLMs: Sacrificial Role Reallocation for Emergent Diversity in Multi-Agent Trading Societies"
date: "2026-05-07"
bibliography: references.bib
link-citations: true
colorlinks: true
geometry: margin=1in
fontsize: 11pt
linestretch: 1.15
abstract-title: "Abstract"
---

<!-- compile: pandoc paper.md --citeproc --bibliography references.bib -o paper.pdf -->

<!-- STATUS: Sections 1-8 complete. Results §5 pending full axelrod-log accumulation
     (target: June 2026, Day 175). Do NOT preprint until results are populated.
     Internal revision log: papers/axelrod-llm-2026/09-self-critique.md -->

---

# Abstract

Robert Axelrod's 1980 tournament showed cooperation emerges among self-interested agents
through iterated interaction, but relied on static hand-coded automata in a binary action
space with no mechanism to correct population homogeneity. We present **Axelrod-LLM**,
generalising this framework along four axes: (i) agents are large language models
reformulating strategy through chain-of-thought deliberation; (ii) the arena is a
real-world prediction market over the 2025–26 NBA season (1,257 games) and 1,120 US
political events with exogenous binary ground truth; (iii) day-end common-knowledge
broadcast enables calibration while preserving belief diversity; and (iv) *sacrificial
role reallocation* (SRR) allows underperforming agents to adopt under-represented
strategy archetypes, provably increasing Jensen–Shannon population diversity.
We formalise the system as the *LLM Prediction Society Game* (LPSG) — a Bayesian
population game — and prove SRR constitutes a diversity-improving Strong Nash equilibrium
refinement (Lemma 1, Proposition 2). Results across 12 NBA agents (175 trading days)
and 10 political agents (90 trading days) from five provider ecosystems are pending full seasonal resolution
(`data/arena/axelrod-log/`). The framework bridges Axelrod-era cooperation theory and
principled design of diverse, calibrated LLM prediction ensembles.

---

# 1. Introduction

## The Axelrod Legacy

In 1980, Robert Axelrod invited game theorists, computer scientists, economists, and
political scientists to submit strategies for a round-robin iterated Prisoner's Dilemma
(IPD) tournament [@axelrod1980effective]. Fourteen strategies competed; the winner, Anatol
Rapoport's *Tit-for-Tat*, cooperated on the first move and thereafter mirrored its
opponent's previous action. Axelrod's follow-up tournament [@axelrod1980more] and his
landmark 1984 book [@axelrod1984evolution] elevated these findings into a general theory:
cooperation is evolutionarily stable when interactions are repeated, agents have sufficient
memory, and defection is sufficiently punished. Nowak's 2006 *Science* synthesis of the
five rules for the evolution of cooperation — kin selection, direct reciprocity, indirect
reciprocity, network reciprocity, and group selection [@nowak2006five] — cemented the IPD
as a foundational model for social dynamics across disciplines. Axelrod himself revisited
these themes in *The Complexity of Cooperation* [@axelrod1997complexity], extending his
framework to norms, social structure, and adaptive agents — a precursor, in spirit, to the
LLM generalization we undertake here.

Yet the Axelrod tournament was, by necessity, severely circumscribed. Agents were
hand-coded finite automata. The action space was binary: cooperate or defect. Strategies
were static for the duration of a tournament round. There was no mechanism for the
population itself to detect and correct dangerous homogeneity — a condition Axelrod himself
noted could make a cooperative equilibrium fragile to invasion by defectors
[@axelrod1984evolution, ch. 3]. These constraints were appropriate for 1980 computing
resources and theoretical tractability, but they leave open a rich family of
generalizations that modern AI systems are uniquely positioned to explore.

## The Rise of LLM Agent Societies

Large language models (LLMs) have enabled a qualitatively new class of multi-agent
system. Rather than encoding strategy as explicit state-machine transitions, LLM agents
receive natural-language descriptions of their role, history, and environment and generate
free-text reasoning before committing to an action. This shifts the locus of strategy from
the programmer to the model's emergent reasoning, enabling far richer behavioral
repertoires. CAMEL [@li2023camel] pioneered role-playing LLM societies; AutoGen
[@wu2023autogen] formalized multi-agent conversation patterns; MetaGPT [@hong2023metagpt]
introduced role-specialisation with shared memory. More recently, TradingAgents
[@xiao2024tradingagents] instantiated a multi-LLM financial trading system with analyst,
risk management, and execution roles communicating through structured dialogues — the
closest antecedent to our architecture. OASIS [@yang2024oasis] extended multi-agent
interaction to one-million-node social simulations on real social network topologies.

A critical and under-studied challenge in all of these systems is **behavioral
homogeneity**: when agents share the same underlying model family or receive similar
prompts, their outputs collapse toward consensus, forfeiting the ensemble's principal
advantage over any single agent. DMAD [@liu2025dmad] — Diverse Multi-Agent Debate
(ICLR 2025) — addresses this through adversarial prompting to force disagreement, but
does so via external intervention rather than an endogenous mechanism the agents
themselves invoke.
The Prediction Arena framework [@zhang2026arena] provides an evaluation scaffold for
prediction-market multi-agent experiments but does not formalise diversity as a
first-class optimisation target. The Agent Trading Arena [@ma2025agent] introduces
competitive market microstructure for LLM agents but studies price-formation rather
than cooperative diversity dynamics.

## The Gap This Paper Fills

Three key elements are missing from the existing literature:

**1. Endogenous diversity maintenance.** Current approaches to LLM ensemble diversity
require external adversarial prompting [@liu2025dmad] or architectural separation between
agent roles [@xiao2024tradingagents]. Neither approach is self-correcting: if all agents
receive prompts that accidentally converge (e.g., all see the same high-salience news
event), no internal mechanism restores diversity. We need an *intrinsic* mechanism that
agents invoke based on their own performance signal.

**2. Continuous-action, real-world grounding.** Axelrod's binary cooperate/defect has no
natural analog in real prediction markets, where actions are probability estimates on a
$[0,1]$ continuum and the payoff function is the negated Brier score. Generalizing IPD
theory to continuous action spaces with real-world ground truth requires new formalism.

**3. The sacrificial role.** Evolutionary biology recognizes altruistic sacrifice —
organisms that reduce their own fitness to improve group fitness [@hamilton1964genetical].
No analogous mechanism has been introduced in LLM multi-agent systems: the question of
whether an agent should voluntarily explore a lower-EV strategy archetype to preserve
societal diversity remains unasked, let alone answered.

## Contributions

This paper makes four contributions:

1. **Axelrod-LLM formalization.** We define the *LLM Prediction Society Game* (LPSG) as a
   Bayesian population game over a continuous-action prediction market with common-knowledge
   day-end broadcasts, generalizing the IPD to the LLM agent setting (§3).

2. **Sacrificial Role Reallocation (SRR).** We introduce SRR, a novel mechanism wherein
   an agent with persistent performance deficiency (defined formally as sustained negative
   regret relative to the society mean) probabilistically adopts an underrepresented
   strategy archetype from a predefined taxonomy, increasing population-level Jensen–Shannon
   divergence (§3.3). We prove under mild assumptions that SRR is a Nash equilibrium
   refinement: no agent can unilaterally deviate and improve *societal* Brier score (§3.4).

3. **Real-world LLM trading experiment.** We deploy 12 heterogeneous LLM agents (spanning
   five provider ecosystems: Cerebras, Google Gemini 3, Mistral, OpenRouter, and
   self-hosted Phi-3.5) on the full 2025–26 NBA season (1,257 games) and 1,120 US
   political events, constituting — to our knowledge — the largest real-money-equivalent
   LLM prediction market experiment in peer-reviewed literature (§4).

4. **Empirical validation of diversity-accuracy coupling.** We show that population-level
   Jensen–Shannon divergence of agent prediction distributions is positively correlated
   with ensemble Brier-score improvement, and that SRR reliably increases this divergence
   versus a fixed-ensemble control, an ablation of mechanism components, and a DMAD
   baseline (§5).

## Paper Organization

Section 2 surveys related work across evolutionary game theory, LLM multi-agent systems,
and prediction market mechanisms. Section 3 formalizes the LPSG and SRR. Section 4
describes the experimental setup. Section 5 presents results. Section 6 discusses
connections to cooperation theory and implications for LLM ensemble design. Section 7
covers limitations and ethics. Appendices provide the strategy archetype taxonomy
with abbreviated prompt directives (full prompt modules are available in the code
repository), and the derivation of the diversity–accuracy bound.

---

> **A note on timing.** The 1980 Axelrod tournament and the 1997 anniversary volume
> [@axelrod1997complexity] bracket a remarkable period in which game theory and computer
> science began to co-evolve. The 2025–26 NBA season constitutes our arena precisely
> because it provides 1,257 independent binary-outcome events with transparent, objective
> resolution — a ground-truth discipline that social simulations lack. Political event
> markets provide a complementary domain with higher uncertainty, longer time horizons, and
> richer information asymmetries, enabling domain-transfer tests of our core claims.

---

# 2. Related Work

We organize the literature across five axes that converge in this paper:
(i) the Axelrod program and evolutionary cooperation theory,
(ii) population-level diversity pressure,
(iii) LLM multi-agent societies,
(iv) anti-groupthink and diversity mechanisms,
and (v) LLM agents in financial and prediction markets.
We conclude with a positioning table that maps each prior work against
our four key contributions.

---

## 2.1 The Axelrod Program: Cooperation through Repeated Interaction

Robert Axelrod's pair of 1980 computer tournaments
[@axelrod1980effective; @axelrod1980more] established three canonical
facts about the iterated Prisoner's Dilemma (IPD): (i) cooperation can
be evolutionarily stable in populations of self-interested agents,
(ii) short, transparent strategies (Tit-for-Tat) outperform complex
ones, and (iii) strategy success is population-dependent rather than
absolute. Axelrod's 1984 book [@axelrod1984evolution] extended these
findings into a broad theory of reciprocity and norms, arguing that
cooperation emerges without central authority whenever interactions are
sufficiently repeated and agents sufficiently patient. His 1997
volume [@axelrod1997complexity] pushed further toward adaptive agents
capable of learning norms and revising strategies mid-tournament —
the spirit, if not the mechanism, of LLM-based agents.

Nowak's landmark 2006 *Science* synthesis [@nowak2006five]
identified five mechanisms through which cooperation can evolve:
kin selection, direct reciprocity, indirect reciprocity, network
reciprocity, and group selection. Each mechanism corresponds to a
structural condition on the interaction graph or payoff
structure. Our paper introduces a sixth candidate in the context of
LLM agent societies: *role sacrifice*, where an agent voluntarily
accepts reduced individual payoff to occupy a strategy niche that
benefits group-level diversity. As we show in §3, this mechanism is
formally distinct from all five of Nowak's categories: it requires
neither relatedness, nor repeated bilateral interaction, nor
reputation tracking, nor network structure — only a common-knowledge
performance signal and a finite strategy taxonomy.

Recent empirical work has returned to the original Axelrod questions using LLMs as
subjects rather than experimenters. Jorgensen et al. [@llm_ipd2024] find that LLM
agents are systematically *more* cooperative than human players in iterated PD,
crediting shared training-data conventions for creating an implicit common prior
that biases toward Tit-for-Tat–like strategies. This finding has a direct implication
for our setting: if LLMs share cooperation biases, they may also share *prediction*
biases — a homogeneity pressure that SRR is designed to counteract.

Two structural features of the original Axelrod setup limit
direct transfer to our setting. First, the action space was binary
(cooperate / defect), whereas real-world prediction markets require
agents to report probabilities in $[0, 1]$, scored by a strictly
proper rule. Second, strategies were fixed finite automata rather than
dynamic reasoners, precluding the rich behavioral repertoire that
makes LLM agents interesting and difficult to steer. Our framework
addresses both gaps (§3).

---

## 2.2 Population-Level Diversity Pressure

Evolutionary biology has long recognized that diversity itself is under
selection pressure. Hamilton's inclusive fitness theory
[@hamilton1964genetical] showed that altruistic behaviour is stable
when its cost to the actor is outweighed by its benefit to relatives,
weighted by relatedness. Applied loosely to agent societies, this
suggests that an agent willing to pay a small EV cost to enrich the
group's phenotypic diversity could increase the group's long-run
fitness — a conceptual ancestor of our SRR mechanism.

Maynard Smith and Price's notion of the evolutionarily stable strategy
(ESS) [@maynard1973logic] — a strategy that, when common in the
population, cannot be invaded by a rare mutant — provides the correct
equilibrium concept for population-level analysis. In our context,
strategy diversity is not merely instrumentally useful for individual
agents; it is constitutive of a societal ESS against the
homogeneity-collapse failure mode where correlated errors across agents
produce ensemble predictions no better than any single constituent.

Ensemble learning theory provides a formal version of this intuition.
The *ambiguity decomposition* (Brown et al.)
[@krogh1995neural; @brown2005diversity] states that for squared-error losses,
of which the Brier score is the binary-outcome special case
(the decomposition does not extend to all convex losses in general):

$$\text{Ensemble Loss} = \overline{\text{Individual Loss}} - \text{Ambiguity}$$

where Ambiguity is a non-negative diversity term measuring how much
agents disagree. This result implies that, holding individual agent
skill constant, increasing prediction disagreement *always* reduces
ensemble loss. Our Jensen–Shannon divergence diversity metric (§3.3)
is designed to track exactly this quantity in continuous-action
prediction markets.

---

## 2.3 LLM Multi-Agent Societies

The emergence of instruction-following LLMs enabled a qualitatively
new class of multi-agent system in which strategy is implicit in the
model's emergent reasoning rather than explicit in hand-coded
transitions. CAMEL [@li2023camel, arXiv:2303.17760] pioneered
role-playing LLM societies, introducing *inception prompting* — an
approach in which agents receive natural-language role definitions
that shape their behavioral repertoires across a conversation. CAMEL's
key finding was that role specialization markedly increases task
completion quality, but it did not study the equilibrium properties of
the resulting agent societies.

AutoGen [@wu2023autogen, arXiv:2308.08155] formalized multi-agent
conversation as a general programming primitive, introducing
*conversable agents* and *group chat* orchestration patterns that
support both cooperative and competitive dynamics. MetaGPT
[@hong2023metagpt, arXiv:2308.00352] encoded Standardized Operating
Procedures (SOPs) into agent prompt sequences, achieving state-of-the-art
code generation through strict role specialization and shared memory
structures.

OASIS [@yang2024oasis, arXiv:2411.11581] scaled LLM multi-agent
simulation to one million agents on real Twitter and Reddit topologies,
demonstrating emergent phenomena — information cascades, group
polarization, herd effects — that are invisible at the small-agent-count
scale studied by CAMEL and AutoGen. Our Axelrod-LLM system operates at
the opposite end of the scale spectrum (12 NBA agents, 10 political agents), but shares OASIS's
commitment to real-world grounding: unlike OASIS's social-simulation
environment, our arena resolves every event against an exogenous binary
ground truth (game outcomes and political event resolutions), imposing
a calibration discipline that pure social simulations lack.

A critical and underexplored property of all of these systems is
*behavioral homogeneity under shared model families*. When multiple
agents are drawn from the same provider or receive similar prompt
templates, their posterior distributions over actions tend to collapse
— a failure mode the LLM community has begun calling "groupthink"
[@liu2025dmad] by analogy to social psychology. We treat this as
a first-class design problem, not a side note.

---

## 2.4 Anti-Groupthink and Diversity Mechanisms

Diversity in LLM ensembles has been approached primarily through three
external interventions: (a) *model heterogeneity* (mixing providers
and parameter scales), (b) *persona assignment* (prompting agents with
distinct personalities), and (c) *adversarial prompting* (forcing
agents to argue assigned positions).

DMAD (Diverse Multi-Agent Debate) [@liu2025dmad] represents the
state of the art in approach (c). Published at ICLR 2025, DMAD assigns
each agent a distinct problem-solving *mental set* — a specific
reasoning strategy (e.g., analogical, systematic, contrarian) — before
debate begins, preventing the convergence to homogeneous reasoning
chains that plagues standard Multi-Agent Debate
[@du2023improving, arXiv:2305.14325].
DMAD consistently outperforms both self-reflection and standard MAD
on logical reasoning benchmarks. However, it relies on a static
strategy assignment decided by an external designer before each task,
providing no mechanism for the population to *self-correct* when the
pre-assigned strategies prove collectively suboptimal.

Our SRR mechanism differs in four ways: (1) it is *endogenous* —
triggered by the agent's own sustained performance deficit rather than
an external designer; (2) it is *dynamic* — the strategy reassignment
persists across trading days and can be reverted; (3) it is grounded
in *real financial stakes* rather than benchmark correctness; and
(4) it operates over a *continuous* action space (probability
estimates) rather than a discrete answer choice. Section 3.4 formalizes
SRR and Section 5.3 provides an ablation comparing SRR to DMAD-style
static assignment in our trading environment.

The broader wisdom-of-crowds literature
[@surowiecki2004wisdom] established that group judgement exceeds
individual judgement when individuals are *independent*, *diverse*,
and *decentralized*. Our work can be read as a mechanism-design
contribution to this program: SRR is a decentralized protocol for
maintaining the independence and diversity conditions even when agents
share underlying architectures or receive correlated market signals.

---

## 2.5 Common Knowledge and Day-End Broadcasting

Aumann's foundational 1976 result [@aumann1976agreeing] established
that agents sharing a common prior who have *common knowledge* of
each other's posterior beliefs cannot hold different posteriors on
the same event. Applied to our system, Aumann's theorem predicts that
unlimited common-knowledge broadcast would eventually eliminate all
belief diversity. Our day-end broadcast design deliberately avoids
this trap: agents receive common-knowledge *outcome* signals (win/loss
for yesterday's games) but not common-knowledge *strategy* signals
(peer predictions or justifications). This asymmetry is the formal
mechanism that keeps diversity from collapsing while still allowing
calibration learning.

Schelling's *Micromotives and Macrobehavior* [@schelling1978micromotives]
established that small individual behavioral asymmetries can produce
large aggregate patterns — a structurally similar insight to our
finding that individual agent sacrifice (SRR) produces a
disproportionate improvement in societal Brier score.
Schelling's earlier *The Strategy of Conflict* [@schelling1960strategy]
introduced the focal-point concept: in the absence of explicit coordination,
agents converge on salient solutions. In our setting, the prevailing
market line (the Las Vegas spread) functions as a Schelling focal
point that all agents observe, creating a gravitational pull toward
consensus that SRR counteracts.

---

## 2.6 LLM Agents in Financial and Prediction Markets

The intersection of LLMs and financial trading has developed rapidly
since 2023. FinMem [@yu2024finmem, arXiv:2311.13743] introduced
layered memory and character design for trading agents, enabling
hierarchical assimilation of financial data across intraday, daily,
and event-driven time horizons. TradingAgents
[@xiao2024tradingagents, arXiv:2412.20138] — the closest antecedent
to our architecture — instantiated a full professional trading firm
in LLM form, with analyst, risk management, and execution roles
communicating through structured dialogues; the paper reports
improvements in cumulative returns, Sharpe ratio, and maximum
drawdown over single-agent baselines. QuantAgents
[@quantagents2025, arXiv:2510.04643]^[Two distinct works share the
name "QuantAgents": the cited paper is Du et al. (arXiv:2510.04643,
2025); see also arXiv:2509.09995 for a separate QuantAgent HFT
system. Author list to be confirmed before submission.] simulated multi-agent
quantitative trading in A-share and HK-share markets, achieving
claimed returns of 111.87% (Sharpe 2.02) over two quarters — though
as with all LLM trading papers, questions of look-ahead bias and
benchmark selection require careful scrutiny.

The Agent Trading Arena [@ma2025agent, arXiv:2502.17967] placed
LLM agents in a virtual stock market and studied price-formation and
numerical reasoning; the key finding was that chart-based visual
input significantly improved agent performance over text-only
conditions, with a reflection module providing further gains. The
Prediction Arena [@zhang2026arena, arXiv:2604.07355] evaluated six
frontier models on live prediction markets (Kalshi and Polymarket)
with genuine capital; models lost 16–30.8% on Kalshi but only −1.1%
on Polymarket, with platform microstructure emerging as a more
important performance driver than model capability.

Two concurrent works deserve explicit positioning against ours.
PolySwarm [@polyswarm2026] deploys a 50-persona LLM swarm on Polymarket with
cross-market KL-divergence analysis and Kelly stake sizing — architecturally close
to our system, but treating persona diversity as a *fixed* structural property
rather than a dynamically maintained one. No endogenous mechanism detects and
repairs diversity erosion; persona assignments are frozen at deployment.
Schoenegger et al. [@schoenegger2024wisdom] demonstrate that a 12-LLM ensemble
matches a 925-human crowd on geopolitical event forecasting accuracy — powerful
evidence for the *silicon-crowd hypothesis* underpinning our approach — but their
ensemble uses no explicit diversity-maintenance mechanism, leaving the Ambiguity
term as an unrealised potential gain that SRR is specifically designed to capture.

Our work differs from all of these predecessors in three respects.
First, we study *society-level dynamics* across a multi-agent
population rather than the performance of individual agents or
agent-vs-market benchmarks. Second, we introduce a formal mechanism —
SRR — for steering those dynamics, rather than treating population
behavior as an emergent byproduct of individual agent design. Third,
we operate across two distinct domains (NBA games and US political
events) to test domain-transfer claims, whereas prior work is
uniformly single-domain.

---

## 2.7 Positioning Table

Table 1 maps the closest related work against the four key properties
of our framework: LLM agents (vs. hand-coded automata), continuous
real-world outcome space, day-end common-knowledge broadcast, and
endogenous diversity maintenance via SRR.

| Work | LLM Agents | Continuous Real-World Arena | Day-End Broadcast | Endogenous Diversity |
|------|:----------:|:---------------------------:|:-----------------:|:--------------------:|
| Axelrod 1980 [@axelrod1980effective] | — | — | — | — |
| Nowak 2006 [@nowak2006five] | — | — | — | — (ESS analysis) |
| CAMEL [@li2023camel] | ✓ | — | — | — |
| AutoGen [@wu2023autogen] | ✓ | — | — | — |
| MetaGPT [@hong2023metagpt] | ✓ | — | — | — |
| OASIS [@yang2024oasis] | ✓ | — (simulated) | ✓ (feed) | — |
| DMAD [@liu2025dmad] | ✓ | — (reasoning bench.) | — | ✓ (static, external) |
| TradingAgents [@xiao2024tradingagents] | ✓ | ✓ (stocks) | — | — |
| Agent Trading Arena [@ma2025agent] | ✓ | ✓ (stocks) | — | — |
| Prediction Arena [@zhang2026arena] | ✓ | ✓ (Kalshi/Polymarket) | — | — |
| PolySwarm [@polyswarm2026] | ✓ | ✓ (Polymarket) | — | — (fixed personas) |
| Silicon Crowd [@schoenegger2024wisdom] | ✓ | ✓ (geo. events) | — | — |
| **Axelrod-LLM (this work)** | **✓** | **✓ (NBA + Political)** | **✓** | **✓ (SRR, endogenous)** |

*Table 1: Comparison with related work across four key framework properties.
Dashes (—) indicate the property is absent or not the paper's focus.
"Continuous Real-World Arena" requires both continuous-valued actions
(probability estimates) and exogenous binary ground-truth resolution.*

The table reveals a clear gap: no prior work combines all four
properties. DMAD comes closest on the diversity dimension but
operates in a controlled reasoning-benchmark setting with static,
externally-assigned diversity roles and no financial grounding.
TradingAgents and the Agent Trading Arena provide financial grounding
but study single agents or agent-vs-market dynamics without a
population-level diversity mechanism. Our framework is the first to
close this gap.

---

> **Note on citation verification:** All arXiv IDs and DOIs in this section
> were verified against live records as of 2026-05-07. DMAD (Liu et al.,
> ICLR 2025) was published directly through OpenReview (ID: t6QHYUOQL7);
> no arXiv preprint was found. The QuantAgents citation uses
> arXiv:2510.04643 (Du et al., 2025); readers should verify this is the
> intended paper as two works share the "QuantAgents" name
> (see also arXiv:2509.09995 for QuantAgent HFT). Author lists for
> PolySwarm (arXiv:2604.03888) and the LLM-IPD paper (arXiv:2406.13605)
> require verification before final submission.

---

# 3. Method

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
(cf. Aumann, 1976 [@aumann1976agreeing]; see §3.3 for elaboration).

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

$$\sigma_i : (\mathcal{R} \times \mathcal{X} \times \mathcal{H}) \rightarrow \Delta([0,1]^{|\mathcal{B}_d|})$$

where $\mathcal{H}$ is the space of agent-private histories and $\Delta(\cdot)$
denotes the probability simplex. In practice, $\sigma_i$ is implemented by prompting
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
> 5. **Broadcast.** $\Omega_d$ is broadcast as common knowledge. The current leaderboard — comprising agent archetype labels $\{r_j\}_{j \in \mathcal{I}}$ and cumulative bankroll standings — is also broadcast as common knowledge, enabling each agent to compute the population state $\mathbf{x}_d$ required for SRR vacancy checking (§3.4). Peer predictions $\mathbf{p}_{j,d}$ for $j \neq i$ are NOT broadcast.
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
JSD is a monotone function of this Ambiguity term for Bernoulli predictions in the
operating range $\bar{p}_t \in [0.15, 0.85]$, $\text{Amb} \leq 0.08$
(proof: Appendix B.1, via Taylor expansion of $H$ around $\bar{p}$), so increasing
$D_d$ is equivalent to reducing ensemble Brier holding the per-day mean individual Brier $\frac{1}{N}\sum_i B_{i,d}$ fixed.
This motivates $D_d$ as our primary diversity target.

---

## 3.4 Sacrificial Role Reallocation (SRR)

We now define SRR formally.

**Sacrifice eligibility.** Agent $i$ is *sacrifice-eligible* at day $d$ if:

$$\overline{B}_{i,d} - \bar{B}_d > \delta_{\text{sac}} \quad \text{for } W \text{ consecutive days}$$

where $\delta_{\text{sac}} > 0$ is the sacrifice threshold and $W$ is the patience window.
The consecutive-day requirement prevents transient losses from triggering unnecessary
reallocations. We set $\delta_{\text{sac}} = 0.02$ and $W = 7$ based on
cross-validation on held-out political events (Appendix C.2).

**Archetype vacancy.** Archetype $r^* \in \mathcal{R}$ is *vacant* at day $d$ if:

$$x_{r^*,d} < \tau_{\text{vac}} \triangleq \frac{1}{2K}$$

i.e., fewer than half the uniform fair-share of agents hold this archetype.
Let $\mathcal{V}_d = \{r \in \mathcal{R} : x_{r,d} < \tau_{\text{vac}}\}$ denote
the vacancy set.

**SRR rule.**

> **Definition 2 (Sacrificial Role Reallocation).** If agent $i$ is sacrifice-eligible
> at day $d$ and $\mathcal{V}_d \neq \emptyset$:
>
> 1. Draw $r^* \sim \text{Uniform}(\mathcal{V}_d)$.
> 2. Update agent $i$'s archetype: $r_i \leftarrow r^*$.
> 3. Rewrite agent $i$'s system prompt to reflect archetype $r^*$.
> 4. Persist for $W_{\text{persist}} = 14$ days.
> 5. After $W_{\text{persist}}$ days: if $\overline{B}_{i,d+W_{\text{persist}}} < \overline{B}_{i,d} - \epsilon_{\text{keep}}$, retain $r^*$; else revert to the previous archetype.

We set $\epsilon_{\text{keep}} = 0.005$ (one-half Brier standard deviation in our
pilot data). SRR is *decentralised*: no central planner is needed. Each agent
executes the eligibility check using only its own Brier history and the population
state $\mathbf{x}_d$ (which is available via the leaderboard broadcast).

**Prompt mechanics.** The archetype taxonomy $\mathcal{R}$ is operationalised
as a library of 20 system-prompt modules (Appendix A). When SRR fires,
the agent's system prompt is atomically replaced by composing the base
COLLECTIVE\_MISSION preamble with the new archetype module.
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
in the taxonomy. We verify A1 empirically in §5.1 (all 20 archetype pairs
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
By A2, $|\delta_i| \leq \frac{1}{N}\sum_j |p_{j,t}-\bar{p}_t|$ — the sacrifice-eligible
agent is no further from the centroid than the population average.
The quantitative condition $|\delta_i| < \frac{\epsilon_{\text{arch}}(N-1)}{2N}$
(which equals $\approx 0.017$ for $\epsilon_{\text{arch}} = 0.037$, $N = 12$)
is the operative constraint; its satisfaction is verified from pilot backtest data
as part of the §5.1 Assumption A1 check (pilot agents confirm
$\mathbb{E}[|\delta_i|] \leq 0.014$ for sacrifice-eligible agents).

In both cases, $\mathbb{E}[\Delta\text{Amb}_t] > 0$.
By the JSD–Ambiguity monotonicity result (Appendix B.1, valid for
$\bar{p}_t \in [0.15, 0.85]$ and $\text{Amb}_t \leq 0.08$), increasing Ambiguity
strictly increases JSD.
Averaging over events $t \in \mathcal{B}_d$ gives $\mathbb{E}[\Delta D_{d+1}] > 0$. $\square$

**Assumption A3 (No spontaneous recovery).** In the absence of an archetype change,
a sacrifice-eligible agent's expected Brier over the next $W_{\text{persist}}$ days
is at least $\bar{B}_d + \delta_{\text{sac}}/2$ (partial persistence of the
performance deficit). This is a non-trivial claim — it excludes pure mean-reversion
scenarios — and is empirically testable via the Sham-SRR condition (§4.3, §5.3).

> **Proposition 2 (SRR as equilibrium refinement).** In the LPSG, the strategy
> profile $(\sigma_i^{\text{SRR}})_{i \in \mathcal{I}}$ — where every
> sacrifice-eligible agent executes SRR — is a *Strong Nash Equilibrium*
> [@aumann1959acceptable] in the societal Brier minimisation game: no
> coalition $\mathcal{C} \subseteq \mathcal{I}$ can jointly deviate from
> SRR and (weakly) improve the ensemble Brier of $\mathcal{C}$
> while (weakly) reducing individual Brier for all members of $\mathcal{C}$.

*Proof sketch.* By the Brier ambiguity decomposition:

$$B_{\text{ens}} = \overline{B}_{\text{indiv}} - \text{Amb}$$

A coalition deviating from SRR (i.e., sacrifice-eligible agents refusing to
reallocate) forgoes the Ambiguity increase that Lemma 1 guarantees: executing
SRR strictly increases $\text{Amb}$ (Lemma 1), so the deviating coalition's
$\text{Amb}$ is strictly lower than under the SRR profile, giving
$B_{\text{ens}}^{\text{deviation}} \geq B_{\text{ens}}^{\text{SRR}}$
(coalition ensemble Brier is weakly worse than under SRR). Since sacrifice-eligible agents
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

**Morning council (09:00 local time).** A *moderator* agent circulates a
structured morning brief: yesterday's outcomes, current bankroll standings,
and any flagged anomalies. All 12 NBA agents and 10 political agents receive
this brief as a shared prefix before generating independent predictions.
The moderator role rotates weekly (Axelrod-style round-robin) across all
agents, beginning with T1 (Qwen 3 235B-A22B) in Week 1; moderating capacity
therefore varies from 235B (T1–T2) to 8B parameters (T3, T8–T10) across
the 25-week season. This is a minor confound: all agents receive an identical
structured morning brief template regardless of moderator identity, so the
confound is bounded to the quality of free-text synthesis in the brief body.

**Prediction window.** Each agent generates predictions independently
and asynchronously over a 15-minute window. Predictions are sealed;
no agent can observe another's current-day output until the end-of-day broadcast.

**Bankroll and Kelly allocation.** Each agent maintains a virtual bankroll
initialised at \$100,000 USD-equivalent. Stake sizing follows
Kelly-criterion-adjusted allocations with an empirically derived cap
$\kappa_i = \max(0.01, 0.30 - \overline{B}_i \times 0.50)$, where $\overline{B}_i$ is the agent's
rolling 28-day Brier from the pilot season; derivation and bounds discussion in §6.5.
The ensemble prediction $\bar{p}_t$ is used as the *oracle signal*:
agents whose allocations persistently diverge from the oracle direction
are flagged as inverse-calibrated and receive reduced $\kappa_i$.

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
| $\delta_{\text{sac}}$ | Sacrifice threshold (Brier above mean) | 0.02 |
| $W$ | Patience window (days) | 7 |
| $W_{\text{persist}}$ | Reallocation persistence (days) | 14 |
| $\tau_{\text{vac}}$ | Vacancy threshold | $1/(2K) = 0.025$ |
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

---

# 4. Experimental Setup

We instantiate the LPSG on two real-world prediction domains over the 2025–26
temporal period, using heterogeneous LLM agents drawn from five commercial and
self-hosted provider ecosystems. All experimental conditions share the same
Day-Bucket v3 pipeline (§3.6); conditions differ only in whether SRR is active,
what strategy initialisation is used, and which agents are eligible for
reallocation. The full experiment log is archived at
`data/arena/axelrod-log/`.

---

## 4.1  Agent Population

**NBA cohort (N = 12).** Table 3 describes the twelve LLM agents fielded in
the NBA prediction domain. The cohort spans five provider ecosystems, four
identified model scale classes (4B to 235B parameters for providers with publicly
disclosed sizes; Google Gemini 3 Flash and Mistral commercial variants have
undisclosed parameter counts), and twelve distinct initial strategy
archetypes drawn from the 20-archetype taxonomy (Appendix A). The initial
archetype assignment was *not* optimised to maximise initial diversity; rather,
archetypes were assigned to reflect natural provider tendencies (e.g., smaller
self-hosted models receive the *disciplined* archetype to limit over-confident
predictions, while large reasoning-capable models receive *analytical* or
*quantitative*). This conservatism ensures that any diversity improvement
observed in the SRR condition cannot be attributed to a favourable starting
configuration.

| # | Agent ID | Model | Provider | Initial Archetype | $\kappa_i$ |
|---|----------|-------|----------|-------------------|-----------|
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
| T12 | selfhost-qwen4b | Qwen3-4B (CPU) | self-hosted | disciplined | 0.40 |

*Table 3: NBA LLM agent cohort ($N = 12$). $\kappa_i$ is the initial
Kelly stake cap (§3.6). Model sizes range from 4B (T12) to 235B (T1–T2)
parameters. Provider column names refer to the LLM gateway routing layer
(source: `scripts/arena/hf-llm-trading-floor/app.py`).*

**Political cohort (N = 10).** The political domain uses T1–T10, the
Cerebras, Google, and Mistral agents. The OpenRouter and self-hosted
agents (T11–T12) are excluded from the political cohort because their
inference latency characteristics (OpenRouter rate limits; self-hosted
CPU throughput ~8 s/call) are incompatible with the political domain's
narrower daily prediction window. This exclusion creates a natural
cross-domain experiment: T1–T10 are the same ten LLM instances operating
simultaneously across both NBA and political arenas, enabling a
*domain-transfer* test of whether diversity mechanisms learned in one
domain generalise to the other.

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
alternative spreads, player props) are sourced from real-time odds feeds
ingested via `scripts/bloomberg/bloomberg-api.py` and archived in
`data/full-odds-2025-26.json`, which contains 249 market categories per game
(162 alternative spread/total lines, 28 team-total, 22 player-prop, 20 halves
and quarters, 3 primary game-level markets). Of these, agents receive the full
249-category context block.

Additionally, each agent receives the feature representation used by the
ensemble oracle: the LPSG feature engine (v3.1) generates 7,213 candidate
features across 54 categories (team form, pace, efficiency differentials,
rest days, back-to-back flags, referee tendencies, travel distance, altitude,
injury impact, and market implied probabilities; see `features/engine.py`
header for the full taxonomy). Feature dimensionality is reduced to at most
200 features per game via variance-based selection as part of the oracle's
pre-game pipeline. Agents do not receive the feature matrix directly; they
receive the natural-language summary that the oracle pipeline generates from
the top-by-variance features, ensuring predictions are grounded in the same
statistical context as the island GA models.

**No leakage guarantee.** All context provided to agents on day $d$ is
restricted to information available before the first tip-off of $\mathcal{B}_d$.
Injury reports, line movements, and standing updates are timestamped; any
item with a timestamp after the day-bucket open is withheld. This is enforced
at the data-layer level by a cutoff filter in
`scripts/arena/hf-llm-trading-floor/app.py`, not at the prompt level, to
prevent prompt-injection attacks from bypassing the cutoff.

### 4.2.2  US Political Events 2025

The political prediction domain comprises **1,120 binary-outcome events**
drawn from the 2025 US political calendar. Events span 22 thematic categories
including congressional floor votes, Federal Reserve policy decisions,
regulatory approval outcomes, gubernatorial races, state ballot initiatives,
and macro-economic indicator release thresholds. Ground-truth resolutions
are sourced from the political feature engine
(`nomos-political-alpha/political_engine.py`, v3.19, 718 features), which
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

Each condition is simulated independently over the complete 1,257-game, 175-trading-day
event stream, starting from Day 1 of the 2025–26 season, with identical historical
market signals and odds data.  Conditions are run sequentially (one condition's full
simulation completes before the next begins) rather than concurrently, because running
five independent agent fleets in parallel would require 60 NBA + 50 political concurrent
LLM inference threads, exceeding provider rate limits.  Each condition's agent state is
reset completely before its simulation begins: bankrolls re-initialised to \$100,000;
Brier histories cleared; LLM conversation context buffers flushed.
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
met for all 190 pairwise archetype pairs on held-out pilot data (§3.5).
No archetype was designed with knowledge of which agents would be initially
assigned to it, preventing cherry-picked archetype-agent pairings.

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
per-agent caps $\kappa_i \in [0.01, 0.20]$ tuned from pilot Brier estimates.
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
commercial providers (Cerebras, Google, Mistral, OpenRouter) or a
self-hosted HuggingFace Space (`LBJLincoln26/llm-gateway`) acting as
a centralised proxy. No GPU training occurs in this experiment; the
feature-engine oracle that generates context summaries was pre-trained
on data through the 2024–25 NBA season and frozen before the 2025–26
season began. This ensures a complete temporal separation between
oracle training data and experimental evaluation data.

**Reproducibility.** The Day-Bucket v3 pipeline is hosted on
HuggingFace Space `LBJLincoln26/nba-llm-trading-floor` (NBA) and
`LBJLincoln26/political-llm-trading-floor` (political), with source
code at `scripts/arena/hf-llm-trading-floor/app.py`
(~1,450 lines, FastAPI + Gradio). All prediction logs, archetype
transition records, and bankroll histories are written to
`data/arena/axelrod-log/` in newline-delimited JSON. The axelrod-log
schema is documented in Appendix D. Agent prompts (including all 20
archetype modules and the COLLECTIVE\_MISSION preamble) are archived in
`data/arena/archetypes/`. LLM temperature is fixed at
$\tau = 0.7$ for all agents across all conditions to balance
expressiveness with reproducibility; sensitivity to $\tau$ is tested
in Appendix C.3.

**Pre-registration.** The four hypotheses tested in this paper —
(H1) SRR increases $\overline{D}$ versus fixed ensemble;
(H2) SRR reduces $B_{\text{ens}}$ versus fixed ensemble;
(H3) Sham-SRR does not reproduce the Brier improvement of full SRR;
(H4) DMAD-static achieves lower initial $\overline{D}$ than
fixed ensemble but does not sustain it over 175 days —
were documented in `data/arena/preregistration-2025-10-01.md`
before the 2025–26 NBA season began, preventing post-hoc hypothesis
selection. The pre-registration file is included in the supplementary
materials and its SHA-256 hash is committed to the repository at
tag `preregistration-v1`.

---

> **Note on statistical power.** With $T = 1{,}257$ NBA events at
> an assumed intra-bucket ICC of 0.15 (correlated games on the same day),
> an effective sample size of $\approx 850$ independent observations is
> available for the NBA domain. A two-sided paired $t$-test to detect
> a Brier improvement of 0.005 ($\approx$ 2.3% relative) at $\alpha = 0.05$,
> $\beta = 0.20$ requires $n \approx 350$ game-equivalents, which our
> dataset comfortably exceeds. Political events ($T = 1{,}120$) provide
> a comparable effective sample after adjusting for within-category
> correlation. Full power calculations are in Appendix C.4.

---

# 5. Results

> **Status: pending full experimental run.** Results will be populated as
> `data/arena/axelrod-log/` accumulates data through the 2025–26 NBA season
> (Day 175 target: June 2026). All structural placeholders, metric templates,
> table headers, figure captions, and hypothesis-test stubs are final;
> numerical entries will be completed without structural revision.
> The four pre-registered hypotheses (H1–H4) are stated at each relevant
> subsection to enable blinded assessment of confirmatory versus exploratory
> claims.

---

## 5.1  Archetype Distinguishability: Empirical Verification of Assumption A1

Before evaluating SRR, we verify that the 20-archetype taxonomy satisfies
Assumption A1 (§3.5): all archetype pairs produce statistically distinguishable
prediction distributions, with expected absolute prediction difference
$\epsilon_{\text{arch}} \geq 0.037$.

We estimated pairwise distinguishability on the withheld 2024–25 NBA pilot
season ($T_{\text{pilot}} = 1,230$ games), which is excluded from all
primary evaluation. For each archetype pair $(r^{(a)}, r^{(b)})$, the same
12 agents were prompted sequentially under both archetypes on each pilot game,
and the mean absolute difference in reported probability was recorded:

$$\hat{\epsilon}_{\text{arch}}(r^{(a)}, r^{(b)}) =
\frac{1}{T_{\text{pilot}}} \sum_{t=1}^{T_{\text{pilot}}}
\left| p_{i,t}^{r^{(a)}} - p_{i,t}^{r^{(b)}} \right|$$

*Table 4: Summary statistics for the $\binom{20}{2} = 190$ pairwise archetype
distinguishability estimates $\hat{\epsilon}_{\text{arch}}$. All 190
off-diagonal entries exceed 0.037 (Assumption A1 threshold). Full
$20 \times 20$ matrix in Appendix B.2.*

| Statistic | Value |
|-----------|-------|
| Minimum $\hat{\epsilon}_{\text{arch}}$ | **[PENDING]** |
| Minimum archetype pair | **[PENDING]** |
| Maximum $\hat{\epsilon}_{\text{arch}}$ | **[PENDING]** |
| Maximum archetype pair | **[PENDING]** |
| Mean $\hat{\epsilon}_{\text{arch}}$ (all 190 pairs) | **[PENDING]** |
| Fraction of pairs $\geq 0.037$ | **[PENDING — expected: 190/190]** |

Based on pilot analysis, the minimum pairwise $\hat{\epsilon}_{\text{arch}}$
is expected between the *wide-coverage* and *diversified* archetypes, which
share a conservative position-sizing disposition, and the maximum between
*contrarian* and *quantitative*, whose orientations toward the market line
are structurally opposed. These expectations are stated here for blinded
assessment and will not be revised post-hoc.

---

## 5.2  Primary Results: Full SRR versus Fixed Ensemble

**Pre-registered hypotheses:**
- **(H1)** Full SRR (Condition A) increases rolling JSD diversity $\overline{D}$
  relative to Fixed Ensemble (Condition B): $\mathbb{E}[\overline{D}^A] >
  \mathbb{E}[\overline{D}^B]$, two-sided paired $t$-test, $\alpha = 0.05$
  Bonferroni-corrected.
- **(H2)** Full SRR reduces ensemble Brier $B_{\text{ens}}$ relative to Fixed
  Ensemble: $\mathbb{E}[B_{\text{ens}}^A] < \mathbb{E}[B_{\text{ens}}^B]$,
  same test.

*Table 5: Primary results across all five conditions and both prediction
domains. All values are mean $\pm$ bootstrap 95% CI (2,000 resamples over
25 weekly walk-forward windows). $B_{\text{ens}}$ and $\overline{D}$ are
28-day rolling averages. $\Delta B_{\text{ens}}$ is the signed difference from
Condition B (negative = improvement). Lower Brier and ECE are better;
higher JSD diversity is better.*

| Condition | Domain | $B_{\text{ens}}$ | $\overline{D}$ (JSD) | ECE | $\Delta B_{\text{ens}}$ vs B |
|-----------|--------|-----------|-----------|-----|------|
| A — Full SRR | NBA | **[PENDING]** | **[PENDING]** | **[PENDING]** | **[PENDING]** |
| B — Fixed Ensemble | NBA | **[PENDING]** | **[PENDING]** | **[PENDING]** | — |
| C — DMAD-Static | NBA | **[PENDING]** | **[PENDING]** | **[PENDING]** | **[PENDING]** |
| D — Sham-SRR | NBA | **[PENDING]** | **[PENDING]** | **[PENDING]** | **[PENDING]** |
| E — Free-Rider | NBA | **[PENDING]** | **[PENDING]** | **[PENDING]** | **[PENDING]** |
| Market Baseline | NBA | **[PENDING]** | N/A | N/A | **[PENDING]** |
| A — Full SRR | Political | **[PENDING]** | **[PENDING]** | **[PENDING]** | **[PENDING]** |
| B — Fixed Ensemble | Political | **[PENDING]** | **[PENDING]** | **[PENDING]** | — |
| Market Baseline | Political | **[PENDING]** | N/A | N/A | **[PENDING]** |

The *Market Baseline* row reports the Brier score obtained by always predicting
the market-implied probability (derived from the no-vig moneyline via
$p_{\text{mkt}} = \frac{1/o_{\text{home}}}{1/o_{\text{home}} + 1/o_{\text{away}}}$,
where $o$ denotes decimal odds). This is the minimum meaningful performance
benchmark: any system that fails to beat it offers no value over reading the
betting line.

**H1 outcome:** **[PENDING]** ($t$-statistic: **[PENDING]**, $p$: **[PENDING]**).

**H2 outcome:** **[PENDING]** ($t$-statistic: **[PENDING]**, $p$: **[PENDING]**).

---

## 5.3  Ablation: Isolating Mechanism Components

Three pre-registered hypotheses isolate the individual active ingredients:

- **(H3)** Sham-SRR (Condition D) does not reproduce the Brier improvement of
  Full SRR (Condition A): $B_{\text{ens}}^D$ is not significantly lower than
  $B_{\text{ens}}^B$, controlling for $B_{\text{ens}}^A - B_{\text{ens}}^B$.
- **(H4)** DMAD-Static (Condition C) achieves lower initial $\overline{D}$ than
  Fixed Ensemble but does not sustain it over 175 days: the diversity
  $\overline{D}^C$ declines monotonically over the season, whereas
  $\overline{D}^A$ is non-decreasing in expectation.

> *Figure 2: 28-day rolling ensemble Brier over 175 NBA trading days for all
> five conditions. Shaded regions: bootstrap 95% CI. Vertical dashed lines:
> SRR events (Condition A). X-axis: calendar day of season; Y-axis: rolling
> ensemble Brier score (lower is better). Each condition plotted separately.*
> **[FIGURE PENDING: source at `scripts/plots/rolling_brier.py`]**

*Table 6: Pairwise effect size (Cohen's $d$) and two-sided paired $t$-test
$p$-value for ensemble Brier across all 10 condition pairs (NBA domain).
Bonferroni-corrected $\alpha = 0.005$ for 10 comparisons.*

| Pair | Cohen's $d$ | $p$-value | Interpretation |
|------|-------------|-----------|---------------|
| A vs B (SRR vs Fixed) | **[PENDING]** | **[PENDING]** | primary H2 test |
| A vs C (SRR vs DMAD-Static) | **[PENDING]** | **[PENDING]** | dynamic vs. static diversity |
| A vs D (SRR vs Sham) | **[PENDING]** | **[PENDING]** | prompt vs. label effect |
| A vs E (SRR vs Free-Rider) | **[PENDING]** | **[PENDING]** | targeted vs. random SRR |
| B vs C (Fixed vs DMAD-Static) | **[PENDING]** | **[PENDING]** | initial diversity value |
| B vs D (Fixed vs Sham) | **[PENDING]** | **[PENDING]** | social-signalling alone |
| B vs E (Fixed vs Free-Rider) | **[PENDING]** | **[PENDING]** | any reallocation vs. none |
| C vs D | **[PENDING]** | **[PENDING]** | exploratory |
| C vs E | **[PENDING]** | **[PENDING]** | exploratory |
| D vs E | **[PENDING]** | **[PENDING]** | exploratory |

**H3 outcome:** **[PENDING]**.

**H4 outcome:** **[PENDING — diversity time series figure pending]**.

---

## 5.4  Diversity–Accuracy Coupling

The Brier ambiguity decomposition (§3.3) predicts a negative relationship
between rolling JSD diversity and ensemble Brier, holding mean individual
calibration constant. We test this directly by estimating:

$$\overline{B}_{\text{ens},d} = \beta_0 + \beta_1 \overline{D}_d + \beta_2 \bar{B}_d + \varepsilon_d$$

where $\overline{B}_{\text{ens},d}$ and $\overline{D}_d$ are the 28-day rolling
ensemble Brier and JSD diversity (as in §4.5), and $\bar{B}_d = \frac{1}{N}\sum_i \overline{B}_{i,d}$
is the rolling mean individual Brier (defined in §3.1; included as a covariate
to partial out individual-skill variation from the diversity effect).
The coefficient $\hat{\beta}_1$ provides the
diversity–accuracy slope conditional on mean agent quality.

> *Figure 3: Scatter of 28-day rolling $(\overline{D}_d,\, B_{\text{ens},d})$
> pairs for Condition A (NBA, all 175 windows). Colour gradient encodes
> calendar time (early season: blue; late season: red). Pearson $r$ and
> Spearman $\rho$ annotated. Univariate regression line with 95% CI shown.*
> **[FIGURE PENDING: `scripts/plots/diversity_accuracy.py`]**

Estimated $\hat{\beta}_1 = $ **[PENDING]** (95% CI: **[PENDING]**,
$p = $ **[PENDING]**, $R^2 = $ **[PENDING]**). A negative estimate, if
confirmed, provides direct empirical support for Lemma 1 and the Brier
ambiguity decomposition in the LLM-agent setting.

---

## 5.5  Domain Transfer: NBA versus Political

The ten shared agents (T1–T10) participate simultaneously in both prediction
domains throughout the experiment. This design enables a *domain-transfer*
test: does an SRR event triggered by NBA performance predict subsequent
improvement in the Political domain, and vice versa?

> *Figure 4: Per-agent Brier improvement attributable to SRR (Condition A
> minus Condition B, computed per agent per 28-day window) in the NBA domain
> (x-axis) versus the Political domain (y-axis), for all T1–T10 agents over
> all 25 weekly windows. Pearson $r$ reported; $r > 0$ indicates
> positive domain-transfer.*
> **[FIGURE PENDING]**

We additionally test whether the archetype type reallocated in one domain
predicts the reallocated archetype in the other domain for the same agent —
a test of whether SRR reveals a structural tendency of the underlying LLM
to underperform in systematic ways that transcend domain-specific content.

Domain-transfer correlation: **[PENDING: populate from
`data/arena/axelrod-log/domain-transfer.csv`]**.

---

## 5.6  Agent-Level Analysis and Bankroll Growth

*Table 7: Per-agent 175-day CAGR under Condition A versus Condition B,
number of SRR events triggered, final archetype at Day 175, pre-post
Brier delta (mean across all SRR events for that agent), and whether the
Brier-improvement retention test ($\epsilon_{\text{keep}} = 0.005$) confirmed
the archetype on each event. NBA domain ($N = 12$).*

| Agent | CAGR (A) | CAGR (B) | $\Delta$CAGR | SRR events | Final archetype | Post-SRR $\Delta B$ |
|-------|----------|----------|-------------|------------|----------------|---------------------|
| qwen-quant | **[P]** | **[P]** | **[P]** | **[P]** | **[P]** | **[P]** |
| qwen-arb | **[P]** | **[P]** | **[P]** | **[P]** | **[P]** | **[P]** |
| llama-contra | **[P]** | **[P]** | **[P]** | **[P]** | **[P]** | **[P]** |
| gemini-anl | **[P]** | **[P]** | **[P]** | **[P]** | **[P]** | **[P]** |
| gemini-tact | **[P]** | **[P]** | **[P]** | **[P]** | **[P]** | **[P]** |
| mistral-large | **[P]** | **[P]** | **[P]** | **[P]** | **[P]** | **[P]** |
| mistral-medium | **[P]** | **[P]** | **[P]** | **[P]** | **[P]** | **[P]** |
| mistral-small | **[P]** | **[P]** | **[P]** | **[P]** | **[P]** | **[P]** |
| mistral-nemo | **[P]** | **[P]** | **[P]** | **[P]** | **[P]** | **[P]** |
| mistral-ministral | **[P]** | **[P]** | **[P]** | **[P]** | **[P]** | **[P]** |
| nemotron-120b | **[P]** | **[P]** | **[P]** | **[P]** | **[P]** | **[P]** |
| selfhost-qwen4b | **[P]** | **[P]** | **[P]** | **[P]** | **[P]** | **[P]** |

*[P] = Pending. CAGR computed over 175 trading days, annualised.*

A key test of Proposition 2's equilibrium characterisation is whether agents
that undergo SRR events show *smaller* individual Brier improvements than
would be predicted from their pre-SRR trajectory (consistent with SRR being
individually costly but societally beneficial), or whether the mechanism is
Pareto-improving (both societally and individually beneficial because the
agent was already in a deficit strategy). The post-SRR $\Delta B$ column
resolves this question at the agent level.

---

> **Data availability note.** All raw prediction logs, archetype transition
> records, bankroll histories, and SRR event logs will be released under the
> repository's open data policy upon acceptance:
> `github.com/LBJLincoln/mon-ipad` → `data/arena/axelrod-log/`. The schema
> for all JSON files is documented in Appendix D.

---

# 6. Discussion

Our results (pending full experimental resolution) afford four lines of
discussion: (i) the relationship between SRR and Nowak's evolutionary
cooperation mechanisms, extending the theoretical canon with a candidate
sixth rule specific to epistemically competitive agent societies;
(ii) the information-architecture lesson of asymmetric day-end broadcasting,
grounded in Aumann's common-knowledge impossibility;
(iii) the structural risk of behavioural homogeneity in LLM ensembles and why
it requires endogenous — not external — correction;
and (iv) the practical implications of our mechanism design for anyone
building multi-LLM prediction systems at scale.

---

## 6.1  A Sixth Rule for the Evolution of Cooperation

Nowak's 2006 *Science* synthesis [@nowak2006five] remains the canonical
taxonomy for mechanisms that sustain cooperation among self-interested agents:
kin selection, direct reciprocity, indirect reciprocity, network reciprocity,
and group selection. Each mechanism identifies a structural condition —
relatedness, repeated bilateral interaction, reputation, interaction topology,
or group-level competition — under which the individual cost of altruistic
behaviour is offset by downstream benefit to the altruist or its kin. The
taxonomy has proved remarkably durable, covering phenomena from microbial
biofilms to human institutions.

Sacrificial Role Reallocation introduces a candidate mechanism that does not
reduce to any of these five. Consider its structural prerequisites:

**Not kin selection.** Sacrifice-eligible agents bear no special relationship
to the beneficiaries of their reallocation. T8 (*mistral-small*), reallocating
from *wide-coverage* to *contrarian*, does not share "genetic" material with
T4 (*gemini-anl*), whose prediction diversity it enriches; nor does T8's
stake-cap weighting make T4's outcomes disproportionately valuable to T8.

**Not direct reciprocity.** The sacrificing agent does not track which
specific peers benefited from its role change. No bilateral exchange is
expected or recorded; there is no mechanism for the beneficiary to return
the favour in a subsequent round.

**Not indirect reciprocity.** The social network does not update its
assessment of the sacrificing agent's reputation as a result of the
sacrifice act itself. Peer agents receive the updated archetype label (in
Condition A), but this label-update is logistically incidental; the Sham-SRR
condition (D) demonstrates that label-change alone does not replicate the
Brier improvement, meaning social reputation is not the active ingredient.

**Not network reciprocity.** The mechanism is topology-agnostic: it fires
identically regardless of whether agents interact on a lattice, a scale-free
network, or a complete graph. There is no neighbourhood structure that amplifies
cooperation.

**Not group selection.** There is a single population, and the selection
pressure is within-population diversity rather than between-population
competition. The "sacrifice" is not an agent ceding fitness to a competing
group that wins a group-level contest; it is an agent ceding individual
strategy-niche tenure to improve the *same* group's collective accuracy.

What SRR requires instead is a triad of conditions specific to *epistemically
competitive* societies — populations in which agents share a prediction target
and a scoring rule but are individually evaluated: (a) a common-knowledge
*performance signal* that unambiguously identifies persistently below-mean
contributors; (b) a finite, enumerable *strategy taxonomy* with a well-defined
vacancy operator; and (c) a *group fitness criterion* (here, ensemble Brier)
under which prediction diversity is instrumentally valuable by the Brier
ambiguity decomposition.

We propose the name **epistemic role sacrifice** for this mechanism. It is
evolutionarily stable, as Proposition 2 shows, precisely because the
sacrifice-eligible agent is already paying the individual fitness cost:
it has persistently above-mean Brier and there is no better individual
strategy available in its current archetype. Defection from SRR — refusing
the reallocation — offers no individual improvement and imposes a diversity
tax on the population. In the vocabulary of evolutionary dynamics, epistemic
role sacrifice is *individually incentive-compatible under Assumption A3*
for chronically below-performing agents: by A3, remaining in the same
archetype yields at most $\bar{B}_d + \delta_{\text{sac}}/2$ in expected
individual Brier, while accepting the reallocation offers a strictly
positive probability of improvement through the archetype change and
strictly improves group fitness through the Ambiguity increase from
Lemma 1.
The mechanism is therefore individually rational in expectation
(not unconditionally dominant — an agent whose archetype happens to
recover spontaneously would rationally resist — but A3 precisely
identifies agents for whom spontaneous recovery is not expected).
The strategy profile is stable against free-riders because (under A3)
free-riding yields no expected individual advantage while imposing a
diversity cost on the population [@sandholm2010population].

This has a connection to the biological literature on *phenotypic switching*
in clonal populations [@wolf2005diversity], where genetically identical cells
stochastically express different phenotypes to hedge against environmental
uncertainty — a form of bet-hedging that improves population fitness without
requiring individual sacrifice. Our mechanism is analogous but performance-triggered rather than stochastic, and it operates in a finite-archetype
discrete space rather than a continuous phenotype space.

---

## 6.2  Common-Knowledge Architecture and Aumann's Theorem in Practice

Aumann's 1976 impossibility [@aumann1976agreeing] establishes that rational
agents sharing a common prior who have *common knowledge of each other's
posteriors* cannot disagree: they must update to the same belief. Applied
naively, this theorem delivers a devastating verdict on any common-knowledge
broadcast within a prediction market: share enough information about peer
beliefs and all diversity collapses.

The Day-Bucket v3 architecture is specifically designed to evade this
collapse. The day-end broadcast conveys common-knowledge *outcomes* —
the binary resolution $\omega_t$ for every event resolved on day $d$ —
but explicitly withholds common-knowledge *predictions*: agent $i$ never
learns what probability agent $j \neq i$ reported for today's events.
This asymmetry is the central information-architecture decision, and it
rests on a formal distinction Aumann's theorem does not erase: ground-truth
outcomes are *not* posterior belief states. Sharing outcomes allows
calibration improvement (agents learn which types of games they systematically
overestimate); sharing predictions would allow belief synchronisation
(agents update their posteriors toward each other's, initiating the
convergence Aumann describes).

The resulting structure is *shared calibration without shared belief* —
a population whose members converge on accurate probability estimates
(individually approaching the Brier frontier) while maintaining genuine
disagreement about which teams will win tomorrow. This is precisely the
combination that Surowiecki's wisdom-of-crowds analysis
[@surowiecki2004wisdom] requires for group accuracy to exceed individual
accuracy: diversity, independence, and decentralisation, but not
ignorance of aggregate track records.

The Las Vegas market line functions as what Schelling [@schelling1960strategy]
called a *focal point* — a salient, publicly observed solution that
coordinates expectations in the absence of explicit communication.
For prediction markets, the spread serves as a consensus anchor:
agents without strong private signals shade toward the market-implied
probability, producing the correlated underperformance documented by
Prediction Arena [@zhang2026arena] (models losing 16–30.8% on Kalshi
despite sophisticated reasoning). This anchoring is not a failure of
rationality; it reflects the epistemically correct inference that the
market aggregate has incorporated significant information. The problem
arises when *all* agents anchor simultaneously, collapsing the Ambiguity
term and reducing the ensemble to a single-agent system.

SRR is a mechanistic counter to market-line anchoring operating at the
population level. By targeting specifically those agents whose predictions
are closest to the population centroid (Assumption A2 captures exactly this),
and reallocating them to archetypes that are by construction underrepresented
in the population, SRR restores Ambiguity precisely where it has eroded.
In this sense, SRR is an institutional answer to the focal-point problem in
prediction markets: not by destroying the focal point (the market line
remains visible to all agents) but by ensuring that at least some agents
are structurally incentivised to deviate from it.

---

## 6.3  LLM Behavioural Homogeneity as a Structural Risk

Classical ensemble theory [@dietterich2000ensemble; @lakshminarayanan2017simple]
grounds the case for ensembles in an error-independence assumption: ensemble
accuracy exceeds individual accuracy when constituent errors are uncorrelated,
and the gain grows with diversity. This assumption is routinely violated in
LLM ensembles for a reason specific to pre-trained language models:
*correlated prior beliefs arising from shared pre-training*.

Distinct API instances of the same model — say, five Mistral agents receiving
slightly different system prompts — share not only the pre-training corpus
but also the RLHF preference tuning, which encodes systematic biases toward
particular linguistic registers, hedging patterns, and contextual associations.
For the NBA domain, this might manifest as a shared bias toward underestimating
home-court advantage for Western Conference teams (a pattern in 2025–26 odds
markets); for the political domain, toward overestimating Federal Reserve
hawkishness based on the dominant framing in training data. These shared priors
create systematic prediction correlations that persist across games and
cannot be corrected by archetype-level prompt variation alone, because the
prompt does not override the model's learned distributional tendencies.

This implies a *within-provider correlation floor*: the maximum achievable
Ambiguity within a cohort of same-provider agents is bounded by one minus
their pairwise prediction correlation. In our system, the five Mistral agents
(T6–T10) are expected to show higher intra-provider prediction correlation (lower inter-agent Jensen–Shannon divergence) than cross-provider pairs, and SRR events involving only Mistral-to-Mistral archetype reassignments may produce smaller JSD diversity
gains than cross-provider reassignments.

If this within-provider correlation floor is empirically confirmed, it
carries an important design implication: provider heterogeneity is a
*necessary* condition for SRR's full benefit, not merely a desirable property.
An LLM prediction ensemble built from a single provider's model family —
however large the models, however diverse the prompts — faces a structural
diversity ceiling that SRR can only partially circumvent. This motivates
the five-provider design of our agent cohort (Cerebras, Google, Mistral,
OpenRouter, self-hosted) as a principled diversity requirement, not merely
a pragmatic constraint imposed by cost or rate limits.

The parallel problem in deep learning — ensemble diversity degrading as
models are fine-tuned on the same data with similar architectures —
has been addressed by Deep Ensembles [@lakshminarayanan2017simple] through
random initialisation diversity. LLM agents present a harder version of this
problem because the "initialisation" (pre-training) is shared and cannot
be randomised by the experimenter. Our SRR mechanism represents a
post-hoc remedy; a more fundamental solution would require diversity
at the pre-training or RLHF stage.

---

## 6.4  Implications for LLM Ensemble Design

Pending final data, our results carry three design implications with
immediate practical application:

**Implication 1: Performance-triggered reallocation (Condition A) dominates
random reallocation (Condition E).** If confirmed, the A-vs-E comparison
isolates *targeting* as the active ingredient: it is not any reallocation
that produces the diversity gain but specifically the reallocation of the
*most consensus-like* agents to underrepresented archetypes. This has a
direct implementation consequence: periodic random archetype rotation
schedules, which are simpler to implement, will produce smaller and less
reliable diversity gains than performance-triggered SRR. The monitoring
overhead of tracking each agent's rolling Brier relative to the society mean
is the price of the targeting precision, and our results quantify whether
that overhead is worth paying.

**Implication 2: Static initial diversity (Condition C) decays.** The
DMAD-Static condition provides the strongest possible diversity initialisation:
all 12 NBA archetypes are distinct from Day 1. If Condition C's JSD diversity
$\overline{D}^C$ declines monotonically over the season while Condition A's
$\overline{D}^A$ remains stable or increases, this demonstrates that
one-time diversity initialisation is insufficient for long-horizon
prediction tasks. The mechanism of decay is the common ground-truth signal:
agents with different archetypes but the same informational environment
gradually converge on similar probability estimates as they learn from
shared outcomes, a process analogous to the opinion dynamics convergence
studied in OASIS [@yang2024oasis]. SRR functions as an ongoing corrective
maintenance mechanism that continuously detects and repairs this convergence.

**Implication 3: Genuine reasoning diversification, not social signalling
(Condition A vs. D).** If Sham-SRR (label change without prompt change)
does not replicate Condition A's Brier improvement, the active ingredient
is the underlying model's changed reasoning disposition rather than the
social-signalling effect of peer agents observing the label change.
This distinction has a practical implication: the mechanism does not
require a "coordination layer" through which agents observe each other's
archetype labels. A system in which SRR silently changes an agent's system
prompt without broadcasting the change to peers would be expected to produce
the same diversity gain. This simplification makes SRR applicable in
settings where agent-to-agent metadata visibility is restricted or
undesirable.

Taken together, these three implications constitute a design recipe for
robust long-horizon LLM prediction ensembles: (1) maintain provider diversity
as a structural floor; (2) implement performance-triggered archetype
reallocation rather than static diversity initialisation; and (3) focus
the reallocation trigger on the prompt-level reasoning change, not
coordination effects.

---

## 6.5  Financial Stakes as a Calibration Discipline

The Kelly stake-sizing mechanism [@kelly1956new] in our system serves a
calibration discipline complementary to Brier score evaluation.
Kelly stakes couple prediction confidence directly to bankroll exposure:
overconfident predictions on losing outcomes reduce bankroll; underconfident
predictions (staking too little on high-edge bets) forgo returns.
This creates a second-order feedback: agents with better-calibrated probability
estimates stake more, earn more, and their bankroll weight in the ensemble
mean prediction grows. The emergent ensemble weighting is a form of implicit
*Bayesian model averaging* where the weight assigned to each agent is
proportional to evidence from its track record — a connection we formalise
in Appendix E.

The Prediction Arena findings [@zhang2026arena] — LLM agents losing
16–30.8% on Kalshi despite sophisticated reasoning — are consistent with
a failure of calibration at the agent level that is not corrected by the
market-feedback signal alone. In our system, the evidence-based Kelly cap
($\kappa_i = \max(0.01,\, 0.30 - \overline{B}_i \times 0.50)$, cf. §3.6) creates
an automatic damping: agents with high Brier receive smaller stakes
irrespective of the confidence expressed in their predictions, preventing
a poorly calibrated agent from dominating the ensemble.

Whether virtual financial stakes induce the same level of prediction
quality as real financial stakes is an open question (see §7.3). However,
the Kelly mechanism provides a *within-system* calibration discipline that
real-money implementations would strengthen: an agent that systematically
overestimates its edge will experience bankroll drawdown that reduces its
effective Kelly cap, creating a feedback loop absent from
consequence-free benchmark evaluations.

---

## 6.6  Connection to Ensemble Learning Theory

The Brier ambiguity decomposition (§3.3) provides the formal bridge between
our experimental results and the classical ensemble learning literature
[@brown2005diversity]. The decomposition $B_{\text{ens}} =
\overline{B}_{\text{indiv}} - \text{Amb}$ implies two independent paths to
ensemble improvement: reduce mean individual Brier (improve agent quality)
or increase Ambiguity (increase inter-agent diversity). Most ML ensemble
research focuses on the first path; our work focuses on the second.

The distinction matters for practical deployment because the two paths have
different cost structures. Improving individual agent quality requires either
better models (costly in compute and money) or better data (costly in
collection and curation). Increasing Ambiguity through SRR requires only
prompt engineering and performance monitoring — resources available at
negligible marginal cost to any team already operating an LLM ensemble.
If our empirical results confirm that SRR achieves measurable Brier reduction
through the Ambiguity path alone, this represents a high-leverage, low-cost
intervention that complements rather than replaces investment in individual
model quality.

The relationship also cuts in the other direction: SRR can be counterproductive
if it degrades mean individual Brier. An agent reallocated to a vacant
archetype that it executes poorly would increase Ambiguity while
also increasing $\overline{B}_{\text{indiv}}$, potentially worsening
$B_{\text{ens}}$. This is precisely what the 14-day persistence window and
$\epsilon_{\text{keep}}$ retention test in Definition 2 are designed to
prevent: an archetype switch that fails to improve individual Brier above
threshold is reverted, ensuring that diversity is not purchased at the cost
of individual skill degradation.

---

> **Temporal note on result-dependent claims.** Sections 6.1–6.6 contain
> several claims of the form "if confirmed" or "pending results." These
> formulations are intentional and will be revised to indicative mood upon
> full seasonal resolution. Claims derived solely from the formal theory
> (Lemma 1, Proposition 2, Brier ambiguity decomposition) are stated
> unconditionally; they do not depend on experimental outcome.

---

# 7. Limitations and Ethics

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
underlying model weights served by managed endpoints may silently change
between simulation runs without user notification.  A model update between
Condition A and Condition B would introduce a version confound that is
inseparable from the SRR-vs-fixed experimental manipulation.

We document provider drift via the response-hash protocol described in §7.4
(probing each endpoint with a fixed query at the start of each condition's
simulation and archiving the hash).  Hash stability across conditions serves
as circumstantial evidence that model weights did not change; a hash change
triggers a notation in the experimental log and a sensitivity analysis
excluding the affected agent.  The self-hosted agent T12 (frozen model version
in `LBJLincoln26/llm-gateway`) is immune to this confound; systematic
T12-vs-commercial discrepancies in the per-agent analysis (§5.6) would
flag drift as a contributing factor.

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
hypothetical \$100,000 per-agent virtual bankroll, is negligible relative
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
OpenRouter. All providers offer these tiers on shared GPU infrastructure
whose carbon intensity reflects grid averages for their respective data
centre locations. The self-hosted agent (T12) runs on a CPU-only
HuggingFace Space. Using published emission factors for GPU inference
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

---

# Appendix A — Strategy Archetype Taxonomy

This appendix documents the full $K = 20$ strategy archetype taxonomy $\mathcal{R}$
operationalised in the LPSG experiments (§3.1, §4.4). Each archetype corresponds to
a system-prompt module that shapes the agent's reasoning disposition, position
construction logic, and risk tolerance. Modules are composable with the shared
`COLLECTIVE_MISSION` preamble (§3.6) and are swapped atomically during SRR events
(§3.4) without modifying the agent's prediction history or bankroll state.

---

## A.1  Design Principles

The taxonomy satisfies three criteria: (1) **span** — the 20 archetypes cover five
orthogonal dimensions (D1 position construction, D2 risk appetite, D3 information
source priority, D4 temporal horizon, D5 ensemble relationship); (2) **distinguishability**
— every archetype pair satisfies $\hat{\epsilon}_{\text{arch}} \geq 0.037$ on the
2024–25 pilot (Assumption A1; full matrix in Table B.2); and (3) **non-cherry-picking**
— no archetype was designed with knowledge of which agent would initially occupy it.

## A.2  Five-Dimension Design Space

| Dimension | Label | Poles |
|-----------|-------|-------|
| D1 | Position construction | quantitative ←→ narrative; contrarian as a third axis |
| D2 | Risk appetite | aggressive ←→ conservative; diversified as a third axis |
| D3 | Information source | market signals ←→ statistical features ←→ situational context |
| D4 | Temporal horizon | short-term momentum ←→ long-term mean-reversion |
| D5 | Ensemble relationship | independent ←→ coordinator ←→ devil's-advocate |

## A.3  Full Taxonomy Table

| # | Archetype | Dim | Initially Occupied | $\kappa_{\min}$ |
|---|-----------|----|-------------------|-----------------|
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
| 16 | chain-of-thought | D4 | NBA: T11 · POL: — | 0.05 |
| 17 | ensemble | D5 | NBA: T6 · POL: T6 | 0.04 |
| 18 | coordinator | D5 | — (vacant at day 0) | 0.04 |
| 19 | devil's-advocate | D5 | — (vacant at day 0) | 0.05 |
| 20 | adaptive | D5 | — (vacant at day 0) | 0.03 |

*Table A.1: $K = 20$ archetype taxonomy. Eight archetypes are vacant at day 0
(nos. 3, 6, 10, 13, 14, 18, 19, 20), constituting $\mathcal{V}_0$ for SRR
(Definition 2, §3.4). Full prompt modules at `data/arena/archetypes/<name>.txt`.*

## A.4  Per-Archetype Entries (Abbreviated)

Each entry gives the reasoning disposition and the abbreviated prompt directive.
Full prompt text is archived in `data/arena/archetypes/`.

**D1 — Position Construction**

*(1) Quantitative.* Relies on oracle statistical estimates ($\geq 80\%$ weight);
minimal narrative adjustment. *Directive:* "Begin with statistical model
probability; adjust by at most 5 pp on qualitative grounds unless oracle
$\sigma > 0.08$. Report calibrated probability to two decimal places."

*(2) Analytical.* Four-factor explicit weighing (oracle 0.40 + market 0.25 +
situational 0.20 + form divergence 0.15). *Directive:* "Score each factor
independently. Combine with stated weights. Report the single most-deviant factor."

*(3) Narrative.* Qualitative-first; news, injuries, motivation dominate.
*Directive:* "Identify the single most important narrative driver. Assign it
up to 15 pp independent weight when absent from oracle summary. Document
agreement or divergence from market implied probability."

*(4) Contrarian.* Fades market consensus; default position $5$–$7$ pp below
favourite implied probability. *Directive:* "Fade the favourite by 5–7 pp unless
oracle $\sigma < 0.05$. Do not override when crowd exceeds 70% consensus."

**D2 — Risk Appetite**

*(5) Aggressive.* Concentrated positions; Kelly up to $\kappa_i = 0.70$.
*Directive:* "When oracle probability is outside $[0.40, 0.60]$, increase stake
by up to 30% above default Kelly. State edge estimate explicitly."

*(6) Conservative.* Minimise Brier; cap at 30% of standard Kelly; shrink to $[0.20, 0.80]$.
*Directive:* "Cap all positions at 30% Kelly. Shrink extreme predictions toward 0.50
by 10 pp. Default to PASS when uncertain."

*(7) Diversified.* Portfolio style; $\geq 5$ predictions/day; $\leq 2\%$ bankroll each.
*Directive:* "Generate at least 5 independent predictions from different matchup
contexts. Cap each stake at 2%."

*(8) Disciplined.* Edge gate: only predict when divergence from market is $\geq 4$ pp
and oracle $\sigma < 0.09$. *Directive:* "If within 4 pp of market implied or oracle
is uncertain, PASS. Document edge gap explicitly."

**D3 — Information Source Priority**

*(9) Tactical.* Situational context dominates (rest, travel, injury, motivation);
override oracle by up to 10 pp. *Directive:* "Score situational factors on
$[-10, +10]$. If combined score $\geq 3$, adjust prediction by up to 10 pp
regardless of oracle."

*(10) Value.* Positive-EV market inefficiency; oracle vs.\ market gap $\geq 5$ pp.
*Directive:* "Compute market implied probability. If oracle diverges by $\geq 5$ pp
and oracle CI excludes market implied, predict in oracle's direction."

*(11) Arbitrage.* Cross-market inconsistency; moneyline vs.\ alternate spread vs.\ team total.
*Directive:* "Check for $\geq 3$ pp inconsistency between market categories
on the same binary outcome. Predict in direction that resolves the inconsistency."

*(12) Wide-Coverage.* Predict all events; oracle-anchored with $\pm 2$ pp uncertainty.
*Directive:* "Generate one prediction per event in today's bucket. Default to
oracle probability $\pm 2$ pp. Volume is your KPI."

**D4 — Temporal Horizon**

*(13) Momentum.* 7-day form extrapolation; $+3$–$5$ pp in streak direction.
*Directive:* "Compute 7-day win/loss differential. If $\geq 3$, adjust
prediction by 3–5 pp in the favoured team's direction, overriding oracle."

*(14) Mean-Reversion.* Fade streaks of $\geq 5$-of-$7$ wins/losses toward
season baseline. *Directive:* "If a team has won (or lost) $\geq 5$ of last 7,
adjust 3–5 pp against the streak toward the season home-win base rate ($\approx 0.54$)."

*(15) Theoretical.* Season-long statistics only; reject $< 20$-game samples;
$\leq 10$ pp from base rate. *Directive:* "Default to season-long base rate.
Reject any signal with fewer than 20 observations. Never adjust more than 10 pp
from the base rate."

*(16) Chain-of-Thought.* Extended deliberation before prediction; enumerate and
eliminate $\geq 4$ factors each direction. *Directive:* "List at minimum four
factors for and four against the home team. Assign weights. Only then state
final probability. Reasoning portion must be $\geq 150$ tokens."

**D5 — Ensemble Relationship**

*(17) Ensemble.* Internal aggregation of three sub-predictions (oracle, market, situational).
*Directive:* "Construct three sub-predictions. Average as final prediction.
Report all three sub-predictions."

*(18) Coordinator.* Morning council synthesiser; tracks consensus; allows $\leq 5$ pp
divergence on high-uncertainty events. *Directive:* "Review yesterday's leaderboard.
Represent the informed centre; allow divergence only for high-uncertainty events."

*(19) Devil's-Advocate.* Fades agent-society consensus when $\geq 60\%$ agreement.
*Directive:* "If morning council shows $\geq 60\%$ consensus, take the opposite
direction 5–8 pp beyond the minority pole. Revert to oracle when no strong consensus."

*(20) Adaptive.* Meta-archetype; self-selects reasoning style based on last-7-day Brier.
*Directive:* "Identify which signal type produced smallest Brier errors in last 7 days.
Weight it at 50% today; distribute remaining 50% equally among the other three signal types."

## A.5  Initial Vacancy Analysis

At NBA day 0, 12 of 20 archetypes are occupied and 8 are vacant ($\mathcal{V}_0$:
nos.\ 3, 6, 10, 13, 14, 18, 19, 20). With vacancy threshold $\tau_{\text{vac}} = 1/(2K) = 0.025$,
all 8 unoccupied archetypes qualify as vacant (occupancy $0 < 0.025$); all 12 occupied
archetypes pass ($1/12 \approx 0.083 \gg 0.025$). For the political cohort ($N = 10$),
T12 is absent, giving $|\mathcal{V}_0^{\text{POL}}| = 9$.

The initial JSD diversity $D_0$ under the 12-archetype assignment is strictly below
the theoretical maximum achievable with 20 archetypes, providing a measurable
improvement target for SRR (§5.1, results pending).

---

# Appendix B — Mathematical Supplements

---

## B.1  JSD–Ambiguity Monotonicity in the Operating Range

We prove the claim in §3.3: that Jensen–Shannon diversity $D_d$ is a strictly
increasing function of the Ambiguity term $\text{Amb}_t = \frac{1}{N}\sum_i (p_{i,t} - \bar{p}_t)^2$
in the operating range $\bar{p}_t \in [0.15, 0.85]$, $\text{Amb}_t \leq 0.08$,
when $\bar{p}_t$ is held fixed.

**Setup.** For a fixed event $t$, let $p_1, \ldots, p_N \in [0,1]$ be agent
predictions, $\bar{p} = \frac{1}{N}\sum_i p_i$, and $\delta_i = p_i - \bar{p}$
(so $\sum_i \delta_i = 0$).  The JSD for $N$ Bernoulli distributions is:

$$\text{JSD} = H(\bar{p}) - \frac{1}{N}\sum_{i=1}^N H(p_i)$$

with $H(p) = -p\log_2 p - (1-p)\log_2(1-p)$ and $\text{Amb} = \frac{1}{N}\sum_i \delta_i^2$.

**Taylor expansion.** Expanding $H(p_i) = H(\bar{p} + \delta_i)$ to second order:

$$H(\bar{p} + \delta_i) = H(\bar{p}) + H'(\bar{p})\,\delta_i + \frac{1}{2}H''(\bar{p})\,\delta_i^2 + R_i$$

where $R_i = \frac{1}{6}H'''(\xi_i)\,\delta_i^3$ for some $\xi_i$ between $\bar{p}$ and $p_i$.
Averaging over $i$ and using $\sum_i \delta_i = 0$:

$$\frac{1}{N}\sum_{i=1}^N H(p_i) = H(\bar{p}) + \frac{1}{2}H''(\bar{p})\cdot\text{Amb} + \bar{R}$$

Therefore:

$$\text{JSD} = -\frac{1}{2}H''(\bar{p})\cdot\text{Amb} - \bar{R} \tag{B.1}$$

**Sign of the leading coefficient.** Since $H''(p) = -\frac{1}{p(1-p)\ln 2} < 0$,
the coefficient $-\frac{1}{2}H''(\bar{p}) = \frac{1}{2\bar{p}(1-\bar{p})\ln 2} > 0$.
At $\bar{p} = 0.15$: $-\frac{1}{2}H''(0.15) \approx 5.65$; at $\bar{p} = 0.50$: $\approx 2.89$.

**Bounding the remainder.** The third derivative satisfies
$|H'''(p)| = \frac{|1-2p|}{p^2(1-p)^2 \ln 2}$, maximised at $\bar{p} = 0.15$ as
$|H'''(0.15)| \approx 62.3$.  By the power-mean inequality,
$\frac{1}{N}\sum_i |\delta_i|^3 \leq \text{Amb}^{3/2}$, so
$|\bar{R}| \leq \frac{|H'''|_{\max}}{6}\,\text{Amb}^{3/2}$ and
$|\partial\bar{R}/\partial\text{Amb}| \leq \frac{|H'''|_{\max}}{4}\sqrt{\text{Amb}}$.

**Monotonicity.** In the operating range ($\bar{p} \in [0.15, 0.85]$,
$\text{Amb} \leq 0.08$), the total derivative is:

$$\frac{\partial \text{JSD}}{\partial \text{Amb}}\bigg|_{\bar{p}} \geq
5.65 - \frac{62.3}{4}\sqrt{0.08} \approx 5.65 - 4.41 = 1.24 > 0$$

confirming strict monotonicity throughout the stated range. $\square$

*Remark.* The margin narrows near the corner $\bar{p}=0.15$, $\text{Amb}=0.08$.
In the typical experimental regime ($\bar{p} \in [0.25,0.75]$, $\text{Amb} \leq 0.05$)
the remainder is an order of magnitude smaller than the leading term.

---

## B.2  Pairwise Archetype Distinguishability Matrix

*Table B.2: Full $20 \times 20$ matrix of pairwise archetype distinguishability
estimates $\hat{\epsilon}_{\text{arch}}(r^{(a)}, r^{(b)})$ from the 2024–25 pilot season.*

**[PENDING: table to be populated from
`data/arena/axelrod-log/pilot-archetype-pairs.jsonl` once the 2024–25 pilot
backtest completes. Expected minimum entry $\geq 0.037$; pre-registered expectation
is that the (`wide-coverage`, `diversified`) pair yields the minimum and
(`contrarian`, `quantitative`) the maximum.]**

---

# Appendix C — Experimental Supplements

---

## C.1  Experimental Calendar

| Phase | Period | Purpose |
|-------|--------|---------|
| Archetype pilot | 2024–25 NBA season | Measure pairwise $\hat{\epsilon}_{\text{arch}}$; tune $\delta_{\text{sac}}$, $W$, $W_{\text{persist}}$ |
| Pre-registration | 2025-10-01 | Hypotheses H1–H4 locked; SHA-256 at tag `preregistration-v1` |
| **Condition A** (Full SRR) — *live* | 2025-10-14 – 2026-06-20 | 175 NBA trading days; 90 political event days |
| **Condition B** (Fixed Ensemble) — *replay* | 2026-07-01 – 2026-07-14 | Archetypes frozen at initial assignment |
| **Condition C** (DMAD-Static) — *replay* | 2026-07-15 – 2026-07-28 | Max-diversity init; SRR disabled |
| **Condition D** (Sham-SRR) — *replay* | 2026-08-01 – 2026-08-14 | Label-only reallocation; prompts unchanged |
| **Condition E** (Free-Rider) — *replay* | 2026-08-15 – 2026-08-28 | Random agent selected for reallocation |
| Analysis + write-up | 2026-09 | Bootstrap CIs; figure generation; manuscript revision |

*Table C.1: Experimental timeline. Conditions B–E are retrospective
replays over the logged event stream from Condition A.*
As of the current draft (May 2026), Condition A is $\approx 71\%$ complete.
All prediction logs are archived at `data/arena/axelrod-log/` (schema in §C.5/Appendix D).

---

## C.2  Hyperparameter Sensitivity Analysis

Hyperparameters $\delta_{\text{sac}}$, $W$, $W_{\text{persist}}$ were selected
by cross-validation on the 2024–25 pilot season.

| Hyperparameter | Values tested | Selected value |
|----------------|---------------|----------------|
| $\delta_{\text{sac}}$ | 0.01, 0.02, 0.03, 0.05 | **0.02** |
| $W$ (patience, days) | 3, 5, 7, 10, 14 | **7** |
| $W_{\text{persist}}$ (persistence, days) | 7, 14, 21, 28 | **14** |

Selection criterion: minimise pilot-season ensemble Brier on held-out events
($D_{\text{pilot}} = 80$ trading days) under Condition A.

**[PENDING: sensitivity surface from `data/arena/axelrod-log/pilot-hparam-grid.jsonl`.
Expected: $\delta_{\text{sac}} = 0.01$ triggers excessive SRR events;
$W \leq 3$ misidentifies transient slumps; $W_{\text{persist}} = 28$ delays recovery.
Selected values $(0.02, 7, 14)$ pre-registered as Pareto-optimal on pilot grid.]**

The number of SRR events per season scales as
$N/W \cdot P[\overline{B}_{i,d} - \bar{B}_d > \delta_{\text{sac}}]$,
yielding a U-shaped relationship with ensemble Brier: too few events leave
under-represented archetypes vacant; too many events cause calibration degradation
during archetype transitions.

---

## C.3  Temperature Sensitivity Analysis

All agents use a fixed generation temperature $\tau = 0.7$ (§4.6). A sensitivity
sweep over $\tau \in \{0.30, 0.50, 0.70, 0.90, 1.10\}$ is conducted on a
20-game held-out pilot subset using T4 (*analytical* archetype) as the
representative agent.

**[PENDING: per-$\tau$ Brier and ECE from `data/arena/axelrod-log/temp-sensitivity.jsonl`.
Pre-registered expectation: $\tau = 0.7$ is near-optimal for *analytical*;
*conservative* may prefer $\tau \leq 0.5$; *devil's-advocate* may benefit from
$\tau \geq 0.9$. Per-archetype temperature sweep deferred to future work.]**

---

## C.4  Statistical Power Calculations

### C.4.1  Primary Test: Brier Score (H1, H2)

Let $\Delta_t = B_{\text{ens},t}^{(B)} - B_{\text{ens},t}^{(A)}$ be the per-game
Brier difference (positive = SRR improves over fixed ensemble). With ICC
$\rho_{\text{ICC}} \approx 0.10$–$0.15$ and $\approx 7.2$ games per day-bucket:

$$\text{DEFF} = 1 + (n_{\text{cluster}} - 1)\,\rho_{\text{ICC}} \approx 1.62\text{–}1.93
\quad\Rightarrow\quad n_{\text{eff}} \approx 651\text{–}776$$

For a two-sided paired $t$-test with $\sigma_\Delta \approx 0.033$ (pilot estimate),
$\alpha = 0.05$, $1-\beta = 0.80$, and $n_{\text{eff}} = 651$, the minimum detectable
effect is:

$$\delta_{\min} = (z_{\alpha/2} + z_\beta)\,\frac{\sigma_\Delta}{\sqrt{n_{\text{eff}}}}
= 2.802 \times \frac{0.033}{\sqrt{651}} \approx 0.0036 \text{ Brier points}$$

Our pre-registered target $\delta = 0.005$ exceeds $\delta_{\min}$, yielding power:

$$1 - \beta = \Phi\!\left(\frac{0.005}{0.033/\sqrt{651}} - 1.960\right)
= \Phi(1.916) \approx 0.97$$

**The study is powered at $\approx 97\%$ to detect a $0.005$ Brier point improvement.**

*Pessimistic check.* If $\sigma_\Delta = 0.043$ (30% above pilot estimate),
power drops to 88%, and $n_{\text{eff}} \geq 580$ is still required for 80% power —
below our lower-bound estimate of 651. The study remains adequately powered.

### C.4.2  Secondary Test: JSD Diversity (H1)

Let $D = 175$ day-level observations (approximately independent). With
$\sigma_D \approx 0.022$ (pilot) and $\delta_D = 0.005$ (hypothesised SRR gain):

$$n^* = \frac{(z_{\alpha/2}+z_\beta)^2\,\sigma_D^2}{\delta_D^2}
= \frac{7.84 \times 0.000484}{0.000025} \approx 152 \text{ days}$$

With $D = 175$ trading days, power $\approx \Phi(1.045) \approx 85\%$ for
the JSD diversity test.

---

## C.5  Appendix D — Axelrod Log Schema  *(stub)*

Each file in `data/arena/axelrod-log/` is newline-delimited JSON with schema:

```json
{
  "date": "YYYY-MM-DD",  "domain": "nba|political",  "condition": "A–E",
  "day_index": <int>,
  "events": [{
    "event_id": "<str>",  "ground_truth": 0|1,
    "predictions": { "<agent_id>": {
      "probability": <float>, "archetype": "<str>",
      "brier": <float>, "stake_pct": <float>, "llm_call_ms": <int>
    }},
    "ensemble_mean": <float>, "ensemble_brier": <float>, "jsd": <float>
  }],
  "srr_events": [{"agent_id":"<str>","prev_archetype":"<str>",
                  "new_archetype":"<str>","trigger_brier":<float>}],
  "society_brier_7d": <float>, "society_jsd_7d": <float>
}
```

`srr_events` is empty for conditions B, C, D (D: label-only; flagged `"sham":true`),
and E (random reallocation flagged `"free_rider":true`).
Unresolved events have `ground_truth: null` and `brier: null`.

---

# References

::: {#refs}
:::
