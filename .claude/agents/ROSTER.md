# Nomos42 Agent Roster — v4 "Clean Lanes" (2026-04-21)

**Principle:** one agent, one domain, one repo, one cred set, one cron slot.
No overlap. Every agent knows exactly which HF account / API key to use.
THE BOSS dispatches — never duplicates.

**Commit protocol (MANDATORY for every crew member):**
All autonomous commits MUST shell through `scripts/lib/safe_commit.sh <CODENAME> "<msg>" [paths...]`
(flock on `/tmp/nomos-git.lock`, pull --rebase --autostash, 3× push retry, `[AGENT]` prefix).
Naked `git add / commit / push` is banned — with 14 agents on staggered crons the race-reject
rate was unacceptable. See `project_git_mutex_apr19` memory + `scripts/lib/safe_commit.sh`.

**RCA-first protocol (MANDATORY, 2026-04-21):**
Before ANY TF-facing tune (config, prompt, risk cap, fallback, reroute) by
SWISH / LOBBYIST / DR FRANKENSTEIN / THE BLACKSMITH / THE BOSS, the caller
MUST first invoke **INTERNAL AFFAIRS Mode B (loser-RCA on demand)** and cite
the resulting `data/audit/<tf>-losers-rca-YYYY-MM-DD.md` in the commit
message. No audit → no tune. Infra restarts (dead Space → factory_reboot) and
pure feature additions from HAWKEYE's research queue are exempt. See
`feedback_always_rca_losers_first` memory + INTERNAL AFFAIRS Mode B section
in `.claude/agents/internal-affairs.md`.

**Separation-of-concerns protocol (v4, 2026-04-21):**
- **Science agents** (SWISH, LOBBYIST, FRANKENSTEIN) decide WHAT to change on HF
  Spaces (model config, feature set, persona routing) but NEVER call restart/deploy
  endpoints themselves.
- **Infra agent** (SWITCHBOARD) owns ALL HF Space lifecycle across all 4 accounts
  (start, stop, restart, factory_reboot, hardware upgrade). Holds all 4 tokens
  read/write. Only actor that ever POSTs to `/api/restart` or `HfApi.restart_space`.
- **Platform agent** (LAUNCHPAD) owns CI/CD + cross-repo sha parity. Never
  deploys itself. Reports mismatches for SWITCHBOARD (Space redeploy) or
  FRANKENSTEIN (engine update) to act.

## The Crew — 14 Agents × 9 Departments × 4 Tracks

| # | Codename | Old Name | Dept | Track | Layer | What they do |
|---|----------|----------|------|-------|-------|-------------|
| 1 | **THE BOSS** | nomos-brain | ALL | ALL | L1 | Floor manager — dispatches all 13 agents |
| 2 | **SWISH** | nomos-hoops | D3 Evolution | T1 SCIENCE | L2 | NBA islands S10-S22 (science only) + NBA TF science |
| 3 | **LOBBYIST** | nomos-alpha | D3 Evolution | T1 SCIENCE | L2 | Political islands P1-P8 (science only) + POL TF science |
| 4 | **HAWKEYE** | nomos-scout | D1 Research | T1 SCIENCE | L2 | Daily arXiv/GitHub/web recon |
| 5 | **DR FRANKENSTEIN** | nomos-lab | D1 Research | T1 SCIENCE | L2 | Engine.py + ITF personas + Hermes browser trio |
| 6 | **THE BLACKSMITH** | nomos-forge | D2 Engineering | T2 PLATFORM | L2 | **NO-OP** — councils decommissioned 2026-04-20. Reserved. |
| 7 | **SWITCHBOARD** | nomos-llm | D7 Infra | T2 PLATFORM | L3 | **ALL HF Space lifecycle across 4 accounts** (multi-token) |
| 8 | **INTERNAL AFFAIRS** | nomos-audit | D6 Evaluation | T1 SCIENCE | L2 | Scientific integrity (Mode A scheduled + Mode B loser-RCA on demand) |
| 9 | **THE TICKER** | nomos-tape | D8 Finance | T4 CAPITAL | L3 | Live odds scanner, CLV, steam moves |
| 10 | **THE HERALD** | nomos-wire | D4 Product | T3 MARKET | L2 | Telegram publisher + paywall |
| 11 | **THE ACCOUNTANT** | nomos-pay | D5 Business | T3 MARKET | L2 | Stripe/Whop/LS revenue + niche/pricing/GTM |
| 12 | **PIXEL** | — (new) | D4 Product | T3 MARKET | L2 | Dashboard + /world + browser-QA visual audit |
| 13 | **THE PLUMBER** | — (new) | D7 Infra | T2 PLATFORM | L3 | Data pipeline + ETL health (read-only) |
| 14 | **LAUNCHPAD** | — (new) | D9 Cross-repo | T2 PLATFORM | L2 | CI/CD + deploy sha parity (diagnose only) |

## Account Layout (4 HF accounts × ≤8 Spaces = 32 slots)

All HF Space **lifecycle** (restart / factory_reboot / start / stop) flows through
**SWITCHBOARD** only. Column "Science owner" = who decides WHAT to change on a
given Space; column "Lifecycle" = always SWITCHBOARD.

| Account | Token env | Science owner | Lifecycle | Spaces |
|---------|-----------|---------------|-----------|--------|
| **LBJLincoln26** | `HF_TOKEN_NBA` | SWISH (NBA) / LOBBYIST (POL) / FRANKENSTEIN (ITF, Hermes) | SWITCHBOARD | S16 S17 S20 S21 · nba-llm-trading-floor · political-llm-trading-floor · intraday-trading-floor · pqtf (frozen) · nomos-hermes-agent |
| **LBJLincoln** | `HF_TOKEN` | LOBBYIST | SWITCHBOARD | P1 P2 P3 P4 P5 P6 P7 P8 · nomos-browser-nba |
| **Nomos42** | `HF_TOKEN_LLM` | SWITCHBOARD (infra) / PIXEL (pixel-world) | SWITCHBOARD | llm-gateway · pixel-world · langfuse · selfhost LLM pool |
| **TESTforge42** | `HF_TOKEN_COUNCILS` | SWISH (S18/S19/S22 NBA overflow) / PIXEL (browser-qa consumer) | SWITCHBOARD | S18 S19 S22 · nomos-browser-qa |

**PQTF frozen forever** (memory `project_pqtf_frozen_forever`): SWITCHBOARD
status-check only, NEVER restart. $602K validation artifact must be preserved.

## Department → Agent Mapping

| Dept | Name | Agents | Mission |
|------|------|--------|---------|
| D1 | RESEARCH | HAWKEYE, DR FRANKENSTEIN | Find + implement SOTA techniques |
| D2 | ENGINEERING | THE BLACKSMITH | **NO-OP** (councils deleted 2026-04-20) |
| D3 | EVOLUTION | SWISH, LOBBYIST | NBA + Political island management (science) |
| D4 | PRODUCT | THE HERALD, PIXEL | Publish picks + visual QA |
| D5 | BUSINESS | THE ACCOUNTANT | Revenue pipeline + May 1 deadline |
| D6 | EVALUATION | INTERNAL AFFAIRS | Scientific integrity, audit (Mode A+B) |
| D7 | INFRA | SWITCHBOARD, THE PLUMBER | Space lifecycle + data pipeline health |
| D8 | FINANCE | THE TICKER | Live odds, CLV, steam detection |
| D9 | CROSS-REPO | LAUNCHPAD | CI/CD, deploy sync, cross-repo parity |

## Track → Agent Mapping

| Track | Agents | Focus |
|-------|--------|-------|
| T1 SCIENCE | SWISH, LOBBYIST, HAWKEYE, DR FRANKENSTEIN, INTERNAL AFFAIRS | Brier floor, calibration, mutation, research |
| T2 PLATFORM | THE BLACKSMITH (no-op), SWITCHBOARD, THE PLUMBER, LAUNCHPAD | Lifecycle, deploys, uptime, data pipelines |
| T3 MARKET | THE HERALD, THE ACCOUNTANT, PIXEL | Dashboard, Telegram, subs, pricing, visual QA |
| T4 CAPITAL | THE TICKER | Odds, CLV, TF bankrolls, Kelly sizing |

## Trading Floor Ownership (v4 explicit)

| TF | Engine file | Science owner | Lifecycle | Notes |
|----|-------------|---------------|-----------|-------|
| NBA TF | `scripts/arena/hf-llm-trading-floor/` | SWISH | SWITCHBOARD | 175 days, 17 LLM agents |
| POL TF | `scripts/arena/hf-political-trading-floor/` | LOBBYIST | SWITCHBOARD | 184 days, 17 LLM agents |
| ITF | `scripts/arena/hf-intraday-trading-floor/` | DR FRANKENSTEIN | SWITCHBOARD | v2.6, 17 personas, 71+ instruments |
| PQTF | `scripts/arena/hf-pqtf-trading-floor/` | — (frozen) | SWITCHBOARD (status only) | $602K artifact, NEVER restart |

## Browser + Hermes Trio (2026-04-20 additions)

| Space | Account | Science owner | Lifecycle | Consumer |
|-------|---------|---------------|-----------|----------|
| `LBJLincoln/nomos-browser-nba` | LBJLincoln | DR FRANKENSTEIN | SWITCHBOARD | SWISH (scraped odds → predictions) |
| `TESTforge42/nomos-browser-qa` | TESTforge42 | DR FRANKENSTEIN | SWITCHBOARD | PIXEL (visual QA automation) |
| `LBJLincoln26/nomos-hermes-agent` | LBJLincoln26 | DR FRANKENSTEIN | SWITCHBOARD | DR FRANKENSTEIN (research auto) |

## Cron Schedule (v4)

```
*/30      THE TICKER           (every 30 min — game windows)
:00 */4h  THE BOSS             (dispatcher)
:10 */4h  SWISH                (NBA islands science)
:15 */4h  LOBBYIST             (POL islands science)
:25 */4h  (reserved)           THE BLACKSMITH no-op until councils revive
:35 */4h  THE PLUMBER          (data pipeline health)
:40 */4h  INTERNAL AFFAIRS     (Mode A audit)
:20 */6h  SWITCHBOARD          (all HF Space lifecycle)
:45 */6h  LAUNCHPAD            (CI/CD + sha parity)
:00 */12h DR FRANKENSTEIN      (engine feature impl + ITF/Hermes)
06:00     HAWKEYE              (daily recon)
09:00     THE ACCOUNTANT       (revenue sync)
18:00     THE HERALD           (publish picks)
on-demand PIXEL                (visual QA after deploys)
on-demand INTERNAL AFFAIRS     (Mode B loser-RCA — called by science agents pre-tune)
```

## v3 → v4 Migration notes (2026-04-21)

| Change | Rationale |
|--------|-----------|
| BLACKSMITH → NO-OP | 9 TESTforge42/nomos-dept-d*-* councils deleted 2026-04-20. Karpathy loops retired. Agent file preserved for future revival. |
| SWITCHBOARD → multi-token, all-account lifecycle | Resolves token gap: POL TF + ITF + Hermes trio had no clear lifecycle owner. |
| SWISH/LOBBYIST → "science only" | Removes ambiguity on who restarts Spaces. Science agents never POST to restart endpoints. |
| FRANKENSTEIN scope + ITF + Hermes | Already builder of record for both; now explicit. |
| PQTF frozen-forever block | Protects $602K validation artifact from accidental restart. |
| v4 protocol: separation-of-concerns block | Codifies 14-agent lane discipline. |

## Retired agents (migrated 2026-04-18)

| Old Name | → New Codename | Notes |
|----------|---------------|-------|
| nomos-brain | THE BOSS | Same role, expanded crew list |
| nomos-hoops | SWISH | Same scope (narrowed to science v4) |
| nomos-alpha | LOBBYIST | Same scope (narrowed to science v4) |
| nomos-scout | HAWKEYE | Same scope |
| nomos-lab | DR FRANKENSTEIN | Expanded (ITF + Hermes trio v4) |
| nomos-forge | THE BLACKSMITH | NO-OP (councils deleted v4) |
| nomos-llm | SWITCHBOARD | Expanded (multi-token all-account v4) |
| nomos-audit | INTERNAL AFFAIRS | Mode A + Mode B (RCA gate v4) |
| nomos-tape | THE TICKER | Same scope |
| nomos-wire | THE HERALD | Same scope |
| nomos-pay | THE ACCOUNTANT | Same scope |
| — | PIXEL | NEW — visual QA |
| — | THE PLUMBER | NEW — data pipelines |
| — | LAUNCHPAD | NEW — CI/CD |
