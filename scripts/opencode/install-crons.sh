#!/bin/bash
################################################################################
# Install ALL Nomos42 Cron Jobs — OpenCode agents + councils + monitoring
# Run this manually: bash scripts/opencode/install-crons.sh
# To remove: bash scripts/opencode/install-crons.sh --remove
# To preview: bash scripts/opencode/install-crons.sh --dry-run
#
# Full cron schedule (UTC):
#   */5   : watchdog.sh           (every 5 min — service health + Telegram alerts)
#   */30  : keepalive-spaces.sh   (every 30 min — 25 HF spaces)
#   :30/4h: autonomous-cycle.sh  (every 4h at :30 — muscle: predictions, deploy)
#   :05/6h: research-agent.sh    (every 6h at :05 — OpenCode research)
#   :35/6h: evaluation-agent.sh  (every 6h at :35 — OpenCode evaluation)
#   :15/4h: infra-agent.sh       (every 4h at :15 — OpenCode infra)
#   :45/4h: run-councils.sh      (every 4h at :45 — 9-dept council runner)
#   :20/2h: cross-repo-monitor.py (every 2h at :20 — ecosystem health)
#   :10/6h: fetch_political_data.py (every 6h at :10 — political signal ingestion)
################################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
POLITICAL_DIR="/home/lahargnedebartoli/nomos-political-alpha"
TERMIUS_ROOT="/home/lahargnedebartoli"

# ── All cron entries ─────────────────────────────────────────────────────────
# Times are staggered to prevent resource contention with the 4h brain cycle (:00).
# Brain at :00, muscle at :30, councils at :45, cross-repo at :20.
CRON_ENTRIES=(
    # ── Keepalive (every 30 min) ──
    "*/30 * * * * $TERMIUS_ROOT/mon-ipad/scripts/keepalive-spaces.sh >> $TERMIUS_ROOT/mon-ipad/logs/keepalive.log 2>&1"

    # ── Autonomous cycle / muscle (every 4h at :30) ──
    "30 */4 * * * cd $TERMIUS_ROOT/nomos-nba-agent && bash $TERMIUS_ROOT/mon-ipad/scripts/autonomous-cycle.sh >> $TERMIUS_ROOT/mon-ipad/logs/autonomous-cycle.log 2>&1"

    # ── OpenCode department agents ──
    # Research: every 6h at :05 (offset from brain :00 and muscle :30)
    "5 */6 * * * $SCRIPT_DIR/research-agent.sh >> $REPO_ROOT/data/opencode/research.log 2>&1"
    # Evaluation: every 6h at :35
    "35 */6 * * * $SCRIPT_DIR/evaluation-agent.sh >> $REPO_ROOT/data/opencode/evaluation.log 2>&1"
    # Infra: every 4h at :15
    "15 */4 * * * $SCRIPT_DIR/infra-agent.sh >> $REPO_ROOT/data/opencode/infra.log 2>&1"

    # ── Council runner (every 4h at :45) ──
    # Runs all 9 department councils in execute mode (real actions, not dry-run).
    # Staggered 45min after brain cycle to consume brain's health-status.json output.
    "45 */4 * * * cd $TERMIUS_ROOT/mon-ipad && python3 scripts/councils/smart-council.py --all --execute >> $TERMIUS_ROOT/mon-ipad/logs/councils.log 2>&1"

    # ── Cross-repo ecosystem monitor (every 2h at :20) ──
    # Writes cross-repo-health.json — brain reads this for ecosystem state.
    # Runs every 2h so brain always has fresh data even between brain cycles.
    "20 */2 * * * cd $TERMIUS_ROOT/mon-ipad && python3 scripts/cross-repo-monitor.py --output data/cross-repo-health.json >> $TERMIUS_ROOT/mon-ipad/logs/cross-repo-monitor.log 2>&1 && git -C $TERMIUS_ROOT/mon-ipad add data/cross-repo-health.json && git -C $TERMIUS_ROOT/mon-ipad diff --cached --quiet || git -C $TERMIUS_ROOT/mon-ipad commit -m 'data: cross-repo health $(date +%Y-%m-%d-%H%M)' && git -C $TERMIUS_ROOT/mon-ipad push origin main 2>/dev/null"

    # ── Political data ingestion (every 6h at :10) ──
    # Fetches FEC, SEC Form 4, exec orders, Polymarket, Kalshi into Supabase.
    # Offset at :10 to avoid conflicts with brain (:00) and research-agent (:05).
    "10 */6 * * * cd $POLITICAL_DIR && python3 ops/fetch_political_data.py >> $TERMIUS_ROOT/mon-ipad/logs/political-data.log 2>&1"

    # ── Watchdog (every 5 min) ──
    # Monitors all services, restarts dead ones, Telegram alerts with 15min cooldown.
    "*/5 * * * * bash $TERMIUS_ROOT/mon-ipad/scripts/watchdog.sh >> $TERMIUS_ROOT/mon-ipad/logs/watchdog.log 2>&1"
)

MARKER_START="# --- Nomos42 All Crons START ---"
MARKER_END="# --- Nomos42 All Crons END ---"

# ── Remove ───────────────────────────────────────────────────────────────────
if [ "${1:-}" = "--remove" ]; then
    echo "Removing all Nomos42 cron entries..."
    CURRENT_CRON=$(crontab -l 2>/dev/null || true)
    # Also clean up old OpenCode marker
    echo "$CURRENT_CRON" \
        | sed "/# --- OpenCode Department Agents START ---/,/# --- OpenCode Department Agents END ---/d" \
        | sed "/$MARKER_START/,/$MARKER_END/d" \
        | crontab -
    echo "Done."
    exit 0
fi

# ── Dry run ──────────────────────────────────────────────────────────────────
if [ "${1:-}" = "--dry-run" ]; then
    echo "=== DRY RUN: Would install these cron entries ==="
    echo ""
    echo "$MARKER_START"
    for entry in "${CRON_ENTRIES[@]}"; do
        echo "$entry"
    done
    echo "$MARKER_END"
    echo ""
    echo "=== Current crontab ==="
    crontab -l 2>/dev/null || echo "(empty)"
    exit 0
fi

# ── Install ──────────────────────────────────────────────────────────────────
echo "Installing all Nomos42 cron jobs..."
echo ""

# Verify OpenCode scripts exist and are executable
for script in research-agent.sh evaluation-agent.sh infra-agent.sh; do
    if [ ! -x "$SCRIPT_DIR/$script" ]; then
        echo "WARNING: $SCRIPT_DIR/$script not executable — run: chmod +x $SCRIPT_DIR/$script"
    fi
done

# Remove old markers (old OpenCode-only marker + new all-crons marker)
CURRENT_CRON=$(crontab -l 2>/dev/null || true)
CLEAN_CRON=$(echo "$CURRENT_CRON" \
    | sed "/# --- OpenCode Department Agents START ---/,/# --- OpenCode Department Agents END ---/d" \
    | sed "/$MARKER_START/,/$MARKER_END/d")

# Build new crontab
NEW_CRON="$CLEAN_CRON
$MARKER_START"
for entry in "${CRON_ENTRIES[@]}"; do
    NEW_CRON="$NEW_CRON
$entry"
done
NEW_CRON="$NEW_CRON
$MARKER_END"

echo "$NEW_CRON" | crontab -

echo "Installed cron entries:"
echo ""
crontab -l | sed -n "/$MARKER_START/,/$MARKER_END/p"
echo ""
echo "Logs:"
echo "  keepalive:       $TERMIUS_ROOT/mon-ipad/logs/keepalive.log"
echo "  autonomous:      $TERMIUS_ROOT/mon-ipad/logs/autonomous-cycle.log"
echo "  councils:        $TERMIUS_ROOT/mon-ipad/logs/councils.log"
echo "  cross-repo:      $TERMIUS_ROOT/mon-ipad/logs/cross-repo-monitor.log"
echo "  political-data:  $TERMIUS_ROOT/mon-ipad/logs/political-data.log"
echo "  watchdog:        $TERMIUS_ROOT/mon-ipad/logs/watchdog.log"
echo "  research:        $REPO_ROOT/data/opencode/research.log"
echo "  evaluation:      $REPO_ROOT/data/opencode/evaluation.log"
echo "  infra:           $REPO_ROOT/data/opencode/infra.log"
echo ""
echo "To remove: $0 --remove"
echo "To preview: $0 --dry-run"
