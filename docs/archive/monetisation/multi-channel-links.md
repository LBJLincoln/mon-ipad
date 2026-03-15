# Multi-Channel Payment Links

> Generated: 2026-03-08 15:03:46 UTC

All Nomos AI products across 3 payment platforms.

---

## 1. Stripe (Primary) -- 15 products LIVE

| # | Product | Price | Payment Link |
|---|---------|-------|--------------|
| 1 | MEGA BUNDLE - All 14 RAG Products | $497 | https://buy.stripe.com/6oU7sEaTM3z59Dtdkx5J60d |
| 2 | Architecture Blueprint - Multi-Pipeline RAG System | $197 | https://buy.stripe.com/aFa14g4vob1x3f5bcp5J602 |
| 3 | n8n Workflow Collection - Production RAG Workflows | $197 | https://buy.stripe.com/bJe00c9PI8Tp2b1a8l5J603 |
| 4 | Enterprise Site Template - Next.js 15 | $197 | https://buy.stripe.com/14A6oAaTM4D94j93JX5J604 |
| 5 | Agentic Commerce Playbook | $197 | https://buy.stripe.com/aFa3co9PI5Hd2b11BP5J607 |
| 6 | RAG Engineering Handbook | $147 | https://buy.stripe.com/eVq14g6Dwd9F6rh54h5J606 |
| 7 | RAG Eval Framework - 61K-Question System | $127 | https://buy.stripe.com/fZu4gs2ng1qX6rh0xL5J605 |
| 8 | Ingestion Toolkit - V4 Pipeline | $97 | https://buy.stripe.com/dRm7sEfa27PlcPFgwJ5J608 |
| 9 | Dashboard Template - Real-Time RAG Metrics | $97 | https://buy.stripe.com/14AcMYbXQ7PldTJ5S55J60a |
| 10 | RAG Cost Optimization Guide - $0/month Production RAG | $87 | _PENDING: Create in Stripe Dashboard_ |
| 11 | Benchmark Dataset Toolkit - 61K Questions | $67 | https://buy.stripe.com/cNi5kwaTMfhN5nd3JX5J60b |
| 12 | Embeddings Service - Self-Hosted Jina | $67 | https://buy.stripe.com/aFa00ce5Y0mT9Dtcgt5J60c |
| 13 | RAG Debug Playbook - 75+ Fixes | $47 | https://buy.stripe.com/00w7sEd1U2v14j92FT5J600 |
| 14 | Claude Code Skills Pack - 17 Commands | $47 | https://buy.stripe.com/7sY8wIge64D93f53JX5J609 |
| 15 | Agent Context Kit - CLAUDE.md Templates | $27 | https://buy.stripe.com/7sY9AMbXQ4D94j95S55J601 |

---

## 2. Gumroad

**Status**: No products yet. Create manually at https://gumroad.com/products/new

**API Note**: Gumroad has removed product creation from their API (POST /v2/products returns 404).
Products must be created through the web dashboard.

Store URL: https://nomos42.gumroad.com

### Gumroad Manual Creation Steps

1. Log in at https://gumroad.com/login
2. Go to https://gumroad.com/products/new
3. Create each product with these details:

**MEGA BUNDLE - All 13 RAG Products** ($497)
- Price: 49700 cents
- Slug: `mega-bundle`
- Description: Everything. One payment. Lifetime access.

Complete RAG engineering toolkit: Architecture Blueprint, n8n Workflows, Ente...

**Architecture Blueprint - Multi-Pipeline RAG System** ($197)
- Price: 19700 cents
- Slug: `architecture`
- Description: Complete architecture for a production multi-pipeline RAG system. Standard, Graph, and Quantitative pipelines. n8n orche...

**n8n Workflow Collection - Production RAG Workflows** ($197)
- Price: 19700 cents
- Slug: `n8n-workflows`
- Description: 7 production n8n workflow files covering Standard RAG, Graph RAG, Quantitative RAG, website pipelines, and the orchestra...

**Enterprise Site Template - Next.js 15** ($197)
- Price: 19700 cents
- Slug: `enterprise-site`
- Description: Full Next.js 15 website template with 4 sector verticals (Finance, Legal, Construction, Industry), embedded chatbots, re...

**Agentic Commerce Playbook** ($197)
- Price: 19700 cents
- Slug: `agentic-commerce`
- Description: The definitive guide to agentic commerce. How to make your products discoverable and purchasable by AI agents. ACP proto...

**RAG Engineering Handbook** ($147)
- Price: 14700 cents
- Slug: `rag-handbook`
- Description: Comprehensive handbook distilled from 80+ engineering sessions. Covers retrieval strategies, prompt engineering, embeddi...

**RAG Eval Framework - 61K-Question System** ($127)
- Price: 12700 cents
- Slug: `eval-framework`
- Description: Complete evaluation framework: 61,661 questions from 18 SOTA benchmarks. Parallel runner, golden evals, regression detec...

**Ingestion Toolkit - V4 Pipeline** ($97)
- Price: 9700 cents
- Slug: `ingestion-toolkit`
- Description: Data ingestion pipeline: 34,000+ records across 4 sectors. Docling integration, sector-aware chunking, multi-database up...

**Dashboard Template - Real-Time RAG Metrics** ($97)
- Price: 9700 cents
- Slug: `dashboard-template`
- Description: HTML/JS dashboard showing live pipeline metrics, accuracy trends, infrastructure status, and phase progress. Auto-genera...

**Benchmark Dataset Toolkit - 61K Questions** ($67)
- Price: 6700 cents
- Slug: `benchmark-dataset`
- Description: Curated dataset of 61,661 questions from 18 SOTA benchmarks. Pre-categorized by pipeline type (Standard, Graph, Quant)....

**Embeddings Service - Self-Hosted Jina** ($67)
- Price: 6700 cents
- Slug: `embeddings-service`
- Description: Self-hosted embedding service on HF Spaces. Jina v3 1024-dim, Gradio API, health monitoring. Drop-in Jina Cloud replacem...

**RAG Debug Playbook - 75+ Fixes** ($47)
- Price: 4700 cents
- Slug: `debug-playbook`
- Description: Library of 75+ real fixes. Diagnostic flowcharts, n8n gotchas, Pinecone/Neo4j/Supabase patterns, embedding pitfalls, LLM...

**Claude Code Skills Pack - 17 Commands** ($47)
- Price: 4700 cents
- Slug: `claude-skills`
- Description: 17 production slash commands for Claude Code: session-start, eval, sync-directives, self-heal, progress-10pct, regressio...

**Agent Context Kit - CLAUDE.md Templates** ($27)
- Price: 2700 cents
- Slug: `agent-context-kit`
- Description: Template system for AI agent context: CLAUDE.md, PROJECT-STATE.md, DEBUG-PLAYBOOK.md, INFRASTRUCTURE.md. The exact syste...

4. After creating all products, run:
   ```
   export $(grep -v '^#' .env.local | xargs)
   python3 monetisation/multi-channel-setup.py --fetch
   ```

---

## 3. Lemon Squeezy

**Status**: No products yet. Create at https://app.lemonsqueezy.com

**API Note**: Lemon Squeezy API does not support POST on /v1/products.
Products must be created through the dashboard.

Store: https://nomos42.lemonsqueezy.com

### Lemon Squeezy Manual Creation Steps

1. Log in at https://app.lemonsqueezy.com
2. Navigate to Products > New Product
3. Create each product with these details:

**MEGA BUNDLE - All 13 RAG Products** ($497)
- Price: $497
- Slug: `mega-bundle`
- Description: Everything. One payment. Lifetime access.

Complete RAG engineering toolkit: Architecture Blueprint, n8n Workflows, Ente...

**Architecture Blueprint - Multi-Pipeline RAG System** ($197)
- Price: $197
- Slug: `architecture`
- Description: Complete architecture for a production multi-pipeline RAG system. Standard, Graph, and Quantitative pipelines. n8n orche...

**n8n Workflow Collection - Production RAG Workflows** ($197)
- Price: $197
- Slug: `n8n-workflows`
- Description: 7 production n8n workflow files covering Standard RAG, Graph RAG, Quantitative RAG, website pipelines, and the orchestra...

**Enterprise Site Template - Next.js 15** ($197)
- Price: $197
- Slug: `enterprise-site`
- Description: Full Next.js 15 website template with 4 sector verticals (Finance, Legal, Construction, Industry), embedded chatbots, re...

**Agentic Commerce Playbook** ($197)
- Price: $197
- Slug: `agentic-commerce`
- Description: The definitive guide to agentic commerce. How to make your products discoverable and purchasable by AI agents. ACP proto...

**RAG Engineering Handbook** ($147)
- Price: $147
- Slug: `rag-handbook`
- Description: Comprehensive handbook distilled from 80+ engineering sessions. Covers retrieval strategies, prompt engineering, embeddi...

**RAG Eval Framework - 61K-Question System** ($127)
- Price: $127
- Slug: `eval-framework`
- Description: Complete evaluation framework: 61,661 questions from 18 SOTA benchmarks. Parallel runner, golden evals, regression detec...

**Ingestion Toolkit - V4 Pipeline** ($97)
- Price: $97
- Slug: `ingestion-toolkit`
- Description: Data ingestion pipeline: 34,000+ records across 4 sectors. Docling integration, sector-aware chunking, multi-database up...

**Dashboard Template - Real-Time RAG Metrics** ($97)
- Price: $97
- Slug: `dashboard-template`
- Description: HTML/JS dashboard showing live pipeline metrics, accuracy trends, infrastructure status, and phase progress. Auto-genera...

**Benchmark Dataset Toolkit - 61K Questions** ($67)
- Price: $67
- Slug: `benchmark-dataset`
- Description: Curated dataset of 61,661 questions from 18 SOTA benchmarks. Pre-categorized by pipeline type (Standard, Graph, Quant)....

**Embeddings Service - Self-Hosted Jina** ($67)
- Price: $67
- Slug: `embeddings-service`
- Description: Self-hosted embedding service on HF Spaces. Jina v3 1024-dim, Gradio API, health monitoring. Drop-in Jina Cloud replacem...

**RAG Debug Playbook - 75+ Fixes** ($47)
- Price: $47
- Slug: `debug-playbook`
- Description: Library of 75+ real fixes. Diagnostic flowcharts, n8n gotchas, Pinecone/Neo4j/Supabase patterns, embedding pitfalls, LLM...

**Claude Code Skills Pack - 17 Commands** ($47)
- Price: $47
- Slug: `claude-skills`
- Description: 17 production slash commands for Claude Code: session-start, eval, sync-directives, self-heal, progress-10pct, regressio...

**Agent Context Kit - CLAUDE.md Templates** ($27)
- Price: $27
- Slug: `agent-context-kit`
- Description: Template system for AI agent context: CLAUDE.md, PROJECT-STATE.md, DEBUG-PLAYBOOK.md, INFRASTRUCTURE.md. The exact syste...

4. After creating all products, run:
   ```
   export $(grep -v '^#' .env.local | xargs)
   python3 monetisation/multi-channel-setup.py --fetch
   ```

---

## Sales Pages & Bots

- **Main store**: https://lbjlincoln.github.io/rag-dashboard/store.html
- **Telegram bot**: @Nomos42Bot
- **Gumroad store**: https://nomos42.gumroad.com
- **Lemon Squeezy store**: https://nomos42.lemonsqueezy.com

---

## Summary

| Platform | Products | Status |
|----------|----------|--------|
| Stripe | 14 | LIVE |
| Gumroad | 0 | PENDING (manual creation needed) |
| Lemon Squeezy | 0 | PENDING (manual creation needed) |

## API Limitations Discovered

- **Gumroad**: POST /v2/products returns 404. Product creation API has been removed.
  Read endpoints (GET /v2/products, GET /v2/user) still work.
  Write endpoints for webhooks (PUT /v2/resource_subscriptions) still work.
- **Lemon Squeezy**: POST /v1/products returns 405 (Method Not Allowed).
  Only GET/HEAD supported. Products must be created via dashboard.
  POST /v1/checkouts IS supported (for creating checkout sessions from existing products).
