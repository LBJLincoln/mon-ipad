# RAG Debug Context -- Production Fixes from 80+ Sessions

> Drop this file into your CLAUDE.md, .cursorrules, or .github/copilot-instructions.md.
> Structured for AI agent consumption. Machine-readable error patterns, fixes, and anti-patterns.
> Built from 80+ sessions, 1,100+ commits, and 79 documented fixes on a production Multi-RAG system.

---

## INSTRUCTIONS FOR AI AGENTS

When the user reports a RAG pipeline issue:
1. Check SYMPTOM-FIX-MAP first (Section 1) -- most problems have known solutions
2. Walk the DIAGNOSTIC-TREES (Section 2) for systematic diagnosis
3. Apply the relevant FIX-PATTERN (Section 3) -- one fix at a time
4. Verify against ANTI-PATTERNS (Section 4) to prevent regression
5. Use IRON-RULES (Section 5) as hard constraints on all actions

---

## 1. SYMPTOM-FIX-MAP

> Machine-readable lookup table. Match the symptom string to the fix.

| Symptom | Category | Fix ID | Solution Summary |
|---------|----------|--------|------------------|
| `[object Object]` in response | Serialization | FIX-P01 | `typeof obj === 'object' ? JSON.stringify(obj) : obj` |
| `<!DOCTYPE html>` in response | URL Config | FIX-P02 | API URL missing `/chat/completions` suffix |
| `Query must start with SELECT` | LLM / Rate Limit | FIX-P03 | LLM returned error/HTML instead of SQL; check 429 status |
| `access to env vars denied` | n8n Config | FIX-P04 | Set `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` in entrypoint |
| `Credential with ID xxx does not exist` | Migration | FIX-P05 | Credentials not migrated; recreate and remap IDs |
| `SQLITE_CONSTRAINT FOREIGN KEY` | Import | FIX-P06 | Strip FK fields before workflow import |
| `webhook not registered` (404) | Activation | FIX-P07 | Workflow not active or wrong webhook path |
| `X-N8N-API-KEY header required` (401) | Auth | FIX-P08 | Use cookie auth via `/rest/login` or PostgreSQL direct |
| HTTP 429 Too Many Requests | Rate Limit | FIX-P09 | Implement key rotation, backoff 8s, or switch model |
| HTTP 502/503 Service Unavailable | Infrastructure | FIX-P10 | n8n overload or restart; wait 30s and retry |
| Empty response body `[]` or `""` | Workflow Design | FIX-P11 | Check for `respondToWebhook` + `executeWorkflow` conflict |
| Response from wrong pipeline | Routing | FIX-P12 | Intent classifier miscategorized; check routing logic |
| Fix applied but no effect | Caching | FIX-P13 | n8n Task Runner caches compiled code; full restart cycle required |
| SQL correct but wrong result | Query Logic | FIX-P14 | Use `ILIKE '%keyword%'` instead of exact match; include sample data |
| `Rate limit exceeded` from OpenRouter | Throughput | FIX-P15 | Multi-key rotation across 3+ accounts |
| Webhook accepts but never responds | Stuck Executions | FIX-P16 | Delete stuck executions from DB, restart n8n |
| Timeout > 60s | Pipeline Load | FIX-P17 | Increase timeout; quantitative needs 90-120s normally |
| `Invalid LLM response` from SQL validator | LLM Format | FIX-P18 | Add multi-strategy extraction: JSON, sql block, raw SELECT |
| SQL returns 0 rows despite correct query | Tenant Filter | FIX-P19 | Wrong `tenant_id` value; verify filter matches data |
| PATCH updates have no effect | Duplicate Workflows | FIX-P20 | Two workflows share same webhook; wrong one is active |
| n8n expressions `{{ }}` not evaluated | Expression Syntax | FIX-P21 | Use `={{ }}` (with equals sign) in n8n jsonBody fields |
| `trailing comma` in JSON body | API Format | FIX-P22 | Jina API rejects trailing commas; validate JSON before send |
| Dimension mismatch error | Index Config | FIX-P23 | Embedding model changed; ensure index dimensions match (e.g., 1024 for Jina) |
| HF Space 502 after deploy | Proxy Config | FIX-P24 | n8n must listen on port 7860 directly; remove nginx reverse proxy |
| `set -e` kills container | Entrypoint | FIX-P25 | Remove `set -e` from entrypoint.sh; transient failures are normal |
| Quick test passes but full eval fails | Test Quality | FIX-P26 | Smoke tests use easy questions; validate with 50+ question eval |
| CONFIG_ERROR on HF Space | Secrets Conflict | FIX-P27 | Duplicate secret and variable names; remove duplicates |

---

## 2. DIAGNOSTIC-TREES

### 2.1 Pipeline responds but result is incorrect

```
Response received but wrong
    |
    +-- Contains "[object Object]"?
    |       YES --> FIX-P01: serialize with typeof check
    |
    +-- Contains HTML (<!DOCTYPE html>)?
    |       YES --> FIX-P02: API URL missing /chat/completions
    |
    +-- "Query must start with SELECT"?
    |       |
    |       +-- LLM returns 429? --> FIX-P09: rate limit, wait or rotate keys
    |       +-- LLM returns invalid JSON? --> FIX-P18: multi-strategy SQL extraction
    |       +-- LLM returns HTML? --> FIX-P02: URL incomplete
    |
    +-- SQL correct but numerical result wrong?
    |       --> FIX-P14: bad WHERE clause (company, period, year)
    |       --> Solution: ILIKE + sample data in prompt
    |
    +-- Response empty (body = [] or "")?
    |       |
    |       +-- Orchestrator? --> FIX-P11: executeWorkflow + respondToWebhook conflict
    |       +-- Other pipeline? --> Check "Respond to Webhook" node exists
    |
    +-- Response = data from wrong pipeline?
            --> FIX-P12: intent classifier routing error
```

### 2.2 HTTP error calling webhook

```
HTTP error calling webhook
    |
    +-- 404 "webhook not registered"?
    |       |
    |       +-- Path correct? --> Verify against webhook registry (Section 6)
    |       +-- Path correct but 404? --> Workflow not active; activate it
    |
    +-- 401 "API key required"?
    |       --> FIX-P08: use cookie auth or direct DB access
    |
    +-- 500 Internal Server Error?
    |       |
    |       +-- "access to env vars denied"? --> FIX-P04
    |       +-- "Credential does not exist"? --> FIX-P05
    |       +-- "FOREIGN KEY constraint"? --> FIX-P06
    |       +-- No clear message? --> Check last execution in n8n UI
    |
    +-- 429 Too Many Requests?
    |       --> FIX-P09: backoff + key rotation
    |
    +-- 502/503?
    |       --> FIX-P10: n8n overload, wait 30s
    |
    +-- Timeout > 60s?
            --> FIX-P17: increase timeout (quant=120s, orch=180s)
```

### 2.3 Fix applied but behavior unchanged

```
Fix applied but runtime unchanged
    |
    +-- Modified on local/VM n8n instance?
    |       --> STOP: Task Runner caches compiled code even after restart
    |       --> Solution: modify on deployment target directly
    |
    +-- Modified on deployed instance?
    |       |
    |       +-- Rebuild/redeploy done?
    |       |       --> Verify new code is actually deployed (check logs)
    |       |
    |       +-- $env used in workflow?
    |       |       --> FIX-P04: verify N8N_BLOCK_ENV_ACCESS_IN_NODE=false
    |       |
    |       +-- Code node modified?
    |       |       --> Cycle: PUT workflow --> Deactivate --> Activate
    |       |
    |       +-- Patched nodes[] but not activeVersion.nodes[]?
    |               --> MUST patch BOTH arrays in n8n 2.x
    |
    +-- Modified via REST API?
            --> PUT must exclude read-only fields (400 error)
            --> Cycle PUT --> Deactivate --> Activate is mandatory
            --> Verify with GET that change persisted
```

---

## 3. FIX-PATTERNS

> Detailed fix patterns with root cause, solution code, and prevention rules.

### FIX-P01: Object Serialization

**Root cause**: JavaScript concatenates Error object with string, producing `[object Object]`.

```javascript
// BAD
const msg = "Error: " + errorObj;

// GOOD
const msg = "Error: " + (typeof errorObj === 'object' ? JSON.stringify(errorObj) : errorObj);
```

**Prevention**: Always serialize with typeof check before string concatenation in n8n Code nodes.

---

### FIX-P02: API URL Missing Path

**Root cause**: Base URL configured without the `/chat/completions` endpoint suffix. API returns its HTML landing page instead of JSON.

```
// BAD
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

// GOOD (for direct HTTP calls)
url = "https://openrouter.ai/api/v1/chat/completions"
```

**Prevention**: Always verify full API URL in HTTP Request node includes the endpoint path.

---

### FIX-P04: n8n Environment Variable Access Blocked

**Root cause**: n8n 2.8+ blocks `$env.*` access in ALL node types by default (not just Code nodes). The Task Runner sandbox evaluates ALL expressions and blocks environment variable resolution.

```bash
# Add to entrypoint.sh BEFORE n8n starts
export N8N_BLOCK_ENV_ACCESS_IN_NODE=false
```

**Impact**: Cross-pipeline. Without this, ALL pipelines using `$env.OPENROUTER_API_KEY`, `$env.PINECONE_API_KEY`, etc. will fail silently or return "access to env vars denied".

**Prevention**: This config MUST be present in every n8n deployment's startup script. Test with a simple `$env.TEST_VAR` expression after deployment.

---

### FIX-P05: Credential ID Mismatch After Migration

**Root cause**: Exported workflows contain credential IDs from the source database. After importing to a fresh instance, those IDs don't exist. n8n silently fails or returns 500.

```python
# Credential remapping pattern
credential_map = {
    "old_id_from_export": "new_id_on_target",
    # ... map all credentials
}

def remap_credentials(workflow_json, credential_map):
    text = json.dumps(workflow_json)
    for old_id, new_id in credential_map.items():
        text = text.replace(old_id, new_id)
    return json.loads(text)
```

**Prevention**: After every fresh import, verify all credential IDs exist on the target. Create a credential restore script that runs on boot.

---

### FIX-P06: Foreign Key Constraint on Import

**Root cause**: Workflow JSON exports contain references to source DB entities (shared, activeVersion, versionId). These FK references break on a fresh database.

```python
FK_FIELDS = ['shared', 'activeVersion', 'activeVersionId', 'versionId', 'versionCounter']

def strip_fk_fields(workflow):
    for field in FK_FIELDS:
        if field in workflow:
            del workflow[field]
    return workflow
```

**Prevention**: Always strip FK fields before importing workflows. This is especially critical for n8n instances with ephemeral storage (HF Spaces, Docker without volumes).

---

### FIX-P09: Rate Limit Management (429 Errors)

**Root cause**: Free-tier LLM APIs (OpenRouter, Groq) limit to ~20 req/min per API key. RAG pipelines with multiple LLM calls per question (SQL generation + validation + interpretation) exhaust limits quickly.

```python
# Multi-key rotation pattern
import itertools

class KeyRotator:
    def __init__(self, keys):
        self.keys = keys
        self.cycle = itertools.cycle(keys)
        self.usage = {k: 0 for k in keys}

    def get_next_key(self):
        key = next(self.cycle)
        self.usage[key] += 1
        return key

# n8n HTTP Request node configuration
# maxTries: 3
# waitBetweenTries: 8000  (ms)
# neverError: true  (prevents workflow crash on 429)
```

**Scaling strategy**:
- 1 key = ~20 req/min
- 3 accounts x 2 keys = ~120 req/min
- 7 keys across 3 accounts = ~140 req/min

**Prevention**: Use a LiteLLM proxy with automatic key rotation. Configure retry with exponential backoff (8s base) in all HTTP Request nodes.

---

### FIX-P11: executeWorkflow Returns Empty

**Root cause**: `executeWorkflow` nodes call sub-workflows that use `respondToWebhook`. The respondToWebhook sends the HTTP response to the original client but does NOT return data back to the parent executeWorkflow node. Result: empty array `[[]]`.

```json
// BAD: executeWorkflow node
{
  "type": "n8n-nodes-base.executeWorkflow",
  "parameters": { "workflowId": "sub-workflow-id" }
}

// GOOD: httpRequest to webhook
{
  "type": "n8n-nodes-base.httpRequest",
  "parameters": {
    "url": "http://localhost:5678/webhook/sub-workflow-path",
    "method": "POST",
    "body": { "query": "={{$json.task_query}}" },
    "timeout": 30000
  }
}
```

**Rule**: NEVER use `executeWorkflow` for workflows that contain `respondToWebhook`. Use `httpRequest` POST to the webhook URL instead.

---

### FIX-P14: SQL Generates Correct Structure but Wrong Results

**Root cause**: LLM generates exact-match WHERE clauses (`company_name = 'TechVision'`) when the data contains variants (`'TechVision Inc'`). Also mismatches on fiscal periods (FY vs Q1-Q4) and year formats.

```sql
-- BAD: exact match
SELECT revenue FROM financials WHERE company_name = 'TechVision' AND period = '2023';

-- GOOD: fuzzy match with explicit period format
SELECT revenue FROM financials
WHERE company_name ILIKE '%techvision%'
  AND fiscal_year = 2023
  AND period = 'FY'
  AND tenant_id = 'benchmark'
LIMIT 1;
```

**Prompt engineering fix**: Include 3-5 sample data rows in the SQL generation prompt so the LLM knows exact column values, naming conventions, and available periods.

---

### FIX-P16: Stuck Executions Block All Webhooks

**Root cause**: Executions stuck in `new`/`running` status accumulate. n8n tries to resume ALL on startup, consuming all processing capacity. New webhook requests are accepted but queued behind stuck execution resume attempts. Symptom: `healthz` returns 200 but webhooks never respond.

```bash
# 1. Stop n8n
docker stop n8n-container

# 2. Delete stuck executions
docker exec postgres-container psql -U n8n -d n8n -t -A -c \
  "DELETE FROM execution_entity WHERE status IN ('new', 'running', 'waiting', 'crashed');"

# 3. Start n8n clean
docker start n8n-container

# 4. Wait for full startup (30-60s for webhook registration)
sleep 45
```

**Monitoring rule**: When n8n hangs on webhook responses but healthz is OK, ALWAYS check for stuck executions first. This is the #1 cause of "webhooks accept but never respond".

---

### FIX-P18: LLM Returns Markdown Instead of JSON

**Root cause**: Free-tier models (Llama 70B, Gemma 27B) often return markdown-wrapped responses with Chain-of-Thought reasoning even when instructed to output JSON only. SQL may appear inside ` ```sql ` code blocks.

```javascript
// Multi-strategy extraction for SQL from LLM response
function extractSQL(content) {
  // Strategy 1: Direct JSON parse
  try { return JSON.parse(content).sql; } catch(e) {}

  // Strategy 2: Extract from ```sql code block
  const sqlMatch = content.match(/```sql\s*([\s\S]*?)```/);
  if (sqlMatch) return sqlMatch[1].trim();

  // Strategy 3: Extract from ```json code block
  const jsonMatch = content.match(/```json\s*([\s\S]*?)```/);
  if (jsonMatch) {
    try { return JSON.parse(jsonMatch[1]).sql; } catch(e) {}
  }

  // Strategy 4: Raw SELECT extraction
  const selectMatch = content.match(/(SELECT[\s\S]*?;)/i);
  if (selectMatch) return selectMatch[1].trim();

  return null; // All strategies failed
}
```

**Prevention**: Always handle both JSON and markdown LLM responses. Never assume the model will follow format instructions exactly.

---

### FIX-P19: Tenant ID Filter Mismatch

**Root cause**: Data ingested with `tenant_id='benchmark'` but queries filter on `tenant_id='default'` (or vice versa). SQL is syntactically correct and runs without error but returns 0 rows.

```sql
-- Diagnostic: check what tenant_ids exist
SELECT DISTINCT tenant_id, COUNT(*) FROM financials GROUP BY tenant_id;

-- Ensure ALL queries include the correct tenant_id
WHERE tenant_id = 'benchmark'  -- NOT 'default'
```

**Prevention**: Include the tenant_id filter in every SQL template and prompt. Document the canonical tenant_id value prominently.

---

### FIX-P20: Duplicate Active Workflows

**Root cause**: Two workflows with the same webhook path are both active. n8n routes requests to one of them (usually the older one). Patching the other workflow has no effect because it never receives requests.

```bash
# Diagnostic: check which workflow actually handles requests
# Look at the workflowId field in recent execution data
GET /rest/executions?limit=1
# Compare execution.workflowId with the workflow you've been patching
```

**Fix**: Deactivate the stale workflow. Before patching any workflow, ALWAYS verify which `workflowId` appears in actual execution data.

---

### FIX-P23: Embedding Dimension Mismatch

**Root cause**: Switching embedding models (e.g., Cohere 1536d to Jina 1024d) without recreating the vector index. Queries return dimension mismatch errors or garbage results.

```
Cohere embed-english-v3.0  --> 1536 dimensions
Jina jina-embeddings-v3    --> 1024 dimensions (default)
OpenAI text-embedding-3    --> 1536 or 3072 dimensions
e5-large                   --> 1024 dimensions
```

**Fix**: Create a new index with the correct dimensions. Re-embed all documents with the new model. Never mix embedding models within a single index.

---

### FIX-P24: HF Space 502 with Nginx

**Root cause**: Running nginx as a reverse proxy in front of n8n on HF Spaces causes persistent 502 errors. HF Spaces expects the application to listen directly on port 7860.

```dockerfile
# BAD: nginx reverse proxy
EXPOSE 7860
# nginx proxies 7860 --> n8n on 5678

# GOOD: n8n listens directly on 7860
ENV N8N_PORT=7860
EXPOSE 7860
```

**Prevention**: On HF Spaces, always have the primary application listen directly on 7860. No intermediate proxies.

---

## 4. ANTI-PATTERNS

> These are the most common mistakes. Check against this list before making changes.

| ID | Anti-Pattern | Frequency | Prevention |
|----|-------------|-----------|------------|
| AP-01 | Typing webhook paths from memory | EVERY SESSION | Always copy from a registry/config file |
| AP-02 | Using `question` instead of `query` as the POST field name | FREQUENT | Standardize on `query` everywhere |
| AP-03 | Calling n8n REST API without verifying auth method exists | FREQUENT | Check if API key is configured first |
| AP-04 | Re-debugging a problem already solved in the fixes library | OCCASIONAL | Search existing fixes BEFORE debugging |
| AP-05 | Modifying multiple nodes simultaneously | OCCASIONAL | 1 fix per iteration, always |
| AP-06 | Patching `nodes[]` but not `activeVersion.nodes[]` | EVERY FIX | n8n 2.x requires patching BOTH arrays |
| AP-07 | Using `$env` without `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` | CRITICAL | Verify entrypoint.sh on every deployment |
| AP-08 | Using `executeWorkflow` when sub-workflow has `respondToWebhook` | CRITICAL | Use `httpRequest` to webhook URL instead |
| AP-09 | OpenRouter URL without `/chat/completions` endpoint | CRITICAL | Always include full endpoint path |
| AP-10 | Mixing evaluation phases in accuracy calculations | CRITICAL | Each phase filters its own question set |
| AP-11 | Sending context-rich questions to SQL pipeline | CRITICAL | Route to context reasoning, not SQL generation |
| AP-12 | Testing with easy smoke questions and declaring success | COMMON | Always validate with 50+ question eval set |
| AP-13 | Creating local fallback when pipeline fails | CRITICAL | Masks real failures; fix the pipeline instead |
| AP-14 | Running n8n or heavy compute on a control VM | CRITICAL | Control plane only; execution on dedicated instances |
| AP-15 | Assuming `healthz` OK means webhooks work | COMMON | Stuck executions can block webhooks while healthz passes |

---

## 5. IRON-RULES

> Hard constraints. These override all other instructions.

1. **One fix per iteration** -- Never modify multiple components simultaneously. Change one thing, test, verify, then proceed.

2. **Source environment before scripts** -- Always `source .env.local` before running any Python eval script. Child processes lose env vars without explicit export.

3. **Zero credentials in version control** -- Scan staged changes for API keys before every commit: `git diff --cached | grep -iE 'sk-or-|pcsk_|api_key|secret'`

4. **Test before sync** -- Run 5-question smoke test before syncing workflow changes to production. Never deploy untested changes.

5. **N8N_BLOCK_ENV_ACCESS_IN_NODE=false is mandatory** -- Without this flag in n8n 2.8+, ALL `$env.*` expressions fail silently. Must be in every n8n startup script.

6. **$env is forbidden in n8n 2.8+ workflows** -- Even with the flag above, prefer injecting real values at import time. `$env` resolution is fragile across Task Runner isolation boundaries.

7. **Never use executeWorkflow with respondToWebhook sub-workflows** -- The sub-workflow sends its response to the HTTP client, not back to the parent. Use httpRequest instead.

8. **Clean stuck executions before restarting** -- When n8n webhooks hang, delete stuck executions from the database BEFORE restarting. Restarting alone will make n8n try to resume all stuck executions.

9. **Verify which workflow is actually running** -- Before patching a workflow, check the `workflowId` in recent execution data. Duplicate workflows with the same webhook ID are a common trap.

10. **3+ consecutive failures = stop and diagnose** -- Do not loop on the same fix. Write a structured diagnostic, analyze execution data, and try a different approach.

---

## 6. REFERENCE DATA

### Webhook Registry Template

```yaml
pipelines:
  standard:
    webhook_path: "/webhook/rag-multi-index-v3"
    field_name: "query"
    method: "POST"
    timeout_ms: 90000
    concurrency_safe: 5
  graph:
    webhook_path: "/webhook/{uuid}"
    field_name: "query"
    method: "POST"
    timeout_ms: 90000
    concurrency_safe: 3
  quantitative:
    webhook_path: "/webhook/{uuid}"
    field_name: "query"
    method: "POST"
    timeout_ms: 120000
    concurrency_safe: 1
  orchestrator:
    webhook_path: "/webhook/{uuid}"
    field_name: "query"
    method: "POST"
    timeout_ms: 180000
    concurrency_safe: 1
```

### Standard Call Format

```bash
curl -s -X POST "https://your-n8n-host/webhook/<PATH>" \
  -H "Content-Type: application/json" \
  -d '{"query": "your question here"}' | python3 -m json.tool
```

### n8n Cookie Authentication Pattern

```python
import urllib.request
import http.cookiejar
import json

# n8n on HF Spaces requires cookie auth (not API key)
cookie_jar = http.cookiejar.MozillaCookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))

login_data = json.dumps({
    "emailOrLdapLoginId": "your@email.com",  # NOT "email" field
    "password": "your-password"
}).encode()

req = urllib.request.Request(
    f"{n8n_host}/rest/login",
    data=login_data,
    headers={"Content-Type": "application/json"},
    method="POST"
)
response = opener.open(req)
# Cookie is now stored in cookie_jar for subsequent requests
```

### Recommended Timeouts by Pipeline

| Pipeline | Questions/min | LLM Calls/Question | Recommended Timeout | Delay Between Questions |
|----------|--------------|---------------------|---------------------|------------------------|
| Standard (vector) | 20 | 0-1 (HyDE optional) | 90s | 3s |
| Graph (knowledge graph) | 10 | 1 (community synthesis) | 90s | 5s |
| Quantitative (SQL) | 7 | 2-3 (SQL gen + validate + interpret) | 120s | 8-10s |
| Orchestrator (meta) | 5 | 1-2 (routing + delegation) | 180s | 5s |

### LLM Resilience Configuration

```yaml
# n8n HTTP Request node settings for LLM calls
retry:
  maxTries: 3
  waitBetweenTries: 8000  # 8 seconds (covers most rate limit windows)

error_handling:
  neverError: true  # Prevents workflow crash on LLM failure

fallback_cascade:
  - primary_model: "llama-3.3-70b-instruct"
  - fallback_model: "gemma-3-27b-it"
  - last_resort: "template_sql"  # Bypass LLM entirely for known patterns

prompt_engineering:
  include_sample_data: true  # 3-5 real rows from the target table
  include_static_schema: true  # Precomputed compact schema
  use_ilike: true  # Fuzzy matching instead of exact WHERE
```

---

## 7. DATABASE GOTCHAS

> Common database-specific issues discovered in production.

### Pinecone
- Free tier: max 100K vectors per index, 5 indexes total
- Namespace isolation is critical for multi-dataset indexes
- Dimension mismatch = silent garbage results (no error)
- Serverless latency varies: 200-500ms typical, spikes to 2s under cold start
- Metadata filtering is faster than post-retrieval filtering

### Neo4j Aura
- **bolt:// protocol does NOT work** through n8n HTTP Request nodes; use HTTPS API only
- API endpoint: `https://{id}.databases.neo4j.io/db/neo4j/query/v2`
- `tx/commit` returns 403 on Aura free tier; use `/db/neo4j/query/v2` (Query API)
- Free tier pauses after 3 days inactivity; send a wake-up query
- Use `UNWIND $rows` for bulk operations (100x faster than sequential statements)

### Supabase
- **Port 5432** (session pooler) for psycopg2; port 6543 (transaction pooler) silently drops inserts
- `tenant_id = 'benchmark'` for evaluation data (NOT 'default')
- `exec_sql` RPC for dynamic SQL generation
- Free tier pauses after 1 week inactivity
- Connection pooler max 60 concurrent connections

### n8n SQLite (Ephemeral Deployments)
- HF Space rebuilds wipe the SQLite database (credentials, executions, everything)
- Workflows survive via JSON import but credential IDs become orphans
- PATCH changes update in-memory DB only; they do NOT persist across restarts
- Must update source JSON files AND sync for permanent changes

---

## 8. EVALUATION TRAPS

> Mistakes that make your RAG accuracy numbers meaningless.

| Trap | Symptom | Fix |
|------|---------|-----|
| Smoke test bias | 5/5 PASS but full eval shows 40% | Use 50+ diverse questions for real accuracy |
| Phase mixing | Phase 2 questions counted in Phase 1 gates | Filter questions by phase before calculating |
| Rate limit false negatives | "Unable to generate SQL" = FAIL | Exclude timeout/rate-limit errors from accuracy calc |
| Fuzzy matching too strict | "6.7 billion" vs "6,745,000,000" = FAIL | Normalize numbers before comparison |
| Fuzzy matching too loose | Any response containing "the" = PASS | Require substantive keyword match |
| Local fallback inflation | 65% accuracy but pipeline is actually broken | Disable local fallback; measure pipeline accuracy directly |
| Empty expected_contains | `expected_contains: ""` always matches | Every test question needs a substantive expected value |

---

## META

**Source**: 80+ development sessions on a production Multi-RAG orchestrator (2025-2026).
**Fixes documented**: 79 unique issues, categorized and cross-referenced.
**Pipelines covered**: Standard (vector RAG), Graph (knowledge graph RAG), Quantitative (SQL RAG), Orchestrator (meta-routing).
**Infrastructure**: n8n workflow engine, Pinecone, Neo4j, Supabase, OpenRouter, Jina, LiteLLM.
**Price**: $27 -- AI Agent Context Kit.
