#!/bin/bash
################################################################################
# Install OpenCode Department Agent Cron Jobs
# Run this manually: bash scripts/opencode/install-crons.sh
# To remove: bash scripts/opencode/install-crons.sh --remove
################################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Cron entries with staggered schedules to avoid resource contention
CRON_ENTRIES=(
    # Research: every 6 hours at :05
    "5 */6 * * * $SCRIPT_DIR/research-agent.sh >> $REPO_ROOT/data/opencode/research.log 2>&1"
    # Evaluation: every 6 hours at :35
    "35 */6 * * * $SCRIPT_DIR/evaluation-agent.sh >> $REPO_ROOT/data/opencode/evaluation.log 2>&1"
    # Infra: every 4 hours at :15
    "15 */4 * * * $SCRIPT_DIR/infra-agent.sh >> $REPO_ROOT/data/opencode/infra.log 2>&1"
)

MARKER_START="# --- OpenCode Department Agents START ---"
MARKER_END="# --- OpenCode Department Agents END ---"

if [ "${1:-}" = "--remove" ]; then
    echo "Removing OpenCode cron entries..."
    CURRENT_CRON=$(crontab -l 2>/dev/null || true)
    echo "$CURRENT_CRON" | sed "/$MARKER_START/,/$MARKER_END/d" | crontab -
    echo "Done. Removed OpenCode cron entries."
    exit 0
fi

if [ "${1:-}" = "--dry-run" ]; then
    echo "=== DRY RUN: Would install these cron entries ==="
    echo ""
    echo "$MARKER_START"
    for entry in "${CRON_ENTRIES[@]}"; do
        echo "$entry"
    done
    echo "$MARKER_END"
    echo ""
    echo "=== Current crontab ==="
    crontab -l 2>/dev/null || echo "(empty)"
    exit 0
fi

echo "Installing OpenCode department agent cron jobs..."
echo ""

# Verify scripts exist and are executable
for script in research-agent.sh evaluation-agent.sh infra-agent.sh; do
    if [ ! -x "$SCRIPT_DIR/$script" ]; then
        echo "ERROR: $SCRIPT_DIR/$script is not executable. Run: chmod +x $SCRIPT_DIR/$script"
        exit 1
    fi
done

# Get current crontab, remove old entries if present
CURRENT_CRON=$(crontab -l 2>/dev/null || true)
CLEAN_CRON=$(echo "$CURRENT_CRON" | sed "/$MARKER_START/,/$MARKER_END/d")

# Build new crontab
NEW_CRON="$CLEAN_CRON
$MARKER_START"

for entry in "${CRON_ENTRIES[@]}"; do
    NEW_CRON="$NEW_CRON
$entry"
done

NEW_CRON="$NEW_CRON
$MARKER_END"

# Install
echo "$NEW_CRON" | crontab -

echo "Installed cron entries:"
echo ""
crontab -l | sed -n "/$MARKER_START/,/$MARKER_END/p"
echo ""
echo "Logs will be at:"
echo "  $REPO_ROOT/data/opencode/research.log"
echo "  $REPO_ROOT/data/opencode/evaluation.log"
echo "  $REPO_ROOT/data/opencode/infra.log"
echo ""
echo "To remove: $0 --remove"
echo "To preview: $0 --dry-run"
