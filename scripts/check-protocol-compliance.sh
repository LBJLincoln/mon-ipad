#!/bin/bash
# =================================================================
# PROTOCOL COMPLIANCE CHECKER — Validates CLAUDE.md rules
# =================================================================
# Checks: commit frequency, staleness, credentials safety,
# session-state freshness, and running processes.
# Exit 0 = all OK, Exit 1 = violations found.
# Last updated: 2026-02-24
# =================================================================

cd /home/termius/mon-ipad 2>/dev/null || exit 1

VIOLATIONS=0

echo "=== PROTOCOL COMPLIANCE CHECK — $(date -Iseconds) ==="
echo ""

# Rule 5: ZERO credentials in git
echo "[Rule 5] Checking for credentials in staged files..."
if git diff --cached 2>/dev/null | grep -iE 'sk-or-|pcsk_|jV_zGdx|sbp_|hf_|jina_|ghp_' | head -3; then
    echo "  VIOLATION: Potential credentials in staged changes!"
    VIOLATIONS=$((VIOLATIONS + 1))
else
    echo "  OK"
fi

# Rule 9: Commit frequency (every 15-20 min)
echo ""
echo "[Rule 9] Checking commit frequency..."
if git diff --quiet && git diff --cached --quiet 2>/dev/null; then
    echo "  OK (no uncommitted changes)"
else
    LAST_COMMIT_TS=$(git log -1 --format=%ct 2>/dev/null || echo 0)
    NOW_TS=$(date +%s)
    AGE_MIN=$(( (NOW_TS - LAST_COMMIT_TS) / 60 ))
    if [ "$AGE_MIN" -gt 20 ]; then
        echo "  VIOLATION: ${AGE_MIN}min since last commit (>20min) with uncommitted changes"
        git status --short | head -5
        VIOLATIONS=$((VIOLATIONS + 1))
    else
        echo "  OK (${AGE_MIN}min since last commit)"
    fi
fi

# Rule 10: session-state.md freshness
echo ""
echo "[Rule 10] Checking session-state.md freshness..."
if [ -f "directives/session-state.md" ]; then
    SS_AGE_HOURS=$(( ( $(date +%s) - $(stat -c %Y "directives/session-state.md") ) / 3600 ))
    if [ "$SS_AGE_HOURS" -gt 2 ]; then
        echo "  WARNING: session-state.md is ${SS_AGE_HOURS}h old (should update after each milestone)"
    else
        echo "  OK (${SS_AGE_HOURS}h old)"
    fi
else
    echo "  VIOLATION: session-state.md does not exist!"
    VIOLATIONS=$((VIOLATIONS + 1))
fi

# Rule 14: VM = pilotage ONLY (no n8n, no Docker)
echo ""
echo "[Rule 14] Checking VM is pilotage-only..."
if docker ps 2>/dev/null | grep -q n8n; then
    echo "  VIOLATION: n8n Docker container running on VM!"
    VIOLATIONS=$((VIOLATIONS + 1))
else
    echo "  OK (no n8n on VM)"
fi

# Anti-staleness: check all directive files
echo ""
echo "[Staleness] Checking directive files..."
STALE_COUNT=0
for f in directives/session-state.md directives/status.md docs/executive-summary.md technicals/debug/knowledge-base.md; do
    if [ -f "$f" ]; then
        AGE_HOURS=$(( ( $(date +%s) - $(stat -c %Y "$f") ) / 3600 ))
        if [ "$AGE_HOURS" -gt 48 ]; then
            echo "  STALE: $f (${AGE_HOURS}h)"
            STALE_COUNT=$((STALE_COUNT + 1))
        fi
    fi
done
if [ "$STALE_COUNT" -eq 0 ]; then
    echo "  OK (all directives fresh)"
else
    echo "  $STALE_COUNT stale files found"
fi

# Workflow JSON integrity: no generic OPENROUTER_API_KEY in core pipelines
echo ""
echo "[Key Rotation] Checking workflow JSONs..."
GENERIC_COUNT=$(grep -l 'OPENROUTER_API_KEY' n8n/live/standard.json n8n/live/graph.json n8n/live/quantitative.json n8n/live/orchestrator.json 2>/dev/null | wc -l)
if [ "$GENERIC_COUNT" -gt 0 ]; then
    echo "  VIOLATION: $GENERIC_COUNT core pipeline(s) still use generic OPENROUTER_API_KEY"
    VIOLATIONS=$((VIOLATIONS + 1))
else
    echo "  OK (all core pipelines use per-pipeline keys)"
fi

# File count check
echo ""
echo "[Cleanup] Checking tracked file count..."
FILE_COUNT=$(git ls-files | wc -l)
if [ "$FILE_COUNT" -gt 120 ]; then
    echo "  WARNING: $FILE_COUNT tracked files (target: <80)"
else
    echo "  OK ($FILE_COUNT tracked files)"
fi

# Summary
echo ""
echo "=== RESULT: $VIOLATIONS violation(s) found ==="
if [ "$VIOLATIONS" -gt 0 ]; then
    echo "Fix violations before proceeding."
    exit 1
else
    echo "All protocol checks passed."
    exit 0
fi
