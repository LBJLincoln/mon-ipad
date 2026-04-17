#!/bin/bash
# Deploy refreshed self-host LLM Spaces + gateway + TFs + councils via git subtree push.
# Called ad-hoc after bumping model weights in scripts/arena/llm-spaces/*/Dockerfile.
#
# Requires: HF_TOKEN_LLM (Nomos42 spaces), HF_TOKEN (LBJLincoln26 gateway+TFs, TESTforge42 councils)
# Run from repo root: bash scripts/deploy-llm-spaces.sh

set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
source .env.local

NOMOS=${HF_TOKEN_LLM:?missing HF_TOKEN_LLM}
LBJ26=${HF_TOKEN_NBA:?missing HF_TOKEN_NBA}
FORGE=${HF_TOKEN_COUNCILS:-$HF_TOKEN}

# Map: local_prefix -> hf_account hf_repo token
declare -a TARGETS=(
  "scripts/arena/llm-spaces/qwen Nomos42 qwen25-05b-cpu $NOMOS"
  "scripts/arena/llm-spaces/llama Nomos42 llama32-1b-cpu $NOMOS"
  "scripts/arena/llm-spaces/gemma Nomos42 gemma2-2b-cpu $NOMOS"
  "scripts/arena/hf-cpu-gemma4 Nomos42 nomos42-llm-cpu $NOMOS"
  "scripts/arena/hf-llm-gateway LBJLincoln26 llm-gateway $LBJ26"
  "scripts/arena/hf-llm-trading-floor LBJLincoln26 nba-llm-trading-floor $LBJ26"
  "scripts/arena/hf-political-trading-floor LBJLincoln26 political-llm-trading-floor $LBJ26"
)

for entry in "${TARGETS[@]}"; do
  read -r prefix account repo token <<<"$entry"
  url="https://${account}:${token}@huggingface.co/spaces/${account}/${repo}"
  label="${account}/${repo}"
  echo "=== subtree push $prefix -> $label ==="
  tmp_branch="deploy-$(basename "$prefix")-$$"
  git subtree split --prefix="$prefix" -b "$tmp_branch" >/dev/null
  git push "$url" "$tmp_branch":main --force
  git branch -D "$tmp_branch" >/dev/null
done

echo "=== all HF Space pushes complete ==="
