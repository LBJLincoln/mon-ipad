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
population game — and prove SRR constitutes a diversity-improving Nash equilibrium
refinement (Lemma 1, Proposition 2). Results across 12 NBA and 10 political LLM agents
from five provider ecosystems over 175 trading days are pending full seasonal resolution
(`data/arena/axelrod-log/`). The framework bridges Axelrod-era cooperation theory and
principled design of diverse, calibrated LLM prediction ensembles.

> *Brier-delta, bankroll advantage, and JSD-gain figures to be inserted upon
> full-season resolution of `data/arena/axelrod-log/`.*
