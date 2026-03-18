# OpenClaw v5 — HF Spaces Docker Deployment
FROM node:20-slim

ENV PORT=7860
ENV NODE_ENV=production
ENV DEBIAN_FRONTEND=noninteractive
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
ENV CHROME_BIN=/usr/bin/google-chrome-stable

# System deps: curl, python3 (DNS resolver), gnupg (Chrome repo), Google Chrome
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl python3 gnupg \
    && curl --location --silent https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY package.json ./
RUN npm install --omit=dev
COPY . .
RUN mkdir -p /data/conversations /data/logs /data/executions /data/odds /data/a2a /data/watchdog /data/agentic-loop && chmod -R 777 /data

# DNS fix: preload dns-fix.cjs (patches dns.lookup) + telegram-proxy.cjs (patches fetch)
# This fixes HF Spaces blocking api.telegram.org DNS resolution
ENV NODE_OPTIONS="--require /app/scripts/dns-fix.cjs --require /app/scripts/telegram-proxy.cjs"

EXPOSE 7860

# Startup: resolve DNS via DoH first, then start Node
CMD python3 /app/scripts/dns-resolve.py /tmp/dns-resolved.json && node server.js
