# HF Space Webhook Status Report
**Timestamp**: 2026-02-23T16:30:00Z

## Summary
- **n8n HF Space**: https://lbjlincoln-nomos-rag-engine.hf.space
- **Health**: 200 OK — server is alive
- **Workflows**: CRITICAL ISSUE — Only 1/5 webhooks responding, others failing with 000/timeout or 404

## Detailed Results

### 1. Health Check
```
URL: /healthz
Status: HTTP 200 ✓
Body: (empty response but status is 200)
Conclusion: n8n server is RUNNING and responding
```

### 2. Standard Pipeline (rag-multi-index-v3)
```
URL: /webhook/rag-multi-index-v3
Status: HTTP 000 (TIMEOUT)
Body: (no response)
Duration: ~15s timeout
Conclusion: BROKEN — webhook activated but not responding, likely crash or hang
Symptom: Same as Graph pipeline (000 timeout)
```

### 3. Quantitative Pipeline (3e0f8010-...)
```
URL: /webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9
Status: HTTP 500 (Internal Server Error)
Body: {"message":"Error in workflow"}
Conclusion: BROKEN — workflow is active but errors on execution
Symptom: Indicates issue inside the workflow logic, not activation
```

### 4. Orchestrator Pipeline (92217bb8-...)
```
URL: /webhook/92217bb8-ffc8-459a-8331-3f553812c3d0
Status: HTTP 404 (Not Found)
Body: "The requested webhook is not registered"
Conclusion: BROKEN — workflow is NOT ACTIVATED
Evidence: "The workflow must be active for a production URL to run successfully"
Action Required: Activate this workflow in n8n
```

### 5. Graph Pipeline (ff622742-...)
```
URL: /webhook/ff622742-6d71-4e91-af71-b5c666088717
Status: HTTP 000 (TIMEOUT)
Body: (no response)
Duration: ~15s timeout
Conclusion: BROKEN — webhook activated but not responding
Symptom: Same pattern as Standard pipeline
```

## Critical Issues by Category

### Issue A: 404 Errors (Workflow Not Activated)
**Pipelines**: Orchestrator
**Root Cause**: HF Space rebuild (Session 39) wiped database, lost workflow activations
**Status**: 1/5 pipelines not activated
**Fix**: Activate workflow in n8n UI or via API

### Issue B: 000 Timeout Errors (Webhook Active But Not Responding)
**Pipelines**: Standard, Graph
**Root Cause**: Unknown — likely:
  - Internal n8n crash or infinite loop
  - Database connection issue
  - Webhook handler crash
  - Memory/resource exhaustion
**Status**: 2/5 pipelines hanging
**Fix**: Restart n8n, check logs, inspect node configurations

### Issue C: 500 Internal Server Error (Workflow Executes But Errors)
**Pipelines**: Quantitative
**Root Cause**: Unknown — issue inside workflow logic
**Status**: 1/5 pipeline erroring on execution
**Fix**: Check n8n execution logs for stack trace

### Issue D: Healthy (200 OK)
**Services**: Health endpoint
**Status**: n8n server is alive, but webhooks not responsive

## Summary Table

| Pipeline | Webhook | Status | Issue | Priority |
|----------|---------|--------|-------|----------|
| Standard | rag-multi-index-v3 | 000 timeout | Webhook hangs/crash | **CRITICAL** |
| Quantitative | 3e0f8010-... | 500 error | Workflow logic error | **CRITICAL** |
| Orchestrator | 92217bb8-... | 404 not found | NOT ACTIVATED | **HIGH** |
| Graph | ff622742-... | 000 timeout | Webhook hangs/crash | **CRITICAL** |
| Health | /healthz | 200 OK | Server alive | OK |

## Recommended Actions

1. **Immediate** (Orchestrator — quick fix):
   - Activate Orchestrator workflow in n8n UI
   - Re-test webhook

2. **High Priority** (Quantitative — error diagnosis):
   - Connect to n8n and view last execution logs
   - Check "Error in workflow" stack trace
   - Fix the issue (likely a node crashing)

3. **High Priority** (Standard + Graph — timeout investigation):
   - Check n8n logs for crash/hang patterns
   - Inspect webhook handler node configuration
   - Restart n8n if necessary
   - May indicate HF Space rebuild incompleteness

4. **Follow-up**:
   - Verify `entrypoint.sh` activation logic is working
   - Check if n8n database is corrupted post-rebuild
   - Re-import workflows if necessary

## Session Context
- Last status (Session 39): "ALL WORKFLOWS 404" after HF Space rebuild
- Current status: Mixed — some 404, some 500, some timeout, 1 healthy
- Conclusion: Partial recovery but critical issues remain blocking Phase 2 testing
