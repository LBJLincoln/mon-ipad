#!/bin/bash
# Run Codex agent for ecosystem monitoring
# Fallback if Claude Code is unavailable
source /home/termius/mon-ipad/.env.local 2>/dev/null
LOG="/home/termius/mon-ipad/logs/agents/codex-$(date +%Y-%m-%d).log"
mkdir -p "$(dirname "$LOG")"

echo "[$(date -u)] Starting Codex monitor..." >> "$LOG"

if command -v npx &>/dev/null && [ -n "$OPENAI_API_KEY" ]; then
    PROMPT="Check all Nomos42 HF spaces health. Curl each /api/status endpoint for: nomos42-nba-quant, nomos42-nba-quant-2, nomos42-nba-evo-3, nomos42-nba-evo-4, nomos42-nba-evo-5, nomos42-nba-evo-6, nomos42-political-alpha, nomos42-political-alpha-2. Report which are UP and which are DOWN. For UP spaces, extract best_brier and generation from the JSON response."
    timeout 120 npx codex --quiet --approval-mode full-auto "$PROMPT" >> "$LOG" 2>&1
    echo "[$(date -u)] Codex monitor complete" >> "$LOG"
else
    echo "[$(date -u)] Codex not available, using curl fallback" >> "$LOG"

    NBA_UP=0
    NBA_DOWN=0
    BEST_BRIER="1.0"
    BEST_SPACE=""

    for SPACE in nomos42-nba-quant nomos42-nba-quant-2 nomos42-nba-evo-3 nomos42-nba-evo-4 nomos42-nba-evo-5 nomos42-nba-evo-6; do
        STATUS=$(curl -sf --max-time 10 "https://$SPACE.hf.space/api/status" 2>/dev/null)
        if [ -n "$STATUS" ]; then
            BRIER=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('best_brier','?'))" 2>/dev/null)
            GEN=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('generation','?'))" 2>/dev/null)
            STAG=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('stagnation','?'))" 2>/dev/null)
            echo "  UP: $SPACE brier=$BRIER gen=$GEN stag=$STAG" >> "$LOG"
            NBA_UP=$((NBA_UP + 1))
            # Track best brier
            if python3 -c "exit(0 if float('$BRIER') < float('$BEST_BRIER') else 1)" 2>/dev/null; then
                BEST_BRIER="$BRIER"
                BEST_SPACE="$SPACE"
            fi
            # Stagnation warning
            if python3 -c "exit(0 if int('$STAG') > 25 else 1)" 2>/dev/null; then
                echo "  WARNING: $SPACE stagnation=$STAG" >> "$LOG"
            fi
        else
            echo "  DOWN: $SPACE" >> "$LOG"
            NBA_DOWN=$((NBA_DOWN + 1))
        fi
    done

    POL_UP=0
    POL_DOWN=0
    for SPACE in nomos42-political-alpha nomos42-political-alpha-2; do
        STATUS=$(curl -sf --max-time 10 "https://$SPACE.hf.space/api/status" 2>/dev/null)
        if [ -n "$STATUS" ]; then
            echo "  UP: $SPACE" >> "$LOG"
            POL_UP=$((POL_UP + 1))
        else
            echo "  DOWN: $SPACE" >> "$LOG"
            POL_DOWN=$((POL_DOWN + 1))
        fi
    done

    echo "" >> "$LOG"
    echo "[$(date -u)] === Codex Monitor Report ===" >> "$LOG"
    echo "  NBA Islands: $NBA_UP/6 UP" >> "$LOG"
    echo "  Political:   $POL_UP/2 UP" >> "$LOG"
    if [ -n "$BEST_SPACE" ]; then
        echo "  Best Brier:  $BEST_BRIER ($BEST_SPACE)" >> "$LOG"
    fi
    echo "[$(date -u)] Curl fallback complete" >> "$LOG"
fi
