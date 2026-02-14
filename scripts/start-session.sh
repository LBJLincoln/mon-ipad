#!/usr/bin/env bash
# =============================================================================
# start-session.sh — Lance Claude Code avec validation de tous les MCP servers
# Usage: ./scripts/start-session.sh [--check-only]
#   --check-only : teste tout sans lancer Claude Code a la fin
# =============================================================================
set -uo pipefail

# Resolve repo dir
if [[ -n "${BASH_SOURCE[0]:-}" && "${BASH_SOURCE[0]}" != "$0" ]]; then
    REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
else
    REPO_DIR="$(cd "$(dirname "$0")/.." 2>/dev/null && pwd)" || REPO_DIR="$(git rev-parse --show-toplevel 2>/dev/null)" || REPO_DIR="$PWD"
fi

CHECK_ONLY=false
[[ "${1:-}" == "--check-only" ]] && CHECK_ONLY=true

SETTINGS="$REPO_DIR/.claude/settings.json"
ENV_FILE="$REPO_DIR/.env.local"
VENV_PYTHON="$REPO_DIR/.venv/bin/python3"
MCP_TESTER="$REPO_DIR/scripts/test-mcp-server.py"

# Colors
G='\033[0;32m' R='\033[0;31m' Y='\033[1;33m' C='\033[0;36m' B='\033[1m' N='\033[0m'

passed=0 failed=0 warnings=0
declare -a results=()

ok()   { ((passed++)); results+=("${G}OK${N}    $1"); echo -e " ${G}ok${N}"; }
fail() { ((failed++)); results+=("${R}FAIL${N}  $1 — $2"); echo -e " ${R}fail${N}"; }
warn() { ((warnings++)); results+=("${Y}WARN${N}  $1 — $2"); echo -e " ${Y}warn${N}"; }

# Read a value from settings.json
cfg() {
    python3 -c "
import json, sys
d = json.load(open('$SETTINGS'))
try:
    result = eval(sys.argv[1], {'d': d})
    print(result)
except:
    print('', end='')
" "$1" 2>/dev/null
}

# Test a stdio MCP server using the Python tester
test_stdio() {
    local name="$1"
    shift
    local result
    result=$(timeout 30 python3 "$MCP_TESTER" --timeout 25 "$@" 2>/dev/null) || true

    if [[ -z "$result" ]]; then
        fail "$name" "timeout — no response"
        return
    fi

    local is_ok tc err
    is_ok=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('ok',False))" 2>/dev/null)
    tc=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tools_count',0))" 2>/dev/null)
    err=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('error',''))" 2>/dev/null)

    if [[ "$is_ok" == "True" ]]; then
        ok "$name ($tc tools)"
    elif [[ -n "$err" ]]; then
        fail "$name" "$err"
    else
        fail "$name" "unknown error"
    fi
}

# ═════════════════════════════════════════════════════════════════════════════

echo ""
echo -e "${B}${C}══════════════════════════════════════════════════${N}"
echo -e "${B}${C}  Multi-RAG Orchestrator — Session Startup${N}"
echo -e "${B}${C}  $(date '+%Y-%m-%d %H:%M:%S')${N}"
echo -e "${B}${C}══════════════════════════════════════════════════${N}"

# ── [1/4] Pre-flight ─────────────────────────────────────────────────────────
echo ""
echo -e "${B}[1/4] Pre-flight checks${N}"

echo -n "  settings.json"
[[ -f "$SETTINGS" ]] && ok "settings.json" || fail "settings.json" "not found at $SETTINGS"

echo -n "  .env.local"
[[ -f "$ENV_FILE" ]] && ok ".env.local" || warn ".env.local" "not found"

echo -n "  Python venv"
[[ -x "$VENV_PYTHON" ]] && ok "Python venv" || fail "Python venv" "$VENV_PYTHON missing"

echo -n "  MCP tester"
[[ -f "$MCP_TESTER" ]] && ok "test-mcp-server.py" || fail "test-mcp-server.py" "not found"

echo -n "  npx"
command -v npx &>/dev/null && ok "npx" || fail "npx" "not in PATH"

echo -n "  claude CLI"
command -v claude &>/dev/null && ok "claude CLI" || fail "claude CLI" "not in PATH"

# Load env
[[ -f "$ENV_FILE" ]] && { set -a; source "$ENV_FILE" 2>/dev/null; set +a; }

# ── [2/4] MCP Servers ────────────────────────────────────────────────────────
echo ""
echo -e "${B}[2/4] Testing MCP servers (7 servers)${N}"

tmpdir=$(mktemp -d)
trap "rm -rf '$tmpdir'" EXIT

# --- 1. n8n (HTTP — special: test via curl) ---
echo -n "  n8n (http)"
n8n_url="$(cfg "d['mcpServers']['n8n']['url']")"
n8n_auth="$(cfg "d['mcpServers']['n8n']['headers']['Authorization']")"
n8n_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 \
    -H "Authorization: $n8n_auth" "$n8n_url" 2>&1) || n8n_code="000"
[[ "$n8n_code" == "200" || "$n8n_code" == "405" ]] \
    && ok "n8n (HTTP $n8n_code — 3 tools)" \
    || fail "n8n" "HTTP $n8n_code"

# --- 2. neo4j (stdio binary) ---
echo -n "  neo4j"
export NEO4J_URI="$(cfg "d['mcpServers']['neo4j']['env']['NEO4J_URI']")"
export NEO4J_USERNAME="$(cfg "d['mcpServers']['neo4j']['env']['NEO4J_USERNAME']")"
export NEO4J_PASSWORD="$(cfg "d['mcpServers']['neo4j']['env']['NEO4J_PASSWORD']")"
export NEO4J_DATABASE="$(cfg "d['mcpServers']['neo4j']['env']['NEO4J_DATABASE']")"
export NEO4J_READ_ONLY="true" NEO4J_TELEMETRY="false" NEO4J_TRANSPORT_MODE="stdio"
test_stdio "neo4j" neo4j-mcp

# --- 3. pinecone (node direct) ---
echo -n "  pinecone"
export PINECONE_API_KEY="$(cfg "d['mcpServers']['pinecone']['env']['PINECONE_API_KEY']")"
pc_cmd="$(cfg "d['mcpServers']['pinecone']['command']")"
pc_args="$(cfg "d['mcpServers']['pinecone']['args'][0]")"
test_stdio "pinecone" "$pc_cmd" "$pc_args"

# --- 4. jina-embeddings (python custom) ---
echo -n "  jina-embeddings"
export PINECONE_API_KEY="$(cfg "d['mcpServers']['jina-embeddings']['env']['PINECONE_API_KEY']")"
export PINECONE_HOST="$(cfg "d['mcpServers']['jina-embeddings']['env']['PINECONE_HOST']")"
export OPENROUTER_API_KEY="$(cfg "d['mcpServers']['jina-embeddings']['env']['OPENROUTER_API_KEY']")"
export JINA_API_KEY="$(cfg "d['mcpServers']['jina-embeddings']['env']['JINA_API_KEY']")"
export N8N_API_KEY="$(cfg "d['mcpServers']['jina-embeddings']['env']['N8N_API_KEY']")"
export N8N_HOST="$(cfg "d['mcpServers']['jina-embeddings']['env']['N8N_HOST']")"
jina_script="$(cfg "d['mcpServers']['jina-embeddings']['args'][0]")"
test_stdio "jina-embeddings" "$VENV_PYTHON" "$jina_script"

# --- 5. cohere (python custom) ---
echo -n "  cohere"
export COHERE_API_KEY="$(cfg "d['mcpServers']['cohere']['env']['COHERE_API_KEY']")"
cohere_script="$(cfg "d['mcpServers']['cohere']['args'][0]")"
test_stdio "cohere" "$VENV_PYTHON" "$cohere_script"

# --- 6. huggingface (python custom) ---
echo -n "  huggingface"
export HF_TOKEN="$(cfg "d['mcpServers']['huggingface']['env']['HF_TOKEN']")"
hf_script="$(cfg "d['mcpServers']['huggingface']['args'][0]")"
test_stdio "huggingface" "$VENV_PYTHON" "$hf_script"

# --- 7. supabase ---
echo -n "  supabase"
supa_token="$(cfg "d['mcpServers']['supabase']['env'].get('SUPABASE_ACCESS_TOKEN','')")"
if [[ -z "$supa_token" || "$supa_token" == "REPLACE_WITH_YOUR_PAT" ]]; then
    warn "supabase" "PAT needed — supabase.com/dashboard/account/tokens"
else
    export SUPABASE_ACCESS_TOKEN="$supa_token"
    test_stdio "supabase" npx -y @supabase/mcp-server-supabase@latest --read-only --project-ref=ayqviqmxifzmhphiqfmj
fi


# ── [3/4] External services ──────────────────────────────────────────────────
echo ""
echo -e "${B}[3/4] Testing external services${N}"

echo -n "  n8n Docker health"
n8n_h="${N8N_HOST:-http://34.136.180.66:5678}"
hcode=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$n8n_h/healthz" 2>&1) || hcode="000"
[[ "$hcode" == "200" ]] && ok "n8n Docker ($n8n_h)" || fail "n8n Docker" "HTTP $hcode"

echo -n "  Git repo"
cd "$REPO_DIR"
branch=$(git branch --show-current 2>/dev/null || echo "?")
ok "Git (branch: $branch)"

# ── [4/4] Summary ────────────────────────────────────────────────────────────
echo ""
echo -e "${B}[4/4] Summary${N}"
echo "────────────────────────────────────────"
for r in "${results[@]}"; do
    echo -e "  $r"
done
echo "────────────────────────────────────────"
echo -e "  ${G}$passed passed${N}  ${R}$failed failed${N}  ${Y}$warnings warnings${N}"
echo ""

if [[ $failed -gt 0 ]]; then
    echo -e "${R}${B}Some checks failed. Review issues above.${N}"
    if [[ "$CHECK_ONLY" == true ]]; then
        exit 1
    fi
    echo ""
    read -rp "Launch Claude Code anyway? [y/N] " choice
    if [[ "$choice" != "y" && "$choice" != "Y" ]]; then
        echo "Aborted."
        exit 1
    fi
else
    echo -e "${G}${B}All checks passed!${N}"
fi

if [[ "$CHECK_ONLY" == true ]]; then
    echo ""
    echo -e "${C}Done (check-only mode).${N}"
    exit 0
fi

echo ""
echo -e "${C}${B}Launching Claude Code...${N}"
echo ""
cd "$REPO_DIR"
exec claude
