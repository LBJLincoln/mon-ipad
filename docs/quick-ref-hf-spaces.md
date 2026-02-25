# Quick Reference: HF Spaces Multi-Endpoint Architecture

Last updated: 2026-02-25

## Space URLs

| Space | URL | Pipelines |
|-------|-----|-----------|
| **Primary (#1)** | https://lbjlincoln-nomos-rag-engine.hf.space | Standard, Graph |
| **Secondary (#2)** | https://lbjlincoln26-nomos-rag-engine-2.hf.space | Quantitative, Orchestrator |

## Webhook Endpoints

### Space #1 (Working)
```bash
# Standard RAG
curl -X POST https://lbjlincoln-nomos-rag-engine.hf.space/webhook/rag-multi-index-v3 \
  -H "Content-Type: application/json" -d '{"question":"..."}'

# Graph RAG
curl -X POST https://lbjlincoln-nomos-rag-engine.hf.space/webhook/ff622742-6d71-4e91-af71-b5c666088717 \
  -H "Content-Type: application/json" -d '{"question":"..."}'
```

### Space #2 (Needs fixing)
```bash
# Quantitative (HTTP 500 - needs debug)
curl -X POST https://lbjlincoln26-nomos-rag-engine-2.hf.space/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9 \
  -H "Content-Type: application/json" -d '{"question":"..."}'

# Orchestrator (Not active - needs sub-workflow fix)
curl -X POST https://lbjlincoln26-nomos-rag-engine-2.hf.space/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0 \
  -H "Content-Type: application/json" -d '{"question":"..."}'
```

## n8n Login (Both Spaces)

```python
import urllib.request, json

base_url = "https://lbjlincoln26-nomos-rag-engine-2.hf.space"  # or Space #1
login_data = {
    "emailOrLdapLoginId": "ci@nomos.ai",
    "password": "CI-Nomos-2026!"
}

req = urllib.request.Request(
    f"{base_url}/rest/login",
    data=json.dumps(login_data).encode('utf-8'),
    headers={'Content-Type': 'application/json'},
    method='POST'
)
resp = urllib.request.urlopen(req, timeout=30)
cookie_header = resp.headers.get('Set-Cookie', '')
# Extract n8n-auth cookie
```

## Environment Variables (Space #2)

All 21 secrets set via HF API:
- N8N_ENCRYPTION_KEY
- OPENROUTER_KEY_QUANTITATIVE, OPENROUTER_KEY_ORCHESTRATOR, OPENROUTER_API_KEY
- PINECONE_API_KEY, PINECONE_HOST
- JINA_API_KEY
- NEO4J_URI, NEO4J_AUTH
- COHERE_API_KEY, GOOGLE_API_KEY
- SUPABASE_HOST, SUPABASE_PORT, SUPABASE_DB, SUPABASE_USER, SUPABASE_PASSWORD
- CI_EMAIL, CI_PASSWORD
- LLM_MAIN_MODEL, LLM_FAST_MODEL, LLM_EXTRACT_MODEL

## Next Steps

1. **Fix Orchestrator** - Replace sub-workflow nodes with HTTP webhooks to Space #1
2. **Debug Quantitative** - Check logs, verify credentials, test simple query
3. **Update eval scripts** - Use Space #2 URLs for Quant/Orch pipelines
4. **Cross-space testing** - Verify latency and reliability

## Files

- **Deployment docs**: /home/termius/mon-ipad/docs/hf-space-deployment.md
- **Deployment report**: /home/termius/mon-ipad/docs/hf-space-2-deployment-report.md
- **Local clone**: /tmp/hf-space-2/
- **Env backup**: /tmp/hf-space-2-env.json
