#!/usr/bin/env bash
# =============================================================================
# wake-codespaces.sh — Wake + status check for all repos (next session starter)
# Usage: bash scripts/wake-codespaces.sh [--wake] [--no-ssh]
#   --wake     : Also wake Codespaces (otherwise status-only)
#   --no-ssh   : Skip SSH connectivity test (faster)
# =============================================================================
set -uo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
WAKE=${1:-"--wake"}
NO_SSH=""
[[ "${2:-}" == "--no-ssh" ]] && NO_SSH=true
[[ "${1:-}" == "--no-ssh" ]] && NO_SSH=true && WAKE="--wake"

# Colors
G='\033[0;32m'; R='\033[0;31m'; Y='\033[1;33m'; C='\033[0;36m'
B='\033[1m'; DIM='\033[2m'; N='\033[0m'

PASS="${G}✓${N}"; FAIL="${R}✗${N}"; WARN="${Y}~${N}"; INFO="${C}·${N}"

echo ""
echo -e "${B}${C}╔══════════════════════════════════════════════════╗${N}"
echo -e "${B}${C}║   Multi-RAG — Session Start Dashboard            ║${N}"
echo -e "${B}${C}║   $(date '+%Y-%m-%d %H:%M:%S')                          ║${N}"
echo -e "${B}${C}╚══════════════════════════════════════════════════╝${N}"

# ── [1/5] VM Health ──────────────────────────────────────────────────────────
echo ""
echo -e "${B}[1/5] VM Health${N}"

# RAM
ram_info=$(free -m | awk 'NR==2 {printf "%.0fMB used / %.0fMB total | %.0fMB free", $3, $2, $7}')
ram_free=$(free -m | awk 'NR==2 {print $7}')
if [[ $ram_free -gt 150 ]]; then
  echo -e "  $PASS RAM: $ram_info"
elif [[ $ram_free -gt 80 ]]; then
  echo -e "  $WARN RAM: $ram_info (tight)"
else
  echo -e "  $FAIL RAM: $ram_info (CRITICAL — avoid heavy scripts)"
fi

# CPU load
load=$(cat /proc/loadavg | awk '{print $1}')
load_i=$(awk "BEGIN {printf \"%d\", $load * 10}")
if [[ $load_i -lt 10 ]]; then
  echo -e "  $PASS CPU load: $load (healthy)"
elif [[ $load_i -lt 30 ]]; then
  echo -e "  $WARN CPU load: $load (moderate)"
else
  echo -e "  $FAIL CPU load: $load (HIGH)"
fi

# Swap
swap_used=$(free -m | awk 'NR==3 {print $3}')
echo -e "  ${DIM}Swap used: ${swap_used}MB${N}"

# ── [2/5] Docker + n8n ───────────────────────────────────────────────────────
echo ""
echo -e "${B}[2/5] Docker + n8n (11 workflows)${N}"

# Container check
for c in n8n-n8n-1 n8n-redis-1 n8n-postgres-1; do
  status=$(docker inspect --format '{{.State.Status}}' "$c" 2>/dev/null || echo "missing")
  [[ "$status" == "running" ]] \
    && echo -e "  $PASS $c" \
    || echo -e "  $FAIL $c: $status"
done

# n8n API quick check
n8n_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "http://localhost:5678/healthz" 2>/dev/null || echo "000")
[[ "$n8n_code" == "200" ]] \
  && echo -e "  $PASS n8n API reachable (localhost:5678)" \
  || echo -e "  $FAIL n8n API: HTTP $n8n_code"

# Workflow count from API (fast)
source "$REPO_DIR/.env.local" 2>/dev/null || true
if [[ -n "${N8N_API_KEY:-}" ]]; then
  active_count=$(curl -sf "http://localhost:5678/api/v1/workflows?active=true&limit=50" \
    -H "X-N8N-API-KEY: $N8N_API_KEY" 2>/dev/null | \
    python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('data',[])))" 2>/dev/null || echo "?")
  echo -e "  $INFO Active workflows: $active_count / 11"
fi

# ── [3/5] Production URLs ─────────────────────────────────────────────────────
echo ""
echo -e "${B}[3/5] Production Sites${N}"

check_url() {
  local name="$1" url="$2"
  code=$(curl -sf -o /dev/null -w "%{http_code}" --max-time 10 "$url" 2>/dev/null || echo "000")
  [[ "$code" == "200" || "$code" == "302" ]] \
    && echo -e "  $PASS $name: ${DIM}$url${N}" \
    || echo -e "  $FAIL $name (HTTP $code): ${DIM}$url${N}"
}

check_url "rag-website" "https://nomos-ai-pied.vercel.app"
check_url "rag-dashboard" "https://nomos-dashboard.vercel.app"
check_url "n8n external" "https://lbjlincoln-nomos-rag-engine.hf.space/healthz"

# ── [4/5] Codespace Status ───────────────────────────────────────────────────
echo ""
echo -e "${B}[4/5] GitHub Codespaces${N}"

# Get codespace status
cs_list=$(gh codespace list 2>/dev/null || echo "")
if [[ -z "$cs_list" ]]; then
  echo -e "  $WARN No Codespaces found (or gh CLI error)"
else
  echo "$cs_list" | while IFS=$'\t' read -r name display_name repo branch state updated; do
    case "$state" in
      Available) echo -e "  $PASS $display_name ($repo) — ${G}Running${N}" ;;
      Shutdown)  echo -e "  $WARN $display_name ($repo) — ${Y}Shutdown${N}" ;;
      *)         echo -e "  $INFO $display_name ($repo) — $state" ;;
    esac
  done
fi

# Wake Codespaces if requested
if [[ "$WAKE" == "--wake" ]]; then
  echo ""
  echo -e "  ${B}Waking Codespaces...${N}"

  # Get shutdown codespace names
  shutdown_cs=$(gh codespace list 2>/dev/null | grep "Shutdown" | awk '{print $1}')

  if [[ -z "$shutdown_cs" ]]; then
    echo -e "  $INFO All Codespaces already running"
  else
    while IFS= read -r cs_name; do
      if [[ -n "$cs_name" ]]; then
        echo -e "  ${DIM}Waking: $cs_name${N}"
        # SSH triggers wake-up (non-blocking with timeout)
        timeout 20 gh codespace ssh --codespace "$cs_name" -- "echo ONLINE 2>/dev/null" 2>/dev/null &
      fi
    done <<< "$shutdown_cs"

    # Brief wait then re-check
    sleep 5
    echo -e "  ${DIM}Wake signals sent (Codespaces may take 30-60s to be available)${N}"
  fi
fi

# ── [5/5] Git Sync Status ────────────────────────────────────────────────────
echo ""
echo -e "${B}[5/5] Git Sync (5 repos)${N}"

cd "$REPO_DIR"
current_sha=$(git rev-parse --short HEAD 2>/dev/null || echo "?")
echo -e "  ${B}mon-ipad${N} (local): ${DIM}$current_sha${N}"

for remote in origin rag-tests rag-website rag-dashboard rag-data-ingestion; do
  remote_sha=$(git ls-remote "$remote" refs/heads/main 2>/dev/null | awk '{print substr($1,1,7)}' || echo "?")
  if [[ "$remote_sha" == "$current_sha" || "$remote_sha" == "${current_sha:0:7}" ]]; then
    echo -e "  $PASS $remote: ${DIM}$remote_sha${N} (in sync)"
  elif [[ "$remote_sha" == "?" ]]; then
    echo -e "  $WARN $remote: unreachable"
  else
    echo -e "  $WARN $remote: ${DIM}$remote_sha${N} (diverged — run: git push $remote main)"
  fi
done

# ── Priorities from session-state ─────────────────────────────────────────────
echo ""
echo -e "${B}Pending actions (from session-state.md)${N}"
state_file="$REPO_DIR/directives/session-state.md"
if [[ -f "$state_file" ]]; then
  # Extract prochaine action section
  python3 -c "
import re, sys
txt = open('$state_file').read()
m = re.search(r'## Prochaine action\s*\n(.*?)(?=\n## |\Z)', txt, re.DOTALL)
if m:
    lines = [l for l in m.group(1).split('\n') if re.match(r'^\d+\.', l.strip())]
    for l in lines[:6]: print(l.strip())
" 2>/dev/null | while IFS= read -r line; do echo -e "  ${DIM}$line${N}"; done || true
fi

# Phase gates summary
echo ""
echo -e "  ${B}Phase 1 Gates:${N}"
echo -e "  ${G}Standard: 85.5% ✓${N}  ${R}Graph: 68.7% ✗${N}  ${R}Quant: 78.3% ✗${N}  ${G}Orch: 80.0% ✓${N}"

echo ""
echo -e "${B}${C}════════════════════════════════════════════════════${N}"
echo -e "${B}${C}  Ready. Run: bash scripts/start-session.sh${N}"
echo -e "${B}${C}════════════════════════════════════════════════════${N}"
echo ""
