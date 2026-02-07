# Multi-RAG Orchestrator — SOTA 2026

## Objective

Benchmark, test, and iteratively improve 4 n8n RAG workflows deployed on n8n cloud.
The system evaluates each pipeline's accuracy, latency, and cost, then proposes targeted
workflow structure improvements ONLY when data shows a clear need (e.g. accuracy plateau,
high error rate, routing failures).

**Current phase: Evaluation & Iterative Improvement**

## What Has Been Done

### Orchestrator Bug Fixes (Feb 7 2026)
- **If1 dead-end branch**: Connected branch 2 → Postgres: Get Current Tasks (was `[]`)
- **Return Response V8**: Changed `$json.final_response` → `$('Response Builder V9').item.json.final_response`
- **Invalid settings**: Removed `availableInMCP`, `timeSavedMode` (caused HTTP 400 on deploy)
- All fixes deployed to n8n cloud and verified working.

### Baseline Evaluation (200 questions, Feb 7 2026)
| Pipeline | Accuracy | Avg Latency | Errors | Notes |
|---|---|---|---|---|
| Standard | 78.0% | 5.5s | 0 | Pinecone vectors, good factual recall |
| Graph | 50.0% | 4.4s | 2 | Neo4j entities sparse, many "not in context" |
| Quantitative | 80.0% | 2.5s | 6 | Supabase SQL, strong numeric matching |
| Orchestrator | 48.0% | 10.9s | 16 | 16/50 timeouts, routing overhead |

### Infrastructure
- Live GitHub Pages dashboard at `docs/index.html` (auto-refresh, Chart.js, cost tracking)
- Live results writer `benchmark-workflows/live-results-writer.py` feeds `docs/data.json`
- Evaluation script wired to dashboard for real-time progress updates
- Tested questions tracked in `docs/tested-questions.json` to prevent re-testing

## What Remains

### Immediate (next session)
1. **Full database ingestion** — Supabase DNS blocked in current env; run from local/external:
   ```bash
   export SUPABASE_PASSWORD="udVECdcSnkMCAPiY"
   cd benchmark-workflows
   python populate-all-databases.py
   python push-all-datasets.py
   ```
2. **Run full 1,200-question evaluation** — after ingestion, all questions become testable
3. **Analyze weak spots** — identify categories/question types with lowest accuracy

### Iterative Improvement Cycle
1. Run evaluation → review results on dashboard
2. Identify failing patterns (e.g. graph multi-hop accuracy <50%, orchestrator timeouts)
3. Propose targeted workflow changes (prompt tuning, retrieval params, routing logic)
4. Apply changes via `deploy-corrected-workflows.py`
5. Re-run evaluation on same questions → compare before/after
6. Repeat until accuracy targets met

### Improvement Targets
- Standard RAG: ≥85% accuracy
- Graph RAG: ≥70% accuracy (requires more Neo4j entities)
- Quantitative RAG: ≥85% accuracy
- Orchestrator: ≥70% accuracy, <15s avg latency, <5% timeout rate

## Architecture

### n8n Cloud Workflows (host: amoret.app.n8n.cloud)
| Workflow | Webhook Path | DB |
|---|---|---|
| WF5 Standard RAG V3.4 | `/webhook/rag-multi-index-v3` | Pinecone |
| WF2 Graph RAG V3.3 | `/webhook/ff622742-...` | Neo4j |
| WF4 Quantitative V2.0 | `/webhook/3e0f8010-...` | Supabase SQL |
| V10.1 Orchestrator | `/webhook/92217bb8-...` | Routes to above |

### Databases
| DB | Content | Size |
|---|---|---|
| **Pinecone** | Vector embeddings (text-embedding-3-small, 1536-dim) | 10,411 vectors, 12 namespaces |
| **Neo4j** | Entity graph (Person, Org, Tech, City...) | 145 nodes, 98 relationships |
| **Supabase** | Financial tables (3 companies) + benchmark_datasets | 88 rows + HF datasets |

### Datasets (3 question files, 1,200 total)
| File | Questions | Types |
|---|---|---|
| `benchmark-50x2-questions.json` | 100 | 50 graph + 50 quantitative |
| `benchmark-standard-orchestrator-questions.json` | 100 | 50 standard + 50 orchestrator |
| `rag-1000-test-questions.json` | 1,000 | 500 graph + 500 quantitative (HF datasets) |

After HF ingestion, 16 additional datasets (10,500 items) provide the DB content needed
to make all 1,200 questions testable.

## Key Files

### Root
- `V10.1 orchestrator copy (5).json` — Main orchestrator workflow (66 nodes, 3 bugs fixed)
- `TEST - SOTA 2026 - WF*.json` — Individual RAG pipeline workflows
- `TEST - SOTA 2026 - Ingestion V3.1.json` — Document ingestion workflow

### docs/ (GitHub Pages Dashboard)
- `index.html` — Live dashboard (auto-refresh 5s, Chart.js charts, question feed)
- `data.json` — Live data feed (pipeline stats, DB coverage, question results, history)
- `tested-questions.json` — Dedup manifest: all tested question IDs with timestamps

### benchmark-workflows/
- `run-comprehensive-eval.py` — **Main eval script**: tests all 4 pipelines, feeds dashboard live
- `live-results-writer.py` — Module: records results to `docs/data.json` in real-time
- `deploy-corrected-workflows.py` — Deploys workflow JSON to n8n cloud via REST API
- `populate-all-databases.py` — Master DB population (Supabase + Pinecone + Neo4j)
- `populate-neo4j-entities.py` — Neo4j entity graph builder
- `populate-pinecone-embeddings.py` — Real embedding creator for Pinecone
- `push-all-datasets.py` — HuggingFace dataset ingestion pipeline (16 datasets)
- `financial-tables-migration.sql` — Supabase financial tables DDL + seed data
- `community-summaries-migration.sql` — Graph RAG community summaries
- `supabase-migration.sql` — Core Supabase schema
- `WF-Benchmark-*.json` — Benchmark helper workflows for n8n

## Environment Variables Required
```bash
export SUPABASE_PASSWORD="..."        # Supabase PostgreSQL
export PINECONE_API_KEY="..."         # Pinecone vector DB
export PINECONE_HOST="https://sota-rag-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
export NEO4J_PASSWORD="..."           # Neo4j Aura graph DB
export OPENROUTER_API_KEY="..."       # LLM API (for embeddings + eval)
# Optional: export OPENAI_API_KEY="..." # Direct OpenAI (preferred for embeddings)
```

## Conventions
- Workflow JSON must NOT be modified directly — use deploy script with patches
- All credentials via environment variables only — never commit secrets
- Dashboard updates happen automatically via `live-results-writer.py`
- Every eval run records tested question IDs to prevent duplicate testing
- Workflow improvements are proposed ONLY when eval data shows clear need
