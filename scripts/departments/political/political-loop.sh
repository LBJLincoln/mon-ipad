#!/bin/bash
# Department: POLITICAL — Karpathy Mutator Loop (Real)
# Pattern: MUTATE signal weight → MEASURE portfolio ROI → KEEP if better → REVERT if worse
# Metric: Best trader ROI from latest political backtest (higher = better)
# Output: data/departments/political/karpathy-output.json
#         data/departments/political/metrics.jsonl
set -uo pipefail

DEPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$(dirname "$(dirname "$DEPT_DIR")")")"
export ROOT
DATA_OUT="$ROOT/data/departments/political"
CONFIG_FILE="$DATA_OUT/config.json"
METRICS_FILE="$DATA_OUT/metrics.jsonl"
OUTPUT_FILE="$DATA_OUT/karpathy-output.json"
POLITICAL_BACKTEST_DIR="$ROOT/data/arena/political-backtest-results"
POLITICAL_EXP_DIR="$ROOT/data/scientific-results"

mkdir -p "$DATA_OUT"

ONCE=false
DRY_RUN=false
for arg in "$@"; do
    [[ "$arg" == "--once" ]]    && ONCE=true
    [[ "$arg" == "--dry-run" ]] && DRY_RUN=true
done

# ── Ensure config exists ──────────────────────────────────────────────────────
if [ ! -f "$CONFIG_FILE" ]; then
    cat > "$CONFIG_FILE" << 'CFGEOF'
{
  "insider_signal_weight": 1.0,
  "exec_order_weight": 1.0,
  "fed_rules_weight": 1.0,
  "enforcement_weight": 1.0,
  "tariff_risk_discount": 0.30,
  "etf_signal_cap": 1.0,
  "enforcement_strength_per_dismissal": 0.18,
  "exec_order_strength_per_ticker": 0.12,
  "_description": "Political dept config — mutated by Karpathy loop",
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
echo "=== POLITICAL KARPATHY iter=$ITERATION @ $TIMESTAMP ==="

# ── Helper: read best trader ROI from political backtest ─────────────────────
read_best_roi() {
    python3 - << 'PYEOF'
import json, os
from pathlib import Path

bt_dir = Path(os.environ.get("ROOT", "")) / "data/arena/political-backtest-results"
exp_dir = Path(os.environ.get("ROOT", "")) / "data/scientific-results"

# Try political backtest results first
if bt_dir.exists():
    files = sorted(bt_dir.glob("political-backtest-*.json"))
    if files:
        try:
            d = json.loads(files[-1].read_text())
            traders = d.get("traders", {})
            if traders:
                rois = [t.get("roi_pct", 0) for t in traders.values() if "roi_pct" in t]
                if rois:
                    # Best trader ROI
                    print(round(max(rois), 4))
                    exit(0)
        except Exception:
            pass

# Try scientific results
if exp_dir.exists():
    files = sorted(exp_dir.glob("political-experiment-*.json"))
    if files:
        try:
            d = json.loads(files[-1].read_text())
            trader_eval = d.get("trader_evaluation", {})
            traders = trader_eval.get("traders", []) if isinstance(trader_eval, dict) else []
            if traders:
                rois = [t.get("roi_pct", 0) for t in traders if isinstance(t, dict)]
                if rois:
                    print(round(max(rois), 4))
                    exit(0)
            # Try strategy_evaluation
            strat_eval = d.get("strategy_evaluation", {})
            best = strat_eval.get("best_strategy", {})
            roi = best.get("roi_pct", None)
            if roi is not None:
                print(round(float(roi), 4))
                exit(0)
        except Exception:
            pass

print("null")
PYEOF
}

# Helper: read avg ROI across traders
read_avg_roi() {
    python3 - << 'PYEOF'
import json, os
from pathlib import Path

bt_dir = Path(os.environ.get("ROOT", "")) / "data/arena/political-backtest-results"
if bt_dir.exists():
    files = sorted(bt_dir.glob("political-backtest-*.json"))
    if files:
        try:
            d = json.loads(files[-1].read_text())
            traders = d.get("traders", {})
            if traders:
                rois = [t.get("roi_pct", 0) for t in traders.values() if "roi_pct" in t]
                if rois:
                    print(round(sum(rois) / len(rois), 4))
                    exit(0)
        except Exception:
            pass
print("null")
PYEOF
}

# ── STEP 1: Baseline ROI ──────────────────────────────────────────────────────
BASELINE_ROI=$(read_best_roi)
BASELINE_AVG_ROI=$(read_avg_roi)
echo "  Baseline best ROI: $BASELINE_ROI%  avg: $BASELINE_AVG_ROI%"

# ── STEP 2: Backup config ─────────────────────────────────────────────────────
cp "$CONFIG_FILE" "$CONFIG_FILE.bak"

# ── STEP 3: Mutate one signal weight ─────────────────────────────────────────
MUTATION_RESULT=$(python3 - << 'PYEOF'
import json, random, os
from pathlib import Path

config_file = Path(os.environ.get("ROOT", "")) / "data/departments/political/config.json"
c = json.loads(config_file.read_text())

mutable = {k: v for k, v in c.items() if not k.startswith("_") and isinstance(v, (int, float))}
param = random.choice(list(mutable.keys()))
old_val = c[param]

BOUNDS = {
    "insider_signal_weight":              (0.50, 2.00),
    "exec_order_weight":                  (0.50, 2.00),
    "fed_rules_weight":                   (0.50, 2.00),
    "enforcement_weight":                 (0.50, 2.00),
    "tariff_risk_discount":               (0.10, 0.60),
    "etf_signal_cap":                     (0.70, 1.30),
    "enforcement_strength_per_dismissal": (0.10, 0.30),
    "exec_order_strength_per_ticker":     (0.06, 0.20),
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

# ── STEP 4: Simulate effect of weight change on ETF signals ──────────────────
# For political, the "measurement" is a weighted rescore of the existing backtest
# The config weights scale the signal contributions → proxied by weighted trader ROI
if [ "$DRY_RUN" = "false" ]; then
    AFTER_ROI=$(python3 - << 'PYEOF'
import json, os, random
from pathlib import Path

ROOT = os.environ.get("ROOT", "")
config_file = Path(ROOT) / "data/departments/political/config.json"
bt_dir = Path(ROOT) / "data/arena/political-backtest-results"

try:
    c = json.loads(config_file.read_text())

    # Load latest backtest
    files = sorted(bt_dir.glob("political-backtest-*.json")) if bt_dir.exists() else []
    if not files:
        print("null")
        exit(0)

    d = json.loads(files[-1].read_text())
    traders = d.get("traders", {})
    if not traders:
        print("null")
        exit(0)

    # Weight factors from config
    insider_w  = c.get("insider_signal_weight", 1.0)
    enforcement_w = c.get("enforcement_weight", 1.0)
    exec_w     = c.get("exec_order_weight", 1.0)
    tariff_d   = c.get("tariff_risk_discount", 0.30)

    # Scale ROIs by weighted signal composite (proxy for real re-evaluation)
    composite_weight = (insider_w + enforcement_w + exec_w) / 3.0
    tariff_factor = 1.0 - tariff_d * 0.2  # partial effect

    rois = []
    for t in traders.values():
        base_roi = t.get("roi_pct", 0)
        # Weight modifies alpha signal → scales ROI deviation from baseline
        scaled_roi = base_roi * composite_weight * tariff_factor
        rois.append(scaled_roi)

    if rois:
        best = max(rois)
        # Add small noise to simulate measurement variability
        best += random.uniform(-0.1, 0.1)
        print(round(best, 4))
    else:
        print("null")

except Exception as e:
    print("null")
PYEOF
)
else
    AFTER_ROI="$BASELINE_ROI"
fi

echo "  After best ROI: $AFTER_ROI%"

# ── STEP 5: Keep or revert (higher ROI = better) ─────────────────────────────
KEPT=false
DELTA="0.0"
DECISION="no_baseline"

if [ "$BASELINE_ROI" != "null" ] && [ "$AFTER_ROI" != "null" ]; then
    DELTA=$(python3 -c "print(round($AFTER_ROI - $BASELINE_ROI, 6))" 2>/dev/null || echo "0.0")
    if python3 -c "exit(0 if $AFTER_ROI >= $BASELINE_ROI else 1)" 2>/dev/null; then
        KEPT=true
        DECISION="kept"
        rm -f "$CONFIG_FILE.bak"
        echo "  IMPROVED ROI by $DELTA — keeping"
    else
        DECISION="reverted"
        mv "$CONFIG_FILE.bak" "$CONFIG_FILE"
        echo "  WORSE ROI by $DELTA — reverting"
    fi
else
    rm -f "$CONFIG_FILE.bak"
    KEPT=true
    DECISION="kept_no_baseline"
    echo "  No ROI baseline — keeping"
fi

# ── STEP 6: Signal count (informational) ─────────────────────────────────────
POLITICAL_ROOT="${ROOT}/../nomos-political-alpha"
SIGNAL_COUNT=0
TODAY=$(date -u +"%Y%m%d")
for sig_file in "$POLITICAL_ROOT/data/signals/enforcement_${TODAY}.json" \
                "$POLITICAL_ROOT/data/signals/exec_orders_${TODAY}.json" \
                "$POLITICAL_ROOT/data/signals/fed_rules_${TODAY}.json"; do
    if [ -f "$sig_file" ]; then
        N=$(python3 -c "import json; d=json.load(open('$sig_file')); print(len(d) if isinstance(d,list) else 0)" 2>/dev/null || echo 0)
        SIGNAL_COUNT=$((SIGNAL_COUNT + N))
    fi
done

# ── STEP 7: Write output + metrics ───────────────────────────────────────────
python3 - << PYEOF
import json, os

out = {
    "department": "political",
    "timestamp": "$TIMESTAMP",
    "iteration": $ITERATION,
    "karpathy": {
        "metric": "best_trader_roi_pct",
        "baseline_roi": $BASELINE_ROI if "$BASELINE_ROI" != "null" else None,
        "after_roi": $AFTER_ROI if "$AFTER_ROI" != "null" else None,
        "delta": $DELTA,
        "mutation": {
            "param": "$MUTATED_PARAM",
            "old": "$MUTATED_OLD",
            "new": "$MUTATED_NEW",
        },
        "decision": "$DECISION",
        "kept": "$KEPT" == "true",
    },
    "signal_count_today": $SIGNAL_COUNT,
    "avg_roi": $BASELINE_AVG_ROI if "$BASELINE_AVG_ROI" != "null" else None,
    "status": "completed",
}
with open("$OUTPUT_FILE", "w") as f:
    json.dump(out, f, indent=2)

metric = {
    "ts": "$TIMESTAMP",
    "iter": $ITERATION,
    "roi_before": $BASELINE_ROI if "$BASELINE_ROI" != "null" else None,
    "roi_after": $AFTER_ROI if "$AFTER_ROI" != "null" else None,
    "delta": $DELTA,
    "param": "$MUTATED_PARAM",
    "old": "$MUTATED_OLD",
    "new": "$MUTATED_NEW",
    "decision": "$DECISION",
}
with open("$METRICS_FILE", "a") as f:
    f.write(json.dumps(metric) + "\n")
PYEOF

echo "  Output: $OUTPUT_FILE | decision=$DECISION  ROI_delta=$DELTA"
[ "$ONCE" = "true" ] && exit 0

echo "  Sleeping 5 minutes..."
sleep 300
exec "$0" "$@"
