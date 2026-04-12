#!/bin/bash
# Department: POLITICAL (D7) — Karpathy Loop
# Pattern: scan signals → compute alpha → propose features → measure → keep/revert
# Metric: political_brier, etf_roi, signal_accuracy
# Runtime: max 5 minutes per iteration, loops indefinitely
# Usage: ./political-loop.sh [--once] [--dry-run]
set -euo pipefail

DEPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$(dirname "$(dirname "$DEPT_DIR")")")"
POLITICAL_ROOT="${ROOT}/../nomos-political-alpha"
export ROOT
export POLITICAL_ROOT
OUTPUT_DIR="$ROOT/data/departments/political"
LOG_FILE="$OUTPUT_DIR/loop.log"
STATE_FILE="$OUTPUT_DIR/loop-state.json"
KARPATHY_OUT="$OUTPUT_DIR/karpathy-output.json"

ONCE=false
DRY_RUN=false
for arg in "$@"; do
    [[ "$arg" == "--once" ]]    && ONCE=true
    [[ "$arg" == "--dry-run" ]] && DRY_RUN=true
done

mkdir -p "$OUTPUT_DIR"

log() {
    local ts
    ts=$(date -u +"%H:%M:%S")
    echo "[$ts] $*" | tee -a "$LOG_FILE"
}

# ── READ CURRENT STATE ────────────────────────────────────────────────────────
read_state() {
    python3 -c "
import json, os
f = '$STATE_FILE'
default = {
    'iteration': 0,
    'best_brier': 0.28359,
    'best_etf_roi': 79.06,
    'best_sharpe': 5.327,
    'last_signal_count': 0,
    'last_run': None,
    'improvements': 0,
    'proposals_sent': 0
}
if os.path.exists(f):
    try:
        d = json.load(open(f))
        default.update(d)
    except Exception:
        pass
print(json.dumps(default))
" 2>/dev/null
}

write_state() {
    local state_json="$1"
    echo "$state_json" > "$STATE_FILE"
}

# ── STEP 1: FETCH / REFRESH SIGNALS ──────────────────────────────────────────
# NOTE: All log() calls inside fetch_signals use >&2 so only the final count goes to stdout.
fetch_signals() {
    log "[D7-SIGNALS] Scanning political signal sources..." >&2
    local signals_count=0

    # Count enforcement dismissals (most reliable signal)
    local today
    today=$(date -u +"%Y%m%d")
    local enf_file="$POLITICAL_ROOT/data/signals/enforcement_${today}.json"
    if [[ -f "$enf_file" ]]; then
        local n_enf
        n_enf=$(python3 -c "import json; d=json.load(open('$enf_file')); print(len(d) if isinstance(d,list) else 0)" 2>/dev/null || echo 0)
        log "  enforcement_dismissed: $n_enf records" >&2
        signals_count=$((signals_count + n_enf))
    else
        log "  enforcement_dismissed: no file for today" >&2
    fi

    # Count exec orders
    local eo_file="$POLITICAL_ROOT/data/signals/exec_orders_${today}.json"
    if [[ -f "$eo_file" ]]; then
        local n_eo
        n_eo=$(python3 -c "import json; d=json.load(open('$eo_file')); print(len(d) if isinstance(d,list) else 0)" 2>/dev/null || echo 0)
        log "  exec_orders: $n_eo records" >&2
        signals_count=$((signals_count + n_eo))
    fi

    # Count fed rules
    local fr_file="$POLITICAL_ROOT/data/signals/fed_rules_${today}.json"
    if [[ -f "$fr_file" ]]; then
        local n_fr
        n_fr=$(python3 -c "import json; d=json.load(open('$fr_file')); print(len(d) if isinstance(d,list) else 0)" 2>/dev/null || echo 0)
        log "  fed_rules: $n_fr records" >&2
        signals_count=$((signals_count + n_fr))
    fi

    # Check social signals
    local social_latest="$POLITICAL_ROOT/data/social/social_signals_latest.json"
    if [[ -f "$social_latest" ]]; then
        local n_nonzero
        n_nonzero=$(python3 -c "
import json
d=json.load(open('$social_latest'))
sigs=d.get('signals',{})
print(sum(1 for v in sigs.values() if v.get('total_mentions',0)>0))
" 2>/dev/null || echo 0)
        log "  social_signals: $n_nonzero non-zero (of 26 tickers)" >&2
    fi

    # Check insider data
    local ins_file="$POLITICAL_ROOT/data/insider/form4_${today}.json"
    if [[ -f "$ins_file" ]]; then
        local n_ins
        n_ins=$(python3 -c "
import json
d=json.load(open('$ins_file'))
if isinstance(d, dict): print(sum(len(v) for v in d.values()))
elif isinstance(d, list): print(len(d))
else: print(0)
" 2>/dev/null || echo 0)
        log "  insider_form4: $n_ins transactions" >&2
        signals_count=$((signals_count + n_ins))
    fi

    echo "$signals_count"
}

# ── STEP 2: COMPUTE ETF SIGNALS ───────────────────────────────────────────────
compute_etf_signals() {
    log "[D7-ETF] Computing ETF signals from political data..." >&2
    python3 - <<'PYEOF'
import json, os, sys
from datetime import datetime
from pathlib import Path

POLITICAL_ROOT = Path(os.environ.get("POLITICAL_ROOT") or str(Path(os.environ.get("ROOT", "")).parent / "nomos-political-alpha"))
today = datetime.utcnow().strftime("%Y%m%d")

# Load enforcement dismissals
enf_file = POLITICAL_ROOT / f"data/signals/enforcement_{today}.json"
enforcement = []
if enf_file.exists():
    try:
        enforcement = json.loads(enf_file.read_text())
    except Exception:
        pass

# Ticker -> ETF sector map
TICKER_ETF = {
    "COIN": "QQQ", "HOOD": "QQQ", "META": "QQQ", "AAPL": "QQQ", "MSFT": "QQQ",
    "NVDA": "QQQ", "AMZN": "QQQ", "MSTR": "QQQ",
    "CVX": "XLE",  "XOM": "XLE",  "OXY": "XLE",  "COP": "XLE",  "HAL": "XLE",
    "LMT": "XLI",  "RTX": "XLI",  "BA": "XLI",   "GD": "XLI",   "NOC": "XLI",
    "UNH": "XLV",  "PFE": "XLV",  "MO": "XLV",   "ABBV": "XLV",
    "GEO": "IWM",  "CXW": "IWM",
    "JPM": "XLF",  "BAC": "XLF",  "GS": "XLF",   "MS": "XLF",
    "TSLA": "QQQ", "OKLO": "XLK", "FDX": "XLI",  "UNP": "XLI",
    "FOUR": "XLF", "CMCSA": "QQQ",
}

etf_signals = {}

# Score from enforcement dismissals
for r in enforcement:
    ticker = r.get("ticker", "")
    etf = TICKER_ETF.get(ticker, "SPY")
    if etf not in etf_signals:
        etf_signals[etf] = {"strength": 0.0, "drivers": [], "direction": "long"}
    etf_signals[etf]["strength"] += 0.18  # each dismissal = +0.18 signal
    etf_signals[etf]["drivers"].append(f"enforcement_drop:{ticker}")

# Score from exec orders
eo_file = POLITICAL_ROOT / f"data/signals/exec_orders_{today}.json"
if eo_file.exists():
    try:
        eos = json.loads(eo_file.read_text())
        for eo in eos:
            for t in eo.get("affected_tickers", []):
                etf = TICKER_ETF.get(t, "SPY")
                if etf not in etf_signals:
                    etf_signals[etf] = {"strength": 0.0, "drivers": [], "direction": "long"}
                etf_signals[etf]["strength"] += 0.12
                etf_signals[etf]["drivers"].append(f"exec_order:{t}")
    except Exception:
        pass

# Score from fed rules (tickers mentioned)
fr_file = POLITICAL_ROOT / f"data/signals/fed_rules_{today}.json"
if fr_file.exists():
    try:
        from collections import Counter
        rules = json.loads(fr_file.read_text())
        ticker_counts = Counter()
        for r in rules:
            for t in r.get("affected_tickers", []):
                ticker_counts[t] += 1
        for t, count in ticker_counts.items():
            etf = TICKER_ETF.get(t, "SPY")
            if etf not in etf_signals:
                etf_signals[etf] = {"strength": 0.0, "drivers": [], "direction": "long"}
            etf_signals[etf]["strength"] += count * 0.02
            etf_signals[etf]["drivers"].append(f"fed_rules_mention:{t}(x{count})")
    except Exception:
        pass

# Cap at 1.0 and round
for etf in etf_signals:
    etf_signals[etf]["strength"] = round(min(etf_signals[etf]["strength"], 1.0), 4)

# Tariff risk overlay: Liberation Day anniversary April 2
from datetime import date
days_to_april2 = (date(2026, 4, 2) - date.today()).days
if 0 <= days_to_april2 <= 3:
    # Reduce tech exposure as tariff anniversary risk
    for t in ["QQQ", "XLK"]:
        if t in etf_signals:
            etf_signals[t]["tariff_anniversary_discount"] = 0.3
            etf_signals[t]["strength"] = round(max(0, etf_signals[t]["strength"] - 0.3), 4)
            etf_signals[t]["drivers"].append(f"tariff_anniversary_risk(T-{days_to_april2}d)")
    # Add GLD hedge
    etf_signals["GLD"] = {"strength": 0.40, "direction": "long",
                          "drivers": ["liberation_day_anniversary_hedge"],
                          "reason": "inflation/tariff hedge"}

print(json.dumps(etf_signals, indent=2))
PYEOF
}

# ── STEP 3: MEASURE POLITICAL BRIER ──────────────────────────────────────────
measure_brier() {
    log "[D7-MEASURE] Computing political Brier score..." >&2
    python3 - <<'PYEOF'
import json, math
from pathlib import Path

POLITICAL_ROOT = Path(os.environ.get("POLITICAL_ROOT") or str(Path(os.environ.get("ROOT", "")).parent / "nomos-political-alpha"))
events_file = POLITICAL_ROOT / "data/historical/consolidated_events.json"

if not events_file.exists():
    print("null")
    exit(0)

events = json.loads(events_file.read_text())
events = [e for e in events if "y" in e and "signal_strength" in e]

if not events:
    print("null")
    exit(0)

# Current naive brier
brier_naive = sum((e.get("signal_strength", 0.5) - e.get("y", 0)) ** 2 for e in events) / len(events)
brier_half  = sum((0.5 - e.get("y", 0)) ** 2 for e in events) / len(events)

# By type
from collections import defaultdict
by_type = defaultdict(lambda: {"n": 0, "brier_sum": 0.0, "wins": 0})
for e in events:
    t = e.get("event_type", "unknown")
    by_type[t]["n"] += 1
    by_type[t]["brier_sum"] += (e.get("signal_strength", 0.5) - e.get("y", 0)) ** 2
    by_type[t]["wins"] += int(e.get("y", 0))

by_type_out = {}
for t, v in by_type.items():
    by_type_out[t] = {
        "brier": round(v["brier_sum"] / v["n"], 5),
        "win_rate": round(v["wins"] / v["n"], 4),
        "n": v["n"]
    }

result = {
    "brier_naive": round(brier_naive, 5),
    "brier_baseline_half": round(brier_half, 5),
    "brier_gap": round(brier_naive - brier_half, 5),
    "n_events": len(events),
    "by_type": by_type_out,
    "calibration_needed": brier_naive > brier_half
}
print(json.dumps(result))
PYEOF
}

# ── STEP 4: PROPOSE QUICK WINS ───────────────────────────────────────────────
propose_quick_wins() {
    log "[D7-PROPOSE] Generating quick-win proposals..." >&2
    python3 - <<'PYEOF'
import json
from datetime import datetime

proposals = []

# P1: Fix insider transaction_type (critical, 4h)
proposals.append({
    "id": "D7-P1",
    "priority": 1,
    "title": "Fix insider transaction_type disambiguation",
    "type": "data_fix",
    "effort_hours": 4,
    "expected_brier_delta": -0.015,
    "action": "In ops/fetch_political_data.py: parse Form4 XML transactionCode. P=buy, S=sell. Add buy_cluster_14d feature.",
    "file": "/home/termius/nomos-political-alpha/ops/fetch_political_data.py",
    "created_at": datetime.utcnow().isoformat() + "Z"
})

# P2: Fix Polymarket CLOB (critical, 3h)
proposals.append({
    "id": "D7-P2",
    "priority": 2,
    "title": "Fix Polymarket CLOB to active policy markets",
    "type": "data_fix",
    "effort_hours": 3,
    "expected_brier_delta": -0.012,
    "action": "Update polymarket fetch to clob.polymarket.com. Track: tariff_reciprocal, china_trade_deal, trump_approval.",
    "file": "/home/termius/nomos-political-alpha/ops/fetch_political_data.py",
    "created_at": datetime.utcnow().isoformat() + "Z"
})

# P3: Liberation Day tariff anniversary feature (high, 6h)
proposals.append({
    "id": "D7-P3",
    "priority": 3,
    "title": "Liberation Day anniversary tariff risk feature",
    "type": "feature_engineering",
    "effort_hours": 6,
    "expected_brier_delta": -0.008,
    "action": "Add tariff_anniversary_flag, days_to_tariff_anniversary, import_intensity_sector. Short XLK/QQQ into April 2.",
    "file": "/home/termius/nomos-political-alpha/features/political_engine.py",
    "created_at": datetime.utcnow().isoformat() + "Z"
})

# P4: Fix USAspending gov contracts (high, 2h)
proposals.append({
    "id": "D7-P4",
    "priority": 4,
    "title": "Fix USAspending.gov contract fetch",
    "type": "data_fix",
    "effort_hours": 2,
    "expected_brier_delta": -0.006,
    "action": "Debug ops/fetch_political_data.py fetch_usaspending(). gov_contracts returning {}. Check POST payload to /api/v2/search/spending_by_award/",
    "file": "/home/termius/nomos-political-alpha/ops/fetch_political_data.py",
    "created_at": datetime.utcnow().isoformat() + "Z"
})

# P5: Calibrate signal_strength (critical for Brier)
proposals.append({
    "id": "D7-P5",
    "priority": 5,
    "title": "Calibrate signal_strength to true probabilities",
    "type": "calibration",
    "effort_hours": 5,
    "expected_brier_delta": -0.020,
    "action": "Current signal_strength values (0.5, 0.7) are uncalibrated — naive Brier 0.28 > baseline 0.25. Apply isotonic calibration from calibration/isotonic_calibrator.py to output calibrated probs.",
    "file": "/home/termius/nomos-political-alpha/calibration/isotonic_calibrator.py",
    "created_at": datetime.utcnow().isoformat() + "Z"
})

# P6: Restart HF Space
proposals.append({
    "id": "D7-P6",
    "priority": 6,
    "title": "Restart LBJLincoln26/nomos-political-alpha HF Space",
    "type": "infra_fix",
    "effort_hours": 0.25,
    "expected_brier_delta": 0.0,
    "action": "HF Space has been DOWN all day (cron logs confirm). Go to https://huggingface.co/spaces/LBJLincoln26/nomos-political-alpha and restart.",
    "created_at": datetime.utcnow().isoformat() + "Z"
})

print(json.dumps({"proposals": proposals, "count": len(proposals)}, indent=2))
PYEOF
}

# ── STEP 5: UPDATE KARPATHY OUTPUT ────────────────────────────────────────────
update_output() {
    local iteration="$1"
    local brier_json="$2"
    local etf_json="$3"
    local proposals_json="$4"
    local signal_count="$5"

    python3 - "$iteration" "$brier_json" "$etf_json" "$proposals_json" "$signal_count" <<'PYEOF'
import json, os, sys
from datetime import datetime

iteration     = int(sys.argv[1])
brier_data    = json.loads(sys.argv[2]) if sys.argv[2] != "null" else None
etf_data      = json.loads(sys.argv[3]) if sys.argv[3] != "{}" else {}
proposals     = json.loads(sys.argv[4]).get("proposals", [])
signal_count  = int(sys.argv[5])

out_path = os.path.join(os.environ.get("ROOT", ""), "data/departments/political/karpathy-output.json")

try:
    existing = json.load(open(out_path))
except Exception:
    existing = {}

political_brier = brier_data["brier_naive"] if brier_data else existing.get("political_brier", None)

# Merge updates into existing output
existing.update({
    "timestamp":            datetime.utcnow().isoformat() + "+00:00",
    "iteration":            iteration,
    "political_brier":      political_brier,
    "political_brier_baseline": brier_data["brier_baseline_half"] if brier_data else 0.25,
    "brier_gap_vs_baseline": brier_data["brier_gap"] if brier_data else None,
    "n_events_measured":    brier_data["n_events"] if brier_data else 0,
    "signal_count_today":   signal_count,
    "etf_live_signals":     etf_data,
    "new_signals_proposed": proposals[:8],
    "loop_status":          "running",
    "status":               "completed"
})

with open(out_path, "w") as f:
    json.dump(existing, f, indent=2)
print("updated")
PYEOF
}

# ── MAIN LOOP ─────────────────────────────────────────────────────────────────
main() {
    log "═══ D7 POLITICAL KARPATHY LOOP STARTING ═══"
    log "  Root: $ROOT"
    log "  Political repo: $POLITICAL_ROOT"
    log "  Output: $OUTPUT_DIR"

    local state
    state=$(read_state)
    local iteration
    iteration=$(echo "$state" | python3 -c "import json,sys; print(json.load(sys.stdin)['iteration'])")

    while true; do
        iteration=$((iteration + 1))
        local ts
        ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
        log ""
        log "═══ ITERATION $iteration — $ts ═══"

        # ── Step 1: Fetch signals ──
        local signal_count
        signal_count=$(fetch_signals)
        log "  Total signals collected: $signal_count"

        # ── Step 2: Compute ETF signals ──
        local etf_json="{}"
        if [[ "$DRY_RUN" == "false" ]]; then
            etf_json=$(compute_etf_signals 2>/dev/null || echo "{}")
            local n_etf_signals
            n_etf_signals=$(echo "$etf_json" | python3 -c "import json,sys; d=json.load(sys.stdin); print(len([v for v in d.values() if v.get('strength',0)>0]))" 2>/dev/null || echo 0)
            log "  ETF signals with strength>0: $n_etf_signals"
        fi

        # ── Step 3: Measure Brier ──
        local brier_json="null"
        brier_json=$(measure_brier 2>/dev/null || echo "null")
        if [[ "$brier_json" != "null" ]]; then
            local current_brier
            current_brier=$(echo "$brier_json" | python3 -c "import json,sys; print(json.load(sys.stdin)['brier_naive'])" 2>/dev/null || echo "N/A")
            log "  Political Brier: $current_brier (baseline: 0.25000)"
        fi

        # ── Step 4: Propose quick wins ──
        local proposals_json="{}"
        proposals_json=$(propose_quick_wins 2>/dev/null || echo '{"proposals":[]}')
        local n_proposals
        n_proposals=$(echo "$proposals_json" | python3 -c "import json,sys; print(json.load(sys.stdin)['count'])" 2>/dev/null || echo 0)
        log "  Proposals generated: $n_proposals"

        # ── Step 5: Update output ──
        if [[ "$DRY_RUN" == "false" ]]; then
            update_output "$iteration" "$brier_json" "$etf_json" "$proposals_json" "$signal_count" >/dev/null 2>&1 && \
                log "  karpathy-output.json updated"
        fi

        # ── Update state ──
        local new_state
        new_state=$(echo "$state" | python3 -c "
import json, sys
d = json.load(sys.stdin)
d['iteration'] = $iteration
d['last_signal_count'] = $signal_count
d['last_run'] = '$ts'
d['proposals_sent'] = d.get('proposals_sent', 0) + $n_proposals
print(json.dumps(d))
" 2>/dev/null || echo "$state")
        write_state "$new_state"
        state="$new_state"

        log "  Iteration $iteration complete."

        # ── Loop control ──
        if [[ "$ONCE" == "true" ]]; then
            log "═══ D7 LOOP COMPLETE (--once) ═══"
            break
        fi

        log "  Sleeping 5 minutes before next iteration..."
        sleep 300
    done
}

main "$@"
