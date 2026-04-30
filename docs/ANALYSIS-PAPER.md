# Nomos42 — Pattern Analysis & Mathematical Dashboard

**Authors:** Nomos42 LLM Trading Floor research team
**Date:** 2026-04-30
**Version:** 1.0 (post-carte-blanche-reset)

A short technical paper summarizing the Trading Floor architecture A/B (Carte-Blanche solo vs TauricResearch debate-chain), the post-reset audit, the mathematical path to $1M, and the open data-quality issues we know about.

---

## 1. Architecture A/B

We run **two parallel NBA trading floors** with identical inputs (Oracle, odds, standings, full-odds menu, 17 LLM personas) but different decision-making flow:

### 1.1 Carte-Blanche solo (existing)

Per agent per day:
1. Single LLM call with full game context + persona + Axelrod-cooperation canon
2. LLM emits JSON: `{ allocations: [...], parlays: [...], cash_held_pct: 0.X }`
3. Server scales total deploy UP to 30% of bankroll if LLM picks less. Server does NOT inject new bets (post-2026-04-30 reset).

### 1.2 TauricResearch debate-chain (new — `nba-tauric-trading-floor`)

Per agent per day, **3 LLM calls in sequence**:

| Pass | Persona | Output | Provider |
|---|---|---|---|
| 1. BULL | "Find the strongest bullish case" | 3-6 sentence text | Cerebras llama3.1-8b (cheap) |
| 2. BEAR | "Counter-argue every claim" (sees pass 1) | 3-6 sentence text | Cerebras llama3.1-8b |
| 3. TRADER (synthesis) | "Decide given both" (sees passes 1+2) | JSON allocations | Agent's primary model |

All 3 text blobs persist in `day_log[tauric_bull_case]`, `day_log[tauric_bear_case]`, `allocations` (from synthesis). Full audit trail per agent per day.

**Hypothesis:** debate-chain produces better-calibrated decisions (anti-groupthink, structured opposing-view) at 3× LLM cost. We measure: fleet $, hit-rate, Brier, days-to-double.

---

## 2. Post-reset audit results (Day 0,1,2,3 — Carte-Blanche)

**Pre-reset state (110 days run, observed 2026-04-29):**

```
Fleet:   $1,400  / $1,700 seed (-18%)
Forced bets:     79.2% of all 500 sampled allocations
Lockstep:         9 of 17 agents got IDENTICAL forced bets on the same day
Real LLM picks:   only 8.6% (engine source, LLM-edge-overridden)
Top agent:        $322 (selfhost-qwen4b)
```

**Post-reset (Day 0):**

| metric | value |
|---|---|
| forced bets | **0.0%** (was 79.2%) |
| sources | `engine: 11`, `llm_capped: 6` (all real LLM picks) |
| sovereign PASS days | 7/17 agents (no edge → no bet — allowed by doctrine) |
| rationale specificity | 100% concrete (player out, ref tendency, line move) |

**Day 1 winners:**
| agent | bankroll | Δ |
|---|---|---|
| mistral-ministral | $217.84 | **+143%** |
| mistral-small | $132.66 | +33% |
| gemini-tact | $131.58 | +32% |

**Day 2:** -$33 on mistral-ministral (game variance), but **0% forced** maintained.

---

## 3. Mathematical path to $1M

### 3.1 Compound horizon

| daily rate | $100 → $1M | $94K → $1M (ITF) |
|---|---|---|
| 5% | 189 days | 48 days |
| 7% | 136 days | 35 days |
| **10%** | **97 days** | **25 days** |
| 15% | 66 days | 17 days |

### 3.2 What 10%/day requires (Kelly arithmetic)

For a binary bet at decimal odds $b$ and win probability $p$:

$$f^* = \frac{b \cdot p - (1-p)}{b}$$

$$E[r] \text{ per bet} = (p \cdot b - (1-p)) \cdot f^*$$

Using the actual NBA Oracle calibration (CV Brier 0.22054, isotonic-calibrated):

| scenario | win prob | Kelly | E[r]/bet | bets to 10%/day |
|---|---|---|---|---|
| edge 0.05 floor | 55% | 6% | 0.28% | 36 ❌ |
| **edge 0.08, Kelly 10% (PQTF)** | **58%** | **10%** | **1.08%** | **9** ✅ |
| edge 0.10, Kelly 15% | 60% | 15% | 2.19% | 5 ✅ |
| edge 0.15, Kelly 20% | 62% | 20% | 3.68% | 3 ✅ |

**Conclusion:** Carte-blanche doctrine provides the scaffolding (deploy floor, no forced bets, free Kelly within personality cap) for agents to reach 9-bets/day at 8% edge floor — the proven PQTF $244K winner pattern.

---

## 4. Known data quality issues

### 4.1 Odds clustering bug (5 categories stuck on 1.91)

Our forensic odds audit (last 10 days × 17 agents = 218 sampled allocations) found:

| category | n bets | unique odds | issue |
|---|---|---|---|
| `prop_points_star1_home` | 9 | **1** | All 1.91 (fake hardcoded) |
| `spread_away_minus8.5` | 3 | 1 | All 1.91 |
| `prop_rebounds_role2_away` | 3 | 1 | All 1.91 |
| `prop_rebounds_role2_home` | 3 | 1 | All 1.91 |
| `alt_spread_home_minus18` | 3 | 1 | All 2.32 (also fake) |

**Cause:** `data/full-odds-2025-26.json` contains 249 categories per game but historical data covers only 802 games. When LLM picks a category not in the historical data, the legacy `get_odds_dec()` fallback returns 1.91 (from `app.py:2699`). Outcomes are then resolved against fake odds → randomized loss/win.

**Fix in flight:** drop bets where category absent from historical odds (instead of fake-1.91), AND eventually expand `data/full-odds-historical-2017-2026.json` (already pushed for ML categories per memory `nba_market_features_apr29`).

### 4.2 Possible home/away confusion (under investigation)

User-reported observation; rationale text references e.g. "MIN's strong home advantage" on a `MIN@SAC` game where MIN is the AWAY team. Need to verify whether:
- LLM is correctly interpreting `home_team` / `away_team` fields
- The `_format_game_block` rendering is consistent
- The persona prompt makes home/away unambiguous

### 4.3 Lockstep (FIXED post-reset)

Pre-reset: `engine_forced_floor` injected the engine's top-3 edges to ANY agent whose LLM emitted 0 allocations → 9/17 agents bet identically every day. Killed by `NBA_ENGINE_FORCED_FLOOR=0`.

---

## 5. Live observability

### 5.1 Dashboards
- **CEO `/audit` page (Vercel):** [nomosdashboard.vercel.app/audit](https://nomosdashboard.vercel.app/audit)
  - **ALL FLEETS** tab — every TF in one screen, 60s auto-refresh
  - **NBA · Live (structured)** — per-day timeline + per-agent drill-down + lockstep detector
- **Per-trade rationale:** click any agent in the audit grid

### 5.2 Trading Floors (HF Spaces)
- NBA carte-blanche: [LBJLincoln26/nba-llm-trading-floor](https://huggingface.co/spaces/LBJLincoln26/nba-llm-trading-floor)
- NBA Tauric: [LBJLincoln26/nba-tauric-trading-floor](https://huggingface.co/spaces/LBJLincoln26/nba-tauric-trading-floor)
- POL: [LBJLincoln26/political-llm-trading-floor](https://huggingface.co/spaces/LBJLincoln26/political-llm-trading-floor)
- ITF: [LBJLincoln26/intraday-trading-floor](https://huggingface.co/spaces/LBJLincoln26/intraday-trading-floor)
- ITF Tauric: [TESTforge42/itf-tauric-trading-floor](https://huggingface.co/spaces/TESTforge42/itf-tauric-trading-floor)

### 5.3 Overnight monitor
- Cron `0 * * * *` runs `/home/termius/mon-ipad/scripts/ops/overnight_monitor.sh` hourly
- Snapshots all 4 TFs + Alpaca → `data/ops/overnight-snapshots/YYYY-MM-DD-HHMM.md`
- Auto-restarts dead Spaces (RUNTIME_ERROR / CONFIG_ERROR / BUILD_ERROR)
- Commits + pushes every cycle

### 5.4 Code paths (for engineers)
- `scripts/arena/hf-llm-trading-floor/app.py` — NBA carte-blanche (~5300 lines)
- `scripts/arena/hf-llm-trading-floor-tauric/app.py` — NBA Tauric (forked, 3-pass `_agent_llm_worker`)
- `scripts/arena/hf-intraday-trading-floor/app.py` — ITF
- `scripts/arena/hf-intraday-trading-floor-tauric/app.py` — ITF Tauric
- `scripts/ops/overnight_monitor.sh` — autonomous monitor

---

## 6. Open questions / next experiments

1. **Does Tauric beat Carte-Blanche?** Need 30+ days both running. First metric: fleet $ delta vs seed; second: top-1 agent $ delta.
2. **Home/away confusion:** Audit 100 random rationales, classify "correct" / "ambiguous" / "wrong-side".
3. **Odds bug fix:** Drop bets on categories absent from `full-odds-historical-2017-2026.json` instead of faking 1.91.
4. **Selfhost LLM Tauric:** Use the 5 alive selfhost LLMs as the BULL/BEAR pass (zero rate-limit). Currently using Cerebras for debate.

---

## 7. References

- TauricResearch/TradingAgents (55.7K stars) — [github.com/TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)
- arXiv 2412.20138 — Multi-Agents LLM Financial Trading Framework
- `RESULTS.md` (this repo) — single-line CEO summary
- `MEMORY.md` (assistant memory) — incident & doctrine evolution log
- `CLAUDE.md` (this repo) — architecture overview

