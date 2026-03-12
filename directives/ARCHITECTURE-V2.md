# Architecture V2 — 5 Parts, Clear Separation

> Date: 2026-03-12 | Status: DESIGN PHASE

## Vision

Le projet est restructure en **5 parties independantes**, chacune avec ses propres scripts, agents, skills, et metriques. Chaque partie a un **role unique** et communique via **Redis queues** (Upstash) ou **webhooks n8n**.

```
PART 1          PART 2           PART 3          PART 4           PART 5
DATA            ENRICHMENT       RAG             EVAL &           DATASET
ACQUISITION     PIPELINE         PIPELINES       IMPROVEMENT      PROVIDERS
& INGESTION                      (6 query)       & TESTING
    |               ^                |               |               |
    +---> Redis --->+                |               |               |
    |    queue                       v               v               |
    +-----------> Pinecone -----> Queries <----- Eval-blast         |
    +-----------> Supabase -----> Queries <----- Regression         |
    +-----------> Neo4j --------> Queries                           |
                                                                    |
                                     ^                              |
                                     +--- Expert Q&A datasets <----+
```

---

## PART 1: DATA ACQUISITION & INGESTION

### Role
Trouver, telecharger, traiter (Docling), chunker, embedder, et stocker des documents reels dans les 3 bases.

### Scripts (a garder/creer)
| Script | Role | Status |
|--------|------|--------|
| `ops/ingest-pipeline.py` | **NEW** — Script unifie remplacant les 5 chemins | A CREER |
| `ops/docling-s6-ingest.py` | PDF processing via Docling S6 | KEEP + FIX |
| `ops/tavily-mass-ingest.py` | Web document acquisition | KEEP + REFACTOR |

### Flux
```
1. Source discovery (Tavily, HF datasets, PDF URLs, local files)
2. Document download + dedup (check Supabase document_registry)
3. Processing: Docling S6 for PDFs, raw text for web content
4. Chunking: semantic chunks (1000 chars, 200 overlap, paragraph-aware)
5. Embedding: Pinecone E5 integrated (multilingual-e5-large, 1024d)
6. Storage: Pinecone vectors + Supabase sector_documents
7. Queue: Push doc_id to Redis `nomos:enrich:pending` for Part 2
```

### n8n Workflow
- **Ingestion V4.0** on S9 (`nh1D4Up0wBZhuQbp`)
- Webhook: `/webhook/rag-v6-ingestion`
- Nodes: Receive → Docling → Chunk → Embed → Pinecone + Supabase → Redis push

### Agent
- **Ingest Agent** — `ops/agent-ingest.py` (NEW, replaces ingest-feed + ingest-runner + continuous-ingest)
- Cycle: Every 30min, finds new sources, processes, stores, queues for enrichment
- Metric: docs_ingested_per_hour, vector_count_delta

### To DELETE (replaced by unified pipeline)
- `ops/fast-ingest.py` (absorbed into ingest-pipeline)
- `ops/continuous-ingest.py` (absorbed)
- `ops/agent-ingest-feed.py` (absorbed)
- `ops/ingest-enrich-chain.py` (absorbed)
- `ops/ingest-integrated.py` (dead code)
- `ops/ingest-to-pinecone.py` (dead code)
- `ops/clean-ingest.py` (utility, keep separately)
- `data/agents/_ingest_runner.py` (replaced)

---

## PART 2: ENRICHMENT PIPELINE

### Role
Prendre les documents ingeres (via Redis queue), extraire entites, relations, tables financieres, et enrichir Neo4j + Supabase.

### Scripts
| Script | Role | Status |
|--------|------|--------|
| `ops/enrich-worker.py` | **NEW** — Redis consumer, calls enrichment | A CREER |
| `ops/populate-neo4j-entities.py` | NER regex extraction → Neo4j | KEEP + IMPROVE |
| `ops/populate-quant-tables.py` | Financial table extraction → Supabase | KEEP |

### Flux
```
1. Redis consumer: pop from `nomos:enrich:pending`
2. Fetch document content from Supabase
3. Entity extraction (regex NER + LLM-assisted)
4. Neo4j writes: Entity nodes, SectorDocument nodes, MENTIONS rels
5. Financial table extraction (for Quant pipeline)
6. Supabase writes: sector_financial_tables
7. Mark doc as enriched in document_registry
8. Push to Redis `nomos:enrich:done`
```

### n8n Workflow
- **Enrichment V4.0** on S9 (`ORa01sX4xI0iRCJ8`)
- Webhook: `/webhook/rag-v6-enrichment`
- Nodes: Receive doc_id → Fetch from Supabase → LLM entity extraction → Neo4j write → Financial tables → Mark done

### Redis Integration (Upstash)
```
Queue: nomos:enrich:pending (FIFO list)
  - Payload: {"doc_id": "...", "sector": "...", "source": "..."}

Set: nomos:enrich:done (dedup tracking)
  - Members: doc_ids already enriched

Worker: ops/enrich-worker.py
  - BLPOP from pending queue
  - Process enrichment
  - SADD to done set
  - Configurable concurrency (1-3 workers)
```

### Agent
- **Enrich Agent** — `ops/agent-enrich.py` (NEW)
- Watches Redis queue depth, processes backlog
- Metric: entities_per_hour, queue_depth, enrichment_rate

### To DELETE
- `ops/redis-ingest-bridge.py` (absorbed into enrich-worker)
- `data/agents/_docs_runner.py` (USELESS, delete entirely)

---

## PART 3: RAG QUERY PIPELINES (6+)

### Role
Repondre aux questions des utilisateurs avec precision d'expert sectoriel. 6 pipelines minimum.

### Pipelines
| # | Pipeline | Workflow ID | Webhook | Role |
|---|----------|-----------|---------|------|
| 1 | **Standard** | `9FQdtx38JLPiT3Hx` | `/webhook/rag-multi-index-v3` | Vector search sectorielle |
| 2 | **Graph** | `6257AfT1l4FMC6lY` | `/webhook/ff622742-...` | Relations entites Neo4j |
| 3 | **Quantitative** | `cjhEhVs0KV1ExHqX` | `/webhook/3e0f8010-...` | Donnees financieres SQL |
| 4 | **Orchestrator** | `qOSaFFrqO8Jb4VGb` | `/webhook/orchestrator-v2` | Routage intelligent |
| 5 | **Hybrid** | TBD | TBD | Standard + Graph fusion |
| 6 | **Expert** | TBD | TBD | Deep research multi-source |

### Agent
- **Pipeline Monitor** — `ops/agent-pipeline.py` (NEW, replaces _pipeline_runner.py)
- Real quality checks (not just "returns >10 chars")
- Metric: response_quality_score, latency_p95, error_rate

### To DELETE
- `data/agents/_pipeline_runner.py` (false-positive smoke tests)
- `data/agents/_monitor_runner.py` (just wraps monitor.py)
- `ops/agentic-loop.py` (22 cycles, 0 results)

---

## PART 4: EVALUATION & IMPROVEMENT

### Role
Mesurer la qualite, detecter les regressions, proposer et tester des ameliorations. Environnement dedie.

### Scripts
| Script | Role | Status |
|--------|------|--------|
| `eval/eval-blast.py` | High-volume eval (50 Q/run) | KEEP (USEFUL) |
| `eval/quick-test.py` | Smoke test (5 Q/pipeline) | KEEP |
| `eval/llm_judge.py` | LLM answer scoring | KEEP |
| `eval/expert-eval.py` | Expert-level evaluation | KEEP |
| `ops/agent-regression.py` | Regression detection | KEEP (USEFUL) |
| `ops/agent-improver.py` | **NEW** — Autoresearch-style improve loop | A CREER |

### Autoresearch Pattern (from Karpathy)
```
1. Read current pipeline config (the "train.py")
2. Form hypothesis (e.g., "change Graph Cypher query template")
3. Create experiment branch
4. Deploy modified workflow to test Space
5. Run eval-blast on modified pipeline (fixed budget: 50 questions)
6. Compare vs baseline
7. If improved: commit + deploy to production
8. If regressed: revert + log why
9. Repeat
```

### Agent
- **Eval Agent** — eval-blast (KEEP as-is, already USEFUL)
- **Regression Agent** — agent-regression.py (KEEP as-is, already USEFUL)
- **Improver Agent** — `ops/agent-improver.py` (NEW, autoresearch pattern)
- Metric: accuracy_delta_per_session, experiments_run, improvements_committed

### Dedicated Space
- Use **S11** (Nomos42 engine-11) as testing/experiment Space
- Production changes only after passing eval on S11

### To DELETE
- `eval/dashboard-generator.py` (old)
- `eval/docling-fidelity.py` (unused)
- `eval/queue-eval-orchestrator.py` (experimental, unused)
- `eval/continue-eval.py` (redundant with eval-blast)
- `eval/continuous-eval.py` (redundant)
- `eval/continuous-judge.py` (redundant)
- `data/agents/_eval_runner.py` (redundant with eval-blast)
- `ops/agent-fixer.py` (diagnoses but never fixes, replace with improver)

---

## PART 5: DATASET PROVIDERS

### Role
Trouver des documents reels, generer des questions/reponses d'expert, alimenter les bases et l'eval.

### Scripts
| Script | Role | Status |
|--------|------|--------|
| `eval/generate-expert-questions.py` | Expert Q&A via Tavily+LLM | KEEP + IMPROVE |
| `eval/generate-standard-questions.py` | Standard Q&A generation | KEEP |
| `eval/generate-graph-questions.py` | Graph-specific Q&A | KEEP |
| `eval/generate-quant-questions.py` | Quantitative Q&A | KEEP |
| `eval/expert-discovery.py` | Find domain experts | KEEP |
| `ops/dataset-provider.py` | **NEW** — Unified dataset acquisition | A CREER |

### Dataset Types per Pipeline
| Pipeline | Dataset Needed | Current Count | Target |
|----------|---------------|--------------|--------|
| Standard | Sector Q&A with golden answers | ~500 | 5,000 |
| Graph | Entity relationship Q&A | ~200 | 2,000 |
| Quantitative | Financial data Q&A | ~300 | 3,000 |
| Orchestrator | Mixed routing Q&A | ~100 | 1,000 |
| Hybrid | Multi-source Q&A | 0 | 1,000 |
| Expert | Deep research Q&A | ~129 | 2,000 |

### Flux
```
1. Tavily search for real documents per sector
2. LLM generates expert-level questions from documents
3. LLM generates golden answers with source citations
4. Questions tagged by: sector, pipeline, difficulty, doc_type
5. Stored in Supabase eval_question_bank (already 29K+ questions)
6. Documents also fed to Part 1 (Ingestion) for indexing
```

### Agent
- **Dataset Agent** — `ops/agent-dataset.py` (NEW)
- Continuously finds new real documents and generates expert Q&A
- Metric: new_questions_per_day, sector_coverage, doc_type_coverage

---

## PHASE PLAN (3 Phases)

### Phase 1: CLEANUP & FOUNDATION (This session)
- [ ] Kill useless agents (docs runner, ingest runner, agentic loop)
- [ ] Delete dead code and old files
- [ ] Set up Redis (Upstash) connection
- [ ] Create unified ingest-pipeline.py
- [ ] Create enrich-worker.py with Redis consumer
- [ ] Test ingestion → Redis → enrichment flow end-to-end
- [ ] Deploy OpenClaw to HF Space
- [ ] Clone Karpathy autoresearch

### Phase 2: PIPELINE QUALITY (Next sessions)
- [ ] Fix Graph pipeline accuracy (tenant_id, Neo4j data quality)
- [ ] Fix Standard pipeline accuracy (BM25 table, BTP data gap)
- [ ] Create Hybrid pipeline (Standard + Graph fusion)
- [ ] Create Expert pipeline (deep research)
- [ ] Deploy agent-improver.py (autoresearch pattern)
- [ ] Set up S11 as dedicated test Space

### Phase 3: SCALE & EXPERTISE (Ongoing)
- [ ] Scale to 100K+ vectors per sector
- [ ] Generate 10K+ expert Q&A per pipeline
- [ ] Achieve accuracy targets (90%+ Standard, 75%+ Graph, 95%+ Quant)
- [ ] Lightning.ai deployment for GPU experiments
- [ ] Continuous autoresearch-style improvement loop

---

## NEW AGENT SYSTEM (Replaces all current agents)

| Agent | Script | Cycle | Part | Metric |
|-------|--------|-------|------|--------|
| **Ingest** | `ops/agent-ingest.py` | 30min | Part 1 | docs_ingested/hr |
| **Enrich** | `ops/agent-enrich.py` | Continuous (Redis) | Part 2 | entities/hr |
| **Pipeline** | `ops/agent-pipeline.py` | 15min | Part 3 | quality_score |
| **Eval** | `eval/eval-blast.py` | 30min | Part 4 | accuracy% |
| **Regression** | `ops/agent-regression.py` | 15min | Part 4 | delta% |
| **Improver** | `ops/agent-improver.py` | 1hr | Part 4 | improvements/session |
| **Dataset** | `ops/agent-dataset.py` | 1hr | Part 5 | new_questions/day |

**Total: 7 agents, each with clear purpose and measurable output.**

---

## FILES TO DELETE (Cleanup list)

### USELESS AGENTS (kill processes first)
- `data/agents/_docs_runner.py`
- `data/agents/_ingest_runner.py`
- `data/agents/_monitor_runner.py`
- `data/agents/_eval_runner.py`
- `data/agents/_pipeline_runner.py`
- `ops/agentic-loop.py`
- `ops/agents-separated.py`

### DEAD/REDUNDANT SCRIPTS
- `ops/ingest-integrated.py`
- `ops/ingest-to-pinecone.py`
- `ops/gws-auth-helper.py`
- `ops/analyze_n8n_executions.py`
- `eval/dashboard-generator.py`
- `eval/docling-fidelity.py`
- `eval/queue-eval-orchestrator.py`
- `eval/continue-eval.py`
- `eval/continuous-eval.py`
- `eval/continuous-judge.py`
- `monetisation-daemon.sh`
- `testing-daemon.sh`

### OLD N8N WORKFLOWS (keep only canonical)
- `n8n/live/standard-rag-v3.4-fixed.json`
- `n8n/live/standard-rag-v3.8-litellm.json`
- `n8n/live/graph-rag-v3.3-fixed.json`
- `n8n/live/graph-rag-v3.4-litellm.json`
- `n8n/live/quantitative.json`
- `n8n/live/orchestrator-minimal.json`
- `n8n/live/orchestrator-v14-llm.json`
- `n8n/live/orchestrator-v14.1-harness.json`

### AGENTIC LOOP DATA (117 auto-generated files, ~2MB)
- `data/agentic-loop/analyses/` (all)
- `data/agentic-loop/baselines/` (all)
- `data/agentic-loop/builds/` (all)
- `data/agentic-loop/collected/` (all)
- `data/agentic-loop/plans/` (all)
- `data/agentic-loop/reports/` (all)

### OLD DOCS
- `docs/archive/` (2.9MB)
