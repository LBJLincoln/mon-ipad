#!/bin/bash
################################################################################
# Cross-Repo Council Runner — Run department councils across ALL 8 repos
#
# Usage: cross-repo-councils.sh <dept> [--dry-run]
#
# Runs the same department council for each repo that has the council script.
# Each repo's council reads its OWN data and produces its OWN proposals.
# The shared council-template.py from mon-ipad is the engine.
################################################################################

set -uo pipefail

DEPT="${1:-}"
DRY_RUN="${2:-}"

if [ -z "$DEPT" ]; then
    echo "Usage: $0 <department> [--dry-run]"
    echo "Departments: research engineering evolution product business evaluation infra finance"
    echo ""
    echo "Runs council for ALL repos that have scripts/councils/department-council.sh"
    exit 1
fi

# Source env
source /home/termius/mon-ipad/.env.local 2>/dev/null || true

REPOS=(
    "/home/termius/mon-ipad"
    "/home/termius/nomos-nba-agent"
    "/home/termius/nomos-political-alpha"
    "/home/termius/nomos-dashboard"
    "/home/termius/rgwa"
    "/home/termius/nomos-picks"
    "/home/termius/nomos-pierre"
    "/home/termius/OddsHarvester"
)

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "[$TIMESTAMP] Cross-Repo Council — $DEPT"
echo "================================================="

SUCCESS=0
FAIL=0
SKIP=0

for repo in "${REPOS[@]}"; do
    repo_name=$(basename "$repo")
    council_script="$repo/scripts/councils/department-council.sh"

    if [ ! -f "$council_script" ]; then
        echo "  [$repo_name] SKIP — no council script"
        SKIP=$((SKIP + 1))
        continue
    fi

    echo "  [$repo_name] Running $DEPT council..."
    if bash "$council_script" "$DEPT" $DRY_RUN 2>&1 | tail -3; then
        SUCCESS=$((SUCCESS + 1))
    else
        echo "  [$repo_name] FAILED"
        FAIL=$((FAIL + 1))
    fi
    echo ""
done

echo "================================================="
echo "Results: $SUCCESS succeeded, $FAIL failed, $SKIP skipped (of ${#REPOS[@]} repos)"
echo "Timestamp: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
