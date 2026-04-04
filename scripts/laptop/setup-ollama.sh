#!/bin/bash
# ============================================================
# Nomos42 — Ollama Setup for Acer Aspire 3 Laptop
# ============================================================
# Installs Ollama and pulls recommended models for monitoring.
# Run on the laptop (Windows WSL or Linux).
#
# Usage:
#   chmod +x setup-ollama.sh
#   ./setup-ollama.sh
# ============================================================

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color
BOLD='\033[1m'

echo -e "${GREEN}"
echo "╔══════════════════════════════════════════════════════╗"
echo "║     Nomos42 — Ollama Model Setup                     ║"
echo "║     Target: Acer Aspire 3 (8-16GB RAM)              ║"
echo "╚══════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ── Step 1: Check/Install Ollama ────────────────────────────

echo -e "${BOLD}[1/4] Checking Ollama installation...${NC}"

if command -v ollama &>/dev/null; then
    OLLAMA_VERSION=$(ollama --version 2>/dev/null || echo "unknown")
    echo -e "${GREEN}  Ollama found: ${OLLAMA_VERSION}${NC}"
else
    echo -e "${YELLOW}  Ollama not found. Installing...${NC}"

    # Detect OS
    if [[ "$OSTYPE" == "linux-gnu"* ]] || grep -qi microsoft /proc/version 2>/dev/null; then
        echo "  Installing via curl (Linux/WSL)..."
        curl -fsSL https://ollama.com/install.sh | sh
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "  Installing via Homebrew (macOS)..."
        brew install ollama
    else
        echo -e "${RED}  Unsupported OS. Please install Ollama manually from https://ollama.com${NC}"
        exit 1
    fi

    echo -e "${GREEN}  Ollama installed successfully.${NC}"
fi

# ── Step 2: Ensure Ollama is running ────────────────────────

echo -e "${BOLD}[2/4] Ensuring Ollama server is running...${NC}"

if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo -e "${GREEN}  Ollama server is running.${NC}"
else
    echo -e "${YELLOW}  Starting Ollama server...${NC}"
    ollama serve &>/dev/null &
    sleep 3

    if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
        echo -e "${GREEN}  Ollama server started.${NC}"
    else
        echo -e "${RED}  Could not start Ollama server. Start it manually: ollama serve${NC}"
        exit 1
    fi
fi

# ── Step 3: Pull models ────────────────────────────────────

echo -e "${BOLD}[3/4] Pulling models...${NC}"

# Check available RAM
TOTAL_RAM_KB=$(grep MemTotal /proc/meminfo 2>/dev/null | awk '{print $2}' || echo "0")
TOTAL_RAM_GB=$((TOTAL_RAM_KB / 1024 / 1024))

if [[ $TOTAL_RAM_GB -gt 0 ]]; then
    echo -e "  System RAM: ${TOTAL_RAM_GB}GB"
else
    echo -e "  ${YELLOW}Could not detect RAM. Assuming 8GB.${NC}"
    TOTAL_RAM_GB=8
fi

# Models to pull (ordered by priority)
MODELS=(
    "qwen2.5:3b"    # Primary: all-rounder (1.9GB)
    "gemma2:2b"      # Fast: quick polling (1.6GB)
    "phi3:mini"      # Code: analysis (2.3GB)
    "hermes3:3b"     # Agent: monitoring loop (2.0GB)
)

DESCRIPTIONS=(
    "Lightweight reasoning (1.9GB) — primary all-rounder"
    "Fast inference (1.6GB) — quick health checks"
    "Code generation (2.3GB) — script analysis"
    "Agent mode (2.0GB) — monitoring loop"
)

for i in "${!MODELS[@]}"; do
    MODEL="${MODELS[$i]}"
    DESC="${DESCRIPTIONS[$i]}"

    echo ""
    echo -e "  ${BOLD}Pulling ${MODEL}${NC} — ${DESC}"

    # Check if already pulled
    if ollama list 2>/dev/null | grep -q "${MODEL}"; then
        echo -e "  ${GREEN}Already available, skipping.${NC}"
    else
        echo -e "  ${YELLOW}Downloading...${NC}"
        ollama pull "${MODEL}"
        echo -e "  ${GREEN}Done.${NC}"
    fi
done

# ── Step 4: Verify ──────────────────────────────────────────

echo ""
echo -e "${BOLD}[4/4] Verification...${NC}"
echo ""
echo -e "${GREEN}Installed models:${NC}"
ollama list 2>/dev/null || echo "  (could not list models)"

echo ""
echo -e "${GREEN}Quick test (qwen2.5:3b):${NC}"
echo "What is 2+2?" | timeout 30 ollama run qwen2.5:3b --nowordwrap 2>/dev/null | head -5 || echo "  (test skipped)"

echo ""
echo -e "${GREEN}"
echo "╔══════════════════════════════════════════════════════╗"
echo "║  Setup complete!                                     ║"
echo "║                                                      ║"
echo "║  Models ready:                                       ║"
echo "║    qwen2.5:3b  — default reasoning                  ║"
echo "║    gemma2:2b   — fast inference                      ║"
echo "║    phi3:mini   — code generation                     ║"
echo "║    hermes3:3b  — agent mode                          ║"
echo "║                                                      ║"
echo "║  Next: python3 scripts/laptop/agent-monitor.py       ║"
echo "║  API:  http://localhost:11434                        ║"
echo "╚══════════════════════════════════════════════════════╝"
echo -e "${NC}"
