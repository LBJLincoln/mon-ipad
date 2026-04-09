#!/usr/bin/env bash
# Cycle 14 Tier 1.3 — Phoenix UI on brother's laptop (Tailscale node)
#
# Phoenix = Arize's open-source LLM trace viewer. It's a SQLite-backed
# FastAPI app with a React UI showing trace spans, latency distributions,
# token costs per model, and a compare-two-runs diff view.
#
# Arize documents a 2GB RAM requirement for self-host — that's too much
# for the VM (969 MB) but trivial on the laptop (8-16 GB). Brother's
# laptop is already on the Tailscale mesh, so traders on the VM can
# POST spans to http://<laptop-tailnet>:6006 just like they POST to
# http://localhost:4318 for the local sqlite-otel sink.
#
# This script is INTENDED TO RUN ON THE LAPTOP, not the VM. Copy it
# across (it's also committed to the repo), then:
#
#   bash laptop-phoenix-bootstrap.sh install   # one-time: python3 -m venv + pip
#   bash laptop-phoenix-bootstrap.sh start     # launch Phoenix on :6006
#   bash laptop-phoenix-bootstrap.sh status    # check it's running
#   bash laptop-phoenix-bootstrap.sh stop      # kill it
#
# Once running, on the VM:
#   export OTEL_EXPORTER_OTLP_ENDPOINT=http://<laptop-tailnet-ip>:6006/v1/traces
#
# And OpenLIT in trading-floor-v5.py will ship every LLM call there too.
# (You'll want a DUAL-SINK pattern — see scripts/observability/README.md.)

set -euo pipefail

ACTION="${1:-help}"
VENV="${HOME}/.nomos42/phoenix-venv"
PORT="${PHOENIX_PORT:-6006}"
WORKING_DIR="${PHOENIX_WORKING_DIR:-${HOME}/.phoenix}"
LOG="${HOME}/.nomos42/phoenix.log"
PID="${HOME}/.nomos42/phoenix.pid"

mkdir -p "$(dirname "$LOG")" "$WORKING_DIR"

install_phoenix() {
    echo "[phoenix] creating venv at $VENV"
    python3 -m venv "$VENV"
    # shellcheck disable=SC1091
    source "$VENV/bin/activate"
    pip install --upgrade pip wheel
    # arize-phoenix pulls in fastapi, uvicorn, sqlalchemy, pandas, strawberry
    pip install 'arize-phoenix>=5.0,<6.0'
    echo "[phoenix] installed. Start with: bash $0 start"
}

start_phoenix() {
    if [[ -f "$PID" ]]; then
        old=$(cat "$PID" 2>/dev/null || echo "")
        if [[ -n "$old" ]] && kill -0 "$old" 2>/dev/null; then
            echo "[phoenix] already running pid=$old"
            return 0
        fi
    fi
    # shellcheck disable=SC1091
    source "$VENV/bin/activate"
    export PHOENIX_WORKING_DIR="$WORKING_DIR"
    export PHOENIX_HOST="0.0.0.0"   # needed so the VM can POST via Tailscale
    export PHOENIX_PORT="$PORT"
    echo "[phoenix] starting on :$PORT → $WORKING_DIR"
    nohup python -m phoenix.server.main serve >> "$LOG" 2>&1 &
    echo $! > "$PID"
    sleep 2
    new_pid=$(cat "$PID")
    if kill -0 "$new_pid" 2>/dev/null; then
        ip=$(tailscale ip -4 2>/dev/null | head -1 || hostname -I | awk '{print $1}')
        echo "[phoenix] OK pid=$new_pid"
        echo "[phoenix] UI:       http://$ip:$PORT"
        echo "[phoenix] OTLP in:  http://$ip:$PORT/v1/traces"
        echo "[phoenix] log:      $LOG"
    else
        echo "[phoenix] FAIL — check $LOG"
        tail -20 "$LOG" || true
        exit 1
    fi
}

status_phoenix() {
    if [[ -f "$PID" ]]; then
        pid=$(cat "$PID")
        if kill -0 "$pid" 2>/dev/null; then
            echo "[phoenix] running pid=$pid port=$PORT"
            return 0
        fi
    fi
    echo "[phoenix] not running"
    return 1
}

stop_phoenix() {
    if [[ -f "$PID" ]]; then
        pid=$(cat "$PID")
        kill "$pid" 2>/dev/null || true
        rm -f "$PID"
        echo "[phoenix] stopped pid=$pid"
    fi
}

case "$ACTION" in
    install) install_phoenix ;;
    start)   start_phoenix ;;
    status)  status_phoenix ;;
    stop)    stop_phoenix ;;
    restart) stop_phoenix; start_phoenix ;;
    *)
        echo "Usage: bash $0 {install|start|status|stop|restart}"
        echo ""
        echo "Run on brother's laptop, NOT on the VM. Target: Phoenix"
        echo "UI on :$PORT accessible via Tailscale from the VM."
        exit 1
        ;;
esac
