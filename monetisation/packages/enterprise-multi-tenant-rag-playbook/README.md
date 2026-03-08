# Enterprise Multi-Tenant RAG Playbook

## Production-Grade Multi-Tenancy for RAG Systems at Scale

**Price: $147** | **SKU: NOMOS-ENT-MT-001**
**Format: ZIP (Markdown + Python + Terraform/Pulumi + JSON configs + Test Suite)**
**Author: Alexis Moret** | Polytechnique + HEC Paris | 76+ production sessions

---

## Why This Playbook Exists

Every RAG tutorial assumes a single user, a single index, a single pipeline. The moment you need to serve **multiple tenants** — different clients, business units, or end-user organizations — everything breaks.

Suddenly you are dealing with data isolation, cross-tenant contamination in vector search, noisy neighbor problems in shared infrastructure, per-tenant SLAs, compliance boundaries, cost allocation, and migration nightmares. None of the open-source frameworks handle this out of the box.

We built a production multi-tenant RAG system from the ground up: **40 Supabase tables** with row-level security and `tenant_id` isolation, **53,000+ vectors** across Pinecone namespaces, **70,847 Neo4j nodes** with label-based tenant boundaries, and **4 specialized pipeline types** (Standard, Graph, Quantitative, Orchestrator). This playbook is the distilled engineering knowledge from that effort — 76+ sessions, 1,100+ commits, and 61,000+ evaluated queries.

If you are a platform engineer, SaaS CTO, or RAG architect tasked with making your RAG system serve multiple tenants without compromising accuracy, security, or performance, this is the guide you need.

---

## What's Included

| Component | Details |
|-----------|---------|
| **7 comprehensive chapters** | 300+ pages of architecture patterns, implementation guides, and production lessons |
| **15+ architecture diagrams** | Tenant isolation topologies, data flow maps, scaling decision trees, migration flowcharts |
| **10+ production code templates** | Python modules for tenant-aware RAG operations, middleware, routing |
| **Terraform/Pulumi IaC examples** | Infrastructure-as-code for multi-tenant Pinecone, Supabase, Neo4j deployments |
| **Tenant isolation test suite** | Automated tests to verify data boundaries, prevent cross-tenant leakage |
| **Cost allocation calculator** | Spreadsheet + Python tool for per-tenant chargeback modeling |
| **Migration runbook** | Step-by-step single-tenant to multi-tenant migration with rollback procedures |
| **SLA monitoring templates** | Grafana/Prometheus configs for per-tenant accuracy and latency tracking |

---

## Who This Is For

- **Platform engineers** building SaaS products with RAG capabilities who need tenant isolation without duplicating infrastructure
- **SaaS CTOs** evaluating multi-tenant architectures and needing a decision framework with real production data
- **RAG architects** scaling from a single-tenant proof-of-concept to a multi-tenant production system
- **DevOps/SRE teams** responsible for operating multi-tenant RAG infrastructure with per-tenant SLAs
- **Compliance engineers** who need to demonstrate data isolation for SOC2, GDPR, or HIPAA audits

**Prerequisites:** Familiarity with RAG fundamentals (retrieval, embedding, generation). Experience with at least one vector database. Basic understanding of multi-tenant SaaS patterns.

---

## Real System Metrics (From Our Production Deployment)

| Component | Metric | Detail |
|-----------|--------|--------|
| **Supabase** | 40 tables | Full RLS with `tenant_id` on every row |
| **Pinecone** | 53,000+ vectors | Namespace-per-tenant isolation across 2 indexes |
| **Neo4j Aura** | 70,847 nodes / 76,717 relationships | Label-based tenant boundaries |
| **Pipelines** | 4 types | Standard (87.5%), Graph, Quantitative (95.2%), Orchestrator |
| **Eval queries** | 61,000+ | Cross-tenant accuracy validation |
| **n8n instances** | 9 HF Spaces | Round-robin load balancing across tenants |
| **Sessions** | 76+ | Engineering iterations with incremental testing |
| **Commits** | 1,100+ | Production-hardened over months of development |

---

## Table of Contents

---

### Chapter 1: Multi-Tenant Architecture Patterns

The foundational chapter. Before writing a single line of code, you need to choose the right tenancy model. The wrong choice here will haunt you for years.

1. **Shared-Everything Architecture**
   - Single database, single index, single pipeline — tenants separated by metadata filters
   - When it works: low tenant count (<20), uniform workloads, cost-sensitive deployments
   - When it fails: compliance requirements, large tenants drowning small ones, accuracy drift
   - Implementation: `tenant_id` filter on every query, embedding metadata tags
   - Real example: Our early architecture used shared Pinecone indexes with metadata filtering — worked until tenant #12 introduced domain-specific jargon that polluted retrieval for all tenants

2. **Shared-Nothing Architecture**
   - Dedicated database, dedicated index, dedicated pipeline per tenant
   - When it works: enterprise clients with strict compliance, high-value tenants justifying cost
   - When it fails: 100+ tenants, cost pressure, operational overhead explosion
   - Implementation: Terraform modules for per-tenant infrastructure provisioning
   - Cost analysis: 3-10x more expensive than shared-everything, but zero contamination risk

3. **Hybrid Architecture (Recommended)**
   - Shared infrastructure with logical isolation — the production sweet spot
   - Pinecone namespace isolation: each tenant gets a dedicated namespace within shared indexes
   - Supabase RLS: row-level security policies enforcing `tenant_id` on every query
   - Neo4j label-based isolation: tenant-specific labels on all nodes and relationships
   - n8n pipeline routing: tenant-aware webhook dispatch to appropriate pipeline variant
   - Decision matrix: when to promote a tenant from shared to dedicated infrastructure
   ```
   Tenant Classification Matrix:
   ┌─────────────┬──────────────┬────────────────┬───────────────────┐
   │ Tier        │ Isolation    │ Infrastructure │ SLA               │
   ├─────────────┼──────────────┼────────────────┼───────────────────┤
   │ Free/Trial  │ Shared-all   │ Shared pool    │ Best-effort       │
   │ Professional│ Namespace    │ Shared + quota │ 99.5% / 500ms p95 │
   │ Enterprise  │ Dedicated    │ Isolated stack │ 99.9% / 200ms p95 │
   │ Regulated   │ Full isolate │ Own VPC/region │ 99.99% + audit    │
   └─────────────┴──────────────┴────────────────┴───────────────────┘
   ```

4. **Namespace Isolation in Vector Databases**
   - **Pinecone**: Native namespace support — zero-copy isolation within a single index
     - Our setup: `sota-rag-jina-1024` (21,073 vectors) + `website-sectors-jina-1024` (31,916 vectors)
     - Namespace naming conventions: `{tenant_id}_{data_type}_{version}`
     - Metadata schema per namespace vs global metadata schema
     - Query routing: ensuring tenant queries never cross namespace boundaries
   - **Weaviate**: Class-based multi-tenancy with native tenant isolation
     - Multi-tenancy toggle per class, automatic shard-per-tenant
     - Hot/cold tenant management for cost optimization
   - **Qdrant**: Collection-based isolation with payload filtering
     - When to use separate collections vs payload-based filtering
     - Performance implications of each approach at 100K+ vectors per tenant

5. **Row-Level Security in Relational Stores**
   - Supabase/PostgreSQL RLS implementation for RAG metadata
   ```sql
   -- Production RLS policy from our 40-table Supabase deployment
   CREATE POLICY tenant_isolation ON rag_chunks
     USING (tenant_id = current_setting('app.current_tenant')::uuid);

   CREATE POLICY tenant_isolation ON rag_evaluations
     USING (tenant_id = current_setting('app.current_tenant')::uuid);

   -- Applied across all 40 tables with consistent policy naming
   ```
   - Session-level tenant context: setting `app.current_tenant` on every connection
   - Performance impact of RLS: benchmark results from our 40-table schema
   - Common RLS pitfalls: joins that bypass policies, function security definer leaks
   - Testing RLS: automated verification that cross-tenant queries return zero rows

6. **Graph Database Tenant Isolation (Neo4j)**
   - Label-based isolation: `(:Tenant_ABC:Document)` vs `(:Document {tenant_id: 'abc'})`
   - Our approach: 70,847 nodes with label-based boundaries across tenant subgraphs
   - Cypher query patterns that enforce tenant boundaries
   - Graph traversal containment: preventing relationship walks from crossing tenant boundaries
   - Neo4j Aura limitations: 200K node / 400K relationship caps and tenant capacity planning

---

### Chapter 2: Data Isolation & Security

Multi-tenant RAG has unique security challenges that traditional multi-tenant SaaS does not face. Embeddings can leak information. Retrieved chunks can cross boundaries. LLM context windows can mix tenant data.

7. **Tenant Data Boundaries in Embeddings**
   - Why embedding spaces are dangerous for multi-tenancy: semantic similarity can surface cross-tenant content
   - Namespace-level isolation as the primary defense (not metadata filtering alone)
   - Embedding model considerations: shared models vs per-tenant fine-tuned models
   - Embedding cache isolation: preventing cache-based cross-tenant leakage
   - Jina embedding dimensions (1024) and namespace boundary enforcement in our system

8. **Cross-Tenant Contamination Prevention**
   - The 5 contamination vectors in multi-tenant RAG:
     1. Vector search returning chunks from wrong namespace (misconfigured filter)
     2. LLM context window containing mixed-tenant retrieved passages
     3. Cached responses served to wrong tenant
     4. Shared graph traversals crossing tenant subgraphs
     5. Batch processing pipelines mixing tenant data in memory
   - Defense-in-depth: isolation at every layer (network, database, application, LLM)
   - Automated contamination detection: canary documents per tenant
   - Incident response: what to do when contamination is detected
   ```python
   class TenantIsolationValidator:
       """Validates tenant isolation across all RAG layers."""

       def __init__(self, tenant_id: str):
           self.tenant_id = tenant_id
           self.violations = []

       def validate_pinecone_namespace(self, query_results: list) -> bool:
           """Verify all returned vectors belong to correct namespace."""
           for result in query_results:
               if result.namespace != f"tenant_{self.tenant_id}":
                   self.violations.append({
                       "layer": "vector_db",
                       "type": "namespace_leak",
                       "vector_id": result.id,
                       "expected_ns": f"tenant_{self.tenant_id}",
                       "actual_ns": result.namespace
                   })
           return len(self.violations) == 0

       def validate_supabase_rls(self, rows: list) -> bool:
           """Verify all returned rows have correct tenant_id."""
           for row in rows:
               if row.get("tenant_id") != self.tenant_id:
                   self.violations.append({
                       "layer": "relational_db",
                       "type": "rls_bypass",
                       "row_id": row.get("id"),
                       "expected_tenant": self.tenant_id,
                       "actual_tenant": row.get("tenant_id")
                   })
           return len(self.violations) == 0
   ```

9. **Encryption at Rest and in Transit Per Tenant**
   - Tenant-specific encryption keys (BYOK — Bring Your Own Key)
   - Key management architecture: AWS KMS / GCP KMS / HashiCorp Vault per tenant
   - Encrypting vectors at rest: performance trade-offs and implementation patterns
   - TLS configuration for per-tenant API endpoints
   - Field-level encryption for sensitive metadata in Supabase

10. **Compliance Patterns Per Tenant**
    - **SOC2**: Audit logging per tenant, access control evidence, data retention policies
    - **GDPR**: Right to erasure across vector stores + graph + relational (complete tenant data purge)
    - **HIPAA**: PHI isolation in RAG chunks, BAA requirements for vector database providers
    - Per-tenant compliance configuration: which regulations apply to which tenant
    - Audit trail implementation: every query, every retrieval, every generation logged per tenant
    - Data residency: geographic constraints on where tenant data can be stored and processed
    ```
    Compliance Matrix Per Tenant:
    ┌───────────┬────────┬────────┬────────┬───────────┬─────────────┐
    │ Tenant    │ SOC2   │ GDPR   │ HIPAA  │ Residency │ Retention   │
    ├───────────┼────────┼────────┼────────┼───────────┼─────────────┤
    │ Acme Corp │ Yes    │ Yes    │ No     │ EU-West   │ 7 years     │
    │ MedTech   │ Yes    │ Yes    │ Yes    │ US-East   │ 10 years    │
    │ FinServ   │ Yes    │ No     │ No     │ Any       │ 5 years     │
    │ GovCloud  │ Yes    │ Yes    │ No     │ US-Gov    │ 30 years    │
    └───────────┴────────┴────────┴────────┴───────────┴─────────────┘
    ```

---

### Chapter 3: Scaling Strategies

Multi-tenant RAG systems face unique scaling challenges. A single large tenant can consume all available resources. Vector search latency varies by namespace size. LLM API rate limits are shared across tenants.

11. **Per-Tenant Resource Allocation**
    - Compute budgets: LLM tokens per tenant per hour/day/month
    - Vector database quotas: max vectors per namespace, query rate limits
    - Storage allocation: Pinecone index capacity planning (our limit: 100K vectors per index)
    - Neo4j capacity: node/relationship budgets per tenant (our limit: 200K nodes / 400K relationships)
    - Queue depth limits: preventing one tenant from monopolizing the ingestion pipeline
    ```python
    # Production resource allocation config
    TENANT_RESOURCE_LIMITS = {
        "free": {
            "max_vectors": 1_000,
            "max_queries_per_hour": 100,
            "max_llm_tokens_per_day": 50_000,
            "max_ingestion_docs_per_day": 10,
            "pipeline_types": ["standard"],
            "batch_size": 5,
            "concurrency": 1,
        },
        "professional": {
            "max_vectors": 25_000,
            "max_queries_per_hour": 2_000,
            "max_llm_tokens_per_day": 500_000,
            "max_ingestion_docs_per_day": 500,
            "pipeline_types": ["standard", "graph"],
            "batch_size": 10,
            "concurrency": 5,
        },
        "enterprise": {
            "max_vectors": 250_000,
            "max_queries_per_hour": 50_000,
            "max_llm_tokens_per_day": 10_000_000,
            "max_ingestion_docs_per_day": 10_000,
            "pipeline_types": ["standard", "graph", "quantitative", "orchestrator"],
            "batch_size": 10,
            "concurrency": 5,
            "timeout": 90,
        },
    }
    ```

12. **Noisy Neighbor Mitigation**
    - Detection: identifying tenants consuming disproportionate resources
    - Throttling strategies: token bucket, sliding window, adaptive rate limiting
    - Priority queues: ensuring high-tier tenants are not impacted by burst traffic from lower tiers
    - Circuit breakers: isolating failing tenants from healthy ones
    - Our experience: how one tenant's 10K-document bulk ingestion impacted all other tenants' query latency
    - Solution: dedicated batch processing queues with tenant-aware scheduling
    ```
    Noisy Neighbor Detection Flow:
    ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
    │ Monitor      │────>│ Detect       │────>│ Throttle     │
    │ Per-tenant   │     │ Anomalies    │     │ Offending    │
    │ resource use │     │ (>2x median) │     │ tenant       │
    └──────────────┘     └──────────────┘     └──────┬───────┘
                                                      │
                                               ┌──────▼───────┐
                                               │ Notify       │
                                               │ tenant +     │
                                               │ suggest      │
                                               │ tier upgrade │
                                               └──────────────┘
    ```

13. **Horizontal vs Vertical Scaling Decision Matrix**
    - When to add more n8n instances vs scaling existing ones (our approach: 9 HF Spaces)
    - Pinecone pod scaling: replicas vs pods vs index splitting by tenant tier
    - Supabase connection pooling: per-tenant connection limits and PgBouncer configuration
    - Neo4j Aura scaling: when to split tenant subgraphs into separate databases
    - Decision matrix:
    ```
    ┌──────────────────┬────────────────────┬────────────────────┐
    │ Bottleneck       │ Scale Horizontal   │ Scale Vertical     │
    ├──────────────────┼────────────────────┼────────────────────┤
    │ Query throughput │ Add n8n instances   │ Upgrade LLM tier   │
    │ Vector search    │ Add Pinecone pods   │ Upgrade pod type   │
    │ Graph traversal  │ Split to databases  │ Upgrade Aura tier  │
    │ Ingestion rate   │ Add worker nodes    │ Increase batch sz  │
    │ LLM latency      │ Multi-provider LB   │ Use faster model   │
    │ Storage          │ Shard by tenant     │ Compress/prune     │
    └──────────────────┴────────────────────┴────────────────────┘
    ```

14. **Cost Allocation and Chargeback Models**
    - Per-tenant cost tracking: LLM tokens, vector operations, storage, compute
    - Chargeback formula: `tenant_cost = (llm_tokens * token_rate) + (vector_ops * op_rate) + (storage_gb * gb_rate)`
    - Margin analysis by tenant tier: identifying unprofitable tenants
    - Cost optimization levers: model selection per tenant tier (free models for low-tier)
    - Our model selection strategy:
      - Free tier: `meta-llama/llama-3.3-70b-instruct:free` (zero cost)
      - Professional: `google/gemma-3-27b-it:free` for fast queries, Llama 70B for complex
      - Enterprise: dedicated LLM endpoints with guaranteed throughput

---

### Chapter 4: Ingestion Pipeline Per Tenant

Ingestion is where multi-tenancy gets complicated. Each tenant may have different document types, different chunking requirements, different metadata schemas, and different update frequencies.

15. **Tenant-Aware Chunking and Embedding**
    - Per-tenant chunking strategies: legal documents (large chunks) vs technical docs (small chunks)
    - Embedding model selection per tenant: Jina (1024d) vs OpenAI (1536d) vs Cohere (1024d)
    - Our Jina embedding pipeline: 1024 dimensions, optimized for multi-lingual content
    - Chunk metadata schema with mandatory `tenant_id`:
    ```json
    {
      "chunk_id": "uuid-v4",
      "tenant_id": "tenant_abc",
      "document_id": "doc_123",
      "chunk_index": 5,
      "content": "...",
      "embedding": [0.023, -0.891, ...],
      "metadata": {
        "source_type": "pdf",
        "ingestion_date": "2026-03-08T10:00:00Z",
        "pipeline_type": "standard",
        "sector": "finance",
        "language": "en",
        "chunk_size": 512,
        "overlap": 50
      }
    }
    ```
    - Validation: rejecting chunks without `tenant_id` before they reach the vector store

16. **Metadata Tagging Strategies**
    - Global metadata vs tenant-specific metadata fields
    - Searchable metadata in Pinecone: which fields to index for filtered search
    - Neo4j property schema per tenant: flexible vs strict property validation
    - Supabase table design: shared tables with RLS vs per-tenant tables
    - Our 40-table Supabase schema: why we chose shared tables with RLS for all 40

17. **Incremental vs Full Re-Index Per Tenant**
    - Change detection: hash-based document deduplication per tenant
    - Incremental upsert: adding/updating only changed chunks
    - Full re-index triggers: embedding model change, chunking strategy change, schema migration
    - Tenant-specific re-index scheduling: off-peak hours for large tenants
    - Our experience: re-indexing 21,073 vectors in `sota-rag-jina-1024` — timing, cost, and impact
    ```python
    class TenantReindexManager:
        """Manages per-tenant reindexing operations."""

        def should_full_reindex(self, tenant_id: str) -> bool:
            """Determine if tenant needs full reindex."""
            tenant_config = self.get_tenant_config(tenant_id)
            return (
                tenant_config.embedding_model_changed
                or tenant_config.chunking_strategy_changed
                or tenant_config.schema_version != self.current_schema_version
                or tenant_config.vector_count_drift > 0.1  # >10% drift
            )

        def schedule_reindex(self, tenant_id: str, priority: str = "normal"):
            """Queue tenant reindex with priority."""
            job = {
                "tenant_id": tenant_id,
                "type": "full_reindex" if self.should_full_reindex(tenant_id) else "incremental",
                "priority": priority,
                "estimated_vectors": self.estimate_vector_count(tenant_id),
                "scheduled_at": self.get_next_off_peak_window(tenant_id),
            }
            self.job_queue.enqueue(job)
    ```

18. **Batch Processing with Tenant Prioritization**
    - Priority queue design: enterprise tenants processed before free tier
    - Batch size configuration per tenant tier (our config: 3-10 depending on pipeline type)
    - Concurrency limits: preventing one tenant's batch from starving others
    - Our production batch settings:
      - Standard pipeline: batch 10, concurrency 5, timeout 90s
      - Graph pipeline: batch 5, concurrency 3, timeout 90s
      - Quantitative pipeline: batch 3, concurrency 1, timeout 120s
      - Orchestrator pipeline: batch 2, concurrency 1, timeout 180s
    - Failure handling: tenant-specific retry policies and dead letter queues

---

### Chapter 5: Query Routing & Orchestration

In a multi-tenant system, every incoming query must be authenticated, routed to the correct tenant context, processed with the right pipeline, and returned within the tenant's SLA.

19. **Tenant-Aware Query Routing**
    - Authentication: extracting tenant context from JWT, API key, or session
    - Routing logic: mapping tenant to correct Pinecone namespace, Supabase RLS context, Neo4j subgraph
    - Pipeline selection: which of the 4 pipeline types to invoke per query
    - Our webhook routing: 4 webhook paths across 9 n8n instances with round-robin balancing
    ```python
    class TenantQueryRouter:
        """Routes queries to correct tenant context and pipeline."""

        PIPELINE_WEBHOOKS = {
            "standard": "/webhook/rag-multi-index-v3",
            "graph": "/webhook/ff622742-6d71-4e91-af71-b5c666088717",
            "quantitative": "/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
            "orchestrator": "/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0",
        }

        def route_query(self, query: str, tenant_id: str) -> dict:
            """Route query to appropriate tenant context and pipeline."""
            tenant_config = self.get_tenant_config(tenant_id)
            pipeline_type = self.classify_query(query, tenant_config)

            return {
                "query": query,
                "tenant_id": tenant_id,
                "namespace": f"tenant_{tenant_id}",
                "pipeline": pipeline_type,
                "webhook": self.PIPELINE_WEBHOOKS[pipeline_type],
                "n8n_instance": self.select_instance(tenant_config.tier),
                "model": tenant_config.llm_model,
                "max_tokens": tenant_config.max_response_tokens,
                "timeout": tenant_config.query_timeout,
            }
    ```

20. **Per-Tenant Model Selection**
    - Why different tenants need different LLM models
    - Model routing by query complexity and tenant tier
    - Our free-tier model strategy: Llama 3.3 70B (free) for SQL/intent/QA, Gemma 3 27B (free) for fast queries
    - Enterprise model routing: dedicated endpoints, guaranteed throughput, custom fine-tunes
    - A/B testing models per tenant: tracking accuracy by model by tenant
    - Fallback chains: primary model -> backup model -> degraded response

21. **Rate Limiting and Quota Management**
    - Token bucket implementation per tenant
    - Sliding window rate limiter for burst protection
    - Quota tracking in Supabase: real-time usage counters per tenant
    - Graceful degradation: serving cached/approximate results when quota is exhausted
    - Overage billing vs hard limits: configuration per tenant tier
    ```python
    class TenantRateLimiter:
        """Per-tenant rate limiting with sliding window."""

        def __init__(self, supabase_client):
            self.db = supabase_client

        async def check_rate_limit(self, tenant_id: str) -> dict:
            """Check if tenant is within rate limits."""
            usage = await self.db.rpc("get_tenant_usage", {
                "p_tenant_id": tenant_id,
                "p_window_minutes": 60
            }).execute()

            limits = await self.get_tenant_limits(tenant_id)

            return {
                "allowed": usage.data["query_count"] < limits["max_queries_per_hour"],
                "current_usage": usage.data["query_count"],
                "limit": limits["max_queries_per_hour"],
                "reset_at": usage.data["window_reset"],
                "tokens_used": usage.data["tokens_used"],
                "tokens_limit": limits["max_llm_tokens_per_day"],
            }
    ```

22. **Multi-Tenant Caching Strategies**
    - Tenant-scoped cache keys: `cache:{tenant_id}:{query_hash}`
    - Shared semantic cache: common questions across tenants (with isolation guarantees)
    - Cache invalidation per tenant: when tenant data changes, invalidate only that tenant's cache
    - Cache warming: pre-populating cache for high-priority tenants after deployments
    - Redis cluster configuration for multi-tenant caching with memory limits per tenant

---

### Chapter 6: Monitoring & SLAs

You cannot manage what you cannot measure. In a multi-tenant RAG system, you need visibility into every tenant's experience — independently.

23. **Per-Tenant Accuracy Tracking**
    - Golden evaluation sets per tenant: 50-200 curated question/answer pairs
    - Automated accuracy testing: scheduled eval runs per tenant
    - Our eval methodology: `quick-test.py --questions 5` per pipeline, `run-eval-parallel.py` for full suite
    - Accuracy baselines per tenant: Standard 87.5%, Quantitative 95.2% from our Phase 3 results
    - Regression detection: alerting when accuracy drops >2% for any tenant
    - A/B testing infrastructure: comparing pipeline versions per tenant

24. **SLA Management Across Tenants**
    - SLA tiers: best-effort (free), 99.5% (professional), 99.9% (enterprise), 99.99% (regulated)
    - Latency SLAs: p50/p95/p99 targets per tenant tier
    - Accuracy SLAs: minimum retrieval precision and answer quality guarantees
    - SLA reporting: automated weekly/monthly reports per tenant
    - SLA violation response: escalation procedures, credits, post-mortems
    ```
    SLA Dashboard Per Tenant:
    ┌─────────────┬──────────┬──────────┬──────────┬──────────┐
    │ Tenant      │ Uptime   │ p95 (ms) │ Accuracy │ Status   │
    ├─────────────┼──────────┼──────────┼──────────┼──────────┤
    │ Acme Corp   │ 99.97%   │ 340ms    │ 91.2%    │ OK       │
    │ MedTech     │ 99.92%   │ 520ms    │ 94.8%    │ OK       │
    │ FinServ     │ 99.45%   │ 890ms    │ 85.3%    │ WARNING  │
    │ GovCloud    │ 99.99%   │ 210ms    │ 96.1%    │ OK       │
    │ StartupX    │ 98.50%   │ 1200ms   │ 78.9%    │ DEGRADED │
    └─────────────┴──────────┴──────────┴──────────┴──────────┘
    ```

25. **Alerting and Escalation Per Tier**
    - Alert routing: PagerDuty for enterprise, Slack for professional, email for free
    - Escalation timelines: enterprise issues escalated in 15 min, professional in 1 hour
    - Tenant-specific runbooks: custom incident response procedures per tenant
    - Noise reduction: different alert thresholds per tier to prevent alert fatigue
    - Our alerting experience: how we reduced false positives from 40+/day to <5/day

26. **Usage Analytics and Billing Integration**
    - Metering: tracking every API call, LLM token, vector operation per tenant
    - Usage dashboards: self-service tenant portals with real-time consumption data
    - Billing integration: Stripe metered billing with per-tenant usage events
    - Revenue analytics: ARPU, churn prediction, upsell triggers based on usage patterns
    - Cost-to-serve per tenant: identifying tenants that cost more than they pay

---

### Chapter 7: Migration Guide

The hardest part of multi-tenancy is not building it from scratch — it is migrating an existing single-tenant system. This chapter provides a battle-tested migration path.

27. **Single-Tenant to Multi-Tenant Migration Path**
    - Assessment: cataloging all single-tenant assumptions in your current system
    - The 8-step migration sequence:
      1. Add `tenant_id` column to all database tables (backward-compatible)
      2. Backfill `tenant_id` for existing data (default tenant)
      3. Enable RLS policies (permissive first, then restrictive)
      4. Create Pinecone namespaces per tenant, migrate vectors
      5. Add tenant labels to Neo4j nodes, update Cypher queries
      6. Update API layer: extract tenant from auth, inject into all operations
      7. Deploy tenant-aware caching layer
      8. Enable per-tenant monitoring and alerting
    - Timeline: realistic estimates from our experience (4-8 weeks for a production system)
    - Risk assessment: what can go wrong at each step and how to detect it

28. **Zero-Downtime Tenant Onboarding**
    - Automated provisioning: Terraform/Pulumi modules for tenant infrastructure
    - Namespace creation: automated Pinecone namespace + initial vector seeding
    - RLS policy deployment: adding new tenant to existing policies without restart
    - Neo4j subgraph initialization: creating tenant node structure
    - Onboarding checklist: 15-point verification before tenant goes live
    ```python
    class TenantOnboarder:
        """Zero-downtime tenant provisioning."""

        async def onboard_tenant(self, tenant_config: dict) -> dict:
            """Provision all infrastructure for a new tenant."""
            tenant_id = tenant_config["tenant_id"]
            results = {}

            # 1. Supabase: Create tenant record + verify RLS
            results["supabase"] = await self.provision_supabase(tenant_id)

            # 2. Pinecone: Create namespace in appropriate index
            results["pinecone"] = await self.provision_pinecone_namespace(
                tenant_id,
                index="sota-rag-jina-1024",
                dimension=1024
            )

            # 3. Neo4j: Create tenant subgraph structure
            results["neo4j"] = await self.provision_neo4j_subgraph(tenant_id)

            # 4. n8n: Configure webhook routing for tenant
            results["n8n"] = await self.configure_webhook_routing(tenant_id)

            # 5. Monitoring: Set up per-tenant dashboards
            results["monitoring"] = await self.provision_monitoring(tenant_id)

            # 6. Validation: Run isolation tests
            results["validation"] = await self.run_isolation_tests(tenant_id)

            return results
    ```

29. **Data Migration Patterns**
    - Bulk vector migration: moving vectors between namespaces without re-embedding
    - Graph migration: exporting and importing Neo4j subgraphs per tenant
    - Relational data migration: tenant-aware pg_dump and restore
    - Validation: verifying data integrity post-migration with checksums
    - Our migration story: moving 53,000+ vectors and 70,847 nodes to tenant-aware architecture

30. **Rollback Strategies**
    - Per-step rollback procedures for each migration phase
    - Point-in-time recovery: database snapshots before each migration step
    - Vector store rollback: namespace deletion and re-creation from backup
    - Graph rollback: label removal and property cleanup in Neo4j
    - Feature flags: gradual rollout of multi-tenant code paths with instant rollback
    - Our rule: 3+ regressions during migration triggers automatic revert to previous state

---

## Appendices

### Appendix A: Terraform/Pulumi IaC Templates
- Pinecone index provisioning with namespace management
- Supabase project setup with RLS policies
- Neo4j Aura instance provisioning
- n8n HuggingFace Spaces deployment (9-instance setup)
- Monitoring stack (Prometheus + Grafana) per-tenant configuration

### Appendix B: Tenant Isolation Test Suite
- Cross-namespace query tests for Pinecone
- RLS bypass attempt tests for Supabase
- Graph traversal containment tests for Neo4j
- Cache isolation tests for Redis
- End-to-end tenant isolation smoke tests
- CI/CD integration: running isolation tests on every deployment

### Appendix C: Cost Calculator
- Python script: input tenant count, tier distribution, usage estimates
- Output: monthly infrastructure cost, per-tenant cost, margin analysis
- Scenario modeling: what happens when tenant #50 onboards, when enterprise tenant triples usage

### Appendix D: Compliance Checklist Templates
- SOC2 Type II evidence collection for multi-tenant RAG
- GDPR Data Processing Agreement template for RAG systems
- HIPAA BAA requirements checklist for vector database providers
- Audit log schema and retention policies

---

## Frequently Asked Questions

**Q: Can I use this with LangChain or LlamaIndex instead of n8n?**
A: Yes. The multi-tenant patterns are framework-agnostic. The code templates include both n8n webhook and Python SDK implementations. The architectural patterns apply regardless of orchestration framework.

**Q: What if I only use one vector database?**
A: The playbook covers Pinecone, Weaviate, and Qdrant in depth. Even if you only use one, the isolation patterns and migration strategies apply. The Pinecone sections are the most detailed since that is what we run in production.

**Q: Is this relevant for fewer than 10 tenants?**
A: Absolutely. Multi-tenant architecture is harder to retrofit than to build from the start. Even with 3-5 tenants, the isolation, monitoring, and cost allocation patterns will save you significant pain later.

**Q: Do I need all 4 pipeline types?**
A: No. Most multi-tenant RAG systems start with a single pipeline (Standard) and add specialized pipelines as tenant needs evolve. The playbook covers all 4 types (Standard, Graph, Quantitative, Orchestrator) but each chapter is independently useful.

**Q: What cloud providers does this cover?**
A: The infrastructure patterns are cloud-agnostic. The Terraform/Pulumi templates include AWS, GCP, and Azure variants. Our production system runs on GCP + HuggingFace Spaces, but the patterns translate directly.

---

## Pricing & License

| Option | Price | License |
|--------|-------|---------|
| **Individual** | $147 | Single user, personal/company use |
| **Team (up to 10)** | $447 | 10 seats, shared access |
| **Enterprise** | Contact us | Unlimited seats, priority support, custom workshops |

**30-day money-back guarantee.** If the playbook does not meaningfully improve your multi-tenant RAG architecture, get a full refund.

---

## About the Author

**Alexis Moret** — Polytechnique + HEC Paris. Built and operates a production multi-tenant RAG system across 76+ engineering sessions, 1,100+ commits, processing 61,000+ evaluated queries. The system spans 7 repositories, 9 n8n instances, 3 databases (Pinecone, Neo4j, Supabase), and 4 specialized pipeline types achieving up to 95.2% accuracy.

This is not theoretical. Every pattern, every code template, every architecture diagram in this playbook comes from building and operating a real system.

---

*Enterprise Multi-Tenant RAG Playbook v1.0 | SKU: NOMOS-ENT-MT-001 | (c) 2026 Alexis Moret*
