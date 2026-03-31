#!/bin/bash
# ══════════════════════════════════════════════════════════════
# NOMOS42 INFRA AGENT — Autonomous GPU Infrastructure Manager
# ══════════════════════════════════════════════════════════════
# Monitors, launches, restarts ALL evolution platforms:
#   - HF Spaces (10 NBA + 4 Political)
#   - Kaggle GPU kernels (NBA + Political)
#   - Modal serverless GPU (NBA)
#   - Keepalive pings
#
# Run: crontab -e → */30 * * * * /home/termius/mon-ipad/scripts/infra-agent.sh
# Or:  bash scripts/infra-agent.sh          (manual run)
# ══════════════════════════════════════════════════════════════
set -uo pipefail
export PATH="$PATH:/home/termius/.local/bin"

LOG="/home/termius/mon-ipad/logs/infra-agent.log"
STATUS_FILE="/home/termius/mon-ipad/data/infra-status.json"
mkdir -p "$(dirname "$LOG")" "$(dirname "$STATUS_FILE")"

source /home/termius/mon-ipad/.env.local 2>/dev/null

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $1" | tee -a "$LOG"; }
now_epoch() { date +%s; }

log "═══ INFRA AGENT CYCLE START ═══"

# ── Counters ──
TOTAL=0; HEALTHY=0; RESTARTED=0; FAILED=0

# ══════════════════════════════════════════════════════════════
# 1. HF SPACES — Check all NBA + Political islands
# ══════════════════════════════════════════════════════════════

declare -A SPACES=(
  # NBA islands
  ["S10_nba"]="https://nomos42-nba-quant.hf.space"
  ["S11_nba"]="https://nomos42-nba-quant-2.hf.space"
  ["S12_nba"]="https://nomos42-nba-evo-3.hf.space"
  ["S13_nba"]="https://nomos42-nba-evo-4.hf.space"
  ["S14_nba"]="https://nomos42-nba-evo-5.hf.space"
  ["S15_nba"]="https://nomos42-nba-evo-6.hf.space"
  # Political islands
  ["P1_pol"]="https://nomos42-political-alpha.hf.space"
  ["P2_pol"]="https://nomos42-political-alpha-2.hf.space"
  ["P3_pol"]="https://nomos42-political-alpha-3.hf.space"
  ["P4_pol"]="https://nomos42-political-alpha-4.hf.space"
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

KAGGLE_NBA_STATUS=$(check_kaggle "alexismoret6/nba-karpathy-loop" "/home/termius/mon-ipad/scripts/kaggle" "NBA")
KAGGLE_POL_STATUS=$(check_kaggle "alexismoret6/political-alpha-karpathy-loop" "/home/termius/nomos-political-alpha/scripts/kaggle" "Political")

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
    cd /home/termius/nomos-nba-agent && nohup modal run scripts/modal_karpathy.py --iterations 200 --budget 300 >> "$LOG" 2>&1 &
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

cat > "$STATUS_FILE" << STATUSEOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "summary": {
    "total": $TOTAL,
    "healthy": $HEALTHY,
    "restarted": $RESTARTED,
    "failed": $FAILED
  },
  "hf_spaces": $HF_STATUS_JSON,
  "kaggle": {
    "nba": "$KAGGLE_NBA_STATUS",
    "political": "$KAGGLE_POL_STATUS"
  },
  "modal": {
    "nba": "$MODAL_STATUS"
  }
}
STATUSEOF

# ══════════════════════════════════════════════════════════════
# 5. Summary
# ══════════════════════════════════════════════════════════════

log "═══ INFRA AGENT SUMMARY: $HEALTHY/$TOTAL healthy, $RESTARTED restarted, $FAILED failed ═══"

# Alert if too many failures
if [ "$FAILED" -gt 3 ]; then
  log "⚠️  HIGH FAILURE RATE: $FAILED platforms down!"
fi
