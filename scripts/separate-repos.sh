#!/bin/bash
# ============================================================
# separate-repos.sh — Clean separation of satellite repos
# ============================================================
# Each satellite repo gets ONLY its own files, not the full mon-ipad.
# This script clones each satellite, wipes it, copies only relevant
# files from mon-ipad, and force-pushes.
#
# Usage:
#   bash scripts/separate-repos.sh --all          # All 4 repos
#   bash scripts/separate-repos.sh --repo rag-tests  # Single repo
#   bash scripts/separate-repos.sh --dry-run --all   # Preview only
#
# Repos handled:
#   rag-website        — Next.js ETI site (4 secteurs)
#   rag-pme-connectors — Next.js PME site (15 apps)
#   rag-tests          — Eval scripts + datasets
#   rag-data-ingestion — n8n workflows + ingestion scripts
#
# SKIPPED:
#   rag-pme-usecases   — Already clean (43 KB, 1 commit)
#   rag-dashboard      — Stays in mon-ipad (shows all repos)
#
# Last updated: 2026-02-23
# ============================================================

set -euo pipefail

cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd)"
WORK_DIR="/tmp/repo-separation"
DRY_RUN=false
TARGET_REPO=""
DO_ALL=false

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run) DRY_RUN=true; shift;;
        --all) DO_ALL=true; shift;;
        --repo) TARGET_REPO="$2"; shift 2;;
        *) echo "Unknown arg: $1"; exit 1;;
    esac
done

if [[ "$DO_ALL" == "false" && -z "$TARGET_REPO" ]]; then
    echo "Usage: $0 --all | --repo <name> [--dry-run]"
    echo "Repos: rag-website, rag-pme-connectors, rag-tests, rag-data-ingestion"
    exit 1
fi

# ============================================================
# HELPER FUNCTIONS
# ============================================================

get_remote_url() {
    git -C "$REPO_ROOT" remote get-url "$1" 2>/dev/null
}

prepare_repo() {
    local repo="$1"
    local dest="$WORK_DIR/$repo"
    local url
    url=$(get_remote_url "$repo")

    echo -e "${BLUE}=== Preparing $repo ===${NC}"
    echo "  Remote: $url"

    if [[ "$DRY_RUN" == "true" ]]; then
        echo -e "  ${YELLOW}[DRY RUN] Would clone, wipe, and repopulate${NC}"
        return 0
    fi

    # Clone
    rm -rf "$dest"
    git clone "$url" "$dest" --quiet
    echo "  Cloned to $dest"

    # Wipe everything except .git
    find "$dest" -mindepth 1 -maxdepth 1 ! -name '.git' -exec rm -rf {} +
    echo "  Wiped all content (kept .git)"
}

copy_file() {
    local src="$1"
    local dst="$2"
    if [[ -e "$REPO_ROOT/$src" ]]; then
        mkdir -p "$(dirname "$dst")"
        cp -r "$REPO_ROOT/$src" "$dst"
    else
        echo -e "    ${YELLOW}WARN: $src not found${NC}"
    fi
}

finalize_repo() {
    local repo="$1"
    local dest="$WORK_DIR/$repo"
    local msg="feat: clean repo separation — only $repo content

Separated from mon-ipad monorepo. Each satellite repo now contains
only its own files. Directives sync via push-directives.sh.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"

    if [[ "$DRY_RUN" == "true" ]]; then
        echo -e "  ${YELLOW}[DRY RUN] Would commit and force push${NC}"
        return 0
    fi

    cd "$dest"
    git add -A
    git commit -m "$msg" --allow-empty
    echo ""
    echo -e "  ${YELLOW}Ready to force push $repo${NC}"
    echo "  Files:"
    find . -not -path './.git/*' -not -name '.git' -type f | sort | head -40
    FCOUNT=$(find . -not -path './.git/*' -not -name '.git' -type f | wc -l)
    echo "  Total: $FCOUNT files"
    echo ""

    read -p "  Force push $repo to origin/main? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git push --force origin main
        echo -e "  ${GREEN}PUSHED $repo${NC}"
    else
        echo -e "  ${RED}SKIPPED $repo${NC}"
    fi
    cd "$REPO_ROOT"
}

# ============================================================
# RAG-WEBSITE — Next.js ETI site
# ============================================================
separate_rag_website() {
    local repo="rag-website"
    local dest="$WORK_DIR/$repo"
    prepare_repo "$repo"
    [[ "$DRY_RUN" == "true" ]] && return 0

    echo "  Copying files..."

    # Next.js app files
    copy_file "website/src" "$dest/src"
    copy_file "website/public" "$dest/public"
    copy_file "website/package.json" "$dest/package.json"
    copy_file "website/package-lock.json" "$dest/package-lock.json"
    copy_file "website/next.config.ts" "$dest/next.config.ts"
    copy_file "website/tsconfig.json" "$dest/tsconfig.json"
    copy_file "website/tailwind.config.ts" "$dest/tailwind.config.ts"
    copy_file "website/postcss.config.js" "$dest/postcss.config.js"
    copy_file "website/vercel.json" "$dest/vercel.json"
    copy_file "website/next-env.d.ts" "$dest/next-env.d.ts"

    # .gitignore
    if [[ -f "$REPO_ROOT/website/.gitignore" ]]; then
        cp "$REPO_ROOT/website/.gitignore" "$dest/.gitignore"
    else
        cat > "$dest/.gitignore" << 'EOF'
node_modules/
.next/
.env.local
.env
.mcp.json
.claude/
*.tsbuildinfo
EOF
    fi

    # Devcontainer (flatten from .devcontainer/rag-website/ to .devcontainer/)
    mkdir -p "$dest/.devcontainer"
    # Adjusted devcontainer.json (path fix: no more rag-website subdirectory)
    cat > "$dest/.devcontainer/devcontainer.json" << 'EOF'
{
  "name": "Nomos AI — Website ETI (4 secteurs)",
  "image": "mcr.microsoft.com/devcontainers/universal:2",
  "features": {
    "ghcr.io/devcontainers/features/docker-in-docker:2": {},
    "ghcr.io/devcontainers/features/node:1": { "version": "20" }
  },
  "forwardPorts": [3000],
  "postCreateCommand": "bash .devcontainer/setup.sh",
  "customizations": {
    "vscode": {
      "extensions": [
        "bradlc.vscode-tailwindcss",
        "esbenp.prettier-vscode"
      ]
    }
  }
}
EOF

    cat > "$dest/.devcontainer/setup.sh" << 'SETUP'
#!/bin/bash
set -euo pipefail
echo "=== Nomos AI — rag-website Setup ==="
cd /workspaces/rag-website
npm install --silent 2>/dev/null || true
echo "Setup complete. Run: npm run dev"
SETUP
    chmod +x "$dest/.devcontainer/setup.sh"

    # CLAUDE.md from directives
    if [[ -f "$REPO_ROOT/directives/repos/rag-website.md" ]]; then
        cp "$REPO_ROOT/directives/repos/rag-website.md" "$dest/CLAUDE.md"
    fi

    finalize_repo "$repo"
}

# ============================================================
# RAG-PME-CONNECTORS — Next.js PME site (15 apps)
# ============================================================
separate_rag_pme_connectors() {
    local repo="rag-pme-connectors"
    local dest="$WORK_DIR/$repo"
    prepare_repo "$repo"
    [[ "$DRY_RUN" == "true" ]] && return 0

    echo "  Copying files..."

    # Next.js app files
    copy_file "website-pme-connectors/src" "$dest/src"
    copy_file "website-pme-connectors/public" "$dest/public"
    copy_file "website-pme-connectors/package.json" "$dest/package.json"
    copy_file "website-pme-connectors/package-lock.json" "$dest/package-lock.json"
    copy_file "website-pme-connectors/next.config.ts" "$dest/next.config.ts"
    copy_file "website-pme-connectors/tsconfig.json" "$dest/tsconfig.json"
    copy_file "website-pme-connectors/tailwind.config.ts" "$dest/tailwind.config.ts"
    copy_file "website-pme-connectors/postcss.config.js" "$dest/postcss.config.js"
    copy_file "website-pme-connectors/vercel.json" "$dest/vercel.json"

    # .gitignore
    cat > "$dest/.gitignore" << 'EOF'
node_modules/
.next/
.env.local
.env
.mcp.json
.claude/
*.tsbuildinfo
EOF

    # CLAUDE.md from directives
    if [[ -f "$REPO_ROOT/directives/repos/rag-pme-connectors.md" ]]; then
        cp "$REPO_ROOT/directives/repos/rag-pme-connectors.md" "$dest/CLAUDE.md"
    fi

    finalize_repo "$repo"
}

# ============================================================
# RAG-TESTS — Eval scripts + datasets
# ============================================================
separate_rag_tests() {
    local repo="rag-tests"
    local dest="$WORK_DIR/$repo"
    prepare_repo "$repo"
    [[ "$DRY_RUN" == "true" ]] && return 0

    echo "  Copying files..."

    # Eval scripts
    copy_file "eval" "$dest/eval"

    # Datasets
    copy_file "datasets" "$dest/datasets"

    # Analysis scripts
    mkdir -p "$dest/scripts"
    for script in analyze_n8n_executions.py run_n8n_analysis.py; do
        if [[ -f "$REPO_ROOT/scripts/$script" ]]; then
            cp "$REPO_ROOT/scripts/$script" "$dest/scripts/$script"
        fi
    done

    # docs directory for status output
    mkdir -p "$dest/docs"
    mkdir -p "$dest/logs/pipeline-results"

    # .gitignore
    cat > "$dest/.gitignore" << 'EOF'
.env.local
.env
__pycache__/
*.pyc
node_modules/
.mcp.json
.claude/
EOF

    # requirements.txt
    cat > "$dest/requirements.txt" << 'EOF'
requests>=2.31.0
python-dotenv>=1.0.0
numpy>=1.24.0
aiohttp>=3.9.0
EOF

    # Devcontainer
    mkdir -p "$dest/.devcontainer"
    cat > "$dest/.devcontainer/devcontainer.json" << 'EOF'
{
  "name": "Nomos AI — RAG Tests",
  "image": "mcr.microsoft.com/devcontainers/universal:2",
  "features": {
    "ghcr.io/devcontainers/features/python:1": { "version": "3.11" }
  },
  "forwardPorts": [5678],
  "postCreateCommand": "bash .devcontainer/setup.sh",
  "customizations": {
    "vscode": {
      "extensions": [
        "ms-python.python",
        "ms-toolsai.jupyter"
      ]
    }
  },
  "remoteEnv": {
    "VM_HOST": "34.136.180.66",
    "N8N_HOST": "http://34.136.180.66:5678",
    "REPO_ROLE": "rag-tests"
  }
}
EOF

    cat > "$dest/.devcontainer/setup.sh" << 'SETUP'
#!/bin/bash
set -euo pipefail
echo "=== Nomos AI — rag-tests Setup ==="

REPO_ROOT="/workspaces/rag-tests"
VM_HOST="${VM_HOST:-34.136.180.66}"
N8N_URL="http://${VM_HOST}:5678"

echo "[1/3] Installing Python dependencies..."
pip install -q -r "$REPO_ROOT/requirements.txt" 2>/dev/null || true

echo "[2/3] Checking VM connectivity..."
if curl -sf --connect-timeout 10 "${N8N_URL}/healthz" > /dev/null 2>&1; then
  echo "  VM n8n reachable"
else
  echo "  WARN: VM n8n not reachable directly — may need SSH tunnel"
fi

echo "[3/3] Verifying eval scripts..."
for script in eval/quick-test.py eval/iterative-eval.py eval/run-eval-parallel.py; do
  if [ -f "${REPO_ROOT}/${script}" ]; then
    echo "  OK: ${script}"
  else
    echo "  MISSING: ${script}"
  fi
done

echo ""
echo "=== Setup complete ==="
echo "  source .env.local && python3 eval/quick-test.py --questions 5 --pipeline standard"
SETUP
    chmod +x "$dest/.devcontainer/setup.sh"

    # CLAUDE.md from directives
    if [[ -f "$REPO_ROOT/directives/repos/rag-tests.md" ]]; then
        cp "$REPO_ROOT/directives/repos/rag-tests.md" "$dest/CLAUDE.md"
    fi

    finalize_repo "$repo"
}

# ============================================================
# RAG-DATA-INGESTION — n8n workflows + ingestion scripts
# ============================================================
separate_rag_data_ingestion() {
    local repo="rag-data-ingestion"
    local dest="$WORK_DIR/$repo"
    prepare_repo "$repo"
    [[ "$DRY_RUN" == "true" ]] && return 0

    echo "  Copying files..."

    # n8n workflows
    copy_file "n8n/live" "$dest/n8n/live"
    copy_file "n8n/validated" "$dest/n8n/validated"
    copy_file "n8n/sync.py" "$dest/n8n/sync.py"
    copy_file "n8n/manifest.json" "$dest/n8n/manifest.json"

    # Dataset scripts
    copy_file "datasets/scripts" "$dest/datasets/scripts"

    # .gitignore
    cat > "$dest/.gitignore" << 'EOF'
.env.local
.env
__pycache__/
*.pyc
node_modules/
.mcp.json
.claude/
EOF

    # Devcontainer (flatten)
    mkdir -p "$dest/.devcontainer"
    cat > "$dest/.devcontainer/devcontainer.json" << 'EOF'
{
  "name": "Nomos AI — Data Ingestion Stack",
  "image": "mcr.microsoft.com/devcontainers/universal:2",
  "features": {
    "ghcr.io/devcontainers/features/docker-in-docker:2": {},
    "ghcr.io/devcontainers/features/python:1": { "version": "3.11" }
  },
  "forwardPorts": [5678, 5432, 6379],
  "postCreateCommand": "bash .devcontainer/setup.sh",
  "customizations": {
    "vscode": {
      "extensions": [
        "ms-python.python",
        "ms-toolsai.jupyter"
      ]
    }
  },
  "remoteEnv": {
    "VM_HOST": "34.136.180.66",
    "N8N_HOST": "http://localhost:5678",
    "REPO_ROLE": "rag-data-ingestion"
  }
}
EOF

    # docker-compose.yml
    cp "$REPO_ROOT/.devcontainer/rag-data-ingestion/docker-compose.yml" "$dest/.devcontainer/docker-compose.yml"

    cat > "$dest/.devcontainer/setup.sh" << 'SETUP'
#!/bin/bash
set -euo pipefail
echo "=== Nomos AI — rag-data-ingestion Setup ==="

REPO_ROOT="/workspaces/rag-data-ingestion"
N8N_URL="http://localhost:5678"
WORKFLOW_DIR="${REPO_ROOT}/n8n/live"
MAX_WAIT=180

echo "[1/4] Starting n8n ingestion stack..."
if [ -f "${REPO_ROOT}/.devcontainer/docker-compose.yml" ]; then
  docker compose -f "${REPO_ROOT}/.devcontainer/docker-compose.yml" up -d
  echo "  n8n stack starting (main + 2 workers + PG + Redis)..."
else
  echo "  WARN: docker-compose.yml not found"
fi

echo "[2/4] Waiting for n8n..."
elapsed=0
until curl -sf "${N8N_URL}/healthz" > /dev/null 2>&1; do
  sleep 3; elapsed=$((elapsed + 3))
  if [ $elapsed -ge $MAX_WAIT ]; then
    echo "WARN: n8n not ready after ${MAX_WAIT}s — continuing anyway"
    break
  fi
done
[ $elapsed -lt $MAX_WAIT ] && echo "  n8n ready (${elapsed}s)"

echo "[3/4] Importing ingestion workflows..."
for wf in ingestion.json enrichment.json; do
  if [ -f "${WORKFLOW_DIR}/${wf}" ]; then
    curl -sf -X POST "${N8N_URL}/api/v1/workflows" \
      -H "Content-Type: application/json" \
      -d @"${WORKFLOW_DIR}/${wf}" > /dev/null 2>&1 && \
      echo "  Imported: ${wf}" || echo "  WARN: ${wf} skip"
  fi
done

echo "[4/4] Installing Python dependencies..."
pip install -q requests python-dotenv 2>/dev/null || true

echo ""
echo "=== Setup complete ==="
echo "  n8n: ${N8N_URL}"
echo "  source .env.local to set API keys"
SETUP
    chmod +x "$dest/.devcontainer/setup.sh"

    # CLAUDE.md from directives
    if [[ -f "$REPO_ROOT/directives/repos/rag-data-ingestion.md" ]]; then
        cp "$REPO_ROOT/directives/repos/rag-data-ingestion.md" "$dest/CLAUDE.md"
    fi

    finalize_repo "$repo"
}

# ============================================================
# MAIN
# ============================================================
mkdir -p "$WORK_DIR"

echo "============================================"
echo "  REPO SEPARATION SCRIPT"
echo "  Dry run: $DRY_RUN"
echo "  Work dir: $WORK_DIR"
echo "============================================"
echo ""

if [[ "$DO_ALL" == "true" ]]; then
    separate_rag_website
    echo ""
    separate_rag_pme_connectors
    echo ""
    separate_rag_tests
    echo ""
    separate_rag_data_ingestion
elif [[ -n "$TARGET_REPO" ]]; then
    case "$TARGET_REPO" in
        rag-website) separate_rag_website;;
        rag-pme-connectors) separate_rag_pme_connectors;;
        rag-tests) separate_rag_tests;;
        rag-data-ingestion) separate_rag_data_ingestion;;
        *) echo "Unknown repo: $TARGET_REPO"; exit 1;;
    esac
fi

echo ""
echo "============================================"
echo -e "  ${GREEN}SEPARATION COMPLETE${NC}"
echo "============================================"
echo ""
echo "Next steps:"
echo "  1. Verify each repo: gh api repos/LBJLincoln/<repo>/contents --jq '.[].name'"
echo "  2. Check Vercel: curl -s -o /dev/null -w '%{http_code}' https://<site>.vercel.app"
echo "  3. Update push-directives.sh if needed"
