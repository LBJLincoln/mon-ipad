# Results

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
and the mean absolute difference in reported probability was recorded.^[Feasibility note: The protocol does not require $190 \times 12 \times 2 \times 1{,}230$ separate API calls. Instead, we precompute all $20 \times 12 \times 1{,}230 = 295{,}200$ archetype–agent–game combinations in a single retrospective batch (each game presented once per archetype per agent), then derive all 190 pairwise differences algebraically from the stored predictions without additional API calls. Total inference cost is 295,200 calls on a held-out pilot set, completed prior to any primary evaluation.]

$$\hat{\epsilon}_{\text{arch}}(r^{(a)}, r^{(b)}) =
\frac{1}{N \cdot T_{\text{pilot}}} \sum_{i=1}^{N}\sum_{t=1}^{T_{\text{pilot}}}
\left| p_{i,t}^{r^{(a)}} - p_{i,t}^{r^{(b)}} \right|$$

Since Assumption A1 is a *per-agent* uniform bound — it must hold for *every* agent
$i$, not merely in expectation across the cohort — we additionally report the per-agent
minimum, which is the operative test of A1:

$$\hat{\epsilon}_{\text{arch}}^{\min}(r^{(a)}, r^{(b)}) =
\min_{i \in \{1,\ldots,N\}} \frac{1}{T_{\text{pilot}}}
\sum_{t=1}^{T_{\text{pilot}}} \left| p_{i,t}^{r^{(a)}} - p_{i,t}^{r^{(b)}} \right|$$

A1 is confirmed for pair $(r^{(a)}, r^{(b)})$ if and only if
$\hat{\epsilon}_{\text{arch}}^{\min}(r^{(a)}, r^{(b)}) \geq 0.037$.
The cross-agent average $\hat{\epsilon}_{\text{arch}}$ is reported for descriptive
comparison but is not the operative A1 test: if a single agent (most plausibly
T12, selfhost-qwen4b, Qwen3-4B, whose limited capacity may compress its
prediction range) fails the per-agent threshold even while the cross-agent average
passes, A1 is violated for that agent.

*Table 4: Summary statistics for the $\binom{20}{2} = 190$ pairwise archetype
distinguishability estimates. The **operative A1 test** is the per-agent minimum
$\hat{\epsilon}_{\text{arch}}^{\min}$; the cross-agent average is reported for
descriptive purposes. §4.4 circularity note applies: reported minimum is
upward-biased because archetype revision used these pilot data.
Full $20 \times 20$ matrix in Appendix B.2.*

| Statistic | Value |
|-----------|-------|
| Minimum cross-agent average $\hat{\epsilon}_{\text{arch}}$ | **[PENDING]** |
| Minimum archetype pair (by average) | **[PENDING]** |
| **Minimum per-agent minimum $\hat{\epsilon}_{\text{arch}}^{\min}$** | **[PENDING — A1 operative test]** |
| Agent achieving minimum $\hat{\epsilon}_{\text{arch}}^{\min}$ | **[PENDING — expected: T12]** |
| Maximum cross-agent average $\hat{\epsilon}_{\text{arch}}$ | **[PENDING]** |
| Maximum archetype pair | **[PENDING]** |
| Mean $\hat{\epsilon}_{\text{arch}}$ (all 190 pairs, cross-agent avg) | **[PENDING]** |
| Fraction of pairs with $\hat{\epsilon}_{\text{arch}}^{\min} \geq 0.037$ | **[PENDING — expected: 190/190]** |

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
the market-implied probability (derived from the no-vig moneyline):

$$p_{\text{mkt}} = \frac{1/o_{\text{home}}}{1/o_{\text{home}} + 1/o_{\text{away}}}$$

where $o_{\text{home}}$ and $o_{\text{away}}$ are the American-odds moneyline
prices converted to decimal odds. This is the minimum meaningful performance
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
- **(H4)** DMAD-Static (Condition C) achieves higher initial $\overline{D}$ than
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
domains under Conditions A and B (Conditions C, D, and E are NBA-only; §4.3). This design enables a *domain-transfer*
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
