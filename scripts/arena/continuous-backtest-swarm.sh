#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# CONTINUOUS BACKTEST SWARM — NBA + Political
# ═══════════════════════════════════════════════════════════════════════════
# Runs both backtest engines on the FULL historical season every 4h.
# Output feeds the Trading Floor dashboard so the 217 NBA agents +
# 155 political strategies are continuously experimenting on real data,
# not just generating bets for tonight.
#
# Pipeline:
#   1. NBA: scripts/arena/backtest_engine.py --quick --export
#      → data/arena/backtest-results/backtest-<ts>.json
#   2. Political: nomos-political-alpha/scripts/arena/arena_confrontation.py
#      → nomos-political-alpha/data/arena/arena-results.json
#   3. Map both into data/arena/agent-states-v5.json so per-agent stats
#      reflect FULL-SEASON backtest performance, not tonight's noise.
#   4. Commit + push.
# ═══════════════════════════════════════════════════════════════════════════

set -euo pipefail

ROOT="/home/termius/mon-ipad"
POL_ROOT="/home/termius/nomos-political-alpha"
LOG_DIR="${ROOT}/logs/arena"
LOG_FILE="${LOG_DIR}/continuous-backtest.log"
PID_FILE="/tmp/continuous-backtest.pid"

mkdir -p "${LOG_DIR}"

# PID lock
if [[ -f "${PID_FILE}" ]]; then
    OLD_PID=$(cat "${PID_FILE}")
    if kill -0 "${OLD_PID}" 2>/dev/null; then
        echo "[continuous-backtest] Already running (pid ${OLD_PID}). Exit." >> "${LOG_FILE}"
        exit 0
    fi
fi
echo $$ > "${PID_FILE}"
trap "rm -f ${PID_FILE}" EXIT

TS=$(date '+%Y-%m-%d %H:%M:%S UTC')
{
echo ""
echo "============================================================"
echo "[continuous-backtest] Start ${TS}"
echo "============================================================"
} >> "${LOG_FILE}"

# 1. NBA backtest (1081 games × 102 categories × 10 strategies)
echo "[1/3] NBA backtest_engine.py --quick --export" >> "${LOG_FILE}"
timeout 600 python3 "${ROOT}/scripts/arena/backtest_engine.py" --quick --export \
    >> "${LOG_FILE}" 2>&1 || echo "[1/3] NBA backtest exit=$?" >> "${LOG_FILE}"

# 2. Political arena (155 strategies × political markets, elimination tournament)
echo "[2/3] Political arena_confrontation.py" >> "${LOG_FILE}"
timeout 600 python3 "${POL_ROOT}/scripts/arena/arena_confrontation.py" \
    >> "${LOG_FILE}" 2>&1 || echo "[2/3] Political arena exit=$?" >> "${LOG_FILE}"

# 3. Map results into agent-states-v5.json
echo "[3/4] Map backtest results into agent-states-v5.json" >> "${LOG_FILE}"
timeout 60 python3 "${ROOT}/scripts/arena/map-backtest-to-agents.py" \
    >> "${LOG_FILE}" 2>&1 || echo "[3/4] Mapper exit=$?" >> "${LOG_FILE}"

# 4. Build season leaderboard + category registry + $1M projection
echo "[4/4] Season leaderboard + category registry + $1M projection" >> "${LOG_FILE}"
timeout 60 python3 "${ROOT}/scripts/arena/season-leaderboard.py" \
    >> "${LOG_FILE}" 2>&1 || echo "[4/4] Leaderboard exit=$?" >> "${LOG_FILE}"

# 5. Commit + push
cd "${ROOT}"
git add \
    data/arena/backtest-results/ \
    data/arena/agent-states-v5.json \
    data/arena/strategy-truth.json \
    data/arena/season-leaderboard.json \
    data/arena/category-model-registry.json \
    data/arena/one-million-projection.json \
    2>/dev/null || true

if ! git diff --cached --quiet 2>/dev/null; then
    DATE_STR=$(date '+%Y-%m-%d')
    git commit -m "data: continuous backtest swarm ${DATE_STR} (NBA + Political)" --quiet || true
    git push --quiet || true
    echo "[continuous-backtest] Pushed NBA results" >> "${LOG_FILE}"
fi

cd "${POL_ROOT}"
git add data/arena/arena-results.json data/arena/arena-live.json 2>/dev/null || true
if ! git diff --cached --quiet 2>/dev/null; then
    git commit -m "data: continuous backtest swarm $(date '+%Y-%m-%d')" --quiet || true
    git push --quiet || true
    echo "[continuous-backtest] Pushed Political results" >> "${LOG_FILE}"
fi

echo "[continuous-backtest] Done $(date '+%H:%M:%S UTC')" >> "${LOG_FILE}"
