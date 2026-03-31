#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# NOMOS42 MULTI-BRAIN — Uses best available AI CLI
# Priority: Claude Code > Codex > Gemini > Rule-based
# Run via cron: 0 */4 * * * /home/termius/mon-ipad/scripts/agents/multi-brain.sh
# ═══════════════════════════════════════════════════════════════

set -uo pipefail
export PATH="$PATH:/home/termius/.local/bin:/home/termius/.npm-global/bin:/usr/local/bin"

MON_DIR="/home/termius/mon-ipad"
LOG="$MON_DIR/logs/agents/multi-brain-$(date +%Y-%m-%d).log"
mkdir -p "$(dirname "$LOG")"

source "$MON_DIR/.env.local" 2>/dev/null

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $1" | tee -a "$LOG"; }

log "═══ MULTI-BRAIN CYCLE START ═══"

# ── Step 1: Quick health check (always runs, no AI needed) ──
log "[HEALTH] Checking all spaces..."
HEALTH_JSON="{"
TOTAL=0; UP=0; STAGNANT=0

for SPACE in nomos42-nba-quant nomos42-nba-quant-2 nomos42-nba-evo-3 nomos42-nba-evo-4 nomos42-nba-evo-5 nomos42-nba-evo-6; do
    TOTAL=$((TOTAL + 1))
    STATUS=$(curl -sf --max-time 10 "https://$SPACE.hf.space/api/status" 2>/dev/null)
    if [ -n "$STATUS" ]; then
        BRIER=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('best_brier','?'))" 2>/dev/null)
        GEN=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('generation','?'))" 2>/dev/null)
        STAG=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('stagnation',0))" 2>/dev/null)
        log "  ✓ $SPACE: brier=$BRIER gen=$GEN stag=$STAG"
        UP=$((UP + 1))
        [ "$STAG" -gt 20 ] 2>/dev/null && STAGNANT=$((STAGNANT + 1))
    else
        log "  ✗ $SPACE: DOWN — pinging..."
        curl -sf "https://$SPACE.hf.space/" > /dev/null 2>&1
    fi
done

log "[HEALTH] $UP/$TOTAL UP, $STAGNANT stagnant"

# ── Step 2: AI Decision (try best available CLI) ──
PROMPT="Nomos42 Brain: $UP/$TOTAL spaces UP, $STAGNANT stagnant. Check logs at $LOG. Run: python3 $MON_DIR/scripts/agents/orchestrator.py"

AI_USED="none"

# Try 1: Claude Code (best, but may be rate-limited)
if command -v claude &>/dev/null; then
    log "[AI] Trying Claude Code..."
    RESULT=$(timeout 120 claude --print "$PROMPT" 2>/dev/null) && AI_USED="claude"
fi

# Try 2: Codex CLI
if [ "$AI_USED" = "none" ] && command -v npx &>/dev/null; then
    log "[AI] Trying Codex..."
    RESULT=$(timeout 120 npx codex --quiet --approval-mode full-auto "$PROMPT" 2>/dev/null) && AI_USED="codex"
fi

# Try 3: Gemini CLI
if [ "$AI_USED" = "none" ] && command -v gemini &>/dev/null; then
    log "[AI] Trying Gemini..."
    RESULT=$(echo "$PROMPT" | timeout 60 gemini 2>/dev/null) && AI_USED="gemini"
fi

# Try 4: Rule-based fallback
if [ "$AI_USED" = "none" ]; then
    log "[AI] All CLIs unavailable, using rule-based..."
    AI_USED="rules"
    # Run orchestrator directly
    python3 "$MON_DIR/scripts/agents/orchestrator.py" >> "$LOG" 2>&1
fi

log "[AI] Used: $AI_USED"

# ── Step 3: Always run infra checks ──
if [ -f "$MON_DIR/scripts/infra-agent.sh" ]; then
    log "[INFRA] Running infra agent..."
    bash "$MON_DIR/scripts/infra-agent.sh" >> "$LOG" 2>&1 || true
fi

# ── Step 4: Alert if critical ──
DOWN=$((TOTAL - UP))
if [ "$DOWN" -gt 2 ]; then
    log "[ALERT] $DOWN spaces DOWN — sending Telegram alert..."
    if [ -n "$TELEGRAM_BOT_TOKEN" ]; then
        curl -sf -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -H "Content-Type: application/json" \
            -d "{\"chat_id\":\"6582544948\",\"text\":\"🧠 Brain Alert: $DOWN/$TOTAL spaces DOWN. AI: $AI_USED. Check logs.\"}" \
            > /dev/null 2>&1
    fi
fi

log "═══ MULTI-BRAIN COMPLETE (AI: $AI_USED, $UP/$TOTAL UP) ═══"
