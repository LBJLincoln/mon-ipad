# Nomos42 Fin-R1-7B CPU LLM Space — Docker SDK
# Finance-pretrained reasoning LLM (SUFE-AIFLM-Lab arXiv 2503.16252)
# Qwen2.5-7B base + Fin-R1-Data 60k CoT + GRPO-RL
# Matches DeepSeek-R1 on FinQA/ConvFinQA/FinanceIQ at 7B
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

# Fin-R1 Q4_K_M (~4.5 GB) — finance CoT + reasoning
# FinQA 76.0 | ConvFinQA 85.0 | FinanceIQ 73.3 (matches DeepSeek-R1)
# Apache 2.0, CPU-friendly on 2vCPU/16GB HF Space
ENV MODEL_REPO=mradermacher/Fin-R1-GGUF \
    MODEL_FILE=Fin-R1.Q4_K_M.gguf \
    MODEL_DISPLAY=fin-r1-7b \
    CHAT_FORMAT=chatml \
    N_CTX=4096 \
    N_THREADS=2 \
    HF_HOME=/tmp/hf-cache

CMD ["python", "app.py"]
