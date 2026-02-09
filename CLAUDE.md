# Multi-RAG Orchestrator — SOTA 2026

## Objective

Benchmark, test, and iteratively improve 4 n8n RAG workflows deployed on n8n cloud.
The system evaluates each pipeline's accuracy, latency, and cost, then proposes targeted
workflow structure improvements ONLY when data shows a clear need (e.g. accuracy plateau,
high error rate, routing failures).

**Current phase: Phase 1 — Baseline (200q, iterative improvement loop) | Phase 2 DB: COMPLETE**

See `phases/overview.md` for the full 5-phase strategy:
Phase 1 (200q) → Phase 2 (1,000q) → Phase 3 (~10Kq) → Phase 4 (~100Kq) → Phase 5 (1M+q)

---

## Execution Environment

**Claude Code HAS network access** via HTTP proxy. Most API-calling scripts can run
directly from Claude Code. Only `psql` (direct TCP to Supabase) and scripts requiring
`N8N_API_KEY` need user intervention.

### What Claude Code can run directly

| Script | Status | Notes |
|---|---|---|
| `eval/quick-test.py` | ✅ Run directly | n8n webhooks via HTTPS |
| `eval/fast-iter.py` | ✅ Run directly | Parallel eval, all pipelines |
| `eval/run-eval-parallel.py` | ✅ Run directly | Full eval (200q or 1000q) |
| `eval/run-eval.py` | ✅ Run directly | Sequential eval |
| `eval/analyzer.py` | ✅ Run directly | Local file analysis |
| `eval/live-writer.py --snapshot-db` | ⚠️ Partial | Pinecone + Neo4j OK, Supabase psql fails |
| `workflows/improved/apply.py --local` | ✅ Run directly | Local JSON patches |
| `workflows/improved/apply.py --deploy` | ❌ Needs N8N_API_KEY | User must provide |
| `workflows/sync.py` | ❌ Needs N8N_API_KEY | User must provide |
| `db/populate/phase2_neo4j.py` | ✅ Run directly | Uses Neo4j HTTP API |
| `db/populate/phase2_supabase.py` | ❌ Needs psql | DNS blocked for TCP |
| `db/populate/neo4j.py` | ✅ Run directly | Uses Neo4j HTTP API |

### What requires user action

| Action | Why | Where |
|---|---|---|
| Provide `N8N_API_KEY` | JWT for n8n cloud API, not committed | User provides at session start |
| Update n8n credentials | If OpenRouter key expires in n8n | n8n cloud dashboard |
| Run Supabase psql scripts | Direct TCP DNS blocked by proxy | Termius or GCloud Console |

### Environment variables

Claude Code sets these automatically before running scripts. If running manually:

```bash
export SUPABASE_PASSWORD="udVECdcSnkMCAPiY"
export PINECONE_API_KEY="pcsk_6GzVdD_BbHsYNvpcngMqAHH5EvEa9XLnmFpEK9cx5q5xkMp72z5KFQ1q7dEjp8npWhJGBY"
export PINECONE_HOST="https://sota-rag-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
export NEO4J_PASSWORD="jV_zGdxbu-emQZM-ZSQux19pTZ5QLKejR2IHSzsbVak"
export OPENROUTER_API_KEY="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"
export N8N_API_KEY="..."              # User must provide — not committed
export N8N_HOST="https://amoret.app.n8n.cloud"
```

### Fallback: Google Cloud free tier VM (for psql-dependent scripts only)

```bash
sudo apt-get update && sudo apt-get install -y python3 python3-psycopg2 python3-requests git
git clone https://github.com/LBJLincoln/mon-ipad.git ~/mon-ipad
cd ~/mon-ipad
```

---

## Quick Start — Two-Phase Iteration Cycle

The iteration loop has two phases: **fast iteration** (10q, rapid workflow tuning)
and **full evaluation** (200q or 1000q, parallel). Claude Code runs all of these directly.

### Phase A: Fast Iteration Loop (10q per pipeline, ~2-3 min)

Claude Code runs the full iteration loop:

```
A0: Read STATUS.md
A1: Sync workflows      → python3 workflows/sync.py
A2: Smoke test           → python3 eval/quick-test.py --questions 5
A3: Fast iteration test  → python3 eval/fast-iter.py --label "description"
A4: Review results       → check logs/fast-iter/ and logs/pipeline-results/
A5: If bad → fix workflow → repeat from A1
    If good → proceed to Phase B
A6: Commit results       → git add docs/ logs/ && git commit && git push
```

**Commands:**
```bash
python3 eval/fast-iter.py                                 # 10q per pipeline, all 4
python3 eval/fast-iter.py --questions 5 --pipelines graph # 5q, graph only
python3 eval/fast-iter.py --only-failing                  # Re-test only failures
python3 eval/fast-iter.py --label "after fuzzy matching"  # Tag the run
python3 eval/fast-iter.py --dataset phase-2               # Phase 2 questions (graph + quant)
```

### Phase B: Full Evaluation (200q or 1000q, parallel)

Run only AFTER fast-iter shows the workflow is ready.

```bash
# Phase 1: 200q, all 4 pipelines
python3 eval/run-eval-parallel.py --reset --label "Iter N: description"

# Phase 2: 1000q, graph + quantitative only (auto-adjusted)
python3 eval/run-eval-parallel.py --dataset phase-2 --reset --label "Phase 2: baseline"

# Combined: 1200q, all pipelines
python3 eval/run-eval-parallel.py --dataset all --reset --label "Phase 1+2: combined"

# Analyze results
python3 eval/analyzer.py

# Commit + push
git add docs/ workflows/ logs/ && git commit -m "eval: Iter N" && git push
```

### Legacy: Sequential Evaluation

For debugging or isolating a single pipeline:
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
- **DB setup status**: COMPLETE (538 total Supabase rows, 19,788 Neo4j nodes, 10,411 Pinecone vectors)

**Phase 2 DB ingestion:**
```bash
# Neo4j (runs directly from Claude Code — uses HTTP API)
python3 db/populate/phase2_neo4j.py --reset
python3 db/populate/phase2_neo4j.py --reset --llm    # LLM extraction (higher quality)

# Supabase (requires psql — run in Termius if DNS blocked)
python3 db/populate/phase2_supabase.py --reset
```

**Flags disponibles:**
- `--reset` : supprime les données existantes avant de repeupler (RECOMMANDE)
- `--dry-run` : parse sans écrire en base
- `--dataset finqa` : un seul dataset (supabase uniquement)
- `--limit 50` : premières N questions (neo4j uniquement)
- `--llm` : extraction LLM au lieu d'heuristique (neo4j uniquement)

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
1. **Free model rate limits**: 50 req/day without credits, 1000 req/day with $10+ purchase — may bottleneck full evals
2. **Orchestrator timeouts**: Sub-workflow chaining exceeds 60s for complex queries
3. **Graph RAG entity extraction**: Many entities still not found in Neo4j
4. **Quantitative edge cases**: Employee count queries return 0, product queries fail
5. **Model quality delta**: Llama 3.3 70B may perform differently than Gemini Flash — monitor after deploy

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
| DB | Content | Phase 1 | Phase 2 |
|---|---|---|---|
| **Pinecone** | Vector embeddings (text-embedding-3-small, 1536-dim) | 10,411 vectors, 12 namespaces | No changes needed |
| **Neo4j** | Entity graph (Person, Org, Tech, City, Museum, Disease) | 110 nodes, 151 relationships | +4,884 entities, 21,625 total relationships |
| **Supabase** | Financial tables + benchmark_datasets + HF tables | 88 rows, 5 tables | +450 rows (finqa/tatqa/convfinqa), 538 total |

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
│   │   └── deploy.py                  # Deploy workflow JSON to n8n via API
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
│   ├── index.html                     # Interactive dashboard (7 tabs)
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

## Dashboard (docs/index.html — 7 tabs)

The dashboard is the central monitoring and analysis tool. It reads `docs/data.json`
and auto-refreshes every 15 seconds. Each tab serves a distinct operational purpose.

### Tabs
1. **Executive Summary** — Phase roadmap, key metrics, pipeline gauges vs targets, accuracy trend chart, error distribution, blockers, next actions
2. **Focus** — Current step detail: incremental testing progress, Phase 1 exit criteria checklist, Phase 2 readiness, per-pipeline iteration cards, what's working / what's failing
3. **Questions** — Filterable table (phase/pipeline/status/dataset/search), expandable detail with full run history per question
4. **Workflows** — n8n-linked workflow cards (open in n8n), node-level breakdown with LLM model details, modification history, DB state chart
5. **Databases** — DB status cards (Pinecone/Neo4j/Supabase), Phase Readiness Matrix (5 phases × 3 DBs), data growth projection, missing data for next phase
6. **Costs & Models** — LLM model registry per n8n node (model/provider/cost/role/tokens), cost stats, phase cost projection, per-pipeline cost chart
7. **AI Agent** — Environment variables (copy button), iteration protocol, command reference (9 commands with flags), 10 decision rules, data.json schema

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
           docs/index.html (7-tab dashboard, auto-refresh 15s)
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

Claude Code sets these automatically before running scripts. User must provide `N8N_API_KEY`
at session start (not committed to repo).

```bash
export SUPABASE_PASSWORD="udVECdcSnkMCAPiY"
export PINECONE_API_KEY="pcsk_6GzVdD_BbHsYNvpcngMqAHH5EvEa9XLnmFpEK9cx5q5xkMp72z5KFQ1q7dEjp8npWhJGBY"
export PINECONE_HOST="https://sota-rag-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
export NEO4J_PASSWORD="jV_zGdxbu-emQZM-ZSQux19pTZ5QLKejR2IHSzsbVak"
export OPENROUTER_API_KEY="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"
export N8N_API_KEY="..."              # User provides — JWT for n8n cloud API
export N8N_HOST="https://amoret.app.n8n.cloud"
```

---

## Incremental Testing Protocol

The core philosophy is progressive validation. Never skip levels.

```
Endpoint health → 5q/pipeline → 10q (fast-iter) → 50q → 200q (full Phase 1) → 1000q (Phase 2)
```

Each level must PASS before scaling up. At each level:
1. Run test at current scale
2. Analyze errors and regressions
3. Fix ONE root cause
4. Re-test at same scale until pass
5. Scale up to next level

### Scaling Commands
| Level | Command | When to use |
|---|---|---|
| Health check | `python3 eval/quick-test.py --questions 1` | After any workflow deploy |
| 5q/pipeline | `python3 eval/quick-test.py --questions 5` | Smoke test after changes |
| 10q/pipeline | `python3 eval/fast-iter.py --label "desc"` | Standard fast iteration |
| 50q subset | `python3 eval/run-eval-parallel.py --max 50` | Pre-full-eval validation |
| 200q full P1 | `python3 eval/run-eval-parallel.py --reset --label "desc"` | Phase 1 gate check |
| 1000q Phase 2 | `python3 eval/run-eval-parallel.py --dataset phase-2 --reset` | Phase 2 gate check |

---

## LLM Model Registry

**All LLM models are FREE via OpenRouter** (migrated Feb 9, 2026). Embeddings use OpenAI, reranking uses Cohere.

| Workflow | Node | Model | Provider | Cost | Role |
|---|---|---|---|---|---|
| Standard | HyDE Generator | meta-llama/llama-3.3-70b-instruct:free | OpenRouter | FREE | Hypothetical doc generation |
| Standard | LLM Generation | meta-llama/llama-3.3-70b-instruct:free | OpenRouter | FREE | Answer synthesis |
| Standard | Cohere Rerank | rerank-v3.5 | Cohere | $0.002/1K | Re-rank passages |
| Standard | Pinecone Query | text-embedding-3-small | OpenAI | $0.02/1K | Vector embedding |
| Graph | HyDE Entity Extraction | meta-llama/llama-3.3-70b-instruct:free | OpenRouter | FREE | Extract entities |
| Graph | Answer Synthesis | meta-llama/llama-3.3-70b-instruct:free | OpenRouter | FREE | Generate from graph |
| Graph | Cohere Rerank | rerank-multilingual-v3.0 | Cohere | $0.002/1K | Re-rank passages |
| Quantitative | Text-to-SQL | meta-llama/llama-3.3-70b-instruct:free | OpenRouter | FREE | NL to SQL |
| Quantitative | SQL Validator | meta-llama/llama-3.3-70b-instruct:free | OpenRouter | FREE | Validate/fix SQL |
| Quantitative | Interpretation | meta-llama/llama-3.3-70b-instruct:free | OpenRouter | FREE | Interpret results |
| Orchestrator | Intent Analyzer | meta-llama/llama-3.3-70b-instruct:free | OpenRouter | FREE | Route to pipeline |
| Orchestrator | Task Planner | meta-llama/llama-3.3-70b-instruct:free | OpenRouter | FREE | Plan sub-tasks |
| Orchestrator | Response Builder | meta-llama/llama-3.3-70b-instruct:free | OpenRouter | FREE | Merge results |
| DB Population | Entity Extraction | meta-llama/llama-3.3-70b-instruct:free | OpenRouter | FREE | Neo4j entity extraction |

### Free Model Details
- **meta-llama/llama-3.3-70b-instruct:free** — 70B params, 131K context, GPT-4 level quality
- Rate limits: 20 req/min, 1000 req/day (with $10+ credit purchase), 50 req/day (without)
- Fallback models if needed: `google/gemma-3-27b-it:free`, `deepseek/deepseek-chat-v3-0324:free`

### Cost Projections (with free models)
| Phase | LLM | Embeddings | Reranking | Total |
|---|---|---|---|---|
| Phase 1 (200q) | $0.00 | $0.00 | $0.00 | **$0.00** |
| Phase 2 (1Kq) | $0.00 | $0.02 | $0.01 | **$0.03** |
| Phase 3 (10Kq) | $0.00 | $0.20 | $0.10 | **$0.30** |
| Phase 4 (100Kq) | $0.00 | $2.00 | $1.00 | **$3.00** |
| Phase 5 (1M+) | $0.00 | $20.00 | $10.00 | **$30.00** |

---

## HuggingFace Datasets (16 total)

Source datasets used across all phases. See `datasets/manifest.json` for full metadata.

| Dataset | Type | Phase | Questions | Status |
|---|---|---|---|---|
| Custom Phase 1 questions | standard/graph/quant/orch | 1 | 200 | ACTIVE |
| FinQA | quantitative | 2 | 200 | INGESTED |
| TAT-QA | quantitative | 2 | 150 | INGESTED |
| ConvFinQA | quantitative | 2 | 100 | INGESTED |
| MuSiQue | graph (multi-hop) | 2 | 250 | INGESTED |
| 2WikiMultiHopQA | graph (multi-hop) | 2 | 250 | INGESTED |
| FRAMES | standard | 3+ | ~8K | PLANNED |
| HotpotQA | graph | 3+ | ~1K | PLANNED |
| WikiTableQuestions | quantitative | 3+ | ~1K | PLANNED |
| SQA (Sequential QA) | quantitative | 4+ | TBD | PLANNED |
| HybridQA | orchestrator | 4+ | TBD | PLANNED |
| OTT-QA | orchestrator | 4+ | TBD | PLANNED |
| MultiModalQA | orchestrator | 5 | TBD | PLANNED |
| FEVEROUS | graph | 5 | TBD | PLANNED |
| TabFact | quantitative | 5 | TBD | PLANNED |
| InfoTabs | quantitative | 5 | TBD | PLANNED |

---

## n8n Workflow IDs (for deep linking)

| Pipeline | n8n Workflow ID | Link |
|---|---|---|
| Standard RAG | `LnTqRX4LZlI009Ks-3Jnp` | `https://amoret.app.n8n.cloud/workflow/LnTqRX4LZlI009Ks-3Jnp` |
| Graph RAG | `95x2BBAbJlLWZtWEJn6rb` | `https://amoret.app.n8n.cloud/workflow/95x2BBAbJlLWZtWEJn6rb` |
| Quantitative RAG | `LjUz8fxQZ03G9IsU` | `https://amoret.app.n8n.cloud/workflow/LjUz8fxQZ03G9IsU` |
| Orchestrator | `FZxkpldDbgV8AD_cg7IWG` | `https://amoret.app.n8n.cloud/workflow/FZxkpldDbgV8AD_cg7IWG` |

---

## Session Start Protocol

Every new session MUST follow this sequence autonomously:

1. **Read** `STATUS.md` — current state, next steps, blockers
2. **Read** `CLAUDE.md` — architecture, conventions, commands
3. **Check** `docs/data.json` — latest metrics (meta, iterations, pipelines)
4. **Check** `db/readiness/phase-N.json` — current phase gate status
5. **Identify** next action based on decision rules below
6. **Execute** ONE change per iteration, test, commit, push
7. **Update** `STATUS.md` with new state after each iteration

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

### Execution Capabilities
- **Claude Code HAS network access** via HTTP proxy (Pinecone, Neo4j, n8n webhooks, OpenRouter)
- **Direct TCP is blocked** (psql for Supabase fails on DNS resolution)
- Claude Code can: run evals, sync/deploy workflows, populate Neo4j, analyze, commit, push
- Claude Code cannot: run psql commands (use Termius for Supabase population scripts)
- User provides: `N8N_API_KEY` (session start), new OpenRouter key (if expired)

---

## n8n <-> GitHub Integration Status

Bidirectional connectivity between n8n Cloud and GitHub for error logging, dashboard
updates, workflow sync, and automated evaluation.

### Working Flows

| Flow | Direction | Mechanism | Status |
|---|---|---|---|
| Eval results -> Dashboard | GitHub -> Pages | `live-writer.py` -> `data.json` -> `dashboard-deploy.yml` | WORKING |
| Workflow sync | n8n -> Git | `sync.py` pulls via n8n API, saves snapshots + manifest | WORKING |
| Workflow deploy | Git -> n8n | `deploy.py` pushes via n8n API PUT | WORKING |
| Post-eval analysis | GitHub Actions | `agentic-eval.yml` -> `analyzer.py` -> creates issues | WORKING |
| Scheduled eval | GitHub Actions | `rag-eval.yml` daily cron -> auto-commit results | WORKING |
| Dashboard auto-deploy | GitHub Actions | `dashboard-deploy.yml` on `docs/` push -> GitHub Pages | WORKING |

### Partially Working

| Flow | Issue | Fix Needed |
|---|---|---|
| n8n error logging | GitHub Error Logger Code nodes exist in all 4 workflows but **no HTTP Request node** to send to GitHub API | Add HTTP Request node after each logger -> `POST /repos/.../dispatches` |
| Error reception | `n8n-error-log.yml` ready to receive `repository_dispatch` events | Blocked by missing sender (above) |
| n8n credential update | Updated via API PATCH (credential ID: `aTHBqnntMBApo0Dy`) | Working when N8N_API_KEY provided |

### Key Integration Points

- **OpenRouter credential** `aTHBqnntMBApo0Dy` — shared across all 15 LLM nodes in 4 workflows
- **Workflow IDs**: Standard `LnTqRX4LZlI009Ks-3Jnp`, Graph `95x2BBAbJlLWZtWEJn6rb`, Quant `LjUz8fxQZ03G9IsU`, Orch `FZxkpldDbgV8AD_cg7IWG`
- **Dashboard**: auto-refreshes every 15s from `docs/data.json` on GitHub Pages

---

## Phase Gate Enforcement

Phase gates are **enforced in code**. All eval scripts (`run-eval-parallel.py`,
`fast-iter.py`, `run-eval.py`) and GitHub Actions workflows check `db/readiness/phase-1.json`
before allowing `--dataset phase-2` or higher.

### How it works

1. When `--dataset phase-2` (or `all`) is requested, the script reads `db/readiness/phase-1.json`
2. It checks `gate_criteria` — every pipeline must have `"met": true`
3. If any pipeline is below target, the script **exits with error** and prints which gates failed
4. Use `--force-phase` to override for testing/debugging only

### Where gates are enforced

| Location | Mechanism |
|---|---|
| `eval/run-eval-parallel.py` | `check_phase_gate()` before `load_questions()` |
| `eval/fast-iter.py` | `check_phase_gate()` before `load_questions()` |
| `eval/run-eval.py` | Inline gate check before `load_questions()` |
| `.github/workflows/rag-eval.yml` | Python gate check step before eval step |
| `.github/workflows/agentic-eval.yml` | Python gate check step before full-eval step |

### Updating gates after evaluation

After a full 200q eval, update `db/readiness/phase-1.json` gate_criteria with new accuracy
values and set `"met": true/false` accordingly. This is the source of truth for phase progression.

---

## Team-Agentic Mode (2026)

This project operates in **full agentic mode**. Claude Code is the primary executor.
The human operator provides credentials, approves deployments, and reviews results.

### Operating Principles

1. **Zero-command user experience**: Claude Code runs ALL evaluation, analysis, workflow
   patching, Neo4j population, and Git operations. The user never needs to run commands.

2. **Autonomous iteration loop**: Claude Code follows the A0-A6 cycle autonomously:
   - Read STATUS.md -> Sync workflows -> Smoke test -> Fast-iter -> Analyze -> Fix -> Commit

3. **Self-correcting**: If an eval shows regressions, Claude Code reverts and re-tests.
   If a workflow deploy fails, it diagnoses and retries. If credentials expire, it asks
   the user for new ones.

4. **Progressive validation**: Never skip test levels. Each fix is validated at the same
   scale before scaling up. Phase gates prevent premature progression.

5. **Transparent**: All actions are logged to `docs/data.json`, `logs/`, and Git history.
   The dashboard at GitHub Pages shows real-time progress.

### What Claude Code handles autonomously

| Action | How |
|---|---|
| Run evaluations | `eval/fast-iter.py`, `eval/run-eval-parallel.py` directly |
| Analyze results | `eval/analyzer.py` + manual error trace analysis |
| Patch workflows | `workflows/improved/apply.py` -> deploy via n8n API |
| Update credentials | n8n API PATCH on credential objects |
| Populate Neo4j | `db/populate/phase2_neo4j.py` via HTTP API |
| Snapshot databases | `eval/live-writer.py --snapshot-db` (Pinecone + Neo4j) |
| Update dashboard | Writes to `docs/data.json` -> auto-deployed via GitHub Pages |
| Commit & push | Git operations on feature branches |
| Create PRs | `gh pr create` via GitHub CLI |

### What requires human

| Action | Why |
|---|---|
| Provide `N8N_API_KEY` | JWT for n8n cloud, not committed, expires |
| Provide new OpenRouter key | If credit-based key expires |
| Run Supabase psql | TCP port 6543 blocked by sandbox firewall |
| Review & merge PRs | Human approval for main branch changes |
| Purchase OpenRouter credits | If free tier rate limits block evals |

### Agent Decision Rules (expanded)

1. If accuracy < target: analyze error traces, fix ONE root cause, re-test
2. If error rate > 10%: prioritize error fixes over accuracy improvement
3. If 3+ regressions: REVERT last change immediately
4. If orchestrator timeout > 60s: reduce sub-pipeline invocations
5. If graph entity miss: check entity catalog, add fuzzy matching
6. If SQL errors > 5: review Schema Context hints, add ILIKE
7. If empty responses > 10: check continueOnFail, add null-safe guards
8. ONE fix per iteration — never change multiple things at once
9. Run eval directly from Claude Code (has network access via HTTP proxy)
10. Phase gates enforced: `--dataset phase-2` blocked until Phase 1 gates pass
11. After eval: update `db/readiness/phase-N.json` with new metrics
12. If credential expires: ask user, update via API, verify with smoke test
13. If n8n deploy fails: check ALLOWED_SETTINGS filter, retry with clean payload
14. Commit after every successful iteration — never batch multiple iterations
