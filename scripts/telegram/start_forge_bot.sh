#!/bin/bash
# Start/stop Forge42 Bot (@Forge42Bot)
# Forge Factory user-facing Telegram bot
# Usage: ./start_forge_bot.sh [start|stop|status|restart]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="/tmp/forge42-bot.pid"
LOG_FILE="/tmp/forge-bot.log"

# Source mon-ipad env for tokens
[ -f /home/lahargnedebartoli/mon-ipad/.env.local ] && source /home/lahargnedebartoli/mon-ipad/.env.local 2>/dev/null

MODE="${1:-start}"

start_forge() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "Forge42 bot already running (PID $(cat "$PID_FILE"))"
        return
    fi

    # Accept either env var name
    [ -z "$FORGE_BOT_TOKEN" ] && export FORGE_BOT_TOKEN="${FORGE42_BOT_TOKEN:-}"
    if [ -z "$FORGE_BOT_TOKEN" ]; then
        echo "ERROR: FORGE_BOT_TOKEN / FORGE42_BOT_TOKEN not set."
        echo "  Add it to /home/lahargnedebartoli/mon-ipad/.env.local or export it before running."
        exit 1
    fi

    echo "[$(date +%H:%M:%S)] Starting Forge42 bot..."
    nohup python3 "$SCRIPT_DIR/forge_bot.py" >> "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    echo "  PID: $(cat "$PID_FILE") | Log: $LOG_FILE"
}

stop_forge() {
    if [ -f "$PID_FILE" ]; then
        pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid"
            echo "Stopped Forge42 bot (PID $pid)"
        else
            echo "Forge42 bot not running (stale PID file)"
        fi
        rm -f "$PID_FILE"
    else
        echo "Forge42 bot not running"
    fi
}

status_forge() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "Forge42 bot running (PID $(cat "$PID_FILE"))"
        echo "Log: $LOG_FILE"
        echo "Last 5 lines:"
        tail -5 "$LOG_FILE" 2>/dev/null || echo "  (log empty)"
    else
        echo "Forge42 bot NOT running"
    fi
}

case "$MODE" in
    start)   start_forge ;;
    stop)    stop_forge ;;
    restart) stop_forge; sleep 1; start_forge ;;
    status)  status_forge ;;
    *)       echo "Usage: $0 [start|stop|restart|status]" ;;
esac
