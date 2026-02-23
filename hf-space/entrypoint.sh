#!/bin/bash
# =================================================================
# HF Space Entrypoint — n8n Engine v2
# =================================================================
# Architecture: n8n on port 7860 (HF requirement), SQLite, single process
# Credentials + workflows auto-created via setup-workflows.py
#
# RESILIENCE: No set -e. Container stays alive even if setup fails.
# Last updated: 2026-02-23
# =================================================================

trap 'echo "SIGNAL received"; wait' SIGTERM SIGINT

echo "==================================================================="
echo "  NOMOS RAG ENGINE — HF Space Boot v2"
echo "==================================================================="

# ---- 1. Environment setup ----
echo ""
echo "[1/4] Setting up environment..."

# n8n listens directly on HF's required port
export N8N_HOST=0.0.0.0
export N8N_PORT=7860
export N8N_PROTOCOL=http
export WEBHOOK_URL=https://lbjlincoln-nomos-rag-engine.hf.space

# SQLite for minimal boot (persistent across container restarts)
export DB_TYPE=sqlite
export DB_SQLITE_DATABASE=/home/node/.n8n/database.sqlite

# Single process mode
export EXECUTIONS_MODE=regular

# n8n settings
export N8N_DEFAULT_BINARY_DATA_MODE=filesystem
export EXECUTIONS_DATA_PRUNE=true
export EXECUTIONS_DATA_MAX_AGE=48
export EXECUTIONS_DATA_PRUNE_MAX_COUNT=500
export N8N_DIAGNOSTICS_ENABLED=false
export N8N_RUNNERS_ENABLED=false
export N8N_ENCRYPTION_KEY="${N8N_ENCRYPTION_KEY:-sota-rag-2026-hf-space-key}"
export N8N_COMMUNITY_PACKAGES_ALLOW_TOOL_USAGE=true

# Per-pipeline OpenRouter keys (fallback to main key)
export OPENROUTER_KEY_STANDARD="${OPENROUTER_KEY_STANDARD:-${OPENROUTER_API_KEY:-}}"
export OPENROUTER_KEY_GRAPH="${OPENROUTER_KEY_GRAPH:-${OPENROUTER_API_KEY:-}}"
export OPENROUTER_KEY_QUANTITATIVE="${OPENROUTER_KEY_QUANTITATIVE:-${OPENROUTER_API_KEY:-}}"
export OPENROUTER_KEY_ORCHESTRATOR="${OPENROUTER_KEY_ORCHESTRATOR:-${OPENROUTER_API_KEY:-}}"
export OPENROUTER_KEY_PME="${OPENROUTER_KEY_PME:-${OPENROUTER_API_KEY:-}}"
export OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# LLM model vars (used by workflows via $env)
export LLM_MAIN_MODEL="${LLM_MAIN_MODEL:-meta-llama/llama-3.3-70b-instruct:free}"
export LLM_FAST_MODEL="${LLM_FAST_MODEL:-google/gemma-3-27b-it:free}"
export LLM_EXTRACT_MODEL="${LLM_EXTRACT_MODEL:-arcee-ai/trinity-large-preview:free}"

# External service env vars (used by workflows via $env)
export PINECONE_HOST="${PINECONE_HOST:-https://sota-rag-jina-1024-a4mkzmz.svc.aped-4627-b74a.pinecone.io}"
export JINA_API_KEY="${JINA_API_KEY:-}"
export PINECONE_API_KEY="${PINECONE_API_KEY:-}"
export NEO4J_URI="${NEO4J_URI:-}"
export NEO4J_AUTH="${NEO4J_AUTH:-}"
export COHERE_API_KEY="${COHERE_API_KEY:-}"
export GOOGLE_API_KEY="${GOOGLE_API_KEY:-}"
export SUPABASE_HOST="${SUPABASE_HOST:-aws-0-eu-west-1.pooler.supabase.com}"
export SUPABASE_PORT="${SUPABASE_PORT:-6543}"
export SUPABASE_DB="${SUPABASE_DB:-postgres}"
export SUPABASE_USER="${SUPABASE_USER:-postgres.kfyrtsmdolgioyxsglbz}"
export SUPABASE_PASSWORD="${SUPABASE_PASSWORD:-}"

echo "  Mode: SQLite + single process"
echo "  Port: $N8N_PORT"
echo "  Webhook URL: $WEBHOOK_URL"
echo "  OR keys: STANDARD=${OPENROUTER_KEY_STANDARD:+SET} GRAPH=${OPENROUTER_KEY_GRAPH:+SET} QUANT=${OPENROUTER_KEY_QUANTITATIVE:+SET} ORCH=${OPENROUTER_KEY_ORCHESTRATOR:+SET} PME=${OPENROUTER_KEY_PME:+SET}"
echo "  Pinecone: ${PINECONE_API_KEY:+SET} Host: ${PINECONE_HOST:+SET}"
echo "  Jina: ${JINA_API_KEY:+SET}"

# ---- 2. Start n8n ----
echo ""
echo "[2/4] Starting n8n..."

n8n start &
N8N_PID=$!

# ---- 3. Wait for n8n to become healthy ----
echo ""
echo "[3/4] Waiting for n8n to become healthy..."
N8N_READY=false
for i in $(seq 1 120); do
    if curl -sf http://127.0.0.1:7860/healthz > /dev/null 2>&1; then
        echo "  n8n healthy after ${i}s"
        N8N_READY=true
        break
    fi
    sleep 1
done

if [ "$N8N_READY" != "true" ]; then
    echo "WARNING: n8n not healthy after 120s — keeping container alive"
    echo "  n8n PID: $N8N_PID ($(ps -p $N8N_PID -o comm= 2>/dev/null || echo 'DEAD'))"
    wait $N8N_PID
    exit 0
fi

# ---- 4. Setup: credentials, workflows, activation ----
echo ""
echo "[4/4] Setting up credentials and workflows..."
sleep 5  # Let REST API fully initialize

CI_EMAIL="${CI_EMAIL:-ci@nomos.ai}"
CI_PASSWORD="${CI_PASSWORD:-CI-Nomos-2026!}"

# Check for first boot
SETUP_CHECK=$(curl -s http://127.0.0.1:7860/rest/settings 2>/dev/null || echo "")
if echo "$SETUP_CHECK" | python3 -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if d.get('data',d).get('userManagement',{}).get('showSetupOnFirstLoad',False) else 1)" 2>/dev/null; then
    echo "  First boot — creating owner account..."
    curl -s -o /dev/null -X POST http://127.0.0.1:7860/rest/owner/setup \
        -H "Content-Type: application/json" \
        -d "{\"email\":\"$CI_EMAIL\",\"password\":\"$CI_PASSWORD\",\"firstName\":\"CI\",\"lastName\":\"Bot\"}" 2>/dev/null || true
    sleep 3
fi

# Login with retry
COOKIE=""
for attempt in $(seq 1 5); do
    RESP=$(curl -s -o /dev/null -w "%{http_code}" \
        -X POST http://127.0.0.1:7860/rest/login \
        -H "Content-Type: application/json" \
        -d "{\"emailOrLdapLoginId\":\"$CI_EMAIL\",\"password\":\"$CI_PASSWORD\"}" \
        -c /tmp/n8n-cookies.txt 2>/dev/null || echo "000")
    if [ "$RESP" = "200" ]; then
        COOKIE=$(grep n8n-auth /tmp/n8n-cookies.txt 2>/dev/null | awk '{print $NF}')
        [ -n "$COOKIE" ] && echo "  Login OK (attempt $attempt)" && break
    fi
    echo "  Login attempt $attempt (HTTP $RESP)"
    sleep 3
done

# Run Python setup script (credential creation + workflow import + activation)
if [ -n "$COOKIE" ]; then
    if [ -f /app/setup-workflows.py ]; then
        python3 /app/setup-workflows.py "$COOKIE" "http://127.0.0.1:7860" 2>&1
    else
        echo "  WARNING: setup-workflows.py not found — manual setup required"
    fi
else
    echo "  WARNING: Login failed — workflows not imported"
fi

echo ""
echo "==================================================================="
echo "  BOOT COMPLETE — n8n on port 7860"
echo "  Mode: SQLite + single process"
echo "  Webhooks: https://lbjlincoln-nomos-rag-engine.hf.space/webhook/*"
echo "==================================================================="

# Keep container alive
wait $N8N_PID
