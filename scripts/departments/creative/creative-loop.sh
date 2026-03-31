#!/bin/bash
# Department: CREATIVE (RGWA) — Karpathy Loop
# Pattern: generate art → quality check → curate → publish
# Metric: quality_score, pieces_per_day, diversity_index
set -euo pipefail
DEPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$(dirname "$(dirname "$DEPT_DIR")")")"

RGWA_ROOT="/home/termius/rgwa"
QUALITY_SCORE=null
PIECES_TODAY=0

# Check if RGWA repo exists and has metrics
if [[ -d "$RGWA_ROOT" ]]; then
    METRICS_FILE="$RGWA_ROOT/data/quality-metrics.json"
    if [[ -f "$METRICS_FILE" ]]; then
        QUALITY_SCORE=$(python3 -c "import json; d=json.load(open('$METRICS_FILE')); print(d.get('quality_score', 'null'))" 2>/dev/null || echo null)
        PIECES_TODAY=$(python3 -c "import json; d=json.load(open('$METRICS_FILE')); print(d.get('pieces_today', 0))" 2>/dev/null || echo 0)
    fi
fi

echo "{\"status\":\"placeholder\",\"department\":\"creative\",\"metric\":\"quality_score\",\"quality_score\":$QUALITY_SCORE,\"pieces_today\":$PIECES_TODAY,\"diversity_index\":null,\"rgwa_repo_exists\":$([ -d "$RGWA_ROOT" ] && echo true || echo false),\"improved\":false}"
