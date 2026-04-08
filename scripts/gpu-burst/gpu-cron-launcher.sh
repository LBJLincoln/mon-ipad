#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════
# Nomos42 -- GPU Cron Launcher
# ══════════════════════════════════════════════════════════════════════
# Unified launcher for all GPU compute platforms. Handles:
#   - Environment setup (PATH, tokens from .env.local)
#   - Priority cascade: ZeroGPU (free H200) -> Modal (A10G) -> Lightning (T4)
#   - Proper error handling, timeouts, and logging
#   - Exit code propagation for cron monitoring
#
# Usage:
#   ./gpu-cron-launcher.sh              # Auto: run all platforms in priority order
#   ./gpu-cron-launcher.sh zerogpu      # ZeroGPU only
#   ./gpu-cron-launcher.sh modal        # Modal only
#   ./gpu-cron-launcher.sh lightning    # Lightning only
#   ./gpu-cron-launcher.sh orchestrator # Run the full compute orchestrator
#
# Cron entries (add via crontab -e):
#   # GPU burst every 6h (ZeroGPU cascade)
#   0 0,6,12,18 * * * /home/termius/mon-ipad/scripts/gpu-burst/gpu-cron-launcher.sh >> /home/termius/mon-ipad/logs/gpu-burst/gpu-cron.log 2>&1
#   # Modal daily at 3am (paid, only if critical)
#   0 3 * * * /home/termius/mon-ipad/scripts/gpu-burst/gpu-cron-launcher.sh modal >> /home/termius/mon-ipad/logs/gpu-burst/gpu-cron.log 2>&1
# ══════════════════════════════════════════════════════════════════════

set -euo pipefail

# ── Constants ──
REPO_ROOT="/home/termius/mon-ipad"
SCRIPTS_DIR="${REPO_ROOT}/scripts/gpu-burst"
LOG_DIR="${REPO_ROOT}/logs/gpu-burst"
DATA_DIR="${REPO_ROOT}/data/gpu-burst"
ENV_FILE="${REPO_ROOT}/.env.local"

MAX_TOTAL_TIMEOUT=1800  # 30 minutes max total runtime
ZEROGPU_TIMEOUT=600     # 10 minutes for ZeroGPU
MODAL_TIMEOUT=900       # 15 minutes for Modal
LIGHTNING_TIMEOUT=900   # 15 minutes for Lightning

# ── Setup ──
mkdir -p "${LOG_DIR}" "${DATA_DIR}"

# Ensure ~/.local/bin is in PATH (cron has minimal PATH)
export PATH="/home/termius/.local/bin:${HOME}/.local/bin:/usr/local/bin:/usr/bin:/bin:${PATH}"

# Load environment variables from .env.local
if [[ -f "${ENV_FILE}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${ENV_FILE}"
    set +a
fi

# ── Logging ──
ts() {
    date -u +"%Y-%m-%dT%H:%M:%S%z"
}

log() {
    echo "[$(ts)] [INFO] $*"
}

log_warn() {
    echo "[$(ts)] [WARN] $*"
}

log_error() {
    echo "[$(ts)] [ERROR] $*"
}

log_section() {
    echo ""
    echo "[$(ts)] ════════════════════════════════════════════════════════════"
    echo "[$(ts)] $*"
    echo "[$(ts)] ════════════════════════════════════════════════════════════"
}

# ── State tracking ──
OVERALL_START=$(date +%s)
IMPROVED=0
PLATFORMS_TRIED=0
PLATFORMS_SUCCEEDED=0
BEST_BRIER_BEFORE=""
BEST_BRIER_AFTER=""

check_timeout() {
    local now
    now=$(date +%s)
    local elapsed=$(( now - OVERALL_START ))
    if (( elapsed >= MAX_TOTAL_TIMEOUT )); then
        log_warn "Total timeout reached (${elapsed}s >= ${MAX_TOTAL_TIMEOUT}s) -- stopping"
        return 1
    fi
    return 0
}

# Read current best Brier from local files
get_current_best() {
    local best="0.99999"

    # Check karpathy best config
    local karpathy_file="${REPO_ROOT}/data/karpathy/nba-best-config.json"
    if [[ -f "${karpathy_file}" ]]; then
        local kb
        kb=$(python3 -c "import json; d=json.load(open('${karpathy_file}')); print(d.get('best_brier', 1.0))" 2>/dev/null || echo "1.0")
        if python3 -c "exit(0 if float('${kb}') < float('${best}') else 1)" 2>/dev/null; then
            best="${kb}"
        fi
    fi

    # Check ZeroGPU result
    local zgpu_file="${DATA_DIR}/latest-zerogpu-result.json"
    if [[ -f "${zgpu_file}" ]]; then
        local zb
        zb=$(python3 -c "import json; d=json.load(open('${zgpu_file}')); print(d.get('best_brier_found', d.get('best_brier', 1.0)))" 2>/dev/null || echo "1.0")
        if python3 -c "exit(0 if float('${zb}') < float('${best}') else 1)" 2>/dev/null; then
            best="${zb}"
        fi
    fi

    # Check Modal result
    local modal_file="${DATA_DIR}/latest-modal-result.json"
    if [[ -f "${modal_file}" ]]; then
        local mb
        mb=$(python3 -c "import json; d=json.load(open('${modal_file}')); print(d.get('best_brier', 1.0))" 2>/dev/null || echo "1.0")
        if python3 -c "exit(0 if float('${mb}') < float('${best}') else 1)" 2>/dev/null; then
            best="${mb}"
        fi
    fi

    echo "${best}"
}

# ── Platform runners ──

run_zerogpu() {
    log_section "ZEROGPU BURST (free H200, 3 accounts)"
    PLATFORMS_TRIED=$(( PLATFORMS_TRIED + 1 ))

    # Verify tokens
    local has_token=0
    [[ -n "${HF_TOKEN:-}" ]] && has_token=1
    [[ -n "${HF_TOKEN_2:-}" ]] && has_token=1
    [[ -n "${HF_TOKEN_3:-}" ]] && has_token=1

    if (( has_token == 0 )); then
        log_error "No HF tokens available (HF_TOKEN, HF_TOKEN_2, HF_TOKEN_3)"
        log_error "Check ${ENV_FILE} has these tokens set"
        return 1
    fi

    local token_status=""
    [[ -n "${HF_TOKEN:-}" ]] && token_status+="HF_TOKEN=SET "
    [[ -n "${HF_TOKEN_2:-}" ]] && token_status+="HF_TOKEN_2=SET "
    [[ -n "${HF_TOKEN_3:-}" ]] && token_status+="HF_TOKEN_3=SET "
    log "Tokens: ${token_status}"

    local script="${SCRIPTS_DIR}/zerogpu-burst.py"
    if [[ ! -f "${script}" ]]; then
        log_error "Script not found: ${script}"
        return 1
    fi

    log "Running: python3 ${script} --account all (timeout: ${ZEROGPU_TIMEOUT}s)"
    local start_time
    start_time=$(date +%s)

    if timeout "${ZEROGPU_TIMEOUT}" python3 "${script}" --account all; then
        local elapsed=$(( $(date +%s) - start_time ))
        log "ZeroGPU completed successfully in ${elapsed}s"
        PLATFORMS_SUCCEEDED=$(( PLATFORMS_SUCCEEDED + 1 ))
        return 0
    else
        local exit_code=$?
        local elapsed=$(( $(date +%s) - start_time ))
        if (( exit_code == 124 )); then
            log_warn "ZeroGPU timed out after ${ZEROGPU_TIMEOUT}s"
        else
            log_warn "ZeroGPU exited with code ${exit_code} after ${elapsed}s"
        fi
        return "${exit_code}"
    fi
}

run_modal() {
    log_section "MODAL BURST (A10G GPU, paid ~\$0.18/burst)"
    PLATFORMS_TRIED=$(( PLATFORMS_TRIED + 1 ))

    # Check modal CLI
    if ! command -v modal &>/dev/null; then
        log_error "Modal CLI not found in PATH"
        log_error "PATH=${PATH}"
        return 1
    fi

    # Check modal authentication
    if ! modal profile current &>/dev/null; then
        log_warn "Modal not authenticated -- attempting token auth"
        if [[ -n "${MODAL_TOKEN_ID:-}" && -n "${MODAL_TOKEN_SECRET:-}" ]]; then
            modal token set --token-id "${MODAL_TOKEN_ID}" --token-secret "${MODAL_TOKEN_SECRET}" 2>/dev/null || true
        else
            log_error "No MODAL_TOKEN_ID/MODAL_TOKEN_SECRET in environment"
            log_error "Authenticate with: modal token set --token-id <id> --token-secret <secret>"
            return 1
        fi
    fi

    local script="${SCRIPTS_DIR}/modal-burst.py"
    if [[ ! -f "${script}" ]]; then
        log_error "Script not found: ${script}"
        return 1
    fi

    log "Running: modal run ${script} (timeout: ${MODAL_TIMEOUT}s)"
    local start_time
    start_time=$(date +%s)

    if timeout "${MODAL_TIMEOUT}" modal run "${script}" --timeout 600; then
        local elapsed=$(( $(date +%s) - start_time ))
        log "Modal completed successfully in ${elapsed}s"
        PLATFORMS_SUCCEEDED=$(( PLATFORMS_SUCCEEDED + 1 ))
        return 0
    else
        local exit_code=$?
        local elapsed=$(( $(date +%s) - start_time ))
        if (( exit_code == 124 )); then
            log_warn "Modal timed out after ${MODAL_TIMEOUT}s"
        else
            log_warn "Modal exited with code ${exit_code} after ${elapsed}s"
        fi
        return "${exit_code}"
    fi
}

run_lightning() {
    log_section "LIGHTNING BURST (T4/A10G GPU, free tier)"
    PLATFORMS_TRIED=$(( PLATFORMS_TRIED + 1 ))

    # Check lightning CLI
    if ! command -v lightning &>/dev/null; then
        log_error "Lightning CLI not found in PATH"
        return 1
    fi

    local script="${SCRIPTS_DIR}/lightning-deploy.sh"
    if [[ ! -f "${script}" ]]; then
        # Try the Python burst script directly
        script="${SCRIPTS_DIR}/lightning-burst.py"
        if [[ ! -f "${script}" ]]; then
            log_error "No lightning script found (tried lightning-deploy.sh and lightning-burst.py)"
            return 1
        fi
    fi

    log "Running: bash ${script} (timeout: ${LIGHTNING_TIMEOUT}s)"
    local start_time
    start_time=$(date +%s)

    if timeout "${LIGHTNING_TIMEOUT}" bash "${script}"; then
        local elapsed=$(( $(date +%s) - start_time ))
        log "Lightning completed successfully in ${elapsed}s"
        PLATFORMS_SUCCEEDED=$(( PLATFORMS_SUCCEEDED + 1 ))
        return 0
    else
        local exit_code=$?
        local elapsed=$(( $(date +%s) - start_time ))
        if (( exit_code == 124 )); then
            log_warn "Lightning timed out after ${LIGHTNING_TIMEOUT}s"
        else
            log_warn "Lightning exited with code ${exit_code} after ${elapsed}s"
        fi
        return "${exit_code}"
    fi
}

run_orchestrator() {
    log_section "COMPUTE ORCHESTRATOR (full auto-dispatch)"
    PLATFORMS_TRIED=$(( PLATFORMS_TRIED + 1 ))

    local script="${SCRIPTS_DIR}/compute-orchestrator.py"
    if [[ ! -f "${script}" ]]; then
        log_error "Script not found: ${script}"
        return 1
    fi

    log "Running: python3 ${script} (timeout: ${MAX_TOTAL_TIMEOUT}s)"
    local start_time
    start_time=$(date +%s)

    if timeout "${MAX_TOTAL_TIMEOUT}" python3 "${script}"; then
        local elapsed=$(( $(date +%s) - start_time ))
        log "Orchestrator completed in ${elapsed}s"
        PLATFORMS_SUCCEEDED=$(( PLATFORMS_SUCCEEDED + 1 ))
        return 0
    else
        local exit_code=$?
        local elapsed=$(( $(date +%s) - start_time ))
        log_warn "Orchestrator exited with code ${exit_code} after ${elapsed}s"
        return "${exit_code}"
    fi
}

# ── Auto cascade: ZeroGPU -> Modal -> Lightning ──
run_cascade() {
    log_section "GPU CASCADE: ZeroGPU -> Modal -> Lightning"

    BEST_BRIER_BEFORE=$(get_current_best)
    log "Current best Brier: ${BEST_BRIER_BEFORE}"

    # Phase 1: ZeroGPU (always first -- free H200)
    local zerogpu_improved=0
    run_zerogpu && zerogpu_improved=1 || true
    check_timeout || return 0

    # Check if ZeroGPU improved
    local post_zerogpu_brier
    post_zerogpu_brier=$(get_current_best)
    if python3 -c "exit(0 if float('${post_zerogpu_brier}') < float('${BEST_BRIER_BEFORE}') - 0.00005 else 1)" 2>/dev/null; then
        log "ZeroGPU improved Brier: ${BEST_BRIER_BEFORE} -> ${post_zerogpu_brier}"
        IMPROVED=1
    fi

    # Phase 2: Modal (only if ZeroGPU didn't improve AND Modal is configured)
    if (( IMPROVED == 0 )); then
        if [[ -n "${MODAL_TOKEN_ID:-}" && -n "${MODAL_TOKEN_SECRET:-}" ]] || modal profile current &>/dev/null 2>&1; then
            run_modal || true
            check_timeout || return 0

            local post_modal_brier
            post_modal_brier=$(get_current_best)
            if python3 -c "exit(0 if float('${post_modal_brier}') < float('${BEST_BRIER_BEFORE}') - 0.00005 else 1)" 2>/dev/null; then
                log "Modal improved Brier: ${BEST_BRIER_BEFORE} -> ${post_modal_brier}"
                IMPROVED=1
            fi
        else
            log "Skipping Modal -- not authenticated and no tokens configured"
        fi
    else
        log "Skipping Modal -- ZeroGPU already found improvement"
    fi

    # Phase 3: Lightning (fallback if nothing improved)
    if (( IMPROVED == 0 )); then
        if command -v lightning &>/dev/null; then
            run_lightning || true
        else
            log "Skipping Lightning -- CLI not in PATH"
        fi
    else
        log "Skipping Lightning -- already found improvement"
    fi

    BEST_BRIER_AFTER=$(get_current_best)
}

# ── Summary ──
print_summary() {
    local total_elapsed=$(( $(date +%s) - OVERALL_START ))

    log_section "GPU BURST SUMMARY"
    log "Platforms tried:     ${PLATFORMS_TRIED}"
    log "Platforms succeeded: ${PLATFORMS_SUCCEEDED}"
    log "Total time:          ${total_elapsed}s"
    log "Brier before:        ${BEST_BRIER_BEFORE:-unknown}"
    log "Brier after:         ${BEST_BRIER_AFTER:-unknown}"

    if (( IMPROVED == 1 )); then
        log "Result: IMPROVED"
    else
        log "Result: No improvement (will try again next cycle)"
    fi

    # Write summary to state file
    python3 -c "
import json, os
from datetime import datetime, timezone
state_file = '${DATA_DIR}/gpu-cron-state.json'
state = {}
if os.path.exists(state_file):
    try:
        state = json.load(open(state_file))
    except: pass
state['last_run'] = datetime.now(timezone.utc).isoformat()
state['last_duration_sec'] = ${total_elapsed}
state['last_platforms_tried'] = ${PLATFORMS_TRIED}
state['last_platforms_succeeded'] = ${PLATFORMS_SUCCEEDED}
state['last_improved'] = ${IMPROVED} == 1
state['last_brier_before'] = '${BEST_BRIER_BEFORE:-unknown}'
state['last_brier_after'] = '${BEST_BRIER_AFTER:-unknown}'
state['total_runs'] = state.get('total_runs', 0) + 1
state['total_improvements'] = state.get('total_improvements', 0) + (1 if ${IMPROVED} == 1 else 0)
json.dump(state, open(state_file, 'w'), indent=2)
" 2>/dev/null || true
}

# ── Main ──
main() {
    local mode="${1:-cascade}"

    log_section "NOMOS42 GPU CRON LAUNCHER -- $(date -u)"
    log "Mode: ${mode}"
    log "Repo: ${REPO_ROOT}"
    log "PATH: ${PATH}"
    log "Max timeout: ${MAX_TOTAL_TIMEOUT}s"

    case "${mode}" in
        zerogpu|zero)
            BEST_BRIER_BEFORE=$(get_current_best)
            run_zerogpu
            BEST_BRIER_AFTER=$(get_current_best)
            ;;
        modal)
            BEST_BRIER_BEFORE=$(get_current_best)
            run_modal
            BEST_BRIER_AFTER=$(get_current_best)
            ;;
        lightning)
            BEST_BRIER_BEFORE=$(get_current_best)
            run_lightning
            BEST_BRIER_AFTER=$(get_current_best)
            ;;
        orchestrator|orch)
            BEST_BRIER_BEFORE=$(get_current_best)
            run_orchestrator
            BEST_BRIER_AFTER=$(get_current_best)
            ;;
        cascade|auto|"")
            run_cascade
            ;;
        *)
            log_error "Unknown mode: ${mode}"
            log "Usage: $0 [cascade|zerogpu|modal|lightning|orchestrator]"
            exit 1
            ;;
    esac

    print_summary

    # Exit 0 always -- cron should not spam error emails
    exit 0
}

main "$@"
