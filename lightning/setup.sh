#!/bin/bash
# ============================================================
# Nomos Lightning Agent — One-shot setup
# Run this ONCE on your Lightning.ai Studio terminal:
#   curl -sL https://raw.githubusercontent.com/LBJLincoln/mon-ipad/main/lightning/setup.sh | bash
# ============================================================

set -e

WORKDIR="$HOME/nomos-agent"
REPOS_DIR="$WORKDIR/repos"

echo "=== NOMOS LIGHTNING AGENT SETUP ==="

# 1. Create workspace
mkdir -p "$WORKDIR" "$REPOS_DIR"
cd "$WORKDIR"

# 2. Clone all repos
echo "[1/5] Cloning repos..."
for repo in mon-ipad rag-data-ingestion rag-website rag-dashboard; do
  if [ ! -d "$REPOS_DIR/$repo" ]; then
    git clone "https://github.com/LBJLincoln/$repo.git" "$REPOS_DIR/$repo" 2>/dev/null && \
      echo "  + $repo" || echo "  SKIP $repo (private or error)"
  else
    cd "$REPOS_DIR/$repo" && git pull --quiet && cd "$WORKDIR"
    echo "  ~ $repo (updated)"
  fi
done

# 3. Copy agent files from mon-ipad
echo "[2/5] Installing agent..."
cp "$REPOS_DIR/mon-ipad/lightning/agent.py" "$WORKDIR/"
cp "$REPOS_DIR/mon-ipad/lightning/requirements.txt" "$WORKDIR/"

# 4. Install dependencies
echo "[3/5] Installing Python deps..."
pip install -q -r requirements.txt 2>/dev/null

# 5. Load env from mon-ipad
echo "[4/5] Loading env vars..."
if [ -f "$REPOS_DIR/mon-ipad/.env.local" ]; then
  set -a
  source "$REPOS_DIR/mon-ipad/.env.local"
  set +a
  echo "  Loaded .env.local"
else
  echo "  WARNING: .env.local not found — set vars manually"
fi

# 6. Start agent
echo "[5/5] Starting agent on port 8000..."
echo "=== NOMOS LIGHTNING AGENT READY ==="
cd "$WORKDIR"
python3 agent.py
