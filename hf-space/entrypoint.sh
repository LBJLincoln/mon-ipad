#!/bin/bash
# =================================================================
# HF Space Entrypoint — n8n with Queue Mode, PostgreSQL, Activation
# =================================================================
# Single container: supervisord manages n8n-main + workers + redis + nginx
# Database: Supabase PostgreSQL (persistent across HF Space rebuilds)
# Queue mode: workers via Redis for higher throughput
# Multi-key OpenRouter: per-pipeline API keys via env vars
#
# RESILIENCE: No set -e. Container stays alive even if setup fails.
# All setup is best-effort — n8n + nginx always stay running.
#
# Last updated: 2026-02-23
# =================================================================

# NO set -e: container must stay alive even if setup steps fail
# set -e was causing container exits on transient failures

trap 'echo "SIGNAL received — keeping alive"; wait $SUPERVISOR_PID' SIGTERM SIGINT

echo "==================================================================="
echo "  NOMOS RAG ENGINE — HF Space Boot"
echo "  Queue mode: workers + Redis | PostgreSQL: Supabase (persistent)"
echo "==================================================================="

# ---- 1. Set up environment variables ----
echo ""
echo "[1/4] Setting up environment..."

# n8n Queue mode config
export EXECUTIONS_MODE=queue
export QUEUE_BULL_REDIS_HOST=127.0.0.1
export QUEUE_BULL_REDIS_PORT=6379

# n8n Network config
export N8N_HOST=0.0.0.0
export N8N_PORT=7860
export N8N_PROTOCOL=http
export WEBHOOK_URL=https://lbjlincoln-nomos-rag-engine.hf.space

# Supabase PostgreSQL (PERSISTENT — survives HF Space rebuilds)
export DB_TYPE=postgresdb
export DB_POSTGRESDB_HOST=aws-1-eu-west-1.pooler.supabase.com
export DB_POSTGRESDB_PORT=6543
export DB_POSTGRESDB_DATABASE=postgres
export DB_POSTGRESDB_USER=postgres.ayqviqmxifzmhphiqfmj
export DB_POSTGRESDB_PASSWORD="${SUPABASE_PASSWORD:-}"
export DB_POSTGRESDB_SSL_ENABLED=true
export DB_POSTGRESDB_SSL_REJECT_UNAUTHORIZED=false
export DB_POSTGRESDB_SCHEMA=n8n_engine

# n8n execution settings
export N8N_DEFAULT_BINARY_DATA_MODE=filesystem
export EXECUTIONS_DATA_PRUNE=true
export EXECUTIONS_DATA_MAX_AGE=48
export EXECUTIONS_DATA_PRUNE_MAX_COUNT=1000
export N8N_DIAGNOSTICS_ENABLED=false
export N8N_CONCURRENCY_PRODUCTION_LIMIT=5
export N8N_RUNNERS_ENABLED=false
export N8N_ENCRYPTION_KEY="${N8N_ENCRYPTION_KEY:-sota-rag-2026-hf-space-key}"
export N8N_COMMUNITY_PACKAGES_ALLOW_TOOL_USAGE=true

# Per-pipeline OpenRouter keys (default to main key if not set)
export OPENROUTER_KEY_STANDARD="${OPENROUTER_KEY_STANDARD:-${OPENROUTER_API_KEY:-}}"
export OPENROUTER_KEY_GRAPH="${OPENROUTER_KEY_GRAPH:-${OPENROUTER_API_KEY:-}}"
export OPENROUTER_KEY_QUANTITATIVE="${OPENROUTER_KEY_QUANTITATIVE:-${OPENROUTER_API_KEY:-}}"
export OPENROUTER_KEY_ORCHESTRATOR="${OPENROUTER_KEY_ORCHESTRATOR:-${OPENROUTER_API_KEY:-}}"
export OPENROUTER_KEY_PME="${OPENROUTER_KEY_PME:-${OPENROUTER_API_KEY:-}}"
export OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# LLM model vars
export LLM_MAIN_MODEL="${LLM_MAIN_MODEL:-meta-llama/llama-3.3-70b-instruct:free}"
export LLM_FAST_MODEL="${LLM_FAST_MODEL:-google/gemma-3-27b-it:free}"
export LLM_EXTRACT_MODEL="${LLM_EXTRACT_MODEL:-arcee-ai/trinity-large-preview:free}"

echo "  DB: Supabase PostgreSQL (${DB_POSTGRESDB_HOST}:${DB_POSTGRESDB_PORT}/${DB_POSTGRESDB_SCHEMA})"
echo "  Queue: Redis 127.0.0.1:6379"
echo "  Webhook URL: ${WEBHOOK_URL}"
echo "  OpenRouter keys: main=$([ -n "$OPENROUTER_API_KEY" ] && echo 'SET' || echo 'MISSING')"

# ---- 2. Start all services via supervisord ----
echo ""
echo "[2/4] Starting services (redis, n8n-main, workers, nginx)..."

# Start supervisord in background
supervisord -c /etc/supervisor/conf.d/supervisord.conf &
SUPERVISOR_PID=$!

# ---- 3. Wait for n8n to become healthy ----
echo ""
echo "[3/4] Waiting for n8n to become healthy..."
N8N_READY=false
for i in $(seq 1 180); do
    if curl -sf http://127.0.0.1:7860/healthz > /dev/null 2>&1; then
        echo "  n8n healthy after ${i}s"
        N8N_READY=true
        break
    fi
    sleep 1
done

if [ "$N8N_READY" != "true" ]; then
    echo "WARNING: n8n not healthy after 180s — keeping container alive for debugging"
    echo "  supervisord status:"
    supervisorctl status 2>/dev/null || echo "  (supervisorctl unavailable)"
    echo "  Container will stay alive. n8n may still come up."
    # DON'T exit — keep container alive so HF Space stays RUNNING
    wait $SUPERVISOR_PID
    exit 0
fi

# Extra wait for REST API (healthz can be ready before REST endpoints)
echo "  Waiting 15s for REST API initialization..."
sleep 15

# ---- 4. Setup: Login + Import + Activate workflows ----
# ALL steps below are best-effort. Failures won't kill the container.
echo ""
echo "[4/4] Setting up workflows (login, import, activate)..."

setup_workflows() {
    # Try login (for fresh instances, n8n auto-creates owner account)
    local CI_EMAIL="${CI_EMAIL:-ci@nomos.ai}"
    local CI_PASSWORD="${CI_PASSWORD:-CI-Nomos-2026!}"
    local COOKIE=""

    # First check if n8n needs initial setup (fresh Supabase schema)
    local SETUP_CHECK
    SETUP_CHECK=$(curl -s http://127.0.0.1:7860/rest/settings 2>/dev/null || echo "")
    if echo "$SETUP_CHECK" | python3 -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if d.get('data',d).get('userManagement',{}).get('showSetupOnFirstLoad',False) else 1)" 2>/dev/null; then
        echo "  First boot detected — creating owner account..."
        curl -s -o /dev/null -X POST http://127.0.0.1:7860/rest/owner/setup \
            -H "Content-Type: application/json" \
            -d "{\"email\":\"$CI_EMAIL\",\"password\":\"$CI_PASSWORD\",\"firstName\":\"CI\",\"lastName\":\"Bot\"}" 2>/dev/null || true
        echo "  Owner account created (or attempted)"
        sleep 3
    fi

    # Login with retries
    for attempt in $(seq 1 10); do
        local RESP
        RESP=$(curl -s -o /tmp/login-resp.json -w "%{http_code}" \
            -X POST http://127.0.0.1:7860/rest/login \
            -H "Content-Type: application/json" \
            -d "{\"email\":\"$CI_EMAIL\",\"password\":\"$CI_PASSWORD\"}" \
            -c /tmp/n8n-cookies.txt 2>/dev/null || echo "000")

        if [ "$RESP" = "200" ]; then
            COOKIE=$(grep n8n-auth /tmp/n8n-cookies.txt 2>/dev/null | awk '{print $NF}')
            if [ -n "$COOKIE" ]; then
                echo "  Login OK (attempt $attempt)"
                break
            fi
        fi
        echo "  Login attempt $attempt/10 (HTTP $RESP) — waiting 5s..."
        sleep 5
    done

    if [ -z "$COOKIE" ]; then
        echo "WARNING: Login failed — workflows must be activated manually"
        return 1
    fi

    # Import workflows
    echo ""
    echo "  Importing workflows..."
    local IMPORT_OK=0
    for wf in /app/n8n-workflows/*.json; do
        [ -f "$wf" ] || continue
        local WF_NAME
        WF_NAME=$(basename "$wf" .json)

        local IMPORT_RESP
        IMPORT_RESP=$(curl -s -o /tmp/import-resp.json -w "%{http_code}" \
            -X POST http://127.0.0.1:7860/rest/workflows \
            -H "Content-Type: application/json" \
            -b "n8n-auth=$COOKIE" \
            -d @"$wf" 2>/dev/null || echo "000")

        if [ "$IMPORT_RESP" = "200" ]; then
            IMPORT_OK=$((IMPORT_OK + 1))
            echo "    OK: $WF_NAME"
        else
            echo "    $IMPORT_RESP: $WF_NAME (may already exist)"
        fi
    done
    echo "  Imported: $IMPORT_OK workflows"

    # Create n8n credentials from environment variables
    echo ""
    echo "  Creating credentials..."
    create_credential() {
        local CRED_NAME="$1" CRED_TYPE="$2" CRED_DATA="$3"
        local CRED_RESP
        CRED_RESP=$(curl -s -o /dev/null -w "%{http_code}" \
            -X POST http://127.0.0.1:7860/rest/credentials \
            -H "Content-Type: application/json" \
            -b "n8n-auth=$COOKIE" \
            -d "{\"name\":\"$CRED_NAME\",\"type\":\"$CRED_TYPE\",\"data\":$CRED_DATA}" 2>/dev/null || echo "000")
        if [ "$CRED_RESP" = "200" ]; then
            echo "    OK: $CRED_NAME ($CRED_TYPE)"
        else
            echo "    $CRED_RESP: $CRED_NAME (may already exist)"
        fi
    }

    # OpenRouter httpHeaderAuth credentials (per-pipeline)
    for PIPELINE in STANDARD GRAPH QUANTITATIVE ORCHESTRATOR PME; do
        local KEY_VAR="OPENROUTER_KEY_${PIPELINE}"
        local KEY_VAL="${!KEY_VAR:-}"
        [ -z "$KEY_VAL" ] && continue
        create_credential \
            "OpenRouter ${PIPELINE}" \
            "httpHeaderAuth" \
            "{\"name\":\"Authorization\",\"value\":\"Bearer ${KEY_VAL}\"}"
    done

    # Main OpenRouter key
    if [ -n "${OPENROUTER_API_KEY:-}" ]; then
        create_credential \
            "OpenRouter Main" \
            "httpHeaderAuth" \
            "{\"name\":\"Authorization\",\"value\":\"Bearer ${OPENROUTER_API_KEY}\"}"
    fi

    # Pinecone
    if [ -n "${PINECONE_API_KEY:-}" ]; then
        create_credential \
            "Pinecone" \
            "pineconeApi" \
            "{\"apiKey\":\"${PINECONE_API_KEY}\"}"
    fi

    # Neo4j
    if [ -n "${NEO4J_URI:-}" ]; then
        create_credential \
            "Neo4j" \
            "neo4jApi" \
            "{\"uri\":\"${NEO4J_URI}\",\"username\":\"neo4j\",\"password\":\"${NEO4J_PASSWORD:-}\"}"
    fi

    echo "  Credentials setup done"

    # Activate all inactive workflows
    echo ""
    echo "  Activating workflows..."

    local ALL_WFS
    ALL_WFS=$(curl -s "http://127.0.0.1:7860/rest/workflows?limit=50" \
        -b "n8n-auth=$COOKIE" 2>/dev/null || echo "")

    [ -z "$ALL_WFS" ] && { echo "  WARNING: Could not fetch workflows"; return 1; }

    # Parse workflow list to temp file (avoids subshell pipe issue)
    python3 -c "
import json, sys
try:
    data = json.loads(sys.argv[1])
    wfs = data.get('data', data) if isinstance(data, dict) else data
    if isinstance(wfs, list):
        for w in wfs:
            print(f\"{w.get('id','')}\t{w.get('name','')}\t{w.get('active',False)}\t{w.get('versionId','')}\")
except Exception as e:
    print(f'ERROR: {e}', file=sys.stderr)
" "$ALL_WFS" > /tmp/wf-list.txt 2>/dev/null || true

    while IFS=$'\t' read -r wid wname wactive wversion; do
        [ -z "$wid" ] && continue
        [ "$wid" = "ERROR" ] && continue

        if [ "$wactive" = "False" ]; then
            local ACT_RESP
            ACT_RESP=$(curl -s -o /dev/null -w "%{http_code}" \
                -X POST "http://127.0.0.1:7860/rest/workflows/$wid/activate" \
                -H "Content-Type: application/json" \
                -b "n8n-auth=$COOKIE" \
                -d "{\"versionId\":\"$wversion\"}" 2>/dev/null || echo "000")

            if [ "$ACT_RESP" = "200" ]; then
                echo "    ACTIVATED: $wname ($wid)"
            else
                echo "    FAILED: $wname ($wid) HTTP $ACT_RESP"
            fi
        else
            echo "    ALREADY ACTIVE: $wname ($wid)"
        fi
    done < /tmp/wf-list.txt

    # Lightweight webhook verification (HEAD/GET only — no POST to avoid triggering executions)
    echo ""
    echo "  Checking webhook registrations (lightweight)..."
    local WH_CHECK
    WH_CHECK=$(curl -s "http://127.0.0.1:7860/rest/active-webhooks" \
        -b "n8n-auth=$COOKIE" 2>/dev/null || echo "")
    if [ -n "$WH_CHECK" ]; then
        echo "  Active webhooks:"
        echo "$WH_CHECK" | python3 -c "
import json, sys
try:
    data = json.loads(sys.stdin.read())
    whs = data.get('data', data) if isinstance(data, dict) else data
    if isinstance(whs, list):
        for wh in whs:
            path = wh.get('webhookPath', wh.get('path', '?'))
            method = wh.get('httpMethod', wh.get('method', '?'))
            print(f'    {method} /webhook/{path}')
        print(f'  Total: {len(whs)} active webhooks')
    else:
        print(f'  Response: {str(data)[:200]}')
except:
    print('  (could not parse webhook list)')
" 2>/dev/null || echo "  (webhook list unavailable)"
    fi

    return 0
}

# Run setup in best-effort mode (failures don't kill container)
setup_workflows || echo "WARNING: Workflow setup had errors — container stays alive"

# Summary
echo ""
echo "==================================================================="
echo "  BOOT COMPLETE — container alive"
echo "  Workers: queue mode via Redis"
echo "  Database: Supabase PostgreSQL (persistent)"
echo "  n8n UI: http://localhost:5678 (via nginx on :7860)"
echo "==================================================================="

# Keep container alive via supervisord
# This is the ONLY thing that matters — never exit before this
wait $SUPERVISOR_PID
