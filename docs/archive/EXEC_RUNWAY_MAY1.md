# Runway / Shutdown Risk — May 1 2026

> **As of 2026-04-20** | **Days to May 1: 11** | **Days to May 8 CLI-payment cliff: 18** | Source: `MONETIZATION.md`, `data/tracks/t3-market.json`, `data/tracks/t4-capital.json`

## Bottom line up front

**Current MRR: $0. Required MRR by 2026-05-08: $95 ($19 × 5 subs). Delta: −$95 / −100%.** The $1M trading-floor narrative does not pay the Claude Code bill. Only Stripe receipts do.

## The math

| Line | Value | Source |
|---|---:|---|
| Required MRR floor (Claude Code CLI) | $95 / mo | `MONETIZATION.md` |
| Required subs at $19/mo | 5 | $95 / $19 |
| Current paying subs | 0 | `t3-market.json` → `paying_subs: 0` |
| Current MRR | $0 | `t3-market.json` → `mrr_usd: 0` |
| Current Telegram subs (free) | 0 | `t3-market.json` → `telegram_subs: 0` |
| Gap to floor | **−5 subs / −$95** | derived |
| Conversion model (plan assumption) | 2% | `MONETIZATION.md` |
| Required warm-landing visits to hit floor | **250 visits in 18 days ≈ 14/day** | 5 / 0.02 |
| Days to May 1 | 11 | today 2026-04-20 |
| Days to CLI cliff (May 8) | 18 | today 2026-04-20 |

## Status vs the `MONETIZATION.md` day-by-day plan

| Plan day | Plan asset | Required by | Shipped? | Gap |
|---:|---|---|---|---|
| 14 | Stripe Payment Link ($19/mo) | 2026-04-14 | — | 6 days overdue |
| 15 | `@Nomos42Picks` private channel + bot perms | 2026-04-15 | "scaffolded" per `t3-market.json` `last_action` | status unverified |
| 16 | Stripe webhook → whitelist persistence | 2026-04-16 | not in `last_action` | 4 days overdue |
| 17 | Daily-picks auto-post cron | 2026-04-17 | not in `last_action` | 3 days overdue |
| 18-19 | `/subscribe` landing copy + social proof | 2026-04-18/19 | not in `last_action` | 1-2 days overdue |
| 20 | Soft launch, 10 warm leads | **today** | — | today |
| 21-28 | Public launch (Reddit / X / 1 YouTube) | 2026-04-21 → 04-28 | not started | on deck |
| 29-30 | First revenue event | 2026-05-01 → 02 | NOT YET FEASIBLE without shipping 14–19 | **high risk** |
| 35-36 | **Deadline: 5 subs** | 2026-05-07 → 08 | — | binary gate |

**Every upstream asset is late. The 14-day backlog of shipping items compounds into conversion risk, not just timing risk.**

## SCQA — what to do today

- **Situation.** 18 days of runway. Payment plumbing, landing proof, and distribution channel all behind schedule. Trading-floor narrative (PQTF $602K) is load-bearing evidence but not yet on the `/subscribe` page.
- **Complication.** Marketing is the bottleneck per `MONETIZATION.md` — not code. But we do not have a live Stripe link to route traffic to, so marketing cannot start.
- **Question.** What single action in the next 48 hours moves us from 0 → 1 paying sub?
- **Answer.** Ship the **Stripe Payment Link** (no webhook yet, no paywall automation yet — just a URL that takes money and a Telegram DM flow). Manual fulfillment for first 5 subs is acceptable. This is the one-day task that unblocks everything downstream.

## Decision tree

```
        Is Stripe Payment Link live by 2026-04-21 EOD?
                    /               \
                  YES                NO
                   |                  |
        Can we drive 50 visits     Escalate to BOSS:
        to /subscribe by 04-25?    is $19/mo the right
              /       \            price, or switch to
            YES        NO          one-time $49 playbook?
             |          |
        Likely hit    Pivot to
        5 subs by     $49 one-time
        05-08         by 04-27 to
                      preserve May 1
                      revenue event
```

## Three levers the Accountant owns, ranked by expected lift per day of effort

1. **Stripe Payment Link + manual Telegram onboarding** (1 day of founder time). Unblocks ALL other work. Expected: 0 → 1 sub within 72h of posting to any warm channel.
2. **`/subscribe` landing copy with PQTF $602K proof + walk-forward equity curve** (½ day of HERALD + PIXEL). Expected 2% → 3-4% conversion lift on visits.
3. **Price-anchor test: offer $49 one-time "first week" as fallback** if $19/mo recurring has < 1% visit-to-sub conversion by 2026-04-27. Covers the shutdown floor faster (2 one-time sales = $98 ≈ 1 month MRR).

## Kill criteria

- **By 2026-04-23:** if Stripe link still not live → escalate to BOSS for founder-time reallocation. Payment plumbing cannot take 3 more days.
- **By 2026-04-27:** if `/subscribe` page has < 50 visits → marketing is broken, not pricing. Blast 3 Reddit communities + 1 X post the same day.
- **By 2026-05-01:** if 0 subs → switch pricing to one-time $49 and sell 2 seats to personal network to clear the floor.
- **By 2026-05-08:** if < 5 paying subs → **SHUTDOWN** per `project_deadline_may2026.md`.

## What is NOT on the runway path

- NBA/POL/ITF fleet improvements do not pay the May 1 bill. They are the *narrative* that converts visits → subs. They are necessary, not sufficient.
- PQTF's $602K is a sales asset, not revenue. It closes the credibility gap on `/subscribe`. Surface it on the landing page this week.

Next accountant action: confirm with founder that Stripe Payment Link ships by EOD 2026-04-21. Everything else is downstream of that gate.
