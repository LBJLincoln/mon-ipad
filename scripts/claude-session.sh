#!/bin/bash
# Nomos42 — Claude Code Session Launcher
# Usage: ~/mon-ipad/scripts/claude-session.sh [--skip-perms] [--project nba|rgwa|political|dashboard]
#
# Sets up the environment, sources all tokens, ensures bots are running,
# then launches Claude Code with the right working directory.

set -uo pipefail

# ── Parse args ──
SKIP_PERMS=""
PROJECT="nba"
for arg in "$@"; do
  case "$arg" in
    --skip-perms) SKIP_PERMS="--allowedTools '*'" ;;
    --nba|--project=nba) PROJECT="nba" ;;
    --rgwa|--project=rgwa) PROJECT="rgwa" ;;
    --political|--project=political) PROJECT="political" ;;
    --dashboard|--project=dashboard) PROJECT="dashboard" ;;
    --all) PROJECT="all" ;;
  esac
done

# ── Source all env files ──
for envfile in \
  /home/termius/nomos-nba-agent/.env.local \
  /home/termius/mon-ipad/.env.local \
  /home/termius/rgwa/.env.local; do
  [ -f "$envfile" ] && source "$envfile" 2>/dev/null
done

echo "╔══════════════════════════════════════════╗"
echo "║     NOMOS42 — Claude Code Session        ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── Ensure bots are running ──
echo "▸ Checking bots..."
if ! pgrep -f "nomos42_brain.py" > /dev/null 2>&1; then
  echo "  @Nomos42Bot DOWN — starting..."
  cd /home/termius/mon-ipad && bash scripts/telegram/start_bots.sh start 2>/dev/null
else
  echo "  @Nomos42Bot UP"
fi

if ! pgrep -f "rgwa_bot.py" > /dev/null 2>&1; then
  echo "  @RGWAbot DOWN — starting..."
  cd /home/termius/rgwa && bash scripts/telegram/start_bot.sh start 2>/dev/null
else
  echo "  @RGWAbot UP"
fi

# ── Quick health check ──
echo ""
echo "▸ Quick health..."
for ISLAND in S10:nomos42-nba-quant S11:nomos42-nba-quant-2 S12:nomos42-nba-evo-3 S13:nomos42-nba-evo-4 S14:nomos42-nba-evo-5 S15:nomos42-nba-evo-6; do
  NAME="${ISLAND%%:*}"
  SLUG="${ISLAND#*:}"
  BRIER=$(curl -s --max-time 3 "https://${SLUG}.hf.space/api/status" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('best_brier','?'))" 2>/dev/null || echo "?")
  printf "  %-4s %s\n" "$NAME" "$BRIER"
done

# ── Set working directory ──
case "$PROJECT" in
  nba)       WORKDIR="/home/termius/mon-ipad" ;;
  rgwa)      WORKDIR="/home/termius/rgwa" ;;
  political) WORKDIR="/home/termius/nomos-political-alpha" ;;
  dashboard) WORKDIR="/home/termius/nomos-dashboard" ;;
  all)       WORKDIR="/home/termius/mon-ipad" ;;
esac

echo ""
echo "▸ Launching Claude Code in $WORKDIR"
echo "  Project: $PROJECT"
[ -n "$SKIP_PERMS" ] && echo "  Permissions: ALL ALLOWED"
echo ""

cd "$WORKDIR"
exec claude $SKIP_PERMS
