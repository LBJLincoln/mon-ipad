# Monetization Plan — May 1-8 deadline

**Reality check (2026-04-14):**
- 17 days to May 1 (housing/Claude Code cliff)
- Nothing built for payment or paywall yet
- Must ship the minimum-viable paid product THIS WEEK
- Target: first paying subscriber by 2026-04-21, ≥5 subs = $95+/mo by May 8

## The one product: @Nomos42Picks — Paid NBA Picks Telegram channel

**Why this and not the others:**
- The prediction engine exists and works (ATR 0.21570, walk-forward 51.3% ROI, 77.65% WR)
- No regulatory risk (we sell **information**, not bets)
- Lowest technical lift (~1 day of dev, rest is marketing)
- Public proof on the dashboard (calibration, equity curve, CPCV — all live)
- Sports-betting prediction market has proven willingness-to-pay

**Stripe-free dev path (NO code, just a payment link):**
1. Stripe Payment Link, $19/mo recurring, metadata.telegram_username required
2. Webhook → VM cron adds user to `@Nomos42Picks` (private) via Bot API
3. Daily picks auto-post at 09:00 ET from `predict_today.py` output
4. Auto-churn cron removes cancelled subs

## Day-by-day to ship

| Day | Action | Asset needed |
|-----|--------|--------------|
| 14 | Stripe account + Payment Link | bank info (user) |
| 15 | Private Telegram channel `@Nomos42Picks` + bot permissions | @Nomos42Bot admin perms |
| 16 | Webhook endpoint `/api/billing/stripe` on Vercel + whitelist persistence | Vercel env STRIPE_SECRET |
| 17 | Auto-post daily picks cron (09:00 ET) via existing `predict_today.py` | existing |
| 18-19 | Landing page section on dashboard `/subscribe` with copy + social proof (equity curve, WR, calibration chart) | copywriting |
| 20 | Soft launch to personal network (LinkedIn, Discord, Twitter DMs) | 10 warm leads |
| 21-28 | Public launch: Reddit r/sportsbook, Twitter NBA bettor network, 1 YouTube demo | marketing blitz |
| 29-30 (May 1-2) | First revenue event | **≥1 sub** |
| 35-36 (May 7-8) | **DEADLINE**: 5 subs = $95/mo, survive | **≥5 subs** |

## Pricing tiers (launch = simple)

- **$19/mo Picks** — 2-5 daily value bets, reasoning, Kelly stake
- Future: $49 Pro (historical backtest, customizable filters), $149 API access (B2B signals)

## Visible proof page on dashboard
Each of these already has data; just surface it on /subscribe:
- Live equity curve ($100 → $151.30, 51.3% ROI over 6mo walk-forward)
- Calibration reliability diagram (brier 0.20939 OOS)
- CPCV gate (our stats are bias-checked)
- 44 real tracked bets (`/api/nba/quant`)
- 8 evolution islands + 10-agent LLM trading floor (technical credibility)

## Honest risks
- **0 subs** by May 8 = deadline missed regardless of tech
- Need ~250 landing-page visits × 2% conversion = 5 subs
- Marketing is the bottleneck, not code

## What this plan does NOT include (intentional cuts)
- No political signals SaaS (no buyers, no proof, longer sell cycle)
- No dashboard Pro tier (too complex, distracts)
- No custom B2B API (takes weeks of sales)
