# Discussion

Our results (pending full experimental resolution) afford four lines of
discussion: (i) the relationship between SRR and Nowak's evolutionary
cooperation mechanisms, extending the theoretical canon with a candidate
sixth rule specific to *epistemically competitive* agent societies (populations sharing a prediction target and proper scoring rule with individual evaluation — characterised in §6.1);
(ii) the information-architecture lesson of asymmetric day-end broadcasting,
grounded in Aumann's common-knowledge impossibility;
(iii) the structural risk of behavioural homogeneity in LLM ensembles and why
it requires endogenous — not external — correction;
and (iv) the practical implications of our mechanism design for anyone
building multi-LLM prediction systems at scale.

---

## 6.1  A Candidate Sixth Rule: Epistemic Role Sacrifice

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
to the beneficiaries of their reallocation. As an illustrative hypothetical:
if T8 (*mistral-small*) were to reallocate from *wide-coverage* to *contrarian*,
it would not share "genetic" material with T4 (*gemini-anl*), whose prediction
diversity it would enrich; nor would T8's stake-cap weighting make T4's outcomes
disproportionately valuable to T8. (T8's specific SRR events are recorded in
Table 7, §5.6; the Proposition 2 argument applies to any such reallocation.)

**Not direct reciprocity.** The sacrificing agent does not track which
specific peers benefited from its role change. No bilateral exchange is
expected or recorded; there is no mechanism for the beneficiary to return
the favour in a subsequent round.

**Not indirect reciprocity.** The social network does not update its
assessment of the sacrificing agent's reputation as a result of the
sacrifice act itself. Peer agents receive the updated archetype label (in
Condition A), but this label-update is logistically incidental; the Sham-SRR
control (Condition D) is designed to isolate whether label-change alone —
absent the prompt-reasoning change — replicates the Brier improvement; if it
does not, social reputation is not the active ingredient.

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
*stable against sacrifice-refusal deviations* (Strong Nash Equilibrium,
Proposition 2), precisely because the
sacrifice-eligible agent is already paying the individual fitness cost:
it has persistently above-mean Brier and there is no better individual
strategy available in its current archetype. Defection from SRR — refusing
the reallocation — offers no individual improvement and imposes a diversity
tax on the population. In the vocabulary of evolutionary dynamics, epistemic
role sacrifice is *individually incentive-compatible under Assumption A3*
for chronically below-performing agents: by A3, remaining in the same
archetype yields **at least** $\bar{B}_d + \delta_{\text{sac}}/2$ in expected
individual Brier (A3: partial persistence of the performance deficit —
the agent's Brier remains above mean, not below it), while accepting
the reallocation offers a strictly positive probability of improvement
through the archetype change and strictly improves group fitness through
the Ambiguity increase from Lemma 1.
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
learns what probability agent $j \neq i$ reported for today's events
(though cumulative bankroll standings allow partial stake-size inference,
bounded by the three-factor argument in the §3.2 broadcast-step footnote
and further discussed in §7.8).
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
(T6–T10) are expected to show higher intra-provider prediction correlation (lower
pairwise Jensen–Shannon divergence, $\overline{\text{JSD}}_{ij} =
\mathbb{E}_t[\text{JSD}(\text{Ber}(p_{i,t}),\text{Ber}(p_{j,t}))]$ averaged
over same-provider pairs) than cross-provider pairs, and SRR events involving only Mistral-to-Mistral archetype reassignments may produce smaller JSD diversity
gains than cross-provider reassignments.

If this within-provider correlation floor is empirically confirmed, it
carries an important design implication: provider heterogeneity is a
*necessary* condition for SRR's full benefit, not merely a desirable property.
An LLM prediction ensemble built from a single provider's model family —
however large the models, however diverse the prompts — faces a structural
diversity ceiling that SRR can only partially circumvent. This motivates
the four-provider design of our agent cohort (Cerebras, Google, Mistral,
OpenRouter) as a principled diversity requirement, not merely
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
estimates stake more, earn more, and their aggregate bankroll grows.
The emergent financial weighting is a form of implicit
*Bayesian model averaging* at the bankroll level: each agent's effective
financial stake — and hence its contribution to the betting pool — grows
with accumulated track record, with Kelly-sized positions as the weighting
mechanism.^[This BMA analogy applies to the *financial* dimension of the
system, not to prediction averaging. The ensemble mean prediction
$\bar{p}_t = \frac{1}{N}\sum_i p_{i,t}$ (§3.3) is equal-weighted over
agent predictions, independent of stake fractions or bankroll size.
The implicit BMA effect therefore operates through differential betting
exposure rather than differential prediction influence on $\bar{p}_t$.]

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
overestimates its edge will experience higher Brier, which directly reduces
its cap fraction $\kappa_i$ via the formula $\kappa_i = \max(0.01,\, 0.30 -
\overline{B}_i \times 0.50)$, and compounding bankroll drawdown, which further
reduces the absolute dollar stake even at a fixed cap fraction — a dual
feedback loop absent from consequence-free benchmark evaluations.

**Formula derivation and inverse-calibration probation criterion.** The
specific formula $\kappa_i = \max(0.01,\, 0.30 - \overline{B}_i \times 0.50)$
(§3.6) was derived by cross-validation on the 2024–25 pilot season targeting
three anchor points: $\kappa_i = 0.20$ for a pilot-best agent at
$\overline{B}_i = 0.20$ (near current NBA prediction state-of-the-art);
$\kappa_i \approx 0.175$ at the observed population mean $\overline{B}_i \approx 0.25$;
and the floor $\kappa_i = 0.01$ activating at $\overline{B}_i \geq 0.58$.
The slope coefficient $0.50$ reflects the design requirement that halving Brier
roughly doubles the Kelly allocation, creating a linearly increasing reward for
calibration improvement.

The inverse-calibration probation threshold $\overline{B}_i > 0.32$ (§3.6)
is grounded in comparison with the random-Bernoulli baseline. A predictor that
always outputs $p = 0.5$ achieves Brier $= 0.25$ for any binary outcome
($\omega \in \{0, 1\}$, since $(0.5 - 0)^2 = (0.5 - 1)^2 = 0.25$).
An agent reaching Brier $= 0.32$ performs 28% worse than this naive random
predictor — a strong signal of systematic inverse-calibration rather than mere
noise, where the agent reliably assigns higher probability to the losing outcome.
At Brier $= 0.32$, the formula-derived cap alone gives $\kappa_i = 0.30 - 0.50
\times 0.32 = 0.14$, still a substantial position size. The hard-cap override
of $\kappa_i \leq 0.03$ tightens this to at most 3% of bankroll per bet,
limiting losses to the ensemble while preserving the agent's participation
in the ensemble mean prediction $\bar{p}_t$. The threshold and override were
selected empirically from the 2024–25 pilot season.

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
