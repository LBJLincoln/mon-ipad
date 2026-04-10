#!/bin/bash
################################################################################
# Forge v19 — Verify all repos have correct structure
# Usage: ./verify-forge.sh
################################################################################

set -euo pipefail

REPOS="mon-ipad nomos-nba-agent nomos-political-alpha nomos-dashboard rgwa nomos-picks nomos-pierre OddsHarvester"
DEPARTMENTS="research engineering evolution product business evaluation infra finance"
PASS=0
FAIL=0
TOTAL=0

check() {
    TOTAL=$((TOTAL + 1))
    if eval "$2" > /dev/null 2>&1; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "  FAIL: $1"
    fi
}

echo "=========================================="
echo "  Forge v19 — Structure Verification"
echo "  $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "=========================================="

for repo in $REPOS; do
    REPO_PATH="/home/termius/$repo"
    echo ""
    echo "--- $repo ---"

    if [ ! -d "$REPO_PATH/.git" ]; then
        echo "  SKIP: Not a git repo"
        continue
    fi

    # Core structure
    check "$repo: scripts/councils/ exists" "[ -d '$REPO_PATH/scripts/councils' ]"
    check "$repo: department-council.sh exists" "[ -f '$REPO_PATH/scripts/councils/department-council.sh' ]"
    check "$repo: data/departments/ exists" "[ -d '$REPO_PATH/data/departments' ]"
    check "$repo: guardian-report.json exists" "[ -f '$REPO_PATH/data/departments/guardian-report.json' ]"
    check "$repo: forge link/dir exists" "[ -e '$REPO_PATH/scripts/forge' ]"

    # Department council files
    for dept in $DEPARTMENTS; do
        check "$repo: council-${dept}.json" "[ -f '$REPO_PATH/data/departments/council-${dept}.json' ]"
    done

    # CLAUDE.md has Forge v19
    check "$repo: CLAUDE.md has Forge v19" "grep -q 'Forge v19' '$REPO_PATH/CLAUDE.md'"
done

echo ""
echo "=========================================="
echo "  Results: $PASS passed, $FAIL failed (of $TOTAL checks)"
echo "=========================================="

if [ $FAIL -gt 0 ]; then
    echo "  Run: scripts/forge/init-repo-forge.sh <repo> to fix"
    exit 1
else
    echo "  All repos correctly forged!"
    exit 0
fi
