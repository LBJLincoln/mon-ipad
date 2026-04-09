#!/bin/bash
################################################################################
# Research Department Agent — OpenCode + Fallback
# Scans for NBA prediction research, ML techniques, calibration advances
# Output: data/opencode/research-latest.json
# Schedule: Every 6 hours (via install-crons.sh)
################################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

DEPT="research"
OUTPUT_FILE="$DATA_DIR/research-latest.json"

log "$DEPT" "Starting research scan..."

# Build the prompt with current context
PROMPT=$(cat <<'PROMPT_END'
You are the Research Department AI for Nomos42, an NBA prediction system.

Your task: Identify the most promising recent advances in sports prediction and ML that could improve our NBA game outcome predictions.

Current system status:
- Best Brier score: 0.21570 (TabICL neural model on GPU)
- Walk-forward Brier: 0.22447 (tree ensemble on CPU)
- Target: Brier < 0.20
- Engine: 200 features selected from 6253 raw features via genetic algorithm
- Models: XGBoost, LightGBM, CatBoost, ExtraTrees (CPU); TabICL (GPU)
- Known gap: Montrucchio benchmark at 0.199

Analyze and respond with a JSON object containing:
{
  "scan_date": "YYYY-MM-DD",
  "techniques_found": [
    {
      "name": "technique name",
      "source": "paper/repo/blog URL or description",
      "relevance": "high/medium/low",
      "effort": "low/medium/high",
      "expected_impact": "description of potential Brier improvement",
      "implementation_notes": "how to integrate with our system"
    }
  ],
  "feature_ideas": [
    {
      "name": "feature category name",
      "description": "what it captures",
      "data_source": "where to get the data",
      "priority": "high/medium/low"
    }
  ],
  "calibration_insights": [
    "insight about improving calibration"
  ],
  "recommended_next_action": "single most impactful thing to try next"
}

Focus on actionable techniques that work with tree-based ensembles on CPU (our primary constraint). GPU techniques are secondary priority.
PROMPT_END
)

# Try OpenCode first, fallback to direct API
if opencode_available; then
    log "$DEPT" "Using OpenCode ($(${OPENCODE_BIN} --version 2>/dev/null))"

    RAW_OUTPUT=$(run_opencode "$PROMPT" "text" 2>&1) || true

    if [ -n "$RAW_OUTPUT" ] && [ "$RAW_OUTPUT" != "" ]; then
        # Extract JSON from output (OpenCode may wrap it in text)
        JSON_OUTPUT=$(echo "$RAW_OUTPUT" | python3 -c "
import sys, json, re
text = sys.stdin.read()
# Try to find JSON block in output
matches = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
for m in matches:
    try:
        parsed = json.loads(m)
        if 'techniques_found' in parsed or 'scan_date' in parsed:
            print(json.dumps(parsed, indent=2))
            sys.exit(0)
    except:
        continue
# If no structured JSON found, wrap raw output
print(json.dumps({'raw_output': text[:2000], 'parse_note': 'Could not extract structured JSON'}))
" 2>/dev/null)

        write_output "$DEPT" "$JSON_OUTPUT" "$OUTPUT_FILE" "opencode"
        log "$DEPT" "Output written to $OUTPUT_FILE (via OpenCode)"
    else
        log "$DEPT" "OpenCode returned empty output, falling back to API"
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
