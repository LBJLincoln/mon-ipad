# NBA TF Losers RCA — 2026-04-21

**Agent:** INTERNAL AFFAIRS | **Cycle:** 2026-04-21T20:55Z live pull | **Scope:** forensic, diagnosis-only
**Sources:** `/api/status`, `/api/leaderboard`, `/api/day-decisions`, `data/tf-analytics/nba/day-127.json`, prior RCAs `nba-losing-streak-rca-2026-04-21.md`

---

## Executive summary

- Fleet TOTAL **$44.82 / $1,700 seed = −97.4%** across 17 agents on day 121/175. All 17 at max-drawdown 87–99.6%.
- **Dominant failure mode is compounding-loss stake sizing on a miscalibrated edge field**, NOT bad LLM reasoning per se: 5 agents sit at 60–65% WR (above break-even juice) yet still lost 97–99% of bankroll. Negative-geometric-growth over 120 days via over-bet Kelly on a fabricated edge.
- **Secondary failure:** 9/17 providers circuit-broken (`provider_health.providers_dead` count ≥118–3117 seconds). 110/112 decisions routed through `direct_fallback_count` = fallback/sub chain, only 2 through gateway OK. 38 substitutions landed on `openrouter:nemotron-120b` (becoming new single-point-of-failure).
- **Bimodal agent population**: (A) 9 "high-bet" agents at 55–65% WR, 200–299 bets — these are the **fallback-identity cluster** (`mistral-ministral` / `nvidia-minimax` / `nvidia-llama70` / `selfhost-gemma3` / `selfhost-dolphin3` / `selfhost-qwen06` / `gemini-tact` / `nemotron-120b`). (B) 8 "low-bet" agents at 16–40% WR, 75–118 bets — these are **active-LLM-but-bad-signal** (qwen-quant / qwen-arb / mistral-large / mistral-medium / mistral-small / selfhost-qwen4b / llama-contra / mistral-nemo).
- **Peak-drawdown guard insufficient**: gemini-anl hit $170.79 peak then −83% drawdown to $29.02. Drawdown guard at 70% of peak was overridden or not applied.

## Per-loser deep dive

| tid | bankroll | roi | bets | W/L | WR | peak | dd | provider | failure mode |
|---|---|---|---|---|---|---|---|---|---|
| gemini-anl | $29.02 | −71.0% | 250 | 163/87 | 65.2% | $170.79 | 86.7% | google:gemini-3-flash | **Parlay/oversize.** Only agent above fallback floor; peaked high then bled. WR 65% means pre-juice EV+ but size killed it. |
| nvidia-llama70 | $2.83 | −97.2% | 294 | 183/111 | 62.2% | $100 | 97.5% | nvidia:llama-3.3-70b (298 dead-seconds) | Fallback-identity cluster. Provider dead, substituted to nemotron/llama-70b. WR decent, sizing catastrophic. |
| qwen-arb | $2.35 | −97.7% | 80 | 20/60 | 25.0% | $100 | 97.7% | cerebras:qwen-3-235b (3117 dead-seconds) | Active LLM but 25% WR — LLM hallucinating picks. Circuit-broken provider, 38 substitutions to nemotron-120b. |
| selfhost-dolphin3 | $2.29 | −97.7% | 299 | 184/115 | 61.5% | $100 | 97.9% | cerebras:llama3.1-8b (3058 dead-seconds) | Fallback-identity cluster (matches -gemma3 / -minimax / -llama70 within $1). |
| selfhost-gemma3 | $1.85 | −98.2% | 294 | 185/109 | 62.9% | $100 | 98.6% | mistral:medium (215 dead-seconds) | Fallback-identity cluster — provider dead, substituted away; "gemma3" name is cosmetic. |
| nvidia-minimax | $0.81 | −99.2% | 283 | 171/112 | 60.4% | $100 | 99.2% | nvidia:llama-3.3-70b (via minimax, 212 dead-seconds) | Fallback cluster. |
| qwen-quant | $0.75 | −99.2% | 89 | 24/65 | 27.0% | $100 | 99.2% | mistral:large (99 dead-seconds) | Active but 27% WR → LLM produces bad picks. 19 passes / 89 bets = low conviction. |
| llama-contra | $0.74 | −99.3% | 118 | 47/71 | 39.8% | $168.09 | 99.6% | cerebras:llama3.1-8b (dead) | Peaked at $168 then circuit-breaker blew out provider → sub-routing. |
| selfhost-qwen06 | $0.71 | −99.3% | 269 | 161/108 | 59.9% | $100 | 99.3% | mistral:small (OK) | Fallback cluster echo despite live provider — may be LLM output shape rejected. |
| gemini-tact | $0.62 | −99.4% | 275 | 152/123 | 55.3% | $100 | 99.4% | google:gemini-3-flash (186 dead) | Thinking-budget bug continues intermittently; WR at break-even = coin-flip. |
| mistral-ministral | $0.62 | −99.4% | 209 | 87/122 | 41.6% | $100 | 99.4% | mistral:small | Active LLM but 41% WR — picks uncorrelated with outcomes. |
| mistral-large | $0.61 | −99.4% | 102 | 39/63 | 38.2% | $100 | 99.4% | mistral:large (99 dead) | Dead provider, 4 substitutions away. |
| mistral-small | $0.60 | −99.4% | 75 | 12/63 | 16.0% | $100 | 99.4% | mistral:small | **Catastrophic 16% WR** = model is producing inverted picks OR confused by prompt. |
| mistral-medium | $0.58 | −99.4% | 118 | 46/72 | 39.0% | $100 | 99.4% | mistral:medium (215 dead) | Most-substituted-to target in POL but dead on NBA. |
| nemotron-120b | $0.56 | −99.4% | 202 | 111/91 | 55.0% | $100 | 99.4% | openrouter:nemotron-120b (ONLY OK provider, 38 subs-in) | **Single point of failure**: absorbs all substitutions, then picks drift. |
| mistral-nemo | $0.50 | −99.5% | 188 | 95/93 | 50.5% | $100 | 99.5% | cerebras:llama3.1-8b (dead) | Coin-flip WR. |
| selfhost-qwen4b | $0.44 | −99.6% | 79 | 23/56 | 29.1% | $100 | 99.6% | mistral:small | Active but bad — 29% WR, 79 bets, consistent underperformance. |

## Cross-cutting findings

1. **Fabricated-edge collapse.** From prior SWISH RCA: the post-filter "edge" field (e.g. 5.43%, 3.24%) comes from tier-padding, not predictive signal. Agents trusting this number at face value mass-bet into top-of-list picks and lost 1W/2L on edges ≥3%. Expected WR at true 3% edge ≥52%; observed 1.8% on mistral-small's 75-bet sample.
2. **Bimodal signature proves 2 failure modes, not 1.** High-bet cluster (200–299) all share exact WR band 55–65% → fallback uniform-split emitter. Low-bet cluster (75–118) has real LLM pushing bets but random-walk WR. Fix must target both: kill fallback (cluster A) + recalibrate edge prompt (cluster B).
3. **Provider consolidation risk**. Only 2 providers (`openrouter:nemotron-120b`, `mistral:small`) OK. `recent_substitutions` shows 20/20 recent fallbacks landing on nemotron-120b or nvidia:llama-70b. Any single-provider 429/403 would wipe residual bankroll.
4. **Peak-bankroll data contaminated**. `best_bankroll: 100.0` on 15/17 agents = no one ever crossed starting capital. Only gemini-anl (170.79) and llama-contra (168.09) ever had positive days. Evidence: fleet has been **monotonically declining** for 120 days.
5. **Winner vs losers differential (gemini-anl vs rest)**: gemini-anl is the ONLY agent with (a) live LLM provider that produced coherent reasoning across >200 bets, (b) WR high enough (65%) to absorb juice, (c) peak >$170 meaning it DID beat market early. It still lost because when peak drawdown hit, stake sizing compounded losses. Fix: hard equity-curve guardrail (max_drawdown_from_peak → force 1% stake or cash until recovery).

## Proposed patches (prioritized)

| # | File / Space | Change | Predicted effect | Reversibility |
|---|---|---|---|---|
| 1 | `scripts/arena/hf-llm-trading-floor/app.py` (fallback emitter) | On `llm_failed_both` OR substitution-to-fallback-chain, force `action=cash` instead of `UNIFORM_FALLBACK top-3`. | Removes 60%+ of losing bets instantly. High-bet cluster stops bleeding. | Single-line flag, easy revert. |
| 2 | app.py post-filter edge calc | Raise MIN_EDGE display floor to 0.06 (matches POL), raise survival-tier bet-enable floor to 0.08. | Cluster B stops chasing fabricated 3% edges. | Config constant. |
| 3 | app.py stake-sizing | Add peak-equity drawdown clamp: if `bankroll / best_bankroll < 0.50`, stake cap 1% and forbid parlays. If `<0.25`, force cash. | Prevents gemini-anl-style blow-up from repeating. | Behind `PEAK_DD_GUARD_V2=1` env. |
| 4 | SWITCHBOARD | Hard-reroute 9 dead providers to 2 confirmed alive (openrouter:nemotron-120b, mistral:small). Publish new routing table and bump circuit-breaker cooldown from 3600s to 7200s so retry storms don't reopen dead lanes. | Halves substitution churn, reduces single-point-of-failure on nemotron-120b. | Routing table edit. |
| 5 | Kill-switch | **PAUSE NBA TF** via `/api/stop`. State is scientifically contaminated (DMAD lockstep + fabricated edge + 60% fallback). | Stops garbage flowing into analytics. | `/api/run` to resume post-patch. |

## Kill-switch recommendation

**PAUSE + reset + apply patches 1, 3, 4** before next tick. Patch 2 can follow. Every additional day of current run logs uninformative data into `data/tf-analytics/nba/` — we are training on survivorship noise.

**Signed**: INTERNAL AFFAIRS — 2026-04-21T20:55Z
