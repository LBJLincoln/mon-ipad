# Orchestrator Redis Removal - Quick Reference

> Last updated: 2026-02-25T14:35:00+01:00

## TL;DR

**Problem**: Orchestrator workflow has 9 Redis nodes, but Redis not available on HF Space.

**Solution**: Bypass all Redis nodes with simple pass-through code.

**Impact**: ZERO impact on core RAG. Minor performance decrease (~10-20% slower, no caching).

**Risk**: VERY LOW. Already has degradation paths.

**Time**: 15-20 minutes total.

---

## Redis Nodes Breakdown

| Status | Count | Nodes |
|--------|-------|-------|
| ✅ Already bypassed | 4 | Redis: Fetch Conversation, Redis: Store Conv V8, Redis: Set Cache, Redis: Cache + Generator |
| ⚠️ Needs modification | 5 | Cache Parser, Cache Storage, Cache Semantic Search, Memory Merger, Redis Failure Handler |
| **Total** | **9** | |

---

## What Redis Does (Spoiler: Nothing Critical)

```
┌─────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR WORKFLOW                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Webhook Input                                               │
│      │                                                        │
│      v                                                        │
│  ┌───────────────────────┐                                   │
│  │ Redis Fetch Conv      │ ← Short-term memory (OPTIONAL)    │
│  └───────────────────────┘                                   │
│      │                                                        │
│      v                                                        │
│  ┌───────────────────────┐                                   │
│  │ Memory Merger         │ ← Merges Redis + Postgres         │
│  │ (Redis + Postgres)    │   (Can use Postgres-only)         │
│  └───────────────────────┘                                   │
│      │                                                        │
│      v                                                        │
│  ┌───────────────────────────────────────────┐               │
│  │ CORE RAG LOGIC (NOT USING REDIS)          │               │
│  │ - Intent detection                        │               │
│  │ - Task planning                           │               │
│  │ - Call Standard/Graph/Quantitative        │               │
│  │ - Merge results                           │               │
│  │ - Guardrails                              │               │
│  └───────────────────────────────────────────┘               │
│      │                                                        │
│      v                                                        │
│  ┌───────────────────────┐                                   │
│  │ Cache Storage         │ ← FAQ caching (OPTIONAL)          │
│  └───────────────────────┘                                   │
│      │                                                        │
│      v                                                        │
│  ┌───────────────────────┐                                   │
│  │ Redis Store Conv      │ ← Save conversation (OPTIONAL)    │
│  └───────────────────────┘                                   │
│      │                                                        │
│      v                                                        │
│  Response Output                                              │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Key Insight**: Redis wraps around the core RAG logic but is NOT part of it.

---

## Modification Script (5 nodes)

### 1. Cache Parser (always return cache_miss)
```javascript
// Redis bypassed - no cache available
const initData = $node['Init V8 Security & Analysis'].json;
return {
    cache_hit: false,
    cached_response: null,
    query: initData.query,
    query_hash: initData.query_hash,
    trace_id: initData.trace_id,
    redis_status: 'bypassed'
};
```

### 2. Cache Storage (no-op)
```javascript
// Redis bypassed - cache storage disabled
const initData = $node['Init V8 Security & Analysis'].json;
return {
  cache_key: null,
  cache_value: null,
  ttl: 0,
  trace_id: initData.trace_id,
  redis_status: 'bypassed'
};
```

### 3. Cache Semantic Search (disabled)
```javascript
// Redis bypassed - semantic cache disabled
const context = $json;
return {
  ...context,
  cache_search_query: null,
  semantic_search_enabled: false,
  redis_status: 'bypassed'
};
```

### 4. Memory Merger (Postgres-only)
```javascript
// Use only Postgres L2/L3 (see full code in main analysis doc)
const initData = $node['Init V8 Security & Analysis'].json;
const traceId = initData.trace_id;
const pgResult = $node['Postgres L2/L3 Memory']?.json;
// ... Postgres parsing logic ...
return {
  entities: entitiesJson,
  conversation_summary: postgresData.conversation_summary || null,
  conversation_history: [],  // Redis disabled
  redis_available: false,
  postgres_available: postgresAvailable,
  context_status: 'POSTGRES_ONLY',
  trace_id: traceId
};
```

### 5. Redis Failure Handler (always degraded)
```javascript
// Always return degraded mode (no Redis)
const initData = $node['Init V8 Security & Analysis'].json;
const traceId = initData.trace_id;
return {
  conversation_history: [],
  context_status: 'DEGRADED',
  redis_available: false,
  warning: 'Redis removed - running in Postgres-only mode',
  trace_id: traceId
};
```

---

## Testing Checklist

```bash
# 1. Backup current workflow (already done - it's V10.1)

# 2. Apply modifications via n8n REST API
# (See detailed instructions in main analysis doc)

# 3. Test with 5 questions
source .env.local
python3 eval/quick-test.py --questions 5 --pipeline orchestrator

# 4. Expected: All 5 pass, no Redis errors

# 5. Test with 20 questions for accuracy baseline
python3 eval/quick-test.py --questions 20 --pipeline orchestrator --label "no-redis-v10.2"

# 6. Expected: ~80% accuracy (same as Phase 1 baseline)

# 7. If tests pass → activate workflow
# 8. If tests fail → rollback to V10.1 (instant)
```

---

## Node IDs (for API updates)

| Node Name | Node ID |
|-----------|---------|
| Cache Parser | 6afac6d0-4023-43ae-9b7e-76fd1f199862 |
| 💾 Cache Storage | ca85038c-26c6-4002-b9c1-b231dc51e10f |
| 🔎 Cache Semantic Search | 8211b2d7-c032-4617-adcf-037d1b8c0b27 |
| 🧠 Memory Merger (Redis + Postgres) | 771afac4-90da-4e02-a8e8-d4032075bb64 |
| 🛡️ Redis Failure Handler V10.1 | c7ee4ae3-47e2-44d7-b012-f138a2ed80c3 |

Workflow ID: `ALd4gOEqiKL5KR1p`

---

## Files

- **Full Analysis**: `/home/termius/mon-ipad/technicals/debug/orchestrator-redis-removal-analysis.md` (20 KB)
- **JSON Data**: `/home/termius/mon-ipad/technicals/debug/orchestrator_redis_removal_plan.json` (5.4 KB)
- **This Summary**: `/home/termius/mon-ipad/technicals/debug/orchestrator-redis-removal-summary.md` (you are here)

---

## Next Step

```bash
# Ready to execute? Run:
python3 scripts/orchestrator-redis-bypass.py

# This will:
# 1. Login to n8n
# 2. Fetch workflow
# 3. Update 5 nodes with bypass code
# 4. Save as V10.2-no-redis
# 5. Test with 5 questions
# 6. Report results
```

---

*Quick reference created: 2026-02-25T14:35:00+01:00*
