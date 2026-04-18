# Nomos42 — Multi-Agent LLM Trading Floors with Evolution-Priced Edges

**Version:** v1.0 · April 2026
**Authors:** LBJLincoln (aka Nomos42)
**Status:** Living research note — updated every cycle. Treat code commits as authoritative.

> Bridging a 21-island genetic-algorithm fleet (Brier 0.22085 SOTA) to a 17-agent
> real-LLM trading floor with Axelrod coalitions, structural DMAD anti-groupthink,
> and Black-Scholes-priced options on political sector ETFs. Single live infra,
> zero mocks, zero synthetic data.

---

## 1. System Overview

Three coupled experiments run continuously on HuggingFace Spaces:

| Component                       | Agents | Purpose                                  | Live endpoint                                           |
|---------------------------------|:------:|------------------------------------------|---------------------------------------------------------|
| NBA LLM Trading Floor           | 17     | Per-game discrete bets, 23-90 categories | lbjlincoln26-nba-llm-trading-floor.hf.space             |
| Political LLM Trading Floor     | 17     | Sector-ETF discrete bets, daily          | lbjlincoln26-political-llm-trading-floor.hf.space       |
| Political Quant Trading Floor   | 6      | Options + multi-leg, 4 intraday sessions | lbjlincoln26-political-quant-trading-floor.hf.space     |
| Evolution Fleet (NBA)           | 13     | CPU genetic models, tree-ensemble only   | S10-S22 (13 Spaces)                                     |
| Evolution Fleet (Political)     | 8      | Parity fleet, political alpha categories | P1-P8 (8 Spaces)                                        |
| LLM Gateway                     | —      | Unified proxy, 11+ models, fallback chain| lbjlincoln26-llm-gateway.hf.space                       |
| Pixel World                     | —      | Bloomberg-aesthetic live visualization   | nomos42-pixel-world.static.hf.space                     |

Total: **21 evolution islands + 3 trading floors + 1 gateway + 1 pixel visualizer = 26 live HF Spaces.**

## 2. Data Foundations

- **NBA:** 1 247 games (2024-25 + 2025-26 seasons) · odds from Bovada/DK/FD · box-score
  derived features (tree-ensemble only on CPU islands; neural models blocked).
- **Political:** 1 120 events with event_type (FOMC/CPI/ELECTION/insider_trade/etc.),
  signal_sector → ETF routing, direction_bias ∈ {-1, 0, +1}, signal_strength ∈ [0, 1].
- **Engine parity invariant:** `features/engine.py` (local) ≡ `hf-space/features/engine.py`
  (all islands). Enforced at every evolution step. Currently v3.1-65cat · 6 434 raw features ·
  `MAX_FEATURES=200` hard cap.

## 3. The 17-Agent Trading Floor

### 3.1 Roster

| # | trader_id            | Model                              | Provider                 | Personality  | Risk |
|---|----------------------|------------------------------------|--------------------------|--------------|------|
| 1 | qwen-quant           | Qwen 3 235B-A22B                   | Cerebras                 | quantitative | 0.55 |
| 2 | qwen-arb             | Qwen 3 235B-A22B                   | Cerebras                 | arbitrage    | 0.65 |
| 3 | llama-contra         | Llama 3.1 8B                       | Cerebras                 | contrarian   | 0.55 |
| 4 | gemini-anl           | Gemini 3 Flash Preview             | Google (key 2)           | analytical   | 0.55 |
| 5 | gemini-tact          | Gemini 3 Flash Preview             | Google (key 2)           | tactical     | 0.60 |
| 6 | mistral-large        | mistral-large-latest               | Mistral                  | ensemble     | 0.50 |
| 7 | mistral-medium       | mistral-medium-latest              | Mistral                  | diversified  | 0.45 |
| 8 | mistral-small        | mistral-small-latest               | Mistral                  | conservative | 0.35 |
| 9 | mistral-nemo         | open-mistral-nemo                  | Mistral                  | aggressive   | 0.70 |
|10 | mistral-ministral    | ministral-8b-latest                | Mistral                  | theoretical  | 0.35 |
|11 | nemotron-120b        | NVIDIA Nemotron-3-Super-120B       | OpenRouter (free)        | chainthought | 0.55 |
|12 | selfhost-qwen4b      | Qwen3-4B (self-hosted CPU)         | selfhost:qwen3-4b        | disciplined  | 0.40 |
|13 | nvidia-minimax       | MiniMax M2.7                       | NVIDIA NIM (key 1+2)     | decisive     | 0.58 |
|14 | nvidia-llama70       | Llama 3.3 70B                      | NVIDIA NIM (key 1+2)     | swing        | 0.50 |
|15 | selfhost-gemma3      | Gemma-3-4B (self-hosted CPU)       | selfhost:gemma-3-4b      | analytical   | 0.45 |
|16 | selfhost-qwen06      | Qwen3-0.6B (self-hosted CPU)       | selfhost:qwen3-0.6b      | conservative | 0.30 |
|17 | selfhost-dolphin3    | Dolphin3-Llama-3.2-3B (self-hosted)| selfhost:dolphin3-l32-3b | uncensored   | 0.60 |

Identical roster on POL TF. Pqtf uses a 6-agent subset for options trading.

### 3.2 Collective Mission Preamble

Every agent's `system_prompt` is prefixed with the COLLECTIVE_MISSION block:

- "ONE of 17 LLM agents on the Nomos42 trading floor"
- "Same data seen by all; distinguished by personality + reasoning style"
- "Shared goal: grow $100 → $1 000 000 per trader by end of season (2026-11-03)"
- Hard rules: `≥75 % deploy per day`, `≥3 allocations per day`, structural-DMAD
  (coalition partner must use *different* reasoning_template), Axelrod Mech A-D
  (common knowledge + sacrificial rotation + post-mortem + pacts-with-reputation).

### 3.3 Stake Sizing (Kelly-Capped, Bankroll-Relative)

Previous bug (2026-04-14, commit a7d3eed8d) — stake used
`starting_bankroll × LLM-chosen pct`. Agents at 55-65 % WR still ruined to $0-42.

Current (2026-04-15+):

```
stake = min(
    current_bankroll × 0.05,              # 5 % hard cap
    half_kelly(p_model, odds_decimal),    # = 0.5 × (b·p − q) / b
) × allocation_weight
```

Plus:
- `min_edge = 0.03` — reject any allocation with implied edge < 3 %.
- `MIN_DEPLOY_PCT = 0.75`, `MAX_DEPLOY_PCT = 0.95` (normal operation).
- Preservation mode: `PRESERVATION_MAX_DEPLOY = 0.50`, moneylines only, no alt-spreads
  or parlays.

### 3.4 Provider Health & Hot-Swap

`provider_health.py` (commit cbb5cb1eb) tracks per-provider 5-minute error rate.
Dead provider → tier-matched hot-swap while preserving the agent's persona. Example:
cerebras down → swap qwen-quant to `mistral:large` (matched class, keeps
`quantitative` personality). Async self-heal rechecks every 30 s. Eliminates
survivor bias (older code simply dropped the agent — agents that lost to dead
providers looked worse than they were).

## 4. Axelrod Mechanisms (Cooperation Dynamics)

Anchored in Axelrod (1984) + the `axelrod-python` library (~240 canon strategies).

- **Mech A — Common Knowledge:** every agent is shown peer bankrolls each day.
- **Mech B — Sacrificial Rotation:** one agent per day takes the contrarian
  assignment (sacrificial_assignment). Rotated round-robin.
- **Mech C — Post-Mortem Log:** `AXELROD_LOG_DIR = /tmp/axelrod-log` persisted
  per-day jsonl. Fed into next-day system prompt (Karpathy-style iteration).
- **Mech D — Coalition Pacts + Reputation:** agents emit `coalition_proposal` in
  JSON output (MANDATORY since commit 412fc6a19). Reputation score bumped on
  kept pacts, decayed on broken pacts.
- **Structural DMAD** (Li et al. 2024): if two agents pact, they *must* use
  different `reasoning_template` (e.g. Kelly-calculus vs. Elo-expected-value).
  Prevents groupthink without sacrificing aggregation gain.

Per-trader canonical strategy (NICE / RETALIATORY / FORGIVING / PROVOCATIVE
family) is pinned in `AXELROD_STRATEGIES`.

## 5. Evolution Fleet (26 Islands at peak, 21 live)

### 5.1 Mutation Doctrine

- Tree-ensemble only on CPU (neural stacking blocked).
- `MAX_FEATURES = 200` at init / mutate / crossover (enforced 3x).
- Adaptive mutation rate capped at 0.15 (deployed S10/S11/S12/S15).
- Gap-threshold 0.20 → 0.12 for mutation-actuator trigger (prevents stagnation).
- Prediction-Arena ranking (arXiv 2604.07355) — 1-bet-per-agent head-to-head.

### 5.2 Current Leaderboard (2026-04-18)

| Island  | Repo                             | Model              | Gen  | Brier   | Notes                            |
|---------|----------------------------------|--------------------|-----:|:--------|----------------------------------|
| S17     | LBJLincoln26/nba-evo-s17         | ensemble           | 1142 | 0.22085 | ★ FLEET BEST                     |
| S18     | TESTforge42/nba-evo-s18          | catboost_spec      | 1030 | 0.22114 |                                  |
| S14     | Nomos42/nba-evo-5                | lightgbm           |  554 | 0.22186 |                                  |
| S19     | TESTforge42/nba-evo-s19          | wide_search        |  849 | 0.22257 |                                  |
| S15     | Nomos42/nba-evo-6                | wide search        |  127 | 0.22418 |                                  |
| S16     | LBJLincoln26/nba-evo-s16         | gradient_boost     |   86 | 0.22573 |                                  |
| S13     | Nomos42/nba-evo-4                | catboost           |  130 | 0.22749 |                                  |
| S10     | Nomos42/nba-quant                | exploitation       |   86 | 0.22825 |                                  |
| S20     | LBJLincoln26/nba-evo-s20         | isotonic_cpcv      |    0 | —       | Deployed 2026-04-15 (Prediction Arena 2604.07355) |
| S21     | LBJLincoln26/nba-evo-s21         | darwinian_weights  |    0 | —       | Deployed 2026-04-15 (atlas-gic PnL) |
| S22     | TESTforge42/nba-evo-s22          | venn_abers_fusion  |    0 | —       | Deployed 2026-04-15 (Venn-Abers fusion) |

Political parity fleet (P1-P8) achieves 0.24987 (P7, xgboost ensemble, gen 2098).

### 5.3 Colab / GPU Attestation

Fleet CPU-only. The 0.21570 (Colab T4 TabICL) and 0.21514 (Colab TabICL, 186f, iter 129)
numbers are out-of-fleet benchmarks from GPU attempts — not currently productionized
(TabPFN-2.5 GPU wrapper still WIP).

**Walk-forward:** avg 0.22447 over 19 weeks / 934 games on Kaggle (tree ensemble, no
TabICL on P100). CPCV-gated with DSR threshold. Real-pred match rate: 76 % (9-season
pool, 11 513 games).

## 6. Pqtf — Political Quant Trading Floor (Options, Intraday)

### 6.1 Architecture

- `engine.py` — pure 4-session intraday loop. No FastAPI, no Gradio imports at top.
- `options.py` — Black-Scholes pricer + Greeks (delta/gamma/theta/vega/rho) + Newton-IV.
- `intraday_paths.py` — GBM with event-timed jumps. IV scaling:
  FOMC × 1.60 · CPI × 1.45 · ELECTION × 1.80 · insider_trade × 1.00.
- `session_data.py` — event → 4-session router (09:30 / 12:00 / 14:30 / 16:00 ET).
- `spreads.py` — vertical / iron_condor / straddle / butterfly + portfolio-VaR
  + stop-loss + Reg T margin. stdlib only.
- `app.py` — FastAPI + Gradio + auto-resume + daily hub checkpoint.

### 6.2 Phase 1 — Single-Leg Options (shipped)

Per-session per-agent: `{ type: call|put, strike_multiplier, qty, tte_days }`.
Priced via BS at entry + mark-to-market each step. Mined 22 positions on day 1
(no multi-leg yet).

### 6.3 Phase 2 — Multi-Leg + Risk (shipped 2026-04-18, commit 91a099f79)

Four new strategies in `run_session`:

- `vertical` (bull_call / bear_put) · defined-risk, long + short same-type.
- `iron_condor` · 4-leg short vol, defined max loss.
- `straddle` · long or short ATM call+put (short blocked in defensive mode).
- `butterfly` · 3-strike, 4-leg, symmetric.

Per-session risk block persisted:

```json
"risk": {
  "var_95_1d": 17.83,
  "stops_triggered": 0,
  "n_multi_leg": 12,
  "n_single_leg": 10
}
```

Stop-loss at −50 % of entry cost. Portfolio VaR parametric (z=1.645 at 95 %).

### 6.4 Phase 2 — Silent-Fail Bugs Retrospective (2026-04-18)

Pqtf ran 3 days with 0 bets. Root-caused to 4 simultaneous silent failures:

1. `gateway_call(model=...)` — kwarg should be `model_key=...`. TypeError
   swallowed by a bare `except` in `default_call_llm`.
2. Gateway model-registry mismatch. `cerebras:qwen-3-235b-a22b-instruct-2507`
   → must be `cerebras:qwen-3-235b`. Three such renames across providers.
3. `MISTRAL_API_KEY` not set on the gateway Space. Every mistral call 404'd
   and fell through the fallback chain back to cerebras.
4. `GATEWAY_URL` set as *both* variable and secret → HF CONFIG_ERROR on boot.
   Must be variable only.

**Lesson (feedback memory):** when a TF Space shows `running:true` but
bankrolls are frozen, check in order: gateway/api/models vs AGENTS model_key,
gateway/api/chat `model_used` echo (should not be `fallback:true`),
Space vars-vs-secrets intersection, grep engine.py for silent
`except Exception: return None`.

### 6.5 Worker-Recycle Resilience (2026-04-18, commit 85e50b2c1)

HF CPU basic kills the worker every ~14 min. Full 50-day run needs ~5 h.

Solution in `app.py`:

- `_resume_from_hub()` — pulls every `data/decisions/day-NNN.json` from the
  Space repo, replays all positions' pnl into `agents_state`, rebuilds
  wins/losses, sets `days_done`.
- Checkpoint frequency 5 → 1 day (one hub commit per day).
- `_auto_resume_boot()` — on every Space startup with `AUTO_RESUME=1`, spawns
  a daemon thread that calls `run_experiment(max_days=N, resume=True)`.

Verified 2026-04-18 19:31Z: worker rebuild resumed from day-009 → days_done=10,
llama-contra $104 111 lead, 22 bets on day 10, daily checkpoint confirmed at
days 10-13 pushed to hub.

### 6.6 Phase 3 — Planned (not yet shipped)

- Alpaca / Yahoo options-chain ingestion (real strikes + real IV surface).
- Pairs trading (XLE / XLB basis, XLK / XLC basis).
- Vol-of-vol feature (rolling σ of σ).
- Slippage + bid-ask spread model.

## 7. Research Anchors (Papers in Production Use)

| Paper                                                              | arXiv        | Where Used                              |
|--------------------------------------------------------------------|--------------|-----------------------------------------|
| TradingAgents: Bull/Bear debate                                    | 2412.20138   | NBA TF prompt structure                 |
| Prediction Arena: 1-bet-per-agent                                  | 2604.07355   | S20 island + TF ranking                 |
| Agent Trading Arena (chart viz +40 %)                              | 2502.17967   | Dashboard /floor visualization          |
| TabPFN-2.5 (100 % win vs XGBoost)                                  | 2511.08667   | GPU roadmap (not yet productionized)    |
| DMAD (anti-groupthink)                                             | Li 2024      | Structural reasoning_template divergence|
| Axelrod "The Evolution of Cooperation"                             | 1984         | Mech A/B/C/D canon                      |
| atlas-gic Darwinian weights                                        | (repo)       | S21 island                              |
| Venn-Abers calibration fusion                                      | Vovk 2013    | S22 island                              |
| Skfolio CPCV gate                                                  | (repo)       | `scripts/arena/cpcv_gate.py`            |

## 8. Observability

- **Langfuse** — self-hosted on `Nomos42/langfuse` (v2.95.11, Supabase pooler :6543,
  `langfuse` schema). Secrets wired into both TF Spaces 2026-04-18. Every
  `default_call_llm` call emits `{prompt_head, thesis, model, dt}` trace.
- **Audit** — `scripts/audit/run_audit.py` runs every 4 h at :40. Five checks:
  leakage corr / bet-source divergence / WR outlier / lockstep / walk-forward.
- **Post-mortem** — `tf_postmortem.py` pulls `day-XXX.json` every 6 h, flags
  rationale vs. outcome divergence.

## 9. Monetization & Deadline

Hard constraint: **May 1 2026**. If no revenue by then, Claude Code access
shuts down May 8.

- Product: @Nomos42Picks Telegram, $19/mo via Stripe Payment Link.
- Targets: ≥5 subs = $95/mo by May 8.
- Publication surface: daily pick broadcast (NBA + political), OOS-gated.
  Never cite per-agent TF results as proof — use the walk-forward backtest
  (0.22447 Brier, 19 weeks) instead.

## 10. Reproducibility

Commits in this paper (April 2026):

```
91a099f79  feat(pqtf): Phase 2 — multi-leg spreads + portfolio risk
85e50b2c1  feat(pqtf): state resume from hub + daily checkpoint + AUTO_RESUME boot
412fc6a19  feat(tf): coalition MANDATORY + guardrails relaxed
1a7a02b48  fix(pol-tf): LEAKAGE — post-filter was using excess_return
cbb5cb1eb  feat(tf): provider_health + hot-swap + self-heal
b87d60d28  feat(tf): COLLECTIVE_MISSION + parlays + rogue triggers + Langfuse
ee652c387  feat(councils): niche rewrite + live arXiv per iteration
b08b4466a  fix(pixel-world): 17 real agents + full live leaderboard + stripped UI
```

Each commit is on GitHub `LBJLincoln/mon-ipad@main` plus subtree-pushed to the
relevant HF Space. All data (day-decisions, evolution snapshots, dept councils)
is persisted to the public HF repo under `data/`.

## 11. Known Gaps

1. **No unified walk-forward over the 17-agent period** — current backtest
   predates the NVIDIA + self-host additions.
2. **Phase 3 pqtf not shipped** — Alpaca/Yahoo chain + pairs + vol-of-vol +
   slippage.
3. **Cross-repo audit** — 4 sibling repos (nomos-dashboard, nomos-nba-agent,
   nomos-political-alpha, rgwa) last audited 2026-04-15. Drift possible.
4. **Revenue** — zero subs as of 2026-04-18. Deadline 13 days away.

— End v1.0 —
