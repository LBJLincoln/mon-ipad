#!/usr/bin/env python3
"""Create ALL Stripe products for maximum revenue in 24h."""
import os, stripe
stripe.api_key = os.environ["STRIPE_SECRET_KEY"]

# First list existing products to avoid duplicates
existing = {p.name: p for p in stripe.Product.list(limit=100).data}
print(f"Existing products: {list(existing.keys())}")

PRODUCTS = [
    # TIER 1 - High value bundles
    {
        "name": "Multi-RAG Architecture Blueprint",
        "description": "Complete architecture for a 4-pipeline RAG system handling 61K+ questions at 87-95% accuracy. Includes infrastructure setup (100% free tier), n8n workflow configs, LiteLLM proxy setup, evaluation methodology, and phase-based scaling strategy. Built from 80+ production sessions.",
        "price_cents": 19700,
        "currency": "usd",
    },
    {
        "name": "n8n RAG Workflow Collection — 10 Production Workflows",
        "description": "10 battle-tested n8n workflow JSON files: Standard RAG, Graph RAG, Quantitative RAG, Orchestrator, Enrichment Pipeline, Ingestion Pipeline, PME Gateway, Project Chatbot, and more. Import directly into n8n — zero setup. Groq/OpenRouter/LiteLLM compatible.",
        "price_cents": 19700,
        "currency": "usd",
    },
    {
        "name": "Enterprise RAG Website Template — Next.js 14",
        "description": "Production Next.js 14 + Tailwind + shadcn/ui website with 4 sector-specific AI chatbots (Finance, Legal, Construction, Manufacturing). MacBook frame animations, live dashboard with SSE streaming, SEO pre-configured. Deploy to Vercel in 5 minutes.",
        "price_cents": 19700,
        "currency": "usd",
    },
    # TIER 2 - Mid value
    {
        "name": "RAG Evaluation Framework — Phase-Gated Testing",
        "description": "Complete Python evaluation suite: smoke tests, parallel batch evaluation, phase gates (200→1K→10K→61K questions), regression detection, live metrics dashboard. 11 production scripts battle-tested across 80+ sessions.",
        "price_cents": 12700,
        "currency": "usd",
    },
    {
        "name": "RAG Engineering Handbook — 2,500+ Lines",
        "description": "Complete technical documentation: 79+ production fixes with root cause analysis, infrastructure reference (Pinecone, Neo4j, Supabase, n8n), project roadmap with SOTA research review, 1000+ document types by sector. The encyclopedia of RAG engineering.",
        "price_cents": 14700,
        "currency": "usd",
    },
    {
        "name": "Agentic Commerce Playbook",
        "description": "How to sell AI products TO AI agents. ACP protocol implementation, 10-platform distribution strategy, MCP server integration, revenue automation. Based on McKinsey's $1T agentic commerce prediction by 2030. First-mover advantage guide.",
        "price_cents": 19700,
        "currency": "usd",
    },
    # TIER 3 - Accessible
    {
        "name": "RAG Ingestion Toolkit — Scripts & Services",
        "description": "20+ production scripts for document ingestion: multi-format parsing (PDF, DOCX, JSONL), Pinecone/Neo4j/Supabase loaders, BM25 service, reranker service, quality validation, contextual enrichment. Process 34K+ documents reliably.",
        "price_cents": 9700,
        "currency": "usd",
    },
    {
        "name": "Claude Code Skill Pack — 17 Custom Commands",
        "description": "17 production-ready Claude Code skills: session management, evaluation, monitoring, self-healing, cross-repo sync, regression detection, metrics aggregation, website audit, and more. Drop into .claude/commands/ and supercharge your AI coding workflow.",
        "price_cents": 4700,
        "currency": "usd",
    },
    {
        "name": "RAG Pipeline Dashboard Template",
        "description": "Real-time HTML/JS dashboard for RAG pipeline monitoring. Chart.js visualizations, trading board (BEST/WORST/MIDDLE), auto-refresh, Vercel serverless API, fallback mode. Deploy in 2 minutes on GitHub Pages or Vercel.",
        "price_cents": 9700,
        "currency": "usd",
    },
    {
        "name": "SOTA Benchmark Dataset Toolkit",
        "description": "18 curated SOTA benchmark datasets (61,661 questions) with download scripts, phase generators, and evaluation harness. SQuAD v2, MS MARCO, TriviaQA, HotpotQA, FinQA, and more. Ready for RAG evaluation.",
        "price_cents": 6700,
        "currency": "usd",
    },
    {
        "name": "Self-Hosted Embeddings Service",
        "description": "Deploy your own Jina-compatible embeddings API on HuggingFace Spaces (free tier). Lazy model loading, health monitoring, TEI-compatible endpoints. Stop paying per-token for embeddings. Includes deployment guide.",
        "price_cents": 6700,
        "currency": "usd",
    },
    # MEGA BUNDLE
    {
        "name": "MEGA BUNDLE — Complete RAG Engineering Stack",
        "description": "EVERYTHING: Architecture Blueprint + 10 n8n Workflows + Debug Playbook + Agent Context Kit + Eval Framework + Engineering Handbook + Ingestion Toolkit + Dashboard + Claude Skills + Embeddings Service + Agentic Commerce Playbook. $1,400+ value for $497. Build a production RAG system from scratch in one weekend.",
        "price_cents": 49700,
        "currency": "usd",
    },
]

results = []
for p in PRODUCTS:
    if p["name"] in existing:
        print(f"⏭ SKIP (exists): {p['name']}")
        continue

    product = stripe.Product.create(
        name=p["name"],
        description=p["description"],
        metadata={"source": "nomos-ai", "type": "digital", "agentic": "true"},
    )

    price = stripe.Price.create(
        product=product.id,
        unit_amount=p["price_cents"],
        currency=p["currency"],
    )

    payment_link = stripe.PaymentLink.create(
        line_items=[{"price": price.id, "quantity": 1}],
        metadata={"product": p["name"]},
    )

    print(f"✓ {p['name']} (${p['price_cents']/100:.0f}) → {payment_link.url}")
    results.append({"name": p["name"], "price": f"${p['price_cents']/100:.0f}", "url": payment_link.url})

print("\n" + "="*60)
print("ALL PRODUCTS CREATED:")
print("="*60)
for r in results:
    print(f"  {r['name']} ({r['price']}): {r['url']}")
