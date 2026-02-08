# Multi-RAG Orchestrator — SOTA 2026

## Objective

Benchmark, test, and iteratively improve 4 n8n RAG workflows deployed on n8n cloud.
The system evaluates each pipeline's accuracy, latency, and cost, then proposes targeted
workflow structure improvements ONLY when data shows a clear need (e.g. accuracy plateau,
high error rate, routing failures).

**Current phase: Phase 1 — Baseline (200q, iterative improvement loop)**

See `phases/overview.md` for the full 5-phase strategy:
Phase 1 (200q) → Phase 2 (1,000q) → Phase 3 (~10Kq) → Phase 4 (~100Kq) → Phase 5 (1M+q)

---

## Terminal Execution Environment

**Claude Code (sandbox) does NOT have network access.** All commands that call
external APIs (n8n, Supabase, Neo4j, Pinecone, OpenRouter) MUST be run manually
by the user on their terminal.

### Where to run commands

| Where | What |
|---|---|
| **Termius** (SSH to Google Cloud free tier VM) | All `python` commands that hit APIs (eval, populate, sync, deploy) |
| **Google Cloud Console** (browser SSH) | Same — alternative if Termius unavailable |
| **Claude Code** (this sandbox) | Code editing, analysis, git commits, dry-runs only |

### Before every terminal session — ALWAYS pull from main

```bash
# === RUN THIS FIRST IN TERMIUS / GOOGLE CLOUD CONSOLE ===
cd ~/mon-ipad
git pull origin main          # Always sync from main before running anything
```

### Environment variables — paste once per terminal session

```bash
export SUPABASE_PASSWORD="udVECdcSnkMCAPiY"
export PINECONE_API_KEY="pcsk_6GzVdD_BbHsYNvpcngMqAHH5EvEa9XLnmFpEK9cx5q5xkMp72z5KFQ1q7dEjp8npWhJGBY"
export PINECONE_HOST="https://sota-rag-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
export NEO4J_PASSWORD="jV_zGdxbu-emQZM-ZSQux19pTZ5QLKejR2IHSzsbVak"
export OPENROUTER_API_KEY="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"
export N8N_API_KEY="..."
export N8N_HOST="https://amoret.app.n8n.cloud"
```

### Google Cloud free tier VM setup (one-time)

```bash
sudo apt-get update && sudo apt-get install -y python3 python3-pip postgresql-client git
pip3 install requests
git clone https://github.com/LBJLincoln/mon-ipad.git ~/mon-ipad
cd ~/mon-ipad
```

---

## Quick Start — Two-Phase Iteration Cycle

The iteration loop has two phases: **fast iteration** (10q, rapid workflow tuning)
and **full evaluation** (200q, parallel). Workflows are validated with fast-iter
before committing to a full eval.

### Phase A: Fast Iteration Loop (10q per pipeline, ~2-3 min)

This is the inner loop for rapid workflow improvement. Run this repeatedly
until results look good, THEN proceed to Phase B.

**Run in Termius / Google Cloud Console:**
```bash
cd ~/mon-ipad && git pull origin main

# Step A0: Read current state
cat STATUS.md

# Step A1: Sync workflows from n8n cloud
python3 workflows/sync.py

# Step A2: Smoke test (5 questions)
python3 eval/quick-test.py --questions 5

# Step A3: Fast iteration test
python3 eval/fast-iter.py --label "description"

# Step A4: Review results (auto-saved to logs/fast-iter/ and logs/pipeline-results/)

# Step A5: If bad → fix workflow in n8n → repeat from A1
#          If good → proceed to Phase B

# Step A6: Commit results
git add docs/ logs/ && git commit -m "fast-iter: ..." && git push origin main
```

**Fast-iter features:**
- Runs all 4 pipelines in **parallel** (~4x speedup)
- Selects a **strategic mix**: 50% previously-failing, 30% untested, 20% passing (regression check)
- Saves per-pipeline JSON snapshots to `logs/pipeline-results/`
- Auto-compares with previous fast-iter run (regressions/fixes)
- Results feed the dashboard in real-time

**Commands (run in Termius / Google Cloud Console):**
```bash
python3 eval/fast-iter.py                                 # 10q per pipeline, all 4
python3 eval/fast-iter.py --questions 5 --pipelines graph # 5q, graph only
python3 eval/fast-iter.py --only-failing                  # Re-test only failures
python3 eval/fast-iter.py --label "after fuzzy matching"  # Tag the run
```

### Phase B: Full Evaluation (200q, parallel, ~15-20 min)

Run this only AFTER fast-iter shows the workflow is ready. Uses **parallel execution**
across all 4 pipelines simultaneously.

**Run in Termius / Google Cloud Console:**
```bash
cd ~/mon-ipad && git pull origin main

# Step B1: Run parallel evaluation
python3 eval/run-eval-parallel.py --reset --label "Iter N: description"

# Step B2: Analyze results
python3 eval/analyzer.py

# Step B3: Commit + push
git add docs/ workflows/ logs/ && git commit -m "eval: Iter N" && git push origin main

# Step B4: Back to Phase A for next improvement
```

**Parallel eval features:**
- All 4 pipelines execute **concurrently** (ThreadPoolExecutor)
- Thread-safe dashboard writes (live-writer.py uses locks)
- Per-pipeline result snapshots saved to `logs/pipeline-results/`
- ~4x speedup vs sequential `run-eval.py`

**Commands (run in Termius / Google Cloud Console):**
```bash
python3 eval/run-eval-parallel.py --reset --label "Iter 6: fuzzy matching"  # Full 200q
python3 eval/run-eval-parallel.py --max 20 --types graph,orchestrator       # Subset
python3 eval/run-eval-parallel.py --push                                     # Auto git push
```

### Legacy: Sequential Evaluation

The original sequential `run-eval.py` is still available for debugging or
when you want to isolate a single pipeline:

**Run in Termius / Google Cloud Console:**
```bash
python3 eval/run-eval.py --types graph --max 10 --label "debug graph"
```

**Key principle**: Each iteration should target ONE specific improvement.
Don't change multiple things at once — it makes it impossible to attribute improvements.

---

## Phase Gates (Exit Criteria)

### Phase 1 — Baseline (200q) — CURRENT
| Pipeline | Current | Target | Gap | Status |
|---|---|---|---|---|
| Standard | 82.6% | ≥85% | -2.4pp | CLOSE |
| Graph | 52.0% | ≥70% | -18pp | ITERATING |
| Quantitative | 80.0% | ≥85% | -5pp | ITERATING |
| Orchestrator | 49.6% | ≥70% | -20.4pp | CRITICAL |
| **Overall** | **67.7%** | **≥75%** | **-7.3pp** | **ITERATING** |

Additional Phase 1 exit criteria:
- [ ] Orchestrator P95 latency <15s, error rate <5%
- [ ] At least 3 consecutive stable iterations (no regression)

### Phase 2 — Expand (1,000q)
- Requires: Phase 1 gates passed + DB ingestion (Neo4j entities + Supabase tables from HF datasets)
- Targets: Graph ≥60%, Quantitative ≥70% on new questions
- No Phase 1 regression
- **DB setup status**: MIGRATION_READY (scripts created, need to run on terminal)

**Phase 2 DB ingestion (run in Termius / Google Cloud Console):**
```bash
cd ~/mon-ipad && git pull origin main

# 1. Create Supabase tables + populate 450 rows
python3 db/populate/phase2_supabase.py

# 2. Extract ~5000 entities into Neo4j (heuristic mode, fast)
python3 db/populate/phase2_neo4j.py

# 2b. OR with LLM for higher quality (~5min, ~$0.05)
python3 db/populate/phase2_neo4j.py --llm
```

### Phase 3 — Scale (~9,500q)
- Requires: Phase 2 gates + full `db/populate/push-datasets.py` execution
- Targets: Standard ≥75%, Graph ≥55%, Quant ≥65%, Orch ≥60%

### Phase 4 — Full HF (~100Kq)
- Requires: Phase 3 gates + 10x ingestion + potential DB upgrades
- Targets: No regression from Phase 3

### Phase 5 — Million+ (1M+q)
- Requires: Production infrastructure
- Targets: Sustained accuracy + throughput >100q/hour

---

## Iteration Results (200q, Feb 8 2026 — 5 iterations)

| Pipeline | Baseline | After Improvements | Delta | Errors | Status |
|---|---|---|---|---|---|
| **Standard** | 78.0% | **82.6%** | +4.6pp | 0 | topK increased, good recall |
| **Graph** | 50.0% | **52.0%** (13/25) | +2.0pp | 1 | Fixed JS syntax, fuzzy matching deployed |
| **Quantitative** | 80.0% | **80.0%** | +0.0pp | 14 | Stable, SQL edge cases remain |
| **Orchestrator** | 48.0% | **49.6%** | +1.6pp | 37 | Timeouts + credits exhausted |
| **Overall** | **64.0%** | **67.7%** | **+3.7pp** | — | — |

### Iteration Log
1. **Iter 1** (40q): Standard 90%, Graph 40%, Quant 100%, Orch 60%. Identified Graph entity extraction + Orch timeout as critical.
2. **Iter 2** (60q): Fixed Graph RAG Response Formatter JS syntax error (single quotes inside single-quoted string). Deployed "never say insufficient context" directive. Orchestrator Intent Analyzer timeout reduced.
3. **Iter 3** (100q, 200 total): All 200 base questions tested. Graph RAG improved to 60% on retested questions. Standard at 100% for new questions.
4. **Iter 4** (18q retested): OpenRouter API credits exhausted — all remaining orchestrator retests returned empty/error. Not a workflow issue.
5. **Iter 5** (code improvements, no eval — env vars not set): Deep analysis of 79 error files. apply.py rewritten with 17 workflow patches (9 P0). Orchestrator: continueOnFail, Response Builder null-safe, timeouts capped. Graph: fuzzy matching (Levenshtein), entity extraction rules. Quant: SQL hints, ILIKE, zero-row detection. Standard: RRF boost, empty fallback. Eval scoring improved: exact_match, normalize_text, retry on empty responses. Fixed quantitative-rag.json invalid JSON.

---

## Root Cause Analysis (Priority Order)

### 1. Orchestrator (48% — CRITICAL, 38% error rate)
- Timeouts cascade: waits for ALL sub-pipelines, latency = max(standard, graph, quant) + routing overhead
- Routing logic adds 4-5s overhead per query
- No fallback: if sub-pipeline times out, entire request fails
- Response Builder V9 gets empty `$json.task_results` from timed-out sub-workflows
- **Fix**: Per-pipeline timeout guards, smart routing (1-2 pipelines instead of broadcast), null-check in Response Builder

### 2. Graph RAG (50% — HIGH PRIORITY)
- Entity extraction failures: HyDE extracts wrong names → Neo4j lookup returns nothing
- Fuzzy matching deployed but entities like Ada Lovelace, Mozart, Roosevelt, Lincoln not in Neo4j
- Multi-hop path gaps (some >3 hops)
- **Fix**: Fuzzy matching in Neo4j, entity catalog in HyDE prompt, bidirectional entity seeding

### 3. Standard RAG (82.6% — CLOSE TO TARGET)
- Low F1 even on passing answers (mean 0.16): verbose but technically correct
- 13 hard failures on topics not in Pinecone
- **Fix**: Prompt tuning for conciseness, topK tuning, potential re-embedding

### 4. Quantitative RAG (80% — NEAR TARGET)
- SQL edge cases: multi-table JOINs, growth calculations, employee queries (only 9 rows)
- **Fix**: SQL template fixes, data seeding for employees table

---

## Remaining Blockers
1. **OpenRouter credits**: Need to refill to continue orchestrator + graph testing
2. **Orchestrator timeouts**: Sub-workflow chaining exceeds 60s for complex queries
3. **Graph RAG entity extraction**: Many entities still not found in Neo4j
4. **Quantitative edge cases**: Employee count queries return 0, product queries fail

---

## Architecture

### n8n Cloud Workflows (host: amoret.app.n8n.cloud)
| Workflow | Webhook Path | DB | Nodes |
|---|---|---|---|
| WF5 Standard RAG V3.4 | `/webhook/rag-multi-index-v3` | Pinecone | 23 |
| WF2 Graph RAG V3.3 | `/webhook/ff622742-...` | Neo4j + Supabase | 26 |
| WF4 Quantitative V2.0 | `/webhook/3e0f8010-...` | Supabase SQL | 25 |
| V10.1 Orchestrator | `/webhook/92217bb8-...` | Routes to above | 68 |

### Databases
| DB | Content | Size |
|---|---|---|
| **Pinecone** | Vector embeddings (text-embedding-3-small, 1536-dim) | 10,411 vectors, 12 namespaces |
| **Neo4j** | Entity graph (Person, Org, Tech, City, Museum, Disease) | 110+ nodes, 151+ relationships |
| **Supabase** | Financial tables (3 companies) + benchmark_datasets + community_summaries | 88 rows + HF datasets |

---

## Repository Structure

```
mon-ipad/
├── CLAUDE.md                          # THIS FILE — project anchor
├── STATUS.md                          # Session entry point, quick reference
│
├── datasets/                          # Question datasets by phase
│   ├── manifest.json                  # 16 HF datasets metadata + ingestion status
│   ├── phase-1/
│   │   ├── graph-quant-50x2.json      # 100q: 50 graph + 50 quantitative
│   │   └── standard-orch-50x2.json    # 100q: 50 standard + 50 orchestrator
│   └── phase-2/
│       └── hf-1000.json               # 1,000q: HuggingFace datasets
│
├── eval/                              # Evaluation scripts
│   ├── run-eval.py                    # Sequential eval runner (legacy/debug)
│   ├── run-eval-parallel.py           # PARALLEL eval runner (~4x faster)
│   ├── fast-iter.py                   # Fast iteration: 10q/pipeline, parallel
│   ├── live-writer.py                 # Writes results to docs/data.json + logs/ (thread-safe)
│   ├── quick-test.py                  # Smoke tests (5q/pipeline)
│   ├── analyzer.py                    # Post-eval analysis + recommendations
│   └── iterate.sh                     # Run eval + auto-commit + push
│
├── workflows/                         # n8n workflow management
│   ├── manifest.json                  # Version tracking (hashes, diffs)
│   ├── sync.py                        # Pull workflows from n8n cloud
│   ├── deploy/
│   │   ├── deploy.py                  # Deploy workflow JSON to n8n via API
│   │   ├── deploy-iteration2-fixes.py
│   │   ├── deploy-embedding-fallback.py
│   │   ├── deploy-free-model-fixes.py
│   │   └── deploy-logging-patches.py
│   ├── source/                        # Source workflow JSONs
│   │   ├── standard-rag.json
│   │   ├── graph-rag.json
│   │   ├── quantitative-rag.json
│   │   ├── orchestrator.json
│   │   └── ingestion.json
│   ├── improved/                      # Latest patched versions
│   │   ├── standard-rag.json
│   │   ├── graph-rag.json
│   │   ├── quantitative-rag.json
│   │   ├── orchestrator.json
│   │   └── apply.py
│   ├── snapshots/                     # Timestamped workflow snapshots
│   └── helpers/                       # Benchmark helper workflows for n8n
│       ├── WF-Benchmark-Dataset-Ingestion.json
│       ├── WF-Benchmark-Monitoring.json
│       ├── WF-Benchmark-Orchestrator-Tester.json
│       └── WF-Benchmark-RAG-Tester.json
│
├── db/                                # Database schemas & population
│   ├── migrations/
│   │   ├── supabase-core.sql
│   │   ├── financial-tables.sql
│   │   └── community-summaries.sql
│   │   └── phase2-financial-tables.sql # Phase 2: finqa/tatqa/convfinqa tables
│   ├── populate/
│   │   ├── all.py                     # Master DB population script
│   │   ├── neo4j.py                   # Neo4j entity graph builder (Phase 1)
│   │   ├── phase2_neo4j.py            # Neo4j entity extraction (Phase 2, 500 graph q)
│   │   ├── phase2_supabase.py         # Supabase table population (Phase 2, 450 rows)
│   │   ├── fetch_wikitablequestions.py # Fetch wiki table CSVs from HuggingFace
│   │   ├── pinecone.py                # Pinecone embedding creator
│   │   ├── push-datasets.py           # HuggingFace dataset ingestion
│   │   └── migrate.py                 # Run SQL migrations
│   └── readiness/                     # DB readiness checks per phase
│       ├── phase-1.json ... phase-5.json
│
├── phases/
│   └── overview.md                    # Full 5-phase strategy + exit criteria
│
├── docs/                              # GitHub Pages dashboard
│   ├── index.html                     # Interactive dashboard (10 tabs)
│   ├── data.json                      # Live evaluation data (v2 format)
│   ├── tested-questions.json          # Dedup manifest
│   └── data-v1-backup.json
│
├── logs/                              # Structured execution traces
│   ├── README.md                      # Schema documentation
│   ├── executions/                    # Per-session JSONL logs
│   ├── errors/                        # Individual error trace files (102 files)
│   ├── db-snapshots/                  # Periodic DB state snapshots (15 files)
│   ├── pipeline-results/              # Per-pipeline JSON result snapshots
│   └── fast-iter/                     # Fast iteration run snapshots
│
└── .github/workflows/
    ├── rag-eval.yml                   # Scheduled + manual eval runner
    ├── agentic-eval.yml               # Post-eval AI analysis
    ├── n8n-error-log.yml              # Receives n8n errors via repository_dispatch
    └── dashboard-deploy.yml           # Auto-deploy dashboard to GitHub Pages
```

---

## Dashboard (docs/index.html — 10 tabs)

The dashboard is the central monitoring and analysis tool. It reads `docs/data.json`
and auto-refreshes every 15 seconds.

### Tabs
1. **Command Center** — Phase progress, pipeline gauges vs targets, blockers, AI recommendations
2. **Test Matrix** — Questions x Iterations grid (heat map: green/red/yellow per cell with F1 gradient)
3. **Iterations** — Timeline, accuracy trend chart, iteration comparison (fixed/broken/improved), burndown to targets
4. **Pipelines** — Per-pipeline accuracy/error/latency charts, F1 distribution, error type breakdown
5. **Error Analysis** — Error classification breakdown, timeline, patterns, most-erroring questions
6. **Phase Tracker** — 5-phase roadmap, exit criteria checklist (live-computed), DB readiness gauges
7. **Questions Explorer** — Searchable table with full answer history, pass rate, trend
8. **Smoke Tests** — Endpoint health checks, per-pipeline status cards
9. **Workflows & Changes** — n8n versions, node diffs, DB snapshots, modification log
10. **AI Insights** — Live analysis, auto-generated recommendations, decision rules, API schema

### Data Format (v2)
`docs/data.json` contains:
- `meta{}` — status, phase, totals
- `iterations[]` — grouped test runs with per-question results
- `question_registry{}` — 200 unique questions with cross-iteration history
- `pipelines{}` — endpoints, targets, accuracy trends
- `workflow_versions{}` — current n8n workflow state (hash, nodes, models)
- `workflow_history[]` — version change log with diffs
- `quick_tests[]` — smoke test results
- `workflow_changes[]` — modifications with before/after metrics
- `db_snapshots[]` — periodic DB state snapshots
- `evaluation_phases` — phase definitions, gates, status
- `current_phase` — active phase number and iteration count

---

## Data Flow

```
                          ┌─────────────────────────────────────┐
                          │  eval/fast-iter.py (10q, parallel)  │  ← Fast iteration loop
                          │  eval/run-eval-parallel.py (200q)   │  ← Full eval
                          │  eval/run-eval.py (sequential)      │  ← Legacy/debug
                          └──────────────┬──────────────────────┘
                                         │ (4 parallel threads)
             ┌───────────┬───────────────┼───────────────┬──────────────┐
             ↓           ↓               ↓               ↓              ↓
         Standard    Graph RAG     Quantitative     Orchestrator    (concurrent)
         Pipeline    Pipeline       Pipeline         Pipeline
             │           │               │               │
             └───────────┴───────────────┴───────────────┘
                                         │
                              eval/live-writer.py (thread-safe, locked)
                                         │
                   ┌─────────────┬───────┼───────────┬──────────────┐
                   ↓             ↓       ↓           ↓              ↓
           docs/data.json  logs/exec  logs/errors  logs/pipeline-  logs/fast-iter/
           (dashboard)     (JSONL)    (per-error)  results/        (run snapshots)
                   ↓
           docs/index.html (10-tab dashboard, auto-refresh 15s)
```

---

## Error Classification
Errors are automatically classified into types for analytics:
- `TIMEOUT` — n8n execution or HTTP timeout (>25s or "timed out" in error)
- `NETWORK` — Connection failures (urlopen error, connection refused)
- `SERVER_ERROR` — HTTP 5xx responses from n8n
- `RATE_LIMIT` — HTTP 429 responses
- `EMPTY_RESPONSE` — HTTP 200 with empty body
- `ENTITY_MISS` — Graph RAG entity extraction failure
- `SQL_ERROR` — Quantitative SQL generation/execution error
- `UNKNOWN` — Unclassified errors

---

## Environment Variables Required

**Paste in Termius / Google Cloud Console at the start of each session:**
```bash
export SUPABASE_PASSWORD="udVECdcSnkMCAPiY"
export PINECONE_API_KEY="pcsk_6GzVdD_BbHsYNvpcngMqAHH5EvEa9XLnmFpEK9cx5q5xkMp72z5KFQ1q7dEjp8npWhJGBY"
export PINECONE_HOST="https://sota-rag-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
export NEO4J_PASSWORD="jV_zGdxbu-emQZM-ZSQux19pTZ5QLKejR2IHSzsbVak"
export OPENROUTER_API_KEY="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"
export N8N_API_KEY="..."              # JWT for n8n cloud API
export N8N_HOST="https://amoret.app.n8n.cloud"
```

---

## Conventions
- Workflow JSON must NOT be modified directly — use deploy scripts with patches
- All credentials via environment variables only — never commit secrets
- Dashboard updates happen automatically via `eval/live-writer.py`
- Every eval run records tested question IDs in `docs/tested-questions.json` to prevent duplicates
- Workflow improvements are proposed ONLY when eval data shows clear need
- Every eval run takes pre/post DB snapshots automatically
- Error traces are written as individual JSON files for easy inspection
- Execution logs use JSONL format (one JSON per line) for streaming analysis
- ONE change per iteration — never change multiple things at once

### Terminal Execution Rules
- **Claude Code sandbox has NO network access** — it cannot call Supabase, Neo4j, Pinecone, OpenRouter, or n8n
- **ALL API-calling scripts** must be run by the user in **Termius** (SSH to GCloud VM) or **Google Cloud Console** (browser SSH)
- **Always `git pull origin main`** before running any command on the terminal
- **Always `git push origin main`** after running commands that produce results (logs, data.json, etc.)
- Claude Code can: edit files, analyze data, write scripts, commit, push to feature branches
- Claude Code cannot: run eval, populate DBs, sync workflows, deploy patches
