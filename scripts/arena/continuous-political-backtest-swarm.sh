#!/usr/bin/env bash
# Continuous Political Backtest Swarm
# ====================================
# Runs scripts/arena/political-trading-floor.py periodically and saves each
# completed run to data/arena/political-backtest-results/ as a CPCV fold.
# This is the political analogue of continuous-backtest-swarm.sh (NBA).
#
# CRON entry (already-installed equivalent for NBA: every 4h):
#   17 */4 * * * /home/termius/mon-ipad/scripts/arena/continuous-political-backtest-swarm.sh
#
# Each invocation:
#   1. Run political-trading-floor.py (full competition, ~15-90s)
#   2. Copy data/arena/political/political-trading-floor-latest.json
#      → data/arena/political-backtest-results/political-backtest-<ts>.json
#   3. Run scripts/arena/political_cpcv_gate.py to refresh the gated leaderboard
#   4. Commit + push the gated file (cron pushes are quiet)

set -uo pipefail

ROOT="/home/termius/mon-ipad"
RESULTS_DIR="$ROOT/data/arena/political-backtest-results"
LATEST="$ROOT/data/arena/political/political-trading-floor-latest.json"
LOG="$ROOT/data/arena/political-backtest-swarm.log"

mkdir -p "$RESULTS_DIR"

ts() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

log "swarm-run start"

cd "$ROOT" || { log "ERR cd $ROOT"; exit 1; }

# Step 1 — run the political competition
if ! python3 scripts/arena/political-trading-floor.py run >>"$LOG" 2>&1; then
  log "ERR political-trading-floor.py exit=$?"
  exit 2
fi

# Step 2 — snapshot the latest run as a CPCV fold
if [[ ! -f "$LATEST" ]]; then
  log "ERR missing $LATEST after run"
  exit 3
fi
SNAPSHOT="$RESULTS_DIR/political-backtest-$(date -u +%Y%m%d-%H%M%S).json"
cp "$LATEST" "$SNAPSHOT"
log "snapshot -> $SNAPSHOT ($(stat -c%s "$SNAPSHOT") bytes)"

# Keep only the last 100 fold files (gate uses last 24 by default)
ls -1t "$RESULTS_DIR"/political-backtest-*.json 2>/dev/null \
  | tail -n +101 | xargs -r rm -f

# Step 3 — refresh the gated leaderboard
if ! python3 scripts/arena/political_cpcv_gate.py >>"$LOG" 2>&1; then
  log "WARN political_cpcv_gate exit=$? (continuing)"
fi

# Step 4 — commit + push (silent on no-op)
if ! git diff --quiet -- data/arena/political-cpcv-gated-strategies.json \
                          data/arena/political-backtest-results/ 2>/dev/null; then
  git add data/arena/political-cpcv-gated-strategies.json \
          data/arena/political-backtest-results/ 2>/dev/null || true
  git commit -m "political-swarm: $(date -u +%Y-%m-%dT%H:%MZ) fold + CPCV gate" \
             >>"$LOG" 2>&1 || true
  git push origin main >>"$LOG" 2>&1 || log "WARN push failed (will retry next run)"
fi

log "swarm-run done"
