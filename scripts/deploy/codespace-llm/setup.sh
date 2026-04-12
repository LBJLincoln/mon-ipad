#!/bin/bash
# Nomos42 Codespace LLM Setup
# ===========================
# Installs llama-cpp-python and downloads Qwen3-7B Q4_K_M GGUF (~4.7 GB)
# Target: GitHub Codespace 8 GB RAM / 2 CPU cores
#
# Usage:
#   bash setup.sh
#   bash serve.sh
#
# Model choice rationale for 8 GB Codespace:
#   Qwen3-7B Q4_K_M = ~4.7 GB on disk, ~5.2 GB RAM when loaded
#   Leaves ~2.8 GB for OS + Python + the script.
#   Best quality/size for Codespace.
#
# Alternatives (all fit in 8 GB):
#   Qwen3-4B Q4_K_M  = ~2.9 GB  (faster, lower quality)
#   Llama-3.2-8B Q4  = ~5.0 GB  (Meta model, similar quality)
#   Gemma-3-4B Q4    = ~3.0 GB  (Google model)
#   Phi-4-mini Q4    = ~2.5 GB  (Microsoft, very fast on CPU)
#
# NOT recommended for 8 GB Codespace:
#   Gemma-3-12B Q4 = ~8.1 GB (tight, may OOM under load)
#   Qwen3-14B Q4   = ~9.3 GB (won't fit)

set -e

echo "=== Nomos42 Codespace LLM Setup ==="
echo "Target: Qwen3-7B Q4_K_M (4.7 GB)"
echo ""

# ── System deps ──────────────────────────────────────────────────────────────
echo "[1/4] Installing system deps..."
sudo apt-get update -qq
sudo apt-get install -y -qq curl wget python3-pip python3-venv git

# ── Python venv ───────────────────────────────────────────────────────────────
VENV_DIR="$HOME/llm-venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "[2/4] Creating Python venv at $VENV_DIR ..."
    python3 -m venv "$VENV_DIR"
else
    echo "[2/4] Python venv already exists at $VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
pip install --quiet --upgrade pip

# Install llama-cpp-python with prebuilt CPU wheel (no compilation needed)
echo "[2/4] Installing llama-cpp-python (prebuilt CPU wheel)..."
# Use prebuilt wheel from abetlen — avoids 10-min compilation
pip install --quiet \
    "llama-cpp-python==0.3.9" \
    "huggingface_hub>=0.23.0" \
    "fastapi>=0.111.0" \
    "uvicorn>=0.30.0" \
    "pydantic>=2.7.0"

echo "      Python packages installed."

# ── Model download ────────────────────────────────────────────────────────────
MODEL_DIR="$HOME/models"
mkdir -p "$MODEL_DIR"

# Default: Qwen3-7B Q4_K_M
MODEL_REPO="${MODEL_REPO:-Qwen/Qwen3-7B-GGUF}"
MODEL_FILE="${MODEL_FILE:-qwen3-7b-q4_k_m.gguf}"
MODEL_PATH="$MODEL_DIR/$MODEL_FILE"

echo "[3/4] Checking model: $MODEL_REPO / $MODEL_FILE"

if [ -f "$MODEL_PATH" ]; then
    SIZE=$(du -sh "$MODEL_PATH" | cut -f1)
    echo "      Already downloaded: $MODEL_PATH ($SIZE)"
else
    echo "      Downloading $MODEL_FILE from HuggingFace (~4.7 GB)..."
    echo "      This may take 5-15 minutes depending on connection speed."

    python3 - <<PYEOF
from huggingface_hub import hf_hub_download
import os

model_path = hf_hub_download(
    repo_id="${MODEL_REPO}",
    filename="${MODEL_FILE}",
    local_dir="${MODEL_DIR}",
    local_dir_use_symlinks=False,
)
size_gb = os.path.getsize(model_path) / 1e9
print(f"Downloaded: {model_path} ({size_gb:.2f} GB)")
PYEOF
fi

# ── Write server script ───────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[4/4] Writing .env.llm config..."
cat > "$SCRIPT_DIR/.env.llm" <<EOF
# Nomos42 Codespace LLM Config
# Edit these to change model or parameters

MODEL_PATH=$MODEL_PATH
MODEL_DISPLAY=Qwen/Qwen3-7B
N_CTX=4096
N_THREADS=2
MAX_TOKENS=512
PORT=8080
EOF

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Start server:    bash serve.sh"
echo "Test endpoint:   curl http://localhost:8080/health"
echo ""
echo "Add to api_pool.py:"
echo '  "self_hosted_codespace": ProviderConfig('
echo '      base_url="http://localhost:8080",'
echo '      models=["Qwen/Qwen3-7B"],'
echo '      rpm=3, rpd=200, timeout=120.0,'
echo '  )'
echo ""
echo "Or if forwarding port from Codespace:"
echo '  base_url="https://YOUR-CODESPACE-8080.githubpreview.dev"'
