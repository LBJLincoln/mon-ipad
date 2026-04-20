# Nomos42 — NBA Quant AI + Political Alpha

> Architecture v21 — "The Trading Floor Crew" (14 agents × 9 depts × 4 tracks) + TF v3 (17 LLM agents) + 21 Evolution Islands | Updated: 2026-04-19

## Mission
Build the best NBA prediction AI in the world.
**Best:** Brier 0.21514 (Colab TabICL, 186f, iter 129) | Fleet best: 0.22073 (S22 venn_abers_fusion, gen 39, checkpointed 2026-04-19) | **Target:** < 0.20, ROI > 5%, Sharpe > 1.5
**Walk-forward:** avg 0.22447 (Kaggle, 19 weeks, 934 games, tree ensemble — no TabICL on P100)
**NBA TF v4 (Apr 18, 17 agents, FULL FREEDOM):** BASE_CATS FDR gate DELETED — agents now free across all 227 categories per game. Edge threshold 0.03→0.01. Top-5 edges → top-50 exposed to LLM prompt. MIN_DEPLOY_PCT=0.75 floor + tiered Kelly cap (2%/5%/10%). Live day 7/175, 17 agents bidding.
**Political TF (Apr 18):** 17 agents, day 25/50. $13K leakage bug fixed (excess_return fallback removed 2026-04-18 commit 1a7a02b48). State wiped clean.
**PQTF v2 (Apr 18, 6 derivatives day-traders):** Multi-leg options (vertical/iron_condor/straddle/butterfly). $600K fleet start → target 10× by Nov 3. Live day 47/50.
**Top-tier 14-agent Crew (Apr 18):** THE BOSS / SWISH / LOBBYIST / HAWKEYE / DR FRANKENSTEIN / THE BLACKSMITH / SWITCHBOARD / INTERNAL AFFAIRS / THE TICKER / THE HERALD / THE ACCOUNTANT / PIXEL / THE PLUMBER / LAUNCHPAD — L1/L2/L3 layered, mental-model personas, refusal rules, niche-expert bars. Live scientific snapshot via `data/pipeline-health.json` (PLUMBER :35 every 4h) + `data/audit/` (INTERNAL AFFAIRS :40 every 4h).

## Nomos42 Ecosystem

| Flagship | Repo | Bot | Vercel | Status |
|----------|------|-----|--------|--------|
| NBA Quant AI | mon-ipad + nomos-nba-agent | @Nomos42Bot | via dashboard | ACTIVE -- 6 NBA + 5 POL SURVIVOR islands (was 13+8; 10 "nuls" eliminated — slots redirected to selfhost LLMs) + Kaggle Karpathy |
| Political Alpha | nomos-political-alpha | -- | none (data only) | ACTIVE -- v3.19 engine, 22 categories, 718 features |
| Dashboard Hub | nomos-dashboard | -- | nomosdashboard.vercel.app | ACTIVE -- /nba /political /evolution /trading-floor /forge /world |
| AI Artistic Generation | rgwa | @RGWAbot | none | ZOMBIE -- no commits since Mar 2026, deprioritized |
| Factory / Complex RAGs | rag-website | -- | none | SHELVED |

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
    ├── S13 Nomos42/nba-evo-4:        catboost      gen=130   brier=0.22749
    ├── S14 Nomos42/nba-evo-5:        lightgbm      gen=554   brier=0.22186
    ├── S15 Nomos42/nba-evo-6:        wide search   gen=127   brier=0.22418
    ├── S17 LBJLincoln26/nba-evo-s17: ensemble      gen=78    brier=0.22340
    ├── S18 TESTforge42/nba-evo-s18:  catboost_spec gen=1030  brier=0.22114
    └── S22 TESTforge42/nba-evo-s22:  venn_abers_fusion gen=39 brier=0.22073  ★ FLEET BEST
    Political Survivors (5, CPU tree-only):
    ├── P1 Nomos42/political-alpha:      xgboost        gen=3042  brier=0.24996
    ├── P2 Nomos42/political-alpha-2:    lightgbm       gen=11953 brier=0.25223
    ├── P4 LBJLincoln/political-alpha-4: logistic       gen=16728 brier=0.25146
    ├── P5 LBJLincoln/political-alpha-5: catboost       gen=1567  brier=0.25347
    └── P7 LBJLincoln/political-alpha-7: gradient_boost gen=2098  brier=0.24987  ★ POL BEST

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
2. **Feature engine parity** — `features/engine.py` = `hf-space/features/engine.py` always
3. **1 fix per iteration** — never multiple simultaneous changes
4. **All experiments tagged** with `feature_engine_version` in Supabase
5. **Feature engine** — v3.1 = 54 categories, ~7213 raw feature candidates (verified 2026-04-18 from features/engine.py header)
6. **MAX_FEATURES=200** — hard cap enforced in init/mutate/crossover on all spaces (target 50-100 selected per island via GA)
7. **Mutation cap** — adaptive mutation capped at 0.15 (deployed S10/S11/S12/S15)
8. **CPU-only islands** — no neural models on CPU (tree-based only), stacking removed
9. **Supabase** — primary (ayqviq) paused (402), using pooler connection (xivvnr)
10. **Git mutex** — every autonomous agent commit MUST shell through `scripts/lib/safe_commit.sh <CODENAME> "<msg>" [paths...]` (flock on `/tmp/nomos-git.lock`, pull --rebase --autostash, 3× push retry, `[AGENT]` prefix). Raw `git push` from agents is banned — with 14 crew on staggered crons the race-reject rate was unacceptable.

## New Tools (Apr 4)

| Tool | Script | Purpose |
|------|--------|---------|
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
|-----|------|---------|
| @Nomos42Bot | mon-ipad | NBA Brain -- predictions, analysis, research |
| @RGWAbot | rgwa | AI Art Terminal -- generation, gallery, quality |

Channel: @Nomos42

## Department Forge Structure (v19)

| Dept | Name | Karpathy Loop | Metric | Max Run |
|------|------|---------------|--------|---------|
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

## Delegation

| Task | Model | Mechanism |
|------|-------|-----------|
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

