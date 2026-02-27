# Continuous HF Spaces Monitoring

## Overview

The continuous monitoring system runs as a background daemon and tracks the health of all 10 HF Spaces across 5 RAG pipelines.

## Features

- **Lightweight ping** (every 5 min): Tests 5 webhooks on 3 sample spaces (1 question each)
- **Deep test** (every 15 min): Runs 5 questions per pipeline on primary space
- **Pattern detection**: Identifies rate-limiting, credential issues, empty responses, total outages
- **Live metrics**: Updates `docs/status.json` with real-time monitoring data
- **Detailed logs**: Appends JSON lines to `logs/monitor/YYYY-MM-DD.jsonl`
- **Graceful shutdown**: Handles SIGTERM/SIGINT cleanly

## Quick Start

### Single-run mode (testing)
```bash
source .env.local
python3 scripts/continuous-monitor.py --once
```

### Daemon mode (production)
```bash
# Start
bash scripts/start-monitor.sh

# Check logs
tail -f logs/monitor/daemon.log

# Stop
bash scripts/stop-monitor.sh
```

### Manual daemon (without wrapper)
```bash
source .env.local
nohup python3 scripts/continuous-monitor.py > logs/monitor/daemon.log 2>&1 &
echo $! > logs/monitor/daemon.pid
```

## Monitored Endpoints

| Pipeline | Webhook Path | Field | Test Question |
|----------|-------------|-------|---------------|
| Standard | `/webhook/rag-multi-index-v3` | `query` | What is the capital of Japan? |
| Graph | `/webhook/ff622742-6d71-4e91-af71-b5c666088717` | `query` | What did Marie Curie win Nobel Prizes for? |
| Quantitative | `/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9` | `query` | What was TechVision Inc's total revenue in 2023? |
| Orchestrator | `/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0` | `query` | What is the largest ocean? |
| Chatbot | `/webhook/project-chatbot` | `question` | What is this project about? |

## HF Spaces (10 instances)

1. `https://lbjlincoln-nomos-rag-engine.hf.space` (primary)
2. `https://lbjlincoln26-nomos-rag-engine-2.hf.space`
3. `https://lbjlincoln-nomos-rag-engine-3.hf.space`
4. `https://lbjlincoln26-nomos-rag-engine-4.hf.space`
5. `https://lbjlincoln-nomos-rag-engine-5.hf.space`
6. `https://lbjlincoln26-nomos-rag-engine-6.hf.space`
7. `https://lbjlincoln-nomos-rag-engine-7.hf.space`
8. `https://lbjlincoln26-nomos-rag-engine-8.hf.space`
9. `https://lbjlincoln-nomos-rag-engine-9.hf.space`
10. `https://lbjlincoln26-nomos-rag-engine-10.hf.space`

**Note**: Lightweight ping samples 3 spaces (1, 5, 10) to reduce load. Deep test uses primary space only.

## Log Format

### Lightweight ping
```json
{
  "timestamp": "2026-02-25T14:03:38.335659Z",
  "type": "lightweight_ping",
  "total_tests": 15,
  "ok": 12,
  "empty": 3,
  "errors": 0,
  "timeouts": 0,
  "rate_limit_429": 0,
  "slow_30s": 6,
  "credential_errors": 0,
  "patterns": {
    "rate_limiting": true,
    "credential_issues": false,
    "empty_responses": false,
    "total_outage": false
  },
  "results": [...]
}
```

### Deep test
```json
{
  "timestamp": "2026-02-25T13:57:41.080490Z",
  "type": "deep_test",
  "space": "lbjlincoln-nomos-rag-engine",
  "pipelines": {
    "standard": {
      "tested": 5,
      "ok": 5,
      "accuracy_pct": 100.0,
      "results": [...]
    },
    ...
  }
}
```

## Pattern Detection

| Pattern | Trigger | Meaning |
|---------|---------|---------|
| `rate_limiting` | 429 errors OR >5 responses >30s | OpenRouter rate limits or HF Space overload |
| `credential_issues` | Error contains "credential" | API key expired/invalid |
| `empty_responses` | >20% responses empty | Workflow returning 200 but no answer |
| `total_outage` | 0 OK responses | All spaces down or unreachable |

## Status.json Integration

The monitor updates `docs/status.json` with a new `monitor` section:

```json
{
  "monitor": {
    "last_check": "2026-02-25T14:10:00Z",
    "lightweight_ping": {
      "timestamp": "2026-02-25T14:09:45Z",
      "ok_pct": 80.0,
      "total_tests": 15,
      "ok": 12,
      "patterns": {...}
    },
    "deep_test": {
      "timestamp": "2026-02-25T14:05:00Z",
      "pipelines": {
        "standard": {"accuracy_pct": 100.0, "tested": 5, "ok": 5},
        "graph": {"accuracy_pct": 100.0, "tested": 5, "ok": 5},
        ...
      }
    }
  }
}
```

## Timeouts

- **Lightweight ping**: 60s per webhook (HF Space cold start can take 40s)
- **Deep test**: 90s per question (complex pipelines need more time)
- **Total runtime**:
  - Lightweight: ~5 min (3 spaces × 5 webhooks × 60s timeout + delays)
  - Deep: ~10 min (4 pipelines × 5 questions × 90s timeout + delays)

## Troubleshooting

### All timeouts (30s)
- Old code version with 30s timeout
- Fix: Pull latest version with 60s+ timeouts

### Space #2 shows 404 errors
- Known issue: Space #2 only has 3/14 workflows imported
- Ignore or rebuild Space #2

### Orchestrator shows "empty response body"
- Known issue: Orchestrator returns 200 but empty response
- Debug: Check n8n execution logs

### High rate_limiting pattern
- Standard/Graph pipelines take 35-45s (cold start)
- Not actual rate limiting, just slow LLM calls
- Fix: Increase `slow_30s` threshold to 45s

## Files

- `scripts/continuous-monitor.py` — Main monitoring script (350 lines)
- `scripts/start-monitor.sh` — Daemon starter
- `scripts/stop-monitor.sh` — Daemon stopper
- `logs/monitor/YYYY-MM-DD.jsonl` — Daily log files (append-only)
- `logs/monitor/daemon.log` — Daemon stdout/stderr (if using wrapper)
- `logs/monitor/daemon.pid` — Daemon PID file
- `docs/status.json` — Updated with live metrics

## Integration with Dashboard

The dashboard can read `docs/status.json` to display:
- Last check timestamp
- OK percentage for lightweight ping
- Per-pipeline accuracy from deep test
- Detected patterns (outage, rate-limit, etc.)

Example dashboard snippet:
```javascript
fetch('/docs/status.json')
  .then(r => r.json())
  .then(data => {
    const mon = data.monitor;
    document.getElementById('last-check').textContent = mon.last_check;
    document.getElementById('ok-pct').textContent = mon.lightweight_ping.ok_pct + '%';
    // Show alerts for patterns
    if (mon.lightweight_ping.patterns.total_outage) {
      alert('TOTAL OUTAGE - all spaces down!');
    }
  });
```

## Future Enhancements

- [ ] Slack/email alerts on total_outage or high error rate
- [ ] Prometheus metrics export
- [ ] Historical trend graphs (7-day window)
- [ ] Per-space health scores
- [ ] Auto-restart Space on repeated failures
- [ ] Load balancer integration (route to healthy spaces only)
