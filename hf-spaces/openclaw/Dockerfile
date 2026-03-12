# OpenClaw v2026.3.11-beta.1 — HF Spaces Docker Deployment
# Nomos42/worker-2 — AI Operations Agent with full infra access
# Multi-stage build for optimized Node.js image

# ---- Stage 1: Dependencies ----
FROM node:20-slim AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --omit=dev && npm cache clean --force

# ---- Stage 2: Runtime ----
FROM node:20-slim AS runtime

# HF Spaces requires port 7860
ENV PORT=7860
ENV NODE_ENV=production
ENV TZ=Europe/Paris

# Install system deps for persistence, git ops, and curl (healthchecks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    ca-certificates \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Install lightweight Python deps for direct DB/API access
RUN pip3 install --no-cache-dir --break-system-packages \
    psycopg2-binary \
    neo4j \
    pinecone-client \
    requests \
    huggingface_hub

WORKDIR /app

# Copy deps from stage 1
COPY --from=deps /app/node_modules ./node_modules

# Copy application code
COPY . .

# HF Spaces persistent storage mount
RUN mkdir -p /data/conversations /data/logs /data/executions

# Non-root user (HF Spaces requirement)
RUN useradd -m -u 1000 openclaw && chown -R openclaw:openclaw /app /data
USER openclaw

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:7860/keep-alive || exit 1

CMD ["node", "server.js"]
