#!/bin/bash
# =================================================================
# HF Space Entrypoint — n8n Engine v5.0
# =================================================================
# POSTGRESQL + REST API ACTIVATION
#
# 1. Strip credential refs from workflows → clean JSONs
# 2. CLI import cleaned workflows (n8n creates PG tables on import)
# 3. Start n8n → connects to Supabase PostgreSQL
# 4. Wait healthy → Login → Create credentials → Activate via REST
# 5. Verify webhooks
#
# WHY v5.0:
# - v4.0 used SQLite + sqlite3 active=1 hack → didn't register webhooks
# - PostgreSQL (Supabase) = data persists across HF Space rebuilds
# - REST API PATCH activation = proper webhook registration
#
# RESILIENCE: No set -e. Container stays alive even if setup fails.
# Last updated: 2026-02-23
# =================================================================

SETUP_LOG="/tmp/setup-workflows.log"
exec > >(tee -a "$SETUP_LOG") 2>&1

echo "=== NOMOS RAG ENGINE — HF Space Boot v5.0 ==="
echo "Boot started at $(date -u)"

trap 'echo "SIGNAL received"; wait' SIGTERM SIGINT

# ---- 1. Environment setup ----
echo ""
echo "[1/6] Setting up environment..."

export N8N_HOST=0.0.0.0
export N8N_PORT=7860
export N8N_PROTOCOL=http
export WEBHOOK_URL=https://lbjlincoln-nomos-rag-engine.hf.space

# PostgreSQL (Supabase) — persistent across rebuilds
export DB_TYPE=postgresdb
export DB_POSTGRESDB_HOST="${SUPABASE_HOST:-aws-0-eu-west-1.pooler.supabase.com}"
export DB_POSTGRESDB_PORT="${SUPABASE_PORT:-6543}"
export DB_POSTGRESDB_DATABASE="${SUPABASE_DB:-postgres}"
export DB_POSTGRESDB_USER="${SUPABASE_USER:-postgres.kfyrtsmdolgioyxsglbz}"
export DB_POSTGRESDB_PASSWORD="${SUPABASE_PASSWORD:-}"
export DB_POSTGRESDB_SSL_REJECT_UNAUTHORIZED=false
export DB_POSTGRESDB_SCHEMA=public

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

# External service env vars (for $env expressions in workflows)
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
echo "  DB_TYPE: $DB_TYPE"
echo "  DB_HOST: $DB_POSTGRESDB_HOST"
echo "  DB_PORT: $DB_POSTGRESDB_PORT"
echo "  DB_SCHEMA: $DB_POSTGRESDB_SCHEMA"
[ -n "$DB_POSTGRESDB_PASSWORD" ] && echo "  DB_PASSWORD: SET (${#DB_POSTGRESDB_PASSWORD} chars)" || echo "  DB_PASSWORD: UNSET"
[ -n "$OPENROUTER_API_KEY" ] && echo "  OPENROUTER_API_KEY: SET (${#OPENROUTER_API_KEY} chars)" || echo "  OPENROUTER_API_KEY: UNSET"
[ -n "$PINECONE_API_KEY" ] && echo "  PINECONE_API_KEY: SET (${#PINECONE_API_KEY} chars)" || echo "  PINECONE_API_KEY: UNSET"
[ -n "$JINA_API_KEY" ] && echo "  JINA_API_KEY: SET (${#JINA_API_KEY} chars)" || echo "  JINA_API_KEY: UNSET"
[ -n "$NEO4J_AUTH" ] && echo "  NEO4J_AUTH: SET (${#NEO4J_AUTH} chars)" || echo "  NEO4J_AUTH: UNSET"
[ -n "$N8N_ENCRYPTION_KEY" ] && echo "  N8N_ENCRYPTION_KEY: SET" || echo "  N8N_ENCRYPTION_KEY: UNSET"
echo "  ================="

# ---- 2. Strip credentials from workflow JSONs ----
echo ""
echo "[2/6] Stripping credential refs from workflow JSONs..."

mkdir -p /home/node/.n8n
mkdir -p /tmp/n8n-clean-workflows
CLEANED=0
for wf in /app/n8n-workflows/*.json; do
    [ -f "$wf" ] || continue
    WFNAME=$(basename "$wf")
    python3 -c "
import json, uuid
with open('$wf') as f:
    d = json.load(f)
for node in d.get('nodes', []):
    node.pop('credentials', None)
for key in ['shared', 'tags', 'activeVersion', 'activeVersionId', 'versionId',
            'versionCounter', 'triggerCount', 'pinData', 'meta', 'staticData']:
    d.pop(key, None)
if not d.get('id'):
    d['id'] = str(uuid.uuid4())[:20].replace('-','')
d['active'] = False
with open('/tmp/n8n-clean-workflows/$WFNAME', 'w') as f:
    json.dump(d, f)
print('  Cleaned: $WFNAME')
" 2>&1
    CLEANED=$((CLEANED + 1))
done
echo "  Cleaned $CLEANED workflow files"

# ---- 3. CLI import (creates PG schema + imports) ----
echo ""
echo "[3/6] CLI importing workflows..."

CLI_OK=0
CLI_FAIL=0
for wf in /tmp/n8n-clean-workflows/*.json; do
    [ -f "$wf" ] || continue
    WFNAME=$(basename "$wf")
    if n8n import:workflow --input="$wf" 2>&1; then
        CLI_OK=$((CLI_OK + 1))
        echo "  OK: $WFNAME"
    else
        CLI_FAIL=$((CLI_FAIL + 1))
        echo "  FAIL: $WFNAME (may already exist — OK)"
    fi
done
echo "  CLI import: $CLI_OK OK, $CLI_FAIL failed"

# ---- 4. Start n8n ----
echo ""
echo "[4/6] Starting n8n..."
n8n start &
N8N_PID=$!
echo "  n8n PID: $N8N_PID"

# Wait for healthy
echo "  Waiting for n8n to become healthy..."
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
    echo "  CRITICAL: n8n not healthy after 180s"
    echo "  PID: $N8N_PID ($(ps -p $N8N_PID -o comm= 2>/dev/null || echo 'DEAD'))"
    echo "  Checking if PG connection issue..."
    echo "  DB_HOST=$DB_POSTGRESDB_HOST DB_PORT=$DB_POSTGRESDB_PORT"
    wait $N8N_PID
    exit 0
fi

# ---- 5. REST API: Owner + Login + Credentials + Activate ----
echo ""
echo "[5/6] REST API setup (owner + credentials + activation)..."

# Wait for REST API to be fully ready
echo "  Waiting for REST API..."
for i in $(seq 1 30); do
    RESP=$(curl -s http://127.0.0.1:7860/rest/settings 2>/dev/null || echo "")
    if echo "$RESP" | python3 -c "import sys,json; json.load(sys.stdin)" 2>/dev/null; then
        echo "  REST API ready after $((i*2))s"
        break
    fi
    sleep 2
done

CI_EMAIL="${CI_EMAIL:-ci@nomos.ai}"
CI_PASSWORD="${CI_PASSWORD:-CI-Nomos-2026!}"

# Check if first boot
SETTINGS=$(curl -s http://127.0.0.1:7860/rest/settings 2>/dev/null || echo "{}")
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

# Owner setup (first boot only)
if [ "$IS_FIRST_BOOT" = "yes" ]; then
    echo "  Creating owner account..."
    OWNER_RESP=$(curl -s -w "\n_HTTP_%{http_code}" \
        -X POST http://127.0.0.1:7860/rest/owner/setup \
        -H "Content-Type: application/json" \
        -d "{\"email\":\"$CI_EMAIL\",\"password\":\"$CI_PASSWORD\",\"firstName\":\"CI\",\"lastName\":\"Bot\"}" 2>/dev/null)
    OWNER_HTTP=$(echo "$OWNER_RESP" | grep "^_HTTP_" | head -1 | sed 's/_HTTP_//')
    echo "  Owner setup: HTTP $OWNER_HTTP"
    sleep 3
fi

# Login with retry
COOKIE=""
echo "  Attempting login..."
for attempt in $(seq 1 8); do
    LOGIN_RESP=$(curl -s -w "\n_HTTP_%{http_code}" \
        -X POST http://127.0.0.1:7860/rest/login \
        -H "Content-Type: application/json" \
        -d "{\"emailOrLdapLoginId\":\"$CI_EMAIL\",\"password\":\"$CI_PASSWORD\"}" \
        -c /tmp/n8n-cookies.txt 2>/dev/null)
    HTTP_CODE=$(echo "$LOGIN_RESP" | grep "^_HTTP_" | head -1 | sed 's/_HTTP_//')
    echo "  Login attempt $attempt: HTTP $HTTP_CODE"

    if [ "$HTTP_CODE" = "200" ]; then
        COOKIE=$(grep n8n-auth /tmp/n8n-cookies.txt 2>/dev/null | awk '{print $NF}')
        if [ -n "$COOKIE" ]; then
            echo "  Login SUCCESS (cookie: ${#COOKIE} chars)"
            break
        else
            echo "  HTTP 200 but no cookie — checking response..."
            echo "$LOGIN_RESP" | head -3
        fi
    fi

    # If 401, try owner setup again (in case timing issue)
    if [ "$HTTP_CODE" = "401" ] && [ "$attempt" -le 3 ]; then
        echo "  Retrying owner setup..."
        curl -s -X POST http://127.0.0.1:7860/rest/owner/setup \
            -H "Content-Type: application/json" \
            -d "{\"email\":\"$CI_EMAIL\",\"password\":\"$CI_PASSWORD\",\"firstName\":\"CI\",\"lastName\":\"Bot\"}" 2>/dev/null > /dev/null
        sleep 3
    fi
    sleep 2
done

if [ -z "$COOKIE" ]; then
    echo "  CRITICAL: Login failed after 8 attempts"
    echo "  Webhooks will NOT work (cannot activate workflows)"
    echo "  Dumping n8n logs for debug..."
    # Write diagnostic info accessible via /tmp/setup-workflows.log
    echo "LOGIN_FAILED" > /tmp/boot-status.txt
    # Still keep container alive
    wait $N8N_PID
    exit 0
fi

# Run setup-workflows.py (creates credentials, updates workflows, activates)
echo "  Running setup-workflows.py..."
python3 /app/setup-workflows.py "$COOKIE" "http://127.0.0.1:7860" 2>&1
SETUP_EXIT=$?
echo "  setup-workflows.py exit code: $SETUP_EXIT"

# ---- 6. Verify webhooks ----
echo ""
echo "[6/6] Verifying webhooks..."
sleep 5

WEBHOOKS_OK=0
WEBHOOKS_TOTAL=0
for wh in debug-status rag-multi-index-v3 ff622742-6d71-4e91-af71-b5c666088717 3e0f8010-39e0-4bca-9d19-35e5094391a9 92217bb8-ffc8-459a-8331-3f553812c3d0 pme-assistant-gateway; do
    WEBHOOKS_TOTAL=$((WEBHOOKS_TOTAL + 1))
    WH_CODE=$(curl -s -o /tmp/wh-resp.txt -w "%{http_code}" -X POST \
        "http://127.0.0.1:7860/webhook/$wh" \
        -H "Content-Type: application/json" \
        -d '{"question":"boot-verify","query":"boot-verify"}' --max-time 15 2>/dev/null || echo "000")
    BODY=$(head -c 200 /tmp/wh-resp.txt 2>/dev/null || echo "")
    STATUS="FAIL"
    [ "$WH_CODE" != "404" ] && [ "$WH_CODE" != "000" ] && STATUS="OK" && WEBHOOKS_OK=$((WEBHOOKS_OK + 1))
    echo "  $wh: HTTP $WH_CODE ($STATUS)"
done

# Write boot status for diagnostic endpoint
echo "${WEBHOOKS_OK}/${WEBHOOKS_TOTAL}" > /tmp/boot-status.txt

echo ""
echo "=== BOOT COMPLETE ==="
echo "  n8n PID: $N8N_PID"
echo "  n8n version: $(n8n --version 2>/dev/null || echo '?')"
echo "  Database: PostgreSQL (Supabase) schema=n8n"
echo "  Webhooks: $WEBHOOKS_OK/$WEBHOOKS_TOTAL responding"
echo "  Auth: OK (cookie obtained)"
echo "  Boot completed at $(date -u)"
echo ""
echo "==================================================================="
echo "  NOMOS RAG ENGINE v5.0 READY"
echo "  URL: https://lbjlincoln-nomos-rag-engine.hf.space"
echo "  Webhooks: $WEBHOOKS_OK/$WEBHOOKS_TOTAL responding"
echo "  DB: PostgreSQL (persistent across rebuilds)"
echo "==================================================================="

# Keep container alive
wait $N8N_PID
