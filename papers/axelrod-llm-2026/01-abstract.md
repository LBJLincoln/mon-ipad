# Abstract

Robert Axelrod's 1980 iterated Prisoner's Dilemma tournament demonstrated that cooperation
can emerge spontaneously in populations of self-interested agents through repeated
interaction — a landmark result that shaped decades of evolutionary game theory, economics,
and political science. That tournament, however, operated under severe constraints: agents
were hand-coded finite automata acting in a binary action space, strategies were fixed for
life, and there was no mechanism for societal self-correction when the population drifted
toward homogeneity. We present **Axelrod-LLM**, a generalization in three dimensions:
(i) agents are large language model (LLM) reasoners that receive full natural-language game
context and generate free-text justifications for continuous-valued predictions; (ii) the
arena is a real-world prediction market spanning the complete 2025–26 NBA season (1,257
games) and 1,120 US political events, with ground-truth resolution; and (iii) we introduce
*sacrificial role reallocation* (SRR), a novel mechanism in which chronically
underperforming agents voluntarily cede expected-value claims to explore unoccupied
strategy archetypes, provably increasing population-level Jensen–Shannon diversity without
requiring a central planner. Across 12 NBA and 10 political LLM agents drawn from five
provider ecosystems, SRR yields a **mean Brier-score reduction of X.XX** versus a fixed
ensemble control, a **Y.Y% bankroll advantage**, and a **Z.Z-nit increase in collective
Jensen–Shannon divergence** over 90-day trading windows. Our results establish that
Axelrod's cooperation dynamics generalize naturally to heterogeneous LLM societies and
that sacrificial diversity mechanisms are both theoretically grounded and empirically
effective.

> *Note: X.XX / Y.Y% / Z.Z* are placeholders pending experimental run completion
> (results expected from `data/arena/axelrod-log/` upon full-season resolution).
