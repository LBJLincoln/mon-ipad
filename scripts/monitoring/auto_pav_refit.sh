#!/usr/bin/env bash
# Cycle 14 Tier 1.5 — Auto-PAV refit trigger
#
# Polls data/monitoring/drift-summary.json (written by nba_drift_monitor.py
# every 30 min). When `recalibration_needed: true` (rolling ECE > 0.03 per
# Wilkens 2023 arXiv:2303.06021), trigger the PAV isotonic refit and reset
# the flag idempotently.
#
# This automates what was previously a manual "notice Brier drifted, run
# calibration_fit.py" loop that took days of lag.
#
# Install (cron):
#   */30 * * * * bash /home/termius/mon-ipad/scripts/monitoring/auto_pav_refit.sh >> /home/termius/mon-ipad/logs/auto-pav-refit.log 2>&1
#
# Usage:
#   bash scripts/monitoring/auto_pav_refit.sh          # check & refit if needed
#   bash scripts/monitoring/auto_pav_refit.sh --force  # refit no matter what
#   bash scripts/monitoring/auto_pav_refit.sh --dry    # log what it would do

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "${SCRIPT_DIR}/../.." && pwd)"
SUMMARY="$REPO/data/monitoring/drift-summary.json"
LEDGER="$REPO/data/monitoring/auto-pav-refit-ledger.json"
CALIBRATION_MAP="$REPO/data/nba-agent/calibration-map.json"
LOG_DIR="$REPO/logs"
COOLDOWN_MIN=60  # never refit more than once per hour, even if drift persists

mkdir -p "$LOG_DIR" "$(dirname "$LEDGER")"

ts() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

log() { echo "[$(ts)] $*"; }

force=0
dry=0
for a in "$@"; do
    case "$a" in
        --force) force=1 ;;
        --dry)   dry=1 ;;
    esac
done

# 1. Read the drift summary. If it doesn't exist, nothing to do yet.
if [[ ! -f "$SUMMARY" ]]; then
    log "summary not found yet: $SUMMARY (drift monitor hasn't run)"
    exit 0
fi

recal_needed=$(python3 -c "
import json, sys
try:
    d = json.load(open('$SUMMARY'))
    print('true' if d.get('recalibration_needed') else 'false')
except Exception as e:
    print('false', file=sys.stderr)
    print(f'ERR: {e}', file=sys.stderr)
")

overall_state=$(python3 -c "
import json
try:
    d = json.load(open('$SUMMARY'))
    print(d.get('state', 'UNKNOWN'))
except Exception:
    print('ERROR')
")

ece=$(python3 -c "
import json
try:
    d = json.load(open('$SUMMARY'))
    print(d.get('metrics', {}).get('rolling_ece', 'null'))
except Exception:
    print('null')
")

log "state=$overall_state rolling_ece=$ece recal_needed=$recal_needed"

if [[ "$recal_needed" != "true" && $force -eq 0 ]]; then
    log "no refit needed"
    exit 0
fi

# 2. Cooldown — don't thrash the refit every 30 min if the cron has
#    multiple intervals of drift
if [[ -f "$LEDGER" && $force -eq 0 ]]; then
    last_ts=$(python3 -c "
import json
try:
    l = json.load(open('$LEDGER'))
    print(l.get('last_refit_epoch', 0))
except Exception:
    print(0)
")
    now=$(date -u +%s)
    age=$(( now - last_ts ))
    if [[ $age -lt $((COOLDOWN_MIN * 60)) ]]; then
        log "cooldown: last refit ${age}s ago (< ${COOLDOWN_MIN}min)"
        exit 0
    fi
fi

# 2.5 Idempotency guard — skip if n_games_used hasn't grown since last refit.
#     calibration_fit.py produces identical output on same game pool.
if [[ -f "$CALIBRATION_MAP" && -f "$LEDGER" && $force -eq 0 ]]; then
    current_n=$(python3 -c "
import json
try:
    c = json.load(open('$CALIBRATION_MAP'))
    print(c.get('_meta', {}).get('n_games_used', 0))
except Exception:
    print(0)
")
    last_n=$(python3 -c "
import json
try:
    l = json.load(open('$LEDGER'))
    print(l.get('last_refit_n_games', -1))
except Exception:
    print(-1)
")
    if [[ "$current_n" -eq "$last_n" && "$current_n" -gt 0 ]]; then
        log "IDEMPOTENCY_GUARD: calibration pool still $current_n games (unchanged) — refit would produce identical map, skipping"
        exit 0
    fi
    log "pool: current_n=$current_n last_refit_n=$last_n — will refit"
fi

# 3. Dry-run gate
if [[ $dry -eq 1 ]]; then
    log "DRY-RUN: would trigger python3 scripts/calibration_fit.py"
    exit 0
fi

# 4. Fire the refit
log "FIRING PAV refit (state=$overall_state ece=$ece)"
cd "$REPO"
if python3 scripts/calibration_fit.py >> "$LOG_DIR/auto-pav-refit.log" 2>&1; then
    log "PAV refit OK"
    python3 -c "
import json, time
try:
    c = json.load(open('$CALIBRATION_MAP'))
    n_games = c.get('_meta', {}).get('n_games_used', 0)
except Exception:
    n_games = 0
ledger = {
    'last_refit_epoch': int(time.time()),
    'last_refit_iso': '$(ts)',
    'trigger_state': '$overall_state',
    'trigger_ece': $ece,
    'cooldown_min': $COOLDOWN_MIN,
    'last_refit_n_games': n_games,
}
open('$LEDGER', 'w').write(json.dumps(ledger, indent=2))
"
    # Optional: Telegram ping via existing bot token (no-op if env unset)
    if [[ -n "${TELEGRAM_BOT_TOKEN:-}" && -n "${TELEGRAM_CHAT_ID:-}" ]]; then
        curl -sS -X POST \
            "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d "chat_id=${TELEGRAM_CHAT_ID}" \
            -d "text=🔄 PAV isotonic refit fired | state=$overall_state ece=$ece" \
            > /dev/null || log "telegram send failed (non-fatal)"
    fi
    exit 0
else
    log "PAV refit FAILED — see $LOG_DIR/auto-pav-refit.log"
    exit 1
fi
