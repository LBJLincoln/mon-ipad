# NOMOS42 — Daily Operations Dashboard

> **Last updated:** 2026-04-02 10:07 UTC | **Auto-refreshed by:** trading-floor-v8 cron
> **Read this on your iPad to know exactly where we are and what YOU need to do.**

---

## CROSS-REPO STATUS AT A GLANCE

| Repo | Purpose | Status | HF Spaces | Key Metric | Next Action |
|------|---------|--------|-----------|------------|-------------|
| **mon-ipad** | Pilot / Orchestrator | ACTIVE | — | Iteration 7, Gen 952 | Auto-iterating |
| **nomos-nba-agent** | NBA Predictions | ACTIVE | S10-S15 (6 islands) | Brier 0.21570 ATR | Engine parity check |
| **nomos-political-alpha** | Political Alpha | ACTIVE | P1-P4 (4 islands) | Brier 0.24186 (P1) | P3/P4 need deploy |
| **rgwa** | AI Art Generation | IDLE | — (needs setup) | 0 pieces generated | First generation run |
| **nomos-dashboard** | Frontend / Arena | ACTIVE | — (Vercel) | Trading Floor v5 live | Visual iteration |

---

## WHAT YOU NEED TO DO MANUALLY (Blockers)

### CRITICAL (blocks progress)
- [ ] **Stripe account setup** — Connect Stripe to your account for SaaS billing ($19/$49/$149 tiers). Claude can't do this for you — needs your banking info. Go to stripe.com/dashboard
- [ ] **Social media accounts** — Give Claude the API keys/tokens for: X/Twitter, LinkedIn. TikTok/YouTube/Instagram later. Type `! export TWITTER_API_KEY=xxx` in Claude Code to add
- [ ] **Vercel domain** — If you want a custom domain for nomos-dashboard, add it in Vercel dashboard
- [ ] **P3/P4 Political Spaces** — P3 (catboost) and P4 (wide) show gen=None. Check HF dashboard: huggingface.co/Nomos42 — they may need manual restart or redeploy

### IMPORTANT (accelerates progress)
- [ ] **Kaggle API token refresh** — Check if `~/.kaggle/kaggle.json` is current. Needed for GPU burst sessions
- [ ] **Colab notebook review** — Open `colab/nba_evolution_gpu.ipynb`, run cells to verify T4 access still works
- [ ] **Lightning AI credits** — Check remaining credits at lightning.ai/dashboard
- [ ] **Review & approve social media posts** — Pre-drafted posts are in `docs/social-media/` — review before publishing
- [ ] **Review investor deck** — Draft deck is in `docs/deck/` — review narrative and approve

### MINOR (nice to have)
- [ ] **Delete 13 unused HF Spaces** — See audit below. Delete from HF dashboard:
  - Nomos42: nomos42-infra-brain, nomos42-paperclip, nomos42-brain, karpathy-arena, political-alpha-3, political-alpha-4
  - LBJLincoln: betting-monitor, fleet-monitor, island-coordinator
  - LBJLincoln26: research-radar, quality-tracker, predictions-monitor, political-monitor
- [ ] **Recreate P3/P4 on LBJLincoln** — After deleting from Nomos42, redeploy on LBJLincoln account
- [ ] **Telegram channel posts** — @Nomos42 channel could use weekly update posts

---

## TRADING FLOOR — GAME ITERATIONS

### Current State
- **Iteration:** 43 | **Generation:** 5848
- **Best bankroll:** $302,155 by codex
- **$1M target:** 30.2% achieved, need 3.3x more
- **Best strategy:** full_kelly (+72,615% ROI)
- **Best model:** xgboost (+$322/bet avg)
- **Mutations:** Claude adopted streak_momentum from Codex
- **Eliminations:** 3 NBA + 3 political strategies coffined

### Auto-Iteration Loop (every 4h via cron)
```
Iteration N finishes
  → autonomous-cycle.sh Phase 3c triggers
  → python3 trading-floor-v4.py karpathy
  → Analyzes ALL results (strategy/model/category performance)
  → Auto-eliminates losing strategies (<-50% ROI)
  → Mutates losing agents (adopt winner strategies)
  → Saves best config toward $1M
  → Writes karpathy-output.json for Guardian
  → Git push results
  → Next iteration starts on next cron cycle
```

---

## 3-LAYER ORGANIZATION PER PROJECT

### Layer 1: IDEATION & ANALYSIS (Brain)

| Dept | Metric | Current | Target | Loop | HF Space |
|------|--------|---------|--------|------|----------|
| **Research** | papers scanned/week, techniques tested | 18 techniques | 30/week | 5-min Karpathy | — (Claude Code) |
| **Evaluation** | false positive rate, calibration | monitoring | FPR < 5% | 5-min Karpathy | — (VM) |
| **Strategy Design** | strategies tested, Sharpe ratio | 20 active | Sharpe > 1.5 | Trading Floor | — |

### Layer 2: STRATEGIC REALIZATION (Muscle)

| Dept | Metric | Current | Target | Loop | HF Space |
|------|--------|---------|--------|------|----------|
| **Product & Testing** | Brier score, feature count | 0.21570 | < 0.20 | GA Evolution | S10-S15 |
| **Business/Pricing** | MRR, conversion rate | $0 (pre-launch) | $10K MRR | — | — |
| **Communication** | followers, engagement, posts/week | pre-launch | 1K followers | — | — |

### Layer 3: LOGISTICS & INTENDANCE (Foundation)

| Dept | Metric | Current | Target | Loop | HF Space |
|------|--------|---------|--------|------|----------|
| **Infrastructure** | uptime %, restart count | 99%+ | 99.9% | 5-min Karpathy | S10-S15, P1-P4 |
| **Finance/Accounting** | revenue, costs, margin | Stripe: NOT CONNECTED | Break-even | — | — |
| **Admin/Legal** | compliance, ToS, privacy policy | NOT STARTED | Complete | — | — |

---

## HF SPACE AUDIT (4 accounts, 8 max per account)

### Account: Nomos42 (HF_TOKEN_3) — MAIN PRODUCTION (14 spaces → 8 after cleanup)
| Space | Role | Status | Action |
|-------|------|--------|--------|
| Nomos42/nba-quant (S10) | NBA exploitation | ACTIVE | KEEP |
| Nomos42/nba-quant-2 (S11) | NBA exploration | ACTIVE | KEEP |
| Nomos42/nba-evo-3 (S12) | Extra-trees specialist | ACTIVE | KEEP |
| Nomos42/nba-evo-4 (S13) | CatBoost specialist | ACTIVE | KEEP |
| Nomos42/nba-evo-5 (S14) | LightGBM specialist | ACTIVE | KEEP |
| Nomos42/nba-evo-6 (S15) | Wide search | ACTIVE | KEEP |
| Nomos42/political-alpha (P1) | Political exploitation | ACTIVE | KEEP |
| Nomos42/political-alpha-2 (P2) | Political exploration | ACTIVE | KEEP |
| Nomos42/political-alpha-3 (P3) | Political CatBoost | ACTIVE | **DELETE** → move to LBJLincoln |
| Nomos42/political-alpha-4 (P4) | Political wide | ACTIVE | **DELETE** → move to LBJLincoln |
| Nomos42/nomos42-infra-brain | Dead infra brain | DEAD | **DELETE** |
| Nomos42/nomos42-paperclip | Dead paperclip | DEAD | **DELETE** |
| Nomos42/nomos42-brain | Dead brain | DEAD | **DELETE** |
| Nomos42/karpathy-arena | Dead arena | DEAD | **DELETE** |

### Account: LBJLincoln (HF_TOKEN) — PERSONAL (3 spaces → 0, then +4 planned)
| Space | Role | Status | Action |
|-------|------|--------|--------|
| LBJLincoln/betting-monitor | Old monitor | DEAD | **DELETE** |
| LBJLincoln/fleet-monitor | Old monitor | DEAD | **DELETE** |
| LBJLincoln/island-coordinator | Old coordinator | DEAD | **DELETE** |
**Planned:** P3 (political CatBoost), P4 (political wide), RGWA gen-1, RGWA gen-2 → 4/8

### Account: LBJLincoln26 (HF_TOKEN_2) — SECONDARY (4 spaces → 0, then +2 planned)
| Space | Role | Status | Action |
|-------|------|--------|--------|
| LBJLincoln26/research-radar | Old monitor | DEAD | **DELETE** |
| LBJLincoln26/quality-tracker | Old monitor | DEAD | **DELETE** |
| LBJLincoln26/predictions-monitor | Old monitor | DEAD | **DELETE** |
| LBJLincoln26/political-monitor | Old monitor | DEAD | **DELETE** |
**Planned:** experimental overflow → 2/8

### Allocation Plan (after cleanup)
- **Nomos42**: 6 NBA (S10-S15) + 2 Political (P1-P2) = **8/8** ✅
- **LBJLincoln**: 2 Political (P3-P4) + 2 RGWA = **4/8**
- **LBJLincoln26**: 2 experimental = **2/8**
- **Total:** 13 deletions needed, 14 spaces target across 3 accounts
- **Capacity remaining:** 10 free slots

---

## GPU BURST RESOURCES (10-30 min MAX per session)

| Resource | GPU | Session Limit | Cost | Use Case | Status |
|----------|-----|---------------|------|----------|--------|
| **Google Colab** | T4 16GB | 30 min burst | Free / $10 Pro | TabICL training, feature search | CHECK CREDITS |
| **Kaggle** | P100 16GB | 30 min burst (of 9h weekly) | Free | Karpathy NBA loop, heavy eval | CHECK TOKEN |
| **Lightning AI** | T4/A10G | 22h total | Free tier | Evolution bursts | CHECK CREDITS |
| **Modal** | A10G/A100 | 10 min burst | $0.16/hr | Fast experiment validation | SETUP NEEDED |

### GPU Burst Pattern (Karpathy style)
```
1. Clone latest from GitHub (storage)
2. Load best config from HF Space (infra)
3. Run 10-30 min experiment burst
4. Measure metric (Brier, ROI, etc.)
5. If improved → push to GitHub + update HF Space
6. If not → discard, log failure
7. Shutdown GPU immediately
```

---

## INFRASTRUCTURE MAP

```
┌─────────────────────────────────────────────────────────┐
│                    mon-ipad (PILOT)                       │
│  ┌─────────────┐ ┌─────────────┐ ┌──────────────────┐   │
│  │ Guardian     │ │ Trading     │ │ Autonomous       │   │
│  │ Orchestrator │ │ Floor v5    │ │ Cycle (cron 4h)  │   │
│  └──────┬──────┘ └──────┬──────┘ └────────┬─────────┘   │
│         │               │                  │              │
│         ▼               ▼                  ▼              │
│  ┌──────────────────────────────────────────────────┐    │
│  │          9 Department Karpathy Loops              │    │
│  │  Research│Eng│Evo│Betting│Eval│Infra│Pol│Creative │    │
│  │  + Trading Floor (9th dept)                       │    │
│  └──────────────────────────────────────────────────┘    │
└───────────┬──────────────┬──────────────┬────────────────┘
            │              │              │
     ┌──────▼──────┐ ┌────▼─────┐ ┌──────▼──────┐
     │ nomos-nba   │ │ nomos-   │ │    rgwa     │
     │ -agent      │ │ political│ │             │
     │             │ │ -alpha   │ │             │
     │ prediction  │ │ signals  │ │ creative    │
     │ loop        │ │ loop     │ │ loop        │
     └──────┬──────┘ └────┬─────┘ └──────┬──────┘
            │              │              │
     ┌──────▼──────┐ ┌────▼─────┐ ┌──────▼──────┐
     │ HF Spaces   │ │ HF Spaces│ │ HF Spaces   │
     │ S10-S15     │ │ P1-P4    │ │ (to setup)  │
     │ (Nomos42)   │ │ (Nomos42)│ │ (LBJLincoln)│
     │ CPU/RAM 24/7│ │ CPU/RAM  │ │             │
     └─────────────┘ └──────────┘ └─────────────┘
            │              │              │
     ┌──────▼──────────────▼──────────────▼──────┐
     │          GPU BURSTS (10-30 min max)        │
     │  Colab T4 │ Kaggle P100 │ Lightning │Modal │
     │  On-demand for Karpathy autoresearch only  │
     └────────────────────────────────────────────┘
            │
     ┌──────▼──────────────────────────────────────┐
     │          GitHub (STORAGE / DRIVE)            │
     │  All repos synced, all results versioned     │
     │  GitHub = source of truth for code + data    │
     └─────────────────────────────────────────────┘
            │
     ┌──────▼──────────────────────────────────────┐
     │          nomos-dashboard (FRONTEND)          │
     │  Vercel auto-deploy from GitHub              │
     │  /arena = Trading Floor (main page)          │
     │  /nba /political /rgwa /terminal /knowledge  │
     └─────────────────────────────────────────────┘
```

---

## COMMUNICATION (Pre-drafted, awaiting your approval)

### Ready for Publishing
- [ ] `docs/social-media/launch-thread-twitter.md` — 10-tweet thread explaining Nomos42
- [ ] `docs/social-media/linkedin-post.md` — Professional announcement
- [ ] `docs/social-media/telegram-announcement.md` — @Nomos42 channel post

### Investor Deck (Draft)
- [ ] `docs/deck/nomos42-deck.md` — VC pitch deck outline
  - Pain: Insider trading advantages, market inefficiencies exploited by few
  - Solution: AI models that beat markets + democratize access
  - Product: NBA predictions (Brier 0.215 vs market 0.25), Political alpha
  - Traction: 6 HF islands, 994 backtested games, 5-AI competition
  - Business model: SaaS tiers ($19/$49/$149)
  - Market size: $100B+ sports betting + political prediction markets
  - Ask: Seed round for GPU infrastructure + team

### Platforms Status
| Platform | Account | Status | Action Needed |
|----------|---------|--------|---------------|
| Telegram | @Nomos42Bot, @Nomos42 | ACTIVE | Posts ready |
| X/Twitter | — | NO API KEY | You: provide API key |
| LinkedIn | — | NO API KEY | You: provide API key |
| TikTok | — | LATER | Video content pipeline |
| YouTube | — | LATER | Demo videos |
| Instagram | — | LATER | Visual content |

---

## FINANCE & ACCOUNTING

| Item | Status | Action |
|------|--------|--------|
| Stripe | NOT CONNECTED | You: connect at stripe.com |
| SaaS pricing | Defined ($19/$49/$149) | Ready when Stripe connected |
| Monthly costs | ~$20 (VM + domains) | Tracked |
| HF Spaces | Free tier (all 10) | $0 |
| GPU | Free tier (Colab/Kaggle) | $0, burst only |
| Vercel | Free tier | $0 |
| **Total monthly burn:** | **~$20** | Sustainable |

---

## KARPATHY AUTORESEARCH PATTERN (Official, per github.com/karpathy/autoresearch)

Each department follows the same loop:
```
1. Read program.md (research direction)
2. Modify code with proposed change
3. Run experiment (5 min fixed budget)
4. Measure metric (single number)
5. If improved → keep commit
6. If not → git reset --hard
7. Repeat (12 experiments/hour, ~100 overnight)
```

**Our adaptation:** Each department's Karpathy loop is in `scripts/departments/{dept}/{dept}-loop.sh`. The Guardian Orchestrator reads all outputs and cross-pollinates wins between departments. The Trading Floor runs the full-season backtest as its "experiment" with bankroll as the metric.

---

## DAILY RHYTHM

| Time (UTC) | What Happens | Automated? |
|------------|-------------|------------|
| :00 every 4h | Cloud Brain (Sonnet) analyzes + decides | YES (remote trigger) |
| :30 every 4h | VM Muscle executes (predictions, trading floor, sync) | YES (cron) |
| */30 | HF Space keepalive pings | YES (cron) |
| 12:00, 18:00 | NBA odds fetch | YES (cron) |
| On-demand | GPU bursts (Colab/Kaggle) | MANUAL trigger |
| Morning | You: read this doc, unblock manual items | MANUAL |

---

*This document is the single source of truth for daily operations. Updated automatically by the autonomous cycle. Manual items are clearly marked with checkboxes.*
