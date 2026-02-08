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

## Quick Start — Iteration Cycle Protocol

This is the rapid iteration loop used throughout Phase 1 (and future phases).
Every session should follow this cycle:

### Step 0: Read current state
```bash
# Check current metrics (always start here)
cat docs/data.json | python -m json.tool | head -20
cat STATUS.md
```

### Step 1: Sync workflows from n8n
```bash
python workflows/sync.py
```
Pulls latest workflow JSON from n8n cloud, stores snapshots in `workflows/snapshots/`,
computes diffs, updates `workflows/manifest.json`.

### Step 2: Smoke test (validate endpoints are alive)
```bash
python eval/quick-test.py --questions 5
```
Tests 5 known-good questions per pipeline. If any fail → investigate before proceeding.
Results written to `docs/data.json` under `quick_tests[]`.

### Step 3: Analyze failures (decide what to fix)
```bash
python eval/analyzer.py
```
Reads `docs/data.json`, identifies regressions, error patterns, gap-to-target per pipeline.
Outputs prioritized recommendations.

### Step 4: Apply workflow patch in n8n
Modify the workflow directly in n8n cloud UI, then:
```bash
python workflows/sync.py  # capture the change
python eval/quick-test.py  # verify no regression
```

### Step 5: Run evaluation
```bash
python eval/run-eval.py \
  --types standard,graph,quantitative,orchestrator \
  --label "Description of what changed" \
  --description "Detailed change notes" \
  --reset  # re-test all questions (omit to skip already-tested)
```
Results feed `docs/data.json` live. Dashboard auto-refreshes.

### Step 6: Commit + push
```bash
git add docs/ workflows/ logs/
git commit -m "eval: iteration N — description"
git push
```

### Step 7: Repeat from Step 3

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

## Iteration Results (200q, Feb 8 2026 — 4 iterations)

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
│   ├── run-eval.py                    # Main eval runner (feeds dashboard live)
│   ├── live-writer.py                 # Writes results to docs/data.json + logs/
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
│   ├── populate/
│   │   ├── all.py                     # Master DB population script
│   │   ├── neo4j.py                   # Neo4j entity graph builder
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
│   └── db-snapshots/                  # Periodic DB state snapshots (15 files)
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
n8n Workflow → HTTP Response → eval/run-eval.py
                                   ↓
                              eval/live-writer.py
                                   ↓ (parallel writes)
                   ┌───────────────┼──────────────┐
                   ↓               ↓              ↓
           docs/data.json   logs/executions/  logs/errors/
           (dashboard)      (JSONL traces)    (error files)
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
```bash
export SUPABASE_PASSWORD="..."        # Supabase PostgreSQL
export PINECONE_API_KEY="..."         # Pinecone vector DB
export PINECONE_HOST="https://sota-rag-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
export NEO4J_PASSWORD="..."           # Neo4j Aura graph DB
export OPENROUTER_API_KEY="..."       # LLM API (for embeddings + eval)
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
