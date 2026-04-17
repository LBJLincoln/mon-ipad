#!/bin/bash
# Nomos42 — Claude Code Session Launcher (Full Ecosystem)
# Usage:
#   ~/mon-ipad/scripts/claude-session.sh [--skip-perms]
#                                         [--project nba|rgwa|political|dashboard|all]
#                                         [--no-launch]   # status only, do not exec claude
#                                         [--quiet]       # skip status, launch immediately
#                                         [--no-probe]    # skip network probes (offline)
#                                         [--section hf|kaggle|gpu|db|repos|bots|crons|vercel|agents|forge]
#
# Complete status across ALL platforms:
#   HF Spaces (4 accounts, 24+ spaces), Kaggle (7 kernels + 1 dataset),
#   Modal, Colab, Lightning.ai, 2x Supabase, 2x Neo4j, 2x Pinecone,
#   Upstash Redis, 5 repos, 5 bots, crons, 5 Vercel sites,
#   4 Tracks (SCIENCE · PLATFORM · MARKET · CAPITAL), 2 live HF Trading Floors,
#   Fleet-matrix slot scoreboard (GPU/CPU specialization).

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ── Colors ──
R='\033[0;31m'; G='\033[0;32m'; Y='\033[0;33m'; B='\033[0;34m'
C='\033[0;36m'; W='\033[1;37m'; D='\033[0;90m'; M='\033[0;35m'; N='\033[0m'

# ── Parse args ──
SKIP_PERMS=""
PROJECT="nba"
NO_LAUNCH=""
QUIET=""
NO_PROBE=""
SECTION=""
for arg in "$@"; do
  case "$arg" in
    --skip-perms|--bypass|--yolo) SKIP_PERMS="--dangerously-skip-permissions" ;;
    --nba|--project=nba)       PROJECT="nba" ;;
    --rgwa|--project=rgwa)     PROJECT="rgwa" ;;
    --political|--project=political) PROJECT="political" ;;
    --dashboard|--project=dashboard) PROJECT="dashboard" ;;
    --all)                     PROJECT="all" ;;
    --no-launch|--dry-run)     NO_LAUNCH="1" ;;
    --quiet|--fast)            QUIET="1" ;;
    --no-probe|--offline)      NO_PROBE="1" ;;
    --section=*)               SECTION="${arg#--section=}" ;;
    -h|--help)
      grep -E '^# ' "$0" | sed 's/^# //' | head -20
      exit 0
      ;;
  esac
done

# ── Source all env files (safely, even under set -u) ──
set +u
for envfile in \
  "${ROOT}/../nomos-nba-agent/.env.local" \
  "${ROOT}/.env.local" \
  "${ROOT}/../rgwa/.env.local" \
  "${ROOT}/../nomos-political-alpha/.env.local"; do
  [ -f "$envfile" ] && source "$envfile" 2>/dev/null || true
done
set -u

# ── Helpers ──
ok()     { printf "  ${G}%-2s${N} %-32s %s\n" "OK" "$1" "$2"; }
warn()   { printf "  ${Y}%-2s${N} %-32s %s\n" "!!" "$1" "$2"; }
fail()   { printf "  ${R}%-2s${N} %-32s %s\n" "XX" "$1" "$2"; }
info()   { printf "  ${D}%-2s${N} %-32s %s\n" "--" "$1" "$2"; }
header() { echo ""; echo -e "${B}━━━ $1 ━━━${N}"; }

# Show a section only if --section unset OR matches
show() { [ -z "$SECTION" ] || [ "$SECTION" = "$1" ]; }

# Quiet mode: straight to launch
if [ -n "$QUIET" ]; then
  case "$PROJECT" in
    nba)       WORKDIR="${ROOT}" ;;
    rgwa)      WORKDIR="${ROOT}/../rgwa" ;;
    political) WORKDIR="${ROOT}/../nomos-political-alpha" ;;
    dashboard) WORKDIR="${ROOT}/../nomos-dashboard" ;;
    all)       WORKDIR="${ROOT}" ;;
  esac
  cd "$WORKDIR"
  [ -n "$NO_LAUNCH" ] && exit 0
  exec claude $SKIP_PERMS
fi

# ── Temp dir for parallel curl results ──
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

# ── Counters ──
OK_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0
count_ok()   { OK_COUNT=$((OK_COUNT+1)); ok   "$@"; }
count_warn() { WARN_COUNT=$((WARN_COUNT+1)); warn "$@"; }
count_fail() { FAIL_COUNT=$((FAIL_COUNT+1)); fail "$@"; }

echo ""
echo -e "${W}╔════════════════════════════════════════════════════════════════════╗${N}"
echo -e "${W}║              NOMOS42 — Full Ecosystem Dashboard                    ║${N}"
printf  "${W}║              %-53s ║${N}\n" "$(date -u '+%Y-%m-%d %H:%M UTC')  (v21 · 4 tracks)"
echo -e "${W}╚════════════════════════════════════════════════════════════════════╝${N}"

# ══════════════════════════════════════════════════════════════════
# 1. HF SPACES — ALL ACCOUNTS (parallel curl)
# ══════════════════════════════════════════════════════════════════

# NBA evo islands (8) + political (2) + infra (1) + 2 trading floors + RGWA (1) + pol legacy (1) = 15 live targets
declare -A ACTIVE_SPACES=(
  # NBA Islands (Nomos42)
  ["S10"]="nomos42-nba-quant"
  ["S11"]="nomos42-nba-quant-2"
  ["S12"]="nomos42-nba-evo-3"
  ["S13"]="nomos42-nba-evo-4"
  ["S14"]="nomos42-nba-evo-5"
  ["S15"]="nomos42-nba-evo-6"
  # NBA Islands (LBJLincoln26)
  ["S16"]="lbjlincoln26-nba-evo-s16"
  ["S17"]="lbjlincoln26-nba-evo-s17"
  # Political Islands (Nomos42)
  ["P1"]="nomos42-political-alpha"
  ["P2"]="nomos42-political-alpha-2"
  # Infra/Other (Nomos42)
  ["INFRA"]="nomos42-nomos42-infra-brain"
  # Live Trading Floors (LBJLincoln26) — HF-first, ground-truth engines
  ["NBA_TF"]="lbjlincoln26-nba-llm-trading-floor"
  ["POL_TF"]="lbjlincoln26-political-llm-trading-floor"
  ["GATEWAY"]="lbjlincoln26-llm-gateway"
  # RGWA (LBJLincoln)
  ["RGWA"]="lbjlincoln-nomos-rgwa"
  # Political (LBJLincoln26)
  ["P0_26"]="lbjlincoln26-nomos-political-alpha"
)

if [ -z "$NO_PROBE" ] && show hf; then
  for TAG in "${!ACTIVE_SPACES[@]}"; do
    SLUG="${ACTIVE_SPACES[$TAG]}"
    (
      RESP=$(curl -s --max-time 6 "https://${SLUG}.hf.space/api/status" 2>/dev/null)
      HTTP=$(curl -s -o /dev/null -w "%{http_code}" --max-time 6 "https://${SLUG}.hf.space/" 2>/dev/null)
      if [ -n "$RESP" ] && echo "$RESP" | python3 -c "import sys,json; json.load(sys.stdin)" 2>/dev/null; then
        BRIER=$(echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('best_brier', d.get('best','')))" 2>/dev/null)
        GEN=$(echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('generation', d.get('gen','')))" 2>/dev/null)
        MODEL=$(echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('best_model_type',''))" 2>/dev/null)
        echo "UP|${BRIER}|${GEN}|${MODEL}" > "$TMPDIR/$TAG"
      elif [ "$HTTP" = "200" ] || [ "$HTTP" = "302" ]; then
        echo "UP|||" > "$TMPDIR/$TAG"
      else
        echo "DOWN|$HTTP||" > "$TMPDIR/$TAG"
      fi
    ) &
  done
  wait
fi

# ── Display: Nomos42 account (12 spaces) ──
if show hf; then
  header "HF: Nomos42 (12 spaces) — Primary account"

  echo -e "  ${C}NBA Evolution Islands (8):${N}"
  for TAG in S10 S11 S12 S13 S14 S15 S16 S17; do
    if [ -f "$TMPDIR/$TAG" ]; then
      IFS='|' read -r STATUS BRIER GEN MODEL < "$TMPDIR/$TAG"
      ROLES=""
      case $TAG in
        S10) ROLES="exploitation" ;; S11) ROLES="exploration" ;; S12) ROLES="extra_trees" ;;
        S13) ROLES="catboost" ;; S14) ROLES="lightgbm" ;; S15) ROLES="wide_search" ;;
        S16) ROLES="gradient_boost" ;; S17) ROLES="ensemble" ;;
      esac
      if [ "$STATUS" = "UP" ]; then
        DETAIL=""
        [ -n "$BRIER" ] && DETAIL="brier=$BRIER"
        [ -n "$GEN" ] && DETAIL="$DETAIL gen=$GEN"
        [ -n "$MODEL" ] && DETAIL="$DETAIL [$MODEL]"
        count_ok "$TAG ($ROLES)" "$DETAIL"
      else
        count_fail "$TAG ($ROLES)" "DOWN (HTTP $BRIER)"
      fi
    else
      count_warn "$TAG" "no response"
    fi
  done

  echo -e "  ${C}Political Evolution Islands (2):${N}"
  for TAG in P1 P2; do
    if [ -f "$TMPDIR/$TAG" ]; then
      IFS='|' read -r STATUS BRIER GEN MODEL < "$TMPDIR/$TAG"
      ROLES=""
      case $TAG in
        P1) ROLES="exploitation" ;; P2) ROLES="exploration" ;;
      esac
      if [ "$STATUS" = "UP" ]; then
        DETAIL=""
        [ -n "$BRIER" ] && DETAIL="brier=$BRIER"
        [ -n "$GEN" ] && DETAIL="$DETAIL gen=$GEN"
        count_ok "$TAG ($ROLES)" "$DETAIL"
      else
        count_fail "$TAG ($ROLES)" "DOWN (HTTP $BRIER)"
      fi
    else
      count_warn "$TAG" "no response"
    fi
  done

  echo -e "  ${C}Other (1):${N}"
  for TAG in INFRA; do
    LABEL="nomos42-infra-brain"
    if [ -f "$TMPDIR/$TAG" ]; then
      IFS='|' read -r STATUS BRIER GEN MODEL < "$TMPDIR/$TAG"
      [ "$STATUS" = "UP" ] && count_ok "$LABEL" "RUNNING" || count_fail "$LABEL" "DOWN"
    else
      count_warn "$LABEL" "no response"
    fi
  done

  echo -e "  ${C}Trading Floors (HF-first — ground truth):${N}"
  for TAG in NBA_TF POL_TF; do
    SLUG="${ACTIVE_SPACES[$TAG]}"
    LABEL=""
    case $TAG in
      NBA_TF) LABEL="nba-llm-trading-floor" ;;
      POL_TF) LABEL="political-llm-trading-floor" ;;
    esac
    TF_RESP=$(curl -s --max-time 8 "https://${SLUG}.hf.space/api/status" 2>/dev/null)
    if [ -n "$TF_RESP" ] && echo "$TF_RESP" | python3 -c "import sys,json; json.load(sys.stdin)" 2>/dev/null; then
      TF_LINE=$(echo "$TF_RESP" | python3 -c "
import sys, json
d = json.load(sys.stdin)
run  = d.get('running', False)
stop = d.get('stopped', False)
done = d.get('completed', False)
dp   = d.get('days_processed', d.get('days_completed', '?'))
dt   = d.get('days_total', '?')
agents = d.get('agents', {}) or {}
calls = sum(a.get('llm_calls', 0) for a in agents.values()) if agents else d.get('llm_calls', 0)
okn   = sum(a.get('llm_ok', 0)    for a in agents.values()) if agents else d.get('llm_ok', 0)
bets  = sum(a.get('total_bets',0) for a in agents.values()) if agents else d.get('total_bets', 0)
state = 'done' if done else ('running' if run else ('stopped' if stop else 'idle'))
ratio = f'{okn}/{calls}' if calls else 'na'
print(f'{state} days={dp}/{dt} llm_ok={ratio} bets={bets}')
" 2>/dev/null || echo "parse-err")
      count_ok "$LABEL" "$TF_LINE"
    else
      count_fail "$LABEL" "DOWN or not ready"
    fi
  done

  # LLM Gateway probe
  if [ -f "$TMPDIR/GATEWAY" ]; then
    IFS='|' read -r STATUS BRIER GEN MODEL < "$TMPDIR/GATEWAY"
    [ "$STATUS" = "UP" ] && count_ok "llm-gateway" "UP (11 models)" || count_fail "llm-gateway" "DOWN"
  fi

  # ── Display: LBJLincoln account (3 spaces) ──
  header "HF: LBJLincoln (3 spaces) — Legacy/RGWA"
  if [ -f "$TMPDIR/RGWA" ]; then
    IFS='|' read -r STATUS BRIER GEN MODEL < "$TMPDIR/RGWA"
    [ "$STATUS" = "UP" ] && count_ok "nomos-rgwa" "RUNNING (docker)" || count_fail "nomos-rgwa" "DOWN"
  else
    count_warn "nomos-rgwa" "no response"
  fi
  info "nomos-nba-quant"   "OLD (migrated to Nomos42)"
  info "nomos-nba-quant-2" "OLD (migrated to Nomos42)"

  # ── Display: LBJLincoln26 account (10 spaces) ──
  header "HF: LBJLincoln26 (10 spaces) — NBA S16/S17 + Political"
  echo -e "  ${C}Already counted above (S16, S17 → primary NBA evo group)${N}"
  if [ -f "$TMPDIR/P0_26" ]; then
    IFS='|' read -r STATUS BRIER GEN MODEL < "$TMPDIR/P0_26"
    [ "$STATUS" = "UP" ] && count_ok "nomos-political-alpha" "RUNNING" || info "nomos-political-alpha" "PAUSED/OLD"
  else
    info "nomos-political-alpha" "PAUSED/OLD"
  fi
  info "nba-evo-3"           "OLD (migrated to Nomos42)"
  info "nba-evo-4"           "OLD (migrated to Nomos42)"
  info "nomos-rag-engine-*"  "5 PAUSED (RAG dead)"
fi

# ══════════════════════════════════════════════════════════════════
# 2. KAGGLE — 7 kernels + 1 dataset
# ══════════════════════════════════════════════════════════════════
if show kaggle; then
  header "Kaggle (alexismoret6) — 7 kernels + 1 dataset"

  KAGGLE_KERNELS=(
    "alexismoret6/nba-karpathy-loop:NBA Karpathy Loop"
    "alexismoret6/political-alpha-karpathy-loop:Political Karpathy"
    "alexismoret6/nba-strategy-confrontation-tree-only:Strategy Confrontation"
    "alexismoret6/nba-season-backtest-real-odds-multi-market:Season Backtest"
    "alexismoret6/nba-quant-gpu-v2-tabicl:GPU v2 TabICL"
    "alexismoret6/nba-quant-gpu-evolution-v2:GPU Evolution v2"
    "alexismoret6/nba-quant-gpu-runner:GPU Runner"
  )

  if [ -z "$NO_PROBE" ] && command -v kaggle >/dev/null 2>&1; then
    for ENTRY in "${KAGGLE_KERNELS[@]}"; do
      IFS=':' read -r KERNEL LABEL <<< "$ENTRY"
      STATUS=$(kaggle kernels status "$KERNEL" 2>/dev/null | grep -oP 'KernelWorkerStatus\.\K\w+' || echo "?")
      case "$STATUS" in
        RUNNING)  count_ok   "$LABEL" "RUNNING" ;;
        COMPLETE) info       "$LABEL" "COMPLETE (idle)" ;;
        ERROR)    count_fail "$LABEL" "ERROR" ;;
        CANCEL*)  count_warn "$LABEL" "CANCELLED" ;;
        *)        info       "$LABEL" "$STATUS" ;;
      esac
    done
  else
    info "kaggle CLI" "not probed (--no-probe or CLI missing)"
  fi

  echo -e "  ${C}Datasets:${N}"
  info "nba-2025-26-odds" "12KB (manually refreshed)"
fi

# ══════════════════════════════════════════════════════════════════
# 3. GPU PLATFORMS — Modal, Colab, Lightning, Codespaces
# ══════════════════════════════════════════════════════════════════
if show gpu; then
  header "GPU Platforms"

  # Modal
  if [ -z "$NO_PROBE" ] && command -v modal >/dev/null 2>&1; then
    MODAL_COUNT=$(modal app list 2>/dev/null | grep -c "nba-karpathy\|nomos" 2>/dev/null || echo "0")
    MODAL_COUNT=$(echo "$MODAL_COUNT" | tr -d '[:space:]')
    if [ "${MODAL_COUNT:-0}" -gt 0 ]; then
      count_ok "Modal (lbjlincoln)" "RUNNING ($MODAL_COUNT active)"
    else
      info "Modal (lbjlincoln)" "IDLE (\$30/mo free tier)"
    fi
  else
    info "Modal (lbjlincoln)" "not probed"
  fi

  # Colab
  COLAB_STATE="${ROOT}/data/colab-state.json"
  if [ -f "$COLAB_STATE" ]; then
    COLAB_TS=$(python3 -c "import json,sys; d=json.load(open('$COLAB_STATE')); print(d.get('timestamp','?'))" 2>/dev/null || echo "?")
    ok "Google Colab" "Last: $COLAB_TS"
  else
    info "Google Colab" "Not running (T4 on-demand)"
  fi

  # Lightning.ai
  info "Lightning.ai (moretalexis24)" "22 GPU-hr/mo"

  # GitHub Codespaces
  if [ -z "$NO_PROBE" ] && command -v gh >/dev/null 2>&1; then
    CS_STATUS=$(gh codespace list --json name,state 2>/dev/null | python3 -c "
import sys,json
try:
    cs = json.load(sys.stdin)
    if not cs: print('NONE')
    else:
        active = [c for c in cs if c.get('state') == 'Available']
        print(f'{len(active)} active / {len(cs)} total')
except: print('?')
" 2>/dev/null || echo "CLI unavailable")
    if echo "$CS_STATUS" | grep -q "active"; then
      count_ok "GitHub Codespaces" "$CS_STATUS"
    else
      info "GitHub Codespaces" "$CS_STATUS"
    fi
  fi

  # MCP Compute Server (local port 8082)
  MCP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 "http://localhost:8082/health" 2>/dev/null || echo 000)
  if [ "$MCP_CODE" = "200" ]; then
    count_ok "MCP Compute Server" "UP (port 8082)"
  else
    info "MCP Compute Server" "not running (start: python3 scripts/mcp-compute-server.py)"
  fi

  # Bloomberg API (port 8042)
  BB_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 "http://localhost:8042/health" 2>/dev/null || echo 000)
  if [ "$BB_CODE" = "200" ]; then
    count_ok "Bloomberg API" "UP (port 8042)"
  else
    info "Bloomberg API" "not running (cron-driven)"
  fi
fi

# ══════════════════════════════════════════════════════════════════
# 4. DATABASES
# ══════════════════════════════════════════════════════════════════
if show db && [ -z "$NO_PROBE" ]; then
  header "Databases (7 services)"

  echo -e "  ${C}Supabase (2 projects):${N}"
  SB2_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "https://xivvnrkbtuhfsphtmmtv.supabase.co/rest/v1/" -H "apikey: ${SUPABASE_ANON_KEY_2:-none}" 2>/dev/null || echo 000)
  if [ "$SB2_CODE" = "200" ] || [ "$SB2_CODE" = "401" ]; then
    count_ok "xivvnr (active)" "UP — 56 tables"
  else
    count_warn "xivvnr (active)" "HTTP $SB2_CODE (use pooler)"
  fi
  SB1_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "https://ayqviqmxifzmhphiqfmj.supabase.co/rest/v1/" -H "apikey: ${SUPABASE_API_KEY:-none}" 2>/dev/null || echo 000)
  if [ "$SB1_CODE" = "402" ] || [ "$SB1_CODE" = "000" ]; then
    info "ayqviq (old primary)" "PAUSED (402)"
  else
    info "ayqviq (old primary)" "HTTP $SB1_CODE"
  fi

  echo -e "  ${C}Neo4j (2 instances):${N}"
  NEO4J_1=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "https://38c949a2.databases.neo4j.io" 2>/dev/null || echo 000)
  if [ "$NEO4J_1" = "200" ] || [ "$NEO4J_1" = "401" ]; then
    count_ok "38c949a2 (knowledge graph)" "UP"
  else
    info "38c949a2 (knowledge graph)" "HTTP $NEO4J_1 (bolt)"
  fi
  NEO4J_2=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "https://48d838a5.databases.neo4j.io" 2>/dev/null || echo 000)
  if [ "$NEO4J_2" = "200" ] || [ "$NEO4J_2" = "401" ]; then
    count_ok "48d838a5 (secondary)" "UP"
  else
    info "48d838a5 (secondary)" "HTTP $NEO4J_2"
  fi

  echo -e "  ${C}Vector DBs (2 Pinecone):${N}"
  PC1_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "${PINECONE_HOST:-https://pinecone.io}/describe_index_stats" -H "Api-Key: ${PINECONE_API_KEY:-none}" 2>/dev/null || echo 000)
  if [ "$PC1_CODE" = "200" ]; then
    count_ok "Pinecone #1 (sota-rag)" "UP"
  else
    info "Pinecone #1 (sota-rag)" "HTTP $PC1_CODE"
  fi
  info "Pinecone #2" "Secondary key configured"

  echo -e "  ${C}Cache:${N}"
  REDIS_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "${UPSTASH_REDIS_REST_URL:-https://upstash.io}" -H "Authorization: Bearer ${UPSTASH_REDIS_REST_TOKEN:-none}" 2>/dev/null || echo 000)
  if [ "$REDIS_CODE" = "200" ] || [ "$REDIS_CODE" = "401" ]; then
    count_ok "Upstash Redis" "UP"
  else
    info "Upstash Redis" "HTTP $REDIS_CODE"
  fi
fi

# ══════════════════════════════════════════════════════════════════
# 5. REPOSITORIES (5)
# ══════════════════════════════════════════════════════════════════
if show repos; then
  header "Repositories (5 active)"

  declare -A REPOS=(
    ["mon-ipad"]="${ROOT}:Brain"
    ["nomos-nba-agent"]="${ROOT}/../nomos-nba-agent:NBA Engine"
    ["nomos-political-alpha"]="${ROOT}/../nomos-political-alpha:Political"
    ["rgwa"]="${ROOT}/../rgwa:RGWA"
    ["nomos-dashboard"]="${ROOT}/../nomos-dashboard:Dashboard"
  )

  for NAME in mon-ipad nomos-nba-agent nomos-political-alpha rgwa nomos-dashboard; do
    IFS=':' read -r RPATH LABEL <<< "${REPOS[$NAME]}"
    if [ -d "$RPATH/.git" ]; then
      DIRTY=$(cd "$RPATH" && git status --porcelain 2>/dev/null | wc -l)
      LAST=$(cd "$RPATH" && git log -1 --format="%ar" 2>/dev/null || echo "?")
      if [ "$DIRTY" -gt 20 ]; then
        count_warn "$NAME ($LABEL)" "${DIRTY} dirty, $LAST"
      elif [ "$DIRTY" -gt 0 ]; then
        info "$NAME ($LABEL)" "${DIRTY} dirty, $LAST"
      else
        count_ok "$NAME ($LABEL)" "clean, $LAST"
      fi
    else
      count_fail "$NAME ($LABEL)" "NOT FOUND"
    fi
  done
fi

# ══════════════════════════════════════════════════════════════════
# 6. BOTS
# ══════════════════════════════════════════════════════════════════
if show bots; then
  header "Telegram Monetization (cron-driven)"

  # Live pipeline: daily_picks.py posts to @Nomos42Picks at 18:00 UTC
  # sync_subscribers.py reconciles Stripe/Whop/LS at 09:00 UTC
  DAILY="${ROOT}/scripts/telegram/daily_picks.py"
  if [ -f "$DAILY" ]; then
    if crontab -l 2>/dev/null | grep -q "daily_picks.py"; then
      count_ok "daily_picks.py" "scheduled (cron)"
    else
      count_warn "daily_picks.py" "file exists but NOT in crontab"
    fi
  else
    count_fail "daily_picks.py" "missing"
  fi

  SYNC="${ROOT}/scripts/telegram/sync_subscribers.py"
  if [ -f "$SYNC" ]; then
    if crontab -l 2>/dev/null | grep -q "sync_subscribers.py"; then
      count_ok "sync_subscribers.py" "scheduled (cron)"
    else
      count_warn "sync_subscribers.py" "file exists but NOT in crontab"
    fi
  else
    count_fail "sync_subscribers.py" "missing"
  fi

  # Last-run artifacts
  LAST_PICKS="${ROOT}/data/telegram/daily-picks-latest.json"
  if [ -f "$LAST_PICKS" ]; then
    TS=$(python3 -c "import json; d=json.load(open('$LAST_PICKS')); print(d.get('timestamp', d.get('date','?')))" 2>/dev/null || echo "?")
    info "last picks post" "$TS"
  else
    info "last picks post" "no artifact yet"
  fi

  info "legacy bots" "@Nomos42Bot/@Forge42Bot/@RGWAbot archived — see git log 2026-04"
fi

# ══════════════════════════════════════════════════════════════════
# 7. CRONS
# ══════════════════════════════════════════════════════════════════
if show crons; then
  header "Cron Jobs"

  CRON_TOTAL=$(crontab -l 2>/dev/null | grep -v '^#' | grep -cv '^\s*$' || echo 0)
  CRON_NBA=$(crontab -l 2>/dev/null | grep -c "mon-ipad\|nomos-nba-agent" || echo 0)
  CRON_POL=$(crontab -l 2>/dev/null | grep -c "nomos-political-alpha" || echo 0)
  info "Total" "${CRON_TOTAL} active (NBA/Brain: ${CRON_NBA}, Political: ${CRON_POL})"

  for PAIR in "watchdog.sh:Watchdog" "infra-agent:Infra Agent" "keepalive:Keepalive" "data_server:Data Server" "autonomous-cycle:Auto Cycle"; do
    IFS=':' read -r PROC PLABEL <<< "$PAIR"
    if pgrep -f "$PROC" > /dev/null 2>&1; then
      count_ok "$PLABEL" "RUNNING"
    else
      info "$PLABEL" "cron-driven"
    fi
  done
fi

# ══════════════════════════════════════════════════════════════════
# 8. VERCEL SITES (5)
# ══════════════════════════════════════════════════════════════════
if show vercel && [ -z "$NO_PROBE" ]; then
  header "Vercel Sites (5)"

  check_site() {
    local url="$1" label="$2" desc="$3"
    local code
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$url" 2>/dev/null || echo 000)
    if [ "$code" = "200" ]; then
      count_ok "$label" "UP — $desc"
    elif [ "$code" = "404" ]; then
      count_warn "$label" "NOT DEPLOYED"
    else
      info "$label" "HTTP $code"
    fi
  }

  echo -e "  ${C}Live:${N}"
  check_site "https://nomosdashboard.vercel.app" "nomosdashboard.vercel.app" "Admin dashboard"

  echo -e "  ${C}SaaS (paid users):${N}"
  check_site "https://nomosquant42.vercel.app"   "nomosquant42.vercel.app"   "NBA SaaS"
  check_site "https://stupidpolitical.vercel.app" "stupidpolitical.vercel.app" "Political SaaS"
  check_site "https://rgwa-studio.vercel.app"    "rgwa-studio.vercel.app"    "RGWA Studio"

  echo -e "  ${C}Other:${N}"
  check_site "https://nomos42.vercel.app" "nomos42.vercel.app (Forge)" "SHELVED"
fi

# ══════════════════════════════════════════════════════════════════
# 9. AGENT SWARM (25 agents, 9 departments)
# ══════════════════════════════════════════════════════════════════
if show agents; then
  header "Agent Swarm (25 agents, 9 departments)"

  AGENT_RUNNING=0
  for APROC in "orchestrator" "agent-cron" "betting_agent" "evaluate_predictions" "nba-daily-odds" "infra-agent" "watchdog" "halftime_rescore"; do
    pgrep -f "$APROC" > /dev/null 2>&1 && AGENT_RUNNING=$((AGENT_RUNNING + 1))
  done

  AGENT_JSON="${ROOT}/data/agent-activity.json"
  if [ -f "$AGENT_JSON" ]; then
    LAST_ACTIVITY=$(python3 -c "
import json
try:
    d = json.load(open('$AGENT_JSON'))
    if isinstance(d, dict):
        ts = d.get('timestamp', d.get('last_run', '?'))
        print(ts)
    elif isinstance(d, list) and len(d) > 0:
        print(d[-1].get('timestamp', '?'))
except: print('?')
" 2>/dev/null || echo "?")
    info "Last activity" "$LAST_ACTIVITY"
  fi

  info "Research (4)"     "paper-scout, repo-scout, strategy-researcher, data-scout"
  info "Engineering (5)"  "feature-eng, test-creator, test-runner, bug-fixer, optimizer"
  info "Evolution (3)"    "evo-monitor, evo-optimizer, karpathy-loop"
  info "Betting (5)"      "odds-monitor, strategist, tester, corrector, halftime"
  info "Evaluation (2)"   "results-evaluator, performance-analyst"
  info "Infra (2)"        "infra-agent, dashboard-sync"
  info "Oversight (1)"    "orchestrator"
  info "Fleet Monitor (3)" "pierre-usage, pierre-practice, pierre-infra"
  info "Active processes" "${AGENT_RUNNING} agent processes running"
fi

# ══════════════════════════════════════════════════════════════════
# 10. 4-TRACK CONSOLIDATION (T1-T4) — v21 replacement for 9 depts
# ══════════════════════════════════════════════════════════════════
if show forge; then
  header "4-Track Consolidation (v21) — Opus-orchestrator every 8h"

  TRACKS_DIR="${ROOT}/data/tracks"
  declare -A TRACK_MAP=(
    ["T1"]="SCIENCE   (D1+D3+D6) — Brier · calibration · mutation · research"
    ["T2"]="PLATFORM  (D2+D7+D9) — code parity · deploys · uptime"
    ["T3"]="MARKET    (D4+D5)    — dashboard · telegram · subs · paywall"
    ["T4"]="CAPITAL   (D8+TFs)   — bankroll · \$1M goal"
  )

  if [ -f "${TRACKS_DIR}/TRACKS.md" ]; then
    ok "TRACKS spec" "data/tracks/TRACKS.md present"
  else
    count_warn "TRACKS spec" "TRACKS.md missing"
  fi

  for T in T1 T2 T3 T4; do
    LATEST="${TRACKS_DIR}/$(echo $T | tr 'A-Z' 'a-z')-latest.json"
    DESC="${TRACK_MAP[$T]}"
    if [ -f "$LATEST" ]; then
      AGE_SEC=$(python3 -c "
import json, datetime as dt
try:
    d=json.load(open('$LATEST'))
    ts=d.get('timestamp', d.get('last_run', ''))
    if not ts: print(-1); exit()
    t=dt.datetime.fromisoformat(ts.replace('Z','+00:00'))
    print(int((dt.datetime.now(dt.timezone.utc)-t).total_seconds()))
except: print(-1)
" 2>/dev/null || echo -1)
      if [ "$AGE_SEC" -lt 0 ]; then
        info "$T $DESC" "no timestamp"
      elif [ "$AGE_SEC" -lt 28800 ]; then  # <8h
        count_ok "$T $DESC" "fresh ($((AGE_SEC/60))min)"
      elif [ "$AGE_SEC" -lt 86400 ]; then
        count_warn "$T $DESC" "stale ($((AGE_SEC/3600))h)"
      else
        count_fail "$T $DESC" "OLD ($((AGE_SEC/86400))d)"
      fi
    else
      info "$T $DESC" "scaffolded · orchestrator not wired yet"
    fi
  done
fi

# ══════════════════════════════════════════════════════════════════
# 11. FLEET-MATRIX SCOREBOARD + SEASON BACKTEST + CPCV
# ══════════════════════════════════════════════════════════════════
if show forge; then
  header "Fleet-Matrix (GPU/CPU slot scoreboard)"

  FM="${ROOT}/data/fleet-matrix/scoreboard.json"
  if [ -f "$FM" ]; then
    FM_LINE=$(python3 -c "
import json
try:
    d=json.load(open('$FM'))
    gb=d.get('global_best') or {}
    best=gb.get('best_brier','?')
    slot=gb.get('slot','?')
    hyp=gb.get('hypothesis','?')
    nm=d.get('n_slots_measured',0)
    nt=d.get('n_slots_tracked',0)
    print(f'best={best} [{slot}/{hyp}]  measured={nm}/{nt}')
except Exception as e: print(f'err {e}')
" 2>/dev/null || echo "?")
    count_ok "scoreboard" "$FM_LINE"

    # Per-slot brief listing (top 6 slots by best_brier)
    python3 -c "
import json
try:
    d=json.load(open('$FM'))
    rows=[(s,v) for s,v in d.get('slots',{}).items() if v.get('best_brier') is not None]
    rows.sort(key=lambda r: r[1]['best_brier'])
    for sid,v in rows[:6]:
        br=v.get('best_brier','?')
        h=v.get('hypothesis','?')[:28]
        p=v.get('platform','?')[:12]
        print(f'     {sid:<6} {p:<12} {h:<28} br={br}')
except: pass
" 2>/dev/null || true
  else
    count_warn "scoreboard" "data/fleet-matrix/scoreboard.json missing — run scripts/fleet-matrix/aggregate.py"
  fi

  # Open hypotheses the fleet can still claim
  REG="${ROOT}/data/fleet-matrix/hypothesis-registry.json"
  if [ -f "$REG" ]; then
    OPEN_N=$(python3 -c "
import json
try:
    d=json.load(open('$REG'))
    o=d.get('open_hypotheses', d.get('open', []))
    print(len(o) if isinstance(o, list) else 0)
except: print(0)
" 2>/dev/null || echo 0)
    info "open hypotheses" "$OPEN_N pending (new GPU accounts should claim from this list)"
  fi

  header "Season Backtest + CPCV"

  BT="${ROOT}/data/nba-agent/full-season-backtest.json"
  if [ -f "$BT" ]; then
    BT_LINE=$(python3 -c "
import json
try:
    d=json.load(open('$BT'))
    ts=d.get('generated_at','?')
    roi=d.get('roi_pct','?')
    br=d.get('brier','?')
    bets=d.get('total_bets','?')
    print(f'{ts} | roi={roi}% brier={br} bets={bets}')
except Exception as e: print(f'parse-error: {e}')
" 2>/dev/null || echo "?")
    count_ok "Season backtest" "$BT_LINE"
  else
    count_warn "Season backtest" "missing"
  fi

  CPCV="${ROOT}/data/arena/cpcv-watcher-state.json"
  if [ -f "$CPCV" ]; then
    count_ok "CPCV watcher" "state present"
  else
    info "CPCV watcher" "no state"
  fi
fi

# ══════════════════════════════════════════════════════════════════
# 12. ALERTS
# ══════════════════════════════════════════════════════════════════
CROSS_JSON="${ROOT}/data/cross-repo-health.json"
if [ -f "$CROSS_JSON" ]; then
  ALERTS=$(python3 -c "
import json
try:
    d = json.load(open('$CROSS_JSON'))
    for a in d.get('alerts', [])[:8]:
        print(a)
except: pass
" 2>/dev/null || true)
  if [ -n "$ALERTS" ]; then
    header "Alerts"
    while IFS= read -r line; do
      echo -e "  ${Y}!! ${N}$line"
    done <<< "$ALERTS"
  fi
fi

# ══════════════════════════════════════════════════════════════════
# SUMMARY + HEALTH SCORE
# ══════════════════════════════════════════════════════════════════
TOTAL=$((OK_COUNT + WARN_COUNT + FAIL_COUNT))
if [ "$TOTAL" -gt 0 ]; then
  HEALTH=$(( (OK_COUNT * 100) / TOTAL ))
else
  HEALTH=0
fi

HEALTH_COLOR="$G"
[ "$HEALTH" -lt 80 ] && HEALTH_COLOR="$Y"
[ "$HEALTH" -lt 60 ] && HEALTH_COLOR="$R"

echo ""
echo -e "${W}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${N}"
echo -e "  ${C}HF Spaces:${N}  13 NBA evo + 8 political + infra + 2 TF + gateway + RGWA"
echo -e "  ${C}Kaggle:${N}     7 kernels + 1 dataset (alexismoret6)"
echo -e "  ${C}GPU:${N}        Modal + Colab + Lightning.ai + Kaggle + Codespaces + ZeroGPU + Paperspace"
echo -e "  ${C}Databases:${N}  2x Supabase + 2x Neo4j + 2x Pinecone + Upstash Redis"
echo -e "  ${C}Tracks:${N}     4 (T1 SCIENCE · T2 PLATFORM · T3 MARKET · T4 CAPITAL) — Opus orchestrator /8h"
echo -e "  ${C}Capital:${N}    2 live TF (NBA 12 · POL 10) · MIN_DEPLOY_PCT=0.75 · \$1M goal"
echo -e "  ${C}Fleet:${N}      12 GPU/CPU slots + 8 open hypotheses (data/fleet-matrix/scoreboard.json)"
CRON_COUNT=$(crontab -l 2>/dev/null | grep -v '^#' | grep -cv '^\s*$' || echo 0)
echo -e "  ${C}Repos:${N} 5  ${C}Bots:${N} 5  ${C}Crons:${N} ${CRON_COUNT}  ${C}Vercel:${N} 5"
echo -e "  ${C}Health:${N}    ${HEALTH_COLOR}${HEALTH}%${N}  (${G}OK:${OK_COUNT}${N} ${Y}WARN:${WARN_COUNT}${N} ${R}FAIL:${FAIL_COUNT}${N})"
echo -e "${W}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${N}"

# ── Launch Claude Code ──
case "$PROJECT" in
  nba)       WORKDIR="${ROOT}" ;;
  rgwa)      WORKDIR="${ROOT}/../rgwa" ;;
  political) WORKDIR="${ROOT}/../nomos-political-alpha" ;;
  dashboard) WORKDIR="${ROOT}/../nomos-dashboard" ;;
  all)       WORKDIR="${ROOT}" ;;
esac

echo ""
echo -e "  ${G}>${N} Workdir:     ${W}$WORKDIR${N}"
echo -e "  ${G}>${N} Project:     ${W}$PROJECT${N}"
[ -n "$SKIP_PERMS" ] && echo -e "  ${G}>${N} Permissions: ${Y}ALL ALLOWED${N}"
[ -n "$NO_LAUNCH" ]  && echo -e "  ${G}>${N} Mode:        ${C}status-only (no launch)${N}"
echo ""

if [ -n "$NO_LAUNCH" ]; then
  exit 0
fi

cd "$WORKDIR"
exec claude $SKIP_PERMS
