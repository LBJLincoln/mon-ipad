#!/usr/bin/env bash
#
# Trading Floor v5 — Daily Cron Runner
# =====================================
# Runs the 200+ agent swarm for today's NBA games.
# Called by cron at game time (daily around 18:00 UTC).
#
# Usage:
#   ./scripts/arena/trading-floor-v5-cron.sh [--dry-run] [--date YYYY-MM-DD]
#
# Designed to be idempotent — safe to run multiple times per day.
# Second run updates predictions if odds changed; skips if no games.

set -euo pipefail

ROOT="/home/termius/mon-ipad"
SCRIPT="${ROOT}/scripts/arena/trading-floor-v5.py"
LOG_DIR="${ROOT}/logs/arena"
LOG_FILE="${LOG_DIR}/trading-floor-v5.log"
PID_FILE="/tmp/trading-floor-v5.pid"

mkdir -p "${LOG_DIR}"

# Load environment variables (including API keys with 'export' prefix)
set -a
source "${ROOT}/.env.local" 2>/dev/null || true
set +a

# Parse args
DRY_RUN=""
DATE_ARG=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN="--dry-run" ;;
        --date) DATE_ARG="--date $2"; shift ;;
        *) ;;
    esac
    shift
done

# Prevent duplicate runs
if [[ -f "${PID_FILE}" ]]; then
    OLD_PID=$(cat "${PID_FILE}")
    if kill -0 "${OLD_PID}" 2>/dev/null; then
        echo "[v5-cron] Already running (pid ${OLD_PID}). Exiting."
        exit 0
    fi
fi
echo $$ > "${PID_FILE}"
trap "rm -f ${PID_FILE}" EXIT

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S UTC')
echo "" >> "${LOG_FILE}"
echo "======================================================================" >> "${LOG_FILE}"
echo "[v5-cron] Starting run at ${TIMESTAMP} ${DRY_RUN}" >> "${LOG_FILE}"
echo "======================================================================" >> "${LOG_FILE}"

# Run v5 for today (or specified date)
python3 "${SCRIPT}" ${DATE_ARG} ${DRY_RUN} 2>&1 | tee -a "${LOG_FILE}"
EXIT_CODE=${PIPESTATUS[0]}

echo "[v5-cron] Finished with exit code ${EXIT_CODE} at $(date '+%H:%M:%S UTC')" >> "${LOG_FILE}"

# Git push results
if [[ ${EXIT_CODE} -eq 0 ]]; then
    cd "${ROOT}"
    git add \
        data/arena/trading-floor-v5-latest.json \
        data/arena/trading-floor-v5-*.json \
        data/arena/agent-states-v5.json \
        data/arena/trading-floor-v5-iteration.json \
        data/arena/predictions-v5/ \
        data/arena/traders-v5/ \
        2>/dev/null || true

    if ! git diff --cached --quiet 2>/dev/null; then
        DATE_STR=$(date '+%Y-%m-%d')
        ITER=$(python3 -c "
import json
try:
    d = json.load(open('data/arena/trading-floor-v5-iteration.json'))
    print(d.get('iteration', 0))
except:
    print(0)
" 2>/dev/null || echo "?")
        git commit -m "data: Trading Floor v5 iter ${ITER} (${DATE_STR} — 200+ agent swarm)" --quiet 2>/dev/null || true
        git push --quiet 2>/dev/null || true
        echo "[v5-cron] Git pushed iteration ${ITER}" >> "${LOG_FILE}"
    else
        echo "[v5-cron] No changes to push" >> "${LOG_FILE}"
    fi
fi

exit ${EXIT_CODE}
