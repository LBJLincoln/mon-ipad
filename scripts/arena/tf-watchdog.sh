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
  llm_calls=$(python3 -c "import json; d=json.load(open('/tmp/tf-status-$tag.json')); print(d.get('llm_calls', 0))" 2>/dev/null || echo "0")
  started=$(python3 -c "import json; d=json.load(open('/tmp/tf-status-$tag.json')); print(d.get('started_utc', ''))" 2>/dev/null || echo "")
  # Healthy = running AND has actually called the LLM (not stuck pre-loop).
  # 2026-04-26 fix: NameError on sys.stderr made running=True but llm_calls=0
  # for 30+ min after Day-0 reset. Watchdog now detects this stuck state.
  if [ "$running" = "True" ]; then
    if [ "$llm_calls" -gt 0 ]; then
      return  # truly healthy
    fi
    # running=True but 0 LLM calls — check age
    if [ -n "$started" ]; then
      local age_sec
      age_sec=$(python3 -c "from datetime import datetime, timezone; t=datetime.fromisoformat('$started'.replace('Z','+00:00')); print(int((datetime.now(timezone.utc)-t).total_seconds()))" 2>/dev/null || echo "0")
      if [ "$age_sec" -lt 300 ]; then
        return  # <5min, still warming up
      fi
      echo "$(date -u +%FT%TZ) $tag STUCK: running=True llm_calls=0 after ${age_sec}s — forcing /api/run" >> "$LOG"
    fi
  fi
  # Not running, OR running-but-stuck → kick it
  local resp
  resp=$(curl -s -X POST --max-time 15 "$url/api/run" 2>/dev/null || echo "curl_err")
  echo "$(date -u +%FT%TZ) $tag running=$running llm_calls=$llm_calls → restart: $resp" >> "$LOG"
}

# DISABLED 2026-04-27 to preserve NBA halt — re-enable when better Oracle wired
# check_and_restart NBA https://lbjlincoln26-nba-llm-trading-floor.hf.space
check_and_restart POL https://lbjlincoln26-political-llm-trading-floor.hf.space
