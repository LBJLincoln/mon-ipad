#!/bin/bash
# Sync status.json from mon-ipad to rag-dashboard repo
# This keeps the public dashboard updated with latest metrics
#
# Usage: bash scripts/sync-dashboard-data.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MON_IPAD_DIR="$(dirname "$SCRIPT_DIR")"
DASHBOARD_DIR="/tmp/rag-dashboard-sync"

echo "🔄 Syncing dashboard data..."
echo "Source: $MON_IPAD_DIR/docs/status.json"
echo "Target: rag-dashboard/docs/status.json"

# Clone or update rag-dashboard repo
if [ -d "$DASHBOARD_DIR" ]; then
    echo "📂 Updating existing rag-dashboard clone..."
    cd "$DASHBOARD_DIR"
    git fetch origin
    git reset --hard origin/main
else
    echo "📥 Cloning rag-dashboard..."
    rm -rf "$DASHBOARD_DIR"
    git clone https://github.com/LBJLincoln/rag-dashboard.git "$DASHBOARD_DIR"
    cd "$DASHBOARD_DIR"
fi

# Configure git
git config user.email "alexis.moret6@outlook.fr"
git config user.name "Claude Code (auto-sync)"

# Copy status.json
echo "📋 Copying status.json..."
mkdir -p docs
cp "$MON_IPAD_DIR/docs/status.json" docs/status.json

# Also update the API fallback file
echo "📋 Updating API fallback..."
cp "$MON_IPAD_DIR/docs/status.json" api/fallback-status.json

# Check if there are changes
if git diff --quiet docs/status.json api/fallback-status.json; then
    echo "✅ No changes detected - dashboard already up to date"
    exit 0
fi

# Commit and push
echo "💾 Committing changes..."
git add docs/status.json api/fallback-status.json

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
git commit -m "chore: auto-sync status.json from mon-ipad

Updated: $TIMESTAMP
Source: mon-ipad/docs/status.json
Target: rag-dashboard/docs/status.json + api/fallback-status.json

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"

echo "🚀 Pushing to rag-dashboard..."
git push origin main

echo "✅ Dashboard data synced successfully!"
echo "🌐 Live dashboard: https://nomos-dashboard-alexis-morets-projects.vercel.app"
