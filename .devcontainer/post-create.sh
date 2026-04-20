#!/usr/bin/env bash
# Codespaces/devcontainer post-create: install NBA Quant deps + browser-use + Hermes.
# Paired with .devcontainer/devcontainer.json "postCreateCommand".
#
# This runs ONCE when the codespace is first created. Safe to re-run manually
# via: bash .devcontainer/post-create.sh

set -u

log() { printf '[post-create %s] %s\n' "$(date -u +%H:%M:%SZ)" "$*"; }

# ---------- 1. Existing NBA Quant deps (matches prior postCreateCommand) ----------
log "installing python ML stack"
pip install --user scikit-learn xgboost lightgbm catboost pandas numpy httpx kaggle huggingface-hub \
    >/tmp/pc-pip-ml.log 2>&1 \
    && log "pip ML stack OK" \
    || log "pip ML stack FAILED (see /tmp/pc-pip-ml.log) — continuing"

log "installing Claude Code CLI"
npm install -g @anthropic-ai/claude-code >/tmp/pc-npm.log 2>&1 \
    && log "claude-code OK" \
    || log "claude-code FAILED (see /tmp/pc-npm.log) — continuing"

# ---------- 2. browser-use + uv ----------
log "installing browser-use 0.12.6 + uv"
pip install --user browser-use==0.12.6 uv >/tmp/pc-browseruse.log 2>&1 \
    && log "browser-use OK" \
    || log "browser-use FAILED (see /tmp/pc-browseruse.log)"

# ---------- 3. chromium (best-effort, can be skipped in lean codespaces) ----------
if [ "${SKIP_CHROMIUM:-0}" = "1" ]; then
    log "chromium: SKIPPED (SKIP_CHROMIUM=1)"
else
    export PATH="$HOME/.local/bin:$PATH"
    if command -v uvx >/dev/null 2>&1; then
        log "fetching chromium via 'uvx browser-use install'"
        uvx browser-use install >/tmp/pc-chromium.log 2>&1 \
            && log "chromium OK" \
            || log "chromium FAILED (see /tmp/pc-chromium.log) — browser-use will fall back"
    else
        log "chromium: uvx not found, skipping"
    fi
fi

# ---------- 4. Hermes (NousResearch/hermes-agent) — NON-FATAL ----------
log "installing Hermes (non-fatal)"
curl -fsSL --max-time 30 https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh \
    | bash >/tmp/pc-hermes.log 2>&1 \
    && log "hermes OK" \
    || log "hermes install failed, retry manually via scripts/setup/install-browser-hermes.sh"

# ---------- 5. Bashrc persistence for HERMES_CONFIG_DIR ----------
if ! grep -q 'HERMES_CONFIG_DIR' "$HOME/.bashrc" 2>/dev/null; then
    echo "export HERMES_CONFIG_DIR=\$HOME/.hermes" >> "$HOME/.bashrc"
    log "~/.bashrc: appended HERMES_CONFIG_DIR"
fi

log "done."
