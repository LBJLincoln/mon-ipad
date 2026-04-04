#!/bin/bash
################################################################################
# Run All Councils — Cross-Repo Department Councils for ALL 8 Repos
#
# Loops through every existing repo, runs ALL applicable departments in
# parallel (background processes) with a 120s timeout each, collects results,
# and writes a summary to data/departments/cross-repo-council-summary.json.
#
# Usage:
#   bash run-all-councils.sh [--dry-run]
#
# Cron (every 4h):
#   0 */4 * * * bash /home/termius/mon-ipad/scripts/councils/run-all-councils.sh >> /home/termius/mon-ipad/logs/councils.log 2>&1
################################################################################

set -uo pipefail

DRY_RUN="${1:-}"
FORGE_ROOT="/home/termius/mon-ipad"
COUNCIL_PY="$FORGE_ROOT/scripts/forge/council-template.py"
SUMMARY_FILE="$FORGE_ROOT/data/departments/cross-repo-council-summary.json"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
TIMEOUT_SECS=120
TMPDIR_BASE="/tmp/council-run-$$"

# Source env
source "$FORGE_ROOT/.env.local" 2>/dev/null || true

echo "[$TIMESTAMP] === Cross-Repo All-Council Run ==="
echo "Timeout per council: ${TIMEOUT_SECS}s"
[ "$DRY_RUN" = "--dry-run" ] && echo "MODE: DRY RUN"
echo "================================================="

# ── Department applicability per repo ──────────────────────────────────
# Maps repo name → space-separated list of applicable departments
declare -A REPO_DEPTS
REPO_DEPTS=(
    ["mon-ipad"]="research engineering evolution evaluation infra cross_repo_agents product business finance"
    ["nomos-nba-agent"]="research engineering evolution evaluation infra"
    ["nomos-political-alpha"]="research engineering evolution evaluation infra"
    ["nomos-dashboard"]="engineering product infra"
    ["rgwa"]="research engineering evolution product infra"
    ["nomos-picks"]="engineering evaluation product infra"
    ["nomos-pierre"]="engineering product business infra"
    ["OddsHarvester"]="engineering infra research"
)

# ── Discover existing repos ────────────────────────────────────────────
REPOS_ORDERED=(
    "mon-ipad"
    "nomos-nba-agent"
    "nomos-political-alpha"
    "nomos-dashboard"
    "rgwa"
    "nomos-picks"
    "nomos-pierre"
    "OddsHarvester"
)

EXISTING_REPOS=()
MISSING_REPOS=()
for repo in "${REPOS_ORDERED[@]}"; do
    if [ -d "/home/termius/$repo" ]; then
        EXISTING_REPOS+=("$repo")
    else
        MISSING_REPOS+=("$repo")
        echo "  [SKIP] $repo — directory not found"
    fi
done

echo "Repos found: ${#EXISTING_REPOS[@]} / ${#REPOS_ORDERED[@]}"
[ ${#MISSING_REPOS[@]} -gt 0 ] && echo "Missing: ${MISSING_REPOS[*]}"
echo ""

# ── Create temp dir for results ────────────────────────────────────────
mkdir -p "$TMPDIR_BASE"
mkdir -p "$(dirname "$SUMMARY_FILE")"

# ── Launch councils: repos sequentially, depts in parallel per repo ────
# This caps parallelism at ~9 processes (max depts for mon-ipad) instead
# of 38, preventing resource exhaustion on the 1 vCPU / 969 MB VM.
TOTAL_LAUNCHED=0
SUCCESS=0
FAIL=0
TIMEOUT_COUNT=0
RESULTS_JSON="{"

for repo in "${EXISTING_REPOS[@]}"; do
    repo_path="/home/termius/$repo"
    depts="${REPO_DEPTS[$repo]:-}"

    if [ -z "$depts" ]; then
        echo "  [$repo] No departments configured — skipping"
        continue
    fi

    echo "--- $repo ---"

    # Launch all departments for THIS repo in parallel
    declare -A REPO_PIDS
    declare -A REPO_OUTFILES
    for dept in $depts; do
        outfile="$TMPDIR_BASE/${repo}__${dept}.log"
        key="${repo}:${dept}"

        ARGS="--repo $repo_path --dept $dept"
        [ "$DRY_RUN" = "--dry-run" ] && ARGS="$ARGS --dry-run"

        (
            timeout "$TIMEOUT_SECS" python3 "$COUNCIL_PY" $ARGS 2>&1
            echo "EXIT_CODE=$?"
        ) > "$outfile" 2>&1 &

        REPO_PIDS[$key]=$!
        REPO_OUTFILES[$key]="$outfile"
        TOTAL_LAUNCHED=$((TOTAL_LAUNCHED + 1))
    done

    # Wait for all departments of this repo to finish before moving to next
    for key in $(echo "${!REPO_PIDS[@]}" | tr ' ' '\n' | sort); do
        pid=${REPO_PIDS[$key]}
        outfile=${REPO_OUTFILES[$key]}
        dept="${key##*:}"

        wait "$pid" 2>/dev/null
        exit_code=$?

        # Parse exit code from output
        actual_exit=0
        if [ -f "$outfile" ]; then
            last_line=$(tail -1 "$outfile" 2>/dev/null || echo "")
            if echo "$last_line" | grep -q "EXIT_CODE="; then
                actual_exit=$(echo "$last_line" | sed 's/EXIT_CODE=//')
            else
                actual_exit=$exit_code
            fi
        fi

        # Determine status
        if [ "$actual_exit" = "124" ]; then
            status="TIMEOUT"
            TIMEOUT_COUNT=$((TIMEOUT_COUNT + 1))
        elif [ "$actual_exit" = "0" ]; then
            status="OK"
            SUCCESS=$((SUCCESS + 1))
        else
            status="FAIL"
            FAIL=$((FAIL + 1))
        fi

        # Extract last meaningful line for summary
        summary_line=""
        if [ -f "$outfile" ]; then
            summary_line=$(grep -v "^EXIT_CODE=" "$outfile" | grep -v "^$" | tail -1 2>/dev/null || echo "")
        fi

        echo "  [$repo:$dept] $status (exit=$actual_exit)"

        # Build JSON result entry
        safe_summary=$(echo "$summary_line" | sed 's/"/\\"/g' | head -c 200)
        RESULTS_JSON="${RESULTS_JSON}\"${key}\":{\"status\":\"${status}\",\"exit_code\":${actual_exit},\"summary\":\"${safe_summary}\"},"
    done

    # Clean up associative arrays for next repo
    unset REPO_PIDS
    unset REPO_OUTFILES
    echo ""
done

# ── Write summary JSON ─────────────────────────────────────────────────
RESULTS_JSON="${RESULTS_JSON%,}}"  # Remove trailing comma, close object

END_TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

DRY_RUN_BOOL=$([ "$DRY_RUN" = "--dry-run" ] && echo "True" || echo "False")
MISSING_LIST=$(printf '%s\n' "${MISSING_REPOS[@]}" 2>/dev/null | python3 -c "import sys,json; print(json.dumps([l.strip() for l in sys.stdin if l.strip()]))" 2>/dev/null || echo '[]')

python3 -c "
import json, sys

results_raw = '''${RESULTS_JSON}'''
try:
    results = json.loads(results_raw)
except:
    results = {'parse_error': 'Failed to parse results JSON'}

# Organize by repo
by_repo = {}
for key, val in results.items():
    if ':' in key:
        repo, dept = key.split(':', 1)
        if repo not in by_repo:
            by_repo[repo] = {}
        by_repo[repo][dept] = val

summary = {
    'timestamp': '${TIMESTAMP}',
    'end_timestamp': '${END_TIMESTAMP}',
    'total_launched': ${TOTAL_LAUNCHED},
    'success': ${SUCCESS},
    'failed': ${FAIL},
    'timeout': ${TIMEOUT_COUNT},
    'repos_found': ${#EXISTING_REPOS[@]},
    'repos_missing': json.loads('${MISSING_LIST}'),
    'dry_run': ${DRY_RUN_BOOL},
    'by_repo': by_repo,
    'flat_results': results
}

with open('${SUMMARY_FILE}', 'w') as f:
    json.dump(summary, f, indent=2)
print(f'Summary written to ${SUMMARY_FILE}')
" 2>&1

echo ""
echo "================================================="
echo "DONE: $SUCCESS OK, $FAIL failed, $TIMEOUT_COUNT timeout (of $TOTAL_LAUNCHED launched)"
echo "Repos: ${#EXISTING_REPOS[@]} found, ${#MISSING_REPOS[@]} missing"
echo "Summary: $SUMMARY_FILE"
echo "End: $END_TIMESTAMP"

# ── Cleanup temp files ─────────────────────────────────────────────────
rm -rf "$TMPDIR_BASE"

# Exit with error if any failures
[ "$FAIL" -gt 0 ] || [ "$TIMEOUT_COUNT" -gt 0 ] && exit 1
exit 0
