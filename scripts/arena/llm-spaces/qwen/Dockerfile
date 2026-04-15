# Nomos42 Qwen2.5-0.5B CPU LLM Space — Docker SDK
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

ENV MODEL_REPO=Qwen/Qwen2.5-0.5B-Instruct-GGUF \
    MODEL_FILE=qwen2.5-0.5b-instruct-q4_k_m.gguf \
    MODEL_DISPLAY=qwen2.5-0.5b-instruct \
    N_CTX=2048 \
    N_THREADS=2 \
    HF_HOME=/tmp/hf-cache

CMD ["python", "app.py"]
