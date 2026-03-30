# Pierre — Prototype User Setup Guide

> First external user testing the full Nomos42 ecosystem
> Machine: MacBook Air 2016 (Intel i5, 8GB, macOS)
> Role: Prototype user + browser dispatch node
> Created: 2026-03-28 | Updated: 2026-03-30

## What Pierre Tests

Pierre is the **prototype user** for the entire Nomos42 product line:

| Product | URL | Pierre's Role |
|---------|-----|---------------|
| Nomos Picks (SaaS) | nomos-picks.com (TBD) | First paying customer prototype |
| Dashboard | nomosdashboard.vercel.app | Power user testing all routes |
| @Forge42Bot | Telegram | First external bot user |
| NBA Predictions | via bot + dashboard | Daily picks consumer |
| Agent Platform | via Claude Desktop | Tests 22-agent delegation |

## SECURITY RULES

1. **Pierre has access to `nomos-pierre` repo ONLY** — ZERO access to any other repo
2. **Read-only on main Supabase tables** — writes only to `pierre_*` tables
3. **Full monitoring** — all Claude Code CLI activity logged and visible to Alexis
4. **No SSH to VM internals** — API access only via infra-brain
5. **Credentials pre-loaded in `.env.local`** — Pierre never touches credentials
6. **HF token sent via @Forge42Bot** — secure delivery
7. **Claude Desktop = dispatch target** — Alexis can send browser tasks

## Architecture

```
Pierre (MacBook Air 2016, macOS) — NO GITHUB, NO VM ACCESS
    ├── Claude Desktop → 22 agents (Alexis's Max subscription)
    ├── Claude Code CLI → advanced terminal commands
    ├── Chrome browser → 5 Vercel sites + Claude extension
    ├── Telegram → @Forge42Bot + @Nomos42Bot
    ├── NO SSH to VM, NO repo cloning, NO server access
    └── Everything runs locally — APIs only via public endpoints

Aurelien's Acer Aspire 3 (Windows 11 + WSL2)
    ├── COMPUTE NODE ONLY — Alexis SSHs in for free GPU/ML
    ├── WSL2 Ubuntu → ML training, quant models, evolution
    ├── NO repo, NO user access, NO interaction
    └── Role: free hardware for model training

Alexis (iPad + VM)
    ├── Full read access to nomos-pierre repo (owner)
    ├── SSHs into Aurelien's Acer for ML compute
    ├── git log monitoring (all commits visible)
    ├── Can assign tasks via @Forge42Bot
    └── Evaluates: can this become a SaaS/API product?
```

**GOAL:** Validate that external users can benefit from our 22-agent AI swarm + web products without touching backend/infra.

---

## Step 1: Create GitHub Repo (Alexis, on VM)

```bash
mkdir -p ~/nomos-pierre
cd ~/nomos-pierre
git init

# Copy agent infrastructure (NOT code, just configuration)
cp -r ~/mon-ipad/.claude/agent-definitions/ .claude/agent-definitions/ 2>/dev/null
mkdir -p .claude/hooks scripts data

git add -A && git commit -m "initial: Pierre + Aurelien workspace"
gh repo create LBJLincoln/nomos-pierre --private --source=. --push

# Add Pierre as collaborator (replace with his GitHub username)
gh api repos/LBJLincoln/nomos-pierre/collaborators/PIERRE_GITHUB_USERNAME -X PUT -f permission=push
# Aurelien = compute node only, no repo access needed
```

## Step 2: CLAUDE.md for Pierre & Aurelien

Create this file in the repo root:

```markdown
# Nomos42 Agent Platform — Pierre & Aurelien Workspace

## Available Agents (22)

### Research Department (4)
| Agent | Role |
|-------|------|
| research-analyst | Papers + data analysis (WebSearch, Supabase) |
| karpathy-researcher | Feature proposals + Karpathy loop |
| repo-scout | GitHub/HF model discovery |
| feature-engineer | Feature engineering proposals |

### Engineering Department (5)
| Agent | Role |
|-------|------|
| evolution-optimizer | Tune GA parameters |
| nba-brain | 24/7 decision making |
| market-analyst | Live odds analysis |
| test-runner | Run test suites |
| bug-fixer | Diagnose + fix issues |

### Betting Department (5)
| Agent | Role |
|-------|------|
| odds-monitor | Live odds + steam moves |
| betting-strategist | Portfolio Kelly + multi-market |
| strategy-tester | Backtest strategies |
| strategy-corrector | Fix losing strategies |
| halftime-scorer | In-game 2H bets |

### Available Skills
| Skill | Usage |
|-------|-------|
| /karpathy-loop | Autonomous research cycle |
| /daily-edge | Daily predictions + value bets |
| /progress-10pct | Improve weakest metric by 10% |
| /spaces-health | Check all HF evolution islands |
| /evolve-report | Evolution progress report |
| /agent-review | Agent performance review |

## Telegram Bot
@Forge42Bot — send commands, receive picks, check status

## Web Products (test all)
- Dashboard: nomosdashboard.vercel.app (/nba, /political, /rgwa, /evolution)
- Nomos Picks: TBD (SaaS prototype)

## Data Access (API)
curl -s https://nomos42-nomos42-infra-brain.hf.space/api/spaces
curl -s https://nomos42-nomos42-infra-brain.hf.space/api/predictions

## Rules
1. ZERO ML training on laptop — use HF Spaces or Kaggle
2. Data access is READ-ONLY on main tables
3. Write to pierre_* tables in Supabase
4. All experiments tagged with user: pierre or user: aurelien
```

## Step 3: Pierre's MacBook Setup

See: `docs/PIERRE-INSTALL-MESSAGE.md` (French, 3 steps)

Summary:
1. Homebrew + git + python3 + node
2. Claude Code Desktop + Chrome extension
3. Clone repo + SSH test

## Step 4: Aurelien's Acer (Compute Node Only)

Aurelien's Acer Aspire 3 is used as a **free compute node** by Alexis.
No user setup needed — Alexis SSHs in via WSL2 for ML training.

Setup (Alexis does this):
1. WSL2 Ubuntu with ML deps (python3, pytorch, scikit-learn, xgboost, lightgbm, catboost)
2. SSH key from VM → Acer
3. Cron jobs run remotely from VM via SSH

## Step 5: Dedicated HF Space (NEW account)

Create a new HF account for Pierre's space:

```bash
# On VM (Alexis) — after creating the new HF account
# Store the token as HF_TOKEN_PIERRE in .env.local
python3 -c "
from huggingface_hub import HfApi
api = HfApi(token='HF_TOKEN_PIERRE_VALUE')
api.create_repo('PIERRE_HF_ACCOUNT/nomos-pierre', repo_type='space', space_sdk='gradio')
print('Space created')
"
```

## Step 6: Supabase — Dedicated Tables

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
    edge_pct FLOAT,
    user_id TEXT DEFAULT 'pierre'
);

-- Aurelien = compute node only, no dedicated tables needed
```

## Step 7: @Forge42Bot Setup

The bot is already defined in `scripts/telegram/forge_bot.py`.

```bash
# Start the Forge bot
cd ~/mon-ipad
python3 scripts/telegram/forge_bot.py &

# Pierre interacts via Telegram:
# /start — Welcome + available commands
# /picks — Today's NBA picks
# /status — System health
# /login pierre — Link account
```

## Step 8: Browser Dispatch (Alexis → Pierre/Aurelien)

With Claude Desktop + Chrome extension installed, Alexis can dispatch browser tasks:

```bash
# From VM, push a task file that Pierre's Claude picks up:
cat > ~/nomos-pierre/tasks/pending/scrape-espn.json << 'EOF'
{
  "type": "browser",
  "target": "pierre",
  "url": "https://www.espn.com/nba/scoreboard",
  "action": "extract_scores",
  "output": "data/scores-today.json",
  "priority": "normal"
}
EOF
git add -A && git commit -m "task: scrape ESPN scores" && git push
```

Pierre's Claude Desktop (running in background) picks up the task, opens Chrome, scrapes, saves result, pushes back.

## Step 9: Pre-loaded Credentials (.env.local)

```bash
# .env.local — Pierre & Aurelien workspace
# All credentials managed by Alexis

# HuggingFace (Pierre's dedicated account)
HF_TOKEN=hf_xxxxx

# Supabase (shared, write to pierre_*/aurelien_* tables only)
SUPABASE_URL=https://xivvnrkbtuhfsphtmmtv.supabase.co
SUPABASE_KEY=eyJxxxxx

# Neo4j (read-only)
NEO4J_URI=neo4j+s://38c949a2.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=xxxxx

# Pinecone (dedicated index)
PINECONE_API_KEY=xxxxx
PINECONE_INDEX=pierre-nba

# Infra Brain API (read-only access to Nomos42 data)
INFRA_BRAIN_URL=https://nomos42-nomos42-infra-brain.hf.space
INFRA_AUTH_TOKEN=pierre_read_xxxxx

# Forge Bot
FORGE_BOT_TOKEN=xxxxx

# Kaggle (shared or personal)
KAGGLE_USERNAME=xxxxx
KAGGLE_KEY=xxxxx
```

## Step 10: Monitoring (Alexis side)

```bash
# Cron on VM — monitor Pierre & Aurelien activity
*/30 * * * * cd ~/nomos-pierre && git pull && git log --oneline -5 >> /tmp/fleet-activity.log

# Auto-push hook in .claude/settings.json
{
  "hooks": {
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "cd $CLAUDE_PROJECT_DIR && git add -A && git commit -m 'auto: session sync' && git push 2>/dev/null || true"
      }]
    }]
  }
}
```

## Step 11: Product Testing Checklist

Pierre tests ALL products:

- [ ] Dashboard: login, browse /nba, /political, /evolution
- [ ] @Forge42Bot: /start, /picks, /status, /login
- [ ] Nomos Picks: sign up flow, view predictions, check history
- [ ] Agent dispatch: run /daily-edge, /karpathy-loop, /spaces-health
- [ ] Browser scraping: ESPN scores, DraftKings odds, injury reports
- [ ] API access: curl infra-brain endpoints
- [ ] HF Space: view evolution dashboard
- [ ] Supabase: write experiment, read predictions

## SaaS Evaluation

| Feature | Pierre (test) | Scout ($19) | Edge ($49) | Whale ($149) |
|---------|---------------|-------------|------------|--------------|
| Daily picks | Yes | 3/day | All | All + props |
| Agents | All 22 | 3 basic | 10 | All 22 |
| API access | Full | Read-only | Read + write | Full + priority |
| Browser dispatch | Yes | No | No | Yes |
| HF Space | Dedicated | Shared | Dedicated | Dedicated + GPU |
| @Forge42Bot | Full | Basic | Full | Full + priority |
| Support | Direct | Email | Chat | 1:1 |

**Metrics to track:**
- Time to first successful prediction check
- Which agents Pierre uses most
- Which products he returns to daily
- Would he pay $49/month for this?
- Aurelien's data ingestion reliability

---

*Nomos42 Fleet — Pierre + Aurelien prototype | 2026-03-30*
