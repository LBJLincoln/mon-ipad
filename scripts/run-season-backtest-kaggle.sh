#!/bin/bash
################################################################################
# Push & run NBA season backtest on Kaggle GPU
################################################################################
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KERNEL_DIR="$SCRIPT_DIR/kaggle"
SLUG="nba-season-backtest"

# Read username
KAGGLE_JSON="$HOME/.kaggle/kaggle.json"
USERNAME=$(python3 -c "import json; print(json.load(open('$KAGGLE_JSON'))['username'])" 2>/dev/null)

echo "[$(date '+%H:%M:%S')] Pushing season backtest to Kaggle..."
echo "  Username: $USERNAME"
echo "  Slug: $SLUG"

# Create temp dir with kernel + metadata
TMP=$(mktemp -d)
cp "$KERNEL_DIR/nba_season_backtest.py" "$TMP/"
cp "$KERNEL_DIR/season-backtest-metadata.json" "$TMP/kernel-metadata.json"

# Push
cd "$TMP"
kaggle kernels push -p "$TMP"

echo "[$(date '+%H:%M:%S')] Kernel pushed! Monitor at:"
echo "  https://www.kaggle.com/code/$USERNAME/$SLUG"

# Check status
sleep 10
kaggle kernels status "$USERNAME/$SLUG" 2>&1 || true

rm -rf "$TMP"
echo "[$(date '+%H:%M:%S')] Done. Results will be at /kaggle/working/season_backtest_results.json"
