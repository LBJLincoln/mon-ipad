#!/bin/bash
# cron-git-gc.sh — Weekly git garbage collection and cleanup
# Usage: bash scripts/cron-git-gc.sh
# Cron: 0 3 * * 0 /home/termius/mon-ipad/scripts/cron-git-gc.sh >> /var/log/cron-git-gc.log 2>&1

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
LOGS_DIR="$REPO_ROOT/logs"
TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)

# Color codes (if terminal supports)
if [ -t 1 ]; then
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    RED='\033[0;31m'
    BLUE='\033[0;34m'
    NC='\033[0m'
else
    GREEN=''
    YELLOW=''
    RED=''
    BLUE=''
    NC=''
fi

echo "=== Git GC & Cleanup — $TIMESTAMP ==="
echo ""

# 1. Check disk usage BEFORE
echo -e "${BLUE}━━━ Disk Usage (BEFORE) ━━━${NC}"
df -h / | grep -E '^/dev/' | awk '{print "Total: "$2" | Used: "$3" ("$5") | Available: "$4}'
du -sh "$REPO_ROOT" | awk '{print "Repo size: "$1}'
du -sh "$REPO_ROOT/.git" 2>/dev/null | awk '{print "Git objects: "$1}' || echo "Git objects: N/A"
echo ""

# 2. Git garbage collection (mon-ipad)
echo -e "${BLUE}━━━ Git GC (mon-ipad) ━━━${NC}"
cd "$REPO_ROOT"

# Count objects before
objects_before=$(git count-objects -v | grep 'count:' | awk '{print $2}')
size_before=$(git count-objects -v | grep 'size-pack:' | awk '{print $2}')

echo "Objects before: $objects_before"
echo "Size before: ${size_before}KB"

# Run aggressive GC
echo "Running git gc --aggressive --prune=now..."
git gc --aggressive --prune=now 2>&1 | head -n 5

# Count objects after
objects_after=$(git count-objects -v | grep 'count:' | awk '{print $2}')
size_after=$(git count-objects -v | grep 'size-pack:' | awk '{print $2}')

echo "Objects after: $objects_after"
echo "Size after: ${size_after}KB"

if [[ $size_before -gt $size_after ]]; then
    saved=$((size_before - size_after))
    echo -e "${GREEN}✓ Saved ${saved}KB${NC}"
else
    echo -e "${YELLOW}No significant space saved${NC}"
fi
echo ""

# 3. Clean temp directories
echo -e "${BLUE}━━━ Clean Temp Directories ━━━${NC}"

TEMP_DIRS=(
    "/tmp/push-directive-*"
    "/tmp/n8n-*"
    "/tmp/eval-*"
    "$REPO_ROOT/tmp"
)

for pattern in "${TEMP_DIRS[@]}"; do
    if ls $pattern 1> /dev/null 2>&1; then
        size=$(du -sh $pattern 2>/dev/null | awk '{sum+=$1} END {print sum}')
        rm -rf $pattern
        echo -e "${GREEN}✓ Cleaned $pattern (${size} removed)${NC}"
    fi
done
echo ""

# 4. Clean old logs (>30 days)
echo -e "${BLUE}━━━ Clean Old Logs (>30 days) ━━━${NC}"

if [[ -d "$LOGS_DIR" ]]; then
    # Count logs before
    logs_before=$(find "$LOGS_DIR" -type f | wc -l)

    # Delete old logs
    deleted=$(find "$LOGS_DIR" -type f -name "*.log" -mtime +30 -delete -print | wc -l)
    deleted_json=$(find "$LOGS_DIR" -type f -name "*.json" -mtime +30 -delete -print | wc -l)

    # Count logs after
    logs_after=$(find "$LOGS_DIR" -type f | wc -l)

    echo "Logs before: $logs_before"
    echo "Deleted: $deleted .log files + $deleted_json .json files"
    echo "Logs after: $logs_after"
    echo -e "${GREEN}✓ Cleaned $((deleted + deleted_json)) old log files${NC}"
else
    echo -e "${YELLOW}Logs directory not found${NC}"
fi
echo ""

# 5. Clean Python cache
echo -e "${BLUE}━━━ Clean Python Cache ━━━${NC}"

pycache_count=$(find "$REPO_ROOT" -type d -name "__pycache__" | wc -l)
if [[ $pycache_count -gt 0 ]]; then
    find "$REPO_ROOT" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    echo -e "${GREEN}✓ Removed $pycache_count __pycache__ directories${NC}"
else
    echo "No __pycache__ directories found"
fi

pyc_count=$(find "$REPO_ROOT" -type f -name "*.pyc" | wc -l)
if [[ $pyc_count -gt 0 ]]; then
    find "$REPO_ROOT" -type f -name "*.pyc" -delete 2>/dev/null || true
    echo -e "${GREEN}✓ Removed $pyc_count .pyc files${NC}"
else
    echo "No .pyc files found"
fi
echo ""

# 6. Clean node_modules cache (if any)
echo -e "${BLUE}━━━ Clean Node Cache ━━━${NC}"

node_modules_count=$(find "$REPO_ROOT" -type d -name "node_modules" -maxdepth 2 2>/dev/null | wc -l)
if [[ $node_modules_count -gt 0 ]]; then
    echo -e "${YELLOW}Found $node_modules_count node_modules directories${NC}"
    echo "Skipping removal (managed by npm). Run 'npm prune' manually if needed."
else
    echo "No node_modules directories found"
fi
echo ""

# 7. Check disk usage AFTER
echo -e "${BLUE}━━━ Disk Usage (AFTER) ━━━${NC}"
df -h / | grep -E '^/dev/' | awk '{print "Total: "$2" | Used: "$3" ("$5") | Available: "$4}'
du -sh "$REPO_ROOT" | awk '{print "Repo size: "$1}'
du -sh "$REPO_ROOT/.git" 2>/dev/null | awk '{print "Git objects: "$1}' || echo "Git objects: N/A"
echo ""

# 8. Summary
echo -e "${GREEN}=== Cleanup Complete ===${NC}"
echo "Timestamp: $TIMESTAMP"
echo "Next scheduled run: Weekly (Sunday 3am)"
echo ""
echo "To run manually: bash scripts/cron-git-gc.sh"
echo "To add to cron: crontab -e"
echo "  → 0 3 * * 0 /home/termius/mon-ipad/scripts/cron-git-gc.sh >> /var/log/cron-git-gc.log 2>&1"
