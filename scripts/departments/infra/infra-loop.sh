#!/bin/bash
# Department: INFRA (D6) — Karpathy Monitoring Loop
# Pattern: check → detect → fix → verify → output JSON
# Metric: uptime_pct, restart_count, cpu_load, disk_pct, spaces_alive
# Run: every 30 min via cron or on-demand
# Output: data/departments/infra/karpathy-output.json

set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$(dirname "$(dirname "$SCRIPT_DIR")")")"

ITERATION=${1:-1}
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
OUTPUT_FILE="$ROOT/data/departments/infra/karpathy-output.json"
LOG_FILE="$ROOT/logs/departments/infra-loop.log"

mkdir -p "$(dirname "$OUTPUT_FILE")" "$(dirname "$LOG_FILE")"
exec > >(tee -a "$LOG_FILE") 2>&1
echo "=== INFRA LOOP $TIMESTAMP iter=$ITERATION ==="

# ─── 1. SYSTEM RESOURCES ────────────────────────────────────────────────────
echo "[1/8] System resources..."
CPU_LOAD_1=$(awk '{print $1}' /proc/loadavg)
CPU_LOAD_5=$(awk '{print $2}' /proc/loadavg)
CPU_LOAD_15=$(awk '{print $3}' /proc/loadavg)

MEM_TOTAL=$(awk '/MemTotal/{print $2}' /proc/meminfo)
MEM_FREE=$(awk '/MemFree/{print $2}' /proc/meminfo)
MEM_AVAIL=$(awk '/MemAvailable/{print $2}' /proc/meminfo)
MEM_TOTAL_MB=$((MEM_TOTAL / 1024))
MEM_FREE_MB=$((MEM_FREE / 1024))
MEM_AVAIL_MB=$((MEM_AVAIL / 1024))
MEM_USED_MB=$((MEM_TOTAL_MB - MEM_FREE_MB))

SWAP_TOTAL=$(awk '/SwapTotal/{print $2}' /proc/meminfo)
SWAP_FREE=$(awk '/SwapFree/{print $2}' /proc/meminfo)
SWAP_USED_MB=$(( (SWAP_TOTAL - SWAP_FREE) / 1024 ))

DISK_PCT=$(df / | awk 'NR==2{print $5}' | tr -d '%')
DISK_AVAIL_GB=$(df -BG / | awk 'NR==2{print $4}' | tr -d 'G')

DATA_DIR_MB=$(du -sm "$ROOT/data" 2>/dev/null | awk '{print $1}' || echo 0)

echo "  CPU load: $CPU_LOAD_1 / $CPU_LOAD_5 / $CPU_LOAD_15"
echo "  RAM: ${MEM_USED_MB}MB used / ${MEM_TOTAL_MB}MB total"
echo "  Disk: ${DISK_PCT}% (${DISK_AVAIL_GB}GB free)"

# ─── 2. CRON COUNT ──────────────────────────────────────────────────────────
echo "[2/8] Cron jobs..."
CRONS_ACTIVE=$(crontab -l 2>/dev/null | grep -c '^[^#]' || echo 0)
echo "  Active cron lines: $CRONS_ACTIVE"

# ─── 3. PROCESSES ───────────────────────────────────────────────────────────
echo "[3/8] Processes..."
PROC_BRAIN=$(pgrep -f 'nomos42_brain.py' > /dev/null 2>&1 && echo "ALIVE" || echo "DOWN")
PROC_NBA_BOT=$(pgrep -f 'nomos_nba_bot.py' > /dev/null 2>&1 && echo "ALIVE" || echo "DOWN")
PROC_FORGE=$(pgrep -f 'forge_bot.py' > /dev/null 2>&1 && echo "ALIVE" || echo "DOWN")
PROC_POLITICAL=$(pgrep -f 'stupid_political_bot.py' > /dev/null 2>&1 && echo "ALIVE" || echo "DOWN")
PROC_RGWA=$(pgrep -f 'rgwa_bot.py' > /dev/null 2>&1 && echo "ALIVE" || echo "DOWN")
PROC_TERMINAL=$(pgrep -f 'terminal_api.py' > /dev/null 2>&1 && echo "ALIVE" || echo "DOWN")
PROC_DATA_SERVER=$(pgrep -f 'http.server' > /dev/null 2>&1 && echo "ALIVE" || echo "DOWN")
echo "  brain=$PROC_BRAIN nba_bot=$PROC_NBA_BOT forge=$PROC_FORGE data_server=$PROC_DATA_SERVER"

# ─── 4. DATA SERVER HTTP CHECK ───────────────────────────────────────────────
echo "[4/8] Data server HTTP..."
DATA_SERVER_HTTP=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://localhost:8080/ 2>/dev/null || echo "000")
echo "  HTTP: $DATA_SERVER_HTTP"

# Auto-restart data server if DOWN
if [[ "$PROC_DATA_SERVER" == "DOWN" ]]; then
    echo "  [AUTO-FIX] Data server DOWN — restarting..."
    python3 -m http.server 8080 -b 0.0.0.0 --directory "$ROOT/data" &>/dev/null &
    sleep 2
    PROC_DATA_SERVER=$(pgrep -f 'http.server' > /dev/null 2>&1 && echo "RESTARTED" || echo "RESTART_FAILED")
    echo "  Result: $PROC_DATA_SERVER"
fi

# ─── 5. HF SPACES HEALTH ─────────────────────────────────────────────────────
echo "[5/8] HF Spaces health..."

# Check spaces via /api/status endpoint (JSON response)
check_space() {
    local name="$1"
    local url="$2"
    local result
    result=$(curl -sf --max-time 8 "${url}/api/status" 2>/dev/null)
    if [[ $? -eq 0 ]] && echo "$result" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('brier',0))" > /dev/null 2>&1; then
        local brier gen status
        brier=$(echo "$result" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('brier','?'))" 2>/dev/null || echo "?")
        gen=$(echo "$result" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('generation','?'))" 2>/dev/null || echo "?")
        status="running"
        echo "  $name: $status brier=$brier gen=$gen"
        echo "${name}:running:${brier}:${gen}"
    else
        # Fallback: simple HTTP check
        local http_code
        http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 8 "${url}/" 2>/dev/null || echo "000")
        if [[ "$http_code" == "200" ]]; then
            echo "  $name: running (no JSON)"
            echo "${name}:running:?:?"
        else
            echo "  $name: DOWN (http=$http_code)"
            echo "${name}:down_${http_code}:?:?"
        fi
    fi
}

SPACES_RESULTS=()
while IFS= read -r line; do
    SPACES_RESULTS+=("$line")
done < <({
    check_space "S10" "https://nomos42-nba-quant.hf.space"
    check_space "S11" "https://nomos42-nba-quant-2.hf.space"
    check_space "S12" "https://nomos42-nba-evo-3.hf.space"
    check_space "S13" "https://nomos42-nba-evo-4.hf.space"
    check_space "S14" "https://nomos42-nba-evo-5.hf.space"
    check_space "S15" "https://nomos42-nba-evo-6.hf.space"
} | grep -E '^S[0-9]+:')

# Also check political spaces (P1-P2 only; P3/P4 removed 2026-04-03 — never existed on HF)
POL_RESULTS=()
while IFS= read -r line; do
    POL_RESULTS+=("$line")
done < <({
    check_space "PA1" "https://nomos42-political-alpha.hf.space"
    check_space "PA2" "https://nomos42-political-alpha-2.hf.space"
} | grep -E '^PA[0-9]+:')

# Count up/down
NBA_UP=0
POL_UP=0
for r in "${SPACES_RESULTS[@]}"; do
    [[ "$r" == *":running:"* ]] && NBA_UP=$((NBA_UP + 1))
done
for r in "${POL_RESULTS[@]}"; do
    [[ "$r" == *":running:"* ]] && POL_UP=$((POL_UP + 1))
done
FLEET_UP=$((NBA_UP + POL_UP))
FLEET_TOTAL=8
echo "  NBA: $NBA_UP/6 | Political: $POL_UP/2 | Total: $FLEET_UP/$FLEET_TOTAL"

# ─── 6. ISSUES DETECTION ─────────────────────────────────────────────────────
echo "[6/8] Issue detection..."
ISSUES=()

# CPU overload
CPU_INT=$(echo "$CPU_LOAD_1" | python3 -c "import sys; v=float(sys.stdin.read()); print(1 if v>1.5 else 0)")
[[ "$CPU_INT" == "1" ]] && ISSUES+=('{"severity":"HIGH","component":"cpu","description":"CPU overloaded: load '"$CPU_LOAD_1"' on 1 vCPU"}')

# Disk warning
[[ "$DISK_PCT" -ge 90 ]] && ISSUES+=('{"severity":"CRITICAL","component":"disk","description":"Disk '"$DISK_PCT"'% used — CRITICAL"}')
[[ "$DISK_PCT" -ge 80 && "$DISK_PCT" -lt 90 ]] && ISSUES+=('{"severity":"HIGH","component":"disk","description":"Disk '"$DISK_PCT"'% used — WARNING"}')

# Memory warning
MEM_PCT=$(python3 -c "print(round($MEM_USED_MB / $MEM_TOTAL_MB * 100, 1))")
[[ $(echo "$MEM_PCT > 85" | bc 2>/dev/null || echo 0) -eq 1 ]] && ISSUES+=('{"severity":"HIGH","component":"memory","description":"RAM '"$MEM_PCT"'% used"}')

# Swap active
[[ "$SWAP_USED_MB" -gt 200 ]] && ISSUES+=('{"severity":"MEDIUM","component":"swap","description":"Swap active: '"$SWAP_USED_MB"'MB used"}')

# Data server down
[[ "$PROC_DATA_SERVER" == "DOWN" || "$DATA_SERVER_HTTP" == "000" ]] && ISSUES+=('{"severity":"HIGH","component":"data_server","description":"Data server not responding"}')

# Telegram bots
[[ "$PROC_BRAIN" == "DOWN" ]] && ISSUES+=('{"severity":"HIGH","component":"telegram","description":"nomos42_brain.py DOWN"}')
[[ "$PROC_NBA_BOT" == "DOWN" ]] && ISSUES+=('{"severity":"MEDIUM","component":"telegram","description":"nomos_nba_bot.py DOWN"}')
[[ "$PROC_FORGE" == "DOWN" ]] && ISSUES+=('{"severity":"MEDIUM","component":"telegram","description":"forge_bot.py DOWN"}')

# Political spaces
[[ "$POL_UP" -lt 2 ]] && ISSUES+=('{"severity":"MEDIUM","component":"political_spaces","description":"Political spaces DOWN: '"$POL_UP"'/2 running."}')

# NBA spaces
[[ "$NBA_UP" -lt 6 ]] && ISSUES+=('{"severity":"HIGH","component":"nba_spaces","description":"NBA spaces DOWN: '"$NBA_UP"'/6 running"}')

# Large data dir
[[ "$DATA_DIR_MB" -gt 200 ]] && ISSUES+=('{"severity":"LOW","component":"disk","description":"data/ directory is '"$DATA_DIR_MB"'MB — consider archiving arena/karpathy logs"}')

echo "  Issues found: ${#ISSUES[@]}"

# ─── 7. UPTIME CALCULATION ───────────────────────────────────────────────────
echo "[7/8] Uptime calculation..."
UPTIME_PCT=$(python3 -c "
spaces=$FLEET_UP; total=$FLEET_TOTAL
bots_alive=sum(1 for x in ['$PROC_BRAIN','$PROC_NBA_BOT','$PROC_FORGE','$PROC_POLITICAL','$PROC_RGWA'] if x=='ALIVE')
data_ok=1 if '$DATA_SERVER_HTTP'=='200' else 0
# Weighted: spaces 60%, bots 30%, data 10%
score = (spaces/total)*60 + (bots_alive/5)*30 + data_ok*10
print(round(score, 1))
")
echo "  Uptime score: $UPTIME_PCT%"

# ─── 8. WRITE OUTPUT JSON ────────────────────────────────────────────────────
echo "[8/8] Writing output JSON..."

# Build issues JSON array
ISSUES_JSON="["
for i in "${!ISSUES[@]}"; do
    [[ $i -gt 0 ]] && ISSUES_JSON+=","
    ISSUES_JSON+="${ISSUES[$i]}"
done
ISSUES_JSON+="]"

# Build spaces JSON
SPACES_JSON="{}"
if [[ ${#SPACES_RESULTS[@]} -gt 0 ]] || [[ ${#POL_RESULTS[@]} -gt 0 ]]; then
    SPACES_JSON=$(python3 -c "
import json

nba_results = '''$(printf '%s\n' "${SPACES_RESULTS[@]}")'''.strip().split('\n')
pol_results = '''$(printf '%s\n' "${POL_RESULTS[@]}")'''.strip().split('\n')

spaces = {}
for line in nba_results + pol_results:
    if not line.strip():
        continue
    parts = line.split(':')
    if len(parts) >= 4:
        name, status, brier, gen = parts[0], parts[1], parts[2], parts[3]
        spaces[name] = {'status': status, 'brier': brier if brier != '?' else None, 'generation': gen if gen != '?' else None}
print(json.dumps(spaces))
" 2>/dev/null || echo '{}')
fi

# Assemble final JSON
python3 -c "
import json, datetime

output = {
    'department': 'infra',
    'timestamp': '$TIMESTAMP',
    'iteration': $ITERATION,
    'vm_health': {
        'cpu_load': $CPU_LOAD_1,
        'cpu_load_5m': $CPU_LOAD_5,
        'cpu_load_15m': $CPU_LOAD_15,
        'cpu_count': 1,
        'cpu_overloaded': $CPU_LOAD_1 > 1.0,
        'memory_mb': {
            'total': $MEM_TOTAL_MB,
            'used': $MEM_USED_MB,
            'free': $MEM_FREE_MB,
            'available': $MEM_AVAIL_MB,
            'used_pct': round($MEM_USED_MB / $MEM_TOTAL_MB * 100, 1)
        },
        'swap_mb': {'used': $SWAP_USED_MB, 'active': $SWAP_USED_MB > 0},
        'disk_pct': $DISK_PCT,
        'disk_avail_gb': $DISK_AVAIL_GB,
        'data_dir_mb': $DATA_DIR_MB,
    },
    'crons_active': $CRONS_ACTIVE,
    'processes_running': {
        'brain': '$PROC_BRAIN',
        'nba_bot': '$PROC_NBA_BOT',
        'forge_bot': '$PROC_FORGE',
        'political_bot': '$PROC_POLITICAL',
        'rgwa_bot': '$PROC_RGWA',
        'terminal_api': '$PROC_TERMINAL',
        'data_server': '$PROC_DATA_SERVER'
    },
    'data_server_http': '$DATA_SERVER_HTTP',
    'spaces_health': json.loads('''${SPACES_JSON}'''),
    'spaces_summary': {
        'nba_up': $NBA_UP,
        'nba_total': 6,
        'political_up': $POL_UP,
        'political_total': 2,
        'fleet_up': $FLEET_UP,
        'fleet_total': $FLEET_TOTAL
    },
    'issues_detected': json.loads('''${ISSUES_JSON}'''),
    'issues_count': len(json.loads('''${ISSUES_JSON}''')),
    'uptime_pct': $UPTIME_PCT,
    'status': 'completed'
}

with open('$OUTPUT_FILE', 'w') as f:
    json.dump(output, f, indent=2)
print('OK')
"

echo "=== INFRA LOOP DONE — issues=${#ISSUES[@]} uptime=${UPTIME_PCT}% ==="
