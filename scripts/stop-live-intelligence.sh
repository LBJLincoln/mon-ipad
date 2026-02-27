#!/bin/bash
# Stop Live Intelligence System
# Usage: bash scripts/stop-live-intelligence.sh

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$BASE_DIR/logs/live-intelligence.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "PID file not found. Live Intelligence System may not be running."
    exit 1
fi

PID=$(cat "$PID_FILE")

if ps -p "$PID" > /dev/null 2>&1; then
    echo "Stopping Live Intelligence System (PID: $PID)..."
    kill -TERM "$PID"

    # Wait up to 10 seconds for graceful shutdown
    for i in {1..10}; do
        if ! ps -p "$PID" > /dev/null 2>&1; then
            echo "Live Intelligence System stopped."
            rm "$PID_FILE"
            exit 0
        fi
        sleep 1
    done

    # Force kill if still running
    echo "Graceful shutdown failed, force killing..."
    kill -9 "$PID"
    rm "$PID_FILE"
    echo "Live Intelligence System force-stopped."
else
    echo "Process $PID not running. Removing stale PID file."
    rm "$PID_FILE"
fi
