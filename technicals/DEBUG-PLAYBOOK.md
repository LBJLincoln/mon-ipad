# DEBUG PLAYBOOK — Multi-RAG Orchestrator

> Last updated: 2026-03-07T14:00:00Z
>
> **SINGLE SOURCE OF TRUTH** for debugging Multi-RAG pipelines.
> Combines diagnostic flowcharts, 79+ documented fixes, and operational knowledge.
> Read Section 1 (Quick Diagnostic) first, then search for specific symptoms.

---

## TABLE OF CONTENTS

1. [Quick Diagnostic Flowcharts](#1-quick-diagnostic-flowcharts)
2. [Fixes Library (FIX-01 to FIX-79)](#2-fixes-library)
3. [Iron Rules (Never Violate)](#3-iron-rules)
4. [Quick Reference (Pre-Flight)](#4-quick-reference)
5. [Recurring Patterns & Solutions](#5-recurring-patterns--solutions)
6. [Anti-Patterns to Eliminate](#6-anti-patterns-to-eliminate)
7. [LLM Models & Behavior](#7-llm-models--behavior)
8. [APIs & External Services](#8-apis--external-services)
9. [Databases & Schemas](#9-databases--schemas)
10. [Infrastructure & Performance](#10-infrastructure--performance)
11. [Evaluation & Testing](#11-evaluation--testing)

---

## 1. QUICK DIAGNOSTIC FLOWCHARTS

### 1.1 Diagnostic Tree — Pipeline responds but result incorrect

```
Response received but wrong
    |
    +-- Response contains "[object Object]"?
    |       YES → Pattern 5.2: serializer typeof check
    |
    +-- Response contains HTML (<!DOCTYPE html>)?
    |       YES → URL API incomplete (ex: /chat/completions missing)
    |             → FIX-35: verify OPENROUTER_BASE_URL
    |
    +-- Response "Query must start with SELECT"?
    |       |
    |       +-- LLM returns error 429? → Rate limit OpenRouter
    |       |       → Wait 60s, or change model, or use multi-key rotation
    |       |       → See Section 7.6
    |       |
    |       +-- LLM returns JSON invalid? → Model generates bad SQL
    |       |       → Pattern 5.3: ILIKE, sample data, schema statique
    |       |
    |       +-- LLM returns HTML? → URL API sans /chat/completions
    |               → FIX-35
    |
    +-- SQL correct but numerical result wrong?
    |       → Pattern 5.3: bad WHERE (company, period, year)
    |       → Solution: ILIKE + sample data in prompt
    |
    +-- Response empty (body = [] or "")?
    |       |
    |       +-- Orchestrator? → FIX-34: executeWorkflow + respondToWebhook
    |       |       → Verify Invoke nodes are httpRequest (not executeWorkflow)
    |       |
    |       +-- Other pipeline? → Pattern 5.8: verify Respond to Webhook node
    |
    +-- Response = data from another pipeline?
            → Orchestrator routing error → verify Intent Classifier
```

### 1.2 Diagnostic Tree — HTTP error calling webhook

```
HTTP error calling webhook
    |
    +-- 404 "webhook not registered"?
    |       |
    |       +-- Path correct? → Verify Section 4.1
    |       |       → ALWAYS copy path from docs, NEVER type from memory
    |       |
    |       +-- Path correct but 404? → Workflow not active
    |               → VM: docker exec n8n-postgres-1 psql -U n8n -d n8n -t -A \
    |                     -c "SELECT active FROM workflow_entity WHERE id = '<ID>'"
    |               → HF Space: verify logs de startup (activation failed?)
    |
    +-- 401 "X-N8N-API-KEY header required"?
    |       → FIX-27: no API key on VM
    |       → Use PostgreSQL direct or MCP n8n (Section 4.3)
    |       → DO NOT attempt REST API
    |
    +-- 500 Internal Server Error?
    |       |
    |       +-- Message "access to env vars denied"?
    |       |       → FIX-33/63: $env blocked in n8n 2.8+
    |       |       → Solution: N8N_BLOCK_ENV_ACCESS_IN_NODE=false
    |       |
    |       +-- Message "Credential with ID xxx does not exist"?
    |       |       → FIX-06/53: credentials not migrated
    |       |       → Create credentials + remap IDs
    |       |
    |       +-- Message "SQLITE_CONSTRAINT FOREIGN KEY"?
    |       |       → FIX-18: FK to source DB entities
    |       |       → Strip FK fields before import
    |       |
    |       +-- No clear message?
    |               → Verify execution in n8n: analyze last executed node
    |               → scripts/analyze_n8n_executions.py --pipeline <name> --limit 1
    |
    +-- 429 Too Many Requests?
    |       → OpenRouter rate limit (~20 req/min free tier)
    |       → Options: wait, retry backoff 8s, multi-key, change model
    |
    +-- 502/503 Service Unavailable?
    |       → n8n overload or restart in progress
    |       → Wait 30s and retry
    |       → If VM: verify RAM (free -m), kill zombie sessions
    |       → If HF Space: verify container up (curl healthz)
    |
    +-- Timeout (>60s)?
            → Pipeline under load or slow LLM
            → Quantitative: 3 LLM calls = 15-30s normal
            → Orchestrator: delegates to sub-pipelines = 20-45s normal
            → Increase timeout to 90s in test script
```

### 1.3 Diagnostic Tree — Workflow modification has no effect

```
Fix applied but runtime behavior unchanged
    |
    +-- Modified on VM n8n?
    |       → FORBIDDEN since session 25 (Pattern 5.11)
    |       → Task Runner caches compiled code even after restart
    |       → SOLUTION: modify on HF Space ONLY
    |
    +-- Modified on HF Space?
    |       |
    |       +-- Rebuild done? (git push → Docker rebuild)
    |       |       → Verify in HF Space logs that new code deployed
    |       |
    |       +-- $env used in workflow?
    |       |       → FIX-33: $env blocked in n8n 2.8+
    |       |       → Verify N8N_BLOCK_ENV_ACCESS_IN_NODE=false set
    |       |
    |       +-- Code node modified?
    |       |       → Cycle PUT → Deactivate → Activate (FIX-21)
    |       |       → OR: complete re-import (HF Space = fresh DB on rebuild)
    |       |
    |       +-- nodes[] modified but not activeVersion.nodes[]?
    |               → Anti-pattern AP-6: ALWAYS patch BOTH
    |               → FIX-29, FIX-32 document this trap
    |
    +-- Modified via REST API?
            → FIX-09: PUT payload must exclude read-only fields
            → FIX-21: cycle PUT → Deactivate → Activate mandatory
            → Verify with GET that change is persisted
```

### 1.4 Quick Symptom Matrix

| Symptom | Tree | Probable Fix | Reference |
|---------|------|--------------|-----------|
| 404 webhook | 1.2 | Wrong path | Section 4.1 |
| 500 "$env denied" | 1.2 | FIX-33/63 | Section 2 |
| 500 "credential not found" | 1.2 | FIX-06/53 | Section 2 |
| 429 rate limit | 1.2 | Backoff/multi-key | Section 7.6 |
| Body empty (Orchestrator) | 1.1 | FIX-34 | Section 2 |
| HTML instead of JSON | 1.1 | FIX-35 | Section 2 |
| "[object Object]" | 1.1 | Pattern 5.2 | Section 5 |
| "Query must start with SELECT" | 1.1 | LLM 429 or URL | Section 7.6 |
| Fix no effect (VM) | 1.3 | Pattern 5.11 | Section 5 |
| Fix no effect (HF) | 1.3 | AP-6 / FIX-21 | Section 2 |
| OOM on VM | - | Rule 3.8 | Section 3 |
| Test inconsistent | - | Rate limit | Section 11 |

### 1.5 Pre-Debug Checklist (MANDATORY)

Before starting any debug, verify in order:

```
[ ] 1. Is symptom in Quick Symptom Matrix above?
[ ] 2. Is symptom in Fixes Library (Section 2)?
[ ] 3. Is symptom in Recurring Patterns (Section 5)?
[ ] 4. Are anti-patterns AP-1 to AP-12 avoided?
[ ] 5. Is pre-flight checklist (Section 4.4) followed?
```

**If any check finds answer: APPLY EXISTING SOLUTION.**
**Do NOT re-diagnose. Do NOT re-analyze. Apply directly.**

---

## 2. FIXES LIBRARY

### Index by Category

| # | Category | Problem | Session | Impact |
|---|----------|---------|---------|--------|
| 01 | n8n Infrastructure | Task Runner isolation breaks $getWorkflowStaticData | 16 | CRITICAL |
| 02 | n8n Infrastructure | SQL Error Handler infinite loop (counter $execution.id) | 16 | CRITICAL |
| 03 | n8n SQL | SQL Validator fallback SQL without FROM (PostgreSQL syntax error) | 16 | CRITICAL |
| 04 | n8n Embedding | Jina JSON trailing comma (standard pipeline) | 8 | CRITICAL |
| 05 | n8n Auth | Task Broker TTL 15s→120s (grant token expiry) | 8 | CRITICAL |
| 06 | n8n Credentials | Credentials missing after cloud→Docker migration | 15 | CRITICAL |
| 07 | Graph Pipeline | Neo4j URL bolt://localhost → HTTPS API (Shield #4) | 17 | CRITICAL |
| 08 | Quantitative Pipeline | Credential postgres missing (live workflow empty) | 17 | CRITICAL |
| 09 | n8n API | PUT workflow rejects read-only fields (400 error) | 17 | IMPORTANT |
| 10 | CI/CD | n8n runners isolation → timeout 300s×2q = CI fail | 16 | CRITICAL |
| 11 | Graph Pipeline | Init & ACL multi-format (orchestrator support) | 14 | IMPORTANT |
| 12 | Pinecone | Migration Cohere 1536d → Jina 1024d (index mismatch) | 7 | CRITICAL |
| 13 | HF Space | Docker python3 missing (node:20-bookworm-slim) | 24 | CRITICAL |
| 14 | HF Space | n8n import:workflow format array vs object | 24 | CRITICAL |
| 15 | HF Space | HF proxy breaks POST body for /rest/ and /api/ | 24 | IMPORTANT |
| 16 | HF Space | n8n import:workflow always inactive + activation REST fails | 24 | RESOLVED by FIX-18 |
| 17 | HF Space | n8n 2.x login API emailOrLdapLoginId (not email) | 24 | IMPORTANT |
| 18 | HF Space | SQLITE FK constraint — shared/activeVersion refs VM entities | 24 | CRITICAL |
| 19 | HF Space | n8n 2.8+ activation requires publish (versionId) | 24 | CRITICAL |
| 20 | HF Space | REST API not ready after healthz (timing) | 24 | IMPORTANT |
| 21 | n8n Infrastructure | Code node cache — PUT + Activate cycle mandatory | 25 | CRITICAL |
| 22 | Quantitative Pipeline | OpenRouter 429 rate-limit — retries + neverError + error serialization | 25 | CRITICAL |
| 23 | Datasets | HuggingFace dataset IDs incorrect (6/11 wrong) | 25 | IMPORTANT |
| 24 | n8n Infrastructure | N8N_RUNNERS_ENABLED deprecated in n8n 2.7.4+ (always active) | 25 | IMPORTANT |
| 25 | VM Infrastructure | Old Claude Code zombie sessions consume RAM | 25 | IMPORTANT |
| 26 | Agent Process | Webhook path/field name incorrect — pre-flight checklist mandatory | 25 | CRITICAL |
| 27 | n8n API | REST API 401 — no API key configured in Docker | 25 | IMPORTANT |
| 28 | HF Space | n8n $env vars not resolved — Quant+Orch 500 (OPENROUTER_API_KEY empty) | 26 | CRITICAL |
| 29 | Quant + Orch | HF Space TCP port 6543 blocked + require('crypto') + API key type | 27 | CRITICAL |
| 30 | Orchestrator | PostgreSQL local for HF Space (port 6543 blocked) | 27 | IMPORTANT |
| 31 | Infrastructure | Live diagnostic server (diag-server.py) on port 7861 | 27 | IMPORTANT |
| 32 | Quant + Standard | $env blocked in Code nodes Task Runner + sub-workflow return | 27 | CRITICAL |
| 33 | ALL workflows | $env blocked for ALL node types n8n 2.8+ (not just Code) | 27 | CRITICAL |
| 34 | Orchestrator | executeWorkflow returns empty (sub-wf respondToWebhook) → httpRequest | 27 | CRITICAL |
| 35 | Quantitative | OPENROUTER_BASE_URL without /chat/completions → HTML instead of JSON | 27 | CRITICAL |
| 36 | Evaluation | Phase 1 gates counted Phase 2 questions (musique, finqa) | 30 | CRITICAL |
| 37 | Quantitative | Phase 2 context-based questions need LLM reasoning, not SQL | 34 | CRITICAL |
| 38 | Evaluation | load_questions() broke 2wikimultihopqa context (wrong JSON format) | 35 | CRITICAL |
| 39 | Data Validation | Permanent data validator + preflight checks + all context formats | 35 | CRITICAL |
| 40 | VM Infrastructure | OOM → zombie processes → PG connection timeouts → all webhooks 404/503 | 40 | CRITICAL |
| 41 | n8n Infrastructure | FIX-05 TTL 15s→120s re-applied — still needed on e2-micro VM | 40 | CRITICAL |
| 42 | VM Infrastructure | Stuck executions (79 new/running) block webhook response — DELETE + restart | 40b | CRITICAL |
| 43 | VM Infrastructure | PME workflows active=true but 0 webhooks registered — missing credentials silently fail | 40c | IMPORTANT |
| 44 | VM Infrastructure | n8n restart only partially activates workflows when stuck execs exist during shutdown | 40d | CRITICAL |
| 45 | Monitoring | deploy-overnight false positive: curl timeout <30s reports webhooks DOWN when they need 40-120s | 40e | IMPORTANT |
| 46 | VM Infrastructure | Stuck exec cleanup only — 5 execs cleared, webhooks restored without restart | 40f | IMPORTANT |
| 47 | VM Infrastructure | Stuck execs + n8n restart required — cleanup alone insufficient when webhooks timeout despite healthz OK | 40g | CRITICAL |
| 48 | HF Space | nginx reverse proxy causes persistent 502 (n8n must listen directly on 7860) | 42 | CRITICAL |
| 49 | HF Space | n8n SQLite minimal boot (strip PostgreSQL+Redis to break race conditions) | 42 | IMPORTANT |
| 50 | n8n API | v2.8+ login field change: emailOrLdapLoginId (not email) | 42 | IMPORTANT |
| 51 | HF Space | set -e kills container on any transient failure in entrypoint.sh | 42 | CRITICAL |
| 52 | n8n Workflows | Hardcoded API keys in workflow JSONs expire and cause 401 errors | 43 | CRITICAL |
| 53 | n8n Workflows | Credential ID mismatch after fresh import (non-existent IDs) | 43 | CRITICAL |
| 54 | n8n Workflows | Broken expression syntax `={{.VAR}}` instead of `={{$env.VAR}}` | 51 | CRITICAL |
| 55 | Infrastructure | mon-ipad repo growing too large (datasets/snapshots/logs) | 51 | IMPORTANT |
| 59 | OpenRouter | Free models rate-limited — swap Llama/Gemma → Mistral/StepFun | 54 | CRITICAL |
| 60 | HF Space | CONFIG_ERROR from duplicate secret+variable names | 54 | CRITICAL |
| 61 | Jina/Cohere | API credits exhausted — embeddings + reranking blocked | 54 | CRITICAL |
| 62 | n8n Credentials | Jina + Cohere credentials missing on HF Space | 54 | IMPORTANT |
| 63 | HF Space | N8N_BLOCK_ENV_ACCESS_IN_NODE missing — ALL $env denied | 58 | CRITICAL |
| 64 | Ingestion V4.0 | Redis lock nodes prevent workflow startup (HTTP 500) | 61 | CRITICAL |
| 65 | HF Space | N8N_BLOCK_ENV_ACCESS_IN_NODE=false deployed to 10 HF Spaces | 62 | CRITICAL |
| 66 | HF Space | Credential restore script for post-rebuild recovery | 62 | CRITICAL |
| 67 | HF Space | HF Space rebuilds reset all webhook registrations | 62 | IMPORTANT |
| 68 | Quantitative | SQL Validator only parses JSON — LLM returns markdown/CoT → extraction fails | 75 | CRITICAL |
| 69 | Quantitative | Postgres credential ID mismatch (cH96→b44av) — Schema Introspection returns 0 rows | 75 | CRITICAL |
| 70 | Quantitative | tenant_id='default' vs 'benchmark' — SQL returns 0 rows despite correct query | 75 | CRITICAL |
| 71 | n8n Workflows | Duplicate active workflows with same webhook ID — wrong one handles requests | 75 | CRITICAL |
| 72 | n8n API | n8n 2.8+ activate requires versionId POST body (not just PATCH active=true) | 75 | IMPORTANT |
| 73 | n8n API | API key (X-N8N-API-KEY) returns 401 — use cookie auth via /rest/login instead | 75 | IMPORTANT |
| 74 | n8n Expressions | {{ 'model' \|\| 'fallback' }} in jsonBody not evaluated — hardcode or ={{ }} | 69 | CRITICAL |
| 75 | Data-Ingestion | 6 LLM nodes (3 ingestion + 3 enrichment) switched to LiteLLM proxy | 69 | IMPORTANT |
| 76 | Eval Scripts | Orchestrator duplication bug — Phase 3 loader mirrored 10,700 extra questions | 69 | CRITICAL |
| 77 | Eval Scripts | run-eval-parallel.py hardcoded 45s timeouts overriding source module 90/120/180s | 69 | IMPORTANT |
| 78 | Neo4j Ingestion | tx/commit returns 403 on Aura — use /db/neo4j/query/v2 (Query API) | 69 | CRITICAL |
| 79 | Neo4j Ingestion | Sequential statements 100x slower — use UNWIND $rows for bulk ops | 69 | IMPORTANT |

---

### FIX-63: N8N_BLOCK_ENV_ACCESS_IN_NODE missing (CRITICAL — Most Common)

**Session**: 58, 62, 65 (recurrent)
**Component**: HF Space — ALL workflows using $env.*
**Symptom**: ALL pipelines return "Unable to generate answer" or "NO_ANSWER". Execution data shows `{"error": "access to env vars denied"}` in HTTP Request nodes.

**Root cause**: n8n 2.8.3 blocks `$env.*` access in ALL node types by default. The entrypoint.sh was missing `N8N_BLOCK_ENV_ACCESS_IN_NODE=false`. Despite 20+ HF secrets correctly set, n8n refused to resolve them.

**Fix**:
```bash
# Add to entrypoint.sh BEFORE n8n start
export N8N_BLOCK_ENV_ACCESS_IN_NODE=false
```

**Impact**: CROSS-PIPELINE — fixes ALL 5 pipelines simultaneously.
**RULE**: This config MUST ALWAYS be present in entrypoint.sh.

---

### FIX-71: Duplicate workflows with same webhook ID

**Session**: 75
**Symptom**: PATCH updates to workflow code have no effect. Execution uses old code.

**Root cause**: Two Quant workflows (V3.1 `cjhEhVs0KV1ExHqX` and V5.0 `EW07B8H7OmoghE8Z`) were BOTH active with the same webhook ID. V3.1 was handling all requests. Patching V5.0 had no effect.

**Fix**: Identify which workflow ID appears in execution data (`workflowId` field). Deactivate the stale one, fix the active one.

**Debug**:
```bash
GET /rest/executions?workflowId=X&limit=1
# Check data.results[0].workflowId in flatted format
```

**RULE**: Before patching a workflow, ALWAYS check the execution's `workflowId` to confirm which workflow is actually running.

---

### FIX-68: SQL Validator only parses JSON

**Session**: 75
**Symptom**: Quant pipeline always returns `SQL_GENERATION_ERROR: Invalid LLM response`. LLM generates correct SQL but wrapped in markdown Chain-of-Thought format.

**Root cause**: SQL Validator uses `JSON.parse(content)` which fails when content starts with `### Chain-of-Thought`. SQL is inside ` ```sql ` code blocks.

**Fix**: Multi-strategy extraction in SQL Validator:
```javascript
// Strategy 1: JSON.parse
// Strategy 2: ```sql block regex
// Strategy 3: ```json block regex
// Strategy 4: raw SELECT regex
```

**RULE**: Always handle both JSON and markdown LLM responses. Free-tier models (Llama 70B via Groq) often return markdown even when asked for JSON-only.

---

### FIX-34: executeWorkflow returns empty (respondToWebhook)

**Session**: 27
**Pipeline**: Orchestrator V10.1
**Symptom**: Orchestrator returns 200 empty body. Standard/Graph/Quant work individually.

**Root cause**: `executeWorkflow` nodes call sub-workflows that use `respondToWebhook`. The respondToWebhook sends HTTP response to original client but DOES NOT return data to parent executeWorkflow node. Result: `data.main: [[]]` (empty array).

**Fix**: Replace `executeWorkflow` with `httpRequest` POST to webhook:
```json
{
  "type": "n8n-nodes-base.httpRequest",
  "url": "http://localhost:5678/webhook/rag-multi-index-v3",
  "method": "POST",
  "body": {"query": "={{$json.task_query}}"},
  "timeout": 30000
}
```

**RULE**: NEVER use `executeWorkflow` for workflows that use `respondToWebhook`. Use `httpRequest` instead.

---

### FIX-42: Stuck executions block webhook response

**Session**: 40b
**Symptom**: All webhooks accept HTTP POST but never respond (curl hangs, eventually times out with code 000). `healthz` returns 200. Logs show "Execution is already being resumed" spam.

**Root cause**: 79 executions stuck in `new`/`running` status. n8n tries to resume ALL on startup, consuming all processing capacity. New webhook requests are accepted but queued behind stuck execution resume attempts.

**Fix**:
```bash
# 1. Stop n8n
docker stop n8n-n8n-1

# 2. Delete stuck executions
docker exec n8n-postgres-1 psql -U n8n -d n8n -t -A -c \
  "DELETE FROM execution_entity WHERE status IN ('new', 'running', 'waiting', 'crashed');"

# 3. Start n8n (clean activation)
docker start n8n-n8n-1

# 4. Wait for full startup
sleep 35
```

**RULE**: When n8n hangs on webhook responses but healthz is OK, ALWAYS check for stuck executions first. This is the #1 cause of "webhooks accept but never respond".

---

### FIX-33: $env blocked for ALL node types (n8n 2.8+)

**Session**: 27
**Component**: HF Space — ALL workflows with $env
**Symptom**: Quantitative returns 200 but `"Error: access to env vars denied"`. ALL HTTP Request nodes with $env return error.

**Root cause**: n8n 2.8.3 with Task Runners evaluates ALL expressions (not just Code nodes) in sandbox. Sandbox blocks `$env` for ALL node types: Code, HTTP Request, Postgres, etc.

**Fix**: Replace ALL `$env.X` references with real values at import time in entrypoint.sh. Python script parses JSON text BEFORE parsing and replaces each `$env.VAR_NAME` with `os.environ.get(VAR_NAME, default)`.

**Impact**: 117 references across 5 workflows.

**RULE DEFINITIVE**: `$env` is FORBIDDEN in n8n 2.8+ for ALL node types. NEVER use $env in workflows. Inject values at import OR use credentials.

---

## 3. IRON RULES

> **These rules are ABSOLUTE. They override everything else.**

### RULE 1: VM Google Cloud = PILOTAGE ONLY
- **NO n8n on VM** (removed Session 42, never reinstall)
- **NO local eval** (no calling OpenRouter directly from VM)
- **NO LOCAL fallback** (DISABLED Session 57 — was masking pipeline failures)
- VM runs ONLY: Claude Code, git repos, MCP servers, eval scripts (POST to HF Space)

### RULE 2: HF Space = EXECUTION (2 instances)
- ALL n8n pipelines run on HF Space (16GB RAM each)
- ALL webhook calls go to HF Space URLs, NEVER localhost
- If HF Space is down → FIX IT, don't create local workarounds

### RULE 3: .env.local — ALWAYS EXPORT
- Every variable in `.env.local` MUST have `export` keyword
- After session compaction, child processes lose env vars if not exported

### RULE 4: NO LOCAL FALLBACK — EVER
- `call_local_reasoning()` was producing FAKE accuracy (65%+ when real was ~36%)
- If pipelines fail → FIX THE PIPELINES, don't mask with local calls

### RULE 5: HF SPACE REBUILD WIPES CREDENTIALS
- HF Space rebuild (factory reboot) wipes SQLite database including ALL credential references
- Workflows persist in JSON but credential IDs become orphaned
- setup-workflows.py must run during boot to restore credentials

### RULE 6: $env REQUIRES N8N_BLOCK_ENV_ACCESS_IN_NODE=false
- Without this flag, ALL `$env.*` expressions return "access to env vars denied"
- MUST be in entrypoint.sh: `export N8N_BLOCK_ENV_ACCESS_IN_NODE=false`

### RULE 7: source .env.local BEFORE Python scripts
- ALWAYS run `source .env.local` before any Python eval script
- Example:
```bash
source /home/termius/mon-ipad/.env.local
python3 eval/quick-test.py --questions 5
```

### RULE 8: Stuck executions cleanup pattern
- When webhooks hang (accept but never respond), ALWAYS clean stuck executions:
```bash
docker exec n8n-postgres-1 psql -U n8n -d n8n -t -A -c \
  "DELETE FROM execution_entity WHERE status IN ('new', 'running');"
```

---

## 4. QUICK REFERENCE

### 4.1 Webhook Paths — Pipelines RAG

| Pipeline | Workflow ID | Webhook Path | Field Name | Method |
|----------|-------------|--------------|------------|---------|
| **Standard** | `TmgyRP20N4JFd9CB` | `/webhook/rag-multi-index-v3` | `query` | POST |
| **Graph** | `6257AfT1l4FMC6lY` | `/webhook/ff622742-6d71-4e91-af71-b5c666088717` | `query` | POST |
| **Quantitative** | `cjhEhVs0KV1ExHqX` (V3.1 active) | `/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9` | `query` | POST |
| **Orchestrator** | `ALd4gOEqiKL5KR1p` | `/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0` | `query` | POST |

### 4.2 Standard Call Format

```bash
# ALWAYS use 'query' (never 'question')
curl -s -X POST "http://localhost:5678/webhook/<PATH>" \
  -H "Content-Type: application/json" \
  -d '{"query": "your question here"}'

# With JSON formatting
curl -s -X POST "http://localhost:5678/webhook/<PATH>" \
  -H "Content-Type: application/json" \
  -d '{"query": "your question here"}' | python3 -m json.tool
```

### 4.3 n8n API Authentication (VM)

```bash
# VM n8n has NO API key configured
# Method 1: MCP n8n (preferred — but sometimes empty under memory pressure)
# Method 2: PostgreSQL direct
docker exec n8n-postgres-1 psql -U n8n -d n8n -t -A -c "SELECT ..."
# Method 3: If API REST needed, create API key in n8n UI
# NEVER use Authorization: Bearer or X-N8N-API-KEY without verifying key exists
```

### 4.4 Pre-Flight Checklist BEFORE Any Test

```
PRE-TEST CHECKLIST:
[ ] 1. Webhook path verified in Section 4.1 above
[ ] 2. Field name = 'query' (not 'question')
[ ] 3. Content-Type: application/json
[ ] 4. n8n is up: curl -s http://localhost:5678/healthz
[ ] 5. Workflow is active: docker exec n8n-postgres-1 psql -U n8n -d n8n -t -A \
        -c "SELECT active FROM workflow_entity WHERE id = '<ID>';"
```

---

## 5. RECURRING PATTERNS & SOLUTIONS

### 5.1 Pattern: Fix present but runtime uses old code

**Symptom**: Code modified via REST API, GET confirms change, but runtime behavior doesn't change.

**Solution**: Cycle PUT → Deactivate → Activate (FIX-21).

**Lesson**: n8n caches compiled Code nodes in memory. Simple PUT doesn't recompile.

---

### 5.2 Pattern: "[object Object]" in response

**Symptom**: Output contains `[object Object]` instead of error details.

**Cause**: JavaScript concatenates Error object with string.

**Solution**:
```javascript
typeof obj === 'object' ? JSON.stringify(obj) : obj
```

**Prevention**: Always serialize with typeof check before string concatenation.

---

### 5.3 Pattern: SQL valid but result wrong

**Symptom**: SQL executes without error but returns wrong value.

**Cause**: LLM generates WHERE matching wrong record (ex: `company_name = 'TechVision'` instead of `'TechVision Inc'`).

**Solution**:
- Use `ILIKE '%keyword%'` instead of `= 'exact match'`
- Include sample data rows in LLM prompt
- SQL templates for known patterns

---

### 5.4 Pattern: HuggingFace dataset not found

**Symptom**: `Invalid username or password` or 404 on download.

**Cause**: HF ID incorrect (namespace/name changes).

**Solution**: Always verify with `mcp__huggingface__hf_search_datasets` BEFORE adding dataset.

**Lesson**: HF IDs change often (redirects, renames). 6/11 were wrong in session 25.

---

### 5.5 Pattern: Workflow n8n import fails on fresh DB

**Symptom**: `SQLITE_CONSTRAINT: FOREIGN KEY constraint failed`.

**Cause**: Exported workflows contain FKs to source DB entities (shared, activeVersion, versionId).

**Solution**: Strip FK fields before import (FIX-18).

```python
FK_FIELDS = ['shared', 'activeVersion', 'activeVersionId', 'versionId', 'versionCounter']
for field in FK_FIELDS:
    if field in wf:
        del wf[field]
```

---

### 5.6 Pattern: Environment variable inaccessible in Code node

**Symptom**: `access to env vars denied` in Code node n8n.

**Cause**: Task runners (n8n >= 2.7.4) isolate Code nodes. `$env.VAR` works but `process.env.VAR` doesn't.

**Solution**: Use `$env.VAR_NAME` (not `process.env`). Requires N8N_BLOCK_ENV_ACCESS_IN_NODE=false.

---

### 5.7 Pattern: Test passes in quick-test but fails in eval complete

**Symptom**: 5/5 PASS in smoke test, but low accuracy in eval 50q+.

**Cause**: Quick-test uses "easy" questions with `expected_contains: ""` (empty). Eval complete has precise expected values.

**Solution**: Always validate with complete eval (50q minimum) before declaring fix successful.

---

### 5.8 Pattern: Test webhook with wrong path or field name

**Symptom**: 404 "webhook not registered" or VALIDATION_ERROR "query is required".

**Cause**: Webhook path typed from memory (or copied from old session), or field name incorrect (`question` instead of `query`).

**Solution**: ALWAYS consult Section 4.1 QUICK REFERENCE before any test.

**Frequency**: VERY HIGH — reproduces almost every session.

**Prevention**: Add automatic pre-flight check in eval scripts.

---

### 5.9 Pattern: n8n REST API 401 — header required

**Symptom**: `{"message":"'X-N8N-API-KEY' header required"}` on REST API calls.

**Cause**: VM n8n has no `N8N_PUBLIC_API_KEY` configured in Docker. Public API is enabled (`N8N_PUBLIC_API_DISABLED=false`) but without key.

**Solution**: Use PostgreSQL direct (`docker exec n8n-postgres-1 psql ...`) or MCP n8n.

**Prevention**: Section 4.3 QUICK REFERENCE — never attempt REST API without verifying auth.

---

### 5.10 Pattern: curl returns 200 but empty body

**Symptom**: HTTP 200 but no content in response.

**Cause**: n8n webhook returns empty array `[]` or workflow has no Respond node.

**Solution**: Verify workflow has "Respond to Webhook" node correctly configured.

---

### 5.11 Pattern: n8n Task Runner executes old code despite restart

**Symptom**: Code updated in PostgreSQL (verified via psql). n8n restarted (docker restart). But execution uses OLD code.

**Cause**: Task Runner (subprocess isolated, n8n >= 2.7.4) caches compiled code. Even complete container restart doesn't guarantee recompilation.

**Solution**: DO NOT modify workflows on VM. Modify directly on HF Space n8n (16GB RAM, functional REST API, no cache issue due to fresh import).

**Prevention**: Architectural rule — VM = pilotage ONLY. Workflow modifications = HF Space.

---

## 6. ANTI-PATTERNS TO ELIMINATE

| # | Anti-Pattern | Frequency | Prevention |
|---|-------------|-----------|------------|
| AP-1 | Test webhook with path typed from memory | EVERY SESSION | Consult Section 4.1 |
| AP-2 | Use `question` instead of `query` as field name | FREQUENT | Consult Section 4.2 |
| AP-3 | Attempt n8n REST API without verifying API key exists | FREQUENT | Consult Section 4.3 |
| AP-4 | Re-debug problem already solved in this library | OCCASIONAL | Read Section 2 FIRST |
| AP-5 | Modify multiple nodes at once | OCCASIONAL | Rule 10: 1 fix per iteration |
| AP-6 | Patch nodes[] but not activeVersion.nodes[] | EVERY FIX | Always patch BOTH (FIX-29, FIX-32) |
| AP-7 | Use $env without N8N_BLOCK_ENV_ACCESS_IN_NODE=false | CRITICAL | Verify entrypoint.sh includes export |
| AP-8 | Deploy HF Space without N8N_BLOCK_ENV_ACCESS_IN_NODE=false | CRITICAL | Without flag, ALL $env return "denied" |
| AP-9 | Use executeWorkflow when sub-wf has respondToWebhook | CRITICAL | executeWorkflow returns empty — use httpRequest (FIX-34) |
| AP-10 | OpenRouter URL without /chat/completions | CRITICAL | API returns HTML instead of JSON (FIX-35) |
| AP-11 | Mix Phase 2 questions in Phase 1 gates | CRITICAL | Each phase filters its own questions (FIX-36) |
| AP-12 | Send context-rich questions to SQL pipeline | CRITICAL | Classifier detects format and routes to context reasoning (FIX-37) |

---

## 7. LLM MODELS & BEHAVIOR

### 7.1 Catalogue of deployed models (OpenRouter Free Tier)

| Model | ID OpenRouter | Params | Context | Strengths | Weaknesses | Rate Limit |
|-------|---------------|--------|---------|-----------|------------|------------|
| **Llama 3.3 70B** | `meta-llama/llama-3.3-70b-instruct:free` | 70B | 128K | SQL generation, reasoning multi-step, planning | Rate-limit frequent (429), sometimes malformed JSON | ~20 req/min |
| **Gemma 3 27B** | `google/gemma-3-27b-it:free` | 27B | 8K | Fast classification, routing, short responses | Short context (8K), not ideal for complex SQL | ~20 req/min |
| **Trinity Large** | `arcee-ai/trinity-large-preview:free` | ~7B | 32K | Entity extraction, summaries, structured output | Limited reasoning, not for SQL | ~20 req/min |

### 7.2 Candidate models (tested or identified, not deployed)

| Model | ID OpenRouter | Params | Context | Potential | Note |
|-------|---------------|--------|---------|-----------|------|
| **Qwen 3 235B** | `qwen/qwen3-235b-a22b:free` | 235B MoE | 40K | Better SQL than Llama? To test | MoE, free, good SQL benchmark |
| **Qwen 2.5 Coder 32B** | `qwen/qwen-2.5-coder-32b-instruct:free` | 32B | 32K | SQL + code generation | Specialized code, could be better for SQL |
| **DeepSeek V3** | `deepseek/deepseek-chat-v3-0324:free` | 671B MoE | 128K | Advanced reasoning | Large model, may be slow |
| **Mistral Small 3.1** | `mistralai/mistral-small-3.1-24b-instruct:free` | 24B | 128K | Good size/quality ratio | Long context, multilingual |

### 7.3 Model Assignment Matrix

| Env Variable | Current Model | Role | Workflow(s) | Tested Alternatives |
|--------------|---------------|------|-------------|---------------------|
| `LLM_SQL_MODEL` | Llama 70B | SQL generation | Quantitative | gemma-3-12b (too weak), qwen3-235b to test |
| `LLM_FAST_MODEL` | Gemma 27B | Fast classification | Orchestrator, Quantitative | — |
| `LLM_INTENT_MODEL` | Llama 70B | Intent classification | Orchestrator | — |
| `LLM_PLANNER_MODEL` | Llama 70B | Task planning | Orchestrator | — |
| `LLM_AGENT_MODEL` | Llama 70B | Agent reasoning | Orchestrator | — |
| `LLM_HYDE_MODEL` | Llama 70B | HyDE queries | Standard | — |
| `LLM_EXTRACTION_MODEL` | Trinity | Entity extraction | Enrichment | — |
| `LLM_COMMUNITY_MODEL` | Trinity | Community summaries | Graph | — |

### 7.4 Observed Behaviors by Model

#### Llama 3.3 70B
- **SQL generation**: Generates correct SQL ~80% of time. Fails on:
  - Multi-table complex JOINs
  - Period aggregations (FY vs Q1-Q4) — often confused
  - Entity names with variants (TechVision vs TechVision Inc)
- **Rate-limit**: ~20 req/min. Beyond → 429. Retries 3x with 8s wait works.
- **JSON output**: Sometimes generates invalid JSON (trailing comma, single quotes). Workaround: parser with try/catch + regex cleanup.
- **Timeout**: 25s too short under load. 60-90s recommended.

#### Gemma 3 27B
- **Classification**: Excellent for intent detection (standard/graph/quant/orchestrator)
- **Short context**: 8K tokens = problem if DB schema is long. Workaround: static compact schema in prompt.
- **Speed**: ~2x faster than Llama 70B in response time.

#### Trinity Large
- **Entity extraction**: Good for structured NER (persons, orgs, places).
- **Summaries**: Generates coherent community summaries for Graph RAG.
- **Limitation**: Not reliable for complex reasoning or SQL.

### 7.5 LLM Resilience Strategies

| Strategy | Implementation | Impact |
|----------|---------------|--------|
| **Retry with backoff** | maxTries=3, waitBetweenTries=8000ms | Eliminates ~80% of 429s |
| **neverError=true** | On HTTP Request nodes n8n | Prevents workflow crash |
| **Model rotation** | Alternate Llama/Qwen/Gemma per minute | Distributes rate-limit load |
| **Fallback cascade** | Primary → Fallback → Template SQL | Guarantees always a response |
| **Template matching** | Bypass LLM for simple questions (single metric + company + year) | +2pp accuracy |
| **Static schema** | Prompt includes precomputed compact schema | Reduces tokens, improves SQL |
| **Sample data in prompt** | Include 3-5 real data rows in prompt | Anchors LLM expectations |

### 7.6 OpenRouter Rate-Limit — What We Know

- **Global limit**: ~20 req/min per API key (all models combined)
- **429 response**: `{"error":{"message":"Rate limit exceeded","type":"rate_limit_error"}}`
- **Useful headers**: `x-ratelimit-remaining`, `x-ratelimit-reset`
- **OLD workaround**: 8s delay between quantitative requests (3 LLM calls per question)
- **Impact**: Quantitative makes 2-3 LLM calls per question (SQL gen + validation/repair + interpretation). At 20 req/min, max ~7 questions/minute.
- **Multi-key IMPLEMENTED**: **7 keys (3 accounts) → ~140 req/min aggregate** (Session 43)

**Key Rotation System (Session 43)**:
```python
from openrouter_key_rotation import get_rotator

rotator = get_rotator()  # Loads all keys from env
api_key = rotator.get_next_key()  # Returns least-used key
# ... make request ...
rotator.record_usage(api_key)  # Track usage
```

**Environment vars**:
```bash
OPENROUTER_API_KEY=sk-or-v1-xxxxx          # Main (Account 1)
OPENROUTER_KEY_STANDARD=sk-or-v1-xxxxx    # Standard pipeline
OPENROUTER_KEY_GRAPH=sk-or-v1-xxxxx       # Graph pipeline
OPENROUTER_KEY_QUANTITATIVE=sk-or-v1-xxxxx  # Quantitative (Account 2)
OPENROUTER_KEY_ORCHESTRATOR=sk-or-v1-xxxxx  # Orchestrator (Account 2)
OPENROUTER_KEY_PME=sk-or-v1-xxxxx           # PME (Account 3)
OPENROUTER_KEY_ACCOUNT3=sk-or-v1-xxxxx      # Additional key
```

**Result**: 7x throughput increase (20 req/min → 140 req/min)

---

## 8. APIS & EXTERNAL SERVICES

### 8.1 OpenRouter

**Basic info**:
- **URL**: `https://openrouter.ai/api/v1/chat/completions`
- **Auth**: `Authorization: Bearer sk-or-v1-...`
- **Rate limit**: ~20 req/min per key (free tier)
- **Common errors**:
  - 429: Rate limit → use key rotation system
  - 400: JSON parsing failed → verify body
  - 502/503: Server temporarily unavailable → retry
- **Quota**: Unlimited requests/day, but rate-limited per minute

### 8.2 Jina AI

- **Embeddings**: `https://api.jina.ai/v1/embeddings` (model: `jina-embeddings-v3`, dim 1024)
- **Reranker**: `https://api.jina.ai/v1/rerank` (model: `jina-reranker-v2-base-multilingual`)
- **Quota**: 10M tokens/month (free)
- **Common error**: `trailing comma` in JSON body (FIX-04)

### 8.3 Cohere

- **Reranker**: `https://api.cohere.ai/v1/rerank`
- **Status**: Trial ALMOST EXHAUSTED. 2 keys, both close to expiration.
- **Alternative**: Jina reranker is primary now.

### 8.4 Pinecone

- **Primary index**: `sota-rag-jina-1024` (dim=1024, free tier, 21,073 vectors)
- **Common error**: Dimension mismatch if sending Cohere vectors (1536d) to Jina index (1024d) (FIX-12)
- **Namespaces**: 12 active ns (squad, hotpotqa, musique, etc.)

### 8.5 Neo4j Aura

- **API URL**: `https://38c949a2.databases.neo4j.io/db/neo4j/query/v2`
- **Auth**: Basic (neo4j:password)
- **TRAP**: bolt:// protocol DOES NOT work via HTTP Request n8n. Always HTTPS API (FIX-07).
- **Content**: 19,788 nodes, 76,717 relations

### 8.6 Supabase

- **URL**: `https://ayqviqmxifzmhphiqfmj.supabase.co`
- **Key tables**: financials (24 rows), balance_sheet (12), sales_data (1152), employees (150), products (18)
- **Companies**: TechVision Inc, GreenEnergy Corp, HealthPlus Labs
- **Periods**: FY 2020-2023, Q1-Q4 2023
- **tenant_id**: ALWAYS `'benchmark'` (NOT 'default') for eval data

---

## 9. DATABASES & SCHEMAS

### 9.1 Supabase Schema — Quantitative Pipeline

```sql
-- Companies and available periods
SELECT DISTINCT company_name, fiscal_year, period FROM financials ORDER BY company_name, fiscal_year, period;
-- Result: 3 companies x (4 FY + 4 Q) = 24 rows

-- Most requested financials columns
-- revenue, net_income, gross_profit, operating_income, research_development, diluted_eps, basic_eps

-- Most reliable SQL pattern
SELECT metric FROM financials
WHERE company_name ILIKE '%keyword%' AND fiscal_year = YYYY AND period = 'FY'
AND tenant_id = 'benchmark'
LIMIT 1;
```

### 9.2 Neo4j — Graph RAG Entities

```cypher
// Node types
MATCH (n) RETURN DISTINCT labels(n), count(n) ORDER BY count(n) DESC;
// __Entity__ (7628), __Community__ (6143), Document (3176), Chunk (2841)

// Relationships
MATCH ()-[r]->() RETURN type(r), count(r) ORDER BY count(r) DESC;
// RELATED_TO (57,000+), IN_COMMUNITY, HAS_ENTITY, etc.
```

### 9.3 Pinecone — Namespaces

```
sota-rag-jina-1024: 21,073 vectors
  Namespaces: squad, hotpotqa, musique, nq, finqa, cuad, covidqa,
              pubmedqa, techqa, tatqa, emanual, doqa
```

---

## 10. INFRASTRUCTURE & PERFORMANCE

### 10.1 VM Google Cloud — Constraints

- **RAM**: 969 MB total, ~400 MB free (n8n removed Session 42). Claude Code = ~280 MB.
- **RULE**: Never heavy tests on VM. Pilotage ONLY.
- **Swap**: ~1 GB used permanently. Memory-intensive operations are slow.
- **Disk**: 30 GB, 17 GB free.
- **RECURRENT TRAP**: Old Claude Code sessions stay in memory (zombie PID). At session start: `ps aux | grep claude | grep -v grep` and kill old PIDs. Each session = ~280 MB.
- **RAM cleanup**: `sync && echo 3 | sudo tee /proc/sys/vm/drop_caches` frees 20-50 MB filesystem cache.
- **OOM CASCADE (FIX-40)**: When swap reaches 100%, PostgreSQL connections timeout → n8n webhooks 404. Symptoms: healthz=OK but "Cannot POST /webhook/..." or 503. Fix: 1) Kill zombies (git pack-objects, old eval scripts, old claude sessions), 2) Clean execution_entity table, 3) Full docker compose down/up, 4) Wait ~65-110s startup.
- **STUCK EXECUTION HANG (FIX-42)**: Webhooks accept HTTP connection but NEVER respond (curl hangs, HTTP code 000 on timeout). Healthz=200. Logs show "Execution is already being resumed" spam. Root cause: 79+ stuck executions in `new`/`running` status. Fix: clean stuck execs + restart.

### 10.2 HF Space — Capabilities

- **RAM**: 16 GB (cpu-basic, $0)
- **n8n**: 2.8.3 (latest), SQLite, Redis removed
- **Limitation**: HF proxy breaks POST body for /rest/ and /api/ (FIX-15)
- **Webhooks**: Function normally (Standard, Graph OK; Quantitative needs Supabase data)

### 10.3 Concurrent Load Testing Results (Session 27)

Tested on HF Space (cpu-basic, 16GB RAM) with parallel-pipeline-test.py v2.

| Config | Pipelines | Concurrency | Total Concurrent | Standard | Graph | Orchestrator |
|--------|-----------|-------------|-----------------|----------|-------|--------------|
| Baseline | 3 | 1 | 3 | 100% (9s) | 100% (18s) | 100% (14s) |
| Moderate | 3 | 3 | 9 | 100% (23s) | 90% (26s) | 70% (35s) |
| Stress | 3 | 5 | 15 | 100% (29s) | 90% (44s) | 0% AUTO-STOP |
| Solo | 1 | 5 | 5 | 100% (16s) | N/A | N/A |

**Key findings**:
- **Standard pipeline is rock solid** at any concurrency (100% even at 15 concurrent)
- **Graph pipeline** drops 1 question (keyword mismatch, test data issue, not pipeline)
- **Orchestrator degrades under concurrent load** (delegates to sub-pipelines already serving requests → empty responses)
- **Latency scales linearly** with concurrency: ~2-3x at concurrency=5
- **HF Space cpu-basic handles 15 concurrent executions** without crashing (16GB RAM sufficient)

**Recommended concurrency**:
- Standard: concurrency=5 (safe)
- Graph: concurrency=3 (safe)
- Orchestrator: concurrency=1 (must not compete with sub-pipelines)
- Cross-pipeline: max 9 concurrent total (3 pipelines x 3 questions)

---

## 11. EVALUATION & TESTING

### 11.1 Result Interpretation

- **5/5 PASS in quick-test** ≠ pipeline OK. Smoke questions are easy.
- **Accuracy evaluation**: Compare `response` with `expected_answer` via fuzzy matching.
- **Quantitative**: Expected values are precise numbers. Even "almost correct" (wrong company, wrong period) is FAIL.
- **Graph**: Responses are often sentences. Matching searches keywords.

### 11.2 False Negative Causes

- OpenRouter 429 → timeout → "Unable to generate SQL" → FAIL (not real pipeline error)
- n8n 503 transient → timeout → FAIL
- Matching too strict (ex: "6.7 billion" vs "6,745,000,000")

### 11.3 Phase 1 vs Phase 2 Filtering (FIX-36, Session 30)

**Symptom**: Phase 1 gates blocked (Graph 68.7%, Quant 78.3%) while pipelines passed their targets on Phase 1 questions alone.

**Root cause**: `generate_status.py` and `phase_gates.py` counted ALL questions from `question_registry` (including musique, finqa = Phase 2 datasets) in Phase 1 calculation.

**Fix**: Added `_is_phase1_question(qid)` excluding IDs containing "musique", "finqa", or "phase2" from Phase 1 calc.

**Result**: Phase 1 PASSED — Standard 85.5%, Graph 78.0%, Quant 92.0%, Orch 80.0%, Overall 83.9%.

**RULE**: Phase 2 questions MUST NEVER be included in Phase 1 calculation. Phase 2 has its own targets (Graph 60%, Quant 70%, Overall 65%).

### 11.4 Recommended Delays Between Questions

| Pipeline | Delay | Reason |
|----------|-------|--------|
| Standard | 3s | No OpenRouter LLM |
| Graph | 5s | 1 LLM call (community synthesis) |
| Quantitative | 8-10s | 2-3 LLM calls (SQL gen + interpretation + repair) |
| Orchestrator | 5s | 1-2 LLM calls (routing + delegation) |

---

## ADDING NEW SYMPTOMS

When a new problem is resolved and not in this document:

1. Identify the diagnostic tree (Section 1.1-1.3)
2. Add branch to the tree
3. Add entry to Quick Symptom Matrix (Section 1.4)
4. Document fix in Section 2 (Fixes Library)
5. Add pattern to Section 5 (Recurring Patterns)
6. Commit + push immediately

---

## HISTORY OF ADDITIONS

| Session | Additions | Date |
|---------|-----------|------|
| 25 | Document creation, LLM models, 8 patterns, APIs, schemas | 2026-02-19 |
| 27 | $env forbidden all nodes, executeWorkflow empty | 2026-02-19 |
| 30 | Phase1 vs Phase2 filtering, FIX-36 | 2026-02-20 |
| 35 | Neo4j data quality, 98% generic relationships | 2026-02-21 |
| 40 | OOM cascade, stuck executions, VM infrastructure fixes | 2026-02-23 |
| 42 | HF Space minimal boot, nginx removal, SQLite mode | 2026-02-23 |
| 43 | Credential remapping, hardcoded API keys removal | 2026-02-23 |
| 54 | HF Space secrets management, API credits exhaustion | 2026-02-24 |
| 58-62 | N8N_BLOCK_ENV_ACCESS_IN_NODE critical fix | 2026-02-24 to 2026-02-25 |
| 75 | Session 75 critical discoveries (SQL validator, duplicate workflows, tenant_id) | 2026-03-07 |
| 76 | DEBUG-PLAYBOOK.md consolidation from 3 separate files | 2026-03-07 |
