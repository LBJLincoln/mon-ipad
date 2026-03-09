#!/usr/bin/env bash
#
# codespace-control.sh — Pilotage live des Codespaces depuis la VM
#
# Usage:
#   ./scripts/codespace-control.sh list                    # Codespaces actifs
#   ./scripts/codespace-control.sh launch <codespace>      # Lancer un run eval
#   ./scripts/codespace-control.sh status <codespace>      # Progression du run
#   ./scripts/codespace-control.sh logs <codespace> [N]    # N dernières lignes de log
#   ./scripts/codespace-control.sh stream <codespace>      # Stream live (tail -f)
#   ./scripts/codespace-control.sh stop <codespace>        # Arrêter le run en cours
#   ./scripts/codespace-control.sh results <codespace>     # Récupérer les résultats
#   ./scripts/codespace-control.sh monitor [interval]      # Boucle de surveillance
#
# Last updated: 2026-02-18T23:00:00+01:00

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

PROGRESS_FILE="/tmp/eval-progress.json"
PID_FILE="/tmp/eval-run.pid"
LOG_FILE="/tmp/eval-run.log"

# ============================================================
# HELPERS
# ============================================================

usage() {
    echo -e "${CYAN}codespace-control.sh${NC} — Pilotage live des Codespaces"
    echo ""
    echo "Commands:"
    echo "  list                       List active Codespaces"
    echo "  launch <cs> [args]         Launch eval run (args passed to run-eval-parallel.py)"
    echo "  status <cs>                Show run progress (reads /tmp/eval-progress.json)"
    echo "  logs <cs> [N]              Show last N log lines (default 50)"
    echo "  stream <cs>                Live stream logs (tail -f, Ctrl+C to stop)"
    echo "  stop <cs>                  Stop the running eval (kill PID)"
    echo "  results <cs>               Pull results from Codespace"
    echo "  monitor [interval]         Auto-refresh status every N seconds (default 30)"
    echo ""
    echo "Examples:"
    echo "  $0 list"
    echo "  $0 launch nomos-rag-tests-5g6g5q9vjjwjf5g4 --max 50 --label 'Phase1-fix-graph'"
    echo "  $0 status nomos-rag-tests-5g6g5q9vjjwjf5g4"
    echo "  $0 stream nomos-rag-tests-5g6g5q9vjjwjf5g4"
    echo "  $0 stop nomos-rag-tests-5g6g5q9vjjwjf5g4"
    echo "  $0 monitor 30"
}

cs_ssh() {
    local codespace="$1"
    shift
    gh codespace ssh --codespace "$codespace" -- "$@"
}

# ============================================================
# COMMANDS
# ============================================================

cmd_list() {
    echo -e "${CYAN}=== Active Codespaces ===${NC}"
    gh codespace list --json name,state,repository,lastUsedAt \
        --jq '.[] | "\(.state)\t\(.name)\t\(.repository)\t\(.lastUsedAt)"' | \
        column -t -s $'\t'
}

cmd_launch() {
    local codespace="$1"
    shift
    local eval_args="${*:---max 50 --label live-test}"

    echo -e "${CYAN}=== Launching eval on ${codespace} ===${NC}"

    # Ensure Codespace is running
    local state
    state=$(gh codespace list --json name,state --jq ".[] | select(.name==\"$codespace\") | .state")
    if [ "$state" != "Available" ]; then
        echo -e "${YELLOW}Starting Codespace...${NC}"
        gh codespace start --codespace "$codespace" 2>/dev/null || true
        echo "Waiting 10s for startup..."
        sleep 10
    fi

    # Start Docker if needed
    echo -e "${BLUE}Ensuring Docker is up...${NC}"
    cs_ssh "$codespace" "cd /workspaces/* && docker compose up -d 2>/dev/null || true"

    # Wait for n8n health
    echo -e "${BLUE}Waiting for n8n health...${NC}"
    for i in $(seq 1 12); do
        if cs_ssh "$codespace" "curl -sf http://localhost:5678/healthz >/dev/null 2>&1"; then
            echo -e "${GREEN}n8n is healthy${NC}"
            break
        fi
        echo "  Waiting... ($i/12)"
        sleep 5
    done

    # Launch eval in background with nohup, redirect to log file
    echo -e "${BLUE}Launching eval: ${eval_args}${NC}"
    cs_ssh "$codespace" "cd /workspaces/* && nohup bash -c 'source .env.local 2>/dev/null; python3 eval/run-eval-parallel.py ${eval_args}' > ${LOG_FILE} 2>&1 &"

    echo -e "${GREEN}Eval launched in background on ${codespace}${NC}"
    echo -e "Use ${CYAN}$0 status ${codespace}${NC} to check progress"
    echo -e "Use ${CYAN}$0 stream ${codespace}${NC} for live logs"
    echo -e "Use ${CYAN}$0 stop ${codespace}${NC} to abort"
}

cmd_status() {
    local codespace="$1"

    echo -e "${CYAN}=== Run Status: ${codespace} ===${NC}"

    # Read progress file
    local progress
    progress=$(cs_ssh "$codespace" "cat ${PROGRESS_FILE} 2>/dev/null" 2>/dev/null || echo '{"status":"no progress file"}')

    local status label tested total correct accuracy elapsed eta
    status=$(echo "$progress" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','unknown'))" 2>/dev/null || echo "unknown")
    label=$(echo "$progress" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('label',''))" 2>/dev/null || echo "")
    tested=$(echo "$progress" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tested',0))" 2>/dev/null || echo "0")
    total=$(echo "$progress" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('total_questions',0))" 2>/dev/null || echo "0")
    correct=$(echo "$progress" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('correct',0))" 2>/dev/null || echo "0")
    accuracy=$(echo "$progress" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('overall_accuracy',0))" 2>/dev/null || echo "0")
    elapsed=$(echo "$progress" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('elapsed_s',0))" 2>/dev/null || echo "0")
    eta=$(echo "$progress" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('eta_s',0))" 2>/dev/null || echo "0")

    # Status color
    case "$status" in
        running) status_color="${GREEN}" ;;
        done)    status_color="${BLUE}" ;;
        failed)  status_color="${RED}" ;;
        *)       status_color="${YELLOW}" ;;
    esac

    echo -e "  Status:   ${status_color}${status}${NC}"
    echo -e "  Label:    ${label}"
    echo -e "  Progress: ${tested}/${total} questions"
    echo -e "  Correct:  ${correct}/${tested}"
    echo -e "  Accuracy: ${accuracy}%"
    echo -e "  Elapsed:  $((elapsed / 60))m $((elapsed % 60))s"
    [ "$eta" -gt 0 ] 2>/dev/null && echo -e "  ETA:      $((eta / 60))m $((eta % 60))s"

    # Per-pipeline status
    echo ""
    echo -e "${CYAN}  Pipelines:${NC}"
    echo "$progress" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    for name, p in d.get('pipelines', {}).items():
        st = p.get('status', '?')
        acc = p.get('accuracy', 0)
        tested = p.get('tested', 0)
        correct = p.get('correct', 0)
        last_q = p.get('last_question', '')
        last_lat = p.get('last_latency_ms', 0)
        marker = '✓' if st == 'done' else ('▶' if st == 'running' else '○')
        print(f'    {marker} {name:<15} {st:<10} {correct}/{tested} ({acc}%)  last: {last_q} ({last_lat}ms)')
except:
    print('    (no pipeline data)')
" 2>/dev/null || echo "    (parse error)"
}

cmd_logs() {
    local codespace="$1"
    local lines="${2:-50}"

    echo -e "${CYAN}=== Last ${lines} log lines: ${codespace} ===${NC}"
    cs_ssh "$codespace" "tail -n ${lines} ${LOG_FILE} 2>/dev/null" 2>/dev/null || echo "(no log file)"
}

cmd_stream() {
    local codespace="$1"

    echo -e "${CYAN}=== Live stream: ${codespace} (Ctrl+C to stop) ===${NC}"
    cs_ssh "$codespace" "tail -f ${LOG_FILE} 2>/dev/null" 2>/dev/null || echo "(no log file or connection lost)"
}

cmd_stop() {
    local codespace="$1"

    echo -e "${RED}=== Stopping eval on ${codespace} ===${NC}"

    # Read PID and kill
    local pid
    pid=$(cs_ssh "$codespace" "cat ${PID_FILE} 2>/dev/null" 2>/dev/null || echo "")

    if [ -n "$pid" ] && [ "$pid" != "" ]; then
        echo -e "  Killing PID ${pid}..."
        cs_ssh "$codespace" "kill ${pid} 2>/dev/null; kill -9 ${pid} 2>/dev/null; rm -f ${PID_FILE}" 2>/dev/null || true
        echo -e "${GREEN}  Eval stopped.${NC}"
    else
        echo -e "${YELLOW}  No PID file found. Trying to find python eval process...${NC}"
        cs_ssh "$codespace" "pkill -f 'python3 eval/run-eval' 2>/dev/null || pkill -f 'python3.*eval' 2>/dev/null" 2>/dev/null || true
        echo -e "${GREEN}  Kill signal sent.${NC}"
    fi

    # Show final status
    cmd_status "$codespace" 2>/dev/null || true
}

cmd_results() {
    local codespace="$1"

    echo -e "${CYAN}=== Pulling results from ${codespace} ===${NC}"

    # Pull the latest pipeline results
    local results_dir="/tmp/codespace-results-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$results_dir"

    # Copy progress file
    cs_ssh "$codespace" "cat ${PROGRESS_FILE} 2>/dev/null" > "${results_dir}/progress.json" 2>/dev/null || true

    # Copy latest pipeline results
    cs_ssh "$codespace" "ls -t /workspaces/*/logs/pipeline-results/*.json 2>/dev/null | head -8" 2>/dev/null | while read -r file; do
        local basename
        basename=$(basename "$file")
        cs_ssh "$codespace" "cat $file" > "${results_dir}/${basename}" 2>/dev/null || true
    done

    # Copy data.json
    cs_ssh "$codespace" "cat /workspaces/*/docs/data.json 2>/dev/null" > "${results_dir}/data.json" 2>/dev/null || true

    echo -e "${GREEN}  Results saved to: ${results_dir}${NC}"
    echo "  Files:"
    ls -la "$results_dir/" 2>/dev/null
}

cmd_monitor() {
    local interval="${1:-30}"

    echo -e "${CYAN}=== Monitor mode (every ${interval}s, Ctrl+C to stop) ===${NC}"

    # Get all active codespaces
    while true; do
        clear
        echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${CYAN}║          CODESPACE MONITOR — $(date '+%Y-%m-%d %H:%M:%S')          ║${NC}"
        echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
        echo ""

        # List codespaces and check each
        local codespaces
        codespaces=$(gh codespace list --json name,state --jq '.[] | select(.state=="Available") | .name' 2>/dev/null || echo "")

        if [ -z "$codespaces" ]; then
            echo -e "${YELLOW}  No active Codespaces found.${NC}"
        else
            for cs in $codespaces; do
                cmd_status "$cs" 2>/dev/null || echo -e "  ${YELLOW}${cs}: unreachable${NC}"
                echo ""
            done
        fi

        echo -e "${CYAN}Next refresh in ${interval}s... (Ctrl+C to stop)${NC}"
        sleep "$interval"
    done
}

# ============================================================
# MAIN
# ============================================================

if [ $# -lt 1 ]; then
    usage
    exit 1
fi

COMMAND="$1"
shift

case "$COMMAND" in
    list)    cmd_list ;;
    launch)  [ $# -lt 1 ] && { echo "Usage: $0 launch <codespace> [eval-args]"; exit 1; }; cmd_launch "$@" ;;
    status)  [ $# -lt 1 ] && { echo "Usage: $0 status <codespace>"; exit 1; };  cmd_status "$1" ;;
    logs)    [ $# -lt 1 ] && { echo "Usage: $0 logs <codespace> [lines]"; exit 1; };    cmd_logs "$@" ;;
    stream)  [ $# -lt 1 ] && { echo "Usage: $0 stream <codespace>"; exit 1; }; cmd_stream "$1" ;;
    stop)    [ $# -lt 1 ] && { echo "Usage: $0 stop <codespace>"; exit 1; };   cmd_stop "$1" ;;
    results) [ $# -lt 1 ] && { echo "Usage: $0 results <codespace>"; exit 1; }; cmd_results "$1" ;;
    monitor) cmd_monitor "${1:-30}" ;;
    help|-h|--help) usage ;;
    *)
        echo -e "${RED}Unknown command: ${COMMAND}${NC}"
        usage
        exit 1
        ;;
esac
