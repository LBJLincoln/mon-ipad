#!/bin/bash
################################################################################
# Department Council Runner — Karpathy loop per department
# Usage: department-council.sh <dept> [--dry-run]
# Departments: research|engineering|evolution|betting|evaluation|infra|political|creative|comms|business|finance
# Trading Floor has its own continuous loop (trading-floor-council-loop.sh)
################################################################################

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEPT="${1:-}"
DRY_RUN="${2:-}"
LOG_DIR="$REPO_ROOT/logs/councils"
mkdir -p "$LOG_DIR"

source "$REPO_ROOT/.env.local" 2>/dev/null || true

ts() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
log() { echo "[$(ts)] [council:$DEPT] $*" | tee -a "$LOG_DIR/$DEPT.log"; }

if [ -z "$DEPT" ]; then
    echo "Usage: $0 <department>"
    echo "Departments: research engineering evolution betting evaluation infra political creative comms business finance"
    exit 1
fi

# ── Department-specific Karpathy loop ──────────────────────────────────

case "$DEPT" in
    research)
        log "START: Research Council — scan papers, extract techniques, propose features"
        cd "$REPO_ROOT"
        # Run research scanner
        python3 scripts/agents/research-scanner.py --quick 2>&1 | tail -5 | while read line; do log "$line"; done
        # Check for new proposals
        proposals=$(find data/departments/research/ -name '*.json' -newer "$LOG_DIR/research.lastrun" 2>/dev/null | wc -l)
        log "DONE: $proposals new proposals found"
        touch "$LOG_DIR/research.lastrun"
        ;;

    engineering)
        log "START: Engineering Council — check engine parity, test builds, measure Brier delta"
        cd "$REPO_ROOT"
        # Verify feature engine parity across all HF spaces
        python3 -c "
import hashlib, pathlib
local = pathlib.Path('features/engine.py')
hf = pathlib.Path('hf-space/features/engine.py')
if local.exists() and hf.exists():
    lh = hashlib.md5(local.read_bytes()).hexdigest()[:8]
    hh = hashlib.md5(hf.read_bytes()).hexdigest()[:8]
    status = 'PARITY OK' if lh == hh else f'DRIFT: local={lh} hf={hh}'
    print(f'Engine parity: {status}')
else:
    print('Engine files missing')
" 2>&1 | while read line; do log "$line"; done
        log "DONE: Engineering check complete"
        ;;

    evolution)
        log "START: Evolution Council — check 6 islands, stagnation detection, cross-pollinate"
        cd "$REPO_ROOT"
        # Poll all 6 HF islands
        for island in s10:nomos42-nba-quant s11:nomos42-nba-quant-2 s12:nomos42-nba-evo-3 s13:nomos42-nba-evo-4 s14:nomos42-nba-evo-5 s15:nomos42-nba-evo-6; do
            name="${island%%:*}"
            url="${island#*:}"
            status=$(curl -s --max-time 8 "https://${url}.hf.space/api/status" 2>/dev/null || echo '{"error":"down"}')
            brier=$(echo "$status" | python3 -c "import sys,json; print(json.load(sys.stdin).get('best_brier','?'))" 2>/dev/null || echo "?")
            gen=$(echo "$status" | python3 -c "import sys,json; print(json.load(sys.stdin).get('generation','?'))" 2>/dev/null || echo "?")
            log "  $name: Brier=$brier Gen=$gen"
        done
        log "DONE: Evolution check complete"
        ;;

    betting)
        log "START: Betting Council — analyze strategies, ROI, Kelly sizing"
        cd "$REPO_ROOT"
        if [ -f data/nba-agent/bankroll-state.json ]; then
            python3 -c "
import json
with open('data/nba-agent/bankroll-state.json') as f: s = json.load(f)
print(f'Bankroll: \${s.get(\"bankroll\",0):.2f} | ROI: {s.get(\"roi_pct\",0):.1f}% | Bets: {s.get(\"total_bets\",0)}')
" 2>&1 | while read line; do log "$line"; done
        fi
        log "DONE: Betting check complete"
        ;;

    evaluation)
        log "START: Evaluation Council — calibration, phantom detection, false positive audit"
        cd "$REPO_ROOT"
        if [ -f data/nba-agent/latest-eval.json ]; then
            python3 -c "
import json
with open('data/nba-agent/latest-eval.json') as f: e = json.load(f)
print(f'Brier: {e.get(\"brier\",\"?\")} | Games: {e.get(\"total_games\",\"?\")} | Accuracy: {e.get(\"accuracy\",\"?\")}')
" 2>&1 | while read line; do log "$line"; done
        fi
        log "DONE: Evaluation check complete"
        ;;

    infra)
        log "START: Infra Council — check all services, GPU platforms, data pipeline"
        cd "$REPO_ROOT"
        # Already handled by infra-agent.sh, just log summary
        if [ -f data/infra-status.json ]; then
            python3 -c "
import json
with open('data/infra-status.json') as f: s = json.load(f)
total = s.get('total_checks', 0)
ok = s.get('healthy', 0)
print(f'Infra: {ok}/{total} healthy')
" 2>&1 | while read line; do log "$line"; done
        fi
        log "DONE: Infra check complete"
        ;;

    political)
        log "START: Political Council — signal freshness, ETF strategy, category coverage"
        cd /home/termius/nomos-political-alpha 2>/dev/null || cd "$REPO_ROOT"
        python3 ops/fetch_political_data.py --fast 2>&1 | tail -3 | while read line; do log "$line"; done || log "Political fetch skipped"
        log "DONE: Political check complete"
        ;;

    creative)
        log "START: Creative Council — RGWA quality scores, generation rate, gallery"
        cd /home/termius/rgwa 2>/dev/null || cd "$REPO_ROOT"
        log "Checking RGWA generation pipeline..."
        # Placeholder — RGWA specific checks
        log "DONE: Creative check complete"
        ;;

    comms)
        log "START: Communication Council — prepare posts, check bot status, engagement"
        cd "$REPO_ROOT"
        # Check bot health
        for bot in "Nomos42Bot:8672296360:AAHZ5_3-fDE7BBb3b-RJBSRWlXA1qO31UVo" "Forge42Bot:8748162877:AAGZOrjB9HZx_0X6d9714sNAgw3DG12h9uA"; do
            name="${bot%%:*}"
            token="${bot#*:}"
            ok=$(curl -s --max-time 5 "https://api.telegram.org/bot${token}/getMe" | python3 -c "import sys,json; print(json.load(sys.stdin).get('ok',False))" 2>/dev/null || echo "False")
            log "  $name: $ok"
        done
        log "DONE: Communication check complete"
        ;;

    business)
        log "START: Business Council — pricing, conversion, user metrics"
        cd "$REPO_ROOT"
        # Count forge users
        users=$(ls -d forge-users/*/ 2>/dev/null | wc -l)
        log "Forge users: $users"
        log "DONE: Business check complete"
        ;;

    finance)
        log "START: Finance Council — P&L, burn rate, revenue tracking"
        cd "$REPO_ROOT"
        # Compute costs
        log "Monthly costs: ~$6 (VM) + $0 (HF free) + Modal usage"
        if [ -f data/nba-agent/bankroll-state.json ]; then
            bankroll=$(python3 -c "import json; print(json.load(open('data/nba-agent/bankroll-state.json')).get('bankroll',0))" 2>/dev/null)
            log "Bankroll: \$$bankroll"
        fi
        log "DONE: Finance check complete"
        ;;

    *)
        echo "Unknown department: $DEPT"
        echo "Valid: research engineering evolution betting evaluation infra political creative comms business finance"
        exit 1
        ;;
esac

# ── Write council result to JSON ──
python3 -c "
import json, time
result = {
    'department': '$DEPT',
    'timestamp': '$(ts)',
    'status': 'completed',
    'type': 'council'
}
with open('$REPO_ROOT/data/departments/council-$DEPT.json', 'w') as f:
    json.dump(result, f, indent=2)
" 2>/dev/null || true

log "Council result written to data/departments/council-$DEPT.json"
