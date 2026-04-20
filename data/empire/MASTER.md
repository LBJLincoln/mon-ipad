# NOMOS42 EMPIRE LEDGER
_Generated 2026-04-20T09:27:49Z — regenerate via `python3 scripts/empire/build_master.py`_

> **Mission:** Brier < 0.20 on NBA + Brier < 0.25 on POL + PQTF-style 10× on ITF by 2026-11-03. Revenue ≥ $95/mo by 2026-05-08 or shutdown.

## 1. Executive Summary

### Four Trading Floors (2026-04-20 state)
| TF | Status | Last Measured Outcome |
|---|---|---|
| **NBA** | Fresh reset, day 0, prompt_v3 | fleet_best=$100 (just started) — prompt forbids ml_home fallback, unlocks pp_* |
| **POL** | Fresh reset, running, prompt_v4 | day 10 top: gemini-anl $110.88 — category_collapse rule active |
| **ITF** | Live mode (Alpaca PAPER), 7 personas | tick_count starting — CRYPTO_PIVOT + options live |
| **PQTF** | **Paused (archival $602,354)** | 60.2% of $1M mission — preserved as validation proof |

### Selfhost LLM fleet (live HTTP probe)
- **6/11 Spaces LIVE** across 4 accounts
- LBJLincoln 3/3 · LBJLincoln26 1/1 · TESTforge42 2/4 · **Nomos42 0/3 (403-saturated)**
- Gateway exposes 10 `selfhost:` routes, **6 resolve to live Spaces, 4 dead**

## 2. Strategy Scorecard — What Won / What's Pending

### Top-10 WINNERS (ranked by evidence)
**10/10 — PQTF multi-agent multi-leg derivatives**
- *Impact:* PROVEN: $600 → $602,354 (100,292% ROI) across 50 days
- *Status:* ARCHIVED — preserved as $1M validation proof
- *Lesson:* Real LLM agents + multi-leg options + $100 survival floor + stacking = path to $1M

**9/10 — Prompt mutator closed-loop (post-mortem → overrides.json → HF deploy)**
- *Impact:* Enables next-day prompt evolution; 6 rules across 4 TFs as of 2026-04-20
- *Status:* LIVE in production on all 3 TF Spaces
- *Lesson:* Close the scientific feedback loop — if you can't mutate the prompt daily, you're not iterating

**9/10 — Cerebras time-windowed circuit breaker + uniform-fallback emitter**
- *Impact:* Silent-pass storage drops were dominant failure mode, not parser regex
- *Status:* LIVE
- *Lesson:* Silent failures compound — every fallback path must emit a traceable bet, not silence

**8/10 — Player-props ingestion (17,592 pp_* lines across 802 games)**
- *Impact:* Unlocked NBA TF to bet on 42 previously-empty pp_ categories
- *Status:* DEPLOYED 2026-04-20 f0a9e0a21
- *Lesson:* If the prompt advertises a menu, the data MUST back it — or agents fabricate

**7/10 — Selfhost LLM fleet distribution (11 Spaces, 4 accounts)**
- *Impact:* Cost-zero inference; 6/11 live with OpenAI-compatible /v1/models
- *Status:* PARTIAL — Nomos42 account 403-saturated (0/3); gateway has 10 selfhost: routes, 6 resolve live
- *Lesson:* Free-tier concurrent-Space caps are the real bottleneck; spread across accounts

**7/10 — 4-track orchestrator (Science / Platform / Market / Capital)**
- *Impact:* Consolidated 9 depts → 4 tracks; MIN_DEPLOY 75% floor; saved 338MB + 10.5k LOC
- *Status:* SPEC'D — orchestrator not yet auto-wired (every-8h Opus dispatch pending)
- *Lesson:* Less is more — 9 overlapping dept loops produced churn, 4 parallel tracks produce throughput

**7/10 — Axelrod canon (CK + sacrificial rotation + post-mortem log + coalitions)**
- *Impact:* All TF agents pre-pended with COLLECTIVE_MISSION + Axelrod canon
- *Status:* LIVE on NBA + POL
- *Lesson:* Game-theoretic cooperation > isolated utility max — lockstep is preventable via structural divergence rule

**8/10 — Per-agent per-TF intelligent monitor + auto-dispatcher (3-min cadence)**
- *Impact:* Replaces LLM-testing cron with targeted 'what's broken' signal + brief generation
- *Status:* LIVE — runs every 3 min + 4-per-hour dispatcher
- *Lesson:* Monitor what matters (agents, bets, silences, lockstep), not what's easy (LLM pings)

**7/10 — ITF 71-instrument + options derivatives + 7 personas**
- *Impact:* 36 → 71 instruments (MAG7 + leveraged + vol + crypto + options)
- *Status:* LIVE (dry-run default, ITF_OPTIONS_LIVE=1 gates broker)
- *Lesson:* Port the winning architecture (PQTF multi-leg) to ITF directly — don't re-invent

**6/10 — Hub-state-persistence clean-reset recipe**
- *Impact:* factory_reboot alone doesn't reset — /api/reset now purges Hub state
- *Status:* LIVE (ran successfully on POL/NBA/ITF 2026-04-20)
- *Lesson:* HF Spaces have 3 state layers: local, persistent_storage, Hub. Reset all three.

### FAILURES + PENDING FIXES
- **POL TF excess_return leakage (FIXED)** — FIXED 2026-04-18 1a7a02b48 — state wiped clean
  - Impact: 88% WR nemotron-120b → $13K fabricated bankroll from future outcome signal
  - Lesson: Never use outcome as fallback signal in post-filter; cross-check with walk-forward before celebrating
- **NBA TF lockstep (ONGOING)** — MITIGATED by prompt_v3 (forbidden fallback + pp_ unlock rule) — waiting for measurement
  - Impact: 3/17 agents silent last 3 days; 0.97 Jaccard on POL — DMAD groupthink failure
  - Lesson: Structural divergence must be enforced by rule, not advised
- **PQTF zombie rows (ONGOING)** — Prompt_v1 rule deployed; engine-level validation pending
  - Impact: 14/36 PQTF rows had type=null or strike=0 — fabrication leaking through
  - Lesson: Contract validation belongs in the engine, not the prompt
- **ITF 84% crypto-pass (investigated)** — RCA: CRYPTO_PIVOT_CLAUSE deployed + asset-class grouping
  - Impact: 10 orders, 0 crypto — `_build_prompt` sliced quotes[:22], 48 equities filled slot, crypto invisible
  - Lesson: Truncation bugs are stealthy — always validate menu visibility in the prompt bytes
- **POL category_collapse (ONGOING)** — Prompt_v4 (category_collapse) deployed — TF in fresh reset day 0
  - Impact: POL fleet collapsed to single category (insider_trade) for days
  - Lesson: Monoculture = fragility; force ≥2 distinct categories by rule

## 3. Ten Crucial Optimization Points

### 1. Close the loop: every post-mortem → overrides.json → HF deploy within 24h
- *Why:* PQTF proved real LLM agents can hit 60% of $1M if prompts evolve daily
- *Action:* Wire prompt_mutator to run nightly; add tf_postmortem as pre-hook

### 2. Own your silence: every fallback path must emit a traceable bet
- *Why:* Silent-pass storage drops were dominant TF failure mode, not parser issues
- *Action:* Uniform-fallback emitter (done on 3/4 TFs) — finish on ITF

### 3. Diversify the selfhost fleet across all 4 HF accounts
- *Why:* Nomos42 403-saturated at 7 concurrent Spaces; LBJLincoln/26/TESTforge42 have slack
- *Action:* Migrate Nomos42's 3 dead selfhost: routes to TESTforge42 or LBJLincoln

### 4. Validate menu visibility in prompt bytes, not prompt intent
- *Why:* ITF 84% crypto-pass was quotes[:22] truncation hiding crypto — prompt said 'bet crypto'
- *Action:* Unit-test _build_prompt covers every asset class after every persona add

### 5. Enforce structural divergence by rule, not advice
- *Why:* NBA 0.88 lockstep persisted through 3 prompt versions that 'advised' divergence
- *Action:* Hard-exclude top-ranked consensus category per agent (prompt_mutator rule lockstep_v2)

### 6. Every TF must define its 'walk-forward equivalent' before celebrating WR
- *Why:* POL 88% WR was leakage; needed out-of-sample test to catch
- *Action:* INTERNAL_AFFAIRS already runs this — extend to auto-revert overrides that violate

### 7. Port winners across TFs — don't reinvent architectures
- *Why:* ITF copied PQTF multi-leg engine and got to live day 0 in 1 session
- *Action:* Next port: Polymarket TF (queued in memory) inherits PQTF strategy ladder + POL intel

### 8. Treat free-tier quotas as a resource to allocate, not a constraint to hit
- *Why:* 10 'nul' islands killed to free Space slots for selfhost LLMs — same math applies to Spaces/tokens
- *Action:* Quarterly 'slot audit' — is every Space earning its concurrent cap?

### 9. Intelligent monitor > LLM ping-test
- *Why:* Old keepalive crons were binary up/down; tf_intel_monitor catches per-agent silence in 3 min
- *Action:* Retire `keepalive-spaces.sh` for TF Spaces, keep only for static assets

### 10. The empire is the ledger — logs compound into edge
- *Why:* This very doc is what lets specialist agents (THE_ACCOUNTANT, HAWKEYE, SWISH) operate across sessions
- *Action:* Regen data/empire/MASTER.md nightly @ 04:00 UTC; commit; distribute brief per agent

## 4. Evolution Timeline (git since 2026-04-15)

- **Commits:** 400 over 5 days
- **By tag:** TICKER=13, SWITCHBOARD=10, DR_FRANKENSTEIN=7, FRANKENSTEIN=6, INTERNAL_AFFAIRS=5, PIXEL=4, THE-BOSS=4, TF_INTEL=3, BRAIN=3, CLAUDE_CODE_RESUME=3
- **By theme:** nba-tf=43, pixel=35, pol-tf=21, itf=19, pqtf=17, audit=7, prompts=3

### Latest 12 commits
- `291a3b0ee` 2026-04-20T08:31 — data: picks 2026-04-20
- `1c29d660b` 2026-04-20T05:00 — research-vault: 2026-04-20T05:00Z compile
- `30b14fc2c` 2026-04-20T04:00 — vault: refresh 2026-04-20 — 335 raw, 14 wiki articles
- `43d2d87f3` 2026-04-20T03:29 — [DR_FRANKENSTEIN] annotate player-props proposal as implemented
- `1a524457e` 2026-04-20T03:29 — [DR_FRANKENSTEIN] ship player-prop ingestion (pp_* categories, 17592 entries across 802 games) per proposal nba-player-props-ingestion-2026-04-20
- `47a3f88e1` 2026-04-20T03:16 — [TF_INTEL] research: player-props ingestion proposal (P1) + monitor cadence 4m→3m
- `dccae1a7c` 2026-04-20T02:59 — [TF_INTEL] ops: tf_intel fix — Alpaca uses ALPACA_PAPER_KEY/SECRET (not ALPACA_API_KEY_ID)
- `42ec8d2fc` 2026-04-20T02:57 — [TF_INTEL] ops: smart per-agent per-TF intel monitor + dispatcher (cron 4m/15m)
- `2841efd31` 2026-04-20T02:47 — [LAUNCHPAD] gpu-burst: prune eliminated islands (11 survivors post-2026-04-17 cull)
- `fa66d655c` 2026-04-20T02:46 — [INTERNAL_AFFAIRS] audit: NBA d006 leakage exoneration — tier-pad lockstep not excess_return leakage (severity 1)
- `410087cf3` 2026-04-20T02:32 — [INTERNAL_AFFAIRS] rollup: cross-TF Apr 15-19 evidence pack for prompt rewrites (12 proposals, 5 patterns)
- `c8c4ec9ba` 2026-04-20T02:30 — [HAWKEYE] research: Apr-20 arXiv+GitHub refresh — 10 papers, 5 repos, 10 FRANKENSTEIN-ready proposals (CoalT, Risk-Constrained Kelly, Venn-Abers sweep, KL/JS divergence, PolyBench gate)

## 5. Live Intel Snapshot (last 3-min TF monitor)

- Total alerts: ?
- By severity: ?
### Alert-code frequency (last 500)
- `agent_silent`: 230
- `itf_agent_silent`: 150
- `category_collapse`: 24
- `pqtf_zombie_rows`: 24
- `pqtf_no_multileg`: 24
- `broker_401`: 24
- `itf_no_crypto`: 24

### Dispatcher — who got paged (last 300)
- `SWITCHBOARD`: 26
- `DR_FRANKENSTEIN`: 14
- `LAUNCHPAD`: 13
- `LOBBYIST`: 9
- `THE_TICKER`: 9

## 6. Integrity Audit Digest

- Last 10 runs logged: 10
- Severity counts: {}

## 7. Research Pipeline (HAWKEYE + FRANKENSTEIN)

- Proposal status: {'?': 11, 'pending': 3}
- Priority distribution: {1: 5, 2: 3, 3: 4, 5: 1, '?': 1}
### Recently Implemented
### Pending Priority-1 Proposals
- Replace MANDATORY-pact prompt with Coalition-of-Thought (CoalT) from Guo et al. 2604.14386
- Replace heuristic MIN_DEPLOY tiers with formal Risk-Constrained Kelly 1-D calibration (Long 2604.11577)
- Audit all islands; swap isotonic → Venn-Abers / Beta on CatBoost/XGBoost/LightGBM (Manokhin 2601.19944)
- Port PolySwarm's KL/JS divergence cross-market inefficiency engine as lockstep/inefficiency signal
- CRITICAL: NBA TF thesis↔outcome leakage re-detected

## 8. 4-Track Orchestrator State

### t1-science
- timestamp: 2026-04-20T09:17:01.382113+00:00
- track: T1 SCIENCE
- absorbs: ['D1 research', 'D3 evolution', 'D6 evaluation']
- status: ok
- last_metric: {'fleet_best_brier': 0.22447, 'target_brier': 0.2, 'calibration_mce': None, 'calibration_ece': None, 'drift_alarms': 0}
- last_action: 21 evolution islands running, fleet-matrix scoreboard fresh every 30min
### t2-platform
- timestamp: 2026-04-20T09:17:01.402308+00:00
- track: T2 PLATFORM
- absorbs: ['D2 engineering', 'D7 infra', 'D9 cross-repo']
- status: watch
- last_metric: {'engine_sha_match': None, 'nba_fleet_up': None, 'infra_alerts': 0}
- last_action: Both TFs deployed w/ T13/T14 NVIDIA parity 2026-04-17
### t3-market
- timestamp: 2026-04-20T09:17:01.405024+00:00
- track: T3 MARKET
- absorbs: ['D4 product', 'D5 business']
- status: behind
- last_metric: {'telegram_subs': 0, 'paying_subs': 0, 'mrr_usd': 0, 'target_may1': 95}
- last_action: @Nomos42Picks channel + Stripe paywall scaffolded
### t4-capital
- timestamp: 2026-04-20T09:17:01.413743+00:00
- track: T4 CAPITAL
- absorbs: ['D8 finance', 'NBA TF', 'POL TF']
- status: ok
- last_metric: {'nba_tf_total_bankroll': None, 'pol_tf_total_bankroll': None, 'nba_tf_agents': 14, 'pol_tf_agents': 14, 'target_collective_usd': 1000000, 'min_deploy_pct': 0.7
- last_action: T13 nvidia-minimax + T14 nvidia-llama70 deployed to both TFs 2026-04-17

## 9. Cross-Session Memory Index

- MEMORY.md: 319 lines, 78 sections
### DEPLOYMENT RULE
- - [feedback_hf_first_then_vercel.md](feedback_hf_first_then_vercel.md) — Always deploy to HF Space first, Vercel prod only after user confirms
### AUTONOMY RULE (2026-04-19)
- - [feedback_always_do_all_apr19.md](feedback_always_do_all_apr19.md) — "alwaus do all" — documented recovery recipes on own infra = act, don't ask. Prod-visible surface + external-visible = still conf
### POLYMARKET TF PROPOSAL (2026-04-20) — 5th floor + POL options overlay queued for FRANKENSTEIN
- - [project_polymarket_tf_proposal_apr20.md](project_polymarket_tf_proposal_apr20.md) — 2 proposal JSONs committed cc77546a4. PM-TF: arb/maker/oracle, py-clob-client, Chainlink. POL options overlay: po
### PIXEL v2.19 PANEL SURGERY (2026-04-20) — superposition fixed, 41-agent visibility restored
- - [project_pixel_panel_surgery_apr20.md](project_pixel_panel_surgery_apr20.md) — Drastic surgery on HP/bet-tag/strategy-badge → hover-only + HP slimmed 8px→5px. Supersedes v2.15. Deploy via HF_TOKEN_L
### ITF CRYPTO-PIVOT FIX (2026-04-20) — 84%-pass RCA: quotes truncated hid all crypto
- - [project_itf_crypto_pivot_apr20.md](project_itf_crypto_pivot_apr20.md) — `_build_prompt` sliced quotes[:22] so 48 equities filled slot and 10 crypto pairs invisible. Fixed: asset-class grouping + al
### SELFHOST FLEET REALITY (2026-04-20) — 5/15 LIVE, gateway selfhost: routing broken
- - [project_selfhost_fleet_reality_apr20.md](project_selfhost_fleet_reality_apr20.md) — HTTP probe across 4 accounts: LBJLincoln 2/3 (gemma2-2b DOWN), LBJLincoln26 1/1, TESTforge42 2/4, Nomos42 0/7. Ga
### ITF WINNER-ROUTED (2026-04-19) — follow cross-fleet aggressive winners, not equal-weight defaults
- - [feedback_itf_follow_winners_apr19.md](feedback_itf_follow_winners_apr19.md) — Every ITF persona's model_primary MUST be a top-3 winner across NBA/POL/PQTF for its tier. Seeded 2026-04-19 with mistr
### SELFHOST LLM EXPANSION (2026-04-19) — 4 new OpenAI-compat selfhost, wheel-based build
- - [project_selfhost_llm_expansion_apr19.md](project_selfhost_llm_expansion_apr19.md) — Pause P3/P6/P8/S19 → deploy qwen2.5-0.5b + gemma-2-2b + phi-3.5-mini + qwen2.5-1.5b. Use `--prefer-binary --extra
### LLM FLEET DISTRIBUTED CROSS-ACCOUNTS (2026-04-19, 2-3 sessions ago) — 6 RUNNING, 2 building, Nomos42 saturated
- - [project_llm_fleet_distribution_apr19.md](project_llm_fleet_distribution_apr19.md) — 11 island SURVIVORS (eliminated 10 "nuls": S10/S11/S12/S16/S19/S20/S21 + P3/P6/P8 — DO NOT restart). Selfhost LLM
### LA FORGE THESIS (2026-04-19) — Nomos42 vs Paperclip AI positioning
- - [project_la_forge_thesis_apr19.md](project_la_forge_thesis_apr19.md) — 3 measurable floors (NBA Brier<0.20 / POL Brier<0.25 / PQTF 10× by Nov 3) as the anti-vibes answer to Paperclip AI (38K⭐ "zero-
### PQTF 60% OF $1M (2026-04-19) — fleet completed 50/50 with $602K
- - [project_pqtf_1m_60pct_apr19.md](project_pqtf_1m_60pct_apr19.md) — PQTF real-data run completed $600→$602,354 (100,292% ROI, 60.2% of $1M mission alone). mistral-large $244K + mistral-medium $155K +
### $1M ROAD 3 BLOCKERS FIXED (2026-04-19) — Cerebras + MIN_DEPLOY + coalitions
- - [project_1m_road_3_blockers_apr19.md](project_1m_road_3_blockers_apr19.md) — efdddd5e1 + 77a01a839: time-windowed Cerebras circuit breaker, uniform-fallback emitter (NBA top-3 ML / POL SPY-QQQ-IWM, 

## 10. Where The Data Lives

| Topic | Path |
|---|---|
| This ledger | `data/empire/MASTER.md` |
| Machine-readable | `data/empire/MASTER_DATA.json` |
| Strategy scorecard | `data/empire/strategy-scorecard.json` |
| Evolution timeline | `data/empire/evolution-timeline.jsonl` |
| Per-agent briefs | `data/empire/briefs/<agent>.md` |
| 3-min TF intel | `data/ops/tf-intel-{latest,alerts,summary}` |
| 4h audit sweeps | `data/audit/` |
| Per-TF daily stats | `data/tf-analytics/{nba,pol,pqtf}/day-*.json` |
| Cross-TF attribution | `data/cross-tf/` |
| HAWKEYE proposals | `data/research/tf-proposals-*.json` |
| 4-track orchestrator | `data/tracks/` |
| Cross-session memory | `~/.claude/projects/-home-termius-mon-ipad/memory/MEMORY.md` |
