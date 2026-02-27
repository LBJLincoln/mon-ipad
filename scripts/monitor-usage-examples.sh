#!/bin/bash
# Continuous Monitor — Usage Examples

# ============================================================
# BASIC USAGE
# ============================================================

# 1. Single-run mode (test before running daemon)
source /home/termius/mon-ipad/.env.local
python3 /home/termius/mon-ipad/scripts/continuous-monitor.py --once
# Expected: Runs lightweight ping + deep test once, then exits
# Runtime: ~10-15 minutes
# Output: logs/monitor/YYYY-MM-DD.jsonl + docs/status.json updated

# 2. Start daemon (background monitoring every 5/15 min)
bash /home/termius/mon-ipad/scripts/start-monitor.sh
# Expected: Daemon starts in background
# Output: PID file created at logs/monitor/daemon.pid

# 3. Check daemon status
tail -f /home/termius/mon-ipad/logs/monitor/daemon.log
# or
ps aux | grep continuous-monitor | grep -v grep

# 4. Stop daemon
bash /home/termius/mon-ipad/scripts/stop-monitor.sh
# Expected: Graceful shutdown (SIGTERM), waits up to 10s, then force kills

# ============================================================
# ADVANCED USAGE
# ============================================================

# 5. Manual daemon start (without wrapper scripts)
cd /home/termius/mon-ipad
source .env.local
nohup python3 scripts/continuous-monitor.py > logs/monitor/daemon.log 2>&1 &
echo $! > logs/monitor/daemon.pid
# Useful if wrapper scripts aren't available

# 6. View today's monitoring results
python3 << 'EOF'
import json
from datetime import datetime
log_file = f"logs/monitor/{datetime.utcnow().strftime('%Y-%m-%d')}.jsonl"
with open(log_file) as f:
    for line in f:
        entry = json.loads(line)
        if entry["type"] == "lightweight_ping":
            print(f"{entry['timestamp'][:19]} | Ping: {entry['ok']}/{entry['total_tests']} OK")
            for k, v in entry["patterns"].items():
                if v:
                    print(f"  ⚠️  Pattern: {k}")
        elif entry["type"] == "deep_test":
            print(f"{entry['timestamp'][:19]} | Deep test on {entry['space']}")
            for pipe, res in entry["pipelines"].items():
                print(f"  {pipe}: {res['accuracy_pct']}% ({res['ok']}/{res['tested']})")
EOF

# 7. Check for pattern alerts in last 24h
grep '"patterns":' logs/monitor/$(date -u +%Y-%m-%d).jsonl | \
  grep -E 'rate_limiting.*true|credential_issues.*true|total_outage.*true' && \
  echo "⚠️ ALERTS DETECTED" || echo "✅ No alerts"

# 8. Extract average latency by pipeline (today)
python3 << 'EOF'
import json
from datetime import datetime
from collections import defaultdict

log_file = f"logs/monitor/{datetime.utcnow().strftime('%Y-%m-%d')}.jsonl"
latencies = defaultdict(list)

with open(log_file) as f:
    for line in f:
        entry = json.loads(line)
        if entry["type"] == "lightweight_ping":
            for result in entry["results"]:
                if result["status"] == "ok":
                    latencies[result["pipeline"]].append(result["latency_ms"])

for pipe, times in sorted(latencies.items()):
    avg = sum(times) / len(times) if times else 0
    print(f"{pipe:15} | Avg: {int(avg):5}ms | Samples: {len(times)}")
EOF

# 9. Generate hourly summary report
python3 << 'EOF'
import json
from datetime import datetime
from collections import Counter

log_file = f"logs/monitor/{datetime.utcnow().strftime('%Y-%m-%d')}.jsonl"
hourly = {}

with open(log_file) as f:
    for line in f:
        entry = json.loads(line)
        hour = entry["timestamp"][:13]  # YYYY-MM-DDTHH
        if hour not in hourly:
            hourly[hour] = {"ok": 0, "total": 0, "patterns": Counter()}
        if entry["type"] == "lightweight_ping":
            hourly[hour]["ok"] += entry["ok"]
            hourly[hour]["total"] += entry["total_tests"]
            for k, v in entry["patterns"].items():
                if v:
                    hourly[hour]["patterns"][k] += 1

print("Hourly Summary")
print("=" * 60)
for hour in sorted(hourly.keys()):
    h = hourly[hour]
    pct = round(h["ok"] / h["total"] * 100, 1) if h["total"] > 0 else 0
    patterns_str = ", ".join(f"{k}({v})" for k, v in h["patterns"].items()) or "none"
    print(f"{hour} | {pct:5.1f}% OK ({h['ok']:3}/{h['total']:3}) | Patterns: {patterns_str}")
EOF

# 10. Test single webhook directly (debug mode)
bash /home/termius/mon-ipad/scripts/test-single-ping.sh
# Expected: Tests one webhook with detailed output
# Useful for debugging connectivity issues

# ============================================================
# INTEGRATION WITH DASHBOARD
# ============================================================

# 11. Serve status.json via HTTP (simple Python server)
cd /home/termius/mon-ipad
python3 -m http.server 8080 &
# Dashboard can now fetch: http://localhost:8080/docs/status.json

# 12. Extract monitor section from status.json
python3 -c "import json; s=json.load(open('docs/status.json')); print(json.dumps(s.get('monitor',{}), indent=2))"

# ============================================================
# TROUBLESHOOTING
# ============================================================

# 13. Check if daemon is actually running
if [ -f logs/monitor/daemon.pid ]; then
    PID=$(cat logs/monitor/daemon.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "✅ Daemon running (PID $PID)"
    else
        echo "❌ Daemon not running (stale PID file)"
    fi
else
    echo "❌ No PID file found"
fi

# 14. Force restart daemon
bash /home/termius/mon-ipad/scripts/stop-monitor.sh 2>/dev/null
sleep 2
bash /home/termius/mon-ipad/scripts/start-monitor.sh

# 15. Clear old logs (keep last 7 days)
find logs/monitor -name "*.jsonl" -mtime +7 -delete
echo "Old logs cleared (kept last 7 days)"

# ============================================================
# DEBUGGING SPECIFIC ISSUES
# ============================================================

# 16. Test if .env.local is sourced correctly
source .env.local && [ -n "$N8N_HOST" ] && echo "✅ N8N_HOST set: $N8N_HOST" || echo "❌ N8N_HOST not set"

# 17. Test single space connectivity
curl -s -o /dev/null -w "%{http_code}\n" https://lbjlincoln-nomos-rag-engine.hf.space/

# 18. Find which spaces are down
for space in \
  https://lbjlincoln-nomos-rag-engine.hf.space \
  https://lbjlincoln26-nomos-rag-engine-2.hf.space \
  https://lbjlincoln-nomos-rag-engine-3.hf.space \
  https://lbjlincoln26-nomos-rag-engine-4.hf.space \
  https://lbjlincoln-nomos-rag-engine-5.hf.space \
  https://lbjlincoln26-nomos-rag-engine-6.hf.space \
  https://lbjlincoln-nomos-rag-engine-7.hf.space \
  https://lbjlincoln26-nomos-rag-engine-8.hf.space \
  https://lbjlincoln-nomos-rag-engine-9.hf.space \
  https://lbjlincoln26-nomos-rag-engine-10.hf.space
do
  name=$(echo $space | sed 's/https:\/\///' | cut -d. -f1)
  code=$(curl -s -o /dev/null -w "%{http_code}" $space/ --max-time 10)
  [ "$code" = "200" ] && echo "✅ $name" || echo "❌ $name (HTTP $code)"
done

# 19. Tail multiple log files at once
tail -f logs/monitor/*.log logs/monitor/$(date -u +%Y-%m-%d).jsonl

# 20. Export monitor data to CSV (for Excel analysis)
python3 << 'EOF'
import json, csv
from datetime import datetime
from glob import glob

csv_file = f"logs/monitor/export-{datetime.utcnow().strftime('%Y%m%d')}.csv"
with open(csv_file, 'w', newline='') as csvf:
    writer = csv.writer(csvf)
    writer.writerow(['timestamp', 'type', 'space', 'pipeline', 'status', 'latency_ms', 'error'])

    for log_file in sorted(glob('logs/monitor/*.jsonl')):
        with open(log_file) as f:
            for line in f:
                entry = json.loads(line)
                if entry["type"] == "lightweight_ping":
                    for r in entry["results"]:
                        writer.writerow([
                            entry["timestamp"],
                            "ping",
                            r["space"],
                            r["pipeline"],
                            r["status"],
                            r["latency_ms"],
                            r.get("error", "")
                        ])
print(f"Exported to {csv_file}")
EOF
