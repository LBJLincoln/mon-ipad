# Appendix C — Experimental Supplements

---

## C.1  Experimental Calendar

The five experimental conditions (§4.3) share a single chronological event
stream but are run at different points in the experimental timeline. Condition A
(Full SRR) ran live during the 2025–26 season; Conditions B–E are retrospective
replays over the logged event stream, scheduled to complete after the season
concludes in June 2026.

### C.1.1  Timeline

| Phase | Period | Purpose |
|-------|--------|----------|
| Archetype pilot | 2024–25 NBA season (Oct 2024 – Jun 2025) | Measure pairwise $\hat{\epsilon}_{\text{arch}}$; tune $\delta_{\text{sac}}$, $W$, $W_{\text{persist}}$ |
| Pre-registration | 2025-10-01 | Hypotheses H1–H4 locked; SHA-256 recorded at tag `preregistration-v1` |
| **Condition A** (Full SRR) — *live* | 2025-10-14 – 2026-06-20 | 175 NBA trading days; 90 political event days; primary treatment |
| **Condition B** (Fixed Ensemble) — *replay* | 2026-07-01 – 2026-07-14 | Estimated 14 compute-days; bankrolls reset; archetypes frozen at initial assignment |
| **Condition C** (DMAD-Static) — *replay* | 2026-07-15 – 2026-07-28 | Pre-assigned max-diversity archetypes; SRR disabled |
| **Condition D** (Sham-SRR) — *replay* | 2026-08-01 – 2026-08-14 | Label-only reallocation; system prompts unchanged |
| **Condition E** (Free-Rider) — *replay* | 2026-08-15 – 2026-08-28 | Random eligible agent selected for reallocation regardless of performance |
| Analysis + write-up | 2026-09 | Bootstrap CI computation; figure generation; manuscript revision |

*Replay conditions use identical API calls replayed against cached LLM
responses from Condition A where possible (to control for stochastic variation
in model outputs), supplemented by live API calls for agent–archetype
combinations that did not occur in Condition A.*

### C.1.2  Data Availability at Submission

As of the current draft (May 2026), Condition A is 71% complete (125/175 NBA
trading days; 68/90 political event days). Conditions B–E are pending season
conclusion. Results in §6 are therefore placeholders; the pre-registered
analysis will be executed in September 2026 and incorporated in the revised
manuscript.

All prediction logs accumulated to date are archived at
`data/arena/axelrod-log/` in newline-delimited JSON, with one file per
trading day per domain. The schema is described in §C.5.

---

## C.2  Hyperparameter Sensitivity Analysis

The LPSG has three primary hyperparameters governing the SRR mechanism:
the sacrifice threshold $\delta_{\text{sac}}$, the patience window $W$,
and the persistence window $W_{\text{persist}}$. These were selected via
cross-validation on the 2024–25 archetype pilot season (held out from
all evaluation) using a grid search over the ranges in Table C.2.

### C.2.1  Grid

| Hyperparameter | Values tested | Selected value |
|----------------|---------------|----------------|
| $\delta_{\text{sac}}$ (Brier excess) | 0.01, 0.02, 0.03, 0.05 | **0.02** |
| $W$ (patience window, days) | 3, 5, 7, 10, 14 | **7** |
| $W_{\text{persist}}$ (persistence, days) | 7, 14, 21, 28 | **14** |

Selection criterion: minimise pilot-season ensemble Brier on held-out events
$(D_{\text{pilot}} = 80\text{ trading days})$ under Condition A (Full SRR).

### C.2.2  Results

**[PENDING: sensitivity surface to be populated from
`data/arena/axelrod-log/pilot-hparam-grid.jsonl` once pilot backtest
completes. Expected result: (a) $\delta_{\text{sac}} = 0.01$ triggers
excessive SRR events (reallocation instability); (b) $W \leq 3$ misidentifies
transient slumps as sacrifice-eligible; (c) $W_{\text{persist}} = 28$ delays
recovery; confirmed selection $\delta_{\text{sac}} = 0.02$, $W = 7$,
$W_{\text{persist}} = 14$ should be Pareto-optimal in the pilot grid.]**

### C.2.3  Reversal-Target Sensitivity Analysis

Definition 2, step 5, reverts to $r_i^{(\text{pre})}$ — the archetype immediately
before the SRR event — rather than the agent's initial archetype $r_i^{(0)}$.
The trade-off between these two designs is discussed in the §3.4 footnote.
Empirical comparison requires tracking multi-hop SRR chains, defined as an agent
experiencing $\geq 2$ SRR events within one season. Under the selected parameters
($W_{\text{persist}} = 14$ days, $D = 175$ trading days), an agent can undergo at
most $\lfloor 175/14 \rfloor = 12$ SRR events; multi-hop chains deeper than two
are therefore possible but rare. **[PENDING: comparison of immediately-prior vs.\
home-base reversal designs from pilot data, to be populated from
`data/arena/axelrod-log/srr-chain-analysis.jsonl`.]**

### C.2.4  Archetype Distinguishability Out-of-Sample Validation

The pairwise distinguishability estimates $\hat{\epsilon}_{\text{arch}}$ reported in
Table B.2 and cited in Assumption A1 are computed from the full 2024–25 pilot season.
To provide an unbiased bound for A1's numerical constant, the pilot season should be
partitioned into a *development half* (October 2024 – February 2025) and a *validation
half* (March – June 2025), with $\hat{\epsilon}_{\text{arch}}$ recomputed on the
held-out validation half.

If the held-out estimate satisfies $\hat{\epsilon}_{\text{arch}}^{\text{val}} \geq 0.037$,
Assumption A1 is confirmed out-of-sample and the Lemma 1 / Proposition 2 arithmetic
carries through unchanged. If $\hat{\epsilon}_{\text{arch}}^{\text{val}} < 0.037$,
the A1 bound should be revised downward to $\hat{\epsilon}_{\text{arch}}^{\text{val}}$
and the Lemma 1 Case 2 sufficient condition re-verified: the condition requires
$\frac{N-1}{N}\hat{\epsilon}_{\text{arch}} > 2 \times 0.014$, i.e., a threshold of
$\hat{\epsilon}_{\text{arch}} > \frac{12}{11} \times 0.028 \approx 0.031$.  The
current estimate (0.037) carries a slack of 0.006 above this threshold, so values in
$(0.031, 0.037)$ would tighten but not break the result; values $\leq 0.031$ would
require either a tighter A4 bound or an explicit restatement.
**[PENDING: held-out half recomputation, scheduled for September 2026 analysis;
listed in pre-submission checklist as item 12.]**

### C.2.5  Interaction Effects

Because $\delta_{\text{sac}}$ and $W$ jointly determine sacrifice eligibility,
we also evaluate the full $4 \times 5 = 20$-point $(\delta_{\text{sac}}, W)$
cross-grid at the selected $W_{\text{persist}} = 14$. The number of SRR events
per season under each configuration is:

$$\text{SRR events} \propto \frac{N}{W} \cdot P\!\left[\overline{B}_{i,d} - \bar{B}_d > \delta_{\text{sac}}\right]$$

where the probability term is estimated empirically from pilot data.
We expect a monotone decrease in SRR events as $\delta_{\text{sac}}$
or $W$ increases, and a U-shaped relationship between SRR event frequency
and pilot-season Brier (too few events: insufficient diversity exploration;
too many: disruptive churn that degrades calibration during transitions).

**[PENDING: full $4 \times 5$ surface figure to be generated once pilot
backtest completes.]**

---

## C.3  Temperature Sensitivity Analysis

All agents use a fixed generation temperature $\tau = 0.7$ (§4.6).
Temperature controls the stochasticity of LLM outputs: lower $\tau$ yields
more deterministic (potentially overconfident) predictions; higher $\tau$
introduces noise that may improve diversity but degrade calibration.

### C.3.1  Grid

We evaluate five temperature values on a 20-game held-out subset of the
2024–25 pilot using T4 (Gemini 3 Flash, *analytical* archetype) as the
representative agent:

| $\tau$ | Expected effect |
|--------|----------------|
| 0.30 | Near-deterministic; predictions cluster near modal estimate |
| 0.50 | Low variance; good calibration in well-specified settings |
| **0.70** | **Selected; balances expressiveness and reproducibility** |
| 0.90 | Moderate variance; may improve diversity at cost of calibration |
| 1.10 | High variance; risk of prediction extremism for overconfident models |

### C.3.2  Results

**[PENDING: per-$\tau$ Brier scores and ECE values to be populated from
`data/arena/axelrod-log/temp-sensitivity.jsonl`. Expected finding:
$\tau = 0.7$ is near-optimal for the *analytical* archetype; archetypes
with explicit probability-shrinkage directives (e.g., *conservative*)
may prefer $\tau \leq 0.5$, while archetypes designed for high divergence
(e.g., *devil's-advocate*) may benefit from $\tau \geq 0.9$. A
per-archetype temperature sweep is deferred to future work.]**

### C.3.3  Limitation: Self-Hosted Model Temperature

The temperature sweep in C.3.1–C.3.2 uses T4 (Gemini 3 Flash Preview,
managed inference via Google API) as the representative agent.
Two structurally distinct mechanisms cause managed-inference models to
respond to the `temperature` parameter differently from self-hosted models:

**(a) RLHF-induced distribution sharpening.** Instruction-following
fine-tuning via reinforcement learning from human feedback (RLHF)
concentrates logit probability mass on tokens consistent with alignment
objectives [@ouyang2022training]. Because the pre-softmax logit spread
narrows during RLHF, the *effective* sample entropy at a given $\tau$
is lower for an instruction-tuned model than for a base model of the
same scale — not because temperature is applied differently, but because
the input logit distribution is already sharper. This effect is
model-scale- and training-recipe-dependent and cannot be characterised
from the API alone.

**(b) Provider-specific sampling pipeline.** Several managed-inference
APIs apply top-$k$ or nucleus top-$p$ sampling *after* temperature
scaling but before token emission, further constraining the output
distribution beyond what $\tau$ alone specifies. Gemini 3 Flash applies
such a filtering step; the exact cutoffs are undisclosed, making the
effective generation entropy provider-dependent at identical $\tau$ values.

The original experimental design intended T12 as a self-hosted agent
(Qwen3-4B via llama.cpp, CPU inference) that would be subject to neither
Mechanism (a) nor Mechanism (b) in the same way: Qwen3-4B uses a lighter
alignment procedure than frontier 235B models, and llama.cpp applies
temperature directly to raw logits with no implicit top-$k$ filtering.
This design intent was not realised: T12's self-hosted endpoint timed out
and was rerouted to `cerebras:qwen-3-235b` — the same 235B instruction-tuned
model as T1–T2 (§4.1 Table 3 note$^\dagger$). As deployed, T12 is subject to
both Mechanism (a) (235B RLHF-induced sharpening) and Mechanism (b)
(Cerebras API sampling pipeline) at a level structurally identical to T1–T2.

The comparison between a self-hosted 4B model and managed-inference T4
that this section was originally designed to motivate is therefore no longer
feasible in the current experimental configuration. The planned T12
temperature sweep (self-hosted vs.\ managed comparison) is deferred to future
work contingent on restoring a working self-hosted inference endpoint.
Under the actual rerouted configuration, all 12 agents are governed by
mechanisms (a) and (b) with provider-specific parameters; the $\tau = 0.7$
selection from the T4 validation is applied uniformly, with Mechanism (a) and (b)
magnitudes varying by provider as discussed in C.3.1–C.3.2.

---

## C.4  Statistical Power Calculations

We provide formal power calculations for the primary hypothesis tests.
Unlike Appendices C.2 and C.3, this appendix does not require experimental
data — the power analysis can be conducted under design-stage assumptions.

### C.4.1  Primary Test: SRR vs.\ Fixed Ensemble (H1, H2)

**Setup.** Let $\Delta_t = B_{\text{ens},t}^{(B)} - B_{\text{ens},t}^{(A)}$
be the per-game Brier difference between the Fixed Ensemble (Condition B)
and Full SRR (Condition A), where positive $\Delta_t$ indicates SRR
improves the ensemble Brier for game $t$. Under H0: $\mathbb{E}[\Delta_t] = 0$.
Under H1 (our directional hypothesis): $\mathbb{E}[\Delta_t] = \delta > 0$.

**Effective sample size.** The $T = 1{,}257$ NBA games are not independent:
games played on the same day share the same morning-council context and
archetype configuration. The intra-day intraclass correlation (ICC) for
Brier differences, estimated from pilot data, is $\rho_{\text{ICC}} \approx 0.15$.
With approximately $T / D = 1{,}257 / 175 \approx 7.2$ games per day-bucket,
the design effect is:

$$\text{DEFF} = 1 + (n_{\text{cluster}} - 1) \cdot \rho_{\text{ICC}}
= 1 + 6.2 \times 0.15 = 1.93$$

The effective sample size at ICC $= 0.15$ (conservative upper bound) is:

$$n_{\text{eff}} = \frac{T}{\text{DEFF}} = \frac{1{,}257}{1.93} \approx 651$$

Under ICC $= 0.10$ (optimistic lower bound), DEFF $= 1.62$ and
$n_{\text{eff}} = 776$. The range $[651, 776]$ brackets the plausible
effective sample size; §4.5 and all power statements use the conservative
lower bound $n_{\text{eff}} = 651$.

**Minimum detectable effect.** For a two-sided paired $t$-test at
$\alpha = 0.05$ and power $1 - \beta = 0.80$:

$$n_{\text{eff}} = \frac{(z_{\alpha/2} + z_\beta)^2 \cdot \sigma_\Delta^2}{\delta^2}$$

Solving for $\delta$ with $n_{\text{eff}} = 651$, $z_{0.025} = 1.960$,
$z_{0.20} = 0.842$, and pilot-estimated $\sigma_\Delta \approx 0.033$:

$$\delta_{\min} = (z_{\alpha/2} + z_\beta) \cdot \frac{\sigma_\Delta}{\sqrt{n_{\text{eff}}}}
= 2.802 \times \frac{0.033}{\sqrt{651}} = 2.802 \times 0.00129 \approx 0.0036$$

The minimum detectable effect is $\delta_{\min} \approx 0.0036$ Brier points
($\approx 1.6\%$ relative to the pilot ensemble baseline of 0.226). Our
pre-registered target of $\delta = 0.005$ ($\approx 2.3\%$ relative) is
comfortably above this threshold, giving power:

$$1 - \beta = \Phi\!\left(\frac{\delta}{\sigma_\Delta / \sqrt{n_{\text{eff}}}} - z_{\alpha/2}\right)
= \Phi\!\left(\frac{0.005}{0.00129} - 1.960\right) = \Phi(3.876 - 1.960) = \Phi(1.916) \approx 0.97$$

**The study is thus powered at $\approx 97\%$ to detect a 0.005 Brier point
improvement, assuming the pilot-estimated variance structure holds in the
2025–26 season.**

### C.4.2  Secondary Test: JSD Diversity (H1)

**Setup.** The JSD hypothesis $H_1$ posits that SRR increases mean daily
diversity $\overline{D}_d$. Let $\Delta_d^D = D_d^{(A)} - D_d^{(B)}$ be
the day-level JSD difference between Full SRR and Fixed Ensemble.
Day-level observations are approximately independent (distinct game
matchups, archetype transitions are sparse), so we use the number of
trading days $D = 175$ as the effective sample size.

**Pilot estimate.** JSD from the pilot season has $\sigma_D \approx 0.022$
(day-level standard deviation).  A detectable effect of $\delta_D = 0.005$
(hypothesised SRR-induced increase in mean JSD per day) requires:

$$n = \frac{(z_{\alpha/2} + z_\beta)^2 \cdot \sigma_D^2}{\delta_D^2}
= \frac{7.84 \times 0.000484}{0.000025} = \frac{0.003794}{0.000025} \approx 152\ \text{days}$$

With $D = 175$ days, the study is powered at:

$$1 - \beta = \Phi\!\left(\frac{0.005 \times \sqrt{175}}{0.022} - 1.960\right)
= \Phi\!\left(\frac{0.0661}{0.022} - 1.960\right) = \Phi(3.005 - 1.960) = \Phi(1.045) \approx 0.85$$

**The JSD analysis is powered at $\approx 85\%$ to detect a 0.005 increase
in daily diversity, comfortably exceeding the $80\%$ threshold.**

### C.4.3  Pilot Variance Assumptions

Both calculations depend on the pilot-estimated standard deviations
$\sigma_\Delta = 0.033$ (Brier difference) and $\sigma_D = 0.022$ (daily JSD).
These were estimated from the 2024–25 held-out pilot season under a Fixed
Ensemble configuration (no SRR), providing a conservative baseline
(SRR-induced archetype changes may reduce $\sigma_\Delta$ by introducing
structured rather than random variation, but we do not assume this benefit
in the power calculation).

*Sensitivity check.* If $\sigma_\Delta$ is 30% larger than the pilot estimate
(i.e., $\sigma_\Delta = 0.043$), the Brier power drops from 97% to 88%
and the required $n_{\text{eff}}$ for 80% power rises to:

$$n = \frac{7.84 \times 0.043^2}{0.005^2} = \frac{7.84 \times 0.001849}{0.000025} \approx 580$$

Still below the lower-bound effective sample size estimate of 651.
The study remains adequately powered under this pessimistic variance assumption.

---

## C.5  Axelrod Log JSON Schema

*(Stub — full documentation deferred to data release upon season completion.)*

The prediction logs at `data/arena/axelrod-log/` follow the schema below.
Each newline-delimited JSON file corresponds to one trading day in one domain.

```json
{
  "date":       "<YYYY-MM-DD>",
  "domain":     "nba | political",
  "condition":  "A | B | C | D | E",
  "day_index":  <int>,
  "events": [
    {
      "event_id":    "<string>",
      "ground_truth": 0 | 1,
      "predictions": {
        "<agent_id>": {
          "probability":  <float in [0,1]>,
          "archetype":    "<archetype_name>",
          "brier":        <float>,
          "stake_pct":    <float>,
          "llm_call_ms":  <int>
        }
      },
      "ensemble_mean":  <float>,
      "ensemble_brier": <float>,
      "jsd":            <float>
    }
  ],
  "srr_events": [
    {
      "agent_id":       "<string>",
      "prev_archetype": "<archetype_name>",
      "new_archetype":  "<archetype_name>",
      "trigger_brier":  <float>
    }
  ],
  "society_brier_7d": <float>,
  "society_jsd_7d":   <float>
}
```

The `srr_events` array is empty for all conditions except A and D.
In condition D (Sham-SRR), `new_archetype` changes but the agent's
actual system prompt does not; this is flagged by `"sham": true` in the
event record.

All fields are non-null for completed trading days. Incomplete days
(season still in progress) have `ground_truth: null` and `brier: null`
for unresolved events.
