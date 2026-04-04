#!/bin/bash
################################################################################
# Evaluation Department Agent — OpenCode + Fallback
# Audits prediction quality, calibration, and systematic biases
# Output: data/opencode/evaluation-latest.json
# Schedule: Every 6 hours, offset 30min (via install-crons.sh)
################################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

DEPT="evaluation"
OUTPUT_FILE="$DATA_DIR/evaluation-latest.json"

log "$DEPT" "Starting evaluation audit..."

# Gather current prediction data for context
EVAL_CONTEXT=""
if [ -f "$REPO_ROOT/data/nba-agent/latest-eval.json" ]; then
    EVAL_CONTEXT=$(python3 -c "
import json
with open('$REPO_ROOT/data/nba-agent/latest-eval.json') as f:
    data = json.load(f)
# Extract key metrics, truncate to avoid huge prompts
summary = {k: v for k, v in data.items() if k in ('brier_score', 'accuracy', 'calibration', 'log_loss', 'games_evaluated', 'date_range', 'model_type', 'roi', 'sharpe')}
print(json.dumps(summary, indent=2)[:1000])
" 2>/dev/null || echo '{"note": "eval data unavailable"}')
fi

QUANT_CONTEXT=""
if [ -f "$REPO_ROOT/data/nba-agent/quant-summary.json" ]; then
    QUANT_CONTEXT=$(python3 -c "
import json
with open('$REPO_ROOT/data/nba-agent/quant-summary.json') as f:
    data = json.load(f)
summary = {k: v for k, v in list(data.items())[:10]}
print(json.dumps(summary, indent=2)[:1000])
" 2>/dev/null || echo '{"note": "quant data unavailable"}')
fi

PROMPT=$(cat <<PROMPT_END
You are the Evaluation Department AI for Nomos42, an NBA prediction system.

Your task: Audit the current prediction quality and identify areas for improvement.

Current evaluation data:
$EVAL_CONTEXT

Quantitative summary:
$QUANT_CONTEXT

System context:
- Best Brier: 0.21570, Walk-forward: 0.22447
- 6 evolution islands running genetic algorithms
- Tree-based models: XGBoost, LightGBM, CatBoost, ExtraTrees
- 200 features selected from 6253 raw (genetic selection)
- Bankroll: started \$100, currently tracking performance

Analyze and respond with a JSON object containing:
{
  "audit_date": "YYYY-MM-DD",
  "overall_health": "green/yellow/red",
  "brier_assessment": {
    "current": 0.0,
    "trend": "improving/stable/degrading",
    "gap_to_target": 0.0,
    "bottleneck": "what is limiting improvement"
  },
  "calibration_issues": [
    {
      "issue": "description",
      "severity": "high/medium/low",
      "affected_games": "description of which predictions are affected",
      "fix_suggestion": "how to address"
    }
  ],
  "bias_detected": [
    {
      "type": "home_bias/recency_bias/favorite_bias/etc",
      "magnitude": "description",
      "evidence": "what data shows this"
    }
  ],
  "model_comparison": {
    "best_performer": "model name",
    "worst_performer": "model name",
    "ensemble_benefit": "description of ensemble vs single model"
  },
  "recommendations": [
    {
      "priority": 1,
      "action": "specific action to take",
      "expected_improvement": "estimated Brier delta"
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
        if 'audit_date' in parsed or 'overall_health' in parsed or 'calibration_issues' in parsed:
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
    run_fallback "$PROMPT" "$OUTPUT_FILE"
    log "$DEPT" "Output written to $OUTPUT_FILE (via API fallback)"
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
