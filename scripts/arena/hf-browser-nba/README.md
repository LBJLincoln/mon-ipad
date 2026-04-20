---
title: Nomos42 Browser NBA Scraper
emoji: 🏀
colorFrom: blue
colorTo: red
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# nomos-browser-nba

Browser-agent Space for Nomos42. Scrapes live NBA lines (ESPN, basketball-reference,
Vegas Insider) using [browser-use](https://github.com/browser-use/browser-use) v0.12.6
with `ChatAnthropic(claude-sonnet-4-6)` primary + `ChatGoogle(gemini-3-flash)` fallback.

## Endpoints

- `GET /api/status` — liveness + provider availability
- `POST /api/scrape-nba-lines` — `{sources:[...], date:"YYYY-MM-DD"}` → `{games:[...]}`
- `GET /api/latest-lines` — last cached scrape (reads `/data/lines-latest.json`)

## Secrets required

- `ANTHROPIC_API_KEY` — primary LLM
- `GOOGLE_API_KEY` — fallback (gemini-3-flash)
- `BROWSERUSE_API_KEY` — optional, enables fastest proprietary path

Owned by DR FRANKENSTEIN. Upstream proposal: `data/research/hermes-browser-agents-2026-04-20.md`.
