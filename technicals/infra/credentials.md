# Credentials & Cles API

> Last updated: 2026-03-03T18:15:00+00:00

> **Ce fichier DOIT etre mis a jour** apres chaque rotation de cle ou changement de service.

---

## n8n — HF Space #1

### Acces
- **Host** : `https://lbjlincoln-nomos-rag-engine.hf.space`
- **Auth** : Cookie-based login (NOT API key — JWT invalidates on HF rebuild)
- **Login** : `ci@nomos.ai` / `CI-Nomos-2026!` (field: `emailOrLdapLoginId`)
- **Helper** : `python3 scripts/n8n-api.py list|get|deploy|activate`
- **DB** : SQLite (ephemeral per space, for workflow storage only)

> **IMPORTANT**: VM n8n was removed Session 42. All n8n runs on HF Space #1.

### n8n Credentials (HF Space)
| Credential | Type | ID | Usage |
|------------|------|-----|-------|
| OpenRouter (Standard) | httpHeaderAuth | `VTFur78v4L4wWEk9` | Standard RAG pipeline |
| OpenRouter (Graph) | httpHeaderAuth | `8zKa8MqNEHsbVGKp` | Graph RAG pipeline |
| OpenRouter (Quantitative) | httpHeaderAuth | `lGI3u8XGRIwaFq1e` | Quantitative pipeline |
| OpenRouter (Orchestrator) | httpHeaderAuth | `S7i3kAtU5ZqIVCYS` | Orchestrator pipeline |
| LiteLLM Proxy Key | httpHeaderAuth | `mStiDbYim2aZ0cMq` | Ingestion + Enrichment (auto key rotation) |
| Jina API Key | httpHeaderAuth | `I68x3RvlHJZyQuR6` | Embeddings (key 2 — key 1 exhausted) |
| Supabase Postgres | postgres | `Vrvh0ukcROAk9dyX` | SQL queries |
| Pinecone API Key | httpHeaderAuth | `US6Cxlgs8LfyZWss` | Vector search |

---

## LiteLLM Proxy — HF Space #7

### Acces
- **Host** : `https://lbjlincoln-nomos-rag-engine-7.hf.space`
- **Master Key** : `sk-litellm-nomos-2026`
- **Persistence** : Supabase Postgres (DATABASE_URL env var)
- **Config** : `hf-space/litellm-proxy/litellm-config.yaml`

### Key Pool (10 keys, auto-rotation)
| Provider | Keys | Model Names |
|----------|------|-------------|
| OpenRouter (5 keys) | OPENROUTER_KEY_STANDARD, _GRAPH, _QUANTITATIVE, _ORCHESTRATOR, OPENROUTER_API_KEY | llama-70b, trinity, gemma-27b |
| Groq (5 keys) | GROQ_API_KEY through GROQ_API_KEY_5 | llama-70b-groq (also fallback for llama-70b) |
| Jina (2 keys) | JINA_API_KEY, JINA_API_KEY_2 | jina-embed, jina-rerank |

---

## Services configures

### Pinecone
- **Index principal** : `sota-rag-jina-1024` (Jina embeddings-v3, 1024-dim)
- **Index Phase 2 Graph** : `sota-rag-phase2-graph` (e5-large, 1024-dim)
- **Vectors** : ~19,000+ (default namespace: ~9,500+)
- **Plan** : Free (serverless, 100K max)

### Supabase
- **Project ref** : `ayqviqmxifzmhphiqfmj`
- **URL** : `https://ayqviqmxifzmhphiqfmj.supabase.co`
- **Pooler** : `aws-1-eu-west-1.pooler.supabase.com:6543`
- **Plan** : Free tier
- **Usage** : Quantitative data, LiteLLM persistence, financial tables

### Neo4j Aura
- **API** : `https://38c949a2.databases.neo4j.io/db/neo4j/query/v2`
- **Auth** : Basic auth (credentials in .env.local)
- **Stats** : 19,788 nodes / 76,717 relationships
- **Plan** : Free tier (200K nodes / 400K rels max)

### OpenRouter (6 keys across 3 accounts)
- Per-pipeline keys: `OPENROUTER_KEY_STANDARD`, `_GRAPH`, `_QUANTITATIVE`, `_ORCHESTRATOR`
- Generic: `OPENROUTER_API_KEY`
- Rate limit: 20 req/min per key
- Models: `meta-llama/llama-3.3-70b-instruct:free`, `arcee-ai/trinity-large-preview:free`, `google/gemma-3-27b-it:free`

### Groq (5 keys)
- Keys: `GROQ_API_KEY` through `GROQ_API_KEY_5`
- Rate limit: 30 req/min per key
- Model: `llama-3.3-70b-versatile`
- Used via: LiteLLM proxy (auto-rotation), OpenClaw gateway

### Jina AI
- **Embeddings** : `jina-embeddings-v3` (1024-dim)
- **Reranker** : `jina-reranker-v2-base-multilingual`
- **Keys** : 2 (key 1 EXHAUSTED — "Insufficient account balance", key 2 ACTIVE)
- **Limite** : 1M tokens/month, 100K tokens/min
- **Usage** : Pinecone ingestion, Standard pipeline embeddings, reranking

### Cohere (BACKUP — trial exhausted)
- Trial quasi-epuise (429 errors)
- Index backup conserve: `sota-rag-cohere-1024`

### Vercel
- **Token** : `vcp_6cSoud...` in .env.local (renewed Session 67)
- **Team** : `team_UNwVypB5JKvFoiY57skYS6ZA`
- **User** : `lbjlincoln`

### HuggingFace
- **Token** : In .env.local
- **Space #1** : `https://huggingface.co/spaces/LBJLincoln/nomos-rag-engine` (private, Docker, cpu-basic)
- **Space #7** : LiteLLM proxy

---

## Variables d'environnement

Les cles API sont configurees dans :
1. **HF Space env vars** : Source de verite pour n8n workflows (set via HF API)
2. **`.env.local`** : Pour les scripts Python locaux (gitignore)
3. **LiteLLM env vars** : Set via HF Space secrets API for Space #7

> **IMPORTANT** : Les cles API ne doivent PAS etre dans le repo GitHub.
> Pre-push check : `git diff --cached | grep -iE 'sk-or-|pcsk_|jV_zGdx|sbp_|hf_|jina_|ghp_'`
