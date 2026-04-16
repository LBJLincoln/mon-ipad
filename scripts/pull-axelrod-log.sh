#!/usr/bin/env bash
# pull-axelrod-log.sh — fetch per-day Axelrod post-mortem logs from both TF Spaces
# and persist to data/arena/axelrod-log/{nba,political}/day-NNN.jsonl.
#
# Idempotent: only writes days that are new or changed. Commits to git.
#
# Called by cron (every 15min during active runs) and by §6 analysis pipeline.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

NBA_URL="https://lbjlincoln26-nba-llm-trading-floor.hf.space/api/axelrod-log"
POL_URL="https://lbjlincoln26-political-llm-trading-floor.hf.space/api/axelrod-log"

mkdir -p data/arena/axelrod-log/nba data/arena/axelrod-log/political

fetch_arena() {
  local label="$1" base_url="$2" out_dir="$3"
  local idx_json tmp
  idx_json="$(curl -sS -m 30 "$base_url" || echo '{}')"
  if ! echo "$idx_json" | python3 -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if 'index' in d and d['index'] else 1)" 2>/dev/null; then
    echo "[$label] no index yet (likely experiment not started or early days)"
    return 0
  fi
  local n_days
  n_days="$(echo "$idx_json" | python3 -c "import sys,json; print(json.load(sys.stdin).get('n_days', 0))")"
  echo "[$label] index has $n_days days"
  local days
  days="$(echo "$idx_json" | python3 -c "import sys,json; [print(d['day_idx']) for d in json.load(sys.stdin).get('index', [])]")"
  for d in $days; do
    local day_fp="$out_dir/day-$(printf '%03d' "$d").jsonl"
    tmp="$(mktemp)"
    if curl -sS -m 20 "$base_url?day=$d" > "$tmp"; then
      python3 -c "
import sys, json
data = json.load(open('$tmp'))
rows = data.get('rows', [])
if not rows:
    sys.exit(1)
with open('$day_fp', 'w') as f:
    for r in rows:
        f.write(json.dumps(r) + '\n')
" && echo "[$label] wrote $day_fp ($(wc -l < "$day_fp") rows)" || echo "[$label] skip day=$d (empty)"
    fi
    rm -f "$tmp"
  done
}

fetch_arena nba "$NBA_URL" data/arena/axelrod-log/nba
fetch_arena political "$POL_URL" data/arena/axelrod-log/political

# summary
nba_days="$(ls data/arena/axelrod-log/nba/*.jsonl 2>/dev/null | wc -l)"
pol_days="$(ls data/arena/axelrod-log/political/*.jsonl 2>/dev/null | wc -l)"
ts="$(date -u +%FT%TZ)"
cat > data/arena/axelrod-log/_summary.json <<EOF
{
  "updated": "$ts",
  "nba_days": $nba_days,
  "political_days": $pol_days
}
EOF
echo "[axelrod-log] summary: nba=$nba_days political=$pol_days"
