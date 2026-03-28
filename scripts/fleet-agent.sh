#!/bin/bash
# ══════════════════════════════════════════════════════════════
# NOMOS42 FLEET AGENT — Hardware Fleet Health Monitor
# ══════════════════════════════════════════════════════════════
# Monitors all machines in the fleet, reports status, alerts on failures.
# Phase 1: VM-only monitoring (remote machines need SSH setup)
# Phase 2: SSH-based remote monitoring (after fleet setup)
#
# Run: crontab -e → */10 * * * * /home/termius/mon-ipad/scripts/fleet-agent.sh
# Or:  bash scripts/fleet-agent.sh          (manual run)
# ══════════════════════════════════════════════════════════════
set -uo pipefail

BASE_DIR="/home/termius/mon-ipad"
LOG="$BASE_DIR/logs/fleet-agent.log"
STATUS_FILE="$BASE_DIR/data/fleet-status.json"
CONFIG_FILE="$BASE_DIR/data/fleet-config.yaml"
ALERT_COOLDOWN_DIR="/tmp/fleet-alerts"

mkdir -p "$(dirname "$LOG")" "$(dirname "$STATUS_FILE")" "$ALERT_COOLDOWN_DIR"

# Source env for tokens
source "$BASE_DIR/.env.local" 2>/dev/null

# ── Helpers ──────────────────────────────────────────────────

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $1" >> "$LOG"; }

alert_telegram() {
    local msg="$1"
    local severity="${2:-warning}"  # warning, critical, info

    # Cooldown: max 1 alert per 30 min per unique message
    local key
    key=$(echo "$msg" | md5sum | cut -c1-8)
    local cooldown_file="$ALERT_COOLDOWN_DIR/$key"

    if [ -f "$cooldown_file" ]; then
        local age=$(( $(date +%s) - $(stat -c %Y "$cooldown_file" 2>/dev/null || echo 0) ))
        [ "$age" -lt 1800 ] && return  # 30 min cooldown
    fi
    touch "$cooldown_file"

    local icon="--"
    case "$severity" in
        critical) icon="CRITICAL" ;;
        warning)  icon="WARNING" ;;
        info)     icon="INFO" ;;
    esac

    if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${ADMIN_TELEGRAM_ID:-}" ]; then
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -H 'Content-Type: application/json' \
            -d "{\"chat_id\":\"${ADMIN_TELEGRAM_ID}\",\"text\":\"[$icon] FLEET: ${msg}\",\"parse_mode\":\"HTML\"}" \
            > /dev/null 2>&1
    fi
    log "[ALERT:$severity] $msg"
}

bytes_to_human() {
    local bytes=$1
    if [ "$bytes" -gt 1073741824 ]; then
        echo "$(( bytes / 1073741824 ))G"
    elif [ "$bytes" -gt 1048576 ]; then
        echo "$(( bytes / 1048576 ))M"
    else
        echo "$(( bytes / 1024 ))K"
    fi
}

# ══════════════════════════════════════════════════════════════
# 1. LOCAL VM MONITORING (always runs)
# ══════════════════════════════════════════════════════════════

log "=== FLEET AGENT CYCLE START ==="

# CPU usage (1-second sample)
CPU_IDLE=$(top -bn1 | grep "%Cpu" | grep -oP '[\d.]+\s*id' | awk '{print $1}' 2>/dev/null || echo "0")
CPU_IDLE=${CPU_IDLE:-0}
CPU_USED=$(awk "BEGIN {printf \"%.0f\", 100 - $CPU_IDLE}" 2>/dev/null || echo "?")

# Memory
MEM_TOTAL=$(free -b | awk '/^Mem:/ {print $2}')
MEM_USED=$(free -b | awk '/^Mem:/ {print $3}')
MEM_AVAIL=$(free -b | awk '/^Mem:/ {print $7}')
MEM_PCT=$(( MEM_USED * 100 / MEM_TOTAL ))

# Disk
DISK_TOTAL=$(df / | awk 'NR==2 {print $2}')
DISK_USED=$(df / | awk 'NR==2 {print $3}')
DISK_PCT=$(df / | awk 'NR==2 {print $5}' | tr -d '%')

# Uptime
UPTIME_SECS=$(cat /proc/uptime | cut -d. -f1)
UPTIME_DAYS=$(( UPTIME_SECS / 86400 ))
UPTIME_HRS=$(( (UPTIME_SECS % 86400) / 3600 ))

# Load average
LOAD_1=$(cat /proc/loadavg | awk '{print $1}')
LOAD_5=$(cat /proc/loadavg | awk '{print $2}')
LOAD_15=$(cat /proc/loadavg | awk '{print $3}')

# Process count
PROC_COUNT=$(ps aux | wc -l)

log "[VM] CPU: ${CPU_USED}% | RAM: ${MEM_PCT}% ($(bytes_to_human $MEM_USED)/$(bytes_to_human $MEM_TOTAL)) | Disk: ${DISK_PCT}% | Load: $LOAD_1 $LOAD_5 $LOAD_15"

# ── VM Service Checks ────────────────────────────────────────

SVC_DATA_SERVER="down"
SVC_TELEGRAM_BRAIN="down"
SVC_TELEGRAM_RGWA="down"

# Data server (port 8080)
if curl -s --max-time 3 http://localhost:8080/ > /dev/null 2>&1; then
    SVC_DATA_SERVER="running"
elif pgrep -f "nba-data-server" > /dev/null 2>&1; then
    SVC_DATA_SERVER="running"
fi

# Telegram bots
if pgrep -f "nomos42_brain.py" > /dev/null 2>&1; then
    SVC_TELEGRAM_BRAIN="running"
fi
if pgrep -f "rgwa_bot.py" > /dev/null 2>&1; then
    SVC_TELEGRAM_RGWA="running"
fi

# Count running cron jobs related to nomos
CRON_COUNT=$(crontab -l 2>/dev/null | grep -cv "^#\|^$" || echo "0")

log "[VM] Services: data_server=$SVC_DATA_SERVER brain=$SVC_TELEGRAM_BRAIN rgwa=$SVC_TELEGRAM_RGWA crons=$CRON_COUNT"

# ══════════════════════════════════════════════════════════════
# 2. REMOTE MACHINE MONITORING (SSH-based, Phase 2)
# ══════════════════════════════════════════════════════════════

# Remote machine configs: name|host|port|user
# Uncomment and fill in when SSH is configured:
# REMOTE_MACHINES=(
#   "mba-1|192.168.x.x|22|user"
#   "mba-2|192.168.x.x|22|user"
#   "acer-a3|192.168.x.x|22|user"
# )

declare -A REMOTE_STATUS

check_remote_machine() {
    local name="$1"
    local host="$2"
    local port="${3:-22}"
    local user="${4:-termius}"

    # SSH ping with 5s timeout
    if ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no -p "$port" "$user@$host" "echo ok" > /dev/null 2>&1; then
        # Get remote stats
        local stats
        stats=$(ssh -o ConnectTimeout=10 -p "$port" "$user@$host" '
            cpu=$(top -bn1 2>/dev/null | grep "Cpu(s)" | awk "{print 100 - \$8}" 2>/dev/null || echo "?")
            mem_pct=$(free 2>/dev/null | awk "/^Mem:/ {printf \"%d\", \$3/\$2*100}" 2>/dev/null || echo "?")
            disk_pct=$(df / 2>/dev/null | awk "NR==2 {print \$5}" | tr -d "%" 2>/dev/null || echo "?")
            echo "${cpu}|${mem_pct}|${disk_pct}"
        ' 2>/dev/null || echo "?|?|?")

        local cpu_r mem_r disk_r
        cpu_r=$(echo "$stats" | cut -d'|' -f1)
        mem_r=$(echo "$stats" | cut -d'|' -f2)
        disk_r=$(echo "$stats" | cut -d'|' -f3)

        REMOTE_STATUS["$name"]="online"
        log "[REMOTE] $name: ONLINE (cpu=${cpu_r}% mem=${mem_r}% disk=${disk_r}%)"
        echo "{\"status\":\"online\",\"cpu_pct\":\"$cpu_r\",\"mem_pct\":\"$mem_r\",\"disk_pct\":\"$disk_r\"}"
    else
        REMOTE_STATUS["$name"]="unreachable"
        log "[REMOTE] $name: UNREACHABLE"
        alert_telegram "$name is UNREACHABLE (SSH failed)" "warning"
        echo "{\"status\":\"unreachable\"}"
    fi
}

# Phase 2: Uncomment to enable remote monitoring
# MBA1_JSON=$(check_remote_machine "mba-1" "IP_HERE" "22" "USER")
# MBA2_JSON=$(check_remote_machine "mba-2" "IP_HERE" "22" "USER")
# ACER_JSON=$(check_remote_machine "acer-a3" "IP_HERE" "22" "USER")

# For now, set all remotes as "not_configured"
MBA1_JSON='{"status":"not_configured","note":"SSH setup required"}'
MBA2_JSON='{"status":"not_configured","note":"SSH setup required"}'
ACER_JSON='{"status":"not_configured","note":"SSH setup required"}'

# ══════════════════════════════════════════════════════════════
# 3. ALERTS — Trigger on threshold breaches
# ══════════════════════════════════════════════════════════════

VM_HEALTH="healthy"

# RAM alert (VM only has 969MB, alert at 85%)
if [ "$MEM_PCT" -gt 85 ]; then
    alert_telegram "VM RAM critical: ${MEM_PCT}% used ($(bytes_to_human $MEM_AVAIL) free)" "critical"
    VM_HEALTH="degraded"
fi

# Disk alert
if [ "$DISK_PCT" -gt 90 ]; then
    alert_telegram "VM disk critical: ${DISK_PCT}% full" "critical"
    VM_HEALTH="degraded"
elif [ "$DISK_PCT" -gt 80 ]; then
    alert_telegram "VM disk warning: ${DISK_PCT}% full" "warning"
fi

# Load alert (1 vCPU, alert if sustained load > 2)
LOAD_HIGH=$(awk "BEGIN {print ($LOAD_5 > 2.0) ? 1 : 0}" 2>/dev/null || echo 0)
if [ "$LOAD_HIGH" = "1" ]; then
    alert_telegram "VM load high: $LOAD_1 $LOAD_5 $LOAD_15 (1 vCPU)" "warning"
    VM_HEALTH="degraded"
fi

# Service down alerts
if [ "$SVC_DATA_SERVER" = "down" ]; then
    alert_telegram "Data server is DOWN" "critical"
    VM_HEALTH="degraded"
fi
if [ "$SVC_TELEGRAM_BRAIN" = "down" ]; then
    alert_telegram "@Nomos42Bot is DOWN" "warning"
fi

# ══════════════════════════════════════════════════════════════
# 4. WRITE STATUS JSON
# ══════════════════════════════════════════════════════════════

cat > "$STATUS_FILE" << STATUSEOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "fleet_size": 4,
  "machines": {
    "gcp-vm": {
      "name": "Google Cloud VM",
      "role": "Primary Orchestrator",
      "status": "$VM_HEALTH",
      "specs": "1 vCPU, 969MB RAM, 30GB disk",
      "metrics": {
        "cpu_pct": "$CPU_USED",
        "mem_pct": "$MEM_PCT",
        "mem_used": "$(bytes_to_human $MEM_USED)",
        "mem_total": "$(bytes_to_human $MEM_TOTAL)",
        "mem_avail": "$(bytes_to_human $MEM_AVAIL)",
        "disk_pct": "$DISK_PCT",
        "load_1m": "$LOAD_1",
        "load_5m": "$LOAD_5",
        "load_15m": "$LOAD_15",
        "uptime_days": "$UPTIME_DAYS",
        "uptime_hours": "$UPTIME_HRS",
        "process_count": "$PROC_COUNT"
      },
      "services": {
        "data_server": "$SVC_DATA_SERVER",
        "telegram_brain": "$SVC_TELEGRAM_BRAIN",
        "telegram_rgwa": "$SVC_TELEGRAM_RGWA",
        "cron_jobs": "$CRON_COUNT"
      }
    },
    "mba-1": $MBA1_JSON,
    "mba-2": $MBA2_JSON,
    "acer-a3": $ACER_JSON
  },
  "gpu_platforms": {
    "note": "Tracked by infra-agent.sh, not fleet-agent.sh",
    "status_file": "data/infra-status.json"
  }
}
STATUSEOF

log "[STATUS] Written to $STATUS_FILE"

# ══════════════════════════════════════════════════════════════
# 5. CLEANUP — Rotate alert cooldown files
# ══════════════════════════════════════════════════════════════

find "$ALERT_COOLDOWN_DIR" -type f -mmin +120 -delete 2>/dev/null

# ══════════════════════════════════════════════════════════════
# 6. SUMMARY
# ══════════════════════════════════════════════════════════════

ONLINE_COUNT=1  # VM is always "online" if this script runs
CONFIGURED=1    # Only VM is configured in Phase 1
TOTAL_FLEET=4

log "=== FLEET AGENT DONE: $ONLINE_COUNT/$CONFIGURED configured online, $TOTAL_FLEET total in fleet, VM=$VM_HEALTH ==="
