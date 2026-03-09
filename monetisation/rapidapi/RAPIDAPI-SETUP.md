# RapidAPI Setup Guide -- Nomos Multi-RAG API

## Overview

This guide covers publishing the Nomos Multi-RAG API on RapidAPI Marketplace to monetize the 3 RAG pipelines (Standard, Graph, Quantitative).

## Files

| File | Purpose |
|------|---------|
| `openapi.json` | OpenAPI 3.0 specification (3 endpoints, full schemas) |
| `publish-rapidapi.py` | Automated listing script (create API, upload spec, set pricing) |
| `RAPIDAPI-SETUP.md` | This setup guide |

## Prerequisites

1. **RapidAPI Provider Account**
   - Sign up at https://rapidapi.com/provider
   - Go to **My APIs** in the provider dashboard

2. **API Keys**
   - Get your **Provider API Key** from https://rapidapi.com/developer/apps
   - Add to `.env.local`:
     ```bash
     export RAPIDAPI_KEY="your-provider-api-key"
     export RAPIDAPI_OWNER="your-rapidapi-username"
     ```

3. **Endpoints must be live**
   - Standard: `POST https://lbjlincoln-nomos-rag-engine.hf.space/webhook/rag-multi-index-v3`
   - Graph: `POST https://lbjlincoln-nomos-rag-engine.hf.space/webhook/ff622742-6d71-4e91-af71-b5c666088717`
   - Quantitative: `POST https://lbjlincoln-nomos-rag-engine.hf.space/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9`

## Option A: Automated Publishing

### 1. Dry run (no API calls)

```bash
cd /home/termius/mon-ipad
source .env.local
python3 monetisation/rapidapi/publish-rapidapi.py --dry-run
```

This shows what would be created without touching RapidAPI.

### 2. Publish for real

```bash
python3 monetisation/rapidapi/publish-rapidapi.py
```

The script will:
- Create the API listing (or find an existing one)
- Upload the OpenAPI 3.0 spec
- Configure 3 pricing tiers

### 3. Finalize in the dashboard

After the script runs, go to https://rapidapi.com/provider/dashboard to:
- Add a logo (use the dashboard favicon or a custom one)
- Write a long description with markdown
- Review endpoint documentation
- Click **Make Live** to publish

## Option B: Manual Publishing

If the Platform API is unavailable or your account does not have provider API access, follow these manual steps.

### 1. Create the API

1. Go to https://rapidapi.com/provider/dashboard
2. Click **Add New API**
3. Fill in:
   - **API Name**: `Nomos Multi-RAG API`
   - **Category**: Artificial Intelligence / Machine Learning
   - **Short Description**: "Production RAG API with 3 pipelines: Standard (vector), Graph (Neo4j), Quantitative (SQL). 46K+ documents, 86K+ graph nodes, 3,800+ financial tables."

### 2. Upload the OpenAPI spec

1. In your API settings, go to **Definition** > **Import**
2. Upload `monetisation/rapidapi/openapi.json`
3. RapidAPI will auto-detect the 3 POST endpoints

### 3. Configure the Base URL

Set the base URL to:
```
https://lbjlincoln-nomos-rag-engine.hf.space
```

### 4. Set up pricing

Go to **Pricing** and create 3 plans:

| Plan | Price | Daily Limit | Hourly Limit |
|------|-------|-------------|--------------|
| Free | $0 | 10 | 5 |
| Basic | $9.99/mo | 100 | 50 |
| Pro | $29.99/mo | 1,000 | 200 |

All plans get access to all 3 endpoints.

### 5. Test

Use the RapidAPI test console to verify each endpoint:

**Standard:**
```json
POST /webhook/rag-multi-index-v3
{"question": "What are the main safety regulations in construction?"}
```

**Graph:**
```json
POST /webhook/ff622742-6d71-4e91-af71-b5c666088717
{"question": "What companies operate in the construction sector?"}
```

**Quantitative:**
```json
POST /webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9
{"question": "What is the average revenue in the finance sector?"}
```

### 6. Publish

Click **Make Live** to publish on the RapidAPI marketplace.

## Pricing Rationale

| Tier | Target User | Margin |
|------|-------------|--------|
| **Free** (10 req/day) | Developers evaluating the API. Low cost (free-tier LLMs, self-hosted embeddings). Funnel to paid. |
| **Basic** $9.99 (100 req/day) | Prototypers and small projects. ~$0.10/query covers compute. |
| **Pro** $29.99 (1,000 req/day) | Production integrations. ~$0.03/query at volume. Priority on n8n execution queue. |

Infrastructure cost per query is near zero (free-tier LLMs on OpenRouter/Groq, self-hosted embeddings on HF cpu-basic, Supabase/Pinecone/Neo4j free tiers). Revenue is almost pure margin.

## Monitoring

After publishing, monitor usage via:
- **RapidAPI Analytics**: Provider dashboard shows calls/day, errors, latency
- **n8n Executions**: Check execution logs on the HF Space
- **trace_id**: Every response includes a `trace_id` for end-to-end debugging

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Endpoints return 502 | HF Space may be sleeping. Visit the Space URL to wake it. |
| Slow responses (>30s) | First request after sleep takes ~60s. Subsequent requests are 3-15s. |
| Graph returns "not available" | Query may not match entities in Neo4j. Try sector-specific entities. |
| Quant returns NULL_RESULT | SQL found no matching rows. Check the `sql_executed` field. |
| RapidAPI Platform API 403 | Your API key may lack provider permissions. Use manual setup. |

## RapidAPI Marketplace SEO

To maximize visibility on the marketplace:

1. **Title keywords**: "RAG API", "Knowledge Graph", "SQL Generation", "AI"
2. **Tags**: `rag`, `ai`, `nlp`, `knowledge-graph`, `sql`, `llm`, `retrieval-augmented-generation`
3. **Long description**: Include use cases, benchmarks (87.5% accuracy), and data coverage
4. **Examples**: Provide 3-5 example queries per endpoint in the documentation
5. **Tutorials**: Link to the dashboard at https://lbjlincoln.github.io/rag-dashboard/
