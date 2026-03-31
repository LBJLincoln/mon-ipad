#!/bin/bash
# Department: INFRA — Karpathy Loop
# Pattern: health check all systems → detect issues → auto-fix → verify restoration
# Metric: uptime_pct, restart_count, response_time_ms
set -euo pipefail
DEPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$(dirname "$(dirname "$DEPT_DIR")")")"

INFRA_FILE="$ROOT/data/infra-status.json"
HEALTH_FILE="$ROOT/data/agent-health.json"
UPTIME_PCT=null
RESTART_COUNT=0

if [[ -f "$INFRA_FILE" ]]; then
    UPTIME_PCT=$(python3 -c "import json; d=json.load(open('$INFRA_FILE')); print(d.get('uptime_pct', 'null'))" 2>/dev/null || echo null)
fi

if [[ -f "$HEALTH_FILE" ]]; then
    RESTART_COUNT=$(python3 -c "import json; d=json.load(open('$HEALTH_FILE')); print(d.get('restart_count', 0))" 2>/dev/null || echo 0)
fi

# Quick HF spaces check (non-blocking, 3s timeout per space)
SPACES_UP=0
SPACES_TOTAL=6
for SPACE_URL in \
    "https://nomos42-nba-quant.hf.space/api/status" \
    "https://nomos42-nba-quant-2.hf.space/api/status"; do
    if curl -sf --max-time 3 "$SPACE_URL" > /dev/null 2>&1; then
        SPACES_UP=$((SPACES_UP + 1))
    fi
done

echo "{\"status\":\"placeholder\",\"department\":\"infra\",\"metric\":\"uptime_pct\",\"uptime_pct\":$UPTIME_PCT,\"restart_count\":$RESTART_COUNT,\"spaces_up\":$SPACES_UP,\"spaces_total\":$SPACES_TOTAL,\"improved\":false}"
