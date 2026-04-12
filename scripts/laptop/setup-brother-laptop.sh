#!/bin/bash
# ============================================================
# Nomos42 — Brother Laptop Full Environment Setup
# Target: Ubuntu (native — WSL2 supported as fallback)
# Run this INSIDE the laptop as the regular user (not root).
# Usage: bash setup-brother-laptop.sh
# ============================================================
set -e

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
info "Checking environment..."
[[ "$(uname -s)" == "Linux" ]] || err "Must run on Linux (native Ubuntu or WSL2)"
UBUNTU_VERSION=$(lsb_release -rs 2>/dev/null || echo "unknown")
IS_WSL=0
if grep -qi microsoft /proc/version 2>/dev/null; then
    IS_WSL=1
    info "WSL2 detected"
else
    info "Native Linux detected"
fi
info "Ubuntu $UBUNTU_VERSION on $(uname -m) — user=$(whoami)"

[[ "$(id -u)" != "0" ]] || err "Do NOT run as root — run as the normal user (sudo will be used when needed)"

HOME_DIR="$HOME"
NOMOS_DIR="$HOME_DIR/nomos42"
mkdir -p "$NOMOS_DIR" "$HOME_DIR/logs"

# ── 1. SYSTEM PACKAGES ───────────────────────────────────────
info "Step 1/10: System packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    python3 python3-venv python3-pip \
    git curl wget tmux jq openssl \
    build-essential libssl-dev \
    openssh-client ca-certificates gnupg \
    2>/dev/null
log "System packages installed"

# ── 2. NODE.JS v22 (LTS — match VM) ──────────────────────────
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
    curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg 2>/dev/null
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
        | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
    sudo apt-get update -qq && sudo apt-get install -y -qq gh
    log "gh $(gh --version | head -1) installed"
else
    log "gh already installed"
fi

# ── 4. CLAUDE CODE CLI ───────────────────────────────────────
info "Step 4/10: Claude Code CLI..."
if ! command -v claude &>/dev/null; then
    # npm global dir in user home to avoid sudo
    mkdir -p "$HOME_DIR/.npm-global"
    npm config set prefix "$HOME_DIR/.npm-global"
    grep -q "/.npm-global/bin" "$HOME_DIR/.bashrc" 2>/dev/null \
        || echo 'export PATH="$HOME/.npm-global/bin:$PATH"' >> "$HOME_DIR/.bashrc"
    export PATH="$HOME_DIR/.npm-global/bin:$PATH"
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
GITHUB_USER="LBJLincoln"

clone_or_pull() {
    local repo="$1" dest="$2"
    if [ -d "$dest/.git" ]; then
        info "  Updating $repo..."
        git -C "$dest" pull --ff-only 2>/dev/null || warn "  Could not fast-forward $repo"
    else
        info "  Cloning $repo..."
        if [ -n "${GH_TOKEN:-}" ]; then
            git clone "https://${GH_TOKEN}@github.com/${GITHUB_USER}/${repo}.git" "$dest" 2>/dev/null \
                && log "  $repo cloned" \
                || warn "  $repo clone failed — check GH_TOKEN and repo visibility"
        elif gh auth status &>/dev/null; then
            gh repo clone "${GITHUB_USER}/${repo}" "$dest" -- --quiet 2>/dev/null \
                && log "  $repo cloned (via gh)" \
                || warn "  $repo clone failed via gh"
        else
            git clone "git@github.com:${GITHUB_USER}/${repo}.git" "$dest" 2>/dev/null \
                && log "  $repo cloned" \
                || warn "  $repo clone failed — no GH_TOKEN, no gh auth, no SSH key"
        fi
    fi
}

mkdir -p "$NOMOS_DIR/repos"
clone_or_pull "mon-ipad"              "$NOMOS_DIR/repos/mon-ipad"
clone_or_pull "nomos-nba-agent"       "$NOMOS_DIR/repos/nomos-nba-agent"
clone_or_pull "nomos-political-alpha" "$NOMOS_DIR/repos/nomos-political-alpha"
clone_or_pull "nomos-dashboard"       "$NOMOS_DIR/repos/nomos-dashboard"
clone_or_pull "rgwa"                  "$NOMOS_DIR/repos/rgwa"

# ── 7. ENVIRONMENT VARIABLES ─────────────────────────────────
info "Step 7/10: Environment variables (.env.local)..."
ENV_FILE="$NOMOS_DIR/.env.local"
ENC_BUNDLE="$NOMOS_DIR/repos/mon-ipad/secrets/.env.local.enc"

if [ -f "$ENV_FILE" ]; then
    log ".env.local already exists at $ENV_FILE"
elif [ -f "$ENC_BUNDLE" ]; then
    info "Encrypted bundle found — running env-decrypt.sh"
    info "(You will be prompted for the passphrase set on the VM)"
    bash "$NOMOS_DIR/repos/mon-ipad/scripts/laptop/env-decrypt.sh" "$ENV_FILE" \
        && log ".env.local decrypted → $ENV_FILE" \
        || warn "Decryption skipped/failed — you will need to populate $ENV_FILE manually"
else
    warn "No encrypted bundle at $ENC_BUNDLE"
    warn "Either:"
    warn "  (a) run env-encrypt.sh on a machine that has .env.local, push, then git pull here and re-run"
    warn "  (b) create $ENV_FILE manually with your API keys"
    cat > "$ENV_FILE.template" << 'ENVEOF'
# ============================================================
# Nomos42 — Laptop .env.local TEMPLATE
# Fill in, rename to .env.local, then: source ~/nomos42/.env.local
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
    log "Template written at $ENV_FILE.template"
fi
[ -f "$ENV_FILE" ] && chmod 600 "$ENV_FILE"

# ── 8. CLAUDE CODE SETTINGS + MEMORY ─────────────────────────
info "Step 8/10: Claude Code settings + memory..."
CLAUDE_DIR="$HOME_DIR/.claude"
mkdir -p "$CLAUDE_DIR"

CLAUDE_SETTINGS="$CLAUDE_DIR/settings.json"
if [ ! -f "$CLAUDE_SETTINGS" ]; then
    # Note: values come from $ENV_FILE when available, else use hardcoded
    # fallbacks (same as the old VM setup — private repo, acceptable)
    _NEO4J_URI="${NEO4J_URI:-neo4j+s://38c949a2.databases.neo4j.io}"
    _NEO4J_USER="${NEO4J_USER:-neo4j}"
    _NEO4J_PASSWORD="${NEO4J_PASSWORD:-jV_zGdxbu-emQZM-ZSQux19pTZ5QLKejR2IHSzsbVak}"
    _HF_TOKEN="${HF_TOKEN:-__REPLACE_WITH_HF_TOKEN__}"
    _SUPABASE_MCP_TOKEN="${SUPABASE_MCP_TOKEN:-sbp_4b916ac72ca470f1330060456425838fec006d4d}"

    cat > "$CLAUDE_SETTINGS" << SETTINGSEOF
{
  "skipDangerousModePermissionPrompt": true,
  "effortLevel": "high",
  "prefersReducedMotion": true,
  "mcpServers": {
    "neo4j": {
      "command": "neo4j-mcp",
      "env": {
        "NEO4J_URI": "$_NEO4J_URI",
        "NEO4J_USERNAME": "$_NEO4J_USER",
        "NEO4J_PASSWORD": "$_NEO4J_PASSWORD",
        "NEO4J_DATABASE": "neo4j",
        "NEO4J_READ_ONLY": "true",
        "NEO4J_TELEMETRY": "false",
        "NEO4J_TRANSPORT_MODE": "stdio"
      }
    },
    "huggingface": {
      "command": "$VENV/bin/python3",
      "args": [
        "$NOMOS_DIR/mcp-servers/huggingface-mcp-server.py"
      ],
      "env": {
        "HF_TOKEN": "$_HF_TOKEN"
      }
    },
    "supabase": {
      "type": "streamableHttp",
      "url": "https://mcp.supabase.com/mcp?project_ref=ayqviqmxifzmhphiqfmj",
      "headers": {
        "Authorization": "Bearer $_SUPABASE_MCP_TOKEN"
      }
    }
  }
}
SETTINGSEOF
    log "Claude settings.json created at $CLAUDE_SETTINGS"
    [ "$_HF_TOKEN" = "__REPLACE_WITH_HF_TOKEN__" ] \
        && warn "HF_TOKEN not set — edit $CLAUDE_SETTINGS manually or source .env.local first"
else
    log "Claude settings.json already exists"
fi

# Copy HF MCP server from repo (not from VM filesystem)
MCP_SRC="$NOMOS_DIR/repos/mon-ipad/mcp-servers/custom/huggingface-mcp-server.py"
MCP_DST="$NOMOS_DIR/mcp-servers"
mkdir -p "$MCP_DST"
if [ -f "$MCP_SRC" ]; then
    cp "$MCP_SRC" "$MCP_DST/" && log "HF MCP server copied from repo"
else
    warn "HF MCP server not found in repo at $MCP_SRC (skipped)"
fi

# ── 9. MEMORY SYNC ───────────────────────────────────────────
info "Step 9/10: Claude memory sync..."
# Claude stores per-project memory under $HOME/.claude/projects/<encoded-path>/
# For this laptop, the project path is $NOMOS_DIR/repos/mon-ipad
PROJ_PATH="$NOMOS_DIR/repos/mon-ipad"
PROJ_KEY="$(echo "$PROJ_PATH" | sed 's|/|-|g')"
MEMORY_DEST="$CLAUDE_DIR/projects/$PROJ_KEY/memory"
mkdir -p "$MEMORY_DEST"

cat > "$MEMORY_DEST/MEMORY.md" << MEMEOF
# $(hostname) — Nomos42 Node

## THIS MACHINE
- Role: COMPLEMENT node (compute, GPU prep, backtests, builds)
- Hostname: $(hostname)
- User: $(whoami)
- OS: Ubuntu $UBUNTU_VERSION$([ "$IS_WSL" = "1" ] && echo " (WSL2)" || echo " (native)")
- Repos: $NOMOS_DIR/repos/ (all 5 cloned)
- Venv: $VENV
- Env: $ENV_FILE (source in ~/.bashrc)

## VM (primary node / control tower)
- IP: \${VM_HOST:-100.70.229.122} (Tailscale)
- SSH: ssh \${VM_USER:-termius}@\${VM_HOST:-100.70.229.122}
- Role: Control tower, cron hub, Telegram bots, Bloomberg API

## RULES (same as VM)
- ZERO ML on this laptop in production — offload to HF Spaces
- Exception: quick local backtests/validation are OK (not deployed)
- NEVER run \`next build\` / \`tsc\` in prod — push to Vercel instead
- All deployed training on HF Spaces / Kaggle / Colab

## PROJECT CONTEXT
Full context lives in the repo at: $PROJ_PATH/CLAUDE.md

## WHAT THIS LAPTOP CAN DO (that the VM cannot)
1. Heavy backtests (more RAM than the 969MB VM)
2. Kaggle notebook prep + submission
3. Build Next.js dashboard (VM too weak for \`npm run build\`)
4. Run compute-heavy Python scripts without starving the VM
5. Secondary GPU compute account (Colab/Kaggle)
6. Local model inference with Ollama (llama3/mistral)
MEMEOF
log "Claude memory initialized at $MEMORY_DEST"

# ── 10. TAILSCALE ────────────────────────────────────────────
info "Step 10/10: Tailscale..."
if [ "$IS_WSL" = "1" ]; then
    warn "WSL2 detected — install Tailscale on Windows side: https://tailscale.com/download/windows"
elif ! command -v tailscale &>/dev/null; then
    info "Installing Tailscale..."
    curl -fsSL https://tailscale.com/install.sh | sh 2>/dev/null \
        && log "Tailscale installed — run: sudo tailscale up" \
        || warn "Tailscale install failed — see https://tailscale.com/download/linux"
else
    log "Tailscale already present: $(tailscale version 2>/dev/null | head -1)"
fi

# ── BASHRC SETUP ─────────────────────────────────────────────
info "Setting up ~/.bashrc..."
BASHRC="$HOME_DIR/.bashrc"
if ! grep -q "nomos42" "$BASHRC" 2>/dev/null; then
    cat >> "$BASHRC" << BASHRCEOF

# ── Nomos42 ──────────────────────────────────────────────────
export NOMOS_DIR="\$HOME/nomos42"
export REPOS="\$NOMOS_DIR/repos"

# Load env (set -a exports every var)
if [ -f "\$NOMOS_DIR/.env.local" ]; then
    set -a
    source "\$NOMOS_DIR/.env.local"
    set +a
fi

# Venv activate shortcut
alias nomos="source \$NOMOS_DIR/venv/bin/activate"
alias mon="cd \$REPOS/mon-ipad"
alias nba="cd \$REPOS/nomos-nba-agent"

# Quick sync
alias sync-repos="for r in mon-ipad nomos-nba-agent nomos-political-alpha nomos-dashboard rgwa; do git -C \$REPOS/\$r pull --ff-only 2>/dev/null; done"

# SSH shortcut
alias vm="ssh \${VM_USER:-termius}@\${VM_HOST:-100.70.229.122}"
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
    ssh-keygen -t ed25519 -C "nomos42-$(hostname)-$(date +%Y%m%d)" -f "$SSH_KEY" -N "" 2>/dev/null
    log "SSH key generated at $SSH_KEY"
    warn "ACTION: Add this public key to VM:"
    warn "  cat $SSH_KEY.pub"
    warn "  Then on VM: echo '<pubkey>' >> ~/.ssh/authorized_keys"
else
    log "SSH key already exists at $SSH_KEY"
fi

# SSH config for VM (uses env vars, resolved at connect time)
SSH_CONFIG="$HOME_DIR/.ssh/config"
if ! grep -q "Host vm" "$SSH_CONFIG" 2>/dev/null; then
    cat >> "$SSH_CONFIG" << 'SSHEOF'

Host vm
    HostName 100.70.229.122
    User termius
    IdentityFile ~/.ssh/id_ed25519
    StrictHostKeyChecking accept-new
    ConnectTimeout 20
    ServerAliveInterval 30
    ServerAliveCountMax 3
SSHEOF
    chmod 600 "$SSH_CONFIG"
    log "SSH config updated — use: ssh vm"
fi

# ── CRONTAB (laptop-specific tasks) ──────────────────────────
info "Setting up laptop crontab..."
CRON_FILE="/tmp/nomos42-laptop-cron.$$"
crontab -l 2>/dev/null > "$CRON_FILE" || true

if ! grep -q "nomos42-laptop" "$CRON_FILE"; then
    cat >> "$CRON_FILE" << CRONEOF

# ── Nomos42 Laptop Node ──────────────────────────────────────
# Sync repos from GitHub every 30 min
*/30 * * * * bash -lc 'cd $NOMOS_DIR/repos/mon-ipad && git pull --ff-only' >> $HOME_DIR/logs/git-sync.log 2>&1
# Kaggle GPU evolution (daily 03:30 UTC — offset from VM's 03:00)
30 3 * * * bash -lc 'source $ENV_FILE && $VENV/bin/python3 $NOMOS_DIR/repos/mon-ipad/scripts/kaggle/nba_karpathy_loop.py --max-iter 50' >> $HOME_DIR/logs/kaggle-laptop.log 2>&1
# Cross-pollinate from laptop HF spaces (weekly)
0 5 * * 0 bash -lc 'source $ENV_FILE && $VENV/bin/python3 $NOMOS_DIR/repos/mon-ipad/scripts/agents/cross-pollinate.py --source laptop' >> $HOME_DIR/logs/cross-pollinate-laptop.log 2>&1
# ─────────────────────────────────────────────────────────────
CRONEOF
    crontab "$CRON_FILE"
    log "Laptop crontab installed (3 jobs)"
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
echo "Next steps:"
echo ""
if [ ! -f "$ENV_FILE" ]; then
    echo "  1. Populate credentials:"
    echo "     (a) If you have the encrypted bundle in the repo:"
    echo "         cd $NOMOS_DIR/repos/mon-ipad && git pull"
    echo "         bash scripts/laptop/env-decrypt.sh"
    echo "     (b) Otherwise, fill the template manually:"
    echo "         nano $ENV_FILE.template && mv $ENV_FILE.template $ENV_FILE"
    echo ""
fi
echo "  2. Auth GitHub CLI (if not done):    gh auth login"
echo "  3. Auth Claude Code:                 claude (login with claude.ai account)"
echo "  4. Add SSH pubkey to VM (optional):"
echo "       cat $SSH_KEY.pub   # then append to VM's ~/.ssh/authorized_keys"
if [ "$IS_WSL" != "1" ]; then
    echo "  5. Tailscale:                        sudo tailscale up"
fi
echo "  6. (Optional) Ollama for local models:"
echo "       bash $NOMOS_DIR/repos/mon-ipad/scripts/laptop/setup-ollama.sh"
echo ""
echo "  7. Open a new shell (to pick up ~/.bashrc), then:"
echo "       source $VENV/bin/activate"
echo "       python3 -c 'import sklearn, xgboost, lightgbm, catboost; print(\"ML stack OK\")'"
echo ""
echo "  8. Open Claude Code in mon-ipad:"
echo "       mon && claude"
echo ""
echo "Laptop role: COMPLEMENT (compute, builds, Kaggle, backtests)"
echo "VM role:     CONTROL TOWER (crons, bots, Bloomberg, Telegram)"
echo ""
