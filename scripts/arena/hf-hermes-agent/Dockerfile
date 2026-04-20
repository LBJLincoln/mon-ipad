FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git bash ca-certificates sqlite3 build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
USER user
WORKDIR /home/user/app

ENV PATH=/home/user/.local/bin:$PATH \
    HERMES_CONFIG_DIR=/data/.hermes \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/data

COPY --chown=user requirements.txt /home/user/app/
RUN pip install --no-cache-dir --user -r requirements.txt

# Best-effort Hermes install — do NOT fail the build if the official installer
# is unreachable from inside the HF builder. The RPC server stub handles
# `hermes` binary missing at runtime and returns a structured error.
RUN set -e; \
    curl -fsSL --max-time 30 https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh -o /tmp/hermes-install.sh 2>/dev/null \
      && bash /tmp/hermes-install.sh || echo "[warn] hermes install script unreachable — RPC server will report binary_missing=true" ; \
    pip install --no-cache-dir --user hermes-agent 2>/dev/null || true

COPY --chown=user hermes_rpc_server.py /home/user/app/

EXPOSE 7860
CMD ["python", "-m", "uvicorn", "hermes_rpc_server:app", "--host", "0.0.0.0", "--port", "7860"]
