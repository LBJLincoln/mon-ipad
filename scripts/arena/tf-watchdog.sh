#!/bin/bash
# TF watchdog — restart NBA + POL trading floors when HF container preempts.
# Runs every 2 min via cron. State resumes from hub-persisted day decisions
# (see app.py:_load_state_from_disk + _push_day_decisions_to_hub).
set -u
LOG=/home/termius/mon-ipad/logs/tf-watchdog.log
mkdir -p "$(dirname "$LOG")"

check_and_restart() {
  local tag="$1" url="$2"
  local status running http_code
  http_code=$(curl -s -o /tmp/tf-status-"$tag".json -w "%{http_code}" --max-time 10 "$url/api/status" 2>/dev/null || echo "000")
  if [ "$http_code" != "200" ]; then
    echo "$(date -u +%FT%TZ) $tag HTTP=$http_code — skipping (Space waking)" >> "$LOG"
    return
  fi
  running=$(python3 -c "import json; d=json.load(open('/tmp/tf-status-$tag.json')); print(d.get('running'))" 2>/dev/null || echo "?")
  if [ "$running" = "True" ]; then
    return  # healthy, nothing to do
  fi
  # Not running → kick it
  local resp
  resp=$(curl -s -X POST --max-time 15 "$url/api/run" 2>/dev/null || echo "curl_err")
  echo "$(date -u +%FT%TZ) $tag running=$running → restart: $resp" >> "$LOG"
}

check_and_restart NBA https://lbjlincoln26-nba-llm-trading-floor.hf.space
check_and_restart POL https://lbjlincoln26-political-llm-trading-floor.hf.space
