---
title: Nomos42 Browser QA
emoji: 🎨
colorFrom: purple
colorTo: pink
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# nomos-browser-qa

Browser-agent QA Space for Nomos42. Two primary targets:

- `/api/qa-pixel` — navigates to `nomos42-pixel-world.static.hf.space`, asserts sprite
  count ≥ 40, no console errors, HP bars rendered, takes full-page screenshot.
- `/api/qa-dashboard` — navigates `nomosdashboard.vercel.app/{nba,political,world}`,
  asserts zero TS/console errors, verifies Stripe link on `/pricing` if present.

Backed by `browser-use` + direct Playwright for low-level DOM checks.

## Endpoints

- `GET /api/status`
- `GET /api/latest-qa` — last 10 runs
- `POST /api/qa-pixel`
- `POST /api/qa-dashboard`

## Secrets

- `ANTHROPIC_API_KEY` (primary agent model)
- `GOOGLE_API_KEY` (fallback)

Owned by DR FRANKENSTEIN.
