---
title: Nomos42 Hermes Agent
emoji: ⚡
colorFrom: yellow
colorTo: green
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# nomos-hermes-agent

FastAPI RPC wrapper around the `NousResearch/hermes-agent` CLI.

## Endpoints

- `GET /api/status` — liveness + reports whether the `hermes` binary installed
- `POST /api/task` — `{prompt, model?}` → runs `hermes --task -` subprocess
- `POST /api/skills` — list Hermes skills (`hermes skills list`)

## Secrets

- `NOUS_API_KEY` (may not yet exist — user will add)
- `OPENROUTER_API_KEY`
- `ANTHROPIC_API_KEY`
- `MODAL_TOKEN_ID` (optional, for code-exec backend)

If the installer could not reach `raw.githubusercontent.com` during HF build,
the status endpoint returns `binary_missing: true` and `/api/task` returns a
structured stub response instead of crashing.
