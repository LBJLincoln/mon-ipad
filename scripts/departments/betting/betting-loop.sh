#!/bin/bash
# Department: BETTING — Karpathy Loop
# Pattern: tweak strategy → backtest on historical → measure ROI/Sharpe → keep/revert
# Metric: roi_delta, sharpe_ratio, kelly_edge, win_rate
set -euo pipefail
DEPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$(dirname "$(dirname "$DEPT_DIR")")")"

BANKROLL_FILE="$ROOT/data/nba-agent/bankroll-state.json"
CURRENT_ROI=null
CURRENT_SHARPE=null
WIN_RATE=null

if [[ -f "$BANKROLL_FILE" ]]; then
    CURRENT_ROI=$(python3 -c "import json; d=json.load(open('$BANKROLL_FILE')); print(d.get('roi_pct', 'null'))" 2>/dev/null || echo null)
    CURRENT_SHARPE=$(python3 -c "import json; d=json.load(open('$BANKROLL_FILE')); print(d.get('sharpe', 'null'))" 2>/dev/null || echo null)
    WIN_RATE=$(python3 -c "import json; d=json.load(open('$BANKROLL_FILE')); wins=d.get('wins',0); losses=d.get('losses',0); total=wins+losses; print(round(wins/total,4) if total>0 else 'null')" 2>/dev/null || echo null)
fi

echo "{\"status\":\"placeholder\",\"department\":\"betting\",\"metric\":\"roi_delta\",\"roi_delta\":0,\"current_roi\":$CURRENT_ROI,\"sharpe_ratio\":$CURRENT_SHARPE,\"win_rate\":$WIN_RATE,\"kelly_edge\":null,\"improved\":false}"
