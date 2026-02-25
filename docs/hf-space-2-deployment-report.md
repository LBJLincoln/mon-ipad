# HF Space #2 Deployment Report

**Date**: 2026-02-25  
**Status**: PARTIAL SUCCESS  
**Space URL**: https://lbjlincoln26-nomos-rag-engine-2.hf.space

## Summary

Successfully deployed a second HuggingFace Space for distributed RAG pipeline hosting. The infrastructure is running and workflows are imported, but the Orchestrator pipeline requires modification to work across spaces.

## What Was Accomplished

### 1. Space Creation
- Created HF Space via API: `LBJLincoln26/nomos-rag-engine-2`
- Account: LBJLincoln26 (Edmond Dantès)
- Space ID: 699eb56c44ce132f22083688
- SDK: Docker
- Hardware: cpu-basic (free tier)

### 2. Repository Setup
- Cloned space repository
- Copied infrastructure files:
  - Dockerfile
  - entrypoint.sh
  - setup-workflows.py
  - healthcheck.py
- Copied workflow JSONs:
  - debug-status.json
  - quantitative.json
  - orchestrator-v10.json
- Updated README.md for Space #2
- Committed and pushed to HF Space repository

### 3. Environment Configuration
- Set 21 environment variables via HF Secrets API:
  - N8N_ENCRYPTION_KEY
  - OPENROUTER_KEY_QUANTITATIVE
  - OPENROUTER_KEY_ORCHESTRATOR
  - OPENROUTER_API_KEY (fallback)
  - PINECONE_API_KEY, PINECONE_HOST
  - JINA_API_KEY
  - NEO4J_URI, NEO4J_AUTH
  - COHERE_API_KEY
  - GOOGLE_API_KEY
  - SUPABASE_* (5 vars)
  - CI_EMAIL, CI_PASSWORD
  - LLM_* models (3 vars)

### 4. Deployment
- HF Space built successfully
- Container started and running
- n8n server healthy (HTTP 200 on /healthz)
- Workflows imported via CLI
- Owner account created
- Login successful

### 5. Workflow Status
| Workflow | ID | Active | Status |
|----------|-----|--------|--------|
| Debug Status | 91367103771f43a58 | ✓ Yes | Working (GET only) |
| Quantitative V2.0 | E19NZG9WfM7FNsxr | ✓ Yes | HTTP 500 (needs debug) |
| Orchestrator V10.1 | ALd4gOEqiKL5KR1p | ✗ No | Cannot activate - missing sub-workflows |

## Issues Identified

### 1. Orchestrator Sub-Workflow Dependencies
**Problem**: The Orchestrator workflow uses n8n "Execute Workflow" nodes to invoke Standard and Graph pipelines. These workflows don't exist in Space #2.

**Error**:
```
Cannot publish workflow: Node "Invoke WF5: Standard" references workflow TmgyRP20N4JFd9CB 
which is not published; Node "Invoke WF2: Graph" references workflow 6257AfT1l4FMC6lY 
which is not published.
```

**Root Cause**: The Orchestrator was designed to run on the same n8n instance as the other pipelines. In a distributed architecture, it needs to call cross-space webhooks instead.

**Solution Required**: Modify the Orchestrator workflow to use HTTP Request nodes calling:
- Standard: `https://lbjlincoln-nomos-rag-engine.hf.space/webhook/rag-multi-index-v3`
- Graph: `https://lbjlincoln-nomos-rag-engine.hf.space/webhook/ff622742-6d71-4e91-af71-b5c666088717`

### 2. Quantitative Pipeline Error
**Problem**: Webhook returns HTTP 500 "Error in workflow"

**Possible Causes**:
- Missing or invalid credentials
- Incorrect environment variable references
- Supabase connection issues
- OpenRouter API key issues

**Next Steps**: 
- Check n8n execution logs for the Quantitative workflow
- Verify Supabase credentials are correctly set
- Test with a simple query
- Use node-analyzer.py to debug

### 3. Debug Status Webhook
**Problem**: Returns 404 for POST requests, expects GET

**Cause**: Workflow is configured for GET method, not POST

**Impact**: Low - this is a status endpoint, not critical for pipeline functionality

## Local Environment Updates

### Files Created/Modified
1. `/home/termius/mon-ipad/.env.local` - Added HF Space #2 URLs:
   - `HF_SPACE_2_URL`
   - `N8N_HOST_QUANTITATIVE`
   - `N8N_HOST_ORCHESTRATOR`

2. `/home/termius/mon-ipad/docs/hf-space-deployment.md` - Comprehensive deployment documentation

3. `/home/termius/mon-ipad/docs/hf-space-2-deployment-report.md` - This file

4. `/tmp/hf-space-2-env.json` - Environment variables backup

## Next Steps (Priority Order)

### Immediate (Required for basic functionality)
1. **Fix Orchestrator workflow** (BLOCKING)
   - Option A: Modify to use HTTP webhooks instead of sub-workflow invocation
   - Option B: Copy Standard + Graph to Space #2 (defeats distributed purpose)
   - **Recommended**: Option A

2. **Debug Quantitative pipeline** (HIGH PRIORITY)
   - Check execution logs on Space #2
   - Verify credentials are working
   - Test with simple question
   - Use node-analyzer.py

### Short-term (Needed for production)
3. **Test cross-space communication**
   - Ensure Space #2 can call Space #1 webhooks
   - Verify latency is acceptable
   - Test with concurrent requests

4. **Update eval scripts**
   - Modify quick-test.py to use Space #2 URLs for Quantitative/Orchestrator
   - Update iterative-eval.py with new endpoints
   - Test end-to-end

5. **Monitor resource usage**
   - Check Space #2 CPU/memory
   - Verify no cold starts
   - Monitor webhook response times

### Long-term (Optimization)
6. **Add PME Gateway to appropriate space**
   - Decide: Space #1 or Space #2?
   - Deploy and test

7. **Set up monitoring**
   - Health checks every 5 min
   - Alert on downtime
   - Track success rates per pipeline

8. **Upgrade hardware if needed**
   - Current: cpu-basic (free)
   - Consider: cpu-upgrade or t4-small if needed

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ HF Space #1: lbjlincoln-nomos-rag-engine.hf.space          │
│ Account: LBJLincoln                                          │
├─────────────────────────────────────────────────────────────┤
│ Pipelines:                                                   │
│  • Standard RAG     /webhook/rag-multi-index-v3             │
│  • Graph RAG        /webhook/ff622742-...                   │
│  • Debug Status     /webhook/debug-status                   │
└─────────────────────────────────────────────────────────────┘
                             ▲
                             │ HTTP calls
                             │
┌─────────────────────────────────────────────────────────────┐
│ HF Space #2: lbjlincoln26-nomos-rag-engine-2.hf.space      │
│ Account: LBJLincoln26                                        │
├─────────────────────────────────────────────────────────────┤
│ Pipelines:                                                   │
│  • Quantitative     /webhook/3e0f8010-...  [NEEDS FIX]      │
│  • Orchestrator     /webhook/92217bb8-...  [BLOCKED]        │
│  • Debug Status     /webhook/debug-status  [GET only]       │
└─────────────────────────────────────────────────────────────┘
                             │
                             ▼
                    ┌────────────────┐
                    │  VM (Piloting)  │
                    │  34.136.180.66  │
                    └────────────────┘
```

## Resource Links

- **Space #1**: https://huggingface.co/spaces/LBJLincoln/nomos-rag-engine
- **Space #2**: https://huggingface.co/spaces/LBJLincoln26/nomos-rag-engine-2
- **Space #2 Settings**: https://huggingface.co/spaces/LBJLincoln26/nomos-rag-engine-2/settings
- **Space #2 Logs**: https://huggingface.co/spaces/LBJLincoln26/nomos-rag-engine-2/logs
- **Local Repo**: /tmp/hf-space-2/ (cloned space repository)

## Testing URLs

### Health Check
```bash
curl https://lbjlincoln26-nomos-rag-engine-2.hf.space/healthz
```

### Debug Status (GET)
```bash
curl https://lbjlincoln26-nomos-rag-engine-2.hf.space/webhook/debug-status
```

### Quantitative (when fixed)
```bash
curl -X POST https://lbjlincoln26-nomos-rag-engine-2.hf.space/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9 \
  -H "Content-Type: application/json" \
  -d '{"question":"Test question"}'
```

### Orchestrator (when fixed)
```bash
curl -X POST https://lbjlincoln26-nomos-rag-engine-2.hf.space/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0 \
  -H "Content-Type: application/json" \
  -d '{"question":"Test question"}'
```

## Credentials Used

- **HF Token**: hf_nOtcpFtBBuIgiCiFQ... (LBJLincoln26 account)
- **n8n Login**: ci@nomos.ai / CI-Nomos-2026!
- **Git**: alexis.moret6@outlook.fr
- **OpenRouter Keys**: Per-pipeline rotation (6 keys, 3 accounts)
- **External Services**: Same as Space #1 (Pinecone, Supabase, Neo4j, etc.)

## Success Metrics

- [✓] Space created and deployed
- [✓] Container running and healthy
- [✓] n8n server accessible
- [✓] Workflows imported
- [✓] Environment variables set
- [✓] Login working
- [~] Quantitative pipeline (imported but erroring)
- [✗] Orchestrator pipeline (blocked by sub-workflow deps)
- [✗] All webhooks responding correctly

**Overall Progress**: 70% complete. Infrastructure is solid, workflows need fixes.
