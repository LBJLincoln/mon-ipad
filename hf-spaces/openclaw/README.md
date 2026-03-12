---
title: OpenClaw Nomos Agent
emoji: 🦞
colorFrom: red
colorTo: purple
sdk: docker
pinned: true
app_port: 7860
---

# OpenClaw v2026.3.11-beta.1

AI Operations Agent for Nomos Sector AI. Full infrastructure access — same capabilities as Claude Code CLI on the VM.

## Capabilities

- **14 HF Spaces** management (health check, deploy, restart, logs)
- **4 RAG Pipelines** query & evaluation (Standard, Graph, Quantitative, Orchestrator)
- **Database access**: Supabase (43K docs), Neo4j (72K nodes), Pinecone (58K vectors)
- **LLM routing**: OpenRouter with 9 models, automatic fallback chain
- **Telegram bot**: Command & control via webhook
- **Self-monitoring**: 5-minute health checks, auto-alerts on failures
- **Conversation persistence**: History saved to /data with periodic flush

## Environment Variables (Secrets)

Configure these in the HF Space settings:

### Required
| Variable | Description |
|----------|-------------|
| `OPENROUTER_API_KEY` | OpenRouter API key for LLM completions |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token from @BotFather |
| `ADMIN_TELEGRAM_ID` | Your Telegram user ID for admin commands |

### Infrastructure Access
| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Supabase PostgreSQL connection string (pooler) |
| `NEO4J_URI` | Neo4j Aura connection URI |
| `NEO4J_PASSWORD` | Neo4j password |
| `PINECONE_HOST` | Pinecone index host |
| `PINECONE_API_KEY` | Pinecone API key |
| `HF_TOKEN` | HF token (lbjlincoln account) |
| `HF_TOKEN_2` | HF token (lbjlincoln26 account) |
| `HF_TOKEN_3` | HF token (nomos42 account) |
| `LITELLM_PROXY_URL` | LiteLLM proxy URL (S7) |
| `LITELLM_MASTER_KEY` | LiteLLM master key |

### Optional
| Variable | Description |
|----------|-------------|
| `LOG_LEVEL` | Logging level (default: info) |
| `PERSISTENCE_DIR` | Override data directory (default: /data/conversations) |

## Telegram Commands

| Command | Access | Description |
|---------|--------|-------------|
| `/start` | All | Show help |
| `/status` | All | Infrastructure health check |
| `/spaces` | All | List all 14 HF Spaces |
| `/models` | All | Show configured LLM models |
| `/ping` | All | Connectivity test |
| `/query <q>` | All | Query RAG pipeline |
| `/eval [pipe] [n]` | All | Run eval smoke test |
| `/db <sql>` | Admin | Direct Supabase SQL query |
| `/neo4j <cypher>` | Admin | Direct Neo4j Cypher query |
| `/deploy <space>` | Admin | Restart/deploy a Space |
| `/logs <space>` | Admin | View Space logs |
| `/ingest <sector>` | Admin | Trigger ingestion |
| `/exec <space> <wh>` | Admin | Execute arbitrary webhook |

## REST API

All endpoints available at `https://<space-url>/api/v1/`:

- `POST /api/v1/query` — Query RAG pipeline
- `POST /api/v1/eval` — Run evaluation
- `POST /api/v1/exec` — Execute webhook on any Space
- `POST /api/v1/chat` — Direct OpenRouter LLM chat
- `POST /api/v1/db` — Supabase SQL (read-only)
- `POST /api/v1/neo4j` — Neo4j Cypher (read-only)
- `POST /api/v1/ingest` — Trigger ingestion
- `GET /api/v1/spaces` — List spaces with health
- `GET /api/v1/metrics` — System metrics
- `GET /keep-alive` — Health check (prevents HF sleep)

## Architecture

```
Telegram Bot <--webhook--> [OpenClaw HF Space]
                              |
              +---------------+---------------+
              |               |               |
        [14 HF Spaces]   [Databases]    [OpenRouter]
         S1-S11, etc.    Supabase       9 models
         n8n webhooks    Neo4j          auto-fallback
         HF Hub API      Pinecone
```
