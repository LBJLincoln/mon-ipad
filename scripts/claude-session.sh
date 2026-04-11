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
#   Upstash Redis, 5 repos, 25 agents, 5 bots, 11+ crons, 5 Vercel sites,
#   9 Department Forge councils, Trading Floor v5.

set -uo pipefail

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
    --skip-perms)              SKIP_PERMS="--allowedTools '*'" ;;
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
  /home/termius/nomos-nba-agent/.env.local \
  /home/termius/mon-ipad/.env.local \
  /home/termius/rgwa/.env.local \
  /home/termius/nomos-political-alpha/.env.local; do
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
    nba)       WORKDIR="/home/termius/mon-ipad" ;;
    rgwa)      WORKDIR="/home/termius/rgwa" ;;
    political) WORKDIR="/home/termius/nomos-political-alpha" ;;
    dashboard) WORKDIR="/home/termius/nomos-dashboard" ;;
    all)       WORKDIR="/home/termius/mon-ipad" ;;
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
printf  "${W}║              %-53s ║${N}\n" "$(date -u '+%Y-%m-%d %H:%M UTC')  (v20 · 9 depts)"
echo -e "${W}╚════════════════════════════════════════════════════════════════════╝${N}"

# ══════════════════════════════════════════════════════════════════
# 1. HF SPACES — ALL ACCOUNTS (parallel curl)
# ══════════════════════════════════════════════════════════════════

# NBA evo islands (8) + political (2) + infra (2) + RGWA (1) + political legacy (1) = 14 live targets
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
  ["CLIP"]="nomos42-nomos42-paperclip"
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

  echo -e "  ${C}Other (2):${N}"
  for TAG in INFRA CLIP; do
    LABEL=""
    case $TAG in
      INFRA) LABEL="nomos42-infra-brain" ;; CLIP) LABEL="nomos42-paperclip" ;;
    esac
    if [ -f "$TMPDIR/$TAG" ]; then
      IFS='|' read -r STATUS BRIER GEN MODEL < "$TMPDIR/$TAG"
      [ "$STATUS" = "UP" ] && count_ok "$LABEL" "RUNNING" || count_fail "$LABEL" "DOWN"
    else
      count_warn "$LABEL" "no response"
    fi
  done

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
  COLAB_STATE="/home/termius/mon-ipad/data/colab-state.json"
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
    ["mon-ipad"]="/home/termius/mon-ipad:Brain"
    ["nomos-nba-agent"]="/home/termius/nomos-nba-agent:NBA Engine"
    ["nomos-political-alpha"]="/home/termius/nomos-political-alpha:Political"
    ["rgwa"]="/home/termius/rgwa:RGWA"
    ["nomos-dashboard"]="/home/termius/nomos-dashboard:Dashboard"
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
  header "Telegram Bots (5)"

  declare -A BOT_CHECKS=(
    ["@Nomos42Bot"]="nomos42_brain.py:Brain (admin/research)"
    ["@Forge42Bot"]="forge_bot.py:Forge Factory (fleet/SaaS)"
    ["@NomosNBABot"]="nomos_nba_bot.py:NBA SaaS (scout/edge/whale)"
    ["@StupidPoliticalBot"]="stupid_political_bot.py:Political SaaS (signals/trades)"
  )

  ANY_DOWN=false
  for BOT_NAME in "@Nomos42Bot" "@Forge42Bot" "@NomosNBABot" "@StupidPoliticalBot"; do
    IFS=':' read -r PROC_MATCH BOT_DESC <<< "${BOT_CHECKS[$BOT_NAME]}"
    if pgrep -f "$PROC_MATCH" > /dev/null 2>&1; then
      count_ok "$BOT_NAME" "RUNNING — $BOT_DESC"
    else
      count_fail "$BOT_NAME" "DOWN — $BOT_DESC"
      ANY_DOWN=true
    fi
  done

  if [ "$ANY_DOWN" = true ] && [ -z "$NO_LAUNCH" ]; then
    info "" "Auto-starting mon-ipad bots..."
    cd /home/termius/mon-ipad && bash scripts/telegram/start_bots.sh start 2>/dev/null || true
  fi

  if pgrep -f "rgwa_bot.py" > /dev/null 2>&1; then
    count_ok "@RGWAbot" "RUNNING — AI Art Terminal"
  else
    count_fail "@RGWAbot" "DOWN — AI Art Terminal"
    [ -z "$NO_LAUNCH" ] && { cd /home/termius/rgwa && bash scripts/telegram/start_bot.sh start 2>/dev/null || true; }
  fi
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

  AGENT_JSON="/home/termius/mon-ipad/data/agent-activity.json"
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
# 10. DEPARTMENT FORGE — 9 councils (D1-D9)
# ══════════════════════════════════════════════════════════════════
if show forge; then
  header "Department Forge v19 — 9 Councils"

  DEPT_DIR="/home/termius/mon-ipad/data/departments"
  for DEPT in research engineering evolution product business evaluation infra finance cross-repo; do
    LATEST="${DEPT_DIR}/council-${DEPT}-latest.json"
    if [ -f "$LATEST" ]; then
      TS=$(python3 -c "import json; d=json.load(open('$LATEST')); print(d.get('timestamp', d.get('last_run', '?')))" 2>/dev/null || echo "?")
      # Age in seconds from now
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
        info "D-${DEPT}" "$TS"
      elif [ "$AGE_SEC" -lt 21600 ]; then  # <6h
        count_ok "D-${DEPT}" "fresh ($((AGE_SEC/60))min)"
      elif [ "$AGE_SEC" -lt 86400 ]; then  # <24h
        count_warn "D-${DEPT}" "stale ($((AGE_SEC/3600))h)"
      else
        count_fail "D-${DEPT}" "OLD ($((AGE_SEC/86400))d)"
      fi
    else
      count_fail "D-${DEPT}" "no council JSON"
    fi
  done
fi

# ══════════════════════════════════════════════════════════════════
# 11. TRADING FLOOR v5 + TESTS
# ══════════════════════════════════════════════════════════════════
if show forge; then
  header "Trading Floor v5 + Backtest"

  TF_STATE="/home/termius/mon-ipad/data/arena/agent-states-v5.json"
  if [ -f "$TF_STATE" ]; then
    TF_LINE=$(python3 -c "
import json
try:
    d=json.load(open('$TF_STATE'))
    n=d.get('active_count', d.get('agent_count','?'))
    ts=d.get('last_backtest_sync', d.get('last_feedback_sync','?'))
    print(f'{n} agents  sync={ts}')
except Exception as e: print(f'err {e}')
" 2>/dev/null || echo "?")
    count_ok "TF v5 state" "$TF_LINE"
  else
    count_warn "TF v5 state" "missing"
  fi

  BT="/home/termius/mon-ipad/data/nba-agent/full-season-backtest.json"
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

  POL_STATE="/home/termius/mon-ipad/data/arena/political-trading-floor-iteration.json"
  if [ -f "$POL_STATE" ]; then
    count_ok "Political TF" "state present"
  else
    info "Political TF" "no state"
  fi

  CPCV="/home/termius/mon-ipad/data/arena/cpcv-watcher-state.json"
  if [ -f "$CPCV" ]; then
    count_ok "CPCV watcher" "state present"
  else
    info "CPCV watcher" "no state"
  fi

  info "Scripts" "arena/trading-floor-v5.py  arena/trading-floor-v5-real.py  arena/political-trading-floor.py"
fi

# ══════════════════════════════════════════════════════════════════
# 12. ALERTS
# ══════════════════════════════════════════════════════════════════
CROSS_JSON="/home/termius/mon-ipad/data/cross-repo-health.json"
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
echo -e "  ${C}HF Spaces:${N}  24+ total (4 credentials) — 8 NBA evo + 2 pol + infra + RGWA"
echo -e "  ${C}Kaggle:${N}     7 kernels + 1 dataset (alexismoret6)"
echo -e "  ${C}GPU:${N}        Modal + Colab + Lightning.ai + Kaggle + Codespaces"
echo -e "  ${C}Databases:${N}  2x Supabase + 2x Neo4j + 2x Pinecone + Upstash Redis"
echo -e "  ${C}Agents:${N}     25 (9 depts — D1 Research · D2 Eng · D3 Evo · D4 Product · D5 Business · D6 Eval · D7 Infra · D8 Finance · D9 Cross-Repo)"
echo -e "  ${C}Forge:${N}      Karpathy loop per dept + Trading Floor v5 + CPCV gate"
CRON_COUNT=$(crontab -l 2>/dev/null | grep -v '^#' | grep -cv '^\s*$' || echo 0)
echo -e "  ${C}Repos:${N} 5  ${C}Bots:${N} 5  ${C}Crons:${N} ${CRON_COUNT}  ${C}Vercel:${N} 5"
echo -e "  ${C}Health:${N}    ${HEALTH_COLOR}${HEALTH}%${N}  (${G}OK:${OK_COUNT}${N} ${Y}WARN:${WARN_COUNT}${N} ${R}FAIL:${FAIL_COUNT}${N})"
echo -e "${W}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${N}"

# ── Launch Claude Code ──
case "$PROJECT" in
  nba)       WORKDIR="/home/termius/mon-ipad" ;;
  rgwa)      WORKDIR="/home/termius/rgwa" ;;
  political) WORKDIR="/home/termius/nomos-political-alpha" ;;
  dashboard) WORKDIR="/home/termius/nomos-dashboard" ;;
  all)       WORKDIR="/home/termius/mon-ipad" ;;
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
