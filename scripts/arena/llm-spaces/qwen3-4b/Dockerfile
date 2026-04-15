# Nomos42 Qwen3-4B-Instruct CPU LLM Space — Docker SDK
FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    cmake build-essential git curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 7860

RUN useradd -m -u 1000 user
USER user

# Qwen3-4B-Instruct-2507 Q4_K_M (~2.5 GB) — top quality/size Apr 2026
# MMLU-Redux 83.1 | MMLU-Pro 61.4 | IFEval 69.5
ENV MODEL_REPO=unsloth/Qwen3-4B-Instruct-2507-GGUF \
    MODEL_FILE=Qwen3-4B-Instruct-2507-Q4_K_M.gguf \
    MODEL_DISPLAY=qwen3-4b-instruct \
    CHAT_FORMAT=chatml \
    N_CTX=2048 \
    N_THREADS=2 \
    HF_HOME=/tmp/hf-cache

CMD ["python", "app.py"]
