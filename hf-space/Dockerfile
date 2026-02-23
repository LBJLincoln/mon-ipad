FROM node:20-slim

# Install system dependencies (no nginx — n8n listens directly on 7860)
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash curl python3 redis-server supervisor procps \
    && rm -rf /var/lib/apt/lists/*

# Install n8n globally
RUN npm install -g n8n@latest

WORKDIR /app

# Copy configuration files
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY entrypoint.sh /app/entrypoint.sh
COPY healthcheck.py /app/healthcheck.py
COPY n8n-workflows/ /app/n8n-workflows/

RUN chmod +x /app/entrypoint.sh

# Create n8n data directory
RUN mkdir -p /home/node/.n8n && chown -R 1000:1000 /home/node/.n8n

# HF Spaces requires port 7860 — n8n listens directly on this port
EXPOSE 7860

CMD ["/app/entrypoint.sh"]
