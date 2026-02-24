# PME Gateway Workflow Import Report

**Date**: 2026-02-24
**Task**: Import and activate PME Gateway workflow into HF Space n8n
**Status**: ✅ IMPORTED (workflow created) | ⚠️ REQUIRES MANUAL ACTIVATION

---

## Summary

The PME Gateway workflow ("Multi-Canal Gateway") has been successfully imported into the HF Space n8n instance but requires manual activation to register webhooks.

### Workflow Details

- **Name**: Multi-Canal Gateway
- **ID on HF Space**: `XhnGNbcnYv6gtAte`
- **Webhook Path**: `/webhook/pme-assistant-gateway`
- **Total Nodes**: 10
- **Active**: ❌ False (needs activation)
- **Saved to**: 
  - `/home/termius/mon-ipad/n8n/live/pme-gateway.json`
  - `/home/termius/mon-ipad/hf-space/n8n-workflows/pme-gateway.json`

### Workflow Architecture

The PME Gateway implements a multi-channel chatbot routing system:

1. **Webhook Trigger** — Entry point for PME assistant questions
2. **Channel Detector** — Detects communication channel (Slack, Gmail, direct API)
3. **Intent Classifier** — LLM-based intent classification
4. **Parse Intent** — Parses LLM response to extract intent type
5. **Switch Router** — Routes requests based on intent:
   - **search** → RAG Search via Orchestrator
   - **action** → Action Executor (create tasks, calendar events, etc.)
   - **report** → Report Generator
6. **Response Formatter** — Formats final response for the channel
7. **Respond to Webhook** — Returns response to caller

### Current State

✅ **Working**: 11 out of 18 workflows are active on HF Space
❌ **Blocked**: PME Gateway returns 404 because workflow is inactive

```bash
# Test command (currently fails with 404)
curl -X POST "https://lbjlincoln-nomos-rag-engine.hf.space/webhook/pme-assistant-gateway" \
  -H "Content-Type: application/json" \
  -d '{"question":"Comment gérer la trésorerie?"}' \
  -m 30
  
# Expected response: 
# {"code":404,"message":"The requested webhook \"POST pme-assistant-gateway\" is not registered."}
```

---

## Why API Activation Failed

The n8n REST API **does NOT support programmatic workflow activation** in version 2.8.x:

1. ❌ `PATCH /api/v1/workflows/:id` with `{"active": true}` → Response: "active is read-only"
2. ❌ `PUT /api/v1/workflows/:id` with full payload → "active is read-only"
3. ❌ `POST /api/v1/workflows/:id/activate` → "POST method not allowed"
4. ❌ `POST /rest/workflows/:id/activate` → "Unauthorized" (requires different auth)

According to n8n architecture, workflows with webhook triggers **must be activated** to register webhooks. The `active` field controls webhook registration, and it can only be set via:
- n8n UI (toggle switch)
- n8n CLI (`n8n workflow:activate --id=...`)
- Internal activation during HF Space boot (via entrypoint.sh)

---

## Activation Options

### Option 1: Manual Activation via UI (IMMEDIATE)

1. Access the workflow in n8n UI:
   ```
   https://lbjlincoln-nomos-rag-engine.hf.space/workflow/XhnGNbcnYv6gtAte
   ```

2. Click the toggle switch in the top-right corner to activate

3. Verify webhook is registered:
   ```bash
   curl -X POST "https://lbjlincoln-nomos-rag-engine.hf.space/webhook/pme-assistant-gateway" \
     -H "Content-Type: application/json" \
     -d '{"question":"test"}' -m 30
   ```

**Time**: ~2 minutes

---

### Option 2: Automatic Activation via HF Space Rebuild (ROBUST)

The PME Gateway workflow has been added to `/hf-space/n8n-workflows/pme-gateway.json`. When the HF Space is rebuilt, the `entrypoint.sh` script will:

1. Import the workflow via n8n CLI (line 129)
2. Start n8n (line 142)
3. Create credentials (line 256)
4. Activate workflows via `setup-workflows.py` (line 256)
5. Verify webhook is responding (line 268)

**Steps to trigger rebuild**:

1. Commit and push changes to the HF Space repository:
   ```bash
   cd /home/termius/mon-ipad
   git add hf-space/n8n-workflows/pme-gateway.json n8n/live/pme-gateway.json
   git commit -m "feat: add PME Gateway workflow to HF Space

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
   git push origin main
   ```

2. Trigger HF Space rebuild:
   - Option A: Push a change to the HF Space repo (any file)
   - Option B: Manual rebuild via HF Space UI settings

3. Wait for rebuild (~5-10 minutes)

4. Verify activation via logs or webhook test

**Time**: ~15 minutes total (5min rebuild + 10min testing)

---

### Option 3: n8n CLI via HF Space Shell (if available)

If HF Space provides shell access:

```bash
n8n workflow:activate --id=XhnGNbcnYv6gtAte
```

**Note**: HF Spaces typically don't provide SSH/shell access, so this option may not be available.

---

## Known Issues

### Issue 1: HF Space Entrypoint Activation Broken (Session 39)

According to `technicals/debug/knowledge-base.md`:

> **CRITICAL BLOCKER**: HF Space rebuild wiped n8n DB. NO pipelines can run until entrypoint.sh fixed. #1 cross-pipeline bottleneck (fixes 3+ pipelines).

However, current status shows **11 out of 18 workflows ARE active**, which means:
- ✅ Entrypoint.sh IS working for most workflows
- ❌ PME Gateway may need special handling or was added after last rebuild
- ❌ New workflows imported via API default to `active: false` and need manual activation

### Issue 2: Credential Requirements

The PME Gateway workflow requires several credentials to function:
- OpenRouter API key (for Intent Classifier LLM)
- Orchestrator webhook access (for RAG search)
- Action Executor webhook access (optional, for task creation)

These are configured in `setup-workflows.py` via:
- `OPENROUTER_KEY_PME` environment variable
- Automatic credential creation during HF Space boot

---

## Recommendation

**Immediate Action**: Use **Option 1** (manual UI activation) for fastest resolution (~2 minutes).

**Long-term Solution**: Ensure PME Gateway is included in HF Space rebuild process:
1. ✅ Workflow JSON added to `hf-space/n8n-workflows/` (DONE)
2. ⚠️ Verify `entrypoint.sh` includes PME webhook in verification (line 268)
3. ⚠️ Verify `setup-workflows.py` restores PME credentials
4. ⚠️ Test next HF Space rebuild to ensure auto-activation works

---

## Testing Checklist

After activation:

- [ ] Webhook responds (not 404)
- [ ] Intent classification works
- [ ] RAG search integration works
- [ ] Response formatting works
- [ ] Test with sample questions:
  ```bash
  curl -X POST "https://lbjlincoln-nomos-rag-engine.hf.space/webhook/pme-assistant-gateway" \
    -H "Content-Type: application/json" \
    -d '{"question":"Comment gérer la trésorerie?"}' -m 30
    
  curl -X POST "https://lbjlincoln-nomos-rag-engine.hf.space/webhook/pme-assistant-gateway" \
    -H "Content-Type: application/json" \
    -d '{"question":"Créer une tâche pour préparer le bilan financier"}' -m 30
  ```

---

## Files Modified

- ✅ `/home/termius/mon-ipad/n8n/live/pme-gateway.json` — Workflow exported from HF Space
- ✅ `/home/termius/mon-ipad/hf-space/n8n-workflows/pme-gateway.json` — Ready for HF rebuild

---

## Next Steps

1. **IMMEDIATE**: Manually activate workflow via UI (Option 1)
2. **COMMIT**: Push workflow files to git
3. **VERIFY**: Test webhook after activation
4. **DOCUMENT**: Update `docs/status.json` with PME Gateway status
5. **MONITOR**: Check next HF Space rebuild includes PME Gateway

