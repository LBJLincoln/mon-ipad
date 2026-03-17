#!/bin/bash
# Autonomous Phase 4 eval — runs in background, survives iPad disconnect
# Usage: nohup bash scripts/autonomous-eval.sh >> /tmp/eval-autonomous.log 2>&1 &

set -e
source /home/termius/mon-ipad/.env.local
cd /home/termius/mon-ipad

LOGFILE="/tmp/eval-autonomous.log"
PIPELINES=("standard" "graph" "quantitative")

echo "$(date -Iseconds) === AUTONOMOUS EVAL STARTED ==="

for pipeline in "${PIPELINES[@]}"; do
    echo "$(date -Iseconds) Testing $pipeline pipeline..."
    python3 eval/quick-test.py --questions 5 --pipeline "$pipeline" 2>&1 || echo "WARN: $pipeline test failed"
    echo "$(date -Iseconds) $pipeline done"
    echo "---"
done

echo "$(date -Iseconds) === Quick tests complete. Starting Phase 4 parallel eval ==="

# Run Phase 4 eval in batches (Standard first since it's the best)
python3 eval/run-eval-parallel.py --dataset phase-4 --types standard --batch-size 10 --max 100 --label "auto-s86-std" 2>&1 || echo "WARN: Phase 4 std eval failed"

echo "$(date -Iseconds) === Phase 4 Quant eval ==="
python3 eval/run-eval-parallel.py --dataset phase-4 --types quantitative --batch-size 5 --max 50 --label "auto-s86-quant" 2>&1 || echo "WARN: Phase 4 quant eval failed"

echo "$(date -Iseconds) === AUTONOMOUS EVAL COMPLETE ==="
