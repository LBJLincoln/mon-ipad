# Architecture Reference — Multi-RAG Orchestrator SOTA 2026

> Reference detaillee. Pour demarrage rapide, utiliser `docs/status.json`.

---

## n8n Docker Workflows (host: 34.136.180.66:5678)

### Pipelines RAG (4)

| Workflow | Webhook Path | DB | Docker ID |
|---|---|---|---|
| Standard RAG V3.4 | `/webhook/rag-multi-index-v3` | Pinecone | `M12n4cmiVBoBusUe` |
| Graph RAG V3.3 | `/webhook/ff622742-...` | Neo4j + Supabase | `Vxm4TDdOLdb7j3Jy` |
| Quantitative V2.0 | `/webhook/3e0f8010-...` | Supabase SQL | `nQnAJyT06NTbEQ3y` |
| Orchestrator V10.1 | `/webhook/92217bb8-...` | Routes to above | `P1no6VZkNtnRdlBi` |

### Support Workflows (9)

| Workflow | Docker ID |
|---|---|
| Ingestion V3.1 | `6lPMHEYyWh1v34ro` |
| Enrichissement V3.1 | `KXnQKuKw8ZUbyZUl` |
| Feedback V3.1 | `cMlr32Qq7Sgy6Xq8` |
| Benchmark V3.0 | `tygzgU4i67FU6vm2` |
| Dataset Ingestion Pipeline | `S4FFbvx9Mn7DRkgk` |
| Monitoring & Alerting | `xFAcxnFS5ISnlytH` |
| Orchestrator Tester | `R0HRiLQmL3FoCNKg` |
| RAG Batch Tester | `k7jHXRTypXAQOreJ` |
| SQL Executor Utility | `Dq83aCiXCfymsgCV` |

### Trace Cloud (OBSOLETE — reference uniquement)

| Pipeline | Cloud ID | Execution reussie |
|---|---|---|
| Standard | `IgQeo5svGlIAPkBc` | #19404 |
| Graph | `95x2BBAbJlLWZtWEJn6rb` | #19305 |
| Quantitative | `E19NZG9WfM7FNsxr` | #19326 |
| Orchestrator | `ALd4gOEqiKL5KR1p` | #19323 |

---

## Databases

| DB | Content | Phase 1 | Phase 2 |
|---|---|---|---|
| **Pinecone** | Vector embeddings | 10,411 vectors, 12 namespaces | Configurable via n8n |
| **Neo4j** | Entity graph | 110 nodes, 151 relationships | +4,884 entities |
| **Supabase** | Financial tables | 88 rows, 5 tables | +450 rows |

---

## LLM Model Registry

Modeles gratuits via OpenRouter.

### Docker Env Vars (models configured in n8n)

| Variable | Model | Usage |
|---|---|---|
| `LLM_SQL_MODEL` | meta-llama/llama-3.3-70b-instruct:free | SQL generation |
| `LLM_FAST_MODEL` | google/gemma-3-27b-it:free | Fast operations |
| `LLM_INTENT_MODEL` | meta-llama/llama-3.3-70b-instruct:free | Intent classification |
| `LLM_PLANNER_MODEL` | meta-llama/llama-3.3-70b-instruct:free | Task planning |
| `LLM_AGENT_MODEL` | meta-llama/llama-3.3-70b-instruct:free | Agent reasoning |
| `LLM_HYDE_MODEL` | meta-llama/llama-3.3-70b-instruct:free | HyDE generation |
| `LLM_EXTRACTION_MODEL` | arcee-ai/trinity-large-preview:free | Entity extraction |
| `LLM_COMMUNITY_MODEL` | arcee-ai/trinity-large-preview:free | Community summaries |
| `LLM_LITE_MODEL` | google/gemma-3-27b-it:free | Lightweight tasks |

### Embeddings & Reranking

| Provider | Model | Dimensions |
|---|---|---|
| **Cohere** (primary) | embed-english-v3.0 | 1024 |
| **Cohere** (reranker) | rerank-multilingual-v3.0 | N/A |
| **Jina AI** (backup) | jina-embeddings-v3 | 1024 |

---

## Capability Matrix (from Claude Code)

| Capability | Access | How |
|---|---|---|
| **n8n Webhooks** | DIRECT | HTTPS to `34.136.180.66:5678/webhook/*` |
| **n8n REST API** | DIRECT | HTTPS to `34.136.180.66:5678/api/v1/*` |
| **n8n MCP** | DIRECT | streamableHttp to `34.136.180.66:5678/mcp-server/http` |
| **GitHub** | DIRECT | `git push` + `gh` CLI |
| **Pinecone** | DIRECT | HTTPS REST API |
| **Neo4j** | VIA n8n | Docker bolt://localhost:7687 |
| **Supabase** | VIA n8n | Docker direct access |
| **OpenRouter** | VIA n8n | Proxied through n8n workflows |

---

## Data Flow

```
eval/quick-test.py (1-5q)   -+
eval/iterative-eval.py       -+-- 4 pipelines (n8n webhooks)
eval/run-eval-parallel.py    -+
          |
          +-- Standard Pipeline  --> Pinecone
          +-- Graph RAG Pipeline --> Neo4j + Supabase
          +-- Quantitative       --> Supabase SQL
          +-- Orchestrator       --> Routes to above
                    |
          eval/node-analyzer.py  (diagnostics)
          scripts/analyze_n8n_executions.py (raw data)
                    |
          +--------+--------------------+
          v        v                    v
    docs/data.json  logs/diagnostics/  n8n/analysis/
          v
    eval/generate_status.py
          v
    docs/status.json
          v
    docs/index.html (dashboard)
```

---

## Repository Structure

```
mon-ipad/
+-- CLAUDE.md                    # Session bootstrap
+-- directives/                  # Mission control
+-- technicals/                  # Reference docs (architecture, stack, credentials, phases, knowledge-base)
+-- eval/                        # Evaluation scripts
+-- scripts/                     # Utility scripts
+-- n8n/                         # Workflows (live, validated, sync)
+-- mcp/                         # MCP servers & docs
+-- website/                     # Next.js frontend
+-- site/                        # Website reference (copies)
+-- datasets/                    # Test questions
+-- db/                          # Database management
+-- docs/                        # Dashboard + status
+-- logs/                        # Execution logs
+-- snapshot/                    # Historical backups
+-- outputs/                     # Dated session archives
+-- utilisation/                 # Usage guides
```

---

## Phase Gates (Targets)

### Phase 1 — Baseline (200q) — CURRENT
| Pipeline | Target |
|---|---|
| Standard | >=85% |
| Graph | >=70% |
| Quantitative | >=85% |
| Orchestrator | >=70% (P95 latency <15s, error rate <5%) |
| **Overall** | **>=75%** (3 consecutive stable iterations) |

### Phase 2-5
See `technicals/phases-overview.md` for full gate definitions.

---

## Root Cause Analysis (from previous iterations)

### Orchestrator
- Cascading timeouts: broadcasts to ALL 3 sub-pipelines
- Response Builder crash on empty `task_results`
- Query Router bug: leading space in `" direct_llm"` causes misrouting

### Graph RAG
- Entity extraction failures: HyDE extracts wrong names
- Missing entities: historical figures not matched

### Quantitative RAG
- SQL edge cases: multi-table JOINs, period filtering

### Standard RAG
- "No item to return" from Pinecone
- Verbose answers lower F1
