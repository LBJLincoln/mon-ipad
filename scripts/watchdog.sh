#!/bin/bash
# Nomos42 Master Watchdog — runs every 5 min via cron
# Monitors ALL services, auto-restarts dead ones, alerts via Telegram
set -uo pipefail

LOG="/home/termius/mon-ipad/logs/watchdog.log"
ALERT_COOLDOWN="/tmp/watchdog-alert-cooldown"
mkdir -p "$(dirname "$LOG")"

# Source env for tokens
source /home/termius/mon-ipad/.env.local 2>/dev/null

log() { echo "[$(date -u +%Y-%m-%d\ %H:%M:%S)] $1" >> "$LOG"; }

alert() {
    local msg="$1"
    # Cooldown: max 1 alert per 15 min per service
    local key=$(echo "$msg" | md5sum | cut -c1-8)
    local cooldown_file="${ALERT_COOLDOWN}-${key}"
    if [ -f "$cooldown_file" ]; then
        local age=$(( $(date +%s) - $(stat -c %Y "$cooldown_file") ))
        [ "$age" -lt 900 ] && return  # 15 min cooldown
    fi
    touch "$cooldown_file"

    # Send to admin via Nomos42Bot
    if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${ADMIN_TELEGRAM_ID:-}" ]; then
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -H 'Content-Type: application/json' \
            -d "{\"chat_id\":\"${ADMIN_TELEGRAM_ID}\",\"text\":\"⚠️ WATCHDOG: ${msg}\",\"parse_mode\":\"HTML\"}" \
            > /dev/null 2>&1
    fi
    log "[ALERT] $msg"
}

FIXES=0

# ── 1. Telegram Bots ─────────────────────────────────────────
# @Nomos42Bot
if ! pgrep -f "nomos42_brain.py" > /dev/null 2>&1; then
    log "[BOT] @Nomos42Bot DOWN — restarting"
    cd /home/termius/mon-ipad && bash scripts/telegram/start_bots.sh start >> "$LOG" 2>&1
    FIXES=$((FIXES + 1))
    alert "@Nomos42Bot was DOWN — restarted"
else
    log "[BOT] @Nomos42Bot OK"
fi

# @RGWAbot
if ! pgrep -f "rgwa_bot.py" > /dev/null 2>&1; then
    log "[BOT] @RGWAbot DOWN — restarting"
    cd /home/termius/rgwa && bash scripts/telegram/start_bot.sh start >> "$LOG" 2>&1
    FIXES=$((FIXES + 1))
    alert "@RGWAbot was DOWN — restarted"
else
    log "[BOT] @RGWAbot OK"
fi

# ── 2. Data Server ────────────────────────────────────────────
# Check for either the custom server script OR the http.server fallback (both serve on 8080)
if ! { pgrep -f "nba-data-server" > /dev/null 2>&1 || pgrep -f "http\.server 8080" > /dev/null 2>&1; }; then
    log "[SERVER] Data server DOWN — restarting"
    nohup python3 -m http.server 8080 -b 0.0.0.0 --directory /home/termius/mon-ipad/data > /dev/null 2>&1 &
    FIXES=$((FIXES + 1))
    alert "Data server was DOWN — restarted (PID $!)"
else
    log "[SERVER] Data server OK"
fi

# ── 2b. Terminal API (port 8081) ──────────────────────────────
if ! pgrep -f "terminal_api.py" > /dev/null 2>&1; then
    log "[TERMINAL] Terminal API DOWN — restarting"
    source /home/termius/mon-ipad/.env.local 2>/dev/null
    nohup python3 /home/termius/mon-ipad/scripts/terminal_api.py > /tmp/terminal_api.log 2>&1 &
    FIXES=$((FIXES + 1))
    alert "Terminal API was DOWN — restarted (PID $!)"
else
    log "[TERMINAL] Terminal API OK"
fi

# ── 3. HF Spaces (quick check, not full keepalive) ───────────
SPACES_DOWN=""
for ISLAND in \
    "S10:https://nomos42-nba-quant.hf.space" \
    "S11:https://nomos42-nba-quant-2.hf.space" \
    "S12:https://nomos42-nba-evo-3.hf.space" \
    "S13:https://nomos42-nba-evo-4.hf.space" \
    "S14:https://nomos42-nba-evo-5.hf.space" \
    "S15:https://nomos42-nba-evo-6.hf.space"; do
    NAME="${ISLAND%%:*}"
    URL="${ISLAND#*:}"
    HTTP=$(curl -s -o /dev/null -w "%{http_code}" --max-time 8 "$URL/" 2>/dev/null || echo "000")
    if [ "$HTTP" = "000" ] || [ "$HTTP" = "502" ] || [ "$HTTP" = "503" ]; then
        SPACES_DOWN="${SPACES_DOWN} ${NAME}(${HTTP})"
    fi
done

if [ -n "$SPACES_DOWN" ]; then
    log "[SPACES] DOWN:${SPACES_DOWN}"
    alert "HF Spaces DOWN:${SPACES_DOWN}"
else
    log "[SPACES] All 6 islands OK"
fi

# ── 4. Political Alpha Spaces ────────────────────────────────
PA_DOWN=""
for ISLAND in \
    "P1:https://nomos42-political-alpha.hf.space" \
    "P2:https://nomos42-political-alpha-2.hf.space" \
    "P3:https://nomos42-political-alpha-3.hf.space" \
    "P4:https://nomos42-political-alpha-4.hf.space"; do
    NAME="${ISLAND%%:*}"
    URL="${ISLAND#*:}"
    HTTP=$(curl -s -o /dev/null -w "%{http_code}" --max-time 8 "$URL/" 2>/dev/null || echo "000")
    if [ "$HTTP" = "000" ] || [ "$HTTP" = "502" ] || [ "$HTTP" = "503" ]; then
        PA_DOWN="${PA_DOWN} ${NAME}(${HTTP})"
    fi
done

if [ -n "$PA_DOWN" ]; then
    log "[PA-SPACES] DOWN:${PA_DOWN}"
    alert "Political Alpha DOWN:${PA_DOWN}"
else
    log "[PA-SPACES] All 4 islands OK"
fi

# ── 5. Disk space check ──────────────────────────────────────
DISK_PCT=$(df / | awk 'NR==2 {print $5}' | tr -d '%')
if [ "$DISK_PCT" -gt 90 ]; then
    log "[DISK] WARNING: ${DISK_PCT}% full"
    alert "Disk ${DISK_PCT}% full!"
    # Auto-clean old logs
    find /home/termius/mon-ipad/logs/ -name "*.log" -size +50M -exec truncate -s 10M {} \;
    find /tmp/ -name "watchdog-alert-cooldown-*" -mtime +1 -delete 2>/dev/null
fi

# ── 6. Log rotation (keep logs under 20MB each) ──────────────
for logfile in /home/termius/mon-ipad/logs/*.log /tmp/nomos42-brain.log /tmp/rgwa-bot.log; do
    if [ -f "$logfile" ]; then
        SIZE=$(stat -c%s "$logfile" 2>/dev/null || echo 0)
        if [ "$SIZE" -gt 20971520 ]; then  # 20MB
            tail -n 5000 "$logfile" > "${logfile}.tmp" && mv "${logfile}.tmp" "$logfile"
            log "[LOGROTATE] Trimmed $logfile"
        fi
    fi
done

# ── Summary ───────────────────────────────────────────────────
if [ "$FIXES" -gt 0 ]; then
    log "[WATCHDOG] Cycle done — ${FIXES} service(s) restarted"
else
    log "[WATCHDOG] Cycle done — all systems nominal"
fi
