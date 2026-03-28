# Fleet Setup Guide

> 4 machines: 1 cloud VM (orchestrator) + 2 MacBook Air 2016 + 1 Acer Aspire 3

Rule: ZERO ML training on any local machine. All GPU work on Kaggle/Modal/Colab/HF Spaces.

---

## Phase 1: VM Already Running (Nothing to Do)

The Google Cloud VM is the primary orchestrator. It runs:
- Cloud Brain (4h cycle), Data server, Terminal API
- Telegram bots, 12 cron jobs, watchdog, infra-agent
- All fleet coordination via `scripts/fleet-agent.sh`

---

## Phase 2: MacBook Air Setup (Both Machines)

### 2.1 Install Homebrew

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### 2.2 Install Core Dependencies

```bash
brew install git python3 node jq
pip3 install --user requests pandas numpy python-telegram-bot supabase
```

### 2.3 Install Claude Desktop

1. Download from https://claude.ai/download (macOS version)
2. Install the .dmg
3. Sign in with the same Anthropic account used on the VM
4. Claude Desktop gives you a GUI + the ability to run Claude Code projects

### 2.4 Install Claude Code CLI

```bash
npm install -g @anthropic-ai/claude-code
```

Verify:
```bash
claude --version
```

### 2.5 Generate SSH Key

```bash
ssh-keygen -t ed25519 -C "macbook-air-1@nomos42"  # or macbook-air-2
```

Then add the public key to:
- **GitHub**: Settings > SSH keys > Add `~/.ssh/id_ed25519.pub`
- **VM authorized_keys**: `ssh-copy-id termius@<VM_IP>` or manually append to `~/.ssh/authorized_keys` on the VM

### 2.6 Clone Repositories

```bash
mkdir -p ~/nomos42 && cd ~/nomos42
git clone git@github.com:LBJLincoln/mon-ipad.git
git clone git@github.com:LBJLincoln/nomos-nba-agent.git
git clone git@github.com:LBJLincoln/nomos-dashboard.git
git clone git@github.com:LBJLincoln/nomos-political-alpha.git
git clone git@github.com:LBJLincoln/rgwa.git
```

### 2.7 Copy Credentials from VM

```bash
scp termius@<VM_IP>:~/mon-ipad/.env.local ~/nomos42/mon-ipad/.env.local
```

Verify:
```bash
wc -l ~/nomos42/mon-ipad/.env.local
# Should show 50+ lines
```

### 2.8 Setup Cron Jobs

#### MacBook Air #1 (Research & Feature Engineering)

```bash
crontab -e
```

Add:
```cron
# Git sync every 30 min
*/30 * * * * cd ~/nomos42/mon-ipad && git pull --rebase --quiet && git push --quiet 2>/dev/null

# Feature engineering proposals every 6h
0 */6 * * * cd ~/nomos42/mon-ipad && source .env.local && claude -p "Analyze the latest evolution results and propose 3 new feature engineering ideas. Write proposals to data/research-proposals/" --max-turns 5 >> /tmp/feature-proposals.log 2>&1

# Repo scout every 12h
0 */12 * * * cd ~/nomos42/mon-ipad && source .env.local && claude -p "Search for new NBA prediction papers, datasets, and open-source models. Summarize findings." --max-turns 5 >> /tmp/repo-scout.log 2>&1
```

#### MacBook Air #2 (Strategy & Backtesting)

```bash
crontab -e
```

Add:
```cron
# Git sync every 30 min
*/30 * * * * cd ~/nomos42/mon-ipad && git pull --rebase --quiet && git push --quiet 2>/dev/null

# Daily analysis at 8am local
0 8 * * * cd ~/nomos42/mon-ipad && source .env.local && claude -p "Review yesterday's predictions vs results. Analyze which bet types performed best. Write summary to data/research/" --max-turns 5 >> /tmp/daily-analysis.log 2>&1
```

### 2.9 Verify Setup

```bash
# Test SSH to VM
ssh termius@<VM_IP> "echo 'VM reachable'"

# Test Git
cd ~/nomos42/mon-ipad && git status

# Test Claude Code
cd ~/nomos42/mon-ipad && claude -p "What is the current ATR Brier score?" --max-turns 1

# Test env
source ~/nomos42/mon-ipad/.env.local && echo "Tokens loaded: $(env | grep -c TOKEN)"
```

### 2.10 Enable Sleep Prevention (Important for Crons)

MacBook Air will sleep by default, killing cron jobs.

Option A -- caffeinate (keeps awake while plugged in):
```bash
# Add to ~/.zshrc or run in background
caffeinate -d &
```

Option B -- System Preferences:
- System Preferences > Energy Saver > "Prevent computer from sleeping automatically when the display is off" (check)

Option C -- amphetamine (free app from Mac App Store, more control)

---

## Phase 3: Acer Aspire 3 Setup

### 3.1 Determine OS

If Windows is installed, use WSL2 (recommended). If Linux is already installed, skip to 3.3.

### 3.2 Install WSL2 (Windows only)

Open PowerShell as Administrator:
```powershell
wsl --install
```

Restart, then open "Ubuntu" from Start menu. Set up username/password.

All subsequent commands run inside WSL2 Ubuntu terminal.

### 3.3 Install Dependencies

```bash
sudo apt update && sudo apt install -y git python3 python3-pip nodejs npm jq curl
pip3 install --user requests pandas numpy python-telegram-bot supabase
```

### 3.4 Install Claude Desktop

- **Windows**: Download from https://claude.ai/download (Windows version)
- **Linux**: Download the Linux .deb or .AppImage from https://claude.ai/download

### 3.5 Install Claude Code CLI

```bash
npm install -g @anthropic-ai/claude-code
```

### 3.6 SSH Key, Clone Repos, Copy Credentials

Same as MacBook Air steps 2.5, 2.6, 2.7 above.

### 3.7 Setup Cron Jobs (Data Ingestion Role)

```bash
crontab -e
```

Add:
```cron
# Git sync every 30 min
*/30 * * * * cd ~/nomos42/mon-ipad && git pull --rebase --quiet && git push --quiet 2>/dev/null

# Hourly data pull: odds, injuries, tracking
0 * * * * cd ~/nomos42/mon-ipad && source .env.local && python3 scripts/nba-daily-odds.py >> /tmp/odds-pull.log 2>&1
0 * * * * cd ~/nomos42/mon-ipad && source .env.local && python3 scripts/fetch_injury_reports.py >> /tmp/injuries.log 2>&1

# Player tracking data every 4h
0 */4 * * * cd ~/nomos42/mon-ipad && source .env.local && python3 scripts/fetch_player_tracking.py >> /tmp/tracking.log 2>&1

# Log aggregation every 4h
0 */4 * * * ssh termius@<VM_IP> "cat /home/termius/mon-ipad/logs/*.log" >> ~/nomos42/logs/vm-aggregate.log 2>/dev/null
```

### 3.8 WSL2 Auto-Start (Windows only)

To keep WSL2 crons running after login:

1. Create `%USERPROFILE%\wsl-startup.vbs`:
```vbs
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "wsl -d Ubuntu -e bash -c 'sudo service cron start'", 0, False
```

2. Place shortcut in `shell:startup` folder (Win+R > `shell:startup`)

---

## Phase 4: Enable Remote Monitoring from VM

Once all machines have SSH keys set up and the VM can reach them:

### 4.1 Add Machine IPs to fleet-config.yaml

Edit `data/fleet-config.yaml` and fill in `ip`, `ssh_user`, `ssh_port` for each machine.

### 4.2 Enable Remote Checks in fleet-agent.sh

Edit `scripts/fleet-agent.sh` and uncomment the remote monitoring section:

```bash
MBA1_JSON=$(check_remote_machine "mba-1" "192.168.x.x" "22" "username")
MBA2_JSON=$(check_remote_machine "mba-2" "192.168.x.x" "22" "username")
ACER_JSON=$(check_remote_machine "acer-a3" "192.168.x.x" "22" "username")
```

### 4.3 Test Connectivity

```bash
# From VM, test SSH to each machine
ssh -o ConnectTimeout=5 user@macbook1-ip "echo ok"
ssh -o ConnectTimeout=5 user@macbook2-ip "echo ok"
ssh -o ConnectTimeout=5 user@acer-ip "echo ok"
```

Note: Local machines behind a router need either:
- Port forwarding (router config: forward port 22 to each machine's LAN IP)
- Tailscale/ZeroTier VPN (recommended, free, zero port forwarding needed)
- ngrok/Cloudflare tunnel (alternative)

### 4.4 Recommended: Tailscale VPN

Install on all machines (VM + 3 locals):
```bash
# Linux/WSL
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up

# macOS
brew install --cask tailscale
# Then open Tailscale app and sign in
```

Tailscale gives each machine a stable 100.x.y.z IP. No port forwarding needed. Free for personal use (up to 100 devices).

---

## Claude Desktop Memory Sharing

### The Problem
Claude Code stores project memory at `~/.claude/projects/<project-hash>/memory/MEMORY.md`. This is local to each machine and NOT in the Git repo.

### The Solution

**Shared rules**: Use `CLAUDE.md` in the repo root (already Git-synced to all machines). This file contains architecture, rules, skills, and project context. All machines see the same CLAUDE.md after `git pull`.

**Shared state**: Use Supabase tables (`predictions`, `experiments`, `fleet_status`). All machines read/write the same database.

**Machine-specific memory**: Each machine's `~/.claude/projects/.../memory/MEMORY.md` can contain machine-specific notes. These do NOT need to sync -- they are context for that machine's Claude sessions only.

**If you want to sync memory files anyway**:

Option A -- Symlink to repo (not recommended, clutters Git):
```bash
ln -s ~/nomos42/mon-ipad/.claude-memory ~/.claude/projects/-home-user-nomos42-mon-ipad/memory
```

Option B -- Periodic rsync (better):
```bash
# Pull memory from VM every hour
0 * * * * rsync -az termius@<VM_IP>:~/.claude/projects/-home-termius-mon-ipad/memory/ ~/.claude/projects/<local-hash>/memory/
```

Option C -- Just use CLAUDE.md (recommended):
Everything important is already in CLAUDE.md. Machine-specific memory files are fine being local-only.
