---
name: Payment provider status as of 2026-04-17
description: Live status of Stripe, Whop, and LemonSqueezy accounts — what is set up vs what is missing
type: reference
---

## Stripe
- Account ID: acct_1T8eB335TLa6P2TQ
- Email: lahargnedebartoli@gmail.com
- Country: FR (France)
- charges_enabled: true
- payouts_enabled: true
- Key in .env.local: STRIPE_SECRET_KEY (sk_live_...)
- 3 recurring subscription prices:
  - STRIPE_PRICE_USER_PRO: price_1TAqqX35TLa6P2TQVXqfpvmZ — $20/mo (Scout)
  - STRIPE_PRICE_USER_SERIOUS: price_1TAqqY35TLa6P2TQ5pdojtC6 — $50/mo (Edge)
  - STRIPE_PRICE_USER_STAR: price_1TAqqa35TLa6P2TQ8RjcsOCm — $200/mo (Whale)
- 10 active payment links created (buy.stripe.com/... URLs)
- 0 completed checkout sessions ever

## Whop
- Company ID: biz_fu0YiwSIuhaJBr
- Key: WHOP_API_KEY in .env.local
- 0 active memberships

## LemonSqueezy
- Store ID: 310020, name "Nomos 42", currency EUR
- Key: LEMON_SQUEEZY_API_KEY in .env.local
- Status: test_mode=true — no live products published
- $0 all-time revenue, 0 all-time sales
