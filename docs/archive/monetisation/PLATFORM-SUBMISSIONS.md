# Platform Submissions — Status & URLs

> Last updated: 2026-03-09

## LIVE (Products Listed & Purchasable)

### 1. Whop — 14 products LIVE
- **Store URL**: https://whop.com/nomosai/
- **Status**: LIVE, all 14 products visible and purchasable
- **Products**: MEGA BUNDLE ($497), Architecture ($197), n8n Workflows ($197), etc.

### 2. Stripe — 19 products LIVE
- **Status**: All 19 payment links active and returning HTTP 200
- **Products & Links**:
  - $497 MEGA BUNDLE: https://buy.stripe.com/6oU7sEaTM3z59Dtdkx5J60d
  - $197 Multi-RAG Architecture: https://buy.stripe.com/aFa14g4vob1x3f5bcp5J602
  - $197 n8n Workflows: https://buy.stripe.com/bJe00c9PI8Tp2b1a8l5J603
  - $197 Enterprise Website: https://buy.stripe.com/14A6oAaTM4D94j93JX5J604
  - $197 Agentic Commerce: https://buy.stripe.com/aFa3co9PI5Hd2b11BP5J607
  - $157 AI Agent Orchestration: https://buy.stripe.com/aFa00c1jc5Hd02T3JX5J60h
  - $147 MCP + RAG Playbook: https://buy.stripe.com/6oU6oA6Dw2v1dTJdkx5J60i
  - $147 RAG Handbook: https://buy.stripe.com/eVq14g6Dwd9F6rh94h5J606
  - $137 Multimodal RAG: https://buy.stripe.com/3cIeV6aTMglR16X2FT5J60e
  - $127 Eval Framework: https://buy.stripe.com/fZu4gs2ng1qX6rh0xL5J605
  - $107 Latency Guide: https://buy.stripe.com/3cI5kw9PI1qX3f5bcp5J60g
  - $97 RAG Ingestion Toolkit: https://buy.stripe.com/dRm7sEfa27PlcPFgwJ5J608
  - $97 Dashboard Template: https://buy.stripe.com/14AcMYbXQ7PldTJ5S55J60a
  - $97 Operations Runbook: https://buy.stripe.com/dRm8wI1jcerf1148B85J609
  - $87 Chunking Guide: https://buy.stripe.com/6oU5kw5zs1qXcPFcgt5J60f
  - $67 Self-Hosted Embeddings: https://buy.stripe.com/aFa00ce5Y0mT9Dtcgt5J60c
  - $67 SOTA Benchmark Dataset: https://buy.stripe.com/cNi5kwaTMfhN5nd3JX5J60b
  - $47 Debug Playbook: https://buy.stripe.com/00w7sEd1U2v14j92FT5J600
  - $47 Claude Code Skills: https://buy.stripe.com/7sY8wIge64D93f53JX5J609
  - $27 AI Agent Context Kit: https://buy.stripe.com/7sY9AMbXQ4D94j95S55J601

### 3. GitHub Pages — Landing Pages LIVE
- **Buy Page**: https://lbjlincoln.github.io/rag-dashboard/buy.html (JUST DEPLOYED)
- **Store Page**: https://lbjlincoln.github.io/rag-dashboard/store.html
- **Dashboard**: https://lbjlincoln.github.io/rag-dashboard/

### 4. Vercel Sites — 5 sites LIVE
- https://rag-mega-bundle.vercel.app/
- https://rag-free-tools.vercel.app/
- https://ai-agent-marketplace-sable.vercel.app/
- https://rag-dashboard.vercel.app/
- https://rag-mega-bundle-v2.vercel.app/

---

## MANUAL SUBMISSION REQUIRED (Do NOW)

### 5. Gumroad — CREATE PRODUCTS MANUALLY
- **Store URL**: https://nomos42.gumroad.com
- **API**: POST /products returns 404 (deprecated). Must create manually.
- **Token works**: GET /v2/products returns success (0 products)
- **Action**: Go to https://gumroad.com/products/new
- **Content ready**: Full copy-paste content in `monetisation/gumroad-listings.md`
- **Products to create** (4):
  1. RAG Debug Playbook ($47) → permalink: rag-debug-playbook
  2. AI Agent Context Kit ($27) → permalink: ai-agent-context-kit
  3. Multi-RAG Architecture Blueprint ($197) → permalink: multi-rag-blueprint
  4. Site Pro en 5 min ($17) → permalink: site-pro-5min

### 6. Lemon Squeezy — CREATE PRODUCTS MANUALLY
- **Store URL**: https://nomos42.lemonsqueezy.com
- **API**: POST /products returns 405 (read-only). Must create via dashboard.
- **Action**: Go to https://app.lemonsqueezy.com/products
- **Create same 15 products as Stripe** (copy names/prices/descriptions from above)

### 7. Product Hunt — SUBMIT PRODUCT
- **URL**: https://www.producthunt.com/posts/new
- **Account must be 7+ days old**
- **Submission details**:
  - Name: Nomos Multi-RAG
  - Tagline: "4 RAG pipelines on free infrastructure. 87.5% accuracy." (60 chars max)
  - URL: https://lbjlincoln.github.io/rag-dashboard/buy.html
  - Description: Production-grade Multi-RAG system with Standard, Graph, and Quantitative pipelines. Built from 90+ engineering sessions. 19 products available.

### 8. n8n Template Library — SUBMIT 3 WORKFLOWS
- **URL**: https://n8n.io/workflows/ (click "Share a workflow")
- **Template files ready**: `n8n/templates/`
  - standard-rag-template.json (23 nodes)
  - graph-rag-template.json (26 nodes)
  - quantitative-rag-template.json (20 nodes)
- **Submission process**: Copy JSON, paste in template code field
- **Template 1**: "Multi-Index Standard RAG Pipeline (Pinecone + Supabase + Groq)"
  - Tags: RAG, Pinecone, Supabase, Groq, LLM, AI
- **Template 2**: "Graph RAG Pipeline (Neo4j Knowledge Graph + Groq)"
  - Tags: RAG, Neo4j, Knowledge Graph, Groq, AI
- **Template 3**: "Quantitative RAG Pipeline (SQL Generation + LiteLLM)"
  - Tags: RAG, SQL, LiteLLM, Finance, AI

### 9. HaveWorkflow.com — SUBMIT 3 WORKFLOWS
- **URL**: https://haveworkflow.com/share-workflow/
- **Process**: Fill form, upload JSON, publish
- **Same 3 templates as n8n above**

### 10. Vercel Templates — SUBMIT WEBSITE TEMPLATE
- **Submission form**: https://vercel.com/templates/submit
- **Alt form**: https://docs.google.com/forms/d/e/1FAIpQLSfU4EP7LkkUb2RX7vxxRJgq1iCiqYS6JW6CaZxMExR_hQR_hQ/viewform
- **Submit**: rag-website repo as a Next.js template
- **GitHub repo**: https://github.com/LBJLincoln/rag-website

### 11. RapidAPI — PUBLISH API (Requires Account)
- **Sign up**: https://rapidapi.com/provider
- **OpenAPI spec ready**: `monetisation/rapidapi/openapi.json`
- **Publish script ready**: `monetisation/rapidapi/publish-rapidapi.py`
- **3 endpoints**: Standard RAG, Graph RAG, Quantitative RAG
- **Pricing tiers**: Free (10/day), Basic ($9.99, 100/day), Pro ($29.99, 1000/day)
- **Action**: Create account, set RAPIDAPI_KEY + RAPIDAPI_OWNER, run script

### 12. Dev.to — PUBLISH ARTICLE
- **URL**: https://dev.to/new
- **Need API key**: https://dev.to/settings/extensions → Generate API Key
- **Content ready**: Distribution posts in `monetisation/distribution-posts.md`
- **Article script ready**: `monetisation/devto-poster.py`

---

## RESEARCH / FUTURE

### 13. GitHub Marketplace — NOT APPLICABLE
- GitHub Marketplace is for GitHub Apps and Actions only, not digital products.
- Our tools are digital downloads, not GitHub integrations.

### 14. HuggingFace Monetization — NO NATIVE SUPPORT
- HF Spaces don't have built-in monetization (no donate button, no paid access).
- Could add a "Buy" link in Space README pointing to buy.html.

### 15. free-for-dev GitHub PR — LOW PRIORITY
- Only for free-tier SaaS offerings. Our RAG API has a free tier (10 req/day).
- Could submit PR to ripienaar/free-for-dev for the API.

---

## SUMMARY

| Platform | Status | Products | Automation |
|----------|--------|----------|------------|
| Whop | LIVE | 14 | API |
| Stripe | LIVE | 19 | API |
| GH Pages (buy.html) | LIVE | All | Deployed |
| Vercel Sites (5) | LIVE | Showcase | Deployed |
| Gumroad | MANUAL NEEDED | 0/4 | Copy-paste ready |
| Lemon Squeezy | MANUAL NEEDED | 0/15 | Copy-paste ready |
| Product Hunt | MANUAL NEEDED | 0/1 | Guide ready |
| n8n Templates | MANUAL NEEDED | 0/3 | JSONs ready |
| HaveWorkflow | MANUAL NEEDED | 0/3 | JSONs ready |
| Vercel Templates | MANUAL NEEDED | 0/1 | Form link ready |
| RapidAPI | NEEDS ACCOUNT | 0/1 | Script ready |
| Dev.to | NEEDS API KEY | 0/1 | Script ready |
