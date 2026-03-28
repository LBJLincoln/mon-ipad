#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# NOMOS42 AGENT SWARM — Consolidated Cron Orchestrator
# Replaces all individual crons with a single intelligent system
# ═══════════════════════════════════════════════════════════════

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MON_DIR="/home/termius/mon-ipad"
NBA_DIR="/home/termius/nomos-nba-agent"
LOG_DIR="$MON_DIR/logs/agents"
mkdir -p "$LOG_DIR"

HOUR=$(date +%H)
MINUTE=$(date +%M)
DOW=$(date +%u)  # 1=Monday, 7=Sunday
TODAY=$(date +%Y-%m-%d)

log() { echo "[$(date '+%H:%M:%S')] $1" | tee -a "$LOG_DIR/orchestrator-$TODAY.log"; }

log "═══ AGENT SWARM — Hour $HOUR:$MINUTE ═══"

# ─── ALWAYS (every run, */30) ───────────────────────────────────
# 1. Keepalive all 6 HF Spaces
log "[KEEPALIVE] Pinging 6 HF islands..."
for space in nomos42-nba-quant nomos42-nba-quant-2 nomos42-nba-evo-3 nomos42-nba-evo-4 nomos42-nba-evo-5 nomos42-nba-evo-6; do
    curl -sf "https://$space.hf.space/" > /dev/null 2>&1 && log "  $space: OK" || log "  $space: DOWN (pinged)"
done

# 2. Data server check
if ! curl -sf http://localhost:8080/backtest-results.json > /dev/null 2>&1; then
    log "[DATA SERVER] DOWN — restarting..."
    cd "$MON_DIR/data" && python3 -m http.server 8080 &
    sleep 2
fi

# ─── EVERY 2 HOURS (:00) ───────────────────────────────────────
if [ "$MINUTE" -lt 30 ] && [ $((HOUR % 2)) -eq 0 ]; then
    # 3. Orchestrator health check
    log "[ORCHESTRATOR] Full health check..."
    python3 "$SCRIPT_DIR/orchestrator.py" >> "$LOG_DIR/orchestrator-$TODAY.log" 2>&1

    # 4. Dashboard sync
    log "[DASHBOARD SYNC] Updating data files..."
    if [ -f "$MON_DIR/scripts/autonomous-cycle.sh" ]; then
        bash "$MON_DIR/scripts/autonomous-cycle.sh" >> "$LOG_DIR/autonomous-$TODAY.log" 2>&1 || true
    fi
fi

# ─── EVERY 4 HOURS (:30) ──────────────────────────────────────
if [ "$MINUTE" -ge 30 ] && [ $((HOUR % 4)) -eq 0 ]; then
    # 5. Prediction cycle (if NBA games today)
    log "[PREDICTIONS] Checking for NBA games..."
    if [ -f "$NBA_DIR/predict_today.py" ]; then
        cd "$NBA_DIR"
        python3 predict_today.py --date "$TODAY" >> "$LOG_DIR/predictions-$TODAY.log" 2>&1 || log "  No games or prediction failed"
    fi
fi

# ─── DAILY 10:00 UTC ──────────────────────────────────────────
if [ "$HOUR" -eq 10 ] && [ "$MINUTE" -lt 30 ]; then
    # 6. Results evaluator
    log "[EVALUATOR] Scoring yesterday's predictions..."
    cd "$MON_DIR"
    export $(grep -v '^#' .env.local | grep DATABASE_URL | xargs 2>/dev/null) || true
    python3 scripts/evaluate_predictions.py >> "$LOG_DIR/evaluator-$TODAY.log" 2>&1 || true

    # 7. Data leakage tests
    log "[TESTS] Running data leakage suite..."
    python3 scripts/agents/test_data_leakage.py >> "$LOG_DIR/tests-$TODAY.log" 2>&1 || true

    # 8. Betting agent (game days only)
    log "[BETTING] Running portfolio optimizer..."
    python3 scripts/betting_agent.py --strategy portfolio_kelly --compare-all >> "$LOG_DIR/betting-$TODAY.log" 2>&1 || true
fi

# ─── HALFTIME RE-SCORE (every 2 min during game hours: 23-06 UTC) ──
# Only runs from separate cron: */2 23-23,0-5 * * * (see below)
# Integrated via: */2 23-23,0-5 * * * python3 /home/termius/mon-ipad/scripts/halftime_rescore.py --live
# The --live flag handles its own polling loop, so cron just ensures it starts.

# ─── DAILY 12:00 + 18:00 UTC ─────────────────────────────────
if [ "$HOUR" -eq 12 ] || [ "$HOUR" -eq 18 ]; then
    # 9. Odds fetcher
    log "[ODDS] Fetching live odds..."
    if [ -f "$MON_DIR/scripts/nba-daily-odds.py" ]; then
        python3 "$MON_DIR/scripts/nba-daily-odds.py" >> "$LOG_DIR/odds-$TODAY.log" 2>&1 || true
    fi
fi

# ─── WEEKLY (Monday 06:00) ────────────────────────────────────
if [ "$DOW" -eq 1 ] && [ "$HOUR" -eq 6 ] && [ "$MINUTE" -lt 30 ]; then
    # 10. Performance analyst
    log "[ANALYST] Weekly performance review..."
    # TODO: Implement weekly_analyst.py

    # 11. Kaggle kernel health check + relaunch if needed
    log "[KAGGLE] Checking kernel status..."
    kaggle kernels status alexismoret6/nba-karpathy-loop 2>&1 | tee -a "$LOG_DIR/kaggle-$TODAY.log" || true
    kaggle kernels status alexismoret6/nba-season-backtest 2>&1 | tee -a "$LOG_DIR/kaggle-$TODAY.log" || true
fi

# ─── GIT AUTO-COMMIT (daily 23:00) ───────────────────────────
if [ "$HOUR" -eq 23 ] && [ "$MINUTE" -lt 30 ]; then
    log "[GIT] Auto-committing data updates..."
    cd "$MON_DIR"
    git add data/nba-agent/*.json data/nba-agent/halftime-archive/*.json data/agent-health.json 2>/dev/null || true
    git diff --cached --quiet || git commit -m "data: auto-update $(date +%Y-%m-%d)" 2>/dev/null || true
fi

log "═══ AGENT SWARM COMPLETE ═══"
