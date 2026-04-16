# Nomos42 Gemma-4-E2B CPU LLM Space — Docker SDK (2026 SOTA, Apr 2 2026 release, native JSON)
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

ENV MODEL_REPO=ggml-org/gemma-4-e2b-it-GGUF \
    MODEL_FILE=gemma-4-e2b-it-Q4_K_M.gguf \
    MODEL_DISPLAY=gemma-4-e2b-it \
    CHAT_FORMAT=gemma \
    N_CTX=4096 \
    N_THREADS=2 \
    HF_HOME=/tmp/hf-cache

CMD ["python", "app.py"]
