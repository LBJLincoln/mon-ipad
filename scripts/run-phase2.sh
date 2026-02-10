#!/bin/bash
# ============================================================
# Phase 2 Complete Runbook — GCloud Console
# ============================================================
# Copy-paste this entire script into GCloud Console.
# It handles: repo setup, data reset, Phase 2 transition,
# iterative eval with node analysis, and GitHub push.
#
# Usage:
#   bash scripts/run-phase2.sh
#   bash scripts/run-phase2.sh --quick    # Only 5q smoke test
#   bash scripts/run-phase2.sh --full     # Full 500q per pipeline
# ============================================================

set -e

MODE="${1:-full}"
REPO_DIR="$HOME/mon-ipad"
BRANCH="claude/launch-step-2-lByT2"

echo "============================================================"
echo "  PHASE 2 EVALUATION — Multi-RAG Orchestrator"
echo "  Mode: $MODE"
echo "  Branch: $BRANCH"
echo "============================================================"

# --- Step 1: Environment Variables ---
echo ""
echo ">>> Step 1: Setting environment variables..."
export SUPABASE_PASSWORD="udVECdcSnkMCAPiY"
export SUPABASE_API_KEY="sb_publishable_xUcuBcYYUO2G9Mkq_McdeQ_ocFjgonm"
export PINECONE_API_KEY="pcsk_6GzVdD_BbHsYNvpcngMqAHH5EvEa9XLnmFpEK9cx5q5xkMp72z5KFQ1q7dEjp8npWhJGBY"
export PINECONE_HOST="https://sota-rag-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
export NEO4J_PASSWORD="jV_zGdxbu-emQZM-ZSQux19pTZ5QLKejR2IHSzsbVak"
export OPENROUTER_API_KEY="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"
export N8N_API_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyMTU3NjdlMC05NThhLTRjNzQtYTY3YS1lMzM1ODA3ZWJhNjQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY5MDQ2NTExLCJleHAiOjE3NzE2Mjg0MDB9.fyOBVwb32HlzwQhSxCxoKsmMlYcxppTFGbj6S01AX2A"
export N8N_HOST="https://amoret.app.n8n.cloud"
echo "  Done."

# --- Step 2: Repository Setup ---
echo ""
echo ">>> Step 2: Setting up repository..."
if [ ! -d "$REPO_DIR" ]; then
    echo "  Cloning repository..."
    git clone https://github.com/LBJLincoln/mon-ipad.git "$REPO_DIR"
fi
cd "$REPO_DIR"

# Fetch and checkout the branch
echo "  Fetching branch $BRANCH..."
git fetch origin "$BRANCH" 2>/dev/null || git fetch origin
git checkout "$BRANCH" 2>/dev/null || git checkout -b "$BRANCH" origin/"$BRANCH"
git pull origin "$BRANCH" || true
echo "  On branch: $(git branch --show-current)"

# --- Step 3: Install Dependencies ---
echo ""
echo ">>> Step 3: Installing Python dependencies..."
pip install -q requests psycopg2-binary pinecone-client 2>/dev/null || pip3 install -q requests psycopg2-binary pinecone-client 2>/dev/null || echo "  Some pip installs skipped (may already be present)"

# --- Step 4: Clear Previous Data ---
echo ""
echo ">>> Step 4: Clearing previous evaluation data..."
python3 eval/live-writer.py --reset 2>/dev/null || echo "  live-writer reset done"

# Reset tested-questions dedup
echo '{}' > docs/tested-questions.json 2>/dev/null || true

# Clear old pipeline results
rm -rf logs/pipeline-results/* 2>/dev/null || true
rm -rf logs/iterative-eval/*.json 2>/dev/null || true
rm -rf logs/errors/* 2>/dev/null || true
rm -rf logs/executions/* 2>/dev/null || true
echo "  Data cleared."

# --- Step 5: Phase 2 Transition ---
echo ""
echo ">>> Step 5: Running Phase 2 transition..."
python3 eval/phase2-transition.py --force --auto

# --- Step 6: Regenerate status.json ---
echo ""
echo ">>> Step 6: Regenerating status.json..."
python3 eval/generate_status.py

# --- Step 7: Run Phase 2 Evaluation ---
echo ""
echo ">>> Step 7: Running Phase 2 evaluation..."

if [ "$MODE" = "--quick" ]; then
    echo "  Running SMOKE TEST only (5q per pipeline)..."
    python3 eval/iterative-eval.py \
        --dataset phase-2 \
        --force \
        --label "Phase 2 smoke test" \
        --stage 1 \
        --parallel
elif [ "$MODE" = "--full" ] || [ "$MODE" = "full" ]; then
    echo "  Running FULL iterative eval (5 → 10 → 50 → 200 → 500)..."
    echo "  This will take several hours."
    python3 eval/iterative-eval.py \
        --dataset phase-2 \
        --force \
        --label "Phase 2 full eval" \
        --no-gate \
        --parallel \
        --push
else
    echo "  Running iterative eval with gates..."
    python3 eval/iterative-eval.py \
        --dataset phase-2 \
        --force \
        --label "Phase 2 eval" \
        --parallel \
        --push
fi

# --- Step 8: Regenerate Status ---
echo ""
echo ">>> Step 8: Regenerating status after eval..."
python3 eval/generate_status.py
echo "  Status regenerated."

# --- Step 9: Git Push ---
echo ""
echo ">>> Step 9: Pushing results to GitHub..."
git add docs/data.json docs/status.json docs/tested-questions.json STATUS.md logs/
git commit -m "eval: Phase 2 evaluation results" || echo "  Nothing to commit"

# Push with retry
for attempt in 1 2 3 4; do
    echo "  Push attempt $attempt/4..."
    if git push -u origin "$BRANCH" 2>&1; then
        echo "  Push successful!"
        break
    fi
    if [ "$attempt" -lt 4 ]; then
        delay=$((2 ** attempt))
        echo "  Push failed, retrying in ${delay}s..."
        sleep $delay
    else
        echo "  Push FAILED after 4 attempts."
        echo "  Try manually: git push -u origin $BRANCH"
    fi
done

# --- Done ---
echo ""
echo "============================================================"
echo "  PHASE 2 EVALUATION COMPLETE"
echo "============================================================"
echo "  Branch: $BRANCH"
echo "  Status: $(python3 -c 'import json; d=json.load(open("docs/status.json")); print(f"Phase {d[\"phase\"][\"current\"]} — Overall {d[\"overall\"][\"accuracy\"]}%")')"
echo ""
echo "  Dashboard: https://lbjlincoln.github.io/mon-ipad/"
echo "  Results:   docs/data.json"
echo "  Logs:      logs/iterative-eval/"
echo "============================================================"
