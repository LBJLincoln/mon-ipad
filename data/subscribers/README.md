# @Nomos42Picks subscriber ledger

Written by the Stripe webhook in `nomos-dashboard/src/app/api/billing/stripe/route.ts`.

- `pending/`   — every Stripe event dropped here as `YYYY-MM-DD_<event_id>.json` first
- `active/`    — moved here after a VM cron verifies subscription is live + Telegram handle is in the channel
- `cancelled/` — subscription ended or payment failed > 7d

The webhook PUTs via the GitHub Contents API (no DB) so we keep everything
auditable in git. Do NOT commit raw PII to public branches — filter emails
at the cron step before moving to `active/`.

**Next cron to write (W16 work, not yet implemented):**
- `scripts/telegram/sync_subscribers.sh` reads `pending/`, invites to @Nomos42Picks,
  moves to `active/`. Runs every 5 min.
