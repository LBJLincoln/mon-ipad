# Multi-RAG Orchestrator — SOTA 2026

> **NEXT SESSION BOOTSTRAP** — Claude Code: read this block FIRST, then execute.
> 1. `cat STATUS.md` — current state, blockers, next action
> 2. `python3 eval/phase_gates.py` — check which phase gates are met/blocked
> 3. Identify the ONE pipeline with the worst gap to target
> 4. Fix that ONE root cause → deploy → fast-iter → check improvement
> 5. Repeat until all Phase 1 gates pass, THEN `--dataset phase-2`
> 6. Commit + push after every iteration

## Objective

Benchmark, test, and iteratively improve 4 n8n RAG workflows deployed on n8n cloud.
The system evaluates each pipeline's accuracy, latency, and cost, then proposes targeted
workflow structure improvements ONLY when data shows a clear need.

**Current phase: Phase 1 — Baseline (200q) | Phase 2 DB: COMPLETE | Phase Gates: ENFORCED**

Phase 1 (200q) → Phase 2 (1,000q) → Phase 3 (~10Kq) → Phase 4 (~100Kq) → Phase 5 (1M+q)

---

## Execution Model — Full-Agentic 2026

This project runs in **fully agentic mode**. Claude Code operates autonomously —
NO user terminal (Termius/GCloud) needed. The agent does everything directly.

### Capability Matrix (verified Feb 9, 2026)

| Capability | Access | How |
|---|---|---|
| **n8n Webhooks** (eval pipelines) | DIRECT | HTTPS to `amoret.app.n8n.cloud/webhook/*` |
| **n8n REST API** (sync/deploy workflows) | DIRECT | HTTPS to `amoret.app.n8n.cloud/api/v1/*` |
| **GitHub** (push, PR, issues) | DIRECT | `git push` + `gh` CLI |
| **OpenRouter** (LLM via n8n) | DIRECT | Proxied through n8n webhooks |
| **Pinecone** (vector stats) | DIRECT | HTTPS REST API |
| **Code, files, git, analysis** | DIRECT | Full filesystem + git access |
| **Supabase** (PostgreSQL) | BLOCKED | Proxy 403 — use n8n Quantitative pipeline for SQL |
| **Neo4j** (graph queries) | BLOCKED | Proxy 403 — use n8n Graph pipeline for queries |

**Key insight**: Supabase and Neo4j are NOT directly accessible from Claude Code
(proxy blocks those domains). But this doesn't matter for eval — all DB queries go
through n8n workflows which have full DB access. For DB population scripts, the user
must run them on a machine with direct DB access (GCloud VM).

### What Claude Code does autonomously (no user needed)

1. **Run evaluations**: `python3 eval/fast-iter.py` — calls n8n webhooks directly
2. **Deploy workflow patches**: `python3 workflows/improved/apply.py --deploy` — n8n API
3. **Sync workflows**: `python3 workflows/sync.py` — n8n API
4. **Analyze results**: read `docs/data.json`, `logs/errors/`, produce recommendations
5. **Fix n8n workflow bugs**: GET workflow → patch node → PUT back → activate
6. **Git operations**: commit, push, create PRs
7. **Check phase gates**: `python3 eval/phase_gates.py`

### What requires user action (DB population only)

1. `python3 db/populate/phase2_supabase.py` — needs psycopg2 + Supabase DNS
2. `python3 db/populate/phase2_neo4j.py` — needs Neo4j bolt protocol
3. `pip3 install psycopg2-binary` on GCloud VM (one-time)

### Team-Agentic Protocol

Multiple Claude Code agents can work concurrently on different aspects:
- **Agent A**: Workflow improvement (patch + deploy + test loop)
- **Agent B**: Evaluation runner (fast-iter, parallel eval)
- **Agent C**: Dashboard + data analysis
- **Agent D**: Database operations (population, migration)

**Coordination rules**:
1. Always `git pull` before starting work
2. Always commit + push results immediately after completion
3. Use feature branches for experiments, main for validated improvements
4. Check `STATUS.md` first — it's the coordination point between agents
5. ONE change per iteration — never modify multiple pipelines simultaneously
6. Phase gates are **enforced in code** — eval scripts block if prerequisites unmet

---

## Credentials

### Environment Variables (set at start of each session)

```bash
export SUPABASE_PASSWORD="udVECdcSnkMCAPiY"
export SUPABASE_API_KEY="sb_publishable_xUcuBcYYUO2G9Mkq_McdeQ_ocFjgonm"
export PINECONE_API_KEY="pcsk_6GzVdD_BbHsYNvpcngMqAHH5EvEa9XLnmFpEK9cx5q5xkMp72z5KFQ1q7dEjp8npWhJGBY"
export PINECONE_HOST="https://sota-rag-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
export NEO4J_PASSWORD="jV_zGdxbu-emQZM-ZSQux19pTZ5QLKejR2IHSzsbVak"
export OPENROUTER_API_KEY="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"
export N8N_API_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyMTU3NjdlMC05NThhLTRjNzQtYTY3YS1lMzM1ODA3ZWJhNjQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY5MDQ2NTExLCJleHAiOjE3NzE2Mjg0MDB9.fyOBVwb32HlzwQhSxCxoKsmMlYcxppTFGbj6S01AX2A"
export N8N_HOST="https://amoret.app.n8n.cloud"
export GITHUB_TOKEN="..."  # Set by user — GitHub PAT (not committed for push protection)
```

---

## Quick Start — Agentic Iteration Cycle

### Phase A: Fast Iteration (10q/pipeline, ~2-3 min)

```bash
# A0: Check current state
cat STATUS.md

# A1: Sync workflows from n8n
python3 workflows/sync.py

# A2: Smoke test
python3 eval/quick-test.py --questions 5

# A3: Fast iteration
python3 eval/fast-iter.py --label "description"

# A4: If bad → fix workflow → repeat
#     If good → Phase B

# A5: Commit
git add docs/ logs/ && git commit -m "fast-iter: ..." && git push
```

### Phase B: Full Evaluation (200q or 1000q)

```bash
# B1: Phase 1 full eval
python3 eval/run-eval-parallel.py --reset --label "Iter N: description"

# B2: Phase 2 eval (BLOCKED until Phase 1 gates pass — enforced by phase_gates.py)
python3 eval/run-eval-parallel.py --dataset phase-2 --reset --label "Phase 2: baseline"
# Use --force to override gate check (not recommended)

# B3: Analyze
python3 eval/analyzer.py

# B4: Commit + push
git add docs/ workflows/ logs/ && git commit -m "eval: ..." && git push
```

---

## Phase Gates — ENFORCED

Phase gates are enforced by `eval/phase_gates.py`. Eval scripts **block execution**
if the prerequisite phase gates are not met. Use `--force` to override (not recommended).

### Phase 1 — Baseline (200q) — CURRENT

| Pipeline | Current | Target | Gap | Status |
|---|---|---|---|---|
| Standard | 82.6% | >=85% | -2.4pp | CLOSE |
| Graph | 52.0% | >=70% | -18pp | ITERATING |
| Quantitative | 80.0% | >=85% | -5pp | ITERATING |
| Orchestrator | 49.6% | >=70% | -20.4pp | CRITICAL |
| **Overall** | **67.7%** | **>=75%** | **-7.3pp** | **NOT MET** |

Additional exit criteria:
- [ ] Orchestrator P95 latency <15s, error rate <5%
- [ ] 3 consecutive stable iterations (no regression)

### Phase 2 — Expand (1,000q)

**Prerequisites**: Phase 1 ALL gates passed + DB ingestion complete
- Targets: Graph >=60%, Quantitative >=70% on new HF questions
- No Phase 1 regression allowed
- **DB status**: COMPLETE (538 Supabase rows, 19,788 Neo4j nodes, 10,411 Pinecone vectors)

### Phase 3-5

See `phases/overview.md` for full gate definitions.

### Gate Check Commands

```bash
# Check current phase gate status
python3 eval/phase_gates.py

# Check specific phase
python3 eval/phase_gates.py --phase 1

# Enforce before target phase (used by eval scripts automatically)
python3 eval/phase_gates.py --enforce 2

# JSON output for programmatic use
python3 eval/phase_gates.py --phase 1 --json
```

### Gate Enforcement Rules

1. **ALL pipelines** must meet their individual targets before phase advancement
2. **Overall accuracy** must meet the phase target
3. Prerequisites are **recursive** — Phase 3 requires Phase 2, which requires Phase 1
4. Eval scripts (`fast-iter.py`, `run-eval-parallel.py`) automatically check gates when `--dataset phase-N` is specified
5. `--force` flag overrides gates but prints warnings — results flagged as unreliable

---

## n8n Workflow Sync — GitHub Integration

### Current State

| Component | Status | Details |
|---|---|---|
| **Workflow sync** (n8n → GitHub) | MANUAL | `workflows/sync.py` — run to pull latest from n8n |
| **Workflow deploy** (GitHub → n8n) | MANUAL | `workflows/improved/apply.py --deploy` |
| **Dashboard deploy** (GitHub → Pages) | AUTO | `.github/workflows/dashboard-deploy.yml` on docs/ push |
| **Error logging** (n8n → GitHub) | BROKEN | GitHub Action ready, n8n missing HTTP request node |
| **Eval pipeline** (scheduled) | AUTO | `.github/workflows/rag-eval.yml` daily 6am UTC |
| **Post-eval analysis** | AUTO | `.github/workflows/agentic-eval.yml` triggers after eval |

### Sync Commands

```bash
# Pull latest workflows from n8n (creates snapshots, updates manifest)
python3 workflows/sync.py

# Deploy patched workflows to n8n
python3 workflows/improved/apply.py --deploy

# Dry-run patches (no n8n changes)
python3 workflows/improved/apply.py

# Direct API deploy (used by deploy.py)
python3 workflows/deploy/deploy.py <workflow.json> <workflow_id>
```

### n8n API Access

```python
# Pattern for n8n API calls
import urllib.request, json
api_key = os.environ["N8N_API_KEY"]
host = "https://amoret.app.n8n.cloud"

# GET workflow
req = urllib.request.Request(f"{host}/api/v1/workflows/{wf_id}",
    headers={"X-N8N-API-KEY": api_key})

# PUT workflow (deploy) — must filter settings to ALLOWED_SETTINGS
ALLOWED_SETTINGS = {"executionOrder", "callerPolicy", "saveManualExecutions", "saveExecutionProgress"}
```

### Known Issue: Error Logging Broken

The GitHub Action `.github/workflows/n8n-error-log.yml` is ready to receive
`repository_dispatch` events, but n8n workflows have no HTTP request node
to call `POST https://api.github.com/repos/LBJLincoln/mon-ipad/dispatches`.
Error logging only works through eval scripts, not real-time from n8n.

---

## Architecture

### n8n Cloud Workflows (host: amoret.app.n8n.cloud)

| Workflow | Webhook Path | DB | Nodes | n8n Link |
|---|---|---|---|---|
| WF5 Standard RAG V3.4 | `/webhook/rag-multi-index-v3` | Pinecone | 23 | [Open](https://amoret.app.n8n.cloud/workflow/LnTqRX4LZlI009Ks-3Jnp) |
| WF2 Graph RAG V3.3 | `/webhook/ff622742-...` | Neo4j + Supabase | 26 | [Open](https://amoret.app.n8n.cloud/workflow/95x2BBAbJlLWZtWEJn6rb) |
| WF4 Quantitative V2.0 | `/webhook/3e0f8010-...` | Supabase SQL | 25 | [Open](https://amoret.app.n8n.cloud/workflow/E19NZG9WfM7FNsxr) |
| V10.1 Orchestrator | `/webhook/92217bb8-...` | Routes to above | 68 | [Open](https://amoret.app.n8n.cloud/workflow/ALd4gOEqiKL5KR1p) |

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
├── STATUS.md                          # Session entry point, agent coordination
│
├── eval/                              # Evaluation scripts
│   ├── phase_gates.py                 # PHASE GATE VALIDATOR — enforces phase transitions
│   ├── run-eval-parallel.py           # PARALLEL eval runner (~4x faster, gate-enforced)
│   ├── fast-iter.py                   # Fast iteration: 10q/pipeline, parallel, gate-enforced
│   ├── run-eval.py                    # Sequential eval runner (legacy/debug)
│   ├── live-writer.py                 # Writes results to docs/data.json + logs/ (thread-safe)
│   ├── quick-test.py                  # Smoke tests (5q/pipeline)
│   ├── analyzer.py                    # Post-eval analysis + recommendations
│   └── iterate.sh                     # Run eval + auto-commit + push
│
├── datasets/                          # Question datasets by phase
│   ├── manifest.json                  # 16 HF datasets metadata + ingestion status
│   ├── phase-1/
│   │   ├── graph-quant-50x2.json      # 100q: 50 graph + 50 quantitative
│   │   └── standard-orch-50x2.json    # 100q: 50 standard + 50 orchestrator
│   └── phase-2/
│       └── hf-1000.json               # 1,000q: HuggingFace datasets
│
├── workflows/                         # n8n workflow management
│   ├── manifest.json                  # Version tracking (hashes, diffs)
│   ├── sync.py                        # Pull workflows from n8n cloud → snapshots
│   ├── deploy/
│   │   └── deploy.py                  # Deploy workflow JSON to n8n via API
│   ├── source/                        # Source workflow JSONs (synced from n8n)
│   ├── improved/                      # Patched versions (apply.py output)
│   │   └── apply.py                   # 30+ patches: orchestrator, graph, quant, standard
│   ├── snapshots/                     # Timestamped workflow snapshots
│   └── helpers/                       # Benchmark helper workflows for n8n
│
├── db/                                # Database schemas & population
│   ├── migrations/                    # SQL migration files
│   ├── populate/                      # DB population scripts
│   │   ├── phase2_neo4j.py            # Neo4j entity extraction (Phase 2)
│   │   ├── phase2_supabase.py         # Supabase table population (Phase 2)
│   │   └── ...
│   └── readiness/                     # DB readiness checks per phase
│
├── phases/
│   └── overview.md                    # Full 5-phase strategy + exit criteria
│
├── docs/                              # GitHub Pages dashboard
│   ├── index.html                     # Interactive dashboard (7 tabs)
│   ├── data.json                      # Live evaluation data (v2 format)
│   └── tested-questions.json          # Dedup manifest
│
├── logs/                              # Structured execution traces
│   ├── executions/                    # Per-session JSONL logs
│   ├── errors/                        # Individual error trace files
│   ├── db-snapshots/                  # Periodic DB state snapshots
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

## LLM Model Registry

**All LLM models are FREE via OpenRouter** (migrated Feb 9, 2026).

| Workflow | Node | Model | Provider | Cost |
|---|---|---|---|---|
| Standard | HyDE Generator | meta-llama/llama-3.3-70b-instruct:free | OpenRouter | FREE |
| Standard | LLM Generation | meta-llama/llama-3.3-70b-instruct:free | OpenRouter | FREE |
| Standard | Cohere Rerank | rerank-v3.5 | Cohere | $0.002/1K |
| Standard | Pinecone Query | text-embedding-3-small | OpenAI | $0.02/1K |
| Graph | HyDE Entity Extraction | meta-llama/llama-3.3-70b-instruct:free | OpenRouter | FREE |
| Graph | Answer Synthesis | meta-llama/llama-3.3-70b-instruct:free | OpenRouter | FREE |
| Quantitative | Text-to-SQL | meta-llama/llama-3.3-70b-instruct:free | OpenRouter | FREE |
| Quantitative | SQL Validator | meta-llama/llama-3.3-70b-instruct:free | OpenRouter | FREE |
| Orchestrator | Intent Analyzer | meta-llama/llama-3.3-70b-instruct:free | OpenRouter | FREE |
| Orchestrator | Task Planner | meta-llama/llama-3.3-70b-instruct:free | OpenRouter | FREE |
| Orchestrator | Response Builder | meta-llama/llama-3.3-70b-instruct:free | OpenRouter | FREE |

Rate limits: 20 req/min, 1000 req/day (with $10+ credit purchase), 50 req/day (without)

---

## Data Flow

```
eval/fast-iter.py (10q)  ─┐
eval/run-eval-parallel.py ─┤── phase_gates.py check ──► 4 parallel threads
eval/run-eval.py (legacy) ─┘
          │
          ├── Standard Pipeline (n8n webhook)
          ├── Graph RAG Pipeline (n8n webhook)
          ├── Quantitative Pipeline (n8n webhook)
          └── Orchestrator Pipeline (n8n webhook)
                    │
          eval/live-writer.py (thread-safe)
                    │
          ┌────────┼────────────────────────────┐
          ↓        ↓                            ↓
    docs/data.json  logs/executions/   logs/pipeline-results/
          ↓
    docs/index.html (7-tab dashboard, auto-refresh 15s)
          ↓
    .github/workflows/dashboard-deploy.yml → GitHub Pages
```

---

## Session Start Protocol

Every new session MUST follow this sequence:

1. **Read** `STATUS.md` — current state, next steps, blockers
2. **Read** `CLAUDE.md` — architecture, credentials, commands
3. **Check** phase gates: `python3 eval/phase_gates.py`
4. **Check** `docs/data.json` — latest metrics
5. **Identify** the ONE next action
6. **Execute** → test → commit → push

### AI Decision Rules

1. **Phase gates are enforced** — never skip to next phase until ALL pipelines pass
2. If accuracy < target: analyze error traces, fix ONE root cause, re-test
3. If error rate > 10%: prioritize error fixes over accuracy improvements
4. If 3+ regressions: REVERT last change immediately
5. If orchestrator timeout > 60s: reduce sub-pipeline invocations
6. If graph entity miss: check entity catalog, add fuzzy matching
7. If SQL errors > 5: review Schema Context hints, add ILIKE
8. If empty responses > 10: check continueOnFail, add null-safe guards
9. ONE fix per iteration — never change multiple things at once
10. After Phase 1 gates pass: `--dataset phase-2 --reset`

---

## Conventions

- Workflow JSON must NOT be modified directly — use deploy scripts with patches
- All credentials via environment variables only — never commit secrets
- Dashboard updates happen automatically via `eval/live-writer.py`
- Every eval run records tested question IDs in `docs/tested-questions.json`
- Error traces are written as individual JSON files for easy inspection
- ONE change per iteration — never change multiple things at once
- Phase gates are checked automatically by eval scripts for Phase 2+ datasets
- Always commit and push after eval runs to keep team agents in sync
