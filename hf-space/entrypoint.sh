#!/bin/bash
# =================================================================
# HF Space Entrypoint — n8n MINIMAL BOOT
# =================================================================
# Phase 1: Get n8n running on HF Space (SQLite, no queue, no workers)
# Phase 2: Add PostgreSQL + queue mode + workers once boot confirmed
#
# RESILIENCE: No set -e. Container stays alive even if setup fails.
# Last updated: 2026-02-23
# =================================================================

trap 'echo "SIGNAL received"; wait' SIGTERM SIGINT

echo "==================================================================="
echo "  NOMOS RAG ENGINE — HF Space Boot (Minimal)"
echo "==================================================================="

# ---- 1. Minimal n8n config — just enough to start ----
echo ""
echo "[1/3] Setting up environment..."

# n8n listens directly on HF's required port
export N8N_HOST=0.0.0.0
export N8N_PORT=7860
export N8N_PROTOCOL=http
export WEBHOOK_URL=https://lbjlincoln-nomos-rag-engine.hf.space

# SQLite for initial boot (will switch to PostgreSQL once boot confirmed)
export DB_TYPE=sqlite
export DB_SQLITE_DATABASE=/home/node/.n8n/database.sqlite

# Disable queue mode for simplicity (single process)
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

echo "  Mode: SQLite + single process (minimal boot)"
echo "  Port: $N8N_PORT"
echo "  Webhook URL: $WEBHOOK_URL"

# ---- 2. Start n8n directly (no supervisord for simplicity) ----
echo ""
echo "[2/3] Starting n8n..."

# Start n8n in background
n8n start &
N8N_PID=$!

# ---- 3. Wait for n8n to become healthy ----
echo ""
echo "[3/3] Waiting for n8n to become healthy..."
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
fi

# Best-effort workflow setup
if [ "$N8N_READY" = "true" ]; then
    echo ""
    echo "  Setting up workflows..."
    sleep 10  # Wait for REST API

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

    # Login
    COOKIE=""
    for attempt in $(seq 1 5); do
        RESP=$(curl -s -o /dev/null -w "%{http_code}" \
            -X POST http://127.0.0.1:7860/rest/login \
            -H "Content-Type: application/json" \
            -d "{\"emailOrLdapLoginId\":\"$CI_EMAIL\",\"password\":\"$CI_PASSWORD\"}" \
            -c /tmp/n8n-cookies.txt 2>/dev/null || echo "000")
        if [ "$RESP" = "200" ]; then
            COOKIE=$(grep n8n-auth /tmp/n8n-cookies.txt 2>/dev/null | awk '{print $NF}')
            [ -n "$COOKIE" ] && echo "  Login OK" && break
        fi
        echo "  Login attempt $attempt (HTTP $RESP)"
        sleep 3
    done

    # Import + activate workflows
    if [ -n "$COOKIE" ]; then
        IMPORT_OK=0
        for wf in /app/n8n-workflows/*.json; do
            [ -f "$wf" ] || continue
            WF_NAME=$(basename "$wf" .json)
            RESP=$(curl -s -o /dev/null -w "%{http_code}" \
                -X POST http://127.0.0.1:7860/rest/workflows \
                -H "Content-Type: application/json" \
                -b "n8n-auth=$COOKIE" \
                -d @"$wf" 2>/dev/null || echo "000")
            if [ "$RESP" = "200" ]; then
                IMPORT_OK=$((IMPORT_OK + 1))
                echo "    Imported: $WF_NAME"
            else
                echo "    $RESP: $WF_NAME"
            fi
        done
        echo "  Imported: $IMPORT_OK workflows"

        # Activate
        ALL_WFS=$(curl -s "http://127.0.0.1:7860/rest/workflows?limit=50" \
            -b "n8n-auth=$COOKIE" 2>/dev/null || echo "")
        if [ -n "$ALL_WFS" ]; then
            python3 -c "
import json, sys
try:
    data = json.loads(sys.argv[1])
    wfs = data.get('data', data) if isinstance(data, dict) else data
    if isinstance(wfs, list):
        for w in wfs:
            print(f\"{w.get('id','')}\t{w.get('name','')}\t{w.get('active',False)}\t{w.get('versionId','')}\")
except: pass
" "$ALL_WFS" > /tmp/wf-list.txt 2>/dev/null || true
            while IFS=$'\t' read -r wid wname wactive wversion; do
                [ -z "$wid" ] && continue
                if [ "$wactive" = "False" ]; then
                    ACT_RESP=$(curl -s -o /dev/null -w "%{http_code}" \
                        -X POST "http://127.0.0.1:7860/rest/workflows/$wid/activate" \
                        -H "Content-Type: application/json" \
                        -b "n8n-auth=$COOKIE" \
                        -d "{\"versionId\":\"$wversion\"}" 2>/dev/null || echo "000")
                    echo "    Activate $wname: HTTP $ACT_RESP"
                else
                    echo "    Already active: $wname"
                fi
            done < /tmp/wf-list.txt
        fi
    fi
fi

echo ""
echo "==================================================================="
echo "  BOOT COMPLETE — n8n on port 7860"
echo "  Mode: SQLite + single process"
echo "==================================================================="

# Keep container alive
wait $N8N_PID
