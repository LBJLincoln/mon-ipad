# Architecture Reference — Multi-RAG Orchestrator SOTA 2026

> Detailed reference for the project. For quick session start, use `docs/status.json`.

---

## n8n Cloud Workflows (host: amoret.app.n8n.cloud)

| Workflow | Webhook Path | DB | Nodes | n8n Link |
|---|---|---|---|---|
| WF5 Standard RAG V3.4 | `/webhook/rag-multi-index-v3` | Pinecone | 23 | [Open](https://amoret.app.n8n.cloud/workflow/LnTqRX4LZlI009Ks-3Jnp) |
| WF2 Graph RAG V3.3 | `/webhook/ff622742-...` | Neo4j + Supabase | 26 | [Open](https://amoret.app.n8n.cloud/workflow/95x2BBAbJlLWZtWEJn6rb) |
| WF4 Quantitative V2.0 | `/webhook/3e0f8010-...` | Supabase SQL | 25 | [Open](https://amoret.app.n8n.cloud/workflow/LjUz8fxQZ03G9IsU) |
| V10.1 Orchestrator | `/webhook/92217bb8-...` | Routes to above | 68 | [Open](https://amoret.app.n8n.cloud/workflow/FZxkpldDbgV8AD_cg7IWG) |

---

## Databases

| DB | Content | Phase 1 | Phase 2 |
|---|---|---|---|
| **Pinecone** | Vector embeddings (configurable via `setup_embeddings.py`) | 10,411 vectors, 12 namespaces | Embedding model configurable via n8n `$vars` |
| **Neo4j** | Entity graph (Person, Org, Tech, City, Museum, Disease) | 110 nodes, 151 relationships | +4,884 entities, 21,625 total relationships |
| **Supabase** | Financial tables + benchmark_datasets + HF tables | 88 rows, 5 tables | +450 rows (finqa/tatqa/convfinqa), 538 total |

---

## LLM Model Registry

All LLM models FREE via OpenRouter (`arcee-ai/trinity-large-preview:free`).
Rate limits: 20 req/min, 1000 req/day (with $10+ credit), 50 req/day (without).

| Workflow | Node | Model |
|---|---|---|
| Standard | HyDE Generator | arcee-ai/trinity-large-preview:free |
| Standard | LLM Generation | arcee-ai/trinity-large-preview:free |
| Standard | Cohere Rerank | rerank-multilingual-v3.0 ($0.002/1K) |
| Standard | Pinecone Query | n8n `$vars.EMBEDDING_MODEL` (configurable) |
| Graph | HyDE Entity Extraction | arcee-ai/trinity-large-preview:free |
| Graph | Answer Synthesis | arcee-ai/trinity-large-preview:free |
| Quantitative | Text-to-SQL | arcee-ai/trinity-large-preview:free |
| Quantitative | SQL Validator | arcee-ai/trinity-large-preview:free |
| Orchestrator | Intent Analyzer | arcee-ai/trinity-large-preview:free |
| Orchestrator | Task Planner | arcee-ai/trinity-large-preview:free |
| Orchestrator | Response Builder | arcee-ai/trinity-large-preview:free |

### Free Alternatives (if needed)
| Model | Params | Context | Best For |
|---|---|---|---|
| `google/gemma-3-27b-it:free` | 27B | 131K | Faster, lighter |
| `deepseek/deepseek-chat-v3-0324:free` | 671B MoE | 164K | Strong SQL |
| `qwen/qwen3-coder:free` | 480B MoE | 262K | SQL specialist |
| `meta-llama/llama-4-maverick:free` | Large MoE | 131K | Newest Llama |
| `deepseek/deepseek-r1:free` | 671B MoE | 164K | Reasoning |

---

## Capability Matrix (from Claude Code)

| Capability | Access | How |
|---|---|---|
| **n8n Webhooks** (eval pipelines) | DIRECT | HTTPS to `amoret.app.n8n.cloud/webhook/*` |
| **n8n REST API** (sync/deploy workflows) | DIRECT | HTTPS to `amoret.app.n8n.cloud/api/v1/*` |
| **GitHub** (push, PR, issues) | DIRECT | `git push` + `gh` CLI |
| **OpenRouter** (LLM via n8n) | DIRECT | Proxied through n8n webhooks |
| **Pinecone** (vector stats) | DIRECT | HTTPS REST API |
| **Code, files, git, analysis** | DIRECT | Full filesystem + git access |
| **Supabase** (PostgreSQL) | BLOCKED | Proxy 403 — use n8n Quantitative pipeline |
| **Neo4j** (graph queries) | BLOCKED | Proxy 403 — use n8n Graph pipeline |

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
          ↓                                     ↓
    eval/generate_status.py           logs/fast-iter/
          ↓
    docs/status.json (compact, <3KB)
          ↓
    docs/index.html (7-tab dashboard)
          ↓
    GitHub Pages (auto-deploy)
```

---

## Repository Structure

```
mon-ipad/
├── CLAUDE.md                          # Session bootstrap (<120 lines)
├── STATUS.md                          # Human-readable status
│
├── eval/                              # Evaluation scripts
│   ├── generate_status.py             # STATUS GENERATOR — docs/status.json from data.json
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
│   ├── manifest.json                  # 16 HF datasets metadata
│   ├── phase-1/                       # 200q: 50 per pipeline type
│   └── phase-2/                       # 1,000q: HuggingFace datasets
│
├── workflows/                         # n8n workflow management
│   ├── manifest.json                  # Version tracking
│   ├── sync.py                        # Pull workflows from n8n
│   ├── deploy/deploy.py               # Deploy workflow JSON to n8n
│   ├── source/                        # Source workflow JSONs
│   ├── improved/apply.py              # 30+ patches + deploy
│   └── snapshots/                     # Timestamped snapshots
│
├── db/                                # Database schemas & population
│   ├── populate/                      # DB population scripts
│   └── readiness/                     # DB readiness checks
│
├── docs/                              # Dashboard + data
│   ├── index.html                     # Interactive dashboard (7 tabs)
│   ├── data.json                      # Full evaluation data (1MB+, v2 format)
│   ├── status.json                    # COMPACT STATUS (<3KB, auto-generated)
│   ├── architecture.md                # THIS FILE — detailed reference
│   └── tested-questions.json          # Dedup manifest
│
├── logs/                              # Execution traces
│   ├── executions/                    # Per-session JSONL
│   ├── errors/                        # Error trace files
│   ├── pipeline-results/              # Per-pipeline JSON
│   └── fast-iter/                     # Fast iteration snapshots
│
├── phases/overview.md                 # Full 5-phase strategy
│
└── .github/workflows/
    ├── rag-eval.yml                   # Scheduled + manual eval
    ├── agentic-eval.yml               # Post-eval AI analysis
    ├── n8n-error-log.yml              # Error receiver
    └── dashboard-deploy.yml           # Auto-deploy dashboard
```

---

## Phase Gates (Targets)

### Phase 1 — Baseline (200q) — CURRENT
| Pipeline | Target | Additional |
|---|---|---|
| Standard | >=85% | |
| Graph | >=70% | |
| Quantitative | >=85% | |
| Orchestrator | >=70% | P95 latency <15s, error rate <5% |
| **Overall** | **>=75%** | 3 consecutive stable iterations |

### Phase 2 — Expand (1,000q)
Requires Phase 1 ALL gates passed. Graph >=60%, Quantitative >=70%. No Phase 1 regression.

### Phase 3-5
See `phases/overview.md` for full gate definitions.

---

## n8n API Access Pattern

```python
import urllib.request, json, os
api_key = os.environ["N8N_API_KEY"]
host = "https://amoret.app.n8n.cloud"

# GET workflow
req = urllib.request.Request(f"{host}/api/v1/workflows/{wf_id}",
    headers={"X-N8N-API-KEY": api_key})

# PUT workflow (deploy) — must filter settings
ALLOWED_SETTINGS = {"executionOrder", "callerPolicy", "saveManualExecutions", "saveExecutionProgress"}
```

---

## Root Cause Analysis (from Phase 1 iterations)

### Orchestrator — CRITICAL
- Cascading timeouts: broadcasts to ALL 3 sub-pipelines, waits for slowest
- Response Builder crash on empty `task_results`
- Query Router bug: leading space in `" direct_llm"` causes misrouting
- Cache Hit bug: compares against string `"Null"` instead of boolean
- 11 fixes in apply.py (Router, Cache, Response Builder, continueOnFail, Intent Analyzer)

### Graph RAG
- Entity extraction failures: HyDE extracts wrong names
- Missing entities: historical figures not matched
- 7 fixes in apply.py (fuzzy matching, entity rules, answer compression)

### Quantitative RAG
- SQL edge cases: multi-table JOINs, period filtering, entity name mismatch
- 8 fixes in apply.py (SQL hints, ILIKE, zero-row detection, Phase 2 tables)

### Standard RAG
- "No item to return" from Pinecone
- Verbose answers lower F1
- 6 fixes in apply.py (answer compression, topK increase, HyDE improvement)

---

## Workflow Patches (`workflows/improved/apply.py`)

| Pipeline | Fixes | Key Changes |
|---|---|---|
| Orchestrator | 11 | Timeout cascade, routing, Response Builder, continueOnFail |
| Graph | 7 | Entity extraction, fuzzy matching, answer conciseness |
| Standard | 6 | Answer compression, topK, HyDE prompts |
| Quantitative | 8 | SQL generation, ILIKE, zero-row detection, Phase 2 tables |

Deploy: `python3 workflows/improved/apply.py --deploy`
Dry-run: `python3 workflows/improved/apply.py`
