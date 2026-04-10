#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# Nomos42 — GPU Platform Status Check
# ═══════════════════════════════════════════════════════════════════
# Quick health check of all GPU/compute platforms.
# Prints a table: platform / status / GPU / credits / last_result / next_run
#
# Usage:
#   scripts/gpu-burst/gpu-status.sh          # Full status
#   scripts/gpu-burst/gpu-status.sh --brief  # One-line summary
#   scripts/gpu-burst/gpu-status.sh --json   # Machine-readable JSON
#
# No ML runs on this VM (969MB RAM). This script only CHECKS status.
# ═══════════════════════════════════════════════════════════════════

set -euo pipefail

REPO_ROOT="/home/lahargnedebartoli/mon-ipad"
DATA_DIR="$REPO_ROOT/data/gpu-burst"
KARPATHY_DIR="$REPO_ROOT/data/karpathy"
LOG_DIR="$REPO_ROOT/logs"

# Load env silently
if [[ -f "$REPO_ROOT/.env.local" ]]; then
    set -a
    source "$REPO_ROOT/.env.local" 2>/dev/null || true
    set +a
fi

# Args
BRIEF=false
JSON_OUT=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --brief) BRIEF=true; shift ;;
        --json) JSON_OUT=true; shift ;;
        --help|-h)
            echo "Usage: $0 [--brief] [--json]"
            exit 0
            ;;
        *) shift ;;
    esac
done

# ── Colors ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# ── Helper functions ──
ts() { date -u "+%Y-%m-%dT%H:%M:%SZ"; }

check_cmd() { command -v "$1" &>/dev/null; }

# Read a JSON field from a file (lightweight, no jq dependency)
json_field() {
    local file="$1" field="$2"
    python3 -c "
import json, sys
try:
    with open('$file') as f:
        d = json.load(f)
    val = d.get('$field', '?')
    print(val if val is not None else '?')
except Exception:
    print('?')
" 2>/dev/null
}

# ══════════════════════════════════════════════════════════
# PLATFORM CHECKS
# ══════════════════════════════════════════════════════════

declare -A PLATFORM_STATUS
declare -A PLATFORM_GPU
declare -A PLATFORM_CREDITS
declare -A PLATFORM_LAST_BRIER
declare -A PLATFORM_LAST_TIME
declare -A PLATFORM_NEXT_RUN

# ── 1. HF Spaces (6 CPU islands, always running) ──
check_hf_spaces() {
    local running=0
    local total=6
    local best_brier="?"

    for island in S10 S11 S12 S13 S14 S15; do
        case $island in
            S10) url="https://nomos42-nba-quant.hf.space" ;;
            S11) url="https://nomos42-nba-quant-2.hf.space" ;;
            S12) url="https://nomos42-nba-evo-3.hf.space" ;;
            S13) url="https://nomos42-nba-evo-4.hf.space" ;;
            S14) url="https://nomos42-nba-evo-5.hf.space" ;;
            S15) url="https://nomos42-nba-evo-6.hf.space" ;;
        esac

        if timeout 8 curl -s --connect-timeout 3 --max-time 6 "${url}/api/status" &>/dev/null; then
            running=$((running + 1))
        fi
    done

    if [[ $running -eq $total ]]; then
        PLATFORM_STATUS[hf_spaces]="OK ($running/$total)"
    elif [[ $running -gt 0 ]]; then
        PLATFORM_STATUS[hf_spaces]="PARTIAL ($running/$total)"
    else
        PLATFORM_STATUS[hf_spaces]="DOWN (0/$total)"
    fi
    PLATFORM_GPU[hf_spaces]="CPU x6"
    PLATFORM_CREDITS[hf_spaces]="always-on"
    PLATFORM_NEXT_RUN[hf_spaces]="continuous"

    # Get fleet best from quant summary
    if [[ -f "$REPO_ROOT/data/nba-agent/quant-summary.json" ]]; then
        PLATFORM_LAST_BRIER[hf_spaces]=$(json_field "$REPO_ROOT/data/nba-agent/quant-summary.json" "fleet_best_brier")
    fi
}

# ── 2. HF ZeroGPU (H200, 5 min/account x 3 = 15 min/day) ──
check_zerogpu() {
    local cron_exists=false
    if crontab -l 2>/dev/null | grep -q "zerogpu-burst" 2>/dev/null; then
        cron_exists=true
    fi

    local tokens=0
    [[ -n "${HF_TOKEN:-}" ]] && tokens=$((tokens + 1)) || true
    [[ -n "${HF_TOKEN_2:-}" ]] && tokens=$((tokens + 1)) || true
    [[ -n "${HF_TOKEN_3:-}" ]] && tokens=$((tokens + 1)) || true

    if $cron_exists && [[ $tokens -gt 0 ]]; then
        PLATFORM_STATUS[zerogpu]="OK (cron + ${tokens} tokens)"
    elif [[ $tokens -gt 0 ]]; then
        PLATFORM_STATUS[zerogpu]="NO CRON (${tokens} tokens)"
    else
        PLATFORM_STATUS[zerogpu]="NO TOKENS"
    fi
    PLATFORM_GPU[zerogpu]="H200"
    PLATFORM_CREDITS[zerogpu]="${tokens}x5min/day"
    PLATFORM_NEXT_RUN[zerogpu]="06:00 UTC"

    if [[ -f "$DATA_DIR/latest-zerogpu-result.json" ]]; then
        PLATFORM_LAST_BRIER[zerogpu]=$(json_field "$DATA_DIR/latest-zerogpu-result.json" "best_brier_found")
        PLATFORM_LAST_TIME[zerogpu]=$(json_field "$DATA_DIR/latest-zerogpu-result.json" "timestamp")
    fi
}

# ── 3. Kaggle (P100, 30h/week) ──
check_kaggle() {
    if check_cmd kaggle; then
        # Kaggle CLI is slow to start -- just check binary exists
        PLATFORM_STATUS[kaggle]="OK (installed)"
    else
        PLATFORM_STATUS[kaggle]="NOT INSTALLED"
    fi
    PLATFORM_GPU[kaggle]="P100"
    PLATFORM_CREDITS[kaggle]="30h/week"
    PLATFORM_NEXT_RUN[kaggle]="03:00 UTC"

    if [[ -f "$DATA_DIR/latest-kaggle-result.json" ]]; then
        PLATFORM_LAST_BRIER[kaggle]=$(json_field "$DATA_DIR/latest-kaggle-result.json" "best_brier")
        PLATFORM_LAST_TIME[kaggle]=$(json_field "$DATA_DIR/latest-kaggle-result.json" "timestamp")
    fi
}

# ── 4. Lightning AI (T4/A10G, 22h total free) ──
check_lightning() {
    if check_cmd lightning; then
        # Lightning CLI is slow -- just check binary exists
        PLATFORM_STATUS[lightning]="OK (installed)"
    else
        PLATFORM_STATUS[lightning]="NOT INSTALLED"
    fi
    PLATFORM_GPU[lightning]="T4/A10G"
    PLATFORM_CREDITS[lightning]="22h total"
    PLATFORM_NEXT_RUN[lightning]="12:00 UTC"

    if [[ -f "$DATA_DIR/latest-lightning-nba-result.json" ]]; then
        PLATFORM_LAST_BRIER[lightning]=$(json_field "$DATA_DIR/latest-lightning-nba-result.json" "best_score")
        PLATFORM_LAST_TIME[lightning]=$(json_field "$DATA_DIR/latest-lightning-nba-result.json" "timestamp")
    fi
}

# ── 5. Modal (A10G/A100, $0.16+/hr) ──
check_modal() {
    if python3 -c "import modal" 2>/dev/null; then
        # Modal profile check is slow -- just verify import works
        PLATFORM_STATUS[modal]="OK (installed)"
    else
        PLATFORM_STATUS[modal]="NOT INSTALLED"
    fi
    PLATFORM_GPU[modal]="A10G/A100"
    PLATFORM_CREDITS[modal]="pay-per-use"
    PLATFORM_NEXT_RUN[modal]="on-demand"

    if [[ -f "$DATA_DIR/latest-modal-result.json" ]]; then
        PLATFORM_LAST_BRIER[modal]=$(json_field "$DATA_DIR/latest-modal-result.json" "best_brier")
        PLATFORM_LAST_TIME[modal]=$(json_field "$DATA_DIR/latest-modal-result.json" "timestamp")
    fi
}

# ── 6. Google Colab (T4, free tier) ──
check_colab() {
    PLATFORM_STATUS[colab]="MANUAL ONLY"
    PLATFORM_GPU[colab]="T4"
    PLATFORM_CREDITS[colab]="free tier"
    PLATFORM_NEXT_RUN[colab]="manual"

    if [[ -f "$DATA_DIR/latest-colab-result.json" ]]; then
        PLATFORM_LAST_BRIER[colab]=$(json_field "$DATA_DIR/latest-colab-result.json" "best_brier")
        PLATFORM_LAST_TIME[colab]=$(json_field "$DATA_DIR/latest-colab-result.json" "timestamp")
    fi
}

# ── 7. Laptop Ollama (local, monitoring only) ──
check_laptop() {
    # Check if laptop is reachable via Tailscale
    if timeout 3 ping -c 1 -W 2 100.64.0.2 &>/dev/null 2>&1; then
        PLATFORM_STATUS[laptop]="REACHABLE (Tailscale)"
    else
        PLATFORM_STATUS[laptop]="UNREACHABLE"
    fi
    PLATFORM_GPU[laptop]="CPU (Ollama)"
    PLATFORM_CREDITS[laptop]="local"
    PLATFORM_NEXT_RUN[laptop]="continuous"
}

# ══════════════════════════════════════════════════════════
# RUN ALL CHECKS
# ══════════════════════════════════════════════════════════

if $BRIEF; then
    # Skip slow network checks for brief mode
    PLATFORM_STATUS[hf_spaces]="(skipped)"
    PLATFORM_GPU[hf_spaces]="CPU x6"
    check_zerogpu
    check_kaggle
    check_lightning
    check_modal
    check_colab
    PLATFORM_STATUS[laptop]="(skipped)"
    PLATFORM_GPU[laptop]="CPU"
else
    check_hf_spaces
    check_zerogpu
    check_kaggle
    check_lightning
    check_modal
    check_colab
    check_laptop
fi

# ══════════════════════════════════════════════════════════
# OUTPUT
# ══════════════════════════════════════════════════════════

if $JSON_OUT; then
    # JSON output for machine consumption
    python3 -c "
import json
platforms = {}
" # Shell will populate via heredoc below

    python3 << 'PYEOF'
import json, sys

platforms = {
    "hf_spaces": {
        "status": """${PLATFORM_STATUS[hf_spaces]:-?}""",
        "gpu": """${PLATFORM_GPU[hf_spaces]:-?}""",
        "credits": """${PLATFORM_CREDITS[hf_spaces]:-?}""",
        "last_brier": """${PLATFORM_LAST_BRIER[hf_spaces]:-?}""",
        "next_run": """${PLATFORM_NEXT_RUN[hf_spaces]:-?}""",
    },
}
# Simplified -- full JSON handled by compute-orchestrator.py --status
print(json.dumps({"note": "Use compute-orchestrator.py --status for full JSON"}, indent=2))
PYEOF
    exit 0
fi

if $BRIEF; then
    # One-line summary
    ok_count=0
    total_count=7
    for key in hf_spaces zerogpu kaggle lightning modal colab laptop; do
        status="${PLATFORM_STATUS[$key]:-?}"
        if [[ "$status" == OK* ]]; then
            ok_count=$((ok_count + 1))
        fi
    done

    # Get best brier
    best_brier="?"
    if [[ -f "$KARPATHY_DIR/nba-best-config.json" ]]; then
        best_brier=$(json_field "$KARPATHY_DIR/nba-best-config.json" "best_brier")
    fi

    echo "GPU Fleet: ${ok_count}/${total_count} OK | Best Brier: ${best_brier} | $(date -u '+%H:%M UTC')"
    exit 0
fi

# Full table output
echo ""
echo -e "${BOLD}═══════════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  NOMOS42 GPU FLEET STATUS  $(date -u '+%Y-%m-%d %H:%M UTC')${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════════════════${NC}"

# Current best
best_brier="?"
if [[ -f "$KARPATHY_DIR/nba-best-config.json" ]]; then
    best_brier=$(json_field "$KARPATHY_DIR/nba-best-config.json" "best_brier")
fi
echo -e "\n  ${CYAN}Best Brier:${NC} ${BOLD}${best_brier}${NC}  |  ATR: 0.21570  |  Target: < 0.20000"

# Table header
echo ""
printf "  ${BOLD}%-14s %-10s %-14s %-26s %-12s${NC}\n" \
    "PLATFORM" "GPU" "CREDITS" "STATUS" "NEXT RUN"
printf "  %-14s %-10s %-14s %-26s %-12s\n" \
    "--------------" "----------" "--------------" "--------------------------" "------------"

# Table rows
for key in hf_spaces zerogpu kaggle lightning modal colab laptop; do
    status="${PLATFORM_STATUS[$key]:-?}"
    gpu="${PLATFORM_GPU[$key]:-?}"
    credits="${PLATFORM_CREDITS[$key]:-?}"
    next="${PLATFORM_NEXT_RUN[$key]:-?}"
    last_brier="${PLATFORM_LAST_BRIER[$key]:-}"

    # Color code status
    if [[ "$status" == OK* ]]; then
        color=$GREEN
    elif [[ "$status" == PARTIAL* ]] || [[ "$status" == "NO CRON"* ]] || [[ "$status" == "MANUAL"* ]]; then
        color=$YELLOW
    else
        color=$RED
    fi

    # Add brier to status if available
    if [[ -n "$last_brier" ]] && [[ "$last_brier" != "?" ]]; then
        status_display="$status"
    else
        status_display="$status"
    fi

    printf "  %-14s %-10s %-14s ${color}%-26s${NC} %-12s\n" \
        "$key" "$gpu" "$credits" "$status_display" "$next"
done

# Latest results section
echo ""
echo -e "  ${BOLD}Latest Results:${NC}"
printf "  %-14s %-12s %-16s %-12s\n" "PLATFORM" "BRIER" "MODEL" "DATE"
printf "  %-14s %-12s %-16s %-12s\n" "--------------" "------------" "----------------" "------------"

for key in zerogpu kaggle lightning modal colab; do
    brier="${PLATFORM_LAST_BRIER[$key]:-n/a}"
    ts="${PLATFORM_LAST_TIME[$key]:-never}"
    # Truncate timestamp
    if [[ "$ts" != "never" ]] && [[ "$ts" != "?" ]]; then
        ts="${ts:0:10}"
    fi

    result_file=""
    case $key in
        zerogpu)   result_file="$DATA_DIR/latest-zerogpu-result.json" ;;
        kaggle)    result_file="$DATA_DIR/latest-kaggle-result.json" ;;
        lightning) result_file="$DATA_DIR/latest-lightning-nba-result.json" ;;
        modal)     result_file="$DATA_DIR/latest-modal-result.json" ;;
        colab)     result_file="$DATA_DIR/latest-colab-result.json" ;;
    esac

    model="?"
    if [[ -n "$result_file" ]] && [[ -f "$result_file" ]]; then
        model=$(json_field "$result_file" "model_type")
    fi

    printf "  %-14s %-12s %-16s %-12s\n" "$key" "$brier" "$model" "$ts"
done

# Schedule
echo ""
echo -e "  ${BOLD}Daily Schedule (UTC):${NC}"
echo "  06:00  ZeroGPU H200 burst (3 accounts, 15 min free)"
echo "  03:00  Kaggle P100 session (cron, if credits)"
echo "  12:00  Lightning T4/A10G burst (if hours remain)"
echo "  ----   Modal A10G (\$0.18/burst, on-demand only)"
echo "  ----   Colab T4 (manual launch)"

# Scripts
echo ""
echo -e "  ${BOLD}Quick Commands:${NC}"
echo "  python3 scripts/gpu-burst/compute-orchestrator.py --status   # Full metrics"
echo "  python3 scripts/gpu-burst/compute-orchestrator.py --plan     # Today's plan"
echo "  python3 scripts/gpu-burst/compute-orchestrator.py --force zerogpu  # Force run"
echo "  python3 scripts/gpu-burst/hf-inference-client.py --test      # Test LLM models"
echo ""
echo -e "${BOLD}═══════════════════════════════════════════════════════════════════${NC}"
