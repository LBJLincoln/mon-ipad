#!/bin/bash
# Auto-deploy engine.py to all 6 NBA HF evolution islands
# Checks if engine.py has changed since last deploy, and if so, pushes to all spaces
# Run via cron: 0 */6 * * * (every 6 hours)

set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
source "${REPO_ROOT}/.env.local" 2>/dev/null

NBA_REPO="${REPO_ROOT}/../nomos-nba-agent"
LAST_HASH_FILE="${REPO_ROOT}/data/.last-engine-hash"
LOG="${REPO_ROOT}/logs/agents/auto-deploy-$(date +%Y-%m-%d).log"
mkdir -p "$(dirname "$LOG")"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $1" | tee -a "$LOG"; }

# Check current engine hash
CURRENT_HASH=$(md5sum "$NBA_REPO/features/engine.py" 2>/dev/null | cut -d' ' -f1)
LAST_HASH=$(cat "$LAST_HASH_FILE" 2>/dev/null || echo "none")

if [ "$CURRENT_HASH" = "$LAST_HASH" ]; then
    log "Engine unchanged (hash=$CURRENT_HASH). Skipping deploy."
    exit 0
fi

log "Engine CHANGED! Old=$LAST_HASH New=$CURRENT_HASH"
log "Deploying to all 6 NBA islands..."

# Step 1: Ensure hf-space/features/engine.py is in sync
cp "$NBA_REPO/features/engine.py" "$NBA_REPO/hf-space/features/engine.py"

# Step 2: Commit if needed
cd "$NBA_REPO"
if ! git diff --quiet hf-space/features/engine.py 2>/dev/null; then
    git add hf-space/features/engine.py
    git commit -m "sync: engine.py to hf-space (auto-deploy)" || true
    git pull --rebase --quiet origin main 2>/dev/null || true
    git push || true
fi

# Step 3: Subtree split
git subtree split --prefix=hf-space -b hf-deploy 2>/dev/null || true

# Step 4: Push to all 6 spaces (all on Nomos42 account)
SPACES="nba-quant nba-quant-2 nba-evo-3 nba-evo-4 nba-evo-5 nba-evo-6"
SUCCESS=0
FAIL=0

for SPACE in $SPACES; do
    log "  Pushing to Nomos42/$SPACE..."
    if git push "https://user:${HF_TOKEN_3}@huggingface.co/spaces/Nomos42/$SPACE" hf-deploy:main --force 2>>"$LOG"; then
        log "  ✓ $SPACE deployed"
        SUCCESS=$((SUCCESS + 1))
    else
        log "  ✗ $SPACE FAILED"
        FAIL=$((FAIL + 1))
    fi
done

# Step 5: Save hash
echo "$CURRENT_HASH" > "$LAST_HASH_FILE"

# Step 6: Alert
log "Deploy complete: $SUCCESS/6 success, $FAIL failed"
if [ -n "$TELEGRAM_BOT_TOKEN" ]; then
    MSG="Engine auto-deploy: $SUCCESS/6 spaces updated. Hash: ${CURRENT_HASH:0:8}"
    curl -sf -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -H "Content-Type: application/json" \
        -d "{\"chat_id\":\"6582544948\",\"text\":\"$MSG\"}" > /dev/null 2>&1
fi
