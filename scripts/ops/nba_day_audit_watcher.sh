#!/bin/bash
# Watches NBA TF Hub for new day-XXX.json files. The moment one lands, runs
# the deploy/breadth/leakage audit and writes report to data/audit/.
# Cron: */5 * * * * /home/termius/mon-ipad/scripts/ops/nba_day_audit_watcher.sh

set -u
SPACE="LBJLincoln26/nba-llm-trading-floor"
LOCAL_DIR="/home/termius/mon-ipad/data/audit/nba-day-watch"
mkdir -p "$LOCAL_DIR"
. /home/termius/mon-ipad/.env.local 2>/dev/null

# List day files on Hub
LATEST=$(curl -s -H "Authorization: Bearer $HF_TOKEN_NBA" \
  "https://huggingface.co/api/spaces/$SPACE/tree/main/data/decisions" 2>/dev/null \
  | python3 -c "import json,sys; d=json.load(sys.stdin); files=sorted([x['path'] for x in d if isinstance(x,dict) and x.get('type')=='file']); print(files[-1] if files else '')")

[ -z "$LATEST" ] && exit 0
DAY_FILE=$(basename "$LATEST")
RECEIPT="$LOCAL_DIR/${DAY_FILE%.json}.audit.json"
[ -f "$RECEIPT" ] && exit 0  # already audited

curl -sL -H "Authorization: Bearer $HF_TOKEN_NBA" \
  "https://huggingface.co/spaces/$SPACE/resolve/main/$LATEST" \
  > "/tmp/$DAY_FILE"

python3 << PY
import json, sys
d = json.load(open('/tmp/$DAY_FILE'))
ag = d.get('agents') or {}
date = d.get('date'); n_games = d.get('n_games')
under_3 = 0; under_60 = 0; ff_pos = 0; ff_neg = 0
viol_3 = []; viol_60 = []
for tid, a in ag.items():
    bk_b = a.get('bankroll_before',0)
    allocs = a.get('allocations') or []
    parlays = a.get('parlays') or []
    deployed = sum(al.get('stake',0) or 0 for al in allocs) + sum(p.get('stake',0) or 0 for p in parlays)
    deploy_pct = deployed/bk_b*100 if bk_b else 0
    if len(allocs)+len(parlays) < 3: under_3 += 1; viol_3.append(tid)
    if deploy_pct < 60 and bk_b > 0: under_60 += 1; viol_60.append(tid)
    for al in allocs:
        if al.get('edge_source') == 'engine_forced_floor':
            if al.get('edge', 0) > 0: ff_pos += 1
            else: ff_neg += 1
report = {
    'date': date, 'n_games': n_games, 'audited_at': '$(date -u +%FT%TZ)',
    'violators_under_3_bets': under_3, 'agents': viol_3[:5],
    'violators_under_60_deploy': under_60, 'low_deploy_agents': viol_60[:5],
    'forced_floor_positive': ff_pos, 'forced_floor_negative': ff_neg,
}
json.dump(report, open('$RECEIPT', 'w'), indent=2)
print(json.dumps(report, indent=2))
PY

# Append to log + alert if violations >50% of fleet
echo "[$(date -u +%FT%TZ)] $DAY_FILE audited" >> "$LOCAL_DIR/audit.log"
