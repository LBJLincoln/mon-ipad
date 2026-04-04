#!/usr/bin/env bash
# run-councils.sh — Run all smart councils for all projects
# Usage:
#   ./run-councils.sh            # dry-run (safe, no changes)
#   ./run-councils.sh --execute  # real execution
#   ./run-councils.sh --project nba --dept evolution --execute
#   ./run-councils.sh --list     # show all configured councils

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
COUNCIL_PY="${SCRIPT_DIR}/smart-council.py"
LOG_DIR="${ROOT}/logs/councils"
TODAY=$(date -u +"%Y-%m-%d")
LOG_FILE="${LOG_DIR}/run-${TODAY}.log"

mkdir -p "${LOG_DIR}"

# Load .env.local for API keys
if [[ -f "${ROOT}/.env.local" ]]; then
    set +u
    source "${ROOT}/.env.local" 2>/dev/null || true
    set -u
fi

echo "================================================================"
echo "Smart Council Runner — $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
echo "Root: ${ROOT}"
echo "Log:  ${LOG_FILE}"
echo "================================================================"

# Parse args
EXECUTE_FLAG=""
PROJECT_FLAG=""
DEPT_FLAG=""
LIST_FLAG=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --execute)   EXECUTE_FLAG="--execute" ;;
        --dry-run)   EXECUTE_FLAG="" ;;
        --project)   PROJECT_FLAG="--project $2"; shift ;;
        --dept)      DEPT_FLAG="--dept $2"; shift ;;
        --list)      LIST_FLAG="--list" ;;
        *) echo "Unknown arg: $1" ;;
    esac
    shift
done

if [[ -n "${LIST_FLAG}" ]]; then
    python3 "${COUNCIL_PY}" --list
    exit 0
fi

if [[ -z "${EXECUTE_FLAG}" ]]; then
    echo "MODE: DRY-RUN (pass --execute to actually run actions)"
else
    echo "MODE: EXECUTE (actions will be applied)"
fi
echo ""

# Single council run
if [[ -n "${PROJECT_FLAG}" && -n "${DEPT_FLAG}" ]]; then
    echo "Running single council: ${PROJECT_FLAG} ${DEPT_FLAG}"
    python3 "${COUNCIL_PY}" ${PROJECT_FLAG} ${DEPT_FLAG} ${EXECUTE_FLAG} 2>&1 | tee -a "${LOG_FILE}"
    exit 0
fi

# Run all councils, ordered by priority
# Priority order: infra first (keep spaces up), then evolution, research, engineering, evaluation
# Then political, cross_repo, business, finance

run_council() {
    local project="$1"
    local dept="$2"
    echo ""
    echo "--- Council: ${project}/${dept} ---"
    python3 "${COUNCIL_PY}" \
        --project "${project}" \
        --dept "${dept}" \
        ${EXECUTE_FLAG} \
        2>&1 | tee -a "${LOG_FILE}" || echo "[WARN] Council ${project}/${dept} failed"
    # Small pause between councils to respect rate limits
    sleep 5
}

# ── NBA Councils ──────────────────────────────────────────────────────────────
echo "=== NBA PROJECT ==="
run_council "nba" "infra"       # First: keep spaces up
run_council "nba" "evolution"   # Core: tune GA
run_council "nba" "research"    # New techniques
run_council "nba" "engineering" # Code quality
run_council "nba" "evaluation"  # Audit metrics

# ── Political Councils ────────────────────────────────────────────────────────
echo ""
echo "=== POLITICAL PROJECT ==="
run_council "political" "political"

# ── Cross-Repo Council ────────────────────────────────────────────────────────
echo ""
echo "=== CROSS-REPO ==="
run_council "cross_repo" "cross_repo"

# ── Business / Finance ────────────────────────────────────────────────────────
echo ""
echo "=== BUSINESS & FINANCE ==="
run_council "business" "business"
run_council "finance" "finance"

echo ""
echo "================================================================"
echo "All councils completed — $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
echo "Log: ${LOG_FILE}"
echo ""
echo "Recent log entries (last 20 lines):"
tail -20 "${LOG_FILE}" 2>/dev/null || echo "(log file not found)"
echo "================================================================"
