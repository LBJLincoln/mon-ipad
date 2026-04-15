#!/usr/bin/env bash
# Deploy Trading Floor Space to HuggingFace
# Usage: ./deploy.sh [SPACE_NAME]
#   SPACE_NAME defaults to Nomos42/nba-trading-floor
#
# Prerequisites:
#   - huggingface-cli login (with write token)
#   - git lfs installed
#
# This script:
#   1. Syncs arena modules from scripts/arena/
#   2. Syncs data files needed for predictions
#   3. Pushes to HF Space via git

set -euo pipefail

SPACE_NAME="${1:-Nomos42/nba-trading-floor}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
ARENA_SRC="$REPO_ROOT/scripts/arena"

echo "=== Nomos42 Trading Floor Space Deploy ==="
echo "Space: $SPACE_NAME"
echo "Source: $ARENA_SRC"
echo ""

# Step 1: Sync arena modules
echo "[1/4] Syncing arena modules..."
for f in api_pool.py agent_registry.py bet_categories.py debate_round.py; do
    if [ -f "$ARENA_SRC/$f" ]; then
        cp "$ARENA_SRC/$f" "$SCRIPT_DIR/arena/$f"
        echo "  Copied: $f"
    else
        echo "  WARNING: $f not found in $ARENA_SRC"
    fi
done

# Step 2: Sync data files (odds, predictions) if they exist
echo "[2/4] Syncing data files..."
mkdir -p "$SCRIPT_DIR/data/nba-agent"
mkdir -p "$SCRIPT_DIR/data/arena"

# Copy predictions if available
for f in "$REPO_ROOT/data/nba-agent/predictions-latest.json" \
         "$REPO_ROOT/data/nba-agent/odds-latest.json"; do
    if [ -f "$f" ]; then
        cp "$f" "$SCRIPT_DIR/data/nba-agent/"
        echo "  Copied: $(basename "$f")"
    fi
done

# Copy arena state if available
for f in "$REPO_ROOT/data/arena/agent-states-v5.json" \
         "$REPO_ROOT/data/arena/trading-floor-v5-latest.json"; do
    if [ -f "$f" ]; then
        cp "$f" "$SCRIPT_DIR/data/arena/"
        echo "  Copied: $(basename "$f")"
    fi
done

# Step 3: Verify files
echo "[3/4] Verifying structure..."
echo "  Files:"
find "$SCRIPT_DIR" -type f -not -path '*/.git/*' -not -path '*/__pycache__/*' | sort | while read -r f; do
    size=$(wc -c < "$f")
    echo "    $(basename "$f") ($size bytes)"
done

# Step 4: Push to HF (only if HF_TOKEN is set)
echo "[4/4] Pushing to HuggingFace..."
if [ -z "${HF_TOKEN:-}" ] && [ -z "${HF_TOKEN_LLM:-}" ]; then
    echo "  No HF_TOKEN set. To push manually:"
    echo "    cd $SCRIPT_DIR"
    echo "    git init"
    echo "    git remote add space https://huggingface.co/spaces/$SPACE_NAME"
    echo "    git add -A"
    echo "    git commit -m 'Deploy trading floor space'"
    echo "    git push space main --force"
    echo ""
    echo "  Or use huggingface-cli:"
    echo "    huggingface-cli upload $SPACE_NAME $SCRIPT_DIR . --repo-type=space"
else
    TOKEN="${HF_TOKEN_LLM:-$HF_TOKEN}"
    echo "  Using HF token to upload..."

    # Check if huggingface-cli is available
    if command -v huggingface-cli &>/dev/null; then
        huggingface-cli upload "$SPACE_NAME" "$SCRIPT_DIR" . \
            --repo-type=space \
            --token="$TOKEN" \
            --commit-message="Deploy trading floor v5 space"
        echo "  Deployed to: https://huggingface.co/spaces/$SPACE_NAME"
    else
        echo "  huggingface-cli not found. Install: pip install huggingface_hub"
        echo "  Manual push:"
        echo "    cd $SCRIPT_DIR && git init && git remote add space https://USER:TOKEN@huggingface.co/spaces/$SPACE_NAME"
        echo "    git add -A && git commit -m 'Deploy' && git push space main --force"
    fi
fi

echo ""
echo "=== Deploy complete ==="
echo "Space URL: https://huggingface.co/spaces/$SPACE_NAME"
echo "API URL:   https://${SPACE_NAME//\//-}.hf.space/api/status"
