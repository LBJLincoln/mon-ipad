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

# 2b. Update backtest-latest.json symlink to the newest timestamped file.
#     The dashboard route.ts fetches this path first so it always gets the
#     freshest backtest without needing to know the exact timestamp filename.
LATEST_BACKTEST=$(ls -t "${ROOT}/data/arena/backtest-results"/backtest-2*.json 2>/dev/null | head -1)
if [[ -n "${LATEST_BACKTEST}" ]]; then
    ln -sf "${LATEST_BACKTEST}" "${ROOT}/data/arena/backtest-results/backtest-latest.json"
    echo "[continuous-backtest] backtest-latest.json → $(basename "${LATEST_BACKTEST}")" >> "${LOG_FILE}"
fi

# 3. Map results into agent-states-v5.json
echo "[3/4] Map backtest results into agent-states-v5.json" >> "${LOG_FILE}"
timeout 60 python3 "${ROOT}/scripts/arena/map-backtest-to-agents.py" \
    >> "${LOG_FILE}" 2>&1 || echo "[3/4] Mapper exit=$?" >> "${LOG_FILE}"

# 4. Build season leaderboard + category registry + $1M projection
echo "[4/5] Season leaderboard + category registry + \$1M projection" >> "${LOG_FILE}"
timeout 60 python3 "${ROOT}/scripts/arena/season-leaderboard.py" \
    >> "${LOG_FILE}" 2>&1 || echo "[4/5] Leaderboard exit=$?" >> "${LOG_FILE}"

# 5. Aggregate latest swarm result into the dashboard's full-season-backtest.json
#    (the source the /api/nba/backtest route reads). Was previously stale because
#    full_season_backtest.py needs Supabase predictions which are gone.
echo "[5/5] Aggregate swarm -> data/nba-agent/full-season-backtest.json" >> "${LOG_FILE}"
timeout 30 python3 "${ROOT}/scripts/arena/aggregate_swarm_to_season.py" \
    >> "${LOG_FILE}" 2>&1 || echo "[5/5] Aggregator exit=$?" >> "${LOG_FILE}"

# 6. Run CPCV gate — evaluate all backtest results against scientific gate
#    Updates data/arena/cpcv-gated-strategies.json which the watcher polls.
echo "[6/7] CPCV gate evaluation" >> "${LOG_FILE}"
timeout 120 python3 "${ROOT}/scripts/arena/cpcv_gate.py" \
    >> "${LOG_FILE}" 2>&1 || echo "[6/7] CPCV gate exit=$?" >> "${LOG_FILE}"

# 7. Commit + push
# IMPORTANT: rebase against origin BEFORE committing so we don't lose every push
# to the Apr 11 audit-discovered race condition. Prior symptom in the swarm log:
#   ! [rejected]  main -> main (fetch first)
#   error: failed to push some refs...
# Root cause: this cron fires every 4h while Hermes councils, Karpathy loops,
# research-vault compiles, and manual edits also land commits on main between
# our add and our push. We were LOSING swarm data every run.
cd "${ROOT}"
git stash --quiet 2>/dev/null || true
git pull --rebase --quiet origin main 2>>"${LOG_FILE}" || echo "[continuous-backtest] rebase(mon-ipad) failed" >> "${LOG_FILE}"
git stash pop --quiet 2>/dev/null || true
git add \
    data/arena/backtest-results/ \
    data/arena/backtest-results/backtest-latest.json \
    data/arena/agent-states-v5.json \
    data/arena/strategy-truth.json \
    data/arena/season-leaderboard.json \
    data/arena/category-model-registry.json \
    data/arena/one-million-projection.json \
    data/nba-agent/full-season-backtest.json \
    data/arena/cpcv-gated-strategies.json \
    2>/dev/null || true

if ! git diff --cached --quiet 2>/dev/null; then
    DATE_STR=$(date '+%Y-%m-%d')
    git commit -m "data: continuous backtest swarm ${DATE_STR} (NBA + Political)" --quiet || true
    if git push --quiet 2>>"${LOG_FILE}"; then
        echo "[continuous-backtest] Pushed NBA results" >> "${LOG_FILE}"
    else
        echo "[continuous-backtest] NBA push rejected — one retry after rebase" >> "${LOG_FILE}"
        git stash --quiet 2>/dev/null || true
        git pull --rebase --quiet origin main 2>>"${LOG_FILE}" && { git stash pop --quiet 2>/dev/null || true; } && git push --quiet 2>>"${LOG_FILE}" \
            && echo "[continuous-backtest] Pushed NBA results on retry" >> "${LOG_FILE}" \
            || echo "[continuous-backtest] NBA push still rejected — data on disk, will retry next run" >> "${LOG_FILE}"
    fi
fi

cd "${POL_ROOT}"
git stash --quiet 2>/dev/null || true
git pull --rebase --quiet origin main 2>>"${LOG_FILE}" || echo "[continuous-backtest] rebase(political) failed" >> "${LOG_FILE}"
git stash pop --quiet 2>/dev/null || true
git add data/arena/arena-results.json data/arena/arena-live.json 2>/dev/null || true
if ! git diff --cached --quiet 2>/dev/null; then
    git commit -m "data: continuous backtest swarm $(date '+%Y-%m-%d')" --quiet || true
    if git push --quiet 2>>"${LOG_FILE}"; then
        echo "[continuous-backtest] Pushed Political results" >> "${LOG_FILE}"
    else
        echo "[continuous-backtest] Political push rejected — one retry after rebase" >> "${LOG_FILE}"
        git stash --quiet 2>/dev/null || true
        git pull --rebase --quiet origin main 2>>"${LOG_FILE}" && { git stash pop --quiet 2>/dev/null || true; } && git push --quiet 2>>"${LOG_FILE}" \
            && echo "[continuous-backtest] Pushed Political results on retry" >> "${LOG_FILE}" \
            || echo "[continuous-backtest] Political push still rejected — data on disk, will retry next run" >> "${LOG_FILE}"
    fi
fi

echo "[continuous-backtest] Done $(date '+%H:%M:%S UTC')" >> "${LOG_FILE}"
