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
# ============================================================

set -euo pipefail

PROJECT_DIR="$HOME/mon-ipad"
cd "$PROJECT_DIR"

# Load environment
source .env.local 2>/dev/null

# Ensure PATH includes latest Claude Code
export PATH="$HOME/.npm-global/bin:$PATH"

# Force IPv4 — some HF Spaces unreachable via IPv6 from GCP VM
export CURL_FLAGS="--ipv4"

# Permission mode
PERMS_FLAG=""
if [[ "${1:-}" == "--skip-perms" ]]; then
    PERMS_FLAG="--dangerously-skip-permissions"
    shift
fi

# Auto session-start system prompt
LATEST_STATE=$(ls -t directives/SYSTEM-STATE-S*.md 2>/dev/null | head -1 || echo "directives/PROJECT-STATE.md")
AUTO_START="CRITICAL: At the START of every conversation, BEFORE responding to the user, automatically execute ALL steps from the /session-start skill: read ${LATEST_STATE}, read directives/PROJECT-STATE.md, source .env.local, check pipeline health, check database status, and output a concise session brief. Also git pull origin main first, then check if the user has created any new docs in the repo (git log --oneline -10). Do this even if the user has not asked — it is mandatory startup procedure."

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# ── Pre-flight cleanup ──────────────────────────────────────
cleanup() {
    echo -e "${CYAN}[Pre-flight Cleanup]${NC}"

    # Kill zombie claude processes (not the one we're about to start)
    local zombies=$(pgrep -a claude 2>/dev/null | grep -v "$$" | grep -v "claude-session" | wc -l)
    if [ "$zombies" -gt 0 ]; then
        echo -e "  Zombie claude processes: ${RED}${zombies}${NC}"
        pgrep -a claude 2>/dev/null | grep -v "$$" | grep -v "claude-session" | while read pid rest; do
            echo -e "    Killing PID $pid: $rest"
            kill "$pid" 2>/dev/null || true
        done
        sleep 2
    else
        echo -e "  No zombie processes ${GREEN}✓${NC}"
    fi

    # Kill stale background processes from previous sessions
    local stale_python=$(pgrep -af "python3.*(eval|ingest|metrics|self-heal)" 2>/dev/null | wc -l)
    if [ "$stale_python" -gt 0 ]; then
        echo -e "  Stale background Python: ${YELLOW}${stale_python} processes${NC}"
        pgrep -af "python3.*(eval|ingest|metrics|self-heal)" 2>/dev/null | while read pid rest; do
            echo -e "    → PID $pid: ${rest:0:60}"
        done
        echo -e "  ${YELLOW}(Not killing — may be intentional. Use 'kill PID' manually)${NC}"
    fi

    echo ""
}

# ── Health check ─────────────────────────────────────────────
health_check() {
    echo -e "${CYAN}[Health Check]${NC}"

    # Claude Code version
    local version=$(claude --version 2>/dev/null || echo "NOT FOUND")
    echo -e "  Claude Code: ${GREEN}${version}${NC}"

    # RAM
    local ram_avail=$(free -m | awk '/Mem:/{print $7}')
    local swap_used=$(free -m | awk '/Swap:/{print $3}')
    if [ "$ram_avail" -lt 200 ]; then
        echo -e "  RAM: ${RED}${ram_avail}MB available (LOW!) | Swap: ${swap_used}MB${NC}"
        echo -e "  ${RED}→ Consider killing background processes before starting${NC}"
    elif [ "$ram_avail" -lt 350 ]; then
        echo -e "  RAM: ${YELLOW}${ram_avail}MB available | Swap: ${swap_used}MB${NC}"
    else
        echo -e "  RAM: ${GREEN}${ram_avail}MB available | Swap: ${swap_used}MB${NC}"
    fi

    # Disk
    local disk_pct=$(df -h / | awk 'NR==2{print $5}' | tr -d '%')
    if [ "$disk_pct" -gt 85 ]; then
        echo -e "  Disk: ${RED}${disk_pct}% used${NC}"
    else
        echo -e "  Disk: ${GREEN}${disk_pct}% used${NC}"
    fi

    # HF Spaces quick ping (parallel, 5s timeout each, force IPv4)
    echo -e "  ${CYAN}HF Spaces:${NC}"
    for space_info in "S1:lbjlincoln-nomos-rag-engine" "S3:lbjlincoln-nomos-rag-engine-3" "S5:lbjlincoln-nomos-rag-engine-5" "S9:lbjlincoln-nomos-rag-engine-9" "S6:lbjlincoln-nomos-docling-api"; do
        label="${space_info%%:*}"
        space="${space_info#*:}"
        status=$(curl -4 -s -o /dev/null -w "%{http_code}" --max-time 5 "https://${space}.hf.space/healthz" 2>/dev/null || echo "000")
        # Docling uses /health not /healthz
        if [ "$status" = "000" ] && [ "$label" = "S6" ]; then
            status=$(curl -4 -s -o /dev/null -w "%{http_code}" --max-time 5 "https://${space}.hf.space/health" 2>/dev/null || echo "000")
        fi
        if [ "$status" = "200" ]; then
            echo -e "    $label: ${GREEN}UP${NC}"
        elif [ "$status" = "000" ]; then
            echo -e "    $label: ${RED}DOWN/SLEEP${NC}"
        else
            echo -e "    $label: ${YELLOW}${status}${NC}"
        fi
    done &
    wait

    # Check progress files from previous session
    if [ -f "data/eval/progress.json" ]; then
        local eval_info=$(python3 -c "import json; d=json.load(open('data/eval/progress.json')); print(f'{d.get(\"current\",0)}/{d.get(\"total\",0)} ({d.get(\"sector\",\"?\")})')" 2>/dev/null || echo "?")
        echo -e "  Last eval: ${YELLOW}${eval_info}${NC}"
    fi
    if [ -f "data/ingest/progress.json" ]; then
        local ingest_info=$(python3 -c "import json; d=json.load(open('data/ingest/progress.json')); print(f'{d.get(\"processed\",0)} processed ({d.get(\"sector\",\"?\")})')" 2>/dev/null || echo "?")
        echo -e "  Last ingest: ${YELLOW}${ingest_info}${NC}"
    fi

    # Agent status
    echo -e "  ${CYAN}Agents:${NC}"
    for agent in monitor eval ingest pipeline docs; do
        pidfile="data/agents/${agent}.pid"
        if [ -f "$pidfile" ]; then
            pid=$(cat "$pidfile")
            if kill -0 "$pid" 2>/dev/null; then
                echo -e "    $agent: ${GREEN}RUNNING (PID $pid)${NC}"
            else
                echo -e "    $agent: ${RED}DEAD (stale PID $pid)${NC}"
            fi
        else
            echo -e "    $agent: ${YELLOW}STOPPED${NC}"
        fi
    done

    # Git status
    local branch=$(git branch --show-current 2>/dev/null)
    local dirty=$(git status --porcelain 2>/dev/null | wc -l)
    if [ "$dirty" -gt 0 ]; then
        echo -e "  Git: ${YELLOW}${branch} (${dirty} uncommitted)${NC}"
    else
        echo -e "  Git: ${GREEN}${branch} (clean)${NC}"
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
        for task in "$@"; do
            echo -e "${YELLOW}>>> Task: ${task}${NC}"
            claude -p "$task" --model claude-opus-4-6 $PERMS_FLAG &
        done
        wait
        echo -e "${GREEN}All batch tasks completed.${NC}"
        ;;
    "")
        # Interactive mode with auto session-start
        cleanup
        health_check
        # Auto-launch agents if not running
        echo -e "${CYAN}[Auto-launching agents]${NC}"
        python3 ops/agents.py launch all 2>/dev/null || echo -e "  ${YELLOW}Agent launch skipped (manual: python3 ops/agents.py launch all)${NC}"
        echo ""
        echo -e "${CYAN}Launching interactive Claude session (Opus 4.6)...${NC}"
        echo -e "${YELLOW}Skills: /session-start | /monitor | /eval | /status-check | /self-heal${NC}"
        echo ""
        claude --model claude-opus-4-6 $PERMS_FLAG \
            --append-system-prompt "$AUTO_START"
        ;;
    *)
        # Direct question mode
        cleanup
        health_check
        echo -e "${CYAN}Running: ${1}${NC}"
        echo ""
        claude -p "$*" --model claude-opus-4-6 $PERMS_FLAG \
            --append-system-prompt "$AUTO_START"
        ;;
esac
