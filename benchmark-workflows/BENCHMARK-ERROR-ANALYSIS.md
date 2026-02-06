# Benchmark Error Analysis — 28,053 Results

## Executive Summary

**100% of benchmark results failed** with the same error: `fetch is not defined`

- Total results: 28,053
- With actual answer: 0 (0%)
- With error: 28,053 (100%)
- Error: `fetch is not defined` — every single entry

## Root Cause

The **"Execute RAG Queries"** node in `WF-Benchmark-RAG-Tester.json` uses JavaScript `fetch()` to call RAG workflow endpoints:

```javascript
// Line causing the error (Execute RAG Queries node)
const response = await fetch(endpoint, {
  method: 'POST',
  headers: { ... },
  body: JSON.stringify({ query: item.question, ... })
});
```

**Problem**: n8n's Code node runs in a **sandboxed VM2 environment** that does NOT expose the global `fetch()` API. This is a known n8n limitation — Code nodes cannot make HTTP requests via `fetch()`, `XMLHttpRequest`, or `require('http')`.

## Available Alternatives in n8n Code Nodes

| Method | Available | Notes |
|--------|-----------|-------|
| `fetch()` | NO | Not in sandbox |
| `require('http')` | NO | No require in sandbox |
| `axios` | NO | Not bundled |
| `$http.request()` | **YES** | n8n built-in helper, available in Code nodes |
| HTTP Request node | **YES** | Native n8n node, most reliable |

## Fix Strategy

### Option A: Replace `fetch()` with `$http.request()` in the Code node (Minimal change)

Replace the fetch call with n8n's built-in `$http.request()`:

```javascript
const response = await this.helpers.httpRequest({
  method: 'POST',
  url: endpoint,
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${$vars.N8N_API_KEY || ''}`
  },
  body: {
    query: item.question,
    tenant_id: batch.tenant_id,
    namespace: `benchmark-${batch.dataset_name}`,
    top_k: 10,
    include_sources: true,
    benchmark_mode: true
  },
  timeout: 30000,
  returnFullResponse: false
});
```

### Option B: Split the workflow — add HTTP Request node (Recommended)

Replace the single "Execute RAG Queries" Code node with:
1. **"Prepare RAG Request"** (Code node) — builds the request payload per item
2. **"Call RAG Endpoint"** (HTTP Request node) — makes the actual HTTP call
3. **"Collect RAG Response"** (Code node) — parses response and adds to results

This is more robust because the HTTP Request node handles retries, timeouts, and auth natively.

## Affected Workflows

| Workflow | Node | Uses fetch() | Fix needed |
|----------|------|-------------|------------|
| WF-Benchmark-RAG-Tester.json | Execute RAG Queries | YES | **YES** |
| WF-Benchmark-Orchestrator-Tester.json | Execute Orchestrator Queries | YES | YES |
| All other workflows | — | No | No |

## Error Distribution by RAG Type

| RAG Type | Results | Errors |
|----------|---------|--------|
| standard | 5,395 | 5,395 |
| graph | 10,539 | 10,539 |
| quantitative | 11,584 | 11,584 |
| unknown | 535 | 535 |

## Error Distribution by Dataset

| Dataset | Results | All errors |
|---------|---------|-----------|
| hotpotqa | 3,320 | 3,320 |
| msmarco | 5,250 | 5,250 |
| triviaqa | 3,250 | 3,250 |
| asqa | 2,750 | 2,750 |
| finqa | 2,830 | 2,830 |
| narrativeqa | 2,750 | 2,750 |
| popqa | 2,250 | 2,250 |
| squad_v2 | 2,370 | 2,370 |
| pubmedqa | 1,340 | 1,340 |
| frames | 1,943 | 1,943 |

## Next Steps

1. Apply the fix to `WF-Benchmark-RAG-Tester.json` (replace fetch with $http.request)
2. Apply the same fix to `WF-Benchmark-Orchestrator-Tester.json`
3. Deploy corrected workflows to n8n cloud
4. Run validation test (10 questions per RAG type = 30 questions)
5. If successful, re-run full benchmark
