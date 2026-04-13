#!/bin/bash
# ═══════════════════════════════════════════════════════════
# Karpathy Codespace Runner — Continuous tuning on GitHub Codespace
# ═══════════════════════════════════════════════════════════
# Runs continuously on Codespace (2 cores, 8GB RAM, 32GB storage).
# Much better than VM (1 vCPU, 969MB) for training.
#
# Usage:
#   bash scripts/karpathy/codespace-runner.sh          # 100 iterations NBA + Political
#   bash scripts/karpathy/codespace-runner.sh --loop    # Continuous loop until stopped
# ═══════════════════════════════════════════════════════════

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

LOOP_MODE=false
if [[ "${1:-}" == "--loop" ]]; then
    LOOP_MODE=true
fi

echo "═══════════════════════════════════════════════════════"
echo "KARPATHY CODESPACE RUNNER — $(date -u +"%Y-%m-%d %H:%M UTC")"
echo "Machine: $(nproc) cores, $(free -h | awk '/Mem:/ {print $2}') RAM"
echo "Mode: $([ "$LOOP_MODE" = true ] && echo 'CONTINUOUS LOOP' || echo 'SINGLE RUN')"
echo "═══════════════════════════════════════════════════════"

# Install deps if missing
python3 -c "import sklearn" 2>/dev/null || pip install -q scikit-learn lightgbm numpy

run_iteration() {
    echo ""
    echo "── NBA Karpathy (50 iterations) ──"
    python3 scripts/karpathy/nba_iterate.py --iterations 50 2>&1 | tail -20

    echo ""
    echo "── Political Karpathy (50 iterations) ──"
    python3 scripts/karpathy/political_iterate.py --iterations 50 2>&1 | tail -20

    # Push results back to repo
    git add data/karpathy/ 2>/dev/null || true
    if ! git diff --cached --quiet 2>/dev/null; then
        git commit -m "karpathy: codespace tuning $(date -u +%Y-%m-%dT%H:%MZ)" --quiet 2>/dev/null || true
        git pull --rebase --quiet origin main 2>/dev/null || true
        git push --quiet 2>/dev/null || echo "Push failed (will retry next iteration)"
    fi
}

if [ "$LOOP_MODE" = true ]; then
    while true; do
        run_iteration
        echo ""
        echo "── Sleeping 5 min before next round ──"
        sleep 300
    done
else
    run_iteration
fi

echo ""
echo "═══════════════════════════════════════════════════════"
echo "DONE"
echo "═══════════════════════════════════════════════════════"
