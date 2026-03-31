#!/bin/bash
# Deploy all 7 monitoring agent HF Spaces
# LBJLincoln: fleet-monitor, island-coordinator, betting-monitor
# LBJLincoln26: quality-tracker, research-radar, predictions-monitor, political-monitor

set -uo pipefail
source /home/termius/mon-ipad/.env.local 2>/dev/null

AGENTS_DIR="/home/termius/mon-ipad/hf-agents"
WORK_DIR="/tmp/hf-deploy-agents"
mkdir -p "$WORK_DIR"

log() { echo "[$(date -u +%H:%M:%S)] $1"; }

deploy_space() {
    local AGENT_NAME="$1"
    local HF_USER="$2"
    local HF_TOKEN_VAR="$3"
    local TOKEN="${!HF_TOKEN_VAR}"

    local SPACE_ID="$HF_USER/$AGENT_NAME"
    local REPO_DIR="$WORK_DIR/$AGENT_NAME"

    log "[$AGENT_NAME] Creating space $SPACE_ID..."

    # Create space via API (ignore if exists)
    curl -sf -X POST "https://huggingface.co/api/repos/create" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"type\":\"space\",\"name\":\"$AGENT_NAME\",\"sdk\":\"gradio\",\"private\":false}" \
        2>/dev/null || true

    # Clone or init repo
    rm -rf "$REPO_DIR"
    GIT_URL="https://user:${TOKEN}@huggingface.co/spaces/$SPACE_ID"

    if git clone --depth 1 "$GIT_URL" "$REPO_DIR" 2>/dev/null; then
        log "[$AGENT_NAME] Cloned existing space"
    else
        mkdir -p "$REPO_DIR"
        cd "$REPO_DIR"
        git init
        git remote add origin "$GIT_URL"
        log "[$AGENT_NAME] Created new repo"
    fi

    # Copy files
    cp "$AGENTS_DIR/$AGENT_NAME/README.md" "$REPO_DIR/"
    cp "$AGENTS_DIR/$AGENT_NAME/requirements.txt" "$REPO_DIR/"
    cp "$AGENTS_DIR/$AGENT_NAME/app.py" "$REPO_DIR/"

    # Commit and push
    cd "$REPO_DIR"
    git add -A
    git commit -m "Deploy $AGENT_NAME monitoring agent" 2>/dev/null || true

    if git push --force origin main 2>/dev/null || git push --force origin master 2>/dev/null; then
        log "[$AGENT_NAME] PUSHED to $SPACE_ID"
    else
        # Try pushing to main (new repo)
        git branch -M main
        git push -u origin main --force 2>/dev/null && log "[$AGENT_NAME] PUSHED (new)" || log "[$AGENT_NAME] PUSH FAILED"
    fi

    # Set secrets
    for SECRET_NAME in TELEGRAM_BOT_TOKEN NOMOS_NBA_BOT_TOKEN STUPID_POLITICAL_BOT_TOKEN FORGE_BOT_TOKEN GOOGLE_API_KEY OPENAI_API_KEY; do
        SECRET_VALUE="${!SECRET_NAME:-}"
        if [ -n "$SECRET_VALUE" ]; then
            curl -sf -X POST "https://huggingface.co/api/spaces/$SPACE_ID/secrets" \
                -H "Authorization: Bearer $TOKEN" \
                -H "Content-Type: application/json" \
                -d "{\"key\":\"$SECRET_NAME\",\"value\":\"$SECRET_VALUE\"}" \
                2>/dev/null || true
        fi
    done
    log "[$AGENT_NAME] Secrets set"
}

# Deploy in parallel — 4 to LBJLincoln, 3 to LBJLincoln26
log "=== DEPLOYING 7 MONITORING AGENTS ==="

# LBJLincoln account
deploy_space "fleet-monitor" "LBJLincoln" "HF_TOKEN" &
deploy_space "island-coordinator" "LBJLincoln" "HF_TOKEN" &
deploy_space "betting-monitor" "LBJLincoln" "HF_TOKEN" &

# LBJLincoln26 account
deploy_space "quality-tracker" "LBJLincoln26" "HF_TOKEN_2" &
deploy_space "research-radar" "LBJLincoln26" "HF_TOKEN_2" &
deploy_space "predictions-monitor" "LBJLincoln26" "HF_TOKEN_2" &
deploy_space "political-monitor" "LBJLincoln26" "HF_TOKEN_2" &

wait
log "=== ALL DEPLOYMENTS COMPLETE ==="
