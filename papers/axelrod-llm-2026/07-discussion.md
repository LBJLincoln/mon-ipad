# 6. Discussion

The findings of §5 connect to three distinct literatures: the Axelrod
cooperation tradition in evolutionary game theory (§6.1–§6.2), ensemble
learning theory (§6.3), and multi-agent LLM systems design (§6.4). We
then address sensitivity to the archetype taxonomy (§6.5) and the
conditions under which we expect the LPSG framework to generalize (§6.6).

---

## 6.1 Axelrod's Result, Reframed for the Continuous Setting

Axelrod's 1980 finding was that *Tit-for-Tat* — a minimal-memory, maximally
transparent strategy — outperformed more sophisticated competitors because
it was simultaneously *nice* (cooperates first), *retaliatory* (defects when
crossed), *forgiving* (resumes cooperation after a single retaliation), and
*clear* (its behavior is predictable) [@axelrod1984evolution]. In the
continuous-action, population-broadcast LPSG setting, the analog of
Tit-for-Tat is not a single dominant strategy; rather, it is a *profile of
archetypes*, each of which embodies one of Axelrod's properties.

- *Niceness* ↔ archetype $\tau_1$ (*quantitative-bayesian*): provides an
  informationally honest first-move probability anchored on base rates.
- *Retaliation* ↔ archetypes $\tau_2$ (*contrarian*) and $\tau_9$
  (*ablation-skeptic*): punish consensus by withdrawing from it when
  common-knowledge evidence reveals systematic population error.
- *Forgiveness* ↔ the temporal structure of SRR itself: an archetype is
  not locked in after a bad run; the agent is reallocated and given a
  fresh start under a different frame.
- *Clarity* ↔ the common-knowledge broadcast (Mech A): each agent's
  rank, bankroll, and reputation are transparent to every other agent,
  so strategic responses are knowable in advance.

This suggests that Axelrod's four virtues are not properties of
*strategies* in the LPSG setting but properties of the *mechanism* itself.
The LPSG is Tit-for-Tat-like at the society level: it begins by
cooperating (broadcasting honest ground truth), retaliates against
homogenization (via SRR), forgives previously sacrificed agents (by
reassigning rather than removing), and is clear (all mechanism rules are
public).

If §5 confirms that Full LPSG strictly dominates the No-SRR ablation on
Brier, we interpret this as evidence that the four-virtue mechanism
structure reproduces the cooperation gradient Axelrod identified, but at
a different level of abstraction: within the society, not within individual
agent strategies.

---

## 6.2 The Role of Common Knowledge (Aumann, Reframed)

Aumann's Agreement Theorem [@aumann1976agreeing] establishes that rational
agents with common priors and common-knowledge posteriors cannot agree to
disagree. Our common-knowledge broadcast (§3.3) operationalizes Aumann's
construction: every day, each agent is assured — verifiably — that every
other agent has seen the same ground-truth resolution, the same
leaderboard, and the same reputation vector. Under Aumann's conditions, we
might therefore expect agent predictions to converge.

They do not, and the interpretation matters. LLM agents are not Bayesian
updaters in Aumann's sense: their posteriors are driven by prompt-conditional
reasoning that diverges even given identical evidence. The LPSG exploits
this — we use common knowledge of *ground truth* to eliminate calibration
disagreement, while leaving common knowledge of *peer strategies* to drive
strategic differentiation (archetype choice). The no-CK ablation (§5.3)
tests this decomposition directly: removing the broadcast should collapse
the strategic-differentiation component, as agents can no longer observe
what the society is doing and therefore cannot choose to deviate from it.

The prediction aligns with the Schelling focal-point interpretation
[@schelling1960strategy]: the archetype taxonomy functions as a set of
salient, pre-existing labels around which agents coordinate differentiation,
but only if common knowledge of *which labels are occupied* is maintained.

---

## 6.3 Ensemble Learning: Krogh–Vedelsby and the Cost of Homogeneity

The ambiguity decomposition of Krogh and Vedelsby [@krogh1995neural]
expresses ensemble error as mean individual error minus mean pairwise
ambiguity:
$$
\mathrm{Brier}(\hat{p}^{\mathrm{ens}}_t) \;=\; \bar{B}_t - A(t).
$$
This identity makes ambiguity — disagreement among ensemble members on the
same inputs — a first-class design target. Standard techniques for
inducing ambiguity include bagging, random feature subsampling, and
explicit diversity-regularized training. None of these is available in the
LLM-prompt setting: we cannot modify model internals, and all agents see
the same market data.

SRR (§3.4) is, mechanistically, a method for inducing prompt-space
ambiguity in populations where model-space ambiguity is fixed. Proposition 2
establishes that SRR weakly increases $\mathbb{E}[A(t)]$; the No-SRR
ablation in §5.1 tests the magnitude of this effect empirically. If the
ablation confirms a positive Brier advantage for Full LPSG, we interpret
this as the first direct empirical demonstration that *prompt-space
ambiguity*, induced by performance-triggered reallocation, improves ensemble
calibration in a real-money-equivalent market.

This result, if it holds, has broader implications for LLM ensemble design.
The field has converged on two approaches: (i) heterogeneous model
ensembling [@jain2025dynamic; @liu2025dmad], which requires access to
multiple model families and is limited by the number of available
high-quality models, and (ii) self-consistency sampling, which increases
per-query cost linearly with sample count. SRR offers a third option:
*prompt-diversification* across a fixed model pool, with diversity
*maintained* across time by a performance-triggered mechanism.

---

## 6.4 Five Mechanisms, One System: Connection to Nowak

Nowak's 2006 *Science* synthesis [@nowak2006five] enumerated five
mechanisms by which cooperation evolves:

1. *Kin selection* — cooperation among related agents.
2. *Direct reciprocity* — I-help-you-you-help-me.
3. *Indirect reciprocity* — I-help-you-so-others-will-help-me.
4. *Network reciprocity* — clustering of cooperators on structured graphs.
5. *Group selection* — between-group competition favors cooperative groups.

The LPSG framework instantiates four of these:

- *Direct reciprocity* is absent by design: agents interact via
  population-level broadcast, not pairwise matches. This is a deliberate
  generalization of Axelrod's IPD to the N-agent setting.
- *Indirect reciprocity* is Mech D: reputation accumulates publicly and
  shapes acceptance of future coalition pacts (§3.6).
- *Network reciprocity* is achieved via archetype clustering: agents of
  the same archetype form a "cluster" in strategy space, and the SRR
  operator prevents any cluster from reaching population-wide dominance.
  The archetype taxonomy plays the role of the network topology.
- *Group selection* is present at the between-run level: replicate runs
  with different SRR seeds constitute a between-population competition,
  reported in §5.7.
- *Kin selection* is absent: agents from the same model family (e.g., all
  Mistral variants) do not receive special treatment. This is intentional
  — kin selection would bias the society toward whichever provider supplies
  the most agents, which would confound the ablation analysis.

The LPSG framework thus distills the cooperation-promoting mechanisms into
the specific subset that operates in the continuous-action,
population-broadcast, real-world-grounded prediction setting.

---

## 6.5 Sensitivity to Archetype Taxonomy Size $M$

We fix $M = 10$ archetypes (§3.4.1) ex ante. Two natural questions arise:
(a) does the specific taxonomy matter, and (b) does the number of
archetypes $M$ matter?

On (a): the ten archetypes were chosen to span qualitatively distinct
reasoning styles (Bayesian, contrarian, narrative, quantitative, etc.) —
the full rationale appears in Appendix A. A replication study using a
*different* ten-archetype taxonomy (drawn from the superforecaster
typology of [@tetlock2015superforecasting], detailed in Appendix D.3) is
planned but not yet executed.

On (b): varying $M$ changes the cardinality of the state space over which
SRR samples. Too small a $M$ limits the expressible diversity; too large a
$M$ may dilute the population across archetypes with few agents per
archetype, weakening within-archetype signal. A sweep over $M \in \{5, 10,
15, 20\}$ is a natural follow-up experiment that we discuss as future work
in §7.3.

---

## 6.6 Generalization Beyond Sports and Politics

The LPSG framework does not depend on the specific domain of NBA or
political prediction. The mechanism requires only: (i) a binary-outcome
event stream with objective ground-truth resolution, (ii) odds or an
equivalent metric for capital allocation, and (iii) a diverse enough agent
pool that distinct archetypes produce distinct predictions.

Natural additional targets include:

- Financial markets (short-horizon trade classification);
- Clinical prediction (diagnostic binary outcomes);
- Industrial forecasting (equipment-failure-by-horizon);
- Prediction markets more broadly (macroeconomic events on Polymarket).

We emphasize that domains where *ground truth is endogenous to agent
action* — e.g., executed financial trades moving prices — require
additional formalism to handle feedback effects on $Y_t$. The LPSG as
stated assumes $Y_t$ is exogenous.

---

## 6.7 What the Results Do and Do Not Establish

If §5 confirms the pre-registered hypotheses, the results establish:

- That SRR is a viable endogenous mechanism for diversity maintenance in
  LLM populations (§5.1, §5.2).
- That the combination of common-knowledge broadcast and SRR jointly
  produces ensemble Brier improvements that exceed either mechanism alone
  (§5.3).
- That these improvements are reliably reproducible across SRR random
  seeds (§5.7).

They do not establish:

- That SRR is optimal among all possible diversity-maintenance mechanisms
  (only that it strictly improves over No-SRR within our taxonomy).
- That the specific archetype taxonomy is uniquely correct (only that it
  is sufficient for the reported effects).
- That results transfer without modification to domains with endogenous
  ground truth (addressed in §7.2).

The precise interpretation of each result — and the conditions under which
we expect it to generalize — is carried to §7.
