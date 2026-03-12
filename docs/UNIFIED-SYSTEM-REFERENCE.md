# Nomos Sector AI Expert — Unified System Reference

> Last updated: 2026-03-12T15:00Z | Session 106 | Claude Code Opus 4.6

---

## TABLE OF CONTENTS

1. [Mission & Architecture](#1-mission--architecture)
2. [Infrastructure](#2-infrastructure)
3. [Databases (Complete Schema)](#3-databases)
4. [RAG Pipelines](#4-rag-pipelines)
5. [Ingestion & Enrichment System](#5-ingestion--enrichment)
6. [Evaluation System](#6-evaluation-system)
7. [Agent System](#7-agent-system)
8. [LLM Configuration](#8-llm-configuration)
9. [All Scripts Reference](#9-all-scripts-reference)
10. [Sector Configurations](#10-sector-configurations)
11. [Repositories](#11-repositories)
12. [Credentials & Environment](#12-credentials--environment)
13. [Workflow IDs & Webhooks](#13-workflow-ids--webhooks)
14. [Metrics & Current State](#14-metrics--current-state)
15. [Production Readiness Checklist](#15-production-readiness-checklist)
16. [Known Issues & Gaps](#16-known-issues--gaps)

---

## 1. MISSION & ARCHITECTURE

**Mission**: Build the world's best AI sector expert assistant across 4 industries: Finance, BTP (Construction), Juridique (Legal), Industrie (Manufacturing).

**Architecture**: Two independent systems:

```
SYSTEM 1: DATA PIPELINE              SYSTEM 2: RAG PIPELINES
┌─────────────────────────┐           ┌─────────────────────────┐
│ Tavily API              │           │ User Question           │
│   ↓                     │           │   ↓                     │
│ Docling S6 (PDF→text)   │           │ Orchestrator V13        │
│   ↓                     │           │   ↓ routes to:          │
│ Chunking + Embedding    │           │ Standard RAG V3.5       │
│   ↓                     │           │ Graph RAG V3.7          │
│ Pinecone (vectors)      │           │ Quant RAG V3.2          │
│ Neo4j (entities)        │           │   ↓                     │
│ Supabase (metadata)     │           │ LiteLLM S7 (LLM)       │
│   ↓                     │           │   ↓                     │
│ Enrichment V4.0         │           │ Expert Answer           │
└─────────────────────────┘           └─────────────────────────┘
```

**Model Hierarchy**:
| Role | Model | Mechanism |
|------|-------|-----------|
| Analysis, decisions | Opus 4.6 | Direct |
| Batch commands, web search | Sonnet 4.6 | Task(model: "sonnet") |
| Codebase exploration | Haiku 4.5 | Task(model: "haiku") |

---

## 2. INFRASTRUCTURE

### 2.1 VM Google Cloud (Pilotage ONLY)
```
IP: 34.136.180.66
OS: Debian 11
CPU: 1 vCPU | RAM: 969 MB | Disk: 30 GB
Role: Orchestration, scripts, agents — NO n8n, NO compute
```

### 2.2 HF Spaces (3 accounts, 10+ slots)

| Space | Account | Role | URL | Status |
|-------|---------|------|-----|--------|
| S1 (engine) | LBJLincoln | n8n primary — All 4 RAG pipelines + AutoHealer | lbjlincoln-nomos-rag-engine.hf.space | UP |
| S2 (engine-2) | lbjlincoln26 | n8n — shared DB with S1 | lbjlincoln26-nomos-rag-engine-2.hf.space | UP |
| S3 (engine-3) | LBJLincoln | n8n — All 4 pipelines (load balance) | lbjlincoln-nomos-rag-engine-3.hf.space | UP |
| S4 (engine-4) | lbjlincoln26 | n8n — shared DB | lbjlincoln26-nomos-rag-engine-4.hf.space | UP |
| S5 (engine-5) | LBJLincoln | n8n — All 4 pipelines (load balance) | lbjlincoln-nomos-rag-engine-5.hf.space | UP |
| S6 (Docling) | LBJLincoln | Docling document processor | lbjlincoln-nomos-docling-api.hf.space | UP |
| S7 (LiteLLM) | LBJLincoln | LiteLLM proxy — 9 models, 13 providers | lbjlincoln-nomos-rag-engine-7.hf.space | UP |
| S9 (Ingest) | LBJLincoln | Ingestion V4.0 + Enrichment V4.0 | lbjlincoln-nomos-rag-engine-9.hf.space | UP |
| Embeddings | LBJLincoln | Self-hosted Jina v3 (1024 dims) | lbjlincoln-nomos-embeddings-api.hf.space | UP |
| S11 (engine-11) | Nomos42 | n8n — NEW account, deploying | nomos42-nomos-rag-engine-11.hf.space | RESTARTING |

**CRITICAL**: S1, S2, S3, S4, S5 share the SAME n8n database (schema: `n8n_engine_1`). S9 has a SEPARATE database. S11 will be separate.

### 2.3 HF Tokens (3 accounts)
| Account | Token Prefix | Spaces |
|---------|-------------|--------|
| LBJLincoln | hf_fpg... | S1, S3, S5, S7, S9, Embeddings, S6 |
| LBJLincoln | hf_PZo... | Same (backup) |
| Nomos42 | hf_Vra... (HF_TOKEN_3) | S11 |

Note: Neither HF1 nor HF2 can write to lbjlincoln26 Spaces (S2, S4).

---

## 3. DATABASES

### 3.1 Pinecone
| Index | Dimensions | Vectors | Role |
|-------|-----------|---------|------|
| `sectors-e5-multilingual` | 1024 | ~78,000 | PRIMARY — E5 embeddings, growing |
| `website-sectors-jina-1024` | 1024 | 12,536 | SECONDARY — Jina embeddings |
| `sota-rag-jina-1024` | 1024 | 46,000 | ARCHIVE — frozen, do not write |

### 3.2 Neo4j Aura
```
Nodes: 71,890 (33K Entity, 30K SectorDoc, 5.2K Law, 1.6K Org)
Relations: 143,000
Enrichment rate: ~95%
```

### 3.3 Supabase (PostgreSQL)

**Connection**: Use DATABASE_URL env var. **CRITICAL**: Always `SET search_path TO public` after connecting (pooler defaults to `n8n_engine_1` schema).

#### Core Data Tables

| Table | Rows | Purpose |
|-------|------|---------|
| `sector_documents` | 43,414 | Source documents (question/answer/context per sector) |
| `financials` | 225 | Income statements (111 companies, 4 sectors) |
| `balance_sheet` | — | Balance sheet data per company/year |
| `quarterly_revenue` | — | Quarterly revenue breakdowns |
| `sector_financial_tables` | 3,876 | Extracted financial tables (JSON) |
| `enriched_metadata` | — | Entity/relationship enrichment data |
| `community_summaries` | — | Graph community summaries |
| `document_registry` | — | Document processing tracking |
| `processing_queue` | — | Ingestion job queue |

#### Eval Tables

| Table | Rows | Purpose |
|-------|------|---------|
| `eval_question_bank` | 29,564 | All eval questions with tracking stats |
| `eval_results` | ~400+ | Individual question evaluation results |
| `eval_runs` | 4+ | Eval run summaries (batch results) |
| `execution_scores` | 0 | n8n execution-level scoring |
| `pipeline_errors` | 1 | Tracked pipeline errors |
| `question_source_map` | 29,564 | Links questions to their data source |

#### eval_question_bank Schema (key fields)
```
id, question, sector, pipeline, expected_contains, golden_answer,
difficulty, category, language, dataset_source, source_url,
times_asked, times_passed, times_failed, avg_score, avg_latency_ms,
last_status, last_score, score_trend, consecutive_fails
```

#### eval_results Schema (key fields)
```
id, run_id, question_id, question, sector, pipeline,
answer, status (pass/fail), latency_ms, space,
total_score (0-100), accuracy_score (0-20), completeness_score (0-20),
terminology_score (0-20), sources_score (0-20), language_score (0-20),
classification (GOOD/MEDIUM/BAD), judge_reasoning, failure_type
```

#### n8n Internal Tables (shared DB)
```
workflow_entity, execution_entity, credentials_entity,
webhook_entity, user, settings, tag_entity, migrations
```

---

## 4. RAG PIPELINES

### 4.1 Pipeline Specifications

| Pipeline | Webhook | Workflow ID | Version | Function |
|----------|---------|-------------|---------|----------|
| **Standard** | `/webhook/rag-multi-index-v3` | `9FQdtx38JLPiT3Hx` | V3.5 | Vector search → LLM answer |
| **Graph** | `/webhook/ff622742-6d71-4e91-af71-b5c666088717` | `6257AfT1l4FMC6lY` | V3.7 | Neo4j Cypher → Entity relations → LLM |
| **Quantitative** | `/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9` | `cjhEhVs0KV1ExHqX` | V3.2 | SQL generation → Financial data → LLM |
| **Orchestrator** | `/webhook/orchestrator-v2` | `qOSaFFrqO8Jb4VGb` | V13 | Regex routing → delegates to sub-pipeline |

### 4.2 Response Fields
| Pipeline | Answer Field | Notes |
|----------|-------------|-------|
| Standard | `response` or `answer` | |
| Graph | `response` or `answer` | |
| Quantitative | `interpretation` | NOT response/answer — critical bug source |
| Orchestrator | `response` or `answer` | |

### 4.3 Batch Sizes & Timeouts
| Pipeline | Batch | Concurrency | Timeout |
|----------|-------|-------------|---------|
| Standard | 10 | 5 | 90s |
| Graph | 5 | 3 | 120s |
| Quantitative | 3 | 1 | 120s |
| Orchestrator | 2 | 1 | 180s |

### 4.4 Current Accuracy (ALL-TIME)
| Pipeline | Pass/Total | Accuracy | Avg Latency |
|----------|-----------|----------|-------------|
| Standard | 21/36 | 58.3% | 42.5s |
| Graph | 17/21 | 81.0% | 38.2s |
| Quantitative | 76/77 | 98.7% | 31.9s |
| Orchestrator | 1/3 | 33.3% | 83.3s |

### 4.5 Accuracy Targets
| Sector | Standard | Graph | Quant | Orchestrator |
|--------|----------|-------|-------|-------------|
| Finance | >= 90% | >= 75% | >= 95% | >= 85% |
| BTP | >= 85% | >= 70% | >= 80% | >= 75% |
| Juridique | >= 90% | >= 80% | N/A | >= 80% |
| Industrie | >= 85% | >= 70% | >= 80% | >= 75% |

---

## 5. INGESTION & ENRICHMENT

### 5.1 System 1: Data Pipeline

```
Tavily API (search) → Docling S6 (PDF processing) → Chunking → Embedding (Jina/E5)
  → Pinecone (vector store) + Neo4j (entity graph) + Supabase (metadata)
  → Enrichment V4.0 (entity extraction, relation mapping)
```

### 5.2 n8n Workflows (on S9)
| Workflow | ID | Role |
|----------|-----|------|
| Ingestion V4.0 | `nh1D4Up0wBZhuQbp` | Tavily → process → store |
| Enrichment V4.0 | `ORa01sX4xI0iRCJ8` | Docs → entities → Neo4j |

### 5.3 VM Scripts
| Script | Role | Schedule |
|--------|------|----------|
| `ops/continuous-ingest.py` | 24/7 daemon: Tavily + fast-ingest + Docling | 1h cycles |
| `ops/tavily-mass-ingest.py` | Bulk Tavily search + ingest per sector | On-demand |
| `ops/agent-ingest-feed.py` | Feed docs to enrichment pipeline | 1h daemon |
| `ops/clean-ingest.py` | Dedup, clean, validate ingested data | On-demand |

### 5.4 Document Types per Sector
- **Finance**: SEC filings, IFRS, annual reports, 10-K/10-Q, earnings calls, balance sheets
- **BTP**: DTU, Eurocodes, CCTP, AFNOR, BOAMP, RE2020, PPSPS, DQE
- **Juridique**: Codes (civil, commerce, travail), jurisprudence, RGPD, NIS2, AI Act
- **Industrie**: ISO 9001/14001/45001, AMDEC, lean/six sigma, ICPE, Seveso

### 5.5 Current Data Scale
| Metric | Current | Target (6mo) |
|--------|---------|-------------|
| E5 Vectors | ~78,000 | 1,000,000 |
| Supabase Docs | 43,414 | 200,000 |
| Neo4j Nodes | 71,890 | 500,000 |
| Financials | 225 (111 companies) | 1,000+ |

---

## 6. EVALUATION SYSTEM

### 6.1 Question Sources
| Source | Count | Quality |
|--------|-------|---------|
| Auto-generated (standard) | ~10,000 | Medium |
| Auto-generated (graph) | ~5,000 | Medium |
| Auto-generated (quant) | ~10,000 | Medium |
| Tavily real-world | ~500 | High |
| Expert-generated (LLM+Tavily) | Growing | High |
| **Total** | **29,564** | |

### 6.2 LLM Judge
- **Script**: `eval/llm_judge.py`
- **Model**: LiteLLM S7 `smart` group
- **Scoring**: accuracy (0-100), completeness (0-100), terminology (0-100)
- **DB storage**: Scores divided by 5 (0-20 constraint), classification GOOD/MEDIUM/BAD
- **Fallback**: Keyword matching if LLM unavailable
- **Features**: Number format equivalence, multilingual, semantic matching

### 6.3 Eval Scripts
| Script | Purpose |
|--------|---------|
| `eval/eval-blast.py` | High-speed eval (20-50 questions, all pipelines) |
| `eval/full-system-test.py` | 12-component infrastructure test |
| `eval/generate-expert-questions.py` | Tavily+LLM expert question generation |
| `eval/generate-standard-questions.py` | Bulk standard question generation |
| `eval/generate-graph-questions.py` | Graph-specific question generation |
| `eval/generate-quant-questions.py` | Quantitative question generation |
| `eval/mass-eval.py` | Large-scale eval runs |
| `eval/continuous-eval.py` | Continuous eval daemon |
| `eval/expert-eval.py` | Expert-level evaluation |
| `eval/llm-judge-rescore.py` | Re-score existing results with LLM judge |
| `eval/dashboard-generator.py` | Generate HTML dashboard from live data |

---

## 7. AGENT SYSTEM

### 7.1 Two-System Architecture

**SYSTEM 1: DATA PIPELINE AGENTS**
| Agent | Script | Cycle | Objective |
|-------|--------|-------|-----------|
| INGEST | `ops/continuous-ingest.py` | 30min | Grow E5 vectors to 100K |
| ENRICH | `ops/agent-ingest-feed.py` | 30min | 95%+ enrichment rate |
| QUALITY | `eval/full-system-test.py` | One-shot | Monitor data quality |

**SYSTEM 2: RAG PIPELINE AGENTS**
| Agent | Script | Cycle | Objective |
|-------|--------|-------|-----------|
| EVAL | `eval/eval-blast.py` | 10min | Track accuracy all pipelines |
| REGRESSION | `ops/agent-regression.py` | 15min | Detect >5% accuracy drops |
| FIXER | `ops/agent-fixer.py` | 20min | Diagnose chronic failures |
| MONITOR | `ops/monitor.py` | 5min | Health check all Spaces |

### 7.2 Agent Management
```bash
python3 ops/agents-separated.py launch all       # Launch all agents
python3 ops/agents-separated.py launch system1    # Data pipeline agents
python3 ops/agents-separated.py launch system2    # RAG pipeline agents
python3 ops/agents-separated.py status            # Show status
python3 ops/agents-separated.py stop all          # Stop all
```

### 7.3 Agentic Loop
- **Script**: `ops/agentic-loop.py` (125KB, comprehensive)
- **Cycle**: 30min intervals
- **Phases**: Plan → Build → Baseline → Collect → Analyze → Report
- **Current**: Cycle 19+, runs continuously
- **Limitation**: Can diagnose but cannot modify n8n workflows directly

### 7.4 Currently Running Agents (S106)
```
monitor.py (2 instances)     — 5min health checks
continuous-ingest.py         — 1h ingestion cycles
agent-fixer.py               — 1h fix analysis
agent-ingest-feed.py         — 1h enrichment feed
agent-regression.py          — 15min regression checks
eval-blast.py                — 30min eval runs (50 questions)
tavily-mass-ingest.py (×2)   — BTP + Finance bulk ingest
5 v1 agents (_runner scripts) — monitor, eval, ingest, pipeline, docs
```

---

## 8. LLM CONFIGURATION

### 8.1 LiteLLM S7 Proxy
```
URL: https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/chat/completions
Key: Bearer sk-litellm-nomos-2026
```

### 8.2 Model Groups
| Group | Providers (fallback order) | Usage |
|-------|---------------------------|-------|
| `smart` | OpenRouter llama-70b → qwen-235b → Gemini Flash → Groq | ALL pipelines |
| `fast` | OpenRouter trinity → gemma-27b → Gemini Flash | Quick tasks |
| `default` | OpenRouter trinity → Gemini → Groq | Fallback |

### 8.3 Provider Keys
All keys managed via LiteLLM config. Direct keys in .env.local:
- OPENROUTER_API_KEY (primary)
- GROQ_API_KEY (fallback)
- GOOGLE_API_KEY (Gemini)
- JINA_API_KEY (embeddings)
- COHERE_API_KEY (reranking)

---

## 9. ALL SCRIPTS REFERENCE

### 9.1 Operations (ops/)
| Script | Lines | Purpose |
|--------|-------|---------|
| `agents.py` | 37K | V1 agent launcher (5 agents) |
| `agents-v2.py` | 10K | V2 agent launcher (4 workers) |
| `agents-separated.py` | 12K | V3 separated system launcher |
| `agentic-loop.py` | 125K | Autonomous improvement loop |
| `monitor.py` | — | Health monitoring daemon |
| `continuous-ingest.py` | 13K | 24/7 ingestion daemon |
| `agent-fixer.py` | 12K | Failure diagnosis agent |
| `agent-ingest-feed.py` | 13K | Enrichment feed agent |
| `agent-regression.py` | 10K | Regression detection agent |
| `analyze_n8n_executions.py` | 13K | n8n execution analysis |
| `auto-healer-cli.py` | 8K | CLI for auto-healer workflow |
| `clean-ingest.py` | 19K | Data cleaning/dedup |
| `cleanup-workflows.py` | 16K | Remove duplicate workflows |
| `deploy-standard-v35.py` | 10K | Deploy Standard RAG |
| `deploy-graph-orch-litellm.py` | 31K | Deploy Graph + Orchestrator |
| `deploy-error-trigger.py` | 16K | Deploy error handling |
| `deploy-eval-judge.py` | 24K | Deploy eval judge workflow |

### 9.2 Evaluation (eval/)
| Script | Lines | Purpose |
|--------|-------|---------|
| `eval-blast.py` | 22K | High-speed multi-pipeline eval |
| `full-system-test.py` | 20K | 12-component system test |
| `llm_judge.py` | 10K | LLM-based semantic evaluation |
| `generate-expert-questions.py` | 13K | Tavily+LLM expert questions |
| `generate-standard-questions.py` | 55K | Standard question generation |
| `generate-graph-questions.py` | 45K | Graph question generation |
| `generate-quant-questions.py` | 26K | Quant question generation |
| `mass-eval.py` | 10K | Large-scale eval |
| `mass-question-generator.py` | 77K | Bulk question generation |
| `continuous-eval.py` | 27K | Continuous eval daemon |
| `continuous-judge.py` | 64K | Continuous judging |
| `expert-eval.py` | 82K | Expert-level evaluation |
| `expert-discovery.py` | 59K | Auto-discover eval questions |
| `dashboard-generator.py` | 14K | HTML dashboard generator |
| `docling-fidelity.py` | 24K | Document processing quality |

---

## 10. SECTOR CONFIGURATIONS

### 10.1 Config Files
Each sector has `sectors/{sector}/config.json` with:
- Eval question templates
- Expected answer patterns
- Document type definitions
- Quality thresholds

### 10.2 Eval Datasets
```
sectors/eval-datasets/
├── sector-full-eval-extended.json    (11.5MB, comprehensive)
├── sector-full-eval.json             (148KB, core)
├── sector-smoke-test.json            (7KB, quick validation)
├── standard-eval-generated.json      (2.9MB)
├── graph-eval-generated.json         (2.0MB)
├── quant-eval-generated.json         (6.4MB)
├── tavily-real-world-tests.json      (196KB)
├── expert-*-generated.json           (per sector, growing)
└── real-documents-to-ingest.json     (112KB)
```

---

## 11. REPOSITORIES

| Repo | Role | Status | Key Files |
|------|------|--------|-----------|
| **mon-ipad** | Tour de controle, eval, ops, MCP | ACTIVE | CLAUDE.md, ops/, eval/, sectors/ |
| **rag-data-ingestion** | Ingestion engine, Docling, 100+ doc types | ACTIVE | — |
| **rag-website** | User-facing chatbot, Next.js | ACTIVE | — |
| **rag-dashboard** | Dashboard, metrics visualization | ACTIVE | docs/ (GitHub Pages) |
| **rag-storage** | Archive LFS + benchmark data | ARCHIVE | — |
| **rag-pme-connectors** | Next.js 15, 15 apps | ARCHIVE | — |
| **rag-tests** | Merged into mon-ipad | ARCHIVE | — |

---

## 12. CREDENTIALS & ENVIRONMENT

All credentials in `.env.local` (NEVER commit to git).

### 12.1 Key Variables
```
DATABASE_URL          — Supabase PostgreSQL connection
PINECONE_API_KEY      — Pinecone vector database
PINECONE_E5_HOST      — E5 index host
NEO4J_URI             — Neo4j Aura connection
NEO4J_USERNAME        — Neo4j user
NEO4J_PASSWORD        — Neo4j password
OPENROUTER_API_KEY    — OpenRouter LLM access
GROQ_API_KEY          — Groq LLM access
GOOGLE_API_KEY        — Google Gemini access
JINA_API_KEY          — Jina embeddings (expired, using self-hosted)
COHERE_API_KEY        — Cohere reranking
TAVILY_API_KEY        — Tavily search API
LITELLM_MASTER_KEY    — LiteLLM proxy auth
N8N_API_KEY           — n8n REST API key
N8N_PASSWORD          — n8n admin password
HF_TOKEN              — HuggingFace (LBJLincoln)
HF_TOKEN_2            — HuggingFace (LBJLincoln backup)
HF_TOKEN_3            — HuggingFace (Nomos42)
```

### 12.2 n8n Authentication
- REST API: Header `X-N8N-API-KEY: {N8N_API_KEY}`
- MCP: Bearer JWT with `aud=mcp-server-api` (different from REST API key)
- Login: `POST /rest/login` with `emailOrLdapLoginId` field

---

## 13. WORKFLOW IDS & WEBHOOKS

### 13.1 Active Workflows (S1/S3/S5 shared DB)
| Pipeline | Workflow ID | Active | Webhook |
|----------|-----------|--------|---------|
| Standard RAG V3.5 | `9FQdtx38JLPiT3Hx` | YES | `/webhook/rag-multi-index-v3` |
| Graph RAG V3.7 | `6257AfT1l4FMC6lY` | YES | `/webhook/ff622742-...` |
| Quant RAG V3.2 | `cjhEhVs0KV1ExHqX` | YES | `/webhook/3e0f8010-...` |
| Orchestrator V13 | `qOSaFFrqO8Jb4VGb` | YES | `/webhook/orchestrator-v2` |
| Auto-Healer V1.2 | `Yqw7Pzn0e7m0C6i3` | YES | Timer (10min) |
| Error Trigger | `AH3eXOmgxt5cOd93` | YES | Error handler |

### 13.2 Active Workflows (S9 separate DB)
| Pipeline | Workflow ID | Active | Webhook |
|----------|-----------|--------|---------|
| Ingestion V4.0 | `nh1D4Up0wBZhuQbp` | YES | `/webhook/ingestion-v4` |
| Enrichment V4.0 | `ORa01sX4xI0iRCJ8` | YES | `/webhook/enrichment-v4` |

### 13.3 Total Workflows on S1
- 100 workflows total (from historical iterations)
- 6 ACTIVE, 94 inactive (legacy/duplicate)
- Use `ops/cleanup-workflows.py` to clean duplicates

---

## 14. METRICS & CURRENT STATE

### 14.1 Pipeline Accuracy (24h window, S106)
| Pipeline | Sector | Accuracy | Notes |
|----------|--------|----------|-------|
| Quantitative | Finance | 97.0% | STRONG |
| Quantitative | BTP | 100% | |
| Quantitative | Industrie | 100% | |
| Quantitative | Juridique | 100% | |
| Graph | Finance | 100% | |
| Graph | Juridique | 100% | |
| Graph | BTP | 50% | WEAK |
| Graph | Industrie | 40% | WEAK |
| Standard | Finance | 50% | NEEDS WORK |
| Standard | BTP | 55.6% | NEEDS WORK |
| Standard | Industrie | 50% | NEEDS WORK |
| Standard | Juridique | 66.7% | NEEDS WORK |
| Orchestrator | Finance | 0% | CRITICAL — needs routing fix |
| Orchestrator | BTP | 0% | CRITICAL |

### 14.2 Infrastructure Health (S106)
- 9/9 Spaces UP
- 4/4 Pipelines responding
- 6/6 Critical workflows ACTIVE
- 16+ agents running
- Ingestion daemon active (2 sectors)
- Eval blast running (50q/30min)
- Regression monitoring active

---

## 15. PRODUCTION READINESS CHECKLIST

### Phase 1: Foundation (MOSTLY DONE)
- [x] 4 RAG pipelines working
- [x] LLM via LiteLLM proxy (multi-provider fallback)
- [x] Self-hosted embeddings
- [x] Eval framework with LLM judge
- [x] 29,564 eval questions
- [x] Continuous monitoring
- [x] Auto-healer workflow
- [ ] All pipelines duplicated across 3+ Spaces
- [ ] Expert-generated eval questions

### Phase 2: Quality (IN PROGRESS)
- [ ] Standard pipeline >= 85% accuracy all sectors
- [ ] Graph pipeline >= 70% accuracy all sectors
- [ ] Orchestrator >= 75% accuracy all sectors
- [x] Quant pipeline >= 95% accuracy
- [ ] Source citation >= 90%
- [ ] Response time <= 30s average
- [ ] 100+ document types per sector

### Phase 3: Scale (PLANNED)
- [ ] 100K E5 vectors (currently 78K)
- [ ] Redis queue for parallel ingestion
- [ ] Dashboard live auto-refresh
- [ ] Cross-Space load balancing
- [ ] 1M documents target

### Phase 4: Monetisation (INFRASTRUCTURE READY)
- [ ] Revenue from products
- [ ] Distribution channels active
- [ ] User-facing chatbot deployed

---

## 16. KNOWN ISSUES & GAPS

1. **Standard pipeline accuracy 50-67%** — Needs better retrieval, more sector data
2. **Orchestrator 0% accuracy** — Routing works but answer extraction may be broken
3. **Only 2/6 workflows were active on S1** — Fixed S106, but needs monitoring
4. **Nomos42 S11 in RUNTIME_ERROR** — Secrets set, restart triggered, awaiting boot
5. **S9 API key different** — Cannot manage S9 workflows from VM
6. **100 workflows on S1** — 94 inactive legacy, should clean
7. **No Redis queue** — Ingestion sequential (Upstash creds exist)
8. **Dashboard only static HTML** — Needs auto-refresh mechanism
9. **Expert questions** — Being generated via Tavily+LLM (S106)
10. **Quantitative `interpretation` field** — All scripts now handle it, but easy to forget

---

*This document is the single source of truth for the Nomos Sector AI Expert system. Updated each session.*
