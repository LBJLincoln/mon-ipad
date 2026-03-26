#!/bin/bash
# Nomos42 — VM Autonomous Cycle (runs every 1h at :30 via cron)
# Handles execution that requires API keys (.env.local)
# The cloud brain (remote trigger at :00) handles analysis + decisions
# Brain writes recommendations to health-status.json → muscle reads and acts
set -uo pipefail  # No -e: continue on individual failures

LOG="/home/termius/mon-ipad/logs/autonomous-cycle.log"
AGENT_DIR="/home/termius/nomos-nba-agent"
MON_DIR="/home/termius/mon-ipad"
S10_URL="https://nomos42-nba-quant.hf.space"
S11_URL="https://nomos42-nba-quant-2.hf.space"
S12_URL="https://nomos42-nba-evo-3.hf.space"
S13_URL="https://nomos42-nba-evo-4.hf.space"
S14_URL="https://nomos42-nba-evo-5.hf.space"
S15_URL="https://nomos42-nba-evo-6.hf.space"
HEALTH="$MON_DIR/data/health-status.json"

mkdir -p "$(dirname "$LOG")" "$MON_DIR/logs"

log() { echo "[$(date -u +%Y-%m-%d\ %H:%M:%S)] $1" >> "$LOG"; }
CYCLE_START=$(date +%s)

log "=== AUTONOMOUS CYCLE START ==="

cd "$AGENT_DIR"
source .env.local 2>/dev/null

# ── Phase 0: Quick Health Snapshot ───────────────────────────
log "[HEALTH] Checking S10/S11 status..."
S10_STATUS=$(curl -s --max-time 10 "$S10_URL/api/status" 2>/dev/null)
S11_STATUS=$(curl -s --max-time 10 "$S11_URL/api/status" 2>/dev/null)

S10_BRIER=$(echo "$S10_STATUS" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('best_brier','?'))" 2>/dev/null || echo "?")
S10_GEN=$(echo "$S10_STATUS" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('generation','?'))" 2>/dev/null || echo "?")
S10_STAG=$(echo "$S10_STATUS" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('stagnation_count','?'))" 2>/dev/null || echo "?")
S11_QUEUE=$(echo "$S11_STATUS" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('queue_depth', d.get('pending',0)))" 2>/dev/null || echo "?")
S11_ALIVE=$(echo "$S11_STATUS" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','DOWN'))" 2>/dev/null || echo "DOWN")

# S12/S13 quick check
S12_BRIER=$(curl -s --max-time 10 "$S12_URL/api/status" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('best_brier','?'))" 2>/dev/null || echo "?")
S13_BRIER=$(curl -s --max-time 10 "$S13_URL/api/status" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('best_brier','?'))" 2>/dev/null || echo "?")

S14_BRIER=$(curl -s --max-time 10 "$S14_URL/api/status" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('best_brier','?'))" 2>/dev/null || echo "?")
S15_BRIER=$(curl -s --max-time 10 "$S15_URL/api/status" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('best_brier','?'))" 2>/dev/null || echo "?")

log "[HEALTH] S10=$S10_BRIER S11=? S12=$S12_BRIER S13=$S13_BRIER S14=$S14_BRIER S15=$S15_BRIER gen=$S10_GEN stag=$S10_STAG"

# ── Phase 1: Crew Research ───────────────────────────────────
# Research is now handled by the Cloud Brain (Claude Code remote trigger at :00)
# The brain uses 4 Claude Code subagents instead of external LLMs
# Muscle only runs crew as fallback if Google API is working
HOUR=$(date -u +%H)
HOUR_MOD=$((10#$HOUR % 6))

log "[CREW] Research handled by Cloud Brain (Claude Code agents) — skipping local crew"

# Commit crew results to git (so cloud brain can read them)
cd "$AGENT_DIR"
git add data/results/crew-*.json data/results/crew-cycle-latest.json 2>/dev/null
git diff --cached --quiet || {
    git commit -m "data: crew cycle $(date -u +%Y-%m-%d-%H%M)" --no-verify
    git push origin main 2>/dev/null || log "[GIT] push failed (nomos-nba-agent)"
}
log "[CREW] Done + pushed"

# ── Phase 2: Brain Recommendations ──────────────────────────
# Read brain's health-status.json and act on "VM SHOULD RUN" items
if [ -f "$HEALTH" ]; then
    # Check if brain recommends CatBoost experiment submission
    HAS_CATBOOST_REC=$(python3 -c "
import json
with open('$HEALTH') as f: d = json.load(f)
recs = d.get('recommendations', [])
print('yes' if any('CatBoost' in r and 'S11' in r for r in recs) else 'no')
" 2>/dev/null || echo "no")

    # Check if brain recommends a checkpoint
    HAS_CHECKPOINT_REC=$(python3 -c "
import json
with open('$HEALTH') as f: d = json.load(f)
recs = d.get('recommendations', [])
print('yes' if any('CHECKPOINT' in r.upper() for r in recs) else 'no')
" 2>/dev/null || echo "no")

    if [ "$HAS_CATBOOST_REC" = "yes" ] && [ "$S11_ALIVE" != "DOWN" ]; then
        log "[BRAIN-REC] Brain recommends CatBoost experiment — submitting to S11..."
        curl -s -X POST "$S10_URL/api/experiment/submit" \
            -H 'Content-Type: application/json' \
            -d '{"description":"CatBoost auto-submit from muscle cycle","model_type":"catboost","pop_size":30,"generations":8,"target_features":120,"mutation_rate":0.15}' \
            >> "$LOG" 2>&1 || log "[S11] Experiment submission failed"
    fi

    if [ "$HAS_CHECKPOINT_REC" = "yes" ]; then
        log "[BRAIN-REC] Brain recommends checkpoint — saving..."
        curl -s -X POST "$S10_URL/api/checkpoint" >> "$LOG" 2>&1 || log "[S10] Checkpoint failed"
    fi
fi

# ── Phase 3: Daily Predictions (if NBA games today) ─────────
log "[PREDICT] Checking for games today..."
cd "$AGENT_DIR"

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

# Push predictions + any mon-ipad changes
cd "$MON_DIR"
git add data/nba-agent/latest-picks.json 2>/dev/null
git diff --cached --quiet || {
    git commit -m "data: picks ${TODAY}" --no-verify
    git push origin main 2>/dev/null || log "[GIT] push failed (mon-ipad)"
}

# ── Phase 4: Infrastructure ─────────────────────────────────
# Ensure data server is alive
if ! pgrep -f "nba-data-server" > /dev/null; then
    log "[SERVER] Data server down — restarting"
    cd "$MON_DIR"
    nohup python3 scripts/nba-data-server.py > /dev/null 2>&1 &
    log "[SERVER] Restarted PID: $!"
fi

# Pull latest from both repos (brain may have pushed)
cd "$MON_DIR" && git pull --rebase origin main 2>/dev/null || true
cd "$AGENT_DIR" && git pull --rebase origin main 2>/dev/null || true

CYCLE_END=$(date +%s)
ELAPSED=$((CYCLE_END - CYCLE_START))
log "=== AUTONOMOUS CYCLE END (${ELAPSED}s) ==="
