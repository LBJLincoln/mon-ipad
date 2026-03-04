#!/bin/bash
# =================================================================
# HF Space Entrypoint — n8n Engine v6.0 (Persistent Postgres)
# =================================================================
# POSTGRES-BACKED PERSISTENT APPROACH:
# - Each Space uses its own Supabase schema (n8n_engine_1..6)
# - First boot: create tables + import workflows + setup credentials
# - Subsequent boots: everything persists — just verify webhooks
# - No more re-importing on every restart!
#
# Env var SPACE_NUMBER (1-6) determines which schema to use.
# Default: 1 (primary Space)
#
# KEY: PATCH {active:true} does NOT register webhooks in n8n 2.8+.
#      POST /workflows/{id}/activate with versionId is required.
#      n8n re-registers webhooks from DB on startup automatically.
#
# RESILIENCE: No set -e. Container stays alive even if setup fails.
# Last updated: 2026-03-03
# =================================================================

SETUP_LOG="/tmp/setup-workflows.log"
exec > >(tee -a "$SETUP_LOG") 2>&1

echo "=== NOMOS RAG ENGINE — HF Space Boot v5.5 ==="
echo "Boot started at $(date -u)"

trap 'echo "SIGNAL received"; wait' SIGTERM SIGINT

# ---- 1. Environment setup ----
echo ""
echo "[1/6] Setting up environment..."

export N8N_HOST=0.0.0.0
export N8N_PORT=7860
export N8N_PROTOCOL=http

# Auto-detect WEBHOOK_URL from HF environment
if [ -n "$SPACE_HOST" ]; then
    export WEBHOOK_URL="https://${SPACE_HOST}"
    echo "  WEBHOOK_URL auto-detected: $WEBHOOK_URL (from SPACE_HOST)"
elif [ -n "$HF_SPACE_URL" ]; then
    export WEBHOOK_URL="$HF_SPACE_URL"
    echo "  WEBHOOK_URL auto-detected: $WEBHOOK_URL (from HF_SPACE_URL)"
else
    export WEBHOOK_URL=https://lbjlincoln-nomos-rag-engine.hf.space
    echo "  WEBHOOK_URL fallback (hardcoded): $WEBHOOK_URL"
fi
# --- Persistent Postgres (Supabase) --- SHARED schema for all Spaces
# All Spaces share the same n8n_engine schema (same workflows, credentials).
# This means: set up once, all Spaces benefit. Load balancer can route anywhere.
# Using shared schema avoids migration conflicts across per-Space schemas.
SPACE_NUMBER="${SPACE_NUMBER:-1}"
export DB_TYPE=postgresdb
export DB_POSTGRESDB_HOST="${SUPABASE_HOST:-aws-1-eu-west-1.pooler.supabase.com}"
export DB_POSTGRESDB_PORT="${SUPABASE_PORT:-6543}"
export DB_POSTGRESDB_DATABASE="${SUPABASE_DB:-postgres}"
export DB_POSTGRESDB_USER="${SUPABASE_USER:-postgres.ayqviqmxifzmhphiqfmj}"
export DB_POSTGRESDB_PASSWORD="${SUPABASE_PASSWORD}"
export DB_POSTGRESDB_SCHEMA="n8n_engine_1"
export DB_POSTGRESDB_SSL_REJECT_UNAUTHORIZED=false
echo "  DB: Postgres schema n8n_engine_1 (shared) @ ${DB_POSTGRESDB_HOST}:${DB_POSTGRESDB_PORT} — Space #${SPACE_NUMBER}"
export EXECUTIONS_MODE=regular
export N8N_DEFAULT_BINARY_DATA_MODE=filesystem
export EXECUTIONS_DATA_PRUNE=true
export EXECUTIONS_DATA_MAX_AGE=48
export EXECUTIONS_DATA_PRUNE_MAX_COUNT=500
export N8N_DIAGNOSTICS_ENABLED=false
export N8N_RUNNERS_ENABLED=false
export N8N_ENCRYPTION_KEY="${N8N_ENCRYPTION_KEY:-sota-rag-2026-hf-space-key}"
export N8N_COMMUNITY_PACKAGES_ALLOW_TOOL_USAGE=true
export N8N_BLOCK_ENV_ACCESS_IN_NODE=false

# Per-pipeline OpenRouter keys (legacy — kept for non-core workflows)
export OPENROUTER_KEY_STANDARD="${OPENROUTER_KEY_STANDARD:-${OPENROUTER_API_KEY:-}}"
export OPENROUTER_KEY_GRAPH="${OPENROUTER_KEY_GRAPH:-${OPENROUTER_API_KEY:-}}"
export OPENROUTER_KEY_QUANTITATIVE="${OPENROUTER_KEY_QUANTITATIVE:-${OPENROUTER_API_KEY:-}}"
export OPENROUTER_KEY_ORCHESTRATOR="${OPENROUTER_KEY_ORCHESTRATOR:-${OPENROUTER_API_KEY:-}}"
export OPENROUTER_KEY_PME="${OPENROUTER_KEY_PME:-${OPENROUTER_API_KEY:-}}"
export OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# Per-pipeline Groq keys (primary — used by core pipelines post-session63)
export GROQ_API_KEY_STANDARD="${GROQ_API_KEY_STANDARD:-${GROQ_API_KEY:-}}"
export GROQ_API_KEY_GRAPH="${GROQ_API_KEY_GRAPH:-${GROQ_API_KEY:-}}"
export GROQ_API_KEY_QUANTITATIVE="${GROQ_API_KEY_QUANTITATIVE:-${GROQ_API_KEY:-}}"
export GROQ_API_KEY_ORCHESTRATOR="${GROQ_API_KEY_ORCHESTRATOR:-${GROQ_API_KEY:-}}"
export GROQ_API_KEY_PME="${GROQ_API_KEY_PME:-${GROQ_API_KEY:-}}"

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
export SUPABASE_HOST="${SUPABASE_HOST:-aws-1-eu-west-1.pooler.supabase.com}"
export SUPABASE_PORT="${SUPABASE_PORT:-6543}"
export SUPABASE_DB="${SUPABASE_DB:-postgres}"
export SUPABASE_USER="${SUPABASE_USER:-postgres.ayqviqmxifzmhphiqfmj}"
export SUPABASE_PASSWORD="${SUPABASE_PASSWORD:-}"

echo "  === ENV CHECK ==="
[ -n "$OPENROUTER_API_KEY" ] && echo "  OPENROUTER_API_KEY: SET (${#OPENROUTER_API_KEY} chars)" || echo "  OPENROUTER_API_KEY: UNSET"
[ -n "$GROQ_API_KEY_STANDARD" ] && echo "  GROQ_API_KEY_STANDARD: SET (${#GROQ_API_KEY_STANDARD} chars)" || echo "  GROQ_API_KEY_STANDARD: UNSET"
[ -n "$GROQ_API_KEY_GRAPH" ] && echo "  GROQ_API_KEY_GRAPH: SET (${#GROQ_API_KEY_GRAPH} chars)" || echo "  GROQ_API_KEY_GRAPH: UNSET"
[ -n "$GROQ_API_KEY_QUANTITATIVE" ] && echo "  GROQ_API_KEY_QUANTITATIVE: SET (${#GROQ_API_KEY_QUANTITATIVE} chars)" || echo "  GROQ_API_KEY_QUANTITATIVE: UNSET"
[ -n "$GROQ_API_KEY_ORCHESTRATOR" ] && echo "  GROQ_API_KEY_ORCHESTRATOR: SET (${#GROQ_API_KEY_ORCHESTRATOR} chars)" || echo "  GROQ_API_KEY_ORCHESTRATOR: UNSET"
[ -n "$PINECONE_API_KEY" ] && echo "  PINECONE_API_KEY: SET (${#PINECONE_API_KEY} chars)" || echo "  PINECONE_API_KEY: UNSET"
[ -n "$JINA_API_KEY" ] && echo "  JINA_API_KEY: SET (${#JINA_API_KEY} chars)" || echo "  JINA_API_KEY: UNSET"
[ -n "$SUPABASE_PASSWORD" ] && echo "  SUPABASE_PASSWORD: SET (${#SUPABASE_PASSWORD} chars)" || echo "  SUPABASE_PASSWORD: UNSET"
[ -n "$NEO4J_AUTH" ] && echo "  NEO4J_AUTH: SET (${#NEO4J_AUTH} chars)" || echo "  NEO4J_AUTH: UNSET"
[ -n "$N8N_ENCRYPTION_KEY" ] && echo "  N8N_ENCRYPTION_KEY: SET" || echo "  N8N_ENCRYPTION_KEY: UNSET"
echo "  ================="

# ---- 2. Check persistence + conditional import ----
echo ""
echo "[2/6] Checking database persistence..."

mkdir -p /home/node/.n8n

# Check if Postgres schema already has workflows (persistent from previous boot)
DB_HAS_WORKFLOWS=false
if [ -n "$SUPABASE_PASSWORD" ]; then
    WF_COUNT=$(python3 -c "
import urllib.request, json, os, ssl
# Check if n8n tables exist by trying a quick count
# n8n will create tables on first start, so we just check if schema exists
schema = os.environ.get('DB_POSTGRESDB_SCHEMA', 'n8n_engine_1')
print('0')  # Will be checked after n8n starts
" 2>/dev/null || echo "0")
    echo "  Postgres schema: n8n_engine_${SPACE_NUMBER}"
    echo "  Pre-check: will verify workflow count after n8n starts"
fi

# Always prepare clean workflows (needed for first boot or updates)
echo "  Preparing clean workflow files..."
mkdir -p /tmp/n8n-clean-workflows
CLEANED=0
for wf in /app/n8n-workflows/*.json; do
    [ -f "$wf" ] || continue
    WFNAME=$(basename "$wf")
    python3 -c "
import json, uuid
with open('$wf') as f:
    d = json.load(f)
# Strip credential references to prevent FOREIGN KEY errors
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

# ---- 3. Start n8n ----
echo ""
echo "[3/6] Starting n8n..."
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

# ---- 3b. Check if DB already has workflows (persistent boot) ----
echo "  Checking if workflows already in Postgres..."
EXISTING_WF_COUNT=$(curl -s http://127.0.0.1:7860/rest/workflows 2>/dev/null | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    data = d.get('data', d)
    if isinstance(data, list):
        print(len(data))
    else:
        print(0)
except:
    print(0)
" 2>/dev/null || echo "0")
echo "  Existing workflows in DB: $EXISTING_WF_COUNT"

if [ "$EXISTING_WF_COUNT" -gt 3 ] 2>/dev/null; then
    echo "  PERSISTENT BOOT — $EXISTING_WF_COUNT workflows found. Skipping CLI import."
    NEEDS_IMPORT=false
else
    echo "  FIRST BOOT — importing workflows via CLI..."
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
    NEEDS_IMPORT=true
fi

# ---- 4. Post-start: Owner setup + credentials ----
echo ""
echo "[4/6] Post-start setup (owner + credentials)..."

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

# Login with extensive retry + diagnostics
COOKIE=""
echo "  Attempting login (10 attempts with diagnostics)..."
for attempt in $(seq 1 10); do
    LOGIN_RAW=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
        -X POST http://127.0.0.1:7860/rest/login \
        -H "Content-Type: application/json" \
        -d "{\"emailOrLdapLoginId\":\"$CI_EMAIL\",\"password\":\"$CI_PASSWORD\"}" \
        -c /tmp/n8n-cookies.txt 2>/dev/null)
    HTTP_CODE=$(echo "$LOGIN_RAW" | grep "^HTTP_CODE:" | head -1 | sed 's/HTTP_CODE://')
    LOGIN_BODY=$(echo "$LOGIN_RAW" | grep -v "^HTTP_CODE:" | head -c 300)
    echo "  Attempt $attempt: HTTP $HTTP_CODE | Body: ${LOGIN_BODY:0:150}"

    if [ "$HTTP_CODE" = "200" ]; then
        COOKIE=$(grep n8n-auth /tmp/n8n-cookies.txt 2>/dev/null | awk '{print $NF}')
        if [ -n "$COOKIE" ]; then
            echo "  LOGIN SUCCESS (cookie: ${#COOKIE} chars)"
            break
        else
            echo "  HTTP 200 but no n8n-auth cookie. Cookie jar:"
            cat /tmp/n8n-cookies.txt 2>/dev/null
        fi
    fi

    # If 401, try owner setup again (may need multiple attempts)
    if [ "$HTTP_CODE" = "401" ] && [ "$attempt" -le 5 ]; then
        echo "  401 → retrying owner setup..."
        OWNER_RESP=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
            -X POST http://127.0.0.1:7860/rest/owner/setup \
            -H "Content-Type: application/json" \
            -d "{\"email\":\"$CI_EMAIL\",\"password\":\"$CI_PASSWORD\",\"firstName\":\"CI\",\"lastName\":\"Bot\"}" 2>/dev/null)
        OWNER_HTTP=$(echo "$OWNER_RESP" | grep "^HTTP_CODE:" | head -1 | sed 's/HTTP_CODE://')
        echo "  Owner setup: HTTP $OWNER_HTTP"
        sleep 3
    fi
    sleep 2
done

if [ -z "$COOKIE" ]; then
    echo ""
    echo "  ============================================"
    echo "  CRITICAL: LOGIN FAILED AFTER 10 ATTEMPTS"
    echo "  ============================================"
fi

# ---- 5. Credential restore + publish/activate ----
echo ""

if [ "$NEEDS_IMPORT" = "true" ] || [ "$IS_FIRST_BOOT" = "yes" ]; then
    echo "[5/6] FIRST BOOT: Running setup-workflows.py (credentials + publish + activate)..."
    if [ -n "$COOKIE" ]; then
        SETUP_SUCCESS=false
        for setup_attempt in 1 2 3; do
            echo "  === setup-workflows.py attempt $setup_attempt/3 ==="
            if python3 /app/setup-workflows.py "$COOKIE" "http://127.0.0.1:7860" 2>&1; then
                SETUP_EXIT=$?
                echo "  setup-workflows.py exit code: $SETUP_EXIT"
                if [ $SETUP_EXIT -eq 0 ]; then
                    SETUP_SUCCESS=true
                    break
                fi
            else
                SETUP_EXIT=$?
                echo "  setup-workflows.py FAILED with exit code: $SETUP_EXIT"
            fi
            if [ $setup_attempt -lt 3 ]; then
                echo "  Waiting 10s before retry..."
                sleep 10
            fi
        done
        if [ "$SETUP_SUCCESS" != "true" ]; then
            echo "  WARNING: setup-workflows.py failed after 3 attempts"
        else
            echo "  setup-workflows.py completed successfully"
        fi
    else
        echo "  Login failed — skipping credential setup."
    fi
else
    echo "[5/6] PERSISTENT BOOT: Credentials already in Postgres — skipping setup."
    echo "  Re-activating webhooks from persisted state..."
    # n8n auto-registers webhooks from DB on startup, but verify with activation
    if [ -n "$COOKIE" ]; then
        # Quick re-activation of all active workflows
        ACTIVE_WFS=$(curl -s http://127.0.0.1:7860/rest/workflows \
            -H "Cookie: n8n-auth=$COOKIE" 2>/dev/null | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    data = d.get('data', d)
    for wf in (data if isinstance(data, list) else []):
        if wf.get('active'):
            print(wf['id'])
except:
    pass
" 2>/dev/null || true)
        REACTIVATED=0
        for wf_id in $ACTIVE_WFS; do
            # Get versionId and re-activate
            VER=$(curl -s "http://127.0.0.1:7860/rest/workflows/$wf_id" \
                -H "Cookie: n8n-auth=$COOKIE" 2>/dev/null | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    data = d.get('data', d)
    print(data.get('versionId',''))
except:
    pass
" 2>/dev/null || true)
            if [ -n "$VER" ]; then
                curl -s -X POST "http://127.0.0.1:7860/rest/workflows/$wf_id/activate" \
                    -H "Cookie: n8n-auth=$COOKIE" \
                    -H "Content-Type: application/json" \
                    -d "{\"versionId\":\"$VER\"}" > /dev/null 2>&1
                REACTIVATED=$((REACTIVATED + 1))
            fi
        done
        echo "  Re-activated $REACTIVATED workflows"
    fi
fi

# ---- 6. Verify webhooks ----
echo ""
echo "[6/6] Webhook verification..."
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
echo "  NOMOS RAG ENGINE READY — Space #${SPACE_NUMBER}"
echo "  DB: Postgres (n8n_engine_${SPACE_NUMBER}) — PERSISTENT"
echo "  URL: ${WEBHOOK_URL}"
echo "  Webhooks: $WEBHOOKS_OK responding"
echo "  Boot type: $([ \"$NEEDS_IMPORT\" = \"true\" ] && echo 'FIRST (imported workflows)' || echo 'PERSISTENT (from DB)')"
echo "==================================================================="

# Keep container alive
wait $N8N_PID
