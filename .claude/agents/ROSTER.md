# Nomos42 Agent Roster — v3 "The Trading Floor Crew" (2026-04-18)

**Principle:** one agent, one domain, one repo, one cred set, one cron slot.
No overlap. Every agent knows exactly which HF account / API key to use.
THE BOSS dispatches — never duplicates.

**Commit protocol (MANDATORY for every crew member):**
All autonomous commits MUST shell through `scripts/lib/safe_commit.sh <CODENAME> "<msg>" [paths...]`
(flock on `/tmp/nomos-git.lock`, pull --rebase --autostash, 3× push retry, `[AGENT]` prefix).
Naked `git add / commit / push` is banned — with 14 agents on staggered crons the race-reject
rate was unacceptable. See `project_git_mutex_apr19` memory + `scripts/lib/safe_commit.sh`.

## The Crew — 14 Agents × 9 Departments × 4 Tracks

| # | Codename | Old Name | Dept | Track | What they do |
|---|----------|----------|------|-------|-------------|
| 1 | **THE BOSS** | nomos-brain | ALL | ALL | Floor manager — dispatches all 13 agents |
| 2 | **SWISH** | nomos-hoops | D3 Evolution | T1 SCIENCE | NBA islands S10-S22 |
| 3 | **LOBBYIST** | nomos-alpha | D3 Evolution | T1 SCIENCE | Political islands P1-P8 |
| 4 | **HAWKEYE** | nomos-scout | D1 Research | T1 SCIENCE | Daily arXiv/GitHub/web recon |
| 5 | **DR FRANKENSTEIN** | nomos-lab | D1 Research | T1 SCIENCE | Implement research → engine.py |
| 6 | **THE BLACKSMITH** | nomos-forge | D2 Engineering | T2 PLATFORM | Department council Karpathy loops |
| 7 | **SWITCHBOARD** | nomos-llm | D7 Infra | T2 PLATFORM | LLM gateway + TF + pixel keepalive |
| 8 | **INTERNAL AFFAIRS** | nomos-audit | D6 Evaluation | T1 SCIENCE | Scientific integrity watchdog |
| 9 | **THE TICKER** | nomos-tape | D8 Finance | T4 CAPITAL | Live odds scanner, CLV, steam moves |
| 10 | **THE HERALD** | nomos-wire | D4 Product | T3 MARKET | Telegram publisher + paywall |
| 11 | **THE ACCOUNTANT** | nomos-pay | D5 Business | T3 MARKET | Stripe/Whop/LS revenue pipeline |
| 12 | **PIXEL** | — (new) | D4 Product | T3 MARKET | Dashboard + /world visual QA |
| 13 | **THE PLUMBER** | — (new) | D7 Infra | T2 PLATFORM | Data pipeline + ETL health |
| 14 | **LAUNCHPAD** | — (new) | D9 Cross-repo | T2 PLATFORM | CI/CD + deploy orchestration |

## Department → Agent Mapping

| Dept | Name | Agents | Mission |
|------|------|--------|---------|
| D1 | RESEARCH | HAWKEYE, DR FRANKENSTEIN | Find + implement SOTA techniques |
| D2 | ENGINEERING | THE BLACKSMITH | Karpathy loops on 8 councils |
| D3 | EVOLUTION | SWISH, LOBBYIST | NBA + Political island management |
| D4 | PRODUCT | THE HERALD, PIXEL | Publish picks + visual QA |
| D5 | BUSINESS | THE ACCOUNTANT | Revenue pipeline + May 1 deadline |
| D6 | EVALUATION | INTERNAL AFFAIRS | Scientific integrity, audit |
| D7 | INFRA | SWITCHBOARD, THE PLUMBER | LLM keepalive + data pipeline health |
| D8 | FINANCE | THE TICKER | Live odds, CLV, steam detection |
| D9 | CROSS-REPO | LAUNCHPAD | CI/CD, deploy sync, cross-repo parity |

## Track → Agent Mapping

| Track | Agents | Focus |
|-------|--------|-------|
| T1 SCIENCE | SWISH, LOBBYIST, HAWKEYE, DR FRANKENSTEIN, INTERNAL AFFAIRS | Brier floor, calibration, mutation, research |
| T2 PLATFORM | THE BLACKSMITH, SWITCHBOARD, THE PLUMBER, LAUNCHPAD | Code parity, deploys, uptime, data pipelines |
| T3 MARKET | THE HERALD, THE ACCOUNTANT, PIXEL | Dashboard, Telegram, subs, pricing, visual QA |
| T4 CAPITAL | THE TICKER | Odds, CLV, TF bankrolls, Kelly sizing |

## Account Layout (4 HF accounts × ≤8 Spaces = 32 slots)

| Account | Token env | Agent(s) | Spaces |
|---------|-----------|----------|--------|
| **LBJLincoln26** | `HF_TOKEN_NBA` | SWISH | S16 S17 S20 S21 + nba-llm-trading-floor |
| **LBJLincoln** | `HF_TOKEN` | LOBBYIST | P1 P2 P3 P4 P5 P6 P7 P8 |
| **Nomos42** | `HF_TOKEN_LLM` | SWITCHBOARD, PIXEL | llm-gateway, gemma4-chat, qwen35-chat, cpu-gemma4, pixel-world, langfuse |
| **TESTforge42** | `HF_TOKEN_COUNCILS` | THE BLACKSMITH | D1 D2 D3 D4 D5 D6 D7 D8, S18 S19 S22 |

## Cron Schedule (v3)

```
*/30      THE TICKER           (every 30 min — game windows)
:00 */4h  THE BOSS             (dispatcher)
:10 */4h  SWISH                (NBA islands)
:15 */4h  LOBBYIST             (Political islands)
:25 */4h  THE BLACKSMITH       (council loops)
:35 */4h  THE PLUMBER          (data pipeline health)
:40 */4h  INTERNAL AFFAIRS     (TF audit)
:20 */6h  SWITCHBOARD          (LLM/TF keepalive)
:45 */6h  LAUNCHPAD            (CI/CD health)
:00 */12h DR FRANKENSTEIN      (engine feature impl)
06:00     HAWKEYE              (daily recon)
09:00     THE ACCOUNTANT       (revenue sync)
18:00     THE HERALD           (publish picks)
on-demand PIXEL                (visual QA after deploys)
```

## Retired agents (migrated 2026-04-18)

| Old Name | → New Codename | Notes |
|----------|---------------|-------|
| nomos-brain | THE BOSS | Same role, expanded crew list |
| nomos-hoops | SWISH | Same scope |
| nomos-alpha | LOBBYIST | Same scope |
| nomos-scout | HAWKEYE | Same scope |
| nomos-lab | DR FRANKENSTEIN | Same scope |
| nomos-forge | THE BLACKSMITH | Same scope |
| nomos-llm | SWITCHBOARD | Same scope |
| nomos-audit | INTERNAL AFFAIRS | Same scope |
| nomos-tape | THE TICKER | Same scope |
| nomos-wire | THE HERALD | Same scope |
| nomos-pay | THE ACCOUNTANT | Same scope |
| — | PIXEL | NEW — visual QA |
| — | THE PLUMBER | NEW — data pipelines |
| — | LAUNCHPAD | NEW — CI/CD |
