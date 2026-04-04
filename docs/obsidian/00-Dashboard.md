---
tags: [dashboard, live-status, nomos42, MOC]
date: 2026-04-04
aliases: [Dashboard, Live Status, Control Room, Home]
cssclasses: [wide-page]
---

# 00 — Live Dashboard

> Command center for the Nomos42 ecosystem. All metrics pulled from live JSON state files.
> Last data pull: 2026-04-04T09:18Z | Auto-updated by autonomous-cycle.sh

---

## System Health

```
SPACES    6/6 NBA + 2/2 POL  ████████████████ 100%   ALL RUNNING
KAGGLE    2/2 RUNNING        ████████████████ 100%   NBA + Political
MODAL     1/1 LAUNCHED       ████████████████ 100%   NBA burst
BOTS      2/2 UP             ████████████████ 100%   @Nomos42Bot + @RGWAbot
CRONS     36/36              ████████████████ 100%   All dept councils live
REPOS     5/5 ACTIVE         ████████████████ 100%   11 uncommitted (mon-ipad)
COUNCILS  12/12 LOADED       ████████████████ 100%   Guardian v3 active
SUPABASE  pooler xivvnr      ████████████████ ACTIVE (primary paused 402)
NEO4J     45 nodes           ████████████████ CONNECTED
DISK      73.4% used         ███████████░░░░░  73%   ~170-270 MB RAM free
```

---

## ATR Scoreboard

| # | Date | Brier | Model | Features | Platform |
|---|------|-------|-------|----------|----------|
| 1 | 2026-03-27 | **0.21570** | TabICL ensemble | 110 | Colab T4 |
| 2 | 2026-03-25 | 0.21844 | Extra Trees | 94 | Kaggle P100 |
| 3 | 2026-03-22 | 0.22041 | XGBoost | 194 | S10 |
| 4 | 2026-03-16 | 0.22471 | Logistic Regression | 24 | baseline |
| SOTA | 2026 | **0.199** | Montrucchio MDPI | -- | external |

> [!tip] Improvement rate
> -0.00901 in 11 days (+4.1% relative). Gap to SOTA: **0.0167**. Gap to target (<0.20): **0.0157**.

---

## HF Evolution Fleet (Live from agent-health.json)

| Island | Status | Brier | Gen | Model | Mut Rate | Role |
|--------|--------|-------|-----|-------|----------|------|
| S10 | RUNNING | 0.22454 | 419 | xgboost_brier | 0.09 | Exploitation |
| S11 | RUNNING | 0.22273 | 707 | xgboost | 0.15 | Exploration |
| S12 | RUNNING | 0.22506 | 932 | catboost | 0.08 | Extra Trees |
| S13 | RUNNING | 0.22455 | 652 | extra_trees | 0.10 | CatBoost |
| S14 | RUNNING | 0.22666 | 697 | xgboost_brier | 0.08 | LightGBM |
| **S15** | **RUNNING** | **0.22159** | **1042** | **random_forest** | **0.18** | **Wide Search** |

Fleet avg: **0.22419** | Fleet best: **0.22159** (S15) | Total gens: **4,449**

> [!info] Cross-pollination pending (Guardian v3)
> 1. Seed S10 with S14 config (gain +0.00545)
> 2. Seed S10 with S12 config (gain +0.00465)
> 3. Seed S11 with S14 config (gain +0.00433)

Full details: [[02-Evolution]] | GPU platforms: [[11-GPU-Compute]]

---

## Trading Floor -- Season 2025-26

### NBA Traders (Iter 402, Gen 54,672)

| Rank | Trader | Provider | Bankroll | ROI | Sharpe | Bets | Record |
|------|--------|----------|----------|-----|--------|------|--------|
| 1 | **Grok** | xAI | **$3,687.51** | **+3,587.5%** | **4.672** | 1,228 | 523W-705L |
| 2 | Gemini | Google | $1,731.08 | +1,631.1% | 2.660 | 3,554 | 1753W-1801L |
| 3 | Claude | Anthropic | $322.86 | +222.9% | 4.423 | 1,936 | 961W-975L |
| 4 | OpenRouter | Multi | $164.63 | +64.6% | 0.560 | 2,125 | 1036W-1089L |
| 5 | Codex | OpenAI | $0.63 | -99.4% | -0.268 | 4,232 | 2177W-2055L |

### Political Traders (12 trading days)

| Rank | Trader | Capital | ROI | Sharpe | Trades | Win Rate |
|------|--------|---------|-----|--------|--------|----------|
| 1 | Codex | $101,083 | +1.08% | 6.569 | 113 | 52.2% |
| 2 | Gemini | $100,790 | +0.79% | 12.289 | 118 | 61.0% |
| 3 | OpenRouter | $100,204 | +0.20% | 5.440 | 95 | 49.5% |
| 4 | Claude | $100,030 | +0.03% | 2.656 | 35 | 48.6% |
| 5 | Grok | $99,708 | -0.29% | -13.441 | 60 | 36.7% |

Full details: [[03-Trading-Floor]] | Strategies: [[07-Betting]]

---

## Live Bankroll (Real Agent)

| Metric | Value | Target |
|--------|-------|--------|
| Balance | $91.89 | growing |
| Start | $100.00 | -- |
| ROI | **-8.11%** | > +5% |
| Record | 16W-25L | -- |
| Win Rate | 39.02% | > 52% |
| Sharpe | -2.99 | > 1.5 |
| Peak | $110.43 | -- |
| Max DD | 16.79% | < 25% |

> [!warning] Root cause: corrupted odds (SAS normalization bug)
> 5 bets where model confidence >60% but market implied <15% = systematic losses. Fix pending in [[07-Betting]].

---

## Department Council Status (Live from council JSONs)

| Dept | Name | Status | Iter | Last Run | Key Metric |
|------|------|--------|------|----------|------------|
| D1 | Research | completed | 6 | 2026-04-04T09:02 | 18 scans, 0 new papers |
| D2 | Engineering | keep | 6 | 2026-04-04T09:12 | Brier 0.2157 stable |
| D3 | Evolution | keep | 8 | 2026-04-04T09:22 | 4,222 gens, 0 stagnant |
| D4 | Evaluation | keep | 5 | 2026-04-04T08:20 | ROI -8.11%, Sharpe -2.99 |
| D5 | Betting | completed | 1 | 2026-04-02 | full_kelly ELITE |
| D6 | Infra | keep | 5 | 2026-04-04T08:40 | 73.4% disk, ~211 MB RAM |
| D7 | Political | completed | 7 | 2026-04-02 | Kaggle RUNNING |
| D8 | Creative | idle | 4 | 2026-04-02 | 0 pieces |
| TF | Trading Floor | completed | 402 | 2026-04-04 | Gen 54,672 |

Full details: [[04-Departments]] | Guardian report: [[01-Architecture]]

---

## Active Alerts

> [!warning] CRITICAL
> 1. ROI -8.11% -- corrupted SAS odds bets causing systematic losses
> 2. ECE overconfidence 0.2758 -- worst bucket 60-70%, Platt scaling needed

> [!info] HIGH
> 3. RAM pressure: 170-211 MB free on 969 MB VM -- infra dept monitoring
> 4. Disk usage 73.4% and rising

> [!tip] MEDIUM
> 5. PHANTOM GAME: BKN vs BKN (home==away, prob 0.6128) -- fix proposed
> 6. nomos-political-alpha 364 uncommitted changes
> 7. nomos-nba-agent 18 uncommitted changes

---

## Quick Navigation

| Area | Notes |
|------|-------|
| **Architecture** | [[01-Architecture]] -- [[04-Departments]] -- [[12-Agent-Registry]] |
| **ML/Evolution** | [[02-Evolution]] -- [[06-Research]] -- [[16-Karpathy-Pattern]] |
| **Money** | [[03-Trading-Floor]] -- [[07-Betting]] -- [[15-Business-Plan]] |
| **Infra** | [[05-Infrastructure]] -- [[11-GPU-Compute]] -- [[13-Tools]] |
| **Projects** | [[17-Political-Alpha]] -- [[18-Creative-RGWA]] -- [[19-Cross-Repo]] |
| **Meta** | [[08-API-Vision]] -- [[09-Legal-Finance]] -- [[10-Repos]] |
| **Comms** | [[14-Communication]] -- [[20-Session-Log]] |
| **Vault** | [[README]] |
