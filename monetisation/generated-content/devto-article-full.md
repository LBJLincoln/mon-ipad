---
title: "How to Build a Multi-Pipeline RAG System on 100% Free Infrastructure"
published: true
description: "Architecture guide for a 4-pipeline RAG system handling 61K+ questions at 87-95% accuracy. Includes n8n workflows, LiteLLM proxy, self-hosted embeddings, and phase-gated evaluation."
tags: ai, rag, n8n, machinelearning
cover_image: ""
canonical_url: https://lbjlincoln.github.io/rag-dashboard/store.html
---

# How to Build a Multi-Pipeline RAG System on 100% Free Infrastructure

After 86 engineering sessions and 1,100+ commits, I've built a multi-pipeline RAG system that handles 61,661 benchmark questions at up to 95.2% accuracy.

Monthly cost: **$0**.

This isn't a tutorial — it's a war story. Here's what actually works (and what breaks) in production RAG.

## The Problem with Single-Pipeline RAG

Most RAG tutorials show you this:

```python
# The "hello world" of RAG
docs = vectorstore.similarity_search(query, k=5)
answer = llm.generate(context=docs, question=query)
```

This gets you to ~70-75% accuracy on mixed query types. Then you hit a wall.

**Why?** Because different questions need different retrieval strategies:

| Query Type | Best Strategy | Example |
|-----------|--------------|---------|
| Factual lookup | Vector similarity + BM25 | "What is the capital of France?" |
| Relationship | Graph traversal | "Who are the board members of Acme Corp?" |
| Quantitative | SQL generation | "What was Q3 revenue for company X?" |
| Multi-hop | Query decomposition | "Compare the revenue growth of A vs B over 3 years" |

One pipeline can't optimize for all of these.

## The Architecture: 4 Specialized Pipelines

### Pipeline 1: Standard RAG (87.5% on 10K questions)

```
Query → HyDE Generation → Dual Embedding (HyDE + Original)
     → Pinecone Search (both embeddings)
     → BM25 Keyword Search (parallel)
     → Reciprocal Rank Fusion (merge results)
     → Reranking (top candidates)
     → LLM Generation → Answer
```

**Key insight**: Dual retrieval with HyDE + original query, merged via RRF, outperforms single embedding by ~15%.

### Pipeline 2: Graph RAG (relationship queries)

```
Query → Entity Extraction (LLM)
     → Neo4j Graph Traversal
     → Relationship Context Assembly
     → LLM Generation → Answer
```

**Stats**: 79K nodes, 219K relationships. 40.9% overall but 90%+ on "who is connected to whom" queries. Overall accuracy is bounded by graph coverage.

### Pipeline 3: Quantitative RAG (95.2% on financial data)

```
Query → Intent Classification
     → SQL Generation (LLM)
     → Multi-Strategy SQL Extraction
     → PostgreSQL Execution
     → Result Formatting → Answer
```

**Game-changer**: `ILIKE` fuzzy matching instead of exact `WHERE` clauses. One change = +12% accuracy.

```sql
-- WRONG: Exact match fails on slight variations
WHERE company_name = 'Apple Inc.'

-- RIGHT: Fuzzy match handles variations
WHERE company_name ILIKE '%apple%'
```

### Pipeline 4: Orchestrator (on hold)

Multi-hop query decomposition. Hit n8n's `executeWorkflow` + `respondToWebhook` architectural conflict. Currently redesigning.

## The Free-Tier Stack

| Component | Service | Free Limit | Our Usage |
|-----------|---------|-----------|-----------|
| Orchestration | n8n on HF Spaces | 16GB RAM/instance | 9 instances |
| Vectors | Pinecone | 100K vectors | 77K vectors |
| Graph | Neo4j Aura | 200K nodes | 79K nodes |
| SQL | Supabase | 500MB | 40 tables |
| Embeddings | Self-hosted (HF) | Unlimited | ~6.3/min |
| LLMs | Groq + OpenRouter | Rate-limited | 3 models |
| Proxy | LiteLLM on HF | 16GB RAM | 9 models |

Total monthly cost: **$0**.

## The 10 Most Expensive Production Bugs

### 1. n8n disabled nodes still fire HTTP requests
Data passes through but HTTP Request nodes still execute. Silent corruption. **Fix**: Delete unused nodes, never just disable.

### 2. HuggingFace Spaces restart randomly
No persistent storage. **Fix**: External PostgreSQL via entrypoint.sh.

### 3. Pinecone metadata >40KB silently fails
Upserts don't error — data just disappears. **Fix**: Validate metadata size before upsert.

### 4. Supabase port 6543 silently drops inserts
Transaction pooler drops `psycopg2` inserts without error. **Fix**: Use port 5432 (session pooler).

### 5. LLMs format SQL output differently
Llama returns JSON. Gemma returns markdown code blocks. Trinity returns plain text. **Fix**: Multi-strategy extraction (try JSON → regex → raw detection).

### 6. Jina embeddings API keys exhaust silently
No warning, just empty responses. **Fix**: Self-hosted embeddings.

### 7. n8n PATCH doesn't persist on HF Spaces
API updates work but vanish on restart. **Fix**: Update workflow JSON files + sync script.

### 8. n8n activate requires versionId (2.8+)
POST to `/activate` needs `{"versionId": "..."}` in body. Undocumented breaking change.

### 9. HF Space proxy breaks curl authentication
HTTP/2 + custom routing. **Fix**: Use Python `urllib.request` + `MozillaCookieJar`.

### 10. Duplicate workflows shadow each other
Multiple workflows with same webhook path — n8n routes to the first one found. **Fix**: Check `workflowId` in execution data.

## Phase-Gated Evaluation

Don't trust accuracy on small test sets.

```
Phase 1: 200 questions → Smoke test (3 min)
Phase 2: 1,000 questions → Pattern validation (15 min)
Phase 3: 10,000 questions → Statistical significance (2 hrs)
Phase 4: 61,661 questions → Full SOTA benchmark (ongoing)
```

We went from "90% on 200 questions" to 87.5% on 10K. That 2.5% gap was hiding real bugs.

**Datasets used**: SQuAD v2, MS MARCO, TriviaQA, HotpotQA, FinQA, TAT-QA, NQ, and 12 more.

## What I'd Do Differently

1. **Start with evaluation infrastructure, not the pipeline.** You can't improve what you can't measure.
2. **Self-host embeddings from day 1.** API key exhaustion is inevitable at scale.
3. **Use PostgreSQL for structured data, not vector search.** SQL generation beats embedding similarity for quantitative queries.
4. **Phase-gate everything.** Don't run 10K questions until you pass 200.
5. **One fix per iteration.** Never change two things at once.

## Get the Tools

I packaged everything into reusable tools:

- **[MEGA BUNDLE — $497](https://buy.stripe.com/6oU7sEaTM3z59Dtdkx5J60d)**: Everything below + $1,400 value
- **[Architecture Blueprint — $197](https://buy.stripe.com/aFa14g4vob1x3f5bcp5J602)**: Complete 4-pipeline architecture
- **[n8n Workflows — $197](https://buy.stripe.com/bJe00c9PI8Tp2b1a8l5J603)**: 10 workflow JSONs, import and run
- **[Debug Playbook — $47](https://buy.stripe.com/00w7sEd1U2v14j92FT5J600)**: 79+ fixes with root cause analysis
- **[Eval Framework — $127](https://buy.stripe.com/fZu4gs2ng1qX6rh0xL5J605)**: 11 Python scripts for phase-gated testing
- **[Agent Context Kit — $27](https://buy.stripe.com/7sY9AMbXQ4D94j95S55J601)**: Claude Code / Copilot context files

**[Full product catalog →](https://lbjlincoln.github.io/rag-dashboard/store.html)**

---

*Built by an engineer from Polytechnique and HEC Paris. 86 sessions, 1,100+ commits, 61K questions evaluated.*
