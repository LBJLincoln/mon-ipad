#!/bin/bash
# Nomos42 — Claude Code Session Launcher (Full Ecosystem)
# Usage: ~/mon-ipad/scripts/claude-session.sh [--skip-perms] [--project nba|rgwa|political|dashboard|all]
#
# Complete status across ALL platforms:
#   HF Spaces (4 accounts, 24+ spaces), Kaggle (7 kernels + 1 dataset),
#   Modal, Colab, Lightning.ai, 2x Supabase, 2x Neo4j, 2x Pinecone,
#   Upstash Redis, 5 repos, 22 agents, 2 bots, 11+ crons, 2x Vercel

set -uo pipefail

# ── Colors ──
R='\033[0;31m'; G='\033[0;32m'; Y='\033[0;33m'; B='\033[0;34m'
C='\033[0;36m'; W='\033[1;37m'; D='\033[0;90m'; M='\033[0;35m'; N='\033[0m'

# ── Parse args ──
SKIP_PERMS=""
PROJECT="nba"
for arg in "$@"; do
  case "$arg" in
    --skip-perms) SKIP_PERMS="--allowedTools '*'" ;;
    --nba|--project=nba) PROJECT="nba" ;;
    --rgwa|--project=rgwa) PROJECT="rgwa" ;;
    --political|--project=political) PROJECT="political" ;;
    --dashboard|--project=dashboard) PROJECT="dashboard" ;;
    --all) PROJECT="all" ;;
  esac
done

# ── Source all env files ──
for envfile in \
  /home/termius/nomos-nba-agent/.env.local \
  /home/termius/mon-ipad/.env.local \
  /home/termius/rgwa/.env.local \
  /home/termius/nomos-political-alpha/.env.local; do
  [ -f "$envfile" ] && source "$envfile" 2>/dev/null
done

# ── Helpers ──
ok()     { printf "  ${G}%-2s${N} %-32s %s\n" "OK" "$1" "$2"; }
warn()   { printf "  ${Y}%-2s${N} %-32s %s\n" "!!" "$1" "$2"; }
fail()   { printf "  ${R}%-2s${N} %-32s %s\n" "XX" "$1" "$2"; }
info()   { printf "  ${D}%-2s${N} %-32s %s\n" "--" "$1" "$2"; }
header() { echo ""; echo -e "${B}━━━ $1 ━━━${N}"; }

# ── Temp dir for parallel curl results ──
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

echo ""
echo -e "${W}╔════════════════════════════════════════════════════════════════════╗${N}"
echo -e "${W}║              NOMOS42 — Full Ecosystem Dashboard                   ║${N}"
echo -e "${W}║              $(date '+%Y-%m-%d %H:%M UTC')                                  ║${N}"
echo -e "${W}╚════════════════════════════════════════════════════════════════════╝${N}"

# ══════════════════════════════════════════════════════════════════
# 1. HF SPACES — ALL 3 ACCOUNTS (parallel curl for active spaces)
# ══════════════════════════════════════════════════════════════════

# Fire off all active space pings in parallel
declare -A ACTIVE_SPACES=(
  # NBA Islands (Nomos42)
  ["S10"]="nomos42-nba-quant"
  ["S11"]="nomos42-nba-quant-2"
  ["S12"]="nomos42-nba-evo-3"
  ["S13"]="nomos42-nba-evo-4"
  ["S14"]="nomos42-nba-evo-5"
  ["S15"]="nomos42-nba-evo-6"
  # Political Islands (Nomos42)
  ["P1"]="nomos42-political-alpha"
  ["P2"]="nomos42-political-alpha-2"
  ["P3"]="nomos42-political-alpha-3"
  ["P4"]="nomos42-political-alpha-4"
  # Infra/Other (Nomos42)
  ["INFRA"]="nomos42-nomos42-infra-brain"
  ["CLIP"]="nomos42-nomos42-paperclip"
  # RGWA (LBJLincoln)
  ["RGWA"]="lbjlincoln-nomos-rgwa"
  # Political (LBJLincoln26)
  ["P0_26"]="lbjlincoln26-nomos-political-alpha"
)

# Parallel curl all active spaces
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

# ── Display: Nomos42 account (13 spaces) ──
header "HF: Nomos42 (13 spaces) — Primary account"

echo -e "  ${C}NBA Evolution Islands:${N}"
for TAG in S10 S11 S12 S13 S14 S15; do
  if [ -f "$TMPDIR/$TAG" ]; then
    IFS='|' read -r STATUS BRIER GEN MODEL < "$TMPDIR/$TAG"
    ROLES=""
    case $TAG in
      S10) ROLES="exploitation" ;; S11) ROLES="exploration" ;; S12) ROLES="extra_trees" ;;
      S13) ROLES="catboost" ;; S14) ROLES="lightgbm" ;; S15) ROLES="wide_search" ;;
    esac
    if [ "$STATUS" = "UP" ]; then
      DETAIL=""
      [ -n "$BRIER" ] && DETAIL="brier=$BRIER"
      [ -n "$GEN" ] && DETAIL="$DETAIL gen=$GEN"
      [ -n "$MODEL" ] && DETAIL="$DETAIL [$MODEL]"
      ok "$TAG ($ROLES)" "$DETAIL"
    else
      fail "$TAG ($ROLES)" "DOWN (HTTP $BRIER)"
    fi
  else
    warn "$TAG" "no response"
  fi
done

echo -e "  ${C}Political Evolution Islands:${N}"
for TAG in P1 P2 P3 P4; do
  if [ -f "$TMPDIR/$TAG" ]; then
    IFS='|' read -r STATUS BRIER GEN MODEL < "$TMPDIR/$TAG"
    ROLES=""
    case $TAG in
      P1) ROLES="exploitation" ;; P2) ROLES="exploration" ;; P3) ROLES="catboost" ;; P4) ROLES="wide_search" ;;
    esac
    if [ "$STATUS" = "UP" ]; then
      DETAIL=""
      [ -n "$BRIER" ] && DETAIL="brier=$BRIER"
      [ -n "$GEN" ] && DETAIL="$DETAIL gen=$GEN"
      ok "$TAG ($ROLES)" "$DETAIL"
    else
      fail "$TAG ($ROLES)" "DOWN (HTTP $BRIER)"
    fi
  else
    warn "$TAG" "no response"
  fi
done

echo -e "  ${C}Other:${N}"
for TAG in INFRA CLIP; do
  LABEL=""
  case $TAG in
    INFRA) LABEL="nomos42-infra-brain" ;; CLIP) LABEL="nomos42-paperclip" ;;
  esac
  if [ -f "$TMPDIR/$TAG" ]; then
    IFS='|' read -r STATUS BRIER GEN MODEL < "$TMPDIR/$TAG"
    [ "$STATUS" = "UP" ] && ok "$LABEL" "RUNNING" || fail "$LABEL" "DOWN"
  else
    warn "$LABEL" "no response"
  fi
done
# Static: nomos-political-alpha-2 (duplicate)
info "nomos-political-alpha-2" "duplicate (old)"

# ── Display: LBJLincoln account (3 spaces) ──
header "HF: LBJLincoln (3 spaces) — Legacy/RGWA"

if [ -f "$TMPDIR/RGWA" ]; then
  IFS='|' read -r STATUS BRIER GEN MODEL < "$TMPDIR/RGWA"
  [ "$STATUS" = "UP" ] && ok "nomos-rgwa" "RUNNING (docker)" || fail "nomos-rgwa" "DOWN"
else
  warn "nomos-rgwa" "no response"
fi
info "nomos-nba-quant" "OLD (migrated to Nomos42)"
info "nomos-nba-quant-2" "OLD (migrated to Nomos42)"

# ── Display: LBJLincoln26 account (8 spaces) ──
header "HF: LBJLincoln26 (8 spaces) — Legacy/Political"

if [ -f "$TMPDIR/P0_26" ]; then
  IFS='|' read -r STATUS BRIER GEN MODEL < "$TMPDIR/P0_26"
  [ "$STATUS" = "UP" ] && ok "nomos-political-alpha" "RUNNING" || info "nomos-political-alpha" "PAUSED/OLD"
else
  info "nomos-political-alpha" "PAUSED/OLD"
fi
info "nba-evo-3" "OLD (migrated to Nomos42)"
info "nba-evo-4" "OLD (migrated to Nomos42)"
info "nomos-rag-engine-2" "PAUSED (RAG dead)"
info "nomos-rag-engine-4" "PAUSED (RAG dead)"
info "nomos-rag-engine-6" "PAUSED (RAG dead)"
info "nomos-rag-engine-8" "PAUSED (RAG dead)"
info "nomos-rag-engine-10" "PAUSED (RAG dead)"

# ══════════════════════════════════════════════════════════════════
# 2. KAGGLE — 7 kernels + 1 dataset
# ══════════════════════════════════════════════════════════════════
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

KAGGLE_OK=false
for ENTRY in "${KAGGLE_KERNELS[@]}"; do
  IFS=':' read -r KERNEL LABEL <<< "$ENTRY"
  STATUS=$(kaggle kernels status "$KERNEL" 2>/dev/null | grep -oP 'KernelWorkerStatus\.\K\w+' || echo "?")
  case "$STATUS" in
    RUNNING)  ok "$LABEL" "RUNNING" ; KAGGLE_OK=true ;;
    COMPLETE) info "$LABEL" "COMPLETE (idle)" ;;
    ERROR)    fail "$LABEL" "ERROR" ;;
    CANCEL*)  warn "$LABEL" "CANCELLED" ;;
    *)        info "$LABEL" "$STATUS" ;;
  esac
done

echo -e "  ${C}Datasets:${N}"
ok "nba-2025-26-odds" "12KB, 7 downloads"

# ══════════════════════════════════════════════════════════════════
# 3. GPU PLATFORMS — Modal, Colab
# ══════════════════════════════════════════════════════════════════
header "GPU Platforms"

# Modal
MODAL_COUNT=$(modal app list 2>/dev/null | grep -c "nba-karpathy\|nomos" 2>/dev/null || echo "0")
MODAL_COUNT=$(echo "$MODAL_COUNT" | tr -d '[:space:]')
if [ "${MODAL_COUNT:-0}" -gt 0 ]; then
  ok "Modal (lbjlincoln)" "RUNNING ($MODAL_COUNT active)"
else
  info "Modal (lbjlincoln)" "IDLE (\$30/mo free tier)"
fi

# Colab
COLAB_STATE="/home/termius/mon-ipad/data/colab-state.json"
if [ -f "$COLAB_STATE" ]; then
  COLAB_TS=$(python3 -c "import json; d=json.load(open('$COLAB_STATE')); print(d.get('timestamp','?'))" 2>/dev/null)
  ok "Google Colab" "Last: $COLAB_TS"
else
  info "Google Colab" "Not running (T4 on-demand)"
fi

# Lightning.ai
info "Lightning.ai (moretalexis24)" "22 GPU-hr/mo, credits Apr 1"

# GitHub Codespaces
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
  ok "GitHub Codespaces" "$CS_STATUS"
elif [ "$CS_STATUS" = "NONE" ]; then
  info "GitHub Codespaces" "none running"
else
  info "GitHub Codespaces" "$CS_STATUS"
fi

# MCP Compute Server (local port 8082)
MCP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 "http://localhost:8082/health" 2>/dev/null)
if [ "$MCP_CODE" = "200" ]; then
  ok "MCP Compute Server" "UP (port 8082) — compute-cli bridge"
else
  info "MCP Compute Server" "not running (start: python3 scripts/mcp-compute-server.py)"
fi

# ══════════════════════════════════════════════════════════════════
# 4. DATABASES (7 services across multiple accounts)
# ══════════════════════════════════════════════════════════════════
header "Databases (7 services)"

echo -e "  ${C}Supabase (2 projects):${N}"
# Supabase #2 (active) - check pooler
SB2_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "https://xivvnrkbtuhfsphtmmtv.supabase.co/rest/v1/" -H "apikey: ${SUPABASE_ANON_KEY_2:-none}" 2>/dev/null)
if [ "$SB2_CODE" = "200" ] || [ "$SB2_CODE" = "401" ]; then
  ok "xivvnr (active)" "UP — 56 tables (NBA+Political+RAG)"
else
  warn "xivvnr (active)" "HTTP $SB2_CODE (use pooler)"
fi
# Supabase #1 (paused)
SB1_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "https://ayqviqmxifzmhphiqfmj.supabase.co/rest/v1/" -H "apikey: ${SUPABASE_API_KEY:-none}" 2>/dev/null)
if [ "$SB1_CODE" = "402" ] || [ "$SB1_CODE" = "000" ]; then
  info "ayqviq (old primary)" "PAUSED (402)"
else
  ok "ayqviq (old primary)" "HTTP $SB1_CODE"
fi

echo -e "  ${C}Neo4j (2 instances):${N}"
# Neo4j #1 (MCP-connected)
NEO4J_1=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "https://38c949a2.databases.neo4j.io" 2>/dev/null)
if [ "$NEO4J_1" = "200" ] || [ "$NEO4J_1" = "401" ]; then
  ok "38c949a2 (knowledge graph)" "UP — Entity, Company, Law, SectorDoc"
else
  info "38c949a2 (knowledge graph)" "HTTP $NEO4J_1 (bolt connection)"
fi
# Neo4j #2
NEO4J_2=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "https://48d838a5.databases.neo4j.io" 2>/dev/null)
if [ "$NEO4J_2" = "200" ] || [ "$NEO4J_2" = "401" ]; then
  ok "48d838a5 (secondary)" "UP"
else
  info "48d838a5 (secondary)" "HTTP $NEO4J_2"
fi

echo -e "  ${C}Vector DBs (2 Pinecone):${N}"
# Pinecone #1
PC1_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "${PINECONE_HOST:-https://pinecone.io}/describe_index_stats" -H "Api-Key: ${PINECONE_API_KEY:-none}" 2>/dev/null)
if [ "$PC1_CODE" = "200" ]; then
  ok "Pinecone #1 (sota-rag)" "UP"
else
  info "Pinecone #1 (sota-rag)" "HTTP $PC1_CODE"
fi
info "Pinecone #2" "Secondary key configured"

echo -e "  ${C}Cache:${N}"
# Upstash Redis
REDIS_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "${UPSTASH_REDIS_REST_URL:-https://upstash.io}" -H "Authorization: Bearer ${UPSTASH_REDIS_REST_TOKEN:-none}" 2>/dev/null)
if [ "$REDIS_CODE" = "200" ] || [ "$REDIS_CODE" = "401" ]; then
  ok "Upstash Redis" "UP (dynamic-frog-47846)"
else
  info "Upstash Redis" "HTTP $REDIS_CODE"
fi

# ══════════════════════════════════════════════════════════════════
# 4b. HF TOKEN: FORGE (4th account)
# ══════════════════════════════════════════════════════════════════
# HF_TOKEN_FORGE is configured — may be a write token for a specific space
# or a 4th HF account. Listed for inventory completeness.
if [ -n "${HF_TOKEN_FORGE:-}" ]; then
  header "HF: Forge Token (4th credential)"
  info "HF_TOKEN_FORGE" "configured (hf_sGp...)"
fi

# ══════════════════════════════════════════════════════════════════
# 5. REPOSITORIES (5)
# ══════════════════════════════════════════════════════════════════
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
    LAST=$(cd "$RPATH" && git log -1 --format="%ar" 2>/dev/null)
    if [ "$DIRTY" -gt 20 ]; then
      warn "$NAME ($LABEL)" "${DIRTY} dirty, $LAST"
    elif [ "$DIRTY" -gt 0 ]; then
      info "$NAME ($LABEL)" "${DIRTY} dirty, $LAST"
    else
      ok "$NAME ($LABEL)" "clean, $LAST"
    fi
  else
    fail "$NAME ($LABEL)" "NOT FOUND"
  fi
done

# ══════════════════════════════════════════════════════════════════
# 6. BOTS + PROCESSES
# ══════════════════════════════════════════════════════════════════
header "Telegram Bots (5)"

# mon-ipad bots (4)
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
    ok "$BOT_NAME" "RUNNING — $BOT_DESC"
  else
    fail "$BOT_NAME" "DOWN — $BOT_DESC"
    ANY_DOWN=true
  fi
done

if [ "$ANY_DOWN" = true ]; then
  info "" "Auto-starting mon-ipad bots..."
  cd /home/termius/mon-ipad && bash scripts/telegram/start_bots.sh start 2>/dev/null
fi

# rgwa bot (separate repo)
if pgrep -f "rgwa_bot.py" > /dev/null 2>&1; then
  ok "@RGWAbot" "RUNNING — AI Art Terminal (~/rgwa)"
else
  fail "@RGWAbot" "DOWN — AI Art Terminal (~/rgwa)"
  cd /home/termius/rgwa && bash scripts/telegram/start_bot.sh start 2>/dev/null
fi

# ══════════════════════════════════════════════════════════════════
# 7. CRONS
# ══════════════════════════════════════════════════════════════════
header "Cron Jobs"

CRON_TOTAL=$(crontab -l 2>/dev/null | grep -v '^#' | grep -v '^\s*$' | wc -l)
CRON_NBA=$(crontab -l 2>/dev/null | grep -c "mon-ipad\|nomos-nba-agent" 2>/dev/null || echo 0)
CRON_POL=$(crontab -l 2>/dev/null | grep -c "nomos-political-alpha" 2>/dev/null || echo 0)
info "Total" "${CRON_TOTAL} active (NBA/Brain: ${CRON_NBA}, Political: ${CRON_POL})"

# Key processes
for PAIR in "watchdog.sh:Watchdog" "infra-agent:Infra Agent" "keepalive:Keepalive" "data_server:Data Server" "autonomous-cycle:Auto Cycle"; do
  IFS=':' read -r PROC PLABEL <<< "$PAIR"
  if pgrep -f "$PROC" > /dev/null 2>&1; then
    ok "$PLABEL" "RUNNING"
  else
    info "$PLABEL" "cron-driven"
  fi
done

# ══════════════════════════════════════════════════════════════════
# 8. VERCEL SITES (5)
# ══════════════════════════════════════════════════════════════════
header "Vercel Sites (5)"

echo -e "  ${C}Live:${N}"
DASH_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "https://nomosdashboard.vercel.app" 2>/dev/null)
if [ "$DASH_CODE" = "200" ]; then
  ok "nomosdashboard.vercel.app" "UP — Admin dashboard (/nba /political /rgwa /evolution)"
else
  fail "nomosdashboard.vercel.app" "DOWN (HTTP $DASH_CODE)"
fi

echo -e "  ${C}SaaS (paid users):${N}"
# NBA Picks — $19/$49/$149 per month
PICKS_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "https://nomosquant42.vercel.app" 2>/dev/null)
if [ "$PICKS_CODE" = "200" ]; then
  ok "nomosquant42.vercel.app" "UP — NBA SaaS (Scout/Edge/Whale)"
elif [ "$PICKS_CODE" = "404" ]; then
  warn "nomosquant42.vercel.app" "NOT DEPLOYED — repo: nomosquant42 (to create)"
else
  info "nomosquant42.vercel.app" "HTTP $PICKS_CODE — TO CREATE"
fi

# Political Alpha — paid users
POLSITE_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "https://stupidpolitical.vercel.app" 2>/dev/null)
if [ "$POLSITE_CODE" = "200" ]; then
  ok "stupidpolitical.vercel.app" "UP — Stupid Political (paid)"
elif [ "$POLSITE_CODE" = "404" ]; then
  warn "stupidpolitical.vercel.app" "NOT DEPLOYED — repo: stupid-political (to create)"
else
  info "stupidpolitical.vercel.app" "HTTP $POLSITE_CODE — TO CREATE"
fi

# RGWA Studio — AI art generation
RGWA_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "https://rgwa-studio.vercel.app" 2>/dev/null)
if [ "$RGWA_CODE" = "200" ]; then
  ok "rgwa-studio.vercel.app" "UP — RGWA AI Art Studio"
elif [ "$RGWA_CODE" = "404" ]; then
  warn "rgwa-studio.vercel.app" "NOT DEPLOYED — repo: rgwa-studio (to create)"
else
  info "rgwa-studio.vercel.app" "HTTP $RGWA_CODE — TO CREATE"
fi

echo -e "  ${C}Other:${N}"
FORGE_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "https://nomos42.vercel.app" 2>/dev/null)
if [ "$FORGE_CODE" = "200" ]; then
  info "nomos42.vercel.app (Forge)" "UP — SHELVED"
else
  info "nomos42.vercel.app (Forge)" "HTTP $FORGE_CODE — SHELVED"
fi

# ══════════════════════════════════════════════════════════════════
# 9. AGENT SWARM (22 agents, 7 departments)
# ══════════════════════════════════════════════════════════════════
header "Agent Swarm (25 agents, 8 departments)"

# Count running agent processes
AGENT_RUNNING=0
for APROC in "orchestrator" "agent-cron" "betting_agent" "evaluate_predictions" "nba-daily-odds" "infra-agent" "watchdog" "halftime_rescore"; do
  pgrep -f "$APROC" > /dev/null 2>&1 && AGENT_RUNNING=$((AGENT_RUNNING + 1))
done

# Check agent health from cached data
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
" 2>/dev/null)
  info "Last activity" "$LAST_ACTIVITY"
fi

info "Research (4)" "paper-scout, repo-scout, strategy-researcher, data-scout"
info "Engineering (5)" "feature-eng, test-creator, test-runner, bug-fixer, optimizer"
info "Evolution (3)" "evo-monitor, evo-optimizer, karpathy-loop"
info "Betting (5)" "odds-monitor, strategist, tester, corrector, halftime"
info "Evaluation (2)" "results-evaluator, performance-analyst"
info "Infra (2)" "infra-agent, dashboard-sync"
info "Oversight (1)" "orchestrator"
info "Fleet Monitor (3)" "pierre-usage, pierre-practice, pierre-infra"
info "Active processes" "${AGENT_RUNNING} agent processes running"

# ══════════════════════════════════════════════════════════════════
# 10. ALERTS (from cached infra data)
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
" 2>/dev/null)
  if [ -n "$ALERTS" ]; then
    header "Alerts"
    while IFS= read -r line; do
      echo -e "  ${Y}!! ${N}$line"
    done <<< "$ALERTS"
  fi
fi

# ══════════════════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════════════════
echo ""
echo -e "${W}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${N}"
echo -e "  ${C}HF Spaces:${N}  24+ total (4 credentials) — 10 evo + infra + RGWA active"
echo -e "  ${C}Kaggle:${N}     7 kernels + 1 dataset (alexismoret6)"
echo -e "  ${C}GPU:${N}        Modal + Colab + Lightning.ai + Kaggle"
echo -e "  ${C}Databases:${N}  2x Supabase + 2x Neo4j + 2x Pinecone + Upstash Redis"
echo -e "  ${C}Agents:${N}     25 (8 depts)  ${C}Repos:${N} 5  ${C}Bots:${N} 5  ${C}Crons:${N} ${CRON_TOTAL}  ${C}Vercel:${N} 5"
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
echo -e "  ${G}>${N} Launching Claude Code in ${W}$WORKDIR${N}"
echo -e "  ${G}>${N} Project: ${W}$PROJECT${N}"
[ -n "$SKIP_PERMS" ] && echo -e "  ${G}>${N} Permissions: ${Y}ALL ALLOWED${N}"
echo ""

cd "$WORKDIR"
exec claude $SKIP_PERMS
