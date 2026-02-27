#!/bin/bash
# Stop continuous-monitor.py daemon
# Usage: bash scripts/stop-monitor.sh

REPO_ROOT="/home/termius/mon-ipad"
PID_FILE="$REPO_ROOT/logs/monitor/daemon.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "Monitor not running (no PID file)"
    exit 1
fi

PID=$(cat "$PID_FILE")
if ! ps -p "$PID" > /dev/null 2>&1; then
    echo "Monitor not running (stale PID file)"
    rm -f "$PID_FILE"
    exit 1
fi

echo "Stopping monitor (PID $PID)..."
kill -TERM "$PID"

# Wait up to 10s for graceful shutdown
for i in {1..10}; do
    if ! ps -p "$PID" > /dev/null 2>&1; then
        echo "Monitor stopped"
        rm -f "$PID_FILE"
        exit 0
    fi
    sleep 1
done

echo "Monitor did not stop gracefully, forcing..."
kill -9 "$PID"
rm -f "$PID_FILE"
echo "Monitor stopped (forced)"
