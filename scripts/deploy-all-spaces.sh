#!/bin/bash
################################################################################
# Deploy engine v3.1-58cat to ALL HF Spaces (NBA + Political)
# Run from VM where .env.local has tokens:
#   bash scripts/deploy-all-spaces.sh
#
# NBA Spaces (token mapping):
#   S10 Nomos42/nba-quant          → HF_TOKEN_LLM
#   S11 Nomos42/nba-quant-2        → HF_TOKEN_LLM
#   S12 Nomos42/nba-evo-3          → HF_TOKEN_LLM
#   S13 Nomos42/nba-evo-4          → HF_TOKEN_LLM
#   S14 Nomos42/nba-evo-5          → HF_TOKEN_LLM
#   S15 Nomos42/nba-evo-6          → HF_TOKEN_LLM
#   S16 LBJLincoln26/nba-evo-s16   → HF_TOKEN_NBA
#   S17 LBJLincoln26/nba-evo-s17   → HF_TOKEN_NBA
#   S18 TESTforge42/nba-evo-s18    → HF_TOKEN_COUNCILS
#   S19 TESTforge42/nba-evo-s19    → HF_TOKEN_COUNCILS
#   S20 LBJLincoln26/nba-evo-s20   → HF_TOKEN_NBA (isotonic_cpcv)
#   S21 LBJLincoln26/nba-evo-s21   → HF_TOKEN_NBA (darwinian_weights)
#   S22 TESTforge42/nba-evo-s22    → HF_TOKEN_COUNCILS (venn_abers_fusion)
#
# Political Spaces:
#   P1 Nomos42/political-alpha      → HF_TOKEN_LLM
#   P2 Nomos42/political-alpha-2    → HF_TOKEN_LLM
#   P3 LBJLincoln/political-alpha-3 → HF_TOKEN
#   P4 LBJLincoln/political-alpha-4 → HF_TOKEN
#   P5 LBJLincoln/political-alpha-5 → HF_TOKEN (catboost_specialist)
#   P6 LBJLincoln/political-alpha-6 → HF_TOKEN (extra_trees_specialist)
#   P7 LBJLincoln/political-alpha-7 → HF_TOKEN (gradient_boost_specialist)
#   P8 LBJLincoln/political-alpha-8 → HF_TOKEN (ensemble_stacking)
################################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
NBA_REPO="${ROOT}/../nomos-nba-agent"
POL_REPO="${ROOT}/../nomos-political-alpha"

# Load tokens
if [ -f "${ROOT}/.env.local" ]; then
    source "${ROOT}/.env.local"
    echo "Tokens loaded from .env.local"
else
    echo "ERROR: .env.local not found at ${ROOT}/.env.local"
    exit 1
fi

# Verify required tokens
for var in HF_TOKEN HF_TOKEN_NBA HF_TOKEN_LLM; do
    if [ -z "${!var:-}" ]; then
        echo "WARNING: $var not set — spaces using that token will be skipped"
    else
        echo "  $var: ${!var:0:12}***"
    fi
done

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║   Deploying engine v3.1-58cat to all HF Spaces      ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# Pull latest code first
echo "── Pulling latest engine from git ──"
cd "$NBA_REPO" && git pull origin main && echo "NBA repo: OK"
cd "$POL_REPO" && git pull origin main && echo "Political repo: OK"
echo ""

deploy_nba() {
    local space_id="$1"
    local role="$2"
    local token_var="$3"
    local token="${!token_var:-}"

    if [ -z "$token" ]; then
        echo "  SKIP $space_id — $token_var not set"
        return
    fi

    echo "  Deploying $space_id ($role)..."
    cd "$NBA_REPO"
    if python3 hf-space/deploy_island.py "$space_id" "$role" "$token_var" 2>&1 | tail -5; then
        echo "  ✓ $space_id deployed"
    else
        echo "  ✗ $space_id FAILED"
    fi
    sleep 3  # Rate limit between deployments
}

deploy_political() {
    local space_id="$1"
    local token_var="$2"
    local token="${!token_var:-}"

    if [ -z "$token" ]; then
        echo "  SKIP $space_id — $token_var not set"
        return
    fi

    echo "  Deploying political $space_id..."
    cd "$POL_REPO"
    # Political engine uses its own deploy or direct huggingface push
    python3 -c "
import os, sys
sys.path.insert(0, '.')
from pathlib import Path
from huggingface_hub import HfApi, CommitOperationAdd

token = os.environ.get('${token_var}', '')
space_id = '${space_id}'
local_dir = Path('hf-space')
skip = {'__pycache__', '.pyc', '.git', 'deploy_island.py'}

api = HfApi(token=token)
ops = []
for fp in local_dir.rglob('*'):
    if fp.is_dir() or any(s in str(fp) for s in skip):
        continue
    rel = fp.relative_to(local_dir)
    ops.append(CommitOperationAdd(path_in_repo=str(rel), path_or_fileobj=str(fp)))

print(f'  Uploading {len(ops)} files to {space_id}...')
api.create_commit(
    repo_id=space_id, repo_type='space', operations=ops,
    commit_message='feat: engine v3.11-political-31cat-cmd-seq-cal (cycle 83)',
)
print('  Upload OK')
" && echo "  ✓ $space_id deployed" || echo "  ✗ $space_id FAILED"
    sleep 3
}

echo "── NBA Islands ──"
deploy_nba "Nomos42/nba-quant"    "exploitation"          "HF_TOKEN_LLM"
deploy_nba "Nomos42/nba-quant-2"  "exploration"           "HF_TOKEN_LLM"
deploy_nba "Nomos42/nba-evo-3"    "extra_trees_specialist" "HF_TOKEN_LLM"
deploy_nba "Nomos42/nba-evo-4"    "catboost_specialist"   "HF_TOKEN_LLM"
deploy_nba "Nomos42/nba-evo-5"    "lightgbm_specialist"   "HF_TOKEN_LLM"
deploy_nba "Nomos42/nba-evo-6"    "wide_search"           "HF_TOKEN_LLM"
deploy_nba "LBJLincoln26/nba-evo-s16" "exploration"       "HF_TOKEN_NBA"
deploy_nba "LBJLincoln26/nba-evo-s17" "wide_search"       "HF_TOKEN_NBA"
deploy_nba "TESTforge42/nba-evo-s18"  "catboost_specialist" "HF_TOKEN_COUNCILS"
deploy_nba "TESTforge42/nba-evo-s19"  "wide_search"         "HF_TOKEN_COUNCILS"
deploy_nba "LBJLincoln26/nba-evo-s20" "isotonic_cpcv"       "HF_TOKEN_NBA"
deploy_nba "LBJLincoln26/nba-evo-s21" "darwinian_weights"   "HF_TOKEN_NBA"
deploy_nba "TESTforge42/nba-evo-s22"  "venn_abers_fusion"   "HF_TOKEN_COUNCILS"

echo ""
echo "── Political Islands ──"
deploy_political "Nomos42/political-alpha"    "HF_TOKEN_LLM"
deploy_political "Nomos42/political-alpha-2"  "HF_TOKEN_LLM"
deploy_political "LBJLincoln/political-alpha-3" "HF_TOKEN"
deploy_political "LBJLincoln/political-alpha-4" "HF_TOKEN"
deploy_political "LBJLincoln/political-alpha-5" "HF_TOKEN"
deploy_political "LBJLincoln/political-alpha-6" "HF_TOKEN"
deploy_political "LBJLincoln/political-alpha-7" "HF_TOKEN"
deploy_political "LBJLincoln/political-alpha-8" "HF_TOKEN"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║   All deployments complete!                          ║"
echo "║   Spaces will restart automatically after push.     ║"
echo "║   Monitor: bash scripts/keepalive-spaces.sh         ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "Deployed:"
echo "  NBA: engine v3.1-58cat (6338+ features, Cat55-58)"
echo "  Political: engine v3.11-31cat (Cat31-33 added)"
