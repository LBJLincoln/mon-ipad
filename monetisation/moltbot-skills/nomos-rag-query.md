# Nomos RAG Query — Moltbot Skill

> Version: 1.0.0 | Author: Nomos AI | License: Commercial (free tier + paid)
> Schema: moltbot-skill/v1

---

## Metadata

```yaml
name: nomos-rag-query
version: 1.0.0
author: Nomos AI
category: knowledge-retrieval
tags: [rag, retrieval, vector-search, graph-rag, sql-rag, multi-pipeline]
pricing: free-tier-limited
purchase_url: https://buy.stripe.com/fZu4gs2ng1qX6rh0xL5J605
full_access_price: "$127"
full_access_product: "RAG Eval Framework - 61K-Question System"
description: >
  Query a production multi-pipeline RAG system with 3 specialized pipelines:
  Standard (vector search over 46K+ embeddings), Graph (entity traversal over
  79K+ Neo4j nodes), and Quantitative (SQL over 40 Supabase tables). Routes
  questions to the best pipeline automatically or lets you target a specific one.
capabilities:
  - semantic_search
  - entity_graph_traversal
  - sql_query_generation
  - multi_pipeline_routing
supported_domains:
  - finance
  - legal
  - construction_btp
  - manufacturing_industry
```

---

## What This Skill Does

You can query a production RAG (Retrieval-Augmented Generation) system that runs on n8n workflows hosted on Hugging Face Spaces. The system has three specialized pipelines:

| Pipeline | Best For | Database | Vectors/Nodes |
|----------|----------|----------|---------------|
| **Standard** | Factual questions, definitions, explanations | Pinecone (Jina embeddings, 1024-dim) | 46,263 vectors |
| **Graph** | Relationship questions, entity connections | Neo4j Aura (entities, paragraphs) | 79,451 nodes |
| **Quantitative** | Numerical questions, comparisons, rankings | Supabase (40 tables, SQL) | 15,263 rows |

---

## API Endpoints

### Base URL

```
https://lbjlincoln-nomos-rag-engine.hf.space
```

### Webhooks

| Pipeline | Method | URL |
|----------|--------|-----|
| Standard | POST | `https://lbjlincoln-nomos-rag-engine.hf.space/webhook/rag-multi-index-v3` |
| Graph | POST | `https://lbjlincoln-nomos-rag-engine.hf.space/webhook/ff622742-6d71-4e91-af71-b5c666088717` |
| Quantitative | POST | `https://lbjlincoln-nomos-rag-engine.hf.space/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9` |

### Health Check

```
GET https://lbjlincoln-nomos-rag-engine.hf.space/healthz
```

Returns `200 OK` when the n8n instance is running.

---

## Step-by-Step Instructions

### Step 1: Classify the Question

Before sending, determine which pipeline fits best:

- **Standard**: "What is X?", "Explain Y", "Define Z", factual retrieval
- **Graph**: "How is X related to Y?", "Who works with Z?", "What entities are connected to X?"
- **Quantitative**: "How much?", "What percentage?", "Compare revenue of X vs Y", any numbers/rankings

If unsure, use **Standard** as the default. It has the highest accuracy (87.5% on 10K questions).

### Step 2: Format the Request

All three pipelines accept the same JSON body:

```json
{
  "question": "Your question here",
  "tenant_id": "benchmark"
}
```

**Required fields**:
- `question` (string): The natural language question. Keep it under 500 characters.
- `tenant_id` (string): Use `"benchmark"` for the public evaluation dataset.

**Optional fields**:
- `session_id` (string): For conversation tracking. Default: auto-generated.
- `top_k` (integer): Number of results to retrieve. Default: 5. Max: 20.

### Step 3: Send the Request

```bash
curl -X POST \
  "https://lbjlincoln-nomos-rag-engine.hf.space/webhook/rag-multi-index-v3" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is retrieval-augmented generation?", "tenant_id": "benchmark"}'
```

### Step 4: Parse the Response

Successful response (HTTP 200):

```json
{
  "answer": "Retrieval-Augmented Generation (RAG) is a technique that combines...",
  "sources": [
    {
      "title": "RAG Survey 2024",
      "score": 0.89,
      "namespace": "default"
    }
  ],
  "pipeline": "standard",
  "latency_ms": 2340
}
```

### Step 5: Handle Errors

| HTTP Code | Meaning | Action |
|-----------|---------|--------|
| 200 | Success | Parse `answer` field |
| 404 | Webhook not registered | Pipeline may be inactive. Try another pipeline. |
| 429 | Rate limited | Wait 60 seconds, then retry. Free tier: 10 req/min. |
| 500 | Internal error | Retry once. If persistent, check `/healthz`. |
| 502/503 | HF Space sleeping | Wait 30s for cold start, then retry. |

---

## Example Queries and Expected Responses

### Example 1: Standard Pipeline — Factual Question

**Request**:
```json
{
  "question": "What are the main components of a RAG system?",
  "tenant_id": "benchmark"
}
```

**Expected response** (summarized):
```json
{
  "answer": "A RAG system consists of three main components: (1) a retriever that fetches relevant documents from a knowledge base using embeddings, (2) an augmenter that formats retrieved context into a prompt, and (3) a generator (LLM) that produces the final answer conditioned on the retrieved context.",
  "pipeline": "standard",
  "sources": [{"title": "RAG Architecture Overview", "score": 0.92}]
}
```

### Example 2: Graph Pipeline — Relationship Question

**Request**:
```json
{
  "question": "What entities are connected to machine learning in the knowledge graph?",
  "tenant_id": "benchmark"
}
```

**Expected response** (summarized):
```json
{
  "answer": "In the knowledge graph, machine learning is connected to: neural networks (IS_TYPE), deep learning (SUBCLASS_OF), natural language processing (APPLIED_IN), TensorFlow and PyTorch (IMPLEMENTED_BY)...",
  "pipeline": "graph",
  "sources": [{"type": "neo4j_traversal", "nodes_visited": 12}]
}
```

### Example 3: Quantitative Pipeline — Numerical Question

**Request**:
```json
{
  "question": "What is the total revenue for BTP sector companies in 2023?",
  "tenant_id": "benchmark"
}
```

**Expected response** (summarized):
```json
{
  "answer": "The total revenue for BTP sector companies in 2023 was EUR 4.2 billion across 1,844 documented companies in the database.",
  "pipeline": "quantitative",
  "sources": [{"type": "sql_query", "table": "sector_financial_tables"}]
}
```

---

## Rate Limits (Free Tier)

| Limit | Value |
|-------|-------|
| Requests per minute | 10 |
| Requests per day | 100 |
| Max question length | 500 chars |
| Max response time | 90 seconds |

---

## Full Access

The free tier provides basic query access. For full capabilities including:

- Unlimited queries (no rate limits)
- Access to all 61,661 evaluation questions across 18 SOTA benchmarks
- Custom pipeline routing logic
- Batch evaluation scripts
- Performance baselines for all pipelines
- n8n workflow source files for self-hosting

Purchase the **RAG Eval Framework** ($127):
https://buy.stripe.com/fZu4gs2ng1qX6rh0xL5J605

Or get everything with the **MEGA BUNDLE** ($497):
https://buy.stripe.com/6oU7sEaTM3z59Dtdkx5J60d

---

## Technical Specs

```yaml
embedding_model: jinaai/jina-embeddings-v3 (1024-dim, self-hosted)
llm_models:
  - meta-llama/llama-3.3-70b-instruct (SQL, Intent, Planning, QA)
  - google/gemma-3-27b-it (Fast, Lite tasks)
  - arcee-ai/trinity-large-preview (Extraction, Summaries)
vector_db: Pinecone (serverless, us-east-1)
graph_db: Neo4j Aura (free tier)
sql_db: Supabase (PostgreSQL 15)
orchestration: n8n (self-hosted on HF Spaces)
cost_per_query: $0.00 (free LLM tier via OpenRouter)
avg_latency: 2-8 seconds (Standard), 3-12 seconds (Graph), 4-15 seconds (Quantitative)
uptime: ~95% (HF Space may cold-start after inactivity)
```
