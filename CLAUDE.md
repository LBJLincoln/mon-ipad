# Nomos42 — NBA Quant AI

> Architecture v18 — Department Forge + Trading Floor v4 | Updated: 2026-03-31

## Mission
Build the best NBA prediction AI in the world.
**Best:** Brier 0.21570 (Colab TabICL, 110f, iter 15) | Latest run: 0.21677 (Gen 38, 200f) | **Target:** < 0.20, ROI > 5%, Sharpe > 1.5
**Walk-forward:** avg 0.22447 (Kaggle, 19 weeks, 934 games, tree ensemble — no TabICL on P100)

## Nomos42 Ecosystem

| Flagship | Repo | Bot | Status |
|----------|------|-----|--------|
| NBA Quant AI | mon-ipad + nomos-nba-agent | @Nomos42Bot | ACTIVE -- 6 islands + Kaggle Karpathy |
| Political Alpha | nomos-political-alpha | -- | ACTIVE -- v2.0 engine, 13 categories |
| AI Artistic Generation | rgwa | @RGWAbot | ACTIVE -- generative AI |
| Dashboard Hub | nomos-dashboard | -- | ACTIVE -- /nba /political /rgwa /evolution |
| Factory / Complex RAGs | rag-website | -- | SHELVED |

## 24/7 Autonomous Architecture

```
CLOUD BRAIN (Sonnet 4.6, every 4h at :00)
    ├── Monitor S10-S15 via public /api/status
    ├── Research via 4 Claude Code subagents
    ├── DECIDE: tune GA / diversify / inject features / checkpoint
    ├── ACT on S10 via POST /api/config
    └── Write health-status.json + push
    Trigger: trig_01BS3ixBvt2uKHY9p5EemcgD

VM MUSCLE (cron, every 4h at :30)
    ├── Run predict_today.py (if NBA games)
    ├── Push results to git
    └── Auto-restart data server
    Script: scripts/autonomous-cycle.sh

HF SPACES (6 islands, always-on, CPU tree-only, MAX_FEATURES=200)
    ├── S10 Nomos42/nba-quant:   exploitation (mut=0.09, cx=0.80, feat=63) → nomos42-nba-quant.hf.space
    ├── S11 Nomos42/nba-quant-2: exploration  (mut=0.15, feat=80)          → nomos42-nba-quant-2.hf.space
    ├── S12 Nomos42/nba-evo-3:   extra_trees specialist (mut=0.08, feat=60)
    ├── S13 Nomos42/nba-evo-4:   catboost specialist    (mut=0.10, feat=66)
    ├── S14 Nomos42/nba-evo-5:   lightgbm specialist    (mut=0.08, feat=55)
    └── S15 Nomos42/nba-evo-6:   wide search            (mut=0.18, feat=80, pop=50)

NOTE: S11 URL = nomos42-nba-quant-2.hf.space (NOT nba-evo-2)

KAGGLE KARPATHY LOOP (GPU, 9h sessions, Karpathy autoresearch pattern)
    ├── scripts/kaggle/nba_karpathy_loop.py: NBA evolution (seeds from 6 islands)
    └── scripts/kaggle/political_karpathy_loop.py: Political alpha evolution
    Pattern: modify config → run 5min → measure Brier → keep if better → loop
    Rate: 12 iterations/hr, ~100/session

GOOGLE COLAB (GPU, on-demand)
    └── colab/nba_evolution_gpu.ipynb: T4 GPU evolution

SYSTEM CRONS
    ├── */30  keepalive-spaces.sh (all 6 islands)
    ├── 12,18 nba-daily-odds.py
    └── :30   autonomous-cycle.sh
```

## Skills

| Skill | Purpose |
|-------|--------|
| `/karpathy-loop` | Autonomous research cycle (5 subagents → proposals → quick wins) |
| `/daily-edge` | Daily predictions + value bets + Kelly sizing |
| `/progress-10pct` | Target 10% improvement in weakest metric |
| `/spaces-health` | Health check all 6 HF evolution islands |
| `/evolve-report` | Comprehensive evolution progress report |
| `/agent-review` | Weekly agent performance review (Jensen HR model) |
| `/cross-repo-audit` | Audit all 5 repos for consistency and improvements |

## Rules

1. **ZERO ML on VM** — 1 vCPU / 969 MB RAM. ALL training on HF Spaces
2. **Feature engine parity** — `features/engine.py` = `hf-space/features/engine.py` always
3. **1 fix per iteration** — never multiple simultaneous changes
4. **All experiments tagged** with `feature_engine_version` in Supabase
5. **Feature engine** — v3.1-46cat = 46 categories, 6253 raw features (Cat47 Drive-Rim + Cat48 Passing + Cat49 Play-Type PPP)
6. **MAX_FEATURES=200** — hard cap enforced in init/mutate/crossover on all spaces
7. **Mutation cap** — adaptive mutation capped at 0.15 (deployed S10/S11/S12/S15)
8. **CPU-only islands** — no neural models on CPU (tree-based only), stacking removed
9. **Supabase** — primary (ayqviq) paused (402), using pooler connection (xivvnr)

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

## Department Forge Structure (v18)

| Dept | Name | Karpathy Loop | Metric | Max Run |
|------|------|---------------|--------|---------|
| D1 | RESEARCH | paper→extract→propose→measure | papers/week, techniques tested | 5 min |
| D2 | ENGINEERING | code→test→measure Brier→keep/revert | Brier delta, test pass rate | 5 min |
| D3 | EVOLUTION | mutate→eval→measure fitness→select | gen/hr, best Brier, diversity | 5 min |
| D4 | BETTING | strategy→backtest→measure ROI→keep/revert | ROI, Sharpe, Kelly edge | 5 min |
| D5 | EVALUATION | audit→identify→fix→verify | false positive rate, calibration | 5 min |
| D6 | INFRA | check→detect→fix→verify | uptime %, restart count | 5 min |
| D7 | POLITICAL | signal→feature→measure alpha→keep/revert | political Brier, ETF ROI | 5 min |
| D8 | CREATIVE (RGWA) | generate→quality→curate→publish | quality score, output/day | 5 min |
| D9 | COMMUNICATION | content→post→measure engagement→optimize | engagement rate, channels active | 5 min |
| D10 | BUSINESS | pricing→onboard→measure conversion→optimize | MRR, conversion rate, ARPU | 5 min |
| D11 | FINANCE | track→report→reconcile→forecast | financial accuracy, burn rate | 5 min |

Guardian Orchestrator v3: Analyzes ALL 11 department loops, allocates resources, cross-pollinates wins.

## Trading Floor v4 — Multi-AI Competition

### NBA Traders (5 AI Agents)
| # | Agent | Provider | Sees | Decides |
|---|-------|----------|------|---------|
| T1 | Gemini | Google | All predictions + all strategies + others' results | Betting strategy + Kelly sizing |
| T2 | OpenRouter | Multi-model | Same | Same |
| T3 | Claude | Anthropic CLI | Same | Same |
| T4 | Codex | OpenAI | Same | Same |
| T5 | Grok | xAI | Same | Same |

### Political Traders (5 AI Agents — same providers)
Trading: ETFs, index funds, real stocks based on political signals
Starting capital: $100,000 virtual | Daily rebalancing

### Command Center Offices (Backend Departments)
Research HQ | Engineering Lab | Evolution Chamber | Betting Ops | Infra Bridge | Political Intel
Each shows: dept status, active loops, metrics, agent activity

## Delegation

| Task | Model | Mechanism |
|------|-------|-----------|
| Analysis, decisions, pilotage | Opus 4.6 | Direct |
| 24/7 brain trigger | Sonnet 4.6 | Remote trigger |
| Batch execution, search | Sonnet 4.6 | Agent(model: "sonnet") |
| Codebase exploration | Haiku 4.5 | Agent(model: "haiku") |


## Forge v19 — 3 Layers × 8 Departments (2026-04-03T20:02:58Z)

```
L1 STRATEGIC:  Claude Code CLI + User (vision, milestones, decisions)
L2 APPLICATION: D1 Research | D2 Engineering | D3 Evolution | D4 Product | D5 Business | D6 Evaluation
L3 LOGISTICS:   D7 Infra | D8 Finance
```

Each department runs a Karpathy autoresearch loop:
- SCAN → PROPOSE → EXECUTE (5-min) → EVALUATE → KEEP/REVERT
- Council state: data/departments/council-<dept>.json
- Metrics log: data/departments/<dept>/metrics.jsonl
- Runner: scripts/councils/department-council.sh <dept>

Shared infra: VM (control tower) + Laptop (local models) + HF Spaces (3 accounts) + GPU burst

