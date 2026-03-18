#!/bin/bash
# ══════════════════════════════════════════════════════════════
# Claude Code Session Launcher — Nomos v4.0 (NBA Quant + HuggingClaw)
# ══════════════════════════════════════════════════════════════
# Architecture v13: Adam (CLI) + Eve (OpenClaw) + Cain (Evolution)
#   Focus: 100% NBA Quant AI Model
#   5 HF Spaces: S10, S11, S7, OpenClaw, LiteLLM-2
#
# Usage:
#   bash ~/mon-ipad/scripts/claude-session.sh --skip-perms
#   bash ~/mon-ipad/scripts/claude-session.sh                  # with perms
#   bash ~/mon-ipad/scripts/claude-session.sh --resume         # resume
#   bash ~/mon-ipad/scripts/claude-session.sh --health         # check only
#   bash ~/mon-ipad/scripts/claude-session.sh "ta question"    # one-shot
# ══════════════════════════════════════════════════════════════

set -euo pipefail

PROJECT_DIR="$HOME/mon-ipad"
cd "$PROJECT_DIR"

# Load environment
source .env.local 2>/dev/null

# Ensure PATH
export PATH="$HOME/.npm-global/bin:$PATH"

# Force IPv4 — GCP VM IPv6 issues with HF
export CURL_FLAGS="--ipv4"

# Permission mode
PERMS_FLAG=""
if [[ "${1:-}" == "--skip-perms" ]]; then
    PERMS_FLAG="--dangerously-skip-permissions"
    shift
fi

# Colors
R='\033[0;31m' G='\033[0;32m' Y='\033[1;33m' C='\033[0;36m' W='\033[1;37m' NC='\033[0m'
DIM='\033[2m'

# ── Pre-flight cleanup ──────────────────────────────────────
cleanup() {
    echo -e "${C}━━━ PRE-FLIGHT CLEANUP ━━━${NC}"

    # Kill zombie claude processes
    local zombies=$(pgrep -a claude 2>/dev/null | grep -v "$$" | grep -v "claude-session" | wc -l)
    if [ "$zombies" -gt 0 ]; then
        echo -e "  ${R}Zombies: ${zombies}${NC} — killing..."
        pgrep -a claude 2>/dev/null | grep -v "$$" | grep -v "claude-session" | while read pid rest; do
            kill "$pid" 2>/dev/null || true
        done
        sleep 2
    else
        echo -e "  Zombies: ${G}0${NC}"
    fi
    echo ""
}

# ── Health check — v13 NBA-only architecture ─────────────────
health_check() {
    echo -e "${W}╔══════════════════════════════════════════════════════╗${NC}"
    echo -e "${W}║  ${C}NOMOS NBA QUANT AI${NC}${W}  —  $(date -u +%H:%M:%SZ)  —  VM GCP${W}    ║${NC}"
    echo -e "${W}╚══════════════════════════════════════════════════════╝${NC}"
    echo ""

    # ── System ───────────────────────────────────────────────
    echo -e "${C}[SYSTEM]${NC}"
    local version=$(claude --version 2>/dev/null || echo "NOT FOUND")
    echo -e "  Claude Code: ${G}${version}${NC}"

    local ram_avail=$(free -m | awk '/Mem:/{print $7}')
    local swap_used=$(free -m | awk '/Swap:/{print $3}')
    local disk_pct=$(df -h / | awk 'NR==2{print $5}' | tr -d '%')

    local ram_color=$G; [ "$ram_avail" -lt 350 ] && ram_color=$Y; [ "$ram_avail" -lt 200 ] && ram_color=$R
    local disk_color=$G; [ "$disk_pct" -gt 85 ] && disk_color=$R

    echo -e "  RAM: ${ram_color}${ram_avail}MB${NC} | Swap: ${swap_used}MB | Disk: ${disk_color}${disk_pct}%${NC}"

    # ── HF Spaces (5 actifs) ─────────────────────────────────
    echo -e "\n${C}[HF SPACES — 5 ACTIVE]${NC}"
    local spaces_up=0
    for space_info in \
        "S10-Evolution:lbjlincoln-nomos-nba-quant" \
        "S11-Training:lbjlincoln-nomos-nba-quant-2" \
        "S7-LiteLLM:lbjlincoln-nomos-rag-engine-7" \
        "OpenClaw-Eve:nomos42-nomos-worker-2" \
        "LiteLLM-2:nomos42-nomos-litellm-2"; do
        label="${space_info%%:*}"
        space="${space_info#*:}"
        status=$(curl -4 -s -o /dev/null -w "%{http_code}" --max-time 8 "https://${space}.hf.space/" 2>/dev/null || echo "000")
        if [ "$status" = "200" ] || [ "$status" = "302" ]; then
            echo -ne "  ${G}●${NC} ${label}  "
            spaces_up=$((spaces_up + 1))
        else
            echo -ne "  ${R}✗${NC} ${label}(${status})  "
        fi
    done
    echo -e "\n  Total: ${G}${spaces_up}/5${NC}"

    # ── OpenClaw (Eve) detail ─────────────────────────────────
    echo -e "\n${C}[OPENCLAW — EVE]${NC}"
    local claw_resp=$(curl -4 -s --max-time 10 "https://nomos42-nomos-worker-2.hf.space/keep-alive" 2>/dev/null)
    if [ -n "$claw_resp" ]; then
        local claw_ver=$(echo "$claw_resp" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('version','?'))" 2>/dev/null || echo "?")
        local claw_up=$(echo "$claw_resp" | python3 -c "import sys,json; d=json.load(sys.stdin); u=d.get('uptime',0); print(f'{u//60}m' if isinstance(u,int) else u)" 2>/dev/null || echo "?")
        echo -e "  Version: ${G}${claw_ver}${NC} | Uptime: ${claw_up}"
    else
        echo -e "  ${R}NOT RESPONDING${NC}"
    fi

    # ── NBA Bankroll ─────────────────────────────────────────
    echo -e "\n${C}[NBA BANKROLL]${NC}"
    if [ -f "$HOME/nomos-nba-agent/data/bankroll/state.json" ]; then
        python3 -c "
import json
s = json.load(open('$HOME/nomos-nba-agent/data/bankroll/state.json'))
bal = s.get('balance', 0)
init = s.get('initial_balance', 1)
growth = (bal / init - 1) * 100
wins = s.get('wins', 0)
losses = s.get('losses', 0)
pending = s.get('pending', 0)
print(f'  Balance: \${bal:,.2f} ({growth:+.1f}%) | Record: {wins}W-{losses}L | Pending: {pending}')
" 2>/dev/null || echo -e "  ${Y}Error reading bankroll${NC}"
    else
        echo -e "  ${Y}No bankroll state${NC}"
    fi

    # ── HTTP Data Server ──────────────────────────────────────
    echo -e "\n${C}[HTTP DATA SERVER]${NC}"
    local http_check=$(curl -s --max-time 2 http://localhost:8080/ 2>/dev/null && echo "UP" || echo "DOWN")
    if [ "$http_check" = "UP" ]; then
        echo -e "  localhost:8080: ${G}SERVING${NC}"
    else
        echo -e "  localhost:8080: ${R}DOWN${NC}"
        echo -e "  ${Y}Fix: cd $PROJECT_DIR && nohup python3 -m http.server 8080 -b 0.0.0.0 &${NC}"
    fi

    # ── Git ──────────────────────────────────────────────────
    echo -e "\n${C}[GIT]${NC}"
    local branch=$(git branch --show-current 2>/dev/null)
    local dirty=$(git status --porcelain 2>/dev/null | wc -l)
    local last_commit=$(git log --oneline -1 2>/dev/null)
    if [ "$dirty" -gt 0 ]; then
        echo -e "  ${Y}${branch} (${dirty} uncommitted)${NC}"
    else
        echo -e "  ${G}${branch} (clean)${NC}"
    fi
    echo -e "  ${DIM}Last: ${last_commit}${NC}"

    echo -e "\n${W}══════════════════════════════════════════════════════${NC}\n"
}

# Main
case "${1:-}" in
    --health)
        health_check
        exit 0
        ;;
    --resume)
        echo -e "${C}Resuming last Claude session...${NC}"
        claude --resume --model claude-opus-4-6 $PERMS_FLAG
        ;;
    "")
        # Interactive mode
        cleanup
        health_check

        # Ensure HTTP server
        if ! curl -s --max-time 1 http://localhost:8080/ > /dev/null 2>&1; then
            echo -e "${C}[Starting HTTP data server]${NC}"
            cd "$PROJECT_DIR" && nohup python3 -m http.server 8080 -b 0.0.0.0 > /dev/null 2>&1 &
            echo -e "  Started on port 8080 ${G}✓${NC}"
        fi

        echo ""
        echo -e "${C}Launching Claude Code (Opus 4.6)...${NC}"
        echo -e "${Y}Skills: /session-start | /monitor | /eval | /status-check | /self-heal | /improve${NC}"
        echo -e "${DIM}Adam (CLI) + Eve (OpenClaw) + Cain (Evolution) — NBA Quant AI${NC}"
        echo ""
        claude --model claude-opus-4-6 $PERMS_FLAG
        ;;
    *)
        # Direct question mode
        cleanup
        health_check
        echo -e "${C}Running: ${1}${NC}"
        echo ""
        claude -p "$*" --model claude-opus-4-6 $PERMS_FLAG
        ;;
esac
