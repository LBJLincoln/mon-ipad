FROM node:20-slim

# Install minimal dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash curl python3 procps \
    && rm -rf /var/lib/apt/lists/*

# Install n8n globally
RUN npm install -g n8n@latest

WORKDIR /app

# Copy files
COPY entrypoint.sh /app/entrypoint.sh
COPY healthcheck.py /app/healthcheck.py
COPY n8n-workflows/ /app/n8n-workflows/

RUN chmod +x /app/entrypoint.sh

# Create n8n data directory
RUN mkdir -p /home/node/.n8n && chown -R 1000:1000 /home/node/.n8n

# HF Spaces requires port 7860
EXPOSE 7860

CMD ["/app/entrypoint.sh"]
