#!/bin/bash
# Nomos42 Codespace LLM Server
# ============================
# Starts an OpenAI-compatible server using llama-cpp-python's built-in server.
# No extra Python file needed — llama_cpp.server is the built-in HTTP server.
#
# Usage:
#   bash setup.sh    (first time only)
#   bash serve.sh    (start server)
#
# Endpoints (once running):
#   GET  http://localhost:8080/health
#   GET  http://localhost:8080/v1/models
#   POST http://localhost:8080/v1/chat/completions

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$HOME/llm-venv"

# Load config
if [ -f "$SCRIPT_DIR/.env.llm" ]; then
    source "$SCRIPT_DIR/.env.llm"
else
    echo "ERROR: .env.llm not found. Run setup.sh first."
    exit 1
fi

# Defaults
MODEL_PATH="${MODEL_PATH:-$HOME/models/qwen3-7b-q4_k_m.gguf}"
MODEL_DISPLAY="${MODEL_DISPLAY:-Qwen/Qwen3-7B}"
N_CTX="${N_CTX:-4096}"
N_THREADS="${N_THREADS:-2}"
MAX_TOKENS="${MAX_TOKENS:-512}"
PORT="${PORT:-8080}"

if [ ! -f "$MODEL_PATH" ]; then
    echo "ERROR: Model not found at $MODEL_PATH"
    echo "Run setup.sh first to download the model."
    exit 1
fi

echo "=== Nomos42 LLM Server ==="
echo "Model:   $MODEL_PATH"
echo "Display: $MODEL_DISPLAY"
echo "Context: $N_CTX tokens"
echo "Threads: $N_THREADS"
echo "Port:    $PORT"
echo ""
echo "Starting server... (first inference may take 30s to warm up)"
echo ""

source "$VENV_DIR/bin/activate"

# llama-cpp-python ships a built-in OpenAI-compatible HTTP server
# python -m llama_cpp.server --help for all options
exec python -m llama_cpp.server \
    --model "$MODEL_PATH" \
    --model_alias "$MODEL_DISPLAY" \
    --n_ctx "$N_CTX" \
    --n_threads "$N_THREADS" \
    --n_gpu_layers 0 \
    --host 0.0.0.0 \
    --port "$PORT" \
    --chat_format chatml \
    --interrupt_requests true \
    --verbose false
