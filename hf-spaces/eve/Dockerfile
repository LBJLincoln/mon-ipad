# Eve — Real HuggingClaw (OpenClaw + Claude Code CLI + Kimi K2 via Groq)
# Based on official HuggingClaw pattern: https://github.com/win4r/HuggingClaw
#
# Architecture: OpenClaw binary → ACP → Claude Code CLI (+ Kimi CLI)
# NOT a custom Express server — this IS the real OpenClaw.

# ── Stage 1: Pull pre-built OpenClaw ─────────────────────────────────────────
FROM ghcr.io/openclaw/openclaw:latest AS openclaw-prebuilt

# ── Stage 2: Runtime ─────────────────────────────────────────────────────────
FROM node:22-bookworm
SHELL ["/bin/bash", "-c"]

# ── System dependencies (root) ───────────────────────────────────────────────
RUN echo "[build] Installing system deps..." && START=$(date +%s) \
  && apt-get update \
  && apt-get install -y --no-install-recommends git ca-certificates curl python3 python3-pip \
     chromium fonts-liberation libgbm1 libnss3 libatk-bridge2.0-0 libgtk-3-0 \
  && rm -rf /var/lib/apt/lists/* \
  && pip3 install --no-cache-dir --break-system-packages huggingface_hub requests \
  && corepack enable \
  && mkdir -p /app/openclaw \
  && chown -R node:node /app \
  && mkdir -p /home/node/.openclaw/workspace /home/node/.openclaw/credentials \
  && chown -R node:node /home/node \
  && echo "[build] System deps: $(($(date +%s) - START))s"

# ── Puppeteer (headless browser for Colab trigger + web automation) ────────
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium
RUN npm install -g puppeteer-core \
  && echo "[build] Puppeteer ready (using system Chromium)"

# ── Claude Code CLI + ACP (acpx) + Kimi CLI ─────────────────────────────────
# Claude Code is the primary coding agent; acpx manages it via ACP
# Kimi Code CLI installed via uv (needs Python 3.12+, uses isolated venv)
RUN echo "[build] Installing Claude Code CLI + acpx..." && START=$(date +%s) \
  && npm install -g @anthropic-ai/claude-code acpx@latest \
  && echo "[build] Claude Code + acpx: $(($(date +%s) - START))s"

# Install uv + Kimi CLI as root (uv manages its own Python 3.12+ venv)
RUN echo "[build] Installing uv + Kimi CLI..." && START=$(date +%s) \
  && curl -LsSf https://astral.sh/uv/install.sh | sh \
  && /root/.local/bin/uv tool install kimi-cli --python 3.12 \
  && ln -sf /root/.local/share/uv/tools/kimi-cli/bin/kimi /usr/local/bin/kimi \
  && echo "[build] Kimi CLI: $(($(date +%s) - START))s"

# ── Copy pre-built OpenClaw (skips clone + install + build entirely) ─────────
COPY --from=openclaw-prebuilt --chown=node:node /app /app/openclaw

USER node
ENV HOME=/home/node
WORKDIR /app

# ── A2A Gateway Extension ───────────────────────────────────────────────────
RUN echo "[build] Installing A2A gateway..." && START=$(date +%s) \
  && git clone --depth 1 https://github.com/win4r/openclaw-a2a-gateway.git /app/openclaw/extensions/a2a-gateway \
  && cd /app/openclaw/extensions/a2a-gateway \
  && npm install --production \
  && echo "[build] A2A gateway: $(($(date +%s) - START))s"

# ── NBA Agent Extension (our custom extension) ──────────────────────────────
COPY --chown=node:node extensions/nba-agent /app/openclaw/extensions/nba-agent

# ── Coding Agent Extension (from HuggingClaw) ───────────────────────────────
COPY --chown=node:node extensions/coding-agent /app/openclaw/extensions/coding-agent

# ── Pre-configure acpx for non-interactive ACP sessions ──────────────────────
RUN mkdir -p /home/node/.acpx \
  && echo '{"defaultAgent":"claude","defaultPermissions":"approve-all","format":"text"}' \
     > /home/node/.acpx/config.json

# ── Prepare runtime dirs ────────────────────────────────────────────────────
RUN mkdir -p /app/openclaw/empty-bundled-plugins \
  && node -e "try{console.log(require('/app/openclaw/package.json').version)}catch(e){console.log('unknown')}" > /app/openclaw/.version \
  && echo "[build] OpenClaw version: $(cat /app/openclaw/.version)"

# ── Scripts + Config + Frontend ──────────────────────────────────────────────
COPY --chown=node:node scripts /home/node/scripts
COPY --chown=node:node frontend /home/node/frontend
COPY --chown=node:node workspace-templates /home/node/workspace-templates
COPY --chown=node:node openclaw.json /home/node/scripts/openclaw.json.default
RUN chmod +x /home/node/scripts/entrypoint.sh /home/node/scripts/sync_hf.py

ENV NODE_ENV=production
ENV OPENCLAW_BUNDLED_PLUGINS_DIR=/app/openclaw/empty-bundled-plugins
ENV OPENCLAW_PREFER_PNPM=1
ENV PATH="/home/node/.local/bin:$PATH"
WORKDIR /home/node

CMD ["/home/node/scripts/entrypoint.sh"]
