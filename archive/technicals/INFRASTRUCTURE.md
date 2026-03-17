# Infrastructure Reference — Multi-RAG Orchestrator SOTA 2026

> Last updated: 2026-03-12T12:00:00Z (Session 105)
> Consolidated infrastructure documentation: architecture, stack, credentials, limits, storage strategy.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Infrastructure Components](#infrastructure-components)
3. [Databases & Storage](#databases--storage)
4. [Services & APIs](#services--apis)
5. [Credentials & Access](#credentials--access)
6. [Environment Variables](#environment-variables)
7. [Limits & Quotas](#limits--quotas)
8. [Storage Strategy](#storage-strategy)
9. [Workflow Registry](#workflow-registry)

---

## Architecture Overview

### Global Architecture (Session 105 — March 2026)

```
VM Google Cloud (34.136.180.66) — PERMANENT (PILOTAGE ONLY)
  n8n Docker : REMOVED (Session 42) — All n8n moved to HF Spaces
  Redis : REMOVED (Session 60 — Orchestrator Redis removed)
  PostgreSQL : REMOVED (Session 42)
  Claude Code : Termius terminal (pilotage + eval orchestration)
  RAM ~413MB available (n8n removed, lightweight only)
  MCP Servers : ~6MB total (neo4j 2.5MB, pinecone 1.4MB, HF 0.8MB, jina 0.7MB, cohere 0.6MB)

HF Spaces — DISTRIBUTED EXECUTION
  Primary (#1) : lbjlincoln-nomos-rag-engine.hf.space
    - n8n 2.8.3, 16GB RAM, SQLite DB
    - Standard + Graph pipelines
    - LiteLLM proxy (Space #7)

  Secondary (#2) : lbjlincoln26-nomos-rag-engine-2.hf.space
    - n8n, same DB as S1 (shared Postgres)
    - Load balancing

  Engine-3 (#3) : lbjlincoln-nomos-rag-engine-3.hf.space
    - n8n, all 4 pipelines (load balance)

  Engine-4 (#4) : lbjlincoln26-nomos-rag-engine-4.hf.space
    - n8n, same DB as S1

  Engine-5 (#5) : lbjlincoln-nomos-rag-engine-5.hf.space
    - n8n, all 4 pipelines (load balance)

  Docling (#6) : lbjlincoln-nomos-docling-api.hf.space
    - Docling document processor
    - CPU-basic, 2 vCPU, 16GB RAM
    - 10MB/20-page PDF limits, 600s timeout

  Engine-9 (#9) : lbjlincoln-nomos-rag-engine-9.hf.space
    - n8n, Standard + Quant (SEPARATE database)

  Embeddings : lbjlincoln-nomos-embeddings-api.hf.space
    - Self-hosted Jina embeddings (1024 dims)

GitHub Codespaces (EPHEMERAL — 60h/month free tier)
  - rag-tests : NOT USED (eval runs from VM → HF Space webhooks)
  - rag-website : Site + demos secteurs (Next.js + local n8n)
  - rag-data-ingestion : Ingestion benchmarks (2 workers)
  - rag-pme-connectors : PME connectors tests

Vercel (PRODUCTION SITES)
  - 4 secteurs : nomos-ai-pied.vercel.app
  - PME connectors : nomos-pme-connectors-alexis-morets-projects.vercel.app
  - PME use cases : nomos-pme-usecases-alexis-morets-projects.vercel.app
  - Dashboard : nomos-dashboard-alexis-morets-projects.vercel.app
```

### Critical Architectural Decision (Session 25)

**VM = PILOTAGE ONLY** — Rules 25, 28, 29

| Action | Execute On | Why |
|--------|-----------|-----|
| Modify n8n workflow | HF Space or Codespace | Task Runner VM cache persists compiled code |
| Test pipeline (1/1, 5/5) | HF Space (16GB) | VM RAM insufficient + Task Runner cache |
| Full eval (50q+) | VM → HF Space webhooks | Round-robin routing to 10 endpoints |
| Piloting, commits, analysis | VM | Claude Code CLI + git + MCP |

---

## Infrastructure Components

### VM Google Cloud (e2-micro, us-central1)

| Resource | Current | Hard Limit | Status | Notes |
|----------|---------|------------|--------|-------|
| **IP** | 34.136.180.66 | Static | OK | SSH via Termius |
| **OS** | Linux Debian 11 (Bullseye) | N/A | OK | Kernel 6.1.0-43 |
| **CPU** | 1 vCPU | Intel Xeon @ 2.20GHz | MEDIUM | Single-threaded |
| **RAM Total** | ~865 MB used | 969 MB | CRITICAL | ~104 MB available |
| **Swap** | ~1084 MB used | 2047 MB | HIGH | VM swaps regularly |
| **Disk** | 12 GB used | 30 GB | OK | 17 GB free (43% full) |
| **Claude Code Process** | ~297 MB | N/A | CRITICAL | 30% of VM RAM |
| **MCP Servers Total** | ~6 MB | N/A | NEGLIGIBLE | Minimal footprint |
| **Network (egress)** | Unknown | 1 GB/month (free tier) | UNKNOWN | May throttle |

**Operational Constraints**:
- ZERO eval tests on VM (Rule 25)
- ZERO workflow modifications on VM (Rule 28)
- Maximum 2-3 concurrent Python processes before OOM risk
- Kill old Claude sessions at startup to reclaim RAM

### HF Space #1 (lbjlincoln-nomos-rag-engine.hf.space)

| Resource | Current | Hard Limit | Status | Notes |
|----------|---------|------------|--------|-------|
| **RAM** | Unknown | 16 GB | EXCELLENT | cpu-basic tier, $0 |
| **n8n Version** | 2.8.3 | Latest | OK | SQLite + Redis |
| **Workers** | 1 | 1 | OK | NOT queue mode |
| **Credentials** | 12/12 imported | Unlimited | OK | See credentials section |
| **Workflows** | 10 active | Unlimited | OK | Standard/Graph/Quant/Orch + Ingestion/Enrichment |
| **Concurrent Executions** | Unknown | Higher than VM | GOOD | More headroom |
| **Uptime** | Best-effort | N/A | MEDIUM | Keep-alive cron every 30 min |
| **Persistence** | SQLite (ephemeral) | No persistent storage | CRITICAL | PATCH changes lost on restart |

**Critical Patterns**:
- **PATCH does NOT persist**: HF Space has `storage: null`. PATCHes update in-memory DB only. MUST update `n8n/live/*.json` and sync via `n8n/sync.py` for permanent changes.
- **REST API BROKEN**: HF Space proxy strips POST body for `/api/` endpoints. Use webhooks only.
- **Disabled nodes pass-through**: Data passes unchanged BUT HTTP Request nodes STILL fire their HTTP calls.
- **Duplicate workflows trap**: Multiple workflows can share same webhook ID. Check execution's `workflowId` to find which is actually running.

### HF Space #7 (LiteLLM Proxy)

| Resource | Value | Notes |
|----------|-------|-------|
| **URL** | https://lbjlincoln-nomos-rag-engine-7.hf.space | Proxy layer |
| **Master Key** | `sk-litellm-nomos-2026` | See credentials section |
| **Status** | **UP** | Confirmed working, all pipelines route through it |
| **Persistence** | Supabase Postgres | DB partially broken (spend tracking only) |
| **Config** | `hf-space/litellm-proxy/litellm-config.yaml` | Model routing |
| **Key Pool** | 12+ keys (7 OpenRouter, 5 Groq, 1 Gemini) | Auto-rotation |
| **Model Groups** | default(10), fast(11), **smart(13)**, llama-70b(12), gemma-27b(7), trinity(7), qwen-235b(7), gemini-flash(1), groq-llama(5) | All pipelines use `smart` |
| **Fallback Chain** | OpenRouter → Gemini → Groq | Automatic on rate limit |

### HF Space #6 — Docling (lbjlincoln-nomos-docling-api.hf.space)

| Resource | Value | Notes |
|----------|-------|-------|
| **URL** | https://lbjlincoln-nomos-docling-api.hf.space | Document processor |
| **Tier** | cpu-basic | 2 vCPU, 16GB RAM, $0 |
| **Status** | **UP** | Processing PDFs for all 4 sectors |
| **Max File Size** | 10 MB | Per upload |
| **Max Pages** | 20 pages | Per PDF |
| **Timeout** | 600s | Per document conversion |
| **Output** | Markdown + JSON | Structured extraction (tables, formulas, layout) |
| **Integration** | continuous-ingest daemon | `ops/continuous-ingest.py --loop 3600` |

**Operational Rules**:
- Large PDFs (>20 pages) must be split before upload
- Tables and formulas extracted with high fidelity
- Used by Ingestion V4.0 workflow (`nh1D4Up0wBZhuQbp`) and VM daemon

### GitHub Codespaces

| Resource | Standard | basicLinux32gb | Hard Limit | Notes |
|----------|----------|----------------|------------|-------|
| **CPU** | 2 cores | 8 cores | 2-8 cores | basicLinux32gb for heavy ingestion |
| **RAM** | 8 GB | 32 GB | 8-32 GB | 8 GB sufficient for 200q tests |
| **Disk** | 32 GB | 128 GB | 32-128 GB | Ephemeral, lost on delete |
| **Active Hours Cost** | 2x multiplier | 8x multiplier | N/A | Against 60h/month quota |
| **Quota** | 60h/month | 60h/month | FREE TIER | Shared across all codespaces |
| **Simultaneous** | 0-2 running | 2 running max | CRITICAL | Can create 3+ but only 2 can run |
| **Network** | Unlimited | Unlimited | N/A | SSH tunnel to VM works |

**Operational Rules**:
- 60h/month = ~2h/day average OR 7-8 full days/month
- Always push results to GitHub BEFORE stopping codespaces (Rule 18)
- Standard = 2x multiplier (30h real quota), basicLinux32gb = 8x multiplier (7.5h real quota)

---

## Databases & Storage

### Pinecone (Free Tier — Serverless)

| Resource | Current Usage | Hard Limit | Status | Notes |
|----------|--------------|------------|--------|-------|
| **Indexes Total** | 4 | 5 (Free tier) | OK | sota-rag-jina-1024, website-sectors-jina-1024, sota-rag-phase2-graph, sota-rag (legacy) |
| **sota-rag-jina-1024** | ~35,000 vectors | 100K per index | OK | Primary benchmark index, 1024-dim Jina |
| **website-sectors-jina-1024** | ~43,000 vectors | 100K per index | OK | Sectors (BTP, Finance, Industrie, Juridique) — E5 total ~78K |
| **sota-rag-phase2-graph** | 1,248 vectors | 100K per index | OK | e5-large, 1024-dim |
| **sota-rag** | 10,411 vectors | 100K per index | OK | Legacy Cohere index |
| **Dimensions** | 1024 | 20,000 | OK | jina-embeddings-v3 standard |
| **Namespaces (jina-1024)** | 12 | 100 (Free tier) | OK | Per-dataset isolation |
| **Query Latency** | ~200-500ms | N/A | OK | Serverless variable |
| **Queries per Second** | Unknown | 100 QPS (Free tier) | OK | Never hit |
| **Storage** | ~50 MB | 10 GB (Free tier) | OK | Vectors + metadata |

**Operational Rules**:
- Max 100K vectors per index — Phase 3 won't exceed
- Free tier has NO time limit (unlimited retention)
- Namespace isolation for datasets (finqa, musique, hotpotqa, etc.)

### Neo4j Aura (Free Tier)

| Resource | Current Usage | Hard Limit | Status | Notes |
|----------|--------------|------------|--------|-------|
| **Nodes** | ~71,890 | 200,000 | OK | 36% used (Entity 33,299 + SectorDoc 30,143 + Law 5,232 + Org 1,615 + Company 1,600) |
| **Relationships** | 76,717 | 400,000 | OK | 19% used |
| **Storage** | Unknown | 50 MB (Free tier) | OK | Graph data only |
| **RAM** | Unknown | 1 GB (Free tier) | OK | Aura managed |
| **API** | https://38c949a2.databases.neo4j.io/db/neo4j/query/v2 | N/A | OK | HTTPS (NOT bolt) |
| **Cypher Query Latency** | ~300-800ms | N/A | MEDIUM | HTTPS API slower than Bolt |
| **Concurrent Connections** | Unknown | 10 (Free tier) | OK | n8n pools connections |
| **Labels** | Variable | Unlimited | OK | Entity, Document, Community |

**Operational Rules**:
- MUST use HTTPS API (not Bolt) for n8n HTTP Request nodes
- Free tier pauses after 3 days inactivity (query to wake)
- Query optimization critical (use indexes on tenant_id, name)

### Supabase (Free Tier)

| Resource | Current Usage | Hard Limit | Status | Notes |
|----------|--------------|------------|--------|-------|
| **Tables** | 40 | Unlimited | OK | public schema |
| **Rows** | ~76K+ | 500 MB storage | OK | 43K sector_documents + 225 financials + 3,876 financial_tables + 29,564 eval_question_bank |
| **Storage** | Unknown | 500 MB (Free tier) | OK | Estimated <100 MB |
| **Project ref** | ayqviqmxifzmhphiqfmj | N/A | OK | EU West 1 |
| **URL** | https://ayqviqmxifzmhphiqfmj.supabase.co | N/A | OK | REST API |
| **Pooler** | aws-1-eu-west-1.pooler.supabase.com:6543 | N/A | OK | PostgreSQL direct |
| **API Requests** | Unknown | Unlimited (Free tier) | OK | No hard limit |
| **Concurrent Connections** | Unknown | 60 (Pooler) | OK | n8n uses pooler |
| **Query Latency** | ~100-300ms | N/A | OK | Fast REST API |
| **Bandwidth** | Unknown | 5 GB/month (Free tier) | OK | Minimal usage |
| **tenant_id** | `benchmark` | N/A | CRITICAL | NOT 'default' (Session 75) |

**Key Tables**:
- `sector_documents` — 43K docs across 4 sectors
- `sector_financial_data` — 225 financials (111 companies, 4 sectors)
- `sector_financial_tables` — 3,876 structured financial tables
- `eval_question_bank` — 29,564 questions (tracks `times_asked`, `score_trend`, `consecutive_fails`)
- `eval_results` — Per-question evaluation results tracking

**Operational Rules**:
- Use Pooler endpoint (port 6543) for n8n to avoid connection exhaustion
- 500 MB storage sufficient for 1M+ rows of financial data
- exec_sql RPC for dynamic SQL generation (Quantitative pipeline)
- Free tier pauses after 1 week inactivity (query to wake)
- ALWAYS `SET search_path TO public` after psycopg2.connect() (pooler defaults to `n8n_engine_1` schema)

### GitHub / Vercel

| Service | Resource | Current | Limit | Notes |
|---------|----------|---------|-------|-------|
| **GitHub Private Repos** | 7 | Unlimited | OK | mon-ipad + 6 satellites |
| **GitHub Actions** | Minimal | 2000 min/month | OK | CI smoke tests only |
| **GitHub Storage** | Unknown | 500 MB | OK | Code only |
| **GitHub LFS (rag-storage)** | ~200 MB | 1 GB limit | OK | Archived datasets |
| **Vercel Projects** | 4 | Unlimited | OK | rag-website, pme-connectors, pme-usecases, dashboard |
| **Vercel Deployments** | Auto on push | 100/day | OK | Never hit |
| **Vercel Bandwidth** | Unknown | 100 GB/month | OK | Static sites minimal |
| **Vercel Build Minutes** | Minimal | 6000 min/month | OK | Next.js builds ~2 min each |

---

## Services & APIs

### LLM Models (Free Tier via OpenRouter)

| Variable | Model | Usage | Cost |
|----------|-------|-------|------|
| `LLM_SQL_MODEL` | meta-llama/llama-3.3-70b-instruct:free | SQL generation | $0 |
| `LLM_FAST_MODEL` | google/gemma-3-27b-it:free | Fast operations | $0 |
| `LLM_INTENT_MODEL` | meta-llama/llama-3.3-70b-instruct:free | Intent classification | $0 |
| `LLM_PLANNER_MODEL` | meta-llama/llama-3.3-70b-instruct:free | Task planning | $0 |
| `LLM_AGENT_MODEL` | meta-llama/llama-3.3-70b-instruct:free | Agent reasoning | $0 |
| `LLM_HYDE_MODEL` | meta-llama/llama-3.3-70b-instruct:free | HyDE generation | $0 |
| `LLM_EXTRACTION_MODEL` | arcee-ai/trinity-large-preview:free | Entity extraction | $0 |
| `LLM_COMMUNITY_MODEL` | arcee-ai/trinity-large-preview:free | Community summaries | $0 |
| `LLM_LITE_MODEL` | google/gemma-3-27b-it:free | Lightweight tasks | $0 |

**Summary by Family**:
- **Llama 70B**: SQL, Intent, Planning, HyDE, Agent, QA, Chunking, Contextual, Generation
- **Gemma 27B**: Fast, Lite
- **Trinity**: Extraction, Community

### OpenRouter (6 keys across 3 accounts)

| Resource | Current Usage | Hard Limit | Status | Notes |
|----------|--------------|------------|--------|-------|
| **API Keys** | 6 active | N/A | OK | Per-pipeline rotation |
| **Models Available** | 3 used | 100+ free models | OK | Llama 70B, Gemma 27B, Trinity |
| **Cost** | $0 | $0 (free tier) | EXCELLENT | All models free |
| **Rate Limits (Llama 70B)** | Unknown | ~20 RPM (typical) | MEDIUM | May cause 429 errors |
| **Rate Limits (Gemma 27B)** | Unknown | ~30 RPM (typical) | MEDIUM | Faster model |
| **Concurrent Requests** | Variable | ~3-5 (typical) | MEDIUM | Sequential safer |
| **Context Length (Llama 70B)** | Unknown | 131,072 tokens | OK | Sufficient |

**Per-Pipeline Keys** (Session 50+57):
- `OPENROUTER_KEY_STANDARD`, `OPENROUTER_KEY_GRAPH`, `OPENROUTER_KEY_QUANTITATIVE`, `OPENROUTER_KEY_ORCHESTRATOR`
- Generic `OPENROUTER_API_KEY` REMOVED from core workflow JSONs (Session 57)

**Operational Rules**:
- 429 errors observed during heavy use (Session 27)
- Retry with exponential backoff for 429 errors
- Switch to faster model (Gemma 27B) for simple operations

### Groq (5 keys)

| Resource | Value | Notes |
|----------|-------|-------|
| **Keys** | GROQ_API_KEY through GROQ_API_KEY_5 | 5 keys total |
| **Rate Limit** | ~30 RPM per key | Per key |
| **Model** | llama-3.3-70b-versatile | Primary |
| **Usage** | LiteLLM proxy (auto-rotation), OpenClaw gateway | Via proxies |

### Jina AI (Free Tier)

| Resource | Current Usage | Hard Limit | Status | Notes |
|----------|--------------|------------|--------|-------|
| **API Keys** | 2 (key 1 EXHAUSTED) | N/A | OK | Key 2 active (Session 75) |
| **Embeddings Quota** | Unknown | 1M tokens/month | OK | ~20K docs/month |
| **Reranker Quota** | Unknown | Unknown | OK | Included in free tier |
| **Embeddings Model** | jina-embeddings-v3 | N/A | OK | 1024 dimensions |
| **Reranker Model** | jina-reranker-v2-base-multilingual | N/A | OK | Multilingual support |
| **Embedding Latency** | ~200-500ms | N/A | OK | Batch requests faster |
| **Batch Size** | Unknown | 2048 texts (API limit) | OK | n8n batches documents |
| **Max Input Length** | 8,192 tokens | 8,192 tokens | OK | Per text |
| **Rate Limit** | Unknown | ~100 RPM (estimate) | OK | Never hit |

**Operational Rules**:
- 1M tokens/month = ~20K documents (avg 50 tokens/doc)
- Late chunking enabled (`late_chunking=True`) for better context
- Key 1 exhausted "Insufficient account balance" (Session 75)
- **Key 2 active**: `jina_63fa...` (Session 75)
- **Self-hosted Jina Space** (`lbjlincoln-nomos-embeddings-api.hf.space`) — Graph pipeline uses this, no API key needed
- API keys expired for some operations; prefer self-hosted Space for embeddings

### Cohere (Trial Tier — EXHAUSTED)

| Resource | Status | Notes |
|----------|--------|-------|
| **Trial Quota** | Nearly exhausted | 429 errors |
| **Reranker** | command-r | Backup only |
| **Embeddings** | embed-english-v3.0 | Backup index (sota-rag-cohere-1024) |

**Operational Rules**:
- Use Jina as primary for embeddings/reranking
- Cohere as BACKUP ONLY when Jina unavailable
- Trial tier has NO renewal (must upgrade to paid)

### HuggingFace (Free Tier)

| Resource | Current | Limit | Notes |
|----------|---------|-------|-------|
| **API Key** | Active | N/A | hf_*** |
| **Hub API Requests** | Unknown | Unlimited | OK |
| **Datasets Download** | Unknown | Unlimited | Bandwidth throttled after heavy use |
| **Spaces** | 9 across 2 accounts | 5 per account (Free tier) | cpu-basic, 16 GB RAM each |
| **Spaces Uptime** | Best-effort | N/A | Keep-alive cron every 30 min |
| **Spaces Storage** | Unknown | 50 GB per Space | Ephemeral (SQLite lost on restart) |
| **HF Tokens** | 3 | N/A | HF_TOKEN (LBJLincoln), HF_TOKEN_2 (LBJLincoln), HF_TOKEN_3 (third account) |

---

## Credentials & Access

### n8n — HF Space #1

| Credential | Type | ID | Usage |
|------------|------|-----|-------|
| **Login** | Email/Password | ci@nomos.ai / CI-Nomos-2026! | Field: `emailOrLdapLoginId` |
| **Auth** | Cookie-based | N/A | JWT invalidates on HF rebuild |
| **Helper** | Python script | `scripts/n8n-api.py` | list/get/deploy/activate |
| **DB** | SQLite | Ephemeral | For workflow storage only |
| **OpenRouter (Standard)** | httpHeaderAuth | `VTFur78v4L4wWEk9` | Standard RAG pipeline |
| **OpenRouter (Graph)** | httpHeaderAuth | `8zKa8MqNEHsbVGKp` | Graph RAG pipeline |
| **OpenRouter (Quantitative)** | httpHeaderAuth | `lGI3u8XGRIwaFq1e` | Quantitative pipeline |
| **OpenRouter (Orchestrator)** | httpHeaderAuth | `S7i3kAtU5ZqIVCYS` | Orchestrator pipeline |
| **LiteLLM Proxy Key** | httpHeaderAuth | `mStiDbYim2aZ0cMq` | Ingestion + Enrichment |
| **Jina API Key** | httpHeaderAuth | `I68x3RvlHJZyQuR6` | Embeddings (key 2) |
| **Supabase Postgres** | postgres | `b44avEJtnkw46GL6` | SQL queries (WORKING, Session 75) |
| **Supabase Postgres (broken)** | postgres | `cH96tQ3I9uIHqiiq` | DO NOT USE |
| **Pinecone API Key** | httpHeaderAuth | `US6Cxlgs8LfyZWss` | Vector search |

**NOTE**: 209 credentials in n8n (massive duplication from 10 HF Spaces sharing same Postgres).

### MCP Servers (7 configured)

| MCP Server | Endpoint | Auth Method | Token Location |
|------------|----------|-------------|----------------|
| **n8n** | http://localhost:5678/mcp-server/http | Bearer token | `N8N_MCP_TOKEN` in `.env.local` |
| **pinecone** | HTTPS API Pinecone | API Key | `PINECONE_API_KEY` in `.mcp.json` env |
| **neo4j** | https://38c949a2.databases.neo4j.io | Basic auth (neo4j/password) | `NEO4J_PASSWORD` in `.mcp.json` env |
| **supabase** | aws-1-eu-west-1.pooler.supabase.com:6543 | Password auth | `SUPABASE_PASSWORD` in `.mcp.json` env |
| **jina-embeddings** | https://api.jina.ai/v1/embeddings | API Key | `JINA_API_KEY` in `.mcp.json` env |
| **cohere** | https://api.cohere.ai/v1 | API Key | `COHERE_API_KEY` in `.mcp.json` env |
| **huggingface** | HuggingFace Hub API | API Key | `HF_TOKEN` in `.mcp.json` env |

**Security Warning**: `.mcp.json` contains keys in `env` sections. File is in `.gitignore`. Migration recommended: move to `.env.local` references.

---

## Environment Variables

### Critical Variables (Docker Compose / HF Space)

| Variable | Value Type | Workflows Using |
|----------|-----------|----------------|
| `OPENROUTER_API_KEY` | `sk-or-v1-***...abc` | orchestrator, quantitative, benchmark-dataset-ingestion |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | orchestrator, quantitative |
| `LLM_SQL_MODEL` | `meta-llama/llama-3.3-70b-instruct:free` | quantitative |
| `LLM_FAST_MODEL` | `google/gemma-3-27b-it:free` | orchestrator, quantitative |
| `LLM_INTENT_MODEL` | `meta-llama/llama-3.3-70b-instruct:free` | orchestrator |
| `LLM_PLANNER_MODEL` | `meta-llama/llama-3.3-70b-instruct:free` | orchestrator |
| `LLM_AGENT_MODEL` | `meta-llama/llama-3.3-70b-instruct:free` | orchestrator |
| `EMBEDDING_API_KEY` | `jina_***...xyz` | benchmark-dataset-ingestion, ingestion |
| `EMBEDDING_API_URL` | `https://api.jina.ai/v1/embeddings` | benchmark-dataset-ingestion, ingestion |
| `EMBEDDING_MODEL` | `jina-embeddings-v3` | benchmark-dataset-ingestion, ingestion |
| `PINECONE_API_KEY` | `pcsk_***...def` | benchmark-dataset-ingestion |
| `PINECONE_HOST` | `sota-rag-jina-1024-***.svc.aped-***.pinecone.io` | benchmark-dataset-ingestion |
| `NEO4J_URL` | `https://38c949a2.databases.neo4j.io/db/neo4j/query/v2` | benchmark-dataset-ingestion, enrichment |
| `NEO4J_USER` | `neo4j` | benchmark-dataset-ingestion |
| `NEO4J_PASSWORD` | `***` | benchmark-dataset-ingestion |
| `N8N_BLOCK_ENV_ACCESS_IN_NODE` | `false` | ALL workflows using $env.VAR_NAME |

**Critical**: `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` enables $env.VAR_NAME access. Without this, expressions return undefined. Added to entrypoint.sh in Session 62.

### Multi-Endpoint Routing (10 HF Spaces, Session 62)

| Variable | Value | Purpose |
|----------|-------|---------|
| `HF_SPACE_1_URL` through `HF_SPACE_10_URL` | `https://lbjlincoln-nomos-rag-engine-*.hf.space` | Multi-endpoint routing |
| `N8N_ALL_HOSTS` | Comma-separated list of all 10 URLs | Round-robin load balancing |
| `N8N_HOST_STANDARD` | `${N8N_ALL_HOSTS}` | Standard pipeline endpoint |
| `N8N_HOST_GRAPH` | `${N8N_ALL_HOSTS}` | Graph pipeline endpoint |
| `N8N_HOST_QUANTITATIVE` | `${N8N_ALL_HOSTS}` | Quantitative pipeline endpoint |
| `N8N_HOST_ORCHESTRATOR` | `${N8N_ALL_HOSTS}` | Orchestrator pipeline endpoint |

### Scripts/VM Variables (`.env.local`)

| Variable | Description | Used By |
|----------|-------------|---------|
| `N8N_HOST` | `https://lbjlincoln-nomos-rag-engine.hf.space` | Scripts eval Python |
| `N8N_API_KEY` | JWT n8n API auth (updated 2026-03-12, subject f1c43c50) | Scripts eval, sync.py |
| `N8N_MCP_TOKEN` | Token MCP n8n server (updated 2026-03-12, subject f1c43c50) | Claude Code MCP |
| `PINECONE_API_KEY` | Pinecone API key | MCP pinecone, Docker |
| `JINA_API_KEY` | Jina AI API key | MCP jina-embeddings |
| `COHERE_API_KEY` | Cohere API key (trial exhausted) | MCP cohere |
| `NEO4J_URI` | `neo4j+s://38c949a2.databases.neo4j.io` | MCP neo4j |
| `NEO4J_PASSWORD` | Neo4j Aura password | MCP neo4j, Docker |
| `SUPABASE_URL` | Supabase project URL | MCP supabase |
| `SUPABASE_API_KEY` | Service role key | MCP supabase |
| `SUPABASE_PASSWORD` | PostgreSQL password | MCP supabase |
| `HF_TOKEN` | HuggingFace token (LBJLincoln) | MCP huggingface, Docker |
| `HF_TOKEN_2` | Secondary HF token (LBJLincoln) | `scripts/deploy-hf-space.sh` (optional) |
| `HF_TOKEN_3` | Third HF token (`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`) | Third account access |
| `VERCEL_TOKEN` | Vercel deploy token | Deployment |
| `ANTHROPIC_MODEL` | `claude-opus-4-6` | Claude Code |

**Git Remotes** (with token integrated):
```
origin             → https://ghp_***@github.com/LBJLincoln/mon-ipad.git
rag-tests          → https://ghp_***@github.com/LBJLincoln/rag-tests.git
rag-website        → https://ghp_***@github.com/LBJLincoln/rag-website.git
rag-dashboard      → https://ghp_***@github.com/LBJLincoln/rag-dashboard.git
rag-data-ingestion → https://ghp_***@github.com/LBJLincoln/rag-data-ingestion.git
rag-pme-connectors → https://ghp_***@github.com/LBJLincoln/rag-pme-connectors.git
rag-pme-usecases   → https://ghp_***@github.com/LBJLincoln/rag-pme-usecases.git
rag-storage        → https://ghp_***@github.com/LBJLincoln/rag-storage.git
```

### Pre-Push Security Check

```bash
git diff --cached | grep -iE 'sk-or-|pcsk_|jV_zGdx|sbp_|hf_|jina_|ghp_'
```

---

## Limits & Quotas

### VM Google Cloud

| Resource | Current | Limit | Status | Impact |
|----------|---------|-------|--------|--------|
| **RAM** | ~865 MB | 969 MB | CRITICAL | ~104 MB available |
| **Swap** | ~1084 MB | 2047 MB | HIGH | VM swaps regularly |
| **CPU** | Variable | 1 vCPU | MEDIUM | Single-threaded bottleneck |
| **Disk** | 12 GB | 30 GB | OK | 17 GB free |
| **Network** | Unknown | 1 GB/month | UNKNOWN | May throttle |

**Actions When Hit**:
- RAM: Kill processes, use HF Space/Codespaces
- Swap: Move work to HF Space
- Disk: Archive to rag-storage GitHub LFS

### GitHub Codespaces

| Resource | Limit | Impact |
|----------|-------|--------|
| **Active Hours** | 60h/month | CRITICAL — shared across all codespaces |
| **Simultaneous** | 2 running max | Can create 3+ but only 2 can run |
| **Storage** | 500 MB | Code only, no large binaries |
| **LFS Bandwidth** | 1 GB/month | Not used |

**60h/month breakdown**:
- Standard (2 core, 8 GB) = 2x multiplier → 30h real quota
- basicLinux32gb (8 core, 32 GB) = 8x multiplier → 7.5h real quota

### Free Tier Services

| Service | Resource | Current | Limit | Headroom |
|---------|----------|---------|-------|----------|
| **Pinecone** | E5 vectors total | ~78K (across 2 indexes) | 100K per index | ~22K per index headroom |
| **Pinecone** | Indexes | 4 | 5 | 1 |
| **Neo4j** | Nodes | ~71,890 | 200K | 128,110 (64%) |
| **Neo4j** | Relationships | 76,717 | 400K | 323,283 (81%) |
| **Supabase** | Storage | ~100 MB | 500 MB | ~400 MB (80%) |
| **Supabase** | Connections | Unknown | 60 (Pooler) | OK |
| **Jina AI** | Tokens/month | Unknown | 1M | OK |
| **OpenRouter** | Rate limit (Llama 70B) | Variable | ~20 RPM | 429 errors possible |
| **OpenRouter** | Rate limit (Gemma 27B) | Variable | ~30 RPM | Faster model |
| **Vercel** | Bandwidth | Unknown | 100 GB/month | OK |
| **Vercel** | Build minutes | Minimal | 6000 min/month | OK |

### Claude Code (Max Plan)

| Resource | Current | Limit | Notes |
|----------|---------|-------|-------|
| **Model** | claude-opus-4-6 | N/A | Subscription Max plan |
| **Session Length** | Variable | 2h recommended (Rule 26) | Efficiency degrades after 2h |
| **RAM Consumption** | ~297 MB | N/A | 30% of VM RAM |
| **Context Window** | 200K tokens | 200K tokens | Entire codebase fits |

---

## Storage Strategy

### Current State (Phase 3)

| Location | Used | Free | Contents |
|----------|------|------|----------|
| **VM disk** | 12 GB | 17 GB | Code, datasets (phase 1-3), eval results |
| **Pinecone sota-rag-jina-1024** | ~35K vectors | 100K limit | Benchmark + standard contexts |
| **Pinecone website-sectors-jina-1024** | ~43K vectors | 100K limit | 4 sectors (BTP, Finance, Industrie, Juridique) |
| **Neo4j Aura** | 71,890 nodes / 76,717 rels | 200K / 400K limit | Entities + relationships |
| **Supabase** | ~76K+ rows | 500MB limit | 43K sector docs + 225 financials + 3,876 fin tables + 29,564 eval questions |
| **GitHub LFS (rag-storage)** | ~200 MB | 1 GB limit | Archived datasets, snapshots |

### Strategy by Phase

**Phase 3 (current — 11,700 questions)**:
- **VM**: Keep all 4 dataset files (~75 MB) + merged file (72 MB)
- **Pinecone**: Ingest standard contexts (~7,700 unique) → default namespace
- **Neo4j**: Already populated (19,965 nodes from phase2_extraction)
- **Supabase**: Financial tables already exist (no new ingestion needed)

**Phase 4 (planned — ~100K questions, ~700 MB datasets)**:
- **VM**: Only keep active dataset files, archive completed phases
- **rag-storage**: Push completed phase datasets to GitHub LFS
- **Pinecone**: May need second index or namespace rotation
- **Neo4j**: Monitor node count (200K limit)
- **Ingestion**: Use HF Space n8n workflows or batch scripts from VM

**Phase 5 (future — 1M+ questions)**:
- **VM**: Streaming ingestion only, no local dataset storage
- **HF Space**: Primary ingestion engine (16 GB RAM)
- **rag-storage**: All datasets in GitHub LFS
- **Consider**: Pinecone paid tier, Neo4j paid tier

### Archival Process

```bash
# Push to rag-storage
cd /home/termius/mon-ipad
tar czf /tmp/phase-N-archive.tar.gz datasets/phase-N/
git -C /path/to/rag-storage add phase-N-archive.tar.gz
git -C /path/to/rag-storage commit -m "Archive phase N datasets"
git -C /path/to/rag-storage push

# Remove from VM
rm -rf datasets/phase-N/
```

### Pinecone Token Budget (Jina Free Tier)

| Phase | Unique Contexts | Est. Tokens | Days at 1M/day |
|-------|----------------|-------------|-----------------|
| Phase 3 Standard | 7,700 | ~13.5M | ~14 days |
| Phase 4 (projected) | ~70K | ~120M | ~120 days |

**Optimization**: Only embed contexts not already in benchmark-* namespaces.

---

## Workflow Registry

### Active Workflows (Session 105 — 2026-03-12)

**RAG Pipelines (4) — ALL via LiteLLM S7**:

| Workflow | Webhook Path | Field | DB | ID | Status |
|----------|-------------|-------|-----|-----------|--------|
| Standard RAG V3.8 | `/webhook/rag-multi-index-v3` | query | Pinecone + Supabase | `TmgyRP20N4JFd9CB` | WORKING (41-50s) |
| Graph RAG V3.5 | `/webhook/ff622742-6d71-4e91-af71-b5c666088717` | query | Neo4j + self-hosted embed | `6257AfT1l4FMC6lY` | WORKING (27-86s) |
| Quantitative V3.2 | `/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9` | query | Supabase SQL | `cjhEhVs0KV1ExHqX` | WORKING (11-87s) |
| Orchestrator V13 | `/webhook/orchestrator-v2` | query | Routes to above | `qOSaFFrqO8Jb4VGb` | WORKING (52s) |

**Support Workflows (6)**:

| Workflow | ID | Status | Notes |
|----------|----|--------|-------|
| Error Trigger Handler V1.0 | `AH3eXOmgxt5cOd93` | ACTIVE (all Spaces) | Error logging to Supabase |
| Auto-Healer V1.2 | `Yqw7Pzn0e7m0C6i3` | ACTIVE (S1/S3/S5) | 10min cycle, 4 Spaces, webhook pings |
| Ingestion V4.0 | `nh1D4Up0wBZhuQbp` | ACTIVE | Docling + Pinecone + Supabase upserts |
| Enrichissement V4.0 | `ORa01sX4xI0iRCJ8` | ACTIVE | Neo4j entity enrichment |

**PME Workflows (3)**:

| Workflow | Description | Status |
|----------|-------------|--------|
| PME Gateway | Main entry point | ACTIVE |
| PME Slack Connector | Slack integration | ACTIVE |
| PME Gmail Connector | Gmail integration | ACTIVE |

### Continuous Ingestion Daemon

| Resource | Value | Notes |
|----------|-------|-------|
| **Script** | `ops/continuous-ingest.py --loop 3600` | Runs on VM, 1-hour cycles |
| **Pipeline** | Exa.AI search → Docling S6 → Chunking → Embedding → Pinecone + Supabase | All 4 sectors |
| **Docling Integration** | Sends PDFs to S6 Space for processing | Markdown + structured extraction |
| **n8n Workflows** | Ingestion V4.0 (`nh1D4Up0wBZhuQbp`) + Enrichment V4.0 (`ORa01sX4xI0iRCJ8`) | Pinecone + Supabase + Neo4j |
| **Growth Rate** | ~7K vectors/cycle (Exa.AI-sourced) | From ~71K to ~78K in recent cycles |
| **Status** | **RUNNING** | Daemon managed via `ops/agents.py` |

### Target Architecture (16 workflows)

**Category A: Test-RAG (4 pipelines)** — ACTIVE NOW
**Category B: Sector (4 pipelines)** — After Phase 2 validated
**Category C: Ingestion (2+2 workflows)** — 2 active, 2 after Phase 2
**Support (4 workflows)** — Dashboard Status API, Benchmark, Dataset Ingestion, SQL Executor

### Workflow Fixes Library (Session 75)

| Fix | Pipeline | Problem | Solution |
|-----|---------|---------|----------|
| FIX-71 | All | Duplicate workflows share webhook ID | Check execution's `workflowId` |
| FIX-75-1 | Quant | Wrong credential | Switch to `b44avEJtnkw46GL6` |
| FIX-75-2 | Quant | SQL Validator markdown escaping | Remove backticks from LLM response |
| FIX-75-3 | Quant | Wrong tenant_id | Use `benchmark` NOT `default` |

---

## Monitoring Commands

```bash
# VM Resources
free -h                                    # RAM/Swap usage
df -h                                      # Disk usage
docker stats --no-stream                   # Container resource usage
ps aux --sort=-%mem | head -10            # Top RAM consumers

# GitHub Codespaces
gh codespace list                          # Active codespaces
scripts/codespace-control.sh monitor 30    # Live monitoring

# n8n
curl https://lbjlincoln-nomos-rag-engine.hf.space/healthz  # Health check
docker logs n8n-n8n-1 --tail 100          # Recent logs (if VM)

# Database Sizes
# Pinecone: Check dashboard at app.pinecone.io
# Neo4j: MATCH (n) RETURN count(n) AS nodes
# Supabase: Check dashboard at supabase.com/dashboard
```

---

## Critical Constraints Summary (Top 10)

| # | Constraint | Hard Limit | Current | Headroom | Action When Hit |
|---|------------|------------|---------|----------|-----------------|
| 1 | **VM RAM** | 969 MB | ~865 MB | ~100 MB | Kill processes, use HF Space |
| 2 | **GitHub Codespaces Hours** | 60h/month | Variable | Unknown | Stop unused, track hours |
| 3 | **Codespaces Simultaneous** | 2 running | 0-2 | 0-2 | Stop one to start another |
| 4 | **n8n Concurrent Webhooks** | ~3-5 | Variable | Low | Sequential testing only |
| 5 | **OpenRouter Rate Limit** | ~20 RPM/model | Variable | Low | Retry with backoff |
| 6 | **Pinecone Vectors/Index** | 100K | ~35K-43K per index | ~57K-65K | Create new index/namespace |
| 7 | **Neo4j Nodes** | 200K | ~71,890 | 128,110 | Optimize graph, prune old |
| 8 | **Jina Embeddings Quota** | 1M tokens/month | ~60K | ~940K | Batch requests, monitor |
| 9 | **Cohere Trial Quota** | Exhausted | ~100% | None | Use Jina only |
| 10 | **Session Duration** | 2h (recommended) | Variable | N/A | Finalize and restart |

---

## Notes

1. **All limits documented are HARD LIMITS** (cannot be exceeded without upgrade/payment).
2. **Free tier limits are permanent** unless explicitly stated as trial.
3. **"Unknown" usage** indicates monitoring not yet implemented.
4. **This document is the SINGLE SOURCE OF TRUTH** for infrastructure reference.

**Last Verified**: 2026-03-12 (Session 105)
**Next Review**: After 100K vectors milestone or next infra change
