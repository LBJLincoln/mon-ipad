#!/bin/bash
# Nomos42 — Daily backup to Google Drive via rclone
# Prerequisites: rclone configured with gdrive remote
# Usage: scripts/backup-to-drive.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPOS_PARENT="$(cd "${ROOT}/.." && pwd)"

BACKUP_DIR="/tmp/nomos42-backup"
DATE=$(date +%Y-%m-%d)
ARCHIVE="nomos42-backup-${DATE}.tar.gz"

echo "[$(date)] Starting backup..."
rm -rf "$BACKUP_DIR"
mkdir -p "$BACKUP_DIR"

# Backup critical data (not git, not node_modules)
for REPO in mon-ipad nomos-nba-agent nomos-political-alpha rgwa nomos-dashboard; do
  if [ -d "${REPOS_PARENT}/$REPO" ]; then
    echo "  Backing up $REPO..."
    tar czf "$BACKUP_DIR/${REPO}.tar.gz" \
      --exclude='.git' \
      --exclude='node_modules' \
      --exclude='__pycache__' \
      --exclude='.next' \
      --exclude='*.pyc' \
      -C "${REPOS_PARENT}" "$REPO" 2>/dev/null || true
  fi
done

# Combine into single archive
cd "$BACKUP_DIR"
tar czf "/tmp/$ARCHIVE" *.tar.gz
echo "[$(date)] Archive: /tmp/$ARCHIVE ($(du -h "/tmp/$ARCHIVE" | cut -f1))"

# Upload to Google Drive via gcloud OAuth (already authenticated)
ACCESS_TOKEN=$(gcloud auth print-access-token 2>/dev/null)
if [ -n "$ACCESS_TOKEN" ]; then
  echo "  Uploading to Google Drive..."
  FOLDER_NAME="nomos42-backups"
  # Find or create backup folder
  FOLDER_ID=$(curl -s "https://www.googleapis.com/drive/v3/files?q=name='${FOLDER_NAME}'+and+mimeType='application/vnd.google-apps.folder'+and+trashed=false&fields=files(id)" \
    -H "Authorization: Bearer $ACCESS_TOKEN" | python3 -c "import sys,json; f=json.load(sys.stdin).get('files',[]); print(f[0]['id'] if f else '')" 2>/dev/null)
  if [ -z "$FOLDER_ID" ]; then
    FOLDER_ID=$(curl -s -X POST "https://www.googleapis.com/drive/v3/files" \
      -H "Authorization: Bearer $ACCESS_TOKEN" \
      -H "Content-Type: application/json" \
      -d "{\"name\":\"${FOLDER_NAME}\",\"mimeType\":\"application/vnd.google-apps.folder\"}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null)
    echo "  Created folder: $FOLDER_ID"
  fi
  # Upload archive
  RESULT=$(curl -s -X POST "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -F "metadata={\"name\":\"$ARCHIVE\",\"parents\":[\"$FOLDER_ID\"]};type=application/json;charset=UTF-8" \
    -F "file=@/tmp/$ARCHIVE;type=application/gzip")
  FILE_ID=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id','FAILED'))" 2>/dev/null)
  echo "[$(date)] Uploaded: $ARCHIVE (id: $FILE_ID)"
else
  echo "  gcloud not authenticated — archive saved locally at /tmp/$ARCHIVE"
fi

# Cleanup
rm -rf "$BACKUP_DIR"
echo "[$(date)] Backup complete."
