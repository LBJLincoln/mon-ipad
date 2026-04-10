#!/bin/bash
# Department: ENGINEERING — Karpathy Loop (Real)
# Pattern: check → measure → detect bugs → output JSON metrics
# Runs every 5 minutes (max), outputs to data/departments/engineering/
#
# Checks performed each iteration:
#   1. Feature engine parity (md5 hash comparison: local vs hf-space)
#   2. Feature count (grep-based category + feature count from engine.py)
#   3. Phantom game detection in latest-picks.json (home == away)
#   4. Odds sanity check (|model_prob - market_implied| > 0.50)
#   5. Test suite pass rate (scripts/agents/test_data_leakage.py)
#
set -uo pipefail

DEPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$(dirname "$(dirname "$DEPT_DIR")")")"
DATA_OUT="$ROOT/data/departments/engineering"
PICKS_FILE="$ROOT/data/nba-agent/latest-picks.json"
HF_ENGINE="$ROOT/hf-space/features/engine.py"
LOCAL_ENGINE="$ROOT/features/engine.py"

mkdir -p "$DATA_OUT"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%S.000000+00:00")
ITER_FILE="$DATA_OUT/.iteration"
ITERATION=$(cat "$ITER_FILE" 2>/dev/null || echo 0)
ITERATION=$((ITERATION + 1))
echo "$ITERATION" > "$ITER_FILE"

# ── 1. Feature Engine Parity ─────────────────────────────────────────
PARITY_STATUS="unknown"
LOCAL_MD5="null"
HF_MD5="null"
HF_LINES=0
HF_BYTES=0
ENGINE_VERSION="unknown"

if [ -f "$HF_ENGINE" ]; then
    HF_MD5=$(md5sum "$HF_ENGINE" | awk '{print $1}')
    HF_LINES=$(wc -l < "$HF_ENGINE")
    HF_BYTES=$(wc -c < "$HF_ENGINE")
    ENGINE_VERSION=$(grep 'ENGINE_VERSION' "$HF_ENGINE" | head -1 | grep -oP '"[^"]+"' | tr -d '"' || echo "unknown")
fi

if [ -f "$LOCAL_ENGINE" ]; then
    LOCAL_MD5=$(md5sum "$LOCAL_ENGINE" | awk '{print $1}')
    if [ "$LOCAL_MD5" = "$HF_MD5" ]; then
        PARITY_STATUS="match"
    else
        PARITY_STATUS="mismatch"
    fi
else
    PARITY_STATUS="local_missing"
    LOCAL_MD5="null"
fi

# ── 2. Feature Count ──────────────────────────────────────────────────
CATEGORY_COUNT=0
FEATURE_ESTIMATE=0

if [ -f "$HF_ENGINE" ]; then
    CATEGORY_COUNT=$(grep -c '^\s*[0-9]\+\.' "$HF_ENGINE" 2>/dev/null || echo 0)
    # Count feature names.append() calls as feature count proxy
    FEATURE_ESTIMATE=$(grep -c 'names\.append\|feat_names\.append' "$HF_ENGINE" 2>/dev/null || echo 0)
fi

# ── 3. Phantom Game Detection ─────────────────────────────────────────
PHANTOM_COUNT=0
PHANTOM_GAMES="[]"

if [ -f "$PICKS_FILE" ]; then
    PHANTOM_RESULT=$(python3 - << 'PYEOF'
import json, sys
from pathlib import Path

picks_file = Path("/home/termius/mon-ipad/data/nba-agent/latest-picks.json")
if not picks_file.exists():
    print('{"count": 0, "games": []}')
    sys.exit(0)

try:
    data = json.loads(picks_file.read_text())
    games = data.get("games", [])
    phantoms = []
    for g in games:
        home = g.get("home", g.get("home_team", ""))
        away = g.get("away", g.get("away_team", ""))
        if home and away and home == away:
            phantoms.append({
                "game": f"{away} @ {home}",
                "market_implied": g.get("market_implied", 0),
                "model_prob": g.get("home_win_prob", 0),
                "edge": g.get("edge", 0)
            })
    print(json.dumps({"count": len(phantoms), "games": phantoms}))
except Exception as e:
    print(json.dumps({"count": -1, "error": str(e), "games": []}))
PYEOF
)
    PHANTOM_COUNT=$(echo "$PHANTOM_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['count'])" 2>/dev/null || echo 0)
    PHANTOM_GAMES=$(echo "$PHANTOM_RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d.get('games', [])))" 2>/dev/null || echo "[]")
fi

# ── 4. Odds Sanity Check ──────────────────────────────────────────────
SANITY_VIOLATIONS=0
SANITY_DETAILS="[]"

if [ -f "$PICKS_FILE" ]; then
    SANITY_RESULT=$(python3 - << 'PYEOF'
import json, sys
from pathlib import Path

picks_file = Path("/home/termius/mon-ipad/data/nba-agent/latest-picks.json")
if not picks_file.exists():
    print('{"violations": 0, "details": []}')
    sys.exit(0)

try:
    data = json.loads(picks_file.read_text())
    games = data.get("games", [])
    violations = []
    for g in games:
        home = g.get("home", g.get("home_team", ""))
        away = g.get("away", g.get("away_team", ""))
        model_prob = g.get("home_win_prob", 0)
        market_implied = g.get("market_implied", 0)
        if model_prob > 0 and market_implied > 0:
            gap = abs(model_prob - market_implied)
            if gap > 0.50:
                violations.append({
                    "game": f"{away} @ {home}",
                    "model_prob": round(model_prob, 4),
                    "market_implied": round(market_implied, 4),
                    "gap": round(gap, 4)
                })
    print(json.dumps({"violations": len(violations), "details": violations}))
except Exception as e:
    print(json.dumps({"violations": -1, "error": str(e), "details": []}))
PYEOF
)
    SANITY_VIOLATIONS=$(echo "$SANITY_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['violations'])" 2>/dev/null || echo 0)
    SANITY_DETAILS=$(echo "$SANITY_RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d.get('details', [])))" 2>/dev/null || echo "[]")
fi

# ── 5. Test Suite ─────────────────────────────────────────────────────
TEST_PASS_RATE=0.0
TEST_TOTAL=0
TEST_PASSED=0

if [ -f "$ROOT/scripts/agents/test_data_leakage.py" ]; then
    TEST_OUTPUT=$(timeout 30 python3 "$ROOT/scripts/agents/test_data_leakage.py" 2>&1 || true)
    TEST_TOTAL=$(echo "$TEST_OUTPUT" | grep -oP 'Total:\s+\K[0-9]+' || echo 0)
    TEST_PASSED=$(echo "$TEST_OUTPUT" | grep -oP 'Passed:\s+\K[0-9]+' || echo 0)
    if [ "$TEST_TOTAL" -gt 0 ] 2>/dev/null; then
        TEST_PASS_RATE=$(python3 -c "print(round($TEST_PASSED / $TEST_TOTAL, 4))" 2>/dev/null || echo 0.0)
    fi
fi

# ── 6. Current Brier ─────────────────────────────────────────────────
BEST_BRIER="null"
HEALTH_FILE="$ROOT/data/agent-health.json"
HEALTH_FILE2="$ROOT/data/health-status.json"

for hf in "$HEALTH_FILE" "$HEALTH_FILE2"; do
    if [ -f "$hf" ]; then
        BEST_BRIER=$(python3 -c "
import json
with open('$hf') as f:
    d = json.load(f)
v = d.get('best_brier', d.get('brier', None))
print(v if v is not None else 'null')
" 2>/dev/null || echo null)
        if [ "$BEST_BRIER" != "null" ]; then break; fi
    fi
done

# ── 7. Determine overall health ───────────────────────────────────────
HEALTH="ok"
CRITICAL_ISSUES="[]"

ISSUES_LIST=""
if [ "$PHANTOM_COUNT" -gt 0 ] 2>/dev/null; then
    HEALTH="critical"
    ISSUES_LIST="${ISSUES_LIST}\"BUG-001: ${PHANTOM_COUNT} phantom game(s) in latest-picks.json\","
fi
if [ "$SANITY_VIOLATIONS" -gt 0 ] 2>/dev/null; then
    [ "$HEALTH" != "critical" ] && HEALTH="warning"
    ISSUES_LIST="${ISSUES_LIST}\"BUG-002: ${SANITY_VIOLATIONS} odds sanity violation(s) (|model-market|>0.50)\","
fi
if [ "$PARITY_STATUS" != "match" ]; then
    [ "$HEALTH" = "ok" ] && HEALTH="warning"
    ISSUES_LIST="${ISSUES_LIST}\"WARN: Engine parity status=${PARITY_STATUS}\","
fi

# Strip trailing comma
ISSUES_LIST="${ISSUES_LIST%,}"
CRITICAL_ISSUES="[${ISSUES_LIST}]"

# ── Output JSON ───────────────────────────────────────────────────────
cat > "$DATA_OUT/karpathy-output.json" << JSONEOF
{
  "department": "engineering",
  "timestamp": "$TIMESTAMP",
  "iteration": $ITERATION,
  "health": "$HEALTH",
  "critical_issues": $CRITICAL_ISSUES,
  "parity_check": {
    "status": "$PARITY_STATUS",
    "local_path": "features/engine.py",
    "hf_path": "hf-space/features/engine.py",
    "local_md5": "$LOCAL_MD5",
    "hf_md5": "$HF_MD5",
    "hf_lines": $HF_LINES,
    "hf_bytes": $HF_BYTES,
    "engine_version": "$ENGINE_VERSION"
  },
  "feature_count": {
    "category_count": $CATEGORY_COUNT,
    "feature_append_calls": $FEATURE_ESTIMATE,
    "declared_version": "$ENGINE_VERSION"
  },
  "phantom_games": {
    "count": $PHANTOM_COUNT,
    "games": $PHANTOM_GAMES
  },
  "odds_sanity": {
    "violations": $SANITY_VIOLATIONS,
    "threshold": 0.50,
    "details": $SANITY_DETAILS
  },
  "test_suite": {
    "total": $TEST_TOTAL,
    "passed": $TEST_PASSED,
    "pass_rate": $TEST_PASS_RATE
  },
  "best_brier": $BEST_BRIER
}
JSONEOF

# Print summary to stdout (for cron log / foreground use)
echo "=== ENGINEERING LOOP iter=$ITERATION ==="
echo "  Health:       $HEALTH"
echo "  Parity:       $PARITY_STATUS (engine $ENGINE_VERSION, ${HF_LINES} lines)"
echo "  Feature ~cnt: $FEATURE_ESTIMATE appends across $CATEGORY_COUNT categories"
echo "  Phantom games: $PHANTOM_COUNT"
echo "  Odds sanity:   $SANITY_VIOLATIONS violations"
echo "  Tests:        $TEST_PASSED/$TEST_TOTAL passed (rate=$TEST_PASS_RATE)"
echo "  Best Brier:   $BEST_BRIER"
echo "  Output:       $DATA_OUT/karpathy-output.json"

# Exit non-zero if critical
if [ "$HEALTH" = "critical" ]; then
    exit 2
elif [ "$HEALTH" = "warning" ]; then
    exit 1
fi
exit 0
