#!/bin/bash
# Autonomous monetisation — keeps Telegram bot alive + monitors sales
# Usage: nohup bash scripts/autonomous-monetisation.sh >> /tmp/monetisation-autonomous.log 2>&1 &

source /home/termius/mon-ipad/.env.local
cd /home/termius/mon-ipad

echo "$(date -Iseconds) === MONETISATION WATCHDOG STARTED ==="

while true; do
    # Check if Telegram sales bot is running
    if ! pgrep -f "telegram-sales-bot.py" > /dev/null; then
        echo "$(date -Iseconds) Telegram bot DOWN — restarting..."
        nohup python3 -u monetisation/telegram-sales-bot.py >> /tmp/telegram-bot.log 2>&1 &
        echo "$(date -Iseconds) Telegram bot restarted (PID $!)"
    fi

    # Keepalive ping to HF Spaces (backup for cron)
    bash /home/termius/mon-ipad/scripts/keepalive-spaces.sh --cron 2>/dev/null

    # Sleep 5 minutes then check again
    sleep 300
done
