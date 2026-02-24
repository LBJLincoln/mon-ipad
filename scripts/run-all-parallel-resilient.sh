#!/bin/bash
# =================================================================
# RESILIENT PARALLEL EVAL — All 5 pipelines, auto-retry, no-stop
# =================================================================
# Runs each pipeline in its own background process with:
# - Auto-retry on failure (up to 3 retries per pipeline)
# - Early-stop on 15 consecutive failures
# - Separate log files per pipeline
# - Auto-commit results every 100 questions
# - Survives session disconnection via nohup
# Last updated: 2026-02-24
# =================================================================

set -o pipefail
cd /home/termius/mon-ipad || exit 1
source .env.local 2>/dev/null

LABEL="phase2-fullrun-$(date +%Y%m%d-%H%M)"
LOG_DIR="logs/parallel-${LABEL}"
mkdir -p "$LOG_DIR"

echo "==================================================================="
echo "  RESILIENT PARALLEL EVAL — $LABEL"
echo "  Started: $(date -Iseconds)"
echo "  Pipelines: standard, graph, quantitative, orchestrator, pme-gateway"
echo "  Log dir: $LOG_DIR"
echo "==================================================================="

# Function: run one pipeline with retry
run_pipeline() {
    local pipe=$1
    local retries=0
    local max_retries=3
    local logfile="${LOG_DIR}/${pipe}.log"
    
    echo "[$(date -Iseconds)] Starting ${pipe} pipeline..." | tee "$logfile"
    
    while [ $retries -lt $max_retries ]; do
        echo "[$(date -Iseconds)] ${pipe}: Attempt $((retries+1))/${max_retries}" | tee -a "$logfile"
        
        python3 eval/run-eval-parallel.py \
            --dataset phase-2 \
            --types "$pipe" \
            --max 1000 \
            --batch-size 0 \
            --force \
            --early-stop 15 \
            --label "${LABEL}-${pipe}" \
            2>&1 | tee -a "$logfile"
        
        EXIT_CODE=${PIPESTATUS[0]}
        
        if [ $EXIT_CODE -eq 0 ]; then
            echo "[$(date -Iseconds)] ${pipe}: COMPLETED SUCCESSFULLY" | tee -a "$logfile"
            break
        else
            retries=$((retries + 1))
            echo "[$(date -Iseconds)] ${pipe}: FAILED (exit $EXIT_CODE), retry $retries/$max_retries" | tee -a "$logfile"
            if [ $retries -lt $max_retries ]; then
                echo "[$(date -Iseconds)] ${pipe}: Waiting 30s before retry..." | tee -a "$logfile"
                sleep 30
            fi
        fi
    done
    
    if [ $retries -ge $max_retries ]; then
        echo "[$(date -Iseconds)] ${pipe}: ALL RETRIES EXHAUSTED" | tee -a "$logfile"
    fi
    
    # Auto-commit results
    echo "[$(date -Iseconds)] ${pipe}: Auto-committing results..." | tee -a "$logfile"
    git add logs/ docs/ 2>/dev/null
    git diff --cached --quiet || git commit -m "eval: ${pipe} ${LABEL} auto-results [skip ci]" 2>/dev/null
}

# Launch all 5 pipelines in parallel
PIDS=()
for pipe in standard graph quantitative orchestrator pme-gateway; do
    run_pipeline "$pipe" &
    PIDS+=($!)
    echo "  Launched ${pipe} (PID $!)"
    sleep 2  # Stagger starts by 2s to avoid initial burst
done

echo ""
echo "All 5 pipelines launched. PIDs: ${PIDS[*]}"
echo "Monitoring..."

# Wait for all to finish
FAILED=0
for i in "${!PIDS[@]}"; do
    wait ${PIDS[$i]}
    if [ $? -ne 0 ]; then
        FAILED=$((FAILED + 1))
    fi
done

echo ""
echo "==================================================================="
echo "  ALL PIPELINES FINISHED — $(date -Iseconds)"
echo "  Failed: $FAILED / 5"
echo "==================================================================="

# Final commit + push
git add logs/ docs/ 2>/dev/null
git diff --cached --quiet || git commit -m "eval: phase2 fullrun ${LABEL} — all 5 pipelines complete [skip ci]"
git push origin main 2>/dev/null || echo "Push failed (will retry next session)"

echo "Done."
