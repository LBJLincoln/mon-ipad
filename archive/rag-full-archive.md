# RAG Pipeline System -- Complete Archive

> **ARCHIVED: 2026-03-17. RAG system decommissioned to focus on NBA Quant AI + THE FORGE. All data preserved in databases (Supabase, Neo4j, Pinecone) -- read-only.**

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Webhook URLs](#2-webhook-urls)
3. [Workflow IDs](#3-workflow-ids)
4. [Database Schemas](#4-database-schemas)
5. [LLM Config](#5-llm-config)
6. [HF Spaces](#6-hf-spaces)
7. [Eval System](#7-eval-system)
8. [Sector Configs](#8-sector-configs)
9. [Ingestion System](#9-ingestion-system)
10. [Key Metrics](#10-key-metrics)
11. [Debug Knowledge](#11-debug-knowledge)

---

## 1. Architecture Overview

### Mission Statement

Build the world's best AI sector expert assistant across 4 sectors (Finance, BTP, Juridique, Industrie) using 4 specialized RAG pipelines, each designed to become an unbeatable expert in its domain.

### Global Architecture

```
VM Google Cloud (34.136.180.66) -- PERMANENT (PILOTAGE ONLY)
  Debian 11 | 1 vCPU | 969 MB RAM | 30 GB disk
  Claude Code (Termius terminal) -- pilotage + eval orchestration
  MCP Servers: ~6MB total (neo4j, pinecone, HF, jina, cohere)
  NO n8n, NO PostgreSQL, NO Redis on VM (removed Session 42)

HF Spaces -- DISTRIBUTED EXECUTION (all compute)
  9 RAG-related Spaces across 2 HuggingFace accounts (LBJLincoln + LBJLincoln26)
  Each Space: cpu-basic, 16GB RAM, $0

Vercel -- PRODUCTION SITES
  nomos-ai-pied.vercel.app (4 sectors)
  nomos-dashboard-alexis-morets-projects.vercel.app

GitHub -- 7 repos (5 active + 2 archive)
  mon-ipad (tour de controle), rag-data-ingestion, rag-website,
  rag-dashboard, rag-storage (archive), rag-pme-connectors (archive),
  rag-tests (merged into mon-ipad)
```

### The 4 RAG Pipelines

#### Standard RAG (V3.8)

- **Role**: Classic vector search across sector documents
- **How it works**: Query -> Jina/E5 embedding -> Pinecone vector search (multi-index: `website-sectors-jina-1024` + `sota-rag-jina-1024`) -> Context retrieval from Supabase -> LLM generation via LiteLLM proxy
- **Databases**: Pinecone (vector search) + Supabase (document store)
- **Avg response time**: 41-50s
- **Last known accuracy**: Standard 70.7% (against 90% target), Finance sector 85.2%

#### Graph RAG (V3.5)

- **Role**: Entity relationship traversal for multi-hop reasoning queries
- **How it works**: Query -> Keyword extraction -> Neo4j Cypher queries (entity search, relationship traversal, community summaries) -> Self-hosted Jina embeddings (1024 dims) -> LLM generation via LiteLLM
- **Databases**: Neo4j Aura (graph traversal) + self-hosted Jina Space (embeddings)
- **Avg response time**: 27-86s
- **Last known accuracy**: 45.9% (against 75% target)
- **Key limitation**: Entity disambiguation in Neo4j was weak; Jina API keys expired so it relied on self-hosted embeddings Space

#### Quantitative RAG (V3.2)

- **Role**: SQL-based queries over structured financial/numerical data
- **How it works**: Query -> Schema introspection (Supabase) -> LLM-generated SQL via LiteLLM -> SQL validation (multi-strategy: JSON, markdown, raw SELECT extraction) -> Supabase exec_sql RPC -> Result formatting
- **Databases**: Supabase (`sector_financial_data`, `sector_financial_tables`)
- **Avg response time**: 11-87s
- **Last known accuracy**: 99.1% on benchmark data (against 95% target)
- **Key gotchas**: tenant_id MUST be 'benchmark' (NOT 'default'); use Postgres credential `b44avEJtnkw46GL6` (NOT `cH96tQ3I9uIHqiiq`); SQL Validator must handle both JSON and markdown LLM responses

#### Orchestrator (V13)

- **Role**: Intelligent routing -- classifies queries and delegates to the appropriate sub-pipeline
- **How it works**: Query -> Regex-based intent classifier -> Routes to Standard, Graph, or Quant via HTTP Request to their webhooks (NOT executeWorkflow) -> Aggregates and returns response
- **Databases**: Meta-pipeline (no direct DB access; delegates to sub-pipelines)
- **Avg response time**: ~52s
- **Last known accuracy**: 60% (against 85% target; small sample)
- **Critical design decision**: Uses `httpRequest` POST to sub-pipeline webhooks, NOT `executeWorkflow` (FIX-34: executeWorkflow + respondToWebhook returns empty body)

### Support Workflows

- **Auto-Healer (V1.2)**: Runs every 10 minutes on S1, pings all 4 Spaces' webhooks, logs errors
- **Error Trigger Handler (V1.0)**: Catches execution errors across all workflows, logs to Supabase
- **Ingestion (V4.0)**: Docling PDF processing -> chunking -> Pinecone + Supabase upserts
- **Enrichment (V4.0)**: Neo4j entity enrichment from ingested documents

### 5 Operational Agents

| Agent | Script | Cycle | Role |
|-------|--------|-------|------|
| MONITOR | `ops/monitor.py --loop 300` | 5min | Health check, error detection, JSONL logging |
| EVAL | `eval/quick-test.py` | After each change | Accuracy baseline, before/after comparison |
| PIPELINE | Manual (Claude Code) | On-demand | 1 fix -> test -> push or revert |
| INGEST | `ops/fast-ingest.py` | Batch | E5 vectors, Exa.AI, PDF, Neo4j enrichment |
| DOCS | Manual | After milestone | Update PROJECT-STATE, DEBUG-PLAYBOOK |

---

## 2. Webhook URLs

All webhooks accept POST with `{"query": "...", "sector": "...", "disable_acl": true}`.

**IMPORTANT**: The field name is `query` (NOT `question`). Using `question` causes VALIDATION_ERROR.

### Primary Host

```
N8N_HOST = https://lbjlincoln-nomos-rag-engine.hf.space
```

### Pipeline Webhooks

| Pipeline | Full URL | Status at Archive |
|----------|----------|-------------------|
| **Standard RAG V3.8** | `{N8N_HOST}/webhook/rag-multi-index-v3` | WORKING |
| **Graph RAG V3.5** | `{N8N_HOST}/webhook/ff622742-6d71-4e91-af71-b5c666088717` | WORKING |
| **Quantitative V3.2** | `{N8N_HOST}/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9` | WORKING |
| **Orchestrator V13** | `{N8N_HOST}/webhook/orchestrator-v2` | WORKING |

### Verified curl Examples

```bash
# Standard RAG
curl -s -X POST "$N8N_HOST/webhook/rag-multi-index-v3" \
  -H "Content-Type: application/json" \
  -d '{"query": "Quels sont les ratios financiers pour evaluer la solvabilite?", "sector": "finance", "disable_acl": true}'

# Graph RAG
curl -s -X POST "$N8N_HOST/webhook/ff622742-6d71-4e91-af71-b5c666088717" \
  -H "Content-Type: application/json" \
  -d '{"query": "Quelles entites sont liees aux normes IFRS?", "sector": "finance", "disable_acl": true}'

# Quantitative
curl -s -X POST "$N8N_HOST/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9" \
  -H "Content-Type: application/json" \
  -d '{"query": "Quelles sont les 5 entreprises avec le plus gros revenu?", "sector": "finance", "disable_acl": true}'

# Orchestrator
curl -s -X POST "$N8N_HOST/webhook/orchestrator-v2" \
  -H "Content-Type: application/json" \
  -d '{"query": "Comment fonctionne la responsabilite delictuelle?", "sector": "juridique", "disable_acl": true}'
```

### Load-Balanced Hosts (10 HF Spaces)

All pipelines could be called on any of these hosts (they share the same database backends):

| Space | URL |
|-------|-----|
| S1 (primary) | `https://lbjlincoln-nomos-rag-engine.hf.space` |
| S2 | `https://lbjlincoln26-nomos-rag-engine-2.hf.space` |
| S3 | `https://lbjlincoln-nomos-rag-engine-3.hf.space` |
| S4 | `https://lbjlincoln26-nomos-rag-engine-4.hf.space` |
| S5 | `https://lbjlincoln-nomos-rag-engine-5.hf.space` |
| S9 | `https://lbjlincoln-nomos-rag-engine-9.hf.space` |

### n8n REST API Access

n8n on HF Spaces does NOT support API key auth (JWT invalidates on rebuild). Must use cookie-based auth:

```bash
# Login (get session cookie)
curl -s -c /tmp/n8n-cookies.txt -X POST "$N8N_HOST/rest/login" \
  -H "Content-Type: application/json" \
  -d '{"emailOrLdapLoginId":"ci@nomos.ai","password":"CI-Nomos-2026!"}'

# List workflows
curl -s -b /tmp/n8n-cookies.txt "$N8N_HOST/rest/workflows"
```

Helper script: `python3 scripts/n8n-api.py list|get|deploy|activate`

---

## 3. Workflow IDs

### RAG Pipeline Workflows (4)

| Pipeline | Workflow ID | Version | Name | Spaces |
|----------|-------------|---------|------|--------|
| **Standard** | `9FQdtx38JLPiT3Hx` (also `TmgyRP20N4JFd9CB` on some Spaces) | V3.8 | Standard RAG (E5+LiteLLM, multi-index) | S1, S3, S5, S11 |
| **Graph** | `6257AfT1l4FMC6lY` | V3.5 | Graph RAG (V3 keyword Cypher + LiteLLM) | S1, S3, S5 |
| **Quantitative** | `cjhEhVs0KV1ExHqX` | V3.2 | Quantitative (LiteLLM, SQL generation) | S1, S3, S5 |
| **Orchestrator** | `qOSaFFrqO8Jb4VGb` | V13 | Orchestrator (regex routing, delegates to sub-pipelines) | S1, S3, S5, S11 |

### Support Workflows (6)

| Workflow | ID | Version | Status |
|----------|----|---------|--------|
| Auto-Healer | `Yqw7Pzn0e7m0C6i3` | V1.2 | ACTIVE (S1/S3/S5) -- 10min cycle |
| Error Trigger Handler | `AH3eXOmgxt5cOd93` | V1.0 | ACTIVE (all Spaces) -- errors to Supabase |
| Ingestion | `nh1D4Up0wBZhuQbp` | V4.0 | ACTIVE (S9) -- Docling + Pinecone + Supabase |
| Enrichment | `ORa01sX4xI0iRCJ8` | V4.0 | ACTIVE (S9) -- Neo4j entity enrichment |
| Dashboard | N/A | N/A | ACTIVE (S1) |
| Debug | N/A | N/A | ACTIVE (S1) |

### PME Workflows (3)

| Workflow | Description | Status |
|----------|-------------|--------|
| PME Gateway | Main entry point | ACTIVE |
| PME Slack Connector | Slack integration | ACTIVE |
| PME Gmail Connector | Gmail integration | ACTIVE |

### n8n Credential IDs (on S1)

| Credential | Type | ID | Pipeline |
|------------|------|----|----------|
| OpenRouter (Standard) | httpHeaderAuth | `VTFur78v4L4wWEk9` | Standard |
| OpenRouter (Graph) | httpHeaderAuth | `8zKa8MqNEHsbVGKp` | Graph |
| OpenRouter (Quantitative) | httpHeaderAuth | `lGI3u8XGRIwaFq1e` | Quantitative |
| OpenRouter (Orchestrator) | httpHeaderAuth | `S7i3kAtU5ZqIVCYS` | Orchestrator |
| LiteLLM Proxy Key | httpHeaderAuth | `mStiDbYim2aZ0cMq` | Ingestion + Enrichment |
| Jina API Key | httpHeaderAuth | `I68x3RvlHJZyQuR6` | Embeddings (key 2) |
| Supabase Postgres (WORKING) | postgres | `b44avEJtnkw46GL6` | SQL queries |
| Supabase Postgres (BROKEN) | postgres | `cH96tQ3I9uIHqiiq` | DO NOT USE |
| Pinecone API Key | httpHeaderAuth | `US6Cxlgs8LfyZWss` | Vector search |

Note: 209 credentials existed in n8n (massive duplication from 10 HF Spaces sharing same Postgres).

---

## 4. Database Schemas

### Pinecone (Free Tier -- Serverless)

**4 indexes (out of 5 max on free tier):**

| Index | Vectors | Dimensions | Model | Status | Role |
|-------|---------|------------|-------|--------|------|
| `website-sectors-jina-1024` | ~43,000 | 1024 | Jina v3 | **PRIMARY** | Sector vectors (BTP, Finance, Industrie, Juridique) |
| `sota-rag-jina-1024` | ~35,000 | 1024 | Jina v3 | **ARCHIVE** (frozen, do not write) | Legacy benchmark vectors |
| `sota-rag-phase2-graph` | 1,248 | 1024 | E5-large | OK | Phase 2 graph data |
| `sota-rag` | 10,411 | 1024 | Cohere | LEGACY | Original Cohere index |

**E5 vectors total across all indexes**: ~78,000 (target was 100K)

**Namespace isolation**: Per-dataset (finqa, musique, hotpotqa, etc.) and per-sector.

**Metadata fields**: `sector`, `tenant_id`, `doc_type`, `source`, `title`, `chunk_index`

**Free tier limits**: 100K vectors per index, 5 indexes max, 10GB storage, unlimited retention.

### Neo4j Aura (Free Tier)

**Connection**: `neo4j+s://38c949a2.databases.neo4j.io`

**HTTP Query API**: `https://38c949a2.databases.neo4j.io/db/neo4j/query/v2`

**CRITICAL**: The old HTTP Transaction API (tx/commit) returns 403 on Aura. Always use `/db/neo4j/query/v2`.

**CRITICAL**: Neo4j HTTP Query API is DEAD for some operations. Use Bolt driver when possible.

| Node Type | Count | Description |
|-----------|-------|-------------|
| Entity | 33,299 | Named entities (companies, standards, laws, organizations) |
| SectorDoc | 30,143 | Sector document references |
| Law | 5,232 | Legal articles and codes |
| Org | 1,615 | Organizations |
| Company | 1,600 | Company entities |
| **Total nodes** | **~71,890** | (limit: 200K) |
| **Total relationships** | **76,717** | (limit: 400K) |

**Node labels**: Entity, Document, Community, Law, Org, Company, SectorDoc

**Key indexes**: On `tenant_id`, `name`, `sector`

**Enrichment level**: 95% of nodes had enriched metadata.

**Free tier behavior**: Pauses after 3 days of inactivity (send a query to wake it).

### Supabase (Free Tier)

**Project ref**: `ayqviqmxifzmhphiqfmj`

**URL**: `https://ayqviqmxifzmhphiqfmj.supabase.co`

**Pooler**: `aws-1-eu-west-1.pooler.supabase.com:6543`

**Key tables**:

| Table | Rows | Description |
|-------|------|-------------|
| `sector_documents` | ~43,000 | Documents across 4 sectors (id field NOT NULL required) |
| `eval_question_bank` | ~29,564 | Evaluation questions with `times_asked`, `score_trend`, `consecutive_fails` |
| `sector_financial_tables` | 3,876 | Structured financial tables |
| `sector_financial_data` | 225 | Financial data for 111 companies across 4 sectors |
| `eval_results` | Variable | Per-question evaluation results tracking |

**Critical rules**:
- `tenant_id` MUST be `'benchmark'` (NEVER `'default'`)
- Use Pooler endpoint (port 6543) for n8n to avoid connection exhaustion
- `exec_sql` RPC for dynamic SQL generation (Quantitative pipeline)
- ALWAYS `SET search_path TO public` after psycopg2.connect() (pooler defaults to `n8n_engine_1` schema)
- `sector_documents` requires `id` field -- NOT NULL, must be included in inserts
- Free tier pauses after 1 week of inactivity

**Supabase schema extended columns** (added during Session 106):
- `golden_answer` -- Golden reference answers for eval questions
- `source_url` -- Source URLs for expert questions
- `category` -- Question categorization

---

## 5. LLM Config

### LiteLLM Proxy (Space S7)

**URL**: `https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/chat/completions`

**Master Key**: `Bearer sk-litellm-nomos-2026`

**Config file**: `hf-space/litellm-proxy/litellm-config.yaml`

**Key pool**: 12+ keys (7 OpenRouter, 5 Groq, 1 Gemini) with auto-rotation

**ALL 4 RAG pipelines route through LiteLLM** -- no direct LLM API calls.

### Model Groups

| Group | Providers/Fallback Chain | Usage |
|-------|--------------------------|-------|
| `smart` (13 providers) | OpenRouter llama-70b -> qwen-235b -> Gemini Flash -> Groq | **ALL pipelines** (primary) |
| `fast` (11 providers) | OpenRouter trinity -> gemma-27b -> Gemini Flash | Quick tasks |
| `default` (10 providers) | OpenRouter trinity -> Gemini -> Groq | Fallback |
| `llama-70b` (12 providers) | OpenRouter + Groq (5 keys) | Heavy reasoning |
| `gemma-27b` (7 providers) | OpenRouter only | Fast, lightweight |
| `trinity` (7 providers) | OpenRouter arcee-ai/trinity | Entity extraction |
| `qwen-235b` (7 providers) | OpenRouter qwen | Complex reasoning |
| `gemini-flash` (1 provider) | Google Gemini direct | Single provider |
| `groq-llama` (5 providers) | Groq only | AVOID: no fallback, rate-limited |

### Model Assignment by Task

| Task | Model | Variable |
|------|-------|----------|
| SQL generation | meta-llama/llama-3.3-70b-instruct:free | `LLM_SQL_MODEL` |
| Fast operations | google/gemma-3-27b-it:free | `LLM_FAST_MODEL` |
| Intent classification | meta-llama/llama-3.3-70b-instruct:free | `LLM_INTENT_MODEL` |
| Task planning | meta-llama/llama-3.3-70b-instruct:free | `LLM_PLANNER_MODEL` |
| Agent reasoning | meta-llama/llama-3.3-70b-instruct:free | `LLM_AGENT_MODEL` |
| HyDE generation | meta-llama/llama-3.3-70b-instruct:free | `LLM_HYDE_MODEL` |
| Entity extraction | arcee-ai/trinity-large-preview:free | `LLM_EXTRACTION_MODEL` |
| Community summaries | arcee-ai/trinity-large-preview:free | `LLM_COMMUNITY_MODEL` |
| Lightweight tasks | google/gemma-3-27b-it:free | `LLM_LITE_MODEL` |

**Total LLM cost**: $0 (all free-tier models via OpenRouter + Groq + Gemini)

### API Keys

- **OpenRouter**: 6 keys across 3 accounts (~120 req/min aggregate). Per-pipeline keys: `OPENROUTER_KEY_STANDARD`, `OPENROUTER_KEY_GRAPH`, `OPENROUTER_KEY_QUANTITATIVE`, `OPENROUTER_KEY_ORCHESTRATOR`
- **Groq**: 5 keys (`GROQ_API_KEY` through `GROQ_API_KEY_5`), ~30 RPM per key
- **Gemini**: 1 key (Google direct)
- **Jina AI**: 2 keys (key 1 EXHAUSTED, key 2 active `jina_63fa...`). Self-hosted Space preferred.
- **Cohere**: Trial tier EXHAUSTED. Backup only.

### Fallback Chain Behavior

When a provider hits rate limits (429), LiteLLM automatically rotates to the next provider in the chain: OpenRouter -> Gemini -> Groq. This is transparent to the pipelines.

---

## 6. HF Spaces

### RAG-Related Spaces (9)

| Space | ID | Account | Role | URL | Status at Archive |
|-------|-----|---------|------|-----|-------------------|
| **S1** (engine) | Primary n8n | LBJLincoln | All 4 RAG pipelines + AutoHealer + 10 workflows | `lbjlincoln-nomos-rag-engine.hf.space` | UP |
| **S2** (engine-2) | Secondary n8n | LBJLincoln26 | Load balance, shared DB with S1 | `lbjlincoln26-nomos-rag-engine-2.hf.space` | UP |
| **S3** (engine-3) | Tertiary n8n | LBJLincoln | All 4 pipelines (load balance) | `lbjlincoln-nomos-rag-engine-3.hf.space` | UP |
| **S4** (engine-4) | Quaternary n8n | LBJLincoln26 | Load balance, shared DB | `lbjlincoln26-nomos-rag-engine-4.hf.space` | UP |
| **S5** (engine-5) | Quinary n8n | LBJLincoln | All 4 pipelines (load balance) | `lbjlincoln-nomos-rag-engine-5.hf.space` | UP |
| **S6** (Docling) | Document processor | LBJLincoln | Docling PDF/DOCX extraction | `lbjlincoln-nomos-docling-api.hf.space` | UP (frequently DOWN/timeout) |
| **S7** (LiteLLM) | LLM proxy | LBJLincoln | 9 models, 13-provider fallback | `lbjlincoln-nomos-rag-engine-7.hf.space` | UP |
| **S9** (engine-9) | Ingestion n8n | LBJLincoln | Ingestion V4.0 + Enrichment V4.0 | `lbjlincoln-nomos-rag-engine-9.hf.space` | UP |
| **Embeddings** | Jina embeddings | LBJLincoln | Self-hosted Jina v3, 1024 dims | `lbjlincoln-nomos-embeddings-api.hf.space` | UP |

### Nomos42 Account Spaces (5) -- Deployed Session 106

| Space | Role | Status |
|-------|------|--------|
| S11 (engine-11) | n8n: Standard + Orchestrator | RUNNING |
| Embeddings-2 | Jina v3 duplicate | RUNNING |
| Docling-2 | Gradio Docling duplicate | RUNNING |
| LiteLLM-2 | LiteLLM proxy duplicate | RUNNING |
| Worker-2 | n8n instance (no workflows loaded) | RUNNING |

### Space Technical Details

- **Tier**: cpu-basic (2 vCPU, 16GB RAM, $0)
- **n8n version**: 2.8.3
- **Database**: SQLite (ephemeral -- lost on restart)
- **Persistence**: NONE -- PATCHes update in-memory DB only. Must sync via `n8n/sync.py` + git for permanent changes
- **Keep-alive**: cron-job.org pings every 30 minutes
- **Critical config**: `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` MUST be in entrypoint.sh (n8n 2.8+ blocks $env by default)
- **Auth**: Cookie-based (ci@nomos.ai / CI-Nomos-2026!), field: `emailOrLdapLoginId`

### Docling (S6) Specs

- Max file size: 10 MB per upload
- Max pages: 20 per PDF
- Timeout: 600s per document
- Output: Markdown + JSON (structured table/formula extraction)
- Known issue: Frequently DOWN or timing out; all scripts need local PDF fallback

---

## 7. Eval System

### Accuracy Targets

| Sector | Standard | Graph | Quant | Orchestrator |
|--------|----------|-------|-------|--------------|
| **Finance** | >= 90% | >= 75% | >= 95% | >= 85% |
| **BTP** | >= 85% | >= 70% | >= 80% | >= 75% |
| **Juridique** | >= 90% | >= 80% | N/A | >= 80% |
| **Industrie** | >= 85% | >= 70% | >= 80% | >= 75% |

### Quality Targets (Expert-level)

| Metric | Target | Last Known |
|--------|--------|------------|
| Source citation | >= 90% answers cite specific document | ~50% |
| Sector terminology | >= 80% use correct professional terms | ~60% |
| Response language match | 100% respond in question language | ~85% |
| Response time | <= 30s average | ~36s |
| Complex document handling | 100+ doc types per sector | ~20 types |

### Enterprise Production Gates (2026 Standards -- NEVER ACHIEVED)

| Metric | Target | Status |
|--------|--------|--------|
| Faithfulness | >= 95% | NEVER MEASURED (RAGAS not integrated) |
| Context Recall | >= 85% | NEVER MEASURED |
| Hallucination Rate | <= 2% | NEVER MEASURED |
| Mean Latency | <= 2.5s | NEVER ACHIEVED (~36s avg) |
| Accuracy | >= 85% | Standard PASS, Graph/Quant/Orch FAIL |

### Evaluation Phases Completed

| Phase | Questions | Status | Key Results |
|-------|-----------|--------|-------------|
| Phase 1 (200q) | 200 curated | **PASSED** (83.9%) | Session 30, Feb 20 2026 |
| Phase 2 (1,000q) | 1,000 HF benchmarks | **PARTIAL** | Graph 78%, Quant 92%, Std 36% (HF Space 404), Orch BROKEN |
| Phase 3 (~11K) | 11,700 from 14 HF datasets | **COMPLETE** | Std 87.5%, Graph 40.9%, Quant INVALID (wrong expected answers) |
| Phase 4 (100K) | 61,661 SOTA benchmarks | **PAUSED** | Std 13%, Graph 7%, Quant 14% -- data mismatch, not prod-relevant |
| Phase 5 (220 sector) | 220 sector-specific | **ACTIVE** | Baseline 25% (index mismatch) |

### 14 Benchmark Datasets Used

| # | Dataset | Questions | Pipeline | Source |
|---|---------|-----------|----------|--------|
| 1 | SQuAD 2.0 | 1,125 | Standard | Stanford, ACL 2018 |
| 2 | TriviaQA | 1,209 | Standard | Joshi et al., ACL 2017 |
| 3 | PopQA | 1,208 | Standard | Mallen et al., 2023 |
| 4 | NarrativeQA | 1,208 | Standard | DeepMind, 2018 |
| 5 | PubMedQA | 625 | Standard | Jin et al., 2019 |
| 6 | FRAMES | 949 | Standard | Google, 2024 |
| 7 | Natural Questions | 1,208 | Standard | Google, TACL 2019 |
| 8 | MS MARCO | 1,000 | Standard | Microsoft, 2016 |
| 9 | ASQA | 948 | Standard | Stelmakh et al., 2022 |
| 10 | HotpotQA | 1,325 | Graph | Yang et al., EMNLP 2018 |
| 11 | MuSiQue | 267 | Graph | Trivedi et al., TACL 2022 |
| 12 | 2WikiMultihopQA | 367 | Graph | Ho et al., COLING 2020 |
| 13 | FinQA | 400 | Quantitative | Chen et al., EMNLP 2021 |
| 14 | TAT-QA | 233 | Quantitative | Zhu et al., ACL 2021 |
| **Total** | **~11,072** | | |

### Eval Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `eval/quick-test.py` | Smoke test + validation (1-5 questions) | `python3 eval/quick-test.py --proxy --pipelines standard --questions 5` |
| `eval/expert-eval.py` | Expert evaluation across sectors | `python3 eval/expert-eval.py --sector all --questions 20` |
| `eval/run-eval-parallel.py` | Parallel evaluation across pipelines | `python3 eval/run-eval-parallel.py --max 10 --reset --label "..."` |
| `eval/iterative-eval.py` | Detailed iterative evaluation | `python3 eval/iterative-eval.py --label "..." --questions 10` |
| `eval/node-analyzer.py` | Diagnostic analysis per node | `python3 eval/node-analyzer.py --execution-id <ID>` |
| `scripts/analyze_n8n_executions.py` | Raw execution data extraction | `python3 scripts/analyze_n8n_executions.py --execution-id <ID>` |
| `eval/generate_status.py` | Regenerate status.json | `python3 eval/generate_status.py` |

### Test Methodology

1. **1/1 Smoke Test** -- single question, single pipeline
2. **5/5 Validation** -- 5 questions sequentially across all pipelines (NEVER parallel to avoid 503)
3. **10/10 Gate** -- parallel stagger (Standard/Graph/Quant parallel, Orchestrator after)
4. **Double analysis MANDATORY** for every question: `node-analyzer.py` + `analyze_n8n_executions.py`
5. **Regression Guard**: Block if accuracy drops >5% on any sector before commit

### Timeouts by Pipeline

| Pipeline | Timeout | Justification |
|----------|---------|---------------|
| Standard | 120s | avg ~30s, max ~90s |
| Graph | 120s | avg ~50s, max ~90s |
| Quantitative | 120s | avg ~40s, max ~90s |
| Orchestrator | 360s | avg ~200s, max ~300s |

### Batch Sizes

| Pipeline | Batch | Concurrency | Timeout |
|----------|-------|-------------|---------|
| Standard | 10 | 5 | 90s |
| Graph | 5 | 3 | 90s |
| Quantitative | 3 | 1 | 120s |
| Orchestrator | 2 | 1 | 180s |

---

## 8. Sector Configs

### Finance

- **Document types**: SEC filings, IFRS standards, annual reports, balance sheets, 10-K/10-Q, earnings calls
- **Supabase docs**: ~2,150
- **Pinecone vectors**: ~10K
- **Neo4j nodes**: ~20K
- **Eval questions**: 42 expert questions with golden answers + source URLs; 55 sector eval questions (financebench, finqa, tatqa, convfinqa)
- **Last accuracy**: 85.2% (target 90%)
- **Config**: `sectors/finance/`

### BTP (Batiment et Travaux Publics)

- **Document types**: DTU, Eurocodes, CCTP, AFNOR normes, BOAMP, permis de construire, etudes de sol, DQE
- **Supabase docs**: ~1,844
- **Pinecone vectors**: ~8K
- **Neo4j nodes**: ~15K
- **Eval questions**: 45 expert questions; 55 sector eval (code_accord, docie, ragbench_techqa)
- **Last accuracy**: 73.7% (target 85%) -- WEAKEST sector (data gap)
- **Config**: `sectors/btp/`

### Juridique

- **Document types**: Codes (civil, commerce, travail), jurisprudence, contrats, CGV, statuts, RGPD
- **Supabase docs**: ~2,500
- **Pinecone vectors**: ~8K
- **Neo4j nodes**: ~25K (including 5,232 Law nodes)
- **Eval questions**: 21+ expert questions; 55 sector eval (cold_french_law, french_case_law)
- **Last accuracy**: 78.8% (target 90%)
- **Config**: `sectors/juridique/`

### Industrie

- **Document types**: ISO normes, manuels maintenance, fiches securite, AMDEC, procedures qualite
- **Supabase docs**: ~1,015
- **Pinecone vectors**: ~6K
- **Neo4j nodes**: ~10K
- **Eval questions**: 21+ expert questions; 55 sector eval (ragbench_emanual, hotpotqa)
- **Last accuracy**: 80.4% (target 85%)
- **Config**: `sectors/industrie/`

### Master Eval Dataset

- **Location**: `sectors/eval-datasets/` and `eval/datasets/sector-eval/sector-full-eval.json`
- **Total**: 220+ sector-specific questions (55 per sector)
- **Supabase**: 29,564 questions in `eval_question_bank` table

---

## 9. Ingestion System

### Architecture

```
Acquisition -> Processing (Docling S6) -> Chunking (per sector) -> Embedding (Jina 1024d) -> Storage (Pinecone + Supabase + Neo4j)
```

### 4 Ingestion Scripts (Operational as of S120)

| Script | Source | Sector | Potential |
|--------|--------|---------|-----------|
| `ingest-legifrance.py` | DILA Open Data (15 codes) | juridique/btp/finance/industrie | ~50K+ articles |
| `ingest-inrs.py` | 74 PDFs INRS | industrie | ~1,300 chunks |
| `ingest-boamp.py` | BOAMP OpenDataSoft API | btp | 25K+ avis/an |
| `ingest-amf.py` | AMF RSS (4 feeds) | finance | 200+ publications |

### Other Ingestion Tools

| Script | Role |
|--------|------|
| `ops/fast-ingest.py --sector all` | Fast batch ingest across all sectors |
| `ops/exa-mass-ingest.py` | Exa.AI web search -> document ingestion |
| `ops/local-pdf-ingest.py` | Local PDF ingestion via Docling |
| `ops/continuous-ingest.py --loop 3600` | Continuous daemon: Exa.AI -> Docling S6 -> chunk -> embed -> upsert |

### n8n Ingestion Workflows (on S9)

| Workflow | ID | Role |
|----------|----|------|
| Ingestion V4.0 | `nh1D4Up0wBZhuQbp` | Docling processing -> Pinecone + Supabase upserts |
| Enrichment V4.0 | `ORa01sX4xI0iRCJ8` | Neo4j entity enrichment from ingested documents |

### Docling (S6) Document Processing

- **URL**: `https://lbjlincoln-nomos-docling-api.hf.space`
- **Capabilities**: Extract tables, formulas, complex layouts from PDFs
- **Limits**: 10MB per file, 20 pages per PDF, 600s timeout
- **Target fidelity**: 95% on complex documents
- **Known issue**: Frequently DOWN -- all scripts need local PDF fallback

### Document Type Targets per Sector (goal: 100+)

- **Finance**: SEC filings, IFRS standards, annual reports, balance sheets, 10-K/10-Q, earnings calls, AMF publications
- **BTP**: DTU, Eurocodes, CCTP, AFNOR normes, BOAMP, permis, etudes sol, DQE
- **Juridique**: Codes (civil, commerce, travail), jurisprudence, contrats, CGV, statuts, RGPD, Legifrance
- **Industrie**: ISO normes, manuels maintenance, fiches securite (INRS), AMDEC, procedures qualite

### Data Reality

43K Supabase entries were ~80% benchmarks and only ~53 real production documents. The 4 ingestion scripts above were tested and working, ready to ingest actual production documents.

---

## 10. Key Metrics

### Last Known Pipeline Accuracy (Session 106 -- 208 results in 24h)

| Pipeline | Pass/Total | Accuracy | Target | Gap |
|----------|-----------|----------|--------|-----|
| **Quantitative** | 107/108 | **99.1%** | 95% | +4.1% |
| **Standard** | 41/58 | **70.7%** | 90% | -19.3% |
| **Orchestrator** | 3/5 | **60.0%** | 85% | -25% |
| **Graph** | 17/37 | **45.9%** | 75% | -29.1% |

### Last Known Sector Accuracy (Session 106 -- 24h window)

| Sector | Pass/Total | Accuracy | Target |
|--------|-----------|----------|--------|
| **Finance** | 69/81 | **85.2%** | 90% |
| **Industrie** | 45/56 | **80.4%** | 85% |
| **Juridique** | 26/33 | **78.8%** | 90% |
| **BTP** | 28/38 | **73.7%** | 85% |

### Database Counts at Archive

| Database | Count | Details |
|----------|-------|---------|
| **Pinecone E5 total** | ~78,000 vectors | Across 2 primary indexes (target was 100K) |
| **Pinecone `website-sectors-jina-1024`** | ~43,000 vectors | Primary sector index |
| **Pinecone `sota-rag-jina-1024`** | ~35,000 vectors | Frozen benchmark index |
| **Neo4j nodes** | ~71,890 | 33K Entity + 30K SectorDoc + 5.2K Law + 1.6K Org + 1.6K Company |
| **Neo4j relationships** | 76,717 | |
| **Supabase sector_documents** | ~43,000 | Across 4 sectors |
| **Supabase eval_question_bank** | 29,564 | With scoring metadata |
| **Supabase financial data** | 225 entries | 111 companies, 4 sectors |
| **Supabase financial tables** | 3,876 | Structured financial data |

### Phase 3 Scale Test Results (Best Historical)

| Pipeline | Questions | Accuracy |
|----------|-----------|----------|
| Standard | 8,006 tested | **87.5%** (above 85% target) |
| Graph | 1,500 tested | **40.9%** (below 70% target) |
| Quantitative | 500 tested | 30% (**INVALID** -- synthetic wrong answers) |

### Infrastructure Metrics

| Metric | Value |
|--------|-------|
| Total sessions | 121+ |
| Total commits | 1,120+ |
| Active n8n workflows on S1 | 10 |
| Total HF Spaces (RAG) | 9 |
| Total n8n credential entries | 209 |
| OpenRouter API keys | 6 |
| Groq API keys | 5 |
| Git repos | 7 (5 active + 2 archive) |

---

## 11. Debug Knowledge

### Top 20 Most Important Fixes from DEBUG-PLAYBOOK

#### FIX-63: N8N_BLOCK_ENV_ACCESS_IN_NODE missing (MOST COMMON)
- **Sessions**: 58, 62, 65 (recurrent)
- **Symptom**: ALL pipelines return "Unable to generate answer" or "NO_ANSWER". Execution data shows `{"error": "access to env vars denied"}`.
- **Root cause**: n8n 2.8.3 blocks `$env.*` access in ALL node types by default.
- **Fix**: Add `export N8N_BLOCK_ENV_ACCESS_IN_NODE=false` to entrypoint.sh BEFORE n8n start.
- **Impact**: CROSS-PIPELINE -- fixes ALL 5 pipelines simultaneously.

#### FIX-71: Duplicate workflows with same webhook ID
- **Session**: 75
- **Symptom**: PATCH updates have no effect. Execution uses old code.
- **Root cause**: Two workflows BOTH active with the same webhook ID. Wrong one handles requests.
- **Fix**: Check execution's `workflowId` field. Deactivate the stale one.

#### FIX-34: executeWorkflow returns empty (respondToWebhook)
- **Session**: 27
- **Symptom**: Orchestrator returns 200 empty body.
- **Root cause**: `executeWorkflow` + `respondToWebhook` = response goes to client, NOT parent workflow.
- **Fix**: Replace `executeWorkflow` with `httpRequest` POST to sub-pipeline webhook.

#### FIX-68: SQL Validator only parses JSON
- **Session**: 75
- **Symptom**: Quant always returns `SQL_GENERATION_ERROR: Invalid LLM response`.
- **Root cause**: `JSON.parse(content)` fails when LLM wraps SQL in markdown.
- **Fix**: Multi-strategy extraction: JSON.parse -> ```sql block -> ```json block -> raw SELECT regex.

#### FIX-33: $env blocked for ALL node types (n8n 2.8+)
- **Session**: 27
- **Symptom**: 500 "access to env vars denied" on every pipeline.
- **Root cause**: n8n 2.8+ blocks $env for ALL node types, not just Code nodes.
- **Fix**: Set `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` environment variable.

#### FIX-48: nginx reverse proxy causes persistent 502
- **Session**: 42
- **Symptom**: HF Space returns 502 on all requests.
- **Root cause**: nginx in front of n8n on HF Space causes proxy issues.
- **Fix**: n8n must listen directly on port 7860, no nginx.

#### FIX-51: set -e kills container on transient failures
- **Session**: 42
- **Symptom**: HF Space container keeps restarting.
- **Root cause**: `set -e` in entrypoint.sh kills entire container on any transient error.
- **Fix**: Remove `set -e` from entrypoint.sh.

#### FIX-52: Hardcoded API keys in workflow JSONs expire
- **Session**: 43
- **Symptom**: 401 errors on LLM calls.
- **Root cause**: API keys hardcoded directly in workflow JSON files instead of credentials.
- **Fix**: Move all keys to n8n credentials, reference by credential ID.

#### FIX-40: OOM -> zombie processes -> all webhooks 404/503
- **Session**: 40
- **Symptom**: All webhooks return 404 or 503.
- **Root cause**: VM OOM creates zombie processes, PG connections timeout, n8n becomes unresponsive.
- **Fix**: Kill zombie processes, clear stuck executions, restart n8n.

#### FIX-21: Code node cache -- PUT + Activate cycle mandatory
- **Session**: 25
- **Symptom**: Code node changes have no effect after PATCH.
- **Root cause**: n8n Task Runner caches compiled code. PATCH alone doesn't invalidate cache.
- **Fix**: Cycle: PUT workflow -> Deactivate -> Activate (forces cache refresh).

#### FIX-18: SQLITE FK constraint -- shared/activeVersion refs VM entities
- **Session**: 24
- **Symptom**: `SQLITE_CONSTRAINT FOREIGN KEY` on workflow import.
- **Root cause**: Workflow JSON contains FKs referencing VM database entities that don't exist in HF Space's SQLite.
- **Fix**: Strip FK fields before import.

#### FIX-35: OPENROUTER_BASE_URL without /chat/completions
- **Session**: 27
- **Symptom**: Pipeline returns HTML instead of JSON.
- **Root cause**: API URL missing `/chat/completions` suffix, hits the provider's HTML homepage.
- **Fix**: Ensure all LLM URLs include full path.

#### FIX-22: OpenRouter 429 rate-limit
- **Session**: 25
- **Symptom**: Frequent 429 errors during evaluation.
- **Root cause**: Free tier rate limits (~20 RPM per key).
- **Fix**: Timeouts/retries (90s, 3 retries, 8s wait), neverError flag, multi-key rotation.

#### FIX-69: Postgres credential ID mismatch
- **Session**: 75
- **Symptom**: Schema Introspection returns 0 rows in Quantitative pipeline.
- **Root cause**: Wrong credential ID (`cH96` instead of `b44av`).
- **Fix**: Switch to credential `b44avEJtnkw46GL6`.

#### FIX-70: tenant_id 'default' vs 'benchmark'
- **Session**: 75
- **Symptom**: SQL returns 0 rows despite correct query.
- **Root cause**: Using `tenant_id='default'` when data is stored under `'benchmark'`.
- **Fix**: ALWAYS use `tenant_id='benchmark'`.

#### FIX-07: Neo4j URL bolt://localhost -> HTTPS API
- **Session**: 17
- **Symptom**: Graph pipeline can't reach Neo4j.
- **Root cause**: Using `bolt://localhost` URL for Neo4j Aura (cloud service).
- **Fix**: Use HTTPS API: `https://38c949a2.databases.neo4j.io/db/neo4j/query/v2`.

#### FIX-78: Neo4j tx/commit returns 403
- **Session**: 69
- **Symptom**: Neo4j ingestion fails with 403.
- **Root cause**: Neo4j Aura blocks the old HTTP Transaction API (tx/commit).
- **Fix**: Use `/db/neo4j/query/v2` (Query API) instead.

#### FIX-04: Jina JSON trailing comma
- **Session**: 8
- **Symptom**: Standard pipeline embedding calls fail with JSON parse error.
- **Root cause**: Jina API response has trailing comma in JSON.
- **Fix**: Strip trailing commas before JSON.parse.

#### FIX-01: Task Runner isolation breaks $getWorkflowStaticData
- **Session**: 16
- **Symptom**: Workflow static data returns undefined.
- **Root cause**: n8n Task Runner creates isolated execution environment that doesn't share static data.
- **Fix**: Use execution-level data instead of workflow static data.

#### FIX-42: Stuck executions block all webhooks
- **Sessions**: 40b, 40f, 40g
- **Symptom**: New webhook requests hang or timeout despite healthz returning OK.
- **Root cause**: 79 stuck executions (new/running status) consume all n8n worker slots.
- **Fix**: DELETE stuck executions via REST API + restart n8n if cleanup alone insufficient.

### Quick Symptom Matrix

| Symptom | Probable Fix |
|---------|--------------|
| 404 webhook | Wrong path -- check Section 2 webhook URLs |
| 500 "$env denied" | FIX-33/63 -- N8N_BLOCK_ENV_ACCESS_IN_NODE=false |
| 500 "credential not found" | FIX-06/53 -- recreate credentials + remap IDs |
| 429 rate limit | Backoff/multi-key rotation |
| Empty body (Orchestrator) | FIX-34 -- use httpRequest not executeWorkflow |
| HTML instead of JSON | FIX-35 -- check API URL includes /chat/completions |
| "[object Object]" in response | Serializer typeof check issue |
| "Query must start with SELECT" | LLM 429 or URL misconfiguration |
| Fix has no effect (VM) | FORBIDDEN -- modify on HF Space ONLY |
| Fix has no effect (HF) | FIX-21 -- PUT + Deactivate + Activate cycle |
| OOM on VM | Kill processes, use HF Space |
| SQL returns 0 rows | Check tenant_id='benchmark' and credential b44av |

### Iron Rules (Never Violate)

1. NEVER modify workflows on VM (Task Runner cache persists compiled code)
2. ALWAYS use cookie auth for n8n REST API (JWT invalidates on HF rebuild)
3. ALWAYS check execution's `workflowId` before patching (duplicate workflow trap)
4. ALWAYS `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` in entrypoint.sh
5. ALWAYS use `query` field (not `question`) in webhook payloads
6. ALWAYS use `tenant_id='benchmark'` (not `'default'`)
7. ALWAYS use Postgres credential `b44avEJtnkw46GL6` (not `cH96tQ3I9uIHqiiq`)
8. NEVER run ML training on VM (1GB RAM -- HF Spaces only)
9. NEVER launch parallel quick-test.py instances (causes 503 n8n overload)
10. 3+ regressions -> REVERT immediately

---

## Appendix A: SOTA Research Papers Referenced

| Paper | arXiv ID | Key Contribution |
|-------|----------|-----------------|
| MA-RAG: Multi-Agent RAG | arXiv:2505.20096 | Stage-level specialization, -23% hallucination |
| A-RAG: Adaptive RAG | arXiv:2602.03442 | LLM tool selection, -31% unnecessary calls |
| GraphRAG vs Vector RAG | arXiv:2502.11371 | GraphRAG 80% vs 50.83% on entity queries |
| Late Chunking (Jina) | arXiv:2409.04701 | +10-12% retrieval accuracy, no LLM cost |
| CRAG: Corrective RAG | arXiv:2401.15884 | Retrieval quality evaluation + fallback |
| Higress-RAG | arXiv:2602.23374 | MCP-based dual hybrid retrieval + adaptive routing |
| RouteRAG (RL routing) | arXiv:2512.09487 | RL-based routing, +7.7 F1 |
| Cohere Rerank 3.5 | Cohere blog 2025 | +26.4% cross-lingual, +23.4% vs hybrid |
| Self-Healing RAG | AIAnytime 2025 | 3-layer auto-recovery |
| RRF: Reciprocal Rank Fusion | Cormack et al. | +18.5% MRR, fuse vector + BM25 |

## Appendix B: Environment Variables Reference

### Critical Variables

| Variable | Description |
|----------|-------------|
| `N8N_HOST` | `https://lbjlincoln-nomos-rag-engine.hf.space` |
| `N8N_API_KEY` | JWT n8n API auth (updated 2026-03-12) |
| `PINECONE_API_KEY` | Pinecone API key |
| `JINA_API_KEY` | Jina AI API key |
| `NEO4J_URI` | `neo4j+s://38c949a2.databases.neo4j.io` |
| `NEO4J_PASSWORD` | Neo4j Aura password |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_API_KEY` | Service role key |
| `SUPABASE_PASSWORD` | PostgreSQL password |
| `HF_TOKEN` | HuggingFace token (LBJLincoln) |
| `HF_TOKEN_2` | Secondary HF token |
| `HF_TOKEN_3` | Third HF token |
| `LITELLM_URL` | `https://lbjlincoln-nomos-rag-engine-7.hf.space` |
| `LITELLM_KEY` | `sk-litellm-nomos-2026` |
| `OPENROUTER_KEY_STANDARD` | Per-pipeline OpenRouter key |
| `OPENROUTER_KEY_GRAPH` | Per-pipeline OpenRouter key |
| `OPENROUTER_KEY_QUANTITATIVE` | Per-pipeline OpenRouter key |
| `OPENROUTER_KEY_ORCHESTRATOR` | Per-pipeline OpenRouter key |
| `GROQ_API_KEY` through `GROQ_API_KEY_5` | 5 Groq keys |
| `N8N_BLOCK_ENV_ACCESS_IN_NODE` | `false` (CRITICAL -- must be set) |

## Appendix C: Repos

| Repo | Role | Status at Archive |
|------|------|-------------------|
| **mon-ipad** | Tour de controle, eval, ops, MCP | ACTIVE |
| **rag-data-ingestion** | Ingestion engine, Docling, 100+ doc types | ACTIVE |
| **rag-website** | Chatbot expert sectoriel, Next.js, Vercel | ACTIVE |
| **rag-dashboard** | Dashboard sector accuracy, live metrics | ACTIVE |
| **rag-storage** | Archive LFS + benchmark legacy | ARCHIVE |
| **rag-pme-connectors** | Next.js 15, 15 apps | ARCHIVE |
| **rag-tests** | Merged into mon-ipad | ARCHIVE |

## Appendix D: Operational Commands

```bash
# Session startup
source .env.local
cat directives/PROJECT-STATE.md

# Agent management
python3 ops/agents.py launch all
python3 ops/agents.py status
python3 ops/agents.py stop all
python3 ops/agents.py logs monitor

# Monitoring
python3 ops/monitor.py                    # One-shot dashboard
python3 ops/monitor.py --loop 300         # Continuous 5min
python3 ops/monitor.py --errors-only

# Evaluation
python3 eval/quick-test.py --proxy --pipelines standard --questions 5
python3 eval/expert-eval.py --sector all --questions 20
python3 eval/run-eval-parallel.py --max 10 --reset --label "description"

# Pipeline analysis
python3 ops/n8n-execution-analyzer.py --hours 24
python3 ops/n8n-smart-analyzer.py --deep

# Ingestion
python3 ops/fast-ingest.py --sector all
python3 ops/exa-mass-ingest.py
python3 ops/local-pdf-ingest.py
python3 ops/continuous-ingest.py --loop 3600

# Deployment
python3 ops/deploy-standard-v35.py
python3 ops/n8n-api.py list

# n8n API (cookie auth)
python3 scripts/n8n-api.py list
python3 scripts/n8n-api.py get <WF_ID>
python3 scripts/n8n-api.py deploy n8n/live/workflow.json
python3 scripts/n8n-api.py activate <WF_ID>

# Health check
curl https://lbjlincoln-nomos-rag-engine.hf.space/healthz
curl -s "https://lbjlincoln-nomos-rag-engine-7.hf.space/health/liveliness"
```

---

**End of RAG Pipeline System Archive**

*Generated: 2026-03-17 by Claude Code (claude-opus-4-6)*
*Source files: CLAUDE.md, PROJECT-STATE.md, PROCESS-RUNBOOKS.md, INFRASTRUCTURE.md, DEBUG-PLAYBOOK.md, PROJECT-ROADMAP.md*
*Total sessions: 121+ | Total commits: 1,120+ | Total fixes documented: 90+*
