#!/usr/bin/env bash
# ============================================================================
# Nomos42 Cross-Device Tmux — Shared Session Across iPad + Laptop
# ============================================================================
#
# Creates or attaches to the shared "nomos42" tmux session.
# Designed for multi-device monitoring via Termius (iPad) and SSH (laptop).
#
# USAGE:
#
#   On the VM directly:
#     ./cross-device-tmux.sh                    # Create or attach
#     ./cross-device-tmux.sh dashboard          # Create with full dashboard
#     ./cross-device-tmux.sh status             # Check session status
#     ./cross-device-tmux.sh kill               # Kill session
#
#   From iPad (Termius app):
#     SSH Host: 100.70.229.122 (Tailscale) or your VM's public IP
#     SSH User: termius
#     Post-connect command:
#       tmux attach -t nomos42 || /home/termius/mon-ipad/scripts/monitoring/cross-device-tmux.sh
#
#   From Laptop (SSH):
#     ssh termius@100.70.229.122 -t 'tmux attach -t nomos42 || /home/termius/mon-ipad/scripts/monitoring/cross-device-tmux.sh'
#
#   From Laptop (one-liner with dashboard):
#     ssh termius@100.70.229.122 -t '/home/termius/mon-ipad/scripts/monitoring/cross-device-tmux.sh dashboard'
#
# MULTI-DEVICE SIMULTANEOUS ACCESS:
#   Device 1: tmux attach -t nomos42
#   Device 2: tmux attach -t nomos42
#   Both see the same session in real-time. Use Ctrl-B + D to detach.
#
#   For independent cursors (different windows on each device):
#   Device 2: tmux new-session -t nomos42 -s nomos42-ipad
#   This creates a "grouped session" — shared windows, independent active window.
#
# TERMIUS SETUP (iPad):
#   1. Add new host: IP=100.70.229.122, User=termius, Key=your SSH key
#   2. In host settings, set "Startup Command":
#      tmux attach -t nomos42 || /home/termius/mon-ipad/scripts/monitoring/cross-device-tmux.sh
#   3. Connect. You'll see the shared tmux session.
#   4. Navigate: swipe left/right for tmux windows (or Ctrl-B + 0-5)
#
# LAPTOP SETUP (Windows/Mac/Linux):
#   1. Ensure Tailscale is connected (or use public IP)
#   2. Add SSH config (~/.ssh/config):
#        Host nomos42-vm
#          HostName 100.70.229.122
#          User termius
#          RequestTTY yes
#          RemoteCommand tmux attach -t nomos42 || /home/termius/mon-ipad/scripts/monitoring/cross-device-tmux.sh
#   3. Then just: ssh nomos42-vm
#
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SESSION="nomos42"
BASE="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DASH_SCRIPT="${SCRIPT_DIR}/tmux-dashboard.sh"
LIVE_STATUS="${SCRIPT_DIR}/live-status.py"

# ── Colors for output ────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ── Functions ─────────────────────────────────────────────────────────────────

print_banner() {
    echo -e "${GREEN}${BOLD}"
    echo "  ============================================"
    echo "    NOMOS42 — Cross-Device Monitoring"
    echo "  ============================================"
    echo -e "${NC}"
}

print_help() {
    print_banner
    echo -e "${CYAN}Usage:${NC}"
    echo "  $0              Create or attach to session"
    echo "  $0 dashboard    Create with full tmux dashboard (6 windows)"
    echo "  $0 live         Launch Rich live-status.py in the session"
    echo "  $0 status       Check if session exists"
    echo "  $0 kill         Kill the session"
    echo "  $0 help         Show this help"
    echo ""
    echo -e "${CYAN}Multi-device:${NC}"
    echo "  iPad:   ssh termius@100.70.229.122 -t 'tmux attach -t $SESSION'"
    echo "  Laptop: ssh termius@100.70.229.122 -t 'tmux attach -t $SESSION'"
    echo "  Grouped: tmux new-session -t $SESSION -s ${SESSION}-ipad"
    echo ""
}

session_exists() {
    tmux has-session -t "$SESSION" 2>/dev/null
}

create_simple_session() {
    echo -e "${YELLOW}Creating simple session '$SESSION'...${NC}"
    tmux new-session -d -s "$SESSION" -n "main" -x 200 -y 50

    # Set up a useful default window
    tmux send-keys -t "$SESSION:0" "cd $BASE && echo 'Nomos42 monitoring session ready.' && echo 'Run: python3 scripts/monitoring/live-status.py'" Enter

    # Style
    tmux set-option -t "$SESSION" status-style "bg=colour235,fg=colour136"
    tmux set-option -t "$SESSION" status-left "#[fg=colour46,bold] NOMOS42 #[fg=colour245]| "
    tmux set-option -t "$SESSION" status-right "#[fg=colour245]%Y-%m-%d %H:%M"
    tmux set-option -t "$SESSION" pane-active-border-style "fg=colour46"

    echo -e "${GREEN}Session '$SESSION' created.${NC}"
}

# ── Main ──────────────────────────────────────────────────────────────────────

case "${1:-}" in
    help|--help|-h)
        print_help
        exit 0
        ;;
    kill)
        if session_exists; then
            tmux kill-session -t "$SESSION"
            echo -e "${GREEN}Session '$SESSION' killed.${NC}"
        else
            echo -e "${YELLOW}No session '$SESSION' found.${NC}"
        fi
        exit 0
        ;;
    status)
        print_banner
        if session_exists; then
            echo -e "${GREEN}Session '$SESSION' is RUNNING.${NC}"
            echo ""
            echo "Windows:"
            tmux list-windows -t "$SESSION" 2>/dev/null | while read -r line; do
                echo "  $line"
            done
            echo ""
            echo "Clients attached:"
            tmux list-clients -t "$SESSION" 2>/dev/null | while read -r line; do
                echo "  $line"
            done || echo "  (none)"
        else
            echo -e "${YELLOW}Session '$SESSION' is NOT running.${NC}"
        fi
        exit 0
        ;;
    dashboard)
        if session_exists; then
            echo -e "${YELLOW}Session '$SESSION' already exists. Attaching...${NC}"
            exec tmux attach-session -t "$SESSION"
        fi
        # Use the full dashboard script if available
        if [ -x "$DASH_SCRIPT" ]; then
            # The dashboard script creates its own session name, so we'll
            # create our session and populate it similarly
            echo -e "${YELLOW}Creating dashboard session '$SESSION'...${NC}"

            # Source the dashboard creation logic with our session name
            # We create a wrapper that runs the dashboard in a renamed session
            tmux new-session -d -s "$SESSION" -n "live" -x 200 -y 50
            tmux send-keys -t "$SESSION:0" "python3 $LIVE_STATUS --refresh 10" Enter

            # Add a plain shell window
            tmux new-window -t "$SESSION" -n "shell"
            tmux send-keys -t "$SESSION:1" "cd $BASE" Enter

            # Add monitoring windows
            tmux new-window -t "$SESSION" -n "evolution"
            tmux send-keys -t "$SESSION:2" "watch -n 60 'python3 -c \"
import json
d = json.load(open(\\\"$BASE/data/infra-status.json\\\"))
print(\\\"=== HF EVOLUTION FLEET ===\")
print(f\\\"Updated: {d.get(\\\"timestamp\\\", \\\"?\\\")}\\\")
s = d.get(\\\"summary\\\", {})
print(f\\\"Healthy: {s.get(\\\"healthy\\\", \\\"?\\\")}/{s.get(\\\"total\\\", \\\"?\\\")}\\\")
print()
for name, info in d.get(\\\"hf_spaces\\\", {}).items():
    if isinstance(info, dict):
        print(f\\\"  {name:>8}: brier={info.get(\\\"brier\\\", \\\"?\\\"):>8} gen={info.get(\\\"gen\\\", \\\"?\\\"):>6} status={info.get(\\\"status\\\", \\\"?\\\")}\\\")
\"'" Enter

            tmux new-window -t "$SESSION" -n "trading"
            tmux send-keys -t "$SESSION:3" "watch -n 30 'python3 -c \"
import json, os
tf = json.load(open(\\\"$BASE/data/arena/trading-floor-v4-latest.json\\\"))
lb = tf.get(\\\"leaderboard\\\", [])
print(\\\"=== TRADING FLOOR LEADERBOARD ===\")
for t in lb:
    e = \\\"ELIM\\\" if t.get(\\\"eliminated\\\") else \\\"OK\\\"
    print(f\\\"  #{t.get(\\\"rank\\\",\\\"?\\\"):<3} {t.get(\\\"name\\\",\\\"?\\\"):<12} \\\${t.get(\\\"nba_bankroll\\\",0):>11,.2f}  ROI:{t.get(\\\"nba_roi_pct\\\",0):>8.1f}%  Sharpe:{t.get(\\\"nba_sharpe\\\",0):.3f}  {e}\\\")
\"'" Enter

            tmux new-window -t "$SESSION" -n "councils"
            tmux send-keys -t "$SESSION:4" "watch -n 60 'python3 -c \"
import json, glob, os
print(\\\"=== DEPARTMENT COUNCILS ===\")
for f in sorted(glob.glob(\\\"$BASE/data/departments/council-*.json\\\")):
    try:
        d = json.load(open(f))
        dept = d.get(\\\"dept\\\", os.path.basename(f))
        print(f\\\"  {dept:<20} iter={d.get(\\\"iteration\\\",0):>4}  last={d.get(\\\"last_run\\\",\\\"?\\\")[:16]}\\\")
    except: pass
\"'" Enter

            tmux new-window -t "$SESSION" -n "system"
            tmux send-keys -t "$SESSION:5" "top -d 5" Enter

            # Style the session
            tmux set-option -t "$SESSION" status-style "bg=colour235,fg=colour136"
            tmux set-option -t "$SESSION" status-left "#[fg=colour46,bold] NOMOS42 #[fg=colour245]| "
            tmux set-option -t "$SESSION" status-right "#[fg=colour245]%Y-%m-%d %H:%M #[fg=colour136]| #[fg=colour46]1vCPU/969MB"
            tmux set-option -t "$SESSION" status-left-length 30
            tmux set-option -t "$SESSION" status-right-length 50
            tmux set-option -t "$SESSION" pane-active-border-style "fg=colour46"

            # Start at window 0 (live dashboard)
            tmux select-window -t "$SESSION:0"

            echo -e "${GREEN}Dashboard session '$SESSION' created with 6 windows.${NC}"
            exec tmux attach-session -t "$SESSION"
        else
            echo -e "${YELLOW}Dashboard script not found. Creating simple session.${NC}"
            create_simple_session
            exec tmux attach-session -t "$SESSION"
        fi
        ;;
    live)
        if session_exists; then
            # Send the live status command to the current window
            tmux send-keys -t "$SESSION" "python3 $LIVE_STATUS --refresh 10" Enter
            echo -e "${GREEN}Live status launched in session '$SESSION'.${NC}"
            exec tmux attach-session -t "$SESSION"
        fi
        create_simple_session
        tmux send-keys -t "$SESSION:0" "python3 $LIVE_STATUS --refresh 10" Enter
        exec tmux attach-session -t "$SESSION"
        ;;
    *)
        # Default: create or attach
        if session_exists; then
            echo -e "${GREEN}Attaching to existing session '$SESSION'...${NC}"
            exec tmux attach-session -t "$SESSION"
        fi

        print_banner
        echo -e "${YELLOW}No session found. Creating...${NC}"
        echo ""
        echo "  Options:"
        echo "    1) Simple session (shell + monitoring commands)"
        echo "    2) Full dashboard (6 windows, auto-monitoring)"
        echo ""

        # Default to simple for non-interactive (SSH RemoteCommand etc.)
        if [ ! -t 0 ]; then
            # Non-interactive — create simple and attach
            create_simple_session
            exec tmux attach-session -t "$SESSION"
        fi

        read -r -p "  Choice [1/2, default=2]: " choice
        case "${choice:-2}" in
            1)
                create_simple_session
                exec tmux attach-session -t "$SESSION"
                ;;
            2|*)
                # Relaunch ourselves with dashboard mode
                exec "$0" dashboard
                ;;
        esac
        ;;
esac
