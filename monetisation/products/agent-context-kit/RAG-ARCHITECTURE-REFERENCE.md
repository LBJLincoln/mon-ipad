# RAG Architecture Reference -- Multi-Pipeline Production System

> Drop this file into your CLAUDE.md, .cursorrules, or .github/copilot-instructions.md.
> Complete architectural reference for a production Multi-RAG system with 4 specialized pipelines.
> Built from 80+ sessions of iterative development, 1,100+ commits, tested on 61K+ questions.

---

## INSTRUCTIONS FOR AI AGENTS

Use this reference when:
- Designing a new RAG pipeline or extending an existing one
- Choosing between vector, graph, SQL, or orchestrated retrieval
- Setting up infrastructure (Pinecone, Neo4j, Supabase, n8n, LiteLLM)
- Debugging query routing or retrieval quality issues
- Optimizing embedding, reranking, or LLM generation steps

---

## 1. SYSTEM ARCHITECTURE

### 1.1 High-Level Overview

```
                    +------------------+
                    |   User Query     |
                    +--------+---------+
                             |
                    +--------v---------+
                    |   Orchestrator    |  <-- Intent classification + routing
                    |   (Meta-Router)   |
                    +--+-----+------+--+
                       |     |      |
            +----------+  +--+--+  +----------+
            |             |     |             |
   +--------v---+  +------v--+  +-------v------+
   |  Standard  |  |  Graph  |  | Quantitative |
   |  RAG       |  |  RAG    |  |  RAG (SQL)   |
   | (Vectors)  |  | (KG)    |  | (Tables)     |
   +-----+------+  +----+----+  +------+-------+
         |              |              |
   +-----v------+  +----v----+  +-----v--------+
   |  Pinecone  |  |  Neo4j  |  |  Supabase    |
   | (Vectors)  |  | (Graph) |  | (PostgreSQL) |
   +------------+  +---------+  +--------------+
```

### 1.2 Pipeline Specialization Matrix

| Pipeline | Data Type | Retrieval Method | Best For | Weakness |
|----------|-----------|-----------------|----------|----------|
| **Standard** | Unstructured text | Vector similarity + BM25 | Factual Q&A, definitions, explanations | Cannot do math or aggregation |
| **Graph** | Entity relationships | Graph traversal + community summaries | Multi-hop reasoning, entity relationships | Slow on simple lookups |
| **Quantitative** | Structured tables | SQL generation + execution | Numbers, comparisons, trends, aggregations | Requires clean schema + data |
| **Orchestrator** | Mixed | Routes to best pipeline | Complex queries spanning multiple types | Adds latency, routing errors possible |

### 1.3 Decision Matrix: When to Use Each Pipeline

```
Question Analysis:
    |
    +-- Asks for a specific number, metric, comparison, or trend?
    |       YES --> Quantitative (SQL)
    |
    +-- Asks about relationships between entities?
    |       YES --> Graph (Knowledge Graph)
    |
    +-- Asks for factual explanation, definition, or passage?
    |       YES --> Standard (Vector)
    |
    +-- Unclear or spans multiple types?
            --> Orchestrator (routes to best pipeline)
```

---

## 2. STANDARD RAG PIPELINE (Vector Retrieval)

### 2.1 Architecture

```
Query --> HyDE Generation --> Dual Embedding --> Vector Search --> Reranking --> LLM Generation --> Response
              |                    |                 |                |
              v                    v                 v                v
         LLM generates        Jina v3           Pinecone         Jina/Cohere
         hypothetical         1024-dim           top-K            reranker
         document             embeddings         retrieval
```

### 2.2 HyDE (Hypothetical Document Embedding)

**Purpose**: Generate a hypothetical answer to the query, embed BOTH the original query AND the hypothetical answer, then search with both embeddings. This bridges the vocabulary gap between questions and documents.

```
Query: "What is the capital of France?"

HyDE Output: "The capital of France is Paris. Paris is the largest city
in France and serves as the country's political, economic, and cultural
center. Located in northern France on the Seine River..."

Search vectors: [embed(original_query), embed(hyde_output)]
Results: merge and deduplicate
```

**Implementation notes**:
- Use a fast LLM (Llama 70B or Gemma 27B) for HyDE generation
- Keep HyDE output to 100-200 tokens (longer is not better)
- Merge original and HyDE results using RRF (see Section 2.4)
- HyDE adds 2-5 seconds latency; skip for simple keyword queries

### 2.3 Dual Embedding Strategy

```python
# Embed both original query and HyDE output
original_embedding = jina_embed(query)          # 1024-dim
hyde_embedding = jina_embed(hyde_document)       # 1024-dim

# Search Pinecone with both
results_original = pinecone.query(vector=original_embedding, top_k=10)
results_hyde = pinecone.query(vector=hyde_embedding, top_k=10)

# Merge using Reciprocal Rank Fusion
merged = reciprocal_rank_fusion([results_original, results_hyde], k=60)
```

### 2.4 Reciprocal Rank Fusion (RRF)

**Purpose**: Merge results from multiple retrieval strategies into a single ranked list. Better than simple interleaving because it accounts for rank positions.

```javascript
// RRF Algorithm
function reciprocalRankFusion(resultSets, k = 60) {
  const scores = {};

  for (const results of resultSets) {
    for (let rank = 0; rank < results.length; rank++) {
      const docId = results[rank].id;
      if (!scores[docId]) {
        scores[docId] = { score: 0, doc: results[rank] };
      }
      scores[docId].score += 1 / (k + rank + 1);
    }
  }

  return Object.values(scores)
    .sort((a, b) => b.score - a.score)
    .map(item => item.doc);
}
```

**Parameters**:
- `k = 60` is the standard constant (controls how much weight top positions get)
- Works with any number of result sets (2 for dual embedding, 3+ for multi-strategy)
- BM25 results can be added as a third input for hybrid search

### 2.5 Reranking

**Purpose**: Re-score the top-K retrieved documents using a cross-encoder model. More accurate than bi-encoder similarity but too slow for initial retrieval.

```python
# Reranking with Jina
reranked = jina_rerank(
    model="jina-reranker-v2-base-multilingual",
    query=original_query,
    documents=[doc.text for doc in merged_results[:20]],
    top_n=5
)
```

**Best practices**:
- Retrieve top-20, rerank to top-5 (good quality/latency tradeoff)
- Jina reranker is multilingual (handles French, English, mixed)
- Cohere reranker is an alternative but free tier exhausts quickly
- Reranking adds 200-500ms latency

### 2.6 Embedding Configuration

| Parameter | Value | Notes |
|-----------|-------|-------|
| Model | jina-embeddings-v3 | Multilingual, 1024 default dim |
| Dimensions | 1024 | Matches Pinecone index |
| Late chunking | Enabled | Better context preservation |
| Max input | 8,192 tokens | Per text segment |
| Batch size | Up to 2048 texts | API limit |

---

## 3. GRAPH RAG PIPELINE (Knowledge Graph)

### 3.1 Architecture

```
Query --> Entity Extraction --> Graph Traversal --> Community Detection --> Summary Generation --> Response
              |                      |                     |                      |
              v                      v                     v                      v
         LLM extracts           Neo4j Cypher          Leiden/Louvain         LLM summarizes
         entities from          queries for            algorithm on           community
         query                  neighbors              entity clusters        context
```

### 3.2 Entity Model

```
Nodes:
  - __Entity__     : Named entities (persons, orgs, places, concepts)
  - Document       : Source documents with metadata
  - Chunk          : Text segments from documents
  - __Community__  : Clusters of related entities

Relationships:
  - RELATED_TO     : Entity-to-entity (weighted, typed)
  - IN_COMMUNITY   : Entity membership in community
  - HAS_ENTITY     : Chunk/Document contains entity
  - PART_OF        : Chunk belongs to document
```

### 3.3 Graph Traversal Pattern

```cypher
// Step 1: Find matching entities
MATCH (e:__Entity__)
WHERE e.name CONTAINS $query_entity OR e.description CONTAINS $keyword
RETURN e LIMIT 10

// Step 2: Expand neighborhood (1-2 hops)
MATCH (e:__Entity__ {name: $entity_name})-[r:RELATED_TO*1..2]-(neighbor)
RETURN e, r, neighbor

// Step 3: Get community context
MATCH (e:__Entity__ {name: $entity_name})-[:IN_COMMUNITY]->(c:__Community__)
RETURN c.summary, c.title
```

### 3.4 Community Summaries

**Purpose**: Pre-computed summaries of entity clusters. When a query matches entities in a community, the community summary provides high-level context without traversing every individual relationship.

```python
# Community summary generation (offline, during ingestion)
for community in communities:
    entities = get_community_members(community)
    relationships = get_internal_relationships(community)

    prompt = f"""Summarize this group of related entities:
    Entities: {entities}
    Relationships: {relationships}
    Write a 2-3 sentence summary of what connects these entities."""

    summary = llm.generate(prompt)  # Use Trinity or similar
    store_community_summary(community.id, summary)
```

### 3.5 Neo4j Access Patterns

```
Protocol: HTTPS API only (bolt:// does NOT work through HTTP proxies or n8n)
Endpoint: https://{instance-id}.databases.neo4j.io/db/neo4j/query/v2
Auth: Basic (neo4j:password)
Bulk ops: UNWIND $rows for batch (100x faster than sequential)
```

**Common Cypher pitfalls**:
- 98% of relationships were generic `RELATED_TO` without types -- quality depends on entity extraction
- Free tier pauses after 3 days inactivity; send a keepalive query
- `tx/commit` endpoint returns 403 on Aura free tier; use Query API v2

---

## 4. QUANTITATIVE RAG PIPELINE (SQL Generation)

### 4.1 Architecture

```
Query --> Schema Introspection --> SQL Generation --> SQL Validation --> SQL Execution --> Result Interpretation --> Response
              |                        |                   |                 |                    |
              v                        v                   v                 v                    v
         Fetch table             LLM generates        Multi-strategy    Supabase            LLM converts
         schema from             SQL from query        extraction       PostgreSQL           raw SQL result
         Supabase                + schema              (JSON/md/raw)    via exec_sql         to natural
                                                                                             language
```

### 4.2 SQL Generation Prompt Strategy

```
You are a SQL expert. Generate a PostgreSQL query for this question.

SCHEMA:
{compact_static_schema}

SAMPLE DATA (first 3 rows):
{sample_rows}

RULES:
- Use ILIKE '%keyword%' for text matching (never exact =)
- Always include: WHERE tenant_id = 'benchmark'
- Available periods: 'FY', 'Q1', 'Q2', 'Q3', 'Q4'
- Fiscal years: 2020, 2021, 2022, 2023
- Output JSON only: {"sql": "SELECT ..."}

QUESTION: {user_question}
```

### 4.3 Multi-Strategy SQL Extraction

**Problem**: Free-tier LLMs return SQL in various formats (pure JSON, markdown code blocks, chain-of-thought with SQL buried inside).

```javascript
function extractSQL(llmResponse) {
  // Strategy 1: Direct JSON
  try { return JSON.parse(llmResponse).sql; } catch(e) {}

  // Strategy 2: ```sql code block
  const sqlBlock = llmResponse.match(/```sql\s*([\s\S]*?)```/);
  if (sqlBlock) return sqlBlock[1].trim();

  // Strategy 3: ```json code block
  const jsonBlock = llmResponse.match(/```json\s*([\s\S]*?)```/);
  if (jsonBlock) try { return JSON.parse(jsonBlock[1]).sql; } catch(e) {}

  // Strategy 4: Raw SELECT
  const rawSelect = llmResponse.match(/(SELECT[\s\S]*?;)/i);
  if (rawSelect) return rawSelect[1].trim();

  return null;
}
```

### 4.4 SQL Validation Pipeline

```
Generated SQL
    |
    +-- Starts with SELECT? (security check)
    |       NO --> REJECT (never execute non-SELECT)
    |
    +-- Contains tenant_id filter?
    |       NO --> ADD: AND tenant_id = 'benchmark'
    |
    +-- Contains DROP/DELETE/INSERT/UPDATE?
    |       YES --> REJECT (read-only enforcement)
    |
    +-- Valid PostgreSQL syntax? (pg_prepare test)
    |       NO --> Send back to LLM for repair (1 retry)
    |
    +-- PASS --> Execute on Supabase
```

### 4.5 Result Interpretation

```
SQL Result: [{"revenue": 6745000000}]

Prompt: "Convert this SQL result to a natural language answer.
Question: What was TechVision's revenue in 2023?
SQL Result: {sql_result}
Provide a clear, concise answer."

Response: "TechVision Inc's revenue in fiscal year 2023 was $6.745 billion."
```

### 4.6 Supabase Schema Design for RAG

```sql
-- Core financial table (quantitative pipeline)
CREATE TABLE financials (
    id SERIAL PRIMARY KEY,
    company_name TEXT NOT NULL,
    fiscal_year INTEGER NOT NULL,
    period TEXT NOT NULL,        -- 'FY', 'Q1', 'Q2', 'Q3', 'Q4'
    revenue NUMERIC,
    net_income NUMERIC,
    gross_profit NUMERIC,
    operating_income NUMERIC,
    research_development NUMERIC,
    diluted_eps NUMERIC,
    basic_eps NUMERIC,
    tenant_id TEXT DEFAULT 'benchmark'
);

-- Sector documents table (multi-sector RAG)
CREATE TABLE sector_documents (
    id SERIAL PRIMARY KEY,
    title TEXT,
    content TEXT,
    sector TEXT,              -- 'finance', 'juridique', 'btp', 'industrie'
    doc_type TEXT,            -- 'regulation', 'case_study', 'report', etc.
    metadata JSONB,
    tenant_id TEXT DEFAULT 'benchmark',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Always include tenant_id in WHERE clauses
-- Always use ILIKE for text matching
-- Port 5432 (session pooler) for psycopg2; port 6543 drops inserts silently
```

---

## 5. ORCHESTRATOR PIPELINE (Meta-Router)

### 5.1 Architecture

```
Query --> Intent Classification --> Pipeline Selection --> Delegation --> Response Aggregation --> Response
              |                         |                     |                   |
              v                         v                     v                   v
         LLM classifies           Decision matrix       HTTP POST to         Merge/select
         query type               picks pipeline(s)     pipeline webhook     best response
```

### 5.2 Intent Classification

```
Query types (detected by LLM):
  - FACTUAL      --> Standard pipeline
  - RELATIONAL   --> Graph pipeline
  - QUANTITATIVE --> Quantitative pipeline
  - MULTI_HOP    --> Graph pipeline (or orchestrate Standard + Graph)
  - COMPARATIVE  --> Quantitative pipeline
  - MIXED        --> Run 2+ pipelines, merge results

Classification prompt:
"Classify this question into one category:
- FACTUAL: asks for facts, definitions, explanations
- QUANTITATIVE: asks for numbers, metrics, trends, comparisons
- RELATIONAL: asks about connections between entities
- MIXED: spans multiple categories

Question: {query}
Output JSON: {\"type\": \"FACTUAL\"}"
```

### 5.3 Delegation Pattern

```javascript
// CRITICAL: Use httpRequest, NOT executeWorkflow
// executeWorkflow + respondToWebhook = empty response (see FIX-P11)

const delegation = {
  FACTUAL: {
    url: `${n8n_host}/webhook/rag-multi-index-v3`,
    timeout: 30000
  },
  RELATIONAL: {
    url: `${n8n_host}/webhook/{graph-uuid}`,
    timeout: 30000
  },
  QUANTITATIVE: {
    url: `${n8n_host}/webhook/{quant-uuid}`,
    timeout: 60000
  }
};

const result = await httpRequest({
  method: "POST",
  url: delegation[queryType].url,
  body: { query: originalQuery },
  timeout: delegation[queryType].timeout
});
```

### 5.4 Concurrency Constraints

| Configuration | Standard | Graph | Orchestrator | Total |
|--------------|----------|-------|--------------|-------|
| Safe | 5 concurrent | 3 concurrent | 1 concurrent | 9 |
| Moderate | 5 | 3 | 2 | 10 |
| Stress (not recommended) | 5 | 5 | 3 | 13 |

**Key constraint**: Orchestrator delegates to sub-pipelines. If sub-pipelines are already at capacity serving direct requests, orchestrator requests queue behind them. Keep orchestrator concurrency low.

---

## 6. EMBEDDING STRATEGIES

### 6.1 Model Comparison

| Model | Provider | Dimensions | Context | Multilingual | Cost |
|-------|----------|-----------|---------|--------------|------|
| jina-embeddings-v3 | Jina AI | 1024 (default) | 8,192 tokens | Yes | Free (1M tokens/month) |
| embed-english-v3.0 | Cohere | 1536 | 4,096 tokens | Limited | Trial (nearly exhausted) |
| text-embedding-3-small | OpenAI | 1536 | 8,191 tokens | Yes | $0.02/1M tokens |
| e5-large-v2 | HuggingFace | 1024 | 512 tokens | Limited | Free (self-hosted) |

### 6.2 Chunking Strategy

```python
# Recommended chunking parameters
chunk_size = 512       # tokens (sweet spot for retrieval precision)
chunk_overlap = 50     # tokens (prevents information loss at boundaries)
separator = "\n\n"     # paragraph-level splitting first

# For tables/structured data: keep entire table as one chunk
# For legal documents: split by article/section
# For financial reports: split by metric/period block
```

### 6.3 Late Chunking (Jina-specific)

**What**: Embed the full document first, then extract chunk embeddings from the full-document embedding. Each chunk retains context from the full document.

**Why**: Standard chunking loses context. A chunk saying "Their revenue increased by 15%" loses the referent of "Their" without the preceding context.

```python
# Late chunking with Jina
response = jina_embed(
    model="jina-embeddings-v3",
    input=[full_document_text],
    late_chunking=True,
    dimensions=1024
)
# Returns embeddings for each segment with full-document context
```

### 6.4 Namespace Strategy (Pinecone)

```
Index: sota-rag-jina-1024 (1024 dimensions)
  |
  +-- Namespace: squad        (SQuAD v2 dataset)
  +-- Namespace: hotpotqa     (HotPotQA dataset)
  +-- Namespace: musique      (MuSiQue dataset)
  +-- Namespace: nq           (Natural Questions)
  +-- Namespace: finqa        (Financial QA)
  +-- Namespace: cuad         (Contract Understanding)
  +-- Namespace: covidqa      (COVID-19 QA)
  +-- Namespace: pubmedqa     (PubMed QA)
  +-- Namespace: techqa       (Technical QA)
  +-- Namespace: tatqa        (Table-and-Text QA)
  +-- Namespace: emanual      (E-Manual)
  +-- Namespace: doqa         (Document QA)

Index: website-sectors-jina-1024 (1024 dimensions)
  |
  +-- Namespace: finance      (Financial documents)
  +-- Namespace: juridique    (Legal documents)
  +-- Namespace: btp          (Construction documents)
  +-- Namespace: industrie    (Manufacturing documents)
```

**Benefits of namespace isolation**:
- Query only relevant documents (faster, more precise)
- Independent ingestion/deletion per dataset
- Metadata filtering within namespace for finer control

---

## 7. RERANKING PATTERNS

### 7.1 When to Rerank

| Scenario | Rerank? | Why |
|----------|---------|-----|
| Simple factual query, top result is likely correct | No | Adds latency without benefit |
| Multi-hop query requiring context synthesis | Yes | Initial retrieval may miss relevant passages |
| Query with ambiguous keywords | Yes | Reranker understands semantic intent better |
| Top-K > 10 documents retrieved | Yes | Diminishing returns after rank 5 without reranking |
| Hybrid retrieval (vector + BM25) | Yes | Different retrieval methods need unified scoring |

### 7.2 Reranking Configuration

```python
# Jina Reranker (primary)
reranked = jina_rerank(
    model="jina-reranker-v2-base-multilingual",
    query=query,
    documents=retrieved_texts,  # Top 20 from retrieval
    top_n=5                     # Return top 5 after reranking
)

# Cohere Reranker (backup)
reranked = cohere_rerank(
    model="rerank-english-v3.0",
    query=query,
    documents=retrieved_texts,
    top_n=5
)
```

### 7.3 Two-Stage Retrieval Pattern

```
Stage 1: Broad retrieval (fast, high recall)
  - Pinecone vector search: top_k=20
  - Optional: BM25 keyword search: top_k=20
  - Merge with RRF if multiple sources

Stage 2: Precise reranking (slow, high precision)
  - Cross-encoder reranker on top 20
  - Select top 5 for LLM context window
  - Total latency: 500-800ms for both stages
```

---

## 8. QUERY ROUTING LOGIC

### 8.1 Classification Features

```python
# Feature extraction for query routing
features = {
    "has_number_question": bool(re.search(r'how much|how many|what.*(?:revenue|income|profit|cost|price)', query, re.I)),
    "has_comparison": bool(re.search(r'compare|difference|versus|vs|more than|less than', query, re.I)),
    "has_relationship": bool(re.search(r'related to|connected|between|who.*work|partner', query, re.I)),
    "has_temporal": bool(re.search(r'\d{4}|quarter|fiscal|annual|year|Q[1-4]', query, re.I)),
    "has_aggregation": bool(re.search(r'total|average|sum|count|trend|growth', query, re.I)),
    "word_count": len(query.split()),
    "has_context_block": len(query) > 500,  # Long queries with embedded context
}

# Routing decision
if features["has_context_block"]:
    route = "standard"  # Context-rich queries go to vector retrieval
elif features["has_number_question"] or features["has_aggregation"]:
    route = "quantitative"
elif features["has_relationship"]:
    route = "graph"
else:
    route = "standard"  # Default to vector retrieval
```

### 8.2 Context-Aware Routing

**Key insight**: Questions with embedded context (e.g., "Given this passage: [500 words]... What is X?") should NEVER go to the SQL pipeline. The SQL pipeline ignores provided context and queries the database instead.

```
Query length > 500 chars AND contains context block
    --> Route to Standard (vector) with context as additional retrieval input
    --> NEVER route to Quantitative (SQL)
```

---

## 9. LLM PROXY CONFIGURATION (LiteLLM)

### 9.1 Architecture

```
Pipeline --> LiteLLM Proxy --> Key Rotation --> Provider APIs
                |                                    |
                v                                    v
           Route by model alias              OpenRouter, Groq,
           + auto-retry on 429               Gemini, etc.
```

### 9.2 Model Aliases

```yaml
# litellm-config.yaml
model_list:
  - model_name: "default"
    litellm_params:
      model: "openrouter/meta-llama/llama-3.3-70b-instruct:free"
      api_key: "os.environ/OPENROUTER_API_KEY"

  - model_name: "fast"
    litellm_params:
      model: "openrouter/google/gemma-3-27b-it:free"
      api_key: "os.environ/OPENROUTER_API_KEY"

  - model_name: "smart"
    litellm_params:
      model: "openrouter/qwen/qwen3-235b-a22b:free"
      api_key: "os.environ/OPENROUTER_API_KEY"

  - model_name: "groq-llama"
    litellm_params:
      model: "groq/llama-3.3-70b-versatile"
      api_key: "os.environ/GROQ_API_KEY"
```

### 9.3 Key Rotation

```yaml
# Multiple keys for the same model = automatic rotation
  - model_name: "default"
    litellm_params:
      model: "openrouter/meta-llama/llama-3.3-70b-instruct:free"
      api_key: "os.environ/OPENROUTER_KEY_1"
  - model_name: "default"
    litellm_params:
      model: "openrouter/meta-llama/llama-3.3-70b-instruct:free"
      api_key: "os.environ/OPENROUTER_KEY_2"
  - model_name: "default"
    litellm_params:
      model: "openrouter/meta-llama/llama-3.3-70b-instruct:free"
      api_key: "os.environ/OPENROUTER_KEY_3"
# LiteLLM automatically rotates across all 3 keys
# Effective rate limit: 3 x 20 RPM = 60 RPM
```

### 9.4 Cost Optimization

| Strategy | Implementation | Monthly Savings |
|----------|---------------|-----------------|
| Free-tier models only | OpenRouter :free suffix, Groq free | $0 LLM cost |
| LiteLLM proxy pooling | 12+ keys across providers, auto-rotation | Eliminates 429 bottleneck |
| Model-task matching | Llama 70B for SQL, Gemma 27B for fast routing | Reduces latency 2x for simple tasks |
| Skip HyDE for simple queries | Keyword detection bypasses HyDE step | Saves 1 LLM call per simple query |
| Template SQL for known patterns | "Revenue of X in Y" bypasses LLM entirely | Saves 2-3 LLM calls per match |
| Static schema in prompts | Precomputed compact schema, no runtime fetch | Saves 1 DB call + reduces token count |

---

## 10. INFRASTRUCTURE SETUP

### 10.1 Complete Stack (All Free Tier)

| Component | Service | Tier | Cost | Role |
|-----------|---------|------|------|------|
| Workflow Engine | n8n on HF Spaces | cpu-basic (16GB) | $0 | Pipeline execution |
| Vector DB | Pinecone Serverless | Free (100K vectors) | $0 | Embedding storage + retrieval |
| Graph DB | Neo4j Aura | Free (200K nodes) | $0 | Knowledge graph |
| SQL DB | Supabase PostgreSQL | Free (500MB) | $0 | Structured data + financial tables |
| LLM Gateway | LiteLLM on HF Space | cpu-basic | $0 | Key rotation + model routing |
| LLMs | OpenRouter + Groq | Free tier | $0 | SQL gen, classification, synthesis |
| Embeddings | Jina AI | Free (1M tokens/mo) | $0 | Document + query embedding |
| Reranking | Jina AI | Free (included) | $0 | Cross-encoder reranking |
| Hosting | Vercel | Free (hobby) | $0 | Frontend + dashboard |
| Control Plane | GCP e2-micro VM | Free tier | $0 | Orchestration + eval scripts |
| **TOTAL** | | | **$0/month** | |

### 10.2 n8n on HF Spaces

```dockerfile
# Dockerfile for n8n on HF Spaces
FROM n8nio/n8n:2.8.3

USER root

# Install Python for helper scripts
RUN apk add --no-cache python3 py3-pip

# Set port for HF Spaces (MUST be 7860)
ENV N8N_PORT=7860
ENV N8N_PROTOCOL=https
ENV N8N_HOST=0.0.0.0

# CRITICAL: Enable $env access in all node types
ENV N8N_BLOCK_ENV_ACCESS_IN_NODE=false

# SQLite mode (no external DB needed)
ENV DB_TYPE=sqlite

# Disable telemetry
ENV N8N_DIAGNOSTICS_ENABLED=false

EXPOSE 7860

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
```

### 10.3 Pinecone Index Setup

```python
from pinecone import Pinecone, ServerlessSpec

pc = Pinecone(api_key="your-api-key")

# Create index for Jina embeddings
pc.create_index(
    name="rag-jina-1024",
    dimension=1024,
    metric="cosine",
    spec=ServerlessSpec(
        cloud="aws",
        region="us-east-1"
    )
)

# Upsert with namespace isolation
index = pc.Index("rag-jina-1024")
index.upsert(
    vectors=[
        {"id": "doc-001", "values": embedding, "metadata": {"source": "squad", "text": "..."}}
    ],
    namespace="squad"
)
```

### 10.4 Evaluation Methodology

```
Phase 1: Smoke Test (200 questions)
  - Purpose: Verify basic pipeline functionality
  - Targets: Standard >= 85%, Graph >= 70%, Quant >= 85%, Orch >= 70%
  - Duration: ~30 minutes

Phase 2: Stress Test (1,000 questions)
  - Purpose: Identify edge cases and rate limit behavior
  - Targets: Standard >= 80%, Graph >= 60%, Quant >= 70%
  - Duration: ~3 hours

Phase 3: Scale Test (10,000 questions)
  - Purpose: Validate at scale, measure throughput
  - Targets: Standard >= 85%, Quant >= 90%
  - Duration: ~24 hours

Phase 4: SOTA Benchmark (61,000+ questions)
  - Purpose: Compare against published benchmarks
  - Sources: RAGBench, CRAG, MultiHop-RAG, SQuAD v2, MS MARCO, TriviaQA
  - Duration: ~1 week
```

---

## 11. PERFORMANCE BENCHMARKS

### 11.1 Production Results

| Phase | Standard | Graph | Quantitative | Orchestrator |
|-------|----------|-------|-------------|-------------|
| Phase 1 (200q) | 85.5% | 78.0% | 92.0% | 80.0% |
| Phase 3 (10Kq) | 87.5% | 40.9% | 95.2% | ON HOLD |

### 11.2 Latency Profiles

| Pipeline | P50 | P90 | P99 | Bottleneck |
|----------|-----|-----|-----|------------|
| Standard | 9s | 23s | 29s | Embedding + reranking |
| Graph | 18s | 26s | 44s | Neo4j traversal + community synthesis |
| Quantitative | 15s | 30s | 45s | SQL generation (LLM) + execution |
| Orchestrator | 14s | 35s | 60s+ | Classification + sub-pipeline delegation |

### 11.3 Throughput Under Load

| Total Concurrent | Standard Success | Graph Success | Orch Success |
|-----------------|-----------------|---------------|--------------|
| 3 (baseline) | 100% | 100% | 100% |
| 9 (moderate) | 100% | 90% | 70% |
| 15 (stress) | 100% | 90% | 0% (auto-stop) |

**Key finding**: Standard pipeline is rock solid at any concurrency. Orchestrator degrades under load because it competes with sub-pipelines for resources.

---

## META

**Source**: 80+ development sessions on a production Multi-RAG orchestrator (2025-2026).
**Architecture**: 4 specialized pipelines, each optimized for a different data/query type.
**Infrastructure**: 100% free tier across 10+ services.
**Evaluation**: Tested on 61,000+ questions from 18 SOTA benchmarks.
**Price**: $27 -- AI Agent Context Kit.
