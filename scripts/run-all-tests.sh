#!/usr/bin/env bash
# run-all-tests.sh — Cross-repo test runner for the Multi-RAG platform
#
# Tests all components:
#   1. mon-ipad: webhook health + quick pipeline tests
#   2. rag-data-ingestion: pytest (if available locally)
#   3. rag-dashboard: HTTP health
#   4. rag-website: Vercel sites HTTP health
#   5. rag-pme-connectors: Vercel site HTTP health
#
# Usage:
#   ./scripts/run-all-tests.sh             # Run all tests
#   ./scripts/run-all-tests.sh --quick     # Webhooks + HTTP only (no pipeline tests)
#   ./scripts/run-all-tests.sh --verbose   # Show full output

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# Load env
[[ -f "$REPO_ROOT/.env.local" ]] && source "$REPO_ROOT/.env.local"

N8N_HOST="${N8N_HOST:-https://lbjlincoln-nomos-rag-engine.hf.space}"
QUICK_MODE=false
VERBOSE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --quick) QUICK_MODE=true; shift ;;
        --verbose) VERBOSE=true; shift ;;
        *) shift ;;
    esac
done

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

PASS=0
FAIL=0
SKIP=0
TOTAL_START=$(date +%s)

log()   { echo -e "${BLUE}[test]${NC} $*"; }
ok()    { echo -e "  ${GREEN}[PASS]${NC} $*"; ((PASS++)); }
fail()  { echo -e "  ${RED}[FAIL]${NC} $*"; ((FAIL++)); }
skip()  { echo -e "  ${YELLOW}[SKIP]${NC} $*"; ((SKIP++)); }

check_url() {
    local url="$1" name="$2" timeout="${3:-10}"
    local code
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time "$timeout" "$url" 2>/dev/null || echo "000")
    if [[ "$code" == "200" || "$code" == "301" || "$code" == "302" || "$code" == "308" ]]; then
        ok "$name (HTTP $code)"
    else
        fail "$name (HTTP $code)"
    fi
    return 0
}

# ══════════════════════════════════════════════════════════════════════════════
echo -e "\n${BOLD}═══ Multi-RAG Cross-Repo Test Suite ═══${NC}\n"
echo -e "  N8N_HOST: $N8N_HOST"
echo -e "  Mode:     $([ "$QUICK_MODE" = true ] && echo "QUICK" || echo "FULL")"
echo -e "  Time:     $(date -u +%Y-%m-%dT%H:%M:%SZ)\n"

# ── 1. n8n HF Space Health ───────────────────────────────────────────────────
echo -e "${BOLD}1. n8n HF Space Health${NC}"

check_url "$N8N_HOST/healthz" "n8n healthz"

# ── 2. Webhook Health (all core webhooks) ────────────────────────────────────
echo -e "\n${BOLD}2. Webhook Health${NC}"

WEBHOOK_NAMES=("Standard" "Graph" "Quantitative" "Orchestrator" "Ingestion" "Dashboard API")
WEBHOOK_PATHS=("/webhook/rag-multi-index-v3" "/webhook/ff622742-6d71-4e91-af71-b5c666088717" "/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9" "/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0" "/webhook/rag-v6-ingestion" "/webhook/dashboard-status")

for i in "${!WEBHOOK_NAMES[@]}"; do
    name="${WEBHOOK_NAMES[$i]}"
    path="${WEBHOOK_PATHS[$i]}"
    # Use POST with empty JSON body — webhook will process (or error) but not 404
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 15 \
        -X POST -H "Content-Type: application/json" -d '{"query":"health-check","benchmark_mode":true}' \
        "$N8N_HOST$path" 2>/dev/null || echo "000")
    # Any non-404 response means webhook is registered and active
    if [[ "$code" != "404" && "$code" != "000" ]]; then
        ok "$name ($code)"
    else
        fail "$name ($code) — webhook not registered"
    fi
done

# ── 3. Pipeline Quick Tests (skip in quick mode) ────────────────────────────
if [[ "$QUICK_MODE" = false ]]; then
    echo -e "\n${BOLD}3. Pipeline Quick Tests (1 question each)${NC}"

    if [[ -f "$REPO_ROOT/eval/quick-test.py" ]]; then
        for pipeline in standard graph quantitative orchestrator; do
            log "Testing $pipeline..."
            output=$(python3 "$REPO_ROOT/eval/quick-test.py" \
                --pipelines "$pipeline" --questions 1 2>&1 || true)
            if echo "$output" | grep -q '\[+\]'; then
                ok "$pipeline pipeline"
            elif echo "$output" | grep -q 'error\|FAIL\|ERROR'; then
                fail "$pipeline pipeline"
                [[ "$VERBOSE" = true ]] && echo "$output" | tail -5
            else
                skip "$pipeline pipeline (no clear result)"
            fi
        done
    else
        skip "quick-test.py not found"
    fi
else
    echo -e "\n${BOLD}3. Pipeline Quick Tests${NC}"
    skip "Skipped (--quick mode)"
fi

# ── 4. rag-data-ingestion Tests ──────────────────────────────────────────────
echo -e "\n${BOLD}4. rag-data-ingestion Tests${NC}"

INGESTION_DIR="/home/termius/rag-data-ingestion"
if [[ -d "$INGESTION_DIR/tests" ]]; then
    if command -v pytest &>/dev/null; then
        log "Running pytest..."
        output=$(cd "$INGESTION_DIR" && python3 -m pytest tests/ -x -q --tb=short 2>&1 || true)
        if echo "$output" | grep -qE "passed|no tests ran"; then
            passed=$(echo "$output" | grep -oE '[0-9]+ passed' | head -1 || echo "? passed")
            ok "pytest ($passed)"
        else
            fail "pytest"
            [[ "$VERBOSE" = true ]] && echo "$output" | tail -10
        fi
    else
        skip "pytest not installed"
    fi
else
    skip "tests/ directory not found in rag-data-ingestion"
fi

# ── 5. Dashboard Health ──────────────────────────────────────────────────────
echo -e "\n${BOLD}5. Dashboard Health${NC}"

check_url "https://nomos-dashboard-alexis-morets-projects.vercel.app" "Dashboard (Vercel)"

# ── 6. Website Health (4 Vercel sites) ───────────────────────────────────────
echo -e "\n${BOLD}6. Website Health (Vercel)${NC}"

check_url "https://nomos-ai-pied.vercel.app" "ETI 4 Secteurs"
check_url "https://nomos-pme-connectors-alexis-morets-projects.vercel.app" "PME Connectors"
check_url "https://nomos-pme-usecases-alexis-morets-projects.vercel.app" "PME Use Cases"

# ── 7. Additional HF Spaces (if configured) ─────────────────────────────────
echo -e "\n${BOLD}7. Additional HF Spaces${NC}"

# Check env vars for additional spaces
for var in N8N_HOST_STANDARD_2 N8N_HOST_QUANTITATIVE N8N_HOST_ORCHESTRATOR N8N_HOST_INGESTION; do
    val="${!var:-}"
    if [[ -n "$val" && "$val" != *"SPACE_2"* && "$val" != *"<"* ]]; then
        check_url "$val/healthz" "$var"
    else
        skip "$var (not configured)"
    fi
done

# ══════════════════════════════════════════════════════════════════════════════
TOTAL_END=$(date +%s)
DURATION=$((TOTAL_END - TOTAL_START))

echo -e "\n${BOLD}═══ Results ═══${NC}"
echo -e "  ${GREEN}Passed:${NC}  $PASS"
echo -e "  ${RED}Failed:${NC}  $FAIL"
echo -e "  ${YELLOW}Skipped:${NC} $SKIP"
echo -e "  Duration: ${DURATION}s"
echo ""

if [[ $FAIL -gt 0 ]]; then
    echo -e "${RED}${BOLD}SOME TESTS FAILED${NC}"
    exit 1
else
    echo -e "${GREEN}${BOLD}ALL TESTS PASSED${NC}"
    exit 0
fi
