#!/bin/bash
# bulk-pull.sh — Pull latest from all 7 repos
# Usage: bash scripts/bulk-pull.sh [--dry-run]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
DRY_RUN=false

# Parse args
for arg in "$@"; do
    if [[ "$arg" == "--dry-run" ]]; then
        DRY_RUN=true
    fi
done

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "=== Bulk Pull (7 repos) ==="
echo "Dry run: $DRY_RUN"
echo ""

# Pull origin (mon-ipad)
echo -e "${BLUE}━━━ origin (mon-ipad) ━━━${NC}"
cd "$REPO_ROOT"

if [[ "$DRY_RUN" == "true" ]]; then
    echo "[DRY RUN] Would run: git pull origin main"
    git fetch origin --dry-run 2>&1 | head -n 3 || true
else
    # Check for uncommitted changes
    if [[ -n $(git status --porcelain) ]]; then
        echo -e "${YELLOW}Warning: Uncommitted changes detected${NC}"
        git status --short | head -n 5
        echo ""
        echo "Stashing changes before pull..."
        git stash push -m "bulk-pull.sh auto-stash $(date +%Y-%m-%d_%H-%M-%S)"
    fi

    # Pull
    if git pull origin main --quiet; then
        echo -e "${GREEN}✓ Pulled successfully${NC}"
    else
        echo -e "${RED}✗ Pull failed${NC}"
    fi
fi
echo ""

# Pull satellite repos (fetch remote refs)
for repo in rag-tests rag-website rag-dashboard rag-data-ingestion rag-pme-connectors rag-pme-usecases; do
    echo -e "${BLUE}━━━ $repo ━━━${NC}"

    if [[ "$DRY_RUN" == "true" ]]; then
        echo "[DRY RUN] Would run: git fetch $repo"
        git -C "$REPO_ROOT" fetch "$repo" --dry-run 2>&1 | head -n 3 || echo "No changes"
    else
        # Fetch latest refs from satellite
        if git -C "$REPO_ROOT" fetch "$repo" --quiet 2>/dev/null; then
            latest_commit=$(git -C "$REPO_ROOT" log -1 --format="%h %s" "$repo/main" 2>/dev/null || echo "No commits")
            echo -e "${GREEN}✓ Fetched successfully${NC}"
            echo "Latest: $latest_commit"
        else
            echo -e "${RED}✗ Fetch failed${NC}"
        fi
    fi
    echo ""
done

echo "=== Summary ==="
if [[ "$DRY_RUN" == "true" ]]; then
    echo "Dry run completed. No changes made."
    echo "Run without --dry-run to execute pulls."
else
    echo "Pull completed for all repos."
    echo "Origin (mon-ipad) was pulled and merged."
    echo "Satellites were fetched (refs updated)."
fi
echo ""
echo "To check status: bash scripts/bulk-status.sh"
