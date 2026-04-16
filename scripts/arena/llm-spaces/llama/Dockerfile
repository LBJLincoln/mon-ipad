# Nomos42 Dolphin3.0-Llama3.2-3B CPU LLM Space — Docker SDK (2026 SOTA upgrade, JSON/function-calling tuned)
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

ENV MODEL_REPO=bartowski/Dolphin3.0-Llama3.2-3B-GGUF \
    MODEL_FILE=Dolphin3.0-Llama3.2-3B-Q4_K_M.gguf \
    MODEL_DISPLAY=dolphin3-llama3.2-3b \
    CHAT_FORMAT=llama-3 \
    N_CTX=4096 \
    N_THREADS=2 \
    HF_HOME=/tmp/hf-cache

CMD ["python", "app.py"]
