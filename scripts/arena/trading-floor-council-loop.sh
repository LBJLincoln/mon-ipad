#!/usr/bin/env bash
#
# Trading Floor Council Loop — Karpathy + Council Pattern
# =========================================================
# Continuous iteration loop that:
#   1. Runs trading-floor-v4.py karpathy (backtest + analyze + mutate)
#   2. Reads karpathy-output.json and conducts a Council review
#   3. Generates council decisions (mutations, experiments, eliminations)
#   4. Saves structured council output to data/arena/council/
#   5. Git commits + pushes results
#   6. Waits configurable delay, then loops
#
# Usage:
#   ./scripts/arena/trading-floor-council-loop.sh [max_iterations] [delay_seconds]
#
# Defaults: max 100 iterations, 300 second (5 min) delay
#
# Output:
#   data/arena/council/council-iter-{N}.json
#   data/arena/council/council-latest.json
#

set -euo pipefail

# ── PATHS ────────────────────────────────────────────────────────────────────
ROOT="/home/lahargnedebartoli/mon-ipad"
SCRIPT_DIR="${ROOT}/scripts/arena"
TRADING_FLOOR="${SCRIPT_DIR}/trading-floor-v4.py"
KARPATHY_OUTPUT="${ROOT}/data/arena/trading-floor-karpathy-output.json"
ITERATION_FILE="${ROOT}/data/arena/trading-floor-iteration.json"
COUNCIL_DIR="${ROOT}/data/arena/council"
COUNCIL_LATEST="${COUNCIL_DIR}/council-latest.json"

# ── PARAMETERS ───────────────────────────────────────────────────────────────
MAX_ITERATIONS="${1:-100}"
DELAY_SECONDS="${2:-300}"

# ── COLORS ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ── SETUP ────────────────────────────────────────────────────────────────────
mkdir -p "${COUNCIL_DIR}"

log() {
    echo -e "${CYAN}[COUNCIL]${NC} $(date '+%H:%M:%S') $*"
}

log_ok() {
    echo -e "${GREEN}[COUNCIL]${NC} $(date '+%H:%M:%S') $*"
}

log_warn() {
    echo -e "${YELLOW}[COUNCIL]${NC} $(date '+%H:%M:%S') $*"
}

log_err() {
    echo -e "${RED}[COUNCIL]${NC} $(date '+%H:%M:%S') $*"
}

# ── VALIDATE DEPENDENCIES ───────────────────────────────────────────────────
if [[ ! -f "${TRADING_FLOOR}" ]]; then
    log_err "trading-floor-v4.py not found at ${TRADING_FLOOR}"
    exit 1
fi

if ! command -v python3 &>/dev/null; then
    log_err "python3 not found"
    exit 1
fi

if ! command -v jq &>/dev/null; then
    log_warn "jq not found -- installing council analysis as pure Python fallback"
    JQ_AVAILABLE=false
else
    JQ_AVAILABLE=true
fi

# ── TRAP: CLEAN EXIT ────────────────────────────────────────────────────────
cleanup() {
    log "Shutting down council loop (received signal)."
    exit 0
}
trap cleanup SIGINT SIGTERM

# ── COUNCIL ANALYSIS (pure bash + jq OR python fallback) ────────────────────
run_council_analysis() {
    local karpathy_file="$1"
    local council_iter="$2"
    local output_file="${COUNCIL_DIR}/council-iter-${council_iter}.json"

    if [[ ! -f "${karpathy_file}" ]]; then
        log_err "Karpathy output not found: ${karpathy_file}"
        return 1
    fi

    # Use Python for robust JSON analysis -- no jq dependency required
    python3 - "${karpathy_file}" "${output_file}" "${council_iter}" <<'PYTHON_COUNCIL'
import json, sys
from datetime import datetime, timezone

karpathy_file = sys.argv[1]
output_file = sys.argv[2]
council_iter = int(sys.argv[3])

with open(karpathy_file) as f:
    kdata = json.load(f)

# ── Extract strategy rankings ────────────────────────────────────────────
strat_rankings = kdata.get("strategy_rankings", [])
top_strategies = strat_rankings[:3] if len(strat_rankings) >= 3 else strat_rankings
bottom_strategies = strat_rankings[-3:] if len(strat_rankings) >= 3 else strat_rankings

# ── Extract model rankings ───────────────────────────────────────────────
model_rankings = kdata.get("model_rankings", [])

# ── Extract category rankings ────────────────────────────────────────────
cat_rankings = kdata.get("category_rankings", [])
best_categories = cat_rankings[:5] if len(cat_rankings) >= 5 else cat_rankings

# ── Leaderboard analysis ────────────────────────────────────────────────
leaderboard = kdata.get("leaderboard", [])
best_trader = leaderboard[0] if leaderboard else {}
worst_trader = leaderboard[-1] if leaderboard else {}

best_bankroll = best_trader.get("nba_bankroll", 100.0)
best_trader_id = best_trader.get("trader_id", "unknown")
best_roi = best_trader.get("nba_roi_pct", 0.0)

# ── Optimization data ───────────────────────────────────────────────────
opt = kdata.get("optimization", {})
distance_to_1m = opt.get("distance_to_1M_pct", 100.0)
target = opt.get("target", 1000000)

# ── Read previous council output for improvement tracking ────────────────
prev_best = None
try:
    import os
    latest_path = os.path.join(os.path.dirname(output_file), "council-latest.json")
    if os.path.exists(latest_path):
        with open(latest_path) as pf:
            prev_data = json.load(pf)
            prev_best = prev_data.get("metrics", {}).get("best_bankroll", None)
except Exception:
    pass

improvement_since_last = 0.0
if prev_best is not None and prev_best > 0:
    improvement_since_last = round(((best_bankroll - prev_best) / prev_best) * 100, 4)

# ── Generate DECISIONS ──────────────────────────────────────────────────

mutations = []
new_experiments = []
eliminations = []

# Decision 1: Worst traders should adopt winner's strategies
if len(leaderboard) >= 2:
    winner_strats = []
    winner_models = []
    # Find winner's strategies from strategy rankings
    for sr in strat_rankings[:3]:
        traders_using = sr.get("traders_using", [])
        if best_trader_id in traders_using:
            winner_strats.append(sr.get("strategy", ""))
    for mr in model_rankings[:3]:
        traders_using = mr.get("traders_using", [])
        if best_trader_id in traders_using:
            winner_models.append(mr.get("model", ""))

    # Bottom 2 traders adopt top strategies
    for loser in leaderboard[-2:]:
        loser_id = loser.get("trader_id", "unknown")
        if loser_id == best_trader_id:
            continue
        mutations.append({
            "agent": loser_id,
            "action": "adopt_winner_strategies",
            "from_agent": best_trader_id,
            "adopt_strategies": winner_strats[:2] if winner_strats else [s.get("strategy") for s in top_strategies[:2]],
            "adopt_models": winner_models[:2] if winner_models else [m.get("model") for m in model_rankings[:2]],
            "reason": f"{loser_id} (rank {loser.get('rank', '?')}) should learn from {best_trader_id} (rank 1)",
        })

# Decision 2: Test cross-pollination of top strategy with mid-tier models
if top_strategies and len(model_rankings) >= 3:
    best_strat_name = top_strategies[0].get("strategy", "unknown")
    mid_models = [m.get("model") for m in model_rankings[2:5]]
    new_experiments.append({
        "type": "cross_pollination",
        "strategy": best_strat_name,
        "test_with_models": mid_models,
        "hypothesis": f"Top strategy '{best_strat_name}' may perform even better with mid-tier models",
        "priority": 1,
    })

# Decision 3: Test combining top 2 categories
if len(best_categories) >= 2:
    new_experiments.append({
        "type": "category_focus",
        "categories": [c.get("category") for c in best_categories[:2]],
        "expected_win_rate": round(sum(c.get("win_rate_pct", 0) for c in best_categories[:2]) / 2, 1),
        "hypothesis": "Focus bets on top-2 winning categories for higher concentration",
        "priority": 2,
    })

# Decision 4: Identify strategies for elimination consideration
for sr in bottom_strategies:
    roi = sr.get("roi_pct", 0)
    strat_name = sr.get("strategy", "")
    bets = sr.get("bets", 0)
    if roi < -20 and bets >= 10:
        eliminations.append({
            "strategy": strat_name,
            "roi_pct": roi,
            "bets": bets,
            "reason": f"Sustained negative ROI ({roi:+.1f}%) over {bets} bets",
            "action": "eliminate_next_iteration",
        })

# Decision 5: Model promotion for evolution department
if model_rankings:
    best_model = model_rankings[0]
    new_experiments.append({
        "type": "model_promotion",
        "model": best_model.get("model", "unknown"),
        "avg_daily_pnl": best_model.get("avg_daily_pnl", 0),
        "win_rate_pct": best_model.get("win_rate_pct", 0),
        "hypothesis": f"Prioritize {best_model.get('model')} in evolution -- top daily PnL",
        "priority": 1,
    })

# Decision 6: Aggressive scaling if close to target
if distance_to_1m < 50:
    new_experiments.append({
        "type": "aggression_increase",
        "current_distance": distance_to_1m,
        "action": "increase Kelly fraction for top 2 traders",
        "hypothesis": f"Within {distance_to_1m:.1f}% of $1M -- increase position sizing",
        "priority": 1,
    })

# ── Build council output ────────────────────────────────────────────────
council_output = {
    "council_iteration": council_iter,
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "source_iteration": kdata.get("iteration", 0),
    "source_generation": kdata.get("generation", 0),
    "analysis": {
        "top_strategies": [
            {
                "strategy": s.get("strategy", ""),
                "roi_pct": s.get("roi_pct", 0),
                "win_rate_pct": s.get("win_rate_pct", 0),
                "bets": s.get("bets", 0),
                "traders_using": s.get("traders_using", []),
            }
            for s in top_strategies
        ],
        "bottom_strategies": [
            {
                "strategy": s.get("strategy", ""),
                "roi_pct": s.get("roi_pct", 0),
                "win_rate_pct": s.get("win_rate_pct", 0),
                "bets": s.get("bets", 0),
                "traders_using": s.get("traders_using", []),
            }
            for s in bottom_strategies
        ],
        "model_rankings": [
            {
                "model": m.get("model", ""),
                "avg_daily_pnl": m.get("avg_daily_pnl", 0),
                "win_rate_pct": m.get("win_rate_pct", 0),
                "bets": m.get("bets", 0),
            }
            for m in model_rankings
        ],
        "best_categories": [
            {
                "category": c.get("category", ""),
                "win_rate_pct": c.get("win_rate_pct", 0),
                "roi_pct": c.get("roi_pct", 0),
                "bets": c.get("bets", 0),
            }
            for c in best_categories
        ],
        "leaderboard_summary": [
            {
                "rank": t.get("rank", 0),
                "trader_id": t.get("trader_id", ""),
                "nba_bankroll": t.get("nba_bankroll", 0),
                "nba_roi_pct": t.get("nba_roi_pct", 0),
                "nba_sharpe": t.get("nba_sharpe", 0),
            }
            for t in leaderboard
        ],
    },
    "decisions": {
        "mutations": mutations,
        "new_experiments": new_experiments,
        "eliminations": eliminations,
    },
    "metrics": {
        "best_bankroll": round(best_bankroll, 2),
        "best_trader": best_trader_id,
        "best_roi_pct": round(best_roi, 2),
        "distance_to_1m": round(distance_to_1m, 4),
        "improvement_since_last": improvement_since_last,
        "total_traders": len(leaderboard),
        "total_strategies_active": len(strat_rankings),
        "total_eliminations_all_time": (
            len(kdata.get("all_eliminations", {}).get("nba", {}))
            + len(kdata.get("all_eliminations", {}).get("political", {}))
        ),
        "matched_games": kdata.get("matched_games", 0),
    },
}

# Write council output
with open(output_file, "w") as f:
    json.dump(council_output, f, indent=2)

# Also write as council-latest.json
import os
latest_path = os.path.join(os.path.dirname(output_file), "council-latest.json")
with open(latest_path, "w") as f:
    json.dump(council_output, f, indent=2)

# Print status line for the shell
bankroll_str = f"${best_bankroll:,.0f}" if best_bankroll >= 1000 else f"${best_bankroll:.2f}"
gap_pct = distance_to_1m
gen = kdata.get("generation", 0)
src_iter = kdata.get("iteration", 0)

print(f"COUNCIL_STATUS|{council_iter}|{gen}|{bankroll_str}|{best_trader_id}|{best_roi:+.0f}%|{gap_pct:.1f}%|{len(mutations)}|{len(new_experiments)}|{len(eliminations)}")
PYTHON_COUNCIL

    return $?
}

# ── HEADER ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}================================================================${NC}"
echo -e "${BOLD}  TRADING FLOOR — COUNCIL LOOP (Karpathy + Council Pattern)${NC}"
echo -e "${BOLD}================================================================${NC}"
echo -e "  Max iterations: ${MAX_ITERATIONS}"
echo -e "  Delay between:  ${DELAY_SECONDS}s ($(( DELAY_SECONDS / 60 ))m $(( DELAY_SECONDS % 60 ))s)"
echo -e "  Council dir:    ${COUNCIL_DIR}"
echo -e "  Started:        $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo -e "${BOLD}================================================================${NC}"
echo ""

# ── DETERMINE STARTING COUNCIL ITERATION ─────────────────────────────────────
COUNCIL_ITER=1
if [[ -f "${COUNCIL_LATEST}" ]]; then
    PREV_COUNCIL=$(python3 -c "
import json
with open('${COUNCIL_LATEST}') as f:
    print(json.load(f).get('council_iteration', 0))
" 2>/dev/null || echo "0")
    COUNCIL_ITER=$(( PREV_COUNCIL + 1 ))
    log "Resuming from council iteration ${COUNCIL_ITER} (previous: ${PREV_COUNCIL})"
else
    log "Starting fresh council loop from iteration 1"
fi

# ── MAIN LOOP ────────────────────────────────────────────────────────────────
COMPLETED=0
FAILURES=0
MAX_CONSECUTIVE_FAILURES=3
CONSECUTIVE_FAILURES=0

while [[ ${COMPLETED} -lt ${MAX_ITERATIONS} ]]; do
    LOOP_START=$(date +%s)

    echo ""
    echo -e "${BOLD}────────────────────────────────────────────────────────────────${NC}"
    log "Council iteration ${COUNCIL_ITER} / ${MAX_ITERATIONS} max"
    echo -e "${BOLD}────────────────────────────────────────────────────────────────${NC}"

    # ── PHASE 0: atlas-gic Darwinian weight update (Cycle 13) ────────────
    # Updates data/arena/trader-darwin-weights.json from the prior iteration's
    # leaderboard so the upcoming run scales kelly_adj per trader. Top quartile
    # x1.05/iter, bottom quartile x0.95/iter, bounded [0.30, 2.50].
    DARWIN_SCRIPT="${SCRIPT_DIR}/darwin_weights.py"
    if [[ -f "${DARWIN_SCRIPT}" ]]; then
        log "Phase 0: atlas-gic Darwinian weight update..."
        python3 "${DARWIN_SCRIPT}" 2>&1 | while IFS= read -r line; do
            echo "  ${line}"
        done || log_warn "darwin_weights.py exit non-zero (continuing)"
    fi

    # ── PHASE 1: Run Karpathy iteration ──────────────────────────────────
    log "Phase 1: Running trading-floor-v4.py karpathy..."

    KARPATHY_EXIT=0
    python3 "${TRADING_FLOOR}" karpathy 2>&1 | while IFS= read -r line; do
        echo "  ${line}"
    done
    KARPATHY_EXIT=${PIPESTATUS[0]}

    if [[ ${KARPATHY_EXIT} -ne 0 ]]; then
        log_err "Karpathy iteration failed (exit code ${KARPATHY_EXIT})"
        CONSECUTIVE_FAILURES=$(( CONSECUTIVE_FAILURES + 1 ))
        FAILURES=$(( FAILURES + 1 ))
        if [[ ${CONSECUTIVE_FAILURES} -ge ${MAX_CONSECUTIVE_FAILURES} ]]; then
            log_err "Hit ${MAX_CONSECUTIVE_FAILURES} consecutive failures -- aborting loop"
            break
        fi
        log_warn "Waiting ${DELAY_SECONDS}s before retry (failure ${CONSECUTIVE_FAILURES}/${MAX_CONSECUTIVE_FAILURES})..."
        sleep "${DELAY_SECONDS}"
        continue
    fi
    CONSECUTIVE_FAILURES=0

    # ── PHASE 2: Council Analysis ────────────────────────────────────────
    log "Phase 2: Council analyzing karpathy output..."

    COUNCIL_OUTPUT=$(run_council_analysis "${KARPATHY_OUTPUT}" "${COUNCIL_ITER}" 2>&1)
    COUNCIL_EXIT=$?

    if [[ ${COUNCIL_EXIT} -ne 0 ]]; then
        log_err "Council analysis failed: ${COUNCIL_OUTPUT}"
        FAILURES=$(( FAILURES + 1 ))
    else
        # Parse the status line from Python output
        STATUS_LINE=$(echo "${COUNCIL_OUTPUT}" | grep "^COUNCIL_STATUS|" | tail -1)

        if [[ -n "${STATUS_LINE}" ]]; then
            IFS='|' read -r _ C_ITER C_GEN C_BANKROLL C_TRADER C_ROI C_GAP C_MUTATIONS C_EXPERIMENTS C_ELIMS <<< "${STATUS_LINE}"
            echo ""
            echo -e "${GREEN}[COUNCIL]${NC} Iter ${CYAN}${C_ITER}${NC} | Gen ${C_GEN} | Best: ${GREEN}${C_BANKROLL}${NC} (${C_TRADER}) | ROI: ${GREEN}${C_ROI}${NC} | Gap to \$1M: ${YELLOW}${C_GAP}${NC}"
            echo -e "         Mutations: ${C_MUTATIONS} | Experiments: ${C_EXPERIMENTS} | Eliminations: ${C_ELIMS}"
        else
            log_ok "Council analysis complete (iter ${COUNCIL_ITER})"
        fi

        log_ok "Saved: ${COUNCIL_DIR}/council-iter-${COUNCIL_ITER}.json"

        # ── PHASE 2b: Append to audit trail (incremental) ───────────────
        AUDIT_SCRIPT="${SCRIPT_DIR}/audit_trail.py"
        if [[ -f "${AUDIT_SCRIPT}" ]]; then
            python3 "${AUDIT_SCRIPT}" --append "${COUNCIL_ITER}" 2>&1 | while IFS= read -r line; do
                echo "  ${line}"
            done
            if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
                log_ok "Audit trail updated for iteration ${COUNCIL_ITER}"
            else
                log_warn "Audit trail append failed (non-fatal)"
            fi
        fi
    fi

    # ── PHASE 3: Git commit + push ───────────────────────────────────────
    log "Phase 3: Git sync..."

    cd "${ROOT}"

    # Stage arena data files + council output + audit trail
    git add \
        data/arena/trading-floor-karpathy-output.json \
        data/arena/trading-floor-iteration.json \
        data/arena/trading-floor-v4-latest.json \
        data/arena/trader-darwin-weights.json \
        data/arena/traders/ \
        data/arena/proposals/ \
        data/arena/council/ \
        data/arena/audit/ \
        data/departments/trading_floor/ \
        2>/dev/null || true

    # Also stage any dated trading floor files
    git add data/arena/trading-floor-v4-*.json 2>/dev/null || true

    # Check if there are staged changes
    if git diff --cached --quiet 2>/dev/null; then
        log_warn "No changes to commit (iteration may have been a no-op)"
    else
        ITER_NUM=$(python3 -c "
import json
with open('${ITERATION_FILE}') as f:
    d = json.load(f)
    print(d.get('iteration', 0))
" 2>/dev/null || echo "?")

        GEN_NUM=$(python3 -c "
import json
with open('${ITERATION_FILE}') as f:
    d = json.load(f)
    print(d.get('generation', 0))
" 2>/dev/null || echo "?")

        COMMIT_MSG="data: Trading Floor council iter ${COUNCIL_ITER} (tf-iter ${ITER_NUM}, gen ${GEN_NUM})"
        git commit -m "${COMMIT_MSG}" --quiet 2>/dev/null || log_warn "Commit failed (may be empty)"

        # Push (non-blocking, tolerate failure)
        git push --quiet 2>/dev/null &
        PUSH_PID=$!
        # Wait up to 30s for push
        PUSH_TIMEOUT=30
        PUSH_WAITED=0
        while kill -0 "${PUSH_PID}" 2>/dev/null && [[ ${PUSH_WAITED} -lt ${PUSH_TIMEOUT} ]]; do
            sleep 1
            PUSH_WAITED=$(( PUSH_WAITED + 1 ))
        done
        if kill -0 "${PUSH_PID}" 2>/dev/null; then
            kill "${PUSH_PID}" 2>/dev/null || true
            log_warn "Git push timed out after ${PUSH_TIMEOUT}s (will retry next iteration)"
        else
            wait "${PUSH_PID}" 2>/dev/null
            PUSH_EXIT=$?
            if [[ ${PUSH_EXIT} -eq 0 ]]; then
                log_ok "Git push complete"
            else
                log_warn "Git push failed (exit ${PUSH_EXIT}) -- will retry next iteration"
            fi
        fi
    fi

    # ── PHASE 4: Stats + Wait ────────────────────────────────────────────
    LOOP_END=$(date +%s)
    LOOP_DURATION=$(( LOOP_END - LOOP_START ))

    COMPLETED=$(( COMPLETED + 1 ))
    COUNCIL_ITER=$(( COUNCIL_ITER + 1 ))

    echo ""
    log "Iteration took ${LOOP_DURATION}s | Completed: ${COMPLETED}/${MAX_ITERATIONS} | Failures: ${FAILURES}"

    if [[ ${COMPLETED} -lt ${MAX_ITERATIONS} ]]; then
        log "Waiting ${DELAY_SECONDS}s before next iteration..."
        echo -e "  ${CYAN}Next iteration at: $(date -d "+${DELAY_SECONDS} seconds" '+%H:%M:%S %Z' 2>/dev/null || date -v+${DELAY_SECONDS}S '+%H:%M:%S %Z' 2>/dev/null || echo "~$(( DELAY_SECONDS / 60 ))m from now")${NC}"

        # Interruptible sleep (check every 5s so Ctrl+C is responsive)
        SLEPT=0
        while [[ ${SLEPT} -lt ${DELAY_SECONDS} ]]; do
            CHUNK=5
            if [[ $(( DELAY_SECONDS - SLEPT )) -lt ${CHUNK} ]]; then
                CHUNK=$(( DELAY_SECONDS - SLEPT ))
            fi
            sleep "${CHUNK}"
            SLEPT=$(( SLEPT + CHUNK ))
        done
    fi
done

# ── SUMMARY ──────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}================================================================${NC}"
echo -e "${BOLD}  COUNCIL LOOP COMPLETE${NC}"
echo -e "${BOLD}================================================================${NC}"
echo -e "  Iterations completed: ${COMPLETED}"
echo -e "  Failures:             ${FAILURES}"
echo -e "  Council files:        ${COUNCIL_DIR}/council-iter-*.json"
echo -e "  Ended:                $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo -e "${BOLD}================================================================${NC}"
echo ""

exit 0
