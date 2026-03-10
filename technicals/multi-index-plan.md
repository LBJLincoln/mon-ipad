# Multi-Index Query Plan for Standard Pipeline V3.5

> Created: 2026-03-10
> Status: PLAN ONLY — do NOT modify workflow JSON until approved

---

## 1. Current Architecture (Standard RAG V3.4)

The Standard pipeline currently queries **one Pinecone index** (`website-sectors-jina-1024`) via two parallel branches, plus one BM25 branch:

```
                              ┌─ HyDE Generator → HyDE Embedding → HTTP Pinecone Query HyDE ──────┐
                              │                                                                      │
Init → Needs Decomposition? ──┤─ Original Embedding → HTTP Pinecone Query Original ─────────────────┼→ Wait All Branches → RRF Merge
                              │                                                                      │
                              └─ BM25 Search Postgres ──────────────────────────────────────────────┘
```

**Key details**:
- Both Pinecone query nodes POST to: `https://website-sectors-jina-1024-a4mkzmz.svc.aped-4627-b74a.pinecone.io/query`
- They use the **standard `/query` endpoint** with pre-computed vectors from self-hosted Jina embeddings
- Body format: `{"vector": [...], "topK": N, "includeMetadata": true, "namespace": "sectors"}`
- HyDE branch embeds a hypothetical answer; Original branch embeds the raw query
- Both send 1024-dim Jina vectors
- Results merge in `Wait All Branches` (n8n Merge node, combineAll mode, 2 inputs: index 0 + index 1)
- `RRF Merge & Rank V3.4` reads from named nodes: `HTTP Pinecone Query HyDE`, `HTTP Pinecone Query Original`, `BM25 Search Postgres`

### Wait All Branches Input Mapping
- **Input 0**: `HTTP Pinecone Query HyDE`
- **Input 1**: `HTTP Pinecone Query Original` AND `BM25 Search Postgres` (both connect to index 1)

---

## 2. Second Index: `sectors-e5-multilingual`

| Property | Value |
|----------|-------|
| Index name | `sectors-e5-multilingual` |
| Host | `https://sectors-e5-multilingual-a4mkzmz.svc.aped-4627-b74a.pinecone.io` |
| Namespace | `sectors` |
| Embedding model | `multilingual-e5-large` (1024 dims, **integrated** into Pinecone) |
| Query endpoint | `/records/namespaces/sectors/query` (integrated inference) |
| Query format | `{"query": {"inputs": {"text": "..."}, "topK": 10}}` |
| Ingest script | `ops/ingest-integrated.py` |

**Critical difference**: This index uses **integrated embedding** (Pinecone generates embeddings server-side). We do NOT send pre-computed vectors. We send raw text and Pinecone embeds it using `multilingual-e5-large`.

**Why this helps**:
- `multilingual-e5-large` is natively strong on French text (trained on multilingual data)
- Jina v3 is also multilingual but has different coverage; combining both gives diversity
- Two different embedding models = different semantic representations = better recall via RRF fusion

---

## 3. Proposed Architecture (V3.5)

```
                              ┌─ HyDE Generator → HyDE Embedding → HTTP Pinecone Query HyDE (Jina) ──────┐
                              │                                                                              │
                              ├─ Original Embedding → HTTP Pinecone Query Original (Jina) ────────────────┤
                              │                                                                              │
Init → Needs Decomposition? ──┤─ BM25 Search Postgres ──────────────────────────────────────────────────────┼→ Wait All Branches → RRF Merge V3.5
                              │                                                                              │
                              ├─ HTTP E5 Query Original (integrated) ───────────────────────────────────────┤
                              │                                                                              │
                              └─ HTTP E5 Query HyDE Text (integrated) ──────────────────────────────────────┘
```

We add **2 new query nodes** that query the E5 index with integrated inference. Total retrieval sources: **5** (was 3).

---

## 4. Nodes to Add

### Node A: `HTTP E5 Query Original`

**Purpose**: Query `sectors-e5-multilingual` with the original raw query text (no pre-embedding needed).

```json
{
  "parameters": {
    "method": "POST",
    "url": "https://sectors-e5-multilingual-a4mkzmz.svc.aped-4627-b74a.pinecone.io/records/namespaces/sectors/query",
    "authentication": "none",
    "sendBody": true,
    "specifyBody": "json",
    "jsonBody": "={\n  \"query\": {\n    \"inputs\": {\n      \"text\": {{ JSON.stringify($node['Init & ACL Pre-Filter V3.4'].json.query || '') }}\n    },\n    \"topK\": {{ Math.min($node['Init & ACL Pre-Filter V3.4'].json.topK || 15, 30) }}\n  }\n}",
    "options": {
      "batching": { "batch": { "batchSize": 1 } },
      "timeout": 30000,
      "retry": { "maxTries": 3, "waitBetweenTries": 3000 }
    },
    "sendHeaders": true,
    "headerParameters": {
      "parameters": [
        { "name": "Api-Key", "value": "={{$env.PINECONE_API_KEY}}" },
        { "name": "Content-Type", "value": "application/json" }
      ]
    }
  },
  "id": "<new-uuid>",
  "name": "HTTP E5 Query Original",
  "type": "n8n-nodes-base.httpRequest",
  "typeVersion": 4.3,
  "position": [3392, 3700],
  "onError": "continueRegularOutput",
  "retryOnFail": true,
  "maxTries": 3,
  "waitBetweenTries": 3000
}
```

**Connection**: `Needs Decomposition?` output[1] (false/no-decomposition) and `Query Merger V3.4` both connect to this node (same as Original Embedding).

### Node B: `HTTP E5 Query HyDE Text`

**Purpose**: Query `sectors-e5-multilingual` with the HyDE-generated hypothetical document text.

```json
{
  "parameters": {
    "method": "POST",
    "url": "https://sectors-e5-multilingual-a4mkzmz.svc.aped-4627-b74a.pinecone.io/records/namespaces/sectors/query",
    "authentication": "none",
    "sendBody": true,
    "specifyBody": "json",
    "jsonBody": "={\n  \"query\": {\n    \"inputs\": {\n      \"text\": {{ JSON.stringify($node['HyDE Generator'].json.choices?.[0]?.message?.content || $node['Init & ACL Pre-Filter V3.4'].json.query || '') }}\n    },\n    \"topK\": {{ Math.min($node['Init & ACL Pre-Filter V3.4'].json.topK || 15, 30) }}\n  }\n}",
    "options": {
      "batching": { "batch": { "batchSize": 1 } },
      "timeout": 30000,
      "retry": { "maxTries": 3, "waitBetweenTries": 3000 }
    },
    "sendHeaders": true,
    "headerParameters": {
      "parameters": [
        { "name": "Api-Key", "value": "={{$env.PINECONE_API_KEY}}" },
        { "name": "Content-Type", "value": "application/json" }
      ]
    }
  },
  "id": "<new-uuid>",
  "name": "HTTP E5 Query HyDE Text",
  "type": "n8n-nodes-base.httpRequest",
  "typeVersion": 4.3,
  "position": [3936, 2240],
  "onError": "continueRegularOutput",
  "retryOnFail": true,
  "maxTries": 3,
  "waitBetweenTries": 3000
}
```

**Connection**: `HyDE Generator` output connects to both `HyDE Embedding` (existing) AND `HTTP E5 Query HyDE Text` (new).

---

## 5. Nodes to Modify

### 5.1 Wait All Branches (Merge node)

Currently has **2 inputs** (index 0 and index 1). We need to either:

**Option A (recommended): Remove the Merge node entirely.** The RRF Merge code already reads from named nodes directly using `$node['HTTP Pinecone Query HyDE'].json` etc. The Merge node is redundant. The RRF node just needs connections from all 5 sources, and it reads them by name.

**Option B: Expand Merge to 5 inputs.** n8n Merge v3.1 `combineAll` mode can handle multiple inputs but the JSON config for extra inputs is complex.

**Recommendation**: Option A. Remove `Wait All Branches` from the flow. Connect all 5 source nodes directly to `RRF Merge & Rank V3.5`. The Code node already reads by name, not by input position.

### 5.2 RRF Merge & Rank V3.4 → V3.5

The RRF code currently reads 3 sources by name. We add 2 more sources.

**Changes to the jsCode**:

```javascript
// Add after BOOSTS definition:
const BOOSTS = { hyde: 1.5, bm25: 1.2, pinecone: 1.0, e5_original: 1.3, e5_hyde: 1.4 };

// === SOURCE 4: E5 Original (integrated inference) ===
console.log(`[${traceId}] Reading E5 Original results...`);
try {
  const e5Data = safeReadNode('HTTP E5 Query Original');
  // Integrated inference returns: { result: { hits: [...] } } or { matches: [...] }
  const e5Hits = e5Data?.result?.hits || e5Data?.matches || [];

  if (e5Hits.length > 0) {
    sourcesAvailable++;
    e5Hits.forEach((item, index) => {
      const id = item._id || item.id;
      const rrfScore = (1 / (k + index + 1)) * BOOSTS.e5_original;

      if (scores[id]) {
        scores[id].score += rrfScore;
        if (!scores[id].sources.includes('e5_original')) {
          scores[id].sources.push('e5_original');
        }
      } else {
        scores[id] = {
          score: rrfScore,
          data: item._metadata || item.metadata || {},
          pineconeScore: item._score || item.score,
          sources: ['e5_original']
        };
      }
    });
    console.log(`[${traceId}] E5 Original: ${e5Hits.length} results added`);
  } else {
    warnings.push('E5 Original: 0 results');
  }
} catch(e) {
  warnings.push('E5 Original error: ' + e.message);
  console.error(`[${traceId}] E5 Original error:`, e.message);
}

// === SOURCE 5: E5 HyDE Text (integrated inference) ===
console.log(`[${traceId}] Reading E5 HyDE results...`);
try {
  const e5HydeData = safeReadNode('HTTP E5 Query HyDE Text');
  const e5HydeHits = e5HydeData?.result?.hits || e5HydeData?.matches || [];

  if (e5HydeHits.length > 0) {
    sourcesAvailable++;
    e5HydeHits.forEach((item, index) => {
      const id = item._id || item.id;
      const rrfScore = (1 / (k + index + 1)) * BOOSTS.e5_hyde * decompositionBoost;

      if (scores[id]) {
        scores[id].score += rrfScore;
        if (!scores[id].sources.includes('e5_hyde')) {
          scores[id].sources.push('e5_hyde');
        }
      } else {
        scores[id] = {
          score: rrfScore,
          data: item._metadata || item.metadata || {},
          pineconeScore: item._score || item.score,
          sources: ['e5_hyde']
        };
      }
    });
    console.log(`[${traceId}] E5 HyDE: ${e5HydeHits.length} results added`);
  } else {
    warnings.push('E5 HyDE: 0 results');
  }
} catch(e) {
  warnings.push('E5 HyDE error: ' + e.message);
  console.error(`[${traceId}] E5 HyDE error:`, e.message);
}
```

Also update version string: `version: '3.5.0'`

### 5.3 extractContent helper

The E5 integrated inference response format stores text differently. Update the helper:

```javascript
function extractContent(metadata) {
  return metadata?.text || metadata?.content || metadata?.chunk_text
    || metadata?.page_content || metadata?.passage || '';
}
```

---

## 6. Connection Changes

### New connections to ADD:

```json
"Needs Decomposition?": {
  "main": [
    [...],  // output 0 (decompose=true) - unchanged
    [
      // output 1 (decompose=false) - ADD new nodes
      { "node": "HyDE Generator", "type": "main", "index": 0 },
      { "node": "Original Embedding", "type": "main", "index": 0 },
      { "node": "BM25 Search Postgres", "type": "main", "index": 0 },
      { "node": "HTTP E5 Query Original", "type": "main", "index": 0 },  // NEW
    ]
  ]
},
"Query Merger V3.4": {
  "main": [
    [
      { "node": "HyDE Generator", "type": "main", "index": 0 },
      { "node": "Original Embedding", "type": "main", "index": 0 },
      { "node": "BM25 Search Postgres", "type": "main", "index": 0 },
      { "node": "HTTP E5 Query Original", "type": "main", "index": 0 },  // NEW
    ]
  ]
},
"HyDE Generator": {
  "main": [
    [
      { "node": "HyDE Embedding", "type": "main", "index": 0 },
      { "node": "HTTP E5 Query HyDE Text", "type": "main", "index": 0 }  // NEW
    ]
  ]
},
// NEW: E5 nodes connect to RRF (or to Wait All Branches if we keep it)
"HTTP E5 Query Original": {
  "main": [
    [{ "node": "RRF Merge & Rank V3.4", "type": "main", "index": 0 }]
  ]
},
"HTTP E5 Query HyDE Text": {
  "main": [
    [{ "node": "RRF Merge & Rank V3.4", "type": "main", "index": 0 }]
  ]
}
```

### Connections to KEEP unchanged:
- `HyDE Embedding` → `HTTP Pinecone Query HyDE` → `Wait All Branches` (or directly to RRF)
- `Original Embedding` → `HTTP Pinecone Query Original` → `Wait All Branches` (or directly to RRF)
- `BM25 Search Postgres` → `Wait All Branches` (or directly to RRF)

---

## 7. Response Format Differences

### Jina index (`/query` endpoint) returns:
```json
{
  "matches": [
    {
      "id": "doc-123",
      "score": 0.87,
      "metadata": {
        "text": "...",
        "source": "...",
        "sector": "finance"
      }
    }
  ]
}
```

### E5 integrated index (`/records/namespaces/{ns}/query`) returns:
```json
{
  "result": {
    "hits": [
      {
        "_id": "doc-456",
        "_score": 0.82,
        "_metadata": {
          "text": "...",
          "source": "...",
          "sector": "juridique"
        }
      }
    ]
  }
}
```

The RRF code must handle BOTH formats. The updated code above uses:
- `item._id || item.id` for document ID
- `item._score || item.score` for relevance score
- `item._metadata || item.metadata` for metadata

---

## 8. RRF Boost Rationale

| Source | Boost | Rationale |
|--------|-------|-----------|
| `hyde` (Jina) | 1.5 | HyDE + Jina = best semantic match for domain text |
| `e5_hyde` (E5) | 1.4 | HyDE + E5 = strong multilingual hypothesis match |
| `e5_original` (E5) | 1.3 | E5 multilingual captures FR nuances Jina may miss |
| `bm25` (Postgres) | 1.2 | Exact keyword match, critical for technical terms |
| `pinecone` (Jina original) | 1.0 | Baseline, direct query embedding |

Documents found by multiple indexes (cross-encoder agreement) will naturally score highest in RRF.

---

## 9. Prerequisites Before Implementation

1. **Verify E5 index has data**: Run `curl` or use Pinecone describe-index-stats to confirm `sectors-e5-multilingual` has vectors in `sectors` namespace
2. **Test E5 query format**: Send a test query to confirm the integrated inference response format matches what we expect
3. **Ensure Pinecone free tier allows 3 indexes**: We currently have 2/5. Adding no new index — `sectors-e5-multilingual` already exists
4. **Ingest data if needed**: If the E5 index is empty, run `ops/ingest-integrated.py` first

### Verification commands:
```bash
# Check E5 index stats
source .env.local
curl -s "https://sectors-e5-multilingual-a4mkzmz.svc.aped-4627-b74a.pinecone.io/describe-index-stats" \
  -H "Api-Key: $PINECONE_API_KEY" | python3 -m json.tool

# Test E5 query
curl -s -X POST "https://sectors-e5-multilingual-a4mkzmz.svc.aped-4627-b74a.pinecone.io/records/namespaces/sectors/query" \
  -H "Api-Key: $PINECONE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": {"inputs": {"text": "ratio de solvabilité"}, "topK": 3}}' | python3 -m json.tool
```

---

## 10. Latency Impact

Adding 2 more HTTP calls will increase total retrieval time. Mitigation:

- E5 queries run **in parallel** with Jina queries (n8n fan-out from the same If/Merger node)
- Integrated inference is fast (no external embedding call needed — saves ~500ms vs Jina self-hosted)
- Net latency increase should be **0-500ms** since all 5 queries run concurrently
- The E5 queries do NOT depend on HyDE Embedding (they send raw text), so `HTTP E5 Query Original` starts immediately (unlike `HTTP Pinecone Query Original` which waits for embedding)

### Expected latency breakdown:
| Branch | Steps | Est. Time |
|--------|-------|-----------|
| HyDE Jina | HyDE Gen (2s) → Embed (1s) → Query (1s) | ~4s |
| Original Jina | Embed (1s) → Query (1s) | ~2s |
| BM25 | Query (0.5s) | ~0.5s |
| E5 Original | Query (1s) | ~1s (NEW, parallel) |
| E5 HyDE | Wait HyDE Gen (2s) → Query (1s) | ~3s (NEW, parallel with Jina HyDE embed+query) |

Total wall-clock: ~4s (unchanged, bottleneck is still HyDE generation)

---

## 11. Rollback Plan

If multi-index degrades accuracy:
1. Disable `HTTP E5 Query Original` and `HTTP E5 Query HyDE Text` nodes (set `"disabled": true`)
2. Remove their entries from RRF code (or the `safeReadNode` will return null and they'll be skipped with a warning)
3. No other changes needed — the pipeline falls back to 3-source RRF

---

## 12. Implementation Checklist

- [ ] Verify E5 index has data (`describe-index-stats`)
- [ ] Test E5 integrated query format (send a test query, capture response shape)
- [ ] Add Node A: `HTTP E5 Query Original` to `standard.json`
- [ ] Add Node B: `HTTP E5 Query HyDE Text` to `standard.json`
- [ ] Update connections: `Needs Decomposition?`, `Query Merger V3.4`, `HyDE Generator`
- [ ] Update connections: E5 nodes → RRF (or Wait All Branches if kept)
- [ ] Update `RRF Merge & Rank V3.4` code to V3.5 with 5 sources
- [ ] Update version string to `3.5.0`
- [ ] Sync to n8n via `n8n/sync.py`
- [ ] Run smoke test: `python3 eval/quick-test.py --sector all`
- [ ] Compare before/after accuracy (20 questions)
- [ ] If regression > 5% on any sector, rollback (disable E5 nodes)
