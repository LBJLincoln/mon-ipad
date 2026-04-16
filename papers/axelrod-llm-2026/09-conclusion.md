# 8. Conclusion

We have presented **Axelrod-LLM**, a generalization of Axelrod's 1980
iterated Prisoner's Dilemma tournament along four axes: (i) agents are
large language models that receive natural-language game context and
emit probabilistic predictions with free-text justifications; (ii) the
arena is a real-world prediction market on the full 2025-26 NBA season
(1,257 games) and 1,120 US political events, with third-party
verifiable ground truth; (iii) common-knowledge broadcast replaces
Axelrod's pairwise private interaction, making per-day resolutions and
reputation available to every agent; and (iv) we introduced *Sacrificial
Role Reallocation* (SRR), a mechanism in which chronically
underperforming agents probabilistically adopt under-occupied strategy
archetypes, provably preventing pure-imitation equilibria and weakly
improving ensemble Brier under the Krogh–Vedelsby ambiguity decomposition.

Our contributions are:

1. **A formal LPSG framework** (§3) that unifies evolutionary game theory,
   prediction-market elicitation, and LLM multi-agent systems in a single
   continuous-action Bayesian population game.

2. **The SRR mechanism** (§3.4) and two theoretical results: that SRR
   eliminates pure-imitation equilibria almost surely (Prop. 1) and that
   it weakly increases ensemble ambiguity under mild assumptions (Prop. 2).

3. **A real-world experimental evaluation** on 2,377 events across two
   domains with 12 / 10 LLM agents from five provider ecosystems (§4),
   the largest such evaluation of which we are aware in peer-reviewed
   literature.

4. **A release of the full experimental stack**: code, prompt templates,
   per-day post-mortem logs, preprocessing pipelines, and replication
   instructions (§4.6, Appendix C).

## 8.1 Implications for LLM Multi-Agent Systems

The core empirical claim of this work — that diversity, *maintained across
time by an endogenous mechanism*, strictly improves ensemble calibration —
has implications beyond the prediction-market setting. Most deployed
LLM multi-agent systems today use *fixed* role assignments: an "analyst",
a "critic", an "executor." The Axelrod-LLM findings suggest that fixed
roles are sufficient to extract ensemble benefit only if the prompt
induces sufficient output-space diversity; when it does not, fixed roles
leave ensemble performance on the table. SRR — or any mechanism that
*dynamically reallocates* roles based on performance — offers a principled
way to recover the missing diversity.

We do not claim SRR is the unique best such mechanism. The question of
optimal mechanism design for LLM ensemble diversity maintenance is open,
and our empirical results (conditional on §5) establish a lower bound
rather than a ceiling: real gains from diversity are available under
tractable engineering, and they exceed what fixed-role designs deliver.

## 8.2 Return to Axelrod

Axelrod's original tournament taught us that cooperation can emerge among
simple, hand-coded agents through repeated interaction. Our generalization
teaches a complementary lesson: in societies of reasoning agents, the
*structural conditions* for cooperation — transparency, retaliation,
forgiveness, clarity — are best implemented at the level of the society's
*mechanism*, not at the level of individual agent strategies. The
mechanism carries the virtues; the agents contribute the reasoning.

This is, in a sense, a more hopeful reading than Axelrod's original. In
the 1980 tournament, it was the individual strategy (Tit-for-Tat) that
carried the virtues, and the society was merely the substrate in which
that strategy could flourish. In the Axelrod-LLM setting, the mechanism
carries the virtues universally, and even agents whose individual
reasoning is imperfect can participate in a society that is, as a whole,
nice, retaliatory, forgiving, and clear. Cooperation does not require
cooperators; it requires cooperative infrastructure.

## 8.3 Future Work

The open questions enumerated in §7.8 point toward three research
trajectories.

**Mechanism design.** Variants of SRR — with different candidate-pool
rules, different archetype taxonomies, and different reallocation
probability functions — may dominate the specific formulation we use.
Formal mechanism-design analysis (what class of mechanisms the LPSG
admits; which are strategyproof) is a natural next paper.

**Domain transfer.** Replicating the full pipeline on clinical diagnostic
prediction, financial-derivative classification, and industrial forecasting
would establish whether the observed Brier improvements are domain-agnostic
or reflect specifics of the sports/political setting.

**Adversarial study.** The reputation mechanism (Mech D) creates a target
for strategic adversaries. A systematic study of which adversarial
strategies can subvert LPSG cooperation — and which defenses suffice —
would connect this line of work to the LLM security literature.

## 8.4 Closing

Forty-six years after Axelrod convened his first tournament, the
agents have grown from hand-coded finite automata to large language
models. The environment has grown from a binary, stylized Prisoner's
Dilemma to real-world prediction markets with objective resolution. The
question Axelrod asked — *under what conditions does cooperation emerge*
— remains the central question. Our answer is that the conditions are
the same, but the level at which they must be implemented has shifted
upward, from strategy to society, from individual to mechanism, from
hand-coded rules to LLM-population dynamics. The virtues Axelrod
identified are as necessary as ever; they have simply migrated from the
agents to the architecture within which the agents reason.
