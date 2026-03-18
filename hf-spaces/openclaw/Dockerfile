# OpenClaw v4 — HF Spaces Docker Deployment
# Node.js + Python + Playwright (for OddsHarvester)
FROM node:20-slim

ENV PORT=7860
ENV NODE_ENV=production
ENV PLAYWRIGHT_BROWSERS_PATH=/app/browsers
ENV DEBIAN_FRONTEND=noninteractive

# System deps: curl, Python 3, Playwright browser deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    python3 \
    python3-pip \
    python3-venv \
    # Playwright/Chromium dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libwayland-client0 \
    && rm -rf /var/lib/apt/lists/*

# Install OddsHarvester + Playwright (Python)
RUN python3 -m venv /app/oddsvenv && \
    /app/oddsvenv/bin/pip install --no-cache-dir oddsharvester playwright && \
    /app/oddsvenv/bin/playwright install chromium

WORKDIR /app
COPY package.json ./
RUN npm install --omit=dev
COPY . .
RUN mkdir -p /data/conversations /data/logs /data/executions /data/odds /data/a2a /data/watchdog /data/agentic-loop && chmod -R 777 /data

EXPOSE 7860
CMD ["node", "server.js"]
