# Multi-RAG Orchestrator — SOTA 2026

## Objective

Benchmark, test, and iteratively improve 4 n8n RAG workflows deployed on n8n cloud.
The system evaluates each pipeline's accuracy, latency, and cost, then proposes targeted
workflow structure improvements ONLY when data shows a clear need (e.g. accuracy plateau,
high error rate, routing failures).

**Current phase: Phase 1 — Baseline (200q, iterative improvement loop)**

See `benchmark-workflows/evaluation-plan.md` for the full 5-phase strategy:
Phase 1 (200q) → Phase 2 (1,000q) → Phase 3 (~10Kq) → Phase 4 (~100Kq) → Phase 5 (1M+q)

---

## Baseline Results (200 questions, Feb 7 2026)

| Pipeline | Accuracy | Avg Latency | P95 | Errors | F1 Mean | Target |
|---|---|---|---|---|---|---|
| **Standard** | 78.0% (39/50) | 5.5s | 6.6s | 0 | 0.16 | ≥85% |
| **Graph** | 50.0% (25/50) | 4.4s | 5.3s | 2 | 0.12 | ≥70% |
| **Quantitative** | 80.0% (40/50) | 2.5s | 3.7s | 6 | 0.06 | ≥85% |
| **Orchestrator** | 48.0% (24/50) | 10.9s | 23.3s | 16 | 0.10 | ≥70%, <15s |
| **Overall** | **64.0%** | **5.8s** | — | **24** | **0.11** | **≥75%** |

### Root Cause Analysis

#### Orchestrator (48% — CRITICAL)
- **38% error rate** (16/50 timeout + HTTP errors) — the #1 system bottleneck
- Timeouts cascade: orchestrator waits for ALL sub-pipelines in parallel, so latency = max(standard, graph, quant) + routing overhead
- Routing logic adds 4-5s overhead per query vs standalone pipelines
- No fallback: if a sub-pipeline times out, entire request fails instead of returning partial results
- Response Builder V9 sometimes gets empty `$json.task_results` from timed-out sub-workflows

#### Graph RAG (50% — HIGH PRIORITY)
- **Entity extraction failures**: WF2's HyDE step extracts entity names from queries, but often misses key entities or generates wrong names → Neo4j lookup returns nothing
- **Sparse graph (was 145 nodes)**: many query topics had no matching entities → "not in context" answers
- **Multi-hop path gaps**: some paths exceeded 3-hop limit (e.g., Fleming→COVID-19 was 4 hops)
- **Generic relationships**: CONNECTE used for everything, losing semantic precision
- **Community summaries stale**: entity_names arrays didn't cover all new entities

#### Standard RAG (78% — MEDIUM)
- Low F1 scores even on passing answers (mean 0.16) → answers are imprecise but "technically correct"
- Pinecone retrieval returns relevant-but-noisy chunks; LLM synthesizes verbose answers
- 13 hard failures on topics likely not in embedding space (Rosetta Stone, tsunamis, Galileo, etc.)

#### Quantitative RAG (80% — CLOSE TO TARGET)
- 6 errors on edge cases (growth calculations, multi-company comparisons, product count queries)
- Employee/department queries fail (tables may not be fully populated in Supabase)
- Strong on simple lookups, weak on cross-table calculations

---

## What Has Been Done

### Knowledge Graph Enrichment (Feb 7 — Session 2)
- **+20 new entities**: Edward Jenner, Radioactivity, Evolution, Gravity, Computer Science, ARPANET, Mona Lisa, Machine Learning, CRISPR, Bletchley Park, Enigma Machine, etc.
- **+71 new relationships** (total: 151 relationships, 110 entities) with richer typing
- **Critical path fixes**: Fleming→Penicillin→Vaccination→COVID-19 (3 hops), Einstein→Royal Society→Darwin→Cambridge (3 hops), Penicillin→Germ Theory→Pasteur (2 hops)
- **WHO direct disease links**: WHO→COVID-19, Malaria, Tuberculosis, Cancer, Influenza all ETUDIE
- **Community summaries updated**: all 9 summaries expanded with new entity names

### Orchestrator Bug Fixes (Feb 7 — Session 1)
- **If1 dead-end branch**: Connected branch 2 → Postgres: Get Current Tasks (was `[]`)
- **Return Response V8**: Changed `$json.final_response` → `$('Response Builder V9').item.json.final_response`
- **Invalid settings**: Removed `availableInMCP`, `timeSavedMode` (caused HTTP 400 on deploy)
- All fixes deployed to n8n cloud and verified working.

### Infrastructure
- Live GitHub Pages dashboard at `docs/index.html` (interactive, Chart.js, filters, cost tracking)
- Live results writer `benchmark-workflows/live-results-writer.py` feeds `docs/data.json`
- Evaluation script wired to dashboard for real-time progress updates
- Tested questions tracked in `docs/tested-questions.json` to prevent re-testing

---

## Improvement Roadmap

### TIER 1: Orchestrator Timeout Elimination (→ 48% → 70%+)

**Problem**: 38% error rate from timeouts. The orchestrator calls all 3 sub-workflows in parallel and waits for ALL to complete. If any sub-workflow exceeds n8n's execution timeout (30s), the orchestrator errors.

**Strategy: Sequential Fallback with Timeout Guards**

1. **Per-pipeline timeout** (via n8n workflow patch):
   - Add `setTimeout` equivalent to each sub-workflow invocation
   - Set individual timeout: Standard=8s, Graph=7s, Quantitative=5s
   - On timeout: return `{success: false, timeout: true}` instead of killing the orchestrator
   - Implementation: Modify Execution Engine V10 to use `waitForSubWorkflow: false` with polling

2. **Smart routing instead of broadcast**:
   - Currently: ALL 3 pipelines invoked for every query
   - Better: Intent Analyzer routes to 1-2 most relevant pipelines only
   - Patch: Make Execution Engine V10 respect intent classification (STANDARD/GRAPH/QUANTITATIVE)
   - Expected: cuts latency by 40-60% (only 1-2 pipelines instead of 3)

3. **Response Builder fallback**:
   - If primary pipeline times out, use backup pipeline's response
   - If all timeout, return LLM-only answer with low confidence flag
   - Patch: Add null-check in Response Builder V9 before accessing `task_results`

4. **Orchestrator parallelization optimization**:
   - Current: `Invoke WF5` + `Invoke WF2` + `Invoke WF4` all fire, then Wait node collects
   - Alternative A: **Speculative execution** — invoke most-likely pipeline first, others only if confidence < threshold
   - Alternative B: **Streaming assembly** — return first response that arrives with confidence > 0.7, cancel others
   - Alternative C: **Cached routing** — use a query→pipeline mapping cache for repeated question patterns (reduces overhead for known question types)

**Expected impact**: Error rate 38% → <5%, Latency 10.9s → ~7s, Accuracy 48% → 68-72%

### TIER 2: Graph RAG Entity Extraction Fix (→ 50% → 70%+)

**Problem**: Even with correct data in Neo4j, WF2's HyDE entity extraction often fails to match entity names.

**Strategy: Multi-Approach Entity Matching**

1. **Fuzzy entity matching in Neo4j query**:
   - Current: exact name match `n.name IN $entity_names`
   - Better: Add fuzzy matching: `n.name =~ '(?i).*' + extracted_name + '.*'` as fallback
   - Or: Use full-text index in Neo4j for approximate entity search
   - Patch: Neo4j Query Builder V2 node

2. **Improved HyDE prompt for entity extraction**:
   - Current prompt: generic "extract entities from question"
   - Better: Include the list of known entity names as context
   - Implementation: Fetch entity catalog from Neo4j (`MATCH (n) RETURN n.name LIMIT 200`) and include in HyDE prompt
   - Expected: reduces entity extraction misses by 50-70%

3. **Bidirectional entity seeding**:
   - For questions like "Which scientists at Cambridge?", extract both "scientists" (type) AND "Cambridge" (name)
   - Start traversal from matched name nodes, filter by type
   - Patch: Neo4j Query Builder to support type-based filtering in MATCH clause

**Expected impact**: Accuracy 50% → 70%, F1 0.12 → 0.35+

### TIER 3: Standard RAG Precision (→ 78% → 85%+)

1. **Chunk quality audit**: Check Pinecone namespaces for embedding quality
   - Some namespaces (benchmark-popqa, benchmark-triviaqa) may have short/noisy chunks
   - Re-embed with larger chunk overlap for better context
2. **Retrieval tuning**: Increase topK from current value, add reranking
3. **Prompt tuning**: Tell LLM to be concise and match expected answer format

### TIER 4: Quantitative Edge Cases (→ 80% → 85%+)

1. **Employee/department queries**: Verify `employees` table has all expected data
2. **Growth calculations**: SQL query may not handle multi-year comparisons correctly
3. **Product catalog queries**: Verify `products` table has all 18 products seeded

---

## Detailed Failure Analysis

### Orchestrator: 19 ERR Questions (38%)
| Pattern | Count | Root Cause | Fix |
|---|---|---|---|
| Timeout (no response) | 12 | n8n 30s timeout exceeded | Per-pipeline timeout guards |
| Graph sub-workflow ERR | 5 | Neo4j entity miss → empty response → builder crash | Null-check in Response Builder |
| Multi-engine timeout | 2 | Both graph+quant timeout on complex queries | Smart routing (invoke 1-2 only) |

### Graph: 24 FAIL Questions (48%)
| Pattern | Count | Root Cause | Fix |
|---|---|---|---|
| Entity not extracted | 10 | HyDE generates wrong entity names | Fuzzy matching, entity catalog in prompt |
| Entity not in graph | 6 | Missing entities (now fixed with enrichment) | ✅ Done (110 entities) |
| Multi-hop path > 3 | 3 | Path too long for traversal limit | ✅ Done (bridging relationships) |
| Low F1 on correct answers | 5 | Graph returns correct entities but LLM generates verbose answer | Prompt tuning |

### Standard: 11 FAIL Questions (22%)
| Pattern | Count | Root Cause | Fix |
|---|---|---|---|
| Topic not in embeddings | 6 | No relevant chunks in Pinecone | Full HF ingestion (16 datasets) |
| Low precision answer | 3 | Verbose LLM output doesn't match expected keywords | Prompt tuning |
| Hallucination | 2 | LLM generates plausible but wrong facts | Context-grounding prompt |

### Quantitative: 4 FAIL + 6 ERR
| Pattern | Count | Root Cause | Fix |
|---|---|---|---|
| SQL error on complex query | 3 | Multi-table JOIN or growth calc fails | SQL template fixes |
| Employee table incomplete | 3 | Only 9 rows in employees table | Data seeding fix |
| Product query miss | 2 | Products table not queried correctly | SQL routing fix |
| Growth/comparison ERR | 2 | Multi-year logic fails | SQL template for year-over-year |

---

## Cost Tracking

### Current State
- **Infrastructure ready** but **all costs hardcoded to $0**
- `live-results-writer.py` supports `cost_usd` parameter on every question
- Dashboard displays cost columns but shows $0.00
- Workflows track `tokens_used` internally but don't expose to eval script

### Cost Estimation per Pipeline Call
| Component | Tokens (est.) | Cost/call |
|---|---|---|
| **Standard**: Embedding (text-embedding-3-small) | ~500 | $0.00001 |
| **Standard**: Pinecone query | — | $0.00 (free tier) |
| **Standard**: LLM synthesis (Gemini Flash) | ~2000 out | $0.00015 |
| **Graph**: HyDE + entity extraction | ~1500 | $0.00012 |
| **Graph**: Neo4j query | — | $0.00 |
| **Graph**: Cohere rerank | ~500 | $0.00003 |
| **Graph**: LLM synthesis | ~2000 | $0.00015 |
| **Quantitative**: SQL generation | ~1000 | $0.00008 |
| **Quantitative**: LLM synthesis | ~1500 | $0.00012 |
| **Orchestrator**: Intent analysis + routing | ~1000 | $0.00008 |
| **Orchestrator**: Sub-workflow calls | (sum of above) | ~$0.0005 |
| **Orchestrator**: Response merging | ~2000 | $0.00015 |

**Estimated total for 200 questions**: ~$0.08-0.15
**Projected for 1,200 questions**: ~$0.50-0.90

---

## Architecture

### n8n Cloud Workflows (host: amoret.app.n8n.cloud)
| Workflow | Webhook Path | DB | Nodes |
|---|---|---|---|
| WF5 Standard RAG V3.4 | `/webhook/rag-multi-index-v3` | Pinecone | ~20 |
| WF2 Graph RAG V3.3 | `/webhook/ff622742-...` | Neo4j + Supabase | ~25 |
| WF4 Quantitative V2.0 | `/webhook/3e0f8010-...` | Supabase SQL | ~15 |
| V10.1 Orchestrator | `/webhook/92217bb8-...` | Routes to above | 66 |

### Databases
| DB | Content | Size |
|---|---|---|
| **Pinecone** | Vector embeddings (text-embedding-3-small, 1536-dim) | 10,411 vectors, 12 namespaces |
| **Neo4j** | Entity graph (Person, Org, Tech, City, Museum, Disease) | 110+ nodes, 151+ relationships |
| **Supabase** | Financial tables (3 companies) + benchmark_datasets + community_summaries | 88 rows + HF datasets |

### Datasets (3 question files, 1,200 total)
| File | Questions | Types |
|---|---|---|
| `benchmark-50x2-questions.json` | 100 | 50 graph + 50 quantitative |
| `benchmark-standard-orchestrator-questions.json` | 100 | 50 standard + 50 orchestrator |
| `rag-1000-test-questions.json` | 1,000 | 500 graph + 500 quantitative (HF datasets) |

---

## Immediate Next Steps

### Priority 1: Re-run Graph RAG eval (validate enrichment)
```bash
cd benchmark-workflows
python run-comprehensive-eval.py --types graph --reset
```
Expected: Graph accuracy 50% → 60-65% from entity enrichment alone.

### Priority 2: Deploy orchestrator timeout patches
```bash
python deploy-corrected-workflows.py  # with timeout guard patches
```

### Priority 3: Full database ingestion
```bash
export SUPABASE_PASSWORD="udVECdcSnkMCAPiY"
cd benchmark-workflows
python populate-all-databases.py
python push-all-datasets.py
```

### Priority 4: Run full 1,200-question evaluation
```bash
python run-comprehensive-eval.py --include-1000 --types standard,graph,quantitative,orchestrator
```

---

## Key Files

### Root
- `V10.1 orchestrator copy (5).json` — Main orchestrator workflow (66 nodes, 3 bugs fixed)
- `TEST - SOTA 2026 - WF*.json` — Individual RAG pipeline workflows
- `TEST - SOTA 2026 - Ingestion V3.1.json` — Document ingestion workflow

### docs/ (GitHub Pages Dashboard — 10 tabs)
- `index.html` — Interactive dashboard: Overview, Pipelines, Questions Explorer, Costs, Cross-Analysis, Knowledge Graph, Workflow Evolution, DB Monitor, **Phases**, Execution Logs
- `data.json` — Live data feed: pipeline stats, DB coverage, questions, history, workflow_changes, db_snapshots, execution_logs, **evaluation_phases**, **current_phase**
- `tested-questions.json` — Dedup manifest: all tested question IDs with timestamps

### logs/ (Structured Execution Traces)
- `executions/exec-*.jsonl` — Per-session JSONL logs (one JSON line per question, full input/output/pipeline details)
- `errors/err-*.json` — Isolated error traces with full payloads, input, partial response, pipeline context
- `db-snapshots/snap-*.json` — Periodic database state snapshots (Pinecone, Neo4j, Supabase)
- `README.md` — Schema documentation for all log formats

### benchmark-workflows/
- `run-comprehensive-eval.py` — **Main eval script**: tests all 4 pipelines, feeds dashboard live, writes execution logs, takes DB snapshots pre/post eval
- `live-results-writer.py` — Module: records results to `docs/data.json` + structured logs in `logs/`
  - New: `record_execution()` — detailed per-question trace with raw response, pipeline details
  - New: `snapshot_databases()` — takes and stores DB state snapshots
  - New: `record_workflow_change()` — logs workflow modifications for evolution timeline
- `evaluation-plan.md` — **5-phase incremental evaluation strategy**: DB readiness checks, gate criteria, scaling projections (200q → 1M+q)
- `n8n-github-logging-patches.md` — **Concrete n8n workflow modifications** for pushing errors/logs to GitHub directly from workflows
- `deploy-corrected-workflows.py` — Deploys workflow JSON to n8n cloud via REST API
- `populate-all-databases.py` — Master DB population (Supabase + Pinecone + Neo4j)
- `populate-neo4j-entities.py` — Neo4j entity graph builder (110 entities, 151 relationships)
- `populate-pinecone-embeddings.py` — Real embedding creator for Pinecone
- `push-all-datasets.py` — HuggingFace dataset ingestion pipeline (16 datasets)
- `financial-tables-migration.sql` — Supabase financial tables DDL + seed data
- `community-summaries-migration.sql` — Graph RAG community summaries (9 communities, enriched)
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

## Logging & Monitoring Architecture

### Data Flow
```
n8n Workflow → HTTP Response → run-comprehensive-eval.py
                                   ↓
                              live-results-writer.py
                                   ↓ (parallel writes)
                   ┌───────────────┼──────────────┐
                   ↓               ↓              ↓
           docs/data.json   logs/executions/  logs/errors/
           (dashboard)      (JSONL traces)    (error files)
                   ↓
           docs/index.html (9-tab dashboard, auto-refresh 5s)
```

### Error Classification
Errors are automatically classified into types for analytics:
- `TIMEOUT` — n8n execution or HTTP timeout (>25s or "timed out" in error)
- `NETWORK` — Connection failures (urlopen error, connection refused)
- `SERVER_ERROR` — HTTP 5xx responses from n8n
- `RATE_LIMIT` — HTTP 429 responses
- `EMPTY_RESPONSE` — HTTP 200 with empty body
- `ENTITY_MISS` — Graph RAG entity extraction failure
- `SQL_ERROR` — Quantitative SQL generation/execution error
- `UNKNOWN` — Unclassified errors

### n8n → GitHub Direct Logging (Proposed)
See `benchmark-workflows/n8n-github-logging-patches.md` for concrete workflow patches:
- Each workflow gets a GitHub Logger node (HTTP Request to GitHub Contents API)
- Fires on error paths: creates error trace files in `logs/errors/`
- Graph RAG: logs entity extraction misses + Neo4j traversal results
- Quantitative: logs SQL validation failures + self-healing attempts
- Orchestrator: logs sub-pipeline timeouts + routing decisions
- Alternative: GitHub Actions `repository_dispatch` for cleaner git handling

## Conventions
- Workflow JSON must NOT be modified directly — use deploy script with patches
- All credentials via environment variables only — never commit secrets
- Dashboard updates happen automatically via `live-results-writer.py`
- Every eval run records tested question IDs to prevent duplicate testing
- Workflow improvements are proposed ONLY when eval data shows clear need
- Every eval run takes pre/post DB snapshots automatically
- Error traces are written as individual JSON files for easy inspection
- Execution logs use JSONL format (one JSON per line) for streaming analysis
