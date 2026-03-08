#!/usr/bin/env bash
# Setup script for monetisation-bot Codespace
# Installs OpenClaw + Claude Code CLI + Telegram integration
set -euo pipefail

echo "=== Monetisation Bot Setup ==="

# 1. Install Node.js (for OpenClaw + Claude Code)
if ! command -v node &>/dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
    sudo apt-get install -y nodejs
fi
echo "Node: $(node --version)"

# 2. Install Claude Code CLI
if ! command -v claude &>/dev/null; then
    npm install -g @anthropic-ai/claude-code
fi
echo "Claude Code: $(claude --version 2>/dev/null || echo 'installing...')"

# 3. Install OpenClaw
if ! command -v openclaw &>/dev/null; then
    npm install -g openclaw
fi
echo "OpenClaw: $(openclaw --version 2>/dev/null || echo 'installing...')"

# 4. Configure OpenClaw with Telegram
mkdir -p ~/.openclaw

# OpenClaw config with Telegram + multi-LLM rotation
cat > ~/.openclaw/config.yaml << 'YAML'
# OpenClaw Configuration — Monetisation Bot
name: "Nomos Monetisation Agent"
description: "Autonomous monetisation agent for RAG training products"

# Messaging — Telegram integration
messaging:
  telegram:
    enabled: true
    # Token will be set via TELEGRAM_BOT_TOKEN env var

# AI Models — Rotation strategy
ai:
  primary:
    provider: anthropic
    model: claude-sonnet-4-6
    # Key via ANTHROPIC_API_KEY env var
  fallback:
    - provider: groq
      model: llama-3.3-70b-versatile
      # Key via GROQ_API_KEY env var
    - provider: google
      model: gemini-2.0-flash
      # Key via GOOGLE_API_KEY env var

# Skills
skills:
  - name: gumroad-manager
    description: "Manage Gumroad products, check sales, update listings"
  - name: content-creator
    description: "Generate marketing content for products"
  - name: social-poster
    description: "Post to Reddit, Twitter, Dev.to, HN"

# Memory
memory:
  enabled: true
  path: ~/.openclaw/memory
YAML

echo "OpenClaw config written to ~/.openclaw/config.yaml"

# 5. Set up environment
cat > /tmp/monetisation-env.sh << 'ENV'
# Source this file before running the bot
# Fill in your actual tokens:
export TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}"
export GROQ_API_KEY="${GROQ_API_KEY:-}"
export GOOGLE_API_KEY="${GOOGLE_API_KEY:-}"
export GUMROAD_ACCESS_TOKEN="${GUMROAD_ACCESS_TOKEN:-}"
export GUMROAD_SELLER="nomos42"
ENV

echo ""
echo "=== Setup Complete ==="
echo "Next steps:"
echo "1. Set TELEGRAM_BOT_TOKEN in environment"
echo "2. Set API keys (ANTHROPIC, GROQ, GOOGLE)"
echo "3. Run: openclaw start"
echo "4. The bot will be accessible via Telegram"
