# Nomos RAG Debug Assistant — Moltbot Skill

> Version: 1.0.0 | Author: Nomos AI | License: Commercial (free tier + paid)
> Schema: moltbot-skill/v1

---

## Metadata

```yaml
name: nomos-debug-assistant
version: 1.0.0
author: Nomos AI
category: debugging-operations
tags: [rag-debug, n8n, troubleshooting, self-healing, fix-library, diagnostics]
pricing: free-tier-limited
purchase_url: https://buy.stripe.com/00w7sEd1U2v14j92FT5J600
full_access_price: "$47"
full_access_product: "RAG Debug Playbook - 75+ Fixes"
description: >
  Diagnose and fix RAG pipeline failures using patterns from 90+ documented fixes
  across 76+ debugging sessions. Covers n8n workflow issues, LLM provider errors,
  vector database problems, SQL generation failures, and infrastructure outages.
  Implements the Self-Healing RAG pattern: detect, diagnose, classify, auto-fix, verify.
capabilities:
  - symptom_based_diagnosis
  - error_pattern_matching
  - severity_classification
  - auto_fix_suggestions
  - regression_detection
  - infrastructure_health_check
  - n8n_workflow_debugging
```

---

## What This Skill Does

When a RAG pipeline breaks or returns incorrect results, this skill walks through a structured diagnostic process derived from 90+ real-world fixes. It matches symptoms to known patterns and suggests (or applies) the documented fix.

---

## Diagnostic Flowcharts

### Flowchart 1: Pipeline Responds But Result Is Wrong

```
Response received but wrong
    |
    +-- Response contains "[object Object]"?
    |       YES -> Serializer bug. Check typeof in n8n Set node.
    |              Wrap with: typeof val === 'object' ? JSON.stringify(val) : val
    |
    +-- Response contains HTML (<!DOCTYPE html>)?
    |       YES -> API URL is wrong. Missing /chat/completions path.
    |              Check OPENROUTER_BASE_URL in workflow credentials.
    |
    +-- Response = "Query must start with SELECT"?
    |       |
    |       +-- LLM returning 429? -> Rate limit. Wait 60s or rotate key.
    |       +-- LLM returning invalid JSON? -> Bad SQL generation.
    |       |       Add ILIKE, sample data, and static schema to prompt.
    |       +-- LLM returning HTML? -> URL missing /chat/completions
    |
    +-- SQL correct but numbers wrong?
    |       -> Bad WHERE clause (wrong company name, period, year)
    |       -> Fix: Add ILIKE for fuzzy matching + sample data in prompt
    |
    +-- Response empty (body = [] or "")?
    |       |
    |       +-- Orchestrator? -> executeWorkflow + respondToWebhook conflict
    |       |       Change Invoke nodes to httpRequest type
    |       +-- Other pipeline? -> Missing Respond to Webhook node
    |
    +-- Response from wrong pipeline?
            -> Intent classifier routing error
            -> Check routing logic in orchestrator
```

### Flowchart 2: HTTP Error When Calling Webhook

```
HTTP error calling webhook
    |
    +-- 404 "webhook not registered"?
    |       +-- Path correct? -> Verify against endpoint table below
    |       +-- Path correct but 404? -> Workflow not active
    |               Activate via n8n REST API: POST /rest/workflows/<ID>/activate
    |
    +-- 429 Too Many Requests?
    |       -> LLM provider rate limit (OpenRouter free tier)
    |       -> Wait 60s, switch model, or use multi-key rotation
    |
    +-- 500 Internal Server Error?
    |       +-- Check n8n execution log for the failed run
    |       +-- Common causes: credential expired, DB connection timeout
    |       +-- LiteLLM proxy: model name mismatch (use short names like "gemma-27b")
    |
    +-- 502 Bad Gateway / 503 Service Unavailable?
    |       -> HF Space is sleeping or restarting
    |       -> Wait 30s for cold start, then retry
    |       -> If persistent: Space may have crashed. Check HF Space logs.
    |
    +-- Connection timeout?
            -> n8n is processing (long query)
            -> Increase timeout to 120s
            -> Or: HF Space is down entirely
```

---

## Step-by-Step Debugging Instructions

### Step 1: Identify the Symptom

Collect these data points:
- Which pipeline? (Standard / Graph / Quantitative)
- HTTP status code received
- Response body (first 500 characters)
- Was it working before? When did it last work?

### Step 2: Check Infrastructure Health

Run these checks in order:

```bash
# 1. Is the n8n instance alive?
curl -s -o /dev/null -w "%{http_code}" \
  "https://lbjlincoln-nomos-rag-engine.hf.space/healthz"
# Expected: 200

# 2. Is the webhook registered? (should return 200, not 404)
curl -s -o /dev/null -w "%{http_code}" -X POST \
  "https://lbjlincoln-nomos-rag-engine.hf.space/webhook/rag-multi-index-v3" \
  -H "Content-Type: application/json" \
  -d '{"question": "test", "tenant_id": "benchmark"}'
# Expected: 200

# 3. Check response content
curl -s -X POST \
  "https://lbjlincoln-nomos-rag-engine.hf.space/webhook/rag-multi-index-v3" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is RAG?", "tenant_id": "benchmark"}' \
  | head -c 500
```

### Step 3: Match Symptom to Pattern

Use this lookup table. Find your symptom in the left column:

| Symptom | Pattern ID | Root Cause | Fix |
|---------|-----------|------------|-----|
| `[object Object]` in response | P-5.2 | n8n Set node serializer | Add `typeof` check before output |
| HTML in response body | P-5.1 | Wrong API base URL | Add `/chat/completions` to URL |
| `"Query must start with SELECT"` | P-5.3 | Bad SQL from LLM | Add ILIKE, sample data, static schema |
| Empty response `[]` | P-5.8 | Missing Respond to Webhook | Add terminal node in n8n |
| HTTP 404 on webhook | P-1.1 | Workflow inactive or wrong path | Activate workflow via API |
| HTTP 429 | P-7.6 | OpenRouter rate limit | Wait 60s or rotate key/model |
| HTTP 500 on Quant pipeline | P-8.1 | LiteLLM model name mismatch | Use short model alias (e.g., `gemma-27b`) |
| Response from wrong pipeline | P-6.1 | Orchestrator intent classification | Fix routing prompt |
| Timeout after 90s | P-10.1 | Slow LLM or DB query | Reduce top_k, simplify query |
| Pinecone "dimension mismatch" | P-9.1 | Wrong embedding model | Must use Jina v3 (1024-dim) |
| Neo4j "connection refused" | P-9.2 | Aura instance sleeping | Wake with any read query |
| Supabase "relation does not exist" | P-9.3 | Wrong schema or table name | Check tenant_id and table list |

### Step 4: Classify Severity

| Level | Category | Examples | Action |
|-------|----------|----------|--------|
| **P0** | Infrastructure | n8n down, HF Space crashed, DB unreachable | Fix immediately |
| **P1** | Rate Limit | 429, quota exhausted, key expired | Switch key/model, wait |
| **P2** | Workflow | [object Object], bad SQL, wrong routing | Patch n8n workflow |
| **P3** | Data | Missing vectors, stale embeddings, empty context | Re-ingest affected data |
| **P4** | Model | Hallucinations, low accuracy, wrong format | Prompt tuning |

### Step 5: Apply Fix

For P0-P2 issues with documented fixes:

1. Apply the fix as described in the pattern table
2. Test with 3 questions against the affected pipeline
3. If all 3 pass: fix confirmed
4. If any fail: escalate (the issue may be different from what the symptom suggests)

### Step 6: Verify No Regressions

After fixing, test ALL pipelines (not just the one you fixed):

```bash
# Test Standard
curl -s -X POST "https://lbjlincoln-nomos-rag-engine.hf.space/webhook/rag-multi-index-v3" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is retrieval-augmented generation?", "tenant_id": "benchmark"}'

# Test Graph
curl -s -X POST "https://lbjlincoln-nomos-rag-engine.hf.space/webhook/ff622742-6d71-4e91-af71-b5c666088717" \
  -H "Content-Type: application/json" \
  -d '{"question": "What entities are related to deep learning?", "tenant_id": "benchmark"}'

# Test Quantitative
curl -s -X POST "https://lbjlincoln-nomos-rag-engine.hf.space/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9" \
  -H "Content-Type: application/json" \
  -d '{"question": "How many companies are in the BTP sector?", "tenant_id": "benchmark"}'
```

### Step 7: Document the Fix

Record what happened for future reference:

```json
{
  "fix_id": "FIX-XXX",
  "timestamp": "2026-03-08T12:00:00Z",
  "pipeline": "standard",
  "symptom": "Description of what was observed",
  "root_cause": "What actually caused it",
  "fix_applied": "What was changed",
  "verified": true,
  "regressions": false
}
```

---

## Iron Rules (Never Violate)

These rules come from 76+ debugging sessions. Violating any of them causes cascading failures:

1. **1 fix per iteration** — Never change multiple things at once
2. **Test before sync** — Run 5-question smoke test before syncing workflows
3. **3+ regressions = REVERT** — If fixing one thing breaks three others, undo everything
4. **Read playbook before debugging** — Always check known fixes before investigating
5. **Never type webhook paths from memory** — Always copy from documentation
6. **PATCH not PUT** for n8n API — PUT returns 404 on HF Space
7. **Cookie auth for n8n** — API key is unreliable, use `/rest/login` with cookie jar
8. **Check for duplicate workflows** — Multiple active workflows can intercept webhooks
9. **Disabled nodes still fire HTTP requests** — Data passes through but side effects still happen
10. **Port 5432 for Supabase** — Port 6543 (transaction pooler) silently drops inserts

---

## Endpoint Reference

| Pipeline | Webhook URL | Workflow ID |
|----------|------------|-------------|
| Standard | `https://lbjlincoln-nomos-rag-engine.hf.space/webhook/rag-multi-index-v3` | `TmgyRP20N4JFd9CB` |
| Graph | `https://lbjlincoln-nomos-rag-engine.hf.space/webhook/ff622742-6d71-4e91-af71-b5c666088717` | `6257AfT1l4FMC6lY` |
| Quantitative | `https://lbjlincoln-nomos-rag-engine.hf.space/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9` | `cjhEhVs0KV1ExHqX` |
| n8n Health | `https://lbjlincoln-nomos-rag-engine.hf.space/healthz` | — |

---

## Full Access

The free tier gives you the diagnostic flowcharts and top 12 fix patterns above. The full Debug Playbook includes:

- **90+ documented fixes** (FIX-01 through FIX-90) with exact steps
- **Recurring pattern analysis** across 76+ sessions
- **Anti-patterns catalog** (things that look like fixes but cause regressions)
- **LLM model behavior guide** (which models fail on which query types)
- **Database schema reference** (Pinecone namespaces, Neo4j labels, Supabase tables)
- **Infrastructure performance baselines** (expected latencies, batch sizes, concurrency limits)
- **Self-healing automation scripts** (detect, diagnose, fix, verify in a single command)

Purchase the **RAG Debug Playbook** ($47):
https://buy.stripe.com/00w7sEd1U2v14j92FT5J600

Or get the **MEGA BUNDLE** with all 13 products ($497):
https://buy.stripe.com/6oU7sEaTM3z59Dtdkx5J60d

---

## Technical Specs

```yaml
documented_fixes: 90+
debugging_sessions: 76+
error_patterns: 12 major categories
severity_levels: 5 (P0-P4)
pipelines_covered: 3 (Standard, Graph, Quantitative)
infrastructure: n8n on HF Spaces, Pinecone, Neo4j Aura, Supabase
self_healing_pattern: detect -> diagnose -> classify -> auto-fix -> verify -> document
avg_diagnosis_time: 2-5 minutes (with playbook)
avg_fix_time: 5-15 minutes (for documented patterns)
```
