# Fleet Setup - 3 Clicks Max Per Step

> Every step = 3 commands or actions max. Copy-paste ready.
> Updated: 2026-03-28

## Architecture

```
iPad (Termius SSH) ──> GCP VM (Primary Brain)
                          ├── 6 HF Spaces (CPU evolution, always-on)
                          ├── Kaggle GPU (30hr/week, Karpathy loops)
                          ├── Modal GPU (serverless TabICL)
                          └── Colab GPU (on-demand)

MacBook Air #1 (Pierre) ──> Test user: 5 Vercel sites + HF Space + databases
Acer Aspire 3  (Aurelien) ──> Compute node: Alexis SSHs in for ML training
```

**RULE: ZERO ML TRAINING on VM or local machines. GPU = Kaggle/Modal/Colab/HF only.**
**RULE: ZERO Next.js build on VM. Deploy = git push, Vercel builds automatically.**

---

## PART 1: Setup Each Secondary Machine

### Step 1.1: MacBook Air #1 (Research Agent)

```bash
# 1. Install prerequisites
brew install git node python3 && pip3 install kaggle modal nba_api

# 2. Clone repos + setup Claude Code
git clone git@github.com:LBJLincoln/mon-ipad.git && git clone git@github.com:LBJLincoln/nomos-nba-agent.git && git clone git@github.com:LBJLincoln/nomos-dashboard.git

# 3. Install Claude Code CLI + copy env
npm install -g @anthropic-ai/claude-code && scp termius@VM_IP:~/mon-ipad/.env.local ~/mon-ipad/.env.local
```

### Step 1.2: MacBook Air #2 (Strategy Agent)

```bash
# Same as MBA-1
brew install git node python3 && pip3 install kaggle modal nba_api
git clone git@github.com:LBJLincoln/mon-ipad.git && git clone git@github.com:LBJLincoln/nomos-nba-agent.git
npm install -g @anthropic-ai/claude-code && scp termius@VM_IP:~/mon-ipad/.env.local ~/mon-ipad/.env.local
```

### Step 1.3: Acer Aspire 3 (Data Agent)

```bash
# 1. Enable WSL2 (PowerShell as Admin)
wsl --install -d Ubuntu

# 2. Inside WSL2 Ubuntu:
sudo apt update && sudo apt install -y git python3-pip nodejs npm
pip3 install kaggle modal nba_api youtube-transcript-api

# 3. Clone + env
git clone git@github.com:LBJLincoln/mon-ipad.git && scp termius@VM_IP:~/mon-ipad/.env.local ~/mon-ipad/.env.local && npm install -g @anthropic-ai/claude-code
```

---

## PART 2: SSH Keys (so VM can reach machines)

### On each secondary machine:

```bash
# 1. Generate key
ssh-keygen -t ed25519 -f ~/.ssh/nomos_fleet -N ""

# 2. Copy public key to VM
ssh-copy-id -i ~/.ssh/nomos_fleet.pub termius@34.136.180.66

# 3. Test connection
ssh -i ~/.ssh/nomos_fleet termius@34.136.180.66 "echo 'Connected from $(hostname)'"
```

### On VM (allow machines to connect):

```bash
# Add each machine's public key (one time)
cat >> ~/.ssh/authorized_keys << 'EOF'
# MBA-1 key (paste here)
# MBA-2 key (paste here)
# Acer key (paste here)
EOF
```

---

## PART 3: Cron Jobs Per Machine

### MBA-1 (Research):
```bash
crontab -e
# Add:
0 */6 * * * cd ~/mon-ipad && claude -p "Run /karpathy-loop" >> /tmp/karpathy.log 2>&1
0 */12 * * * cd ~/mon-ipad && claude -p "Run repo-scout research" >> /tmp/repo-scout.log 2>&1
*/30 * * * * cd ~/mon-ipad && git pull --rebase && git push 2>/dev/null
```

### MBA-2 (Strategy):
```bash
crontab -e
# Add:
0 8 * * * cd ~/mon-ipad && claude -p "Run /daily-edge for today" >> /tmp/daily-edge.log 2>&1
*/30 * * * * cd ~/mon-ipad && git pull --rebase && git push 2>/dev/null
```

### Acer (Data):
```bash
crontab -e
# Add:
0 * * * * cd ~/mon-ipad && python3 scripts/fetch_free_odds.py >> /tmp/odds.log 2>&1
0 */4 * * * cd ~/mon-ipad && python3 scripts/fetch_player_tracking.py >> /tmp/tracking.log 2>&1
*/30 * * * * cd ~/mon-ipad && git pull --rebase && git push 2>/dev/null
```

---

## PART 4: Exploit Secondary Machine CPU

The MacBooks and Acer have 4-8GB RAM + multi-core CPU. They CAN run:
- Data preprocessing (pandas, numpy)
- Feature engineering (no training)
- Backtest analysis (read results, compute stats)
- Claude Code CLI agents (research, proposals)

They CANNOT run: model training, neural networks, GPU tasks.

### Offload CPU work from VM:

```bash
# On MBA-1: Run feature engineering analysis
cd ~/mon-ipad && python3 -c "
from hf_space.features.engine import build_features
# Test feature computation locally (no training)
"

# On MBA-2: Run backtest analysis
cd ~/mon-ipad && python3 scripts/verify_backtest.py

# On Acer: Fetch data (nba_api works better on non-cloud IPs)
cd ~/mon-ipad && python3 scripts/fetch_player_tracking.py
```

---

## PART 5: Vercel Auto-Deploy (NO builds on VM)

### One-time setup:

```bash
# 1. Connect repos to Vercel (do this on vercel.com dashboard)
# nomos-dashboard -> nomosdashboard.vercel.app (ALREADY DONE)
# nomos-picks -> nomospicks.vercel.app (TODO)

# 2. Set env vars on Vercel dashboard for each project:
# TERMINAL_PASSWORD=QLF@26abe
# NEXT_PUBLIC_VM_IP=34.136.180.66
# Any other secrets from .env.local

# 3. Deploy = just push to GitHub
cd ~/nomos-dashboard && git add -A && git commit -m "deploy" && git push
# Vercel auto-builds, auto-deploys. Zero VM resources used.
```

### Alternative: GitHub Actions build (if Vercel not available)

Create `.github/workflows/deploy.yml` in each Next.js repo:
```yaml
name: Build & Deploy
on:
  push:
    branches: [main]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: npm ci && npm run build
```

---

## PART 6: Manual Commands Checklist

### Things YOU must do manually (cross-repo):

#### VM (from iPad Termius):

```bash
# 1. Free disk space (VM at 92%)
rm -rf /home/termius/nomos-picks/node_modules /home/termius/nomos-picks/.next
npm cache clean --force
rm -rf /home/termius/.npm/_cacache

# 2. Persist terminal token (survives reboot)
echo 'export TERMINAL_TOKEN="QLF@26abe"' >> ~/.bashrc && source ~/.bashrc

# 3. Push all uncommitted changes (5 repos)
cd ~/mon-ipad && git add -A && git commit -m "sync" && git push
cd ~/nomos-nba-agent && git add -A && git commit -m "sync" && git push
cd ~/nomos-dashboard && git add -A && git commit -m "sync" && git push
cd ~/nomos-political-alpha && git add -A && git commit -m "sync" && git push
cd ~/rgwa && git add -A && git commit -m "sync" && git push

# 4. Set Vercel env vars (via vercel.com or CLI)
# Go to: vercel.com/dashboard > nomos-dashboard > Settings > Environment Variables
# Add: TERMINAL_PASSWORD = QLF@26abe

# 5. Create nomos-picks GitHub repo
cd ~/nomos-picks && gh repo create LBJLincoln/nomos-picks --private --source=. --push

# 6. Connect nomos-picks to Vercel
# Go to: vercel.com > Import Git Repository > LBJLincoln/nomos-picks
```

#### Kaggle (from any machine):

```bash
# 1. Check running kernels
kaggle kernels list --mine --sort-by dateRun | head -5

# 2. Push updated backtest script
kaggle kernels push -p scripts/kaggle-backtest/

# 3. Download results
kaggle kernels output alexismoret6/nba-season-backtest -p data/nba-agent/
```

#### HF Spaces (from VM or any machine with HF CLI):

```bash
# 1. Check all 6 islands
for s in nba-quant nba-quant-2 nba-evo-3 nba-evo-4 nba-evo-5 nba-evo-6; do
  echo "$s: $(curl -s https://nomos42-$s.hf.space/api/status | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("best_brier","?"))' 2>/dev/null)"
done

# 2. Restart a crashed space
huggingface-cli repo restart Nomos42/nba-quant --type space --token $HF_TOKEN_3

# 3. Deploy updated engine to all spaces
cd ~/mon-ipad && for s in nba-quant nba-quant-2 nba-evo-3 nba-evo-4 nba-evo-5 nba-evo-6; do
  git subtree push --prefix=hf-space https://huggingface.co/spaces/Nomos42/$s main 2>/dev/null &
done
```

#### Modal:

```bash
# 1. Restart evolution (if crashed)
cd ~/mon-ipad && modal run scripts/modal_tabicl_evolution.py &

# 2. Check status
modal app list

# 3. View logs
modal app logs
```

#### Supabase:

```bash
# Primary is PAUSED. Use pooler connection.
# Check if data is being written:
# Go to: supabase.com > Project xivvnr > Table Editor > experiments
```

#### Dashboard:

```bash
# 1. Test locally (MBA-2 only, NOT on VM)
cd ~/nomos-dashboard && npm run dev

# 2. Deploy (just push)
cd ~/nomos-dashboard && git push  # Vercel auto-deploys

# 3. Check status
curl -s https://nomosdashboard.vercel.app/api/nba/spaces | python3 -m json.tool | head -20
```

---

## PART 7: Daily Workflow (from iPad)

```bash
# Morning check (1 command)
ssh termius@VM_IP "cat ~/mon-ipad/data/fleet-status.json | python3 -m json.tool"

# Run daily edge
ssh termius@VM_IP "cd ~/mon-ipad && claude -p '/daily-edge'"

# Check all spaces
ssh termius@VM_IP "~/mon-ipad/scripts/watchdog.sh"

# View agent activity
curl -s https://nomosdashboard.vercel.app/api/agents/activity | python3 -m json.tool
```

---

## PART 8: Troubleshooting

| Problem | Fix (3 clicks) |
|---------|----------------|
| VM disk full | `rm -rf ~/nomos-picks/node_modules ~/.npm/_cacache /tmp/claude-*` |
| HF Space crashed | `huggingface-cli repo restart Nomos42/SPACE_NAME --type space` |
| Kaggle kernel stuck | `kaggle kernels list --mine` then re-push |
| Modal timeout | Increase timeout in script, `modal run ...` |
| Telegram bot down | `cd ~/mon-ipad && scripts/telegram/start_bots.sh restart` |
| Data server down | `nohup python3 -m http.server 8080 -b 0.0.0.0 --directory ~/mon-ipad/data &` |
| Terminal API down | `export TERMINAL_TOKEN=QLF@26abe && nohup python3 scripts/terminal_api.py &` |
| Git conflicts | `git stash && git pull --rebase && git stash pop` |
| Claude Code crash | Just restart: `claude` (state persists in .claude/) |
| Vercel build fail | Check: `vercel.com > Project > Deployments > latest > Build Logs` |
