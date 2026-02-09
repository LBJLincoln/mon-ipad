#!/bin/bash
# iterate.sh — Full agentic iteration cycle
# ============================================
# Orchestrates: deploy patches → fast-iter → analyze → gate check → full eval → push
#
# Usage:
#   ./iterate.sh                              # Fast iteration only
#   ./iterate.sh --full                       # Full 200q eval after fast-iter
#   ./iterate.sh --deploy                     # Deploy patches first
#   ./iterate.sh --full --deploy --label "v6" # Full cycle with label
#   ./iterate.sh --agentic                    # Use agentic-loop.py (recommended)
#   ./iterate.sh --gate                       # Just check phase gates
#
# Examples:
#   ./iterate.sh --deploy --full --label "Iter 6: apply.py P0 fixes"
#   ./iterate.sh --agentic --max-iter 3
#   ./iterate.sh --gate --strict

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BRANCH=$(git -C "$REPO_ROOT" branch --show-current)

# Parse arguments
DEPLOY=false
FULL_EVAL=false
AGENTIC=false
GATE_ONLY=false
STRICT=false
LABEL=""
MAX_ITER=1
QUESTIONS=10
PIPELINES="standard,graph,quantitative,orchestrator"

while [[ $# -gt 0 ]]; do
    case $1 in
        --deploy) DEPLOY=true; shift;;
        --full) FULL_EVAL=true; shift;;
        --agentic) AGENTIC=true; shift;;
        --gate) GATE_ONLY=true; shift;;
        --strict) STRICT=true; shift;;
        --label) LABEL="$2"; shift 2;;
        --max-iter) MAX_ITER="$2"; shift 2;;
        --questions) QUESTIONS="$2"; shift 2;;
        --pipelines) PIPELINES="$2"; shift 2;;
        *) echo "Unknown option: $1"; exit 1;;
    esac
done

echo "=============================================="
echo "  ITERATION CYCLE"
echo "  Branch: $BRANCH"
echo "  Deploy: $DEPLOY | Full eval: $FULL_EVAL"
echo "  Label: ${LABEL:-auto}"
if [ -n "$LABEL" ]; then echo "  Label: $LABEL"; fi
echo "=============================================="

cd "$REPO_ROOT"

# Always pull latest
echo ""
echo ">>> Pulling latest..."
git pull origin "$BRANCH" 2>/dev/null || git pull origin main 2>/dev/null || true

# Gate check only
if [ "$GATE_ONLY" = true ]; then
    echo ""
    echo ">>> Checking phase gates..."
    GATE_ARGS=""
    if [ "$STRICT" = true ]; then GATE_ARGS="--strict"; fi
    python3 eval/phase-gate.py $GATE_ARGS
    exit $?
fi

# Agentic mode: use agentic-loop.py
if [ "$AGENTIC" = true ]; then
    echo ""
    echo ">>> Running agentic loop..."
    ARGS="--max-iterations $MAX_ITER"
    if [ "$FULL_EVAL" = true ]; then ARGS="$ARGS --full-eval"; fi
    if [ "$DEPLOY" = false ]; then ARGS="$ARGS --skip-deploy"; fi
    if [ -n "$LABEL" ]; then ARGS="$ARGS --label \"$LABEL\""; fi
    ARGS="$ARGS --push"
    eval python3 eval/agentic-loop.py $ARGS
    exit $?
fi

# Manual mode: step by step

# Step 1: Deploy patches
if [ "$DEPLOY" = true ]; then
    echo ""
    echo ">>> Deploying workflow patches..."
    if [ -n "$N8N_API_KEY" ]; then
        python3 workflows/improved/apply.py --deploy
    else
        echo "  N8N_API_KEY not set — local only"
        python3 workflows/improved/apply.py --local
    fi
fi

# Step 2: Fast iteration
echo ""
echo ">>> Running fast iteration (${QUESTIONS}q/pipeline)..."
FAST_ARGS="--questions $QUESTIONS --pipelines $PIPELINES"
if [ -n "$LABEL" ]; then FAST_ARGS="$FAST_ARGS --label \"$LABEL\""; fi
eval python3 eval/fast-iter.py $FAST_ARGS

# Step 3: Analyze
echo ""
echo ">>> Analyzing results..."
python3 eval/analyzer.py 2>/dev/null || true

# Step 4: Gate check
echo ""
echo ">>> Checking phase gates..."
python3 eval/phase-gate.py || true

# Step 5: Full eval (if requested)
if [ "$FULL_EVAL" = true ]; then
    echo ""
    echo ">>> Running full parallel evaluation (200q)..."
    EVAL_ARGS="--reset --types $PIPELINES"
    if [ -n "$LABEL" ]; then EVAL_ARGS="$EVAL_ARGS --label \"$LABEL\""; fi
    eval python3 eval/run-eval-parallel.py $EVAL_ARGS

    # Re-analyze and re-check gates
    echo ""
    echo ">>> Post-eval analysis..."
    python3 eval/analyzer.py 2>/dev/null || true
    python3 eval/phase-gate.py || true
fi

# Step 6: Commit and push
echo ""
echo ">>> Committing results..."
git add docs/data.json docs/tested-questions.json logs/ 2>/dev/null || true
git diff --staged --quiet && echo "No changes to commit" && exit 0

COMMIT_LABEL="${LABEL:-auto}"
git commit -m "$(cat <<EOF
eval: $COMMIT_LABEL — iteration results

$(python3 -c "
import json, sys
try:
    with open('docs/data.json') as f:
        data = json.load(f)
    iters = data.get('iterations', [])
    if iters:
        latest = iters[-1]
        for rt, rs in latest.get('results_summary', {}).items():
            print(f'  {rt}: {rs[\"accuracy_pct\"]}% ({rs[\"correct\"]}/{rs[\"tested\"]}) errors={rs[\"errors\"]}')
        print(f'  OVERALL: {latest.get(\"overall_accuracy_pct\", 0)}%')
except Exception as e:
    print(f'  (summary unavailable: {e})')
" 2>/dev/null || echo "  (results summary unavailable)")
EOF
)"

echo ""
echo ">>> Pushing to $BRANCH..."
for i in 1 2 3 4; do
    git push -u origin "$BRANCH" && break
    echo "  Push failed, retry $i/4 (waiting $((2**i))s)..."
    sleep $((2**i))
done

echo ""
echo "=============================================="
echo "  ITERATION COMPLETE"
echo "=============================================="
