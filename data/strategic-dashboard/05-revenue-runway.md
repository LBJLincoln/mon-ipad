# 05 — REVENUE + RUNWAY

**Deadline:** 2026-05-01 — if no revenue, shutdown. CLI runs out ~May 8.
**Target:** ≥5 subs @ $19/mo = $95/mo MRR by May 8.

## Product stack

| Surface | Product | Price | Status |
|---|---|---|---|
| Telegram | `@Nomos42Picks` — daily NBA edge cards | $19/mo | CHANNEL LIVE — paywall via Stripe |
| Telegram | `@Nomos42Bot` — interactive NBA brain (free teaser) | free | LIVE |
| Stripe Payment Link | monthly sub | $19/mo | LIVE |
| Whop | alt payment rail | $19/mo | setup pending |
| Lemon Squeezy | alt payment rail | $19/mo | setup pending |

## Publishing cadence

| Time (UTC) | Action | Owner |
|---|---|---|
| 11:00 | TICKER steam-move scan | THE TICKER |
| 18:00 | HERALD publishes ≤3 NBA edge cards | THE HERALD |
| 20:00 | HERALD CLV + stripe-link reminder | THE HERALD |
| daily | ACCOUNTANT writes runway dashboard | THE ACCOUNTANT |

## Why the numbers above work

- 1257-game TF run proves edges exist; fleet Brier 0.22073 beats closing-line Brier ~0.245.
- Stripe + Telegram = 0 infra cost.
- ≥5 subs covers CLI + provider costs (~$95/mo).

## Blockers

- Stripe welcome-DM automation (< 60s) — pending on HERALD cron
- Whop / LS accounts — not yet connected, not blocking May 1
- No refund policy text published yet — HERALD to ship

## Source of truth

- `data/ops/accountant-latest.json` — daily by THE ACCOUNTANT
- `data/herald/picks-*.json` — daily edge publications
- `MONETIZATION.md` (repo root) — concrete day-by-day plan
