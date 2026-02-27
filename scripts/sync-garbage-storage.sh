#!/usr/bin/env bash
set -euo pipefail

CONTROL_REPO="/home/termius/mon-ipad"
STORAGE_REPO="/home/termius/rag-storage"
STAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

REPOS=(
  /home/termius/mon-ipad
  /home/termius/rag-website
  /home/termius/rag-pme-connectors
  /home/termius/rag-pme-usecases
  /home/termius/rag-dashboard
  /home/termius/rag-storage
  /home/termius/satellite-cleanup/rag-data-ingestion
  /home/termius/satellite-cleanup/rag-tests
)

mkdir -p "$STORAGE_REPO/global/autosync" "$STORAGE_REPO/repos"

for repo in "${REPOS[@]}"; do
  [ -d "$repo/.git" ] || continue
  name="$(basename "$repo")"
  dest="$STORAGE_REPO/repos/$name/autosync/latest"
  mkdir -p "$dest"

  git -C "$repo" status --short > "$dest/git-status.txt" || true
  git -C "$repo" log -1 --oneline > "$dest/git-last-commit.txt" || true
  find "$repo" -maxdepth 2 -type f \( -name 'README*' -o -name 'CLAUDE.md' -o -name 'package.json' -o -name 'pyproject.toml' -o -name 'requirements*.txt' \) \
    | sed "s#^$repo/##" > "$dest/key-files.txt" || true

  # lightweight rsync of operational artifacts
  mkdir -p "$dest/artifacts"
  rsync -a --delete \
    --include='*/' \
    --include='docs/status.json' \
    --include='docs/executive-summary.md' \
    --include='docs/tested_ids.json' \
    --include='logs/***' \
    --include='eval/***' \
    --exclude='*' \
    "$repo/" "$dest/artifacts/" 2>/dev/null || true

done

echo "timestamp=$STAMP" > "$STORAGE_REPO/global/autosync/last-sync.txt"
echo "Synced at $STAMP"
