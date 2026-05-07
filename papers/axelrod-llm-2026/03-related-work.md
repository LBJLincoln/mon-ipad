# Related Work

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
[@brown2005diversity; @brown2013generalized] states that for convex
loss functions (including the Brier score):

$$\text{Ensemble Loss} = \overline{\text{Individual Loss}} - \text{Ambiguity}$$

where Ambiguity is a non-negative diversity term measuring how much
agents disagree. This result implies that, holding individual agent
skill constant, increasing prediction disagreement *always* reduces
ensemble loss. Our Jensen–Shannon divergence diversity metric (§3.5)
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
the opposite end of the scale spectrum (16 agents), but shares OASIS's
commitment to real-world grounding: unlike OASIS's social-simulation
environment, our arena resolves every event against an exogenous binary
ground truth (game outcomes and political event resolutions), imposing
a calibration discipline that pure social simulations lack.

A critical and underexplored property of all of these systems is
*behavioral homogeneity under shared model families*. When multiple
agents are drawn from the same provider or receive similar prompt
templates, their posterior distributions over actions tend to collapse
— a failure mode the LLM community has begun calling "groupthink"
[@zhou2025dmad] by analogy to social psychology. We treat this as
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
estimates) rather than a discrete answer choice. Section 3.3 formalizes
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
Schelling's later work on focal points [@schelling1960strategy]
provides a further connection: in the absence of explicit coordination,
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
[@quantagents2025, arXiv:2510.04643] simulated multi-agent
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
> were verified against live records as of 2026-04-18. DMAD (Liu et al.,
> ICLR 2025) was published directly through OpenReview (ID: t6QHYUOQL7);
> no arXiv preprint was found. The QuantAgents citation uses
> arXiv:2510.04643 (Du et al., 2025); readers should verify this is the
> intended paper as two works share the "QuantAgents" name
> (see also arXiv:2509.09995 for QuantAgent HFT).
