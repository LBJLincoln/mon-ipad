#!/bin/bash
# ============================================================
# Push .env.local from VM to laptop (native Ubuntu via Tailscale)
# ============================================================
# Run from the VM. Requires:
#   - Tailscale active on both sides
#   - SSH key auth configured: ssh $LAPTOP_USER@$LAPTOP_IP works
#
# Usage:
#   bash scripts/laptop/push-env-to-laptop.sh
#
# Env overrides:
#   LAPTOP_IP=100.67.205.125      Tailscale IP of the laptop
#   LAPTOP_USER=nomos             Linux user on the laptop
#   LAPTOP_NOMOS_DIR=/home/nomos/nomos42
#
# For the "can't reach the laptop" case, use env-encrypt.sh
# instead (ships creds via the private git repo).
# ============================================================
set -euo pipefail

LAPTOP_IP="${LAPTOP_IP:-100.67.205.125}"
LAPTOP_USER="${LAPTOP_USER:-nomos}"
LAPTOP_NOMOS_DIR="${LAPTOP_NOMOS_DIR:-/home/${LAPTOP_USER}/nomos42}"
SRC="${SRC:-/home/termius/mon-ipad/.env.local}"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()  { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERR]${NC} $*" >&2; exit 1; }

[ -f "$SRC" ] || err "Source not found: $SRC"

log "Pushing $SRC → ${LAPTOP_USER}@${LAPTOP_IP}:${LAPTOP_NOMOS_DIR}/.env.local"

ssh -o ConnectTimeout=10 -o BatchMode=yes "${LAPTOP_USER}@${LAPTOP_IP}" \
    "mkdir -p ${LAPTOP_NOMOS_DIR}" \
    || err "SSH to ${LAPTOP_USER}@${LAPTOP_IP} failed — check Tailscale + SSH key"

scp -o ConnectTimeout=10 -o BatchMode=yes \
    "$SRC" \
    "${LAPTOP_USER}@${LAPTOP_IP}:${LAPTOP_NOMOS_DIR}/.env.local" \
    || err "scp failed"

ssh -o ConnectTimeout=10 -o BatchMode=yes "${LAPTOP_USER}@${LAPTOP_IP}" \
    "chmod 600 ${LAPTOP_NOMOS_DIR}/.env.local && wc -l ${LAPTOP_NOMOS_DIR}/.env.local" \
    || warn "chmod/verify failed"

log ".env.local installed at ${LAPTOP_NOMOS_DIR}/.env.local on the laptop"
log "On the laptop, load it in a new shell (~/.bashrc auto-sources it) or run:"
echo "   set -a && source ${LAPTOP_NOMOS_DIR}/.env.local && set +a"
