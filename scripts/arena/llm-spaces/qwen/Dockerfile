# Nomos42 Qwen3-0.6B CPU LLM Space — Docker SDK (2026 SOTA upgrade)
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

ENV MODEL_REPO=unsloth/Qwen3-0.6B-GGUF \
    MODEL_FILE=Qwen3-0.6B-Q4_K_M.gguf \
    MODEL_DISPLAY=qwen3-0.6b-instruct \
    CHAT_FORMAT=chatml \
    N_CTX=4096 \
    N_THREADS=2 \
    HF_HOME=/tmp/hf-cache

CMD ["python", "app.py"]
