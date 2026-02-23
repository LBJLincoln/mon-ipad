# Nomos AI — What Is This Project? (2-3 min read)

> Last updated: 2026-02-24T01:00:00+01:00

---

## The One-Liner

Nomos AI is an **AI-powered question-answering system** that searches multiple databases simultaneously to give accurate, sourced answers for businesses.

## How It Works

A user asks a question. The system picks the best search method from 4 options:

| Pipeline | What It Does | Best For |
|----------|-------------|----------|
| **Standard** | Searches document vectors (Pinecone) | General knowledge questions |
| **Graph** | Traverses knowledge graph (Neo4j) | Relationship-based questions |
| **Quantitative** | Queries structured data (Supabase SQL) | Numbers, dates, financial data |
| **Orchestrator** | Routes to the best pipeline above | Any question (auto-selects) |

Each pipeline uses **free AI models** (Llama 70B, Gemma 27B, Trinity) via OpenRouter to generate answers.

## Current State (Feb 2026)

- **Phase 1 (200 questions): PASSED** at 83.9% accuracy
- **Phase 2 (1,000 questions/pipeline): IN PROGRESS** — Graph 78%, Quantitative 92% done
- **Standard & Orchestrator**: Being debugged (env var fix applied, testing v5.5)
- **1,520+ questions tested** across 51 working sessions

## Architecture (Simple View)

```
User Question
     |
 [n8n on HuggingFace Space]  <-- Runs the workflow engine (free, 16GB RAM)
     |
 [4 Pipelines]
     |
 [3 Databases]
   - Pinecone (22K vectors for semantic search)
   - Neo4j (19K entities in knowledge graph)
   - Supabase (17K rows of structured data)
     |
 [Free LLMs via OpenRouter]
     |
 Answer + Sources
```

## The 8 GitHub Repos

| Repo | Purpose |
|------|---------|
| **mon-ipad** | Control tower — directives, scripts, configs |
| **rag-tests** | Eval scripts, test datasets, accuracy results |
| **rag-website** | Business website (4 sectors: BTP, Industry, Finance, Legal) |
| **rag-dashboard** | Live metrics dashboard |
| **rag-data-ingestion** | Document processing + database loading |
| **rag-pme-connectors** | SMB integrations (15 apps: WhatsApp, Slack, Gmail...) |
| **rag-pme-usecases** | 200 business use cases catalog |
| **rag-storage** | Archive/storage for large files |

## What Runs Where

| Machine | Role | Always On? |
|---------|------|-----------|
| **Google Cloud VM** | Control tower (Claude Code pilot) | Yes |
| **HuggingFace Space** | n8n workflow engine (16GB) | Yes |
| **GitHub Codespaces** | Heavy testing (500+ questions) | On demand (60h/month) |
| **Vercel** | 4 websites (auto-deploy from GitHub) | Yes |

## Key Numbers

| Metric | Value |
|--------|-------|
| Total cost | **$0** (all free tiers) |
| AI models | 3 free models via OpenRouter |
| API keys | 7 OpenRouter keys across 3 accounts |
| Target accuracy | 85%+ overall |
| Target latency | < 2.5 seconds |
| Questions tested | 1,520+ |
| Working sessions | 51 |
| Documented fixes | 57 |

## What's Next

1. Fix remaining pipeline errors (Standard, Orchestrator)
2. Complete Phase 2 testing (1,000 questions per pipeline)
3. Ingest sector-specific documents (BTP, Industry, Finance, Legal)
4. Deploy chatbot to websites (replace broken endpoints)
5. Scale to Phase 3 (10,000+ questions)
