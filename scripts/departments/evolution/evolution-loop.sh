#!/bin/bash
# Department: EVOLUTION (D3) — Karpathy Loop
# Pattern: read metrics → detect stagnation → analyze diversity → recommend → write JSON
# Metric: best_brier, diversity_score, stagnation_count, cross_pollination_candidates
# Max runtime: 5 minutes
set -euo pipefail

DEPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$(dirname "$(dirname "$DEPT_DIR")")")"

# Input files
SWARM_FILE="$ROOT/data/swarm-metrics.json"
AGENT_HEALTH="$ROOT/data/agent-health.json"
HEALTH_STATUS="$ROOT/data/health-status.json"
CROSS_POLL="$ROOT/data/cross-pollination/report-$(date +%Y-%m-%d).json"
KARPATHY_BEST="$ROOT/data/karpathy/nba-best-config.json"

# Output file
OUTPUT_DIR="$ROOT/data/departments/evolution"
OUTPUT_FILE="$OUTPUT_DIR/karpathy-output.json"
mkdir -p "$OUTPUT_DIR"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# ─── Extract island data from agent-health.json ───────────────────────────────
extract_island_data() {
    local file="$1"
    if [[ ! -f "$file" ]]; then
        echo "null"
        return
    fi
    python3 - "$file" <<'PYEOF'
import json, sys
data = json.load(open(sys.argv[1]))
spaces = data.get("projects", {}).get("nba", {}).get("spaces", {})
result = {}
for sid, info in spaces.items():
    result[sid] = {
        "brier": info.get("brier"),
        "generation": info.get("generation"),
        "model": info.get("model"),
        "stagnation_cycles": info.get("stagnation_cycles", 0),
        "status": info.get("status", "UNKNOWN")
    }
print(json.dumps(result))
PYEOF
}

# ─── Extract stagnation info from agent-health.json (authoritative source) ────
extract_stagnation() {
    local file="$1"
    if [[ ! -f "$file" ]]; then
        echo "[]"
        return
    fi
    python3 - "$file" <<'PYEOF'
import json, sys
data = json.load(open(sys.argv[1]))
# agent-health uses projects.nba.spaces structure
spaces = data.get("projects", {}).get("nba", {}).get("spaces", {})
# Also try health-status nba_fleet.islands fallback
if not spaces:
    islands_alt = data.get("nba_fleet", {}).get("islands", {})
    spaces = {k: {"stagnation_cycles": v.get("stagnation", 0), "brier": v.get("brier")}
              for k, v in islands_alt.items()}
stagnant = []
for sid, info in spaces.items():
    stag = info.get("stagnation_cycles", 0)
    if stag >= 5:
        stagnant.append({
            "island": sid,
            "stagnation_cycles": stag,
            "brier": info.get("brier"),
            "severity": "HIGH" if stag >= 15 else "MEDIUM" if stag >= 8 else "LOW",
            "recommended_action": "diversify" if stag >= 15 else "boost_mutation"
        })
stagnant.sort(key=lambda x: x["stagnation_cycles"], reverse=True)
print(json.dumps(stagnant))
PYEOF
}

# ─── Calculate diversity score from island data ───────────────────────────────
calc_diversity() {
    local health_file="$1"
    local agent_file="$2"
    if [[ ! -f "$agent_file" ]]; then
        echo "0.5"
        return
    fi
    python3 - "$agent_file" <<'PYEOF'
import json, sys
data = json.load(open(sys.argv[1]))
spaces = data.get("projects", {}).get("nba", {}).get("spaces", {})

models = [v.get("model", "unknown") for v in spaces.values()]
briers = [v.get("brier") for v in spaces.values() if v.get("brier")]

# Model diversity: unique model types / total islands
model_diversity = len(set(models)) / max(len(models), 1)

# Brier diversity: coefficient of variation (lower is less diverse)
if len(briers) > 1:
    avg = sum(briers) / len(briers)
    std = (sum((b - avg)**2 for b in briers) / len(briers)) ** 0.5
    brier_cv = std / avg if avg > 0 else 0
else:
    brier_cv = 0

# Composite diversity score: model variety weighted 60%, brier spread 40%
# brier_cv of 0.01 = 1% spread, scale to 0-1 where 0.02+ = 1.0
brier_diversity = min(brier_cv / 0.02, 1.0)
score = (0.6 * model_diversity) + (0.4 * brier_diversity)
print(f"{score:.3f}")
PYEOF
}

# ─── Get best Brier and fleet metrics ─────────────────────────────────────────
get_fleet_metrics() {
    local file="$1"
    if [[ ! -f "$file" ]]; then
        echo '{"best_brier": null, "fleet_avg": null, "best_island": null}'
        return
    fi
    python3 - "$file" <<'PYEOF'
import json, sys
data = json.load(open(sys.argv[1]))
spaces = data.get("projects", {}).get("nba", {}).get("spaces", {})
briers = {k: v.get("brier") for k, v in spaces.items() if v.get("brier")}
if not briers:
    print('{"best_brier": null, "fleet_avg": null, "best_island": null}')
    sys.exit(0)
best_island = min(briers, key=briers.get)
best_brier = briers[best_island]
fleet_avg = sum(briers.values()) / len(briers)
total_gens = sum(v.get("generation", 0) for v in spaces.values())
print(json.dumps({
    "best_brier": round(best_brier, 5),
    "fleet_avg": round(fleet_avg, 5),
    "best_island": best_island,
    "total_generations": total_gens,
    "island_count": len(spaces)
}))
PYEOF
}

# ─── Get cross-pollination candidates ─────────────────────────────────────────
get_xpoll_candidates() {
    local agent_file="$1"
    if [[ ! -f "$agent_file" ]]; then
        echo "[]"
        return
    fi
    python3 - "$agent_file" <<'PYEOF'
import json, sys
data = json.load(open(sys.argv[1]))
spaces = data.get("projects", {}).get("nba", {}).get("spaces", {})
briers = {k: v.get("brier") for k, v in spaces.items() if v.get("brier")}
if len(briers) < 2:
    print("[]")
    sys.exit(0)
fleet_avg = sum(briers.values()) / len(briers)
candidates = []
for sid, brier in briers.items():
    if brier < fleet_avg:
        target_islands = [t for t, b in briers.items() if b > fleet_avg]
        for target in target_islands[:2]:
            candidates.append({
                "source": sid,
                "source_brier": round(brier, 5),
                "target": target,
                "target_brier": round(briers[target], 5),
                "potential_gain": round(briers[target] - brier, 5)
            })
candidates.sort(key=lambda x: x["potential_gain"], reverse=True)
print(json.dumps(candidates[:3]))
PYEOF
}

# ─── Check if improvement needed (compare to previous output) ─────────────────
check_improved() {
    local current_best="$1"
    local prev_file="$2"
    if [[ ! -f "$prev_file" ]] || [[ -z "$current_best" ]] || [[ "$current_best" == "null" ]]; then
        echo "false"
        return
    fi
    python3 - "$prev_file" "$current_best" <<'PYEOF'
import json, sys
try:
    prev = json.load(open(sys.argv[1]))
    prev_best = prev.get("best_brier") or prev.get("fleet_summary", {}).get("fleet_best_brier") or prev.get("fleet_metrics", {}).get("best_brier")
    current = float(sys.argv[2])
    if prev_best and current < prev_best:
        print("true")
    else:
        print("false")
except:
    print("false")
PYEOF
}

# ─── Main execution ───────────────────────────────────────────────────────────
echo "[D3-EVOLUTION] Starting Karpathy loop at $TIMESTAMP" >&2

ISLAND_DATA=$(extract_island_data "$AGENT_HEALTH")
STAGNATION=$(extract_stagnation "$AGENT_HEALTH")
DIVERSITY_SCORE=$(calc_diversity "$HEALTH_STATUS" "$AGENT_HEALTH")
FLEET_METRICS=$(get_fleet_metrics "$AGENT_HEALTH")
XPOLL_CANDIDATES=$(get_xpoll_candidates "$AGENT_HEALTH")

BEST_BRIER=$(echo "$FLEET_METRICS" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('best_brier','null'))" 2>/dev/null || echo "null")
FLEET_AVG=$(echo "$FLEET_METRICS" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('fleet_avg','null'))" 2>/dev/null || echo "null")
BEST_ISLAND=$(echo "$FLEET_METRICS" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('best_island','null'))" 2>/dev/null || echo "null")
TOTAL_GENS=$(echo "$FLEET_METRICS" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('total_generations',0))" 2>/dev/null || echo "0")

IMPROVED=$(check_improved "$BEST_BRIER" "$OUTPUT_FILE")
STAGNANT_COUNT=$(echo "$STAGNATION" | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d))" 2>/dev/null || echo "0")

# ─── Get Karpathy local best if available ─────────────────────────────────────
KARPATHY_BRIER="null"
KARPATHY_MODEL="null"
if [[ -f "$KARPATHY_BEST" ]]; then
    KARPATHY_BRIER=$(python3 -c "import json; d=json.load(open('$KARPATHY_BEST')); print(d.get('best_brier','null'))" 2>/dev/null || echo "null")
    KARPATHY_MODEL=$(python3 -c "import json; d=json.load(open('$KARPATHY_BEST')); print(d.get('model_type','null'))" 2>/dev/null || echo "null")
fi

# ─── Build recommendations from stagnation + diversity ────────────────────────
RECOMMENDATIONS=$(python3 - "$STAGNATION" "$DIVERSITY_SCORE" "$AGENT_HEALTH" <<'PYEOF'
import json, sys

stagnation = json.loads(sys.argv[1])
diversity_score = float(sys.argv[2])
agent_file = sys.argv[3]

recs = []

# Stagnation recommendations
for s in stagnation:
    sid = s["island"]
    stag = s["stagnation_cycles"]
    sev = s["severity"]
    if sev == "HIGH":
        recs.append({
            "type": "stagnation_critical",
            "island": sid,
            "action": "diversify",
            "command": f"POST /api/config {{\"command\": \"diversify\"}} → {sid}",
            "reason": f"{sid} stagnant for {stag} cycles — CRITICAL. Send diversify command immediately.",
            "priority": 1
        })
    elif sev == "MEDIUM":
        recs.append({
            "type": "stagnation_medium",
            "island": sid,
            "action": "boost_mutation",
            "command": f"POST /api/config {{\"command\": \"boost_mutation\"}} → {sid}",
            "reason": f"{sid} stagnant for {stag} cycles — MEDIUM. Boost mutation to escape local minimum.",
            "priority": 2
        })

# Diversity recommendations
if diversity_score < 0.4:
    recs.append({
        "type": "low_diversity",
        "action": "inject_model_diversity",
        "reason": f"Fleet diversity score {diversity_score:.2f} is LOW. Check for RF monoculture — force specialist models back to their designated architectures.",
        "priority": 2
    })

# Model drift check
try:
    data = json.load(open(agent_file))
    spaces = data.get("projects", {}).get("nba", {}).get("spaces", {})
    specialist_map = {
        "S12": "extra_trees",
        "S13": "catboost",
        "S14": "lightgbm"
    }
    for sid, expected_model in specialist_map.items():
        actual = spaces.get(sid, {}).get("model", "")
        if actual and actual != expected_model and actual != "xgboost_brier":
            recs.append({
                "type": "model_drift",
                "island": sid,
                "expected_model": expected_model,
                "actual_model": actual,
                "action": "inject_specialist_config",
                "reason": f"{sid} specialist role drift: expected {expected_model}, got {actual}. Restore specialist to improve fleet diversity.",
                "priority": 2
            })
except Exception:
    pass

recs.sort(key=lambda x: x["priority"])
print(json.dumps(recs))
PYEOF
)

echo "[D3-EVOLUTION] Analysis complete — writing output" >&2

# ─── Write JSON output ─────────────────────────────────────────────────────────
cat > "$OUTPUT_FILE" <<EOF
{
  "department": "evolution",
  "timestamp": "$TIMESTAMP",
  "iteration": $([ -f "$OUTPUT_FILE" ] && python3 -c "import json; d=json.load(open('$OUTPUT_FILE')); print(d.get('iteration',0)+1)" 2>/dev/null || echo 1),
  "islands": $ISLAND_DATA,
  "fleet_metrics": $FLEET_METRICS,
  "stagnation_detected": $STAGNATION,
  "stagnant_count": $STAGNANT_COUNT,
  "diversity_score": $DIVERSITY_SCORE,
  "cross_pollination_candidates": $XPOLL_CANDIDATES,
  "karpathy_local": {
    "best_brier": $KARPATHY_BRIER,
    "model_type": "$KARPATHY_MODEL"
  },
  "recommendations": $RECOMMENDATIONS,
  "improved": $IMPROVED,
  "best_brier": $BEST_BRIER,
  "fleet_avg_brier": $FLEET_AVG,
  "best_island": "$BEST_ISLAND",
  "total_generations": $TOTAL_GENS,
  "status": "completed"
}
EOF

# ─── Console output for guardian orchestrator ─────────────────────────────────
python3 - "$OUTPUT_FILE" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))
print(json.dumps({
    "status": d["status"],
    "department": d["department"],
    "metric": "best_brier",
    "best_brier": d.get("best_brier"),
    "fleet_avg_brier": d.get("fleet_avg_brier"),
    "best_island": d.get("best_island"),
    "total_generations": d.get("total_generations"),
    "stagnant_count": d.get("stagnant_count", 0),
    "diversity_score": d.get("diversity_score"),
    "improved": d.get("improved", False),
    "recommendations_count": len(d.get("recommendations", []))
}))
PYEOF
