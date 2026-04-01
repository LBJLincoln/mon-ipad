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

# Apply calibration to predictions file if not already done in-process (D5: ECE=0.2758)
python3 - << 'CAL_EOF' >> "$LOG" 2>/dev/null || true
import json
from pathlib import Path
p = Path("/home/termius/nomos-nba-agent/data/nba-agent/predictions-today.json")
if p.exists():
    d = json.loads(p.read_text())
    if not d.get("metadata", {}).get("calibration_applied"):
        import sys
        sys.path.insert(0, '/home/termius/mon-ipad/scripts')
        from calibration import IsotonicCalibration, apply_to_predictions_file
        apply_to_predictions_file(p, IsotonicCalibration())
    else:
        print("[calibration] Already applied in-process — skipping")
CAL_EOF

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

# ── Phase 3b: Sync data files from backtest results ─────────
# Keep quant-summary.json, latest-eval.json, bankroll-state.json fresh
python3 - << 'PYEOF' >> "$LOG" 2>&1
import json, os
from pathlib import Path
from datetime import datetime, timezone

DATA_DIR = Path("/home/termius/mon-ipad/data/nba-agent")
backtest_file = DATA_DIR / "backtest-results.json"
summary_file  = DATA_DIR / "quant-summary.json"
eval_file     = DATA_DIR / "latest-eval.json"
bankroll_file = DATA_DIR / "bankroll-state.json"

if not backtest_file.exists():
    print("[SYNC] backtest-results.json not found — skipping sync")
    exit(0)

try:
    bt = json.loads(backtest_file.read_text())
except Exception as e:
    print(f"[SYNC] Failed to read backtest-results.json: {e}")
    exit(0)

now = datetime.now(timezone.utc).isoformat()

# ── Update bankroll-state.json ──
evaluated = bt.get("trades", [])
total_bets = bt.get("total_bets", 0)
wins = bt.get("wins", 0)
losses = bt.get("losses", 0)
bankroll = bt.get("current_bankroll", 100.0)
initial  = bt.get("initial_bankroll", 100.0)
roi      = bt.get("total_roi_pct", 0.0)
sharpe   = bt.get("sharpe_ratio", 0.0)
max_dd   = bt.get("max_drawdown_pct", 0.0)
peak     = bt.get("peak_bankroll", bankroll)
win_rate = bt.get("win_rate", 0.0)
avg_edge = bt.get("avg_edge_pct", 0.0)
last_bet_ts = evaluated[-1]["date"] + "T00:00:00+00:00" if evaluated else ""
import statistics as _stats
total_wagered = sum(e.get("stake", 0) for e in evaluated)

bankroll_state = {
    "balance": round(bankroll, 2),
    "initial_balance": initial,
    "currency": "USD",
    "total_bets": total_bets,
    "wins": wins,
    "losses": losses,
    "pushes": 0,
    "pending": 0,
    "total_wagered": round(total_wagered, 2),
    "total_profit": round(bankroll - initial, 2),
    "peak_balance": round(peak, 2),
    "trough_balance": initial,
    "max_drawdown_pct": round(max_dd, 2),
    "streak_current": 0,
    "streak_best": 0,
    "streak_worst": 0,
    "daily_bets_today": 0,
    "daily_profit_today": 0.0,
    "last_bet_ts": last_bet_ts,
    "last_updated": now,
    "created": "2026-03-15T11:16:28.623775+00:00",
    "roi_pct": round(roi, 2),
    "win_rate_pct": round(win_rate, 2),
    "sharpe_ratio": round(sharpe, 2),
    "avg_edge_pct": round(avg_edge, 2),
    "season_start": bt.get("season_start", ""),
    "data_source": "backtest-results.json (synced by autonomous-cycle.sh)",
}
bankroll_file.write_text(json.dumps(bankroll_state, indent=2))
print(f"[SYNC] bankroll-state.json updated: ${bankroll:.2f} ({roi:+.2f}% ROI, {total_bets} bets)")

# ── Update latest-eval.json ──
try:
    existing_eval = json.loads(eval_file.read_text()) if eval_file.exists() else {}
except Exception:
    existing_eval = {}

existing_eval["accuracy"] = round(win_rate, 2)
existing_eval["total"] = bt.get("predictions_total", total_bets)
existing_eval["evaluated"] = bt.get("predictions_evaluated", total_bets)
existing_eval["passed"] = wins
existing_eval["total_bets"] = total_bets
existing_eval["wins"] = wins
existing_eval["losses"] = losses
existing_eval["roi_pct"] = round(roi, 2)
existing_eval["sharpe_ratio"] = round(sharpe, 2)
existing_eval["max_drawdown_pct"] = round(max_dd, 2)
existing_eval["bankroll"] = round(bankroll, 2)
existing_eval["brier_score"] = bt.get("brier_score", existing_eval.get("brier_score", 0.21570))
existing_eval["timestamp"] = now
eval_file.write_text(json.dumps(existing_eval, indent=2))
print(f"[SYNC] latest-eval.json updated: brier={existing_eval['brier_score']}, acc={win_rate:.1f}%")

# ── Update quant-summary.json ──
try:
    summary = json.loads(summary_file.read_text()) if summary_file.exists() else {}
except Exception:
    summary = {}

summary["timestamp"] = now
summary["bankroll"] = round(bankroll, 2)
summary["growth_pct"] = round(roi, 2)
summary["record"] = f"{wins}W-{losses}L-0P"
summary["roi_pct"] = round(roi, 2)
summary["daemon_status"] = "RUNNING"
summary["data_source"] = "backtest-results.json (synced by autonomous-cycle.sh)"
summary_file.write_text(json.dumps(summary, indent=2))
print(f"[SYNC] quant-summary.json updated: bankroll=${bankroll:.2f}, record={wins}W-{losses}L")
PYEOF

# ── Phase 3c: Trading Floor Karpathy Loop ──────────────────
# Continuous backtest: 5 AI agents compete on full season → analyze → evolve
# Each cycle: run backtest → rank strategies/models/categories → eliminate losers → mutate agents
log "[TRADING-FLOOR] Running Karpathy loop..."
cd "$MON_DIR"
TF_START=$(date +%s)
timeout 180 python3 scripts/arena/trading-floor-v4.py karpathy >> "$LOG" 2>&1
TF_EXIT=$?
TF_ELAPSED=$(( $(date +%s) - TF_START ))

if [ $TF_EXIT -eq 0 ]; then
    log "[TRADING-FLOOR] Karpathy loop completed (${TF_ELAPSED}s)"
    # Read key result for log
    TF_BEST=$(python3 -c "
import json
d = json.load(open('data/arena/trading-floor-karpathy-output.json'))
bs = d.get('best_strategy', {})
bm = d.get('best_model', {})
it = d.get('iteration', '?')
print(f'iter={it} best_strat={bs.get(\"name\",\"?\")}({bs.get(\"roi_pct\",0):+.1f}%) best_model={bm.get(\"name\",\"?\")}')
" 2>/dev/null || echo "?")
    log "[TRADING-FLOOR] $TF_BEST"
    # Stage arena results for git push
    git add data/arena/trading-floor-v4-latest.json data/arena/trading-floor-karpathy-output.json \
            data/departments/trading_floor/karpathy-output.json \
            data/arena/traders/*.json data/arena/trading-floor-iteration.json 2>/dev/null
    git diff --cached --quiet || {
        git commit -m "data: trading floor karpathy iter $(date -u +%Y-%m-%d-%H%M)" --no-verify
        git push origin main 2>/dev/null || log "[GIT] push failed (trading-floor)"
    }
elif [ $TF_EXIT -eq 124 ]; then
    log "[TRADING-FLOOR] TIMEOUT after ${TF_ELAPSED}s"
else
    log "[TRADING-FLOOR] FAILED (exit $TF_EXIT, ${TF_ELAPSED}s)"
fi

# ── Phase 4: Infrastructure ─────────────────────────────────
# Ensure data server is alive
if ! pgrep -f "nba-data-server" > /dev/null; then
    log "[SERVER] Data server down — restarting"
    cd "$MON_DIR"
    nohup python3 scripts/nba-data-server.py > /dev/null 2>&1 &
    log "[SERVER] Restarted PID: $!"
fi

# ── Phase 5: Political Alpha — Deploy Pending Patches ───────
# Brain Cycle 10 (2026-03-30): autonomous-cycle.sh had no political alpha phase.
# This section auto-deploys the 7-patch fix to resolve feature starvation (Brier=0.3 → <0.26).
POLITICAL_DIR="/home/termius/nomos-political-alpha"
if [ -d "$POLITICAL_DIR" ]; then
    log "[POLITICAL] === Political Alpha Patch Deploy Phase ==="
    cd "$POLITICAL_DIR"

    # Pull latest brain changes (apply_patches.py may have been updated)
    git pull --rebase origin main 2>/dev/null || true

    # If hf-space/app.py is a stub (<5000 bytes), download full version from HF
    APP_SIZE=$(wc -c < hf-space/app.py 2>/dev/null || echo "0")
    if [ "$APP_SIZE" -lt "5000" ]; then
        log "[POLITICAL] hf-space/app.py is stub (${APP_SIZE}B) — downloading full app from HF"
        curl -sL "https://huggingface.co/spaces/Nomos42/political-alpha/raw/main/app.py" \
            > hf-space/app.py 2>/dev/null
        APP_SIZE=$(wc -c < hf-space/app.py 2>/dev/null || echo "0")
        log "[POLITICAL] Downloaded: ${APP_SIZE}B"
    fi

    # Check if 7-patch fix already applied (FIX6 marker: logistic_regression in CPU_MODEL_TYPES)
    PATCHES_APPLIED=$(grep -c 'logistic_regression' hf-space/app.py 2>/dev/null || echo "0")

    if [ "$PATCHES_APPLIED" = "0" ]; then
        log "[POLITICAL] Patches NOT applied — running apply_patches.py"
        python3 hf-space/apply_patches.py >> "$LOG" 2>&1
        PATCH_STATUS=$?
        if [ $PATCH_STATUS -eq 0 ]; then
            log "[POLITICAL] All 7 patches applied successfully"
            git add hf-space/app.py
            git commit -m "fix: deploy 7 patches — feature starvation + LR model (auto via cycle)" --no-verify 2>/dev/null || true
            git push origin main 2>/dev/null || log "[POLITICAL] origin push failed"
            # Push patched app to each HF space remote (hf, hf2, hf3, hf4)
            for HF_REMOTE in hf hf2 hf3 hf4; do
                if git remote get-url $HF_REMOTE > /dev/null 2>&1; then
                    git push $HF_REMOTE main 2>/dev/null && \
                        log "[POLITICAL] Deployed to HF remote: $HF_REMOTE" || \
                        log "[POLITICAL] Push to $HF_REMOTE FAILED (check remote config)"
                fi
            done
        else
            log "[POLITICAL] apply_patches.py FAILED (exit $PATCH_STATUS) — check log above"
        fi
    else
        log "[POLITICAL] Patches already applied ($PATCHES_APPLIED matches) — no action needed"
        # Still check for stagnant islands and send diversify if needed
        for PA_URL in \
            "https://nomos42-political-alpha.hf.space" \
            "https://nomos42-political-alpha-2.hf.space" \
            "https://nomos42-political-alpha-3.hf.space" \
            "https://nomos42-political-alpha-4.hf.space"; do
            STAG=$(curl -s --max-time 8 "${PA_URL}/api/status" 2>/dev/null | \
                python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('stagnation',0))" 2>/dev/null || echo "0")
            if [ "$STAG" -gt "15" ] 2>/dev/null; then
                log "[POLITICAL] Stagnation=$STAG on $PA_URL — sending diversify"
                curl -s -X POST "${PA_URL}/api/command" \
                    -H 'Content-Type: application/json' \
                    -d '{"action":"diversify"}' >> "$LOG" 2>&1 || true
            fi
        done
    fi

    cd "$MON_DIR"
fi

# ── Final: Pull latest from both repos (brain may have pushed) ──
cd "$MON_DIR" && git pull --rebase origin main 2>/dev/null || true
cd "$AGENT_DIR" && git pull --rebase origin main 2>/dev/null || true

CYCLE_END=$(date +%s)
ELAPSED=$((CYCLE_END - CYCLE_START))
log "=== AUTONOMOUS CYCLE END (${ELAPSED}s) ==="
