#!/bin/bash
# ============================================================
# Nomos42 — Encrypt .env.local and commit to repo
# ============================================================
# Run this on ANY machine that already has a working .env.local
# (VM via Termius, iPad Claude Code session, old laptop, etc.)
#
# Produces secrets/.env.local.enc (AES-256-CBC + PBKDF2 600k iter,
# base64-armored) and commits+pushes it to the mon-ipad repo.
# The passphrase is the ONLY thing you need to type on the laptop
# afterwards to decrypt.
#
# Usage:
#   bash scripts/laptop/env-encrypt.sh [/path/to/.env.local]
#
# Default source: $PWD/.env.local, then /home/termius/mon-ipad/.env.local
# ============================================================
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()  { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERR]${NC} $*"; exit 1; }

# ── Locate source .env.local ─────────────────────────────────
SRC="${1:-}"
if [ -z "$SRC" ]; then
    for candidate in \
        "$PWD/.env.local" \
        "/home/termius/mon-ipad/.env.local" \
        "$HOME/mon-ipad/.env.local" \
        "$HOME/nomos42/.env.local"; do
        if [ -f "$candidate" ]; then SRC="$candidate"; break; fi
    done
fi
[ -n "$SRC" ] && [ -f "$SRC" ] || err "No .env.local found. Pass path as arg."
log "Source: $SRC"

# ── Locate mon-ipad repo (where we'll commit) ────────────────
REPO_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel 2>/dev/null || true)"
[ -n "$REPO_ROOT" ] || err "Not inside a git repo. cd into mon-ipad first."
log "Repo: $REPO_ROOT"

DEST="$REPO_ROOT/secrets/.env.local.enc"
mkdir -p "$REPO_ROOT/secrets"

# ── Passphrase prompt (twice, no echo) ───────────────────────
if [ -n "${NOMOS_ENV_PASSPHRASE:-}" ]; then
    PASS="$NOMOS_ENV_PASSPHRASE"
    log "Using passphrase from \$NOMOS_ENV_PASSPHRASE"
else
    read -rsp "Passphrase (min 12 chars): " PASS; echo
    read -rsp "Confirm: " PASS2; echo
    [ "$PASS" = "$PASS2" ] || err "Passphrases do not match"
    [ ${#PASS} -ge 12 ] || err "Passphrase must be at least 12 chars"
fi

# ── Encrypt ──────────────────────────────────────────────────
command -v openssl >/dev/null || err "openssl not installed"
openssl enc -aes-256-cbc -pbkdf2 -iter 600000 -salt -a \
    -in "$SRC" -out "$DEST" -pass "pass:$PASS"
log "Encrypted → $DEST ($(wc -c < "$DEST") bytes)"

# Sanity-check: decrypt back and compare
TMP="$(mktemp)"
openssl enc -aes-256-cbc -pbkdf2 -iter 600000 -d -a \
    -in "$DEST" -out "$TMP" -pass "pass:$PASS"
if ! cmp -s "$SRC" "$TMP"; then
    rm -f "$TMP"
    err "Round-trip failed — NOT committing"
fi
rm -f "$TMP"
log "Round-trip OK"

# ── Write README alongside (reminder) ────────────────────────
cat > "$REPO_ROOT/secrets/README.md" << 'MDEOF'
# secrets/

Encrypted credentials for bootstrapping new Nomos42 nodes.

- `.env.local.enc` — AES-256-CBC + PBKDF2 (600k iter), base64 armor
- Produced by `scripts/laptop/env-encrypt.sh`
- Decrypted by `scripts/laptop/env-decrypt.sh`

The passphrase is **not** stored here. Share it via a password manager
(Bitwarden, 1Password) or a secure channel.

Repo is private, but treat this as defense-in-depth only.
MDEOF

# ── Commit + push ────────────────────────────────────────────
cd "$REPO_ROOT"
git add secrets/.env.local.enc secrets/README.md
if git diff --cached --quiet; then
    warn "No changes to commit (blob identical)"
else
    git commit -m "secrets: update encrypted .env.local bundle ($(date -u +%Y-%m-%dT%H:%MZ))"
    log "Committed"

    CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
    log "Pushing to origin/$CURRENT_BRANCH..."
    for i in 1 2 3 4; do
        if git push -u origin "$CURRENT_BRANCH"; then
            log "Pushed"
            break
        fi
        SLEEP=$((2 ** i))
        warn "Push failed (attempt $i/4) — retry in ${SLEEP}s"
        sleep $SLEEP
    done
fi

echo
log "DONE. On the laptop:"
echo "   1. git clone https://github.com/LBJLincoln/mon-ipad.git ~/nomos42/repos/mon-ipad"
echo "   2. cd ~/nomos42/repos/mon-ipad && git checkout $(git rev-parse --abbrev-ref HEAD)"
echo "   3. bash scripts/laptop/env-decrypt.sh"
echo "   4. Enter the same passphrase you just typed"
