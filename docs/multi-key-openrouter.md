# Multi-Key OpenRouter Setup

> Last updated: 2026-02-23T17:00:00+01:00

## Why Multi-Key?

OpenRouter free tier has a rate limit of ~20 requests/minute per API key. With 4+ pipelines running in parallel, a single key becomes the bottleneck. By assigning 1 key per pipeline, we get 5x the rate limit (100 req/min total).

## How It Works

The HF Space docker-compose exposes per-pipeline environment variables:

| Variable | Pipeline | Used by |
|----------|----------|---------|
| `OPENROUTER_KEY_STANDARD` | Standard RAG V3.4 | Standard pipeline LLM nodes |
| `OPENROUTER_KEY_GRAPH` | Graph RAG V3.3 | Graph pipeline LLM nodes |
| `OPENROUTER_KEY_QUANTITATIVE` | Quantitative V2.0 | Quantitative pipeline LLM nodes |
| `OPENROUTER_KEY_ORCHESTRATOR` | Orchestrator V10.1 | Orchestrator pipeline LLM nodes |
| `OPENROUTER_KEY_PME` | PME Gateway + Action | PME pipeline LLM nodes |
| `OPENROUTER_API_KEY` | Fallback (all pipelines) | Default if per-pipeline key not set |

All per-pipeline keys **default to `OPENROUTER_API_KEY`** if not set. So everything works with a single key, and you add separate keys incrementally.

## Adding New Keys

### Step 1: Create OpenRouter accounts

Go to https://openrouter.ai and create separate accounts (different emails):
- Account 1: Standard pipeline → get API key `sk-or-v1-aaa...`
- Account 2: Graph pipeline → get API key `sk-or-v1-bbb...`
- Account 3: Quantitative pipeline → get API key `sk-or-v1-ccc...`
- Account 4: Orchestrator pipeline → get API key `sk-or-v1-ddd...`
- Account 5: PME pipeline → get API key `sk-or-v1-eee...`

### Step 2: Add keys to .env.local

```bash
# In /home/termius/mon-ipad/.env.local, add:
OPENROUTER_KEY_STANDARD=sk-or-v1-aaa...
OPENROUTER_KEY_GRAPH=sk-or-v1-bbb...
OPENROUTER_KEY_QUANTITATIVE=sk-or-v1-ccc...
OPENROUTER_KEY_ORCHESTRATOR=sk-or-v1-ddd...
OPENROUTER_KEY_PME=sk-or-v1-eee...
```

### Step 3: Re-deploy HF Space

```bash
source .env.local && bash scripts/deploy-hf-space.sh
```

This pushes the new keys as HF Space secrets and triggers a rebuild.

### Step 4: Verify

```bash
bash scripts/deploy-overnight-v2.sh --status
```

All 9 webhooks should respond HTTP 200.

## Workflow Integration

n8n workflows access keys via `$env.OPENROUTER_KEY_STANDARD` etc. To migrate existing workflows:

1. In n8n workflow editor, find HTTP Request nodes that call OpenRouter
2. Replace the hardcoded `Authorization: Bearer $env.OPENROUTER_API_KEY` with per-pipeline key:
   - Standard workflow: `$env.OPENROUTER_KEY_STANDARD`
   - Graph workflow: `$env.OPENROUTER_KEY_GRAPH`
   - etc.

The docker-compose already injects all 5 keys into all n8n containers (main + 3 workers).

## Capacity After Multi-Key

| Config | Rate Limit | Eval Speed (4000q) |
|--------|-----------|-------------------|
| 1 key | ~20 req/min | ~21h (sequential) |
| 5 keys + 3 workers | ~100 req/min | ~2-3h |
| 5 keys + 10 workers | ~100 req/min | ~1.5h (worker-bound, not rate-bound) |
