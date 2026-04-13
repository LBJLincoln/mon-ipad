# Nomos42 — NBA Quant AI + Political Alpha

> Architecture v20 — Department Forge (9 depts) + Trading Floor v5 (10 real LLM agents) + 16 Evolution Islands | Updated: 2026-04-13

## Mission
Build the best NBA prediction AI in the world.
**Best:** Brier 0.21570 (Colab TabICL, 110f, iter 15) | Fleet best: 0.22251 (S14 LightGBM, gen 108) | **Target:** < 0.20, ROI > 5%, Sharpe > 1.5
**Walk-forward:** avg 0.22447 (Kaggle, 19 weeks, 934 games, tree ensemble — no TabICL on P100)

## Nomos42 Ecosystem

| Flagship | Repo | Bot | Vercel | Status |
|----------|------|-----|--------|--------|
| NBA Quant AI | mon-ipad + nomos-nba-agent | @Nomos42Bot | via dashboard | ACTIVE -- 8 NBA islands + 4 Political islands + Kaggle Karpathy |
| Political Alpha | nomos-political-alpha | -- | none (data only) | ACTIVE -- v3.19 engine, 22 categories, 718 features |
| Dashboard Hub | nomos-dashboard | -- | nomosdashboard.vercel.app | ACTIVE -- /nba /political /evolution /trading-floor /forge /world |
| AI Artistic Generation | rgwa | @RGWAbot | none | ZOMBIE -- no commits since Mar 2026, deprioritized |
| Factory / Complex RAGs | rag-website | -- | none | SHELVED |

## 24/7 Autonomous Architecture

```
CLOUD BRAIN (Sonnet 4.6, every 4h at :00)
    ├── Monitor S10-S17 + P1-P4 via public /api/status
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

HF EVOLUTION ISLANDS (8 NBA + 4 Political = 12 active, target 16)
    NBA Islands (all UP, CPU tree-only, MAX_FEATURES=200):
    ├── S10 Nomos42/nba-quant:        exploitation  gen=86   brier=0.22825  → nomos42-nba-quant.hf.space
    ├── S11 Nomos42/nba-quant-2:      exploration   gen=141  brier=0.24572  → nomos42-nba-quant-2.hf.space
    ├── S12 Nomos42/nba-evo-3:        extra_trees   gen=160  brier=0.23252  → nomos42-nba-evo-3.hf.space
    ├── S13 Nomos42/nba-evo-4:        catboost      gen=130  brier=0.22749  → nomos42-nba-evo-4.hf.space
    ├── S14 Nomos42/nba-evo-5:        lightgbm      gen=108  brier=0.22251  → nomos42-nba-evo-5.hf.space  ★ FLEET BEST
    ├── S15 Nomos42/nba-evo-6:        wide search   gen=127  brier=0.22418  → nomos42-nba-evo-6.hf.space
    ├── S16 LBJLincoln26/nba-evo-s16: gradient_boost gen=86  brier=0.22573  → lbjlincoln26-nba-evo-s16.hf.space
    └── S17 LBJLincoln26/nba-evo-s17: ensemble      gen=139  brier=0.22493  → lbjlincoln26-nba-evo-s17.hf.space
    Political Islands (all UP, CPU tree-only):
    ├── P1 Nomos42/political-alpha:      xgboost   gen=3042  brier=0.24996  → nomos42-political-alpha.hf.space
    ├── P2 Nomos42/political-alpha-2:    lightgbm  gen=2212  brier=0.25223  → nomos42-political-alpha-2.hf.space
    ├── P3 LBJLincoln/political-alpha-3: xgboost   gen=10344 brier=0.24990  → lbjlincoln-political-alpha-3.hf.space  ★ POL BEST
    ├── P4 LBJLincoln/political-alpha-4: logistic  gen=4301  brier=0.25146  → lbjlincoln-political-alpha-4.hf.space
    └── P5-P8: NOT YET DEPLOYED (need 4 more for 8-island parity with NBA)

NOTE: S11 URL = nomos42-nba-quant-2.hf.space (NOT nba-evo-2)

HF TRADING FLOOR (Real LLM experiment, 10 agents)
    ├── LBJLincoln26/nba-llm-trading-floor: Live 10-agent NBA experiment
    └── Source: scripts/arena/hf-llm-trading-floor/

HF OTHER SPACES (25 total across 3 accounts)
    ├── Dept Councils: d1-research, d2-engineering, d3-evolution, d4-product, d5-business, d6-evaluation
    ├── Free LLM Chat: gemma4-chat, qwen35-chat
    ├── Docker Runtimes: nomos42-llm-cpu, nomos42-llm
    ├── Legacy TF: Nomos42/nba-trading-floor (v4, superseded)
    └── Pixel World: Nomos42/pixel-world (static)

KAGGLE KARPATHY LOOP (GPU, 9h sessions, Karpathy autoresearch pattern)
    ├── scripts/kaggle/nba_karpathy_loop.py: NBA evolution (seeds from 8 islands)
    └── scripts/kaggle/political_karpathy_loop.py: Political alpha evolution
    Pattern: modify config → run 5min → measure Brier → keep if better → loop
    Rate: 12 iterations/hr, ~100/session

GOOGLE COLAB (GPU, on-demand)
    └── colab/nba_evolution_gpu.ipynb: T4 GPU evolution

GITHUB ACTIONS (3 workflows on schedule)
    ├── Trading Floor:        */2h — 10-agent real LLM iteration
    ├── Backtest Swarm:       */2h — continuous scientific backtest
    ├── Scientific Experiment: */2h — CPCV + DSR gate
    ├── GPU Cron Launcher:    manual — Kaggle/Colab trigger
    └── Arena Engine:         daily — full arena evaluation

SYSTEM CRONS (28 active on VM, all lightweight)
    ├── */30  keepalive-spaces.sh (all 12 islands + TF)
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
5. **Feature engine** — v3.1-54cat = 54 categories, 7213 raw features
6. **MAX_FEATURES=200** — hard cap enforced in init/mutate/crossover on all spaces
7. **Mutation cap** — adaptive mutation capped at 0.15 (deployed S10/S11/S12/S15)
8. **CPU-only islands** — no neural models on CPU (tree-based only), stacking removed
9. **Supabase** — primary (ayqviq) paused (402), using pooler connection (xivvnr)

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

## Trading Floor v5 — 10 Real LLM Agents (Apr 13, 2026)

Every agent is a **real LLM API call** — no hash simulation, no mocks.
Each receives full game context (odds, standings, form, 100+ categories, 22 SOTA strategies)
and REASONS about what to bet. Full 2025-26 season (1257 games).

Architecture: TradingAgents (arXiv 2412.20138) + Prediction Arena (2604.07355) + DMAD anti-groupthink

### NBA Traders (10 AI Agents — all real LLM calls)
| # | Agent | Model | Provider | Personality | Risk |
|---|-------|-------|----------|-------------|------|
| T1 | Gemini Flash | Gemini 2.5 Flash | Google (key 1) | Analytical | 0.60 |
| T2 | Gemini 3 Flash | Gemini 3 Flash Preview | Google (key 2) | Diversified | 0.50 |
| T3 | Qwen 3 235B | Qwen 3 235B-A22B | Cerebras | Quantitative | 0.55 |
| T4 | Llama 3.1 8B | Llama 3.1 8B | Cerebras | Contrarian | 0.65 |
| T5 | ZAI GLM 4.7 | GLM 4.7 | Cerebras | Conservative | 0.40 |
| T6 | GPT-OSS 120B | GPT-OSS 120B | Cerebras | Aggressive | 0.70 |
| T7 | Gemma 4 26B | Gemma 4 26B | OpenRouter (free) | Arbitrage | 0.75 |
| T8 | Nemotron 120B | Nemotron 3 Super 120B | OpenRouter (free) | Tactical | 0.60 |
| T9 | MiniMax M2.5 | MiniMax M2.5 | OpenRouter (free) | Theoretical | 0.35 |
| T10 | Qwen3 80B | Qwen3 Next 80B | OpenRouter (free) | Ensemble | 0.50 |

### Providers (verified 2026-04-13)
| Provider | Status | Models | Cost |
|----------|--------|--------|------|
| Cerebras | WORKING | qwen-3-235b, llama3.1-8b, zai-glm-4.7, gpt-oss-120b | Free, 30 RPM |
| Google Gemini | WORKING | gemini-2.5-flash (key 1), gemini-3-flash-preview (key 2) | Free tier, 14 RPM |
| OpenRouter | FREE ONLY | gemma-4-26b, nemotron-120b, minimax-m2.5, qwen3-80b | Free tier, 20 RPM |
| HF Inference | DEAD | — | Monthly credits exhausted |

### HF Space
Live experiment: `LBJLincoln26/nba-llm-trading-floor` (Gradio, ~4-6h for full season)
Source: `scripts/arena/hf-llm-trading-floor/app.py` (1296 lines)
GH Action: runs every 2h via `.github/workflows/trading-floor.yml`

### Political Traders (10 AI Agents — same models, same providers)
Trading: ETFs, index funds, real stocks based on political signals
Starting capital: $100,000 virtual | Daily rebalancing

## Delegation

| Task | Model | Mechanism |
|------|-------|-----------|
| Analysis, decisions, pilotage | Opus 4.6 | Direct |
| 24/7 brain trigger | Sonnet 4.6 | Remote trigger |
| Batch execution, search | Sonnet 4.6 | Agent(model: "sonnet") |
| Codebase exploration | Haiku 4.5 | Agent(model: "haiku") |


## Forge v19 — 3 Layers × 9 Departments (2026-04-04T08:00:00Z)

```
L1 STRATEGIC:  Claude Code CLI + User (vision, milestones, decisions)
L2 APPLICATION: D1 Research | D2 Engineering | D3 Evolution | D4 Product | D5 Business | D6 Evaluation | D9 Cross-Repo
L3 LOGISTICS:   D7 Infra | D8 Finance
```

Each department runs a Karpathy autoresearch loop:
- SCAN → PROPOSE → EXECUTE (5-min) → EVALUATE → KEEP/REVERT
- Council state: data/departments/council-<dept>.json
- Metrics log: data/departments/<dept>/metrics.jsonl
- Runner: scripts/councils/department-council.sh <dept>

Shared infra: VM (control tower) + Laptop (local models) + HF Spaces (3 accounts) + GPU burst

