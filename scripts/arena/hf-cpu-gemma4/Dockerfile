FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    build-essential cmake git curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
# Install FastAPI + HF hub first (fast)
RUN pip install --no-cache-dir fastapi>=0.115.6 "uvicorn[standard]>=0.32.1" \
    pydantic>=2.10.4 huggingface_hub>=0.27.0

# llama-cpp-python: prefer prebuilt CPU wheel — avoids source compile OOM.
# --prefer-binary forces pip to pick a wheel even if PyPI has newer sources.
RUN pip install --no-cache-dir --prefer-binary \
    --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu \
    llama-cpp-python==0.3.7

COPY app.py .

ENV HF_HOME=/data/huggingface
RUN mkdir -p /data/huggingface && chmod -R 777 /data

EXPOSE 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
