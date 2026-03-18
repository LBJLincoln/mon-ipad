# RGWA — Autonomous OpenClaw Agent

Second autonomous OpenClaw agent. Telegram: @RGWAbot.

## Architecture
- Reuses Eve's codebase (hf-spaces/openclaw/)
- Deployed on lbjlincoln/nomos-rgwa
- Connected to Eve via A2A protocol
- Same 130+ secrets, same DB access (Supabase, Neo4j, Pinecone)
- Own Telegram bot (@RGWAbot) — separate from Eve's @Nomos42Bot
- DNS fixes included (dns-fix.cjs + telegram-proxy.cjs)

## Deploy
```bash
source .env.local
python3 hf-spaces/rgwa/deploy.py
```

## Communication
- Eve → RGWA: POST https://lbjlincoln-nomos-rgwa.hf.space/api/v1/a2a/command
- RGWA → Eve: POST https://nomos42-nomos-worker-2.hf.space/api/v1/a2a/command
