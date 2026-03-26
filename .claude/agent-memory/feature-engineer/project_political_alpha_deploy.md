---
name: Political Alpha Deployment
description: Deploy status of nomos-political-alpha project — Supabase tables, cron jobs, HF Space, and feature engine tests
type: project
---

Deployed 2026-03-26. Project at /home/termius/nomos-political-alpha.

**Why:** New project stream alongside NBA Quant AI — predicts excess stock returns of Trump donor companies following political events.

**How to apply:** Reference this when user asks about political alpha status, cron schedules, or Supabase table schema.

## Supabase Tables (ALL created successfully)
- political_donors — DPI scores, ticker, donation amounts
- political_signals — policy events (exec orders, rules) with sector/ticker tagging
- polymarket_whales — whale trade activity on Trump policy markets
- insider_trades — SEC Form 4 filings
- political_predictions — model output per ticker per day
- political_experiments — evolution run metadata (mirrors NBA experiments table)
- political_bankroll — P&L tracking

## VM Cron Jobs (installed)
- `*/30 * * * *` — fetch_political_data.py --fast (signals + polymarket)
- `0 */6 * * *` — fetch_political_data.py --all (full fetch)
- `0 22 * * 1-5` — fetch_political_data.py --insider (Form 4, weekdays)
- `30 22 * * 1-5` — fetch_political_data.py --prices (stock prices, weekdays)

## HF Space: PENDING
- No hf-space/ directory exists in the repo
- deploy.py expects hf-space/app.py at LBJLincoln26/nomos-political-alpha
- Needs app.py to be written before HF Space deployment

## Feature Engine Tests
- PoliticalFeatureEngine loads: version=v1.0-political-8cat
- 252 features generated from minimal dummy event (8 categories)
- Real events with prices/macro data will expand feature count toward ~2000

## Data Fetcher Tests
- fetch_executive_orders(): 9 records returned, live Federal Register API works
- API name mismatch: deploy.py test assumed FederalRegisterFetcher class (doesn't exist)
  The module uses standalone functions: fetch_executive_orders(), fetch_federal_rules(), etc.
- All main fetchers are standalone functions in ops/fetch_political_data.py
