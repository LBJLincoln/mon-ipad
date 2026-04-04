---
tags: [departments, karpathy-loop, councils, forge-v19, nomos42]
date: 2026-04-03
aliases: [Departments, Councils, Forge Departments, Karpathy Loops]
---

# 04 — Departments (8 Karpathy Loops)

> Forge v19 | Guardian Orchestrator v3 | All depts: SCAN → PROPOSE → EXECUTE → EVALUATE → KEEP/REVERT

## Department Status Overview

| Dept | Name | Status | Iter | Last Run | Cron |
|------|------|--------|------|----------|------|
| D1 | Research | completed | 9 | 2026-04-02 | `2 * * * *` |
| D2 | Engineering | unknown | 7 | 2026-04-02 | `12 * * * *` |
| D3 | Evolution | completed | 1 | 2026-04-02 | `22 * * * *` |
| D4 | Evaluation | completed | 2 | 2026-04-01 | `20 */2 * * *` |
| D5 | Betting | completed | 1 | 2026-04-02 | `10 */2 * * *` |
| D6 | Infra | completed | 1 | 2026-04-02 | `40 */2 * * *` |
| D7 | Political | completed | 7 | 2026-04-02 | `0 8,20 * * *` |
| D8 | Creative | idle | 4 | 2026-04-02 | `0 9,21 * * *` |
| D9 | Comms | — | — | — | `0 7 * * *` |
| D10 | Business | — | — | — | `0 8 * * *` |
| D11 | Finance | — | — | — | `0 23 * * *` |
| TF | Trading Floor | completed | 287 | 2026-04-03 | `0 11 * * *` |

Council state files: `data/departments/council-<dept>.json`
Runner: `scripts/councils/department-council.sh <dept>`

---

## D1 — Research

**Karpathy loop:** paper → extract → propose → measure
**Metric:** papers/week, techniques tested
**Current state:** 9 iterations, 14 papers scanned, 18 techniques extracted

Key metrics:
- Papers scanned: 14
- Techniques extracted: 18
- SOTA reference: Montrucchio 2026 (MDPI Information 17/1/56) — Brier 0.199
- Gap to close: 0.0157

Latest proposals (from scan): Platt scaling, isotonic regression, ensemble stacking, drive-rim features, play-type PPP

→ Full roadmap: [[06-Research]]

---

## D2 — Engineering

**Karpathy loop:** code → test → measure Brier → keep/revert
**Metric:** Brier delta, test pass rate
**Current state:** 7 iterations | Status: UNKNOWN (needs investigation)

Pending engineering tasks (from Evaluation dept):
1. **Phantom game guard** (home != away assertion) — trivial effort
2. **Platt scaling calibration** — expected Brier delta: -0.008, ECE delta: -0.17
3. **Odds sanity gate** (reject |model_prob - market_implied| > 0.50) — small effort
4. **Home court advantage reduction** 2.8 → 2.2 pts — expected Brier delta: -0.002

---

## D3 — Evolution

**Karpathy loop:** mutate → eval → measure fitness → select
**Metric:** gen/hr, best Brier, diversity
**Current state:** 2 iterations | fleet diversity: 0.567

Best Brier: 0.22159 (S15) | Fleet avg: 0.22419 | Total gens: 652+
Cross-pollination pending: 3 actions (see [[02-Evolution]])

---

## D4 — Evaluation (Critical Active Dept)

**Karpathy loop:** audit → identify → fix → verify
**Metric:** false positive rate, calibration
**Current state:** 2 iterations

### Biases Detected

| Type | Severity | Detail | Fix |
|------|----------|--------|-----|
| PHANTOM_GAME | CRITICAL | BKN vs BKN (home==away), prob 0.6128 | Assert home != away |
| OVERCONFIDENCE | HIGH | ECE 0.2758, worst bucket 60-70% | Platt scaling |
| CORRUPTED_ODDS | HIGH | 5 bets, model >60% but market <15% (SAS bug) | Odds sanity gate |
| HOME_BIAS | LOW | 21 home bets, 38.1% WR vs 40% away | Reduce home_court_advantage |

### Corruption Examples (SAS normalization bug)
- 2026-03-21: IND @ SAS — model 68.3%, market 9.1%, edge 6.5x — LOST
- 2026-03-25: SAS @ MEM — model 67.9%, market 10.3%, edge 5.6x — LOST
- 2026-03-27: HOU @ MEM — model 60.7%, market 13.8%, edge 3.4x — LOST

### Improvements Proposed
1. Phantom game guard (priority 1, trivial, 0 Brier delta)
2. Platt scaling (priority 2, medium, -0.008 Brier, -0.17 ECE)
3. Odds sanity gate (priority 3, small, +eliminates 8 bad bets)
4. Home court 2.8→2.2pts (priority 4, small, -0.002 Brier)
5. Automated ECE alert >0.15 (priority 5, small, monitoring)

---

## D5 — Betting

**Karpathy loop:** strategy → backtest → measure ROI → keep/revert
**Metric:** ROI, Sharpe, Kelly edge

Strategy rankings (backtest):
1. full_kelly: +135,550% avg ROI (ELITE)
2. anti_martingale: +125,583% (ELITE)
3. proportional_edge: +73,112% (STRONG)
4. half_kelly: +34,739% (STRONG)

Calibration config:
- Kelly fraction: 0.35
- Min edge: 0.03 (3%)
- ELO K-factor: 22
- Home court advantage: 2.8 pts (target: reduce to 2.2)

→ Full betting details: [[07-Betting]]

---

## D6 — Infra

**Karpathy loop:** check → detect → fix → verify
**Metric:** uptime %, restart count
**Current state:** uptime 88% | 35 crons total | 4 missing

Missing crons (critical):
- keepalive-spaces
- nba-daily-odds
- autonomous-cycle
- cross-repo-optimize

→ Full infra details: [[05-Infrastructure]]

---

## D7 — Political

**Karpathy loop:** signal → feature → measure alpha → keep/revert
**Metric:** political Brier, ETF ROI

Political Alpha v3.1:
- Categories: 22
- Features: 743
- Spaces: P1_pol (Brier 0.24186, gen 8871) + P2_pol (Brier 0.23134, gen 4104)

Signal sources:
- Congressional trades (insider signals)
- FEC donor data
- Social signals
- Crypto prices as sentiment proxy
- Fetch cadence: fast (*/30), full (*/6h), insider (22:00 weekdays), prices (22:30 weekdays)

---

## D8 — Creative (RGWA)

**Karpathy loop:** generate → quality → curate → publish
**Metric:** quality score, output/day
**Current state:** idle (4 iterations) | rgwa_creative status: WARNING

Bot: @RGWAbot | Repo: rgwa | Last commit: 2026-04-01

---

## Guardian Orchestrator v3

Guardian analyzes ALL depts, surfaces wins, allocates resources.

Last run: 2026-04-03T21:28:07Z
Departments loaded: 12/12
Active routes: 1 (evolution → evolution cross-pollination)
Wins this cycle: 0
Pending actions: 3 (MEDIUM priority)

---

## Links

[[README]] | [[00-Dashboard]] | [[01-Architecture]] | [[02-Evolution]] | [[05-Infrastructure]] | [[06-Research]] | [[07-Betting]]
