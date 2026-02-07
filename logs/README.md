# Logs Directory

Structured execution logs, error traces, and database snapshots from RAG pipeline evaluations.

## Structure

```
logs/
  executions/          # Per-execution JSONL files (one line per question)
    exec-2026-02-07T10-00-00.jsonl
    exec-2026-02-08T14-30-00.jsonl
  errors/              # Isolated error traces with full payloads
    err-2026-02-07-orch-42-timeout.json
    err-2026-02-07-graph-15-entity-miss.json
  db-snapshots/        # Periodic database state snapshots
    snapshot-2026-02-07T10-00-00.json
    snapshot-2026-02-08T14-30-00.json
```

## Execution Log Schema (JSONL)

Each line in an execution log is a JSON object:

```json
{
  "timestamp": "2026-02-07T10:15:30.123Z",
  "question_id": "graph-15",
  "rag_type": "graph",
  "question": "What is the connection between Fleming and COVID-19?",
  "expected": "Fleming -> Penicillin -> Vaccination -> COVID-19",

  "input": {
    "query": "What is the connection between Fleming and COVID-19?",
    "tenant_id": "benchmark",
    "top_k": 10
  },

  "output": {
    "raw_response": { ... },
    "extracted_answer": "Fleming discovered penicillin...",
    "confidence": 0.75,
    "engine": "GRAPH",
    "sources_count": 5
  },

  "pipeline_details": {
    "entities_extracted": ["Fleming", "COVID-19"],
    "neo4j_paths_found": 3,
    "traversal_depth": 2,
    "reranker_used": true,
    "community_summaries_matched": 1
  },

  "evaluation": {
    "correct": true,
    "method": "ENTITY_MATCH",
    "f1": 0.45,
    "detail": "3/4 entities matched"
  },

  "performance": {
    "total_latency_ms": 4200,
    "http_status": 200,
    "response_size_bytes": 1523,
    "cost_usd": 0.00030
  },

  "error": null
}
```

## Error Trace Schema

```json
{
  "error_id": "err-2026-02-07-orch-42-timeout",
  "timestamp": "2026-02-07T10:20:45.000Z",
  "question_id": "orch-42",
  "rag_type": "orchestrator",
  "error_type": "TIMEOUT",
  "error_message": "URLError: <urlopen error timed out>",
  "http_status": null,

  "input_payload": {
    "query": "...",
    "tenant_id": "benchmark"
  },

  "partial_response": null,
  "stack_trace": "...",

  "context": {
    "attempt": 4,
    "total_wait_time_ms": 30000,
    "previous_attempts": [...]
  }
}
```

## DB Snapshot Schema

```json
{
  "snapshot_id": "snap-2026-02-07T10-00-00",
  "timestamp": "2026-02-07T10:00:00Z",
  "trigger": "pre-eval|post-eval|manual|enrichment",

  "pinecone": {
    "total_vectors": 10411,
    "namespaces": { "benchmark-asqa": 948, ... }
  },

  "neo4j": {
    "total_nodes": 110,
    "total_relationships": 151,
    "labels": { "Person": 41, ... },
    "relationship_types": { "CONNECTE": 93, ... }
  },

  "supabase": {
    "tables": { "financials": 24, ... },
    "total_rows": 88
  }
}
```

## Usage

Logs are written automatically by `benchmark-workflows/live-results-writer.py`.
Error traces are created for any question with `error != null`.
DB snapshots are taken before/after each evaluation run.

To view recent errors:
```bash
ls -la logs/errors/ | tail -20
cat logs/errors/err-*.json | python -m json.tool
```

To analyze execution patterns:
```bash
cat logs/executions/exec-*.jsonl | python -c "
import sys, json
for line in sys.stdin:
    d = json.loads(line)
    if d.get('error'):
        print(f'{d[\"question_id\"]} | {d[\"error\"][\"type\"]} | {d[\"error\"][\"message\"][:80]}')
"
```
