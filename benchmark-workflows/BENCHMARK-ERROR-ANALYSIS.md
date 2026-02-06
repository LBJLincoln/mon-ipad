# Benchmark Error Analysis — 28,053 Results

## Executive Summary

**100% of benchmark results failed** with the same root error: `fetch is not defined`

- Total results: 28,053
- With actual answer: 0 (0%)
- With error: 28,053 (100%)

After investigation, **4 distinct problems** were identified and fixed:

| # | Problem | Fix | Status |
|---|---------|-----|--------|
| 1 | `fetch()` not available in n8n Code node sandbox | Replaced with `this.helpers.httpRequest()` | FIXED |
| 2 | RAG endpoint URLs were wrong (`/rag-v6-*` vs actual paths) | Updated to real webhook paths | FIXED |
| 3 | Graph/Quant RAG webhooks returned immediately (no answer) | Added `respondToWebhook` nodes, set `responseMode: responseNode` | FIXED |
| 4 | n8n Code node 60s timeout with batch_size=10 | Reduced batch_size to 2 | FIXED |
| 5 | Graph RAG response format not handled (nested dict) | Added multi-format answer extraction | FIXED |
| 6 | JS truthy bug: `[].length` check instead of `[] || fallback` | Fixed array emptiness checks | FIXED |

## Diagnostic Test Results (30 questions)

After all fixes:

| RAG Type | Questions | With Answers | Errors | Status |
|----------|-----------|-------------|--------|--------|
| Standard | 10 | 10 (100%) | 0 | WORKING |
| Graph | 10 | 10 (100%) | 0 | WORKING |
| Quantitative | 10 | 0 (0%) | 0 | BY DESIGN* |

*Quantitative RAG is a Text-to-SQL system. It correctly rejects general knowledge questions (squad_v2). It needs financial/tabular data questions (finqa dataset) to produce answers.

## Root Cause #1: `fetch is not defined`

The **"Execute RAG Queries"** node in `WF-Benchmark-RAG-Tester.json` used JavaScript `fetch()`:

```javascript
// BROKEN: fetch() is NOT available in n8n Code node sandbox
const response = await fetch(endpoint, { method: 'POST', ... });
```

n8n's Code node runs in a **sandboxed VM** that does NOT expose `fetch()`, `XMLHttpRequest`, or `require('http')`.

**Fix**: Replaced with `this.helpers.httpRequest()`:

```javascript
// FIXED: uses n8n's built-in HTTP helper
const data = await this.helpers.httpRequest({
  method: 'POST',
  url: endpoint,
  body: { query: item.question, ... },
  timeout: 30000,
  json: true
});
```

## Root Cause #2: Wrong RAG Endpoint URLs

The benchmark tester's `Init Test Session` mapped RAG types to non-existent endpoints:

| RAG Type | Was (404) | Should Be |
|----------|-----------|-----------|
| standard | `/webhook/rag-v6-query` | `/webhook/rag-multi-index-v3` |
| graph | `/webhook/rag-v6-graph-query` | `/webhook/ff622742-6d71-4e91-af71-b5c666088717` |
| quantitative | `/webhook/rag-v6-quantitative-query` | `/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9` |

## Root Cause #3: Graph/Quant Webhooks Returned Immediately

The Graph RAG and Quantitative RAG workflows had their webhook in `onReceived` mode (default), which returns `{"message": "Workflow was started"}` immediately without waiting for the workflow to complete.

**Fix**: Set `responseMode: responseNode` and added `respondToWebhook` nodes after Response Formatter.

## Root Cause #4: Code Node Timeout

n8n Code nodes have a 60-second execution timeout. Processing 10 questions sequentially (each taking 6-15 seconds) exceeded this limit.

**Fix**: Reduced batch_size from 10 to 2.

## Root Cause #5: Response Format Mismatch

Each RAG type returns a different response format:

| RAG Type | Response Format |
|----------|----------------|
| Standard | `{ response: "string answer", sources: [...] }` |
| Graph | `[{ status, response: { budgeted_context: { vector: [...] } } }]` |
| Quantitative | `[{ answer, interpretation, sql_result }]` |

**Fix**: Added multi-format answer extraction logic that handles all three formats.

## Root Cause #6: JavaScript Truthy Bug

```javascript
// BUG: empty array [] is truthy in JS!
const docs = ctx.reranked || ctx.vector || ctx.graph || [];
// Always returns ctx.reranked even when it's []

// FIX: check .length explicitly
const docs = reranked.length ? reranked : (vector.length ? vector : graph);
```

## Files Modified

| File | Change |
|------|--------|
| `WF-Benchmark-RAG-Tester.json` | fetch->httpRequest, endpoint URLs, answer extraction |
| `WF-Benchmark-Orchestrator-Tester.json` | fetch->httpRequest |
| `run-diagnostic-30q.py` | New diagnostic test script |
| Graph RAG workflow (on n8n) | Added respondToWebhook, OTEL error handling |
| Quantitative RAG workflow (on n8n) | Added respondToWebhook, SQL error handling |

## Re-running the Full Benchmark

To re-run with the fixes:
1. Workflows already deployed to n8n cloud
2. Use `batch_size=2` to avoid Code node timeouts
3. Quantitative RAG should use `finqa` dataset for meaningful results
4. Standard/Graph RAG work with all datasets
