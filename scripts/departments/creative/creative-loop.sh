#!/bin/bash
# Department: CREATIVE — Dashboard Deployment Health Monitor
# (Converted from zombie RGWA scanner to Vercel deployment health check)
# Pattern: Check Vercel deployment → measure error rate / build status → alert on regressions
# No mutation — pure health monitor with keep/alert logic
# Output: data/departments/creative/karpathy-output.json
#         data/departments/creative/metrics.jsonl
set -uo pipefail

DEPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$(dirname "$(dirname "$DEPT_DIR")")")"
export ROOT
DATA_OUT="$ROOT/data/departments/creative"
METRICS_FILE="$DATA_OUT/metrics.jsonl"
OUTPUT_FILE="$DATA_OUT/karpathy-output.json"

mkdir -p "$DATA_OUT"

ONCE=false
for arg in "$@"; do
    [[ "$arg" == "--once" ]] && ONCE=true
done

# ── Iteration counter ─────────────────────────────────────────────────────────
ITER_FILE="$DATA_OUT/.iteration"
ITERATION=$(cat "$ITER_FILE" 2>/dev/null || echo 0)
ITERATION=$((ITERATION + 1))
echo "$ITERATION" > "$ITER_FILE"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "=== CREATIVE/DASHBOARD HEALTH iter=$ITERATION @ $TIMESTAMP ==="

# ── STEP 1: Check Vercel deployment status via API ───────────────────────────
VERCEL_STATUS=$(timeout 8 python3 - << 'PYEOF'
import json, os, urllib.request, urllib.error
from datetime import datetime

token = os.environ.get("VERCEL_TOKEN", "")
team_id = os.environ.get("VERCEL_TEAM_ID", "")

result = {
    "reachable": False,
    "latest_deployment": None,
    "deployment_state": "unknown",
    "deployment_url": None,
    "created_at": None,
    "error": None,
}

if not token:
    result["error"] = "VERCEL_TOKEN not set"
    print(json.dumps(result))
    exit(0)

try:
    # Get latest deployments for the nomos-dashboard project
    url = "https://api.vercel.com/v6/deployments?limit=1&projectId=nomos-dashboard"
    if team_id:
        url += f"&teamId={team_id}"

    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read())

    deployments = data.get("deployments", [])
    if deployments:
        d = deployments[0]
        result["reachable"] = True
        result["latest_deployment"] = d.get("uid")
        result["deployment_state"] = d.get("state", "unknown")
        result["deployment_url"] = d.get("url")
        result["created_at"] = d.get("createdAt")

except urllib.error.HTTPError as e:
    result["error"] = f"HTTP {e.code}: {e.reason}"
except Exception as e:
    result["error"] = str(e)[:200]

print(json.dumps(result))
PYEOF
)
[ -z "$VERCEL_STATUS" ] && VERCEL_STATUS='{"deployment_state":"unknown","error":"timeout","reachable":false}'

DEPLOYMENT_STATE=$(echo "$VERCEL_STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('deployment_state', 'unknown'))" 2>/dev/null || echo "unknown")
VERCEL_ERROR=$(echo "$VERCEL_STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('error') or '')" 2>/dev/null || echo "")
echo "  Vercel deployment: $DEPLOYMENT_STATE"

# ── STEP 2: Ping dashboard health endpoint ────────────────────────────────────
DASHBOARD_URL="https://nomos42.com"
DASHBOARD_HEALTH=$(timeout 8 python3 - "$DASHBOARD_URL" << 'PYEOF'
import sys, json, urllib.request, urllib.error, time

url = sys.argv[1]
result = {
    "url": url,
    "reachable": False,
    "status_code": None,
    "latency_ms": None,
    "error": None,
}

try:
    start = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": "Nomos42-HealthMonitor/1.0"})
    with urllib.request.urlopen(req, timeout=6) as r:
        result["status_code"] = r.status
        result["reachable"] = r.status < 400
    result["latency_ms"] = round((time.time() - start) * 1000, 1)
except urllib.error.HTTPError as e:
    result["status_code"] = e.code
    result["error"] = f"HTTP {e.code}"
except Exception as e:
    result["error"] = str(e)[:200]

print(json.dumps(result))
PYEOF
)
[ -z "$DASHBOARD_HEALTH" ] && DASHBOARD_HEALTH='{"url":"https://nomos42.com","reachable":false,"status_code":null,"latency_ms":null,"error":"timeout"}'

STATUS_CODE=$(echo "$DASHBOARD_HEALTH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status_code'))" 2>/dev/null || echo "null")
LATENCY_MS=$(echo "$DASHBOARD_HEALTH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('latency_ms'))" 2>/dev/null || echo "null")
REACHABLE=$(echo "$DASHBOARD_HEALTH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('reachable', False))" 2>/dev/null || echo "False")
echo "  Dashboard: status=$STATUS_CODE  latency=${LATENCY_MS}ms  reachable=$REACHABLE"

# ── STEP 3: Check API routes ──────────────────────────────────────────────────
API_HEALTH=$(timeout 12 python3 - << 'PYEOF'
import json, urllib.request, urllib.error, time

routes = [
    "/api/status",
    "/api/nba/predictions",
    "/api/arena/cpcv-gate",
]
results = {}

for route in routes:
    url = f"https://nomos42.com{route}"
    try:
        start = time.time()
        req = urllib.request.Request(url, headers={"User-Agent": "Nomos42-HealthMonitor/1.0"})
        with urllib.request.urlopen(req, timeout=4) as r:
            latency = round((time.time() - start) * 1000, 1)
            results[route] = {"status": r.status, "latency_ms": latency, "ok": r.status < 400}
    except urllib.error.HTTPError as e:
        results[route] = {"status": e.code, "latency_ms": None, "ok": False}
    except Exception as e:
        results[route] = {"status": None, "latency_ms": None, "ok": False, "error": str(e)[:100]}

healthy = sum(1 for v in results.values() if v.get("ok"))
print(json.dumps({"routes": results, "healthy": healthy, "total": len(routes)}))
PYEOF
)
[ -z "$API_HEALTH" ] && API_HEALTH='{"routes":{},"healthy":0,"total":3}'

API_HEALTHY=$(echo "$API_HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('healthy', 0))" 2>/dev/null || echo 0)
API_TOTAL=$(echo "$API_HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('total', 3))" 2>/dev/null || echo 3)
echo "  API routes: $API_HEALTHY/$API_TOTAL healthy"

# ── STEP 4: Compare to previous iteration ────────────────────────────────────
PREV_LATENCY="null"
if [ -f "$OUTPUT_FILE" ]; then
    PREV_LATENCY=$(python3 -c "import json; d=json.load(open('$OUTPUT_FILE')); v=d.get('metrics',{}).get('latency_ms'); print(v if v is not None else 'null')" 2>/dev/null || echo "null")
fi

# ── STEP 5: Determine health status ──────────────────────────────────────────
HEALTH=$(python3 - "$REACHABLE" "$STATUS_CODE" "$LATENCY_MS" "$API_HEALTHY" "$API_TOTAL" "$PREV_LATENCY" "$DEPLOYMENT_STATE" << 'PYEOF'
import sys, json

reachable   = sys.argv[1] == "True"
sc_raw      = sys.argv[2]
lat_raw     = sys.argv[3]
api_healthy = int(sys.argv[4])
api_total   = int(sys.argv[5])
prev_lat    = float(sys.argv[6]) if sys.argv[6] not in ("null", "None") else None
dep_state   = sys.argv[7]

status_code = int(sc_raw) if sc_raw not in ("null", "None") else None
latency_ms  = float(lat_raw) if lat_raw not in ("null", "None") else None

health = "ok"
if not reachable:
    health = "critical"
elif status_code and status_code >= 400:
    health = "critical"
elif latency_ms and latency_ms > 3000:
    health = "warning"
elif prev_lat and latency_ms and latency_ms > prev_lat * 1.5:
    health = "warning"
elif api_healthy < api_total:
    health = "warning"
print(health)
PYEOF
)

echo "  Health: $HEALTH"

# ── STEP 6: Write output + metrics ───────────────────────────────────────────
export _CL_VERCEL="$VERCEL_STATUS"
export _CL_DASH="$DASHBOARD_HEALTH"
export _CL_API="$API_HEALTH"
python3 - "$REACHABLE" "$STATUS_CODE" "$LATENCY_MS" \
          "$API_HEALTHY" "$API_TOTAL" "$DEPLOYMENT_STATE" \
          "$TIMESTAMP" "$ITERATION" "$HEALTH" \
          "$METRICS_FILE" "$OUTPUT_FILE" << 'PYEOF'
import sys, json, os

vercel_status    = json.loads(os.environ.get("_CL_VERCEL", "{}"))
dashboard_health = json.loads(os.environ.get("_CL_DASH", "{}"))
api_health       = json.loads(os.environ.get("_CL_API", "{}"))
reachable        = sys.argv[1] == "True"
sc_raw           = sys.argv[2]
lat_raw          = sys.argv[3]
api_healthy      = int(sys.argv[4])
api_total        = int(sys.argv[5])
dep_state        = sys.argv[6]
timestamp        = sys.argv[7]
iteration        = int(sys.argv[8])
health           = sys.argv[9]
metrics_file     = sys.argv[10]
output_file      = sys.argv[11]

status_code = int(sc_raw) if sc_raw not in ("null", "None") else None
latency_ms  = float(lat_raw) if lat_raw not in ("null", "None") else None

out = {
    "department": "creative",
    "mode": "dashboard_health_monitor",
    "timestamp": timestamp,
    "iteration": iteration,
    "health": health,
    "metrics": {
        "status_code": status_code,
        "latency_ms": latency_ms,
        "reachable": reachable,
        "api_healthy": api_healthy,
        "api_total": api_total,
    },
    "vercel": vercel_status,
    "dashboard": dashboard_health,
    "api_routes": api_health,
    "improved": health == "ok",
    "status": "completed",
}
with open(output_file, "w") as f:
    json.dump(out, f, indent=2)

metric = {
    "ts": timestamp,
    "iter": iteration,
    "health": health,
    "status_code": status_code,
    "latency_ms": latency_ms,
    "api_healthy": api_healthy,
    "api_total": api_total,
    "deployment_state": dep_state,
}
with open(metrics_file, "a") as f:
    f.write(json.dumps(metric) + "\n")
print("ok")
PYEOF

echo "  Output: $OUTPUT_FILE | health=$HEALTH  api=$API_HEALTHY/$API_TOTAL  latency=${LATENCY_MS}ms"
[ "$ONCE" = "true" ] && exit 0

echo "  Sleeping 5 minutes..."
sleep 300
exec "$0" "$@"
