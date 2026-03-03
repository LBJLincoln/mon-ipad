# n8n API Endpoints & Reference Complete

> Last updated: 2026-03-03T18:15:00+00:00

> **Ce fichier est la reference unique** pour les scripts Python de test.
> Les scripts doivent s'y referer pour formater les requetes et utiliser les bons points d'entree.

---

## Configuration — HF Space #1 (active)

```bash
# Single active HF Space (Space #1)
N8N_HOST=https://lbjlincoln-nomos-rag-engine.hf.space
# Auth: Cookie-based (scripts/n8n-api.py helper)
# n8n: ci@nomos.ai / CI-Nomos-2026!
```

### HF Space Endpoints
| Space | URL | Account | Role | Status |
|-------|-----|---------|------|--------|
| Space 1 | https://lbjlincoln-nomos-rag-engine.hf.space | LBJLincoln | n8n (RAG pipelines) | **ACTIVE** |
| Space 7 | https://lbjlincoln-nomos-rag-engine-7.hf.space | LBJLincoln | LiteLLM Proxy (key rotation) | **ACTIVE** |
| Spaces 2-6, 8-10 | Various | Mixed | INACTIVE | **NOT DEPLOYED** |

> **NOTE** : Only Space #1 (n8n) and Space #7 (LiteLLM) are active. Other spaces were planned but not deployed.
> SQLite is used for n8n ephemeral workflow storage per space. All shared state uses Supabase Postgres.

---

## LiteLLM Proxy (Space #7)

```bash
LITELLM_URL=https://lbjlincoln-nomos-rag-engine-7.hf.space
LITELLM_KEY=sk-litellm-nomos-2026

# Health check
curl -s "$LITELLM_URL/health/liveliness"

# Chat completion (auto key rotation: 5 OpenRouter + 5 Groq)
curl -s -X POST "$LITELLM_URL/v1/chat/completions" \
  -H "Authorization: Bearer $LITELLM_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"llama-70b","messages":[{"role":"user","content":"test"}]}'

# Available models: llama-70b, llama-70b-groq, trinity, gemma-27b, jina-embed, jina-rerank
```

---

## Format de Requete pour Scripts Python (REFERENCE)

### Format de body webhook (VERIFIE FONCTIONNEL — Session 69)

```python
# Format qui FONCTIONNE — verifie le 2026-03-03
# ATTENTION : le field name est "query" (PAS "question")
payload = {"query": "Your question here"}
# Content-Type: application/json
# Method: POST
```

> **PIEGE RECURRENT** : Utiliser `question` au lieu de `query` provoque une VALIDATION_ERROR.
> Toujours utiliser `query` pour les 4 pipelines.

### Pattern Python pour appeler un webhook

```python
import urllib.request, json

N8N_HOST = "https://lbjlincoln-nomos-rag-engine.hf.space"

def call_webhook(path, question, timeout=120):
    """Appel webhook n8n."""
    url = f"{N8N_HOST}{path}"
    payload = json.dumps({"query": question}).encode()
    req = urllib.request.Request(url, data=payload, method="POST",
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())
```

---

## REST API — Cookie Auth (Session 68 discovery)

> **IMPORTANT**: n8n on HF Space does NOT support API key auth (JWT invalidates on rebuild).
> Use cookie-based auth via `scripts/n8n-api.py` helper.

### Helper script (recommended)

```bash
source .env.local
python3 scripts/n8n-api.py list                          # List workflows
python3 scripts/n8n-api.py get <WF_ID>                   # Export workflow JSON
python3 scripts/n8n-api.py deploy n8n/live/workflow.json  # Import workflow
python3 scripts/n8n-api.py activate <WF_ID>              # Activate webhook
python3 scripts/n8n-api.py exec <WF_ID>                  # Trigger execution
```

### Raw REST API (cookie auth)

```bash
# 1. Login (get session cookie)
curl -s -c /tmp/n8n-cookies.txt -X POST "$N8N_HOST/rest/login" \
  -H "Content-Type: application/json" \
  -d '{"emailOrLdapLoginId":"ci@nomos.ai","password":"CI-Nomos-2026!"}'

# 2. List workflows
curl -s -b /tmp/n8n-cookies.txt "$N8N_HOST/rest/workflows"

# 3. Get workflow
curl -s -b /tmp/n8n-cookies.txt "$N8N_HOST/rest/workflows/<WF_ID>"

# 4. Update workflow (PATCH, not PUT)
curl -s -b /tmp/n8n-cookies.txt -X PATCH "$N8N_HOST/rest/workflows/<WF_ID>" \
  -H "Content-Type: application/json" \
  -d '{"nodes": [...], "connections": {...}}'

# 5. Activate (REQUIRED for webhooks — needs versionId!)
curl -s -b /tmp/n8n-cookies.txt -X POST "$N8N_HOST/rest/workflows/<WF_ID>/activate" \
  -H "Content-Type: application/json" \
  -d '{"versionId": "<VERSION_ID_FROM_PATCH_RESPONSE>"}'

# 6. Get executions
curl -s -b /tmp/n8n-cookies.txt "$N8N_HOST/rest/executions?workflowId=<WF_ID>&limit=5"
```

---

## Webhooks (endpoints de test — verified 2026-03-03)

```bash
N8N_HOST=https://lbjlincoln-nomos-rag-engine.hf.space

# Standard RAG (working — 85%+ accuracy)
curl -s -X POST "$N8N_HOST/webhook/rag-multi-index-v3" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the capital of Japan?"}'

# Graph RAG (working — OTEL Init fixed Session 69)
curl -s -X POST "$N8N_HOST/webhook/ff622742-6d71-4e91-af71-b5c666088717" \
  -H "Content-Type: application/json" \
  -d '{"query": "Who founded Microsoft?", "topK": 100}'

# Quantitative RAG (working — 92% accuracy)
curl -s -X POST "$N8N_HOST/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9" \
  -H "Content-Type: application/json" \
  -d '{"query": "What was Apple revenue in 2023?"}'

# Orchestrator (BROKEN — empty body issue, not fixed yet)
curl -s -X POST "$N8N_HOST/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the capital of Japan?"}'

# Ingestion V4.0 (working — async, routes through LiteLLM)
curl -s -X POST "$N8N_HOST/webhook/rag-v6-ingestion" \
  -H "Content-Type: application/json" \
  -d '{"filename":"test.txt","documentId":"test-001","content":"Document text here.","source":"manual"}'

# Enrichment V4.0 (working — async, routes through LiteLLM)
curl -s -X POST "$N8N_HOST/webhook/rag-v6-enrichment" \
  -H "Content-Type: application/json" \
  -d '{"documentId":"test-001","content":"Text to enrich.","entities":["entity1"]}'
```

---

## Workflow IDs — HF Space (verified 2026-03-03)

### Pipelines RAG (4)
| Pipeline | HF Space ID | Webhook | Status |
|----------|-------------|---------|--------|
| Standard RAG V3.4 | `TmgyRP20N4JFd9CB` | `/webhook/rag-multi-index-v3` | **WORKING** |
| Graph RAG V3.3 | `6257AfT1l4FMC6lY` | `/webhook/ff622742-...` | **WORKING** |
| Quantitative V2.0 | `E19NZG9WfM7FNsxr` | `/webhook/3e0f8010-...` | **WORKING** |
| Orchestrator V10.1 | `ALd4gOEqiKL5KR1p` | `/webhook/92217bb8-...` | **BROKEN** |

### Workflows Support
| Workflow | HF Space ID | Status |
|----------|-------------|--------|
| Ingestion V4.0 | `nh1D4Up0wBZhuQbp` | **WORKING** (LiteLLM routed) |
| Enrichment V4.0 | `ORa01sX4xI0iRCJ8` | **WORKING** (LiteLLM routed) |
| Benchmark V3.0 | `qUm28nhq62SxVWHe` | Active |
| Dashboard Status API | `7866297137a444618` | Active |
| Dataset Ingestion | `L8irkzSrfLlgt2Bt` | Active |
| SQL Executor | `3O2xcKuloLnZB5dH` | Active |

### n8n Credentials on HF Space
| Credential | ID | Usage |
|------------|-----|-------|
| OpenRouter (Standard) | `VTFur78v4L4wWEk9` | Standard pipeline |
| OpenRouter (Graph) | `8zKa8MqNEHsbVGKp` | Graph pipeline |
| OpenRouter (Quantitative) | `lGI3u8XGRIwaFq1e` | Quant pipeline |
| OpenRouter (Orchestrator) | `S7i3kAtU5ZqIVCYS` | Orchestrator pipeline |
| LiteLLM Proxy Key | `mStiDbYim2aZ0cMq` | Ingestion + Enrichment |
| Jina API Key | `I68x3RvlHJZyQuR6` | Embeddings (key 2 active) |
| Supabase Postgres | `Vrvh0ukcROAk9dyX` | Database queries |
| Pinecone API Key | `US6Cxlgs8LfyZWss` | Vector search |

---

## Pieges connus (updated Session 69)

| Piege | Solution |
|-------|----------|
| `"query"` not `"question"` | Webhook body MUST use `query` field |
| API key auth doesn't work on HF Space | Use cookie auth (POST /rest/login) |
| PATCH needs versionId for reactivation | Get versionId from PATCH response → POST /activate |
| Disabled Code nodes pass through raw webhook data | Re-enable or fix downstream references |
| `{{ 'model' || 'fallback' }}` in jsonBody | n8n expressions not evaluated in JSON strings — hardcode |
| `$items('DisabledNode')` crashes | Wrap in try/catch for disabled/optional nodes |
| Jina rate limit 100K tokens/min | Pause background ingestion before testing pipelines |
| Free models OpenRouter changent souvent | Use LiteLLM proxy for automatic fallback to Groq |
| Execution data compressed (string table format) | parsed[0]=structure, parsed[1:]=strings, digit refs are 1-indexed |

---

## Scripts de test

| Script | Chemin | Usage |
|--------|--------|-------|
| Quick test (1-5q) | `eval/quick-test.py` | Smoke test |
| Iterative eval | `eval/iterative-eval.py` | Progressif 5→10→50 |
| Parallel eval (200q) | `eval/run-eval-parallel.py` | Full eval |
| Node analyzer | `eval/node-analyzer.py` | Analyse node-par-node |
| N8n API helper | `scripts/n8n-api.py` | REST API operations |
| N8n execution analyzer | `scripts/analyze_n8n_executions.py` | Analyse brute complete |
| Status generator | `eval/generate_status.py` | Regenere status.json |
| Phase 3 ingestion | `scripts/ingest-phase3-pinecone.py` | Pinecone context ingestion |
