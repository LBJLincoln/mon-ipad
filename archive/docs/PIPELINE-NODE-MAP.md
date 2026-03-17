# Pipeline Commander Dashboard — Node-Level Map

> Every node, every auth, every endpoint, every database reference.
> Updated: 2026-03-11T19:15Z | Session S99

**Legend**: ACT=Active, DIS=Disabled | Red flags: LEAKED!, EXPIRED!, OLD!, NOT SET?

---

### Standard V3.9 (standard-rag-v3.9-multi-index.json) — 24 nodes
| St | Node | Type | Target | Auth | URL |
|----|------|------|--------|------|-----|
| ACT | HyDE Generator | httpRequest | LiteLLM S7 | LiteLLM OK | https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/ |
| ACT | HyDE Embedding | httpRequest | Embeddings | Bearer ...NA_API_KEY}} | https://api.jina.ai/v1/embeddings |
| ACT | HTTP Pinecone Query HyDE | httpRequest | Jina Pinecone ( | none | https://website-sectors-jina-1024-a4mkzmz.svc.aped |
| ACT | Original Embedding | httpRequest | Embeddings | Bearer ...NA_API_KEY}} | https://api.jina.ai/v1/embeddings |
| ACT | HTTP Pinecone Query Original | httpRequest | Jina Pinecone ( | none | https://website-sectors-jina-1024-a4mkzmz.svc.aped |
| ACT | BM25 Search Postgres | postgres | Supabase/PG | cred:Supabase Postgres (P |  |
| ACT | E5 Pinecone Search | httpRequest | E5 Pinecone | none | https://sectors-e5-multilingual-a4mkzmz.svc.aped-4 |
| ACT | Cohere Reranker | httpRequest | Reranker | Bearer ...RE_API_KEY}} | https://api.jina.ai/v1/rerank |
| ACT | LLM Generation | httpRequest | LiteLLM S7 | LiteLLM OK | https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/ |
| ACT | Query Decomposer (V.3.4) | httpRequest | LiteLLM S7 | LiteLLM OK | https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/ |

### Graph V3.6 (graph-rag-v3.6-fixed.json) — 25 nodes
| St | Node | Type | Target | Auth | URL |
|----|------|------|--------|------|-----|
| ACT | WF3: HyDE & Entity Extraction | httpRequest | LiteLLM S7 | LiteLLM OK | https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/ |
| ACT | Shield #4: Neo4j Guardian Trav | httpRequest | Neo4j | Basic auth | https://38c949a2.databases.neo4j.io/db/neo4j/query |
| ACT | WF3: Pinecone HyDE Search | httpRequest | Jina Pinecone ( | none | https://website-sectors-jina-1024-a4mkzmz.svc.aped |
| ACT | Community Summaries Fetch | postgres | Supabase/PG | cred:Supabase Postgres (P |  |
| ACT | WF3: Cohere Reranker | httpRequest | Reranker | none | https://lbjlincoln-nomos-reranker-api.hf.space/v1/ |
| DIS | Shield #9: Export Trace | httpRequest |  | none | https://disabled.otel.io/v1/traces |
| ACT | Generate HyDE Embedding | httpRequest | Embeddings | none | https://lbjlincoln-nomos-embeddings-api.hf.space/v |
| ACT | LLM Answer Synthesis | httpRequest | LiteLLM S7 | LiteLLM OK | https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/ |

### Quant V3.2 (quant-v3.2-litellm.json) — 20 nodes
| St | Node | Type | Target | Auth | URL |
|----|------|------|--------|------|-----|
| ACT | Schema Introspection | postgres | Supabase/PG | cred:Supabase Postgres (P |  |
| ACT | Text-to-SQL Generator (CoT Enh | httpRequest | LiteLLM S7 | LiteLLM OK | https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/ |
| ACT | SQL Executor (Postgres) | postgres | Supabase/PG | cred:Supabase Postgres (P |  |
| ACT | Interpretation Layer (LLM Anal | httpRequest | LiteLLM S7 | LiteLLM OK | https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/ |
| ACT | SQL Repair LLM | httpRequest | LiteLLM S7 | LiteLLM OK | https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/ |

### Orchestrator V13 (orchestrator-v14.1-harness.json) — 68 nodes
| St | Node | Type | Target | Auth | URL |
|----|------|------|--------|------|-----|
| DIS | Redis: Fetch Conversation | redis |  | cred:Redis |  |
| DIS | Postgres L2/L3 Memory | postgres | Supabase/PG | cred:Supabase Postgres (P |  |
| ACT | Invoke WF5: Standard | executeWorkflow |  |  |  |
| ACT | Invoke WF2: Graph | executeWorkflow |  |  |  |
| ACT | Invoke WF4: Quantitative | executeWorkflow |  |  |  |
| DIS | Store RLHF Data V8 | postgres | Supabase/PG | cred:Supabase Postgres (P |  |
| DIS | Redis: Store Conv V8 | redis |  | cred:Redis |  |
| DIS | Postgres: Update Context V8 | postgres | Supabase/PG | cred:Supabase Postgres (P |  |
| ACT | Export Error V8 | httpRequest |  |  | ={{ $env.SENTRY_DSN || 'https://sentry.io/api/inge |
| ACT | 🧠 LLM 1: Intent Analyzer | httpRequest | LiteLLM S7 | LiteLLM OK | https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/ |
| ACT | 🎯 LLM 2: Task Planner | httpRequest | LiteLLM S7 | LiteLLM OK | https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/ |
| ACT | Postgres: Init Tasks Table | postgres | Supabase/PG | cred:Supabase Postgres (P |  |
| ACT | Postgres: Insert Tasks | postgres | Supabase/PG | cred:Supabase Postgres (P |  |
| ACT | 🔀 Dynamic Switch V10 | switch |  |  |  |
| ACT | Postgres: Update Task | postgres | Supabase/PG | cred:Supabase Postgres (P |  |
| ACT | Postgres: Update Fallback | postgres | Supabase/PG | cred:Supabase Postgres (P |  |
| DIS | Redis: Set Cache | redis |  | cred:Redis |  |
| ACT | 🔀 Query Router | switch |  |  |  |
| DIS | Redis: Cache + Generator | redis |  | cred:Redis |  |
| ACT | 🎯 LLM 3: Agent Harness (Opus 4 | httpRequest | LiteLLM S7 | LiteLLM OK | https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/ |
| ACT | Postgres: Apply Skips | postgres | Supabase/PG | cred:Supabase Postgres (P |  |
| ACT | Postgres: Insert New Tasks | postgres | Supabase/PG | cred:Supabase Postgres (P |  |
| ACT | HTTP Request | httpRequest | LiteLLM S7 | LiteLLM OK | https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/ |
| ACT | Postgres : Get Current Tasks | postgres | Supabase/PG | cred:Supabase Postgres (P |  |

### Ingestion V4.0 (ingestion.json) — 30 nodes
| St | Node | Type | Target | Auth | URL |
|----|------|------|--------|------|-----|
| ACT | OCR Extraction | httpRequest | Doc Extract |  | https://api.unstructured.io/general/v0/general |
| ACT | Semantic Chunker V3.1 (Adaptiv | httpRequest | LiteLLM S7 | OpenRouter KEY (LEAKED\!) | https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/ |
| ACT | Version Manager | postgres | Supabase/PG | cred:Supabase Postgres (P |  |
| ACT | Q&A Generator | httpRequest | LiteLLM S7 | OpenRouter KEY (LEAKED\!) | https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/ |
| ACT | Generate Embeddings V4.0 (Late | httpRequest | Embeddings | Jina KEY (EXPIRED\!) | https://lbjlincoln-nomos-embeddings-api.hf.space/v |
| ACT | Pinecone Upsert | httpRequest | Pinecone ( — NO | cred:Pinecone API Key | ={{ $env.PINECONE_URL }}/vectors/upsert |
| ACT | Postgres Store | postgres | Supabase/PG | cred:Supabase Postgres (P |  |
| ACT | Export Trace OTEL | httpRequest |  |  | http://localhost:4318/export |
| ACT | Contextual LLM Call | httpRequest | LiteLLM S7 | OpenRouter KEY (LEAKED\!) | https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/ |

### Enrichment V4.0 (enrichment.json) — 32 nodes
| St | Node | Type | Target | Auth | URL |
|----|------|------|--------|------|-----|
| DIS | Fetch Internal Use Cases | httpRequest |  | cred:OpenRouter API (Main | https://internal-api.company.com/cas-usage |
| DIS | Fetch External Data Sources | httpRequest |  | cred:OpenRouter API (Main | https://external-data-provider.com/api/docs |
| ACT | AI Entity Enrichment V3.1 (Enh | httpRequest | LiteLLM S7 | cred:LiteLLM Proxy Key | https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/ |
| ACT | Upsert Vectors Pinecone | httpRequest | Jina Pinecone ( | cred:Pinecone API Key | https://website-sectors-jina-1024-a4mkzmz.svc.aped |
| ACT | Store Metadata Postgres | postgres | Supabase/PG | cred:Supabase Postgres (P |  |
| ACT | Update Graph Neo4j | httpRequest | Neo4j | cred:Neo4j Aura | https://2fc858f1.databases.neo4j.io/db/neo4j/tx/co |
| DIS | Community Detection Trigger (A | httpRequest | Neo4j | cred:Neo4j Aura | https://2fc858f1.databases.neo4j.io/community-dete |
| DIS | Export Trace to OpenTelemetry | httpRequest |  |  | https://localhost:4318/v1/traces |
| ACT | Extract Entities Per Chunk | httpRequest | LiteLLM S7 | cred:LiteLLM Proxy Key | https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/ |
| ACT | Fetch Community Assignments | httpRequest | Neo4j | cred:Neo4j Aura | https://2fc858f1.databases.neo4j.io/db/neo4j/tx/co |
| ACT | Generate Community Summaries | httpRequest | LiteLLM S7 | cred:LiteLLM Proxy Key | https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/ |
| ACT | Store Community Summaries Neo4 | httpRequest | Neo4j | cred:Neo4j Aura | https://2fc858f1.databases.neo4j.io/db/neo4j/tx/co |
| ACT | Store Community Summaries Post | postgres | Supabase/PG | cred:Supabase Postgres (P |  |
