#!/bin/bash
# agent-log.sh — Log agent activity for live dashboard feed
# Usage: agent-log.sh <agent_name> <event_type> <message> [target_agent]
# Example: agent-log.sh darwin decision "Injecting individual from S14 to S10"
# Example: agent-log.sh karpathy message "Found TabICLv2 paper" darwin

AGENT="${1:?Usage: agent-log.sh <agent> <type> <message> [target]}"
TYPE="${2:?Types: message|decision|result|error|thinking}"
MSG="${3:?Message required}"
TARGET="${4:-}"

LOG_FILE="/home/lahargnedebartoli/mon-ipad/data/agent-activity.json"
MAX_ENTRIES=200

# Create file if missing
[ -f "$LOG_FILE" ] || echo '[]' > "$LOG_FILE"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
ID=$(date +%s%N | sha256sum | head -c 12)

# Build JSON entry
if [ -n "$TARGET" ]; then
  ENTRY="{\"id\":\"${ID}\",\"ts\":\"${TIMESTAMP}\",\"agent\":\"${AGENT}\",\"type\":\"${TYPE}\",\"msg\":$(python3 -c "import json; print(json.dumps('$MSG'))"),\"to\":\"${TARGET}\"}"
else
  ENTRY="{\"id\":\"${ID}\",\"ts\":\"${TIMESTAMP}\",\"agent\":\"${AGENT}\",\"type\":\"${TYPE}\",\"msg\":$(python3 -c "import json; print(json.dumps('$MSG'))")}"
fi

# Append and trim to MAX_ENTRIES
python3 -c "
import json, sys
try:
    with open('$LOG_FILE') as f:
        entries = json.load(f)
except:
    entries = []
entry = json.loads('$ENTRY')
entries.append(entry)
entries = entries[-$MAX_ENTRIES:]
with open('$LOG_FILE', 'w') as f:
    json.dump(entries, f)
"

echo "Logged: [$AGENT] $TYPE: $MSG"
