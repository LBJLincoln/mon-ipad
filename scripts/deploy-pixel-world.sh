#!/bin/bash
# Deploy Nomos42 Pixel World to HF Static Space
# Space: Nomos42/pixel-world (or LBJLincoln/pixel-world)
# Run: bash scripts/deploy-pixel-world.sh

set -euo pipefail
source /home/lahargnedebartoli/mon-ipad/.env.local 2>/dev/null || true

REPO_DIR="/home/lahargnedebartoli/mon-ipad"
SPACE_DIR="hf-pixel-world"
SPACE_ID="Nomos42/pixel-world"
HF_TOKEN_DEPLOY="${HF_TOKEN_3:-${HF_TOKEN:-}}"

log() { echo "[$(date -u +%H:%M:%SZ)] $1"; }

log "=== Nomos42 Pixel World Deploy ==="

# Step 1: Sync latest data files
log "Syncing data files..."
cp "$REPO_DIR/data/arena/agent-states-v5.json" "$REPO_DIR/$SPACE_DIR/data/arena/" 2>/dev/null || true
cp "$REPO_DIR/data/arena/model-predictions-latest.json" "$REPO_DIR/$SPACE_DIR/data/arena/" 2>/dev/null || true
cp "$REPO_DIR/data/agent-health.json" "$REPO_DIR/$SPACE_DIR/data/" 2>/dev/null || true
cp "$REPO_DIR/data/nba-agent/bankroll-state.json" "$REPO_DIR/$SPACE_DIR/data/nba-agent/" 2>/dev/null || true

# Step 2: Commit changes
cd "$REPO_DIR"
if ! git diff --quiet "$SPACE_DIR/" 2>/dev/null || git ls-files --others --exclude-standard "$SPACE_DIR/" | grep -q .; then
    git add "$SPACE_DIR/"
    git commit -m "feat: Nomos42 Pixel World — 207 agent trading floor (pixel art, PixiJS 8)" || true
    git push origin main || true
fi

# Step 3: Push to HF Spaces via subtree
log "Deploying to HF Space: $SPACE_ID"

if [ -z "$HF_TOKEN_DEPLOY" ]; then
    log "ERROR: No HF token available. Set HF_TOKEN_3 or HF_TOKEN in .env.local"
    exit 1
fi

git subtree split --prefix="$SPACE_DIR" -b pixel-world-deploy 2>/dev/null || true

if git push "https://user:${HF_TOKEN_DEPLOY}@huggingface.co/spaces/${SPACE_ID}" pixel-world-deploy:main --force 2>&1; then
    log "SUCCESS: Pixel World deployed to https://huggingface.co/spaces/${SPACE_ID}"
    log "Live URL: https://nomos42-pixel-world.hf.space"
else
    log "WARN: Push to $SPACE_ID failed. May need to create the Space first."
    log "Create at: https://huggingface.co/new-space"
    log "Then run this script again."
fi

# Cleanup temp branch
git branch -D pixel-world-deploy 2>/dev/null || true

log "Done."
