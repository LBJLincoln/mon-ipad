# Environment Variables & Credentials — Document Exhaustif

> Last updated: 2026-02-25T11:30:00+00:00
> Ce fichier documente TOUTES les variables d'environnement, credentials et connexions
> utilisees par le projet Multi-RAG. Les valeurs sont masquees (`.env.local` = source).

---

## Section 1 : n8n Workflow Env Vars (~33 vars)

Variables referencees par `$env.VAR_NAME` dans les workflows n8n (`n8n/live/*.json`).

### LLM & Model APIs
| Variable | Valeur type | Workflows utilisant |
|----------|-------------|---------------------|
| `OPENROUTER_API_KEY` | `sk-or-v1-***...abc` | orchestrator, quantitative, benchmark-dataset-ingestion |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | orchestrator, quantitative |
| `LLM_SQL_MODEL` | `meta-llama/llama-3.3-70b-instruct:free` | quantitative |
| `LLM_FAST_MODEL` | `google/gemma-3-27b-it:free` | orchestrator, quantitative |
| `LLM_INTENT_MODEL` | `meta-llama/llama-3.3-70b-instruct:free` | orchestrator |
| `LLM_PLANNER_MODEL` | `meta-llama/llama-3.3-70b-instruct:free` | orchestrator |
| `LLM_AGENT_MODEL` | `meta-llama/llama-3.3-70b-instruct:free` | orchestrator |
| `LLM_API_URL` | `https://openrouter.ai/api/v1` | ingestion |

### Embeddings & Chunking
| Variable | Valeur type | Workflows utilisant |
|----------|-------------|---------------------|
| `EMBEDDING_API_KEY` | `jina_***...xyz` | benchmark-dataset-ingestion |
| `EMBEDDING_API_URL` | `https://api.jina.ai/v1/embeddings` | benchmark-dataset-ingestion, ingestion |
| `EMBEDDING_MODEL` | `jina-embeddings-v3` | benchmark-dataset-ingestion, ingestion |
| `CHUNKING_MODEL` | `meta-llama/llama-3.3-70b-instruct:free` | ingestion |
| `QA_MODEL` | `meta-llama/llama-3.3-70b-instruct:free` | ingestion |

### RAG-Specific APIs
| Variable | Valeur type | Workflows utilisant |
|----------|-------------|---------------------|
| `CONTEXTUAL_RETRIEVAL_API_URL` | `https://openrouter.ai/api/v1` | ingestion |
| `CONTEXTUAL_RETRIEVAL_MODEL` | `meta-llama/llama-3.3-70b-instruct:free` | ingestion |
| `ENTITY_EXTRACTION_API_URL` | `https://openrouter.ai/api/v1` | enrichment |
| `ENTITY_EXTRACTION_MODEL` | `arcee-ai/trinity-large-preview:free` | enrichment |
| `GENERATION_API_URL` | `https://openrouter.ai/api/v1` | feedback |
| `GENERATION_MODEL` | `meta-llama/llama-3.3-70b-instruct:free` | feedback |

### Vector & Graph Databases
| Variable | Valeur type | Workflows utilisant |
|----------|-------------|---------------------|
| `PINECONE_API_KEY` | `pcsk_***...def` | benchmark-dataset-ingestion |
| `PINECONE_HOST` | `sota-rag-jina-1024-***.svc.aped-***.pinecone.io` | benchmark-dataset-ingestion |
| `PINECONE_URL` | `https://sota-rag-jina-1024-***.svc.aped-***.pinecone.io` | benchmark-dataset-ingestion, enrichment, ingestion |
| `NEO4J_URL` | `https://38c949a2.databases.neo4j.io/db/neo4j/query/v2` | benchmark-dataset-ingestion, enrichment |
| `NEO4J_USER` | `neo4j` | benchmark-dataset-ingestion |
| `NEO4J_PASSWORD` | `***` | benchmark-dataset-ingestion |

### n8n Orchestration
| Variable | Valeur type | Workflows utilisant |
|----------|-------------|---------------------|
| `N8N_API_KEY` | JWT token | benchmark-orchestrator-tester, benchmark-rag-tester |
| `N8N_BASE_URL` | `http://localhost:5678` | benchmark-orchestrator-tester, benchmark-rag-tester, feedback |
| `N8N_BLOCK_ENV_ACCESS_IN_NODE` | `false` | All workflows using $env.VAR_NAME expressions in SQL/Code nodes |
| `HF_SPACE_1_URL` | `https://lbjlincoln-nomos-rag-engine.hf.space` | Multi-endpoint routing |
| `HF_SPACE_2_URL` | `https://<space-2>.hf.space` | Multi-endpoint routing |
| `HF_SPACE_3_URL` | `https://<space-3>.hf.space` | Multi-endpoint routing |
| `HF_SPACE_4_URL` | `https://<space-4>.hf.space` | Multi-endpoint routing |
| `HF_SPACE_5_URL` | `https://<space-5>.hf.space` | Multi-endpoint routing |
| `HF_SPACE_6_URL` | `https://<space-6>.hf.space` | Multi-endpoint routing |
| `HF_SPACE_7_URL` | `https://<space-7>.hf.space` | Multi-endpoint routing |
| `HF_SPACE_8_URL` | `https://<space-8>.hf.space` | Multi-endpoint routing |
| `HF_SPACE_9_URL` | `https://<space-9>.hf.space` | Multi-endpoint routing |
| `HF_SPACE_10_URL` | `https://<space-10>.hf.space` | Multi-endpoint routing |
| `N8N_ALL_HOSTS` | Comma-separated list of all 10 HF Space URLs | Round-robin load balancing |
| `N8N_HOST_STANDARD` | `${N8N_ALL_HOSTS}` | Standard pipeline endpoint (round-robin) |
| `N8N_HOST_GRAPH` | `${N8N_ALL_HOSTS}` | Graph pipeline endpoint (round-robin) |
| `N8N_HOST_QUANTITATIVE` | `${N8N_ALL_HOSTS}` | Quantitative pipeline endpoint (round-robin) |
| `N8N_HOST_ORCHESTRATOR` | `${N8N_ALL_HOSTS}` | Orchestrator pipeline endpoint (round-robin) |

### Observability & Monitoring
| Variable | Valeur type | Workflows utilisant |
|----------|-------------|---------------------|
| `OTEL_COLLECTOR_URL` | `http://localhost:4318` | enrichment, ingestion, quantitative |
| `OTEL_EXPORTER_URL` | `http://localhost:4318` | benchmark-dataset-ingestion, benchmark-monitoring, benchmark-orchestrator-tester, benchmark-rag-tester |
| `SENTRY_DSN` | `https://***@sentry.io/***` | orchestrator |

### External Services
| Variable | Valeur type | Workflows utilisant |
|----------|-------------|---------------------|
| `HF_TOKEN` | `hf_***` | benchmark-dataset-ingestion |
| `SLACK_WEBHOOK_URL` | `https://hooks.slack.com/services/***` | feedback |
| `SLACK_BENCHMARK_WEBHOOK` | `https://hooks.slack.com/services/***` | benchmark-monitoring |

---

## Section 2 : LLM Model Vars (Docker Compose)

Variables definies dans `rag-tests-docker-compose.yml` pour les workers n8n.

| Variable | Modele | Role | Famille |
|----------|--------|------|---------|
| `LLM_SQL_MODEL` | `meta-llama/llama-3.3-70b-instruct:free` | Generation SQL (Quantitative) | Llama 70B |
| `LLM_FAST_MODEL` | `google/gemma-3-27b-it:free` | Operations rapides | Gemma 27B |
| `LLM_INTENT_MODEL` | `meta-llama/llama-3.3-70b-instruct:free` | Classification intent (Orchestrator) | Llama 70B |
| `LLM_PLANNER_MODEL` | `meta-llama/llama-3.3-70b-instruct:free` | Task planning (Orchestrator) | Llama 70B |
| `LLM_AGENT_MODEL` | `meta-llama/llama-3.3-70b-instruct:free` | Agent reasoning (Orchestrator) | Llama 70B |
| `LLM_HYDE_MODEL` | `meta-llama/llama-3.3-70b-instruct:free` | HyDE generation | Llama 70B |
| `LLM_EXTRACTION_MODEL` | `arcee-ai/trinity-large-preview:free` | Entity extraction (Enrichment) | Trinity |
| `LLM_COMMUNITY_MODEL` | `arcee-ai/trinity-large-preview:free` | Community summaries (Graph) | Trinity |
| `LLM_LITE_MODEL` | `google/gemma-3-27b-it:free` | Lightweight tasks | Gemma 27B |

### Resume par famille de modele
| Famille | Modele complet | Roles | Cout |
|---------|---------------|-------|------|
| **Llama 70B** | `meta-llama/llama-3.3-70b-instruct:free` | SQL, Intent, Planning, HyDE, Agent, QA, Chunking, Contextual, Generation | $0 |
| **Gemma 27B** | `google/gemma-3-27b-it:free` | Fast, Lite | $0 |
| **Trinity** | `arcee-ai/trinity-large-preview:free` | Extraction, Community | $0 |

---

## Section 3 : Scripts/VM Vars (`.env.local`)

Variables definies dans `.env.local` pour les scripts Python et outils locaux.

| Variable | Description | Utilise par |
|----------|-------------|-------------|
| `N8N_HOST` | `http://localhost:5678` | Scripts eval Python |
| `N8N_API_KEY` | JWT Docker n8n API auth | Scripts eval, sync.py |
| `N8N_MCP_TOKEN` | Token MCP n8n server | Claude Code MCP |
| `OPENROUTER_API_KEY` | Cle API OpenRouter | Docker n8n env |
| `PINECONE_API_KEY` | Cle API Pinecone | MCP pinecone, Docker |
| `PINECONE_HOST` | Host Pinecone index | MCP pinecone |
| `JINA_API_KEY` | Cle API Jina AI | MCP jina-embeddings |
| `COHERE_API_KEY` | Cle API Cohere (trial quasi-epuise) | MCP cohere |
| `NEO4J_URI` | `neo4j+s://38c949a2.databases.neo4j.io` | MCP neo4j |
| `NEO4J_PASSWORD` | Password Neo4j Aura | MCP neo4j, Docker |
| `SUPABASE_URL` | URL Supabase project | MCP supabase |
| `SUPABASE_API_KEY` | Service role key Supabase | MCP supabase |
| `SUPABASE_PASSWORD` | Password PostgreSQL Supabase | MCP supabase |
| `HF_TOKEN` | Token HuggingFace | MCP huggingface, Docker |
| `HF_TOKEN_2` | Secondary HuggingFace token for redundant HF Space deployment | `scripts/deploy-hf-space.sh` (optional) |
| `VERCEL_TOKEN` | Token Vercel deploy | Deployment |
| `N8N_UI_EMAIL` | `admin@mon-ipad.com` | n8n login |
| `N8N_UI_PASSWORD` | Password UI n8n | n8n login |
| `ANTHROPIC_MODEL` | `claude-opus-4-6` | Claude Code |

### Variables dans `.env.example` uniquement (pas dans `.env.local` courant)
| Variable | Description | Statut |
|----------|-------------|--------|
| `DB_POSTGRESDB_PASSWORD` | PostgreSQL local n8n | Defini dans docker-compose |
| `N8N_ENCRYPTION_KEY` | Cle chiffrement n8n credentials | Defini dans docker-compose |

---

## Section 4 : n8n Credential Objects

Credentials stockees dans n8n Docker (chiffrees par `N8N_ENCRYPTION_KEY`).

| Credential | Type | ID n8n | Details |
|------------|------|--------|---------|
| **Supabase Postgres (Pooler)** | postgres | `USU8ngVzsUbED3mn` | host: `aws-1-eu-west-1.pooler.supabase.com`, port: 6543, user: `postgres.ayqviqmxifzmhphiqfmj`, database: `postgres` |
| **Redis Upstash** | redis | `CWih07lwPxfwFeY6` | host: `dynamic-frog-47846.upstash.io`, port: 6379, TLS: true |

### Notes
- Les credentials n8n sont referencees dans les workflows par leur ID (ex: `"id": "USU8ngVzsUbED3mn"`)
- Pipeline Quantitative utilise `USU8ngVzsUbED3mn` pour exec_sql RPC
- Le credential `zEr7jPswZNv6lWKu` (ancien) a ete remplace par `USU8ngVzsUbED3mn` en session 17

---

## Section 5 : MCP Connections (7 serveurs)

Serveurs MCP configures dans `.mcp.json` et `.claude/settings.json`.

| MCP Server | Endpoint | Auth Method | Token Location |
|------------|----------|-------------|----------------|
| **n8n** | `http://localhost:5678/mcp-server/http` | Bearer token | `N8N_MCP_TOKEN` dans `.env.local` |
| **pinecone** | HTTPS API Pinecone | API Key | `PINECONE_API_KEY` dans `.mcp.json` env |
| **neo4j** | `https://38c949a2.databases.neo4j.io` | Basic auth (neo4j/password) | `NEO4J_PASSWORD` dans `.mcp.json` env |
| **supabase** | `aws-1-eu-west-1.pooler.supabase.com:6543` | Password auth | `SUPABASE_PASSWORD` dans `.mcp.json` env |
| **jina-embeddings** | `https://api.jina.ai/v1/embeddings` | API Key | `JINA_API_KEY` dans `.mcp.json` env |
| **cohere** | `https://api.cohere.ai/v1` | API Key | `COHERE_API_KEY` dans `.mcp.json` env |
| **huggingface** | HuggingFace Hub API | API Key | `HF_TOKEN` dans `.mcp.json` env |

### Avertissement securite
`.mcp.json` contient des cles en dur dans les sections `env`. Ce fichier est dans `.gitignore`.
Migration recommandee : deplacer vers references `.env.local` pour tous les MCP.

---

## Section 6 : GitHub/Vercel/External

| Service | Variable | Description | Location |
|---------|----------|-------------|----------|
| **GitHub** | `GITHUB_TOKEN` (implicite) | Token `ghp_***` dans les remotes git | `.git/config` (pas dans .env) |
| **Vercel** | `VERCEL_TOKEN` | Deploy token | `.env.local` |
| **GitHub Actions** | Secrets repo | `N8N_API_KEY`, `OPENROUTER_API_KEY`, etc. | GitHub Settings > Secrets |

### Git Remotes (avec token integre)
```
origin             → https://ghp_***@github.com/LBJLincoln/mon-ipad.git
rag-tests          → https://ghp_***@github.com/LBJLincoln/rag-tests.git
rag-website        → https://ghp_***@github.com/LBJLincoln/rag-website.git
rag-dashboard      → https://ghp_***@github.com/LBJLincoln/rag-dashboard.git
rag-data-ingestion → https://ghp_***@github.com/LBJLincoln/rag-data-ingestion.git
```

---

## Section 7 : Matrice Workflow x Env Var

Tableau croisant les 13 workflows actifs avec les variables d'environnement qu'ils utilisent.

| Variable | standard | graph | quant | orch | benchmark | dataset-ing | monitoring | orch-tester | rag-tester | sql-exec | ingestion | enrichment | feedback |
|----------|----------|-------|-------|------|-----------|-------------|------------|-------------|------------|----------|-----------|------------|----------|
| `OPENROUTER_API_KEY` | | | X | X | | X | | | | | | | |
| `OPENROUTER_BASE_URL` | | | X | X | | | | | | | | | |
| `LLM_SQL_MODEL` | | | X | | | | | | | | | | |
| `LLM_FAST_MODEL` | | | X | X | | | | | | | | | |
| `LLM_INTENT_MODEL` | | | | X | | | | | | | | | |
| `LLM_PLANNER_MODEL` | | | | X | | | | | | | | | |
| `LLM_AGENT_MODEL` | | | | X | | | | | | | | | |
| `LLM_API_URL` | | | | | | | | | | | X | | |
| `EMBEDDING_API_KEY` | | | | | | X | | | | | | | |
| `EMBEDDING_API_URL` | | | | | | X | | | | | X | | |
| `EMBEDDING_MODEL` | | | | | | X | | | | | X | | |
| `CHUNKING_MODEL` | | | | | | | | | | | X | | |
| `QA_MODEL` | | | | | | | | | | | X | | |
| `CONTEXTUAL_RETRIEVAL_*` | | | | | | | | | | | X | | |
| `ENTITY_EXTRACTION_*` | | | | | | | | | | | | X | |
| `GENERATION_*` | | | | | | | | | | | | | X |
| `PINECONE_API_KEY` | | | | | | X | | | | | | | |
| `PINECONE_HOST` | | | | | | X | | | | | | | |
| `PINECONE_URL` | | | | | | X | | | | | X | X | |
| `NEO4J_URL` | | | | | | X | | | | | | X | |
| `NEO4J_USER` | | | | | | X | | | | | | | |
| `NEO4J_PASSWORD` | | | | | | X | | | | | | | |
| `N8N_API_KEY` | | | | | | | | X | X | | | | |
| `N8N_BASE_URL` | | | | | | | | X | X | | | | X |
| `OTEL_COLLECTOR_URL` | | | X | | | | | | | | X | X | |
| `OTEL_EXPORTER_URL` | | | | | | X | X | X | X | | | | |
| `SENTRY_DSN` | | | | X | | | | | | | | | |
| `HF_TOKEN` | | | | | | X | | | | | | | |
| `SLACK_WEBHOOK_URL` | | | | | | | | | | | | | X |
| `SLACK_BENCHMARK_WEBHOOK` | | | | | | | X | | | | | | |

### Observations
- **standard.json** et **graph.json** : aucune `$env.` reference (credentials hard-codees dans les nodes ou via credential objects)
- **benchmark.json** et **benchmark-sql-executor.json** : aucune `$env.` reference
- **orchestrator** : le plus de vars LLM (5 modeles)
- **benchmark-dataset-ingestion** : le plus de vars (11) — pipeline d'ingestion complet

---

## Section 8 : Log de Modifications

| Date | Variable | Action | Raison |
|------|----------|--------|--------|
| 2026-02-12 | Toutes | Migration Cloud → Docker | Deplacement n8n self-hosted |
| 2026-02-15 | `USU8ngVzsUbED3mn` | Creee | Credential Supabase Postgres Pooler |
| 2026-02-15 | `CWih07lwPxfwFeY6` | Creee | Credential Redis Upstash |
| 2026-02-16 | `JINA_API_KEY` | Ajoutee | Migration Cohere → Jina primary |
| 2026-02-16 | `EMBEDDING_MODEL` | `embed-english-v3.0` → `jina-embeddings-v3` | Migration embeddings |
| 2026-02-16 | `EMBEDDING_API_URL` | Cohere → Jina | Migration embeddings |
| 2026-02-17 | `NEO4J_URL` (graph.json) | `bolt://localhost:7687` → `https://38c949a2...` | Fix FIX-07 bolt protocol |
| 2026-02-17 | Credential quant | `zEr7jPswZNv6lWKu` → `USU8ngVzsUbED3mn` | Fix FIX-11 credential manquante |
| 2026-02-18 | Ce fichier | Cree | Documentation exhaustive session 18 |
| 2026-02-18 | `.mcp.json` OPENROUTER_API_KEY | Aligne sur .env.local | Audit session 24 |
| 2026-02-18 | `.mcp.json` COHERE_API_KEY | Aligne sur .env.local | Audit session 24 |
| 2026-02-18 | 16 HF Space secrets | Crees | Deploiement HF Space nomos-rag-engine |
| 2026-02-23 | `HF_TOKEN_2` | Ajoutee | Secondary HF account support for redundant deployment |
| 2026-02-25 | `N8N_BLOCK_ENV_ACCESS_IN_NODE` | Ajoutee | Critical for n8n node expressions to access environment variables. Without this, $env.VAR_NAME expressions in SQL/Code nodes return undefined. Added to entrypoint.sh in session 62 |
| 2026-02-25 | `HF_SPACE_1_URL` through `HF_SPACE_10_URL` | Ajoutees | Multi-endpoint routing for 10 HF Spaces deployment, round-robin load balancing |
| 2026-02-25 | `N8N_ALL_HOSTS` | Ajoutee | Comma-separated list of all 10 HF Space URLs for round-robin load balancing |
| 2026-02-25 | `N8N_HOST_STANDARD`, `N8N_HOST_GRAPH`, `N8N_HOST_QUANTITATIVE`, `N8N_HOST_ORCHESTRATOR` | Ajoutees | Per-pipeline endpoints set to ${N8N_ALL_HOSTS} for round-robin routing |

---

## Variables manquantes (referencees mais non definies dans .env.local)

Ces variables sont referencees dans les workflows n8n mais n'ont **pas** de definition dans `.env.local` :

| Variable | Utilise dans | Impact si absent |
|----------|-------------|------------------|
| `OTEL_COLLECTOR_URL` | enrichment, ingestion, quantitative | Monitoring silencieusement ignore |
| `OTEL_EXPORTER_URL` | 5 workflows | Monitoring silencieusement ignore |
| `SENTRY_DSN` | orchestrator | Error tracking desactive |
| `SLACK_WEBHOOK_URL` | feedback | Notifications Slack desactivees |
| `SLACK_BENCHMARK_WEBHOOK` | benchmark-monitoring | Alertes benchmark desactivees |
| `N8N_BASE_URL` | 3 workflows | Appels internes n8n echouent si different de localhost |

**Action** : Ces variables sont optionnelles (monitoring/alerting). Les workflows fonctionnent sans.
A configurer quand monitoring sera active (Phase 3+).
