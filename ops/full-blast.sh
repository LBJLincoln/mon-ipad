#!/bin/bash
# ══════════════════════════════════════════════════════════════
# FULL BLAST — Launch ALL daemons H24 7/7
# ══════════════════════════════════════════════════════════════
# Every repo, every category, every daemon — non-stop.
#
# Usage: bash ops/full-blast.sh
#        bash ops/full-blast.sh --status
#        bash ops/full-blast.sh --stop
# ══════════════════════════════════════════════════════════════

set -euo pipefail
cd /home/termius/mon-ipad
source .env.local 2>/dev/null

R='\033[0;31m' G='\033[0;32m' Y='\033[1;33m' C='\033[0;36m' W='\033[1;37m' NC='\033[0m'

# PID tracking
PIDS_DIR="data/daemons"
mkdir -p "$PIDS_DIR"

is_running() {
    local pidfile="$PIDS_DIR/$1.pid"
    if [ -f "$pidfile" ]; then
        local pid=$(cat "$pidfile")
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
    fi
    return 1
}

launch() {
    local name="$1"
    shift
    local cmd="$@"

    if is_running "$name"; then
        local pid=$(cat "$PIDS_DIR/$name.pid")
        echo -e "  ${name}: ${G}ALREADY RUNNING${NC} (PID $pid)"
        return
    fi

    nohup bash -c "source /home/termius/mon-ipad/.env.local 2>/dev/null; $cmd" > "/tmp/nomos-${name}.log" 2>&1 &
    local pid=$!
    echo "$pid" > "$PIDS_DIR/$name.pid"
    echo -e "  ${name}: ${G}LAUNCHED${NC} (PID $pid)"
}

stop_all() {
    echo -e "${R}━━━ STOPPING ALL DAEMONS ━━━${NC}"
    for pidfile in "$PIDS_DIR"/*.pid; do
        [ -f "$pidfile" ] || continue
        local name=$(basename "$pidfile" .pid)
        local pid=$(cat "$pidfile")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null
            echo -e "  ${name}: ${R}KILLED${NC} (PID $pid)"
        else
            echo -e "  ${name}: ${Y}ALREADY DEAD${NC}"
        fi
        rm -f "$pidfile"
    done
}

show_status() {
    echo -e "${W}╔══════════════════════════════════════════════╗${NC}"
    echo -e "${W}║  ${C}FULL BLAST STATUS${NC}  —  $(date -u +%H:%M:%SZ)${W}             ║${NC}"
    echo -e "${W}╚══════════════════════════════════════════════╝${NC}"

    local total=0
    local alive=0
    for pidfile in "$PIDS_DIR"/*.pid; do
        [ -f "$pidfile" ] || continue
        total=$((total + 1))
        local name=$(basename "$pidfile" .pid)
        local pid=$(cat "$pidfile")
        if kill -0 "$pid" 2>/dev/null; then
            alive=$((alive + 1))
            local mem=$(ps -o rss= -p "$pid" 2>/dev/null | awk '{printf "%.0fMB", $1/1024}')
            echo -e "  ${G}●${NC} ${name}: PID $pid (${mem})"
        else
            echo -e "  ${R}○${NC} ${name}: DEAD (stale PID $pid)"
        fi
    done
    echo -e "\n  Total: ${G}${alive}/${total}${NC} running"
    echo -e "  RAM: $(free -m | awk '/Mem:/{print $7}')MB available"
}

# ── Main ──────────────────────────────────────────────────────
case "${1:-launch}" in
    --stop)
        stop_all
        exit 0
        ;;
    --status)
        show_status
        exit 0
        ;;
    *)
        echo -e "${W}╔══════════════════════════════════════════════╗${NC}"
        echo -e "${W}║  ${C}FULL BLAST LAUNCH${NC}  —  ALL DAEMONS H24 7/7${W}  ║${NC}"
        echo -e "${W}╚══════════════════════════════════════════════╝${NC}"
        echo ""

        # ── 1. V2 Karpathy Orchestrator (7 repos × 7 categories = 49 metrics)
        echo -e "${C}[V2 KARPATHY ORCHESTRATOR]${NC}"
        launch "v2-orchestrator" "cd /home/termius/mon-ipad && python3 agents/v2/orchestrator.py --daemon 600"

        # ── 2. Monitor (5min health cycles)
        echo -e "${C}[MONITOR]${NC}"
        launch "monitor" "cd /home/termius/mon-ipad && python3 ops/monitor.py --loop 300"

        # ── 3. NBA Quant Daemon (2h cycles: research + odds + value bets)
        echo -e "${C}[NBA QUANT DAEMON]${NC}"
        launch "nba-quant" "cd /home/termius/nomos-nba-agent && python3 ops/nba-quant-daemon.py --daemon --interval 7200"

        # ── 4. NBA Agent Eval Loop (continuous testing)
        echo -e "${C}[NBA AGENT EVAL]${NC}"
        launch "nba-eval" "cd /home/termius/nomos-nba-agent && while true; do python3 agents/nba-agent.py --test 5 2>/dev/null; sleep 300; done"

        # ── 5. Unified Ingestion (Exa + Brave + Docling → n8n)
        echo -e "${C}[UNIFIED INGESTION]${NC}"
        if [ -f "ops/unified-ingest.py" ]; then
            launch "unified-ingest" "cd /home/termius/mon-ipad && python3 ops/unified-ingest.py --daemon 900"
        elif [ -f "ops/fast-ingest.py" ]; then
            launch "fast-ingest" "cd /home/termius/mon-ipad && python3 ops/fast-ingest.py --all --loop 600"
        fi

        # ── 6. Rate Limits Tracker (track 42 API providers)
        echo -e "${C}[RATE LIMITS TRACKER]${NC}"
        if [ -f "ops/rate-limits-tracker.py" ]; then
            launch "rate-limits" "cd /home/termius/mon-ipad && python3 ops/rate-limits-tracker.py --loop 300"
        fi

        # ── 7. Eval Blast (continuous pipeline testing)
        echo -e "${C}[EVAL BLAST]${NC}"
        if [ -f "eval/quick-test.py" ]; then
            launch "eval-blast" "cd /home/termius/mon-ipad && while true; do python3 eval/quick-test.py --proxy --pipelines standard,graph,orchestrator --questions 10 2>/dev/null; sleep 600; done"
        fi

        # ── 8. HTTP Data Server (serves live data to Dashboard+Vault)
        echo -e "${C}[HTTP DATA SERVER]${NC}"
        if curl -s --max-time 1 http://localhost:8080/ > /dev/null 2>&1; then
            echo -e "  http-server: ${G}ALREADY RUNNING${NC} (port 8080)"
            # Record existing PID
            local http_pid=$(lsof -ti :8080 2>/dev/null | head -1)
            [ -n "$http_pid" ] && echo "$http_pid" > "$PIDS_DIR/http-server.pid"
        else
            launch "http-server" "cd /home/termius/mon-ipad && python3 -m http.server 8080 -b 0.0.0.0"
        fi

        # ── Summary
        echo ""
        echo -e "${C}━━━ LAUNCH COMPLETE ━━━${NC}"
        sleep 2
        show_status
        ;;
esac
