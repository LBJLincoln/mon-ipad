# Nomos42 — NBA Quant AI + Political Alpha

> Architecture v21 — "The Trading Floor Crew" (14 agents × 9 depts × 4 tracks) + TF v3 (17 LLM agents) + 21 Evolution Islands | Updated: 2026-05-02

## Mission
Build the best NBA prediction AI in the world.
**Best:** Brier 0.21139 walk-forward holdout / 0.22169 CV / 0.22054 isotonic-calibrated (Colab TabICL, 186f top-by-variance from 4581 alive of 7246 engine cols, ctx=3072 temp=1.0, 11440 games, promoted to LBJLincoln26/nba-oracle-model 2026-04-28T00:34Z, archive `colab-multi-tabicl-2026-04-28T00-34-04Z.pkl`). Beat 4581f xgboost holdout 0.22079 / lightgbm 0.22181 in same 3-way comparison. ⚠ All 3 models show negative CV→holdout gap (~−0.01) → holdout 0.21139 is window-biased; honest production-Brier expectation is CV 0.22169 / calibrated 0.22054. Stratified-by-month re-cut queued. NBA TF watchdog gate "<0.21 model lands" NOT met → watchdog stays disabled. | Fleet best: 0.22027 (S22 nba-evo-s22 63f, gen 861, checkpointed 2026-05-01) | **Target:** < 0.20, ROI > 5%, Sharpe > 1.5
**Walk-forward:** avg 0.22447 (Kaggle, 19 weeks, 934 games, tree ensemble — no TabICL on P100)
**NBA TF v7 + reroute + pool=8 (Apr 22, 17 agents, DAY-0 RESET 15:24Z):** prompt_v7 (3-bet cap + 100% deploy mandate, Kelly-weighted floors). Round-2 dead-provider reroute (HF SHA cc905b3e1dcd): nemotron-120b→mistral:large, selfhost-dolphin3→nvidia:llama-3.3-70b, selfhost-qwen06/gemma3→cerebras:llama3.1-8b, selfhost-qwen4b→cerebras:qwen-3-235b, nvidia-minimax→mistral:medium. Pool concurrency 4→8 (env NBA_TF_LLM_POOL_WORKERS=8), LLM timeout 45s (env NBA_TF_LLM_TIMEOUT_SEC=45.0). Live day 8/175, 14/17 agents at 100% llm_ok post-reset. PEAK_DD_GUARD_V2 sole safety net. Top: gemini-anl $108, dolphin3 $107.
**Political TF v5_restored (Apr 22 15:46Z ROLLBACK):** 17 agents, day 90. v6 100%-deploy mandate destroyed alpha (qwen-arb -39% / llama-contra -51% in 1h) — rolled back to v5 doctrine: non-consensus mandate (lockstep≤0.88) + ≥3 distinct categories per day. State preserved. qwen-arb $3,472 / qwen-quant $1,459 / gemini-anl $584 carrying forward.
**ITF v_accel70 (Apr 22 14:41Z):** 17 day-traders, 95% stake floor + **70% RESERVED HARD floor** + winner-tier dynamic. Env TICK_SEC=60, CLOSE_STALE 1h/-0.5%, MAX_PENDING=8, MIN_BP=100. Alpaca paper account $101,424 equity / 67.96% deployed (within 2.4% of floor) / 43 positions / +$961 unrealized PnL. ⚠ ITF /api/status unreliable (multi-worker LB) — query Alpaca /v2/account directly.
**PQTF v2 FROZEN FOREVER:** $602,354 validation artifact (mistral-large $244K + mistral-medium $155K + gemini-anl $17K). DO NOT restart. Preserve as scientific proof multi-agent LLM trading hits $1M targets.
**Top-tier 14-agent Crew (Apr 18):** THE BOSS / SWISH / LOBBYIST / HAWKEYE / DR FRANKENSTEIN / THE BLACKSMITH / SWITCHBOARD / INTERNAL AFFAIRS / THE TICKER / THE HERALD / THE ACCOUNTANT / PIXEL / THE PLUMBER / LAUNCHPAD — L1/L2/L3 layered, mental-model personas, refusal rules, niche-expert bars. Live scientific snapshot via `data/pipeline-health.json` (PLUMBER :35 every 4h) + `data/audit/` (INTERNAL AFFAIRS :40 every 4h).

## Nomos42 Ecosystem

| Flagship | Repo | Bot | Vercel | Status |
|----------|------|-----|--------|--------|
| NBA Quant AI | mon-ipad + nomos-nba-agent | @Nomos42Bot | via dashboard | ACTIVE -- 6 NBA + 5 POL SURVIVOR islands (was 13+8; 10 "nuls" eliminated — slots redirected to selfhost LLMs) + Kaggle Karpathy |
| Political Alpha | nomos-political-alpha | -- | none (data only) | ACTIVE -- v3.19 engine, 22 categories, 718 features |
| Dashboard Hub | nomos-dashboard | -- | nomosdashboard.vercel.app | ACTIVE -- /nba /political /evolution /trading-floor /forge /world |
| AI Artistic Generation | rgwa | @RGWAbot | none | ZOMBIE -- no commits since Mar 2026, deprioritized |
| Factory / Complex RAGs | rag-website | -- | none | DECOMMISSIONED 2026-04-20 — repo no longer on disk, removed from ecosystem |

## 24/7 Autonomous Architecture

```
CLOUD BRAIN (Sonnet 4.6, every 4h at :00)
    ├── Monitor S10-S19 + P1-P4 via public /api/status
    ├── Research via 4 Claude Code subagents
    ├── DECIDE: tune GA / diversify / inject features / checkpoint
    ├── ACT on islands via POST /api/config
    └── Write health-status.json + push
    Trigger: trig_01BS3ixBvt2uKHY9p5EemcgD

VM MUSCLE (cron, every 4h at :30)
    ├── Run predict_today.py (if NBA games)
    ├── Push results to git
    └── Auto-restart data server
    Script: scripts/autonomous-cycle.sh

HF EVOLUTION ISLANDS — 11 SURVIVORS (6 NBA + 5 POL) after 2026-04-17 cull
    10 "nul" islands eliminated to free concurrent slots for selfhost LLMs:
    ELIMINATED: S10, S11, S12, S16, S19, S20, S21, P3, P6, P8 — DO NOT restart.
    Eliminated slots now host selfhost LLMs on LBJLincoln/LBJLincoln26/TESTforge42.

    NBA Survivors (6, CPU tree-only, MAX_FEATURES=200):
    ├── S13 Nomos42/nba-evo-4:        extra_trees       gen=351   brier=0.22430  (2026-05-02)
    ├── S14 Nomos42/nba-evo-5:        random_forest     gen=628   brier=0.25312  (2026-05-02)
    ├── S15 Nomos42/nba-evo-6:        random_forest     gen=1675  brier=0.22226  [RECOVERED] (2026-05-02)
    ├── S17 LBJLincoln26/nba-evo-s17: xgboost           gen=---   brier=0.22249  ⚠ DOWN 503 — manual HF admin check needed (2026-05-02)
    ├── S18 TESTforge42/nba-evo-s18:  extra_trees       gen=5448  brier=0.22248  stagnation=15 ⚠ (2026-05-02)
    └── S22 TESTforge42/nba-evo-s22:  xgboost 63f       gen=861   brier=0.22027  ★ FLEET BEST checkpointed (2026-05-02)
    Political Survivors (5, CPU tree-only):
    ├── P1 Nomos42/political-alpha:      xgboost_brier  gen=23796  brier=0.25231  (2026-05-02)
    ├── P2 Nomos42/political-alpha-2:    xgboost_brier  gen=206    brier=0.25003  [fresh restart] (2026-05-02)
    ├── P4 LBJLincoln/political-alpha-4: xgboost_brier  gen=15225  brier=0.24992  ★ POL LIVE BEST (2026-05-02)
    ├── P5 LBJLincoln/political-alpha-5: xgboost_brier  gen=6447   brier=0.24993  [hist 0.24923 ★ POL BEST] (2026-05-02)
    └── P7 LBJLincoln/political-alpha-7: lightgbm       gen=6628   brier=0.25412  hist_best=0.24925 (2026-05-02)

SELFHOST LLM FLEET (6 RUNNING, 2 building — 2026-04-19 20:55 UTC)
    LBJLincoln   (3 RUNNING): qwen25-05b-cpu, gemma2-2b-cpu, phi35-mini-cpu
    LBJLincoln26 (1 RUNNING): gemma3-4b-cpu  [+ llm-gateway + 2 TFs]
    TESTforge42  (2 RUNNING): qwen3-4b-cpu, llama32-1b-cpu  [+ smollm3-3b BUILDING, qwen25-15b starting]
    Nomos42     (0 selfhost RUNNING — 10 paused; account saturated by islands+TFs+pixel-world+langfuse; 403 on restart)
    Gateway routing: resolve `selfhost:*` keys to LBJLincoln/* or TESTforge42/* (NOT Nomos42/*).

NOTE: S11 URL = nomos42-nba-quant-2.hf.space (NOT nba-evo-2)

HF TRADING FLOORS (Real LLM experiment, NBA 16 agents / Political 16 agents — parity 2026-04-17 via +T13 nvidia-minimax +T14 nvidia-llama70 +T15 selfhost-gemma3 +T16 selfhost-qwen06, T12 renamed selfhost-qwen4b. COLLECTIVE_MISSION $1M preamble on every agent + unrestricted prompts: ≥3 allocations + MIN_DEPLOY_PCT=0.75 hard floor.)
    ├── LBJLincoln26/nba-llm-trading-floor: NBA engine (1257 games, FastAPI + Gradio)
    │   └── Source: scripts/arena/hf-llm-trading-floor/
    ├── LBJLincoln26/political-llm-trading-floor: POLITICAL engine (1120 events, same architecture)
    │   └── Source: scripts/arena/hf-political-trading-floor/
    ├── Both expose: /api/status /run /stop /reset /mutate /logs /day-decisions /leaderboard
    └── LBJLincoln26/llm-gateway: Centralized LLM proxy (11 models, fallback chains)

HF DEPT COUNCILS — DECOMMISSIONED 2026-04-20
    All 9 TESTforge42/nomos-dept-d*-* Spaces DELETED (stage was PAUSED — zombie on /api/status).
    Focus narrowed to: islands + selfhost LLMs + 3 TFs + Langfuse. Council Karpathy loops
    retired; THE BLACKSMITH agent is now no-op. Don't recreate — if structural-review is
    needed, spin a single review job, not a 9-Space fleet.

HF OTHER SPACES (across 3 accounts, post-cleanup 2026-04-15)
    ├── Free LLM Chat: gemma4-chat, qwen35-chat
    ├── Docker Runtime: Nomos42/nomos42-llm-cpu (self-hosted Qwen3-1.7B GGUF for api_pool)
    └── Pixel World: Nomos42/pixel-world (static)

GPU PLATFORMS (5 active, ranked by usefulness)
    ├── Kaggle P100 (9h sessions): scripts/kaggle/nba_karpathy_loop.py — STALE since Mar 28
    ├── Google Colab T4 (manual): 2 accounts, best 0.21570 (TabICL) — manual only, no .ipynb in repo
    ├── ZeroGPU H200 (auto): scripts/gpu-burst/zerogpu-burst.py — GH Action every 6h
    ├── Modal A10G (auto): scripts/gpu-burst/modal-burst.py — ACTIVE via GH Action every 4h (.github/workflows/modal-burst.yml)
    ├── Lightning.ai T4 (auto): scripts/lightning/launch_karpathy.py — ACTIVE via GH Action 2x/day (NBA 02:00 UTC, Political 14:00 UTC, .github/workflows/lightning-burst.yml)
    └── Paperspace Gradient (NEW): free GPU, unlimited restarts — SETUP IN PROGRESS

GITHUB ACTIONS (3 workflows on schedule)
    ├── Trading Floor:        */4h — MONITOR ONLY (curls HF Space /api/status, commits snapshot)
    ├── Backtest Swarm:       */2h — continuous scientific backtest
    ├── Scientific Experiment: */2h — CPCV + DSR gate
    ├── GPU Cron Launcher:    manual — Kaggle/Colab trigger
    └── Arena Engine:         daily — full arena evaluation

SYSTEM CRONS (28 active on VM, all lightweight)
    ├── */30  keepalive-spaces.sh (18 islands + TF + Gateway + 9 depts = 33 spaces)
    ├── 12,18 nba-daily-odds.py
    ├── :30   autonomous-cycle.sh
    ├── */2h  monitoring, vault sync, political data
    └──       Bloomberg API (port 8042), data server (port 8080)
```

## Skills

| Skill | Purpose |
|-------|--------|
| `/karpathy-loop` | Autonomous research cycle (5 subagents → proposals → quick wins) |
| `/daily-edge` | Daily predictions + value bets + Kelly sizing |
| `/progress-10pct` | Target 10% improvement in weakest metric |
| `/spaces-health` | Health check all 12+ HF evolution islands |
| `/evolve-report` | Comprehensive evolution progress report |
| `/agent-review` | Weekly agent performance review (Jensen HR model) |
| `/cross-repo-audit` | Audit all 5 repos for consistency and improvements |

## Rules

1. **ZERO ML on VM** — 1 vCPU / 969 MB RAM. ALL training on HF Spaces
2. **Feature engine parity** — `features/engine.py` = `hf-space/features/engine.py` always ⚠ MISMATCH 2026-05-02: mon-ipad b7ec5b5 (+54KB) ahead of nomos-nba-agent f455c47 — engine-parity-sync in work-queue
3. **1 fix per iteration** — never multiple simultaneous changes
4. **All experiments tagged** with `feature_engine_version` in Supabase
5. **Feature engine** — v3.1 = 54 categories, ~7213 raw feature candidates (verified 2026-04-18 from features/engine.py header)
6. **MAX_FEATURES=200** — hard cap enforced in init/mutate/crossover on all spaces (target 50-100 selected per island via GA)
7. **Mutation cap** — adaptive mutation capped at 0.15 (deployed S10/S11/S12/S15)
8. **CPU-only islands** — no neural models on CPU (tree-based only), stacking removed
9. **Supabase** — primary (ayqviq) paused (402), using pooler connection (xivvnr)
10. **Git mutex** — every autonomous agent commit MUST shell through `scripts/lib/safe_commit.sh <CODENAME> "<msg>" [paths...]` (flock on `/tmp/nomos-git.lock`, pull --rebase --autostash, 3× push retry, `[AGENT]` prefix). Raw `git push` from agents is banned — with 14 crew on staggered crons the race-reject rate was unacceptable.
11. **TF Quarantine (post-2026-04-22 compounding mandate)** — NBA + POL are on a 30-day no-reset quarantine. PQTF is frozen forever. `safe_commit.sh` auto-gates any commit mentioning a quarantined Space with destructive markers (`factory_reboot`, `DAY-0 RESET`, `reset-state`, `reset-bankrolls`, `state wipe`, `fresh state`). Override with `NOMOS_QUARANTINE_OVERRIDE=1` **only** when user has explicitly authorised the reset — document the reason in the commit message. State: `data/ops/quarantine.json`. Check: `scripts/ops/tf_quarantine.py status`. Why: 5 agent-initiated resets on 2026-04-22 destroyed every compounding trajectory (qwen-arb $10K → $100, POL fleet $126K → $1.7K, NBA 75% DD → $0). PQTF reached $602K only because nobody was allowed to touch it.
12. **Champion-preserve** — every hour at :55, `scripts/ops/champion_preserve.py scan` snapshots any NBA/POL agent whose bankroll crosses `$500` (5× default seed) into `data/champions/<tf>/<agent>/<ts>.json`. These snapshots survive resets. Intent: future $100 → $10K compounders are preserved *before* the next reset, regardless of whether the reset is legitimate or false-positive leakage. Threshold tunable via `champion_preserve.py threshold <usd>`.
13. **Evidence-based Kelly (2026-04-24)** — `_AGENT_KELLY_OVERRIDE` in NBA + POL `app.py` is now DERIVED from rigorous-validation Brier, not narrative. Formula: `Kelly = max(0.01, 0.30 - brier_empirical * 0.50)`. Agents with Brier > 0.32 (inverse-calibrated) get 0.01-0.03 probation cap; Brier < 0.23 earn 0.17-0.20. The auto-improvement cycle (cron `:20` every 4h) auto-tunes ±0.03 when live W/L or Brier signal crosses thresholds, cooldown 24h per agent.
14. **INVERSE-CALIBRATION PROBATION prompt (2026-04-24)** — Any NBA agent whose `_AGENT_KELLY_OVERRIDE` cap ≤0.03 receives an auto-appended prompt addendum: `default action = PASS`, `HARD LIMIT 1 bet/day, edge ≥0.10, stake ≤3%`, `if disagree with Island Oracle direction → AUTOMATIC PASS`. Probation lifts when 30-day Brier drops below 0.28. Shipped because rigorous measured NBA fleet Brier 0.41 (worse than random 0.25) — LLMs were overriding the oracle's calibrated prediction with narrative. Result in first hour: Brier 0.41 → 0.36, most-recent walk-forward window 0.24 (first sub-0.25). First full scientific evidence the probation works.

## Scientific scorecard layer (2026-04-24)

| Tool | Cron | Output |
|------|------|--------|
| `scripts/ops/tf_baseline_check.py` | on-demand + appends `data/ops/tf-baseline-history.jsonl` | PASS/FAIL integrity (leakage / lockstep / walkforward / source purity / sector diversity) |
| `scripts/ops/tf_scientific_scorecard.py` | `:50 every 4h` | WR, Brier, source purity, per-day trace, `data/audit/scorecard-latest.md` |
| `scripts/ops/tf_rigorous_validation.py` | `:10 every 4h` | Bootstrap CI95 for Brier/WR/PnL + ECE + reliability diagram per bucket + walk-forward rolling Brier + Welch t-test NBA vs POL, `data/audit/rigorous-latest.md` |
| `scripts/ops/tf_trajectory_flash.py` | `:15 every 4h` | IMPROVING/DEGRADING verdict from first-3 vs last-3 walk-forward windows, `data/audit/trajectory-latest.md` |
| `scripts/ops/tf_improvement_cycle.py` | `:20 every 4h` | Auto-tune `_AGENT_KELLY_OVERRIDE` ±0.03 on WR or Brier signal, 24h cooldown per agent, applies to Space via HfApi + restart, appends `data/ops/tf-improvement-history.jsonl` |
| `scripts/ops/tf_cross_llm_view.py` | `:55 every 4h` | Same LLM benchmarked across NBA+POL+ITF, `data/audit/cross-llm-latest.md`. Uses ITF `/api/llm-leaderboard` as source-of-truth for tid→llm mapping |
| `scripts/ops/daily_scientific_digest.py` | `06:00 daily` | One-page morning briefing with baseline + rigorous + cross-LLM + 24h improvement actions + champion ledger + path-to-$1M math, `data/audit/digest-<date>.md` |
| `scripts/ops/tf_unified_control.py` | on-demand | `status/run/stop/restart/reboot/health` against any TF with normalized schema; PQTF mechanically blocked from all write-actions |
| `scripts/ops/pol_watchdog.sh` | `*/5 min` | Auto-fire `/api/run` if POL `running=False` |
| `scripts/ops/itf_position_health.py` | `*/30 min` | Snapshot Alpaca equity/cash/BP/PnL + top 3 losers+winners to `data/ops/itf-position-health.jsonl` |
| `scripts/ops/sync_tf_analytics_to_dashboard.sh` | `:40 hourly` | Mirror `data/tf-analytics/*.json` + audit MD files (scorecard/rigorous/cross-llm/digest/trajectory) to `nomos-dashboard/public/tf-analytics/` + commit+push. Vercel rebuilds. Token-free. |
| `scripts/ops/weekly_oracle_retrain.sh` | `Sun 03:00` | Push Kaggle kernel → train RF from `nba_cached_data.npz` → download pickle → upload to HF dataset `LBJLincoln26/nba-oracle-model` → restart `LBJLincoln26/nba-oracle` Space |

## Oracle Spaces (2026-04-24)

Both built via Kaggle CPU training → HF dataset → FastAPI Space. Weekly auto-retrain via `scripts/ops/weekly_oracle_retrain.sh` (Sun 03:00 UTC).

| Space | Dataset | CV Brier | Target | Status |
|-------|---------|----------|--------|--------|
| `LBJLincoln26/nba-oracle` | `LBJLincoln26/nba-oracle-model` | **0.22087** (best fold 0.21383) | 0.21218 | live, serves /api/predict, /api/status, /api/best |
| `LBJLincoln26/pol-oracle` | `LBJLincoln26/pol-oracle-model` | **0.23274** (best fold 0.22329) | 0.20239 | live |

Both return base-rate when called without features (TF clients only pass identifiers). Full RF prediction requires `{"games"/"events": [{"features": [N-dim vector]}]}`. Neither is yet the default `NBA_ORACLE_URL`/`POL_ORACLE_URL` — that would regress predictions without feature wire-up. Oracles are warm backups + retrain targets for the weekly cron.

## NBA betting surface (2026-04-24)

- 249 categories per game in `data/full-odds-2025-26.json` (162 alt_spread/alt_total, 28 team_total, 22 pp, 20 halves/quarters, 3 game props + ml/spread/total). Previously `[:8]` slicing in `_build_game_block` hid 200+ of them; now agents see all.
- Max 25 allocations/day + 8 parlays/day (was 10+3).
- Same game can appear in allocations under DIFFERENT categories (ml_home + spread_away + pp_points_star1_over valid together).
- Parlays: 2-6 legs, each pct 0.005-0.08.

## New Tools (Apr 4)

| Tool | Script | Purpose |
|------|--------|--------|
| Bloomberg Terminal | `scripts/bloomberg/nomos42-terminal.py` | Rich TUI: odds, predictions, fleet, bankroll |
| Bloomberg API | `scripts/bloomberg/bloomberg-api.py` | HTTP API on port 8042 (auto-restart cron) |
| Free Models | `scripts/forge/free-models-integration.py` | Qwen/Gemma/Mistral council advisors via HF API |
| ZeroGPU Burst | `scripts/gpu-burst/zerogpu-burst.py` | H200 GPU burst (15 min/day free, 3 accounts) |
| OpenCode Agents | `scripts/opencode/*.sh` | D1/D5/D7 automated agents (cron every 4-6h) |
| Laptop Monitor | `scripts/laptop/agent-monitor.py` | Cross-repo health via local Ollama |
| Cross-Repo Council | `scripts/councils/cross-repo-councils.sh` | Run dept councils across all 8 repos |

## Agent Directives (OBLIGATOIRE Overrides)

### Pre-Work
1. **STEP 0 RULE**: Before ANY structural refactor on a file >300 LOC, first remove dead props, unused exports, unused imports, debug logs. Commit cleanup separately.
2. **PHASED EXECUTION**: Never attempt multi-file refactors in single response. Max 5 files per phase. Complete phase → verify → approval → next phase.

### Code Quality
3. **SENIOR DEV OVERRIDE**: Override default "try simplest approach" for architecture work. Fix structural issues, not just symptoms. Ask: "What would a perfectionist senior dev reject in review?"
4. **FORCED VERIFICATION**: After every file modification, run verification before reporting success. Never claim "done" without checking the code compiles/runs.

### Context Management
5. **SUB-AGENT SWARMING**: Tasks touching >5 independent files MUST use parallel sub-agents (5-8 files each). Sequential processing of large tasks guarantees context decay.
6. **CONTEXT DECAY**: After 10+ messages, re-read any file before editing. Auto-compaction may have destroyed context.
7. **FILE READ BUDGET**: Files >500 LOC must be read in chunks with offset/limit. Never assume single read captured full file.
8. **TOOL RESULT BLINDNESS**: If search returns suspiciously few results, re-run with narrower scope. Assume truncation.

### Edit Safety
9. **EDIT INTEGRITY**: Re-read file before AND after every edit. Never batch >3 edits to same file without verification read.
10. **NO SEMANTIC SEARCH**: On rename/signature change, search separately for: direct calls, type refs, string literals, dynamic imports, re-exports, barrel files, test mocks.

## MCP Servers

| Server | Purpose |
|--------|--------|
| Supabase | NBA data, experiments, research_proposals |
| Neo4j | Knowledge graph |
| HuggingFace | Space management |

## Telegram

| Bot | Repo | Purpose |
|-----|------|--------|
| @Nomos42Bot | mon-ipad | NBA Brain -- predictions, analysis, research |
| @RGWAbot | rgwa | AI Art Terminal -- generation, gallery, quality |

Channel: @Nomos42

## Department Forge Structure (v19)

| Dept | Name | Karpathy Loop | Metric | Max Run |
|------|------|---------------|--------|----------|
| D1 | RESEARCH | paper→extract→propose→measure | papers/week, techniques tested | 5 min |
| D2 | ENGINEERING | code→test→measure Brier→keep/revert | Brier delta, test pass rate | 5 min |
| D3 | EVOLUTION | mutate→eval→measure fitness→select | gen/hr, best Brier, diversity | 5 min |
| D4 | PRODUCT | build→test→ship→measure | features shipped, Brier delta | 5 min |
| D5 | BUSINESS | price→onboard→convert→optimize | MRR, conversion rate, ARPU | 5 min |
| D6 | EVALUATION | audit→identify→fix→verify | false positive rate, calibration | 5 min |
| D7 | INFRA | check→detect→fix→verify | uptime %, restart count | 5 min |
| D8 | FINANCE | track→report→reconcile→forecast | financial accuracy, burn rate | 5 min |
| D9 | CROSS-REPO | sync→audit→fix→verify | parity score, cross-repo health | 5 min |

Guardian Orchestrator v3: Analyzes ALL 9 department loops, allocates resources, cross-pollinates wins.

## Trading Floor v5 — 16 Real LLM Agents (NBA + Political, parity) — Apr 17, 2026

Every agent is a **real LLM API call** — no hash simulation, no mocks.
Each receives full game context (odds, standings, form, 100+ categories, 22 SOTA strategies)
and REASONS about what to bet. Full 2025-26 season (1257 games).

**COLLECTIVE_MISSION**: every system_prompt is prefixed with the collective preamble —
ONE of 16 LLM agents, SAME data seen by all, $1M season goal, ≥75% deploy / ≥3 allocations
EVERY day, full collab stack (morning council moderated by qwen-235B, Axelrod canon, pacts,
post-mortem log, sacrificial rotation, rogue triggers at <$25 or peer >$250K).

Architecture: TradingAgents (arXiv 2412.20138) + Prediction Arena (2604.07355) + DMAD anti-groupthink

### NBA Traders (16 AI Agents — all real LLM calls, parity with POL, verified live 2026-04-17)
| # | trader_id | Model | Provider | Personality | Risk |
|---|-----------|-------|----------|-------------|------|
| T1 | qwen-quant | Qwen 3 235B-A22B | Cerebras | quantitative | 0.55 |
| T2 | qwen-arb | Qwen 3 235B-A22B | Cerebras | arbitrage | 0.65 |
| T3 | llama-contra | Llama 3.1 8B | Cerebras | contrarian | 0.55 |
| T4 | gemini-anl | Gemini 3 Flash Preview | Google (key 2) | analytical | 0.55 |
| T5 | gemini-tact | Gemini 3 Flash Preview | Google (key 2) | tactical | 0.60 |
| T6 | mistral-large | mistral-large-latest | Mistral | ensemble | 0.50 |
| T7 | mistral-medium | mistral-medium-latest | Mistral | diversified | 0.45 |
| T8 | mistral-small | mistral-small-latest | Mistral | wide-coverage | 0.35 |
| T9 | mistral-nemo | open-mistral-nemo | Mistral | aggressive | 0.70 |
| T10 | mistral-ministral | ministral-8b-latest | Mistral | theoretical | 0.35 |
| T11 | nemotron-120b | NVIDIA Nemotron-3-Super-120B | OpenRouter (free) | chainthought | 0.55 |
| T12 | selfhost-qwen4b | Qwen3-4B (self-hosted CPU) | selfhost:qwen3-4b | disciplined | 0.40 |
| T13 | nvidia-minimax | MiniMax M2.7 (NVIDIA NIM) | NVIDIA NIM (key 1+2) | decisive | 0.58 |
| T14 | nvidia-llama70 | Llama 3.3 70B (NVIDIA NIM) | NVIDIA NIM (key 1+2) | swing | 0.50 |
| T15 | selfhost-gemma3 | Gemma-3-4B (self-hosted CPU) | selfhost:gemma-3-4b | analytical | 0.45 |
| T16 | selfhost-qwen06 | Qwen3-0.6B (self-hosted CPU) | selfhost:qwen3-0.6b | conservative | 0.30 |

### Providers (verified 2026-04-15)
| Provider | Status | Models in use | Notes |
|----------|--------|---------------|-------|
| Cerebras | WORKING | qwen-3-235b-a22b-instruct-2507, llama3.1-8b | Free, 30 RPM. Other models (gpt-oss-120b, zai-glm-4.7) listed but 404 on POST. |
| Google Gemini | WORKING (parser fixed) | gemini-3-flash-preview (key 2) | Free tier, 14 RPM. **MUST set thinkingBudget=0** or thinking eats all tokens. |
| Mistral | WORKING | large/medium/small/nemo/ministral-8b | Free tier, 20 RPM |
| OpenRouter | FREE-LIMITED | nemotron-3-super-120b:free | All other free models 429 across 3 keys (qwen3-80b, llama-3.3-70b, glm-4.5-air, hermes-3-405b) |
| Self-Host (Nomos42/nomos42-llm-cpu) | WORKING | Phi-3.5 GGUF (CPU) | No quota, slow ~8s/call. Used by T12 gemma4-selfhost. |
| Kimi (Moonshot) | DEAD | — | KIMI_API_KEY 401 invalid |
| Gemini 2.5 Pro | DEAD | — | Key 2 forces thinking, key 3 API disabled |
| HF Inference | DEAD | — | Monthly credits exhausted |

### HF Space (HF-First Architecture)
PRIMARY engine: `LBJLincoln26/nba-llm-trading-floor` (FastAPI + Gradio, ~4-6h for full season)
Source: `scripts/arena/hf-llm-trading-floor/app.py` (~1450 lines)
Control: FastAPI endpoints (/api/status, /api/run, /api/stop, /api/mutate, /api/logs, /api/leaderboard)
LLM Gateway: `LBJLincoln26/llm-gateway` (centralized proxy, 11 models, fallback chains)
GH Action: `.github/workflows/trading-floor.yml` — MONITOR ONLY (curls /api/status, commits snapshot)

### Political Traders (10 AI Agents — subset of NBA, excludes T11 nemotron-120b and T12 gemma4-selfhost)
Trading: ETFs, index funds, real stocks based on political signals
Starting capital: $100,000 virtual | Daily rebalancing
<!-- TODO(fleet): add T11 + T12 for parity with NBA -->
**Political TF drift (2026-04-15):** `scripts/arena/hf-political-trading-floor/app.py` has 10 TRADERS (T1–T10 Cerebras/Google/Mistral). NBA has 12 (+T11 nemotron-120b, +T12 gemma4-selfhost). Parity requires patching political app.py and redeploying the Space.

## Browser + Hermes Agents (2026-04-20)

Owned by DR FRANKENSTEIN. Proposal: `data/research/hermes-browser-agents-2026-04-20.md`.

| Space | Account | Purpose | Client |
|-------|---------|---------|--------|
| `LBJLincoln/nomos-browser-nba` | LBJLincoln | Scrape ESPN/bbref/VegasInsider NBA lines via `browser-use` 0.12.6 | `scripts/agents/nba_line_scraper_client.py` → `data/lines/YYYY-MM-DD.json` |
| `TESTforge42/nomos-browser-qa` | TESTforge42 | Pixel-world + dashboard visual QA (Playwright DOM + screenshot) | `scripts/agents/pixel_qa_client.py`; GH Action `.github/workflows/pixel-qa.yml` on push to `scripts/arena/hf-pixel-world/**` |
| `LBJLincoln26/nomos-hermes-agent` | LBJLincoln26 | `NousResearch/hermes-agent` CLI via FastAPI RPC (`/api/task`, `/api/skills`) | direct `POST /api/task` — binary shipped in image, 71 skills preloaded |

Secrets set: `GOOGLE_API_KEY` (all 3). Pending user add: `ANTHROPIC_API_KEY`, `BROWSERUSE_API_KEY`, `NOUS_API_KEY`, `OPENROUTER_API_KEY`. Source: `scripts/arena/hf-browser-nba/`, `hf-browser-qa/`, `hf-hermes-agent/`. Deploy: `HfApi.upload_folder` + `restart_space(factory_reboot=True)`. Nomos42 account NOT touched (saturated).

### Codespaces + local install (FRANKENSTEIN-2)

- **Codespaces/devcontainer**: `.devcontainer/post-create.sh` installs `browser-use==0.12.6`, `uv`, chromium, and Hermes upstream on every new codespace. Wired via `"postCreateCommand": "bash .devcontainer/post-create.sh"` in `devcontainer.json`. Port 7860 forwarded for local RPC testing. New secrets declared: `NOUS_API_KEY`, `BROWSERUSE_API_KEY`, plus `BROWSER_NBA_URL` / `BROWSER_QA_URL` / `HERMES_AGENT_URL` overrides.
- **VM local install**: `scripts/setup/install-browser-hermes.sh` — idempotent, passes `--break-system-packages`, detects existing `~/.local/bin/hermes`, timeouts the NousResearch installer at 15 min (its playwright step can hang on apt-lock). Use `--no-chromium` to skip the ~600MB chromium fetch on lean boxes.
- **Cross-repo clients**:
  - `scripts/agents/dashboard_qa_client.py` + `.github/workflows/dashboard-qa.yml` ping `TESTforge42/nomos-browser-qa` `/api/qa-dashboard` against `nomosdashboard.vercel.app` on push + daily 07:17 UTC. Mirror workflow `browser-qa.yml` lives in the `nomos-dashboard` repo for direct push-to-main gating.
  - `nomos-political-alpha/scripts/scrape_fec_edgar.py` — stub that probes `LBJLincoln/nomos-browser-nba` for `/api/scrape-fec`; exits 0 with `ENDPOINT_NOT_YET_DEPLOYED` until the endpoint is added, then emits `data/fec/YYYY-MM-DD.json`.
- **Client index + cron recipes**: `scripts/agents/README.md`.

## Delegation

| Task | Model | Mechanism |
|------|-------|----------|
| Analysis, decisions, pilotage | Opus 4.6 | Direct |
| 24/7 brain trigger | Sonnet 4.6 | Remote trigger |
| Batch execution, search | Sonnet 4.6 | Agent(model: "sonnet") |
| Codebase exploration | Haiku 4.5 | Agent(model: "haiku") |

## The Trading Floor Crew — 14 Agents × 9 Departments (v3, 2026-04-18)

```
L1 STRATEGIC:  Claude Code CLI + User (vision, milestones, decisions)
    └── THE BOSS (orchestrator, dispatches all 13 agents)

L2 APPLICATION:
    D1 Research:    HAWKEYE (daily recon) + DR FRANKENSTEIN (engine impl)
    D2 Engineering: THE BLACKSMITH (council Karpathy loops)
    D3 Evolution:   SWISH (NBA S10-S22) + LOBBYIST (Political P1-P8)
    D4 Product:     THE HERALD (Telegram publisher) + PIXEL (visual QA)
    D5 Business:    THE ACCOUNTANT (Stripe/Whop/LS revenue)
    D6 Evaluation:  INTERNAL AFFAIRS (scientific integrity audit)
    D9 Cross-Repo:  LAUNCHPAD (CI/CD + deploy orchestration)

L3 LOGISTICS:
    D7 Infra:       SWITCHBOARD (LLM gateway keepalive) + THE PLUMBER (data pipelines)
    D8 Finance:     THE TICKER (live odds, CLV, steam moves)
```

Agent roster: `.claude/agents/ROSTER.md` (v3 — full mapping with cron schedule)

Each department runs a Karpathy autoresearch loop:
- SCAN → PROPOSE → EXECUTE (5-min) → EVALUATE → KEEP/REVERT
- Council state: data/departments/council-<dept>.json
- Metrics log: data/departments/<dept>/metrics.jsonl
- Runner: scripts/councils/hermes-runner.sh <dept>

Shared infra: VM (control tower) + Laptop (local models) + HF Spaces (3 accounts) + GPU burst
