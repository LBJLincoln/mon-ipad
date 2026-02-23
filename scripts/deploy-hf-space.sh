#!/bin/bash
# =================================================================
# Deploy HF Space — Push hf-space/ to HuggingFace Spaces
# =================================================================
# Copies workflow JSONs, pushes everything to HF Space via git.
# Sets secrets (API keys) via HF API.
#
# Usage:
#   source .env.local && bash scripts/deploy-hf-space.sh
#
# Prerequisites:
#   - HF_TOKEN in .env.local
#   - SUPABASE_PASSWORD in .env.local
#   - OPENROUTER_API_KEY in .env.local
#   - Workflow JSONs in n8n/live/
#
# Last updated: 2026-02-23
# =================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SPACE_NAME="nomos-rag-engine"
HF_USER="LBJLincoln"
HF_SPACE_DIR="$REPO_ROOT/hf-space"
WORK_DIR="/tmp/hf-space-deploy"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'; CYAN='\033[0;36m'; NC='\033[0m'

# Checks
# HF_TOKEN_2 is optional for secondary HF Space deployment (redundancy)
for var in HF_TOKEN SUPABASE_PASSWORD OPENROUTER_API_KEY; do
    if [ -z "${!var:-}" ]; then
        echo -e "${RED}ERROR: $var not set. Run: source .env.local${NC}"
        exit 1
    fi
done

echo -e "${CYAN}=== Deploy HF Space: ${HF_USER}/${SPACE_NAME} ===${NC}"

# ---- 1. Copy workflow JSONs ----
echo -e "${CYAN}[1/4] Copying workflow JSONs...${NC}"
mkdir -p "$HF_SPACE_DIR/n8n-workflows"
WF_COUNT=0
for wf in "$REPO_ROOT/n8n/live/"*.json; do
    [ -f "$wf" ] || continue
    # Skip duplicate quantitative (same webhook path as quantitative.json)
    [[ "$(basename "$wf")" == "quantitative-v2-template-fix.json" ]] && continue
    cp "$wf" "$HF_SPACE_DIR/n8n-workflows/"
    echo "  Copied: $(basename "$wf")"
    WF_COUNT=$((WF_COUNT + 1))
done
# Also copy PME workflows if they exist
for wf in "$REPO_ROOT/n8n/pme-connectors/"*.json; do
    [ -f "$wf" ] || continue
    cp "$wf" "$HF_SPACE_DIR/n8n-workflows/"
    echo "  Copied PME: $(basename "$wf")"
    WF_COUNT=$((WF_COUNT + 1))
done
echo "  Total: $WF_COUNT workflow files"

# ---- 2. Set HF Space secrets via API ----
echo -e "${CYAN}[2/4] Setting HF Space secrets...${NC}"

set_secret() {
    local key="$1" value="$2"
    HTTP=$(curl -s -o /dev/null -w "%{http_code}" \
        -X POST "https://huggingface.co/api/spaces/${HF_USER}/${SPACE_NAME}/secrets" \
        -H "Authorization: Bearer ${HF_TOKEN}" \
        -H "Content-Type: application/json" \
        -d "{\"key\":\"$key\",\"value\":\"$value\"}" 2>/dev/null || echo "ERR")
    if [ "$HTTP" = "200" ] || [ "$HTTP" = "409" ]; then
        echo -e "  ${GREEN}OK${NC} $key"
    else
        echo -e "  ${YELLOW}$HTTP${NC} $key (may need manual update)"
    fi
}

set_secret "SUPABASE_PASSWORD" "$SUPABASE_PASSWORD"
set_secret "SUPABASE_HOST" "${SUPABASE_HOST:-aws-0-eu-west-1.pooler.supabase.com}"
set_secret "SUPABASE_PORT" "${SUPABASE_PORT:-6543}"
set_secret "SUPABASE_DB" "${SUPABASE_DB:-postgres}"
set_secret "SUPABASE_USER" "${SUPABASE_USER:-postgres.kfyrtsmdolgioyxsglbz}"
set_secret "OPENROUTER_API_KEY" "$OPENROUTER_API_KEY"
set_secret "JINA_API_KEY" "${JINA_API_KEY:-}"
set_secret "PINECONE_API_KEY" "${PINECONE_API_KEY:-}"
set_secret "PINECONE_HOST" "${PINECONE_HOST:-}"
set_secret "NEO4J_URI" "${NEO4J_URI:-}"
set_secret "NEO4J_AUTH" "${NEO4J_AUTH:-neo4j/${NEO4J_PASSWORD:-}}"
set_secret "N8N_ENCRYPTION_KEY" "${N8N_ENCRYPTION_KEY:-sota-rag-2026-hf-space-key}"
set_secret "COHERE_API_KEY" "${COHERE_API_KEY:-}"
set_secret "GOOGLE_API_KEY" "${GOOGLE_API_KEY:-}"

# Per-pipeline OpenRouter keys (all default to main key until user adds separate accounts)
set_secret "OPENROUTER_KEY_STANDARD" "${OPENROUTER_KEY_STANDARD:-${OPENROUTER_API_KEY}}"
set_secret "OPENROUTER_KEY_GRAPH" "${OPENROUTER_KEY_GRAPH:-${OPENROUTER_API_KEY}}"
set_secret "OPENROUTER_KEY_QUANTITATIVE" "${OPENROUTER_KEY_QUANTITATIVE:-${OPENROUTER_API_KEY}}"
set_secret "OPENROUTER_KEY_ORCHESTRATOR" "${OPENROUTER_KEY_ORCHESTRATOR:-${OPENROUTER_API_KEY}}"
set_secret "OPENROUTER_KEY_PME" "${OPENROUTER_KEY_PME:-${OPENROUTER_API_KEY}}"

# ---- 3. Push to HF Space via git ----
echo -e "${CYAN}[3/4] Pushing to HF Space...${NC}"

rm -rf "$WORK_DIR"
cp -r "$HF_SPACE_DIR" "$WORK_DIR"
cd "$WORK_DIR"

git init
git config user.email "alexis.moret6@outlook.fr"
git config user.name "LBJLincoln"
git add -A
git commit -m "fix: v5.5 — remove nodeCredentialType + fix Cohere API key"

REMOTE_URL="https://${HF_USER}:${HF_TOKEN}@huggingface.co/spaces/${HF_USER}/${SPACE_NAME}"
git remote add space "$REMOTE_URL" 2>/dev/null || git remote set-url space "$REMOTE_URL"
git push -f space main 2>&1 || git push -f space master:main 2>&1

cd "$REPO_ROOT"
rm -rf "$WORK_DIR"

echo -e "${GREEN}  Pushed to HF Space${NC}"

# ---- 4. Wait for build + verify ----
echo -e "${CYAN}[4/4] Waiting for HF Space build...${NC}"
echo "  Build takes 5-10 min. Checking every 30s..."

for i in $(seq 1 20); do
    sleep 30
    HTTP=$(curl -s -o /dev/null -w "%{http_code}" \
        "https://lbjlincoln-nomos-rag-engine.hf.space/healthz" \
        --max-time 10 2>/dev/null || echo "000")
    if [ "$HTTP" = "200" ]; then
        echo -e "  ${GREEN}HF Space is UP (HTTP $HTTP) after $((i*30))s${NC}"

        # Verify webhooks
        echo ""
        echo "  Verifying webhooks..."
        for wh in rag-multi-index-v3 ff622742-6d71-4e91-af71-b5c666088717 3e0f8010-39e0-4bca-9d19-35e5094391a9 92217bb8-ffc8-459a-8331-3f553812c3d0 pme-assistant-gateway; do
            WH_HTTP=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
                "https://lbjlincoln-nomos-rag-engine.hf.space/webhook/$wh" \
                -H "Content-Type: application/json" \
                -d '{"query":"deploy-verify"}' --max-time 30 2>/dev/null || echo "ERR")
            echo "    $wh: HTTP $WH_HTTP"
        done
        break
    fi
    echo "  Not ready yet (HTTP $HTTP) — waiting... ($((i*30))s)"
done

echo ""
echo -e "${GREEN}=== DEPLOYMENT COMPLETE ===${NC}"
echo "  Space URL: https://huggingface.co/spaces/${HF_USER}/${SPACE_NAME}"
echo "  n8n URL:   https://lbjlincoln-nomos-rag-engine.hf.space"
echo "  Workers:   3 (queue mode, Redis)"
echo "  Database:  Supabase PostgreSQL (persistent)"
echo "  Multi-key: OPENROUTER_KEY_{STANDARD,GRAPH,QUANTITATIVE,ORCHESTRATOR,PME}"
echo ""
echo "  To add new OpenRouter keys:"
echo "    export OPENROUTER_KEY_STANDARD=sk-or-v1-xxx"
echo "    export OPENROUTER_KEY_GRAPH=sk-or-v1-yyy"
echo "    bash scripts/deploy-hf-space.sh  # re-deploy with new keys"

# ---- SECONDARY HF SPACE DEPLOYMENT (OPTIONAL) ----
# Secondary HF account for redundancy. Set HF_TOKEN_2 to deploy to a second HF Space.
if [ -n "${HF_TOKEN_2:-}" ]; then
    echo ""
    echo -e "${CYAN}=== SECONDARY HF SPACE DEPLOYMENT ===${NC}"
    echo "  HF_TOKEN_2 detected — deploying to secondary account..."

    SPACE_NAME_2="nomos-rag-engine-2"
    read -p "  Secondary space name (default: $SPACE_NAME_2): " INPUT_SPACE
    SPACE_NAME_2="${INPUT_SPACE:-$SPACE_NAME_2}"

    echo -e "${CYAN}  Deploying to ${HF_USER}/${SPACE_NAME_2}...${NC}"

    # Set secrets on secondary space
    echo "  Setting secrets on secondary space..."
    set_secret_2() {
        local key="$1" value="$2"
        HTTP=$(curl -s -o /dev/null -w "%{http_code}" \
            -X POST "https://huggingface.co/api/spaces/${HF_USER}/${SPACE_NAME_2}/secrets" \
            -H "Authorization: Bearer ${HF_TOKEN_2}" \
            -H "Content-Type: application/json" \
            -d "{\"key\":\"$key\",\"value\":\"$value\"}" 2>/dev/null || echo "ERR")
        if [ "$HTTP" = "200" ] || [ "$HTTP" = "409" ]; then
            echo -e "    ${GREEN}OK${NC} $key"
        else
            echo -e "    ${YELLOW}$HTTP${NC} $key (may need manual update)"
        fi
    }

    set_secret_2 "SUPABASE_PASSWORD" "$SUPABASE_PASSWORD"
    set_secret_2 "SUPABASE_HOST" "${SUPABASE_HOST:-aws-0-eu-west-1.pooler.supabase.com}"
    set_secret_2 "SUPABASE_PORT" "${SUPABASE_PORT:-6543}"
    set_secret_2 "SUPABASE_DB" "${SUPABASE_DB:-postgres}"
    set_secret_2 "SUPABASE_USER" "${SUPABASE_USER:-postgres.kfyrtsmdolgioyxsglbz}"
    set_secret_2 "OPENROUTER_API_KEY" "$OPENROUTER_API_KEY"
    set_secret_2 "JINA_API_KEY" "${JINA_API_KEY:-}"
    set_secret_2 "PINECONE_API_KEY" "${PINECONE_API_KEY:-}"
    set_secret_2 "PINECONE_HOST" "${PINECONE_HOST:-}"
    set_secret_2 "NEO4J_URI" "${NEO4J_URI:-}"
    set_secret_2 "NEO4J_AUTH" "${NEO4J_AUTH:-neo4j/${NEO4J_PASSWORD:-}}"
    set_secret_2 "N8N_ENCRYPTION_KEY" "${N8N_ENCRYPTION_KEY:-sota-rag-2026-hf-space-key-2}"
    set_secret_2 "COHERE_API_KEY" "${COHERE_API_KEY:-}"
    set_secret_2 "GOOGLE_API_KEY" "${GOOGLE_API_KEY:-}"
    set_secret_2 "OPENROUTER_KEY_STANDARD" "${OPENROUTER_KEY_STANDARD:-${OPENROUTER_API_KEY}}"
    set_secret_2 "OPENROUTER_KEY_GRAPH" "${OPENROUTER_KEY_GRAPH:-${OPENROUTER_API_KEY}}"
    set_secret_2 "OPENROUTER_KEY_QUANTITATIVE" "${OPENROUTER_KEY_QUANTITATIVE:-${OPENROUTER_API_KEY}}"
    set_secret_2 "OPENROUTER_KEY_ORCHESTRATOR" "${OPENROUTER_KEY_ORCHESTRATOR:-${OPENROUTER_API_KEY}}"
    set_secret_2 "OPENROUTER_KEY_PME" "${OPENROUTER_KEY_PME:-${OPENROUTER_API_KEY}}"

    # Push to secondary HF Space
    echo -e "${CYAN}  Pushing to secondary HF Space...${NC}"
    WORK_DIR_2="/tmp/hf-space-deploy-2"
    rm -rf "$WORK_DIR_2"
    cp -r "$HF_SPACE_DIR" "$WORK_DIR_2"
    cd "$WORK_DIR_2"

    git init
    git config user.email "alexis.moret6@outlook.fr"
    git config user.name "LBJLincoln"
    git add -A
    git commit -m "fix: v5.4 — secondary HF Space deployment"

    REMOTE_URL_2="https://${HF_USER}:${HF_TOKEN_2}@huggingface.co/spaces/${HF_USER}/${SPACE_NAME_2}"
    git remote add space2 "$REMOTE_URL_2" 2>/dev/null || git remote set-url space2 "$REMOTE_URL_2"
    git push -f space2 main 2>&1 || git push -f space2 master:main 2>&1

    cd "$REPO_ROOT"
    rm -rf "$WORK_DIR_2"

    echo -e "${GREEN}  Secondary deployment complete!${NC}"
    echo "  Space URL: https://huggingface.co/spaces/${HF_USER}/${SPACE_NAME_2}"
    echo "  Build takes 5-10 min. Check status at the Space URL."
else
    echo ""
    echo "  Tip: For redundancy, set HF_TOKEN_2 to deploy to a secondary HF Space:"
    echo "    export HF_TOKEN_2=hf_..."
    echo "    bash scripts/deploy-hf-space.sh"
fi
