# Pierre — Test User Setup Guide

> First external user testing Nomos42 AI agent capabilities
> Created: 2026-03-28

## SECURITY RULES

1. **Pierre has access to `nomos-pierre` repo ONLY** — ZERO access to any other repo
2. **Read-only on main Supabase tables** — writes only to `pierre_*` tables
3. **Full monitoring** — all Claude Code CLI activity is logged and visible to Alexis
4. **No SSH access to VM** — API access only via infra-brain
5. **Credentials pre-loaded in `.env.local`** — Pierre never touches credentials
6. **HF token sent via Telegram bot** — secure delivery

## Architecture

```
Pierre (MacBook Air 2016)
    ├── Claude Code CLI (with Alexis's Max subscription)
    ├── Repo: LBJLincoln/nomos-pierre (private, ONLY this repo)
    ├── CLAUDE.md with 22 agents + skills preconfigured
    ├── .env.local with ALL credentials pre-loaded
    ├── HF Space: dedicated (on new HF account)
    ├── Supabase #2: dedicated project or tables (pierre_*)
    ├── Neo4j: dedicated database or namespace
    ├── Pinecone: dedicated index
    └── API access to Nomos42 data (READ-ONLY via infra-brain)

Alexis (iPad + VM)
    ├── Full read access to nomos-pierre repo (owner)
    ├── git log monitoring (all Pierre's commits visible)
    ├── Claude Code CLI activity logs
    ├── Can assign tasks via API
    └── Evaluates: can this become a SaaS/API product?
```

**GOAL:** Validate that an external user can benefit from our 22-agent AI swarm without touching backend/infra.

---

## Step 1: Create GitHub Repo (Alexis, on VM)

```bash
# Create repo
mkdir -p ~/nomos-pierre
cd ~/nomos-pierre
git init

# Copy agent infrastructure (NOT code, just configuration)
cp -r ~/mon-ipad/.claude/agent-definitions/ .claude/agent-definitions/ 2>/dev/null
mkdir -p .claude/hooks scripts data

# Initialize
git add -A && git commit -m "initial: Pierre's workspace"
gh repo create LBJLincoln/nomos-pierre --private --source=. --push

# Add Pierre as collaborator
gh api repos/LBJLincoln/nomos-pierre/collaborators/PIERRE_GITHUB_USERNAME -X PUT -f permission=push
```

## Step 2: CLAUDE.md for Pierre

Create this file in the repo root. It gives Pierre access to all 22 agents via Claude Code CLI:

```markdown
# Nomos42 Agent Platform — Pierre's Workspace

## Available Agents (22)

### Research Department
| Agent | Role | Skills |
|-------|------|--------|
| research-analyst | Research papers + data analysis | WebSearch, Supabase queries |
| karpathy-researcher | Feature proposals + Karpathy loop | WebSearch, code analysis |
| repo-scout | GitHub/HF model discovery | WebSearch, HF Hub |
| feature-engineer | Feature engineering proposals | Code, Supabase |

### Engineering Department
| Agent | Role | Skills |
|-------|------|--------|
| evolution-optimizer | Tune GA parameters | Bash, Supabase, code |
| nba-brain | 24/7 decision making | All tools |
| market-analyst | Live odds analysis | WebFetch, Supabase |

### Available Skills
| Skill | Usage |
|-------|-------|
| /karpathy-loop | Autonomous research cycle |
| /daily-edge | Daily predictions + value bets |
| /progress-10pct | Improve weakest metric by 10% |
| /spaces-health | Check all HF evolution islands |
| /evolve-report | Evolution progress report |
| /agent-review | Agent performance review |

## Data Access (API)

Pierre can access Nomos42 data via the infra-brain API:

```bash
# Get current HF spaces status
curl -s https://nomos42-nomos42-infra-brain.hf.space/api/spaces

# Get latest predictions
curl -s https://nomos42-nomos42-infra-brain.hf.space/task \
  -H "Content-Type: application/json" \
  -d '{"type": "supabase", "table": "predictions", "limit": 10}'

# Run Gemini research
curl -s https://nomos42-nomos42-infra-brain.hf.space/task \
  -H "Content-Type: application/json" \
  -d '{"type": "research", "prompt": "What are the latest NBA prediction papers?"}'
```

## Rules
1. ZERO ML training on MacBook — use HF Spaces or Kaggle
2. Data access is READ-ONLY on main tables
3. Pierre writes to `pierre_*` tables in Supabase
4. All experiments tagged with `user: pierre`
```

## Step 3: Pierre's MacBook Setup (3 commands)

```bash
# 1. Install Claude Code CLI
brew install node python3 git
npm install -g @anthropic-ai/claude-code

# 2. Clone workspace
git clone git@github.com:LBJLincoln/nomos-pierre.git
cd nomos-pierre

# 3. Login to Claude Code (Alexis provides API key)
claude auth login
# Enter Alexis's Max subscription API key when prompted
```

## Step 4: HF Space for Pierre

Create a dedicated HF Space on the new account Alexis will create:

```bash
# On VM (Alexis)
source ~/.env.local

python3 -c "
from huggingface_hub import HfApi
api = HfApi(token='PIERRE_HF_TOKEN')
api.create_repo('PIERRE_ACCOUNT/pierre-workspace', repo_type='space', space_sdk='gradio')
print('Space created')
"
```

## Step 5: Supabase — Dedicated Tables

```sql
-- Pierre's experiment tracking
CREATE TABLE pierre_experiments (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    experiment_name TEXT NOT NULL,
    config JSONB,
    brier_score FLOAT,
    roi_pct FLOAT,
    notes TEXT,
    user_id TEXT DEFAULT 'pierre'
);

-- Pierre's predictions
CREATE TABLE pierre_predictions (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    game_date DATE,
    home_team TEXT,
    away_team TEXT,
    prediction FLOAT,
    actual_result INT,
    bet_type TEXT,
    edge_pct FLOAT
);

-- Grant Pierre read access to main tables
GRANT SELECT ON predictions TO pierre_role;
GRANT SELECT ON experiments TO pierre_role;
GRANT ALL ON pierre_experiments TO pierre_role;
GRANT ALL ON pierre_predictions TO pierre_role;
```

## Step 6: Chrome Extension (Browser Automation)

Pierre can use Claude Code CLI with the Chrome extension for browser automation:

```bash
# On Pierre's MacBook:
# 1. Install Claude Code desktop app (not just CLI)
# 2. Install "Claude in Chrome" extension from Chrome Web Store
# 3. Claude Code CLI will auto-detect the extension

# Usage in Claude Code CLI:
claude "Go to ESPN NBA scores and extract today's game results"
claude "Open DraftKings and check the Celtics moneyline odds"
```

**Remote control from VM (via SSH):**
```bash
# From VM, delegate browser task to Pierre's machine:
ssh pierre@PIERRE_IP "cd ~/nomos-pierre && claude -p 'Open Chrome, go to ESPN NBA scores, save to data/scores.json'"
```

## Step 7: Night GPU Usage

Pierre's MacBook Air 2016 has Intel HD Graphics 6000 (no CUDA). However:

```bash
# Overnight CPU tasks (crontab on Pierre's MacBook):
0 22 * * * cd ~/nomos-pierre && claude -p "/karpathy-loop" >> /tmp/karpathy.log 2>&1
0 2 * * * cd ~/nomos-pierre && python3 scripts/data-fetch.py >> /tmp/data.log 2>&1

# GPU tasks go to Kaggle/Modal (triggered from any machine):
0 23 * * * kaggle kernels push -p scripts/kaggle/
```

---

## API Evaluation Model

This setup is a prototype for the **Nomos Picks SaaS** ($19/$49/$149):

| Feature | Pierre (test) | Scout ($19) | Edge ($49) | Whale ($149) |
|---------|---------------|-------------|------------|--------------|
| Daily picks | Yes | 3/day | All | All + props |
| Agents | All 22 | 3 basic | 10 | All 22 |
| API access | Full | Read-only | Read + write | Full + priority |
| Custom experiments | Yes | No | Limited | Unlimited |
| HF Space | Dedicated | Shared | Dedicated | Dedicated + GPU |
| Support | Direct | Email | Chat | 1:1 |

**Metrics to track:**
- How long does Pierre take to get productive?
- Which agents does he use most?
- Does the API pattern work (request data → run experiment → share results)?
- Would he pay $49/month for this?

---

## Step 8: Pre-loaded Credentials (.env.local)

Pierre's `.env.local` in his repo — Alexis creates this BEFORE Pierre clones:

```bash
# .env.local — Pierre's workspace (DO NOT MODIFY)
# All credentials managed by Alexis

# HuggingFace (Pierre's dedicated account)
HF_TOKEN=hf_xxxxx  # Sent via Telegram

# Supabase (dedicated project or tables)
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=eyJxxxxx
# Pierre writes to pierre_* tables ONLY

# Neo4j (dedicated database)
NEO4J_URI=neo4j+s://xxxxx.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=xxxxx

# Pinecone (dedicated index)
PINECONE_API_KEY=xxxxx
PINECONE_INDEX=pierre-nba

# Infra Brain API (read-only access to Nomos42 data)
INFRA_BRAIN_URL=https://nomos42-nomos42-infra-brain.hf.space
INFRA_AUTH_TOKEN=pierre_read_xxxxx

# Kaggle (shared, Pierre's own account preferred)
KAGGLE_USERNAME=pierre_xxxxx
KAGGLE_KEY=xxxxx
```

**Alexis prepares this file, commits it to the repo, Pierre just clones.**
Pierre never needs to create accounts or find API keys.

## Step 9: Full Monitoring (Alexis side)

### Git monitoring (all commits visible)
```bash
# On VM, add cron to monitor Pierre's activity
*/30 * * * * cd ~/nomos-pierre && git pull && git log --oneline -5 >> /tmp/pierre-activity.log
```

### Claude Code CLI logs
Claude Code stores conversation logs in `~/.claude/`. On Pierre's machine,
these stay local. For monitoring, Pierre's CLAUDE.md includes a hook:

```json
// In .claude/settings.json on Pierre's repo
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "cd $CLAUDE_PROJECT_DIR && git add -A && git commit -m 'auto: session sync' && git push 2>/dev/null || true"
          }
        ]
      }
    ]
  }
}
```

This auto-pushes after every Claude Code session — Alexis sees all changes.

### Dashboard monitoring
Add Pierre's activity to the dashboard at nomosdashboard.vercel.app:
```bash
# API endpoint that checks Pierre's repo
curl -s https://api.github.com/repos/LBJLincoln/nomos-pierre/commits?per_page=5
```

### ISOLATION — Pierre CANNOT access other repos

Pierre's GitHub account gets `push` access to `nomos-pierre` ONLY.
The CLAUDE.md in his repo does NOT reference any other repo paths.
The `.claude/settings.json` has NO hooks that touch `~/mon-ipad/` or other dirs.
The infra-brain API only exposes read-only endpoints.

## Quick Reference

| Resource | URL/Path |
|----------|----------|
| Pierre's repo | github.com/LBJLincoln/nomos-pierre |
| Infra Brain API | nomos42-nomos42-infra-brain.hf.space |
| Dashboard | nomosdashboard.vercel.app |
| Supabase | Tables: pierre_experiments, pierre_predictions |
| HF Space | TBD (new account) |
