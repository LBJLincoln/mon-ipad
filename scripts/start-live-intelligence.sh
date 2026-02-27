#!/bin/bash
# Start Live Intelligence System
# Usage: bash scripts/start-live-intelligence.sh

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="$BASE_DIR/logs/live-intelligence.log"
PID_FILE="$BASE_DIR/logs/live-intelligence.pid"

# Check if already running
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "Live Intelligence System already running (PID: $PID)"
        echo "To stop: kill $PID"
        exit 1
    else
        echo "Stale PID file found, removing..."
        rm "$PID_FILE"
    fi
fi

# Ensure logs directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# Start daemon
echo "Starting Live Intelligence System..."
nohup python3 "$BASE_DIR/scripts/live-intelligence.py" > "$LOG_FILE" 2>&1 &
PID=$!

# Save PID
echo "$PID" > "$PID_FILE"

echo "Live Intelligence System started (PID: $PID)"
echo "Log file: $LOG_FILE"
echo "Report: $BASE_DIR/logs/live-intelligence-report.json"
echo ""
echo "To monitor: tail -f $LOG_FILE"
echo "To stop: kill $PID"
echo "To check status: ps -p $PID"
