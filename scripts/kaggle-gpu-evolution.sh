#!/bin/bash
################################################################################
# Kaggle GPU Evolution Runner — Integrate into autonomous-cycle.sh
#
# Pushes nba_gpu_v2.ipynb to Kaggle, waits for completion, downloads results.
#
# Usage:
#   bash scripts/kaggle-gpu-evolution.sh [--dry-run] [--no-wait]
#
# Environment vars (optional):
#   KAGGLE_USERNAME — default: read from ~/.kaggle/kaggle.json
#   KAGGLE_KERNEL_SLUG — default: nba-quant-gpu-v2
#   TIMEOUT_MINUTES — default: 180
#
################################################################################

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# Defaults
KAGGLE_KERNEL_SLUG="${KAGGLE_KERNEL_SLUG:-nba-quant-gpu-v2}"
TIMEOUT_MINUTES="${TIMEOUT_MINUTES:-180}"
DRY_RUN=false
NO_WAIT=false
LOG_FILE="${REPO_ROOT}/data/agent-activity.json"

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --no-wait)
            NO_WAIT=true
            shift
            ;;
        *)
            echo "Unknown arg: $1"
            exit 1
            ;;
    esac
done

log() {
    local level="$1"
    shift
    local msg="$*"
    local ts=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$ts] [$level] $msg" | tee -a "${LOG_FILE}"
}

# Check Kaggle CLI
if ! command -v kaggle &>/dev/null; then
    log WARN "kaggle CLI not found. Installing..."
    pip install kaggle || {
        log ERROR "Failed to install kaggle"
        exit 1
    }
fi

# Read username from kaggle.json
if [ -z "$KAGGLE_USERNAME" ]; then
    KAGGLE_JSON="$HOME/.kaggle/kaggle.json"
    if [ ! -f "$KAGGLE_JSON" ]; then
        log ERROR "~/.kaggle/kaggle.json not found. Set KAGGLE_USERNAME env var."
        exit 1
    fi
    KAGGLE_USERNAME=$(python3 -c "import json; print(json.load(open('$KAGGLE_JSON'))['username'])" 2>/dev/null) || {
        log ERROR "Could not parse KAGGLE_USERNAME from $KAGGLE_JSON"
        exit 1
    }
fi

log INFO "Kaggle GPU Evolution Runner"
log INFO "Username: $KAGGLE_USERNAME"
log INFO "Kernel: $KAGGLE_KERNEL_SLUG"
log INFO "Timeout: ${TIMEOUT_MINUTES}m"

# Check notebook exists
NOTEBOOK="${REPO_ROOT}/nomos-nba-agent/colab/nba_gpu_v2.ipynb"
if [ ! -f "$NOTEBOOK" ]; then
    NOTEBOOK="${REPO_ROOT}/colab/nba_gpu_v2.ipynb"
fi

if [ ! -f "$NOTEBOOK" ]; then
    log ERROR "Notebook not found: $NOTEBOOK"
    exit 1
fi

log INFO "Notebook: $NOTEBOOK"

# Check if already running
STATUS_OUTPUT=$(kaggle kernels status "$KAGGLE_USERNAME/$KAGGLE_KERNEL_SLUG" 2>&1) || true
if echo "$STATUS_OUTPUT" | grep -qi "running"; then
    log WARN "Kernel already running, skipping push"
    ALREADY_RUNNING=true
else
    ALREADY_RUNNING=false
fi

# Push (if not running)
if [ "$ALREADY_RUNNING" = false ]; then
    log INFO "Pushing kernel..."

    if [ "$DRY_RUN" = true ]; then
        log INFO "[DRY RUN] Would push: python3 $SCRIPT_DIR/kaggle_kernel_manager.py --username $KAGGLE_USERNAME --kernel-slug $KAGGLE_KERNEL_SLUG --notebook $NOTEBOOK --kernel-timeout-seconds 7200"
    else
        # Activate venv if available
        if [ -f "${REPO_ROOT}/venv/bin/activate" ]; then
            source "${REPO_ROOT}/venv/bin/activate"
        fi

        python3 "$SCRIPT_DIR/kaggle_kernel_manager.py" \
            --username "$KAGGLE_USERNAME" \
            --kernel-slug "$KAGGLE_KERNEL_SLUG" \
            --notebook "$NOTEBOOK" \
            --kernel-timeout-seconds 7200 \
            --no-download \
            || {
                log ERROR "Push failed"
                exit 1
            }

        log INFO "✓ Kernel pushed successfully"
    fi
else
    log INFO "Kernel already running, will monitor status"
fi

# Wait for completion
if [ "$NO_WAIT" = true ]; then
    log INFO "Skipping wait (--no-wait)"
else
    log INFO "Waiting for completion (up to ${TIMEOUT_MINUTES}m)..."

    if [ "$DRY_RUN" = false ]; then
        python3 "$SCRIPT_DIR/kaggle_kernel_manager.py" \
            --username "$KAGGLE_USERNAME" \
            --kernel-slug "$KAGGLE_KERNEL_SLUG" \
            --wait \
            --timeout-minutes "$TIMEOUT_MINUTES" \
            --output-dir "${REPO_ROOT}/data/kaggle_results" \
            || {
                log ERROR "Kernel execution or download failed"
                exit 1
            }
    fi
fi

log INFO "✓ Kaggle GPU evolution complete"

# Parse and log results (if available)
RESULTS_DIR="${REPO_ROOT}/data/kaggle_results"
if [ -f "$RESULTS_DIR/best_model.json" ]; then
    log INFO "Found best_model.json"
    python3 << 'PYTHON_PARSE'
import json
from pathlib import Path

try:
    best_file = Path("./data/kaggle_results/best_model.json")
    if best_file.exists():
        with open(best_file) as f:
            best = json.load(f)
        print(f"[INFO] Best Brier: {best.get('brier', 'N/A')}")
        print(f"[INFO] Best Model: {best.get('model_type', 'N/A')}")
        print(f"[INFO] Generations: {best.get('gen', 'N/A')}")
except Exception as e:
    print(f"[WARN] Could not parse results: {e}")
PYTHON_PARSE
else
    log WARN "No best_model.json found (may still be running or failed)"
fi

exit 0
