#!/bin/bash
# Department: EVALUATION — Karpathy Mutator Loop (Real)
# Pattern: MUTATE calibration config → MEASURE ECE → KEEP if better → REVERT if worse
# Metric: ECE (Expected Calibration Error) — lower is better
# Output: data/departments/evaluation/karpathy-output.json
#         data/departments/evaluation/metrics.jsonl
set -uo pipefail

DEPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$(dirname "$(dirname "$DEPT_DIR")")")"
export ROOT
DATA_OUT="$ROOT/data/departments/evaluation"
CONFIG_FILE="$DATA_OUT/config.json"
METRICS_FILE="$DATA_OUT/metrics.jsonl"
OUTPUT_FILE="$DATA_OUT/karpathy-output.json"
BACKTEST_FILE="$ROOT/data/nba-agent/backtest-results.json"

mkdir -p "$DATA_OUT"

ONCE=false
for arg in "$@"; do
    [[ "$arg" == "--once" ]] && ONCE=true
done

# ── Ensure config exists ──────────────────────────────────────────────────────
if [ ! -f "$CONFIG_FILE" ]; then
    cat > "$CONFIG_FILE" << 'CFGEOF'
{
  "ece_target": 0.05,
  "fp_rate_target": 0.25,
  "high_confidence_threshold": 0.70,
  "calibration_shift": 0.0,
  "overconfidence_damping": 1.0,
  "isotonic_n_breakpoints": 10,
  "_description": "Evaluation dept config — mutated by Karpathy loop",
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
echo "=== EVALUATION KARPATHY iter=$ITERATION @ $TIMESTAMP ==="

# ── Helper: compute ECE from backtest trades with given calibration params ────
compute_ece() {
    local shift="$1"
    local damping="$2"
    local threshold="$3"
    python3 - "$shift" "$damping" "$threshold" << 'PYEOF'
import json, os, math, sys

shift     = float(sys.argv[1])
damping   = float(sys.argv[2])
threshold = float(sys.argv[3])

ROOT = os.environ.get("ROOT", "")
bt_file = os.path.join(ROOT, "data/nba-agent/backtest-results.json")

try:
    bt = json.loads(open(bt_file).read()) if os.path.exists(bt_file) else {}
    trades = bt.get("trades", [])
    if not trades:
        print("null")
        sys.exit(0)

    bin_defs = [
        ("50-60%", 0.50, 0.60), ("60-70%", 0.60, 0.70),
        ("70-80%", 0.70, 0.80), ("80-90%", 0.80, 0.90),
        ("90-100%", 0.90, 1.01),
    ]
    bins = {name: {"probs": [], "wins": 0, "count": 0} for name, _, _ in bin_defs}
    n_total = 0

    for t in trades:
        raw_p = float(t.get("model_prob", 0))
        won   = bool(t.get("won", False))

        # Apply calibration config: shift then damp overconfidence toward 0.5
        p = raw_p + shift
        if damping != 1.0:
            p = 0.5 + (p - 0.5) * damping
        p = max(0.01, min(0.99, p))

        n_total += 1
        for name, lo, hi in bin_defs:
            if lo <= p < hi:
                bins[name]["probs"].append(p)
                bins[name]["count"] += 1
                if won:
                    bins[name]["wins"] += 1
                break

    ece = 0.0
    for name, b in bins.items():
        if b["count"] > 0:
            avg_pred = sum(b["probs"]) / b["count"]
            actual_freq = b["wins"] / b["count"]
            ece += abs(avg_pred - actual_freq) * b["count"] / n_total

    print(round(ece, 6))

except Exception as e:
    print("null")
PYEOF
}

# ── STEP 1: Baseline ECE ──────────────────────────────────────────────────────
CURRENT_SHIFT=$(python3 -c "import json; c=json.load(open('$CONFIG_FILE')); print(c.get('calibration_shift', 0.0))" 2>/dev/null || echo 0.0)
CURRENT_DAMPING=$(python3 -c "import json; c=json.load(open('$CONFIG_FILE')); print(c.get('overconfidence_damping', 1.0))" 2>/dev/null || echo 1.0)
CURRENT_THRESHOLD=$(python3 -c "import json; c=json.load(open('$CONFIG_FILE')); print(c.get('high_confidence_threshold', 0.70))" 2>/dev/null || echo 0.70)

BASELINE_ECE=$(compute_ece "$CURRENT_SHIFT" "$CURRENT_DAMPING" "$CURRENT_THRESHOLD")
echo "  Baseline ECE: $BASELINE_ECE  (shift=$CURRENT_SHIFT  damping=$CURRENT_DAMPING)"

# ── STEP 2: Backup config ─────────────────────────────────────────────────────
cp "$CONFIG_FILE" "$CONFIG_FILE.bak"

# ── STEP 3: Mutate one calibration param ─────────────────────────────────────
MUTATION_RESULT=$(python3 - << 'PYEOF'
import json, random, os
from pathlib import Path

config_file = Path(os.environ.get("ROOT", "")) / "data/departments/evaluation/config.json"
c = json.loads(config_file.read_text())

mutable = {k: v for k, v in c.items() if not k.startswith("_") and isinstance(v, (int, float))}
param = random.choice(list(mutable.keys()))
old_val = c[param]

BOUNDS = {
    "calibration_shift":         (-0.05, 0.05),
    "overconfidence_damping":    (0.75, 1.00),
    "high_confidence_threshold": (0.60, 0.80),
    "isotonic_n_breakpoints":    (5, 20),
    "ece_target":                (0.03, 0.10),
    "fp_rate_target":            (0.15, 0.35),
}

lo, hi = BOUNDS.get(param, (old_val * 0.9, old_val * 1.1))
if param == "isotonic_n_breakpoints":
    new_val = random.randint(int(lo), int(hi))
else:
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

# ── STEP 4: Measure ECE after mutation ───────────────────────────────────────
NEW_SHIFT=$(python3 -c "import json; c=json.load(open('$CONFIG_FILE')); print(c.get('calibration_shift', 0.0))" 2>/dev/null || echo 0.0)
NEW_DAMPING=$(python3 -c "import json; c=json.load(open('$CONFIG_FILE')); print(c.get('overconfidence_damping', 1.0))" 2>/dev/null || echo 1.0)
NEW_THRESHOLD=$(python3 -c "import json; c=json.load(open('$CONFIG_FILE')); print(c.get('high_confidence_threshold', 0.70))" 2>/dev/null || echo 0.70)

AFTER_ECE=$(compute_ece "$NEW_SHIFT" "$NEW_DAMPING" "$NEW_THRESHOLD")
echo "  After ECE: $AFTER_ECE"

# ── STEP 5: Keep or revert (lower ECE = better) ───────────────────────────────
KEPT=false
DELTA="0.0"
DECISION="no_baseline"

if [ "$BASELINE_ECE" != "null" ] && [ "$AFTER_ECE" != "null" ]; then
    DELTA=$(python3 -c "print(round($BASELINE_ECE - $AFTER_ECE, 6))" 2>/dev/null || echo "0.0")
    if python3 -c "exit(0 if $AFTER_ECE <= $BASELINE_ECE else 1)" 2>/dev/null; then
        KEPT=true
        DECISION="kept"
        rm -f "$CONFIG_FILE.bak"
        echo "  IMPROVED ECE by $DELTA — keeping"
    else
        DECISION="reverted"
        mv "$CONFIG_FILE.bak" "$CONFIG_FILE"
        echo "  WORSE ECE by $DELTA — reverting"
    fi
else
    rm -f "$CONFIG_FILE.bak"
    KEPT=true
    DECISION="kept_no_baseline"
    echo "  No ECE baseline — keeping"
fi

# ── STEP 6: Compute current Brier also (for reference) ───────────────────────
BRIER=$(python3 "$ROOT/scripts/brier_proxy.py" --json 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('brier', 'null'))" 2>/dev/null || echo "null")

# ── STEP 7: Write output + metrics ───────────────────────────────────────────
python3 - << PYEOF
import json, os

out = {
    "department": "evaluation",
    "timestamp": "$TIMESTAMP",
    "iteration": $ITERATION,
    "karpathy": {
        "metric": "ECE",
        "baseline_ece": $BASELINE_ECE if "$BASELINE_ECE" != "null" else None,
        "after_ece": $AFTER_ECE if "$AFTER_ECE" != "null" else None,
        "delta": $DELTA,
        "mutation": {
            "param": "$MUTATED_PARAM",
            "old": "$MUTATED_OLD",
            "new": "$MUTATED_NEW",
        },
        "decision": "$DECISION",
        "kept": "$KEPT" == "true",
    },
    "calibration_config": {
        "shift": $NEW_SHIFT,
        "damping": $NEW_DAMPING,
        "threshold": $NEW_THRESHOLD,
    },
    "brier_reference": $BRIER if "$BRIER" != "null" else None,
    "status": "completed",
}
with open("$OUTPUT_FILE", "w") as f:
    json.dump(out, f, indent=2)

metric = {
    "ts": "$TIMESTAMP",
    "iter": $ITERATION,
    "ece_before": $BASELINE_ECE if "$BASELINE_ECE" != "null" else None,
    "ece_after": $AFTER_ECE if "$AFTER_ECE" != "null" else None,
    "delta": $DELTA,
    "param": "$MUTATED_PARAM",
    "old": "$MUTATED_OLD",
    "new": "$MUTATED_NEW",
    "decision": "$DECISION",
}
with open("$METRICS_FILE", "a") as f:
    f.write(json.dumps(metric) + "\n")
PYEOF

echo "  Output: $OUTPUT_FILE | decision=$DECISION  ECE_delta=$DELTA"
[ "$ONCE" = "true" ] && exit 0

echo "  Sleeping 5 minutes..."
sleep 300
exec "$0" "$@"
