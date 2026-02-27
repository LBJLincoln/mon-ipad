# Remote Control Server

HTTP API server for remote management of Multi-RAG pipelines.

## Overview

The Remote Control Server (`remote-control.py`) provides a RESTful HTTP interface to manage RAG pipelines remotely. It runs on the VM and allows external clients to:

- Check pipeline health status
- Launch automated fixes
- Trigger pipeline reverts
- Run quick tests
- Monitor background jobs

## Quick Start

### 1. Setup Authentication

Generate or set an auth key in `.env.local`:

```bash
# Option A: Let the server generate a random key (prints on startup)
python3 scripts/remote-control.py

# Option B: Set your own key
echo 'export REMOTE_CONTROL_KEY=your-secret-key-here' >> .env.local
source .env.local
```

### 2. Start Server

```bash
# Default port 8081
python3 scripts/remote-control.py

# Custom port
python3 scripts/remote-control.py --port 8082

# Background (production)
nohup python3 scripts/remote-control.py > logs/remote-control.log 2>&1 &
echo $! > logs/remote-control.pid
```

### 3. Test Connection

```bash
# Using curl
curl -H "X-Auth-Key: $REMOTE_CONTROL_KEY" http://localhost:8081/status

# Using test script
./scripts/test-remote-control.sh
```

## Authentication

All requests require the `X-Auth-Key` header:

```bash
curl -H "X-Auth-Key: YOUR_KEY_HERE" http://localhost:8081/status
```

Missing or invalid key returns `401 Unauthorized`.

## API Endpoints

### GET /status

Get health status of all 4 RAG pipelines.

**Request:**
```bash
curl -H "X-Auth-Key: $REMOTE_CONTROL_KEY" http://localhost:8081/status
```

**Response (200 OK):**
```json
{
  "timestamp": "2026-02-27T18:30:00Z",
  "n8n_host": "https://lbjlincoln-nomos-rag-engine.hf.space",
  "overall_status": "healthy",
  "summary": {
    "total": 4,
    "healthy": 3,
    "degraded": 1,
    "down": 0
  },
  "pipelines": {
    "standard": {
      "pipeline": "standard",
      "url": "https://...",
      "status": "healthy",
      "http_code": 200,
      "latency_ms": 2845,
      "expected_latency_ms": 3000,
      "answer_length": 142,
      "error": null,
      "checked_at": "2026-02-27T18:30:00Z"
    },
    "graph": { ... },
    "quantitative": { ... },
    "orchestrator": { ... }
  }
}
```

**Status values:**
- `healthy` - working normally
- `degraded` - slow or short answers
- `down` - HTTP errors or no response
- `timeout` - exceeded timeout threshold

### POST /fix/\<pipeline\>

Launch auto-remediate.py for a pipeline (background job).

**Request:**
```bash
curl -X POST -H "X-Auth-Key: $REMOTE_CONTROL_KEY" \
  http://localhost:8081/fix/standard
```

**Response (202 Accepted):**
```json
{
  "job_id": "fix-standard-1",
  "message": "Fix job started for standard",
  "command": "python3 /home/termius/mon-ipad/scripts/auto-remediate.py --pipeline standard"
}
```

**Pipelines:** `standard`, `graph`, `quantitative`, `orchestrator`

### POST /revert/\<pipeline\>

Launch auto-revert.py for a pipeline (background job).

**Request:**
```bash
curl -X POST -H "X-Auth-Key: $REMOTE_CONTROL_KEY" \
  http://localhost:8081/revert/graph
```

**Response (202 Accepted):**
```json
{
  "job_id": "revert-graph-2",
  "message": "Revert job started for graph",
  "command": "python3 /home/termius/mon-ipad/scripts/auto-revert.py --pipeline graph"
}
```

### POST /test/\<pipeline\>/\<n\>

Launch quick-test.py with N questions (background job).

**Request:**
```bash
# Test quantitative pipeline with 5 questions
curl -X POST -H "X-Auth-Key: $REMOTE_CONTROL_KEY" \
  http://localhost:8081/test/quantitative/5
```

**Response (202 Accepted):**
```json
{
  "job_id": "test-quantitative-3",
  "message": "Test job started for quantitative with 5 questions",
  "command": "python3 /home/termius/mon-ipad/eval/quick-test.py --questions 5 --pipeline quantitative"
}
```

**Constraints:**
- `n` must be between 1 and 100

### GET /jobs

List all background jobs (running and completed).

**Request:**
```bash
curl -H "X-Auth-Key: $REMOTE_CONTROL_KEY" http://localhost:8081/jobs
```

**Response (200 OK):**
```json
{
  "jobs": [
    {
      "id": "test-standard-1",
      "type": "test",
      "pipeline": "standard",
      "command": "python3 /home/termius/mon-ipad/eval/quick-test.py --questions 5 --pipeline standard",
      "status": "completed",
      "started_at": "2026-02-27T18:25:00Z",
      "finished_at": "2026-02-27T18:26:15Z",
      "stdout": "[test output]",
      "stderr": "",
      "exit_code": 0
    },
    {
      "id": "fix-graph-2",
      "type": "fix",
      "pipeline": "graph",
      "command": "python3 /home/termius/mon-ipad/scripts/auto-remediate.py --pipeline graph",
      "status": "running",
      "started_at": "2026-02-27T18:27:00Z",
      "finished_at": null,
      "stdout": "",
      "stderr": "",
      "exit_code": null
    }
  ],
  "count": 2
}
```

**Job status:**
- `running` - currently executing
- `completed` - finished successfully (exit code 0)
- `failed` - finished with error (exit code != 0)

### GET /jobs/\<id\>

Get details of a specific job.

**Request:**
```bash
curl -H "X-Auth-Key: $REMOTE_CONTROL_KEY" http://localhost:8081/jobs/test-standard-1
```

**Response (200 OK):**
```json
{
  "id": "test-standard-1",
  "type": "test",
  "pipeline": "standard",
  "command": "python3 /home/termius/mon-ipad/eval/quick-test.py --questions 5 --pipeline standard",
  "status": "completed",
  "started_at": "2026-02-27T18:25:00Z",
  "finished_at": "2026-02-27T18:26:15Z",
  "stdout": "[full test output]",
  "stderr": "",
  "exit_code": 0
}
```

**Response (404 Not Found):**
```json
{
  "error": "Job not found: invalid-job-id",
  "status": 404,
  "timestamp": "2026-02-27T18:30:00Z"
}
```

## Error Responses

All errors return JSON with `error`, `status`, and `timestamp` fields.

### 401 Unauthorized
```json
{
  "error": "Unauthorized. Missing or invalid X-Auth-Key header.",
  "status": 401,
  "timestamp": "2026-02-27T18:30:00Z"
}
```

### 404 Not Found
```json
{
  "error": "Unknown endpoint: /invalid",
  "status": 404,
  "timestamp": "2026-02-27T18:30:00Z"
}
```

### 400 Bad Request
```json
{
  "error": "Unknown pipeline: invalid-pipeline",
  "status": 400,
  "timestamp": "2026-02-27T18:30:00Z"
}
```

### 500 Internal Server Error
```json
{
  "error": "Failed to start test job: [error details]",
  "status": 500,
  "timestamp": "2026-02-27T18:30:00Z"
}
```

## CORS Support

The server includes CORS headers for browser access:

```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, POST, OPTIONS
Access-Control-Allow-Headers: Content-Type, X-Auth-Key
```

Browsers will automatically send OPTIONS preflight requests, which are handled correctly.

## Logging

All events are logged to `logs/remote-control.jsonl` in JSON Lines format:

```json
{"timestamp": "2026-02-27T18:25:00Z", "event": "server_started", "port": 8081, "pid": 12345}
{"timestamp": "2026-02-27T18:26:00Z", "event": "status_check", "overall": "healthy"}
{"timestamp": "2026-02-27T18:27:00Z", "event": "job_started", "job_id": "test-standard-1", "type": "test", "pipeline": "standard", "command": "..."}
{"timestamp": "2026-02-27T18:28:15Z", "event": "job_finished", "job_id": "test-standard-1", "status": "completed", "exit_code": 0}
{"timestamp": "2026-02-27T19:00:00Z", "event": "server_stopped"}
```

## Production Deployment

### systemd Service (Recommended)

Create `/etc/systemd/system/remote-control.service`:

```ini
[Unit]
Description=Multi-RAG Remote Control Server
After=network.target

[Service]
Type=simple
User=termius
WorkingDirectory=/home/termius/mon-ipad
EnvironmentFile=/home/termius/mon-ipad/.env.local
ExecStart=/usr/bin/python3 /home/termius/mon-ipad/scripts/remote-control.py --port 8081
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable remote-control
sudo systemctl start remote-control
sudo systemctl status remote-control
```

View logs:
```bash
sudo journalctl -u remote-control -f
```

### Manual Background Process

```bash
# Start
nohup python3 scripts/remote-control.py > logs/remote-control.log 2>&1 &
echo $! > logs/remote-control.pid

# Stop
kill $(cat logs/remote-control.pid)

# View logs
tail -f logs/remote-control.log
```

## Security Considerations

1. **Authentication**: Always set a strong `REMOTE_CONTROL_KEY` in production
2. **Network**: Use firewall rules to restrict access (e.g., only allow specific IPs)
3. **HTTPS**: Consider running behind nginx with SSL/TLS termination
4. **Rate Limiting**: Add nginx rate limiting to prevent abuse

### Example nginx Config

```nginx
upstream remote_control {
    server localhost:8081;
}

server {
    listen 443 ssl;
    server_name control.example.com;

    ssl_certificate /etc/letsencrypt/live/control.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/control.example.com/privkey.pem;

    location / {
        proxy_pass http://remote_control;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        # Rate limiting
        limit_req zone=api burst=10 nodelay;
    }
}

# Rate limit zone
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
```

## Integration Examples

### Python Client

```python
import requests

BASE_URL = "http://localhost:8081"
AUTH_KEY = "your-key-here"

def get_status():
    resp = requests.get(
        f"{BASE_URL}/status",
        headers={"X-Auth-Key": AUTH_KEY}
    )
    return resp.json()

def launch_test(pipeline, n_questions):
    resp = requests.post(
        f"{BASE_URL}/test/{pipeline}/{n_questions}",
        headers={"X-Auth-Key": AUTH_KEY}
    )
    return resp.json()

# Usage
status = get_status()
print(f"Overall: {status['overall_status']}")

job = launch_test("standard", 5)
print(f"Job ID: {job['job_id']}")
```

### JavaScript (Browser)

```javascript
const BASE_URL = "http://localhost:8081";
const AUTH_KEY = "your-key-here";

async function getStatus() {
  const response = await fetch(`${BASE_URL}/status`, {
    headers: { "X-Auth-Key": AUTH_KEY }
  });
  return await response.json();
}

async function launchTest(pipeline, nQuestions) {
  const response = await fetch(`${BASE_URL}/test/${pipeline}/${nQuestions}`, {
    method: "POST",
    headers: { "X-Auth-Key": AUTH_KEY }
  });
  return await response.json();
}

// Usage
getStatus().then(status => {
  console.log("Overall:", status.overall_status);
});

launchTest("standard", 5).then(job => {
  console.log("Job ID:", job.job_id);
});
```

### Bash Script

```bash
#!/bin/bash
source .env.local

BASE_URL="http://localhost:8081"
AUTH_HEADER="X-Auth-Key: $REMOTE_CONTROL_KEY"

# Get status
curl -s -H "$AUTH_HEADER" "$BASE_URL/status" | jq .

# Launch test
JOB=$(curl -s -H "$AUTH_HEADER" -X POST "$BASE_URL/test/standard/5")
JOB_ID=$(echo "$JOB" | jq -r .job_id)

echo "Job ID: $JOB_ID"

# Poll job status
while true; do
  STATUS=$(curl -s -H "$AUTH_HEADER" "$BASE_URL/jobs/$JOB_ID" | jq -r .status)
  echo "Status: $STATUS"

  if [ "$STATUS" != "running" ]; then
    break
  fi

  sleep 5
done

# Get final output
curl -s -H "$AUTH_HEADER" "$BASE_URL/jobs/$JOB_ID" | jq .stdout -r
```

## Troubleshooting

### Server won't start

```bash
# Check if port is already in use
lsof -i :8081

# Check .env.local exists
ls -la .env.local

# Test manually
python3 scripts/remote-control.py
```

### 401 Unauthorized

```bash
# Verify auth key is set
echo $REMOTE_CONTROL_KEY

# Check server logs for the actual key
grep "Auth key:" logs/remote-control.log
```

### Jobs not completing

```bash
# Check job status
curl -H "X-Auth-Key: $REMOTE_CONTROL_KEY" http://localhost:8081/jobs

# Check for zombie processes
ps aux | grep python

# Check VM resources
free -h
df -h
```

## Monitoring

### Health Check Script

```bash
#!/bin/bash
# Check if remote control server is alive

source .env.local

RESPONSE=$(curl -s -w "\n%{http_code}" -H "X-Auth-Key: $REMOTE_CONTROL_KEY" \
  http://localhost:8081/status)

HTTP_CODE=$(echo "$RESPONSE" | tail -n 1)

if [ "$HTTP_CODE" = "200" ]; then
  echo "OK - Remote Control Server is healthy"
  exit 0
else
  echo "CRITICAL - Remote Control Server returned $HTTP_CODE"
  exit 2
fi
```

### Dashboard Integration

Add to your monitoring dashboard:

```bash
# Endpoint: /api/remote-control/status
curl -H "X-Auth-Key: $REMOTE_CONTROL_KEY" http://localhost:8081/status
```

## Performance

- **Latency**: < 50ms for /status checks
- **Concurrency**: HTTP server handles one request at a time (sequential)
- **Job Limit**: No hard limit, but monitor VM RAM usage
- **Log Rotation**: Implement logrotate for `logs/remote-control.jsonl`

## Future Enhancements

Potential improvements:

1. **Multi-threaded server** - Use ThreadingHTTPServer for concurrent requests
2. **Job cleanup** - Auto-remove old completed jobs after N days
3. **Webhook notifications** - POST to external URL when jobs complete
4. **Job cancellation** - DELETE /jobs/<id> to kill running jobs
5. **Metrics** - Prometheus /metrics endpoint
6. **WebSocket** - Real-time job output streaming
7. **Authentication levels** - Read-only vs admin keys

## Support

For issues or questions:

1. Check `logs/remote-control.jsonl` for detailed event log
2. Review HTTP server logs in stdout/stderr
3. Test with `scripts/test-remote-control.sh`
4. Verify all required scripts exist and are executable

---

**Last updated**: 2026-02-27T19:00:00Z
