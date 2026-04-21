# POL TF Losers RCA — 2026-04-21

**Agent:** INTERNAL AFFAIRS | **Cycle:** 2026-04-21T20:55Z live pull | **Scope:** forensic, diagnosis-only
**Sources:** `/api/status`, `/api/leaderboard`, `data/tf-analytics/pol/day-183.json` (pre-restart), `data/tf-analytics/pol/day-179.json..day-183.json` trajectory

---

## Executive summary

- POL TF is on fresh restart: **day 7/184, events 74/2153**. This is a statistically SHALLOW sample (6–24 bets per agent). Do NOT treat the current leaderboard as a verdict — it's early-run noise on many agents. BUT the **loss structure is already recognizable** and matches the NBA failure signature.
- Leaderboard splits **6 winners / 11 losers** roughly matching the NBA bimodality: winners are the **3 live-LLM providers that actually fired** (cerebras qwen-3-235b, google:gemini-3-flash, mistral:medium-small); losers are a mix of dead-provider agents forced onto fallback chains + active-but-low-WR agents (selfhost-qwen4b 14%, selfhost-gemma3 33%, mistral-large 33%).
- **gateway_call_count=6, gateway_fallback_count=92, direct_fallback_count=92**: 92/98 = **94% of calls went through the `direct_fallback` path**. Gateway is effectively bypassed. Every loser is trading on the fallback-uniform or direct-substitution output.
- `providers_dead` has 9 entries including `openrouter:nemotron-120b` (208 dead-seconds) — even the NBA's only-alive provider is now down on POL. Only alive: **mistral:medium, mistral:small** (2 of 11).
- 13/17 substitutions land on `mistral:medium` (66 in-window subs). Same single-point-of-failure pattern as NBA with nemotron-120b, but one provider different.

## Per-loser deep dive

| tid | bankroll | roi | bets | W/L | WR | provider | failure mode |
|---|---|---|---|---|---|---|---|
| selfhost-gemma3 | $7.88 | −92.1% | 6 | 2/4 | 33% | cerebras:llama3.1-8b (3042 dead) | Provider circuit-broken, routed to fallback `mistral:medium`. 6-bet sample insufficient for verdict, BUT 4 consecutive losses post-restart tells us early decisions were high-stake on miscalibrated edge. |
| selfhost-qwen4b | $9.09 | −90.9% | 7 | 1/6 | 14% | mistral:small (OK) | **Provider is ALIVE**, so this is LLM reasoning failure — producing inverted picks. Same signature as NBA mistral-small (16% WR). Likely prompt mis-formatted for small model. |
| mistral-large | $20.97 | −79.0% | 6 | 2/4 | 33% | mistral:large (118 dead) | Provider down, 4 substitutions-in-window. Fallback-identity loss. |
| nvidia-llama70 | $22.15 | −77.8% | 9 | 2/7 | 22% | nvidia:llama-3.3-70b (298 dead) | Persistent 298-sec dead-block. Sub-chain → mistral:medium. |
| nvidia-minimax | $25.19 | −74.8% | 6 | 2/4 | 33% | nvidia:llama-3.3-70b (via minimax, 180 dead) | Same provider death as nvidia-llama70. |
| mistral-ministral | $28.28 | −71.7% | 9 | 4/5 | 44% | mistral:small (OK) | Active LLM, coin-flip WR. Small sample (9 bets) — could be noise. |
| selfhost-qwen06 | $30.66 | −69.3% | 7 | 3/4 | 43% | mistral:small (OK) | Active LLM, coin-flip — small sample. Monitor; do not kill-switch yet. |
| nemotron-120b | $32.17 | −67.8% | 6 | 1/5 | 17% | mistral:large (118 dead) | Should be `openrouter:nemotron-120b` but provider is now DEAD on POL (208 sec). Sub to mistral:large, also dead. Deep fallback. |
| llama-contra | $46.73 | −53.3% | 28 | 12/16 | 43% | cerebras:llama3.1-8b (dead) | Highest-bet-count loser (28) = good sample. 43% WR below break-even. Circuit-broken provider. |
| selfhost-dolphin3 | $49.92 | −50.1% | 7 | 3/4 | 43% | mistral:large (dead) | Two dead providers. Sub chain indeterminate. |
| mistral-nemo | $52.00 | −48.0% | 6 | 1/5 | 17% | cerebras:llama3.1-8b (dead) | 17% WR on 6 bets — small sample but matches NBA's mistral-nemo 50% → bad provider routing. |

## Winners (for differential analysis)

| tid | bankroll | roi | bets | WR | provider | why it worked |
|---|---|---|---|---|---|---|
| qwen-arb | $538.40 | +438% | 24 | 63% | cerebras:llama3.1-8b (dead) | **Apparent anomaly**: provider dead but still winning. Looking at day-183 analytics: qwen-arb fired `FALLBACK_UNIFORM: broad-ETF long (SPY/QQQ/IWM)` and caught a bull-tape day. This is fallback-luck, NOT skill. Flag: monitor — expect reversion. |
| qwen-quant | $382.54 | +283% | 21 | 71% | cerebras:qwen-3-235b | **Real signal.** 71% WR on 21 bets, uses EV framework ("STRUCTURAL DIVERGE edge=7.2%") — active LLM reasoning visible in day-183 per_agent. Provider dead-count low. |
| gemini-anl | $314.43 | +214% | 17 | 65% | google:gemini-3-flash (245 dead) | Same pattern as NBA gemini-anl: live LLM + coherent reasoning. Provider dead 245 sec but substitution chain is shallow. |
| mistral-medium | $148.60 | +48.6% | 9 | 44% | mistral:medium (OK) | Provider healthy, 44% WR + favorable juice = slight positive. |
| mistral-small | $144.50 | +44.5% | 7 | 14% | mistral:small (OK) | **14% WR yet +44%** → winning via variance/outlier (one big parlay win). Not robust. |
| gemini-tact | $122.44 | +22% | 10 | 50% | google:gemini-3-flash | Break-even, small positive. |

## Cross-cutting findings

1. **Gateway is bypassed.** `gateway_call_count=6` vs `gateway_fallback_count=92` = gateway is returning fallback on 94% of requests. Either the gateway health endpoint is still bogus (see `project_tf_llm_reroute_apr20`), or TF's gateway_client is timing out and taking direct path. Either way, the centralized proxy is NOT doing its job.
2. **Same fabricated-edge problem as NBA (prompt_override active).** Prior RCAs confirm POL uses same post-filter path. POL just had $13K leakage fix 2026-04-18 (excess_return fallback removed), but the remaining `FALLBACK_UNIFORM: broad-ETF long SPY/QQQ/IWM` path is still live — qwen-arb rode it to +438% in bull tape, could reverse to −70% in one bad week.
3. **Dead provider cluster overlaps NBA.** The 9 dead providers on POL = 9 dead on NBA minus `openrouter:nemotron-120b` (dead on POL, OK on NBA). This strongly suggests provider outages are **fleet-wide infrastructure issues**, not TF-specific. SWITCHBOARD should treat this as a platform-level incident.
4. **Small-sample trap.** With 6–24 bets per agent, per-agent WR has CI ±20 percentage points. The "winners vs losers" bimodal may collapse within 30 more days. Do NOT make personnel decisions (kill personas) on current data — wait for ≥30 bets/agent.
5. **mistral:small winning despite 14% WR** (mistral-small agent) = one +EV parlay lottery ticket. This is the same variance pattern that killed NBA gemini-anl from peak $170 to $29. Fleet has no guardrails against outlier winners reverting.

## Proposed patches (prioritized)

| # | File / Space | Change | Predicted effect | Reversibility |
|---|---|---|---|---|
| 1 | Same as NBA patch #1: `scripts/arena/hf-political-trading-floor/app.py` fallback emitter | Force `action=cash` on `llm_failed_both` + substitution-chain-depth ≥2. Remove the `FALLBACK_UNIFORM broad-ETF long` path — this is the POL analog of NBA's top-3-ML fabricated bet. | Kills "fallback bull-tape luck" for qwen-arb and 92 direct_fallback bets. | Single-line flag. |
| 2 | SWITCHBOARD platform-level | Treat 9-dead-provider condition as **incident**: post `data/ops/switchboard-alert.json`, notify THE BOSS, pause TFs until provider fleet OK. Today's state is infra outage masquerading as trading signal. | Stops both NBA + POL from running when 9/11 providers dead. | Incident flag. |
| 3 | app.py `_load_prompt_override("pol")` | Require LLM reply to include (a) catalyst cite, (b) edge ≥0.06 (raised from 0.03), (c) no reference to "SPY/QQQ/IWM proxy" (fallback signature). Reject matching responses. | Breaks the mistral:small lottery pattern. | Prompt config. |
| 4 | app.py — gateway client | Audit why `gateway_call_count=6 / direct_fallback_count=92`. Likely a timeout config or URL drift. Fix = real gateway usage = better model routing. | Unlocks centralized health/routing. | Client config. |
| 5 | Monitor-only | **DO NOT kill-switch POL yet** — day 7/184 is too shallow. Re-audit at day 14, day 30. If bimodality persists with bigger samples, then apply patches 1+3. | — | — |

## Kill-switch recommendation

**DO NOT pause POL.** Sample too shallow (6–24 bets/agent) for statistical verdict. But **DO pause the direct_fallback path immediately** (patch #1 above) — qwen-arb's +438% is fallback-luck, and the 11 losers share the same fallback infra that's producing uncorrelated bets. The quality of any future day's data depends on fixing fallback first.

**Signed**: INTERNAL AFFAIRS — 2026-04-21T20:55Z
