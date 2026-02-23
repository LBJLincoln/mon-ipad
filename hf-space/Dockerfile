FROM node:20-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash curl python3 redis-server nginx supervisor procps \
    && rm -rf /var/lib/apt/lists/*

# Install n8n globally
RUN npm install -g n8n@latest

WORKDIR /app

# Copy configuration files
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY nginx.conf /etc/nginx/nginx.conf
COPY entrypoint.sh /app/entrypoint.sh
COPY healthcheck.py /app/healthcheck.py
COPY n8n-workflows/ /app/n8n-workflows/

# Make sure nginx dirs exist and are writable
RUN mkdir -p /var/log/nginx /var/lib/nginx/body /var/run \
    && chmod 755 /var/log/nginx /var/lib/nginx /var/run

RUN chmod +x /app/entrypoint.sh

# Create n8n data directory
RUN mkdir -p /home/node/.n8n && chown -R 1000:1000 /home/node/.n8n

# HF Spaces requires port 7860
EXPOSE 7860

CMD ["/app/entrypoint.sh"]
