#!/bin/bash
# Start Nomos42 Brain bot (NBA-focused)
# RGWA bot has moved to ~/rgwa/scripts/telegram/
# Usage: ./start_bots.sh [start|stop|status]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source ~/.env.local 2>/dev/null || true

MODE="${1:-start}"

start_brain() {
    if [ -f /tmp/nomos42-brain.pid ] && kill -0 "$(cat /tmp/nomos42-brain.pid)" 2>/dev/null; then
        echo "Brain bot already running (PID $(cat /tmp/nomos42-brain.pid))"
        return
    fi
    echo "[$(date +%H:%M:%S)] Starting Nomos42 Brain bot..."
    nohup python3 "$SCRIPT_DIR/nomos42_brain.py" >> /tmp/nomos42-brain.log 2>&1 &
    echo $! > /tmp/nomos42-brain.pid
    echo "  PID: $(cat /tmp/nomos42-brain.pid) | Log: /tmp/nomos42-brain.log"
}

stop_brain() {
    if [ -f /tmp/nomos42-brain.pid ]; then
        pid=$(cat /tmp/nomos42-brain.pid)
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid"
            echo "Stopped Brain bot (PID $pid)"
        fi
        rm -f /tmp/nomos42-brain.pid
    else
        echo "Brain bot not running"
    fi
}

case "$MODE" in
    start)  start_brain ;;
    stop)   stop_brain ;;
    status)
        if [ -f /tmp/nomos42-brain.pid ] && kill -0 "$(cat /tmp/nomos42-brain.pid)" 2>/dev/null; then
            echo "Brain bot running (PID $(cat /tmp/nomos42-brain.pid))"
        else
            echo "Brain bot not running"
        fi
        ;;
    *)  echo "Usage: $0 [start|stop|status]" ;;
esac

echo ""
echo "Note: RGWA bot moved to ~/rgwa/scripts/telegram/start_bot.sh"
