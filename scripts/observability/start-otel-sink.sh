#!/usr/bin/env bash
# Cycle 14 Tier 1.3 — sqlite-otel sink for trading-floor-v5
#
# Single Go binary OTLP/HTTP receiver that writes spans into a SQLite
# database on the VM. Paired with OpenLIT client-side instrumentation
# in scripts/arena/trading-floor-v5.py (Tier 1.2).
#
# Install (one-time):
#   mkdir -p ~/.local/bin
#   curl -L https://github.com/RedShiftVelocity/sqlite-otel/releases/latest/download/sqlite-otel-linux-amd64 \
#       -o ~/.local/bin/sqlite-otel
#   chmod +x ~/.local/bin/sqlite-otel
#
# Run this script to start the sink (idempotent — kills old, starts new):
#   bash scripts/observability/start-otel-sink.sh
#
# Memory: ~20-40 MB idle, well under the VM 969 MB budget.
# Port: 4318 (OTLP/HTTP default). OpenLIT in trading-floor-v5.py POSTs here.
# Storage: ~/data/traces.db (grows ~10 MB/day for ~200 trader calls).

set -euo pipefail

BIN="${HOME}/.local/bin/sqlite-otel"
DB="${HOME}/data/traces.db"
PORT="${SQLITE_OTEL_PORT:-4318}"
LOG="${HOME}/data/sqlite-otel.log"
PID="${HOME}/data/sqlite-otel.pid"

mkdir -p "$(dirname "$DB")" "$(dirname "$LOG")"

if [[ ! -x "$BIN" ]]; then
    echo "[otel-sink] sqlite-otel not installed at $BIN"
    echo "[otel-sink] Install with:"
    echo "    curl -L https://github.com/RedShiftVelocity/sqlite-otel/releases/latest/download/sqlite-otel-linux-amd64 \\"
    echo "        -o $BIN && chmod +x $BIN"
    exit 1
fi

# Stop any running instance
if [[ -f "$PID" ]]; then
    old_pid=$(cat "$PID" 2>/dev/null || echo "")
    if [[ -n "$old_pid" ]] && kill -0 "$old_pid" 2>/dev/null; then
        echo "[otel-sink] stopping old instance pid=$old_pid"
        kill "$old_pid" 2>/dev/null || true
        sleep 1
    fi
    rm -f "$PID"
fi

# Start fresh
echo "[otel-sink] starting sqlite-otel on port $PORT → $DB"
nohup "$BIN" \
    --db "$DB" \
    --port "$PORT" \
    --log-level info \
    >> "$LOG" 2>&1 &

echo $! > "$PID"
sleep 1

# Verify it's alive
new_pid=$(cat "$PID")
if kill -0 "$new_pid" 2>/dev/null; then
    echo "[otel-sink] OK pid=$new_pid log=$LOG"
    echo "[otel-sink] traders → http://localhost:$PORT"
    echo "[otel-sink] query traces: sqlite3 $DB 'SELECT name, status_code, duration_ns FROM spans ORDER BY start_time DESC LIMIT 10'"
    exit 0
else
    echo "[otel-sink] FAIL — process died immediately, see $LOG"
    tail -20 "$LOG" || true
    exit 1
fi
