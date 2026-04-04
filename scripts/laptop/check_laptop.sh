#!/bin/bash
# Check laptop evolution worker status
# Usage: bash scripts/laptop/check_laptop.sh

LAPTOP="laptop"
WSL_CMD='C:\Windows\system32\wsl.exe'
WORK_DIR="/home/nomos/nomos42-evo"

echo "=== Laptop Evolution Node Status ==="
echo ""

# Check reachability
if ! ssh -o ConnectTimeout=5 "$LAPTOP" "echo OK" >/dev/null 2>&1; then
    echo "STATUS: OFFLINE (SSH failed)"
    exit 1
fi
echo "STATUS: REACHABLE"

# Check if worker is running
RUNNING=$(ssh -o ConnectTimeout=10 "$LAPTOP" "$WSL_CMD -d Ubuntu -e bash -c \"pgrep -f laptop_evolution_worker | head -1\"" 2>/dev/null)
if [ -n "$RUNNING" ]; then
    echo "WORKER: RUNNING (PID $RUNNING)"
else
    echo "WORKER: STOPPED"
fi

# Check latest result
echo ""
echo "=== Latest Result ==="
ssh -o ConnectTimeout=10 "$LAPTOP" "$WSL_CMD -d Ubuntu -e cat $WORK_DIR/results/laptop_best.json" 2>/dev/null || echo "(no results yet)"

# Check last few log entries
echo ""
echo "=== Recent Log ==="
ssh -o ConnectTimeout=10 "$LAPTOP" "$WSL_CMD -d Ubuntu -e bash -c \"tail -5 $WORK_DIR/results/laptop_log.jsonl\"" 2>/dev/null || echo "(no log yet)"

# System stats
echo ""
echo "=== System Resources ==="
ssh -o ConnectTimeout=10 "$LAPTOP" "$WSL_CMD -d Ubuntu -e bash -c \"free -h | head -2 && echo --- && uptime\"" 2>/dev/null
