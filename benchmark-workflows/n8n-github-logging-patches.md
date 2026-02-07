# N8N Workflow Modifications for GitHub Error Logging

Concrete patches to add to each n8n workflow so that **all errors, inputs, and outputs**
are automatically pushed to the GitHub repository for persistent monitoring.

## Strategy

Each workflow gets a **GitHub Logger** node (HTTP Request to GitHub API) that fires on
every error path. Instead of errors being lost in n8n execution history (which rotates),
they get committed as structured JSON files to `logs/errors/` in the repo.

The logging uses the **GitHub Contents API** (`PUT /repos/:owner/:repo/contents/:path`)
to create files directly from n8n without needing git on the n8n server.

---

## Shared: GitHub Logger Code Node

Add this as a reusable Code node in each workflow. It takes error data from upstream
and pushes it to GitHub.

```javascript
// Node: GitHub Error Logger
// Type: Code
// Runs after any error handler or error trigger
// Requires: GitHub Personal Access Token in n8n credentials

const errorData = $input.first().json;
const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
const questionId = errorData.question_id || errorData.trace_id || 'unknown';
const pipeline = errorData.engine || errorData.pipeline || 'unknown';
const errorType = errorData.error_type || 'UNKNOWN';

const fileName = `err-${timestamp.slice(0,10)}-${questionId}-${errorType}`.toLowerCase();
const filePath = `logs/errors/${fileName}.json`;

const logEntry = {
  error_id: fileName,
  timestamp: new Date().toISOString(),
  pipeline: pipeline,
  question_id: questionId,
  error_type: errorType,
  error_message: errorData.error || errorData.message || 'No message',

  // Full input that caused the error
  input: {
    query: errorData.query || errorData.original_query || '',
    tenant_id: errorData.tenant_id || 'benchmark',
    trace_id: errorData.trace_id || ''
  },

  // Partial output if any
  partial_response: errorData.partial_response || errorData.response || null,

  // n8n execution context
  n8n_context: {
    workflow_id: $workflow.id,
    workflow_name: $workflow.name,
    execution_id: $execution.id,
    node_name: errorData.failed_node || $node.name,
    run_index: $runIndex
  },

  // Performance data
  performance: {
    latency_ms: errorData.latency_ms || 0,
    http_status: errorData.http_status || null
  }
};

// Base64 encode the content for GitHub API
const content = Buffer.from(JSON.stringify(logEntry, null, 2)).toString('base64');

return [{
  json: {
    path: filePath,
    message: `log: ${pipeline} error on ${questionId} (${errorType})`,
    content: content,
    branch: 'main'
  }
}];
```

### GitHub API HTTP Request Node

After the Code node, add an HTTP Request node:

```
Method: PUT
URL: https://api.github.com/repos/LBJLincoln/mon-ipad/contents/{{ $json.path }}
Authentication: Header Auth
  Name: Authorization
  Value: Bearer {{ $credentials.githubToken }}
Headers:
  Accept: application/vnd.github.v3+json
  Content-Type: application/json
Body (JSON):
  {
    "message": "{{ $json.message }}",
    "content": "{{ $json.content }}",
    "branch": "{{ $json.branch }}"
  }
On Error: continueErrorOutput  (logging should never block the main flow)
```

---

## Patch 1: V10.1 Orchestrator

### Current Error Flow
```
Error Handler V8 → Error Payload V8 → Return: Error Response
```

### Patched Error Flow
```
Error Handler V8 → Error Payload V8 → GitHub Error Logger (Code) → GitHub Push (HTTP)
                                    → Return: Error Response  (parallel)
```

### Additional: Execution Summary Logger

Add after `Response Builder V9` (on both success AND failure paths):

```javascript
// Node: Execution Summary Logger (Code)
// Fires on EVERY execution, not just errors

const result = $('Response Builder V9').item.json;
const input = $('Input Merger V8').item.json;
const intent = $('Init V8 Security & Analysis').item.json;

const summary = {
  timestamp: new Date().toISOString(),
  pipeline: 'orchestrator',
  question_id: input.trace_id || '',
  query: input.query || '',

  // Routing decision
  routing: {
    intent_classification: intent.intent || intent.classification,
    sub_pipelines_invoked: intent.selected_engines || ['standard', 'graph', 'quantitative'],
    routing_confidence: intent.confidence || 0
  },

  // Sub-pipeline results
  sub_results: {
    standard: {
      success: !!$('Invoke WF5: Standard').item?.json?.response,
      latency_ms: $('Invoke WF5: Standard').item?.json?.latency_ms || 0,
      confidence: $('Invoke WF5: Standard').item?.json?.confidence || 0
    },
    graph: {
      success: !!$('Invoke WF2: Graph').item?.json?.response,
      latency_ms: $('Invoke WF2: Graph').item?.json?.latency_ms || 0,
      confidence: $('Invoke WF2: Graph').item?.json?.confidence || 0
    },
    quantitative: {
      success: !!$('Invoke WF4: Quantitative').item?.json?.response,
      latency_ms: $('Invoke WF4: Quantitative').item?.json?.latency_ms || 0,
      confidence: $('Invoke WF4: Quantitative').item?.json?.confidence || 0
    }
  },

  // Final result
  final: {
    success: result.success || false,
    response_length: (result.final_response || '').length,
    confidence: result.confidence || 0,
    selected_engine: result.selected_engine || ''
  }
};

// Write to logs/executions/ via GitHub API
const date = new Date().toISOString().slice(0,10);
const filePath = `logs/executions/orch-${date}-${input.trace_id || Date.now()}.json`;
const content = Buffer.from(JSON.stringify(summary, null, 2)).toString('base64');

return [{
  json: {
    path: filePath,
    message: `exec: orchestrator ${result.success ? 'OK' : 'FAIL'} (${input.trace_id || ''})`,
    content: content,
    branch: 'main'
  }
}];
```

### Timeout Detection Patch

Add before `Execution Engine V10`:

```javascript
// Node: Timeout Guard (Code)
// Wraps sub-workflow invocations with timeout detection

const TIMEOUT_MS = {
  standard: 8000,
  graph: 7000,
  quantitative: 5000
};

// Mark start time for each sub-pipeline
const startTimes = {};
for (const [pipeline, timeout] of Object.entries(TIMEOUT_MS)) {
  startTimes[pipeline] = {
    start: Date.now(),
    timeout: timeout,
    deadline: Date.now() + timeout
  };
}

return [{ json: { ...($input.first().json), _timeout_guards: startTimes } }];
```

---

## Patch 2: WF2 Graph RAG V3.3

### Current Error Points
- HyDE & Entity Extraction (httpRequest) → onError: continueErrorOutput
- Shield #4: Neo4j Guardian Traversal (httpRequest) → onError: continueErrorOutput
- WF3: Cohere Reranker (httpRequest) → onError: continueErrorOutput

### Patched: Entity Extraction Logger

After `Neo4j Query Builder (Deep Traversal V2)`:

```javascript
// Node: Entity Extraction Logger (Code)
// Logs what entities were extracted and whether they matched Neo4j

const builder = $input.first().json;
const entities = builder.entities || builder.parameters?.entity_names || [];
const skipNeo4j = builder.skip_neo4j || false;

const log = {
  timestamp: new Date().toISOString(),
  pipeline: 'graph',
  step: 'entity_extraction',
  query: builder.query_text || '',

  extraction: {
    entities_extracted: entities,
    entity_count: entities.length,
    skip_neo4j: skipNeo4j,
    hyde_document_preview: (builder.hyde_document || '').slice(0, 200)
  },

  neo4j_query: {
    cypher: builder.query || '',
    parameters: builder.parameters || {},
    traversal_config: builder.traversal_config || {}
  }
};

// Only log to GitHub if entity extraction failed (0 entities) or skip_neo4j
if (entities.length === 0 || skipNeo4j) {
  const filePath = `logs/errors/entity-miss-${new Date().toISOString().slice(0,10)}-${Date.now()}.json`;
  const content = Buffer.from(JSON.stringify(log, null, 2)).toString('base64');
  return [{
    json: {
      ...($input.first().json),
      _entity_log: log,
      _github_push: {
        path: filePath,
        message: `log: graph entity extraction miss (${entities.length} entities)`,
        content: content
      }
    }
  }];
}

return [{ json: { ...($input.first().json), _entity_log: log } }];
```

### Patched: Neo4j Results Logger

After `Shield #4: Neo4j Guardian Traversal`:

```javascript
// Node: Neo4j Results Logger (Code)

const neo4jResult = $input.first().json;
const pathCount = neo4jResult.results?.[0]?.data?.length || 0;

const log = {
  timestamp: new Date().toISOString(),
  pipeline: 'graph',
  step: 'neo4j_traversal',
  paths_found: pathCount,
  max_depth_used: 0,
  entities_in_paths: []
};

// Extract path details
if (neo4jResult.results?.[0]?.data) {
  const paths = neo4jResult.results[0].data;
  const allEntities = new Set();
  let maxDepth = 0;

  for (const path of paths) {
    const pathNodes = path[1] || [];
    const pathLength = path[4] || 0;
    maxDepth = Math.max(maxDepth, pathLength);
    for (const node of pathNodes) {
      if (node.name) allEntities.add(node.name);
    }
  }

  log.max_depth_used = maxDepth;
  log.entities_in_paths = Array.from(allEntities);
}

return [{ json: { ...($input.first().json), _neo4j_log: log } }];
```

---

## Patch 3: WF5 Standard RAG V3.4

### Current Error Points
- HyDE Generator (httpRequest) → onError: continueErrorOutput
- HTTP Pinecone Query (httpRequest) → onError: continueErrorOutput

### Patched: Retrieval Quality Logger

After `Merge Pinecone Results`:

```javascript
// Node: Retrieval Quality Logger (Code)

const results = $input.first().json;
const sources = results.merged_results || results.sources || [];
const topScores = sources.slice(0, 5).map(s => s.score || s.normalized_score || 0);

const log = {
  timestamp: new Date().toISOString(),
  pipeline: 'standard',
  step: 'retrieval',
  results_count: sources.length,
  top_5_scores: topScores,
  avg_score: topScores.length ? topScores.reduce((a,b) => a+b, 0) / topScores.length : 0,
  namespaces_hit: [...new Set(sources.map(s => s.namespace || ''))],
  hyde_used: !!results.hyde_results
};

// Flag low-quality retrieval
if (log.avg_score < 0.3 || sources.length < 3) {
  log.quality_flag = 'LOW';
}

return [{ json: { ...($input.first().json), _retrieval_log: log } }];
```

---

## Patch 4: WF4 Quantitative V2.0

### Current Error Points
- SQL Executor (Postgres) → onError: continueErrorOutput
- Text-to-SQL Generator → onError: continueErrorOutput

### Patched: SQL Execution Logger

After `SQL Validator (Shield #1)`:

```javascript
// Node: SQL Execution Logger (Code)

const validated = $input.first().json;

const log = {
  timestamp: new Date().toISOString(),
  pipeline: 'quantitative',
  step: 'sql_validation',
  sql: validated.validated_sql || validated.sql || '',
  validation_status: validated.validation_status || 'UNKNOWN',
  validation_error: validated.validation_error || null,
  explanation: validated.explanation || ''
};

// Log SQL injection attempts or validation failures
if (validated.validation_status === 'FAILED') {
  const filePath = `logs/errors/sql-fail-${new Date().toISOString().slice(0,10)}-${Date.now()}.json`;
  const content = Buffer.from(JSON.stringify(log, null, 2)).toString('base64');
  return [{
    json: {
      ...($input.first().json),
      _sql_log: log,
      _github_push: {
        path: filePath,
        message: `log: SQL validation failed (${validated.validation_error})`,
        content: content
      }
    }
  }];
}

return [{ json: { ...($input.first().json), _sql_log: log } }];
```

### Patched: Self-Healing Logger

After `SQL Error Handler (Self-Healing)`:

```javascript
// Node: Self-Healing Logger (Code)

const handler = $input.first().json;

if (handler.needs_repair) {
  const log = {
    timestamp: new Date().toISOString(),
    pipeline: 'quantitative',
    step: 'self_healing',
    original_sql: handler.original_sql || '',
    error_message: handler.sql_error || '',
    repair_attempt: handler.repair_attempt || 1,
    null_aggregation: handler.null_aggregation || false
  };

  const filePath = `logs/errors/sql-repair-${new Date().toISOString().slice(0,10)}-${Date.now()}.json`;
  const content = Buffer.from(JSON.stringify(log, null, 2)).toString('base64');

  return [{
    json: {
      ...($input.first().json),
      _healing_log: log,
      _github_push: {
        path: filePath,
        message: `log: SQL self-healing triggered (attempt ${handler.repair_attempt})`,
        content: content
      }
    }
  }];
}

return [{ json: $input.first().json }];
```

---

## Implementation Plan

### Phase 1: Credential Setup
1. Create a GitHub Personal Access Token (PAT) with `repo` scope
2. Add it as an n8n credential named `githubToken` (type: Header Auth)
3. Test with a simple PUT to `logs/test.json`

### Phase 2: Error Loggers (Priority)
1. Add Error Logger to Orchestrator (catches 38% error rate)
2. Add Entity Extraction Logger to Graph RAG (catches entity misses)
3. Add SQL Execution Logger to Quantitative (catches SQL errors)
4. Add Retrieval Quality Logger to Standard (catches low-quality retrieval)

### Phase 3: Execution Summary Loggers
1. Add Execution Summary Logger to Orchestrator (every request)
2. Add Neo4j Results Logger to Graph RAG (every traversal)
3. Add Retrieval Quality Logger to Standard (every retrieval)

### Phase 4: Dashboard Integration
The dashboard already reads from `logs/` — new error files will appear
automatically in the Execution Logs tab and Error Explorer.

---

## Alternative: n8n Webhook to GitHub Actions

Instead of direct GitHub API calls from n8n, use a GitHub Actions workflow
triggered by a repository_dispatch event:

```yaml
# .github/workflows/log-n8n-error.yml
name: Log n8n Error
on:
  repository_dispatch:
    types: [n8n-error-log]
jobs:
  log:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Write error log
        run: |
          mkdir -p logs/errors
          echo '${{ toJson(github.event.client_payload) }}' > \
            "logs/errors/err-$(date +%Y-%m-%d)-${{ github.event.client_payload.question_id }}.json"
      - name: Commit and push
        run: |
          git config user.name "n8n-logger"
          git config user.email "n8n@logger.local"
          git add logs/
          git commit -m "log: ${{ github.event.client_payload.pipeline }} error" || true
          git push
```

Then from n8n, fire a simple POST:
```
POST https://api.github.com/repos/LBJLincoln/mon-ipad/dispatches
Authorization: Bearer $TOKEN
Content-Type: application/json

{
  "event_type": "n8n-error-log",
  "client_payload": { ... error data ... }
}
```

This is cleaner because GitHub Actions handles git operations and avoids
merge conflicts from concurrent pushes.
