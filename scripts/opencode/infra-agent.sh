#!/bin/bash
################################################################################
# Infrastructure Department Agent — OpenCode + Fallback
# Checks health of all systems: HF Spaces, VM, crons, data freshness
# Output: data/opencode/infra-latest.json
# Schedule: Every 4 hours, offset 15min (via install-crons.sh)
################################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

DEPT="infra"
OUTPUT_FILE="$DATA_DIR/infra-latest.json"

log "$DEPT" "Starting infrastructure health check..."

# Gather live system metrics (lightweight, no ML)
SYSTEM_METRICS=$(python3 -c "
import json, os, subprocess, time
from datetime import datetime, timezone

metrics = {}

# Disk usage
try:
    result = subprocess.run(['df', '-h', '/'], capture_output=True, text=True, timeout=5)
    lines = result.stdout.strip().split('\n')
    if len(lines) > 1:
        parts = lines[1].split()
        metrics['disk'] = {
            'total': parts[1] if len(parts) > 1 else 'unknown',
            'used': parts[2] if len(parts) > 2 else 'unknown',
            'available': parts[3] if len(parts) > 3 else 'unknown',
            'percent': parts[4] if len(parts) > 4 else 'unknown'
        }
except Exception as e:
    metrics['disk'] = {'error': str(e)}

# Memory usage
try:
    result = subprocess.run(['free', '-m'], capture_output=True, text=True, timeout=5)
    lines = result.stdout.strip().split('\n')
    if len(lines) > 1:
        parts = lines[1].split()
        metrics['memory'] = {
            'total_mb': int(parts[1]) if len(parts) > 1 else 0,
            'used_mb': int(parts[2]) if len(parts) > 2 else 0,
            'free_mb': int(parts[3]) if len(parts) > 3 else 0,
            'available_mb': int(parts[6]) if len(parts) > 6 else 0
        }
except Exception as e:
    metrics['memory'] = {'error': str(e)}

# Load average
try:
    load = os.getloadavg()
    metrics['load'] = {'1m': load[0], '5m': load[1], '15m': load[2]}
except Exception as e:
    metrics['load'] = {'error': str(e)}

# Uptime
try:
    with open('/proc/uptime') as f:
        uptime_seconds = float(f.read().split()[0])
    days = int(uptime_seconds // 86400)
    hours = int((uptime_seconds % 86400) // 3600)
    metrics['uptime'] = f'{days}d {hours}h'
except Exception as e:
    metrics['uptime'] = str(e)

# Data freshness checks
data_files = {
    'agent_health': '/home/termius/mon-ipad/data/agent-health.json',
    'infra_status': '/home/termius/mon-ipad/data/infra-status.json',
    'bankroll_state': '/home/termius/mon-ipad/data/nba-agent/bankroll-state.json',
    'quant_summary': '/home/termius/mon-ipad/data/nba-agent/quant-summary.json',
    'guardian_report': '/home/termius/mon-ipad/data/departments/guardian-report.json',
}

metrics['data_freshness'] = {}
now = time.time()
for name, path in data_files.items():
    try:
        mtime = os.path.getmtime(path)
        age_hours = (now - mtime) / 3600
        metrics['data_freshness'][name] = {
            'age_hours': round(age_hours, 1),
            'stale': age_hours > 12,
            'last_modified': datetime.fromtimestamp(mtime, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        }
    except FileNotFoundError:
        metrics['data_freshness'][name] = {'error': 'file not found'}

# HF Spaces health (quick HTTP check, no heavy calls)
spaces = {
    'S10': 'https://nomos42-nba-quant.hf.space/api/status',
    'S11': 'https://nomos42-nba-quant-2.hf.space/api/status',
    'S12': 'https://nomos42-nba-evo-3.hf.space/api/status',
    'S13': 'https://nomos42-nba-evo-4.hf.space/api/status',
    'S14': 'https://nomos42-nba-evo-5.hf.space/api/status',
    'S15': 'https://nomos42-nba-evo-6.hf.space/api/status',
}

metrics['hf_spaces'] = {}
import urllib.request
for name, url in spaces.items():
    try:
        req = urllib.request.Request(url, method='GET')
        req.add_header('User-Agent', 'Nomos42-Infra-Agent/1.0')
        with urllib.request.urlopen(req, timeout=10) as resp:
            status_code = resp.getcode()
            body = resp.read().decode('utf-8')[:500]
            try:
                data = json.loads(body)
                metrics['hf_spaces'][name] = {
                    'status': 'up',
                    'http_code': status_code,
                    'generation': data.get('generation', 'unknown'),
                    'best_brier': data.get('best_brier', 'unknown')
                }
            except:
                metrics['hf_spaces'][name] = {'status': 'up', 'http_code': status_code}
    except Exception as e:
        metrics['hf_spaces'][name] = {'status': 'down', 'error': str(e)[:100]}

print(json.dumps(metrics, indent=2))
" 2>/dev/null || echo '{"error": "metrics collection failed"}')

# Build the prompt with live metrics
PROMPT=$(cat <<PROMPT_END
You are the Infrastructure Department AI for Nomos42, an NBA prediction system.

Your task: Analyze the current system health and provide actionable recommendations.

Live system metrics:
$SYSTEM_METRICS

System architecture:
- VM: 1 vCPU, 969 MB RAM, 30GB disk (ZERO ML allowed on VM)
- 6 HF Spaces running evolution islands (CPU, tree-based only)
- Cron jobs: keepalive every 30min, predictions at game time, autonomous cycle every 4h
- Data server: auto-restart on failure
- GPU: Kaggle P100 (9h sessions), Colab T4 (on-demand)

Respond with a JSON object:
{
  "check_date": "YYYY-MM-DD",
  "overall_health": "green/yellow/red",
  "vm_status": {
    "health": "green/yellow/red",
    "disk_warning": true/false,
    "memory_pressure": true/false,
    "issues": ["list of issues"]
  },
  "spaces_status": {
    "healthy_count": 0,
    "total_count": 6,
    "down_spaces": ["list"],
    "issues": ["list of issues"]
  },
  "data_freshness": {
    "health": "green/yellow/red",
    "stale_files": ["list of stale data"],
    "issues": ["list of issues"]
  },
  "cron_health": {
    "health": "green/yellow/red",
    "issues": ["list of issues"]
  },
  "critical_alerts": [
    {
      "severity": "critical/warning/info",
      "component": "what is affected",
      "message": "description",
      "action": "recommended fix"
    }
  ],
  "recommendations": [
    {
      "priority": 1,
      "action": "what to do",
      "reason": "why"
    }
  ]
}
PROMPT_END
)

# Try OpenCode first, fallback to direct API
if opencode_available; then
    log "$DEPT" "Using OpenCode"

    RAW_OUTPUT=$(run_opencode "$PROMPT" "text" 2>&1) || true

    if [ -n "$RAW_OUTPUT" ] && [ "$RAW_OUTPUT" != "" ]; then
        JSON_OUTPUT=$(echo "$RAW_OUTPUT" | python3 -c "
import sys, json, re
text = sys.stdin.read()
matches = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
for m in matches:
    try:
        parsed = json.loads(m)
        if 'check_date' in parsed or 'overall_health' in parsed or 'vm_status' in parsed:
            print(json.dumps(parsed, indent=2))
            sys.exit(0)
    except:
        continue
print(json.dumps({'raw_output': text[:2000], 'parse_note': 'Could not extract structured JSON'}))
" 2>/dev/null)

        write_output "$DEPT" "$JSON_OUTPUT" "$OUTPUT_FILE" "opencode"
        log "$DEPT" "Output written to $OUTPUT_FILE (via OpenCode)"
    else
        log "$DEPT" "OpenCode returned empty, falling back to API"
        run_fallback "$PROMPT" "$OUTPUT_FILE"
        log "$DEPT" "Output written to $OUTPUT_FILE (via API fallback)"
    fi
else
    log "$DEPT" "OpenCode not available, using API fallback"

    # For infra, even without AI we can write raw metrics
    if [ -z "$OPENROUTER_API_KEY" ] && [ -z "$OPENAI_API_KEY" ]; then
        log "$DEPT" "No API keys either, writing raw metrics only"
        python3 -c "
import json
from datetime import datetime, timezone

metrics = json.loads('''$SYSTEM_METRICS''')
result = {
    'department': 'infra',
    'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    'method': 'raw_metrics',
    'version': '1.0',
    'data': {
        'check_date': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
        'overall_health': 'unknown',
        'raw_metrics': metrics,
        'note': 'AI analysis unavailable, raw metrics only'
    }
}
print(json.dumps(result, indent=2))
" > "$OUTPUT_FILE"
        log "$DEPT" "Output written to $OUTPUT_FILE (raw metrics only)"
    else
        run_fallback "$PROMPT" "$OUTPUT_FILE"
        log "$DEPT" "Output written to $OUTPUT_FILE (via API fallback)"
    fi
fi

# Validate output
if [ -f "$OUTPUT_FILE" ]; then
    SIZE=$(stat -f%z "$OUTPUT_FILE" 2>/dev/null || stat -c%s "$OUTPUT_FILE" 2>/dev/null || echo "0")
    if [ "$SIZE" -gt 10 ]; then
        log "$DEPT" "Success: $OUTPUT_FILE ($SIZE bytes)"
    else
        log "$DEPT" "WARNING: Output file suspiciously small ($SIZE bytes)"
    fi
else
    log "$DEPT" "ERROR: Output file not created"
    exit 1
fi
