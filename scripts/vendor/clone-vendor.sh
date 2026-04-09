#!/usr/bin/env bash
# Bootstrap vendored OSS repos that the trading floor depends on.
# vendor/ is gitignored, so each VM/clone runs this once.
#
# Repos:
#   - TauricResearch/TradingAgents — real LangGraph bull/bear debate engine
#     used by scripts/arena/debate_round.py (currently a lightweight adapter,
#     migration to real LangGraph runs is tracked in PLAN.md)
#   - camel-ai/oasis — agent society / large-scale interaction simulator
#     used as the upgrade path for the T3 Specialist tier (Task #10)

set -uo pipefail

ROOT="/home/termius/mon-ipad"
VENDOR="$ROOT/vendor"
mkdir -p "$VENDOR"
cd "$VENDOR" || exit 1

clone_or_update() {
  local url="$1" dir="$2"
  if [[ -d "$dir/.git" ]]; then
    echo "[vendor] update $dir"
    git -C "$dir" fetch --depth=1 origin >/dev/null 2>&1 || true
    git -C "$dir" reset --hard origin/HEAD >/dev/null 2>&1 || true
  else
    echo "[vendor] clone $url -> $dir"
    git clone --depth=1 "$url" "$dir"
  fi
}

clone_or_update https://github.com/TauricResearch/TradingAgents.git TradingAgents
clone_or_update https://github.com/camel-ai/oasis.git oasis

echo "[vendor] done"
ls -la "$VENDOR"
