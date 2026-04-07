# Nomos42 Trading Floor — Scientific-Experiment Master Plan

> **Purpose:** This file is the canonical brief for `/ultraplan` (Anthropic's
> cloud planning feature, released 2026-04-07). Run `/ultraplan @PLAN.md` to
> have Claude Code on the web draft the next implementation step in CCR with
> three parallel subagents + a critique pass.

**Last refresh:** 2026-04-07
**Repos in scope:**
- `LBJLincoln/mon-ipad` (NBA Quant — engine, gates, dashboards)
- `LBJLincoln/nomos-political-alpha` (Political Alpha — Cat 1-22 features)
- `LBJLincoln/nomos-dashboard` (Next.js 16 read-only UI)

---

## North-star

Build a **single, parity-correct, scientifically-gated trading experiment**
that runs continuously for **both NBA and Political**, using:

1. The same starting bankroll (NBA $100, Political $100K — *normalized to
   `growth_factor = final / initial` so both are scale-comparable*)
2. The same 5 named AI traders (claude / codex / gemini / grok / openrouter)
3. The same scientific gate (CPCV + DSR + PBO from López de Prado 2024)
4. The same "real OSS" debate engine (TauricResearch/TradingAgents) and the
   same "real OSS" agent-society engine (camel-ai/oasis) — both vendored

Every promotion to the live trading floor MUST clear this gate. No strategy
ever runs live without `dsr > 0 at p < 0.05 and pbo < 0.40`.

---

## Current state (as of 2026-04-07 12:35 UTC)

### NBA — green
- ✅ `scripts/arena/cpcv_gate.py` running, 7 backtest runs in pool
- ✅ `scripts/arena/continuous-backtest-swarm.sh` cron 6×/day → fold files
- ✅ 9-season backfill (`backfill_games_2025_26.py`) — 11,513 games
- ✅ 102 betting categories (`bet_categories.py`)
- ✅ Bull/Bear debate UI on `/trading-floor` (mon-ipad 2f73c16f)
- ✅ 102-cat heatmap on `/trading-floor` (nomos-dashboard 1cdf6d2)
- ⚠️ Only `spec_spread` has positive Sharpe so far (sr=4.76±2.85, 665 bets)
- ⚠️ DSR rejects everything until pool ≥ 24 runs (~4 days from now)

### Political — yellow → green (this commit)
- ✅ NEW: `scripts/arena/political_cpcv_gate.py` (parity with NBA gate)
- ✅ NEW: `scripts/arena/continuous-political-backtest-swarm.sh` cron 6×/day
- ✅ NEW: cron entry installed (`17 */4 * * *`)
- ✅ Seeded with 1 fold from existing `political-trading-floor-latest.json`
- ⚠️ Needs ≥3 folds for DSR (will have 18 folds in ~12h)
- ❌ `data/arena/political-arena-v2.json` still 7d stale — Phase B
- ❌ `/political/page.tsx` has hardcoded DONOR_UNIVERSE / MOCK_EVOLUTION — Phase B

### Vendored OSS (real, official, no more "lightweight adaptations")
- ✅ `vendor/TradingAgents/` — TauricResearch/TradingAgents @ HEAD
- ✅ `vendor/oasis/` — camel-ai/oasis @ HEAD (was MiroFish)
- ✅ `scripts/vendor/clone-vendor.sh` bootstraps both on any new VM
- ✅ `vendor/` is in `.gitignore` (each VM clones locally)
- ❌ Not yet wired: `scripts/arena/debate_round.py` still calls api_pool
  directly. Migration to real `tradingagents.graph.trading_graph` is planned
  in **WORKSTREAM 2** below.

### HF Spaces council
- ✅ Karpathy scheduler bumped from 2×/day → 4×/day (cron `0 1,7,13,19`)
- ✅ Last real iteration: 04:24 UTC today (NBA, iter 30, Brier 0.215448)
- ✅ Last political iter: 04:28 UTC, iter 30, brier 0.230493 / best 0.204543
- ✅ Spaces are *executing real work*, not just keepalive blabbering
- ⚠️ Best HF space Brier (0.22182, S14 catboost) still > Colab TabICL (0.21570)

---

## Workstreams for `/ultraplan`

Each workstream is a discrete unit. Feed PLAN.md to `/ultraplan` and ask it
to design one workstream end-to-end (the three_subagents_with_critique
variant is ideal: one agent reads existing code, one drafts changes, one
identifies risks, then a critique agent rejects unsafe steps).

### W1 — Real LangGraph debate, not adapter
**Goal:** Replace `scripts/arena/debate_round.py` (lightweight adapter) with
a real call into `vendor/TradingAgents/tradingagents/graph/trading_graph.py`.

**Files to read first:**
- `vendor/TradingAgents/main.py` (entry point)
- `vendor/TradingAgents/tradingagents/graph/trading_graph.py`
- `vendor/TradingAgents/tradingagents/agents/researchers/{bull,bear}_researcher.py`
- `scripts/arena/debate_round.py` (current lightweight version)
- `scripts/arena/trading-floor-v5.py` (caller, line 800-850 area)

**Constraints:**
- VM has 1 vCPU / 969 MB. Real LangGraph debates need to be DRY-RUN by default.
- Use `OPENAI_API_KEY` from `.env.local` (free Groq via OpenAI compat).
- Output schema must match what `nomos-dashboard/src/app/trading-floor/page.tsx`
  `BullBearDebatePanel` expects: `{rounds: [{bull, bear}], judge: {...}}`.
- Fall back to current adapter on any exception.

**Acceptance:** One real run produces a `_peer_review.debate` block in
`data/arena/trading-floor-v5-latest.json` whose `judge.model` is the real
LangGraph judge ID, not `"claude-fallback"`.

---

### W2 — OASIS swarm for T3 Specialist tier
**Goal:** Task #10 — replace the static T3 Specialist tier with a real
camel-ai/oasis agent society where 100+ specialists evolve via interaction.

**Files to read first:**
- `vendor/oasis/oasis/social_agent/agent.py`
- `vendor/oasis/examples/twitter_simulation/`
- `scripts/arena/agent_registry.py` (current T3 registration)
- `data/arena/agent-states-v5.json` (current state shape)

**Constraints:**
- OASIS needs an LLM backend — use HF Inference Router (Qwen 2.5 free tier)
- T3 generates predictions, NOT social posts → fork the agent template
- Cap memory at 200 MB total for the entire swarm

**Acceptance:** `data/arena/agent-states-v5.json` has ≥50 active T3 agents
with `provider: "oasis"` and the v5 floor consensus uses their predictions.

---

### W3 — Bankroll parity refactor (NBA $100 → $100K)
**Goal:** Make NBA and Political identical at the bankroll level so the
"same starting bankroll" claim is literal, not just normalized.

**Files to read first:**
- `scripts/arena/trading-floor-v4.py` (lines 178-235 — 5 trader configs)
- `scripts/arena/trading-floor-v5-real.py`
- `scripts/arena/political-trading-floor.py` (line 36 — `INITIAL_CAPITAL = 100_000.0`)
- `data/arena/traders/*-state.json` (live state — must migrate or freeze)

**Decision needed before coding:**
- Option A: NBA → $100K (preserves political, breaks $100 narrative on /trading-floor)
- Option B: Political → $100 (preserves $100→$1M narrative, makes political
  positions absurdly small)
- Option C: Add a `display_bankroll = bankroll * scale` field that the UI
  multiplies, so internal math stays as-is. **Recommended.**

**Acceptance:** Both `/trading-floor` and `/political` show the same starting
capital with the same `growth_factor` semantics.

---

### W4 — Dashboard de-staling (Phase B)
**Goal:** Fix everything the audit found (audit ran 2026-04-07 12:09 UTC).

**Hardcoded mocks to remove:**
1. `nomos-dashboard/src/app/political/page.tsx` lines 80-111 (DONOR_UNIVERSE)
2. `nomos-dashboard/src/app/political/page.tsx` lines 115-152 (MOCK_EVOLUTION + MOCK_KAGGLE_LOG)
3. `nomos-dashboard/src/app/api/nba/backtest/route.ts` lines 61-236 (`generateBacktest()` deterministic-RNG)
4. `nomos-dashboard/src/app/api/forge-metrics/route.ts` lines 6-39 (FALLBACK_METRICS)
5. `nomos-dashboard/src/app/evolution/page.tsx` lines 181-188 (static ATR history)

**Stale data files to refresh (mtime > 2 days old):**
- `data/arena/political-arena-v2.json` (7d) → write from political-trading-floor.py
- `data/nba-agent/backtest-h2-*.json` (10d) → re-run continuous-backtest-swarm.sh
- `data/forge-users/*.json` (7d) → forge user sync cron
- `data/player-tracking/*.json` (7d) → nba_api playertracking re-ingest

---

### W5 — Continuous analysis daemon
**Goal:** Every 30min, a daemon reads the latest CPCV gate output for both
NBA and Political, computes deltas vs the previous run, posts a Telegram
update if a strategy crosses the gate, and writes
`data/arena/cpcv-watcher-state.json` for the dashboard ticker.

**Files to create:**
- `scripts/arena/cpcv_watcher.py`
- `nomos-dashboard/src/app/api/arena/cpcv-watcher/route.ts`
- New panel on `/trading-floor` showing live CPCV deltas

**Acceptance:** When `political_cpcv_gate.py` first promotes a strategy
(currently 0/5 passing), the user gets a Telegram message within 30min.

---

## How to invoke /ultraplan

From any Claude Code session in `/home/termius/mon-ipad`:

```
/ultraplan @PLAN.md — design W1 (real LangGraph debate replacement) end-to-end
```

Anthropic's CCR will:
1. Spawn 3 parallel subagents (read existing code / draft changes / risk audit)
2. Run a critique pass that rejects unsafe edits
3. Return a browser link with the proposed plan
4. On approval, either execute remotely (creates a PR on `LBJLincoln/mon-ipad`)
   or teleport the plan back to your terminal for local execution

**Sources:**
- [Plan in the cloud with ultraplan — official docs](https://code.claude.com/docs/en/ultraplan)
- [Claude Code on the web — docs.claude.com](https://docs.claude.com/en/docs/claude-code/claude-code-on-the-web)

**Operational note (no programmatic API).** Ultraplan has no REST/SDK — it
is CLI/browser only. So we cannot cron-trigger `/ultraplan`. The right shape
is: VM cron keeps running the muscle (NBA + Political CPCV swarms, Karpathy
loops, dept councils), and the user invokes `/ultraplan @PLAN.md` 1-2x/day
as a strategic checkpoint. Each ultraplan PR becomes a documented
hypothesis; each merged PR becomes a validated experiment in the scientific
log. This keeps "always running" (cron muscle) and "always analyzed"
(ultraplan strategic review) on separate clocks, which is the only honest
way to combine them.

---

## Definition of "scientifically perfect"

A trading floor experiment is "scientifically perfect" iff:

| Criterion | NBA | Political |
|---|---|---|
| Same starting bankroll (literal or normalized) | ✓ | ✓ (W3 makes literal) |
| Same 5 named traders | ✓ | ✓ |
| Same CPCV+DSR+PBO promotion gate | ✓ | ✓ (this commit) |
| Same fold count (≥24) | ⚠ 7 | ⚠ 1 |
| Real LangGraph debate (not adapter) | ✗ | ✗ (W1) |
| Real OASIS agent society for T3 | ✗ | ✗ (W2) |
| Continuous CPCV watcher with alerts | ✗ | ✗ (W5) |
| No hardcoded UI mocks | ⚠ | ✗ (W4) |
| Fold pool refreshed within 24h | ✓ | ✓ (this commit) |

**Score today: 12/18.** Target after W1-W5: 18/18.
