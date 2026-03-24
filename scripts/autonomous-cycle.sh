#!/bin/bash
# Nomos42 — VM Autonomous Cycle (runs every 4h via cron)
# Handles execution that requires API keys (.env.local)
# The cloud brain (remote trigger) handles analysis + decisions
set -euo pipefail

LOG="/home/termius/mon-ipad/logs/autonomous-cycle.log"
AGENT_DIR="/home/termius/nomos-nba-agent"
MON_DIR="/home/termius/mon-ipad"

mkdir -p "$(dirname "$LOG")"

log() { echo "[$(date -u +%Y-%m-%d\ %H:%M:%S)] $1" >> "$LOG"; }

log "=== AUTONOMOUS CYCLE START ==="

# ── Phase 1: Crew Research Cycle ─────────────────────────────
log "[CREW] Starting 4-agent research cycle..."
cd "$AGENT_DIR"
source .env.local 2>/dev/null

timeout 600 python3 agents/nba_crew.py --once >> "$LOG" 2>&1 || log "[CREW] FAILED (timeout or error)"

# Commit crew results to git (so cloud brain can read them)
cd "$AGENT_DIR"
git add data/results/crew-*.json data/results/crew-cycle-latest.json 2>/dev/null
git diff --cached --quiet || {
    git commit -m "data: crew cycle $(date -u +%Y-%m-%d-%H%M)" --no-verify
    git push origin main 2>/dev/null || log "[GIT] push failed (nomos-nba-agent)"
}
log "[CREW] Done + pushed"

# ── Phase 2: Daily Predictions (if NBA games today) ─────────
log "[PREDICT] Checking for games today..."
cd "$AGENT_DIR"
source .env.local 2>/dev/null

# Fetch fresh odds
python3 ops/fetch-odds.py --once >> "$LOG" 2>&1 || log "[ODDS] fetch failed"

# Run predictions
timeout 300 python3 predict_today.py >> "$LOG" 2>&1 || log "[PREDICT] FAILED"

# Copy to data server
TODAY=$(date +%Y-%m-%d)
if [ -f "data/predictions/predictions-${TODAY}.json" ]; then
    cp "data/predictions/predictions-${TODAY}.json" "$MON_DIR/data/nba-agent/latest-picks.json"
    log "[PREDICT] Picks copied for Vercel"
else
    log "[PREDICT] No predictions file for today (no games?)"
fi

# Push predictions
cd "$MON_DIR"
git add data/nba-agent/latest-picks.json 2>/dev/null
git diff --cached --quiet || {
    git commit -m "data: picks ${TODAY}" --no-verify
    git push origin main 2>/dev/null || log "[GIT] push failed (mon-ipad)"
}

# ── Phase 3: Ensure data server is alive ─────────────────────
if ! pgrep -f "nba-data-server" > /dev/null; then
    log "[SERVER] Data server down — restarting"
    cd "$MON_DIR"
    nohup python3 scripts/nba-data-server.py > /dev/null 2>&1 &
    log "[SERVER] Restarted PID: $!"
fi

log "=== AUTONOMOUS CYCLE END ==="
