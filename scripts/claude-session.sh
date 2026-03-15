#!/bin/bash
# ══════════════════════════════════════════════════════════════
# Claude Code Session Launcher — Nomos Tour de Controle v3.0
# ══════════════════════════════════════════════════════════════
# Architecture v3: V2 Karpathy Loop (49 metrics) + NBA Tony Bloom
#   + Dashboard/Vault live + Unified ingestion + 15+ daemons
#
# Usage:
#   bash ~/mon-ipad/scripts/claude-session.sh --skip-perms
#   bash ~/mon-ipad/scripts/claude-session.sh                  # with perms
#   bash ~/mon-ipad/scripts/claude-session.sh --resume         # reprend
#   bash ~/mon-ipad/scripts/claude-session.sh --health         # check only
#   bash ~/mon-ipad/scripts/claude-session.sh "ta question"    # one-shot
# ══════════════════════════════════════════════════════════════

set -euo pipefail

PROJECT_DIR="$HOME/mon-ipad"
cd "$PROJECT_DIR"

# Load environment
source .env.local 2>/dev/null

# Ensure PATH
export PATH="$HOME/.npm-global/bin:$PATH"

# Force IPv4 — GCP VM IPv6 issues with HF
export CURL_FLAGS="--ipv4"

# Permission mode
PERMS_FLAG=""
if [[ "${1:-}" == "--skip-perms" ]]; then
    PERMS_FLAG="--dangerously-skip-permissions"
    shift
fi

# Auto session-start prompt
AUTO_START="CRITICAL: At the START of every conversation, BEFORE responding to the user, automatically execute ALL steps from the /session-start skill: read directives/PROJECT-STATE.md, source .env.local, check pipeline health, check database status, and output a concise session brief. Also git pull origin main first, then check if the user has created any new docs in the repo (git log --oneline -10). Do this even if the user has not asked — it is mandatory startup procedure."

# Colors
R='\033[0;31m' G='\033[0;32m' Y='\033[1;33m' C='\033[0;36m' M='\033[0;35m' W='\033[1;37m' NC='\033[0m'
DIM='\033[2m'

# ── Pre-flight cleanup ──────────────────────────────────────
cleanup() {
    echo -e "${C}━━━ PRE-FLIGHT CLEANUP ━━━${NC}"

    # Kill zombie claude processes
    local zombies=$(pgrep -a claude 2>/dev/null | grep -v "$$" | grep -v "claude-session" | wc -l)
    if [ "$zombies" -gt 0 ]; then
        echo -e "  ${R}Zombies: ${zombies}${NC} — killing..."
        pgrep -a claude 2>/dev/null | grep -v "$$" | grep -v "claude-session" | while read pid rest; do
            kill "$pid" 2>/dev/null || true
        done
        sleep 2
    else
        echo -e "  Zombies: ${G}0${NC}"
    fi

    # Kill unnecessary background processes (agent runners are heavyweight)
    local stale_count=$(pgrep -af "python3.*(_runner|mass-question|forge-tester|casino-tester)" 2>/dev/null | wc -l)
    if [ "$stale_count" -gt 0 ]; then
        echo -e "  ${Y}Stale runners: ${stale_count}${NC}"
        pgrep -af "python3.*(_runner|mass-question|forge-tester|casino-tester)" 2>/dev/null | while read pid rest; do
            echo -e "    ${DIM}kill $pid — ${rest:0:50}${NC}"
            kill "$pid" 2>/dev/null || true
        done
    fi

    echo ""
}

# ── Health check with V2 metrics ─────────────────────────────
health_check() {
    echo -e "${W}╔══════════════════════════════════════════════════════╗${NC}"
    echo -e "${W}║  ${C}NOMOS TOUR DE CONTROLE${NC}${W}  —  $(date -u +%H:%M:%SZ)  —  VM GCP${W}  ║${NC}"
    echo -e "${W}╚══════════════════════════════════════════════════════╝${NC}"
    echo ""

    # ── System ───────────────────────────────────────────────
    echo -e "${C}[SYSTEM]${NC}"
    local version=$(claude --version 2>/dev/null || echo "NOT FOUND")
    echo -e "  Claude Code: ${G}${version}${NC}"

    local ram_avail=$(free -m | awk '/Mem:/{print $7}')
    local swap_used=$(free -m | awk '/Swap:/{print $3}')
    local disk_pct=$(df -h / | awk 'NR==2{print $5}' | tr -d '%')
    local proc_count=$(ps -u termius --no-headers 2>/dev/null | wc -l)

    local ram_color=$G; [ "$ram_avail" -lt 350 ] && ram_color=$Y; [ "$ram_avail" -lt 200 ] && ram_color=$R
    local disk_color=$G; [ "$disk_pct" -gt 85 ] && disk_color=$R

    echo -e "  RAM: ${ram_color}${ram_avail}MB${NC} | Swap: ${swap_used}MB | Disk: ${disk_color}${disk_pct}%${NC} | Procs: ${proc_count}"

    # ── HF Spaces (parallel ping) ────────────────────────────
    echo -e "\n${C}[HF SPACES]${NC}"
    local spaces_up=0
    local spaces_total=0
    for space_info in "S1:lbjlincoln-nomos-rag-engine" "S3:lbjlincoln-nomos-rag-engine-3" "S5:lbjlincoln-nomos-rag-engine-5" "S7:lbjlincoln-nomos-rag-engine-7" "S9:lbjlincoln-nomos-rag-engine-9" "S6:lbjlincoln-nomos-docling-api" "EMB:lbjlincoln-nomos-embeddings-api"; do
        spaces_total=$((spaces_total + 1))
        label="${space_info%%:*}"
        space="${space_info#*:}"
        status=$(curl -4 -s -o /dev/null -w "%{http_code}" --max-time 5 "https://${space}.hf.space/healthz" 2>/dev/null || echo "000")
        [ "$status" = "000" ] && status=$(curl -4 -s -o /dev/null -w "%{http_code}" --max-time 5 "https://${space}.hf.space/health" 2>/dev/null || echo "000")
        [ "$status" = "000" ] && status=$(curl -4 -s -o /dev/null -w "%{http_code}" --max-time 5 "https://${space}.hf.space/" 2>/dev/null || echo "000")
        if [ "$status" = "200" ] || [ "$status" = "302" ]; then
            echo -ne "  ${label}: ${G}UP${NC}  "
            spaces_up=$((spaces_up + 1))
        else
            echo -ne "  ${label}: ${R}${status}${NC}  "
        fi
    done
    echo -e "\n  Total: ${G}${spaces_up}/${spaces_total}${NC}"

    # ── V2 Karpathy Metrics (49 = 7 repos × 7 categories) ────
    echo -e "\n${C}[V2 KARPATHY — 49 METRICS]${NC}"
    if [ -f "data/agents/v2/dashboard.json" ]; then
        python3 -c "
import json
d = json.load(open('data/agents/v2/dashboard.json'))
repos = d.get('repos', {})
total_metrics = sum(len(r.get('scores', {})) for r in repos.values())
for name, r in repos.items():
    avg = r.get('avg_score', 0)
    worst = r.get('worst_category', '?')
    gap = r.get('worst_gap', 0)
    color = '32' if avg >= 80 else '33' if avg >= 50 else '31'
    print(f'  \033[0;\${color}m{name:<22s} avg={avg:.0f}% | faible={worst}(gap={gap})\033[0m'.replace('\${color}', str(color)))
cycles = d.get('total_cycles', 0)
impr = d.get('total_improvements', 0)
print(f'  ─── Cycles: {cycles} | Ameliorations: {impr} | Metrics: {total_metrics}')
" 2>/dev/null || echo -e "  ${Y}V2 data unavailable${NC}"
    else
        echo -e "  ${Y}No V2 dashboard data yet${NC}"
    fi

    # ── Pipelines ────────────────────────────────────────────
    echo -e "\n${C}[RAG PIPELINES]${NC}"
    if [ -f "data/health-status.json" ]; then
        python3 -c "
import json
d = json.load(open('data/health-status.json'))
for name, p in d.get('pipelines', {}).items():
    rate = p.get('success_rate', 0)
    total = p.get('total', 0)
    color = '32' if rate >= 80 else '33' if rate >= 50 else '31'
    print(f'  \033[0;{color}m{name:<15s} {rate:.0f}% ({total} tests)\033[0m')
" 2>/dev/null || echo -e "  ${Y}Health data unavailable${NC}"
    fi

    # ── NBA Bankroll ─────────────────────────────────────────
    echo -e "\n${C}[NBA TONY BLOOM]${NC}"
    if [ -f "$HOME/nomos-nba-agent/data/bankroll/state.json" ]; then
        python3 -c "
import json
s = json.load(open('$HOME/nomos-nba-agent/data/bankroll/state.json'))
bal = s.get('balance', 0)
init = s.get('initial_balance', 1)
growth = (bal / init - 1) * 100
wins = s.get('wins', 0)
losses = s.get('losses', 0)
pending = s.get('pending', 0)
print(f'  Bankroll: \${bal:,.2f} ({growth:+.1f}%) | Record: {wins}W-{losses}L | Pending: {pending}')
" 2>/dev/null || echo -e "  ${Y}Bankroll not initialized${NC}"
    else
        echo -e "  ${Y}No bankroll state — run: python3 ~/nomos-nba-agent/ops/bankroll-manager.py init${NC}"
    fi
    if [ -f "data/nba-agent/latest-eval.json" ]; then
        python3 -c "
import json
d = json.load(open('data/nba-agent/latest-eval.json'))
print(f'  Eval: {d.get(\"accuracy\",0):.0f}% ({d.get(\"passed\",0)}/{d.get(\"total\",0)}) | Cycle {d.get(\"cycle\",0)}')
" 2>/dev/null || true
    fi

    # ── Rate Limits ──────────────────────────────────────────
    echo -e "\n${C}[RATE LIMITS — 42 PROVIDERS]${NC}"
    if [ -f "data/rate-limits-live.json" ]; then
        python3 -c "
import json
d = json.load(open('data/rate-limits-live.json'))
s = d.get('summary', {})
ok = s.get('ok', 0)
errs = s.get('errors', 0)
warns = s.get('warnings_80pct', 0)
crit = s.get('critical_90pct', 0)
print(f'  OK: \033[0;32m{ok}\033[0m | Errors: \033[0;31m{errs}\033[0m | Warn>80%: \033[0;33m{warns}\033[0m | Crit>90%: \033[0;31m{crit}\033[0m')
# Show errors
for p in d.get('providers', []):
    if p.get('status') not in ('OK', 'UP'):
        print(f'    \033[0;31m{p[\"provider\"]}: {p.get(\"error\", p.get(\"status\", \"?\"))}\033[0m')
" 2>/dev/null || echo -e "  ${Y}Rate limits data unavailable${NC}"
    fi

    # ── Active Processes ─────────────────────────────────────
    echo -e "\n${C}[PROCESSES]${NC}"
    local daemons=$(ps -u termius -o pid,comm,args --no-headers 2>/dev/null | grep -E "python3|node" | grep -v grep | grep -v claude)
    local daemon_count=$(echo "$daemons" | grep -c . 2>/dev/null || echo 0)
    echo -e "  Active daemons: ${daemon_count}"
    echo "$daemons" | head -8 | while read pid comm args; do
        local short="${args:0:65}"
        echo -e "    ${DIM}PID ${pid} — ${short}${NC}"
    done
    [ "$daemon_count" -gt 8 ] && echo -e "    ${DIM}... +$((daemon_count - 8)) more${NC}"

    # ── HTTP Server (serves live data to Dashboard+Vault) ────
    echo -e "\n${C}[HTTP DATA SERVER]${NC}"
    local http_check=$(curl -s --max-time 2 http://localhost:8080/data/health-status.json 2>/dev/null | head -c 20)
    if [ -n "$http_check" ]; then
        echo -e "  localhost:8080: ${G}SERVING${NC} (Dashboard+Vault live data)"
    else
        echo -e "  localhost:8080: ${R}DOWN${NC} — Dashboard/Vault won't get live data"
        echo -e "  ${Y}Fix: nohup python3 -m http.server 8080 -b 0.0.0.0 &${NC}"
    fi

    # ── Git ──────────────────────────────────────────────────
    echo -e "\n${C}[GIT]${NC}"
    local branch=$(git branch --show-current 2>/dev/null)
    local dirty=$(git status --porcelain 2>/dev/null | wc -l)
    local commits=$(git rev-list --count HEAD 2>/dev/null || echo "?")
    if [ "$dirty" -gt 0 ]; then
        echo -e "  ${Y}${branch} (${dirty} uncommitted) | ${commits} commits${NC}"
    else
        echo -e "  ${G}${branch} (clean) | ${commits} commits${NC}"
    fi

    echo -e "\n${W}══════════════════════════════════════════════════════${NC}\n"
}

# Main
case "${1:-}" in
    --health)
        health_check
        exit 0
        ;;
    --resume)
        echo -e "${C}Resuming last Claude session...${NC}"
        claude --resume --model claude-opus-4-6 $PERMS_FLAG
        ;;
    "")
        # Interactive mode
        cleanup
        health_check

        # Ensure HTTP server runs from mon-ipad (for Dashboard+Vault)
        if ! curl -s --max-time 1 http://localhost:8080/ > /dev/null 2>&1; then
            echo -e "${C}[Starting HTTP data server]${NC}"
            cd "$PROJECT_DIR" && nohup python3 -m http.server 8080 -b 0.0.0.0 > /dev/null 2>&1 &
            echo -e "  Started on port 8080 ${G}✓${NC}"
        fi

        # Launch essential daemons only (monitor = lightweight health loop)
        if ! pgrep -f "monitor.py --loop" > /dev/null 2>&1; then
            echo -e "${C}[Starting monitor daemon]${NC}"
            nohup python3 ops/monitor.py --loop 300 > /dev/null 2>&1 &
            echo -e "  Monitor: 5min cycle ${G}✓${NC}"
        fi

        echo ""
        echo -e "${C}Launching interactive Claude session (Opus 4.6)...${NC}"
        echo -e "${Y}Skills: /session-start | /monitor | /eval | /status-check | /self-heal | /improve${NC}"
        echo -e "${DIM}V2 Karpathy: 7 repos × 7 categories = 49 metrics | NBA: Tony Bloom quant${NC}"
        echo ""
        claude --model claude-opus-4-6 $PERMS_FLAG \
            --append-system-prompt "$AUTO_START"
        ;;
    *)
        # Direct question mode
        cleanup
        health_check
        echo -e "${C}Running: ${1}${NC}"
        echo ""
        claude -p "$*" --model claude-opus-4-6 $PERMS_FLAG \
            --append-system-prompt "$AUTO_START"
        ;;
esac
