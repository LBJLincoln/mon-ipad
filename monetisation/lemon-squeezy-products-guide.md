# Lemon Squeezy Product Setup Guide

> Manual dashboard walkthrough for creating all 14 Nomos RAG products.
> Lemon Squeezy API cannot create products — dashboard only.

---

## Account Info

| Field | Value |
|-------|-------|
| Store ID | `310020` |
| User | Alexis Moret |
| Email | lahargnedebartoli@gmail.com |
| Account ID | `6665457` |
| Dashboard | https://app.lemonsqueezy.com |

---

## 1. Store Settings (Do This First)

1. Go to **Settings > General**
2. Set store name: **Nomos AI**
3. Set store URL slug: `nomos-ai`
4. Currency: **USD**
5. Go to **Settings > Tax** — enable **Tax Inclusive** pricing (Lemon Squeezy handles EU VAT automatically via Merchant of Record)
6. Go to **Settings > Checkout** — enable:
   - Custom thank-you page URL: `https://lbjlincoln.github.io/rag-dashboard/store.html#thanks`
   - Enable "Send receipt email"
   - Enable "Collect billing address" (required for tax compliance)
7. Go to **Settings > Branding** — upload logo, set brand color to `#1a1a2e` (dark navy)

---

## 2. Product Creation (14 Products)

For each product below, go to **Products > New Product** and fill in:

- **Product type**: Digital Download
- **Tax category**: Digital Goods (default)
- **Status**: Published

After creating each product, upload the corresponding ZIP file under the **Files** tab.

---

### TIER 1 — Premium ($197-$497)

#### 1. MEGA BUNDLE — Complete RAG Engineering Stack — $497

| Field | Value |
|-------|-------|
| Name | MEGA BUNDLE — Complete RAG Engineering Stack |
| Price | $497 (one-time) |
| Description | Everything you need to build a production RAG system in one weekend. Includes all 13 products: Architecture Blueprint, 10 n8n Workflows, Enterprise Website Template, Agentic Commerce Playbook, Engineering Handbook, Eval Framework, Ingestion Toolkit, Dashboard, Benchmark Datasets, Embeddings Service, Debug Playbook, Claude Code Skills, and Agent Context Kit. Over $1,400 in value. |
| Tags | `bundle`, `rag`, `ai`, `production`, `best-value` |
| Files | Upload ALL 6 ZIPs from `monetisation/packages/` |
| Media | Add product image showing "BEST VALUE" badge |

---

#### 2. Multi-RAG Architecture Blueprint — $197

| Field | Value |
|-------|-------|
| Name | Multi-RAG Architecture Blueprint |
| Price | $197 (one-time) |
| Description | Complete architecture for a 4-pipeline RAG system handling 61K+ questions at 87-95% accuracy. Covers infrastructure setup on 100% free tiers, n8n workflow configuration, LiteLLM proxy setup, evaluation methodology, and phase-based scaling strategy. Built from 80+ production sessions. |
| Tags | `architecture`, `rag`, `ai`, `blueprint`, `production` |
| Files | Included in `rag-engineering-handbook.zip` |

---

#### 3. n8n RAG Workflow Collection — $197

| Field | Value |
|-------|-------|
| Name | n8n RAG Workflow Collection — 10 Production Workflows |
| Price | $197 (one-time) |
| Description | 10 battle-tested n8n workflow JSON files ready for import: Standard RAG, Graph RAG, Quantitative RAG, Orchestrator, Enrichment, Ingestion, PME Gateway, Project Chatbot, and more. Zero setup required — works with Groq, OpenRouter, and LiteLLM out of the box. |
| Tags | `n8n`, `workflows`, `rag`, `automation`, `no-code` |
| Files | Upload `n8n-rag-workflows.zip` |

---

#### 4. Enterprise RAG Website Template — $197

| Field | Value |
|-------|-------|
| Name | Enterprise RAG Website Template — Next.js 14 |
| Price | $197 (one-time) |
| Description | Production-ready Next.js 14 + Tailwind + shadcn/ui website with 4 sector-specific AI chatbots (Finance, Legal, Construction, Manufacturing). Features MacBook frame animations, live SSE streaming dashboard, and pre-configured SEO. Deploy to Vercel in 5 minutes. |
| Tags | `website`, `nextjs`, `template`, `chatbot`, `enterprise` |
| Files | Not currently packaged — create from rag-website repo |

---

#### 5. Agentic Commerce Playbook — $197

| Field | Value |
|-------|-------|
| Name | Agentic Commerce Playbook |
| Price | $197 (one-time) |
| Description | How to sell AI products TO AI agents. Covers ACP protocol implementation, 10-platform distribution strategy, MCP server integration, and revenue automation. Based on McKinsey's $1T agentic commerce prediction by 2030. Get the first-mover advantage. |
| Tags | `agentic`, `commerce`, `ai-agents`, `mcp`, `strategy` |
| Files | Included in `agent-context-kit.zip` |

---

### TIER 2 — Mid-Range ($97-$147)

#### 6. RAG Engineering Handbook — $147

| Field | Value |
|-------|-------|
| Name | RAG Engineering Handbook — 2,500+ Lines |
| Price | $147 (one-time) |
| Description | The encyclopedia of RAG engineering: 79+ production fixes with root cause analysis, complete infrastructure reference for Pinecone, Neo4j, Supabase, and n8n, project roadmap with SOTA research review, and 1,000+ document types cataloged by sector. |
| Tags | `handbook`, `documentation`, `rag`, `reference`, `production` |
| Files | Upload `rag-engineering-handbook.zip` |

---

#### 7. RAG Evaluation Framework — $127

| Field | Value |
|-------|-------|
| Name | RAG Evaluation Framework — Phase-Gated Testing |
| Price | $127 (one-time) |
| Description | Complete Python evaluation suite with smoke tests, parallel batch evaluation, phase gates (200 to 1K to 10K to 61K questions), regression detection, and live metrics dashboard. 11 production scripts battle-tested across 80+ sessions. |
| Tags | `evaluation`, `testing`, `python`, `rag`, `benchmarks` |
| Files | Upload `rag-eval-framework.zip` |

---

#### 8. RAG Ingestion Toolkit — $97

| Field | Value |
|-------|-------|
| Name | RAG Ingestion Toolkit — Scripts & Services |
| Price | $97 (one-time) |
| Description | 20+ production scripts for document ingestion: multi-format parsing (PDF, DOCX, JSONL), Pinecone/Neo4j/Supabase loaders, BM25 service, reranker service, quality validation, and contextual enrichment. Proven on 34K+ documents. |
| Tags | `ingestion`, `scripts`, `pinecone`, `neo4j`, `data-pipeline` |
| Files | Not currently packaged — create from rag-data-ingestion repo |

---

#### 9. RAG Pipeline Dashboard — $97

| Field | Value |
|-------|-------|
| Name | RAG Pipeline Dashboard Template |
| Price | $97 (one-time) |
| Description | Real-time HTML/JS dashboard for RAG pipeline monitoring. Features Chart.js visualizations, trading board with BEST/WORST/MIDDLE ranking, auto-refresh, Vercel serverless API, and offline fallback mode. Deploy in 2 minutes on GitHub Pages or Vercel. |
| Tags | `dashboard`, `monitoring`, `visualization`, `html`, `chartjs` |
| Files | Not currently packaged — create from rag-dashboard repo |

---

### TIER 3 — Accessible ($27-$67)

#### 10. SOTA Benchmark Dataset Toolkit — $67

| Field | Value |
|-------|-------|
| Name | SOTA Benchmark Dataset Toolkit |
| Price | $67 (one-time) |
| Description | 18 curated SOTA benchmark datasets totaling 61,661 questions with download scripts, phase generators, and evaluation harness. Includes SQuAD v2, MS MARCO, TriviaQA, HotpotQA, FinQA, and more. Ready for RAG evaluation out of the box. |
| Tags | `benchmarks`, `datasets`, `evaluation`, `sota`, `research` |
| Files | Not currently packaged — create from rag-tests repo |

---

#### 11. Self-Hosted Embeddings Service — $67

| Field | Value |
|-------|-------|
| Name | Self-Hosted Embeddings Service |
| Price | $67 (one-time) |
| Description | Deploy your own Jina-compatible embeddings API on HuggingFace Spaces for free. Features lazy model loading, health monitoring, and TEI-compatible endpoints. Stop paying per-token for embeddings. Includes complete deployment guide. |
| Tags | `embeddings`, `self-hosted`, `huggingface`, `jina`, `free-tier` |
| Files | Not currently packaged — create from embeddings Space code |

---

#### 12. RAG Debug Playbook — $47

| Field | Value |
|-------|-------|
| Name | RAG Debug Playbook — 79+ Production Fixes |
| Price | $47 (one-time) |
| Description | 79+ documented production fixes with full root cause analysis, diagnostic flowcharts, and prevention strategies. Covers n8n, Pinecone, Neo4j, Supabase, LiteLLM, embeddings, and more. Stop guessing — fix RAG issues in minutes instead of hours. |
| Tags | `debugging`, `troubleshooting`, `fixes`, `rag`, `production` |
| Files | Upload `rag-debug-playbook.zip` |

---

#### 13. Claude Code Skill Pack — $47

| Field | Value |
|-------|-------|
| Name | Claude Code Skill Pack — 17 Custom Commands |
| Price | $47 (one-time) |
| Description | 17 production-ready Claude Code skills for AI-powered development: session management, evaluation runners, self-healing pipelines, cross-repo sync, regression detection, metrics dashboards, website audit, and more. Drop into your .claude/commands/ folder and go. |
| Tags | `claude-code`, `skills`, `automation`, `developer-tools`, `ai-coding` |
| Files | Upload `claude-code-skills.zip` |

---

#### 14. AI Agent Context Kit — $27

| Field | Value |
|-------|-------|
| Name | AI Agent Context Kit |
| Price | $27 (one-time) |
| Description | Production-tested context management patterns for AI agents: CLAUDE.md templates, state file architecture, multi-repo coordination, session persistence, and memory management. The foundation for reliable AI agent workflows. |
| Tags | `ai-agents`, `context`, `templates`, `claude`, `workflow` |
| Files | Upload `agent-context-kit.zip` |

---

## 3. Step-by-Step Dashboard Walkthrough

### Creating a Single Product

1. Log in at https://app.lemonsqueezy.com
2. Navigate to **Products** in the left sidebar
3. Click **+ New Product** (top right)
4. Fill in:
   - **Name**: Product name from the list above
   - **Description**: Copy the description text
   - **Pricing**: Select "One-time" payment, enter the price in USD
   - **Tax category**: Digital Goods
   - **Media**: Upload a product image (optional but recommended)
5. Click **Save Product**
6. Go to the **Files** tab on the product page
7. Click **Upload File** and select the corresponding ZIP from `monetisation/packages/`
8. Go to the **Variants** tab — keep the default single variant
9. Toggle **Status** to **Published**
10. Note the product URL from the **Share** tab

### Uploading ZIP Files

Lemon Squeezy supports files up to 5GB per product. For each product:

1. Open the product in the dashboard
2. Click the **Files** tab
3. Click **Upload file**
4. Select the ZIP from your local machine (download from `monetisation/packages/` first)
5. Files are served securely — customers get unique download links after purchase

**Available ZIPs** (in `monetisation/packages/`):
| ZIP File | Size | Products |
|----------|------|----------|
| `agent-context-kit.zip` | ~20K | AI Agent Context Kit, Agentic Commerce Playbook |
| `claude-code-skills.zip` | ~50K | Claude Code Skill Pack |
| `n8n-rag-workflows.zip` | ~150K | n8n RAG Workflow Collection |
| `rag-debug-playbook.zip` | ~30K | RAG Debug Playbook |
| `rag-engineering-handbook.zip` | ~100K | RAG Engineering Handbook, Architecture Blueprint |
| `rag-eval-framework.zip` | ~100K | RAG Evaluation Framework |

**Products without ZIPs yet** (need packaging):
- Enterprise RAG Website Template (from `rag-website` repo)
- RAG Ingestion Toolkit (from `rag-data-ingestion` repo)
- RAG Pipeline Dashboard (from `rag-dashboard` repo)
- SOTA Benchmark Dataset Toolkit (from `rag-tests` repo)
- Self-Hosted Embeddings Service (from HF Space code)

For the MEGA BUNDLE, upload all 6 existing ZIPs plus any additional ones created later.

---

## 4. Discount Code Strategy

### Creating Discount Codes

1. Go to **Discounts** in the left sidebar
2. Click **+ New Discount**

#### LAUNCH20 — General Launch Discount

| Field | Value |
|-------|-------|
| Name | LAUNCH20 |
| Code | `LAUNCH20` |
| Type | Percentage |
| Amount | 20% |
| Applies to | All products |
| Usage limit | 100 uses total |
| Expiry | 30 days from creation |

#### BUNDLE30 — Mega Bundle Special

| Field | Value |
|-------|-------|
| Name | BUNDLE30 |
| Code | `BUNDLE30` |
| Type | Percentage |
| Amount | 30% |
| Applies to | MEGA BUNDLE only |
| Usage limit | 50 uses total |
| Expiry | 14 days from creation |

#### Future Discount Ideas

| Code | Discount | Target | Use Case |
|------|----------|--------|----------|
| `REDDIT25` | 25% | All | Reddit community posts |
| `HN20` | 20% | All | Hacker News launch |
| `DEVTO15` | 15% | All | Dev.to article readers |
| `EARLYBIRD40` | 40% | MEGA BUNDLE | First 10 customers |
| `TWITTER10` | 10% | All | Twitter/X followers |

---

## 5. After Creation: API Checkout URLs

Once products exist in the dashboard, use the API to generate checkout URLs for marketing.

### Step 1: Get Product and Variant IDs

```bash
# List all products
curl -s https://api.lemonsqueezy.com/v1/products?filter[store_id]=310020 \
  -H "Authorization: Bearer $LEMON_SQUEEZY_API_KEY" \
  -H "Accept: application/vnd.api+json" | python3 -m json.tool
```

### Step 2: Get Variant IDs (needed for checkouts)

```bash
# List variants for a product
curl -s "https://api.lemonsqueezy.com/v1/variants?filter[product_id]=PRODUCT_ID" \
  -H "Authorization: Bearer $LEMON_SQUEEZY_API_KEY" \
  -H "Accept: application/vnd.api+json" | python3 -m json.tool
```

### Step 3: Create Checkout URLs via API

```python
#!/usr/bin/env python3
"""Generate Lemon Squeezy checkout URLs for all products."""
import os, json, urllib.request

API_KEY = os.environ["LEMON_SQUEEZY_API_KEY"]
STORE_ID = "310020"
BASE = "https://api.lemonsqueezy.com/v1"

def api_get(path):
    req = urllib.request.Request(f"{BASE}{path}", headers={
        "Authorization": f"Bearer {API_KEY}",
        "Accept": "application/vnd.api+json",
    })
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

def create_checkout(variant_id, discount_code=None):
    payload = {
        "data": {
            "type": "checkouts",
            "attributes": {
                "checkout_options": {
                    "discount": True,
                    "media": True,
                },
                "checkout_data": {
                    "discount_code": discount_code or "",
                },
            },
            "relationships": {
                "store": {"data": {"type": "stores", "id": STORE_ID}},
                "variant": {"data": {"type": "variants", "id": str(variant_id)}},
            },
        }
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(f"{BASE}/checkouts", data=data, headers={
        "Authorization": f"Bearer {API_KEY}",
        "Accept": "application/vnd.api+json",
        "Content-Type": "application/vnd.api+json",
    })
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
        return result["data"]["attributes"]["url"]

# Get all products
products = api_get(f"/products?filter[store_id]={STORE_ID}")
for p in products["data"]:
    name = p["attributes"]["name"]
    pid = p["id"]
    # Get variant for this product
    variants = api_get(f"/variants?filter[product_id]={pid}")
    if variants["data"]:
        vid = variants["data"][0]["id"]
        url = create_checkout(vid)
        print(f"{name}: {url}")
```

### Step 4: Direct Store URL (no API needed)

Every product also gets a direct URL at:
```
https://nomos-ai.lemonsqueezy.com/buy/<product-slug>
```

You can append `?discount_code=LAUNCH20` to pre-apply a discount.

---

## 6. Quick Reference — Product Creation Order

Recommended order (highest value first):

| # | Product | Price | ZIP Ready |
|---|---------|-------|-----------|
| 1 | MEGA BUNDLE | $497 | Yes (all ZIPs) |
| 2 | n8n RAG Workflow Collection | $197 | Yes |
| 3 | Multi-RAG Architecture Blueprint | $197 | Yes |
| 4 | Agentic Commerce Playbook | $197 | Yes |
| 5 | Enterprise RAG Website Template | $197 | No |
| 6 | RAG Engineering Handbook | $147 | Yes |
| 7 | RAG Evaluation Framework | $127 | Yes |
| 8 | RAG Ingestion Toolkit | $97 | No |
| 9 | RAG Pipeline Dashboard | $97 | No |
| 10 | SOTA Benchmark Dataset Toolkit | $67 | No |
| 11 | Self-Hosted Embeddings Service | $67 | No |
| 12 | RAG Debug Playbook | $47 | Yes |
| 13 | Claude Code Skill Pack | $47 | Yes |
| 14 | AI Agent Context Kit | $27 | Yes |

**Total catalog value: $2,023**
**MEGA BUNDLE saves: $1,526 (75% off individual prices)**

---

## 7. Checklist

- [ ] Store settings configured (USD, tax, branding)
- [ ] All 14 products created in dashboard
- [ ] ZIP files uploaded for 9 ready products
- [ ] Remaining 5 ZIPs packaged and uploaded
- [ ] LAUNCH20 discount code created
- [ ] BUNDLE30 discount code created
- [ ] Checkout URLs generated via API
- [ ] URLs added to `monetisation/distribution-posts.md`
- [ ] Sales page updated with Lemon Squeezy links as alternative to Stripe
- [ ] Test purchase completed with discount code
