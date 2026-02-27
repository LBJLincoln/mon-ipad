#!/bin/bash
# bulk-status.sh — Check git status across all 7 repos
# Usage: bash scripts/bulk-status.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "=== Bulk Git Status (7 repos) ==="
echo "Checking mon-ipad (origin) + 6 satellites"
echo ""

# Function to check local repo status (origin)
check_local_repo() {
    cd "$REPO_ROOT"

    echo -e "${BLUE}━━━ origin (mon-ipad) ━━━${NC}"

    # Current branch
    branch=$(git branch --show-current)
    echo "Branch: $branch"

    # Last commit
    last_commit=$(git log -1 --format="%h %s" 2>/dev/null || echo "No commits")
    echo "Last commit: $last_commit"

    # Uncommitted changes
    uncommitted=$(git status --porcelain | wc -l)
    if [[ $uncommitted -eq 0 ]]; then
        echo -e "Status: ${GREEN}Clean (0 changes)${NC}"
    else
        echo -e "Status: ${YELLOW}$uncommitted uncommitted changes${NC}"
        git status --short | head -n 5
        if [[ $uncommitted -gt 5 ]]; then
            echo "  ... and $((uncommitted - 5)) more"
        fi
    fi

    # Behind/ahead of remote
    git fetch origin --quiet 2>/dev/null || true
    behind=$(git rev-list --count HEAD..origin/$branch 2>/dev/null || echo "0")
    ahead=$(git rev-list --count origin/$branch..HEAD 2>/dev/null || echo "0")

    if [[ $behind -gt 0 ]]; then
        echo -e "Remote: ${RED}Behind by $behind commits${NC}"
    elif [[ $ahead -gt 0 ]]; then
        echo -e "Remote: ${YELLOW}Ahead by $ahead commits${NC}"
    else
        echo -e "Remote: ${GREEN}Up to date${NC}"
    fi

    echo ""
}

# Function to check satellite repo via GitHub API
check_satellite_repo() {
    local repo="$1"
    echo -e "${BLUE}━━━ $repo ━━━${NC}"

    # Get latest commit from GitHub
    latest_commit=$(gh api "repos/LBJLincoln/$repo/commits?per_page=1" --jq '.[0] | "\(.sha[0:7]) \(.commit.message | split("\n")[0])"' 2>/dev/null || echo "❌ API error")

    if [[ "$latest_commit" == "❌"* ]]; then
        echo -e "${RED}Error: Cannot fetch remote status${NC}"
    else
        echo "Latest commit: $latest_commit"

        # Get default branch
        default_branch=$(gh api "repos/LBJLincoln/$repo" --jq '.default_branch' 2>/dev/null || echo "main")
        echo "Default branch: $default_branch"

        # Check if we have a local fetch of this remote
        local_ref=$(git -C "$REPO_ROOT" ls-remote "$repo" HEAD 2>/dev/null | cut -f1 | head -c7 || echo "")
        if [[ -n "$local_ref" ]]; then
            remote_sha=$(echo "$latest_commit" | cut -d' ' -f1)
            if [[ "$local_ref" == "$remote_sha" ]]; then
                echo -e "Status: ${GREEN}In sync${NC}"
            else
                echo -e "Status: ${YELLOW}Differs from cached remote${NC}"
            fi
        else
            echo -e "Status: ${YELLOW}No local cache${NC}"
        fi
    fi

    echo ""
}

# Check origin (mon-ipad)
check_local_repo

# Check all 6 satellite repos
for repo in rag-tests rag-website rag-dashboard rag-data-ingestion rag-pme-connectors rag-pme-usecases; do
    check_satellite_repo "$repo"
done

echo "=== Summary ==="
echo "Total repos: 7 (1 origin + 6 satellites)"
echo ""
echo "To pull latest from all repos: bash scripts/bulk-pull.sh"
echo "To push directives to satellites: bash scripts/push-directives.sh"
