#!/bin/bash
# Auto-startup for monetisation Codespace
# Re-installs everything if needed and launches agents

echo "=== Nomos Monetisation Startup ==="
echo "$(date)"

# Install deps if missing
if ! command -v node &>/dev/null; then
    echo "Installing Node.js..."
    sudo apk add --no-cache nodejs npm python3 py3-pip curl bash git 2>&1 | tail -3
fi

if ! command -v openclaw &>/dev/null; then
    echo "Installing OpenClaw..."
    sudo npm install -g openclaw --ignore-scripts 2>&1 | tail -3
fi

if ! command -v claude &>/dev/null; then
    echo "Installing Claude Code CLI..."
    sudo npm install -g @anthropic-ai/claude-code 2>&1 | tail -3
fi

echo "Node: $(node --version)"
echo "OpenClaw: $(openclaw --version 2>&1)"
echo "Claude: $(claude --version 2>&1 | head -1)"

# Launch OpenClaw gateway with Telegram
echo ""
echo "Starting OpenClaw gateway..."
export OPENROUTER_API_KEY="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"
setsid openclaw gateway --force > /tmp/openclaw.log 2>&1 &
echo "OpenClaw PID: $!"

echo ""
echo "=== Monetisation agents running ==="
echo "  OpenClaw: Telegram @Nomos42Bot"
echo "  Products: https://nomos42.gumroad.com"
