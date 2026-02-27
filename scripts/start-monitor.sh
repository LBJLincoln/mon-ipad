#!/bin/bash
# Start continuous-monitor.py as background daemon
# Usage: bash scripts/start-monitor.sh

REPO_ROOT="/home/termius/mon-ipad"
SCRIPT="$REPO_ROOT/scripts/continuous-monitor.py"
LOG_FILE="$REPO_ROOT/logs/monitor/daemon.log"
PID_FILE="$REPO_ROOT/logs/monitor/daemon.pid"

# Check if already running
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "Monitor already running (PID $PID)"
        exit 1
    else
        echo "Removing stale PID file"
        rm -f "$PID_FILE"
    fi
fi

# Start monitor in background
echo "Starting continuous monitor..."
source "$REPO_ROOT/.env.local"
nohup python3 "$SCRIPT" > "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"

echo "Monitor started (PID $(cat $PID_FILE))"
echo "Logs: $LOG_FILE"
echo ""
echo "To check status:"
echo "  tail -f $LOG_FILE"
echo ""
echo "To stop:"
echo "  bash scripts/stop-monitor.sh"
