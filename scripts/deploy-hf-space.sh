#!/usr/bin/env bash
# deploy-hf-space.sh — Automated HuggingFace Space deployer for n8n instances
#
# Creates/updates an HF Space with n8n + all RAG pipeline workflows.
# Uploads Dockerfile, entrypoint, setup-workflows.py, and env vars.
#
# Usage:
#   ./scripts/deploy-hf-space.sh create <space-name> <hf-token> [--account <username>]
#   ./scripts/deploy-hf-space.sh status <space-url>
#   ./scripts/deploy-hf-space.sh health <space-url>
#   ./scripts/deploy-hf-space.sh list
#
# Examples:
#   ./scripts/deploy-hf-space.sh create nomos-rag-engine-2 hf_xxxx --account LBJLincoln26
#   ./scripts/deploy-hf-space.sh health https://lbjlincoln-nomos-rag-engine.hf.space
#   ./scripts/deploy-hf-space.sh list

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
HF_SPACE_DIR="$REPO_ROOT/hf-space"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${BLUE}[deploy]${NC} $*"; }
ok()   { echo -e "${GREEN}[  OK ]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*"; }

# ── Known Spaces ──────────────────────────────────────────────────────────────

declare -A KNOWN_SPACES=(
    ["space1"]="https://lbjlincoln-nomos-rag-engine.hf.space"
)

# ── Commands ──────────────────────────────────────────────────────────────────

cmd_health() {
    local url="${1:?Usage: deploy-hf-space.sh health <space-url>}"
    # Strip trailing slash
    url="${url%/}"

    log "Checking health: $url"

    # 1. Basic HTTP check
    local http_code
    http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 15 "$url/healthz" 2>/dev/null || echo "000")
    if [[ "$http_code" == "200" ]]; then
        ok "Healthz: HTTP $http_code"
    else
        err "Healthz: HTTP $http_code (expected 200)"
    fi

    # 2. Check all webhook paths
    local -a WEBHOOKS=(
        "/webhook/rag-multi-index-v3:Standard"
        "/webhook/ff622742-6d71-4e91-af71-b5c666088717:Graph"
        "/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9:Quantitative"
        "/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0:Orchestrator"
        "/webhook/rag-v6-ingestion:Ingestion"
    )

    local pass=0 fail=0
    for entry in "${WEBHOOKS[@]}"; do
        local path="${entry%%:*}"
        local name="${entry##*:}"
        # Use GET — webhook should return 405 (Method Not Allowed) if alive, 404 if not registered
        local code
        code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$url$path" 2>/dev/null || echo "000")
        if [[ "$code" != "404" && "$code" != "000" ]]; then
            ok "  $name ($path): HTTP $code"
            ((pass++))
        else
            err "  $name ($path): HTTP $code (NOT FOUND)"
            ((fail++))
        fi
    done

    echo ""
    log "Result: $pass alive, $fail missing"
    return $((fail > 0 ? 1 : 0))
}

cmd_status() {
    local url="${1:?Usage: deploy-hf-space.sh status <space-url>}"
    url="${url%/}"

    log "Checking Space status: $url"

    # REST API endpoint
    local rest_url="$url/rest/workflows"
    local rest_code
    rest_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$rest_url" 2>/dev/null || echo "000")

    if [[ "$rest_code" == "200" ]]; then
        ok "REST API accessible (HTTP $rest_code)"
        # Count workflows
        local count
        count=$(curl -s --max-time 10 "$rest_url" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('data',[])))" 2>/dev/null || echo "?")
        log "Workflows deployed: $count"

        # List active workflows
        curl -s --max-time 10 "$rest_url" 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin).get('data', [])
for wf in data:
    status = 'ACTIVE' if wf.get('active') else 'INACTIVE'
    print(f'  [{status:8s}] {wf[\"name\"]}')" 2>/dev/null || true
    else
        err "REST API not accessible (HTTP $rest_code)"
    fi
}

cmd_list() {
    log "Known HF Spaces:"
    for name in "${!KNOWN_SPACES[@]}"; do
        local url="${KNOWN_SPACES[$name]}"
        local code
        code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 8 "$url/healthz" 2>/dev/null || echo "000")
        local status_icon="[DOWN]"
        [[ "$code" == "200" ]] && status_icon="[ UP ]"
        echo -e "  $status_icon $name: $url"
    done
    echo ""

    # Also check env vars for additional Spaces
    if [[ -f "$REPO_ROOT/.env.local" ]]; then
        log "Spaces from .env.local:"
        grep -E '^N8N_HOST' "$REPO_ROOT/.env.local" 2>/dev/null | while read -r line; do
            echo "  $line"
        done
    fi
}

cmd_create() {
    local space_name="${1:?Usage: deploy-hf-space.sh create <space-name> <hf-token> [--account <username>]}"
    local hf_token="${2:?HF token required}"
    local account="LBJLincoln"

    # Parse optional args
    shift 2
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --account) account="$2"; shift 2 ;;
            *) err "Unknown option: $1"; exit 1 ;;
        esac
    done

    log "Creating HF Space: $account/$space_name"

    # Check huggingface_hub is available
    if ! python3 -c "import huggingface_hub" 2>/dev/null; then
        err "huggingface_hub not installed. Run: pip install huggingface_hub"
        exit 1
    fi

    # Create Space via API
    python3 <<PYEOF
import os
from huggingface_hub import HfApi

api = HfApi(token="$hf_token")
repo_id = f"$account/$space_name"

try:
    api.create_repo(
        repo_id=repo_id,
        repo_type="space",
        space_sdk="docker",
        space_hardware="cpu-basic",
        private=False,
    )
    print(f"Space created: {repo_id}")
except Exception as e:
    if "already exists" in str(e).lower() or "409" in str(e):
        print(f"Space already exists: {repo_id}")
    else:
        raise

# Upload Dockerfile
dockerfile_path = "$HF_SPACE_DIR/Dockerfile"
if os.path.exists(dockerfile_path):
    api.upload_file(
        path_or_fileobj=dockerfile_path,
        path_in_repo="Dockerfile",
        repo_id=repo_id,
        repo_type="space",
    )
    print("Uploaded Dockerfile")

# Upload entrypoint
entrypoint_path = "$HF_SPACE_DIR/entrypoint.sh"
if os.path.exists(entrypoint_path):
    api.upload_file(
        path_or_fileobj=entrypoint_path,
        path_in_repo="entrypoint.sh",
        repo_id=repo_id,
        repo_type="space",
    )
    print("Uploaded entrypoint.sh")

# Upload setup-workflows
setup_path = "$HF_SPACE_DIR/setup-workflows.py"
if os.path.exists(setup_path):
    api.upload_file(
        path_or_fileobj=setup_path,
        path_in_repo="setup-workflows.py",
        repo_id=repo_id,
        repo_type="space",
    )
    print("Uploaded setup-workflows.py")

# Upload workflows
wf_dir = "$HF_SPACE_DIR/n8n-workflows"
if os.path.isdir(wf_dir):
    for fname in os.listdir(wf_dir):
        if fname.endswith(".json"):
            api.upload_file(
                path_or_fileobj=os.path.join(wf_dir, fname),
                path_in_repo=f"n8n-workflows/{fname}",
                repo_id=repo_id,
                repo_type="space",
            )
            print(f"  Uploaded n8n-workflows/{fname}")

print(f"\nSpace URL: https://{repo_id.replace('/', '-').lower()}.hf.space")
print("NOTE: Set environment variables (secrets) via HF web UI or API")
PYEOF

    ok "Space creation complete. Set env vars via HF Settings > Secrets."
}

# ── Main ──────────────────────────────────────────────────────────────────────

case "${1:-help}" in
    create)  shift; cmd_create "$@" ;;
    status)  shift; cmd_status "$@" ;;
    health)  shift; cmd_health "$@" ;;
    list)    cmd_list ;;
    *)
        echo "Usage: $(basename "$0") <command> [args]"
        echo ""
        echo "Commands:"
        echo "  create <name> <token> [--account <user>]  Create/update HF Space"
        echo "  status <url>                              Check Space status + workflows"
        echo "  health <url>                              Check all webhook health"
        echo "  list                                      List known Spaces"
        ;;
esac
