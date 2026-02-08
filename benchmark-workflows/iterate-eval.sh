#!/bin/bash
# iterate-eval.sh — Run eval and auto-push results to GitHub
# Usage: ./iterate-eval.sh [iteration_number] [extra_args...]
#
# Example:
#   ./iterate-eval.sh 1 --reset
#   ./iterate-eval.sh 2 --types graph,quantitative
#   ./iterate-eval.sh 3

set -e

ITER=${1:-1}
shift 2>/dev/null || true
EXTRA_ARGS="$@"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BRANCH=$(git -C "$REPO_ROOT" branch --show-current)

echo "=============================================="
echo "  ITERATION $ITER — RAG Evaluation"
echo "  Branch: $BRANCH"
echo "  Extra args: $EXTRA_ARGS"
echo "=============================================="

cd "$REPO_ROOT/benchmark-workflows"

# Run evaluation
echo ""
echo ">>> Running evaluation..."
python3 run-comprehensive-eval.py $EXTRA_ARGS

# Commit and push results
echo ""
echo ">>> Committing results..."
cd "$REPO_ROOT"
git add docs/data.json docs/tested-questions.json logs/ 2>/dev/null || true
git diff --staged --quiet && echo "No changes to commit" && exit 0

git commit -m "$(cat <<EOF
eval: iteration $ITER results

$(python3 -c "
import json
with open('docs/data.json') as f:
    data = json.load(f)
for name, p in data['pipelines'].items():
    tested = p.get('tested', 0)
    correct = p.get('correct', 0)
    acc = f'{correct/tested*100:.1f}%' if tested > 0 else 'N/A'
    print(f'  {name}: {acc} ({correct}/{tested}) errors={p.get(\"errors\",0)}')
total_tested = sum(p.get('tested',0) for p in data['pipelines'].values())
total_correct = sum(p.get('correct',0) for p in data['pipelines'].values())
overall = f'{total_correct/total_tested*100:.1f}%' if total_tested > 0 else 'N/A'
print(f'  OVERALL: {overall} ({total_correct}/{total_tested})')
" 2>/dev/null || echo "  (results summary unavailable)")

https://claude.ai/code/session_01HBQUfUc1ftS2KZXvNwqJK7
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
echo "  ITERATION $ITER COMPLETE"
echo "=============================================="
