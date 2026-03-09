---
title: "79 Production RAG Fixes From 90+ Engineering Sessions — What Documentation Never Tells You"
published: false
description: "After building a multi-pipeline RAG system tested on 10K+ questions, I documented every production failure. Here are the patterns, anti-patterns, and fixes that only emerge at scale."
tags: rag, ai, machinelearning, tutorial
canonical_url: https://whop.com/nomosai
cover_image:
series: "Production RAG Engineering"
---

When I started building RAG systems, I followed the standard tutorial: embed documents, store vectors, retrieve top-k, generate an answer. It worked for 10 test questions.

Then production happened.

After 90+ engineering sessions, 1,100+ commits, and 79 documented production fixes, I built a multi-pipeline RAG system that routes queries to specialized pipelines and runs entirely on free-tier infrastructure. Here's what I learned — specifically the things that documentation never mentions.

## The Problem With Tutorial RAG

Every RAG tutorial follows the same pattern:

1. Chunk documents
2. Embed chunks
3. Store in a vector database
4. Retrieve top-k
5. Pass to an LLM
6. Get answer

This works at demo scale. At production scale — thousands of documents, 10K+ queries, real users — it breaks in ways nobody warns you about.

The core issue: **not all queries need the same retrieval strategy.**

- "What is the EBITDA margin for Company X in Q3 2025?" needs SQL against structured data, not vector search.
- "Who are the board members of Company Y?" needs graph traversal, not text retrieval.
- "Summarize the key risks in this 200-page report" needs multi-hop retrieval with synthesis.

One pipeline cannot optimally handle all three. You need specialization.

## The Multi-Pipeline Architecture

I built 4 specialized pipelines:

```
              +-------------------+
              |  Intent Classifier |
              |  (Llama 3.3 70B)  |
              +--------+----------+
                       |
        +--------------+--------------+
        |              |              |
  +-----v----+  +------v-----+  +----v-------+
  | Standard |  |   Graph    |  | Quantitative|
  |   RAG    |  |    RAG     |  |    RAG      |
  +-----+----+  +------+-----+  +----+-------+
        |              |              |
  +-----v----+  +------v-----+  +----v-------+
  | Pinecone |  |   Neo4j    |  |  Supabase  |
  | Vectors  |  |   Graph    |  | PostgreSQL |
  +----------+  +------------+  +------------+
```

### Pipeline 1: Standard RAG — 87.5% on 10K Questions

The key innovation: **dual retrieval with HyDE**.

Instead of embedding only the user's query, I also generate a hypothetical answer using the LLM, then embed both. The hypothetical answer is closer in embedding space to the actual document than the raw question.

```
Query ─────────────────┬───> Embed query ──> Pinecone search (top 20)
                       │
                       └───> LLM generates hypothetical answer
                             │
                             └──> Embed hypothetical ──> Pinecone search (top 20)
                                                              │
BM25 keyword search ──────────────────────────────────────────┤
                                                              │
                                                    Reciprocal Rank Fusion
                                                              │
                                                       Reranking (top 5)
                                                              │
                                                     LLM QA Synthesis
```

**Reciprocal Rank Fusion** merges results from different retrieval methods without normalizing scores: `score = 1/(k + rank)` where k=60.

This dual-retrieval + RRF + reranking approach consistently outperforms single-query retrieval by 10-15%.

### Pipeline 2: Graph RAG — Entity Relationships

Neo4j knowledge graph with ~87K nodes and ~77K relationships. Entity extraction from the query identifies people, companies, and concepts, then traverses the graph.

**Critical lesson:** Graph RAG accuracy is bounded by graph coverage. At 200 questions (Phase 1), it scored 78%. At 10K questions (Phase 3), it dropped to 40.9%. The pipeline didn't get worse — larger test sets exposed that many queries referenced entities outside the graph.

This is the honest number. Most people would report the 78% and move on.

### Pipeline 3: Quantitative RAG — 95.2% on Financial Queries

The hardest pipeline to build and the most rewarding.

The LLM generates SQL queries against a PostgreSQL database with 15K+ rows of structured financial data. Three things made this work:

1. **Schema injection**: The prompt includes table schemas AND sample rows. Without sample rows, the LLM doesn't know how data is formatted.

2. **Multi-strategy SQL extraction**: Different LLMs format SQL differently. Try JSON parse, regex for code blocks, raw SELECT detection. In that order.

3. **ILIKE fuzzy matching**: `WHERE company ILIKE '%total%'` instead of `WHERE company = 'TotalEnergies'`. Users never type entity names exactly as stored. This alone took accuracy from ~80% to 95.2%.

## The Free-Tier Stack

The entire system runs on free-tier infrastructure:

| Component | Service | Free Tier Limit |
|-----------|---------|----------------|
| LLMs | OpenRouter/Groq (Llama 70B, Gemma 27B, Trinity) | Rate-limited but unlimited |
| Vectors | Pinecone (77K vectors) | 100K vectors |
| Graph | Neo4j Aura (87K nodes) | 200K nodes |
| SQL | Supabase PostgreSQL (40 tables) | 500MB |
| Orchestration | 9 n8n instances on HF Spaces | Free tier |
| Embeddings | Self-hosted on HF Spaces | Free cpu-basic |
| LLM Proxy | LiteLLM on HF Spaces | Free tier |

**Monthly cost: $0.**

## 79 Production Fixes — The Patterns

After 90+ sessions, I categorized every failure. Here are the categories that accounted for 80% of issues:

### Category 1: Silent Failures (most dangerous)

These are bugs that produce no error but return wrong results:

**Pinecone metadata >40KB**: Upserts silently fail. No error. Vectors just don't appear. Had to add pre-flight size checks on every upsert.

**Supabase port confusion**: Port 5432 (session pooler) works with psycopg2. Port 6543 (transaction pooler) silently drops inserts. No error returned. Rows just don't appear. Lost 2 sessions to this.

**n8n disabled nodes still fire**: A disabled HTTP Request node still sends the request. Data flows through AND the HTTP call executes. The only safe "disable" is routing around the node with an IF.

### Category 2: LLM Format Variance

LLMs are not deterministic output formatters, even with explicit instructions:

**SQL wrapping**: Same model, same prompt, three different output formats across runs. Multi-strategy extraction is mandatory, not optional.

**JSON partial output**: Some models truncate JSON at the context window edge. Always validate JSON and have a fallback parser.

**Entity name normalization**: French names like "Societe Generale" vs "Societe Generale" (missing accent) vs "SocGen" (abbreviation). Fuzzy matching everywhere.

### Category 3: Infrastructure Ephemerality

Free-tier infrastructure is inherently unreliable:

**HF Spaces restart randomly**: Everything vanishes. Must version-control configs and build sync scripts.

**Free model availability fluctuates**: Models go offline during peak hours. LiteLLM fallback chains (Llama -> Gemma -> Trinity) keep the system running.

**Rate limits compound**: 10 concurrent requests at 10 questions per batch with 5 concurrent batches = 50 API calls in flight. Free tiers cap at 20-30 req/min. Add exponential backoff.

### Category 4: n8n-Specific Gotchas

**PATCH not PUT**: The n8n API returns 404 for PUT requests on workflow updates.

**PATCH doesn't persist on HF Spaces**: API returns 200 but changes evaporate on restart.

**`alwaysOutputData: true`**: If a node returns 0 rows, downstream nodes don't execute. Your webhook hangs forever.

**Cookie auth vs API key**: On HF Spaces, cookie auth via `/rest/login` is more reliable than API key authentication.

**`versionId` required for activation**: Since n8n 2.8+, `POST /workflows/{id}/activate` needs `{"versionId": "..."}`.

## The Evaluation Methodology

This is where most RAG projects fail — they test on 10 questions and call it production-ready.

**Phase-gated testing:**

| Phase | Questions | Purpose |
|-------|-----------|---------|
| Phase 1 | 200 | Baseline sanity — catches infrastructure failures |
| Phase 3 | 10,000 | Statistical significance — catches the 0.5% bugs |
| Phase 4 | 61,661 | SOTA benchmarks — tests generalization |

The 3-regression revert rule: if a fix introduces 3+ regressions on existing tests, revert immediately. This prevents the most common failure mode: fixing one thing while breaking three others.

## Results Summary

| Pipeline | Phase 1 (200q) | Phase 3 (10K) |
|----------|----------------|---------------|
| Standard | 85.5% | **87.5%** |
| Graph | 78.0% | 40.9% |
| Quantitative | 92.0% | **95.2%** |

## What I Packaged

I turned 90+ sessions of battle-tested knowledge into products:

**[RAG Debug Playbook](https://whop.com/debug-playbook)** ($47) — All 79+ fixes with root cause analysis, 3 diagnostic flowcharts, 12 anti-patterns. PDF + Markdown format. The .md version works as a context file for Claude Code, Copilot, or Cursor — drop it in your project and your AI assistant instantly knows every production fix.

**[Agent Context Kit](https://whop.com/agent-context-kit)** ($27) — Drop-in .md context files (CLAUDE.md, PROJECT-STATE.md, DEBUG-PLAYBOOK.md) that give your AI coding assistant structured project knowledge.

**[n8n Workflow Collection](https://whop.com/n8n-workflows)** ($197) — All 7 production workflow JSONs. Import into n8n, connect credentials, run.

**[RAG Architecture Blueprint](https://whop.com/architecture-blueprint)** ($197) — Complete multi-pipeline architecture docs, LiteLLM config, evaluation scripts, infrastructure setup.

**[61K Benchmark Dataset](https://whop.com/benchmark-dataset)** ($67) — 61,661 questions from 18 SOTA benchmarks (RAGBench, CRAG, SQuAD v2, MS MARCO, HotpotQA), pre-categorized by pipeline type.

**[MEGA BUNDLE](https://whop.com/rag-mega-bundle)** ($497) — All 14 products. One payment. Lifetime access.

**Full store: [whop.com/nomosai](https://whop.com/nomosai)**

---

*Background: I'm a Polytechnique + HEC (France) graduate. Founded an AI company serving top French construction firms. Built this system to handle financial, legal, and industrial document analysis at scale.*

---

What questions do you have? I'm happy to dive deeper into any of the pipeline designs, specific failure modes, or evaluation methodology.
