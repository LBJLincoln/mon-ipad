# Hacker News — Show HN Post (Ready to Post)

> Generated: 2026-03-08
> Store: https://lbjlincoln.github.io/rag-dashboard/store.html

---

## Show HN: Multi-RAG Architecture — 4 pipelines, 61K questions, 95.2% accuracy, $0/month infra

**URL:** https://lbjlincoln.github.io/rag-dashboard/store.html

**Text (for the HN comment):**

Hi HN,

I've spent 86 engineering sessions (1,100+ commits) building a multi-pipeline RAG system that routes queries to 4 specialized architectures. The entire thing runs on free-tier infrastructure.

**Architecture:**

- Standard RAG (87.5% on 10K questions) — HyDE + original dual retrieval, RRF fusion, BM25 parallel, reranking
- Graph RAG (40.9% overall) — Neo4j with 79K nodes, 219K relationships
- Quantitative RAG (95.2%) — SQL generation against PostgreSQL with ILIKE fuzzy matching
- Orchestrator (on hold) — multi-hop decomposition, hit n8n architectural limits

**Stack (all free tier):**

- 9 n8n instances on HuggingFace Spaces
- Pinecone (77K vectors), Neo4j Aura (79K nodes), Supabase (40 tables)
- LiteLLM proxy with Llama 3.3 70B, Gemma 3 27B, Trinity (all free via OpenRouter/Groq)
- Self-hosted embeddings on HF Spaces (replaced Jina after exhausting 2 API keys)
- Evaluated against 18 SOTA benchmarks (SQuAD v2, MS MARCO, TriviaQA, HotpotQA, FinQA, etc.)

**What I learned:**

1. Single-pipeline RAG hits ~75% ceiling. Multi-pipeline routing is necessary for diverse query types.
2. Phase-gated evaluation (200→1K→10K→61K) catches bugs that small test sets miss.
3. n8n disabled nodes still fire HTTP requests — the most expensive production bug I encountered.
4. SQL-based RAG with ILIKE fuzzy matching outperforms vector search for quantitative queries.

I documented everything — architecture blueprints, n8n workflow JSONs (ready to import), debug playbook (79+ fixes), evaluation framework, Claude Code skills.

Packaged as digital products ($27-$497). The live dashboard shows real-time pipeline metrics.

Happy to answer technical questions about the architecture.

---

## Alternative Title Options (A/B test):

1. "Show HN: 4-pipeline RAG system — 95.2% accuracy on financial questions, $0/month infrastructure"
2. "Show HN: We evaluated 61K RAG questions across 18 SOTA benchmarks on free-tier infra"
3. "Show HN: Multi-RAG Architecture Blueprint — from 200 questions to 61K with phase-gated evaluation"

---

## Prepared Responses for Common HN Questions:

**Q: "Why not just use LangChain/LlamaIndex?"**

A: We started with those. They're great for prototypes. But in production, you need control over every node in the pipeline — which retrieval strategy, which reranking model, which embedding endpoint. n8n gives visual debugging at the node level + execution replay. When a query fails, I can see exactly which node produced wrong output. Try that in a LangChain chain.

**Q: "95.2% seems high. How do you measure it?"**

A: Exact match + semantic similarity against ground truth answers from SOTA benchmarks (FinQA, TAT-QA, etc.). The 95.2% is specifically for quantitative/financial questions where the answer is a number or short fact. Standard RAG (mixed query types) is 87.5%. We use phase-gated evaluation: pass at 200q doesn't mean pass at 10K.

**Q: "Why would I pay for this when I can build it myself?"**

A: You absolutely can. It took 86 sessions and 79+ bugs to figure out. The debug playbook alone will save you 40+ hours of "why is Supabase silently dropping inserts" and "why does Pinecone metadata fail silently above 40KB." It's $47.

**Q: "Free tier won't scale."**

A: Correct. This architecture is designed for benchmarking, prototyping, and small-scale production. If you need to serve 1000 req/s, you need paid infrastructure. But for teams evaluating RAG approaches, building PoCs, or running <100 req/day, free tier handles it. The architecture blueprints show exactly where the bottlenecks are and how to scale each component.

**Q: "What's the latency?"**

A: Standard RAG: 3-8 seconds (HF Spaces cold start + Groq inference + Pinecone lookup). Quantitative: 5-12 seconds (SQL generation adds a round trip). Not suitable for real-time chat without caching, but fine for batch evaluation and async queries.
