FROM node:22-slim

# Install minimal dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash curl python3 procps \
    && rm -rf /var/lib/apt/lists/*

# Install n8n globally (pinned to 2.8.4 — 2.9.x has publish system that breaks automation)
RUN npm install -g n8n@2.8.4

WORKDIR /app

# Copy files
COPY entrypoint.sh /app/entrypoint.sh
COPY setup-workflows.py /app/setup-workflows.py
COPY healthcheck.py /app/healthcheck.py
COPY n8n-workflows/ /app/n8n-workflows/

RUN chmod +x /app/entrypoint.sh

# Create n8n data directory with full permissions
RUN mkdir -p /home/node/.n8n && chmod -R 777 /home/node/.n8n

# HF Spaces requires port 7860
EXPOSE 7860

# Run as root to avoid permission issues
CMD ["/app/entrypoint.sh"]
