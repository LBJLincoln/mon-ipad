#!/usr/bin/env bash
# v5-review.sh — Council-readable summary of the trading floor v5 swarm run.
# Tails the per-agent council log + bet audit sidecars created by
# trading-floor-v5.py (2026-04-11 Phase B).
#
# Usage:
#   ./scripts/councils/v5-review.sh                    # latest date found
#   ./scripts/councils/v5-review.sh 2026-04-05         # specific date
#   DATE=2026-04-05 TOP=5 ./scripts/councils/v5-review.sh
#
# Outputs:
#   - council log row count + personality mix
#   - top bets by voter_count + dominant personality
#   - per-agent prediction count for the date

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
LOG_DIR="$ROOT/data/arena/council-log-v5"
PRED_DIR="$ROOT/data/arena/predictions-v5"

TARGET_DATE="${1:-${DATE:-}}"
TOP_N="${TOP:-10}"

if [[ -z "$TARGET_DATE" ]]; then
    TARGET_DATE=$(ls "$LOG_DIR"/council-log-*.jsonl 2>/dev/null \
        | sed 's|.*council-log-||' | sed 's|\.jsonl$||' \
        | sort -r | head -1)
fi

if [[ -z "$TARGET_DATE" ]]; then
    echo "No council log found in $LOG_DIR"
    exit 1
fi

COUNCIL_LOG="$LOG_DIR/council-log-${TARGET_DATE}.jsonl"
BET_AUDIT="$LOG_DIR/bet-audit-${TARGET_DATE}.json"

if [[ ! -f "$COUNCIL_LOG" ]]; then
    echo "Missing: $COUNCIL_LOG"
    exit 1
fi

echo "════════════════════════════════════════════════════════════════"
echo "TRADING FLOOR V5 — COUNCIL REVIEW — $TARGET_DATE"
echo "════════════════════════════════════════════════════════════════"

ROWS=$(wc -l < "$COUNCIL_LOG")
UNIQUE_AGENTS=$(python3 -c "
import json
agents=set()
for line in open('$COUNCIL_LOG'):
    try: agents.add(json.loads(line)['agent_id'])
    except: pass
print(len(agents))
")
UNIQUE_GAMES=$(python3 -c "
import json
games=set()
for line in open('$COUNCIL_LOG'):
    try: games.add(json.loads(line)['game_key'])
    except: pass
print(len(games))
")

echo "Council log rows: $ROWS"
echo "Unique agents:    $UNIQUE_AGENTS"
echo "Unique games:     $UNIQUE_GAMES"
echo

echo "── Personality mix ──"
python3 -c "
import json
from collections import Counter
c=Counter()
for line in open('$COUNCIL_LOG'):
    try: c[json.loads(line).get('personality','unknown')] += 1
    except: pass
for p,n in c.most_common():
    print(f'  {p:<25} {n:>5}')
"
echo

echo "── Tier mix ──"
python3 -c "
import json
from collections import Counter
c=Counter()
for line in open('$COUNCIL_LOG'):
    try: c[json.loads(line).get('tier','unknown')] += 1
    except: pass
for p,n in c.most_common():
    print(f'  {p:<25} {n:>5}')
"
echo

if [[ -f "$BET_AUDIT" ]]; then
    echo "── Top $TOP_N bets by voter_count ──"
    python3 -c "
import json
data=json.loads(open('$BET_AUDIT').read())
bets=data.get('bets', [])
bets.sort(key=lambda b: b.get('voter_count',0), reverse=True)
for b in bets[:$TOP_N]:
    top_personality='?'
    bp = b.get('by_personality') or {}
    if bp:
        top_personality=max(bp.items(), key=lambda x: x[1])[0]
    print(f'  {b.get(\"game_key\",\"\")[:40]:<40} {b.get(\"category\",\"\"):<12} {b.get(\"direction\",\"\"):<6} '
          f'voters={b.get(\"voter_count\",0):<4} top_pers={top_personality:<20} stake=\${b.get(\"stake\",0):.0f}')
print()
print(f'  Total bets: {len(bets)}')
"
else
    echo "  [no bet-audit file — run without --dry-run or check $BET_AUDIT]"
fi

echo
echo "════════════════════════════════════════════════════════════════"
echo "Full files:"
echo "  $COUNCIL_LOG"
[[ -f "$BET_AUDIT" ]] && echo "  $BET_AUDIT"
echo "════════════════════════════════════════════════════════════════"
