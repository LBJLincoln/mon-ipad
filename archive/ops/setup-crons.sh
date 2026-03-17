#!/bin/bash
# Setup cron jobs for keepalive and self-healing
# Run once: bash scripts/setup-crons.sh
# Verify: crontab -l

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"

echo "Setting up crons for mon-ipad..."
echo "  Base dir: $BASE_DIR"

# Remove any existing keepalive/self-heal crons, keep everything else
crontab -l 2>/dev/null | grep -v 'keepalive\|self-heal' > /tmp/crontab-clean.txt || true

# Add keepalive: every 5 minutes
echo "*/5 * * * * $BASE_DIR/scripts/keepalive-spaces.sh --cron >> /tmp/keepalive.log 2>&1" >> /tmp/crontab-clean.txt

# Add self-heal smoke: every 15 minutes
echo "*/15 * * * * cd $BASE_DIR && source $BASE_DIR/.env.local && python3 $BASE_DIR/scripts/self-heal-orchestrator.py --smoke >> /tmp/self-heal.log 2>&1" >> /tmp/crontab-clean.txt

# Install new crontab
crontab /tmp/crontab-clean.txt
rm -f /tmp/crontab-clean.txt

echo ""
echo "Crons installed:"
crontab -l | grep -E 'keepalive|self-heal'
echo ""
echo "Logs:"
echo "  Keepalive: /tmp/keepalive.log"
echo "  Self-heal: /tmp/self-heal.log"
echo "  Self-heal JSONL: $BASE_DIR/logs/self-heal.jsonl"
echo ""
echo "Done."
