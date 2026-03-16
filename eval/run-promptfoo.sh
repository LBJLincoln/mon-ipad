#!/usr/bin/env bash
# run-promptfoo.sh — Run Promptfoo evaluation on Nomos RAG pipelines
# Usage:
#   ./eval/run-promptfoo.sh              # Run full eval (20 questions x 4 providers)
#   ./eval/run-promptfoo.sh --view       # Open results viewer
#   ./eval/run-promptfoo.sh --filter fin # Run only finance tests
#   ./eval/run-promptfoo.sh --provider standard-rag  # Run only standard pipeline

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG="$SCRIPT_DIR/promptfoo-config.yaml"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}=== Nomos RAG — Promptfoo Evaluation ===${NC}"
echo "Config: $CONFIG"
echo "Date:   $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""

# Check promptfoo is available
if ! command -v npx &> /dev/null; then
    echo -e "${RED}ERROR: npx not found. Install Node.js first.${NC}"
    exit 1
fi

# Parse arguments
VIEW_ONLY=false
EXTRA_ARGS=()

for arg in "$@"; do
    case "$arg" in
        --view)
            VIEW_ONLY=true
            ;;
        --filter)
            shift_next=true
            ;;
        *)
            if [[ "${shift_next:-false}" == "true" ]]; then
                EXTRA_ARGS+=("--filterPattern" "$arg")
                shift_next=false
            else
                EXTRA_ARGS+=("$arg")
            fi
            ;;
    esac
done

if [[ "$VIEW_ONLY" == "true" ]]; then
    echo -e "${YELLOW}Opening results viewer...${NC}"
    npx promptfoo@latest view
    exit 0
fi

# Run evaluation
echo -e "${YELLOW}Running evaluation (20 questions x 4 providers = 80 calls)...${NC}"
echo -e "${YELLOW}This may take 5-10 minutes depending on pipeline response times.${NC}"
echo ""

cd "$PROJECT_DIR"

npx promptfoo@latest eval \
    --config "$CONFIG" \
    --output "$SCRIPT_DIR/promptfoo-results.json" \
    "${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}"

EXIT_CODE=$?

echo ""
if [[ $EXIT_CODE -eq 0 ]]; then
    echo -e "${GREEN}=== Evaluation complete ===${NC}"
    echo "Results: $SCRIPT_DIR/promptfoo-results.json"
    echo ""
    echo "To view results interactively:"
    echo "  npx promptfoo@latest view"
    echo ""
    echo "To view a summary table:"
    echo "  npx promptfoo@latest eval --config $CONFIG --table"
else
    echo -e "${RED}=== Evaluation failed (exit code: $EXIT_CODE) ===${NC}"
fi

exit $EXIT_CODE
