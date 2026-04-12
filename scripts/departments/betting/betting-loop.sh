#!/bin/bash
# Department: BETTING — Karpathy Mutator Loop (Real)
# Pattern: MUTATE betting strategy param → MEASURE Sharpe → KEEP if better → REVERT if worse
# Metric: Sharpe ratio from latest backtest (higher = better)
# Output: data/departments/betting/karpathy-output.json
#         data/departments/betting/metrics.jsonl
set -uo pipefail

DEPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$(dirname "$(dirname "$DEPT_DIR")")")"
export ROOT
DATA_OUT="$ROOT/data/departments/betting"
CONFIG_FILE="$DATA_OUT/config.json"
METRICS_FILE="$DATA_OUT/metrics.jsonl"
OUTPUT_FILE="$DATA_OUT/karpathy-output.json"
BACKTEST_FILE="$ROOT/data/nba-agent/backtest-results.json"
BANKROLL_FILE="$ROOT/data/nba-agent/bankroll-state.json"

mkdir -p "$DATA_OUT"

ONCE=false
for arg in "$@"; do
    [[ "$arg" == "--once" ]] && ONCE=true
done

# ── Ensure config exists ──────────────────────────────────────────────────────
if [ ! -f "$CONFIG_FILE" ]; then
    cat > "$CONFIG_FILE" << 'CFGEOF'
{
  "kelly_fraction": 0.25,
  "min_edge": 0.05,
  "min_confidence": 0.55,
  "max_bet_fraction": 0.10,
  "drawdown_halt_pct": 20.0,
  "underdog_odds_min": 2.20,
  "underdog_model_prob_min": 0.45,
  "_description": "Betting dept config — mutated by Karpathy loop",
  "_version": 1
}
CFGEOF
fi

# ── Iteration counter ─────────────────────────────────────────────────────────
ITER_FILE="$DATA_OUT/.iteration"
ITERATION=$(cat "$ITER_FILE" 2>/dev/null || echo 0)
ITERATION=$((ITERATION + 1))
echo "$ITERATION" > "$ITER_FILE"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "=== BETTING KARPATHY iter=$ITERATION @ $TIMESTAMP ==="

# ── Helper: read Sharpe from backtest file ────────────────────────────────────
read_sharpe() {
    python3 -c "
import json, os
# Try backtest-results first, then bankroll-state
for f in ['$BACKTEST_FILE', '$BANKROLL_FILE']:
    if os.path.exists(f):
        d = json.load(open(f))
        s = d.get('sharpe_ratio', d.get('sharpe', None))
        if s is not None:
            print(round(float(s), 4))
            exit(0)
print('null')
" 2>/dev/null || echo "null"
}

# Helper: read ROI
read_roi() {
    python3 -c "
import json, os
for f in ['$BACKTEST_FILE', '$BANKROLL_FILE']:
    if os.path.exists(f):
        d = json.load(open(f))
        r = d.get('total_roi_pct', d.get('roi_pct', None))
        if r is not None:
            print(round(float(r), 4))
            exit(0)
print('null')
" 2>/dev/null || echo "null"
}

# ── STEP 1: Baseline metrics ──────────────────────────────────────────────────
BASELINE_SHARPE=$(read_sharpe)
BASELINE_ROI=$(read_roi)
echo "  Baseline  Sharpe=$BASELINE_SHARPE  ROI=$BASELINE_ROI%"

# ── STEP 2: Backup config ─────────────────────────────────────────────────────
cp "$CONFIG_FILE" "$CONFIG_FILE.bak"

# ── STEP 3: Mutate one param ──────────────────────────────────────────────────
MUTATION_RESULT=$(python3 - << 'PYEOF'
import json, random, os
from pathlib import Path

config_file = Path(os.environ.get("ROOT", "")) / "data/departments/betting/config.json"
c = json.loads(config_file.read_text())

mutable = {k: v for k, v in c.items() if not k.startswith("_") and isinstance(v, (int, float))}
param = random.choice(list(mutable.keys()))
old_val = c[param]

# Constrained mutation ranges per param
BOUNDS = {
    "kelly_fraction":          (0.10, 0.50),
    "min_edge":                (0.02, 0.12),
    "min_confidence":          (0.50, 0.70),
    "max_bet_fraction":        (0.05, 0.20),
    "drawdown_halt_pct":       (10.0, 30.0),
    "underdog_odds_min":       (1.80, 2.80),
    "underdog_model_prob_min": (0.35, 0.55),
}

lo, hi = BOUNDS.get(param, (old_val * 0.85, old_val * 1.15))
new_val = round(random.uniform(lo, hi), 4)
c[param] = new_val
config_file.write_text(json.dumps(c, indent=2))
print(json.dumps({"param": param, "old": old_val, "new": new_val}))
PYEOF
)

MUTATED_PARAM=$(echo "$MUTATION_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('param', 'none'))" 2>/dev/null || echo "none")
MUTATED_OLD=$(echo "$MUTATION_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('old', 0))" 2>/dev/null || echo 0)
MUTATED_NEW=$(echo "$MUTATION_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('new', 0))" 2>/dev/null || echo 0)
echo "  Mutated: $MUTATED_PARAM  $MUTATED_OLD → $MUTATED_NEW"

# ── STEP 4: Re-score backtest with new config params ─────────────────────────
# For betting, we rescore using the config's kelly/edge params against backtest trades
AFTER_SHARPE=$(python3 - << 'PYEOF'
import json, os, math
from pathlib import Path

ROOT = os.environ.get("ROOT", "")
config_file = Path(ROOT) / "data/departments/betting/config.json"
backtest_file = Path(ROOT) / "data/nba-agent/backtest-results.json"
bankroll_file = Path(ROOT) / "data/nba-agent/bankroll-state.json"

try:
    c = json.loads(config_file.read_text())
    kelly = c.get("kelly_fraction", 0.25)
    min_edge = c.get("min_edge", 0.05)
    min_conf = c.get("min_confidence", 0.55)

    bt = json.loads(backtest_file.read_text()) if backtest_file.exists() else {}
    trades = bt.get("trades", [])

    if not trades:
        # No trades to rescore — use stored Sharpe
        for f in [backtest_file, bankroll_file]:
            if f.exists():
                d = json.loads(f.read_text())
                s = d.get("sharpe_ratio", d.get("sharpe", None))
                if s is not None:
                    print(round(float(s), 4))
                    exit(0)
        print("null")
        exit(0)

    # Rescore trades with new kelly/edge filter
    bankroll = 100.0
    returns = []
    for t in trades:
        edge = float(t.get("edge", 0))
        prob = float(t.get("model_prob", 0))
        won = bool(t.get("won", False))
        odds = float(t.get("odds", 2.0))

        # Apply new config filters
        if edge < min_edge or prob < min_conf:
            continue

        bet_size = bankroll * kelly * min(edge, 0.20)
        if won:
            bankroll += bet_size * (odds - 1)
            returns.append(bet_size * (odds - 1) / (bankroll + 1e-9))
        else:
            bankroll -= bet_size
            returns.append(-bet_size / (bankroll + 1e-9))

    if len(returns) < 5:
        # Too few trades after filter — read stored value
        for f in [backtest_file, bankroll_file]:
            if f.exists():
                d = json.loads(f.read_text())
                s = d.get("sharpe_ratio", d.get("sharpe", None))
                if s is not None:
                    print(round(float(s), 4))
                    exit(0)
        print("null")
        exit(0)

    avg_r = sum(returns) / len(returns)
    std_r = math.sqrt(sum((r - avg_r) ** 2 for r in returns) / len(returns))
    sharpe = (avg_r / std_r) * math.sqrt(252) if std_r > 0 else 0.0
    print(round(sharpe, 4))

except Exception as e:
    print("null")
PYEOF
)

echo "  After Sharpe: $AFTER_SHARPE"

# ── STEP 5: Keep or revert (higher Sharpe = better) ──────────────────────────
KEPT=false
DELTA="0.0"
DECISION="no_baseline"

if [ "$BASELINE_SHARPE" != "null" ] && [ "$AFTER_SHARPE" != "null" ]; then
    DELTA=$(python3 -c "print(round($AFTER_SHARPE - $BASELINE_SHARPE, 6))" 2>/dev/null || echo "0.0")
    if python3 -c "exit(0 if $AFTER_SHARPE >= $BASELINE_SHARPE else 1)" 2>/dev/null; then
        KEPT=true
        DECISION="kept"
        rm -f "$CONFIG_FILE.bak"
        echo "  IMPROVED Sharpe by $DELTA — keeping"
    else
        DECISION="reverted"
        mv "$CONFIG_FILE.bak" "$CONFIG_FILE"
        echo "  WORSE Sharpe by $DELTA — reverting"
    fi
else
    rm -f "$CONFIG_FILE.bak"
    KEPT=true
    DECISION="kept_no_baseline"
    echo "  No Sharpe baseline — keeping"
fi

# ── STEP 6: Write output + metrics ───────────────────────────────────────────
python3 - << PYEOF
import json, os

out = {
    "department": "betting",
    "timestamp": "$TIMESTAMP",
    "iteration": $ITERATION,
    "karpathy": {
        "baseline_sharpe": $BASELINE_SHARPE if "$BASELINE_SHARPE" != "null" else None,
        "after_sharpe": $AFTER_SHARPE if "$AFTER_SHARPE" != "null" else None,
        "delta": $DELTA,
        "mutation": {
            "param": "$MUTATED_PARAM",
            "old": "$MUTATED_OLD",
            "new": "$MUTATED_NEW",
        },
        "decision": "$DECISION",
        "kept": "$KEPT" == "true",
    },
    "live_metrics": {
        "baseline_roi_pct": $BASELINE_ROI if "$BASELINE_ROI" != "null" else None,
        "sharpe": $BASELINE_SHARPE if "$BASELINE_SHARPE" != "null" else None,
    },
    "status": "completed",
}
with open("$OUTPUT_FILE", "w") as f:
    json.dump(out, f, indent=2)

metric = {
    "ts": "$TIMESTAMP",
    "iter": $ITERATION,
    "sharpe_before": $BASELINE_SHARPE if "$BASELINE_SHARPE" != "null" else None,
    "sharpe_after": $AFTER_SHARPE if "$AFTER_SHARPE" != "null" else None,
    "delta": $DELTA,
    "param": "$MUTATED_PARAM",
    "old": "$MUTATED_OLD",
    "new": "$MUTATED_NEW",
    "decision": "$DECISION",
}
with open("$METRICS_FILE", "a") as f:
    f.write(json.dumps(metric) + "\n")
PYEOF

echo "  Output: $OUTPUT_FILE | decision=$DECISION  delta=$DELTA"
[ "$ONCE" = "true" ] && exit 0

echo "  Sleeping 5 minutes..."
sleep 300
exec "$0" "$@"
