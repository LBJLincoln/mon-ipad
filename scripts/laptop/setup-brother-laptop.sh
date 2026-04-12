#!/bin/bash
# ============================================================
# Nomos42 — Brother Laptop Full Environment Setup
# Target: Acer Aspire A315, WSL2 Ubuntu, Claude Code as primary IDE
# Run this script INSIDE WSL2 Ubuntu as user "nomos"
# Usage: bash setup-brother-laptop.sh
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
VM_HOME="${VM_HOME:-/home/termius}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
info() { echo -e "${BLUE}[INFO]${NC} $1"; }
err()  { echo -e "${RED}[ERR]${NC} $1"; exit 1; }

echo ""
echo "============================================================"
echo "  Nomos42 — Brother Laptop Full Setup"
echo "  $(date)"
echo "============================================================"
echo ""

# ── 0. PREFLIGHT ─────────────────────────────────────────────
info "Checking WSL2 Ubuntu environment..."
[[ "$(uname -s)" == "Linux" ]] || err "Must run inside WSL2 Ubuntu"
UBUNTU_VERSION=$(lsb_release -rs 2>/dev/null || echo "unknown")
info "Ubuntu $UBUNTU_VERSION on $(uname -m)"

HOME_DIR="/home/nomos"
NOMOS_DIR="$HOME_DIR/nomos42"
mkdir -p "$NOMOS_DIR"
mkdir -p "$HOME_DIR/logs"

# ── 1. SYSTEM PACKAGES ───────────────────────────────────────
info "Step 1/10: System packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    python3.12 python3.12-venv python3-pip \
    git curl wget tmux jq \
    build-essential libssl-dev \
    openssh-client \
    2>/dev/null
log "System packages installed"

# ── 2. NODE.JS v22 (LTS — match VM: v22.22.0) ────────────────
info "Step 2/10: Node.js v22..."
if ! command -v node &>/dev/null || [[ "$(node --version | cut -d. -f1 | tr -d v)" -lt 22 ]]; then
    curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash - 2>/dev/null
    sudo apt-get install -y -qq nodejs
    log "Node.js $(node --version) installed"
else
    log "Node.js $(node --version) already installed"
fi

# ── 3. GITHUB CLI (gh) ───────────────────────────────────────
info "Step 3/10: GitHub CLI..."
if ! command -v gh &>/dev/null; then
    curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg 2>/dev/null
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
    sudo apt-get update -qq && sudo apt-get install -y -qq gh
    log "gh $(gh --version | head -1) installed"
else
    log "gh already installed"
fi

# ── 4. CLAUDE CODE CLI ───────────────────────────────────────
info "Step 4/10: Claude Code CLI..."
if ! command -v claude &>/dev/null; then
    npm install -g @anthropic-ai/claude-code 2>/dev/null
    log "Claude Code installed: $(claude --version 2>/dev/null || echo 'check manually')"
else
    log "Claude Code already installed: $(claude --version 2>/dev/null)"
fi

# ── 5. PYTHON VIRTUAL ENVIRONMENT ────────────────────────────
info "Step 5/10: Python venv + packages..."
VENV="$NOMOS_DIR/venv"
if [ ! -d "$VENV" ]; then
    python3 -m venv "$VENV"
fi
source "$VENV/bin/activate"
pip install --upgrade pip -q

# Core scientific stack (CPU only — match VM versions)
pip install -q \
    numpy==1.26.4 \
    pandas \
    scikit-learn \
    xgboost \
    lightgbm \
    catboost \
    scipy

# API clients
pip install -q \
    anthropic \
    openai \
    requests \
    aiohttp \
    httpx \
    supabase

# NBA + data
pip install -q \
    nba_api \
    yfinance \
    beautifulsoup4 \
    lxml

# Utilities
pip install -q \
    python-dotenv \
    python-telegram-bot \
    rich \
    textual \
    tenacity \
    tqdm \
    tabulate \
    typer

# Hugging Face
pip install -q \
    huggingface_hub \
    datasets

deactivate
log "Python packages installed in $VENV"

# ── 6. REPOS CLONE ───────────────────────────────────────────
info "Step 6/10: Git repos..."

# !! ACTION REQUIRED: Replace with your actual GitHub username / SSH or HTTPS
# The VM uses GH_TOKEN — you need to paste it in the .env.local below
GITHUB_USER="LBJLincoln"

clone_or_pull() {
    local repo="$1" dest="$2"
    if [ -d "$dest/.git" ]; then
        info "  Updating $repo..."
        git -C "$dest" pull --ff-only 2>/dev/null || warn "  Could not fast-forward $repo"
    else
        info "  Cloning $repo..."
        # Use HTTPS with token if GH_TOKEN is set, else try SSH
        if [ -n "$GH_TOKEN" ]; then
            git clone "https://${GH_TOKEN}@github.com/${GITHUB_USER}/${repo}.git" "$dest" 2>/dev/null \
                && log "  $repo cloned" \
                || warn "  $repo clone failed — check GH_TOKEN and repo visibility"
        else
            git clone "git@github.com:${GITHUB_USER}/${repo}.git" "$dest" 2>/dev/null \
                && log "  $repo cloned" \
                || warn "  $repo clone failed — no GH_TOKEN and no SSH key"
        fi
    fi
}

mkdir -p "$NOMOS_DIR/repos"
clone_or_pull "mon-ipad"            "$NOMOS_DIR/repos/mon-ipad"
clone_or_pull "nomos-nba-agent"     "$NOMOS_DIR/repos/nomos-nba-agent"
clone_or_pull "nomos-political-alpha" "$NOMOS_DIR/repos/nomos-political-alpha"
clone_or_pull "nomos-dashboard"     "$NOMOS_DIR/repos/nomos-dashboard"
clone_or_pull "rgwa"                "$NOMOS_DIR/repos/rgwa"

# ── 7. ENVIRONMENT VARIABLES ─────────────────────────────────
info "Step 7/10: Environment variables (.env.local)..."
ENV_FILE="$NOMOS_DIR/.env.local"

if [ -f "$ENV_FILE" ]; then
    warn ".env.local already exists — skipping template creation"
    warn "Run: source $ENV_FILE to load vars"
else
    cat > "$ENV_FILE" << 'ENVEOF'
# ============================================================
# Nomos42 — Brother Laptop .env.local
# Copy values from the VM's /home/termius/mon-ipad/.env.local
# Then run: source ~/nomos42/.env.local
# ============================================================

# ── LLM APIs ─────────────────────────────────────────────────
export ANTHROPIC_API_KEY=
export OPENAI_API_KEY=
export OPENROUTER_API_KEY=
export XAI_API_KEY=
export GOOGLE_API_KEY=

# ── HuggingFace (3 accounts) ─────────────────────────────────
export HF_TOKEN=          # LBJLincoln (primary)
export HF_TOKEN_2=        # LBJLincoln26
export HF_TOKEN_3=        # Nomos42
export HF_TOKEN_FORGE=
export HF_TOKEN_USERS=

# ── HF Spaces ────────────────────────────────────────────────
export HF_SPACE_1_URL=https://nomos42-nba-quant.hf.space
export HF_SPACE_2_URL=https://nomos42-nba-quant-2.hf.space
export HF_SPACE_3_URL=https://nomos42-nba-evo-3.hf.space
export HF_SPACE_4_URL=https://nomos42-nba-evo-4.hf.space
export HF_SPACE_5_URL=https://nomos42-nba-evo-5.hf.space
export HF_SPACE_6_URL=https://nomos42-nba-evo-6.hf.space

# ── Supabase ─────────────────────────────────────────────────
export SUPABASE_URL=
export SUPABASE_API_KEY=
export SUPABASE_PASSWORD=
export SUPABASE_URL_2=
export SUPABASE_ANON_KEY_2=
export SUPABASE_PASSWORD_2=
export SUPABASE_POOLER_2=

# ── Neo4j ────────────────────────────────────────────────────
export NEO4J_URI=
export NEO4J_USER=
export NEO4J_PASSWORD=

# ── GitHub ───────────────────────────────────────────────────
export GH_TOKEN=
export GITHUB_TOKEN=

# ── Telegram ─────────────────────────────────────────────────
export TELEGRAM_BOT_TOKEN=
export ADMIN_TELEGRAM_ID=
export TELEGRAM_CHANNEL_ID=

# ── Odds / Betting ───────────────────────────────────────────
export ODDS_API_KEY=

# ── Kaggle ───────────────────────────────────────────────────
export KAGGLE_USERNAME=
export KAGGLE_KEY=

# ── Pinecone ─────────────────────────────────────────────────
export PINECONE_API_KEY=
export PINECONE_HOST=

# ── Misc ─────────────────────────────────────────────────────
export BRAVE_API_KEY=
export TAVILY_API_KEY=
export EXA_API_KEY=
export FIRECRAWL_API_KEY=

# ── Compute ──────────────────────────────────────────────────
export LIGHTNING_USER_ID=
export LIGHTNING_API_KEY=
export TAILSCALE_API_KEY=
export TAILSCALE_AUTH_KEY=

# ── VM connection ────────────────────────────────────────────
export VM_HOST=100.70.229.122
export VM_USER=termius
export LAPTOP_TAILSCALE_IP=100.67.205.125

# ── Laptop role ──────────────────────────────────────────────
export NOMOS_NODE_ROLE=laptop
export NOMOS_NODE_NAME=brother-laptop
ENVEOF
    log ".env.local template created at $ENV_FILE"
    warn "ACTION REQUIRED: Fill in the values from the VM's .env.local before proceeding!"
fi

# ── 8. CLAUDE CODE SETTINGS + MEMORY ─────────────────────────
info "Step 8/10: Claude Code settings + memory..."
CLAUDE_DIR="$HOME_DIR/.claude"
mkdir -p "$CLAUDE_DIR"

# Claude settings.json — identical to VM (MCP servers)
# NOTE: Paths adjusted for WSL Ubuntu (/home/nomos/...)
CLAUDE_SETTINGS="$CLAUDE_DIR/settings.json"
if [ ! -f "$CLAUDE_SETTINGS" ]; then
    cat > "$CLAUDE_SETTINGS" << 'SETTINGSEOF'
{
  "skipDangerousModePermissionPrompt": true,
  "effortLevel": "high",
  "prefersReducedMotion": true,
  "mcpServers": {
    "neo4j": {
      "command": "neo4j-mcp",
      "env": {
        "NEO4J_URI": "neo4j+s://38c949a2.databases.neo4j.io",
        "NEO4J_USERNAME": "neo4j",
        "NEO4J_PASSWORD": "jV_zGdxbu-emQZM-ZSQux19pTZ5QLKejR2IHSzsbVak",
        "NEO4J_DATABASE": "neo4j",
        "NEO4J_READ_ONLY": "true",
        "NEO4J_TELEMETRY": "false",
        "NEO4J_TRANSPORT_MODE": "stdio"
      }
    },
    "huggingface": {
      "command": "/home/nomos/nomos42/venv/bin/python3",
      "args": [
        "/home/nomos/nomos42/mcp-servers/huggingface-mcp-server.py"
      ],
      "env": {
        "HF_TOKEN": "__REPLACE_WITH_HF_TOKEN__"
      }
    },
    "supabase": {
      "type": "streamableHttp",
      "url": "https://mcp.supabase.com/mcp?project_ref=ayqviqmxifzmhphiqfmj",
      "headers": {
        "Authorization": "Bearer sbp_4b916ac72ca470f1330060456425838fec006d4d"
      }
    }
  }
}
SETTINGSEOF
    warn "Claude settings.json written — replace __REPLACE_WITH_HF_TOKEN__ manually"
    log "Claude settings.json created"
else
    log "Claude settings.json already exists"
fi

# Copy the HuggingFace MCP server from repo
HF_MCP_SRC="$NOMOS_DIR/repos/mon-ipad/../mcp-servers/custom/huggingface-mcp-server.py"
MCP_DST="$NOMOS_DIR/mcp-servers"
mkdir -p "$MCP_DST"
if [ -f "${VM_HOME}/mcp-servers/custom/huggingface-mcp-server.py" ]; then
    # Running from VM context — copy directly
    cp "${VM_HOME}/mcp-servers/custom/huggingface-mcp-server.py" "$MCP_DST/" 2>/dev/null && log "HF MCP server copied"
elif [ -f "$NOMOS_DIR/repos/mon-ipad/scripts/bloomberg/bloomberg-api.py" ]; then
    # Running on laptop — find it in repo
    warn "Copy MCP server manually: scp termius@100.70.229.122:/home/termius/mcp-servers/custom/huggingface-mcp-server.py $MCP_DST/"
fi

# ── 9. MEMORY SYNC ───────────────────────────────────────────
info "Step 9/10: Claude memory sync..."
MEMORY_DEST="$CLAUDE_DIR/projects/-home-nomos-nomos42-repos-mon-ipad/memory"
mkdir -p "$MEMORY_DEST"

# The memory files live in the git repo (MEMORY.md references them)
# We create a pointer MEMORY.md that tells Claude where to find context
cat > "$MEMORY_DEST/MEMORY.md" << 'MEMEOF'
# Brother Laptop — Nomos42 Node

## THIS MACHINE
- Role: COMPLEMENT node (compute, GPU prep, backtests, builds)
- CPU: Intel Core i3-6006U @ 2.4 GHz (2 cores / 4 threads)
- RAM: 8 GB (WSL sees ~3.8 GB)
- OS: WSL2 Ubuntu on Windows 10
- Repos: ~/nomos42/repos/ (all 5 cloned)
- Venv: ~/nomos42/venv/
- Env: ~/nomos42/.env.local

## VM (primary node)
- IP: 100.70.229.122 (Tailscale)
- SSH: ssh termius@100.70.229.122
- Role: Control tower, cron hub, Telegram bots, Bloomberg API

## RULES (same as VM)
- ZERO ML on this laptop in production — offload to HF Spaces
- Exception: quick local backtests/validation are OK (not deployed)
- NEVER run next build / tsc — push to Vercel instead
- All deployed training on HF Spaces / Kaggle / Colab

## PROJECT CONTEXT
- See full MEMORY.md on VM at /home/termius/.claude/projects/-home-termius-mon-ipad/memory/MEMORY.md
- Or in repo: ~/nomos42/repos/mon-ipad/ (check git log)

## WHAT THIS LAPTOP CAN DO (that the VM cannot)
1. Heavy backtests (8GB RAM vs 969MB on VM)
2. Kaggle notebook prep + submission (aurelien account)
3. Build Next.js dashboard (VM is too weak for npm build)
4. Run compute-heavy Python scripts without starving the VM
5. Second GPU compute account (second Colab/Kaggle account)
6. Local model inference with Ollama (llama3/mistral for free)

## SSH TO VM
  ssh termius@100.70.229.122
  # or if Tailscale active:
  ssh termius@100.70.229.122
MEMEOF
log "Claude memory initialized at $MEMORY_DEST"

# ── 10. TAILSCALE (WSL2) ─────────────────────────────────────
info "Step 10/10: Tailscale..."
if ! command -v tailscale &>/dev/null; then
    warn "Tailscale not found in WSL — installing..."
    # Note: In WSL2, Tailscale should be installed on Windows side, not WSL
    # But we can still install the Linux version for WSL tunneling
    curl -fsSL https://tailscale.com/install.sh | sh 2>/dev/null \
        && warn "Tailscale installed in WSL — run: sudo tailscale up --authkey=<TAILSCALE_AUTH_KEY>" \
        || warn "Install Tailscale on Windows side: https://tailscale.com/download/windows"
else
    log "Tailscale already present: $(tailscale version 2>/dev/null | head -1)"
fi

# ── BASHRC SETUP ─────────────────────────────────────────────
info "Setting up ~/.bashrc..."
BASHRC="$HOME_DIR/.bashrc"
if ! grep -q "nomos42" "$BASHRC" 2>/dev/null; then
    cat >> "$BASHRC" << 'BASHRCEOF'

# ── Nomos42 ──────────────────────────────────────────────────
export NOMOS_DIR="$HOME/nomos42"
export REPOS="$NOMOS_DIR/repos"

# Load env
[ -f "$NOMOS_DIR/.env.local" ] && source "$NOMOS_DIR/.env.local"

# Venv activate shortcut
alias nomos="source $NOMOS_DIR/venv/bin/activate"
alias mon="cd $REPOS/mon-ipad"
alias nba="cd $REPOS/nomos-nba-agent"

# Quick sync from VM
alias sync-vm="git -C $REPOS/mon-ipad pull && git -C $REPOS/nomos-nba-agent pull && git -C $REPOS/nomos-political-alpha pull"

# SSH shortcuts
alias vm="ssh termius@100.70.229.122"
# ─────────────────────────────────────────────────────────────
BASHRCEOF
    log "~/.bashrc updated"
else
    log "~/.bashrc already has Nomos42 config"
fi

# ── SSH KEY FOR VM ACCESS ─────────────────────────────────────
info "Checking SSH key for VM access..."
SSH_KEY="$HOME_DIR/.ssh/id_ed25519"
if [ ! -f "$SSH_KEY" ]; then
    mkdir -p "$HOME_DIR/.ssh" && chmod 700 "$HOME_DIR/.ssh"
    ssh-keygen -t ed25519 -C "nomos42-laptop-$(date +%Y%m%d)" -f "$SSH_KEY" -N "" 2>/dev/null
    log "SSH key generated at $SSH_KEY"
    warn "ACTION: Add this public key to VM with:"
    warn "  cat $SSH_KEY.pub"
    warn "  Then on VM: echo '<pubkey>' >> ~/.ssh/authorized_keys"
else
    log "SSH key already exists at $SSH_KEY"
fi

# SSH config for VM
SSH_CONFIG="$HOME_DIR/.ssh/config"
if ! grep -q "termius" "$SSH_CONFIG" 2>/dev/null; then
    cat >> "$SSH_CONFIG" << 'SSHEOF'

Host vm
    HostName 100.70.229.122
    User termius
    IdentityFile ~/.ssh/id_ed25519
    StrictHostKeyChecking no
    ConnectTimeout 20
    ServerAliveInterval 30
    ServerAliveCountMax 3
SSHEOF
    chmod 600 "$SSH_CONFIG"
    log "SSH config updated — use: ssh vm"
fi

# ── CRONTAB (laptop-specific tasks only) ─────────────────────
info "Setting up laptop crontab..."
CRON_FILE="/tmp/nomos42-laptop-cron"
crontab -l 2>/dev/null > "$CRON_FILE" || true

if ! grep -q "nomos42-laptop" "$CRON_FILE"; then
    cat >> "$CRON_FILE" << 'CRONEOF'

# ── Nomos42 Laptop Node ──────────────────────────────────────
# Sync repos from GitHub every 30 min (passive pull, not primary push)
*/30 * * * * source /home/nomos/nomos42/.env.local && cd /home/nomos/nomos42/repos/mon-ipad && git pull --ff-only >> /home/nomos/logs/git-sync.log 2>&1
# Kaggle GPU evolution (daily 03:30 UTC — offset from VM's 03:00)
30 3 * * * source /home/nomos/nomos42/.env.local && python3 /home/nomos/nomos42/repos/mon-ipad/scripts/kaggle/nba_karpathy_loop.py --max-iter 50 >> /home/nomos/logs/kaggle-laptop.log 2>&1
# Cross-pollinate from laptop HF spaces (weekly)
0 5 * * 0 source /home/nomos/nomos42/.env.local && python3 /home/nomos/nomos42/repos/mon-ipad/scripts/agents/cross-pollinate.py --source laptop >> /home/nomos/logs/cross-pollinate-laptop.log 2>&1
# ─────────────────────────────────────────────────────────────
CRONEOF
    crontab "$CRON_FILE"
    log "Laptop crontab installed (3 jobs: sync, kaggle, cross-pollinate)"
else
    log "Crontab already configured"
fi
rm -f "$CRON_FILE"

# ── SUMMARY ──────────────────────────────────────────────────
echo ""
echo "============================================================"
echo -e "  ${GREEN}Setup complete!${NC}"
echo "============================================================"
echo ""
echo "Next steps (MANUAL — required):"
echo ""
echo "  1. Fill in ~/.env.local:"
echo "       nano $NOMOS_DIR/.env.local"
echo "       (Copy values from VM: cat /home/termius/mon-ipad/.env.local)"
echo ""
echo "  2. Auth GitHub CLI:"
echo "       gh auth login"
echo "       # Paste GH_TOKEN when prompted"
echo ""
echo "  3. Auth Claude Code:"
echo "       claude"
echo "       # Log in with same Anthropic account (claude.ai subscription)"
echo ""
echo "  4. Fix Claude settings HF_TOKEN:"
echo "       nano $CLAUDE_DIR/settings.json"
echo "       # Replace __REPLACE_WITH_HF_TOKEN__ with actual value"
echo ""
echo "  5. Add laptop SSH pubkey to VM:"
echo "       cat $SSH_KEY.pub"
echo "       # Then on VM: echo '<KEY>' >> ~/.ssh/authorized_keys"
echo ""
echo "  6. Test VM connection:"
echo "       ssh vm"
echo ""
echo "  7. Install Tailscale on WINDOWS side (not WSL):"
echo "       https://tailscale.com/download/windows"
echo "       # Laptop Tailscale IP should be: 100.67.205.125"
echo ""
echo "  8. (Optional) Install Ollama for local models:"
echo "       curl -fsSL https://ollama.ai/install.sh | sh"
echo "       ollama pull llama3"
echo "       ollama pull mistral"
echo ""
echo "  9. Activate venv and test:"
echo "       source ~/nomos42/venv/bin/activate"
echo "       python3 -c 'import sklearn, xgboost, lightgbm, catboost; print(\"ML stack OK\")'"
echo ""
echo "  10. Open Claude Code in mon-ipad:"
echo "       cd ~/nomos42/repos/mon-ipad"
echo "       claude"
echo ""
echo "Laptop role: COMPLEMENT (compute, builds, Kaggle, backtests)"
echo "VM role:     CONTROL TOWER (crons, bots, Bloomberg, Telegram)"
echo ""
