# Introduction

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
[@wu2023autogen] formalized multi-agent conversation patterns; MetaGPT [@hong2023metagpt] introduced role-specialisation with shared memory. More recently, TradingAgents
[@xiao2024tradingagents] instantiated a multi-LLM financial
trading system with analyst, risk management, and execution roles communicating through
structured dialogues — the closest antecedent to our architecture. OASIS [@yang2024oasis]
extended multi-agent interaction to one-million-node social simulations on real social
network topologies.

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
   population game with type heterogeneity (§3.2) over a continuous-action prediction market
   with common-knowledge day-end broadcasts, generalizing the IPD to the LLM agent setting (§3).

2. **Sacrificial Role Reallocation (SRR).** We introduce SRR, a novel mechanism wherein
   an agent with persistent above-mean Brier for $W$ consecutive days
   ($\overline{B}_{i,d} - \bar{B}_d > \delta_{\text{sac}}$; §3.4) probabilistically
   adopts an underrepresented strategy archetype from a predefined taxonomy,
   increasing population-level Jensen–Shannon divergence (§3.3). We prove under mild assumptions that SRR is a *Strong* Nash equilibrium
   refinement (Proposition 2, §3.5): no coalition of sacrifice-eligible agents can
   collectively refuse SRR and simultaneously (weakly) improve ensemble Brier for the
   coalition while (weakly) reducing individual Brier for each coalition member.

3. **Real-world LLM trading experiment.** We deploy 12 LLM agents (four provider
   ecosystems: Cerebras, Google Gemini 3, Mistral, OpenRouter)
   on the full 2025–26 NBA season (1,257 games) and 10 agents (three provider
   ecosystems: Cerebras, Google, Mistral) on 1,120 US political events,
   constituting — to our knowledge — the largest *controlled*
   multi-LLM prediction market experiment with performance-triggered archetype
   reallocation and paired parallel domains (NBA + political) in peer-reviewed
   literature (§4).^[PolySwarm [@polyswarm2026] deploys 50 LLM personas on
   real-money Polymarket with fixed-persona diversity and no performance-triggered
   reallocation. Our 22-agent design (12 NBA + 10 POL) across 2,377 events is
   distinct in its formal SRR mechanism and cross-domain pairing rather than in
   raw agent count.]

4. **Empirical validation of diversity-accuracy coupling.** We pre-register and structure
   four directional hypotheses (H1–H4, §4.3) testing whether SRR increases JSD
   diversity (H1), reduces ensemble Brier (H2), requires genuine prompt-level reasoning
   change rather than label signalling alone (H3), and whether static initial diversity
   decays without dynamic maintenance (H4). Experimental structure and predicted
   outcomes are detailed in §4–5; results pending full season resolution.

## Paper Organization

Section 2 surveys related work across evolutionary game theory, LLM multi-agent systems,
and prediction market mechanisms. Section 3 formalizes the LPSG and SRR. Section 4
describes the experimental setup. Section 5 presents results. Section 6 discusses
connections to cooperation theory and implications for LLM ensemble design. Section 7
covers limitations and ethics. Appendix A documents the full 20-archetype
strategy taxonomy with abbreviated prompt directives (full prompt modules
available in the code repository). Appendix B provides mathematical proofs and
the archetype pairwise distinguishability matrix. Appendix C provides the
experimental calendar, hyperparameter and temperature sensitivity analyses, and
statistical power calculations.

---

> **A note on timing.** The 1980 Axelrod tournament and the 1997 anniversary volume
> [@axelrod1997complexity] bracket a remarkable period in which game theory and computer
> science began to co-evolve. The 2025–26 NBA season constitutes our arena precisely
> because it provides 1,257 independent binary-outcome events with transparent, objective
> resolution — a ground-truth discipline that social simulations lack. Political event
> markets provide a complementary domain with higher uncertainty, longer time horizons, and
> richer information asymmetries, enabling domain-transfer tests of our core claims.
