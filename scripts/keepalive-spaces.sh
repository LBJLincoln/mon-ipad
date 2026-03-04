#!/usr/bin/env bash
#
# keepalive-spaces.sh — Ping all 10 HF Spaces to prevent 48h sleep timeout
#
# HF free-tier cpu-basic spaces sleep after 48h of inactivity.
# This script pings each space and restarts any that are unresponsive.
#
# Spaces run different services:
#   - Spaces 1-6, 8-10: n8n (health: /healthz)
#   - Space 7: LiteLLM proxy (health: /health/liveliness)
#
# Usage:
#   bash scripts/keepalive-spaces.sh          # One-shot run
#   bash scripts/keepalive-spaces.sh --cron   # Silent mode for cron (no stdout)
#
# Cron setup (every 30 minutes):
#   */30 * * * * /home/termius/mon-ipad/scripts/keepalive-spaces.sh --cron
#
# Last updated: 2026-03-04

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="/tmp/spaces-keepalive.log"
MAX_LOG_LINES=5000

# Source env vars
if [[ -f "$PROJECT_DIR/.env.local" ]]; then
    source "$PROJECT_DIR/.env.local"
else
    echo "[ERROR] .env.local not found at $PROJECT_DIR/.env.local" | tee -a "$LOG_FILE"
    exit 1
fi

CRON_MODE=false
if [[ "${1:-}" == "--cron" ]]; then
    CRON_MODE=true
fi

log() {
    local msg="[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $1"
    echo "$msg" >> "$LOG_FILE"
    if [[ "$CRON_MODE" == false ]]; then
        echo "$msg"
    fi
}

# Space definitions: index|url|repo_id|token_var|health_path
# Space 7 is LiteLLM (uses /health/liveliness), all others are n8n (use /healthz)
declare -a SPACE_DEFS=(
    "1|${HF_SPACE_1_URL:-}|LBJLincoln/nomos-rag-engine|HF_TOKEN|/healthz"
    "2|${HF_SPACE_2_URL:-}|LBJLincoln26/nomos-rag-engine-2|HF_TOKEN_2|/healthz"
    "3|${HF_SPACE_3_URL:-}|LBJLincoln/nomos-rag-engine-3|HF_TOKEN|/healthz"
    "4|${HF_SPACE_4_URL:-}|LBJLincoln26/nomos-rag-engine-4|HF_TOKEN_2|/healthz"
    "5|${HF_SPACE_5_URL:-}|LBJLincoln/nomos-rag-engine-5|HF_TOKEN|/healthz"
    "6|${HF_SPACE_6_URL:-}|LBJLincoln26/nomos-rag-engine-6|HF_TOKEN_2|/healthz"
    "7|${HF_SPACE_7_URL:-}|LBJLincoln/nomos-rag-engine-7|HF_TOKEN|/health/liveliness"
    "8|${HF_SPACE_8_URL:-}|LBJLincoln26/nomos-rag-engine-8|HF_TOKEN_2|/healthz"
    "9|${HF_SPACE_9_URL:-}|LBJLincoln/nomos-rag-engine-9|HF_TOKEN|/healthz"
    "10|${HF_SPACE_10_URL:-}|LBJLincoln26/nomos-rag-engine-10|HF_TOKEN_2|/healthz"
)

TOTAL=0
HEALTHY=0
RESTARTED=0
FAILED=0

log "--- Keepalive check starting (${#SPACE_DEFS[@]} spaces) ---"

for entry in "${SPACE_DEFS[@]}"; do
    IFS='|' read -r idx url repo_id token_var health_path <<< "$entry"
    TOTAL=$((TOTAL + 1))

    if [[ -z "$url" ]]; then
        log "Space #$idx: SKIP (no URL configured)"
        FAILED=$((FAILED + 1))
        continue
    fi

    # Ping the appropriate health endpoint
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 15 "${url}${health_path}" 2>/dev/null || echo "000")

    if [[ "$HTTP_CODE" == "200" ]]; then
        log "Space #$idx: OK (HTTP $HTTP_CODE) - $url"
        HEALTHY=$((HEALTHY + 1))
    else
        log "Space #$idx: DOWN (HTTP $HTTP_CODE on $health_path) - $url - Attempting restart..."

        # Get the token value
        TOKEN_VALUE="${!token_var:-}"
        if [[ -z "$TOKEN_VALUE" ]]; then
            log "Space #$idx: CANNOT RESTART (no token for $token_var)"
            FAILED=$((FAILED + 1))
            continue
        fi

        # Check space status via HF API
        API_RESPONSE=$(curl -s -H "Authorization: Bearer $TOKEN_VALUE" \
            "https://huggingface.co/api/spaces/$repo_id" 2>/dev/null)
        STAGE=$(echo "$API_RESPONSE" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('runtime',{}).get('stage','UNKNOWN'))" 2>/dev/null || echo "UNKNOWN")

        log "Space #$idx: HF API stage=$STAGE - Issuing restart..."
        RESTART_RESULT=$(curl -s -X POST \
            -H "Authorization: Bearer $TOKEN_VALUE" \
            "https://huggingface.co/api/spaces/$repo_id/restart" 2>/dev/null)
        NEW_STAGE=$(echo "$RESTART_RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('stage','UNKNOWN'))" 2>/dev/null || echo "UNKNOWN")
        log "Space #$idx: Restart issued, new stage: $NEW_STAGE"
        RESTARTED=$((RESTARTED + 1))
    fi
done

log "--- Keepalive summary: $HEALTHY/$TOTAL healthy, $RESTARTED restarted, $FAILED failed ---"

# Rotate log file if too large
if [[ -f "$LOG_FILE" ]]; then
    LINE_COUNT=$(wc -l < "$LOG_FILE")
    if [[ "$LINE_COUNT" -gt "$MAX_LOG_LINES" ]]; then
        tail -n 2000 "$LOG_FILE" > "${LOG_FILE}.tmp" && mv "${LOG_FILE}.tmp" "$LOG_FILE"
        log "Log rotated (was $LINE_COUNT lines, kept last 2000)"
    fi
fi

exit 0
