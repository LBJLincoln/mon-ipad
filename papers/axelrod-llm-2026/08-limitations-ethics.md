# 7. Limitations and Ethics

We document the known limitations of our experimental setup and methodology
(§7.1–§7.4) and then address ethical concerns specific to LLM agents placing
real-money-equivalent bets in real-world prediction markets (§7.5–§7.7).

---

## 7.1 LLM Non-Determinism and Reproducibility

Our agents are closed-weight models accessed through commercial APIs. Even
with fixed sampling parameters, the output distribution conditional on a
prompt is not strictly reproducible: providers update model checkpoints
without always versioning them explicitly, and per-call sampling stochasticity
is controlled by the provider. We mitigate this in three ways:

- We report Full LPSG results as the mean across $n = 5$ independent runs
  with different SRR sampling seeds, with between-run standard deviation
  (§5.7).
- The Axelrod-python canonical-strategy library [@axelrod2022python] is
  fully deterministic and runs locally, providing a checkable floor on
  agent behavior in coalition-pact decisions (Mech D).
- The common-knowledge broadcast (§3.3) is deterministic given the
  resolution data, and is logged in full.

Despite these mitigations, exact replication of our quantitative results
requires the same provider checkpoints. We report the exact model-version
strings returned by each provider in Appendix B and note any model-version
drift during the experiment window in the replication instructions
(`appendix-C-replication.md`).

---

## 7.2 Ground-Truth Exogeneity

The LPSG as specified (§3) assumes ground-truth outcomes $Y_{t,k}$ are
exogenous: agent actions do not influence event resolution. This holds
in our evaluation corpora (NBA games, political events) because agent
stakes are virtual and do not interact with the markets from which odds
are sourced.

In deployment scenarios where agent actions do move markets (executing
financial trades at non-trivial size, for example), endogeneity would alter
the fitness landscape and potentially the stability of SRR. A rigorous
extension to the endogenous-GT setting would require (i) a market-impact
model, (ii) a stability analysis of SRR under outcome feedback, and
(iii) empirical validation in a controlled sandbox. We do not undertake
this here; we flag it as a necessary condition for responsible deployment
in capital markets.

---

## 7.3 Dataset Scope

Two scope limitations apply.

**Single season, two domains.** The NBA corpus is the full 2025-26
regular season (1,257 games); the political corpus is the 2025-26
US event stream (1,120 events). We do not report multi-year generalization.
SRR's benefit may depend on the specific within-season structural
stability (e.g., stable team rosters) that does not hold across seasons.
Multi-season replication is straightforward given the released
infrastructure and is listed as future work.

**Geographic and cultural coverage.** Both domains are US-centric. The
political corpus specifically excludes non-US events. Our archetype
taxonomy was constructed from primarily-English superforecaster literature
and Western quantitative finance traditions. We do not claim that the
archetype taxonomy generalizes to non-Western cultural contexts; external
validity beyond US English-language prediction markets is an open
question.

---

## 7.4 Provider Bias, Model Opacity, and Commercial Concentration

Our agent pool spans five provider ecosystems (Cerebras, Google, Mistral,
OpenRouter, self-hosted). All of the closed-weight providers impose
rate limits, intermittent outages, and opaque model-lifecycle decisions
that we cannot control. The 16% fraction of llm_failures that we observe
in pilot studies (recorded in `/api/status`) is attributable to provider-side
issues and not to experiment design. This introduces an unavoidable
source of variance that we account for by reporting between-run variance
(§5.7) but cannot eliminate.

A deeper concern is that our ensemble, despite spanning multiple
providers, may share a common upstream training corpus. The Llama, Qwen,
Mistral, and Gemma families all derive from similar web-scale pretraining
data. This means our ensemble is not maximally diverse at the level of
*training distribution*, even if it is diverse at the level of
*prompt-conditioned output distribution*. This is a well-known issue in
LLM-ensemble research [@liu2025dmad] and does not invalidate our results,
but it should be kept in mind when interpreting the magnitude of the
SRR effect: SRR induces prompt-level diversity, which is a strict subset
of the possible diversity available if training-distribution diversity
were also present.

---

## 7.5 Ethics of Real-World Prediction-Market Deployment

The LPSG is a research framework. Deploying it to place real-money bets
on sports or political events raises three distinct ethical concerns:

**Sports betting and addiction.** The NBA corpus resolves to real
professional basketball games with active betting markets. Optimizing
bet-placement algorithms contributes to a broader research program on
automated sports betting that, if deployed consumer-facing, can enable
gambling addiction [@parke2016online]. We do not release consumer-facing
applications, and the code release is explicitly for academic
replication. We urge researchers building on this work to consider the
deployment pathway from framework → commercial product → consumer harm.

**Political prediction markets and influence risk.** Our political corpus
resolves on binary US political events. Large-scale LLM agent participation
in political prediction markets (e.g., Polymarket) could, in principle,
affect the market-derived probability estimates that journalists and
policymakers increasingly use [@arrow2008promise]. We limit our
experiments to *virtual* bankrolls with no on-chain transactions; any
extension to real-capital political prediction markets requires explicit
consideration of market-manipulation risk and regulatory compliance
(e.g., CFTC approval in the US).

**Dual-use of multi-agent coordination mechanisms.** Mech D (coalition
pacts + reputation) is, in form, a mechanism for inducing coordinated
action across LLM agents. This is useful in our research setting but is
structurally similar to coordinated-opinion-manipulation mechanisms. We
release the full implementation precisely because defensive understanding
of such mechanisms is impossible without open-source reference code; we
note the dual-use concern explicitly.

---

## 7.6 Statistical and Interpretive Caveats

**Pre-registration scope.** The pre-registration (§4.7) fixes mechanisms,
metrics, and baselines but does not pre-register specific numerical
thresholds for "significant" effects. Holm–Bonferroni correction on the
six primary comparisons gives a conservative family-wise error rate of
$\alpha = 0.05$; effects smaller than the corrected critical value are
reported but not interpreted as confirmatory.

**Attribution ambiguity.** Full LPSG vs Fixed-ensemble compares *four*
mechanisms simultaneously. The ablation table (§5.1) attempts to isolate
individual mechanism contributions, but interactions among mechanisms
cannot be ruled out. If, for example, SRR and CK broadcast interact
super-additively, the No-SRR and No-CK ablations will under-estimate the
main effect of each. We report only direct pairwise comparisons; a full
$2^4$ factorial design is future work (§7.9).

**Selection bias in the agent pool.** The 12 NBA / 10 political agents
were selected to span provider families; they are not a random sample of
"all LLM agents." Results may not generalize to agent pools dominated by
a single family (e.g., all-OpenAI or all-Anthropic ensembles).

**Market-consensus baseline.** The market-consensus baseline uses
consensus-median odds from five books (§4.1.1). If the book consensus
already prices the "true" probability efficiently, even a perfect LLM
predictor could only match, not exceed, market Brier. We report market
Brier as the floor against which we measure; exceeding market Brier is
the ambitious benchmark.

---

## 7.7 Reproducibility Threats Specific to LLM-Agent Papers

Three reproducibility concerns are acute for LLM-agent systems and merit
explicit treatment.

**Checkpoint drift.** Provider-side model updates may shift agent outputs
over the course of the experiment window. We log the `model_version` field
returned by each API call in the Mech-C post-mortem and report any drift
detected in the full-season trace.

**Rate-limit variance.** Providers throttle differently at different
times of day; this can shift which agent "decides first" on any given
day and through the broadcast affects peer decisions. Our pipeline runs
all 12 NBA agents in parallel for each day with a fixed 10-second
timeout per call; agents that exceed the timeout default to the
market-consensus probability and are flagged in the log.

**Infrastructure cost.** Running the full experimental pipeline (Full
LPSG + six ablations × two corpora × five seeds = 70 runs) requires
approximately 280 hours of orchestrator wall-clock and $\leq \$600$ in
marginal API costs at current provider pricing. We release the pipeline
at a state where a single full-season run is cheap (<\$4) and replicable
(4–6 hours); the full factorial extension is accessible to labs with
research-grade cloud budgets.

---

## 7.8 Open Questions and Future Work

We catalogue the open questions raised but not answered by this work:

- *Optimal taxonomy size.* What $M$ maximizes diversity–accuracy coupling
  for a given agent pool size $N$? (§6.5)
- *SRR in the endogenous-GT setting.* Under what market-impact assumptions
  does the Nash-refinement result of Proposition 1 survive? (§7.2)
- *Cross-domain transfer.* Does an LPSG trained on NBA coordination
  transfer to political coordination, i.e., does the common-knowledge
  broadcast enable cross-corpus meta-learning? (§6.6)
- *Adversarial robustness.* Can a strategic subset of agents exploit the
  reputation mechanism to inject false common knowledge? The `pact_broken`
  field is a direct measurement of adversarial behavior; large-scale
  adversarial study is future work.
- *Factorial ablation.* Full $2^4$ factorial on Mech A/B/C/D would resolve
  attribution ambiguity (§7.6).

These questions, and the mechanisms that might resolve them, are summarized
in §8.
