#!/bin/bash
# ══════════════════════════════════════════════════════════════
# NOMOS42 INFRA AGENT — Autonomous GPU Infrastructure Manager
# ══════════════════════════════════════════════════════════════
# Monitors, launches, restarts ALL evolution platforms:
#   - HF Spaces (6 NBA + 2 Political)
#   - Kaggle GPU kernels (NBA + Political)
#   - Modal serverless GPU (NBA)
#   - Keepalive pings
#
# Run: crontab -e → */30 * * * * /home/termius/mon-ipad/scripts/infra-agent.sh
# Or:  bash scripts/infra-agent.sh          (manual run)
# ══════════════════════════════════════════════════════════════
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
export PATH="$PATH:${HOME}/.local/bin"

LOG="${ROOT}/logs/infra-agent.log"
STATUS_FILE="${ROOT}/data/infra-status.json"
mkdir -p "$(dirname "$LOG")" "$(dirname "$STATUS_FILE")"

source "${ROOT}/.env.local" 2>/dev/null

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $1" | tee -a "$LOG" >&2; }
now_epoch() { date +%s; }

log "═══ INFRA AGENT CYCLE START ═══"

# ── Counters ──
TOTAL=0; HEALTHY=0; RESTARTED=0; FAILED=0

# ══════════════════════════════════════════════════════════════
# 1. HF SPACES — Check all NBA + Political islands
# ══════════════════════════════════════════════════════════════

declare -A SPACES=(
  # NBA islands (10 total — S10-S19)
  ["S10_nba"]="https://nomos42-nba-quant.hf.space"
  ["S11_nba"]="https://nomos42-nba-quant-2.hf.space"
  ["S12_nba"]="https://nomos42-nba-evo-3.hf.space"
  ["S13_nba"]="https://nomos42-nba-evo-4.hf.space"
  ["S14_nba"]="https://nomos42-nba-evo-5.hf.space"
  ["S15_nba"]="https://nomos42-nba-evo-6.hf.space"
  ["S16_nba"]="https://lbjlincoln26-nba-evo-s16.hf.space"
  ["S17_nba"]="https://lbjlincoln26-nba-evo-s17.hf.space"
  ["S18_nba"]="https://testforge42-nba-evo-s18.hf.space"
  ["S19_nba"]="https://testforge42-nba-evo-s19.hf.space"
  # Political islands (8 total — P1-P8)
  ["P1_pol"]="https://nomos42-political-alpha.hf.space"
  ["P2_pol"]="https://nomos42-political-alpha-2.hf.space"
  ["P3_pol"]="https://lbjlincoln-political-alpha-3.hf.space"
  ["P4_pol"]="https://lbjlincoln-political-alpha-4.hf.space"
  ["P5_pol"]="https://lbjlincoln-political-alpha-5.hf.space"
  ["P6_pol"]="https://lbjlincoln-political-alpha-6.hf.space"
  ["P7_pol"]="https://lbjlincoln-political-alpha-7.hf.space"
  ["P8_pol"]="https://lbjlincoln-political-alpha-8.hf.space"
)

HF_STATUS_JSON="{"

for NAME in $(echo "${!SPACES[@]}" | tr ' ' '\n' | sort); do
  URL="${SPACES[$NAME]}"
  TOTAL=$((TOTAL + 1))

  # Check /api/status
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 15 "$URL/api/status" 2>/dev/null)

  if [ "$HTTP_CODE" = "200" ]; then
    # Get best brier
    BRIER=$(curl -s --max-time 10 "$URL/api/status" 2>/dev/null | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin)
    print(d.get('best_brier', d.get('best', '?')))
except: print('?')
" 2>/dev/null)
    GEN=$(curl -s --max-time 10 "$URL/api/status" 2>/dev/null | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin)
    print(d.get('generation', d.get('gen', '?')))
except: print('?')
" 2>/dev/null)
    log "  ✓ $NAME: RUNNING (brier=$BRIER, gen=$GEN)"
    HEALTHY=$((HEALTHY + 1))
    HF_STATUS_JSON="$HF_STATUS_JSON\"$NAME\":{\"status\":\"running\",\"brier\":\"$BRIER\",\"gen\":\"$GEN\"},"
  else
    log "  ✗ $NAME: DOWN (HTTP $HTTP_CODE) — sending keepalive..."
    # Keepalive: just hit the root URL to wake it up
    curl -s --max-time 30 "$URL/" > /dev/null 2>&1
    FAILED=$((FAILED + 1))
    HF_STATUS_JSON="$HF_STATUS_JSON\"$NAME\":{\"status\":\"down\",\"http\":\"$HTTP_CODE\"},"
  fi
done

HF_STATUS_JSON="${HF_STATUS_JSON%,}}"

# ══════════════════════════════════════════════════════════════
# 2. KAGGLE — Check kernel status, relaunch if error/complete
# ══════════════════════════════════════════════════════════════

KAGGLE_NBA_STATUS="unknown"
KAGGLE_POL_STATUS="unknown"

check_kaggle() {
  local KERNEL="$1"
  local PUSH_DIR="$2"
  local NAME="$3"
  local RESULT=""

  TOTAL=$((TOTAL + 1))

  STATUS=$(kaggle kernels status "$KERNEL" 2>/dev/null | grep -oP 'KernelWorkerStatus\.\K\w+' || echo "UNKNOWN")

  case "$STATUS" in
    RUNNING)
      log "  ✓ Kaggle $NAME: RUNNING"
      HEALTHY=$((HEALTHY + 1))
      RESULT="running"
      ;;
    COMPLETE)
      log "  ↻ Kaggle $NAME: COMPLETE — relaunching..."
      (cd "$PUSH_DIR" && kaggle kernels push -p . > /dev/null 2>&1)
      RESTARTED=$((RESTARTED + 1))
      RESULT="relaunched"
      ;;
    ERROR|CANCEL*)
      log "  ↻ Kaggle $NAME: $STATUS — relaunching..."
      (cd "$PUSH_DIR" && kaggle kernels push -p . > /dev/null 2>&1)
      RESTARTED=$((RESTARTED + 1))
      RESULT="relaunched"
      ;;
    *)
      log "  ? Kaggle $NAME: $STATUS"
      FAILED=$((FAILED + 1))
      RESULT="$STATUS"
      ;;
  esac
  echo "$RESULT"
}

KAGGLE_NBA_STATUS=$(check_kaggle "alexismoret6/nba-karpathy-loop" "${ROOT}/scripts/kaggle" "NBA")
KAGGLE_POL_STATUS=$(check_kaggle "alexismoret6/political-alpha-karpathy-loop" "${ROOT}/../nomos-political-alpha/scripts/kaggle" "Political")

# ══════════════════════════════════════════════════════════════
# 3. MODAL — Check if running, launch if idle
# ══════════════════════════════════════════════════════════════

MODAL_STATUS="unknown"
TOTAL=$((TOTAL + 1))

MODAL_RUNNING=$(modal app list 2>/dev/null | grep "nba-karpathy" | grep -c "ephemeral" 2>/dev/null || true)
MODAL_RUNNING=${MODAL_RUNNING:-0}
MODAL_RUNNING=$(echo "$MODAL_RUNNING" | tr -d '[:space:]')

if [ "$MODAL_RUNNING" -gt 0 ]; then
  log "  ✓ Modal NBA: RUNNING ($MODAL_RUNNING active)"
  HEALTHY=$((HEALTHY + 1))
  MODAL_STATUS="running"
else
  # Check if we have GPU budget (Modal free tier: $30/mo)
  HOUR=$(date -u +%H)
  # Only auto-launch during off-peak (to conserve budget)
  if [ "$HOUR" -ge 2 ] && [ "$HOUR" -le 14 ]; then
    log "  ↻ Modal NBA: IDLE — launching 200 iterations..."
    cd "${ROOT}/../nomos-nba-agent" && nohup modal run scripts/modal_karpathy.py --iterations 200 --budget 300 >> "$LOG" 2>&1 &
    RESTARTED=$((RESTARTED + 1))
    MODAL_STATUS="launched"
  else
    log "  ○ Modal NBA: IDLE (peak hours, skipping auto-launch)"
    MODAL_STATUS="idle_peak"
  fi
fi

# ══════════════════════════════════════════════════════════════
# 4. Write status JSON
# ══════════════════════════════════════════════════════════════

# Defensive JSON emission: python3 handles string escaping (control chars,
# embedded newlines, etc.) so shell-captured outputs can never corrupt the file.
# Historical bug (2026-04-11): log() via tee-to-stdout was slurped into
# KAGGLE_*_STATUS command substitutions, embedding literal newlines and turning
# this file into invalid JSON for ~days, which silently broke /api/dashboard/home
# and /api/dashboard/infra on Vercel. Fix: log now goes to stderr AND we json-escape.
# IMPORTANT: export MUST come before the python call so os.environ sees the vars.
export HF_STATUS_JSON KAGGLE_NBA_STATUS KAGGLE_POL_STATUS MODAL_STATUS
TS_NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
export TS_NOW TOTAL HEALTHY RESTARTED FAILED
python3 - "$STATUS_FILE" <<'PYEOF'
import json, sys, os
hf_raw = os.environ.get('HF_STATUS_JSON') or '{}'
try:
    hf = json.loads(hf_raw)
except Exception:
    hf = {"_parse_error": hf_raw[:200]}

def last_line(name: str) -> str:
    v = os.environ.get(name) or 'unknown'
    lines = [l for l in v.strip().splitlines() if l.strip()]
    return lines[-1] if lines else 'unknown'

def as_int(name: str) -> int:
    try:
        return int(os.environ.get(name, '0') or 0)
    except ValueError:
        return 0

payload = {
    "timestamp": os.environ.get('TS_NOW', ''),
    "summary": {
        "total":     as_int('TOTAL'),
        "healthy":   as_int('HEALTHY'),
        "restarted": as_int('RESTARTED'),
        "failed":    as_int('FAILED'),
    },
    "hf_spaces": hf,
    "kaggle": {
        "nba":       last_line('KAGGLE_NBA_STATUS'),
        "political": last_line('KAGGLE_POL_STATUS'),
    },
    "modal": {
        "nba": last_line('MODAL_STATUS'),
    },
}
with open(sys.argv[1], 'w') as f:
    json.dump(payload, f, indent=2)
PYEOF

# ══════════════════════════════════════════════════════════════
# 5. TRADING FLOOR COUNCIL LOOP — KILLED (2026-04-06)
#    Replaced by: Hermes dept councils (hermes-runner.sh, cron every 4h)
#    + HF Space councils (9 spaces with Gemma4/Qwen3.5/DeepSeek)
# ══════════════════════════════════════════════════════════════

# Kill any lingering old loop processes
OLD_TF=$(pgrep -f "trading-floor-council-loop" 2>/dev/null | wc -l)
if [ "$OLD_TF" -gt 0 ]; then
  log "KILLING old trading-floor-council-loop ($OLD_TF processes)"
  pkill -f "trading-floor-council-loop" 2>/dev/null || true
fi
TOTAL=$((TOTAL + 1))

# ══════════════════════════════════════════════════════════════
# 6. Summary
# ══════════════════════════════════════════════════════════════

log "═══ INFRA AGENT SUMMARY: $HEALTHY/$TOTAL healthy, $RESTARTED restarted, $FAILED failed ═══"

# Alert if too many failures
if [ "$FAILED" -gt 3 ]; then
  log "⚠️  HIGH FAILURE RATE: $FAILED platforms down!"
fi
