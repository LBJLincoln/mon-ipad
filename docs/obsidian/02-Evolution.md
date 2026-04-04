---
tags: [evolution, HF-spaces, genetic-algorithm, brier, nomos42]
date: 2026-04-03
aliases: [Evolution, HF Islands, Genetic Algorithm, GA]
---

# 02 — Evolution (6 HF Islands)

> Fleet best: 0.22159 (S15) | ATR: 0.21570 (TabICL Colab) | Last check: 2026-04-03T23:47Z

## Fleet Status

| Island | URL | Status | Brier | Gen | Cycle | Model | Mut Rate | Pareto |
|--------|-----|--------|-------|-----|-------|-------|----------|--------|
| S10 | nomos42-nba-quant.hf.space | RUNNING | 0.22454 | 207 | 34 | xgboost_brier | 0.119 | 14 |
| S11 | nomos42-nba-quant-2.hf.space | RUNNING | 0.22273 | 284 | 41 | xgboost | 0.107 | 20 |
| S12 | nomos42-nba-evo-3.hf.space | RUNNING | 0.22506 | 576 | 134 | catboost | 0.058 | 14 |
| S13 | nomos42-nba-evo-4.hf.space | RUNNING | 0.22455 | 374 | 92 | extra_trees | 0.067 | 15 |
| S14 | nomos42-nba-evo-5.hf.space | RUNNING | 0.22666 | 443 | 117 | xgboost_brier | 0.108 | 10 |
| **S15** | nomos42-nba-evo-6.hf.space | **RUNNING** | **0.22159** | 464 | 104 | random_forest | 0.130 | 14 |

Note: S11 URL = nomos42-nba-quant-2.hf.space (NOT nba-evo-2)

Fleet avg: **0.22419** | Fleet best: **0.22159** | Fleet worst: 0.22666 | Diversity score: 0.567

---

## Island Roles & Strategy

| Island | Role | Mutation | Strategy |
|--------|------|----------|---------|
| S10 | Exploitation | 0.09 → adaptive (cap 0.15) | Exploit best known configs (cx=0.80, feat=63) |
| S11 | Exploration | 0.15 → adaptive | Wide random search (feat=80) |
| S12 | Extra Trees Specialist | 0.08 → adaptive | Lock model=extra_trees (feat=60) |
| S13 | CatBoost Specialist | 0.10 → adaptive | Lock model=catboost (feat=66) |
| S14 | LightGBM Specialist | 0.08 → adaptive | Lock model=lightgbm (feat=55) |
| S15 | Wide Search | 0.18 → adaptive | Pop=50, wide feat space (feat=80) |

---

## All-Time Records (ATR)

| Rank | Date | Brier | Model | Features | Platform | Notes |
|------|------|-------|-------|----------|----------|-------|
| 1 | 2026-03-27 | **0.21570** | TabICL ensemble | 110 | Colab T4 | iter15 |
| 2 | 2026-03-25 | 0.21844 | Extra Trees | 94 | Kaggle P100 | gen52 |
| 3 | 2026-03-22 | 0.22041 | XGBoost | 194 | S10 | MOVDA-era |
| 4 | 2026-03-16 | 0.22471 | Logistic Regression | 24 | baseline | launch |

SOTA reference: **0.199** (Montrucchio 2026, MDPI Information 17/1/56)
Gap to close: **0.0157**

---

## Feature Engine

| Property | Value |
|----------|-------|
| Version | v3.1-46cat |
| Categories | 46 (+ Cat47 Drive-Rim, Cat48 Passing, Cat49 Play-Type PPP) |
| Raw features | 6,253 |
| Usable features | 3,216 |
| Max selected | 200 (hard cap) |
| Engine parity | `features/engine.py` == `hf-space/features/engine.py` |

Feature categories include: EWMA rolling stats, MOVDA (moving avg decay), ELO ratings, Poisson model, Monte Carlo, Drive-Rim (Cat47), Passing efficiency (Cat48), Play-Type PPP (Cat49).

Current best configuration: 110 features from v3.0-37cat (TabICL ATR build)

---

## GA Parameters

| Parameter | S10 | S11 | S12-S14 | S15 |
|-----------|-----|-----|---------|-----|
| Pop size | 30 | 30 | 30 | 50 |
| Crossover | 0.80 | 0.70 | 0.70 | 0.70 |
| Mutation | adaptive | adaptive | adaptive | adaptive |
| Mutation cap | 0.15 | 0.15 | 0.15 | 0.15 |
| Feature cap | 200 | 200 | 200 | 200 |
| Elitism | yes | yes | yes | yes |

---

## Cross-Pollination (Guardian v3 Pending Actions)

Guardian has identified 3 cross-pollination opportunities:

| Action | Source | Target | Brier Gain | Priority |
|--------|--------|--------|------------|----------|
| Seed S10 with S14 config | S14 (0.22666) | S10 (0.22454) | +0.00545 | MEDIUM |
| Seed S10 with S12 config | S12 (0.22506) | S10 (0.22454) | +0.00465 | MEDIUM |
| Seed S11 with S14 config | S14 (0.22666) | S11 (0.22273) | +0.00433 | MEDIUM |

Cross-pollination script: `scripts/agents/cross-pollinate.py` (runs Sundays 04:00)

---

## GPU Burst Platforms

| Platform | Status | Notes |
|----------|--------|-------|
| Colab T4 | not_running | Best results here — TabICL ATR 0.21570 |
| Kaggle P100 | ERROR (timeout) | 9h sessions, was gen52 best |
| Lightning AI | available | 22hr sessions, credentials in memory |
| Vast.ai | available | $0.16/hr |

Kaggle loop rate: 12 iter/hr, ~100/session
Colab TabICL: 318 iter/2h50 (GPU mode)

Walk-forward avg on Kaggle: **0.22447** (19 weeks, 934 games, tree ensemble)

---

## Political Evolution (Bonus Spaces)

| Space | Status | Brier | Gen |
|-------|--------|-------|-----|
| P1_pol | running | 0.24186 | 8871 |
| P2_pol | running | 0.23134 | 4104 |

→ Political details: [[04-Departments#Political]]

---

## Links

[[README]] | [[00-Dashboard]] | [[01-Architecture]] | [[04-Departments]] | [[06-Research]] | [[05-Infrastructure]]
