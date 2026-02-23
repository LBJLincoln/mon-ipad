#!/bin/bash
# =================================================================
# HF Space Entrypoint — n8n Engine v4.0
# =================================================================
# SQLITE-DIRECT APPROACH (no REST API login needed):
# 1. Strip credential refs from workflows → clean JSONs
# 2. CLI import cleaned workflows (creates SQLite entries)
# 3. sqlite3: SET active=true on ALL workflows
# 4. Start n8n → reads active=true → registers webhooks → DONE
# 5. After n8n healthy: create credentials + update workflows via REST
#
# WHY: REST API login from inside container is fragile (timing, auth).
#       Direct SQLite manipulation before n8n starts is 100% reliable.
#
# RESILIENCE: No set -e. Container stays alive even if setup fails.
# Last updated: 2026-02-23
# =================================================================

SETUP_LOG="/tmp/setup-workflows.log"
exec > >(tee -a "$SETUP_LOG") 2>&1

echo "=== NOMOS RAG ENGINE — HF Space Boot v4.0 ==="
echo "Boot started at $(date -u)"

trap 'echo "SIGNAL received"; wait' SIGTERM SIGINT

# ---- 1. Environment setup ----
echo ""
echo "[1/5] Setting up environment..."

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

# ---- 2. Strip credentials + CLI import ----
echo ""
echo "[2/5] Importing workflows via CLI..."

mkdir -p /home/node/.n8n

# Strip credential references to prevent FOREIGN KEY errors
echo "  Stripping credential references..."
mkdir -p /tmp/n8n-clean-workflows
CLEANED=0
for wf in /app/n8n-workflows/*.json; do
    [ -f "$wf" ] || continue
    WFNAME=$(basename "$wf")
    python3 -c "
import json, uuid
with open('$wf') as f:
    d = json.load(f)
# Strip credential references from nodes
for node in d.get('nodes', []):
    node.pop('credentials', None)
# Strip FK-causing fields (reference old DB objects that don't exist)
for key in ['shared', 'tags', 'activeVersion', 'activeVersionId', 'versionId',
            'versionCounter', 'triggerCount', 'pinData', 'meta', 'staticData']:
    d.pop(key, None)
# Ensure required fields
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

# CLI import (n8n creates SQLite DB on first import)
echo "  CLI importing..."
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
        echo "  FAIL: $WFNAME"
    fi
done
echo "  CLI import: $CLI_OK OK, $CLI_FAIL failed"

# ---- 3. SQLite: Activate ALL workflows directly ----
echo ""
echo "[3/5] Activating workflows via SQLite..."

DB_PATH="/home/node/.n8n/database.sqlite"
if [ -f "$DB_PATH" ]; then
    # Count workflows before activation
    WF_COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM workflow_entity;" 2>/dev/null || echo "0")
    echo "  Workflows in DB: $WF_COUNT"

    # Activate ALL workflows
    sqlite3 "$DB_PATH" "UPDATE workflow_entity SET active = 1;" 2>/dev/null
    ACTIVE_COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM workflow_entity WHERE active = 1;" 2>/dev/null || echo "0")
    echo "  Activated: $ACTIVE_COUNT workflows"

    # List all workflows
    echo "  Workflow list:"
    sqlite3 "$DB_PATH" "SELECT id, name, active FROM workflow_entity;" 2>/dev/null | while read -r line; do
        echo "    $line"
    done
else
    echo "  WARNING: Database not found at $DB_PATH"
    echo "  n8n will create it on first start"
fi

# ---- 4. Start n8n ----
echo ""
echo "[4/5] Starting n8n..."
n8n start &
N8N_PID=$!
echo "  n8n PID: $N8N_PID"

# Wait for healthy
echo "  Waiting for n8n to become healthy..."
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
    echo "  WARNING: n8n not healthy after 120s"
    echo "  PID: $N8N_PID ($(ps -p $N8N_PID -o comm= 2>/dev/null || echo 'DEAD'))"
    # Don't exit — try to keep container alive
    wait $N8N_PID
    exit 0
fi

# ---- 5. Post-start: Owner setup + credentials ----
echo ""
echo "[5/5] Post-start setup (owner + credentials)..."

# Wait for REST API
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

# Owner setup
if [ "$IS_FIRST_BOOT" = "yes" ]; then
    echo "  Creating owner account..."
    curl -s -X POST http://127.0.0.1:7860/rest/owner/setup \
        -H "Content-Type: application/json" \
        -d "{\"email\":\"$CI_EMAIL\",\"password\":\"$CI_PASSWORD\",\"firstName\":\"CI\",\"lastName\":\"Bot\"}" 2>/dev/null | head -5
    sleep 3
fi

# Login and create credentials (best-effort — webhooks work even without this)
COOKIE=""
echo "  Attempting login..."
for attempt in $(seq 1 5); do
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
            echo "  Login SUCCESS"
            break
        fi
    fi

    # If 401, try owner setup again
    if [ "$HTTP_CODE" = "401" ] && [ "$attempt" -le 2 ]; then
        curl -s -X POST http://127.0.0.1:7860/rest/owner/setup \
            -H "Content-Type: application/json" \
            -d "{\"email\":\"$CI_EMAIL\",\"password\":\"$CI_PASSWORD\",\"firstName\":\"CI\",\"lastName\":\"Bot\"}" 2>/dev/null > /dev/null
        sleep 3
    fi
    sleep 2
done

if [ -n "$COOKIE" ]; then
    echo "  Running setup-workflows.py for credentials..."
    python3 /app/setup-workflows.py "$COOKIE" "http://127.0.0.1:7860" 2>&1
    echo "  setup-workflows.py exit code: $?"
else
    echo "  Login failed — skipping credential setup."
    echo "  Webhooks will still work (workflows use \$env expressions)."
fi

# ---- Final: Verify webhooks ----
echo ""
echo "=== WEBHOOK VERIFICATION ==="
sleep 3
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
echo "  Auth: ${COOKIE:+OK}${COOKIE:-SKIPPED}"
echo "  Boot complete at $(date -u)"
echo ""
echo "==================================================================="
echo "  NOMOS RAG ENGINE READY"
echo "  URL: https://lbjlincoln-nomos-rag-engine.hf.space"
echo "  Webhooks: $WEBHOOKS_OK responding"
echo "==================================================================="

# Keep container alive
wait $N8N_PID
