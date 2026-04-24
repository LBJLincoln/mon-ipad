#!/bin/bash
# tf_5min_improve.sh — every 5min: check each TF, fix anything broken, log delta.
#
# What "improve" means here:
#   1. If TF is running=False -> hit /api/run (auto-resume)
#   2. If NBA/POL fleet dropped > $50 since last snapshot -> fire improvement_cycle
#      (which auto-tunes Kelly for losers/winners)
#   3. If ITF equity dropped > $200 -> run position-health snapshot +
#      fire improvement_cycle to log signals
#   4. Always append {nba, pol, itf} fleet + equity to history for trend
#
# Output: /tmp/tf-5min-improve.log + data/ops/tf-5min-history.jsonl
#
# Cron: */5 * * * *

set -euo pipefail
REPO="/home/termius/mon-ipad"
cd "$REPO"
HIST="$REPO/data/ops/tf-5min-history.jsonl"
mkdir -p "$(dirname "$HIST")"

TS=$(date -u +%FT%H:%M:%SZ)

# Fetch a number, default -1 on any failure
fetch_num() {
  curl -s --max-time 6 "$1" | python3 -c "
import sys, json
try:
    d = json.loads(sys.stdin.read())
    print($2)
except Exception:
    print(-1)
" 2>/dev/null || echo -1
}

NBA_FLEET=$(fetch_num 'https://lbjlincoln26-nba-llm-trading-floor.hf.space/api/leaderboard' 'sum(float(r.get("bankroll",0)) for r in d.get("leaderboard",[]))')
NBA_RUN=$(curl -s --max-time 6 "https://lbjlincoln26-nba-llm-trading-floor.hf.space/api/status" 2>/dev/null | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(1 if d.get('running') else 0)" 2>/dev/null || echo 0)
POL_FLEET=$(fetch_num 'https://lbjlincoln26-political-llm-trading-floor.hf.space/api/leaderboard' 'sum(float(r.get("bankroll",0)) for r in d.get("leaderboard",[]))')
POL_RUN=$(curl -s --max-time 6 "https://lbjlincoln26-political-llm-trading-floor.hf.space/api/status" 2>/dev/null | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(1 if d.get('running') else 0)" 2>/dev/null || echo 0)
ITF_EQ=$(fetch_num 'https://lbjlincoln26-intraday-trading-floor.hf.space/api/bankrolls' 'd.get("fleet_equity",0)')
ITF_RUN=$(curl -s --max-time 6 "https://lbjlincoln26-intraday-trading-floor.hf.space/api/status" 2>/dev/null | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(1 if d.get('running') else 0)" 2>/dev/null || echo 0)

actions=()

# Auto-resume if stopped
if [ "$NBA_RUN" = "0" ]; then
  curl -s --max-time 6 -X POST "https://lbjlincoln26-nba-llm-trading-floor.hf.space/api/run" > /dev/null 2>&1 || true
  actions+=("NBA_resume")
fi
if [ "$POL_RUN" = "0" ]; then
  curl -s --max-time 6 -X POST "https://lbjlincoln26-political-llm-trading-floor.hf.space/api/run" > /dev/null 2>&1 || true
  actions+=("POL_resume")
fi
if [ "$ITF_RUN" = "0" ]; then
  # ITF /api/run needs body; try without
  curl -s --max-time 6 -X POST -H "Content-Type: application/json" \
       "https://lbjlincoln26-intraday-trading-floor.hf.space/api/run" -d '{}' > /dev/null 2>&1 || true
  actions+=("ITF_resume")
fi

# Compare to last snapshot for drop detection
PREV_NBA=""; PREV_POL=""; PREV_ITF=""
if [ -f "$HIST" ]; then
  read -r PREV_NBA PREV_POL PREV_ITF <<< "$(tail -1 "$HIST" | python3 -c "
import sys, json
try:
    d = json.loads(sys.stdin.read())
    print(d.get('nba',-1), d.get('pol',-1), d.get('itf_equity',-1))
except Exception:
    print('-1 -1 -1')
")"
fi

# Drop thresholds
drop_nba=0; drop_pol=0; drop_itf=0
if [ "$PREV_NBA" != "" ] && [ "$PREV_NBA" != "-1" ]; then
  python3 -c "import sys; sys.exit(0 if float('$NBA_FLEET') < float('$PREV_NBA') - 30 else 1)" && drop_nba=1 || true
fi
if [ "$PREV_POL" != "" ] && [ "$PREV_POL" != "-1" ]; then
  python3 -c "import sys; sys.exit(0 if float('$POL_FLEET') < float('$PREV_POL') - 30 else 1)" && drop_pol=1 || true
fi
if [ "$PREV_ITF" != "" ] && [ "$PREV_ITF" != "-1" ]; then
  python3 -c "import sys; sys.exit(0 if float('$ITF_EQ') < float('$PREV_ITF') - 200 else 1)" && drop_itf=1 || true
fi

# If any TF dropped materially, fire improvement cycle (Brier-aware Kelly auto-tune)
if [ "$drop_nba$drop_pol" != "00" ]; then
  /usr/bin/python3 "$REPO/scripts/ops/tf_improvement_cycle.py" >> /tmp/tf-5min-improve.log 2>&1 &
  actions+=("drop_improve_cycle")
fi
if [ "$drop_itf" = "1" ]; then
  /usr/bin/python3 "$REPO/scripts/ops/itf_position_health.py" >> /tmp/tf-5min-improve.log 2>&1 &
  actions+=("itf_drop_health")
fi

# Append history line
ACTS=$(IFS=,; echo "${actions[*]:-ok}")
echo "{\"ts\":\"$TS\",\"nba\":$NBA_FLEET,\"pol\":$POL_FLEET,\"itf_equity\":$ITF_EQ,\"nba_run\":$NBA_RUN,\"pol_run\":$POL_RUN,\"itf_run\":$ITF_RUN,\"actions\":\"$ACTS\"}" >> "$HIST"

echo "[$TS] NBA=\$$NBA_FLEET POL=\$$POL_FLEET ITF=\$$ITF_EQ run=${NBA_RUN}${POL_RUN}${ITF_RUN} actions=$ACTS"
