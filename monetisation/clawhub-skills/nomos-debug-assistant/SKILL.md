---
name: nomos-debug-assistant
description: Diagnose and fix RAG pipeline failures using 90+ documented fix patterns from 76+ debugging sessions. Covers n8n workflows, LLM errors, vector DB issues, SQL failures, and infrastructure outages. Self-Healing RAG pattern.
version: 1.0.0
metadata:
  openclaw:
    requires:
      env: []
      bins:
        - curl
---

# Nomos RAG Debug Assistant

Diagnose RAG pipeline failures using patterns from 90+ real-world fixes across 76+ sessions.

## Diagnostic Flowchart: Wrong Results

```
Response received but wrong
  |
  +-- Contains "[object Object]"?
  |     YES -> n8n Set node serializer bug
  |            Fix: typeof val === 'object' ? JSON.stringify(val) : val
  |
  +-- Contains HTML (<!DOCTYPE>)?
  |     YES -> API URL wrong. Missing /chat/completions
  |
  +-- "Query must start with SELECT"?
  |     -> Bad SQL from LLM
  |     Fix: Add ILIKE + sample data + static schema to prompt
  |
  +-- Empty response ([] or "")?
  |     -> Missing Respond to Webhook node in n8n
  |
  +-- Numbers wrong but SQL correct?
        -> Bad WHERE clause (wrong company name/year)
        Fix: ILIKE for fuzzy matching + sample data in prompt
```

## Diagnostic Flowchart: HTTP Errors

```
HTTP error calling webhook
  |
  +-- 404? -> Workflow inactive or wrong path
  |          Activate: POST /rest/workflows/<ID>/activate
  |
  +-- 429? -> LLM rate limit
  |          Wait 60s, switch model, or rotate key
  |
  +-- 500? -> Credential expired or DB timeout
  |          LiteLLM: use short model names (gemma-27b not google/gemma-3-27b-it)
  |
  +-- 502/503? -> HF Space sleeping
               Wait 30s for cold start, retry
```

## Step 1: Identify Symptom

Collect:
- Which pipeline? (Standard / Graph / Quantitative)
- HTTP status code
- Response body (first 500 chars)
- When did it last work?

## Step 2: Health Check

```bash
# 1. n8n alive?
curl -s -o /dev/null -w "%{http_code}" "https://lbjlincoln-nomos-rag-engine.hf.space/healthz"

# 2. Webhook registered?
curl -s -o /dev/null -w "%{http_code}" -X POST \
  "https://lbjlincoln-nomos-rag-engine.hf.space/webhook/rag-multi-index-v3" \
  -H "Content-Type: application/json" \
  -d '{"question": "test", "tenant_id": "benchmark"}'

# 3. Response content
curl -s -X POST "https://lbjlincoln-nomos-rag-engine.hf.space/webhook/rag-multi-index-v3" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is RAG?", "tenant_id": "benchmark"}' | head -c 500
```

## Step 3: Pattern Lookup

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| `[object Object]` | n8n Set node | Add typeof check |
| HTML in response | Wrong API URL | Add /chat/completions |
| "Query must start with SELECT" | Bad SQL | Add ILIKE + sample data |
| Empty `[]` | Missing terminal node | Add Respond to Webhook |
| HTTP 404 | Workflow inactive | Activate via API |
| HTTP 429 | Rate limit | Wait 60s or rotate |
| HTTP 500 (Quant) | LiteLLM model name | Use short alias |
| Timeout >90s | Slow LLM or DB | Reduce top_k |

## Step 4: Classify Severity

| Level | Category | Action |
|-------|----------|--------|
| P0 | Infrastructure down | Fix immediately |
| P1 | Rate limit | Switch key, wait |
| P2 | Workflow bug | Patch n8n |
| P3 | Data quality | Re-ingest |
| P4 | Model behavior | Prompt tune |

## Step 5: Apply and Verify

1. Apply fix from pattern table
2. Test with 3 questions
3. If all 3 pass: confirmed
4. Test ALL pipelines for regressions

## Iron Rules

1. **1 fix per iteration** — Never change multiple things at once
2. **Test before sync** — 5-question smoke test before syncing workflows
3. **3+ regressions = REVERT**
4. **PATCH not PUT** for n8n API
5. **Cookie auth for n8n** — API key is unreliable
6. **Check for duplicate workflows**
7. **Port 5432 for Supabase** — Port 6543 drops inserts

## Full Access

Complete playbook with 90+ fixes, anti-patterns, self-healing scripts:

- **Debug Playbook** ($47): https://buy.stripe.com/00w7sEd1U2v14j92FT5J600
- **MEGA BUNDLE** ($497): https://buy.stripe.com/6oU7sEaTM3z59Dtdkx5J60d
