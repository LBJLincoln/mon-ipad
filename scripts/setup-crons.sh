#!/usr/bin/env bash
# Nomos42 — VM Cron Setup (run once after provisioning)
# ======================================================
# Installs all crontab entries required for the autonomous Nomos42 system.
# Safe: checks for existing entries before adding — will not create duplicates.
#
# Usage:
#   bash scripts/setup-crons.sh
#   MON_DIR=/custom/path bash scripts/setup-crons.sh
#
# After running, verify with: crontab -l

set -euo pipefail

MON_DIR="${MON_DIR:-/home/termius/mon-ipad}"
LOGDIR="$MON_DIR/logs"

echo "Nomos42 — VM Cron Setup"
echo "========================"
echo "Mon-ipad dir : $MON_DIR"
echo "Log dir      : $LOGDIR"
echo ""

# Create log dir if needed
mkdir -p "$LOGDIR"

# ── Helpers ─────────────────────────────────────────────────────

# Read current crontab (empty if none)
EXISTING=$(crontab -l 2>/dev/null || echo "")

add_cron() {
    local schedule="$1"
    local command="$2"
    local label="$3"
    local marker="$4"   # unique substring to detect existing entry

    if echo "$EXISTING" | grep -qF "$marker"; then
        printf "  SKIP (exists): %s\n" "$label"
    else
        EXISTING="${EXISTING}
${schedule}  ${command}"
        printf "  ADD           : %s\n" "$label"
    fi
}

echo "Scheduling cron entries..."
echo ""

# ── CORE: Autonomous cycle ───────────────────────────────────────
# Every hour at :30 — runs predictions, trading floor, cross-island sync,
# data server keepalive, political alpha deploy.
add_cron \
    "30 * * * *" \
    "cd $MON_DIR && bash scripts/autonomous-cycle.sh >> $LOGDIR/autonomous-cycle.log 2>&1" \
    "Autonomous cycle (every 1h at :30)" \
    "autonomous-cycle.sh"

# ── Compute orchestrator ─────────────────────────────────────────
# 4x daily: dispatches GPU bursts (ZeroGPU, Kaggle, Colab, Modal)
# and calls hf-inference-eval.py for CPU-side Karpathy loop.
add_cron \
    "0 6,8,12,18 * * *" \
    "python3 $MON_DIR/scripts/gpu-burst/compute-orchestrator.py >> $LOGDIR/compute-orchestrator.log 2>&1" \
    "Compute orchestrator — GPU dispatch (4x daily)" \
    "compute-orchestrator.py"

# ── NBA odds via The Odds API ────────────────────────────────────
# 3x daily (14, 18, 22 UTC). Free tier = 500 req/month; 3×31 = 93/month.
# Saves Pinnacle + 70 books to data/odds/odds-api-latest.json.
add_cron \
    "0 14,18,22 * * *" \
    "cd $MON_DIR && python3 scripts/alpaca/odds_api_client.py nba >> $LOGDIR/odds-api.log 2>&1" \
    "NBA odds via The Odds API (14, 18, 22 UTC)" \
    "odds_api_client.py"

# ── Kraken ticker snapshot ───────────────────────────────────────
# BTC/ETH/SOL prices every 30 min for political alpha crypto basket.
add_cron \
    "*/30 * * * *" \
    "cd $MON_DIR && python3 scripts/alpaca/kraken_client.py ticker >> $LOGDIR/kraken.log 2>&1" \
    "Kraken ticker snapshot (every 30 min)" \
    "kraken_client.py ticker"

# ── Alpaca paper account status ──────────────────────────────────
# Daily health check of paper trading account (political alpha stocks).
add_cron \
    "0 9 * * *" \
    "cd $MON_DIR && python3 scripts/alpaca/paper_client.py status >> $LOGDIR/alpaca.log 2>&1" \
    "Alpaca paper status (daily 09:00 UTC)" \
    "paper_client.py status"

# ── ZeroGPU burst ────────────────────────────────────────────────
# All 3 accounts once per day (LBJLincoln + LBJLincoln26 + Nomos42).
# Each account = ~5 min H200 free/day = 15 min total.
# compute-orchestrator.py also triggers this; direct cron is a safety net.
add_cron \
    "0 6 * * *" \
    "cd $MON_DIR && python3 scripts/gpu-burst/zerogpu-burst.py --account all >> $LOGDIR/zerogpu.log 2>&1" \
    "ZeroGPU burst — all 3 accounts (daily 06:00 UTC)" \
    "zerogpu-burst.py"

# ── Feature cache sync ───────────────────────────────────────────
# Daily download of prebuilt feature matrix from fleet-best HF Space.
# Uploads to HF Dataset repo so GPU sessions skip the 30-min rebuild.
add_cron \
    "0 7 * * *" \
    "cd $MON_DIR && python3 scripts/gpu-burst/feature-cache-sync.py >> $LOGDIR/feature-cache.log 2>&1" \
    "Feature cache sync (daily 07:00 UTC)" \
    "feature-cache-sync.py"

# ── HF Space keepalive ───────────────────────────────────────────
# Ping all 6 NBA islands + 4 political islands every 30 min to prevent
# them going to sleep on the free tier (sleeps after 15 min idle).
if [ -f "$MON_DIR/scripts/keepalive-spaces.sh" ]; then
    add_cron \
        "*/30 * * * *" \
        "cd $MON_DIR && bash scripts/keepalive-spaces.sh >> $LOGDIR/keepalive.log 2>&1" \
        "HF Space keepalive (every 30 min)" \
        "keepalive-spaces.sh"
fi

# ── Bloomberg API keepalive ──────────────────────────────────────
# Ensure the Bloomberg terminal HTTP API (port 8042) stays running.
if [ -f "$MON_DIR/scripts/bloomberg/bloomberg-api.py" ]; then
    add_cron \
        "*/15 * * * *" \
        "pgrep -f bloomberg-api.py > /dev/null || nohup python3 $MON_DIR/scripts/bloomberg/bloomberg-api.py > $LOGDIR/bloomberg-api.log 2>&1 &" \
        "Bloomberg API keepalive (every 15 min)" \
        "bloomberg-api.py"
fi

# ── Data server on reboot ────────────────────────────────────────
# Start nba-data-server.py automatically when the VM reboots.
# The autonomous-cycle.sh Phase 4 also restarts it if down — this is belt+suspenders.
add_cron \
    "@reboot" \
    "sleep 30 && nohup python3 $MON_DIR/scripts/nba-data-server.py > $LOGDIR/data-server.log 2>&1 &" \
    "NBA data server — start on reboot (30s delay)" \
    "nba-data-server.py"

# ── Install ──────────────────────────────────────────────────────
echo ""
echo "Writing crontab..."
echo "$EXISTING" | crontab -

echo ""
echo "Installed crontab:"
echo "------------------"
crontab -l
echo ""
echo "Done. Next steps:"
echo "  1. Verify entries above look correct"
echo "  2. Start data server now: nohup python3 $MON_DIR/scripts/nba-data-server.py > $LOGDIR/data-server.log 2>&1 &"
echo "  3. Trigger first autonomous cycle: bash $MON_DIR/scripts/autonomous-cycle.sh"
echo "  4. Check logs in: $LOGDIR/"
