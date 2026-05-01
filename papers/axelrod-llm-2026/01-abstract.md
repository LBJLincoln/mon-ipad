# Abstract

Robert Axelrod's 1980 tournament proved that cooperation emerges among self-interested
agents through iterated interaction — but relied on static, hand-coded automata in a
binary action space with no mechanism for societal self-correction when the population
drifted toward homogeneity. We present **Axelrod-LLM**, generalising this framework
along four axes: (i) agents are large language models (LLMs) that reformulate strategy
through chain-of-thought deliberation; (ii) the arena is a real-world prediction market
over the complete 2025–26 NBA season (1,257 games) and 1,120 US political events,
with exogenous binary ground-truth resolution; (iii) day-end common-knowledge broadcast
enables population-level strategic updating while preserving belief diversity; and
(iv) we introduce *sacrificial role reallocation* (SRR), wherein chronically
underperforming agents voluntarily adopt under-represented strategy archetypes, provably
increasing Jensen–Shannon population diversity without central planning. We formalise
the system as the *LLM Prediction Society Game* (LPSG) — a Bayesian population game —
and prove SRR constitutes a diversity-improving Nash equilibrium refinement
(Lemma 1, Proposition 2). Empirical results across 12 NBA and 10 political LLM agents
from five provider ecosystems and 175 trading days are pending full experimental
completion (`data/arena/axelrod-log/`). Our framework bridges classical cooperation
theory and the principled design of diverse, calibrated LLM prediction ensembles.

> *Placeholders for Brier-delta, bankroll advantage, and JSD-nit gain will be filled
> upon full-season resolution of `data/arena/axelrod-log/`.*
