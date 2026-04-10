#!/usr/bin/env bash
# swarm-metrics-collector.sh
# Collects all swarm agent metrics and writes to data/swarm-metrics.json
# Run via cron or manually. No ML. No heavy compute. Pure data reading.
#
# Usage:
#   ./scripts/agents/swarm-metrics-collector.sh
#   ./scripts/agents/swarm-metrics-collector.sh --quiet   (no stdout, just write JSON)
#
# Cron (every 4h, aligned to O1 brain cycle):
#   0 0,4,8,12,16,20 * * * /home/lahargnedebartoli/mon-ipad/scripts/agents/swarm-metrics-collector.sh --quiet

set -euo pipefail

REPO_ROOT="/home/lahargnedebartoli/mon-ipad"
POLITICAL_ROOT="/home/lahargnedebartoli/nomos-political-alpha"
RGWA_ROOT="/home/lahargnedebartoli/rgwa"
OUTPUT_FILE="${REPO_ROOT}/data/swarm-metrics.json"
ATR_BRIER="0.21570"
QUIET=0
[[ "${1:-}" == "--quiet" ]] && QUIET=1

log() { [[ $QUIET -eq 0 ]] && echo "[swarm-metrics] $*" || true; }
ts() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
epoch() { date -u +%s; }

# ─────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────

# Read a JSON field from a file using python (no jq dependency assumption)
# Returns raw value: strings without quotes, numbers as-is
jget() {
    local file="$1" field="$2" default="${3:-null}"
    python3 -c "
import json, sys
try:
    with open('$file') as f:
        d = json.load(f)
    keys = '$field'.split('.')
    v = d
    for k in keys:
        v = v[k]
    # Print raw: strings unquoted, everything else as-is
    if isinstance(v, str):
        print(v)
    else:
        print(json.dumps(v))
except Exception:
    print('$default')
" 2>/dev/null || echo "${default}"
}

# Count lines matching pattern in file
count_matches() {
    local file="$1" pattern="$2"
    grep -c "${pattern}" "${file}" 2>/dev/null || echo 0
}

# Age of file in hours (float)
file_age_hours() {
    local file="$1"
    if [[ ! -f "${file}" ]]; then echo 9999; return; fi
    local mtime now age_sec
    mtime=$(stat -c %Y "${file}" 2>/dev/null || stat -f %m "${file}" 2>/dev/null || echo 0)
    now=$(epoch)
    age_sec=$(( now - mtime ))
    python3 -c "print(round(${age_sec}/3600.0, 2))"
}

# HTTP check: returns 1 if URL responds with 200, else 0
http_ok() {
    local url="$1"
    curl -s -o /dev/null -w "%{http_code}" --max-time 10 "${url}" 2>/dev/null | grep -q "200" && echo 1 || echo 0
}

# Status: GREEN/YELLOW/RED based on thresholds
# status_band <value> <red_max_or_min> <green_min_or_max> <direction: higher_is_better|lower_is_better>
status_band() {
    local val="$1" red_thresh="$2" green_thresh="$3" direction="${4:-higher_is_better}"
    python3 -c "
val = float('${val}')
red = float('${red_thresh}')
green = float('${green_thresh}')
if '${direction}' == 'higher_is_better':
    if val >= green: print('GREEN')
    elif val >= red: print('YELLOW')
    else: print('RED')
else:
    if val <= green: print('GREEN')
    elif val <= red: print('YELLOW')
    else: print('RED')
" 2>/dev/null || echo "UNKNOWN"
}

# ─────────────────────────────────────────────────────────
# COLLECT METRICS
# ─────────────────────────────────────────────────────────

log "Starting swarm metrics collection at $(ts)"
COLLECT_TS="$(ts)"
declare -A M  # metrics dict (bash 4+)

# ── O1: Brain ─────────────────────────────────────────────
log "  O1: Brain..."
HEALTH_FILE="${REPO_ROOT}/data/health-status.json"
AGENT_HEALTH="${REPO_ROOT}/data/agent-health.json"

O1_LAST_ACTION_TS="$(jget "${HEALTH_FILE}" "timestamp" "unknown")"
O1_SPACES_UP="$(jget "${AGENT_HEALTH}" "summary.spaces" "unknown")"
O1_ISSUES="$(jget "${AGENT_HEALTH}" "summary.issues" "0")"
O1_STATUS="$(jget "${AGENT_HEALTH}" "summary.status" "UNKNOWN")"
O1_HEALTH_AGE="$(file_age_hours "${AGENT_HEALTH}")"

# ── R1: Research Analyst ──────────────────────────────────
log "  R1: Research Analyst..."
PROPOSALS_FILE="${REPO_ROOT}/data/research/latest-improvements-2026-03-31.json"
R1_PROPOSALS_FILE_EXISTS=0
[[ -f "${PROPOSALS_FILE}" ]] && R1_PROPOSALS_FILE_EXISTS=1
R1_PROPOSALS_AGE="$(file_age_hours "${PROPOSALS_FILE}")"

# Count research proposal files in data/research/
R1_PROPOSAL_COUNT="$(find "${REPO_ROOT}/data/research/" -name "*.json" 2>/dev/null | wc -l | tr -d ' ')"

# ── E1: Feature Engineer ───────────────────────────────────
log "  E1: Feature Engineer..."
# engine.py lives in hf-space/features/engine.py (not features/engine.py)
ENGINE_FILE="${REPO_ROOT}/hf-space/features/engine.py"
E1_FEATURE_CATS=0
E1_ENGINE_VERSION="unknown"
if [[ -f "${ENGINE_FILE}" ]]; then
    # Extract cat count and version from ENGINE_VERSION line (e.g. v3.0-43cat)
    _EV_RESULT="$(python3 - "${ENGINE_FILE}" << 'EVEOF'
import re, sys
path = sys.argv[1]
with open(path) as f:
    content = f.read()
m = re.search(r'ENGINE_VERSION\s*=\s*["\']([^"\']+)', content)
if m:
    ver = m.group(1)
    n = re.search(r'-(\d+)cat', ver)
    print(ver)
    print(n.group(1) if n else "0")
else:
    print("unknown")
    print("0")
EVEOF
)"
    E1_ENGINE_VERSION="$(echo "${_EV_RESULT}" | head -1)"
    E1_FEATURE_CATS="$(echo "${_EV_RESULT}" | tail -1)"
fi
E1_ENGINE_AGE="$(file_age_hours "${ENGINE_FILE}")"

# ── E2: Evolution Optimizer ─────────────────────────────────
log "  E2: Evolution Optimizer..."
EVAL_FILE="${REPO_ROOT}/data/nba-agent/latest-eval.json"
E2_CURRENT_BRIER="$(jget "${EVAL_FILE}" "brier_score" "null")"
E2_ATR_BRIER="${ATR_BRIER}"
E2_BRIER_VS_ATR="null"
E2_BRIER_STATUS="UNKNOWN"
if [[ "${E2_CURRENT_BRIER}" != "null" ]]; then
    E2_BRIER_VS_ATR="$(python3 -c "print(round(float('${E2_CURRENT_BRIER}') - float('${ATR_BRIER}'), 5))")"
    # Positive = worse than ATR, negative = better
    E2_BRIER_STATUS="$(status_band "${E2_BRIER_VS_ATR}" "0.005" "0.0" "lower_is_better")"
fi

# ── E3: Predictions ─────────────────────────────────────────
log "  E3: Predictions..."
PREDS_FILE="${REPO_ROOT}/data/nba-agent/predictions-today.json"
E3_PREDS_EXISTS=0
E3_PREDS_COUNT=0
E3_PREDS_AGE="$(file_age_hours "${PREDS_FILE}")"
if [[ -f "${PREDS_FILE}" ]]; then
    E3_PREDS_EXISTS=1
    E3_PREDS_COUNT="$(python3 -c "
import json
with open('${PREDS_FILE}') as f:
    d = json.load(f)
if isinstance(d, list): print(len(d))
elif isinstance(d, dict): print(len(d.get('predictions', d.get('games', []))))
else: print(0)
" 2>/dev/null || echo 0)"
fi

# ── E5: Data Pipeline ──────────────────────────────────────
log "  E5: Data Pipeline..."
ODDS_FILE="${REPO_ROOT}/data/nba-agent/live-odds.json"
E5_ODDS_AGE="$(file_age_hours "${ODDS_FILE}")"
E5_ODDS_STATUS="$(status_band "${E5_ODDS_AGE}" "3.0" "1.0" "lower_is_better")"

# ── V1: Island Coordinator ─────────────────────────────────
log "  V1: Island Coordinator..."
ISLAND_URLS=(
    "https://nomos42-nba-quant.hf.space"
    "https://nomos42-nba-quant-2.hf.space"
    "https://nomos42-nba-evo-3.hf.space"
    "https://nomos42-nba-evo-4.hf.space"
    "https://nomos42-nba-evo-5.hf.space"
    "https://nomos42-nba-evo-6.hf.space"
)
ISLAND_IDS=("S10" "S11" "S12" "S13" "S14" "S15")
V1_ISLANDS_UP=0
declare -A ISLAND_STATUS
declare -A ISLAND_BRIER
declare -A ISLAND_GEN
declare -A ISLAND_STAG

# Read from agent-health.json (already cached — avoids 6 HTTP calls on every run)
for ISLAND_ID in "${ISLAND_IDS[@]}"; do
    STA="$(jget "${AGENT_HEALTH}" "projects.nba.spaces.${ISLAND_ID}.status" "UNKNOWN")"
    BR="$(jget "${AGENT_HEALTH}" "projects.nba.spaces.${ISLAND_ID}.brier" "null")"
    GN="$(jget "${AGENT_HEALTH}" "projects.nba.spaces.${ISLAND_ID}.generation" "0")"
    ST="$(jget "${AGENT_HEALTH}" "projects.nba.spaces.${ISLAND_ID}.stagnation_cycles" "0")"
    ISLAND_STATUS[$ISLAND_ID]="${STA}"
    ISLAND_BRIER[$ISLAND_ID]="${BR}"
    ISLAND_GEN[$ISLAND_ID]="${GN}"
    ISLAND_STAG[$ISLAND_ID]="${ST}"
    [[ "${STA}" == "UP" ]] && V1_ISLANDS_UP=$(( V1_ISLANDS_UP + 1 ))
done

V1_STATUS="$(status_band "${V1_ISLANDS_UP}" "4" "6" "higher_is_better")"

# Best island Brier
V1_BEST_BRIER="$(python3 -c "
briers = [float(x) for x in ['${ISLAND_BRIER[S10]}','${ISLAND_BRIER[S11]}','${ISLAND_BRIER[S12]}','${ISLAND_BRIER[S13]}','${ISLAND_BRIER[S14]}','${ISLAND_BRIER[S15]}'] if x != 'null']
print(min(briers) if briers else 'null')
" 2>/dev/null || echo "null")"

# ── B5: Evaluator ─────────────────────────────────────────
log "  B5: Evaluator..."
BANK_FILE="${REPO_ROOT}/data/nba-agent/bankroll-state.json"
B5_ROI="$(jget "${BANK_FILE}" "roi_pct" "null")"
B5_BALANCE="$(jget "${BANK_FILE}" "balance" "null")"
B5_SHARPE="$(jget "${BANK_FILE}" "sharpe_ratio" "null")"
B5_WIN_RATE="$(jget "${BANK_FILE}" "win_rate_pct" "null")"
B5_TOTAL_BETS="$(jget "${BANK_FILE}" "total_bets" "0")"
B5_ROI_STATUS="UNKNOWN"
if [[ "${B5_ROI}" != "null" ]]; then
    B5_ROI_STATUS="$(status_band "${B5_ROI}" "0.0" "5.0" "higher_is_better")"
fi

# ── I1/I2: Infrastructure ─────────────────────────────────
log "  I1/I2: Infrastructure..."
INFRA_FILE="${REPO_ROOT}/data/infra-status.json"
I1_DATA_SERVER_STATUS="$(jget "${AGENT_HEALTH}" "infra.data_server.backtest-results.json" "UNKNOWN")"
I1_TELEGRAM_STATUS="$(jget "${AGENT_HEALTH}" "infra.telegram.brain" "UNKNOWN")"
I1_INFRA_AGE="$(file_age_hours "${INFRA_FILE}")"
I2_BOT_STATUS="$(jget "${INFRA_FILE}" "bots.nomos42bot" "UNKNOWN" 2>/dev/null || echo "UNKNOWN")"

# ── Q1: Quality Tracker ────────────────────────────────────
log "  Q1: Quality Tracker..."
Q1_CURRENT_BRIER="${E2_CURRENT_BRIER}"
Q1_ATR="${ATR_BRIER}"
Q1_GAP="${E2_BRIER_VS_ATR}"
Q1_EVAL_AGE="$(file_age_hours "${EVAL_FILE}")"

# ── Political Alpha ────────────────────────────────────────
log "  Political Alpha..."
POL_ENGINE_FILE="${POLITICAL_ROOT}/features/political_engine.py"
POL_CATS=0
POL_ENGINE_VERSION="unknown"
POL_ENGINE_AGE=9999
if [[ -f "${POL_ENGINE_FILE}" ]]; then
    _PEV_RESULT="$(python3 - "${POL_ENGINE_FILE}" << 'PEVEOF'
import re, sys
path = sys.argv[1]
with open(path) as f:
    content = f.read()
m = re.search(r'ENGINE_VERSION\s*=\s*["\']([^"\']+)', content)
if m:
    ver = m.group(1)
    n = re.search(r'-(\d+)cat', ver)
    print(ver)
    print(n.group(1) if n else "0")
else:
    print("unknown")
    print("0")
PEVEOF
)"
    POL_ENGINE_VERSION="$(echo "${_PEV_RESULT}" | head -1)"
    POL_CATS="$(echo "${_PEV_RESULT}" | tail -1)"
    POL_ENGINE_AGE="$(file_age_hours "${POL_ENGINE_FILE}")"
fi
# Political Kaggle status from agent-health
POL_KAGGLE_STATUS="$(jget "${AGENT_HEALTH}" "projects.political.kaggle.political-alpha-karpathy-loop.status" "UNKNOWN")"

# ── RGWA ──────────────────────────────────────────────────
log "  RGWA..."
RGWA_QUALITY_FILE="${RGWA_ROOT}/data/gallery/quality-scores.json"
RGWA_QUALITY_AVG="null"
RGWA_QUALITY_AGE=9999
if [[ -f "${RGWA_QUALITY_FILE}" ]]; then
    RGWA_QUALITY_AGE="$(file_age_hours "${RGWA_QUALITY_FILE}")"
    RGWA_QUALITY_AVG="$(python3 -c "
import json
with open('${RGWA_QUALITY_FILE}') as f:
    d = json.load(f)
scores = d if isinstance(d, list) else d.get('scores', [])
if scores: print(round(sum(float(x) for x in scores)/len(scores), 2))
else: print('null')
" 2>/dev/null || echo "null")"
fi

# ── Forge Factory ─────────────────────────────────────────
log "  Forge Factory..."
FORGE_USERS_DIR="${REPO_ROOT}/forge-users"
FORGE_USER_COUNT=0
FORGE_PRODUCTS_BUILT=0
if [[ -d "${FORGE_USERS_DIR}" ]]; then
    FORGE_USER_COUNT="$(find "${FORGE_USERS_DIR}" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')"
    FORGE_PRODUCTS_BUILT="$(find "${FORGE_USERS_DIR}" -name "product-brief.json" 2>/dev/null | wc -l | tr -d ' ')"
fi

# ─────────────────────────────────────────────────────────
# COMPUTE PRIORITY ALERTS
# ─────────────────────────────────────────────────────────

ALERTS=()

# Priority 1: Existential
[[ "${V1_ISLANDS_UP}" -lt 5 ]] && ALERTS+=("P1-CRITICAL: Only ${V1_ISLANDS_UP}/6 islands UP")
[[ "${E5_ODDS_STATUS}" == "RED" ]] && ALERTS+=("P1-CRITICAL: Odds data stale ${E5_ODDS_AGE}h")
[[ "${E2_BRIER_STATUS}" == "RED" ]] && ALERTS+=("P1-CRITICAL: Brier regression detected (${E2_CURRENT_BRIER} vs ATR ${ATR_BRIER})")

# Priority 2: Strategic
[[ "${B5_ROI}" != "null" ]] && python3 -c "exit(0 if float('${B5_ROI}') >= 0 else 1)" 2>/dev/null && true || ALERTS+=("P2-STRATEGIC: ROI negative (${B5_ROI}%)")
[[ "${V1_ISLANDS_UP}" -lt 6 ]] && [[ "${V1_ISLANDS_UP}" -ge 4 ]] && ALERTS+=("P2-STRATEGIC: ${V1_ISLANDS_UP}/6 islands UP")

# Priority 3: Growth
[[ "${E1_FEATURE_CATS}" -lt 44 ]] && ALERTS+=("P3-GROWTH: Feature engine at ${E1_FEATURE_CATS} cats, target 46+")

# Stagnation check
for ISLAND_ID in "${ISLAND_IDS[@]}"; do
    STAG="${ISLAND_STAG[$ISLAND_ID]}"
    [[ "${STAG}" -gt 20 ]] 2>/dev/null && ALERTS+=("P2-STRATEGIC: Island ${ISLAND_ID} stagnant ${STAG} cycles")
done

# ─────────────────────────────────────────────────────────
# BUILD JSON OUTPUT
# ─────────────────────────────────────────────────────────

# Sanitize all integer-typed variables to strip accidental newlines
E1_FEATURE_CATS="${E1_FEATURE_CATS//[$'\t\r\n ']}"
V1_ISLANDS_UP="${V1_ISLANDS_UP//[$'\t\r\n ']}"
POL_CATS="${POL_CATS//[$'\t\r\n ']}"
FORGE_USER_COUNT="${FORGE_USER_COUNT//[$'\t\r\n ']}"
FORGE_PRODUCTS_BUILT="${FORGE_PRODUCTS_BUILT//[$'\t\r\n ']}"
E3_PREDS_COUNT="${E3_PREDS_COUNT//[$'\t\r\n ']}"
B5_TOTAL_BETS="${B5_TOTAL_BETS//[$'\t\r\n ']}"
O1_ISSUES="${O1_ISSUES//[$'\t\r\n ']}"
R1_PROPOSAL_COUNT="${R1_PROPOSAL_COUNT//[$'\t\r\n ']}"
# Sanitize all float-typed variables
E5_ODDS_AGE="${E5_ODDS_AGE//[$'\t\r\n ']}"
E3_PREDS_AGE="${E3_PREDS_AGE//[$'\t\r\n ']}"
O1_HEALTH_AGE="${O1_HEALTH_AGE//[$'\t\r\n ']}"
Q1_EVAL_AGE="${Q1_EVAL_AGE//[$'\t\r\n ']}"
I1_INFRA_AGE="${I1_INFRA_AGE//[$'\t\r\n ']}"
R1_PROPOSALS_AGE="${R1_PROPOSALS_AGE//[$'\t\r\n ']}"
E1_ENGINE_AGE="${E1_ENGINE_AGE//[$'\t\r\n ']}"
POL_ENGINE_AGE="${POL_ENGINE_AGE//[$'\t\r\n ']}"
RGWA_QUALITY_AGE="${RGWA_QUALITY_AGE//[$'\t\r\n ']}"
for ISLAND_ID in "${ISLAND_IDS[@]}"; do
    ISLAND_STAG[$ISLAND_ID]="${ISLAND_STAG[$ISLAND_ID]//[$'\t\r\n ']}"
    ISLAND_GEN[$ISLAND_ID]="${ISLAND_GEN[$ISLAND_ID]//[$'\t\r\n ']}"
done

# Build alerts list
ALERTS_LIST=()
if [[ ${#ALERTS[@]} -gt 0 ]]; then
    ALERTS_LIST=("${ALERTS[@]}")
fi

# Pass all data to Python via environment variables (no shell interpolation in Python code)
export SMC_COLLECT_TS="${COLLECT_TS}"
export SMC_OUTPUT_FILE="${OUTPUT_FILE}"
export SMC_ATR_BRIER="${ATR_BRIER}"
export SMC_O1_HEALTH_AGE="${O1_HEALTH_AGE}"
export SMC_O1_SPACES_UP="${O1_SPACES_UP}"
export SMC_O1_ISSUES="${O1_ISSUES}"
export SMC_O1_STATUS="${O1_STATUS}"
export SMC_R1_PROPOSAL_COUNT="${R1_PROPOSAL_COUNT}"
export SMC_R1_PROPOSALS_AGE="${R1_PROPOSALS_AGE}"
export SMC_E1_FEATURE_CATS="${E1_FEATURE_CATS}"
export SMC_E1_ENGINE_VERSION="${E1_ENGINE_VERSION}"
export SMC_E1_ENGINE_AGE="${E1_ENGINE_AGE}"
export SMC_E2_CURRENT_BRIER="${E2_CURRENT_BRIER}"
export SMC_E2_BRIER_GAP="${E2_BRIER_VS_ATR}"
export SMC_E2_BRIER_STATUS="${E2_BRIER_STATUS}"
export SMC_E3_PREDS_COUNT="${E3_PREDS_COUNT}"
export SMC_E3_PREDS_AGE="${E3_PREDS_AGE}"
export SMC_E5_ODDS_AGE="${E5_ODDS_AGE}"
export SMC_E5_ODDS_STATUS="${E5_ODDS_STATUS}"
export SMC_V1_ISLANDS_UP="${V1_ISLANDS_UP}"
export SMC_V1_BEST_BRIER="${V1_BEST_BRIER}"
export SMC_V1_STATUS="${V1_STATUS}"
export SMC_ISLAND_S10_STATUS="${ISLAND_STATUS[S10]}"
export SMC_ISLAND_S10_BRIER="${ISLAND_BRIER[S10]}"
export SMC_ISLAND_S10_GEN="${ISLAND_GEN[S10]}"
export SMC_ISLAND_S10_STAG="${ISLAND_STAG[S10]}"
export SMC_ISLAND_S11_STATUS="${ISLAND_STATUS[S11]}"
export SMC_ISLAND_S11_BRIER="${ISLAND_BRIER[S11]}"
export SMC_ISLAND_S11_GEN="${ISLAND_GEN[S11]}"
export SMC_ISLAND_S11_STAG="${ISLAND_STAG[S11]}"
export SMC_ISLAND_S12_STATUS="${ISLAND_STATUS[S12]}"
export SMC_ISLAND_S12_BRIER="${ISLAND_BRIER[S12]}"
export SMC_ISLAND_S12_GEN="${ISLAND_GEN[S12]}"
export SMC_ISLAND_S12_STAG="${ISLAND_STAG[S12]}"
export SMC_ISLAND_S13_STATUS="${ISLAND_STATUS[S13]}"
export SMC_ISLAND_S13_BRIER="${ISLAND_BRIER[S13]}"
export SMC_ISLAND_S13_GEN="${ISLAND_GEN[S13]}"
export SMC_ISLAND_S13_STAG="${ISLAND_STAG[S13]}"
export SMC_ISLAND_S14_STATUS="${ISLAND_STATUS[S14]}"
export SMC_ISLAND_S14_BRIER="${ISLAND_BRIER[S14]}"
export SMC_ISLAND_S14_GEN="${ISLAND_GEN[S14]}"
export SMC_ISLAND_S14_STAG="${ISLAND_STAG[S14]}"
export SMC_ISLAND_S15_STATUS="${ISLAND_STATUS[S15]}"
export SMC_ISLAND_S15_BRIER="${ISLAND_BRIER[S15]}"
export SMC_ISLAND_S15_GEN="${ISLAND_GEN[S15]}"
export SMC_ISLAND_S15_STAG="${ISLAND_STAG[S15]}"
export SMC_B5_ROI="${B5_ROI}"
export SMC_B5_BALANCE="${B5_BALANCE}"
export SMC_B5_SHARPE="${B5_SHARPE}"
export SMC_B5_WIN_RATE="${B5_WIN_RATE}"
export SMC_B5_TOTAL_BETS="${B5_TOTAL_BETS}"
export SMC_B5_ROI_STATUS="${B5_ROI_STATUS}"
export SMC_Q1_EVAL_AGE="${Q1_EVAL_AGE}"
export SMC_I1_DATA_SERVER="${I1_DATA_SERVER_STATUS}"
export SMC_I1_TELEGRAM="${I1_TELEGRAM_STATUS}"
export SMC_I1_INFRA_AGE="${I1_INFRA_AGE}"
export SMC_POL_CATS="${POL_CATS}"
export SMC_POL_ENGINE_VERSION="${POL_ENGINE_VERSION}"
export SMC_POL_ENGINE_AGE="${POL_ENGINE_AGE}"
export SMC_POL_KAGGLE_STATUS="${POL_KAGGLE_STATUS}"
export SMC_RGWA_QUALITY_AVG="${RGWA_QUALITY_AVG}"
export SMC_RGWA_QUALITY_AGE="${RGWA_QUALITY_AGE}"
export SMC_FORGE_USER_COUNT="${FORGE_USER_COUNT}"
export SMC_FORGE_PRODUCTS="${FORGE_PRODUCTS_BUILT}"
# Alerts as newline-separated string
export SMC_ALERTS="$(printf '%s\n' "${ALERTS_LIST[@]+"${ALERTS_LIST[@]}"}")"

python3 << 'PYEOF'
import json, os

def flt(v):
    try: return float(v)
    except: return None

def intr(v):
    try: return int(v)
    except: return 0

def nulflt(v):
    if v in ("null", "", "None", None): return None
    return flt(v)

def nulstr(v):
    if v in ("null", "", "None", None): return None
    return v

e = os.environ

alerts_raw = e.get("SMC_ALERTS", "").strip()
alerts = [a for a in alerts_raw.splitlines() if a.strip()] if alerts_raw else []

def island(id_):
    return {
        "status": e.get(f"SMC_ISLAND_{id_}_STATUS", "UNKNOWN"),
        "brier": nulflt(e.get(f"SMC_ISLAND_{id_}_BRIER")),
        "gen": intr(e.get(f"SMC_ISLAND_{id_}_GEN", "0")),
        "stagnation_cycles": intr(e.get(f"SMC_ISLAND_{id_}_STAG", "0"))
    }

roi = nulflt(e.get("SMC_B5_ROI"))
roi_status = e.get("SMC_B5_ROI_STATUS", "UNKNOWN")
o1_status = e.get("SMC_O1_STATUS", "UNKNOWN")
o1_age = flt(e.get("SMC_O1_HEALTH_AGE", "9999")) or 9999
pol_cats = intr(e.get("SMC_POL_CATS", "0"))
rgwa_avg = nulflt(e.get("SMC_RGWA_QUALITY_AVG"))

data = {
    "collected_at": e.get("SMC_COLLECT_TS"),
    "version": "1.0",
    "products": {
        "nba": {
            "name": "NBA Quant AI",
            "layer1_strategy": {
                "agent": "O1",
                "name": "Brain / Strategy Definer",
                "metric": "decisions_actioned_per_cycle",
                "health_file_age_hours": flt(e.get("SMC_O1_HEALTH_AGE")),
                "spaces_summary": e.get("SMC_O1_SPACES_UP"),
                "open_issues": intr(e.get("SMC_O1_ISSUES", "0")),
                "system_status": o1_status,
                "status": "GREEN" if o1_status == "HEALTHY" else ("RED" if o1_age > 8 else "YELLOW")
            },
            "layer1_research": {
                "agent": "R1",
                "name": "Research Analyst",
                "metric": "research_proposals_per_week",
                "proposal_files_found": intr(e.get("SMC_R1_PROPOSAL_COUNT", "0")),
                "proposals_file_age_hours": flt(e.get("SMC_R1_PROPOSALS_AGE")),
                "status": "GREEN" if intr(e.get("SMC_R1_PROPOSAL_COUNT", "0")) >= 3 else "YELLOW"
            },
            "layer1_features": {
                "agent": "E1",
                "name": "Feature Engineer",
                "metric": "feature_categories_count",
                "current_categories": intr(e.get("SMC_E1_FEATURE_CATS", "0")),
                "engine_version": e.get("SMC_E1_ENGINE_VERSION", "unknown"),
                "engine_age_hours": flt(e.get("SMC_E1_ENGINE_AGE")),
                "target_categories": 46,
                "status": "GREEN" if intr(e.get("SMC_E1_FEATURE_CATS", "0")) >= 46 else "YELLOW"
            },
            "layer1_evolution": {
                "agent": "E2",
                "name": "Evolution Optimizer",
                "metric": "brier_vs_atr",
                "current_brier": nulflt(e.get("SMC_E2_CURRENT_BRIER")),
                "atr_brier": flt(e.get("SMC_ATR_BRIER")),
                "brier_gap": nulflt(e.get("SMC_E2_BRIER_GAP")),
                "status": e.get("SMC_E2_BRIER_STATUS", "UNKNOWN")
            },
            "layer1_predictions": {
                "agent": "E3",
                "name": "Predictions Agent",
                "metric": "predictions_posted_count",
                "predictions_today": intr(e.get("SMC_E3_PREDS_COUNT", "0")),
                "predictions_file_age_hours": flt(e.get("SMC_E3_PREDS_AGE")),
                "status": "GREEN" if intr(e.get("SMC_E3_PREDS_COUNT", "0")) > 0 else "YELLOW"
            },
            "layer1_data": {
                "agent": "E5",
                "name": "Data Pipeline",
                "metric": "odds_data_freshness_hours",
                "current_age_hours": flt(e.get("SMC_E5_ODDS_AGE")),
                "target_max_hours": 2.0,
                "status": e.get("SMC_E5_ODDS_STATUS", "UNKNOWN")
            },
            "layer1_islands": {
                "agent": "V1",
                "name": "Island Coordinator",
                "metric": "islands_active_count",
                "islands_up": intr(e.get("SMC_V1_ISLANDS_UP", "0")),
                "islands_total": 6,
                "best_island_brier": nulflt(e.get("SMC_V1_BEST_BRIER")),
                "island_detail": {
                    "S10": island("S10"),
                    "S11": island("S11"),
                    "S12": island("S12"),
                    "S13": island("S13"),
                    "S14": island("S14"),
                    "S15": island("S15")
                },
                "status": e.get("SMC_V1_STATUS", "UNKNOWN")
            },
            "layer1_betting": {
                "agent": "B5",
                "name": "Evaluator",
                "metric": "season_roi_pct",
                "roi_pct": roi,
                "bankroll_usd": nulflt(e.get("SMC_B5_BALANCE")),
                "sharpe_ratio": nulflt(e.get("SMC_B5_SHARPE")),
                "win_rate_pct": nulflt(e.get("SMC_B5_WIN_RATE")),
                "total_bets": intr(e.get("SMC_B5_TOTAL_BETS", "0")),
                "status": roi_status
            },
            "layer3_quality": {
                "agent": "Q1",
                "name": "Quality Tracker",
                "metric": "brier_vs_atr_gap",
                "current_brier": nulflt(e.get("SMC_E2_CURRENT_BRIER")),
                "atr": flt(e.get("SMC_ATR_BRIER")),
                "gap": nulflt(e.get("SMC_E2_BRIER_GAP")),
                "eval_file_age_hours": flt(e.get("SMC_Q1_EVAL_AGE")),
                "status": e.get("SMC_E2_BRIER_STATUS", "UNKNOWN")
            },
            "layer3_infra": {
                "agent": "I1",
                "name": "Fleet Manager",
                "metric": "fleet_services_status",
                "data_server_backtest": e.get("SMC_I1_DATA_SERVER", "UNKNOWN"),
                "telegram_brain": e.get("SMC_I1_TELEGRAM", "UNKNOWN"),
                "infra_file_age_hours": flt(e.get("SMC_I1_INFRA_AGE")),
                "status": "GREEN" if e.get("SMC_I1_TELEGRAM") == "ALIVE" else "RED"
            }
        },
        "political": {
            "name": "Political Alpha",
            "layer1_engine": {
                "agent": "V3",
                "name": "Political Evolution",
                "metric": "political_engine_categories_live",
                "categories": pol_cats,
                "engine_version": e.get("SMC_POL_ENGINE_VERSION", "unknown"),
                "engine_file_age_hours": flt(e.get("SMC_POL_ENGINE_AGE")),
                "target_categories": 25,
                "status": "GREEN" if pol_cats >= 22 else "YELLOW"
            },
            "layer1_kaggle": {
                "metric": "kaggle_session_status",
                "status": e.get("SMC_POL_KAGGLE_STATUS", "UNKNOWN"),
                "health": "GREEN" if e.get("SMC_POL_KAGGLE_STATUS") == "COMPLETE" else "RED"
            }
        },
        "rgwa": {
            "name": "RGWA Artistic Generation",
            "layer1_quality": {
                "agent": "quality-critic",
                "name": "Quality Critic",
                "metric": "avg_generation_quality_score",
                "current_avg": rgwa_avg,
                "target": 7.5,
                "quality_file_age_hours": flt(e.get("SMC_RGWA_QUALITY_AGE")),
                "status": "PLANNED" if rgwa_avg is None else ("GREEN" if rgwa_avg >= 7.5 else "YELLOW")
            }
        },
        "forge": {
            "name": "Forge Factory",
            "layer1_users": {
                "metric": "forge_users_total",
                "current": intr(e.get("SMC_FORGE_USER_COUNT", "0")),
                "target": 5,
                "products_built": intr(e.get("SMC_FORGE_PRODUCTS", "0")),
                "status": "GREEN" if intr(e.get("SMC_FORGE_USER_COUNT", "0")) >= 3 else (
                    "YELLOW" if intr(e.get("SMC_FORGE_USER_COUNT", "0")) >= 1 else "RED"
                )
            }
        }
    },
    "priority_alerts": alerts,
    "summary": {
        "total_alerts": len(alerts),
        "critical_alerts": len([a for a in alerts if "P1-CRITICAL" in a]),
        "islands_up": intr(e.get("SMC_V1_ISLANDS_UP", "0")),
        "best_brier": nulflt(e.get("SMC_V1_BEST_BRIER")),
        "atr_brier": flt(e.get("SMC_ATR_BRIER")),
        "season_roi_pct": roi,
        "feature_categories": intr(e.get("SMC_E1_FEATURE_CATS", "0")),
        "political_categories": pol_cats,
        "overall_health": "CRITICAL" if len([a for a in alerts if "P1-CRITICAL" in a]) > 0 else (
            "DEGRADED" if len(alerts) > 2 else "HEALTHY"
        )
    }
}

output_file = e.get("SMC_OUTPUT_FILE")
with open(output_file, "w") as f:
    json.dump(data, f, indent=2)

print(json.dumps(data["summary"], indent=2))
PYEOF

EXIT_CODE=$?
if [[ $EXIT_CODE -ne 0 ]]; then
    echo "[swarm-metrics] ERROR: JSON generation failed (exit ${EXIT_CODE})" >&2
    exit 1
fi

log "Metrics written to ${OUTPUT_FILE}"

if [[ $QUIET -eq 0 ]]; then
    echo ""
    echo "=== PRIORITY ALERTS ==="
    if [[ ${#ALERTS[@]} -eq 0 ]]; then
        echo "  None — all systems nominal"
    else
        for ALERT in "${ALERTS[@]}"; do
            echo "  ${ALERT}"
        done
    fi
    echo ""
    echo "=== ISLAND BRIER SCORES ==="
    for ISLAND_ID in "${ISLAND_IDS[@]}"; do
        printf "  %-4s  status=%-4s  brier=%s  gen=%s  stag=%s\n" \
            "${ISLAND_ID}" "${ISLAND_STATUS[$ISLAND_ID]}" "${ISLAND_BRIER[$ISLAND_ID]}" \
            "${ISLAND_GEN[$ISLAND_ID]}" "${ISLAND_STAG[$ISLAND_ID]}"
    done
    echo ""
    echo "=== KEY METRICS ==="
    echo "  NBA ATR Brier:    ${ATR_BRIER}"
    echo "  Best Island:      ${V1_BEST_BRIER}"
    echo "  Season ROI:       ${B5_ROI}%"
    echo "  Feature Engine:   ${E1_FEATURE_CATS} categories"
    echo "  Political Engine: ${POL_CATS} categories"
    echo "  Odds freshness:   ${E5_ODDS_AGE}h"
    echo ""
fi

log "Done."
