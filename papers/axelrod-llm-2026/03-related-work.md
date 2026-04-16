# Related Work

We organize prior work along four axes that our framework synthesizes: (§2.1) the
evolutionary game theory of cooperation, (§2.2) LLM multi-agent societies, (§2.3)
prediction markets and AI forecasting, and (§2.4) ensemble diversity and anti-groupthink
mechanisms. We conclude each subsection by articulating the specific gap our work fills.

---

## 2.1 Evolutionary Game Theory and the Emergence of Cooperation

Axelrod's two-round iterated Prisoner's Dilemma (IPD) tournaments [@axelrod1980effective;
@axelrod1980more] are among the most replicated experiments in social science. The
fundamental insight — that *Tit-for-Tat* (TFT), a memory-1 strategy requiring no
background knowledge, outcompetes all submitted alternatives — demonstrates that
cooperation can be *emergent* rather than prescribed. Axelrod's 1984 monograph
[@axelrod1984evolution] extracted five design principles (niceness, retaliation,
forgiveness, non-envy, clarity) that have since influenced mechanism design across economics
[@fudenberg1986folk], international relations [@oye1986cooperation], and biology.

Hamilton's inclusive fitness framework [@hamilton1964genetical] introduced the first
rigorous account of *altruistic sacrifice*: an agent that reduces its own fitness can
nonetheless spread its genes if the fitness benefit to sufficiently related recipients
exceeds the personal cost, weighted by relatedness ($rb > c$, Hamilton's Rule). Maynard
Smith's Evolutionarily Stable Strategy (ESS) concept [@maynardsmith1982evolution]
formalized the stability condition for a monomorphic population: a strategy is evolutionarily
stable if and only if it cannot be invaded by a rare mutant. Critically, ESS analysis
reveals that *mixed* or *polymorphic* equilibria — where multiple strategies coexist — are
often more robust than monomorphic ones, because population diversity reduces invasion
risk [@hofbauer1998evolutionary].

Nowak's landmark *Science* synthesis [@nowak2006five] unified five cooperation mechanisms
(kin selection, direct reciprocity, indirect reciprocity, network reciprocity, group
selection) under a common mathematical umbrella, noting that each requires distinct
informational conditions. Of particular relevance to our work is **network reciprocity**:
cooperation flourishes when agents interact on structured graphs rather than randomly,
because cooperators can form clusters that resist defector invasion. We generalize this
to the LLM setting, where "network structure" is replaced by *strategy archetype
diversity* — agents that occupy distinct niches in strategy space resist collective
homogenization.

Axelrod's later work on the *complexity of cooperation* [@axelrod1997complexity] extended
the framework to adaptive agents with mutable strategies and norm-enforcement mechanisms.
This work is the direct intellectual antecedent of our approach, but it predated LLMs
by two decades and could not anticipate natural-language reasoning as the mechanism for
strategy expression.

**Gap.** Evolutionary game theory provides the normative framework for cooperation and
diversity, but has been applied exclusively to agents with hand-coded strategies in binary
or low-dimensional action spaces. No prior work instantiates evolutionary cooperation
dynamics with LLM reasoning agents in continuous-action, real-world prediction markets.

---

## 2.2 LLM Multi-Agent Societies

The transition from rule-based to LLM-based multi-agent systems has been rapid. CAMEL
[@li2023camel] introduced *role-playing* LLM societies in which pairs of agents —
one playing an AI assistant, one a human user — solve tasks through structured conversation,
demonstrating emergent collaborative behaviors not present in isolated model calls. AutoGen
[@wu2023autogen] generalized this into a flexible multi-agent conversation framework
supporting diverse topologies (chains, stars, hierarchies) and human-in-the-loop
interruption. MetaGPT [@hong2023metagpt] imposed role-specialization with shared memory
artifacts (design documents, code repositories), enabling complex software engineering
pipelines to emerge from specialized agent interactions.

TradingAgents [@liu2024tradingagents] is the closest architectural precursor to our
system. It deploys multiple LLM agents — quantitative analysts, fundamental analysts,
sentiment analysts, a risk manager, and a trading executor — in a hierarchical
communication topology, with each agent receiving structured market data and passing
recommendations downstream. TradingAgents demonstrated that LLM-agent collaboration
outperforms individual models on Sharpe ratio and maximum drawdown in backtests on
historical US equity data. However, TradingAgents (i) studies fixed agent roles with
no reallocation mechanism, (ii) uses synthetic backtests rather than real-time
ground-truth resolution, and (iii) does not measure or optimize population-level
prediction diversity. Our work addresses all three gaps.

OASIS [@yang2024oasis] demonstrated that CAMEL's multi-agent infrastructure scales to
one million agents on real social network topologies (Reddit, Twitter/X), enabling
simulation of information cascades, opinion polarization, and collective action phenomena
at social-network scale. The key lesson from OASIS relevant to our work is that agent
*interaction topology* — not just individual model capability — determines emergent
collective behavior, and that behavioral diversity is fragile without deliberate
maintenance mechanisms.

Agent Market Arena [@ma2025agentmarket] provides the first lifelong, real-time
benchmark for LLM-based trading agents across multiple live markets. Our work differs
in that we emphasize prediction calibration (Brier score), diversity dynamics
(Jensen–Shannon divergence), and the *mechanism* by which diversity is maintained —
whereas AMA focuses on return metrics and market microstructure.

**Gap.** Multi-agent LLM systems have demonstrated collective capability on structured
tasks, but none has introduced an endogenous mechanism — invoked by agents themselves
based on performance signals — for maintaining behavioral diversity. We fill this gap
with Sacrificial Role Reallocation.

---

## 2.3 Prediction Markets and AI Forecasting

Prediction markets are canonical environments for studying information aggregation under
incentive constraints. Hanson's Combinatorial Information Market Architecture
[@hanson2003combinatorial] established the theoretical basis for market-based
elicitation of probability estimates. The Good Judgment Project [@tetlock2015superforecasting]
empirically demonstrated that a small fraction of human forecasters (*superforecasters*)
achieve calibration substantially superior to crowd averages through deliberate
reasoning practices — a behavioral analog to our strategy archetype taxonomy.

The Prediction Arena framework [@anonymous2026arena] provides a benchmarking scaffold for
evaluating AI models on real-world prediction markets using Brier score as the primary
metric. It establishes reproducible evaluation protocols for multi-model comparisons and
introduces the idea of *arena competition* among AI forecasters — a key inspiration for
our tournament structure. However, Prediction Arena treats each model as an isolated
forecaster; it does not model inter-agent dynamics, diversity, or reallocation.

PolySwarm [@polyswarm2026] deploys 50 diverse LLM personas on Polymarket, using Bayesian
aggregation to combine predictions and *latency arbitrage* — exploiting the
speed differential between LLM inference and human market updates — as a secondary
alpha source. PolySwarm is contemporaneous with our work and shares the goal of
multi-agent diversity in prediction markets, but does not study diversity as a *dynamic*
system with endogenous maintenance mechanisms, and operates on financial markets
(where ground truth is prices, not objective events) rather than the binary-outcome
sports and political event markets we study.

**Gap.** Prediction market AI has progressed from individual model evaluation to
multi-agent ensembles, but has not addressed the *temporal dynamics* of strategy diversity
across a full season: how diversity evolves, what forces deplete it, and how it can be
restored. Our 1,257-game, 90-day experimental window captures these dynamics in full.

---

## 2.4 Ensemble Diversity and Anti-Groupthink Mechanisms

The benefit of ensemble diversity in machine learning is theoretically well-established:
the *ambiguity decomposition* of Krogh and Vedelsby [@krogh1995neural] proves that
ensemble error equals individual error minus mean pairwise ambiguity, where ambiguity
measures the variance of individual predictions around the ensemble mean. This provides
a precise quantification of the value of diversity: increasing ambiguity (disagreement)
decreases ensemble error, all else equal. The challenge is that training procedures
tend to produce similar models — a phenomenon studied as *catastrophic homogenization*
in the context of language model fine-tuning.

For LLM agents specifically, DMAD [@liu2025dmad] — *Diverse Multi-Agent Debate*,
presented at ICLR 2025 — introduces adversarial prompting to prevent reasoning collapse
in multi-agent deliberation tasks. Agents are prompted to explicitly search for
alternative hypotheses and challenge their own conclusions before committing. DMAD
achieves meaningful diversity gains on mathematical and commonsense reasoning benchmarks.
Our work differs from DMAD in two fundamental ways: (i) we study *continuous prediction*
rather than discrete reasoning tasks, where diversity has a direct Brier-score
interpretation; and (ii) our diversity mechanism is *endogenous and performance-triggered*
— agents invoke Sacrificial Role Reallocation based on their own sustained underperformance,
not because they receive adversarial prompting from outside.

Dynamic optimization of LLM ensembles through reinforcement learning has been explored
in [@jain2025dynamic, arXiv:2502.04492], which uses a two-stage RL agent to adaptively
weight ensemble members. This approach optimizes the *aggregation weights* over a fixed
set of agents, whereas SRR operates at the level of *agent identity* — changing which
strategy archetype an agent embodies. These approaches are complementary, and combining
adaptive weighting with archetype reallocation is a natural direction for future work.

Common knowledge — defined by Aumann [@aumann1976agreeing] as the mutual-knowledge
fixed point where all agents know a fact, know that all know it, and so on to arbitrary
depth — is the mathematical foundation for our day-end broadcast mechanism. Aumann
proved that rational agents with common priors who share a common-knowledge posterior
must agree: they cannot "agree to disagree." Our day-end broadcast instantiates
common knowledge of the resolution of each game, eliminating posterior disagreement
about ground truth while leaving prediction strategies free to diverge. Schelling
[@schelling1960strategy] first identified *focal points* — salient solutions that agents
coordinate on without communication — as the empirical correlate of common-knowledge
reasoning. The strategy archetypes in our taxonomy function as Schelling focal points
for agent differentiation: agents coordinate on distinct niches without explicit
negotiation.

**Gap.** Ensemble diversity theory provides a mathematical basis for why diversity
helps, but has not been connected to an *evolutionary* mechanism that maintains diversity
across time in a live trading environment. DMAD provides an external mechanism;
we provide an endogenous one. RL-based ensemble weighting optimizes aggregation
over fixed agents; SRR changes the agents themselves.

---

## 2.5 Positioning Summary

Table 1 summarizes how the present work relates to the most closely related
prior systems along six dimensions.

| System | Real-world GT | Continuous actions | Live trading | Diversity mechanism | Endogenous | Multi-domain |
|--------|:---:|:---:|:---:|:---:|:---:|:---:|
| Axelrod 1980 [@axelrod1980effective] | ✗ | ✗ | ✗ | ✗ | — | ✗ |
| TradingAgents [@liu2024tradingagents] | ✗ | ✓ | ✗ | ✗ | — | ✗ |
| DMAD [@liu2025dmad] | ✗ | ✗ | ✗ | External | ✗ | ✗ |
| Prediction Arena [@anonymous2026arena] | ✓ | ✓ | ✗ | ✗ | — | ✓ |
| PolySwarm [@polyswarm2026] | ✓ | ✓ | ✓ | Fixed personas | ✗ | ✗ |
| OASIS [@yang2024oasis] | ✗ | ✗ | ✗ | Topology | ✗ | ✗ |
| **Axelrod-LLM (ours)** | **✓** | **✓** | **✓** | **SRR** | **✓** | **✓** |

*Table 1. Comparison of the present work to the most closely related systems on six
distinguishing dimensions. GT = ground truth; Endogenous = diversity mechanism is
triggered by agents' own performance signals rather than external design.*

---

> **BibTeX note.** Full references for all works cited in this section appear in
> `references.bib`. DMAD is cited via its ICLR 2025 OpenReview record
> (openreview.net/forum?id=t6QHYUOQL7); no arXiv preprint ID has been confirmed.
> PolySwarm [@polyswarm2026] cites arXiv:2604.03888. Agent Market Arena
> [@ma2025agentmarket] cites arXiv:2510.11695.
