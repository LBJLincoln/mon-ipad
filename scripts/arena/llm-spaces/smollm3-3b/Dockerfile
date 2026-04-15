# Nomos42 SmolLM3-3B CPU LLM Space — Docker SDK
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

# SmolLM3-3B Q4_K_M (~1.9 GB) — 128K ctx, dual think/no-think, 6 languages
# MMLU 68.9 beats Llama-3.2-3B (66.5)
ENV MODEL_REPO=ggml-org/SmolLM3-3B-GGUF \
    MODEL_FILE=SmolLM3-3B-Q4_K_M.gguf \
    MODEL_DISPLAY=smollm3-3b \
    CHAT_FORMAT=chatml \
    N_CTX=2048 \
    N_THREADS=2 \
    HF_HOME=/tmp/hf-cache

CMD ["python", "app.py"]
