# HuggingFace Space Deployment — Multi-Endpoint Architecture

Last updated: 2026-02-25

## Overview

The NOMOS Multi-RAG system is deployed across **2 HuggingFace Spaces** to provide distributed throughput and isolation between pipelines.

## Deployed Spaces

### Space #1 (Primary)
- **Account**: LBJLincoln
- **Space**: nomos-rag-engine
- **URL**: https://lbjlincoln-nomos-rag-engine.hf.space
- **Pipelines**:
  - Standard RAG (`/webhook/rag-multi-index-v3`)
  - Graph RAG (`/webhook/ff622742-6d71-4e91-af71-b5c666088717`)
  - Debug Status (`/webhook/debug-status`)
- **Status**: Active (deployed Feb 23, 2026)

### Space #2 (Secondary)
- **Account**: LBJLincoln26
- **Space**: nomos-rag-engine-2
- **URL**: https://lbjlincoln26-nomos-rag-engine-2.hf.space
- **Pipelines**:
  - Quantitative RAG (`/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9`)
  - Orchestrator (`/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0`)
  - Debug Status (`/webhook/debug-status`)
- **Status**: Deploying (Feb 25, 2026)

## Environment Variables

Both spaces share the same credentials and configuration:

### Core n8n
- `N8N_ENCRYPTION_KEY`
- `CI_EMAIL` / `CI_PASSWORD`

### Per-Pipeline OpenRouter Keys
- Space #1: `OPENROUTER_KEY_STANDARD`, `OPENROUTER_KEY_GRAPH`
- Space #2: `OPENROUTER_KEY_QUANTITATIVE`, `OPENROUTER_KEY_ORCHESTRATOR`
- Fallback: `OPENROUTER_API_KEY`

### External Services
- Pinecone: `PINECONE_API_KEY`, `PINECONE_HOST`
- Jina: `JINA_API_KEY`
- Neo4j: `NEO4J_URI`, `NEO4J_AUTH`
- Cohere: `COHERE_API_KEY`
- Google: `GOOGLE_API_KEY`
- Supabase: `SUPABASE_HOST`, `SUPABASE_PORT`, `SUPABASE_DB`, `SUPABASE_USER`, `SUPABASE_PASSWORD`

### LLM Models
- `LLM_MAIN_MODEL`: meta-llama/llama-3.3-70b-instruct:free
- `LLM_FAST_MODEL`: google/gemma-3-27b-it:free
- `LLM_EXTRACT_MODEL`: arcee-ai/trinity-large-preview:free

## Deployment Process

### Initial Setup
1. Create HF Space via API: `POST /api/repos/create`
2. Clone space repository: `git clone https://huggingface.co/spaces/{space_id}`
3. Copy files: Dockerfile, entrypoint.sh, setup-workflows.py, healthcheck.py
4. Copy workflow JSONs to `n8n-workflows/`
5. Commit and push to space repository
6. Set secrets via API: `POST /api/spaces/{space_id}/secrets`

### Files Structure
```
/
├── Dockerfile
├── README.md
├── entrypoint.sh
├── setup-workflows.py
├── healthcheck.py
└── n8n-workflows/
    ├── debug-status.json
    ├── orchestrator-v10.json (Space #2)
    ├── quantitative.json (Space #2)
    ├── standard.json (Space #1)
    └── graph.json (Space #1)
```

### Build Process
1. HF builds Docker image from Dockerfile
2. Entrypoint.sh runs on container start:
   - Sets environment variables
   - Imports workflows via n8n CLI
   - Starts n8n server
   - Creates owner account and credentials
   - Activates workflows with POST /activate
   - Verifies webhooks

## Testing

### Quick Health Check
```bash
# Space #1
curl https://lbjlincoln-nomos-rag-engine.hf.space/healthz

# Space #2
curl https://lbjlincoln26-nomos-rag-engine-2.hf.space/healthz
```

### Webhook Test
```bash
# Test Quantitative on Space #2
curl -X POST https://lbjlincoln26-nomos-rag-engine-2.hf.space/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9 \
  -H "Content-Type: application/json" \
  -d '{"question":"Test question"}'
```

## Monitoring

- **Web UI**: https://huggingface.co/spaces/{space_id}
- **Logs**: Click "Logs" tab in HF Space UI
- **Status API**: Both spaces expose `/webhook/debug-status`

## Troubleshooting

### Space stuck in APP_STARTING
- Check logs in HF Space UI
- Verify all secrets are set correctly
- Check Dockerfile syntax
- Ensure port 7860 is exposed

### Webhooks returning 404
- Verify POST /activate was called in entrypoint.sh
- Check n8n logs for activation errors
- Ensure credentials were created before activation
- Verify workflow JSON has correct webhook paths

### Login failures
- Check CI_EMAIL and CI_PASSWORD secrets
- Try owner setup endpoint manually
- Verify n8n is healthy before login attempts

## References
- HF Spaces API: https://huggingface.co/docs/hub/spaces-sdks-docker
- n8n Docker: https://docs.n8n.io/hosting/installation/docker/
- Project docs: /home/termius/mon-ipad/technicals/
