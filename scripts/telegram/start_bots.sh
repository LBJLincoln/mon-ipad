#!/bin/bash
# Start/stop/status all Nomos42 Telegram bots
# Usage: ./start_bots.sh [start|stop|status|restart]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
set -a
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
[ -f "${_ROOT}/.env.local" ] && source "${_ROOT}/.env.local" 2>/dev/null
set +a

MODE="${1:-start}"

# Bot definitions: name, script, pidfile, token_var
BOTS=(
    "brain:nomos42_brain.py:nomos42-brain:TELEGRAM_BOT_TOKEN"
    "forge:forge_bot.py:forge-bot:FORGE_BOT_TOKEN"
    "nba:nomos_nba_bot.py:nba-bot:NOMOS_NBA_BOT_TOKEN"
    "political:stupid_political_bot.py:political-bot:STUPID_POLITICAL_BOT_TOKEN"
)

start_bot() {
    local name="$1" script="$2" pidname="$3" tokenvar="$4"
    local pidfile="/tmp/${pidname}.pid"
    local logfile="/tmp/${pidname}.log"

    if [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
        echo "  [$name] Already running (PID $(cat "$pidfile"))"
        return
    fi

    if [ -z "${!tokenvar}" ]; then
        echo "  [$name] SKIP — $tokenvar not set"
        return
    fi

    echo "  [$name] Starting..."
    nohup python3 "$SCRIPT_DIR/$script" >> "$logfile" 2>&1 &
    echo $! > "$pidfile"
    echo "  [$name] PID: $(cat "$pidfile") | Log: $logfile"
}

stop_bot() {
    local name="$1" script="$2" pidname="$3" tokenvar="$4"
    local pidfile="/tmp/${pidname}.pid"

    if [ -f "$pidfile" ]; then
        local pid=$(cat "$pidfile")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid"
            echo "  [$name] Stopped (PID $pid)"
        fi
        rm -f "$pidfile"
    else
        echo "  [$name] Not running"
    fi
}

status_bot() {
    local name="$1" script="$2" pidname="$3" tokenvar="$4"
    local pidfile="/tmp/${pidname}.pid"

    if [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
        echo "  [$name] RUNNING (PID $(cat "$pidfile"))"
    else
        if [ -z "${!tokenvar}" ]; then
            echo "  [$name] DISABLED ($tokenvar not set)"
        else
            echo "  [$name] DOWN"
        fi
    fi
}

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Nomos42 Bot Fleet — $MODE"
echo "================================================="

for bot in "${BOTS[@]}"; do
    IFS=':' read -r name script pidname tokenvar <<< "$bot"
    case "$MODE" in
        start)   start_bot "$name" "$script" "$pidname" "$tokenvar" ;;
        stop)    stop_bot "$name" "$script" "$pidname" "$tokenvar" ;;
        restart) stop_bot "$name" "$script" "$pidname" "$tokenvar"
                 sleep 1
                 start_bot "$name" "$script" "$pidname" "$tokenvar" ;;
        status)  status_bot "$name" "$script" "$pidname" "$tokenvar" ;;
    esac
done

echo ""
echo "RGWA bot: ~/rgwa/scripts/telegram/start_bot.sh $MODE"
