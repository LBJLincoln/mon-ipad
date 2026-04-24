#!/bin/bash
# pol_watchdog.sh — if POL is down, fire /api/run. POL's tick loop tends to
# drop into running=False silently; this restarts every 15 min if needed.
URL="https://lbjlincoln26-political-llm-trading-floor.hf.space"
RUNNING=$(curl -s --max-time 8 "$URL/api/status" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('running',False))" 2>/dev/null)
if [ "$RUNNING" = "False" ]; then
  curl -s -X POST "$URL/api/run" > /dev/null 2>&1
  echo "[$(date -u +%FT%H:%MZ)] POL was False, fired /api/run"
else
  echo "[$(date -u +%FT%H:%MZ)] POL ok"
fi
