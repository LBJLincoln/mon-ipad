#!/bin/bash
# ============================================================
# Claude Code Session Launcher — Termius Snippet
# ============================================================
# Usage:
#   claude-session "ta question ici"
#   claude-session                     # mode interactif
#   claude-session --resume            # reprend dernière session
#   claude-session --batch "task1" "task2" "task3"  # parallel sub-agents
#
# Snippet Termius (RECOMMANDÉ):
#   bash ~/mon-ipad/scripts/claude-session.sh
# Ou avec --dangerously-skip-permissions:
#   bash ~/mon-ipad/scripts/claude-session.sh --skip-perms
# Ancien (sans auto session-start):
#   cd ~/mon-ipad && claude --dangerously-skip-permissions
# ============================================================

set -euo pipefail

PROJECT_DIR="$HOME/mon-ipad"
cd "$PROJECT_DIR"

# Load environment
source .env.local 2>/dev/null

# Ensure PATH includes latest Claude Code
export PATH="$HOME/.npm-global/bin:$PATH"

# Permission mode
PERMS_FLAG=""
if [[ "${1:-}" == "--skip-perms" ]]; then
    PERMS_FLAG="--dangerously-skip-permissions"
    shift
fi

# Auto session-start system prompt
AUTO_START='CRITICAL: At the START of every conversation, BEFORE responding to the user, automatically execute ALL steps from the /session-start skill: read PROJECT-STATE.md, read DEBUG-PLAYBOOK.md (first 100 lines), source .env.local, check pipeline health, check database status, and output a concise session brief. Do this even if the user has not asked — it is mandatory startup procedure.'

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Quick health check
health_check() {
    echo -e "${CYAN}[Health Check]${NC}"

    # Claude Code version
    local version=$(claude --version 2>/dev/null || echo "NOT FOUND")
    echo -e "  Claude Code: ${GREEN}${version}${NC}"

    # RAM
    local ram_avail=$(free -m | awk '/Mem:/{print $7}')
    if [ "$ram_avail" -lt 200 ]; then
        echo -e "  RAM: ${RED}${ram_avail}MB available (LOW)${NC}"
    else
        echo -e "  RAM: ${GREEN}${ram_avail}MB available${NC}"
    fi

    # HF Space quick ping (async, non-blocking)
    local n8n_status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$N8N_HOST/" 2>/dev/null || echo "000")
    if [ "$n8n_status" = "200" ]; then
        echo -e "  n8n Space: ${GREEN}UP${NC}"
    else
        echo -e "  n8n Space: ${YELLOW}${n8n_status} (may be sleeping)${NC}"
    fi

    echo ""
}

# Main
case "${1:-}" in
    --health)
        health_check
        exit 0
        ;;
    --resume)
        echo -e "${CYAN}Resuming last Claude session...${NC}"
        claude --resume --model claude-opus-4-6 $PERMS_FLAG
        ;;
    --batch)
        shift
        echo -e "${CYAN}Launching batch mode with ${#@} tasks...${NC}"
        # Each task gets its own sub-agent via claude -p
        for task in "$@"; do
            echo -e "${YELLOW}>>> Task: ${task}${NC}"
            claude -p "$task" --model claude-opus-4-6 $PERMS_FLAG &
        done
        wait
        echo -e "${GREEN}All batch tasks completed.${NC}"
        ;;
    "")
        # Interactive mode with auto session-start
        health_check
        echo -e "${CYAN}Launching interactive Claude session (Opus 4.6)...${NC}"
        echo -e "${YELLOW}Skills: /session-start | /monitor | /eval | /status-check | /self-heal${NC}"
        echo ""
        claude --model claude-opus-4-6 $PERMS_FLAG \
            --append-system-prompt "$AUTO_START"
        ;;
    *)
        # Direct question mode
        health_check
        echo -e "${CYAN}Running: ${1}${NC}"
        echo ""
        claude -p "$*" --model claude-opus-4-6 $PERMS_FLAG \
            --append-system-prompt "$AUTO_START"
        ;;
esac
