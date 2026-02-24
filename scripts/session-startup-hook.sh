#!/bin/bash
# =================================================================
# SESSION STARTUP HOOK — Auto-displays state for Claude Code
# =================================================================
# Run at start of every session. Shows state files, staleness,
# priority tasks, and infrastructure status in compact format.
# Last updated: 2026-02-24
# =================================================================

cd /home/termius/mon-ipad 2>/dev/null || exit 1

echo "================================================================"
echo "  MULTI-RAG SESSION STARTUP — $(date -Iseconds)"
echo "================================================================"

# Detect session number from recent logs
PREV_SESSION=$(ls outputs/session-*-log.md 2>/dev/null | sort -V | tail -1 | grep -oP 'session-\K\d+' 2>/dev/null || echo "?")
echo "  Previous session: #$PREV_SESSION"

# State files freshness
echo ""
echo "--- STATE FILES ---"
for f in directives/session-state.md directives/status.md docs/status.json; do
    if [ -f "$f" ]; then
        AGE_HOURS=$(( ( $(date +%s) - $(stat -c %Y "$f") ) / 3600 ))
        if [ $AGE_HOURS -gt 48 ]; then
            echo "  STALE ($AGE_HOURS h) $f"
        else
            echo "  OK    ($AGE_HOURS h) $f"
        fi
    else
        echo "  MISSING $f"
    fi
done

# Emergency handoff check
echo ""
if ls outputs/session-*-emergency-handoff.json 2>/dev/null | tail -1 | grep -q .; then
    HANDOFF=$(ls outputs/session-*-emergency-handoff.json 2>/dev/null | tail -1)
    echo "--- EMERGENCY HANDOFF DETECTED ---"
    echo "  File: $HANDOFF"
    echo "  Read this BEFORE proceeding!"
fi

# Priority tasks from session-state
echo ""
echo "--- NEXT ACTIONS (from session-state.md) ---"
grep -A5 'Prochaine\|Next action\|Priority\|TODO\|BLOCKER' directives/session-state.md 2>/dev/null | head -10 || echo "  (none found)"

# Infrastructure quick check
echo ""
echo "--- INFRASTRUCTURE ---"
echo "  HF Space: $(curl -s -o /dev/null -w '%{http_code}' --max-time 5 https://lbjlincoln-nomos-rag-engine.hf.space/healthz 2>/dev/null || echo 'UNREACHABLE')"
echo "  Codespaces: $(gh codespace list --json name,state --jq 'length' 2>/dev/null || echo '?') total"
echo "  Git: $(git log -1 --format='%h %s' 2>/dev/null)"

# Active eval processes
echo ""
EVAL_PIDS=$(pgrep -f 'run-eval' 2>/dev/null | wc -l)
if [ "$EVAL_PIDS" -gt 0 ]; then
    echo "--- ACTIVE EVALS: $EVAL_PIDS processes ---"
    ps aux | grep 'run-eval' | grep -v grep | awk '{print "  PID " $2 " | " $10 " " $11}' | head -5
else
    echo "--- NO ACTIVE EVALS ---"
fi

# Multi-endpoint config
echo ""
echo "--- ENDPOINT CONFIG ---"
echo "  N8N_HOST:              ${N8N_HOST:-NOT SET}"
echo "  N8N_HOST_STANDARD:     ${N8N_HOST_STANDARD:-fallback to N8N_HOST}"
echo "  N8N_HOST_GRAPH:        ${N8N_HOST_GRAPH:-fallback to N8N_HOST}"
echo "  N8N_HOST_QUANTITATIVE: ${N8N_HOST_QUANTITATIVE:-fallback to N8N_HOST}"
echo "  N8N_HOST_ORCHESTRATOR: ${N8N_HOST_ORCHESTRATOR:-fallback to N8N_HOST}"

echo ""
echo "================================================================"
echo "  STARTUP COMPLETE — Read session-state.md before any action"
echo "================================================================"
