# Nomos42 Llama-3.2-1B CPU LLM Space — Docker SDK
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

ENV MODEL_REPO=bartowski/Llama-3.2-1B-Instruct-GGUF \
    MODEL_FILE=Llama-3.2-1B-Instruct-Q4_K_M.gguf \
    MODEL_DISPLAY=llama-3.2-1b-instruct \
    CHAT_FORMAT=llama-3 \
    N_CTX=2048 \
    N_THREADS=2 \
    HF_HOME=/tmp/hf-cache

CMD ["python", "app.py"]
