# Nomos42 Gemma-3-4B-it CPU LLM Space — Docker SDK
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

# Gemma-3-4B-it Q4_K_M (~2.5 GB) — matches Gemma-2-27B-IT on chat/math/IF
# 128K ctx, cleanest tool-call schema
ENV MODEL_REPO=unsloth/gemma-3-4b-it-GGUF \
    MODEL_FILE=gemma-3-4b-it-Q4_K_M.gguf \
    MODEL_DISPLAY=gemma-3-4b-it \
    CHAT_FORMAT=gemma \
    N_CTX=2048 \
    N_THREADS=2 \
    HF_HOME=/tmp/hf-cache

CMD ["python", "app.py"]
