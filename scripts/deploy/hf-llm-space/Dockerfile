# Nomos42 LLM Space — Docker SDK on HF Spaces
# Python 3.11 + glibc (Debian Bookworm) — avoids musl/Alpine issues with llama-cpp-python
# Build time: ~5-8 min (one-time, Docker layer cached)

FROM python:3.11-slim-bookworm

# Install build dependencies for llama-cpp-python source compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    cmake \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies (llama-cpp-python compiles from source = proper glibc build)
COPY requirements-docker.txt .
RUN pip install --no-cache-dir -r requirements-docker.txt

# Copy application
COPY app.py .

# HF Spaces requires port 7860
EXPOSE 7860

# Run as non-root for HF Spaces compatibility
RUN useradd -m -u 1000 user
USER user

CMD ["python", "app.py"]
