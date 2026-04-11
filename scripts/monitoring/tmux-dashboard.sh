#!/usr/bin/env bash
# ============================================================================
# Nomos42 Tmux Dashboard — Full Ecosystem Monitoring
# ============================================================================
# Creates a 6-window tmux session showing all running systems:
#   W0: overview  — system health, git, cron, disk
#   W1: evolution — 8 HF Spaces (S10-S17) live status
#   W2: trading   — Trading Floor leaderboard + iteration state
#   W3: councils  — Department council states (11 depts)
#   W4: logs      — Live log tailing
#   W5: agents    — Running processes, cron, background jobs
#
# Usage:
#   ./tmux-dashboard.sh          # Create/attach session
#   ./tmux-dashboard.sh kill     # Kill existing session
#   ./tmux-dashboard.sh status   # Check if session exists
#
# Lightweight: no ML, just file reads and curls. Safe for 1vCPU/969MB.
# ============================================================================

set -eo pipefail

SESSION="nomos42-dash"
BASE="/home/termius/mon-ipad"
DATA="$BASE/data"
ARENA="$DATA/arena"
DEPTS="$DATA/departments"
NBA="$DATA/nba-agent"

# ── Handle arguments ─────────────────────────────────────────────────────────

case "${1:-}" in
    kill)
        tmux kill-session -t "$SESSION" 2>/dev/null && echo "Session '$SESSION' killed." || echo "No session '$SESSION' found."
        exit 0
        ;;
    status)
        if tmux has-session -t "$SESSION" 2>/dev/null; then
            echo "Session '$SESSION' is running."
            tmux list-windows -t "$SESSION"
        else
            echo "Session '$SESSION' is not running."
        fi
        exit 0
        ;;
esac

# ── If session exists, attach to it ──────────────────────────────────────────

if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "Session '$SESSION' already exists. Attaching..."
    exec tmux attach-session -t "$SESSION"
fi

echo "Creating Nomos42 dashboard session '$SESSION'..."

# ============================================================================
# WINDOW 0: OVERVIEW — System health, git log, cron, disk
# ============================================================================

tmux new-session -d -s "$SESSION" -n "overview" -x 220 -y 55

# Pane 0: System health (top lightweight mode)
tmux send-keys -t "$SESSION:0.0" "top -b -d 5 -n 999 -o %MEM 2>/dev/null || top -d 5" Enter

# Pane 1: Git log
tmux split-window -t "$SESSION:0" -h
tmux send-keys -t "$SESSION:0.1" "watch -n 30 -c 'cd $BASE && echo \"=== LAST 20 COMMITS ===\" && git log --oneline --decorate -20 && echo && echo \"=== UNCOMMITTED ===\" && git status -s | head -20'" Enter

# Pane 2: Crontab
tmux split-window -t "$SESSION:0.1" -v
tmux send-keys -t "$SESSION:0.2" "watch -n 120 'echo \"=== ACTIVE CRON JOBS ===\"; crontab -l 2>/dev/null | grep -v \"^#\" | grep -v \"^$\" | sort; echo; echo \"=== SYSTEMD TIMERS ===\"; systemctl list-timers --no-pager 2>/dev/null | head -10'" Enter

# Pane 3: Disk usage
tmux split-window -t "$SESSION:0.0" -v
tmux send-keys -t "$SESSION:0.3" "watch -n 60 'echo \"=== DISK USAGE ===\"; df -h / /tmp 2>/dev/null; echo; echo \"=== MON-IPAD SIZE ===\"; du -sh $BASE 2>/dev/null; echo; echo \"=== DATA DIR ===\"; du -sh $DATA/*/ 2>/dev/null | sort -rh | head -10; echo; echo \"=== MEMORY ===\"; free -h; echo; echo \"=== UPTIME ===\"; uptime'" Enter

# ============================================================================
# WINDOW 1: EVOLUTION — 6 HF Spaces (S10-S15)
# ============================================================================

tmux new-window -t "$SESSION" -n "evolution"

# Space URLs and roles
declare -A SPACE_URLS=(
    ["S10"]="https://nomos42-nba-quant.hf.space"
    ["S11"]="https://nomos42-nba-quant-2.hf.space"
    ["S12"]="https://nomos42-nba-evo-3.hf.space"
    ["S13"]="https://nomos42-nba-evo-4.hf.space"
    ["S14"]="https://nomos42-nba-evo-5.hf.space"
    ["S15"]="https://nomos42-nba-evo-6.hf.space"
    ["S16"]="https://lbjlincoln26-nba-evo-s16.hf.space"
    ["S17"]="https://lbjlincoln26-nba-evo-s17.hf.space"
)
declare -A SPACE_ROLES=(
    ["S10"]="Exploitation"
    ["S11"]="Exploration"
    ["S12"]="ExtraTrees"
    ["S13"]="CatBoost"
    ["S14"]="LightGBM"
    ["S15"]="Wide Search"
    ["S16"]="Gradient"
    ["S17"]="Ensemble"
)

SPACES_ORDERED=(S10 S11 S12 S13 S14 S15 S16 S17)

# Create 8-pane grid (4 columns x 2 rows) for S10-S17
# First pane: S10
SID="${SPACES_ORDERED[0]}"
tmux send-keys -t "$SESSION:1.0" "watch -n 90 'echo \"=== $SID (${SPACE_ROLES[$SID]}) ===\"; echo \"URL: ${SPACE_URLS[$SID]}\"; echo; STATUS=\$(curl -s --max-time 10 \"${SPACE_URLS[$SID]}/api/status\" 2>/dev/null); if [ -n \"\$STATUS\" ]; then echo \"\$STATUS\" | python3 -m json.tool 2>/dev/null || echo \"\$STATUS\"; else echo \"[TIMEOUT/UNREACHABLE]\"; fi; echo; echo \"--- Infra cache ---\"; python3 -c \"import json; d=json.load(open(\\\"$DATA/infra-status.json\\\")); s=d.get(\\\"hf_spaces\\\",{}).get(\\\"${SID}_nba\\\",{}); print(f\\\"Brier: {s.get(\\\"brier\\\",\\\"?\\\")}, Gen: {s.get(\\\"gen\\\",\\\"?\\\")}, Status: {s.get(\\\"status\\\",\\\"?\\\")}\\\")\" 2>/dev/null'" Enter

# Split for remaining 7 panes (S11-S17)
for i in 1 2 3 4 5 6 7; do
    tmux split-window -t "$SESSION:1" -h

    SID="${SPACES_ORDERED[$i]}"
    PANE_IDX=$i
    tmux send-keys -t "$SESSION:1.${PANE_IDX}" "watch -n 90 'echo \"=== $SID (${SPACE_ROLES[$SID]}) ===\"; echo \"URL: ${SPACE_URLS[$SID]}\"; echo; STATUS=\$(curl -s --max-time 10 \"${SPACE_URLS[$SID]}/api/status\" 2>/dev/null); if [ -n \"\$STATUS\" ]; then echo \"\$STATUS\" | python3 -m json.tool 2>/dev/null || echo \"\$STATUS\"; else echo \"[TIMEOUT/UNREACHABLE]\"; fi; echo; echo \"--- Infra cache ---\"; python3 -c \"import json; d=json.load(open(\\\"$DATA/infra-status.json\\\")); s=d.get(\\\"hf_spaces\\\",{}).get(\\\"${SID}_nba\\\",{}); print(f\\\"Brier: {s.get(\\\"brier\\\",\\\"?\\\")}, Gen: {s.get(\\\"gen\\\",\\\"?\\\")}, Status: {s.get(\\\"status\\\",\\\"?\\\")}\\\")\" 2>/dev/null'" Enter
done

# Even out the layout
tmux select-layout -t "$SESSION:1" tiled

# ============================================================================
# WINDOW 2: TRADING FLOOR — Leaderboard + iteration + stats
# ============================================================================

tmux new-window -t "$SESSION" -n "trading-floor"

# Pane 0: NBA Trading Floor leaderboard
tmux send-keys -t "$SESSION:2.0" "watch -n 30 'python3 -c \"
import json, os
from datetime import datetime

# Load latest trading floor data
tf_file = \\\"$ARENA/trading-floor-v4-latest.json\\\"
if not os.path.exists(tf_file):
    print(\\\"[NO DATA] trading-floor-v4-latest.json not found\\\")
    exit()

d = json.load(open(tf_file))
meta = d.get(\\\"meta\\\", {})
lb = d.get(\\\"leaderboard\\\", [])

print(\\\"=\" * 70)
print(\\\"  NOMOS42 TRADING FLOOR v4 — NBA LEADERBOARD\\\")
print(\\\"=\\\" * 70)
print(f\\\"  Generated: {meta.get(\\\"generated\\\", \\\"?\\\")}\\\")
print(f\\\"  Traders: {meta.get(\\\"traders\\\", 0)} | Models: {meta.get(\\\"nba_models\\\", 0)} | Strategies: {meta.get(\\\"nba_strategies\\\", 0)}\\\")
print(f\\\"  Matched games: {meta.get(\\\"matched_games\\\", 0)}\\\")
print(\\\"=\\\" * 70)
print(f\\\"  {\\\"Rank\\\":<5} {\\\"Trader\\\":<12} {\\\"Bankroll\\\":>12} {\\\"ROI%\\\":>10} {\\\"Sharpe\\\":>8} {\\\"W/L\\\":>10} {\\\"Status\\\":<10}\\\")
print(\\\"-\\\" * 70)
for t in lb:
    status = \\\"ELIM\\\" if t.get(\\\"eliminated\\\") else \\\"ACTIVE\\\"
    w = t.get(\\\"nba_wins\\\", 0)
    l = t.get(\\\"nba_losses\\\", 0)
    print(f\\\"  #{t.get(\\\"rank\\\",\\\"?\\\"):<4} {t.get(\\\"name\\\",\\\"?\\\"):<12} \\\\\\\${t.get(\\\"nba_bankroll\\\",0):>11,.2f} {t.get(\\\"nba_roi_pct\\\",0):>9.2f}% {t.get(\\\"nba_sharpe\\\",0):>7.3f} {w:>4}/{l:<4}  {status}\\\"  )
print(\\\"=\\\" * 70)
\"'" Enter

# Pane 1: Iteration state + political leaderboard
tmux split-window -t "$SESSION:2" -h
tmux send-keys -t "$SESSION:2.1" "watch -n 30 'python3 -c \"
import json, os

# Trading floor iteration
tf_iter = \\\"$ARENA/trading-floor-iteration.json\\\"
if os.path.exists(tf_iter):
    d = json.load(open(tf_iter))
    print(\\\"=== ITERATION STATE ===\")
    print(f\\\"  Iteration: {d.get(\\\"iteration\\\", \\\"?\\\")}\\\")
    print(f\\\"  Generation: {d.get(\\\"generation\\\", \\\"?\\\")}\\\")
    print()

# Political leaderboard
tf_file = \\\"$ARENA/trading-floor-v4-latest.json\\\"
if os.path.exists(tf_file):
    d = json.load(open(tf_file))
    lb = d.get(\\\"leaderboard\\\", [])
    print(\\\"=== POLITICAL TRADING ===\")
    print(f\\\"  {\\\"Trader\\\":<12} {\\\"Bankroll\\\":>14} {\\\"ROI%\\\":>10} {\\\"Approach\\\":<20}\\\")
    print(\\\"-\\\" * 60)
    for t in sorted(lb, key=lambda x: x.get(\\\"political_bankroll\\\",0), reverse=True):
        print(f\\\"  {t.get(\\\"name\\\",\\\"?\\\"):<12} \\\\\\\${t.get(\\\"political_bankroll\\\",0):>13,.2f} {t.get(\\\"political_roi_pct\\\",0):>9.4f}% {t.get(\\\"political_approach\\\",\\\"?\\\"):<20}\\\")
    print()

# Bankroll state
br_file = \\\"$NBA/bankroll-state.json\\\"
if os.path.exists(br_file):
    b = json.load(open(br_file))
    print(\\\"=== REAL BANKROLL ===\")
    for k,v in b.items():
        if isinstance(v, (int, float)):
            print(f\\\"  {k}: {v}\\\")
        elif isinstance(v, str):
            print(f\\\"  {k}: {v}\\\")
\"'" Enter

# ============================================================================
# WINDOW 3: COUNCILS — Department states
# ============================================================================

tmux new-window -t "$SESSION" -n "councils"

# Pane 0: All council states
tmux send-keys -t "$SESSION:3.0" "watch -n 60 'python3 -c \"
import json, os, glob
from datetime import datetime

print(\\\"=\\\" * 80)
print(\\\"  NOMOS42 DEPARTMENT COUNCILS — Forge v19\\\")
print(\\\"=\\\" * 80)
print(f\\\"  {\\\"Dept\\\":<20} {\\\"Iter\\\":>5} {\\\"Best Metric\\\":>14} {\\\"Last Run\\\":>22} {\\\"Status\\\":<12}\\\")
print(\\\"-\\\" * 80)

files = sorted(glob.glob(\\\"$DEPTS/council-*.json\\\"))
for f in files:
    try:
        d = json.load(open(f))
        dept = d.get(\\\"dept\\\", os.path.basename(f))
        it = d.get(\\\"iteration\\\", 0)
        best = d.get(\\\"best_metric\\\", None)
        best_str = f\\\"{best:.5f}\\\" if isinstance(best, (int,float)) else str(best or \\\"--\\\")
        last = d.get(\\\"last_run\\\", \\\"?\\\")

        # Determine health
        status = \\\"ACTIVE\\\"
        if last and last != \\\"?\\\":
            try:
                lr = datetime.fromisoformat(last.replace(\\\"Z\\\",\\\"+00:00\\\"))
                age_h = (datetime.now(lr.tzinfo) - lr).total_seconds() / 3600
                if age_h > 6:
                    status = \\\"STALE\\\"
                elif age_h > 12:
                    status = \\\"DEAD\\\"
            except:
                pass

        print(f\\\"  {dept:<20} {it:>5} {best_str:>14} {last:>22} {status:<12}\\\")
    except Exception as e:
        print(f\\\"  {os.path.basename(f):<20} ERROR: {e}\\\")

print(\\\"=\\\" * 80)

# Guardian report
gr_file = \\\"$DEPTS/guardian-report.json\\\"
if os.path.exists(gr_file):
    g = json.load(open(gr_file))
    print()
    print(\\\"=== GUARDIAN REPORT ===\")
    if isinstance(g, dict):
        for k in [\\\"timestamp\\\", \\\"healthy\\\", \\\"warnings\\\", \\\"critical\\\"]:
            if k in g:
                print(f\\\"  {k}: {g[k]}\\\")
\"'" Enter

# Pane 1: Wins + recent history
tmux split-window -t "$SESSION:3" -h
tmux send-keys -t "$SESSION:3.1" "watch -n 60 'echo \"=== LATEST WINS ===\"; python3 -c \"
import json, os
wf = \\\"$DEPTS/wins-latest.json\\\"
if os.path.exists(wf):
    w = json.load(open(wf))
    if isinstance(w, list):
        for win in w[-10:]:
            print(f\\\"  [{win.get(\\\"ts\\\",\\\"?\\\")[:16]}] {win.get(\\\"dept\\\",\\\"?\\\")}: {win.get(\\\"description\\\",win.get(\\\"proposal\\\",\\\"?\\\"))[:60]}\\\")
    elif isinstance(w, dict):
        for k, v in list(w.items())[:10]:
            print(f\\\"  {k}: {v}\\\")
\" 2>/dev/null; echo; echo \"=== ELIMINATIONS ===\"; python3 -c \"
import json, os
ef = \\\"$DEPTS/eliminations.json\\\"
if os.path.exists(ef):
    e = json.load(open(ef))
    if isinstance(e, list):
        for el in e[-5:]:
            print(f\\\"  {el}\\\")
    elif isinstance(e, dict):
        for k, v in list(e.items())[:5]:
            print(f\\\"  {k}: {v}\\\")
\" 2>/dev/null'" Enter

# ============================================================================
# WINDOW 4: LOGS — Live log tailing
# ============================================================================

tmux new-window -t "$SESSION" -n "logs"

# Pane 0: Agent health log
tmux send-keys -t "$SESSION:4.0" "watch -n 30 'echo \"=== AGENT HEALTH ===\"; python3 -c \"
import json
d = json.load(open(\\\"$DATA/agent-health.json\\\"))
print(f\\\"Timestamp: {d.get(\\\"timestamp\\\", \\\"?\\\")}\\\")
print(f\\\"Summary: {d.get(\\\"summary\\\", \\\"?\\\")}\\\")
issues = d.get(\\\"issues\\\", [])
if issues:
    print(f\\\"Issues ({len(issues)}):\\\")
    for i in issues[:10]:
        print(f\\\"  - {i}\\\")
actions = d.get(\\\"actions_taken\\\", [])
if actions:
    print(f\\\"Actions ({len(actions)}):\\\")
    for a in actions[:10]:
        print(f\\\"  - {a}\\\")
\" 2>/dev/null; echo; echo \"=== CROSS-REPO HEALTH ===\"; python3 -c \"
import json
d = json.load(open(\\\"$DATA/cross-repo-health.json\\\"))
if isinstance(d, dict):
    for k in [\\\"timestamp\\\", \\\"overall_status\\\", \\\"repos_checked\\\"]:
        if k in d:
            print(f\\\"{k}: {d[k]}\\\")
    reps = d.get(\\\"repos\\\", d.get(\\\"projects\\\", {}))
    if isinstance(reps, dict):
        for name, info in reps.items():
            st = info.get(\\\"status\\\", \\\"?\\\") if isinstance(info, dict) else info
            print(f\\\"  {name}: {st}\\\")
\" 2>/dev/null'" Enter

# Pane 1: Latest eval + quant summary
tmux split-window -t "$SESSION:4" -h
tmux send-keys -t "$SESSION:4.1" "watch -n 60 'echo \"=== LATEST EVAL ===\"; python3 -c \"
import json
d = json.load(open(\\\"$NBA/latest-eval.json\\\"))
if isinstance(d, dict):
    for k, v in d.items():
        if isinstance(v, (int, float, str)):
            print(f\\\"  {k}: {v}\\\")
\" 2>/dev/null; echo; echo \"=== QUANT SUMMARY ===\"; python3 -c \"
import json
d = json.load(open(\\\"$NBA/quant-summary.json\\\"))
if isinstance(d, dict):
    for k, v in d.items():
        if isinstance(v, (int, float, str)):
            print(f\\\"  {k}: {v}\\\")
        elif isinstance(v, dict):
            print(f\\\"  {k}:\\\")
            for k2, v2 in v.items():
                print(f\\\"    {k2}: {v2}\\\")
\" 2>/dev/null'" Enter

# Pane 2: Infra status
tmux split-window -t "$SESSION:4.0" -v
tmux send-keys -t "$SESSION:4.2" "watch -n 60 'echo \"=== INFRA STATUS ===\"; python3 -c \"
import json
d = json.load(open(\\\"$DATA/infra-status.json\\\"))
print(f\\\"Timestamp: {d.get(\\\"timestamp\\\", \\\"?\\\")}\\\")
s = d.get(\\\"summary\\\", {})
print(f\\\"Total: {s.get(\\\"total\\\",\\\"?\\\")} | Healthy: {s.get(\\\"healthy\\\",\\\"?\\\")} | Restarted: {s.get(\\\"restarted\\\",\\\"?\\\")} | Failed: {s.get(\\\"failed\\\",\\\"?\\\")}\\\")
print()
print(\\\"HF Spaces:\\\")
for name, info in d.get(\\\"hf_spaces\\\", {}).items():
    if isinstance(info, dict):
        print(f\\\"  {name}: status={info.get(\\\"status\\\",\\\"?\\\")}, brier={info.get(\\\"brier\\\",\\\"?\\\")}, gen={info.get(\\\"gen\\\",\\\"?\\\")}\\\")
print()
print(\\\"Kaggle:\\\")
for name, info in d.get(\\\"kaggle\\\", {}).items():
    val = info if isinstance(info, str) else json.dumps(info)
    print(f\\\"  {name}: {val[:80]}\\\")
\" 2>/dev/null'" Enter

# ============================================================================
# WINDOW 5: AGENTS — Running processes, crons, background jobs
# ============================================================================

tmux new-window -t "$SESSION" -n "agents"

# Pane 0: Running processes related to nomos42
tmux send-keys -t "$SESSION:5.0" "watch -n 15 'echo \"=== RUNNING PYTHON PROCESSES ===\"; ps aux | grep -E \"python3?|node\" | grep -v grep | grep -v watch | head -20; echo; echo \"=== TMUX SESSIONS ===\"; tmux list-sessions 2>/dev/null; echo; echo \"=== BACKGROUND JOBS ===\"; jobs -l 2>/dev/null; echo; echo \"=== LOAD ===\"; uptime; echo; echo \"=== OPEN PORTS ===\"; ss -tlnp 2>/dev/null | head -10'" Enter

# Pane 1: Cron status + next runs
tmux split-window -t "$SESSION:5" -h
tmux send-keys -t "$SESSION:5.1" "watch -n 120 'echo \"=== ACTIVE CRON ENTRIES ===\"; echo; crontab -l 2>/dev/null | grep -v \"^#\" | grep -v \"^$\" | while read line; do echo \"  $line\"; done; echo; echo \"=== CRON LOG (last 20) ===\"; grep CRON /var/log/syslog 2>/dev/null | tail -20 || journalctl -u cron --no-pager -n 20 2>/dev/null || echo \"  (no cron log access)\"'" Enter

# ============================================================================
# Final touches
# ============================================================================

# Go back to window 0
tmux select-window -t "$SESSION:0"

# Set some tmux options for the session
tmux set-option -t "$SESSION" status-style "bg=colour235,fg=colour136"
tmux set-option -t "$SESSION" status-left "#[fg=colour46,bold] NOMOS42 #[fg=colour245]| "
tmux set-option -t "$SESSION" status-right "#[fg=colour245]%Y-%m-%d %H:%M #[fg=colour136]| #[fg=colour46]1vCPU/969MB"
tmux set-option -t "$SESSION" status-left-length 30
tmux set-option -t "$SESSION" status-right-length 50
tmux set-option -t "$SESSION" pane-border-style "fg=colour240"
tmux set-option -t "$SESSION" pane-active-border-style "fg=colour46"

echo ""
echo "============================================"
echo "  Nomos42 Dashboard — Session '$SESSION'"
echo "============================================"
echo "  Windows:"
echo "    0: overview    — system health, git, cron, disk"
echo "    1: evolution   — 8 HF Spaces (S10-S17)"
echo "    2: trading-floor — NBA + Political leaderboard"
echo "    3: councils    — Department council states"
echo "    4: logs        — Agent health, eval, infra"
echo "    5: agents      — Processes, cron, ports"
echo ""
echo "  Navigation: Ctrl-B + 0-5 (switch windows)"
echo "              Ctrl-B + arrow (switch panes)"
echo "              Ctrl-B + z (zoom/unzoom pane)"
echo "              Ctrl-B + d (detach)"
echo ""
echo "  Kill: ./tmux-dashboard.sh kill"
echo "============================================"
echo ""

# Attach
exec tmux attach-session -t "$SESSION"
