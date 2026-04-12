#!/bin/bash
# ============================================================
# Nomos42 — Decrypt secrets/.env.local.enc into ~/nomos42/.env.local
# ============================================================
# Run this on the laptop AFTER cloning mon-ipad.
# It reads secrets/.env.local.enc from the repo, prompts for the
# passphrase, and writes ~/nomos42/.env.local with tight perms.
#
# Usage:
#   bash scripts/laptop/env-decrypt.sh
#   # or with a custom destination:
#   bash scripts/laptop/env-decrypt.sh ~/some/other/.env.local
# ============================================================
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()  { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERR]${NC} $*"; exit 1; }

REPO_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel 2>/dev/null || true)"
[ -n "$REPO_ROOT" ] || err "Not inside a git repo. cd into mon-ipad first."
SRC="$REPO_ROOT/secrets/.env.local.enc"
[ -f "$SRC" ] || err "Encrypted bundle not found at $SRC. Did you git pull?"

DEST="${1:-$HOME/nomos42/.env.local}"
mkdir -p "$(dirname "$DEST")"

if [ -f "$DEST" ]; then
    warn "$DEST already exists. Overwrite? [y/N]"
    read -r ans
    [[ "$ans" =~ ^[Yy]$ ]] || err "Aborted"
fi

if [ -n "${NOMOS_ENV_PASSPHRASE:-}" ]; then
    PASS="$NOMOS_ENV_PASSPHRASE"
else
    read -rsp "Passphrase: " PASS; echo
fi

command -v openssl >/dev/null || err "openssl not installed (apt install openssl)"

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

if ! openssl enc -aes-256-cbc -pbkdf2 -iter 600000 -d -a \
        -in "$SRC" -out "$TMP" -pass "pass:$PASS" 2>/dev/null; then
    err "Decryption failed — wrong passphrase?"
fi

# Sanity: first line should look like an export or a comment
head -1 "$TMP" | grep -qE '^(#|export )' || warn "Decrypted file does not look like a shell env (first line)"

mv "$TMP" "$DEST"
trap - EXIT
chmod 600 "$DEST"
log "Decrypted → $DEST ($(wc -l < "$DEST") lines)"

echo
log "To load it in your current shell:"
echo "   set -a && source $DEST && set +a"
echo
log "It will auto-load in new shells once setup-brother-laptop.sh has sourced it from ~/.bashrc"
