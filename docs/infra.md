# Infrastructure — Single Source of Truth

> Last updated: 2026-03-01T20:30:00Z (Session 67)

## 1. Architecture Overview

```
┌─────────────────┐     ┌──────────────────────────────┐     ┌───────────────────┐
│  VM Google Cloud │────→│  HF Space #1 (n8n 2.8.3)    │────→│  Pinecone (10K+)  │
│  34.136.180.66   │     │  lbjlincoln-nomos-rag-engine │     │  Neo4j (19K+)     │
│  PILOTAGE ONLY   │     │  Standard + Graph + Quant    │     │  Supabase (40 tbl)│
│  Claude Code CLI │     │  16GB RAM, SQLite, Redis     │     └───────────────────┘
└─────────────────┘     └──────────────────────────────┘
        │                         │
        │               ┌────────────────────────────────┐
        │               │  4 Vercel Sites (production)   │
        └──────────────→│  ETI, PME Connectors, PME UC,  │
                        │  Dashboard                      │
                        └────────────────────────────────┘
```

**Execution Rule**: VM = pilotage only. ALL computation on HF Space / Codespaces / GH Actions.

---

## 2. Compute Resources

### VM Google Cloud (permanent)
| Spec | Value |
|------|-------|
| IP | 34.136.180.66 |
| OS | Linux Debian 11 (Bullseye) |
| CPU | 1 vCPU Intel Xeon @ 2.20GHz |
| RAM | 969 MB total, ~413 MB available |
| Disk | 30 GB total, 12 GB used, 17 GB free |
| Role | Claude Code CLI, git, eval scripts → HF Space webhooks |
| n8n | **REMOVED** (Session 42) — all n8n on HF Space |

### HF Space #1 (ACTIVE — primary)
| Spec | Value |
|------|-------|
| URL | `https://lbjlincoln-nomos-rag-engine.hf.space` |
| Account | LBJLincoln |
| n8n | v2.8.3 |
| RAM | 16 GB |
| Storage | SQLite + Redis |
| Pipelines | Standard, Graph, Quantitative (+ support workflows) |
| Status | **UP** (HTTP 200) |

### HF Space #2 (NOT DEPLOYED — planned)
| Spec | Value |
|------|-------|
| URL | TBD |
| Account | LBJLincoln26 or second account |
| Purpose | Orchestrator + overflow for parallel throughput |
| Status | **PENDING** — user must provide valid HF_TOKEN_2 |

### GitHub Codespaces (ephemeral — 60h/mois)
| Spec | Value |
|------|-------|
| CPU | 2 cores |
| RAM | 8 GB |
| Disk | 32 GB |
| Image | Ubuntu + Python 3.11 + Node.js 20 + Docker |
| Use | rag-data-ingestion (heavy), rag-pme-connectors (CI) |

---

## 3. HF Spaces Inventory (10 deployed, 1 ACTIVE)

| # | URL | Account | Status | Notes |
|---|-----|---------|--------|-------|
| 1 | `lbjlincoln-nomos-rag-engine.hf.space` | LBJLincoln | **ACTIVE** | Primary — all pipelines |
| 2-10 | Various | LBJLincoln / LBJLincoln26 | **STALE/DEAD** | Do NOT route traffic here |

**CRITICAL (FIX-66a)**: `N8N_ALL_HOSTS` must contain ONLY Space #1. Round-robin to dead spaces caused 20% accuracy (8/9 requests lost). Fixed in Session 66.

---

## 4. Databases

| Service | Index/DB | Vectors/Nodes | Dimension | Limit | Status |
|---------|----------|---------------|-----------|-------|--------|
| Pinecone | `sota-rag-jina-1024` | 10,411 | 1024 (Jina) | 100K | OK |
| Pinecone | `sota-rag-phase2-graph` | 1,296 | e5-large | 100K | OK |
| Pinecone | `sota-rag` | legacy | 1536 | 100K | Legacy |
| Neo4j Aura | graph DB | 19,788 nodes / 76,717 rels | — | 200K/400K | OK |
| Supabase | PostgreSQL | 40 tables / ~17K rows | — | 500MB | OK |

### Pinecone Namespace Architecture
- **Default namespace**: Actual document content (3,601 vectors) — this is what pipelines query
- **benchmark-* namespaces**: Q&A pairs only (NO content field) — metadata for eval, NOT for retrieval
- **NEVER send namespace to pipeline** — pipeline uses default namespace for retrieval

---

## 5. LLM Models (all FREE via OpenRouter)

| Model | ID | Roles | Cost |
|-------|-----|-------|------|
| Llama 3.3 70B | `meta-llama/llama-3.3-70b-instruct:free` | SQL, Intent, Planning, HyDE, Agent, QA | $0 |
| Gemma 3 27B | `google/gemma-3-27b-it:free` | Fast, Lite | $0 |
| Trinity | `arcee-ai/trinity-large-preview:free` | Entity extraction, Community summaries | $0 |

### API Key Rotation (6 keys, 3 accounts)
| Key Variable | Account | Pipelines |
|-------------|---------|-----------|
| `OPENROUTER_KEY_STANDARD` | Account 1 | Standard |
| `OPENROUTER_KEY_GRAPH` | Account 2 | Graph |
| `OPENROUTER_KEY_QUANTITATIVE` | Account 3 | Quantitative |
| `OPENROUTER_KEY_ORCHESTRATOR` | Account 1 | Orchestrator |
| `OPENROUTER_API_KEY` | Account 1 | Fallback (chatbot, benchmark) |
| `OPENROUTER_KEY_SPARE` | Account 2 | Emergency rotation |

### Embedding Models
| Model | Provider | Dimension | Status |
|-------|----------|-----------|--------|
| jina-embeddings-v3 | Jina AI | 1024 | Primary (1M tokens/month free) |
| Cohere embed | Cohere | 1024 | Backup (trial nearly exhausted) |
| multilingual-e5-large | Pinecone integrated | varies | Phase 2 graph index |

---

## 6. Environment Variables Matrix

### Critical Variables (.env.local)
```bash
# n8n Hosts (Session 66 fix: SINGLE host only)
N8N_HOST=https://lbjlincoln-nomos-rag-engine.hf.space
N8N_ALL_HOSTS=${N8N_HOST}
N8N_HOST_STANDARD=${N8N_HOST}
N8N_HOST_GRAPH=${N8N_HOST}
N8N_HOST_QUANTITATIVE=${N8N_HOST}
N8N_HOST_ORCHESTRATOR=${N8N_HOST}

# n8n Auth
N8N_API_KEY=<from .env.local>
N8N_MCP_TOKEN=<from .env.local>

# LLM
OPENROUTER_API_KEY=<generic fallback>
OPENROUTER_KEY_STANDARD=<per-pipeline>
OPENROUTER_KEY_GRAPH=<per-pipeline>
OPENROUTER_KEY_QUANTITATIVE=<per-pipeline>
OPENROUTER_KEY_ORCHESTRATOR=<per-pipeline>

# Databases
PINECONE_API_KEY=<from .env.local>
NEO4J_URL=<from .env.local>
NEO4J_USER=<from .env.local>
NEO4J_PASSWORD=<from .env.local>
SUPABASE_URL=<from .env.local>
SUPABASE_KEY=<from .env.local>

# Embeddings
JINA_API_KEY=<from .env.local>
COHERE_API_KEY=<from .env.local>
```

### HF Space Required Env Vars
| Variable | Purpose | Critical |
|----------|---------|----------|
| `N8N_BLOCK_ENV_ACCESS_IN_NODE` | Must be `false` for $env access | YES |
| `OPENROUTER_API_KEY` | LLM calls | YES |
| `PINECONE_API_KEY` | Vector search | YES |
| `NEO4J_URL/USER/PASSWORD` | Graph queries | YES |
| `JINA_API_KEY` | Embeddings | YES |
| `N8N_RUNNERS_ENABLED` | Must be `false` (Task Runner cache bug) | YES |

---

## 7. Vercel Deployments (all LIVE)

| Site | URL | Framework | Status |
|------|-----|-----------|--------|
| ETI 4 secteurs | `nomos-ai-pied.vercel.app` | Next.js 14 | UP |
| PME Connectors | `nomos-pme-connectors-alexis-morets-projects.vercel.app` | Next.js 15 | UP |
| PME Use Cases | `nomos-pme-usecases-alexis-morets-projects.vercel.app` | Next.js 14 | UP |
| Dashboard | `nomos-dashboard-alexis-morets-projects.vercel.app` | Static HTML/JS | UP |

**Chatbot Status**: All 4 sites have chatbot widget but API returns `{"error":"fetch failed"}` — can't reach HF Space backend. **NEEDS FIX**.

---

## 8. Repos (7 active)

| Repo | Role | Runs On | Last Commit |
|------|------|---------|-------------|
| **mon-ipad** | Control tower, eval scripts, directives | VM (Claude Code) | Active |
| **rag-tests** | Eval datasets, results archive | VM → HF Space | Active |
| **rag-website** | Next.js 14, 4 ETI sectors, chatbot | Vercel | Active |
| **rag-dashboard** | Static dashboard, metrics | Vercel | Active |
| **rag-data-ingestion** | Ingestion V3.1, enrichment | Codespace / GH Actions | Partial |
| **rag-pme-connectors** | 15 PME apps, MacBook chat | Vercel | Active |
| **rag-pme-usecases** | 200 use cases | Vercel | Active |

---

## 9. MCP Servers (7 configured)

| Server | Purpose | Status |
|--------|---------|--------|
| n8n | Workflow inspection via HF Space | OK (proxy issues possible) |
| pinecone | 3 indexes, 22K+ vectors | OK |
| neo4j | Graph 19K+ nodes, Cypher | OK |
| supabase | Direct SQL queries | OK |
| jina-embeddings | 1024-dim embeddings + Pinecone CRUD | OK (1M tokens/month) |
| cohere | Reranking | Trial nearly exhausted |
| huggingface | Model/dataset search | OK |

---

## 10. Throughput & Performance

### Current Throughput (Session 66)
| Pipeline | Batch Size | Concurrency | Avg Latency | Throughput |
|----------|-----------|-------------|-------------|------------|
| Standard | 5 | 5 concurrent | 15-20s | ~15 q/min |
| Graph | 5 | 3 concurrent | 15-25s | ~10 q/min |
| Quantitative | 3 | 1 concurrent | 10-15s | ~8 q/min |
| Orchestrator | 2 | 1 concurrent | 20-30s | ~3 q/min |

### Bottlenecks (ranked by impact)
1. **Single HF Space** — all 4 pipelines compete for 16GB RAM/CPU → deploy Space #2
2. **Jina rate limit** — 1M tokens/month → get additional keys or use LiteLLM proxy
3. **OpenRouter free tier** — 20 req/min/key → 6 keys help but still limiting at scale
4. **Orchestrator complexity** — 68 nodes, sequential routing → inherently slow
5. **No caching** — Same questions re-embed every call → add Redis/local cache

### Target Throughput (Session 67+)
- **Goal**: 500 q/min per pipeline (user explicit request)
- **Requires**: Multiple HF Spaces, Jina key pool, LiteLLM proxy, result caching

---

## 11. n8n Credentials (HF Space live IDs)

| Credential | Type | HF Space ID | Purpose |
|-----------|------|-------------|---------|
| Supabase Postgres | PostgreSQL | `Vrvh0ukcROAk9dyX` | BM25 search, quant data |
| Redis Upstash | Redis | `IDrWmZSQb5ziEQeC` | Caching (orchestrator) |
| OpenRouter | HTTP Header Auth | varies per workflow | LLM calls |
| Jina AI | HTTP Header Auth | varies | Embeddings + reranking |

**WARNING**: HF Space rebuild wipes SQLite → all credentials lost. Must restore via `POST /api/v1/credentials` (FIX-58).
