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
    local space_name="${1:?Usage: deploy-hf-space.sh create <space-name> <hf-token> --space-num <N> [--account <username>]}"
    local hf_token="${2:?HF token required}"
    local account="LBJLincoln"
    local space_num=""

    # Parse optional args
    shift 2
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --account) account="$2"; shift 2 ;;
            --space-num) space_num="$2"; shift 2 ;;
            *) err "Unknown option: $1"; exit 1 ;;
        esac
    done

    if [[ -z "$space_num" ]]; then
        err "--space-num <N> is required (1-6)"
        exit 1
    fi

    log "Creating HF Space: $account/$space_name (Space #$space_num)"

    # Check huggingface_hub is available
    if ! python3 -c "import huggingface_hub" 2>/dev/null; then
        err "huggingface_hub not installed. Run: pip install huggingface_hub"
        exit 1
    fi

    # Load secrets from .env.local
    if [[ -f "$REPO_ROOT/.env.local" ]]; then
        source "$REPO_ROOT/.env.local"
        log "Loaded secrets from .env.local"
    fi

    # Create Space + upload files + set secrets
    python3 <<PYEOF
import os
from huggingface_hub import HfApi

api = HfApi(token="$hf_token")
repo_id = f"$account/$space_name"

# 1. Create Space
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

# 2. Upload all files
hf_dir = "$HF_SPACE_DIR"
files_to_upload = [
    ("Dockerfile", "Dockerfile"),
    ("entrypoint.sh", "entrypoint.sh"),
    ("setup-workflows.py", "setup-workflows.py"),
]
for local_name, repo_name in files_to_upload:
    path = os.path.join(hf_dir, local_name)
    if os.path.exists(path):
        api.upload_file(path_or_fileobj=path, path_in_repo=repo_name,
                        repo_id=repo_id, repo_type="space")
        print(f"  Uploaded {repo_name}")

# Upload workflows
wf_dir = os.path.join(hf_dir, "n8n-workflows")
if os.path.isdir(wf_dir):
    for fname in sorted(os.listdir(wf_dir)):
        if fname.endswith(".json"):
            api.upload_file(
                path_or_fileobj=os.path.join(wf_dir, fname),
                path_in_repo=f"n8n-workflows/{fname}",
                repo_id=repo_id, repo_type="space",
            )
            print(f"  Uploaded n8n-workflows/{fname}")

# 3. Set all secrets
print("\nSetting Space secrets...")
secrets = {
    "SPACE_NUMBER": "$space_num",
    "SUPABASE_PASSWORD": os.environ.get("SUPABASE_PASSWORD", ""),
    "SUPABASE_HOST": os.environ.get("SUPABASE_HOST", "aws-1-eu-west-1.pooler.supabase.com"),
    "SUPABASE_USER": os.environ.get("SUPABASE_USER", "postgres.ayqviqmxifzmhphiqfmj"),
    "PINECONE_API_KEY": os.environ.get("PINECONE_API_KEY", ""),
    "PINECONE_HOST": os.environ.get("PINECONE_HOST", ""),
    "JINA_API_KEY": os.environ.get("JINA_API_KEY", ""),
    "NEO4J_URI": os.environ.get("NEO4J_URI", ""),
    "NEO4J_PASSWORD": os.environ.get("NEO4J_PASSWORD", ""),
    "COHERE_API_KEY": os.environ.get("COHERE_API_KEY", ""),
    "GOOGLE_API_KEY": os.environ.get("GOOGLE_API_KEY", ""),
    "OPENROUTER_API_KEY": os.environ.get("OPENROUTER_API_KEY", ""),
    "OPENROUTER_KEY_STANDARD": os.environ.get("OPENROUTER_KEY_STANDARD", ""),
    "OPENROUTER_KEY_GRAPH": os.environ.get("OPENROUTER_KEY_GRAPH", ""),
    "OPENROUTER_KEY_QUANTITATIVE": os.environ.get("OPENROUTER_KEY_QUANTITATIVE", ""),
    "OPENROUTER_KEY_ORCHESTRATOR": os.environ.get("OPENROUTER_KEY_ORCHESTRATOR", ""),
    "GROQ_API_KEY": os.environ.get("GROQ_API_KEY", ""),
    "GROQ_API_KEY_2": os.environ.get("GROQ_API_KEY_2", ""),
    "GROQ_API_KEY_3": os.environ.get("GROQ_API_KEY_3", ""),
    "GROQ_API_KEY_4": os.environ.get("GROQ_API_KEY_4", ""),
    "GROQ_API_KEY_5": os.environ.get("GROQ_API_KEY_5", ""),
    "N8N_ENCRYPTION_KEY": "sota-rag-2026-hf-space-key",
}

set_count = 0
for key, value in secrets.items():
    if value:
        try:
            api.add_space_secret(repo_id=repo_id, key=key, value=value)
            print(f"  Secret SET: {key} ({len(value)} chars)")
            set_count += 1
        except Exception as e:
            print(f"  Secret FAIL: {key} — {e}")
    else:
        print(f"  Secret SKIP: {key} (empty)")

url = f"https://{repo_id.replace('/', '-').lower()}.hf.space"
print(f"\n{set_count} secrets configured")
print(f"Space URL: {url}")
print(f"DB Schema: n8n_engine_{$space_num}")
PYEOF

    ok "Space #$space_num deployed with all secrets. Postgres schema: n8n_engine_$space_num"
}

cmd_deploy_all() {
    # Deploy all 6 n8n engine Spaces from .env.local config
    source "$REPO_ROOT/.env.local"

    local -A SPACE_CONFIG=(
        # space_num:account:name:token_var
        ["1"]="LBJLincoln:nomos-rag-engine:HF_TOKEN"
        ["2"]="LBJLincoln26:nomos-rag-engine-2:HF_TOKEN_2"
        ["3"]="LBJLincoln:nomos-rag-engine-3:HF_TOKEN"
        ["4"]="LBJLincoln26:nomos-rag-engine-4:HF_TOKEN_2"
        ["5"]="LBJLincoln:nomos-rag-engine-5:HF_TOKEN"
        ["6"]="LBJLincoln26:nomos-rag-engine-6:HF_TOKEN_2"
    )

    # Parse which Spaces to deploy (default: all)
    local spaces_to_deploy="${1:-1,2,3,4,5,6}"

    log "Deploying Spaces: $spaces_to_deploy"
    echo ""

    IFS=',' read -ra NUMS <<< "$spaces_to_deploy"
    local deployed=0
    local failed=0

    for num in "${NUMS[@]}"; do
        num=$(echo "$num" | tr -d ' ')
        local config="${SPACE_CONFIG[$num]:-}"
        if [[ -z "$config" ]]; then
            err "Unknown Space number: $num"
            ((failed++))
            continue
        fi

        IFS=':' read -r account name token_var <<< "$config"
        local token="${!token_var}"

        if [[ -z "$token" ]]; then
            err "Space #$num: Token $token_var is empty"
            ((failed++))
            continue
        fi

        log "━━━ Deploying Space #$num ($account/$name) ━━━"
        cmd_create "$name" "$token" --account "$account" --space-num "$num"

        if [[ $? -eq 0 ]]; then
            ((deployed++))
        else
            ((failed++))
        fi
        echo ""
    done

    echo ""
    log "Deploy complete: $deployed deployed, $failed failed"
}

cmd_health_all() {
    # Check health of all known Spaces
    source "$REPO_ROOT/.env.local" 2>/dev/null || true

    local up=0
    local down=0
    for i in 1 2 3 4 5 6; do
        local var="HF_SPACE_${i}_URL"
        local url="${!var:-}"
        if [[ -z "$url" ]]; then continue; fi

        local code
        code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$url/healthz" 2>/dev/null || echo "000")
        if [[ "$code" == "200" ]]; then
            ok "Space #$i: UP ($url)"
            ((up++))
        else
            err "Space #$i: DOWN (HTTP $code) — $url"
            ((down++))
        fi
    done
    echo ""
    log "Result: $up UP, $down DOWN"
}

# ── Main ──────────────────────────────────────────────────────────────────────

case "${1:-help}" in
    create)      shift; cmd_create "$@" ;;
    deploy-all)  shift; cmd_deploy_all "$@" ;;
    status)      shift; cmd_status "$@" ;;
    health)      shift; cmd_health "$@" ;;
    health-all)  cmd_health_all ;;
    list)        cmd_list ;;
    *)
        echo "Usage: $(basename "$0") <command> [args]"
        echo ""
        echo "Commands:"
        echo "  create <name> <token> --space-num <N> [--account <user>]"
        echo "                                        Create/update single HF Space"
        echo "  deploy-all [1,2,3,4,5,6]              Deploy all (or specified) Spaces"
        echo "  status <url>                           Check Space status + workflows"
        echo "  health <url>                           Check single Space webhook health"
        echo "  health-all                             Check all 6 Spaces health"
        echo "  list                                   List known Spaces"
        ;;
esac
