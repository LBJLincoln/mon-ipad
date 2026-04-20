#!/usr/bin/env bash
# install-browser-hermes.sh — idempotent installer for browser-use + NousResearch Hermes.
#
# Safe to re-run: detects existing installs and prints ALREADY INSTALLED,
# otherwise INSTALLED v<version>. Exits non-zero only on unrecoverable
# install failures for browser-use (Hermes failure is non-fatal — its
# installer pulls from the upstream repo and can rate-limit).
#
# Companion to the HF Spaces being shipped by the other DR FRANKENSTEIN
# instance:
#   LBJLincoln/nomos-browser-nba   (browser-use, NBA line scraping)
#   TESTforge42/nomos-browser-qa   (browser-use, pixel/dashboard QA)
#   LBJLincoln26/nomos-hermes-agent (Hermes orchestrator)
#
# Usage:
#   bash scripts/setup/install-browser-hermes.sh
#   bash scripts/setup/install-browser-hermes.sh --no-chromium  # skip ~600MB download

set -u
# Don't use -e: we want to keep trying later steps even if Hermes install flakes.

SKIP_CHROMIUM=0
for a in "$@"; do
    case "$a" in
        --no-chromium) SKIP_CHROMIUM=1 ;;
        -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    esac
done

log() { printf '[%s] %s\n' "$(date -u +%H:%M:%SZ)" "$*"; }

# ---------- 1. uv ----------
if command -v uv >/dev/null 2>&1; then
    log "uv: ALREADY INSTALLED ($(uv --version 2>/dev/null | head -1))"
else
    log "uv: installing via pip --user"
    if python3 -m pip install --user --break-system-packages uv >/tmp/install-uv.log 2>&1; then
        # Make sure ~/.local/bin is usable in this session.
        export PATH="$HOME/.local/bin:$PATH"
        log "uv: INSTALLED $(uv --version 2>/dev/null | head -1)"
    else
        log "uv: INSTALL FAILED (see /tmp/install-uv.log) — continuing"
    fi
fi

# ---------- 2. browser-use ----------
BU_VER_TARGET="0.12.6"
bu_version() {
    # browser-use doesn't expose __version__ at module level; use pip show.
    python3 -m pip show browser-use 2>/dev/null | awk '/^Version:/ {print $2}'
}
BU_VER=$(bu_version)
if [ -n "$BU_VER" ] && [ "$BU_VER" = "$BU_VER_TARGET" ]; then
    log "browser-use: ALREADY INSTALLED (v${BU_VER})"
elif [ -n "$BU_VER" ]; then
    log "browser-use: upgrading v${BU_VER} -> v${BU_VER_TARGET}"
    python3 -m pip install --user --break-system-packages --upgrade "browser-use==${BU_VER_TARGET}" >/tmp/install-browseruse.log 2>&1 \
        && log "browser-use: INSTALLED v$(bu_version)" \
        || log "browser-use: UPGRADE FAILED (see /tmp/install-browseruse.log) — keeping v${BU_VER}"
else
    log "browser-use: installing v${BU_VER_TARGET}"
    if python3 -m pip install --user --break-system-packages "browser-use==${BU_VER_TARGET}" >/tmp/install-browseruse.log 2>&1; then
        log "browser-use: INSTALLED v$(bu_version)"
    else
        log "browser-use: INSTALL FAILED (see /tmp/install-browseruse.log)"
        exit 2
    fi
fi

# ---------- 3. chromium via uvx browser-use install ----------
if [ "${SKIP_CHROMIUM}" -eq 1 ]; then
    log "chromium: SKIPPED (--no-chromium)"
else
    # Cache marker — uvx/playwright puts chromium under ~/.cache/ms-playwright
    if [ -d "$HOME/.cache/ms-playwright" ] && find "$HOME/.cache/ms-playwright" -maxdepth 2 -name 'chromium-*' -type d 2>/dev/null | grep -q chromium; then
        log "chromium: ALREADY INSTALLED ($(find "$HOME/.cache/ms-playwright" -maxdepth 2 -name 'chromium-*' -type d | head -1))"
    else
        log "chromium: fetching via 'uvx browser-use install' (may take 1-2 min, ~600MB)"
        if command -v uvx >/dev/null 2>&1; then
            uvx browser-use install >/tmp/install-chromium.log 2>&1 && \
                log "chromium: INSTALLED" || \
                log "chromium: INSTALL FAILED (see /tmp/install-chromium.log) — browser-use will fall back to system chromium if present"
        else
            log "chromium: SKIPPED (uvx not on PATH)"
        fi
    fi
fi

# ---------- 4. Hermes (NousResearch/hermes-agent) — non-fatal ----------
# Also detects pre-existing ~/.local/bin/hermes installs even if not on PATH.
HERMES_DIR="${HERMES_CONFIG_DIR:-$HOME/.hermes}"
HERMES_BIN=""
if command -v hermes >/dev/null 2>&1; then
    HERMES_BIN="$(command -v hermes)"
elif [ -x "$HOME/.local/bin/hermes" ]; then
    HERMES_BIN="$HOME/.local/bin/hermes"
fi

if [ -n "$HERMES_BIN" ]; then
    HV=$("$HERMES_BIN" --version 2>/dev/null | head -1 || echo "?")
    log "hermes: ALREADY INSTALLED ($HERMES_BIN ${HV})"
else
    log "hermes: installing via NousResearch upstream script"
    if curl -fsSL --max-time 30 https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh -o /tmp/hermes-install.sh 2>/dev/null; then
        # Upstream installer runs `npx playwright install --with-deps chromium`
        # which needs ~5 min + passwordless sudo. We cap the full run at 15 min
        # and treat any failure as non-fatal.
        timeout 900 bash /tmp/hermes-install.sh </dev/null >/tmp/install-hermes.log 2>&1 && \
            log "hermes: INSTALLED ($(command -v hermes 2>/dev/null || echo "$HOME/.local/bin/hermes"))" || \
            log "hermes: PARTIAL or FAILED (see /tmp/install-hermes.log) — retry: bash /tmp/hermes-install.sh"
    else
        log "hermes: install script fetch failed (offline? rate-limited?) — skipping (non-fatal)"
    fi
fi

# Ensure HERMES_CONFIG_DIR export persists.
if ! grep -q 'HERMES_CONFIG_DIR' "$HOME/.bashrc" 2>/dev/null; then
    echo "export HERMES_CONFIG_DIR=\$HOME/.hermes" >> "$HOME/.bashrc"
    log "bashrc: appended HERMES_CONFIG_DIR export"
else
    log "bashrc: HERMES_CONFIG_DIR export ALREADY PRESENT"
fi
mkdir -p "$HERMES_DIR"

log "done."
