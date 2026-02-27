# Smart Autofix — Usage Guide

> Last updated: 2026-02-27T19:30:00Z

## Overview

`smart-autofix.py` is an intelligent pipeline repair system that automatically:
1. Detects pipeline failures via webhook health checks
2. Finds the best golden snapshot using a scoring algorithm
3. Applies the golden workflow via n8n REST API
4. Re-tests with quick-test.py to validate the fix
5. Logs results to JSONL and Supabase

## Scoring Algorithm

The script scores each golden snapshot candidate using this formula:

```
score = accuracy_historical × (1 / max(1, days_since_success)) × model_match_factor

where:
  - accuracy_historical: Best accuracy from docs/data.json or Supabase
  - days_since_success: Age of the snapshot (more recent = higher score)
  - model_match_factor: 1.0 if same model, 0.8 if different model
```

This prioritizes:
- **Recent** snapshots over old ones
- **High-accuracy** configurations over low-accuracy
- **Same model** over different model (to avoid model swap issues)

## CLI Usage

### Fix a single pipeline (dry-run)
```bash
source .env.local
python3 scripts/smart-autofix.py --pipeline standard --dry-run
```

### Fix a single pipeline (live)
```bash
source .env.local
python3 scripts/smart-autofix.py --pipeline standard
```

### Fix all broken pipelines (dry-run)
```bash
source .env.local
python3 scripts/smart-autofix.py --all --dry-run
```

### Fix all broken pipelines (live)
```bash
source .env.local
python3 scripts/smart-autofix.py --all
```

### Advanced options
```bash
# Use a specific HF Space
python3 scripts/smart-autofix.py --pipeline graph --space https://my-space.hf.space

# Try up to 5 golden snapshots before giving up
python3 scripts/smart-autofix.py --pipeline orchestrator --max-attempts 5
```

## Importable Module

The script can also be used as a Python module:

```python
import sys
import importlib.util

# Load the module
spec = importlib.util.spec_from_file_location(
    'smart_autofix',
    '/home/termius/mon-ipad/scripts/smart-autofix.py'
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# Check pipeline health
health = mod.check_pipeline_health(
    'https://lbjlincoln-nomos-rag-engine.hf.space',
    'standard'
)
print(f"Healthy: {health['healthy']}")
print(f"Error type: {health['error_type']}")

# Find best golden snapshot
best = mod.find_best_golden('standard')
if best:
    print(f"Best golden: {best['path'].name}")
    print(f"Score: {best['score']:.4f}")

# Run autofix (with authenticated client)
client = mod.N8nClient('https://lbjlincoln-nomos-rag-engine.hf.space')
client.login()

result = mod.autofix_pipeline(
    client,
    'standard',
    dry_run=False,
    max_attempts=3,
)

print(f"Fixed: {result['fixed']}")
print(f"Details: {result['details']}")
```

## Integration with Other Scripts

### With decision-engine.py
```bash
# Check if revert is needed
decision=$(python3 scripts/decision-engine.py --pipeline standard --quiet)
action=$(echo "$decision" | jq -r '.decision')

if [ "$action" = "REVERT" ]; then
    # Auto-revert with smart-autofix
    python3 scripts/smart-autofix.py --pipeline standard
fi
```

### With webhook-health-monitor.py
```bash
# Run health check
health=$(python3 scripts/webhook-health-monitor.py --once --json)
down=$(echo "$health" | jq -r '.summary.down')

if [ "$down" -gt 0 ]; then
    # Auto-fix broken pipelines
    python3 scripts/smart-autofix.py --all
fi
```

### In nohup background automation
```bash
# Daemon mode: check every 5 minutes, auto-fix if needed
nohup bash -c '
while true; do
    source .env.local
    health=$(python3 scripts/webhook-health-monitor.py --once --json 2>/dev/null)
    down=$(echo "$health" | jq -r ".summary.down" 2>/dev/null || echo 0)

    if [ "$down" -gt 0 ]; then
        echo "[$(date -Iseconds)] Detected $down broken pipelines, attempting autofix..."
        python3 scripts/smart-autofix.py --all 2>&1
    else
        echo "[$(date -Iseconds)] All pipelines healthy"
    fi

    sleep 300  # 5 minutes
done
' > logs/auto-healing.log 2>&1 &

echo $! > logs/auto-healing.pid
```

## Exit Codes

- `0`: All pipelines fixed successfully (or already healthy)
- `1`: Some pipelines failed to fix
- `2`: All pipelines failed to fix

## Logs

### JSONL log
All autofix attempts are logged to `logs/smart-autofix.jsonl`:

```json
{
  "pipeline": "standard",
  "fixed": true,
  "error_type": "404",
  "attempts": 2,
  "golden_path": "/home/termius/mon-ipad/snapshot/working-session60/standard.json",
  "golden_score": 0.856,
  "accuracy_before": 0.0,
  "accuracy_after": 88.0,
  "details": "Fixed with standard.json (accuracy: 88.0%)",
  "timestamp": "2026-02-27T19:30:00Z"
}
```

### Supabase logs
Results are also written to:
- `trading_board_snapshots` table (snapshot tracking)
- `bug_signatures` table (if error patterns are detected)

## Error Type Handling

| Error Type | Action | Notes |
|------------|--------|-------|
| `429` | Skip (use auto-model-swap.py) | Rate-limit requires model change |
| `404` | Apply golden | Webhook not registered |
| `timeout` | Apply golden | Workflow taking too long |
| `empty` | Apply golden | Empty response body |
| `auth` | Apply golden | Auth error in workflow |
| `http_error` | Apply golden | Other HTTP errors |
| `network` | Apply golden | Network/connection issues |

## Snapshot Discovery

The script searches these locations (in order):
1. `snapshot/working-session*` (highest number first)
2. `snapshot/current`
3. `snapshot/auto-backup`
4. `snapshot/model-swap-backups`
5. `hf-space/n8n-workflows`

## Best Practices

1. **Always dry-run first** to see what would happen
2. **Run health check first** to identify broken pipelines
3. **Check logs** after each fix attempt
4. **Validate with eval** after successful fix:
   ```bash
   python3 scripts/smart-autofix.py --pipeline standard
   python3 eval/quick-test.py --pipeline standard --questions 10
   python3 eval/golden-check.py --pipeline standard
   ```
4. **Monitor Supabase** for autofix trends and patterns

## Troubleshooting

### No golden snapshots found
- Check that workflow JSONs exist in snapshot directories
- Verify snapshot naming matches PIPELINES config
- Run `python3 n8n/sync.py` to create current snapshots

### All golden attempts failed
- Check n8n logs for errors
- Verify OpenRouter API keys are valid
- Check if models are rate-limited (use auto-model-swap.py)
- Review workflow-diff-engine.py output

### Autofix succeeds but tests still fail
- The golden may be outdated
- Data sources (Pinecone, Neo4j, Supabase) may be stale
- Check if ingestion workflows need to run
- Verify embeddings are up to date

### Authentication failures
- Check N8N_HOST is correct
- Verify login credentials (LOGIN_EMAIL, LOGIN_PASSWORD)
- Check HF Space is running and accessible

## See Also

- `scripts/decision-engine.py` — KEEP/REVERT/HOLD decisions
- `scripts/auto-revert.py` — Manual golden revert
- `scripts/auto-model-swap.py` — Rate-limit model swapping
- `scripts/webhook-health-monitor.py` — Health monitoring
- `eval/golden-check.py` — Golden threshold validation
- `technicals/debug/fixes-library.md` — Fix patterns library
