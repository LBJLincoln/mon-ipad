# NBA TF Losing-Streak RCA — 2026-04-21

**Author:** SWISH | **Scope:** pure diagnosis, no deploy | **Source:** live `/api/status` + INTERNAL AFFAIRS audit `2026-04-21T1240.json` + CK block (d17) + day-127 analytics.

## Root cause (one sentence)
**The fabricated post-filter "edge" field is uncorrelated with outcomes, and ~70% of agent bets are coming from the UNIFORM_FALLBACK path (LLM infra 58% dead) which reads that edge at face value — so the fleet is mass-betting miscalibrated top-of-list picks in lockstep.**

## Evidence (numbers, not vibes)
- **LLM dead rate:** 5/17 agents have `llm_calls=17, llm_ok=0` (mistral-ministral, nvidia-minimax, nvidia-llama70, selfhost-gemma3, selfhost-dolphin3). Another 4 at llm_ok ≤ 6/17. Provider-health dict: 7 providers circuit-broken (cerebras ×2, mistral large/medium, github ×2, nvidia:minimax). Only `openrouter:nemotron-120b` OK. Gateway routed 3/16 calls.
- **Fallback identity signature:** five above agents all land at **exactly $44.66 / 34 bets / 47% WR / DD 55.34%** — proof they share a deterministic path (UNIFORM_FALLBACK top-3 ML even-split), not independent reasoning.
- **Edge calibration failure:** d1 (2025-10-17) fallback bets priced at edge=5.43% / 3.24% / 2.31% went 1W/2L across all 10 fallback agents on the same three games. Sample-wide: mistral-small 1W/56L (1.8% WR) on "edge ≥3%" — expected ≥52% at true 3% edge. Edge field has zero predictive signal.
- **Lockstep critical:** audit shows NBA day-042/043/044 share_pct = 93.8% / 100% / 100%. DMAD/jitter defeated by fallback determinism.
- **Fleet state:** 7/17 below $20 survival floor, group $452.69 / $1,700 (−73.4%), top agent gemini-anl $66.80 (−33.2%). `fleet_best_bankroll` in status confirms.
- **Parlays not the culprit:** council plan mentions parlays but d17 CK block shows 0 parlay bets logged; all losses are straight singles. Parlay hypothesis rejected.

## 3 fixes (smallest-first)
1. **Kill the UNIFORM_FALLBACK edge-trust path.** When LLM fails, force CASH (not "bet top-3 ML"). Removes 60%+ of bleeding bets instantly, zero model changes. One-line change in `app.py` fallback emitter. Owner: DR FRANKENSTEIN.
2. **Recalibrate the post-filter edge computation.** Current "edge=5.4%" is fabricated from tier-padding (the 2026-04-20 RCA we already wrote on TF/Brier noise floor). Raise MIN_EDGE survival-tier floor to 0.06 (matches POL), add prompt-display floor 0.03. Owner: DR FRANKENSTEIN + LOBBYIST parity.
3. **SWITCHBOARD hard-reroute the 7 dead providers** to the 3 confirmed-alive lanes (openrouter:nemotron-120b, google:gemini-3-flash, selfhost:qwen3-4b). Re-verify with `scripts/ops/llm_live_monitor.py`. Today's window_breaker has cerebras/mistral locked out for 3600s — they need new homes, not retry. Owner: SWITCHBOARD.

## Kill-switch recommendation
**PAUSE NBA TF.** Current run is scientifically contaminated (lockstep=1.0, 60%+ fallback bets, no LLM reasoning). Every additional day logs garbage into `data/tf-analytics/nba/`. Stop run, apply fix #1 + #3, reset via `/api/reset` + factory_reboot (`project_tf_state_persistence_apr19.md`), restart. Fix #2 can land in a follow-up cycle after baseline recovers.

`Sxx acted: none (diagnosis cycle). Fleet best Brier: 0.22073 (S22, unchanged). Mutation avg: n/a.`
