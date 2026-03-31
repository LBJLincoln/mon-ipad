#!/bin/bash
# ══════════════════════════════════════════════════════════
# Karpathy Iteration Loop — Runner Script
# ══════════════════════════════════════════════════════════
# Usage:
#   ./run_karpathy.sh nba                     # 100 NBA iterations (CPU)
#   ./run_karpathy.sh political --iterations 500  # 500 political iterations
#   ./run_karpathy.sh nba --gpu               # GPU mode (full dataset)
#   ./run_karpathy.sh nba -n 200 --verbose    # 200 iterations with debug logs
#
# Env: sources .env.local for TELEGRAM_BOT_TOKEN, ADMIN_TELEGRAM_ID
# ══════════════════════════════════════════════════════════

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Source env vars
if [ -f "$ROOT/.env.local" ]; then
    source "$ROOT/.env.local"
fi

# Domain selection
DOMAIN="${1:-nba}"
shift 2>/dev/null || true

# Validate domain
case "$DOMAIN" in
    nba)
        SCRIPT="$SCRIPT_DIR/nba_iterate.py"
        ;;
    political)
        SCRIPT="$SCRIPT_DIR/political_iterate.py"
        ;;
    *)
        echo "Usage: $0 [nba|political] [--iterations N] [--gpu] [--verbose]"
        echo ""
        echo "Domains:"
        echo "  nba        — NBA Quant AI (Brier on 200-game holdout)"
        echo "  political  — Political Alpha (Brier on 50-event holdout)"
        echo ""
        echo "Options:"
        echo "  --iterations N, -n N  Number of iterations (default: 100)"
        echo "  --gpu                 Use full dataset (GPU mode)"
        echo "  --verbose, -v         Enable debug logging"
        exit 1
        ;;
esac

# Check script exists
if [ ! -f "$SCRIPT" ]; then
    echo "ERROR: Script not found: $SCRIPT"
    exit 1
fi

# Ensure data/log directories exist
mkdir -p "$ROOT/data/karpathy" "$ROOT/logs/karpathy"

echo "═══════════════════════════════════════════════════════"
echo "Karpathy Iteration Loop — $DOMAIN"
echo "Script: $SCRIPT"
echo "Args: $*"
echo "═══════════════════════════════════════════════════════"

# Run
exec python3 "$SCRIPT" "$@"
