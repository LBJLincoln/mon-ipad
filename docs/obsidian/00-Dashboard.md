---
tags: [dashboard, live-status, nomos42]
date: 2026-04-03
aliases: [Dashboard, Live Status, Control Room]
---

# 00 — Live Dashboard

> Last data pull: 2026-04-04T07:55Z | Auto-updated by autonomous-cycle.sh

## System Health

```
SPACES    6/6 UP   ████████████ 100%
KAGGLE    2/3 OK   ████████░░░░  67%  (political v24 restarted)
BOTS      2/2 UP   ████████████ 100%
CRONS     36/36    ████████████ 100%  (D9 cross-repo added)
REPOS     5/5 UP   ████████████ 100%
COUNCILS  9/9 LIVE ████████████ 100%  (all 9 depts active)
SUPABASE  249K evals █████████████ ACTIVE
NEO4J     45 nodes  ████████████ CONNECTED
```

---

## ATR Scoreboard

| # | Date | Brier | Model | Features | Platform |
|---|------|-------|-------|----------|----------|
| 1 | 2026-03-27 | **0.21570** | TabICL ensemble | 110 | Colab T4 |
| 2 | 2026-03-25 | 0.21844 | Extra Trees | 94 | Kaggle gen52 |
| 3 | 2026-03-22 | 0.22041 | XGBoost | 194 | S10 |
| 4 | 2026-03-16 | 0.22471 | Logistic Regression | 24 | baseline |
| SOTA | 2026 | 0.199 | Montrucchio MDPI | — | external |

**Gap to close: 0.0157** (Brier, vs SOTA)
**Gap to target: 0.0157** (< 0.20)

---

## HF Evolution Fleet

| Island | Status | Brier | Gen | Model | Mut Rate |
|--------|--------|-------|-----|-------|----------|
| S10 | RUNNING | 0.22454 | 373 | tree_ensemble | 0.09 |
| S11 | RUNNING | 0.22273 | 599 | tree_ensemble | 0.15 |
| S12 | RUNNING | 0.22506 | 861 | extra_trees | 0.08 |
| S13 | RUNNING | 0.22455 | 586 | catboost | 0.10 |
| S14 | RUNNING | 0.22666 | 638 | lightgbm | 0.08 |
| **S15** | **RUNNING** | **0.22159** | 924 | tree_ensemble | 0.18 |

Fleet avg: **0.22402** | Fleet best: **0.22159** (S15)

Cross-pollination pending: S14 → S10 (gain +0.00545), S12 → S10 (gain +0.00465)

→ Full details: [[02-Evolution]]

---

## Trading Floor — Season 2025-26

| Rank | Trader | Bankroll | ROI | Sharpe | Provider |
|------|--------|----------|-----|--------|----------|
| 1 | **Grok** | $3,687.51 | +3,587.5% | 4.672 | xAI |
| 2 | Gemini | $1,731.08 | +1,631.1% | 2.660 | Google |
| 3 | Claude | $322.86 | +222.9% | 4.423 | Anthropic |
| 4 | OpenRouter | $164.63 | +64.6% | 0.560 | Multi |
| 5 | Codex | $0.63 | -99.4% | -0.268 | OpenAI |

→ Full details: [[03-Trading-Floor]]

---

## Bankroll (Live Agent)

| Metric | Value |
|--------|-------|
| Balance | $91.89 |
| Start | $100.00 |
| ROI | -8.11% |
| Record | 16W-25L |
| Win Rate | 39.02% |
| Peak | $110.43 |
| Max DD | 16.79% |
| Sharpe | -2.99 |

**Root cause:** corrupted odds bets (SAS team normalization bug) — fix pending in [[07-Betting]]

---

## Department Council Status

| Dept | Status | Iter | Last Run |
|------|--------|------|----------|
| Research | completed | 9 | 2026-04-02 |
| Engineering | unknown | 7 | 2026-04-02 |
| Evolution | completed | 1 | 2026-04-02 |
| Betting | completed | 1 | 2026-04-02 |
| Evaluation | completed | 2 | 2026-04-01 |
| Infra | completed | 1 | 2026-04-02 |
| Political | completed | 7 | 2026-04-02 |
| Creative | idle | 4 | 2026-04-02 |
| Trading Floor | completed | 287 | 2026-04-03 |

→ Full details: [[04-Departments]]

---

## Active Alerts

1. **CRITICAL** — Kaggle nba-karpathy-loop ERRORED (timeout after 15s)
2. **CRITICAL** — Kaggle nba-season-backtest ERRORED
3. **HIGH** — ECE overconfidence 0.2758 (worst bucket: 60-70%)
4. **HIGH** — Corrupted odds (5 bets, SAS normalization mismatch)
5. **MEDIUM** — PHANTOM GAME: BKN vs BKN (home==away, prob 0.6128)
6. **MEDIUM** — 4 missing crons (keepalive-spaces, nba-daily-odds, autonomous-cycle, cross-repo-optimize)
7. **LOW** — nomos-political-alpha 277 uncommitted changes

---

## Links

[[README]] | [[01-Architecture]] | [[02-Evolution]] | [[03-Trading-Floor]] | [[04-Departments]] | [[05-Infrastructure]] | [[06-Research]] | [[07-Betting]]
