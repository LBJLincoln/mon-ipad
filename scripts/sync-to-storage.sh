#!/bin/bash
# =================================================================
# Sync mon-ipad data to rag-storage repo
# =================================================================
# Copies eval data, logs, snapshots, datasets, and global metrics
# to the centralized rag-storage repo. Run after each session.
#
# Usage: bash scripts/sync-to-storage.sh
# =================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STORAGE_DIR="/home/termius/rag-storage"

if [ ! -d "$STORAGE_DIR" ]; then
    echo "ERROR: rag-storage not found at $STORAGE_DIR"
    echo "Clone: git clone https://github.com/LBJLincoln/rag-storage.git /home/termius/rag-storage"
    exit 1
fi

echo "=== Syncing mon-ipad → rag-storage ==="

# --- Global metrics ---
echo "[1/6] Global metrics..."
cp -f "$REPO_ROOT/docs/status.json" "$STORAGE_DIR/global/status/" 2>/dev/null || true
cp -f "$REPO_ROOT/docs/executive-summary.md" "$STORAGE_DIR/global/executive-summary/" 2>/dev/null || true
cp -f "$REPO_ROOT/technicals/debug/fixes-library.md" "$STORAGE_DIR/global/fixes-timeline/" 2>/dev/null || true

# --- mon-ipad eval data ---
echo "[2/6] Eval data..."
cp -f "$REPO_ROOT/docs/data.json" "$STORAGE_DIR/repos/mon-ipad/eval-data/" 2>/dev/null || true
cp -f "$REPO_ROOT/docs/tested_ids.json" "$STORAGE_DIR/repos/mon-ipad/eval-data/" 2>/dev/null || true
cp -f "$REPO_ROOT/website/public/eval-data.json" "$STORAGE_DIR/repos/mon-ipad/eval-data/" 2>/dev/null || true

# --- Logs ---
echo "[3/6] Logs..."
rsync -a --delete "$REPO_ROOT/logs/" "$STORAGE_DIR/repos/mon-ipad/logs/" 2>/dev/null || \
    cp -r "$REPO_ROOT/logs/"* "$STORAGE_DIR/repos/mon-ipad/logs/" 2>/dev/null || true

# --- Snapshots ---
echo "[4/6] Snapshots..."
rsync -a --delete "$REPO_ROOT/snapshot/" "$STORAGE_DIR/repos/mon-ipad/snapshots/" 2>/dev/null || \
    cp -r "$REPO_ROOT/snapshot/"* "$STORAGE_DIR/repos/mon-ipad/snapshots/" 2>/dev/null || true

# --- Datasets ---
echo "[5/6] Datasets..."
rsync -a "$REPO_ROOT/datasets/" "$STORAGE_DIR/repos/mon-ipad/datasets/" 2>/dev/null || \
    cp -r "$REPO_ROOT/datasets/"* "$STORAGE_DIR/repos/mon-ipad/datasets/" 2>/dev/null || true

# --- Session outputs ---
echo "[6/6] Session outputs..."
cp -r "$REPO_ROOT/outputs/"* "$STORAGE_DIR/repos/mon-ipad/session-outputs/" 2>/dev/null || true

# --- Commit and push ---
echo ""
echo "=== Committing to rag-storage ==="
cd "$STORAGE_DIR"
git add -A
if git diff --cached --quiet; then
    echo "No changes to sync."
else
    TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    git commit -m "sync: mon-ipad → rag-storage ($TIMESTAMP)"
    git push origin main
    echo "Synced and pushed."
fi
