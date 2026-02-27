# Remote Control Server — Quick Reference Card

## Setup (One-time)

```bash
# 1. Add auth key to .env.local
echo 'export REMOTE_CONTROL_KEY=your-secure-key-here' >> .env.local
source .env.local

# 2. Start server
python3 scripts/remote-control.py

# Or background mode:
nohup python3 scripts/remote-control.py > logs/remote-control.log 2>&1 &
echo $! > logs/remote-control.pid
```

## API Endpoints (curl)

```bash
# All requests need this header:
AUTH="-H 'X-Auth-Key: $REMOTE_CONTROL_KEY'"

# 1. Get status
curl $AUTH http://localhost:8081/status | jq

# 2. Launch fix
curl $AUTH -X POST http://localhost:8081/fix/standard

# 3. Launch revert
curl $AUTH -X POST http://localhost:8081/revert/graph

# 4. Launch test (10 questions)
curl $AUTH -X POST http://localhost:8081/test/quantitative/10

# 5. List jobs
curl $AUTH http://localhost:8081/jobs | jq

# 6. Get job details
curl $AUTH http://localhost:8081/jobs/test-standard-1 | jq
```

## CLI Client (easier)

```bash
# Status
python3 scripts/remote-control-client.py status

# Test
python3 scripts/remote-control-client.py test standard 5

# Fix
python3 scripts/remote-control-client.py fix graph

# Revert
python3 scripts/remote-control-client.py revert orchestrator

# Jobs
python3 scripts/remote-control-client.py jobs

# Job details
python3 scripts/remote-control-client.py job test-standard-1

# Wait for job
python3 scripts/remote-control-client.py wait test-standard-1
```

## Remote Access (from mobile/external)

```bash
# Setup
export REMOTE_CONTROL_URL=http://34.136.180.66:8081
export REMOTE_CONTROL_KEY=<your-key>

# Use client
python3 scripts/remote-control-client.py status
```

## Server Management

```bash
# Check if running
lsof -i :8081

# View logs
tail -f logs/remote-control.jsonl
tail -f logs/remote-control.log

# Stop
kill $(cat logs/remote-control.pid)

# Restart
kill $(cat logs/remote-control.pid) 2>/dev/null
nohup python3 scripts/remote-control.py > logs/remote-control.log 2>&1 &
echo $! > logs/remote-control.pid
```

## Pipelines

- `standard` — Multi-index RAG
- `graph` — Neo4j knowledge graph
- `quantitative` — Financial analysis
- `orchestrator` — Meta-pipeline

## Files

| File | Purpose |
|------|---------|
| `scripts/remote-control.py` | HTTP server (main) |
| `scripts/remote-control-client.py` | CLI client |
| `scripts/test-remote-control.sh` | Test suite |
| `scripts/REMOTE-CONTROL.md` | Full documentation |
| `docs/remote-control-summary.md` | Implementation summary |
| `logs/remote-control.jsonl` | Event log |
| `logs/remote-control.log` | Server stdout/stderr |
| `logs/remote-control.pid` | Process ID |

## Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 202 | Job accepted (background) |
| 400 | Bad request (invalid pipeline/params) |
| 401 | Unauthorized (missing/invalid key) |
| 404 | Not found (unknown endpoint/job) |
| 500 | Server error |

## Job Status

| Status | Meaning |
|--------|---------|
| `running` | Currently executing |
| `completed` | Finished successfully |
| `failed` | Finished with errors |

## Health Status

| Status | Meaning |
|--------|---------|
| `healthy` | Working normally |
| `degraded` | Slow or short answers |
| `down` | HTTP errors or no response |
| `timeout` | Exceeded timeout threshold |
| `critical` | Multiple pipelines down |

## Troubleshooting

```bash
# Auth issues
echo $REMOTE_CONTROL_KEY
grep "Auth key:" logs/remote-control.log

# Port in use
lsof -i :8081
# Change port: python3 scripts/remote-control.py --port 8082

# Check scripts exist
ls scripts/auto-remediate.py
ls scripts/auto-revert.py
ls eval/quick-test.py

# Test without server
python3 scripts/remote-control.py --help
python3 scripts/remote-control-client.py
```

## Full Docs

See `scripts/REMOTE-CONTROL.md` for complete documentation including:
- API reference with examples
- Production deployment (systemd)
- Security best practices
- Integration examples (Python, JS, Bash)
- Monitoring setup

---

**Port**: 8081 (default)
**Auth**: X-Auth-Key header
**Logs**: logs/remote-control.jsonl
**Docs**: scripts/REMOTE-CONTROL.md
