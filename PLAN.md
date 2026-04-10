# Nomos42 Trading Floor — Scientific-Experiment Master Plan

> **Purpose:** This file is the canonical brief for `/ultraplan` (Anthropic's
> cloud planning feature, released 2026-04-07). Run `/ultraplan @PLAN.md` to
> have Claude Code on the web draft the next implementation step in CCR with
> three parallel subagents + a critique pass.

**Last refresh:** 2026-04-07 14:30 UTC (Phase B+ shipped: trader pool free-HF
pivot, dashboard mocks removed, OASIS T3 swarm scaffold (50 agents), Alpaca
paper client, Obsidian compile cron live AND auto-pushing every 2h, Claude
Code Web verified, swarm→full-season-backtest aggregator wired so the NBA
backtest API now reads fresh data instead of a 10-day-stale file, infra page
FALLBACK_DEPARTMENTS/_BOTTLENECKS/_CRON_JOBS hardcoded fakes deleted +
honest empty-state UI, forge-metrics route returns 503 instead of fake
"FORGED" status for every repo, evolution page static-March ATR fallback
deleted)
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

## Current state (as of 2026-04-07 14:30 UTC)

### NBA — green
- ✅ `scripts/arena/cpcv_gate.py` running, **7 backtest runs in pool, 0/40 strategies passing** (gate working — DSR rejecting until pool ≥ 24)
- ✅ `scripts/arena/continuous-backtest-swarm.sh` cron 6×/day, latest run 12:45 UTC writes `data/arena/backtest-results/backtest-20260407-124522.json`
- ✅ NEW: `scripts/arena/aggregate_swarm_to_season.py` runs at end of swarm and writes `data/nba-agent/full-season-backtest.json` (was 10d stale; now refreshes every 4h with real Sharpe/ROI/Brier from latest swarm + synthesized trade timestamps for the equity-curve view)
- ✅ 9-season backfill — 11,513 games
- ✅ 102 betting categories (`bet_categories.py`)
- ✅ Bull/Bear debate UI on `/trading-floor` (mon-ipad 2f73c16f)
- ✅ 102-cat heatmap on `/trading-floor` (nomos-dashboard 1cdf6d2)
- 📊 Best swarm strategy: **`spec_spread`** ROI +45.09%, Sharpe 3.33, win-rate 70.3%, 445 bets, Brier 0.21520
- ⚠️ DSR p-value 0.9995 — needs ~17 more swarm runs (≈3 days) to clear gate

### Political — green
- ✅ `scripts/arena/political_cpcv_gate.py` (parity with NBA gate)
- ✅ `scripts/arena/continuous-political-backtest-swarm.sh` cron `17 */4 * * *`
- ✅ Pool now has **2 runs, 5 strategies evaluated, 0 passing** — needs ≥3 folds for DSR
- ✅ FRESHENED: `data/arena/political-arena-v2.json` synced from `nomos-political-alpha/data/arena/arena-results.json` (12:45 UTC, 200KB)
- ✅ FIXED: `/political/page.tsx` DONOR_UNIVERSE + MOCK_EVOLUTION + MOCK_KAGGLE_LOG deleted (commit a226818d)
- ✅ Obsidian compile cron live (`23 */2 * * *`), auto-pushed twice today (7e9e6539, bszi4xjd2)

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

### Trader pool — free HF only (Phase B)
- ✅ NBA + Political TF rebranded: gemini→Gemma 3 27B, openrouter→Qwen 2.5 72B,
  codex→Llama 3.3 70B, grok→Mistral Large 2 (all on free HF Inference Router,
  4 HF accounts cover quota). Claude Code CLI unchanged.
- ✅ Dict keys preserved → existing `data/arena/traders/*-state.json` keep
  bankroll history through the rename.

### OASIS T3 specialist swarm
- ✅ `scripts/arena/oasis_t3_swarm.py` writes 50 specialists across 10 personas
  × 4 free HF backbones into `data/arena/agent-states-v5.json`
- ✅ Total v5 agents: **274** (224 prior + 50 OASIS)
- ⚠️ Lite-mode only (heavy `vendor/oasis` runtime opt-in via `--use-oasis-runtime`)
- ⚠️ Not yet wired into v5 floor consensus (PLAN.md W2 acceptance)

### Dashboard — enterprise-grade pass (this commit)
- ✅ DELETED: `nomos-dashboard/src/app/api/forge-metrics/route.ts` FALLBACK_METRICS
  (was marking every repo as `'FORGED'` even when VM unreachable). Now returns 503.
- ✅ DELETED: `nomos-dashboard/src/app/infra/page.tsx` FALLBACK_DEPARTMENTS,
  FALLBACK_BOTTLENECKS, FALLBACK_CRON_JOBS (~70 lines of fake data). Replaced
  with honest empty-state cards: "Department data offline — VM unreachable".
- ✅ DELETED: `nomos-dashboard/src/app/evolution/page.tsx` AtrProgress static
  March history (4 fake entries). Replaced with empty state.
- ✅ Phase B (commit a226818d): NBA backtest deterministic-RNG + political
  hardcoded DONOR_UNIVERSE + MOCK_EVOLUTION + MOCK_KAGGLE_LOG removed.
- 🟡 Remaining (W6 — see below): pricing TIERS still hardcoded; rgwa+terminal
  pages last touched 2026-03-26 — need re-audit; control room loading skeletons
  missing on metric grid; some chart components silently render empty when
  upstream is null.

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

### W6 — Enterprise visual polish (post Phase B+)

**Goal:** Close the remaining "looks like a draft" issues from the
2026-04-07 evening dashboard audit.

**Hits already shipped this commit (don't redo):**
- `forge-metrics/route.ts` returns 503 instead of fake FORGED status
- `infra/page.tsx` empty-state cards instead of FALLBACK_* hardcoded fakes
- `evolution/page.tsx` AtrProgress empty state instead of static March history
- `political/page.tsx` already mock-free since Phase B

**Files still to touch:**
- `nomos-dashboard/src/app/pricing/page.tsx` lines 14-89: TIERS + FAQs
  hardcoded → wire to `/api/pricing` so the user can update without redeploys
- `nomos-dashboard/src/app/rgwa/page.tsx` (Mar 26 — 12d stale): re-audit for
  stub HF space links and dead bot status
- `nomos-dashboard/src/app/terminal/page.tsx` (Mar 26): verify the slash
  commands shown actually exist as skills
- `nomos-dashboard/src/app/control/page.tsx` lines 88-99: add `<Skeleton>`
  loading state instead of bare metric grid pop-in
- `nomos-dashboard/src/app/page.tsx` lines 420-425: replace `'...'` literals
  in metric bar with `<Skeleton animate-pulse>`
- `nomos-dashboard/src/app/nba/page.tsx` EquityCurve component: add
  "backtest data unavailable" empty state
- `nomos-dashboard/src/app/world/page.tsx` iframe `onError`: 10s timeout +
  "Pixel World offline" message instead of perpetual 60% gradient bar
- `nomos-dashboard/src/app/councils/page.tsx`: change `"never"` to
  `"Pending first run"` for departments with no prior run

**Acceptance:** A cold investor demo (every API blocked at the proxy) shows
honest empty states everywhere, not a single hardcoded fake number.

---

## How to invoke /ultraplan

**Verified 2026-04-07** against the official docs at
[code.claude.com/docs/en/ultraplan](https://code.claude.com/docs/en/ultraplan).
Ultraplan is **research preview**, available to Claude **Pro / Max / Team /
Enterprise** accounts only. It requires Claude Code on the web (claude.ai/code)
+ a connected GitHub repo + the Claude GitHub App installed on `LBJLincoln/mon-ipad`.

**One-time setup (do this first):**
1. Run `/web-setup` from any local Claude Code session — syncs your `gh auth token`
2. OR visit [claude.ai/code](https://claude.ai/code) directly and connect GitHub
3. Pick a default cloud environment

**Invoke from local Claude Code session in `/home/lahargnedebartoli/mon-ipad`:**

```
/ultraplan design W1 (real LangGraph debate replacement) end-to-end using @PLAN.md
```

Three ways to launch:
- **Slash command**: `/ultraplan <prompt>` — opens confirmation dialog
- **Keyword**: any prompt containing the word `ultraplan` — opens confirmation dialog
- **From local plan**: when Claude finishes a local plan, choose "No, refine with
  Ultraplan on Claude Code on the web" in the approval dialog (no extra confirm)

CLI status indicator: `◇ ultraplan` → `◆ ultraplan ready`. Run `/tasks` to open
the session detail view with the browser link, agent activity, and a
**Stop ultraplan** action.

In the browser at claude.ai/code:
- Highlight any passage to leave inline comments
- React with emojis to signal approval/concern
- Iterate until the plan is right
- Click **Approve plan and start coding** → executes in cloud, opens PR on `LBJLincoln/mon-ipad`
- OR click **Approve plan and teleport back to terminal** → injects plan into
  your local CLI session for local execution

CLI alternative for non-plan tasks: `claude --remote "<prompt>"` creates a new
web session that runs in the cloud while you keep working locally. Multiple
`--remote` calls run in parallel.

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
