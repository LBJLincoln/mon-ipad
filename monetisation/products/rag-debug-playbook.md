# RAG Debug Playbook

## The Production Field Guide to Diagnosing and Fixing RAG Pipelines

### 79 Battle-Tested Fixes from 80+ Debugging Sessions in Production

---

**Version 1.0** | March 2026

Built from real-world production debugging across 80+ sessions operating a Multi-RAG Orchestrator with 4 specialized pipelines (Standard, Graph, Quantitative, Orchestrator), serving enterprise workloads on n8n, Pinecone, Neo4j, Supabase, OpenRouter, and HuggingFace Spaces.

Every fix in this guide was earned the hard way. No theory. No hypotheticals. Just battle scars from running RAG at scale.

---

## Who This Guide Is For

- **AI/ML Engineers** building or maintaining RAG systems in production
- **DevOps Engineers** running n8n, LangChain, or custom orchestration pipelines
- **Technical Leads** who need to diagnose and fix RAG issues fast
- **Solo Developers** building RAG products and tired of losing hours to the same bugs

## What You Will Get

- **79 documented production fixes** with root cause, step-by-step solution, and prevention strategy
- **3 diagnostic flowcharts** that take you from symptom to fix in under 5 minutes
- **12 anti-patterns** that cause 80% of RAG failures (and how to eliminate them)
- **LLM behavior profiles** for production models (Llama 70B, Gemma 27B, and more)
- **Database gotchas** for Pinecone, Neo4j, Supabase, and PostgreSQL
- **Rate-limit survival strategies** including multi-key rotation
- **Infrastructure patterns** for running RAG on free-tier cloud services
- **Quick-reference cheat sheets** for instant lookup during incidents

---

## Table of Contents

- [Part I: Diagnostic Flowcharts](#part-i-diagnostic-flowcharts)
  - [Flowchart A: Pipeline Responds But Result Is Wrong](#flowchart-a-pipeline-responds-but-result-is-wrong)
  - [Flowchart B: HTTP Error Calling Webhook](#flowchart-b-http-error-calling-webhook)
  - [Flowchart C: Fix Applied But Nothing Changed](#flowchart-c-fix-applied-but-nothing-changed)
  - [Quick Symptom Matrix](#quick-symptom-matrix)
  - [Pre-Debug Checklist](#pre-debug-checklist)
- [Part II: Fixes Library (79 Production Fixes)](#part-ii-fixes-library-79-production-fixes)
  - [Category 1: Workflow Engine (n8n) Infrastructure](#category-1-workflow-engine-n8n-infrastructure)
  - [Category 2: Cloud Deployment (HuggingFace Spaces)](#category-2-cloud-deployment-huggingface-spaces)
  - [Category 3: LLM Integration & Rate Limiting](#category-3-llm-integration--rate-limiting)
  - [Category 4: Vector Database (Pinecone)](#category-4-vector-database-pinecone)
  - [Category 5: Graph Database (Neo4j)](#category-5-graph-database-neo4j)
  - [Category 6: SQL Database (Supabase/PostgreSQL)](#category-6-sql-database-supabasepostgresql)
  - [Category 7: Pipeline Logic & Orchestration](#category-7-pipeline-logic--orchestration)
  - [Category 8: Evaluation & Testing](#category-8-evaluation--testing)
  - [Category 9: VM & Server Infrastructure](#category-9-vm--server-infrastructure)
  - [Category 10: API & Credential Management](#category-10-api--credential-management)
- [Part III: Recurring Patterns](#part-iii-recurring-patterns)
- [Part IV: Anti-Patterns That Cause 80% of Failures](#part-iv-anti-patterns-that-cause-80-of-failures)
- [Part V: LLM Behavior Profiles & Resilience](#part-v-llm-behavior-profiles--resilience)
- [Part VI: Database Gotchas Reference](#part-vi-database-gotchas-reference)
- [Part VII: Infrastructure & Performance](#part-vii-infrastructure--performance)
- [Part VIII: Quick Reference Cheat Sheet](#part-viii-quick-reference-cheat-sheet)

---

# Part I: Diagnostic Flowcharts

Use these flowcharts FIRST when diagnosing any RAG pipeline issue. Follow the tree from the top symptom to arrive at the specific fix. Each endpoint references a numbered fix in Part II.

---

## Flowchart A: Pipeline Responds But Result Is Wrong

```
SYMPTOM: Response received but content is wrong or unexpected
    |
    |--- Does the response contain "[object Object]"?
    |       |
    |       YES ---> JavaScript serialization error.
    |                Fix: Wrap objects with typeof check before concatenation.
    |                     typeof obj === 'object' ? JSON.stringify(obj) : obj
    |                See: Pattern P-02, FIX-22
    |
    |--- Does the response contain HTML (<!DOCTYPE html>)?
    |       |
    |       YES ---> API URL is incomplete or wrong.
    |                The LLM endpoint is returning its web page, not an API response.
    |                Fix: Verify URL ends with /chat/completions
    |                     (e.g., https://openrouter.ai/api/v1/chat/completions)
    |                See: FIX-35
    |
    |--- Does the response say "Query must start with SELECT"?
    |       |
    |       |--- Is there a 429 error in execution logs?
    |       |       |
    |       |       YES ---> Rate limit hit. LLM returned an error instead of SQL.
    |       |                Fix: Wait 60s, use key rotation, or switch model.
    |       |                See: FIX-22, Section on Rate Limiting
    |       |
    |       |--- Is the LLM returning invalid JSON?
    |       |       |
    |       |       YES ---> Model generates SQL wrapped in markdown, not clean JSON.
    |       |                Fix: Multi-strategy SQL extraction (JSON, ```sql block,
    |       |                     ```json block, raw SELECT regex).
    |       |                See: FIX-68
    |       |
    |       |--- Is the LLM returning HTML?
    |               |
    |               YES ---> API URL missing /chat/completions path.
    |                        See: FIX-35
    |
    |--- Is SQL syntactically correct but returns the wrong value?
    |       |
    |       YES ---> WHERE clause matches wrong record.
    |                Common: exact match fails on entity name variants.
    |                Fix: Use ILIKE '%keyword%' instead of = 'exact match'
    |                     Include sample data rows in LLM prompt.
    |                     Verify tenant_id = 'benchmark' (not 'default').
    |                See: Pattern P-03, FIX-70
    |
    |--- Is the response body empty ([] or "")?
    |       |
    |       |--- Is this the Orchestrator pipeline?
    |       |       |
    |       |       YES ---> executeWorkflow + respondToWebhook conflict.
    |       |                Sub-workflow sends response to client but returns
    |       |                nothing to parent workflow.
    |       |                Fix: Replace executeWorkflow with httpRequest POST.
    |       |                See: FIX-34
    |       |
    |       |--- Is this a non-Orchestrator pipeline?
    |               |
    |               YES ---> Missing or misconfigured "Respond to Webhook" node.
    |                        Fix: Verify workflow ends with a Respond node.
    |                        See: Pattern P-10
    |
    |--- Does the response contain data from the WRONG pipeline?
            |
            YES ---> Orchestrator routing error. Intent classifier sent the
                     query to the wrong sub-pipeline.
                     Fix: Check intent classifier prompt and model.
                     See: Category 7 fixes
```

---

## Flowchart B: HTTP Error Calling Webhook

```
SYMPTOM: HTTP error when calling the RAG webhook
    |
    |--- 404 "webhook not registered"?
    |       |
    |       |--- Is the webhook path correct?
    |       |       |
    |       |       NO ---> Path typed from memory (the #1 recurring mistake).
    |       |               Fix: ALWAYS copy webhook path from documentation.
    |       |               See: Anti-Pattern AP-01, Pre-Flight Checklist
    |       |
    |       |--- Path is correct but still 404?
    |               |
    |               YES ---> Workflow is not active.
    |                        Fix: Check workflow status in database:
    |                             SELECT active FROM workflow_entity WHERE id='<ID>';
    |                        If inactive, activate via API or UI.
    |                        See: FIX-19, FIX-72
    |
    |--- 401 "X-N8N-API-KEY header required"?
    |       |
    |       YES ---> No API key configured in the n8n instance.
    |                Fix: Use database direct access or cookie-based auth instead.
    |                     POST /rest/login with emailOrLdapLoginId (not email).
    |                See: FIX-27, FIX-50, FIX-73
    |
    |--- 500 Internal Server Error?
    |       |
    |       |--- Message: "access to env vars denied"?
    |       |       |
    |       |       YES ---> n8n 2.8+ blocks $env by default.
    |       |                Fix: Set N8N_BLOCK_ENV_ACCESS_IN_NODE=false
    |       |                     in entrypoint BEFORE n8n starts.
    |       |                See: FIX-33, FIX-63, FIX-65
    |       |
    |       |--- Message: "Credential with ID xxx does not exist"?
    |       |       |
    |       |       YES ---> Credential IDs from source environment don't exist
    |       |                in target environment after migration/rebuild.
    |       |                Fix: Create credentials in target, remap IDs in
    |       |                     workflow JSON.
    |       |                See: FIX-06, FIX-53, FIX-66
    |       |
    |       |--- Message: "SQLITE_CONSTRAINT FOREIGN KEY"?
    |       |       |
    |       |       YES ---> Workflow JSON contains foreign key references
    |       |                to source database entities.
    |       |                Fix: Strip FK fields before import
    |       |                     (shared, activeVersion, versionId, etc.)
    |       |                See: FIX-18, Pattern P-05
    |       |
    |       |--- No clear error message?
    |               |
    |               YES ---> Inspect the last execution in n8n.
    |                        Find which node failed and read its error output.
    |                        Fix: Pipeline-specific debugging required.
    |
    |--- 429 Too Many Requests?
    |       |
    |       YES ---> LLM rate limit exceeded (~20 req/min per key on free tier).
    |                Fix: Implement retry with 8s backoff, multi-key rotation,
    |                     or switch to a different model.
    |                See: FIX-22, FIX-59, Rate Limiting section
    |
    |--- 502/503 Service Unavailable?
    |       |
    |       YES ---> Server overloaded or restarting.
    |                Fix: Wait 30s and retry.
    |                     Check RAM usage (free -m) and kill zombie processes.
    |                     For HF Space: verify container is up (curl healthz).
    |                See: FIX-40, FIX-48
    |
    |--- Timeout (>60s, no response)?
            |
            YES ---> Pipeline is overloaded or stuck.
            |        Normal response times:
            |          Standard: 5-15s
            |          Graph: 10-25s
            |          Quantitative: 15-30s (3 LLM calls)
            |          Orchestrator: 20-45s (delegates to sub-pipelines)
            |
            |--- Are there stuck executions?
                    |
                    YES ---> Clean stuck executions from database.
                             DELETE FROM execution_entity
                             WHERE status IN ('new','running','waiting','crashed');
                             Then restart the workflow engine.
                             See: FIX-42, FIX-44, FIX-46, FIX-47
```

---

## Flowchart C: Fix Applied But Nothing Changed

```
SYMPTOM: Code modified but runtime behavior is unchanged
    |
    |--- Was the modification done on a VM-hosted n8n?
    |       |
    |       YES ---> STOP. VM-hosted n8n caches compiled code.
    |                Even container restarts do not guarantee recompilation.
    |                Fix: Modify workflows on a fresh instance only (e.g., HF Space).
    |                     Never modify production workflows on cached VM instances.
    |                See: Pattern P-11, FIX-21
    |
    |--- Was the modification done on a fresh instance (HF Space)?
    |       |
    |       |--- Was the container rebuilt after the change?
    |       |       |
    |       |       NO ---> Changes are not deployed. Trigger a rebuild.
    |       |               Verify in deploy logs that new code is active.
    |       |
    |       |--- Does the workflow use $env variables?
    |       |       |
    |       |       YES ---> Verify N8N_BLOCK_ENV_ACCESS_IN_NODE=false is set.
    |       |                See: FIX-63
    |       |
    |       |--- Was a Code node modified?
    |       |       |
    |       |       YES ---> Code node caching. Must cycle:
    |       |                1. PUT (update workflow)
    |       |                2. Deactivate workflow
    |       |                3. Re-activate workflow
    |       |                See: FIX-21
    |       |
    |       |--- Were nodes[] updated but NOT activeVersion.nodes[]?
    |               |
    |               YES ---> n8n has two node arrays. You must patch BOTH.
    |                        nodes[] = stored definition
    |                        activeVersion.nodes[] = runtime definition
    |                        Fix: Always update both arrays in PATCH calls.
    |                        See: Anti-Pattern AP-06, FIX-29, FIX-32
    |
    |--- Was the modification done via REST API?
            |
            |--- Was PUT used instead of PATCH?
            |       |
            |       YES ---> n8n API requires PATCH, not PUT.
            |                PUT may return 404 or silently fail.
            |                Also: PUT payload must exclude read-only fields.
            |                See: FIX-09
            |
            |--- Was the deactivate-reactivate cycle performed?
                    |
                    NO ---> Mandatory after any workflow update via API:
                            1. PATCH the workflow JSON
                            2. POST /deactivate
                            3. POST /activate (with versionId in body for n8n 2.8+)
                            See: FIX-21, FIX-72
```

---

## Quick Symptom Matrix

| Symptom | Flowchart | Most Likely Fix | Category |
|---------|-----------|-----------------|----------|
| 404 "webhook not registered" | B | Wrong path or inactive workflow | Infrastructure |
| 500 "$env denied" | B | FIX-63: N8N_BLOCK_ENV_ACCESS_IN_NODE=false | Cloud Deployment |
| 500 "credential not found" | B | FIX-53: Credential ID remapping after migration | Credentials |
| 429 rate limit | B | Multi-key rotation + 8s backoff | LLM Integration |
| Response body empty (Orchestrator) | A | FIX-34: Replace executeWorkflow with httpRequest | Orchestration |
| HTML instead of JSON in response | A | FIX-35: URL missing /chat/completions | LLM Integration |
| "[object Object]" in output | A | Pattern P-02: typeof check before stringify | Pipeline Logic |
| "Query must start with SELECT" | A | Rate limit or markdown SQL output | LLM / SQL |
| Fix has no effect (VM) | C | Pattern P-11: Never modify on cached VM | Infrastructure |
| Fix has no effect (HF Space) | C | AP-06: Patch both nodes[] arrays | API |
| Out of memory on server | -- | Kill zombie processes, clean executions | VM Infrastructure |
| Test results inconsistent | -- | Rate limits causing random failures | Evaluation |
| SQL correct but wrong number | A | FIX-70: Wrong tenant_id ('default' vs 'benchmark') | Database |
| Workflow patched but old one runs | C | FIX-71: Duplicate active workflows | Infrastructure |

---

## Pre-Debug Checklist

Before starting any debugging session, verify these items in order. If any check identifies the problem, apply the existing solution immediately. Do not re-diagnose a solved problem.

```
[ ] 1. Is the symptom listed in the Quick Symptom Matrix above?
       -> If YES: go directly to the referenced fix.

[ ] 2. Is the symptom documented in the Fixes Library (Part II)?
       -> Search by keyword. If found, apply the documented solution.

[ ] 3. Is the symptom a known Recurring Pattern (Part III)?
       -> Check the 11 documented patterns.

[ ] 4. Are any of the 12 Anti-Patterns (Part IV) being violated?
       -> AP-01 through AP-12. If yes, correct the anti-pattern first.

[ ] 5. Has the Pre-Flight Checklist been followed?
       -> Webhook path verified from docs (not memory).
       -> Field name is 'query' (not 'question').
       -> Content-Type: application/json header set.
       -> Server health check returns 200.
       -> Target workflow is active in database.
```

**Rule: If any check finds the answer, APPLY THE EXISTING SOLUTION. Do NOT re-analyze. Do NOT re-diagnose. Apply directly.**

---

# Part II: Fixes Library (79 Production Fixes)

Each fix follows a consistent format:
- **ID and Title**: Unique identifier for cross-referencing
- **Severity**: CRITICAL (system down), IMPORTANT (degraded), or INFORMATIONAL
- **Symptom**: What you observe
- **Root Cause**: Why it happens
- **Solution**: Step-by-step fix
- **Prevention**: How to ensure it never happens again

---

## Category 1: Workflow Engine (n8n) Infrastructure

These fixes address issues in the workflow orchestration engine itself -- node caching, expression evaluation, environment variable access, API behavior, and workflow lifecycle management.

---

### FIX-01: Task Runner Isolation Breaks Static Data Storage

**Severity**: CRITICAL

**Symptom**: `$getWorkflowStaticData()` returns empty object `{}` on every execution. State is never persisted between runs. Counters, caches, and accumulated data reset on each call.

**Root Cause**: n8n 2.7.4+ runs Code nodes in an isolated Task Runner subprocess. The subprocess has no access to the main n8n process memory where static data is stored. `$getWorkflowStaticData('global')` creates a new empty object in the subprocess scope each time.

**Solution**:
1. Do not rely on `$getWorkflowStaticData()` for cross-execution persistence.
2. Use an external store for state: database table, Redis key, or file on disk.
3. For simple counters, use the execution ID or timestamp instead.

**Prevention**: Never use `$getWorkflowStaticData()` in n8n 2.7.4+ with Task Runners enabled. If you need persistent state, architect it externally from the start.

---

### FIX-02: SQL Error Handler Creates Infinite Loop

**Severity**: CRITICAL

**Symptom**: Workflow execution hangs indefinitely. CPU usage spikes. The execution never completes, eventually timing out or crashing the container.

**Root Cause**: An error handler node used `$execution.id` as a counter key in `$getWorkflowStaticData()`. Due to FIX-01, the counter never incremented. The error handler kept retrying the failed SQL query with no backoff, creating an infinite loop.

**Solution**:
1. Remove the `$getWorkflowStaticData()` counter.
2. Use the `maxTries` parameter on the HTTP Request node (set to 3).
3. Add `waitBetweenTries: 8000` (8 seconds) for backoff.
4. Set `continueOnFail: true` to prevent the error from blocking the workflow.

**Prevention**: Never build retry logic using static data counters. Use n8n's built-in retry parameters (`maxTries`, `waitBetweenTries`) on the failing node.

---

### FIX-03: SQL Validator Produces Invalid Fallback SQL

**Severity**: CRITICAL

**Symptom**: PostgreSQL error: `syntax error at or near "FROM"`. The fallback SQL generated when validation fails has no table reference.

**Root Cause**: The SQL Validator node generated a fallback query like `SELECT 'No valid SQL generated'` without a `FROM` clause. PostgreSQL requires `SELECT ... FROM` syntax (unlike MySQL which allows bare `SELECT`).

**Solution**:
1. Change the fallback SQL to: `SELECT 'No valid SQL could be generated' AS error_message;`
2. This is valid PostgreSQL syntax (a bare SELECT with an alias is accepted).
3. Alternatively, use `SELECT 1 AS placeholder;` and handle the result downstream.

**Prevention**: Always test fallback SQL against the target database engine. PostgreSQL, MySQL, and SQLite have different syntax requirements for SELECT without FROM.

---

### FIX-04: Jina Embedding API Rejects Trailing Comma in JSON

**Severity**: CRITICAL

**Symptom**: Jina API returns 400 Bad Request. The request body looks correct in the workflow editor but fails at runtime.

**Root Cause**: The JSON body sent to `https://api.jina.ai/v1/embeddings` contained a trailing comma after the last array element. JavaScript's `JSON.stringify()` does not produce trailing commas, but the Code node was manually building the JSON string with string concatenation.

**Solution**:
1. Never build JSON with string concatenation.
2. Use `JSON.stringify()` to serialize the body:
```javascript
const body = JSON.stringify({
  model: "jina-embeddings-v3",
  input: texts,
  dimensions: 1024,
  task: "retrieval.passage"
});
```
3. Set the HTTP Request node to accept JSON body, not raw text.

**Prevention**: Always use `JSON.stringify()` for API request bodies. Never manually concatenate JSON strings.

---

### FIX-05: Task Broker Token Expires Before Code Execution Completes

**Severity**: CRITICAL

**Symptom**: Code node execution fails with timeout error after exactly 15 seconds, even though the code logic should complete in 2-3 seconds.

**Root Cause**: The Task Broker (which manages Task Runner communication) has a default TTL of 15 seconds for grant tokens. If the Code node takes longer than 15 seconds (due to network latency, garbage collection, or waiting for I/O), the grant token expires and the execution fails.

**Solution**:
1. Increase the Task Broker TTL to 120 seconds:
```bash
export N8N_RUNNERS_TASK_BROKER_TTL=120000  # milliseconds
```
2. Add this to your entrypoint script before starting n8n.

**Prevention**: Always set `N8N_RUNNERS_TASK_BROKER_TTL=120000` in production. The 15-second default is too aggressive for any workload involving network calls.

---

### FIX-09: PUT Workflow API Rejects Read-Only Fields

**Severity**: IMPORTANT

**Symptom**: n8n REST API returns 400 error when updating a workflow with PUT.

**Root Cause**: The PUT payload included read-only fields (`id`, `createdAt`, `updatedAt`, `active`, `versionId`). n8n 2.8+ rejects these in the request body.

**Solution**:
1. Use PATCH instead of PUT.
2. If PUT is required, strip all read-only fields before sending:
```python
READONLY_FIELDS = ['id', 'createdAt', 'updatedAt', 'active',
                   'versionId', 'shared', 'activeVersion']
for field in READONLY_FIELDS:
    payload.pop(field, None)
```

**Prevention**: Always use PATCH for workflow updates. Reserve PUT for full replacements only, and always strip read-only fields.

---

### FIX-21: Code Node Cache -- PUT + Deactivate + Activate Cycle Required

**Severity**: CRITICAL

**Symptom**: Code modified via API. GET confirms the change is saved. But the workflow still executes the OLD code at runtime.

**Root Cause**: n8n caches compiled Code node JavaScript in memory. A simple PATCH/PUT updates the stored JSON but does not trigger recompilation. The Task Runner continues to use the cached compiled version.

**Solution**:
1. PATCH the workflow with the updated code.
2. Deactivate the workflow: `POST /rest/workflows/{id}/deactivate`
3. Reactivate the workflow: `POST /rest/workflows/{id}/activate`
   - For n8n 2.8+: include `{"versionId": "..."}` in the body (see FIX-72).
4. Verify with a test request to confirm new behavior.

**Prevention**: After ANY code change via API, always perform the full deactivate-reactivate cycle. No exceptions.

---

### FIX-24: N8N_RUNNERS_ENABLED Deprecated in n8n 2.7.4+

**Severity**: IMPORTANT

**Symptom**: Setting `N8N_RUNNERS_ENABLED=true` produces a deprecation warning. Task Runners appear to not work.

**Root Cause**: Starting from n8n 2.7.4, Task Runners are always active. The `N8N_RUNNERS_ENABLED` environment variable is deprecated and ignored.

**Solution**:
1. Remove `N8N_RUNNERS_ENABLED` from your configuration.
2. Task Runners are always on -- no configuration needed.
3. Focus on configuring `N8N_RUNNERS_TASK_BROKER_TTL` instead.

**Prevention**: When upgrading n8n versions, review the changelog for deprecated environment variables.

---

### FIX-33: $env Blocked for ALL Node Types in n8n 2.8+

**Severity**: CRITICAL

**Symptom**: Every node that references `$env.VARIABLE_NAME` returns "access to env vars denied". This affects HTTP Request nodes, Postgres nodes, Code nodes -- every node type without exception.

**Root Cause**: n8n 2.8.3 with Task Runners evaluates ALL expressions (not just Code nodes) in a sandboxed environment. The sandbox blocks `$env` access by default across all node types: Code, HTTP Request, Postgres, IF, Set, and every other node.

**Solution**:
1. Add to your startup script (BEFORE n8n starts):
```bash
export N8N_BLOCK_ENV_ACCESS_IN_NODE=false
```
2. Alternatively, replace ALL `$env.VARIABLE_NAME` references with hardcoded values at import time using a preprocessing script:
```python
import os, json, re

def inject_env_vars(workflow_json_text):
    """Replace $env.VAR_NAME with actual values before import."""
    def replace_env(match):
        var_name = match.group(1)
        return os.environ.get(var_name, f'MISSING_{var_name}')

    return re.sub(r'\$env\.(\w+)', replace_env, workflow_json_text)
```

**Impact**: This single fix resolves failures across ALL pipelines simultaneously. In a real deployment, 117 `$env` references across 5 workflows were broken by this default.

**Prevention**:
- `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` must be in your startup script.
- Treat this as a non-negotiable configuration for n8n 2.8+.
- Consider pre-injecting values at import time as a defense-in-depth measure.

---

### FIX-54: Broken Expression Syntax in n8n Nodes

**Severity**: CRITICAL

**Symptom**: Expressions like `={{.VAR}}` fail silently. The node receives an empty string instead of the expected value.

**Root Cause**: Incorrect expression syntax. The correct format is `={{ $env.VAR }}` or `={{ $json.field }}`. A missing `$` prefix causes the expression to evaluate to nothing.

**Solution**:
1. Audit all expressions in the workflow JSON:
```bash
grep -n '={{[^$]' workflow.json
```
2. Fix any expression that does not start with `$` after `={{`:
   - Wrong: `={{.VAR}}` or `={{VAR}}`
   - Correct: `={{ $env.VAR }}` or `={{ $json.field }}`

**Prevention**: Use the grep command above as a pre-deployment check. Add it to your CI pipeline.

---

### FIX-71: Duplicate Active Workflows With Same Webhook

**Severity**: CRITICAL

**Symptom**: PATCH updates to a workflow's code have no effect. Execution logs show the old code running. But GET confirms the new code is saved in the patched workflow.

**Root Cause**: Two versions of the same workflow were BOTH active with identical webhook paths. For example, Workflow V3.1 (ID: `abc123`) and Workflow V5.0 (ID: `def456`) both registered the same webhook. The older workflow was handling all requests. Patching the newer workflow had no effect because it never received traffic.

**Solution**:
1. Get the execution data for the most recent request:
```
GET /rest/executions?workflowId=<EXPECTED_ID>&limit=1
```
2. Check the `workflowId` in the execution data. If it differs from your expected workflow, a duplicate is handling the traffic.
3. List all active workflows and find the duplicate:
```
GET /rest/workflows?active=true
```
4. Deactivate the stale/unwanted workflow.
5. Verify the correct workflow now handles requests.

**Prevention**: Before patching any workflow, ALWAYS check execution data to confirm which workflow ID is actually handling requests. Never assume it is the one you expect.

---

### FIX-72: n8n 2.8+ Activation Requires versionId

**Severity**: IMPORTANT

**Symptom**: POST to `/rest/workflows/{id}/activate` returns 400 or silently fails. The workflow remains inactive.

**Root Cause**: Starting in n8n 2.8, the activate endpoint requires a `versionId` in the POST body. This is a publishing mechanism: you must specify which version to activate.

**Solution**:
1. First, get the current versionId:
```
GET /rest/workflows/{id}
# Extract versionId from response
```
2. Then activate with the versionId:
```
POST /rest/workflows/{id}/activate
Content-Type: application/json
{"versionId": "<extracted_version_id>"}
```

**Prevention**: Always fetch the workflow first to get the current versionId before attempting activation.

---

### FIX-74: Expression Not Evaluated in jsonBody

**Severity**: CRITICAL

**Symptom**: HTTP Request node sends literal string `{{ 'model' || 'fallback' }}` instead of evaluating the expression. The API receives the raw expression text.

**Root Cause**: In n8n's HTTP Request node, expressions inside `jsonBody` are not automatically evaluated when using the `{{ }}` syntax without the `=` prefix. The node treats them as plain text.

**Solution**:
1. Use `={{ }}` (with equals sign) for any expression in jsonBody:
   - Wrong: `{{ 'model' || 'fallback' }}`
   - Correct: `={{ 'model' || 'fallback' }}`
2. Alternatively, hardcode the value directly if it is static.

**Prevention**: All n8n expressions must use `={{ }}` syntax. The `{{ }}` form without `=` is not evaluated.

---

## Category 2: Cloud Deployment (HuggingFace Spaces)

These fixes address issues specific to deploying n8n on HuggingFace Spaces (Docker containers with 16GB RAM, free tier). Many of these apply to any Docker-based n8n deployment.

---

### FIX-13: Python3 Missing in n8n Docker Image

**Severity**: CRITICAL

**Symptom**: Entrypoint script fails with `python3: command not found`. The container crashes on startup.

**Root Cause**: The base n8n Docker image (`node:20-bookworm-slim`) does not include Python. If your setup scripts use Python (for environment variable injection, workflow preprocessing, etc.), they fail silently or crash the container.

**Solution**:
Add Python installation to your Dockerfile:
```dockerfile
RUN apt-get update && apt-get install -y python3 python3-pip curl && \
    rm -rf /var/lib/apt/lists/*
```

**Prevention**: Always verify that all required runtime dependencies are included in your Docker image. Test the image locally before deploying to cloud.

---

### FIX-14: Workflow Import Format (Array vs Object)

**Severity**: CRITICAL

**Symptom**: `n8n import:workflow --input=file.json` fails with a parsing error.

**Root Cause**: n8n's import command expects a single workflow JSON object, not an array. If you export multiple workflows, the result is an array `[{...}, {...}]`, which the import command rejects.

**Solution**:
1. Export workflows individually (one file per workflow).
2. If you have an array, split it:
```python
import json
workflows = json.load(open('all-workflows.json'))
for wf in workflows:
    with open(f"wf-{wf['id']}.json", 'w') as f:
        json.dump(wf, f)
```
3. Import each file separately.

**Prevention**: Always export and import workflows as individual files, never as arrays.

---

### FIX-15: HF Proxy Breaks POST Body for REST/API Endpoints

**Severity**: IMPORTANT

**Symptom**: POST requests to `/rest/` and `/api/` endpoints arrive with empty or corrupted body. Webhook endpoints (`/webhook/`) work fine.

**Root Cause**: HuggingFace's reverse proxy processes certain URL paths differently. REST and API paths may have their POST body stripped or modified by the proxy layer.

**Solution**:
1. For internal API calls, use direct container URLs (bypassing the proxy).
2. For webhook calls from external clients, the standard HF Space URL works.
3. For setup scripts running inside the container, use `localhost:7860` directly.

**Prevention**: Test all API endpoints through the HF proxy before relying on them. Keep webhook paths as the primary interface for external access.

---

### FIX-17: n8n 2.x Login Field Name Change

**Severity**: IMPORTANT

**Symptom**: Login to n8n via API fails with 400 or "email is required" error.

**Root Cause**: n8n 2.x changed the login field from `email` to `emailOrLdapLoginId`. Older scripts and documentation reference `email`.

**Solution**:
```python
login_payload = {
    "emailOrLdapLoginId": "user@example.com",  # NOT "email"
    "password": "your-password"
}
response = requests.post(f"{n8n_url}/rest/login", json=login_payload)
```

**Prevention**: When upgrading n8n, check authentication endpoint changes in the changelog. The field name change is not backward-compatible.

---

### FIX-18: SQLite FK Constraint on Workflow Import

**Severity**: CRITICAL

**Symptom**: `SQLITE_CONSTRAINT: FOREIGN KEY constraint failed` when importing a workflow into a fresh n8n instance.

**Root Cause**: Exported workflow JSON contains foreign key fields (`shared`, `activeVersion`, `activeVersionId`, `versionId`, `versionCounter`) that reference entities in the source database. On a fresh import, these referenced entities do not exist.

**Solution**:
Strip FK fields before import:
```python
FK_FIELDS = ['shared', 'activeVersion', 'activeVersionId',
             'versionId', 'versionCounter']

def clean_workflow_for_import(workflow):
    for field in FK_FIELDS:
        workflow.pop(field, None)
    return workflow
```

**Prevention**: Always run a cleanup function on workflow JSON before importing into any fresh n8n instance. Add this to your deployment script.

---

### FIX-19: Imported Workflow Always Inactive + Activation Fails

**Severity**: IMPORTANT (resolved by FIX-18)

**Symptom**: `n8n import:workflow` imports successfully but the workflow is inactive. Attempting to activate via REST API fails.

**Root Cause**: n8n imports all workflows as inactive by default. Activation via REST requires the FK constraint issue to be resolved first (FIX-18) and the versionId to be provided (FIX-72).

**Solution**:
1. Import with FK fields stripped (FIX-18).
2. After import, activate via the REST API with versionId (FIX-72).
3. Or use the n8n UI to activate manually after import.

**Prevention**: Include a post-import activation step in your deployment script.

---

### FIX-20: REST API Not Ready After Healthcheck Passes

**Severity**: IMPORTANT

**Symptom**: `curl /healthz` returns 200, but REST API calls return 503 or connection refused.

**Root Cause**: n8n's health check endpoint becomes available before the REST API and webhook engine are fully initialized. There is a startup delay of 10-30 seconds between healthz=200 and full API readiness.

**Solution**:
1. After healthz returns 200, wait an additional 30 seconds before making API calls.
2. Implement a readiness check that tests an actual API endpoint:
```bash
# Wait for healthz
until curl -s -o /dev/null -w "%{http_code}" http://localhost:7860/healthz | grep -q 200; do sleep 2; done

# Then wait for API readiness
sleep 30

# Verify with actual API call
curl -s http://localhost:7860/rest/workflows | head -c 100
```

**Prevention**: Never assume healthz=200 means the system is fully ready. Always include a startup delay or readiness probe.

---

### FIX-48: Nginx Reverse Proxy Causes Persistent 502

**Severity**: CRITICAL

**Symptom**: All requests to the HF Space return 502 Bad Gateway. Restarting the container does not help.

**Root Cause**: Using nginx as a reverse proxy in front of n8n inside an HF Space container creates a race condition. HF Spaces expects the application to listen directly on port 7860. nginx adds a layer that HF's own proxy cannot reliably pass traffic through.

**Solution**:
1. Remove nginx from the Docker setup entirely.
2. Configure n8n to listen directly on port 7860:
```bash
export N8N_PORT=7860
export N8N_HOST=0.0.0.0
```
3. Let HF's built-in proxy handle external routing.

**Prevention**: On HF Spaces, always have your application listen directly on port 7860. Never add a reverse proxy layer inside the container.

---

### FIX-49: Minimal Boot Configuration for Stability

**Severity**: IMPORTANT

**Symptom**: n8n container crashes intermittently during startup with database connection errors or Redis timeouts.

**Root Cause**: Including PostgreSQL and Redis in the Docker setup creates race conditions during container startup. If n8n starts before the databases are ready, it crashes.

**Solution**:
Use SQLite mode for n8n on HF Spaces (ephemeral instances):
```bash
export DB_TYPE=sqlite
export DB_SQLITE_DATABASE=/data/n8n.sqlite
# Remove all POSTGRES_* and REDIS_* environment variables
```

**Prevention**: For ephemeral/stateless deployments (HF Spaces, serverless), use SQLite. Reserve PostgreSQL for persistent, multi-instance deployments.

---

### FIX-51: set -e in Entrypoint Kills Container on Transient Failure

**Severity**: CRITICAL

**Symptom**: Container exits immediately after a transient error (e.g., a failed curl to check an external service, or a Python script with a non-zero exit code).

**Root Cause**: `set -e` in the entrypoint.sh script causes the entire script to abort on any non-zero exit code, including expected or transient failures.

**Solution**:
1. Remove `set -e` from the top of entrypoint.sh.
2. Use explicit error handling for critical commands:
```bash
#!/bin/bash
# DO NOT use set -e

# Critical setup with error handling
python3 setup-workflows.py || echo "WARN: Setup script failed, continuing..."

# Start n8n (this should always run)
exec n8n start
```

**Prevention**: Never use `set -e` in entrypoint scripts for Docker containers. Use explicit `||` or `if` checks for commands that must succeed.

---

### FIX-60: Duplicate Secret and Variable Names Cause CONFIG_ERROR

**Severity**: CRITICAL

**Symptom**: HF Space fails to start with `CONFIG_ERROR`. No useful error message in logs.

**Root Cause**: HuggingFace Spaces treats secrets and variables as separate namespaces, but n8n resolves them as a flat namespace. If you have a secret named `OPENROUTER_API_KEY` and a variable with the same name, the conflict causes a startup error.

**Solution**:
1. Audit all secrets and variables in your HF Space settings.
2. Remove any duplicates (keep the secret, delete the variable, or vice versa).
3. Use a consistent naming convention to avoid collisions.

**Prevention**: Maintain a single source of truth for environment variables. Never create both a secret and a variable with the same name.

---

### FIX-63: N8N_BLOCK_ENV_ACCESS_IN_NODE Missing (Most Common Fix)

**Severity**: CRITICAL -- This is the single most frequently encountered issue.

**Symptom**: ALL pipelines return "Unable to generate answer" or "NO_ANSWER". Execution data shows `"access to env vars denied"` in every HTTP Request node. Despite 20+ environment variables being correctly configured, none are accessible.

**Root Cause**: n8n 2.8.3 blocks `$env.*` access in ALL node types by default. Without the override flag, every node that references `$env.OPENROUTER_API_KEY`, `$env.PINECONE_API_KEY`, etc., fails silently or returns an error.

**Solution**:
Add this single line to your entrypoint script, BEFORE n8n starts:
```bash
export N8N_BLOCK_ENV_ACCESS_IN_NODE=false
```

**Impact**: Cross-pipeline fix. This one line resolves failures in ALL workflows simultaneously.

**Prevention**:
- This must be in every entrypoint.sh, every Dockerfile, every deployment script.
- Verify after every deploy: `curl -s <webhook_url> -d '{"query":"test"}'` should NOT contain "env vars denied".
- Treat this as the first thing to check when "everything is broken after deploy."

---

### FIX-65: Deploy N8N_BLOCK_ENV_ACCESS_IN_NODE to All Instances

**Severity**: CRITICAL

**Symptom**: Some pipeline instances work, others don't. Inconsistent behavior across multiple HF Space instances.

**Root Cause**: The `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` flag was only added to some instances, not all. Any instance missing the flag has broken `$env` access.

**Solution**:
1. Create a deployment script that updates ALL instances:
```bash
#!/bin/bash
SPACES=("space-1" "space-2" "space-3" ... "space-9")
for space in "${SPACES[@]}"; do
    echo "Deploying to $space..."
    # Update entrypoint.sh with N8N_BLOCK_ENV_ACCESS_IN_NODE=false
    # Push to trigger rebuild
done
```
2. Verify each instance after deployment.

**Prevention**: Use infrastructure-as-code. A single configuration source should define ALL instance configurations, ensuring consistency.

---

### FIX-66: Credential Restore After Container Rebuild

**Severity**: CRITICAL

**Symptom**: After an HF Space rebuild (factory reboot), all webhooks return 500 with "Credential with ID xxx does not exist".

**Root Cause**: HF Space rebuilds wipe the SQLite database, including all credential records. Workflows reference credential IDs that no longer exist.

**Solution**:
Create a credential restore script that runs during boot:
```python
import requests
import json

def restore_credentials(n8n_url, credentials_config):
    """Create credentials and remap IDs in workflows."""
    session = login_to_n8n(n8n_url)

    for cred in credentials_config:
        # Create the credential
        response = session.post(f"{n8n_url}/rest/credentials", json={
            "name": cred["name"],
            "type": cred["type"],
            "data": cred["data"]
        })
        new_id = response.json()["id"]

        # Update all workflows that reference the old ID
        remap_credential_id(session, n8n_url, cred["old_id"], new_id)
```

**Prevention**: Include credential restoration in your startup script. Store credential definitions (encrypted) alongside your workflow configurations.

---

### FIX-67: HF Space Rebuilds Reset Webhook Registrations

**Severity**: IMPORTANT

**Symptom**: After a rebuild, webhooks that were previously active return 404.

**Root Cause**: HF Space rebuilds destroy the SQLite database, which includes webhook registrations. Even though workflows are re-imported, webhooks are only registered when a workflow is activated.

**Solution**:
Include workflow activation in the startup script:
```bash
# After importing workflows
python3 setup-workflows.py  # Imports + activates all workflows
sleep 30  # Wait for webhook registration
# Test each webhook
curl -s -o /dev/null -w "%{http_code}" -X POST "$N8N_URL/webhook/<path>" \
  -H "Content-Type: application/json" -d '{"query":"health check"}'
```

**Prevention**: Your deployment script must always import AND activate workflows. Never assume import alone registers webhooks.

---

## Category 3: LLM Integration & Rate Limiting

---

### FIX-22: OpenRouter 429 Rate Limit Crashes Pipeline

**Severity**: CRITICAL

**Symptom**: Pipeline returns "Unable to generate SQL" or produces garbage output. Execution logs show HTTP 429 from OpenRouter. The pipeline does not retry -- it treats the rate-limit error as a valid LLM response.

**Root Cause**: OpenRouter's free tier limits to ~20 requests per minute per API key (all models combined). Without retry logic, the 429 error body is passed through the pipeline as if it were LLM output. Downstream nodes try to parse the error as SQL or JSON, producing nonsensical results.

**Solution**:
Configure HTTP Request nodes with resilience settings:
```json
{
  "maxTries": 3,
  "waitBetweenTries": 8000,
  "continueOnFail": true
}
```

Additionally, implement proper error detection:
```javascript
// In the response processing Code node
const response = $input.first().json;

if (response.error && response.error.type === 'rate_limit_error') {
  return [{ json: {
    error: 'RATE_LIMIT',
    message: 'LLM rate limit exceeded, retry later',
    retry_after: 60
  }}];
}
```

**Prevention**:
- Always set `maxTries >= 3` and `waitBetweenTries >= 8000` on LLM HTTP Request nodes.
- Always check the response for error conditions before processing.
- Implement multi-key rotation for high-throughput scenarios (see FIX-59).

---

### FIX-35: OpenRouter URL Missing /chat/completions Returns HTML

**Severity**: CRITICAL

**Symptom**: LLM node returns raw HTML (`<!DOCTYPE html>...`) instead of a JSON response. Downstream processing fails.

**Root Cause**: The `OPENROUTER_BASE_URL` environment variable was set to `https://openrouter.ai/api/v1` without the `/chat/completions` path. The API endpoint returns its web interface (HTML) for requests to the base URL.

**Solution**:
Ensure the full URL is used:
```
# WRONG:
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# CORRECT:
OPENROUTER_URL=https://openrouter.ai/api/v1/chat/completions
```

**Prevention**: Always include the complete API path in URL configuration. Validate by checking that the response `Content-Type` is `application/json`, not `text/html`.

---

### FIX-59: Free Model Rate-Limited -- Model Swap Strategy

**Severity**: CRITICAL

**Symptom**: Persistent 429 errors even with retry logic. Certain free models become heavily rate-limited during peak hours.

**Root Cause**: Popular free models (Llama 70B, Gemma 27B) attract heavy usage. OpenRouter enforces stricter rate limits on these models during peak periods.

**Solution**:
Implement a model fallback chain:
```javascript
const MODEL_CHAIN = [
  "meta-llama/llama-3.3-70b-instruct:free",     // Primary
  "qwen/qwen3-235b-a22b:free",                   // Fallback 1
  "mistralai/mistral-small-3.1-24b-instruct:free", // Fallback 2
  "google/gemma-3-27b-it:free"                    // Fallback 3
];

async function callWithFallback(prompt, modelIndex = 0) {
  if (modelIndex >= MODEL_CHAIN.length) {
    return { error: "All models rate-limited" };
  }

  const response = await callLLM(prompt, MODEL_CHAIN[modelIndex]);
  if (response.status === 429) {
    return callWithFallback(prompt, modelIndex + 1);
  }
  return response;
}
```

**Prevention**: Never rely on a single model. Always have at least 2 fallback models configured. Monitor rate-limit headers (`x-ratelimit-remaining`) proactively.

---

### FIX-61: Embedding/Reranking API Credits Exhausted

**Severity**: CRITICAL

**Symptom**: Pinecone queries return 0 results. Reranking returns empty arrays. API calls return 402 or quota-exceeded errors.

**Root Cause**: Jina AI and Cohere offer free tiers with monthly token limits (Jina: 10M tokens/month, Cohere: trial credits). When exhausted, all embedding and reranking operations fail silently.

**Solution**:
1. Monitor usage proactively:
```bash
# Check Jina quota
curl -s https://api.jina.ai/v1/usage \
  -H "Authorization: Bearer $JINA_API_KEY" | python3 -m json.tool
```
2. Implement a quota check before batch operations.
3. Have backup API keys from separate accounts.
4. Switch between providers (Jina and Cohere are interchangeable for reranking).

**Prevention**: Set up usage alerts at 80% of quota. Rotate to backup keys before exhaustion.

---

### FIX-68: SQL Validator Only Parses JSON -- LLM Returns Markdown

**Severity**: CRITICAL

**Symptom**: Quantitative pipeline always returns "SQL_GENERATION_ERROR: Invalid LLM response". The LLM generates correct SQL but the validator rejects it.

**Root Cause**: The SQL Validator node uses `JSON.parse(content)` to extract SQL from the LLM response. But free-tier models (especially Llama 70B via Groq) frequently return SQL wrapped in markdown format with Chain-of-Thought reasoning, not clean JSON. Example:
```
### Analysis
The question asks about revenue...

```sql
SELECT revenue FROM financials WHERE company_name ILIKE '%techvision%'
```
```

**Solution**:
Implement multi-strategy extraction:
```javascript
function extractSQL(content) {
  // Strategy 1: Try JSON.parse
  try {
    const parsed = JSON.parse(content);
    if (parsed.sql) return parsed.sql;
    if (parsed.query) return parsed.query;
  } catch (e) { /* not JSON */ }

  // Strategy 2: Extract from ```sql code block
  const sqlBlock = content.match(/```sql\s*\n?([\s\S]*?)```/i);
  if (sqlBlock) return sqlBlock[1].trim();

  // Strategy 3: Extract from ```json code block
  const jsonBlock = content.match(/```json\s*\n?([\s\S]*?)```/i);
  if (jsonBlock) {
    try {
      const parsed = JSON.parse(jsonBlock[1]);
      if (parsed.sql) return parsed.sql;
    } catch (e) { /* invalid JSON in block */ }
  }

  // Strategy 4: Find raw SELECT statement
  const selectMatch = content.match(/(SELECT[\s\S]+?;)/i);
  if (selectMatch) return selectMatch[1].trim();

  return null; // No SQL found
}
```

**Prevention**: Never assume LLM output format. Always implement multi-strategy parsing that handles JSON, markdown, and raw text responses. Free-tier models are especially inconsistent.

---

## Category 4: Vector Database (Pinecone)

---

### FIX-12: Dimension Mismatch After Embedding Model Migration

**Severity**: CRITICAL

**Symptom**: Pinecone upsert returns "Vector dimension mismatch: expected 1024, got 1536". All embedding operations fail.

**Root Cause**: The Pinecone index was created with dimension 1024 (for Jina embeddings), but the workflow was still configured to use Cohere embeddings (dimension 1536). After switching embedding providers, the index dimensions no longer match.

**Solution**:
1. Verify your index dimensions:
```bash
curl -s "https://<index-host>/describe_index_stats" \
  -H "Api-Key: $PINECONE_API_KEY" | python3 -m json.tool
# Check "dimension" field
```
2. Ensure your embedding model produces vectors of the correct dimension:
   - Jina v3: 1024 dimensions
   - Cohere embed-english-v3: 1024 dimensions
   - Cohere embed-english-v2: 4096 dimensions
   - OpenAI ada-002: 1536 dimensions
3. If there is a mismatch, either:
   - Re-create the index with the correct dimension, OR
   - Switch the embedding model to match the index

**Prevention**: When changing embedding providers, ALWAYS check dimension compatibility with your existing index. Document the dimension in your configuration file.

---

## Category 5: Graph Database (Neo4j)

---

### FIX-07: Neo4j bolt:// Protocol Fails in HTTP Request Nodes

**Severity**: CRITICAL

**Symptom**: Neo4j queries fail with connection error. The workflow node cannot reach the Neo4j instance despite correct credentials.

**Root Cause**: Neo4j's native protocol (`bolt://`) requires a dedicated driver and TCP connection. n8n's HTTP Request node can only make HTTP/HTTPS calls. Using `bolt://localhost:7687` in an HTTP Request node will always fail.

**Solution**:
Use Neo4j's HTTP API instead of the Bolt protocol:
```
# WRONG (Bolt protocol):
bolt://localhost:7687

# CORRECT (HTTP Query API for Aura):
https://<instance-id>.databases.neo4j.io/db/neo4j/query/v2

# Authentication: Basic Auth (neo4j:<password>)
# Method: POST
# Content-Type: application/json
# Body:
{
  "statements": [{"statement": "MATCH (n) RETURN count(n) AS count"}]
}
```

**Prevention**: When using Neo4j from workflow engines that only support HTTP, always use the HTTP API, never the Bolt protocol.

---

### FIX-78: Neo4j tx/commit Returns 403 on Aura

**Severity**: CRITICAL

**Symptom**: Neo4j transaction endpoint (`/db/neo4j/tx/commit`) returns 403 Forbidden on Neo4j Aura.

**Root Cause**: Neo4j Aura (managed cloud) does not support the legacy transaction endpoint. The newer Query API (`/db/neo4j/query/v2`) must be used instead.

**Solution**:
```
# WRONG (legacy transaction API):
POST https://<host>/db/neo4j/tx/commit

# CORRECT (Query API v2):
POST https://<host>/db/neo4j/query/v2
Content-Type: application/json
Authorization: Basic <base64(neo4j:password)>

{
  "statements": [
    {"statement": "UNWIND $rows AS row MERGE (d:Document {id: row.id}) SET d.title = row.title",
     "parameters": {"rows": [...]}}
  ]
}
```

**Prevention**: For Neo4j Aura, always use `/db/neo4j/query/v2`. The transaction endpoints are not available on managed instances.

---

### FIX-79: Sequential Neo4j Statements Are 100x Slower

**Severity**: IMPORTANT

**Symptom**: Neo4j data ingestion runs extremely slowly. Ingesting 1,000 documents takes 30+ minutes.

**Root Cause**: Each document is inserted with an individual Cypher statement. Each statement incurs network round-trip and transaction overhead. With 1,000 documents, that is 1,000 HTTP requests.

**Solution**:
Use UNWIND for bulk operations:
```cypher
-- WRONG (1 request per document):
CREATE (d:Document {id: '1', title: 'Doc 1'})
CREATE (d:Document {id: '2', title: 'Doc 2'})
-- ... 998 more requests

-- CORRECT (1 request for all documents):
UNWIND $rows AS row
MERGE (d:Document {id: row.id})
SET d.title = row.title, d.content = row.content
```

Send all rows as a parameter:
```python
batch_size = 500
for i in range(0, len(documents), batch_size):
    batch = documents[i:i+batch_size]
    payload = {
        "statements": [{
            "statement": "UNWIND $rows AS row MERGE (d:Document {id: row.id}) SET d += row",
            "parameters": {"rows": batch}
        }]
    }
    requests.post(neo4j_url, json=payload, auth=(user, password))
```

**Prevention**: Always use UNWIND with parameterized batches for bulk operations. Set batch size to 500 documents per request.

---

## Category 6: SQL Database (Supabase/PostgreSQL)

---

### FIX-08: Credential Missing in Live Workflow

**Severity**: CRITICAL

**Symptom**: Quantitative pipeline returns 500 with "Credential with ID 'cH96...' not found". The PostgreSQL node cannot connect to Supabase.

**Root Cause**: The workflow was exported from one environment and imported into another. The credential ID embedded in the workflow JSON does not exist in the target environment's credential store.

**Solution**:
1. Create the PostgreSQL credential in the target n8n instance.
2. Note the new credential ID.
3. Update the workflow JSON to reference the new ID:
```python
def remap_credential(workflow, old_id, new_id, cred_type="postgres"):
    json_text = json.dumps(workflow)
    json_text = json_text.replace(old_id, new_id)
    return json.loads(json_text)
```

**Prevention**: Include credential creation and remapping in your deployment script. Never assume credential IDs are portable between environments.

---

### FIX-69: Credential ID Mismatch -- Schema Introspection Returns 0 Rows

**Severity**: CRITICAL

**Symptom**: Quantitative pipeline's Schema Introspection node returns 0 rows. SQL generation has no schema context and produces incorrect queries.

**Root Cause**: The PostgreSQL credential ID in the workflow (`cH96...`) did not match the working credential (`b44av...`). The node silently used a non-existent or misconfigured credential, returning an empty result instead of an error.

**Solution**:
1. Identify the working credential ID by testing in the n8n UI.
2. Update all Postgres nodes to use the correct credential:
```python
# Find all nodes using postgres credentials
for node in workflow['nodes']:
    if node.get('credentials', {}).get('postgres'):
        node['credentials']['postgres']['id'] = 'CORRECT_ID'
```
3. Verify schema introspection returns table definitions after the fix.

**Prevention**: After any deployment, verify that schema introspection queries return data. A 0-row result from schema queries is always a credential or configuration error, never a data issue.

---

### FIX-70: tenant_id Mismatch -- SQL Returns 0 Rows Despite Correct Query

**Severity**: CRITICAL

**Symptom**: SQL query is syntactically correct and references the right table and column. But it returns 0 rows. Manual testing in a SQL client confirms data exists.

**Root Cause**: The query used `tenant_id = 'default'` but the evaluation data was ingested with `tenant_id = 'benchmark'`. Multi-tenant databases silently return empty results when the tenant filter does not match.

**Solution**:
1. Verify the correct tenant_id:
```sql
SELECT DISTINCT tenant_id FROM financials;
-- Should show: 'benchmark' (for eval data)
```
2. Update the SQL generation prompt to always include the correct tenant_id:
```
Always add: WHERE tenant_id = 'benchmark'
```
3. Or inject tenant_id in the SQL Validator as a post-processing step.

**Prevention**: Always explicitly document and configure the tenant_id. Include it in the schema context provided to the LLM. Add a validation check that rejects SQL without a tenant_id filter.

---

## Category 7: Pipeline Logic & Orchestration

---

### FIX-11: Init and ACL Node Multi-Format Support

**Severity**: IMPORTANT

**Symptom**: Graph pipeline fails when called by the Orchestrator but works when called directly via webhook.

**Root Cause**: The Init node expected a specific input format (direct webhook body). When called from the Orchestrator, the input format was different (wrapped in orchestrator metadata).

**Solution**:
```javascript
// Handle both direct webhook and orchestrator calls
const input = $input.first().json;
const query = input.query || input.task_query || input.body?.query;

if (!query) {
  throw new Error('No query found in input. Expected: query, task_query, or body.query');
}
```

**Prevention**: Pipeline init nodes should always handle multiple input formats. Use a cascade of field lookups to find the query regardless of how the pipeline is invoked.

---

### FIX-34: executeWorkflow Returns Empty When Sub-Workflow Uses respondToWebhook

**Severity**: CRITICAL

**Symptom**: Orchestrator returns 200 with empty body. The sub-pipelines (Standard, Graph, Quant) all work correctly when called individually.

**Root Cause**: The Orchestrator used `executeWorkflow` nodes to call sub-pipelines. But those sub-pipelines end with `respondToWebhook` nodes, which send the HTTP response directly to the original client. The `respondToWebhook` does NOT return data back to the parent `executeWorkflow` node. Result: the parent receives `data.main: [[]]` (empty).

**Solution**:
Replace all `executeWorkflow` nodes with `httpRequest` nodes that POST to the sub-pipeline's webhook URL:
```json
{
  "type": "n8n-nodes-base.httpRequest",
  "parameters": {
    "url": "={{ $json.pipeline_url }}/webhook/<path>",
    "method": "POST",
    "body": {
      "query": "={{ $json.task_query }}"
    },
    "timeout": 30000,
    "options": {
      "response": { "response": { "fullResponse": true } }
    }
  }
}
```

**Prevention**: NEVER use `executeWorkflow` for workflows that end with `respondToWebhook`. These two mechanisms are incompatible. Use `httpRequest` to call sub-pipelines as HTTP endpoints.

---

### FIX-37: Context-Rich Questions Sent to SQL Pipeline

**Severity**: CRITICAL

**Symptom**: Questions that include context passages are routed to the Quantitative (SQL) pipeline, which tries to generate SQL queries from narrative text. This always fails.

**Root Cause**: The intent classifier did not detect that the question contained embedded context. Context-based questions should be routed to the Standard or Graph pipeline for passage-based reasoning, not to the SQL pipeline.

**Solution**:
Add format detection to the classifier:
```javascript
function detectQuestionFormat(input) {
  // Context-based questions contain passages
  if (input.context && input.context.length > 100) {
    return 'context_reasoning';  // Route to Standard pipeline
  }

  // SQL questions are about metrics, numbers, aggregation
  if (/revenue|profit|eps|margin|growth|percentage/i.test(input.query)) {
    return 'quantitative';  // Route to Quant pipeline
  }

  return 'standard';
}
```

**Prevention**: Always check for the presence of context/passages in the input before routing to SQL-based pipelines. SQL pipelines should only receive questions about structured data.

---

### FIX-64: Redis Lock Nodes Prevent Workflow Startup

**Severity**: CRITICAL

**Symptom**: Workflow activation fails with HTTP 500. The workflow contains Redis-based locking nodes but no Redis instance is available.

**Root Cause**: Ingestion workflows used Redis-based distributed locks to prevent concurrent processing. On environments without Redis (SQLite mode), these nodes fail on startup and prevent the entire workflow from activating.

**Solution**:
1. Remove Redis lock nodes from workflows running on Redis-less environments.
2. If locking is needed, use a database-based lock:
```sql
-- Simple advisory lock in PostgreSQL
SELECT pg_advisory_lock(12345);
-- ... do work ...
SELECT pg_advisory_unlock(12345);
```
3. Or use file-based locks for single-instance deployments.

**Prevention**: Do not use Redis-dependent nodes in workflows that must run on environments without Redis. Use environment-appropriate locking mechanisms.

---

### FIX-75: LLM Nodes Switched to Proxy for Centralized Control

**Severity**: IMPORTANT

**Symptom**: Changing the LLM model requires updating 6+ nodes across 3 workflows. Model changes are error-prone and inconsistent.

**Root Cause**: Each LLM node was configured with its own API URL and model name, hardcoded in the workflow JSON. Changing the model required finding and updating every node individually.

**Solution**:
Route all LLM calls through a centralized proxy (e.g., LiteLLM):
```
# All nodes point to the same proxy URL:
LLM_PROXY_URL=https://your-litellm-proxy.example.com/v1/chat/completions

# Model selection is handled by the proxy:
# model: "default"  -> routes to Llama 70B
# model: "fast"     -> routes to Gemma 27B
# model: "smart"    -> routes to Qwen 235B
```

**Prevention**: Never hardcode model names and API URLs in individual workflow nodes. Use a proxy that centralizes model routing and makes switching models a single configuration change.

---

## Category 8: Evaluation & Testing

---

### FIX-36: Phase Filtering -- Wrong Questions in Wrong Phase

**Severity**: CRITICAL

**Symptom**: Phase 1 evaluation gates fail even though all Phase 1 questions are answered correctly. Phase 1 accuracy shows 68% instead of the expected 85%.

**Root Cause**: The evaluation script counted ALL questions (including Phase 2 dataset questions like FinQA and MuSiQue) in the Phase 1 calculation. Phase 2 questions are harder and dragged down the Phase 1 score.

**Solution**:
```python
def is_phase1_question(question_id):
    """Filter out Phase 2+ questions from Phase 1 calculation."""
    phase2_markers = ['musique', 'finqa', 'phase2', 'tatqa', 'wikitable']
    return not any(marker in question_id.lower() for marker in phase2_markers)

# Apply filter
phase1_results = [r for r in all_results if is_phase1_question(r['id'])]
phase1_accuracy = sum(1 for r in phase1_results if r['pass']) / len(phase1_results)
```

**Prevention**: Each evaluation phase must filter to only its own questions. Never mix phases in accuracy calculations. Use naming conventions in question IDs that make filtering easy.

---

### FIX-38: Context Field Parsing Breaks Multi-Hop Questions

**Severity**: CRITICAL

**Symptom**: Multi-hop questions (2WikiMultiHopQA) fail because the context arrives as a malformed string instead of a structured array.

**Root Cause**: The `load_questions()` function used a JSON format that did not match the multi-hop context structure. Multi-hop questions have nested context (multiple passages with titles), which was being flattened into a single string.

**Solution**:
```python
def load_context(question):
    """Handle all context formats: string, list, dict, nested."""
    ctx = question.get('context', '')

    if isinstance(ctx, str):
        return ctx

    if isinstance(ctx, list):
        # List of passages or [title, text] pairs
        parts = []
        for item in ctx:
            if isinstance(item, list) and len(item) == 2:
                parts.append(f"{item[0]}: {item[1]}")
            elif isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(item.get('text', str(item)))
        return '\n\n'.join(parts)

    if isinstance(ctx, dict):
        return json.dumps(ctx, indent=2)

    return str(ctx)
```

**Prevention**: Always implement multi-format context parsing. Different datasets use different context structures. The parser must handle strings, lists, dicts, and nested formats.

---

### FIX-39: Permanent Data Validator for Evaluation Datasets

**Severity**: CRITICAL

**Symptom**: Evaluation runs fail mid-execution because a question has missing fields, wrong types, or incompatible format.

**Root Cause**: No validation was performed on questions before sending them to pipelines. A single malformed question could crash the entire evaluation batch.

**Solution**:
```python
def validate_question(question, index):
    """Validate question before evaluation. Returns (valid, errors)."""
    errors = []

    if 'query' not in question and 'question' not in question:
        errors.append(f"Q{index}: Missing query/question field")

    if 'expected_answer' not in question:
        errors.append(f"Q{index}: Missing expected_answer")

    if 'pipeline' not in question:
        errors.append(f"Q{index}: Missing pipeline type")

    query = question.get('query', question.get('question', ''))
    if not query or len(query.strip()) < 5:
        errors.append(f"Q{index}: Query too short or empty")

    return len(errors) == 0, errors

# Pre-flight validation
invalid = []
for i, q in enumerate(questions):
    valid, errors = validate_question(q, i)
    if not valid:
        invalid.extend(errors)

if invalid:
    print(f"BLOCKED: {len(invalid)} validation errors")
    for e in invalid:
        print(f"  {e}")
    sys.exit(1)
```

**Prevention**: Always validate evaluation datasets before running them through pipelines. Fail fast on malformed data rather than discovering errors mid-execution.

---

### FIX-76: Evaluation Script Duplicates Questions

**Severity**: CRITICAL

**Symptom**: Phase 3 evaluation shows 10,700 extra questions. The total count is 21,400 instead of the expected 10,700.

**Root Cause**: The Phase 3 loader in `run-eval-parallel.py` loaded questions from multiple dataset files, and the Orchestrator questions were mirrored (duplicated) in the loading logic. Each question appeared twice.

**Solution**:
```python
def load_phase3_questions():
    questions = []
    seen_ids = set()

    for file in dataset_files:
        for q in load_file(file):
            if q['id'] not in seen_ids:
                seen_ids.add(q['id'])
                questions.append(q)
            # else: skip duplicate

    return questions
```

**Prevention**: Always deduplicate questions by ID after loading from multiple sources. Include a seen-IDs set to prevent duplicates.

---

### FIX-77: Hardcoded Timeouts Override Pipeline-Specific Settings

**Severity**: IMPORTANT

**Symptom**: Quantitative pipeline times out at 45 seconds, but it legitimately needs 90-120 seconds (3 LLM calls per question).

**Root Cause**: `run-eval-parallel.py` had a hardcoded 45-second timeout that overrode the pipeline-specific timeout settings from the source module (Standard: 90s, Quant: 120s, Orchestrator: 180s).

**Solution**:
```python
PIPELINE_TIMEOUTS = {
    'standard': 90,
    'graph': 90,
    'quantitative': 120,
    'orchestrator': 180
}

timeout = PIPELINE_TIMEOUTS.get(pipeline_type, 90)
```

**Prevention**: Never hardcode timeouts. Use pipeline-specific timeout configurations. The Quantitative pipeline makes 2-3 LLM calls per question and needs significantly more time than Standard.

---

## Category 9: VM & Server Infrastructure

---

### FIX-25: Zombie Claude Code Sessions Consume All RAM

**Severity**: IMPORTANT

**Symptom**: VM becomes sluggish. Free memory drops below 100 MB. Swap usage hits 100%. Subsequent processes fail with OOM.

**Root Cause**: Old Claude Code sessions (from previous SSH connections) stay in memory as zombie processes. Each session consumes ~280 MB. On a 969 MB RAM VM, 3 zombie sessions exhaust all memory.

**Solution**:
At the start of every session:
```bash
# Find zombie sessions
ps aux | grep claude | grep -v grep

# Kill old sessions (keep only the current one)
kill -9 <old_pids>

# Free filesystem cache
sync && echo 3 | sudo tee /proc/sys/vm/drop_caches
```

**Prevention**: Always kill old sessions at the start of a new session. Add this to your session startup script.

---

### FIX-40: OOM Cascade -- Zombies to PG Timeout to Webhooks 404

**Severity**: CRITICAL

**Symptom**: All webhooks return 404 or 503. Health check returns 200. PostgreSQL connections time out. Swap at 100%.

**Root Cause**: Cascade failure: zombie processes consume RAM -> swap fills -> PostgreSQL connections time out -> n8n cannot query workflow_entity table -> webhooks are not registered -> all requests return 404. The healthz endpoint still returns 200 because it does not depend on PostgreSQL.

**Solution**:
1. Kill all zombie processes (git pack-objects, old eval scripts, old Claude sessions).
2. Clean execution_entity table (stuck executions add memory pressure).
3. Full service restart (`docker compose down && docker compose up -d`).
4. Wait 65-110 seconds for full startup.

**Prevention**:
- Kill zombie processes at session start.
- Monitor swap usage (`free -m`). If swap > 800 MB, investigate immediately.
- Clean stuck executions regularly.

---

### FIX-42: Stuck Executions Block All Webhook Responses

**Severity**: CRITICAL

**Symptom**: Webhooks accept HTTP POST requests but NEVER respond. curl hangs indefinitely and eventually times out with code 000. Health check returns 200. Logs show "Execution is already being resumed" spam.

**Root Cause**: 79+ executions stuck in `new` or `running` status in the database. On startup, n8n tries to resume ALL stuck executions, consuming all processing capacity. New webhook requests are accepted but queued behind the stuck execution resume attempts, which never complete.

**Solution**:
```bash
# 1. Stop the workflow engine
docker stop n8n-container

# 2. Delete ALL stuck executions
docker exec postgres-container psql -U n8n -d n8n -t -A -c \
  "DELETE FROM execution_entity WHERE status IN ('new', 'running', 'waiting', 'crashed');"

# 3. Restart
docker start n8n-container

# 4. Wait for full startup (webhooks register after workflow activation)
sleep 35

# 5. Verify webhooks respond
curl -s -o /dev/null -w "%{http_code}" -X POST "http://localhost:5678/webhook/<path>" \
  -H "Content-Type: application/json" -d '{"query":"health check"}'
```

**Prevention**:
- This is the #1 cause of "webhooks accept but never respond."
- When you see this symptom, ALWAYS check for stuck executions first.
- Set up a cron job to clean old executions:
```bash
# Clean executions older than 24 hours
0 * * * * docker exec postgres psql -U n8n -d n8n -c \
  "DELETE FROM execution_entity WHERE status IN ('new','running') AND \"startedAt\" < NOW() - INTERVAL '24 hours';"
```

---

### FIX-43: Workflows Active But Zero Webhooks Registered

**Severity**: IMPORTANT

**Symptom**: `SELECT active FROM workflow_entity` shows `true` for all workflows. But no webhooks are registered. All webhook calls return 404.

**Root Cause**: Missing credentials silently prevent webhook registration. When a workflow is activated, n8n validates all credentials. If any credential is missing or invalid, the workflow is marked as active in the database, but its webhooks are NOT registered. No error is logged.

**Solution**:
1. Check credentials for each workflow:
```bash
# List all credentials in n8n
docker exec postgres psql -U n8n -d n8n -c \
  "SELECT id, name, type FROM credentials_entity;"
```
2. Verify that all credential IDs referenced in workflows exist.
3. Re-create any missing credentials.
4. Deactivate and reactivate each workflow.

**Prevention**: After any deployment, verify that webhooks are actually registered, not just that workflows are marked as active. Test each webhook with a health check call.

---

### FIX-44: Partial Workflow Activation After Restart with Stuck Executions

**Severity**: CRITICAL

**Symptom**: After a restart, only some workflows activate. Others remain inactive despite being configured as active.

**Root Cause**: If stuck executions exist during shutdown, n8n may not cleanly deactivate all workflows. On restart, it tries to resume stuck executions first, which can prevent other workflows from activating properly.

**Solution**:
1. Clean stuck executions BEFORE restarting.
2. Then restart the workflow engine.
3. Verify all expected workflows are active:
```bash
docker exec postgres psql -U n8n -d n8n -c \
  "SELECT id, name, active FROM workflow_entity WHERE active = true;"
```

**Prevention**: Always clean stuck executions before any restart operation.

---

### FIX-45: False Positive Monitoring -- Timeout Too Short for RAG Pipelines

**Severity**: IMPORTANT

**Symptom**: Monitoring script reports webhooks as DOWN, but they are actually working. Manual curl confirms the webhook responds correctly.

**Root Cause**: The monitoring script used a 30-second timeout. RAG pipelines (especially Quantitative and Orchestrator) need 40-120 seconds to respond because they make multiple LLM calls. The monitoring script times out before the pipeline can respond.

**Solution**:
Set monitoring timeouts appropriately:
```bash
# WRONG: 30s timeout
curl -s --max-time 30 ...

# CORRECT: Pipeline-specific timeouts
STANDARD_TIMEOUT=60
GRAPH_TIMEOUT=90
QUANT_TIMEOUT=120
ORCHESTRATOR_TIMEOUT=180
```

**Prevention**: Monitoring timeouts must be longer than the worst-case pipeline response time. Use pipeline-specific timeouts.

---

### FIX-46: Stuck Execution Cleanup Without Full Restart

**Severity**: IMPORTANT

**Symptom**: Webhooks hang but only a few executions are stuck (5 or fewer).

**Root Cause**: A small number of stuck executions can still block webhook responses if they occupy processing slots.

**Solution**:
Clean the stuck executions without restarting:
```bash
docker exec postgres psql -U n8n -d n8n -c \
  "DELETE FROM execution_entity WHERE status IN ('new', 'running');"
```
If webhooks resume after cleanup: done. If they do not resume: a full restart is needed (FIX-47).

**Prevention**: Try cleanup-only first. Escalate to full restart only if cleanup is insufficient.

---

### FIX-47: Cleanup Alone Insufficient -- Full Restart Required

**Severity**: CRITICAL

**Symptom**: After cleaning stuck executions, webhooks still time out. Health check returns 200 but no webhook responds.

**Root Cause**: When the webhook handler's internal state is corrupted (e.g., from an OOM event), simply cleaning the database is not enough. The in-memory webhook registry needs to be rebuilt, which only happens on a full restart.

**Solution**:
```bash
# Full restart sequence
docker compose down
sleep 5
docker compose up -d
sleep 65  # Wait for full initialization
# Verify all webhooks
```

**Prevention**: If cleanup-only does not restore webhooks within 60 seconds, proceed to full restart immediately. Do not waste time debugging further.

---

## Category 10: API & Credential Management

---

### FIX-06: Credentials Missing After Environment Migration

**Severity**: CRITICAL

**Symptom**: Workflow executes but all credential-dependent nodes fail with "Credential not found".

**Root Cause**: Credentials are stored in the database, not in the workflow JSON. When migrating a workflow from one n8n instance to another (cloud to Docker, Docker to HF Space), credential references become orphaned.

**Solution**:
1. Export credential list from source: document credential names, types, and IDs.
2. Create credentials in target environment (UI or REST API).
3. Remap credential IDs in workflow JSON:
```python
credential_map = {
    "old_id_1": "new_id_1",
    "old_id_2": "new_id_2"
}

for node in workflow['nodes']:
    for cred_type, cred_ref in node.get('credentials', {}).items():
        if cred_ref.get('id') in credential_map:
            cred_ref['id'] = credential_map[cred_ref['id']]
```

**Prevention**: Maintain a credential mapping document. Include credential creation in your deployment automation.

---

### FIX-27: REST API Returns 401 -- No API Key Configured

**Severity**: IMPORTANT

**Symptom**: All REST API calls return `{"message":"'X-N8N-API-KEY' header required"}`.

**Root Cause**: The n8n instance has the public API enabled but no API key configured. Without a key, all API calls are rejected.

**Solution**:
Use alternative access methods:
1. **Database direct**: Query PostgreSQL for workflow information.
2. **Cookie auth**: Login via `/rest/login` and use the session cookie.
3. **Create an API key**: In the n8n UI, go to Settings > API Keys.

```python
# Cookie authentication method
import requests

session = requests.Session()
login_response = session.post(f"{n8n_url}/rest/login", json={
    "emailOrLdapLoginId": "user@example.com",
    "password": "password"
})
# Session cookie is now stored in `session`
# All subsequent calls use the cookie automatically
workflows = session.get(f"{n8n_url}/rest/workflows")
```

**Prevention**: Choose one authentication method and document it. Cookie auth is the most reliable fallback when API keys are not configured.

---

### FIX-52: Hardcoded API Keys Expire and Cause 401 Errors

**Severity**: CRITICAL

**Symptom**: Workflows that worked yesterday now return 401 from external APIs (OpenRouter, Jina, Cohere).

**Root Cause**: API keys were hardcoded directly in workflow JSON. When keys are rotated or expire, every workflow containing the old key breaks simultaneously.

**Solution**:
1. Remove all hardcoded keys from workflow JSON.
2. Use environment variables or n8n credentials:
```json
// WRONG: Hardcoded key
"headers": {
  "Authorization": "Bearer sk-or-v1-abc123..."
}

// CORRECT: Environment variable
"headers": {
  "Authorization": "Bearer ={{ $env.OPENROUTER_API_KEY }}"
}

// ALSO CORRECT: n8n credential
"credentials": {
  "httpHeaderAuth": { "id": "credential_id", "name": "OpenRouter" }
}
```
3. When using `$env`, ensure FIX-63 is applied.

**Prevention**:
- Never commit API keys in workflow JSON.
- Use grep to scan for leaked keys before committing:
```bash
git diff --cached | grep -iE 'sk-or-|pcsk_|jina_|Bearer [a-zA-Z0-9]+'
```

---

### FIX-53: Credential ID Mismatch After Fresh Import

**Severity**: CRITICAL

**Symptom**: Fresh n8n instance. Workflows imported. All credential-dependent nodes fail with "Credential with ID 'xxx' does not exist".

**Root Cause**: Workflow JSON contains credential IDs from the source environment. These IDs do not exist in the fresh instance.

**Solution**:
Post-import credential setup script:
```python
def setup_credentials_and_remap(n8n_url, session, workflows):
    """Create credentials and remap IDs in all workflows."""

    # 1. Create required credentials
    credentials_needed = [
        {"name": "OpenRouter", "type": "httpHeaderAuth",
         "data": {"name": "Authorization", "value": f"Bearer {os.environ['OPENROUTER_API_KEY']}"}},
        {"name": "Jina", "type": "httpHeaderAuth",
         "data": {"name": "Authorization", "value": f"Bearer {os.environ['JINA_API_KEY']}"}},
        {"name": "PostgreSQL", "type": "postgres",
         "data": {"host": os.environ['PG_HOST'], "port": 5432,
                  "database": "postgres", "user": "postgres",
                  "password": os.environ['PG_PASSWORD']}}
    ]

    id_map = {}
    for cred in credentials_needed:
        resp = session.post(f"{n8n_url}/rest/credentials", json=cred)
        new_id = resp.json()['id']
        id_map[cred['name']] = new_id

    # 2. Remap all credential references in workflows
    for wf in workflows:
        for node in wf.get('nodes', []):
            for cred_type, cred_ref in node.get('credentials', {}).items():
                if cred_ref.get('name') in id_map:
                    cred_ref['id'] = id_map[cred_ref['name']]
        # 3. Update workflow
        session.patch(f"{n8n_url}/rest/workflows/{wf['id']}", json=wf)
```

**Prevention**: Credential setup must be the FIRST step after importing workflows into any new environment.

---

### FIX-73: API Key Returns 401 -- Use Cookie Auth Instead

**Severity**: IMPORTANT

**Symptom**: `X-N8N-API-KEY` header returns 401 even when the key looks correct.

**Root Cause**: The API key may be incorrectly configured, expired, or the n8n instance may not support API key authentication (community edition limitations).

**Solution**:
Use cookie authentication as a reliable fallback:
```python
import urllib.request
import http.cookiejar
import json

def n8n_login(base_url, email, password):
    """Login using cookie auth (works when API keys fail)."""
    cj = http.cookiejar.MozillaCookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cj)
    )

    data = json.dumps({
        "emailOrLdapLoginId": email,
        "password": password
    }).encode('utf-8')

    req = urllib.request.Request(
        f"{base_url}/rest/login",
        data=data,
        headers={'Content-Type': 'application/json'}
    )

    response = opener.open(req)
    return opener  # Use this opener for all subsequent requests
```

**Note**: On HF Spaces, curl may fail due to HTTP/2 + proxy interactions. Python's `urllib.request` with `MozillaCookieJar` is the most reliable method.

**Prevention**: Always implement cookie auth as a fallback mechanism. Do not rely solely on API key authentication.

---

### FIX-62: Jina and Cohere Credentials Missing on HF Space

**Severity**: IMPORTANT

**Symptom**: Embedding and reranking nodes fail after HF Space rebuild. Other credentials work.

**Root Cause**: Credential restore scripts only created OpenRouter and PostgreSQL credentials. Jina and Cohere credentials were not included in the restore list.

**Solution**:
Add all required credentials to the restore script:
```python
ALL_CREDENTIALS = [
    {"name": "OpenRouter", "type": "httpHeaderAuth", "env_key": "OPENROUTER_API_KEY"},
    {"name": "Jina", "type": "httpHeaderAuth", "env_key": "JINA_API_KEY"},
    {"name": "Cohere", "type": "httpHeaderAuth", "env_key": "COHERE_API_KEY"},
    {"name": "PostgreSQL", "type": "postgres", "env_key": "DATABASE_URL"},
    {"name": "Pinecone", "type": "httpHeaderAuth", "env_key": "PINECONE_API_KEY"},
    {"name": "Neo4j", "type": "httpBasicAuth", "env_key": "NEO4J_PASSWORD"},
]
```

**Prevention**: Maintain a complete list of ALL credentials used across all workflows. Update the list whenever a new integration is added.

---

# Part III: Recurring Patterns

These are patterns that appear repeatedly across sessions. Recognizing them saves hours of debugging.

---

### Pattern P-01: Fix Applied But Runtime Uses Old Code

**Frequency**: Occurs in almost every debugging session involving n8n.

**Symptom**: Code modified via REST API. GET confirms the change is stored. But the runtime behavior does not change.

**Root Cause**: n8n caches compiled Code nodes in memory. A PUT/PATCH alone does not trigger recompilation.

**Solution**: Always perform the deactivate-reactivate cycle after any code update (FIX-21).

**Time Lost Without This Knowledge**: 30-60 minutes per occurrence.

---

### Pattern P-02: "[object Object]" in Response Output

**Frequency**: Common when adding error handling to JavaScript nodes.

**Symptom**: Response contains `[object Object]` instead of meaningful error details.

**Root Cause**: JavaScript concatenates an Error object with a string, producing `[object Object]`.

**Solution**:
```javascript
// WRONG:
const message = "Error: " + error;

// CORRECT:
const message = "Error: " + (typeof error === 'object' ? JSON.stringify(error) : error);
```

**Prevention**: Always use typeof check before string concatenation with any variable that might be an object.

---

### Pattern P-03: SQL Valid But Returns Wrong Result

**Frequency**: Very common with free-tier LLMs.

**Symptom**: SQL executes without error but returns the wrong value. The WHERE clause matches the wrong record.

**Root Cause**: LLM generates exact-match WHERE clauses that fail on entity name variants. Example: `company_name = 'TechVision'` when the database contains `'TechVision Inc'`.

**Solution**:
1. Use `ILIKE '%keyword%'` instead of `= 'exact match'`.
2. Include 3-5 sample data rows in the LLM prompt.
3. Provide SQL templates for common query patterns.
4. Verify tenant_id is correct (FIX-70).

**Prevention**: Always include sample data in SQL generation prompts. The LLM needs to see actual values to generate correct WHERE clauses.

---

### Pattern P-04: HuggingFace Dataset Not Found

**Frequency**: Occurred 6 out of 11 times in a single session.

**Symptom**: `Invalid username or password` or 404 when downloading datasets.

**Root Cause**: HuggingFace dataset IDs change frequently (redirects, renames, namespace changes). IDs copied from documentation may be outdated.

**Solution**: Always verify dataset IDs with the HuggingFace API before adding them to configuration.

**Prevention**: Treat dataset IDs as volatile. Verify before each use, or pin to specific commit hashes.

---

### Pattern P-05: Workflow Import Fails on Fresh Database

**Frequency**: Every fresh deployment.

**Symptom**: `SQLITE_CONSTRAINT: FOREIGN KEY constraint failed` on import.

**Root Cause**: Exported workflow JSON contains foreign keys to the source database.

**Solution**: Strip FK fields before import (FIX-18).

**Prevention**: Pre-import cleanup is mandatory for all workflows.

---

### Pattern P-06: $env Inaccessible in Code Nodes

**Frequency**: Every deployment on n8n 2.7.4+.

**Symptom**: `access to env vars denied` in Code nodes.

**Root Cause**: Task Runners sandbox Code nodes. `process.env` is blocked. `$env.VAR` works only with `N8N_BLOCK_ENV_ACCESS_IN_NODE=false`.

**Solution**: Set the flag (FIX-63). Use `$env.VAR` (not `process.env`).

**Prevention**: Flag must be in every deployment configuration.

---

### Pattern P-07: Quick Test Passes, Full Eval Fails

**Frequency**: Common source of false confidence.

**Symptom**: 5/5 PASS in smoke test. Low accuracy in full evaluation (50+ questions).

**Root Cause**: Smoke test questions are intentionally easy (some have empty expected values, meaning any answer passes). Full evaluation has precise expected values.

**Solution**: Always validate with a full evaluation (minimum 50 questions) before declaring a fix successful.

**Prevention**: Never trust quick-test alone. It is a sanity check, not a performance measurement.

---

### Pattern P-08: Webhook Path Typed from Memory

**Frequency**: Almost EVERY session. The single most common mistake.

**Symptom**: 404 "webhook not registered" or VALIDATION_ERROR.

**Root Cause**: Webhook path typed from memory instead of copied from documentation. Paths contain UUIDs that are impossible to remember correctly.

**Solution**: ALWAYS copy the webhook path from the reference documentation.

**Prevention**: Add automatic pre-flight checks to evaluation scripts. Never rely on human memory for UUID paths.

---

### Pattern P-09: n8n REST API 401

**Frequency**: Occurs whenever someone tries to use the REST API without checking authentication.

**Symptom**: `'X-N8N-API-KEY' header required`.

**Root Cause**: No API key configured. API is enabled but without a key.

**Solution**: Use database direct access or cookie auth (FIX-27, FIX-73).

**Prevention**: Always verify authentication method before making API calls.

---

### Pattern P-10: HTTP 200 But Empty Response Body

**Frequency**: Common with Orchestrator and custom workflows.

**Symptom**: HTTP 200 but response body is empty.

**Root Cause**: Workflow has no "Respond to Webhook" node, or the node is misconfigured.

**Solution**: Verify every webhook workflow ends with a properly configured Respond node.

---

### Pattern P-11: Task Runner Executes Old Code Despite Full Restart

**Frequency**: Discovered in Session 25. A fundamental architecture issue.

**Symptom**: Code updated in database. Container restarted. But execution still uses old code.

**Root Cause**: Task Runner (subprocess) caches compiled JavaScript. Even container restart does not guarantee cache invalidation.

**Solution**: Never modify workflows on a VM-hosted n8n. Use a fresh instance (HF Space) where each deployment starts from a clean state.

**Prevention**: Architectural rule: production modifications only on fresh/ephemeral instances.

---

# Part IV: Anti-Patterns That Cause 80% of Failures

These are the mistakes that cause the vast majority of debugging time. Eliminate them and you eliminate most of your issues.

| # | Anti-Pattern | Frequency | Impact | Prevention |
|---|-------------|-----------|--------|------------|
| AP-01 | Typing webhook paths from memory | EVERY session | 404 errors | Always copy from documentation |
| AP-02 | Using `question` instead of `query` as field name | FREQUENT | Silent failures | Standardize on `query` |
| AP-03 | Calling REST API without verifying auth method | FREQUENT | 401 errors | Check auth before calling |
| AP-04 | Re-debugging a problem that is already solved | OCCASIONAL | Hours wasted | Search the Fixes Library first |
| AP-05 | Modifying multiple nodes at once | OCCASIONAL | Cannot isolate cause | One fix per iteration |
| AP-06 | Patching nodes[] but not activeVersion.nodes[] | EVERY fix | Changes have no effect | Always patch BOTH arrays |
| AP-07 | Using $env without the unblock flag | CRITICAL | All pipelines fail | Verify entrypoint has the flag |
| AP-08 | Deploying without N8N_BLOCK_ENV_ACCESS_IN_NODE=false | CRITICAL | Everything breaks | Non-negotiable config |
| AP-09 | Using executeWorkflow with respondToWebhook sub-flows | CRITICAL | Empty responses | Use httpRequest instead |
| AP-10 | OpenRouter URL without /chat/completions | CRITICAL | HTML instead of JSON | Always use full URL |
| AP-11 | Mixing Phase 2 questions in Phase 1 evaluation | CRITICAL | Wrong accuracy scores | Filter by phase |
| AP-12 | Sending context-rich questions to SQL pipeline | CRITICAL | 100% failure rate | Detect format first |

### The One Rule That Prevents All Anti-Patterns

**Before acting, verify.** Check the documentation. Verify the path. Verify the field name. Verify the authentication. Verify the phase filter. Verification takes 30 seconds. Debugging takes 30 minutes.

---

# Part V: LLM Behavior Profiles & Resilience

## Production Model Profiles

### Llama 3.3 70B (via OpenRouter/Groq)

| Attribute | Detail |
|-----------|--------|
| **Best at** | SQL generation, multi-step reasoning, task planning |
| **Weak at** | Multi-table JOINs, fiscal period aggregation, entity name variants |
| **Rate limit** | ~20 req/min per API key (free tier) |
| **Timeout** | 60-90s recommended (25s is too short under load) |
| **JSON output** | Sometimes invalid (trailing commas, single quotes). Always parse with try/catch. |
| **SQL accuracy** | ~80% on single-table queries, ~50% on complex JOINs |

### Gemma 3 27B (via OpenRouter)

| Attribute | Detail |
|-----------|--------|
| **Best at** | Intent classification, routing, short structured responses |
| **Weak at** | Complex SQL (context window too short for long schemas) |
| **Rate limit** | ~20 req/min per API key (free tier) |
| **Speed** | ~2x faster than Llama 70B |
| **Context** | 8K tokens only -- problematic for large database schemas |

### Trinity Large (via OpenRouter)

| Attribute | Detail |
|-----------|--------|
| **Best at** | Entity extraction (NER), summaries, structured output |
| **Weak at** | Complex reasoning, SQL generation |
| **Rate limit** | ~20 req/min per API key |
| **Use case** | Graph RAG entity extraction and community summaries |

## LLM Resilience Strategies

| Strategy | How to Implement | Impact |
|----------|-----------------|--------|
| **Retry with backoff** | `maxTries: 3`, `waitBetweenTries: 8000ms` | Eliminates ~80% of 429 errors |
| **Continue on fail** | `continueOnFail: true` on HTTP nodes | Prevents single failure from crashing pipeline |
| **Model fallback chain** | Primary -> Fallback 1 -> Fallback 2 -> Template | Guarantees a response always |
| **Multi-key rotation** | 7 API keys across 3 accounts, round-robin | 7x throughput (20 -> 140 req/min) |
| **Template matching** | Bypass LLM for simple queries (metric + company + year) | +2 percentage points accuracy |
| **Static schema in prompt** | Precomputed compact schema, not dynamic introspection | Reduces tokens, improves SQL quality |
| **Sample data in prompt** | Include 3-5 real data rows with actual values | Anchors LLM expectations for WHERE clauses |

## Multi-Key Rotation Implementation

```python
import os
import time
from collections import defaultdict

class KeyRotator:
    def __init__(self):
        self.keys = []
        self.usage = defaultdict(int)
        self.last_used = defaultdict(float)

        # Load all available keys
        key_vars = [
            'OPENROUTER_API_KEY',
            'OPENROUTER_KEY_STANDARD',
            'OPENROUTER_KEY_GRAPH',
            'OPENROUTER_KEY_QUANTITATIVE',
            'OPENROUTER_KEY_ORCHESTRATOR',
            'OPENROUTER_KEY_PME',
            'OPENROUTER_KEY_ACCOUNT3',
        ]

        for var in key_vars:
            key = os.environ.get(var)
            if key:
                self.keys.append(key)

    def get_next_key(self):
        """Return the least-recently-used key."""
        if not self.keys:
            raise ValueError("No API keys configured")

        # Find key with oldest last-used timestamp
        best_key = min(self.keys, key=lambda k: self.last_used[k])
        self.usage[best_key] += 1
        self.last_used[best_key] = time.time()
        return best_key

# Usage:
rotator = KeyRotator()
api_key = rotator.get_next_key()
headers = {"Authorization": f"Bearer {api_key}"}
```

**Result**: 7 keys across 3 accounts increases aggregate throughput from ~20 req/min to ~140 req/min.

---

# Part VI: Database Gotchas Reference

## Pinecone

| Gotcha | Symptom | Fix |
|--------|---------|-----|
| Dimension mismatch | "expected 1024, got 1536" | Match embedding model to index dimension (FIX-12) |
| Wrong namespace | 0 results | Verify namespace name (case-sensitive) |
| Stale embeddings | Low relevance scores | Re-embed after data changes |
| Free tier limit | Upsert fails silently | Max 100K vectors on free tier |

## Neo4j Aura

| Gotcha | Symptom | Fix |
|--------|---------|-----|
| bolt:// in HTTP nodes | Connection refused | Use HTTPS Query API (FIX-07) |
| tx/commit endpoint | 403 Forbidden | Use /db/neo4j/query/v2 (FIX-78) |
| Sequential inserts | Extremely slow | Use UNWIND for bulk ops (FIX-79) |
| Missing auth | 401 | Use Basic Auth (neo4j:password) |
| Query timeout | 504 | Reduce UNWIND batch size to 500 |

## Supabase / PostgreSQL

| Gotcha | Symptom | Fix |
|--------|---------|-----|
| Wrong tenant_id | 0 results | Use 'benchmark', not 'default' (FIX-70) |
| Wrong port | Silent insert failures | Use port 5432 (session pooler), not 6543 (transaction pooler) |
| ILIKE needed | Wrong entity matched | Use ILIKE '%keyword%', not = 'exact' (Pattern P-03) |
| Connection pooler DDL | Table creation fails | Use MCP migration or direct connection for DDL |
| Missing FROM | Syntax error | PostgreSQL requires FROM clause (FIX-03) |

## General SQL for RAG

```sql
-- Most reliable query pattern for financial RAG:
SELECT metric_column
FROM financials
WHERE company_name ILIKE '%keyword%'
  AND fiscal_year = 2023
  AND period = 'FY'
  AND tenant_id = 'benchmark'
LIMIT 1;

-- Always verify data exists:
SELECT DISTINCT company_name, fiscal_year, period
FROM financials
WHERE tenant_id = 'benchmark'
ORDER BY company_name, fiscal_year;
```

---

# Part VII: Infrastructure & Performance

## Resource Constraints & Mitigation

### Low-RAM Environments (under 2 GB)

| Constraint | Mitigation |
|-----------|------------|
| 969 MB total RAM | Pilotage only, no execution workloads |
| ~280 MB per Claude Code session | Kill zombie sessions at start of each session |
| Swap fills to 100% | Triggers OOM cascade (FIX-40). Monitor with `free -m`. |
| git pack-objects | Can consume 500+ MB. Kill if memory-constrained. |

### Startup Sequence Timing

| Event | Time After Start |
|-------|-----------------|
| Container running | 0s |
| healthz returns 200 | 10-15s |
| REST API ready | 30-45s |
| Webhooks registered | 45-65s |
| Full operational | 65-110s |

### Concurrency Limits by Pipeline

| Pipeline | Safe Concurrency | Max Tested | Response Time |
|----------|-----------------|------------|---------------|
| Standard | 5 | 15 (100% success) | 5-29s |
| Graph | 3 | 5 (90% success) | 10-44s |
| Quantitative | 1 | 3 | 15-30s |
| Orchestrator | 1 | 1 | 20-45s |

### Recommended Delays Between Evaluation Questions

| Pipeline | Delay | Reason |
|----------|-------|--------|
| Standard | 3s | No LLM calls, pure retrieval |
| Graph | 5s | 1 LLM call for community synthesis |
| Quantitative | 8-10s | 2-3 LLM calls (SQL generation + validation + interpretation) |
| Orchestrator | 5s | 1-2 LLM calls (routing + delegation to sub-pipeline) |

---

# Part VIII: Quick Reference Cheat Sheet

Cut out this section and keep it at hand during debugging sessions.

---

## Emergency Fixes (Memorize These)

```
EVERYTHING BROKEN AFTER DEPLOY?
  -> Check N8N_BLOCK_ENV_ACCESS_IN_NODE=false in entrypoint.sh
  -> This is the #1 cause. Fix: add the flag and redeploy.

WEBHOOKS ACCEPT BUT NEVER RESPOND?
  -> Clean stuck executions:
     DELETE FROM execution_entity
     WHERE status IN ('new','running','waiting','crashed');
  -> Then restart the workflow engine.
  -> This is the #2 cause.

404 ON ALL WEBHOOKS?
  -> Workflow not active, OR wrong path.
  -> Verify: SELECT active FROM workflow_entity WHERE id='<ID>';
  -> If active=true but 404: missing credentials prevent webhook registration (FIX-43).

500 "CREDENTIAL NOT FOUND"?
  -> Rebuild wiped credentials. Run credential restore script.
  -> Then deactivate + reactivate all workflows.

HTML INSTEAD OF JSON FROM LLM?
  -> API URL missing /chat/completions.
  -> Fix the URL. Must end with: /api/v1/chat/completions

PATCHES HAVE NO EFFECT?
  -> Check for duplicate active workflows (FIX-71).
  -> Perform deactivate + reactivate cycle.
  -> Verify you patched BOTH nodes[] arrays.
```

## Webhook Paths Quick Reference

```
Standard:     /webhook/rag-multi-index-v3
Graph:        /webhook/<UUID>
Quantitative: /webhook/<UUID>
Orchestrator: /webhook/<UUID>

Method: POST
Field:  query (NEVER "question")
Header: Content-Type: application/json
Body:   {"query": "your question here"}
```

## Pre-Flight Checklist (Before Any Test)

```
[ ] Webhook path copied from documentation (not typed from memory)
[ ] Field name is 'query'
[ ] Content-Type: application/json header set
[ ] Server health check returns 200
[ ] Target workflow is active in database
[ ] N8N_BLOCK_ENV_ACCESS_IN_NODE=false is set
[ ] Credentials exist in target environment
```

## Timeout Reference

```
Standard pipeline:     90s timeout
Graph pipeline:        90s timeout
Quantitative pipeline: 120s timeout
Orchestrator:          180s timeout
Monitoring probes:     Use pipeline-specific timeouts (NOT a global 30s)
```

## n8n API Cheat Sheet

```
Authentication (prefer cookie auth):
  POST /rest/login
  Body: {"emailOrLdapLoginId": "...", "password": "..."}
  Note: Field is emailOrLdapLoginId (NOT email)

Update workflow:
  PATCH /rest/workflows/{id}     (NOT PUT)
  Exclude read-only fields: id, createdAt, updatedAt, active, versionId

Activate workflow (n8n 2.8+):
  POST /rest/workflows/{id}/activate
  Body: {"versionId": "..."}     (REQUIRED in 2.8+)

Deactivate:
  POST /rest/workflows/{id}/deactivate

After ANY code change:
  1. PATCH the workflow
  2. POST /deactivate
  3. POST /activate (with versionId)
```

## n8n Environment Variables (Non-Negotiable)

```bash
# REQUIRED for n8n 2.8+
export N8N_BLOCK_ENV_ACCESS_IN_NODE=false

# REQUIRED for Code node timeout
export N8N_RUNNERS_TASK_BROKER_TTL=120000

# For HF Spaces (direct port, no reverse proxy)
export N8N_PORT=7860
export N8N_HOST=0.0.0.0

# For SQLite mode (ephemeral deployments)
export DB_TYPE=sqlite
```

## Stuck Execution Cleanup

```bash
# Check for stuck executions
SELECT status, count(*) FROM execution_entity GROUP BY status;

# Clean all stuck
DELETE FROM execution_entity
WHERE status IN ('new', 'running', 'waiting', 'crashed');

# Clean old executions (keep last 24h)
DELETE FROM execution_entity
WHERE "startedAt" < NOW() - INTERVAL '24 hours';

# If cleanup alone doesn't fix webhooks: full restart
docker compose down && sleep 5 && docker compose up -d && sleep 65
```

## Decision Tree: When to Restart vs When to Clean

```
Webhooks not responding?
  |
  |-- healthz returns 200?
  |     |
  |     YES --> Check stuck executions.
  |     |       Found stuck executions?
  |     |         YES --> Clean them. Wait 60s.
  |     |         |       Webhooks responding now?
  |     |         |         YES --> Done.
  |     |         |         NO  --> Full restart.
  |     |         NO  --> Full restart.
  |     |
  |     NO --> Service is down. Full restart.
```

---

## Index of Fixes by Number

| Fix | Category | Title |
|-----|----------|-------|
| FIX-01 | n8n Engine | Task Runner isolation breaks static data |
| FIX-02 | n8n Engine | SQL error handler infinite loop |
| FIX-03 | n8n Engine | SQL Validator invalid fallback SQL |
| FIX-04 | n8n Engine | Jina API rejects trailing comma |
| FIX-05 | n8n Engine | Task Broker TTL too short |
| FIX-06 | Credentials | Credentials missing after migration |
| FIX-07 | Neo4j | bolt:// fails in HTTP nodes |
| FIX-08 | Credentials | PostgreSQL credential missing |
| FIX-09 | n8n API | PUT rejects read-only fields |
| FIX-10 | CI/CD | Task Runner timeout in CI |
| FIX-11 | Pipeline | Init node multi-format support |
| FIX-12 | Pinecone | Dimension mismatch after model change |
| FIX-13 | HF Space | Python3 missing in Docker image |
| FIX-14 | HF Space | Import format array vs object |
| FIX-15 | HF Space | Proxy breaks POST body |
| FIX-17 | n8n API | Login field name change |
| FIX-18 | HF Space | SQLite FK constraint on import |
| FIX-19 | HF Space | Imported workflow always inactive |
| FIX-20 | HF Space | API not ready after healthcheck |
| FIX-21 | n8n Engine | Code node cache cycle |
| FIX-22 | LLM | OpenRouter 429 crashes pipeline |
| FIX-23 | Datasets | HuggingFace dataset IDs incorrect |
| FIX-24 | n8n Engine | N8N_RUNNERS_ENABLED deprecated |
| FIX-25 | VM Infra | Zombie sessions consume RAM |
| FIX-26 | Process | Webhook path pre-flight checklist |
| FIX-27 | n8n API | REST API 401 no key configured |
| FIX-28 | HF Space | $env not resolved in workflows |
| FIX-29 | Pipeline | TCP port blocked + crypto + API key |
| FIX-30 | Pipeline | PostgreSQL local for HF Space |
| FIX-31 | Infra | Live diagnostic server |
| FIX-32 | Pipeline | $env blocked + sub-workflow return |
| FIX-33 | n8n Engine | $env blocked ALL node types |
| FIX-34 | Orchestrator | executeWorkflow empty response |
| FIX-35 | LLM | URL without /chat/completions |
| FIX-36 | Evaluation | Phase filtering wrong counts |
| FIX-37 | Pipeline | Context questions sent to SQL |
| FIX-38 | Evaluation | Context parsing breaks multi-hop |
| FIX-39 | Evaluation | Permanent data validator |
| FIX-40 | VM Infra | OOM cascade to webhooks 404 |
| FIX-41 | n8n Engine | Task Broker TTL re-applied |
| FIX-42 | VM Infra | Stuck executions block webhooks |
| FIX-43 | VM Infra | Active but zero webhooks |
| FIX-44 | VM Infra | Partial activation after restart |
| FIX-45 | Monitoring | False positive short timeout |
| FIX-46 | VM Infra | Cleanup without restart |
| FIX-47 | VM Infra | Full restart required |
| FIX-48 | HF Space | Nginx proxy causes 502 |
| FIX-49 | HF Space | Minimal boot configuration |
| FIX-50 | n8n API | Login field change (duplicate of 17) |
| FIX-51 | HF Space | set -e kills container |
| FIX-52 | Credentials | Hardcoded API keys expire |
| FIX-53 | Credentials | Credential ID mismatch |
| FIX-54 | n8n Engine | Broken expression syntax |
| FIX-55 | Infra | Repository growing too large |
| FIX-59 | LLM | Free models rate-limited swap |
| FIX-60 | HF Space | Duplicate secret/variable names |
| FIX-61 | LLM | API credits exhausted |
| FIX-62 | Credentials | Jina/Cohere credentials missing |
| FIX-63 | HF Space | N8N_BLOCK_ENV_ACCESS_IN_NODE (critical) |
| FIX-64 | Pipeline | Redis lock prevents startup |
| FIX-65 | HF Space | Deploy flag to all instances |
| FIX-66 | HF Space | Credential restore post-rebuild |
| FIX-67 | HF Space | Rebuild resets webhooks |
| FIX-68 | LLM | SQL Validator markdown handling |
| FIX-69 | Database | Credential ID schema introspection |
| FIX-70 | Database | tenant_id mismatch |
| FIX-71 | n8n Engine | Duplicate active workflows |
| FIX-72 | n8n API | Activation requires versionId |
| FIX-73 | n8n API | API key 401 use cookie auth |
| FIX-74 | n8n Engine | Expression not evaluated |
| FIX-75 | Pipeline | LLM nodes to proxy |
| FIX-76 | Evaluation | Question duplication bug |
| FIX-77 | Evaluation | Hardcoded timeout override |
| FIX-78 | Neo4j | tx/commit 403 on Aura |
| FIX-79 | Neo4j | Sequential statements slow |

---

## About This Guide

This guide was built from real production debugging across 80+ sessions operating a Multi-RAG system. Every fix, pattern, and anti-pattern was encountered, diagnosed, and resolved in a live production environment.

The system operates:
- **4 specialized RAG pipelines** (Standard retrieval, Graph-based, SQL/Quantitative, Orchestrator)
- **5 database backends** (Pinecone, Neo4j, Supabase/PostgreSQL, SQLite, Redis)
- **3 LLM providers** (OpenRouter, Groq, LiteLLM proxy)
- **9 cloud instances** on HuggingFace Spaces
- **61,000+ evaluation questions** from 18 SOTA benchmarks

Production results:
- Standard pipeline: **87.5% accuracy** (10K questions)
- Quantitative pipeline: **95.2% accuracy** (SQL generation)
- System uptime: **99%+** after implementing the patterns in this guide

---

*RAG Debug Playbook v1.0 -- Copyright 2026. All rights reserved.*
