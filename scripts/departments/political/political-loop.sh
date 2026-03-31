#!/bin/bash
# Department: POLITICAL — Karpathy Loop
# Pattern: scan political signals → test new features → measure alpha → keep/revert
# Metric: political_brier, etf_roi, signal_accuracy
set -euo pipefail
DEPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$(dirname "$(dirname "$DEPT_DIR")")")"

POLITICAL_ROOT="/home/termius/nomos-political-alpha"
POLITICAL_BRIER=null
ETF_ROI=null

# Check if political alpha repo exists and has metrics
if [[ -d "$POLITICAL_ROOT" ]]; then
    METRICS_FILE="$POLITICAL_ROOT/data/latest-metrics.json"
    if [[ -f "$METRICS_FILE" ]]; then
        POLITICAL_BRIER=$(python3 -c "import json; d=json.load(open('$METRICS_FILE')); print(d.get('brier_score', 'null'))" 2>/dev/null || echo null)
        ETF_ROI=$(python3 -c "import json; d=json.load(open('$METRICS_FILE')); print(d.get('etf_roi', 'null'))" 2>/dev/null || echo null)
    fi
fi

echo "{\"status\":\"placeholder\",\"department\":\"political\",\"metric\":\"political_brier\",\"political_brier\":$POLITICAL_BRIER,\"etf_roi\":$ETF_ROI,\"signal_accuracy\":null,\"political_repo_exists\":$([ -d "$POLITICAL_ROOT" ] && echo true || echo false),\"improved\":false}"
