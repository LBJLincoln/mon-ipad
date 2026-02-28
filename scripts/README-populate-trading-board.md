# populate-trading-board.py — Usage Guide

## Overview

This script extracts pipeline metrics from evaluation results and writes them to the Supabase `trading_board_snapshots` table, powering the live trading board UI.

## Quick Start

```bash
# Basic usage (reads from docs/data.json)
source .env.local
python3 scripts/populate-trading-board.py

# Preview what would be written (dry-run)
python3 scripts/populate-trading-board.py --dry-run

# Verbose output showing all details
python3 scripts/populate-trading-board.py --dry-run --verbose
```

## Integration with Eval Pipeline

### After running iterative-eval

```bash
source .env.local

# Run evaluation
python3 eval/iterative-eval.py --label "Phase2-batch1" --max 50

# Populate trading board with results
python3 scripts/populate-trading-board.py
```

### After decision engine

```bash
source .env.local

# Get decision from decision engine
DECISION=$(python3 scripts/decision-engine.py --pipeline standard --quiet | jq -r '.decision')

# Populate trading board with decision tracking
python3 scripts/populate-trading-board.py \
  --last-decision "$DECISION" \
  --last-decision-pipeline standard
```

### From custom results file

```bash
# Use specific results file instead of data.json
python3 scripts/populate-trading-board.py \
  --results-file logs/iterative-eval/iterative-20260227-1434.json
```

## Command-Line Options

| Flag | Description | Example |
|------|-------------|---------|
| `--results-file`, `-r` | Path to results JSON | `--results-file logs/iterative-eval/latest.json` |
| `--dry-run` | Preview without writing to Supabase | `--dry-run` |
| `--verbose`, `-v` | Show detailed output | `--verbose` |
| `--last-decision` | Track decision (KEEP/REVERT/HOLD) | `--last-decision KEEP` |
| `--last-decision-pipeline` | Pipeline for decision | `--last-decision-pipeline standard` |

## Data Sources

The script extracts metrics from multiple sources (in priority order):

1. **Iterative eval results** (`pipelines` key) — most detailed
2. **Latest iterations** (`iterations[].results_summary`) — recent performance
3. **Quick tests** (`quick_tests`) — fallback for smoke tests

### Metrics Extracted

For each pipeline:
- **Accuracy** (%)
- **Latency P95** (ms)
- **Error rate** (%)
- **Total tested** (last 24h)

### Overall Calculations

- **Best pipeline**: Highest accuracy
- **Worst pipeline**: Lowest accuracy
- **Overall accuracy**: Weighted by test count
- **Active alerts**: Critical issues detected

## Supabase Tables

### trading_board_snapshots

Each row represents a snapshot of all pipeline metrics:

```json
{
  "best_pipeline": "standard",
  "best_accuracy": 85.5,
  "best_latency_p95": 3200,
  "best_since": "2026-02-27T12:00:00Z",

  "worst_pipeline": "graph",
  "worst_accuracy": 72.0,
  "worst_latency_p95": 8500,
  "worst_since": "2026-02-27T12:00:00Z",

  "middle_pipelines": [
    {"pipeline": "quantitative", "accuracy": 88.0, "latency_p95": 4500}
  ],

  "total_tests_24h": 1500,
  "overall_accuracy": 82.3,

  "active_alerts_count": 2,
  "last_decision": "KEEP",
  "last_decision_pipeline": "standard",
  "last_decision_at": "2026-02-27T12:00:00Z",

  "alert_feed": [
    {
      "severity": "critical",
      "message": "Accuracy 72.0% < 90% of golden (76.5%)",
      "pipeline": "graph",
      "timestamp": "2026-02-27T12:00:00Z"
    }
  ]
}
```

### bug_signatures

Detected errors and anomalies:

```json
{
  "signature_id": "accuracy-regression-graph-1772221107",
  "pipeline": "graph",
  "source": "golden-check",
  "detected_at": "2026-02-27T12:00:00Z",
  "execution_id": null,
  "error_snippet": "Accuracy 72.0% < 90% of golden (76.5%)",
  "metadata": {
    "accuracy": 72.0,
    "golden_threshold": 85.0,
    "regression_severity": "critical"
  },
  "acknowledged": false,
  "auto_action_taken": "REVERT recommended",
  "fix_applied": null
}
```

## Error Detection

The script automatically detects and records:

1. **High error rates** (>20%)
2. **Accuracy regressions** (<90% of golden threshold)
3. **Iteration errors** (from recent iterations)

All detected issues are written to `bug_signatures` table with severity levels.

## Example Output

### Dry-run mode

```
Loading metrics from: /home/termius/mon-ipad/docs/data.json
Extracting pipeline metrics...
Calculating overall rankings...
Scanning for errors and bugs...

Writing snapshot to Supabase...
DRY RUN: Would write to trading_board_snapshots:
{
  "best_pipeline": "standard",
  "best_accuracy": 85.5,
  ...
}

Writing 2 bug signatures to Supabase...

DRY RUN: Would write 2 bug signatures:
  - accuracy-regression-graph-1772221107: Accuracy 72.0% < 90% of golden (76.5%)
  - high-error-rate-orchestrator-1772221107: Error rate 25.0% exceeds threshold
```

### Normal mode

```
Loading metrics...

✓ Trading board populated successfully.
  Best: standard (85.5%)
  Worst: graph (72.0%)
  Overall: 82.3% (1500 tests)
  Alerts: 2
```

## Automation

### Cron job (hourly)

```bash
# /etc/cron.d/populate-trading-board
0 * * * * termius cd /home/termius/mon-ipad && source .env.local && python3 scripts/populate-trading-board.py >> logs/trading-board.log 2>&1
```

### GitHub Actions (after eval)

```yaml
- name: Run evaluation
  run: |
    source .env.local
    python3 eval/iterative-eval.py --label "CI-${{ github.run_number }}"

- name: Populate trading board
  run: |
    source .env.local
    python3 scripts/populate-trading-board.py
```

### Post-commit hook

```bash
#!/bin/bash
# .git/hooks/post-commit

# Only run on main branch after eval results update
if git diff-tree --no-commit-id --name-only -r HEAD | grep -q "docs/data.json"; then
  source .env.local
  python3 scripts/populate-trading-board.py
fi
```

## Requirements

- **Python 3.7+** (no external dependencies, uses stdlib only)
- **Supabase credentials** in `.env.local`:
  - `SUPABASE_URL`
  - `SUPABASE_API_KEY`
- **Data source**: `docs/data.json` or custom results file

## Troubleshooting

### "SUPABASE_URL and SUPABASE_API_KEY required"

Ensure `.env.local` contains:
```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_API_KEY=your-api-key
```

### "No pipeline metrics found"

The data file is empty or malformed. Verify:
```bash
python3 -c "import json; print(json.load(open('docs/data.json')).keys())"
```

### HTTP 404 or 401 from Supabase

Check table exists and API key has permissions:
```bash
# Test connection
curl -X GET \
  "https://$SUPABASE_URL/rest/v1/trading_board_snapshots?limit=1" \
  -H "apikey: $SUPABASE_API_KEY" \
  -H "Authorization: Bearer $SUPABASE_API_KEY"
```

## See Also

- `scripts/decision-engine.py` — KEEP/REVERT/HOLD decisions
- `eval/golden-check.py` — Golden threshold validation
- `eval/iterative-eval.py` — Full evaluation pipeline
- `technicals/automation/agentic-automation-spec.md` — Automation spec
