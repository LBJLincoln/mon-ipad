#!/bin/bash
# Push .env.local from VM to brother's laptop (WSL2)
# Run from VM. Requires Tailscale active and SSH key auth.
# Usage: bash scripts/laptop/push-env-to-laptop.sh

set -e

LAPTOP_IP="100.67.205.125"
LAPTOP_SSH_USER="aurel"
# We target WSL2's filesystem via Windows SSH → wsl path
# WSL home is at C:\Users\aurel\AppData\Local\Packages\...\rootfs\home\nomos\
# But simpler: write to Windows and let user copy, OR use the nomos WSL user
WSL_USER="nomos"

echo "[INFO] Pushing .env.local to laptop WSL2..."

# Write via Windows SSH then invoke WSL
# Step 1: copy to Windows temp
scp -o ConnectTimeout=10 \
    /home/lahargnedebartoli/mon-ipad/.env.local \
    "${LAPTOP_SSH_USER}@${LAPTOP_IP}:C:/tmp/env.local.tmp" 2>/dev/null && {
    echo "[OK] File copied to Windows temp"
    # Step 2: move into WSL via ssh + wsl
    ssh -o ConnectTimeout=10 "${LAPTOP_SSH_USER}@${LAPTOP_IP}" \
        "C:\\Windows\\system32\\wsl.exe -d Ubuntu -e bash -c 'mkdir -p /home/nomos/nomos42 && cp /mnt/c/tmp/env.local.tmp /home/nomos/nomos42/.env.local && chmod 600 /home/nomos/nomos42/.env.local && echo done'" 2>/dev/null \
        && echo "[OK] .env.local installed in WSL at /home/nomos/nomos42/.env.local" \
        || echo "[WARN] WSL move failed — file is at C:\\tmp\\env.local.tmp, copy manually"
} || {
    echo "[WARN] scp failed — laptop may be asleep or SSH not running"
    echo "       Manual alternative: copy /home/lahargnedebartoli/mon-ipad/.env.local contents"
    echo "       and paste into ~/nomos42/.env.local on the laptop"
}
