#!/bin/bash
# Cross-Repo Optimization Loop — Nomos42 Ecosystem
# Runs every 4h via cron. Checks all projects, pushes improvements.
# Best practice: Karpathy-style continuous improvement across all repos.
set -uo pipefail

LOG="/home/termius/mon-ipad/logs/cross-repo-optimize.log"
mkdir -p "$(dirname "$LOG")"

log() { echo "[$(date -u +%Y-%m-%d\ %H:%M:%S)] $1" >> "$LOG"; }

log "=== CROSS-REPO OPTIMIZATION CYCLE START ==="

# ── Source env ──
source /home/termius/mon-ipad/.env.local 2>/dev/null
CYCLE_START=$(date +%s)

# ── 1. NBA Quant: Check all 6 islands, log best scores ──
log "[NBA] Checking evolution islands..."
for ISLAND in \
  "S10:https://nomos42-nba-quant.hf.space" \
  "S11:https://nomos42-nba-quant-2.hf.space" \
  "S12:https://nomos42-nba-evo-3.hf.space" \
  "S13:https://nomos42-nba-evo-4.hf.space" \
  "S14:https://nomos42-nba-evo-5.hf.space" \
  "S15:https://nomos42-nba-evo-6.hf.space"; do
  NAME="${ISLAND%%:*}"
  URL="${ISLAND#*:}"
  STATUS=$(curl -s --max-time 10 "$URL/api/status" 2>/dev/null)
  BRIER=$(echo "$STATUS" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('best_brier','?'))" 2>/dev/null || echo "DOWN")
  GEN=$(echo "$STATUS" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('generation','?'))" 2>/dev/null || echo "?")
  log "[NBA] $NAME: brier=$BRIER gen=$GEN"
done

# ── 2. RGWA: Check @RGWAbot is alive ──
log "[RGWA] Checking bot..."
RGWA_PID=$(pgrep -f "rgwa_bot.py" 2>/dev/null || echo "")
if [ -n "$RGWA_PID" ]; then
  log "[RGWA] @RGWAbot running (PID $RGWA_PID)"
else
  log "[RGWA] @RGWAbot DOWN — restarting..."
  cd /home/termius/rgwa && bash scripts/telegram/start_bot.sh start >> "$LOG" 2>&1
fi

# ── 3. NBA Bot: Check @Nomos42Bot is alive ──
log "[NBA] Checking bot..."
NBA_PID=$(pgrep -f "nomos42_brain.py" 2>/dev/null || echo "")
if [ -n "$NBA_PID" ]; then
  log "[NBA] @Nomos42Bot running (PID $NBA_PID)"
else
  log "[NBA] @Nomos42Bot DOWN — restarting..."
  cd /home/termius/mon-ipad && bash scripts/telegram/start_bots.sh start >> "$LOG" 2>&1
fi

# ── 4. Git auto-commit data changes across repos ──
log "[GIT] Auto-committing data..."

# mon-ipad: odds, picks, health data
cd /home/termius/mon-ipad
git add data/nba-agent/*.json data/health-status.json 2>/dev/null
git diff --cached --quiet || git commit -m "data: auto-commit $(date -u +%Y-%m-%d-%H%M)" 2>/dev/null
git push origin main 2>/dev/null

# nomos-nba-agent: predictions, results
cd /home/termius/nomos-nba-agent
git add data/results/*.json data/predictions/*.json 2>/dev/null
git diff --cached --quiet || git commit -m "data: auto-commit $(date -u +%Y-%m-%d-%H%M)" 2>/dev/null
git push origin main 2>/dev/null

# ── 5. Dashboard health check ──
log "[DASH] Checking nomosdashboard.vercel.app..."
DASH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "https://nomosdashboard.vercel.app/" 2>/dev/null)
log "[DASH] Status: $DASH_STATUS"

# ── 6. Write health summary ──
SUMMARY=$(cat <<ENDJSON
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "cycle": "cross-repo-optimize",
  "dashboard": "$DASH_STATUS",
  "rgwa_bot": "$([ -n "$RGWA_PID" ] && echo 'UP' || echo 'RESTARTED')",
  "nba_bot": "$([ -n "$NBA_PID" ] && echo 'UP' || echo 'RESTARTED')"
}
ENDJSON
)
echo "$SUMMARY" > /home/termius/mon-ipad/data/cross-repo-health.json

ELAPSED=$(( $(date +%s) - ${CYCLE_START:-$(date +%s)} ))
log "=== CROSS-REPO OPTIMIZATION DONE (${ELAPSED}s) ==="
