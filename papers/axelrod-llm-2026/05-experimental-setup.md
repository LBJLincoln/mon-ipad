# 4. Experimental Setup

This section specifies, in full detail, the experimental instantiation of
the LPSG framework (§3). We report datasets (§4.1), agent pool (§4.2), the
gateway and inference pipeline (§4.3), evaluation metrics (§4.4), baselines
and ablations (§4.5), compute and reproducibility (§4.6), and statistical
protocol (§4.7). Our objective is a level of detail sufficient for
independent replication given the released code and data.

---

## 4.1 Datasets

We evaluate on two non-overlapping event populations.

### 4.1.1 NBA — 2025-26 Regular Season

The *NBA corpus* comprises **1,257 games** spanning the full 2025-26
regular season (2025-10-21 through 2026-04-12), sourced from official NBA
box scores and cross-referenced against Kaggle public box-score corpora.
Each game has a binary outcome $Y_k = 1$ if the home team wins and $Y_k = 0$
otherwise. Moneyline odds are captured from a consensus-median over five
books (DraftKings, FanDuel, BetMGM, Caesars, Bovada) at $T - 60$ minutes
before tip-off; we use the median to reduce book-specific microstructure
noise. Per-game context includes full team stats (season-to-date offensive
and defensive ratings, pace, turnover rate, eFG%, recent five-game form),
head-to-head history, roster/injury status, and location.

### 4.1.2 Political — 2025-26 Event Stream

The *political corpus* comprises **1,120 binary-outcome US political
events** spanning 2025-10-01 through 2026-04-10. Events are drawn from a
curated union of (i) Polymarket-listed binary propositions that resolved
in-window and (ii) ground-truth events from officially reported outcomes
(elections, votes, nominations, judicial rulings, regulatory announcements).
All events have objective, third-party-verifiable resolution. Context
includes prior polling, market price history, endorsement signals,
political-calendar fixtures, and relevant news summaries.

### 4.1.3 Train/Evaluation Split and Windowing

We do not fine-tune LLMs; consequently there is no training split. The
*evaluation protocol* is strictly causal: on day $t$, each agent sees only
$x_{t,\cdot}$ and the common-knowledge block $\mathcal{K}(t)$ composed from
days $1, \ldots, t-1$. All reported metrics are forward-walking, giving no
agent access to future information. Sliding windows of length $W_{\mathrm{eval}}
= 90$ days are used for diversity–accuracy correlation analysis (§5, §6).

### 4.1.4 Preprocessing and Release

Event IDs, resolutions, odds snapshots, and pre-event contexts are released
as part of the paper's replication bundle at
`data/arena/axelrod-log/` (see §4.6). All preprocessing code — tokenization,
prompt composition, odds median computation, leaderboard formatting —
is deterministic and is included in the release.

---

## 4.2 Agent Pool

### 4.2.1 NBA Pool (12 agents)

The NBA LPSG is instantiated with $N = 12$ heterogeneous LLM agents drawn
from five provider ecosystems. Table 2 summarizes the pool.

| ID | Model | Provider | Axelrod-1980 seed strategy | Starting archetype $\pi^{(1)}$ |
|---|---|---|---|---|
| T1 | Qwen-3-235B-A22B-Instruct | Cerebras | *TitForTat* [@axelrod1980effective] | *quantitative-bayesian* |
| T2 | Qwen-3-235B-A22B-Instruct | Cerebras | *Grudger* | *arbitrage-specialist* |
| T3 | Llama-3.1-8B | Cerebras | *SuspiciousTitForTat* | *contrarian* |
| T4 | Gemini-3-Flash-Preview | Google | *TitFor2Tats* | *narrative-fundamental* |
| T5 | Gemini-3-Flash-Preview | Google | *TwoTitsForTat* | *momentum-chase* |
| T6 | Mistral-Large-Latest | Mistral | *WinStayLoseShift* | *risk-parity* |
| T7 | Mistral-Medium-Latest | Mistral | *GenerousTitForTat* | *market-maker* |
| T8 | Mistral-Small-Latest | Mistral | *Cooperator* | *ablation-skeptic* |
| T9 | Open-Mistral-Nemo | Mistral | *Defector* | *chaos-contributor* |
| T10 | Ministral-8B-Latest | Mistral | *FirmButFair* | *mean-reverter* |
| T11 | Nemotron-3-Super-120B | OpenRouter | *Adaptive* | *quantitative-bayesian* |
| T12 | Phi-3.5-Mini (self-hosted) | HuggingFace Space | *Tullock* | *ablation-skeptic* |

*Table 2. NBA agent pool. "Axelrod-1980 seed strategy" refers to the
canonical 1980-tournament strategy [@axelrod1980effective] attached as a
background prior via the axelrod-python library; this is a soft bias on
cooperation decisions (Mech D). "Starting archetype" is the initial LPSG
archetype $\pi^{(1)}$; agents may be reassigned by SRR (§3.4).*

The pool was constructed with deliberate redundancy: multiple model families
(Cerebras-Qwen, Google-Gemini, Mistral-Large family, OpenRouter-Nemotron,
self-hosted-Phi) and, within Mistral, multiple scales (Large/Medium/Small/Nemo/Ministral)
to enable per-family and per-scale ablations (§4.5).

### 4.2.2 Political Pool (10 agents)

The political LPSG uses a 10-agent subset comprising T1–T10 of the NBA pool;
Nemotron-120B (T11) and the self-hosted Phi-3.5 (T12) are excluded from the
political run as they did not reliably emit structured allocations on political
event contexts in pilot studies. The same Axelrod-1980 seeds and initial
archetypes are used.

### 4.2.3 Prompt Templates

Each archetype $\tau \in \mathcal{T}$ corresponds to a prompt template block
of $\sim$200–400 tokens describing the decision frame and expected
output schema. Full templates are released in the paper's appendix
(`papers/axelrod-llm-2026/appendix-A-prompts.md`) and in the codebase at
`scripts/arena/hf-llm-trading-floor/app.py`. All agents share the
common-knowledge block $\mathcal{K}(t)$ and the "Axelrod canon" reminder
prefix (see §3.3, §3.6).

---

## 4.3 Inference Pipeline

### 4.3.1 LLM Gateway

All agent calls are routed through a single gateway Space
(`LBJLincoln26/llm-gateway`) that provides (a) unified provider abstraction
with per-provider back-off on rate limit, (b) automatic fallback across
model families when a primary provider is unavailable, and (c) centralized
request logging for reproducibility. Direct provider calls are used only as
a fallback when the gateway is unreachable.

### 4.3.2 Sampling Hyperparameters

Default sampling parameters are $\text{temperature} = 0.8$, $\text{max\_tokens} = 4{,}096$,
$\text{top\_p} = 0.95$. For the Gemini-3 family we additionally set
$\text{thinkingBudget} = 0$: the reasoning trace is disabled because Gemini
thinking consumed the full token budget in pilot runs, producing empty
structured outputs. Full hyperparameters per model are listed in
`appendix-B-hyperparameters.md`.

### 4.3.3 Output Parsing

Agents are prompted to emit a JSON block containing per-event
$(\hat{p}, s, \text{rationale})$ triples, prefaced by free-form reasoning.
We parse the JSON using a two-stage pipeline: (i) regex extraction of the
first valid JSON block, then (ii) schema validation with graceful fallback
to per-line field extraction. The fallback handles $\sim$4\% of responses
in which the JSON is malformed but the intent is recoverable from the
rationale text. Parses that fail both stages are recorded as "no-bet days"
with $s_{i,t,\cdot} = 0$ and counted in the `llm_failures` telemetry
surfaced by `/api/status`.

### 4.3.4 Stake Sizing

LLM-proposed stakes $s^{\mathrm{raw}}$ are capped via half-Kelly with a
5% per-event maximum and a 0.03 minimum edge threshold, giving the final
$s_{i,t,k}$ used in Kelly payoff computation (§3.1). This cap replaces an
earlier pipeline in which raw LLM stake proposals caused full bankroll
depletion; the fix was validated on a backtest of days 1–27 of the NBA
corpus prior to the main experimental run.

---

## 4.4 Evaluation Metrics

We report the following metrics on both corpora.

**Per-agent and per-day.**
- *Brier score* $B_{i,t,k}$ — primary calibration metric.
- *Kelly bankroll* $b_{i,t}$ — primary capital metric.
- *Win rate* — fraction of placed bets with $\hat{p} \cdot Y + (1-\hat{p}) \cdot (1-Y) > 0.5$.

**Population-level.**
- *Ensemble Brier* $\mathrm{Brier}(\hat{p}_t^{\mathrm{ens}})$ — Brier of the
  agent-mean prediction.
- *Collective Jensen–Shannon divergence* $\mathrm{JS}(t)$ — diversity,
  measured on per-agent prediction distributions over all same-day events.
- *Ambiguity* $A(t) = \bar{B}_t - \mathrm{Brier}(\hat{p}_t^{\mathrm{ens}})$
  — derived from Krogh–Vedelsby [@krogh1995neural].
- *Cooperation pact density* — number of proposed/honored pacts per day,
  by category.
- *SRR frequency* — fraction of days on which at least one agent was
  sacrificed; mean number of sacrifices per day.

### 4.4.1 Calibration Diagnostics

We additionally report reliability diagrams at 10-bin, 20-bin, and
isotonic-smoothed calibration for both the individual agent with the best
average Brier and the ensemble prediction. Expected calibration error (ECE)
and the Brier decomposition (reliability, resolution, uncertainty) are
computed per bin.

---

## 4.5 Baselines and Ablations

We compare the full Axelrod-LLM system against the following configurations.
All baselines run on the same 1,257-game NBA and 1,120-event political
corpora with the same agent pool.

| Label | Mech A | Mech B (SRR) | Mech C | Mech D | Stake rule |
|---|:---:|:---:|:---:|:---:|---|
| *Full LPSG* (ours) | ✓ | ✓ | ✓ | ✓ | Half-Kelly 5% cap |
| *No-SRR* | ✓ | ✗ | ✓ | ✓ | Half-Kelly 5% cap |
| *No-CK* | ✗ | ✓ | ✓ | ✓ | Half-Kelly 5% cap |
| *No-Pacts* | ✓ | ✓ | ✓ | ✗ | Half-Kelly 5% cap |
| *DMAD-style* | ✗ | ✗ | ✓ | ✗ | Adversarial prompt rotation [@liu2025dmad] |
| *Fixed-ensemble* | ✗ | ✗ | ✓ | ✗ | Half-Kelly 5% cap |
| *Single-model-best* | — | — | — | — | Single best-Brier agent only |
| *Market-consensus* | — | — | — | — | Odds-implied probability |

*Table 3. Baseline and ablation configurations.*

The *No-SRR* ablation is the primary test of Proposition 2 (§3.7): does SRR
measurably increase ensemble ambiguity and decrease ensemble Brier? The
*No-CK* ablation tests whether common-knowledge broadcast is necessary or
sufficient. The *DMAD-style* baseline instantiates the external-adversarial
prompting approach of [@liu2025dmad] within our architecture, providing a
direct comparison against the state-of-the-art diversity mechanism that
preceded our work. *Market-consensus* — a zero-reasoning baseline using the
odds-implied probability — provides the minimum acceptable calibration
floor.

---

## 4.6 Compute, Cost, and Reproducibility

### 4.6.1 Compute

All inference is performed on provider-hosted LLM endpoints; we use no
fine-tuning. The orchestration layer runs on a single 1-vCPU, 16 GB
HuggingFace Space per corpus. Total wall-clock per full-season run is
$\approx$4–6 hours per corpus, dominated by provider rate limits (not
throughput). The gateway multiplexes across 22 providers (Table 4, released
separately) giving effective $\sim$40 LLM calls per minute population-wide.

### 4.6.2 Cost

Per full-season run, the marginal API cost on paid tiers is $\leq \$4$ USD
across all 12 NBA agents plus 10 political agents. The Cerebras, Gemini-3,
and self-hosted Phi-3.5 paths are zero marginal cost at our tier. Total
cost across the 20+ runs reported in this paper was $\leq \$80$.

### 4.6.3 Reproducibility and Release

We release the full experimental stack:

- **Code.** Both trading-floor Spaces source
  (`scripts/arena/hf-llm-trading-floor/`,
  `scripts/arena/hf-political-trading-floor/`), gateway Space source
  (`scripts/arena/hf-llm-gateway/`), prompt templates, and analysis
  notebooks.
- **Data.** Event IDs, resolutions, odds snapshots, and pre-event
  contexts at `data/arena/axelrod-log/`.
- **Logs.** Per-day Mech-C post-mortem JSONL records preserving the full
  trajectory of $\langle$agent, bankroll, archetype, sacrifice flag,
  consensus distance$\rangle$ for every day $t \in \{1, \ldots, T\}$.
- **Replication instructions.** `papers/axelrod-llm-2026/appendix-C-replication.md`.

LLM non-determinism introduces a source of between-run variance that we
characterize by running the Full LPSG configuration *five times* with
different random seeds (controlling only the sampling RNG for SRR archetype
draws). Between-run variance is reported in §6 alongside point estimates.

---

## 4.7 Statistical Protocol

**Paired comparisons.** All baseline-vs-LPSG comparisons use a paired
bootstrap with $B = 10{,}000$ resamples at the per-day level, preserving
the within-day correlation across agents.

**Multiple comparisons.** We report both raw p-values and Holm–Bonferroni
adjusted p-values across the six pairwise comparisons in Table 3.

**Effect sizes.** Brier differences are reported in absolute points with
95% bootstrap CIs. Bankroll differences are reported as percentage of
starting bankroll with matching CIs. $\mathrm{JS}$ divergence differences
are reported in nats with 95% CIs.

**Pre-registration.** The four mechanisms (A–D), the ten-archetype
taxonomy, the SRR hyperparameters $(W, \epsilon, \beta) = (7, 1.0, 2.0)$,
the evaluation metrics, and the baseline set (Table 3) were frozen in a
pre-registration document committed to the repository at
`papers/axelrod-llm-2026/preregistration.md` *before* the first full-season
run initiated. Any post-hoc analyses are explicitly marked as such in §6.

---

## 4.8 Runtime Telemetry

During each run, the orchestrator emits telemetry to `/api/status` every
LLM call including counters $\langle$*llm_calls, llm_failures,
gateway_routed, cooperation_pacts_count, sacrificial_assignments,
reputation*$\rangle$. Full per-day logs (Mech C) are exported via
`/api/axelrod-log` to the version-controlled store. This telemetry is the
ground truth for all tables and figures in §6.

---

With the experimental protocol fixed, §5 presents results on the full
datasets across all baselines, including the primary ablation test of
Proposition 2 and the calibration-diversity coupling of Proposition 1.
