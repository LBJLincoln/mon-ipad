# Appendix B — Hyperparameters and Provider Configuration

All hyperparameters below are frozen at the pre-registration date
(2026-04-16, git `df0d0d72c`) and apply identically to both the NBA and
political corpora unless explicitly noted. Values marked **(default)** are
those used in the Full LPSG configuration reported in §5.

---

## B.1 Sacrificial Role Reallocation (SRR, Mech B)

| Symbol | Value | Description |
|---|---|---|
| $W$ | $7$ | Rolling-window length (days) over which per-agent cumulative Brier is measured. |
| $\epsilon$ | $1.0$ | Threshold on normalized Brier-gap $g_i^{(t)}$ above which an agent enters the sacrificial candidate pool. |
| $\beta$ | $2.0$ | Boltzmann temperature in the reassignment probability $P(\pi \mid i) \propto \exp(-\beta \cdot \mathrm{count}(\pi))$. |
| $M$ | $10$ | Archetype taxonomy size (§3.4.1, Appendix A). |
| $\rho$ | $0.15$ | Target sacrificial population fraction (top-$\rho N$ candidates enter the pool). |
| Seed count | $n = 5$ | Independent SRR random seeds for between-seed replication (§5.7). |

## B.2 Coalition Pacts and Reputation (Mech D)

| Symbol | Value | Description |
|---|---|---|
| Pact acceptance threshold | $\geq 2$ mutual | Both agents must independently propose the pact on day $t$ for it to enter the ledger. |
| `pact_honored` increment | $+1$ per pact | Per-peer reputation delta when both agents execute the proposed category on the proposed game. |
| `pact_broken` increment | $+1$ per pact | Per-peer reputation delta when the counterparty fails to execute. |
| Reputation decay | None | The reputation ledger is cumulative over the full season. |

## B.3 Common-Knowledge Broadcast (Mech A)

| Symbol | Value | Description |
|---|---|---|
| Broadcast position | Prompt block 2 of 5 | After `AXELROD_CANON`, before archetype (§A). |
| Leaderboard size | Top-5 + Bottom-3 | Identity + bankroll; reputation counters for all agents. |
| JS divergence | Computed nightly | Reported as part of the broadcast. |
| Stackelberg leader | Top-1 bankroll yesterday | Receives explicit "leader" role suffix in system prompt. |

## B.4 Kelly Stake-Sizing Guardrails

Introduced after the 2026-04-14 stake-sizing regression (agents with
60–65 % hit-rate draining bankroll to \$0 due to uncapped LLM-chosen bet
fractions). Applied uniformly across all baseline configurations.

| Symbol | Value | Description |
|---|---|---|
| `MAX_PCT_PER_BET` | $0.05$ | Half-Kelly cap on any single bet as fraction of current bankroll. |
| `MIN_EDGE` | $0.03$ | Minimum edge estimate below which the agent's proposed bet is dropped. |
| `MIN_STAKE` | \$0.50 | Minimum dollar stake; bets below this are dropped. |
| `BANKRUPT_THRESHOLD` | \$5.00 | Agent is paused (no LLM call) if bankroll falls below this. |

## B.5 LLM Sampling Parameters

All agents use identical sampling parameters; structural diversity is
induced via (a) model-family choice (§4.2) and (b) prompt archetype
(§A).

| Parameter | Value | Notes |
|---|---|---|
| `temperature` | $0.3$ | Provider-agnostic. Low temperature favors well-calibrated probability outputs over creative exploration. |
| `max_output_tokens` | $4096$ | Sufficient for the JSON-schema response (§A.3). |
| `response_mime_type` | `application/json` | Enforced where providers support it (Google Gemini). Otherwise we rely on prompt engineering + robust parser (§4.3.3). |
| `top_p` | $1.0$ | Provider default. |
| `thinking_budget` | $0$ | **Critical for Gemini.** Without explicit zero, thinking tokens consume the entire output budget and the response is empty. This was the root cause of the 2026-04-14 "Gemini 0-bets" regression. |
| Gateway timeout | $30\,\mathrm{s}$ | Per-call deadline. Agents returning timeout are logged as `llm_failures` and default to full-cash for the day. |
| Direct-fallback timeout | $20\,\mathrm{s}$ | Used when the LLM gateway is unavailable. |
| Max retries | $1$ | One retry on transport error; no retries on 4xx. |

## B.6 Per-Provider Rate Limits

Rate limits are enforced client-side via a per-provider token bucket
before each call. These are the floors (we never exceed them); provider
throttles may be more aggressive in practice.

| Provider | RPM | Min interval (s) | Models in use |
|---|---|---|---|
| Cerebras | $30$ | $2.00$ | `qwen-3-235b-a22b-instruct-2507`, `llama3.1-8b` |
| Google Gemini (key 2) | $14$ | $4.29$ | `gemini-3-flash-preview` |
| Mistral | $20$ | $3.00$ | `mistral-large/medium/small/nemo/ministral-8b` |
| OpenRouter (free tier) | $10$ | $6.00$ | `nvidia/nemotron-3-super-120b:free` |
| Self-hosted (HF Space) | $\infty$ | $0.00$ | Phi-3.5-mini (CPU, ~8 s/call wall time) |

## B.7 Intra-Day Parallelism

Added 2026-04-16 after initial full-season runs projected ~29 h
wall-clock. Intra-day agent decisions fire concurrently via
`ThreadPoolExecutor(max_workers=16)`; day-sequential ordering is
preserved because the Mech-A common-knowledge broadcast on day $N+1$
depends deterministically on day $N$ resolution.

| Symbol | Value | Description |
|---|---|---|
| `max_workers` | $\min(\lvert\mathrm{TRADERS}\rvert, 16)$ | Pool size per day. |
| Per-agent timeout | $30\,\mathrm{s}$ | Hard deadline inside worker; worker returns `None` on exception. |
| Phase-2 serialization | Yes | State mutations (bankroll, bets, logs) happen in strict agent-order after Phase 1 completes. |

Measured speed-up: **~10–12×** throughput versus sequential (the
per-day floor is set by the slowest provider's one-call latency plus its
rate-limit interval, not by the agent count).

## B.8 Evolution-Island Feeder (Optional, Not Part of LPSG)

Included for reproducibility of §5's "ensemble-vs-island" baseline. The
eight NBA evolution islands (S10–S17) are independent XGBoost/LightGBM/
CatBoost fleets and are **not** part of the LPSG mechanism. The
market-consensus baseline does not use them.

| Symbol | Value | Description |
|---|---|---|
| `MAX_FEATURES` | $200$ | Feature-subset cap per individual. |
| Mutation cap | $0.15$ | Adaptive mutation upper bound. |
| Best fleet Brier | $0.22114$ | S18 catboost-specialist, gen 1030, 2026-04-15. Not used as input to LPSG — reported for context only. |

---

## B.9 Reproducibility Notes

- All random seeds (SRR reassignment, coalition tie-breaking) are
  derived from a single top-level `SEED` environment variable. The five
  replicate runs set `SEED ∈ {1, 2, 3, 4, 5}` (§4.7).
- LLM provider model checkpoints are logged per-call in the Mech-C
  post-mortem (`data/arena/axelrod-log/{nba,political}/day-NNN.jsonl`).
  Replication requires the same checkpoint strings; see Appendix C.
- The ten archetype templates (Appendix A) are embedded verbatim in the
  two Space apps. Changes require a new pre-registration.
