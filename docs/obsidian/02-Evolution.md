---
tags: [evolution, HF-spaces, genetic-algorithm, brier, nomos42]
date: 2026-04-04
aliases: [Evolution, HF Islands, Genetic Algorithm, GA, Fleet]
---

# 02 -- Evolution (6 HF Islands)

> Fleet best: 0.22159 (S15) | ATR: 0.21570 (TabICL Colab) | Total gens: 4,449 | Last check: 2026-04-04T09:18Z

---

## Fleet Status (Live from infra-status.json)

| Island | URL | Status | Brier | Gen | Model | Mut Rate | Pareto |
|--------|-----|--------|-------|-----|-------|----------|--------|
| S10 | nomos42-nba-quant.hf.space | RUNNING | 0.22454 | 419 | xgboost_brier | 0.119 | 14 |
| S11 | nomos42-nba-quant-2.hf.space | RUNNING | 0.22273 | 707 | xgboost | 0.107 | 20 |
| S12 | nomos42-nba-evo-3.hf.space | RUNNING | 0.22506 | 932 | catboost | 0.058 | 14 |
| S13 | nomos42-nba-evo-4.hf.space | RUNNING | 0.22455 | 652 | extra_trees | 0.067 | 15 |
| S14 | nomos42-nba-evo-5.hf.space | RUNNING | 0.22666 | 697 | xgboost_brier | 0.108 | 10 |
| **S15** | nomos42-nba-evo-6.hf.space | **RUNNING** | **0.22159** | **1042** | **random_forest** | **0.130** | 14 |

> [!info] URL exception
> S11 URL = `nomos42-nba-quant-2.hf.space` (NOT nba-evo-2)

Fleet avg: **0.22419** | Fleet best: **0.22159** | Fleet worst: 0.22666 | Diversity: 0.567 | Stagnant: 0

---

## Island Roles & Strategy

| Island | Role | Base Mutation | Crossover | Pop Size | Features | Strategy |
|--------|------|---------------|-----------|----------|----------|---------|
| S10 | Exploitation | 0.09 -> adaptive (cap 0.15) | 0.80 | 30 | 63 | Exploit best known configs |
| S11 | Exploration | 0.15 -> adaptive | 0.70 | 30 | 80 | Wide random search |
| S12 | Extra Trees Specialist | 0.08 -> adaptive | 0.70 | 30 | 60 | Lock model=extra_trees |
| S13 | CatBoost Specialist | 0.10 -> adaptive | 0.70 | 30 | 66 | Lock model=catboost |
| S14 | LightGBM Specialist | 0.08 -> adaptive | 0.70 | 30 | 55 | Lock model=lightgbm |
| S15 | Wide Search | 0.18 -> adaptive | 0.70 | 50 | 80 | Large population diversity |

---

## All-Time Records (ATR)

| Rank | Date | Brier | Model | Features | Platform | Notes |
|------|------|-------|-------|----------|----------|-------|
| 1 | 2026-03-27 | **0.21570** | TabICL ensemble | 110 | Colab T4 | iter 15, CURRENT ATR |
| 2 | 2026-03-25 | 0.21844 | Extra Trees | 94 | Kaggle P100 | gen52 |
| 3 | 2026-03-22 | 0.22041 | XGBoost | 194 | S10 | MOVDA-era |
| 4 | 2026-03-16 | 0.22471 | Logistic Regression | 24 | baseline | launch day |

> [!tip] SOTA reference
> **Montrucchio 2026** (MDPI Information 17/1/56) achieved Brier **0.199**. Gap to close: **0.0167**.

---

## Feature Engine

| Property | Value |
|----------|-------|
| Version | v3.1-46cat |
| Categories | 46 (+Cat47 Drive-Rim, +Cat48 Passing, +Cat49 Play-Type PPP) |
| Raw features | 6,253 |
| Usable features | 3,216 |
| Max selected | 200 (hard cap) |
| Engine parity | `features/engine.py` == `hf-space/features/engine.py` |
| ATR config | 110 features from v3.0-37cat (TabICL build) |

Feature categories include: EWMA rolling stats (Cat36), MOVDA moving avg decay (Cat37), ELO ratings, Poisson model, Monte Carlo, Drive-Rim (Cat47), Passing efficiency (Cat48), Play-Type PPP (Cat49).

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

## Cross-Pollination (Guardian v3)

Guardian has identified 3 cross-pollination opportunities:

| Action | Source | Target | Brier Gain | Priority |
|--------|--------|--------|------------|----------|
| Seed S10 with S14 config | S14 (0.22666) | S10 (0.22454) | +0.00545 | MEDIUM |
| Seed S10 with S12 config | S12 (0.22506) | S10 (0.22454) | +0.00465 | MEDIUM |
| Seed S11 with S14 config | S14 (0.22666) | S11 (0.22273) | +0.00433 | MEDIUM |

Script: `scripts/agents/cross-pollinate.py` (runs Sundays 04:00)

---

## Model Performance (Production Ensemble)

| Model | Brier | Weight | Status |
|-------|-------|--------|--------|
| TabICL ensemble | 0.2157 | 0.30 | ATR_BEST |
| CatBoost | 0.22041 | 0.20 | ACTIVE |
| XGBoost | 0.22050 | 0.18 | ACTIVE |
| LightGBM | 0.22080 | 0.16 | ACTIVE |
| Extra Trees | 0.22250 | 0.10 | ACTIVE |
| Random Forest | 0.22447 | 0.06 | ACTIVE |

---

## Political Evolution (Bonus Spaces)

| Space | Status | Brier | Gen |
|-------|--------|-------|-----|
| P1_pol | RUNNING | 0.24997 | 326 |
| P2_pol | RUNNING | 0.23134 | 6,030 |

Details: [[17-Political-Alpha]]

---

## Walk-Forward Validation

| Platform | Metric | Value | Period |
|----------|--------|-------|--------|
| Kaggle P100 | Walk-forward avg | 0.22447 | 19 weeks, 934 games |
| Colab T4 | Best Brier | 0.21570 | iter 15 |
| Colab T4 | Iterations | 318 iter/2h50 | GPU mode |
| Kaggle | Loop rate | 12 iter/hr, ~100/session | 9h sessions |

---

## Links

[[00-Dashboard]] | [[01-Architecture]] | [[04-Departments]] | [[06-Research]] | [[11-GPU-Compute]] | [[16-Karpathy-Pattern]]
