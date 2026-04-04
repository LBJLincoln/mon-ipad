---
tags: [vault-index, MOC, nomos42]
date: 2026-04-03
aliases: [Vault Index, MOC]
---

# Nomos42 — Knowledge Vault

> Cross-repo piloting dashboard | Forge v19 | Updated: 2026-04-03

## Map of Content

This vault is the single source of truth for the Nomos42 NBA Quant AI ecosystem. Navigate using [[wikilinks]] or the index below.

---

## Core Notes

| Note | Purpose | Status |
|------|---------|--------|
| [[00-Dashboard]] | Live system overview | ACTIVE |
| [[01-Architecture]] | Forge v19, 3 layers, 8 depts | STABLE |
| [[02-Evolution]] | 6 HF islands, GA, Brier scores | RUNNING |
| [[03-Trading-Floor]] | 5 AI traders, P&L, strategies | RUNNING |
| [[04-Departments]] | All 8 dept Karpathy loops | RUNNING |
| [[05-Infrastructure]] | VM + HF + GPU + crons | STABLE |
| [[06-Research]] | SOTA papers, 18 techniques | ACTIVE |
| [[07-Betting]] | Bankroll, Kelly, categories | ACTIVE |
| [[08-API-Vision]] | API marketplace, agent sales | PLANNED |
| [[09-Legal-Finance]] | Holding, BPI deeptech, greffe | PLANNED |
| [[10-Repos]] | All 8 repos with descriptions | STABLE |

---

## Quick Numbers (2026-04-03)

| Metric | Value | Target |
|--------|-------|--------|
| Best Brier (ATR) | **0.21570** (TabICL, Colab) | < 0.20 |
| Fleet avg Brier | 0.22419 (6 islands) | < 0.22 |
| Fleet best Brier | 0.22159 (S15) | < 0.22 |
| SOTA reference | 0.199 (Montrucchio 2026) | beat it |
| Bankroll | $91.89 / $100 start | +ROI |
| ROI | -8.11% (41 bets) | > +5% |
| Sharpe | -2.99 | > 1.5 |
| Win rate | 39.02% | > 52% |
| Spaces up | 6/6 | 6/6 |
| Kaggle | ERROR (timeout) | RUNNING |

---

## Critical Alerts

- Kaggle kernels timeout (3 errored) — see [[05-Infrastructure]]
- ROI -8.11% — corrupted odds bets (SAS bug) — see [[07-Betting]]
- ECE overconfidence 0.2758 — Platt scaling needed — see [[04-Departments#Evaluation]]
- 4 missing crons (keepalive-spaces, nba-daily-odds, autonomous-cycle, cross-repo-optimize)

---

## Vault Navigation

- Start here for status: [[00-Dashboard]]
- Dive into ML: [[02-Evolution]] → [[06-Research]]
- Follow the money: [[07-Betting]] → [[03-Trading-Floor]]
- System health: [[05-Infrastructure]] → [[04-Departments]]
- Big picture: [[01-Architecture]] → [[08-API-Vision]] → [[09-Legal-Finance]]
- All repos: [[10-Repos]]
