#!/bin/bash
# =================================================================
# HF Space Entrypoint — n8n Engine v3.1
# =================================================================
# NUCLEAR APPROACH:
# 1. Start n8n to create initial database
# 2. Wait for healthy
# 3. Setup owner account
# 4. Import workflows via REST API with auth
# 5. Activate all workflows
# 6. NEVER stop trying — retry until it works
#
# RESILIENCE: No set -e. Container stays alive even if setup fails.
# Last updated: 2026-02-23
# =================================================================

SETUP_LOG="/tmp/setup-workflows.log"
exec > >(tee -a "$SETUP_LOG") 2>&1

echo "=== NOMOS RAG ENGINE — HF Space Boot v3.1 ==="
echo "Boot started at $(date -u)"

trap 'echo "SIGNAL received"; wait' SIGTERM SIGINT

# ---- 1. Environment setup ----
echo ""
echo "[1/4] Setting up environment..."

export N8N_HOST=0.0.0.0
export N8N_PORT=7860
export N8N_PROTOCOL=http
export WEBHOOK_URL=https://lbjlincoln-nomos-rag-engine.hf.space
export DB_TYPE=sqlite
export DB_SQLITE_DATABASE=/home/node/.n8n/database.sqlite
export EXECUTIONS_MODE=regular
export N8N_DEFAULT_BINARY_DATA_MODE=filesystem
export EXECUTIONS_DATA_PRUNE=true
export EXECUTIONS_DATA_MAX_AGE=48
export EXECUTIONS_DATA_PRUNE_MAX_COUNT=500
export N8N_DIAGNOSTICS_ENABLED=false
export N8N_RUNNERS_ENABLED=false
export N8N_ENCRYPTION_KEY="${N8N_ENCRYPTION_KEY:-sota-rag-2026-hf-space-key}"
export N8N_COMMUNITY_PACKAGES_ALLOW_TOOL_USAGE=true

# Per-pipeline OpenRouter keys
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

# External service env vars
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

echo "  === ENV CHECK ==="
[ -n "$OPENROUTER_API_KEY" ] && echo "  OPENROUTER_API_KEY: SET (${#OPENROUTER_API_KEY} chars)" || echo "  OPENROUTER_API_KEY: UNSET"
[ -n "$PINECONE_API_KEY" ] && echo "  PINECONE_API_KEY: SET (${#PINECONE_API_KEY} chars)" || echo "  PINECONE_API_KEY: UNSET"
[ -n "$JINA_API_KEY" ] && echo "  JINA_API_KEY: SET (${#JINA_API_KEY} chars)" || echo "  JINA_API_KEY: UNSET"
[ -n "$SUPABASE_PASSWORD" ] && echo "  SUPABASE_PASSWORD: SET (${#SUPABASE_PASSWORD} chars)" || echo "  SUPABASE_PASSWORD: UNSET"
[ -n "$NEO4J_AUTH" ] && echo "  NEO4J_AUTH: SET (${#NEO4J_AUTH} chars)" || echo "  NEO4J_AUTH: UNSET"
[ -n "$N8N_ENCRYPTION_KEY" ] && echo "  N8N_ENCRYPTION_KEY: SET" || echo "  N8N_ENCRYPTION_KEY: UNSET"
echo "  ================="

# ---- 2. Start n8n ----
echo ""
echo "[2/4] Starting n8n..."

# Strip credential references from workflow JSONs to prevent FOREIGN KEY errors
# during CLI import (credentials will be re-added by setup-workflows.py later)
echo "  Stripping credential references from workflow JSONs..."
mkdir -p /tmp/n8n-clean-workflows
for wf in /app/n8n-workflows/*.json; do
    [ -f "$wf" ] || continue
    WFNAME=$(basename "$wf")
    python3 -c "
import json, sys
with open('$wf') as f:
    d = json.load(f)
for node in d.get('nodes', []):
    node.pop('credentials', None)
# Set active=false to prevent activation errors during import
d['active'] = False
with open('/tmp/n8n-clean-workflows/$WFNAME', 'w') as f:
    json.dump(d, f)
print('  Cleaned: $WFNAME')
" 2>&1
done

# CLI import the cleaned workflows (no credential refs = no FOREIGN KEY errors)
echo "  CLI importing cleaned workflows..."
CLI_IMPORTED=0
for wf in /tmp/n8n-clean-workflows/*.json; do
    [ -f "$wf" ] || continue
    WFNAME=$(basename "$wf")
    if n8n import:workflow --input="$wf" 2>&1; then
        CLI_IMPORTED=$((CLI_IMPORTED + 1))
    else
        echo "  CLI FAIL: $WFNAME"
    fi
done
echo "  CLI import: $CLI_IMPORTED workflows"

mkdir -p /home/node/.n8n
n8n start &
N8N_PID=$!
echo "  n8n PID: $N8N_PID"

# ---- 3. Wait for healthy ----
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
    echo "WARNING: n8n not healthy after 120s"
    echo "  PID: $N8N_PID ($(ps -p $N8N_PID -o comm= 2>/dev/null || echo 'DEAD'))"
    wait $N8N_PID
    exit 0
fi

# ---- 4. Full setup: owner + credentials + workflows + activation ----
echo ""
echo "[4/4] Full setup..."

# Wait for REST API to be fully ready
echo "  Waiting for REST API..."
for i in $(seq 1 30); do
    if curl -s http://127.0.0.1:7860/rest/settings 2>/dev/null | python3 -c "import sys,json; json.load(sys.stdin)" 2>/dev/null; then
        echo "  REST API ready after $((i*2))s"
        break
    fi
    sleep 2
done

CI_EMAIL="${CI_EMAIL:-ci@nomos.ai}"
CI_PASSWORD="${CI_PASSWORD:-CI-Nomos-2026!}"

# Check settings
SETTINGS=$(curl -s http://127.0.0.1:7860/rest/settings 2>/dev/null || echo "{}")
echo "  Settings response (first 200 chars): ${SETTINGS:0:200}"

IS_FIRST_BOOT=$(echo "$SETTINGS" | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin)
    data = d.get('data', d)
    setup = data.get('userManagement',{}).get('showSetupOnFirstLoad',False)
    print('yes' if setup else 'no')
except:
    print('error')
" 2>/dev/null || echo "error")
echo "  First boot: $IS_FIRST_BOOT"

# Owner setup (if first boot)
if [ "$IS_FIRST_BOOT" = "yes" ]; then
    echo "  Creating owner account..."
    OWNER_RESP=$(curl -s -w "\n_HTTP_%{http_code}" -X POST http://127.0.0.1:7860/rest/owner/setup \
        -H "Content-Type: application/json" \
        -d "{\"email\":\"$CI_EMAIL\",\"password\":\"$CI_PASSWORD\",\"firstName\":\"CI\",\"lastName\":\"Bot\"}" 2>/dev/null)
    echo "  Owner setup response: $OWNER_RESP"
    sleep 5
fi

# Login — try multiple times with different approaches
COOKIE=""
echo "  Attempting login..."
for attempt in $(seq 1 15); do
    LOGIN_RESP=$(curl -s -w "\n_HTTP_%{http_code}" \
        -X POST http://127.0.0.1:7860/rest/login \
        -H "Content-Type: application/json" \
        -d "{\"emailOrLdapLoginId\":\"$CI_EMAIL\",\"password\":\"$CI_PASSWORD\"}" \
        -c /tmp/n8n-cookies.txt 2>/dev/null)
    HTTP_CODE=$(echo "$LOGIN_RESP" | grep "^_HTTP_" | head -1 | sed 's/_HTTP_//')
    echo "  Login attempt $attempt: HTTP $HTTP_CODE"
    echo "  Login body: $(echo "$LOGIN_RESP" | grep -v '^_HTTP_' | head -3)"

    if [ "$HTTP_CODE" = "200" ]; then
        COOKIE=$(grep n8n-auth /tmp/n8n-cookies.txt 2>/dev/null | awk '{print $NF}')
        if [ -n "$COOKIE" ]; then
            echo "  Login SUCCESS (cookie=${COOKIE:0:10}...)"
            break
        else
            echo "  Login 200 but no cookie in jar. Cookie jar contents:"
            cat /tmp/n8n-cookies.txt 2>/dev/null || echo "  (empty)"
        fi
    fi

    # If we get 401, try creating owner again
    if [ "$HTTP_CODE" = "401" ] && [ "$attempt" -le 3 ]; then
        echo "  Got 401 — retrying owner setup..."
        curl -s -X POST http://127.0.0.1:7860/rest/owner/setup \
            -H "Content-Type: application/json" \
            -d "{\"email\":\"$CI_EMAIL\",\"password\":\"$CI_PASSWORD\",\"firstName\":\"CI\",\"lastName\":\"Bot\"}" 2>/dev/null | head -3
        sleep 3
    fi

    sleep 2
done

if [ -z "$COOKIE" ]; then
    echo "  CRITICAL: Cannot login after 15 attempts"
    echo "  Attempting n8n CLI import as last resort..."

    # CLI import as fallback
    for wf in /app/n8n-workflows/*.json; do
        [ -f "$wf" ] || continue
        WFNAME=$(basename "$wf")
        echo "  CLI import: $WFNAME"
        n8n import:workflow --input="$wf" 2>&1 || echo "  CLI FAILED: $WFNAME"
    done
    echo "  CLI import done. Workflows may not be activated."
    echo "  Restarting n8n to pick up imported workflows..."
    kill $N8N_PID 2>/dev/null
    sleep 5
    n8n start &
    N8N_PID=$!
    echo "  New n8n PID: $N8N_PID"
else
    # We have auth — run the full setup
    echo ""
    echo "  Running setup-workflows.py..."
    python3 /app/setup-workflows.py "$COOKIE" "http://127.0.0.1:7860" 2>&1
    echo "  setup-workflows.py exit code: $?"
fi

# ---- Final: Verify webhooks ----
echo ""
echo "=== WEBHOOK VERIFICATION ==="
sleep 5
WEBHOOKS_OK=0
for wh in debug-status rag-multi-index-v3 ff622742-6d71-4e91-af71-b5c666088717 3e0f8010-39e0-4bca-9d19-35e5094391a9 92217bb8-ffc8-459a-8331-3f553812c3d0 pme-assistant-gateway; do
    WH_CODE=$(curl -s -o /tmp/wh-resp.txt -w "%{http_code}" -X POST \
        "http://127.0.0.1:7860/webhook/$wh" \
        -H "Content-Type: application/json" \
        -d '{"question":"boot-verify","query":"boot-verify"}' --max-time 10 2>/dev/null || echo "000")
    BODY=$(head -c 200 /tmp/wh-resp.txt 2>/dev/null || echo "")
    STATUS="FAIL"
    [ "$WH_CODE" != "404" ] && [ "$WH_CODE" != "000" ] && STATUS="OK" && WEBHOOKS_OK=$((WEBHOOKS_OK + 1))
    echo "  $wh: HTTP $WH_CODE ($STATUS) — ${BODY:0:100}"
done

echo ""
echo "=== BOOT COMPLETE ==="
echo "  n8n PID: $N8N_PID"
echo "  n8n version: $(n8n --version 2>/dev/null || echo '?')"
echo "  Webhooks working: $WEBHOOKS_OK"
echo "  Auth: ${COOKIE:+OK}${COOKIE:-FAILED}"
echo "  Setup log: /tmp/setup-workflows.log ($(wc -l < /tmp/setup-workflows.log 2>/dev/null || echo 0) lines)"
echo "  Boot complete at $(date -u)"
echo ""
echo "==================================================================="
echo "  NOMOS RAG ENGINE READY"
echo "  URL: https://lbjlincoln-nomos-rag-engine.hf.space"
echo "  Webhooks: $WEBHOOKS_OK responding"
echo "==================================================================="

# Keep container alive
wait $N8N_PID
