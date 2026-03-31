#!/bin/bash
# ══════════════════════════════════════════════════════════
# Karpathy Scheduler — Cron-triggered REAL iteration loops
# ══════════════════════════════════════════════════════════
# Runs twice daily (4AM + 4PM UTC) via cron.
# Executes real mutate→train→measure→keep loops for NBA + Political.
# ZERO fake research — this trains actual models.
#
# Schedule: 0 4,16 * * *
# ══════════════════════════════════════════════════════════

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
LOG_DIR="$ROOT/logs/karpathy"
DATA_DIR="$ROOT/data/karpathy"

mkdir -p "$LOG_DIR" "$DATA_DIR"

# Source env (for Telegram alerts)
if [ -f "$ROOT/.env.local" ]; then
    set -a
    source "$ROOT/.env.local"
    set +a
fi

DATE=$(date -u +"%Y-%m-%d %H:%M UTC")
echo "═══════════════════════════════════════════════════════"
echo "KARPATHY SCHEDULER — $DATE"
echo "═══════════════════════════════════════════════════════"

RESULTS_FILE="$DATA_DIR/schedule-log.json"
NBA_RESULT="skipped"
POL_RESULT="skipped"
NBA_BRIER=""
POL_BRIER=""

# ── Check memory (skip if < 150MB available) ──
FREE_MB=$(free -m | awk '/Mem:/ {print $7}')
if [ "$FREE_MB" -lt 150 ]; then
    echo "SKIP: Only ${FREE_MB}MB available (need 150MB). VM under pressure."
    echo "{\"ts\":\"$(date -u +%FT%TZ)\",\"status\":\"skipped\",\"reason\":\"low_memory\",\"free_mb\":$FREE_MB}" > "$RESULTS_FILE"
    exit 0
fi

# ── NBA Karpathy Loop (30 iterations, CPU mode) ──
echo ""
echo "── NBA Karpathy Loop (30 iterations) ──"
if python3 "$SCRIPT_DIR/nba_iterate.py" --iterations 30 2>&1 | tail -5; then
    NBA_RESULT="completed"
    # Read best Brier
    if [ -f "$DATA_DIR/nba-best-config.json" ]; then
        NBA_BRIER=$(python3 -c "import json; d=json.load(open('$DATA_DIR/nba-best-config.json')); print(d.get('best_score','?'))" 2>/dev/null || echo "?")
    fi
    echo "NBA: $NBA_RESULT (best Brier: $NBA_BRIER)"
else
    NBA_RESULT="failed"
    echo "NBA: FAILED"
fi

# ── Political Karpathy Loop (30 iterations, CPU mode) ──
echo ""
echo "── Political Karpathy Loop (30 iterations) ──"
if python3 "$SCRIPT_DIR/political_iterate.py" --iterations 30 2>&1 | tail -5; then
    POL_RESULT="completed"
    if [ -f "$DATA_DIR/political-best-config.json" ]; then
        POL_BRIER=$(python3 -c "import json; d=json.load(open('$DATA_DIR/political-best-config.json')); print(d.get('best_score','?'))" 2>/dev/null || echo "?")
    fi
    echo "Political: $POL_RESULT (best Brier: $POL_BRIER)"
else
    POL_RESULT="failed"
    echo "Political: FAILED"
fi

# ── Check Kaggle status (restart if idle) ──
echo ""
echo "── Kaggle kernel check ──"
if [ -f "$ROOT/scripts/kaggle-live-status.py" ]; then
    python3 "$ROOT/scripts/kaggle-live-status.py" 2>/dev/null | head -3 || echo "Kaggle check: unavailable"
fi

# ── Log results ──
cat > "$RESULTS_FILE" <<EOJSON
{
  "ts": "$(date -u +%FT%TZ)",
  "status": "completed",
  "nba": {"result": "$NBA_RESULT", "best_brier": "$NBA_BRIER", "iterations": 30},
  "political": {"result": "$POL_RESULT", "best_brier": "$POL_BRIER", "iterations": 30},
  "free_mb_before": $FREE_MB
}
EOJSON

echo ""
echo "═══════════════════════════════════════════════════════"
echo "DONE — Results saved to $RESULTS_FILE"
echo "═══════════════════════════════════════════════════════"
