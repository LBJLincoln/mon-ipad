#!/usr/bin/env bash
# deploy-llm-space.sh — Deploy Qwen3-1.7B CPU LLM Space to HuggingFace
# ======================================================================
# Creates + uploads a self-hosted LLM Space on HuggingFace (free CPU tier).
# Once running, set SELF_HOSTED_HF_URL in .env.local to activate it as
# a fallback provider in api_pool.py.
#
# Usage:
#   ./scripts/deploy/deploy-llm-space.sh [ACCOUNT]
#   ACCOUNT: nomos42 (default) | lbjlincoln | lbjlincoln26
#
# Prerequisites: huggingface-cli installed + logged in (or HF_TOKEN_LLM set)
#
# The Space runs Qwen3-1.7B Q4_K_M via llama.cpp for ~12 tok/s on CPU.
# ~512 tok response takes ~40s. Rate: ~4 req/min, RPD ~288.

set -euo pipefail

ACCOUNT="${1:-nomos42}"
SPACE_NAME="nomos42-llm-cpu"
SPACE_ID="${ACCOUNT}/${SPACE_NAME}"
DEPLOY_DIR="$(dirname "$0")/hf-llm-space"

# Pick the right HF token based on account
case "$ACCOUNT" in
  nomos42)      HF_TOKEN_USE="${HF_TOKEN_LLM:-${HF_TOKEN:-}}" ;;
  lbjlincoln)   HF_TOKEN_USE="${HF_TOKEN:-}" ;;
  lbjlincoln26) HF_TOKEN_USE="${HF_TOKEN_NBA:-}" ;;
  *)            echo "Unknown account: $ACCOUNT"; exit 1 ;;
esac

if [ -z "$HF_TOKEN_USE" ]; then
  echo "ERROR: No HF token found for account $ACCOUNT"
  echo "Set HF_TOKEN_LLM (nomos42), HF_TOKEN (lbjlincoln), or HF_TOKEN_NBA (lbjlincoln26)"
  exit 1
fi

export HUGGING_FACE_HUB_TOKEN="$HF_TOKEN_USE"

echo "=== Deploy LLM Space ==="
echo "  Space: $SPACE_ID"
echo "  Source: $DEPLOY_DIR"
echo ""

# Step 1: Create the Space (gradio SDK, CPU Basic)
echo "[1/4] Creating HuggingFace Space..."
huggingface-cli repo create "$SPACE_NAME" \
  --type space \
  --space-sdk gradio \
  --organization "$ACCOUNT" \
  2>/dev/null || echo "  (Space may already exist — continuing)"

# Step 2: Upload files from the deploy directory
echo "[2/4] Uploading app files..."
huggingface-cli upload \
  "${ACCOUNT}/${SPACE_NAME}" \
  "$DEPLOY_DIR/" \
  . \
  --repo-type space

# Step 3: Set environment variables (GGUF model config)
echo "[3/4] Setting Space env vars..."
curl -s -X POST \
  "https://huggingface.co/api/spaces/${SPACE_ID}/secrets" \
  -H "Authorization: Bearer ${HF_TOKEN_USE}" \
  -H "Content-Type: application/json" \
  -d '{"key":"GGUF_REPO","value":"bartowski/Qwen3-1.7B-GGUF"}' \
  > /dev/null

curl -s -X POST \
  "https://huggingface.co/api/spaces/${SPACE_ID}/secrets" \
  -H "Authorization: Bearer ${HF_TOKEN_USE}" \
  -H "Content-Type: application/json" \
  -d '{"key":"GGUF_FILE","value":"Qwen3-1.7B-Q4_K_M.gguf"}' \
  > /dev/null

# Step 4: Print activation instructions
echo "[4/4] Done!"
echo ""
echo "=== ACTIVATION ==="
echo "Space URL: https://${ACCOUNT}-${SPACE_NAME}.hf.space"
echo ""
echo "Once the Space is running (check https://huggingface.co/spaces/${SPACE_ID}),"
echo "add this to /home/termius/mon-ipad/.env.local:"
echo ""
echo "  export SELF_HOSTED_HF_URL=\"https://${ACCOUNT}-${SPACE_NAME}.hf.space\""
echo ""
echo "Then verify with:"
echo "  cd /home/termius/mon-ipad && python3 -c \""
echo "  import sys; sys.path.insert(0, 'scripts/arena')"
echo "  from api_pool import get_completion"
echo "  print(get_completion('self_hosted_hf:Qwen/Qwen3-1.7B', 'Say hi in 3 words'))"
echo "  \""
