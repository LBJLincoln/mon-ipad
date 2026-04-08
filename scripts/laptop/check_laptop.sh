#!/bin/bash
# ============================================================
# Check laptop evolution worker status (native Ubuntu)
# ============================================================
# Usage:
#   bash scripts/laptop/check_laptop.sh
#
# Env overrides:
#   LAPTOP=laptop          SSH alias or user@ip
#   WORK_DIR=/home/nomos/nomos42-evo
# ============================================================

LAPTOP="${LAPTOP:-laptop}"
WORK_DIR="${WORK_DIR:-/home/nomos/nomos42-evo}"

echo "=== Laptop Evolution Node Status ==="
echo " Target: $LAPTOP:$WORK_DIR"
echo ""

# Check reachability
if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "$LAPTOP" "echo OK" >/dev/null 2>&1; then
    echo "STATUS: OFFLINE (SSH failed)"
    exit 1
fi
echo "STATUS: REACHABLE"

# Check if worker is running
RUNNING=$(ssh -o ConnectTimeout=10 "$LAPTOP" "pgrep -f laptop_evolution_worker | head -1" 2>/dev/null)
if [ -n "$RUNNING" ]; then
    echo "WORKER: RUNNING (PID $RUNNING)"
else
    echo "WORKER: STOPPED"
fi

# Latest result
echo ""
echo "=== Latest Result ==="
ssh -o ConnectTimeout=10 "$LAPTOP" "cat $WORK_DIR/results/laptop_best.json 2>/dev/null" || echo "(no results yet)"

# Recent log
echo ""
echo "=== Recent Log ==="
ssh -o ConnectTimeout=10 "$LAPTOP" "tail -5 $WORK_DIR/results/laptop_log.jsonl 2>/dev/null" || echo "(no log yet)"

# System stats
echo ""
echo "=== System Resources ==="
ssh -o ConnectTimeout=10 "$LAPTOP" "free -h | head -2 && echo --- && uptime"
