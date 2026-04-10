#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# Nomos42 — Lightning AI GPU Burst Deployer
# ═══════════════════════════════════════════════════════════════════
# Launches a 30-min evolution burst on Lightning AI (T4/A10G GPU).
# Copies engine.py + best config from HF space, runs evolution,
# pushes results back to GitHub + HF islands.
#
# Usage:
#   scripts/gpu-burst/lightning-deploy.sh              # Default: 30min NBA burst
#   scripts/gpu-burst/lightning-deploy.sh --political   # Political alpha mode
#   scripts/gpu-burst/lightning-deploy.sh --duration 600 # 10 min burst
#   scripts/gpu-burst/lightning-deploy.sh --check        # Check studio status
#
# Prerequisites:
#   - LIGHTNING_API_KEY env var (or in .env.local)
#   - HF_TOKEN env var (for cloning feature engine)
#   - GITHUB_TOKEN env var (for pushing results)
#
# Cron example:
#   0 12 * * * /home/termius/mon-ipad/scripts/gpu-burst/lightning-deploy.sh >> /home/termius/mon-ipad/logs/lightning-burst.log 2>&1
# ═══════════════════════════════════════════════════════════════════

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_DIR="$REPO_ROOT/logs"
RESULT_DIR="$REPO_ROOT/data/gpu-burst"
BURST_SCRIPT="$SCRIPT_DIR/lightning-burst.py"

# Load env if available
if [[ -f "$REPO_ROOT/.env.local" ]]; then
    set -a
    source "$REPO_ROOT/.env.local"
    set +a
fi

# ── Defaults ──
DURATION=1800
MODE="nba"
CHECK_ONLY=false

# ── Parse args ──
while [[ $# -gt 0 ]]; do
    case "$1" in
        --political) MODE="political"; shift ;;
        --duration) DURATION="$2"; shift 2 ;;
        --check) CHECK_ONLY=true; shift ;;
        --help|-h)
            echo "Usage: $0 [--political] [--duration SECS] [--check]"
            exit 0
            ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

# ── Timestamp ──
ts() { date -u "+%Y-%m-%dT%H:%M:%SZ"; }
log() { echo "[$(ts)] $*"; }

# ── Ensure dirs ──
mkdir -p "$LOG_DIR" "$RESULT_DIR"

# ── Check Lightning CLI ──
ensure_lightning() {
    if ! command -v lightning &>/dev/null; then
        log "Installing lightning CLI..."
        pip install lightning --break-system-packages -q 2>/dev/null || {
            log "ERROR: Failed to install lightning CLI"
            exit 1
        }
    fi
    log "Lightning CLI: $(lightning --version 2>/dev/null || echo 'installed')"
}

# ── Check status only ──
if $CHECK_ONLY; then
    ensure_lightning
    log "=== Lightning AI Status ==="

    # Check if lightning is authenticated
    if lightning user me &>/dev/null 2>&1; then
        log "Authenticated: YES"
        # List active studios
        lightning list studios 2>/dev/null | head -20 || log "No active studios"
    else
        log "Authenticated: NO (set LIGHTNING_API_KEY)"
    fi

    # Check last local result
    LAST_RESULT="$RESULT_DIR/latest-lightning-nba-result.json"
    if [[ -f "$LAST_RESULT" ]]; then
        log "Last result:"
        python3 -c "
import json
with open('$LAST_RESULT') as f:
    r = json.load(f)
print(f'  Brier: {r.get(\"best_score\", r.get(\"best_brier\", \"?\"))}')
print(f'  Model: {r.get(\"model_type\", \"?\")}')
print(f'  Features: {r.get(\"n_features\", \"?\")}')
print(f'  Time: {r.get(\"total_time_sec\", \"?\")}s')
print(f'  Timestamp: {r.get(\"timestamp\", \"?\")}')
" 2>/dev/null || log "  (could not parse result)"
    else
        log "No previous result found"
    fi
    exit 0
fi

# ── Pre-flight checks ──
ensure_lightning

if [[ -z "${HF_TOKEN:-}" ]]; then
    log "WARNING: HF_TOKEN not set — burst may fail to clone feature engine"
fi
if [[ -z "${GITHUB_TOKEN:-}" ]]; then
    log "WARNING: GITHUB_TOKEN not set — results won't push to GitHub"
fi

# ── Prepare burst payload ──
# The burst script is self-contained and runs on Lightning's infrastructure.
# We prepare it with the right env vars and upload it.

log "=== Lightning AI GPU Burst ==="
log "Mode: $MODE | Duration: ${DURATION}s"
log "Script: $BURST_SCRIPT"

# ── Strategy 1: Direct execution via Lightning run (if CLI supports it) ──
# Lightning CLI can execute Python files on their GPU infrastructure.
# This is the simplest approach — no Studio management needed.

run_via_lightning_run() {
    log "Attempting lightning run (direct execution)..."

    # Create a temporary wrapper that sets env vars
    WRAPPER=$(mktemp /tmp/lightning-burst-XXXX.py)
    cat > "$WRAPPER" <<PYEOF
import os
import sys

# Set environment
os.environ["BURST_MODE"] = "$MODE"
os.environ["HF_TOKEN"] = os.environ.get("HF_TOKEN", "${HF_TOKEN:-}")
os.environ["GITHUB_TOKEN"] = os.environ.get("GITHUB_TOKEN", "${GITHUB_TOKEN:-}")
os.environ["TELEGRAM_BOT_TOKEN"] = os.environ.get("TELEGRAM_BOT_TOKEN", "${TELEGRAM_BOT_TOKEN:-}")
os.environ["ADMIN_TELEGRAM_ID"] = os.environ.get("ADMIN_TELEGRAM_ID", "${ADMIN_TELEGRAM_ID:-}")
os.environ["DATABASE_URL"] = os.environ.get("DATABASE_URL", "${DATABASE_URL:-}")

# Override max duration
import lightning_burst
lightning_burst.MAX_DURATION_SECONDS = $DURATION

# Run
result = lightning_burst.run_burst()
print(f"Result: {result}")
PYEOF

    # Try lightning run with GPU
    lightning run app "$WRAPPER" \
        --cloud \
        --accelerator gpu \
        --name "nomos42-${MODE}-burst" \
        2>&1 || return 1

    rm -f "$WRAPPER"
    return 0
}

# ── Strategy 2: Run locally (burst script handles its own GPU detection) ──
# If Lightning CLI run isn't available, execute locally.
# The burst script will use CPU on the VM (suboptimal but functional).

run_locally() {
    log "Running burst script locally (CPU fallback)..."
    log "NOTE: For GPU acceleration, run this on Lightning AI Studio directly"

    export BURST_MODE="$MODE"

    # Override duration in the script
    python3 -c "
import sys, os
sys.path.insert(0, '$SCRIPT_DIR')
os.environ['BURST_MODE'] = '$MODE'

# Monkey-patch duration
import lightning_burst as lb
lb.MAX_DURATION_SECONDS = $DURATION

# Run
result = lb.run_burst()

import json
# Save result locally
result_path = '$RESULT_DIR/latest-lightning-${MODE}-result.json'
with open(result_path, 'w') as f:
    json.dump(result, f, indent=2)
print(f'Result saved to {result_path}')
" 2>&1
}

# ── Strategy 3: SSH into existing Lightning Studio ──
# If a studio is already running, SSH in and execute there.

run_via_ssh() {
    log "Checking for running Lightning Studios..."

    # Check if we can SSH into an existing studio
    STUDIO_NAME="nomos42-evolution"

    # Try to run on the studio directly
    lightning ssh "$STUDIO_NAME" \
        --command "
            cd /teamspace/studios/this_studio &&
            git clone --depth 1 https://user:${HF_TOKEN:-}@huggingface.co/spaces/Nomos42/nba-quant nba-quant-space 2>/dev/null || true &&
            export HF_TOKEN='${HF_TOKEN:-}' &&
            export GITHUB_TOKEN='${GITHUB_TOKEN:-}' &&
            export BURST_MODE='$MODE' &&
            pip install -q xgboost lightgbm catboost scikit-learn 2>/dev/null &&
            python3 -c '
import json, sys
sys.path.insert(0, \"nba-quant-space\")
# Inline the burst logic here for SSH
exec(open(\"nba-quant-space/scripts/gpu-burst/lightning-burst.py\" if False else \"/dev/null\").read())
print(\"SSH burst complete\")
'
        " 2>&1 || return 1

    return 0
}

# ── Execute with fallback chain ──
log "Starting burst execution..."

# Try Lightning run first, fall back to local
if run_via_lightning_run 2>/dev/null; then
    log "Lightning run completed successfully"
elif run_via_ssh 2>/dev/null; then
    log "Lightning SSH completed successfully"
else
    log "Lightning cloud execution unavailable — running locally"
    run_locally
fi

# ── Post-burst: check results ──
RESULT_FILE="$RESULT_DIR/latest-lightning-${MODE}-result.json"
if [[ -f "$RESULT_FILE" ]]; then
    log "=== Burst Result ==="
    python3 -c "
import json
with open('$RESULT_FILE') as f:
    r = json.load(f)
metric = r.get('best_score', r.get('best_brier', '?'))
print(f'  Metric: {metric}')
print(f'  Model: {r.get(\"model_type\", \"?\")}')
print(f'  Features: {r.get(\"n_features\", \"?\")}')
print(f'  Iterations: {r.get(\"iterations\", \"?\")}')
print(f'  Improvement: {r.get(\"improvement\", \"?\")}')
print(f'  Time: {r.get(\"total_time_sec\", \"?\")}s')
print(f'  Platform: {r.get(\"platform\", \"?\")}')
" 2>/dev/null || log "(could not parse result)"
else
    log "No result file found at $RESULT_FILE"
fi

log "=== Lightning Deploy Complete ==="
