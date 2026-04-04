# Nomos42 — Unified Infrastructure Map

> All compute, storage, and communication channels across the ecosystem.
> Updated: 2026-04-04

## Compute Layer

### Tier 1: Always-On (Free)
| Node | Specs | Role | Cost |
|------|-------|------|------|
| Google Cloud VM | 1 vCPU, 969MB RAM, 30GB | Control tower, crons, bots, API | $0 (free tier) |
| HF Spaces ×6 | 2 vCPU, 16GB each | Evolution islands (S10-S15) | $0 (free CPU) |
| Vercel | Serverless | Dashboard hosting | $0 (hobby) |
| Supabase | Postgres + Edge Functions | Data warehouse | $0 (free tier) |

### Tier 2: Burst GPU (Free/Low-cost)
| Node | Specs | Role | Cost |
|------|-------|------|------|
| Kaggle P100 | 16GB VRAM, 9h sessions | Karpathy GPU loops | $0 (30h/week) |
| Google Colab T4 | 15GB VRAM, 12h sessions | TabICL training | $0 (free) / $10 (Pro) |
| HF ZeroGPU H200 | 80GB VRAM | Ultra-fast inference | $0 (5min/day/acct × 3) |
| Lightning.ai | A10G, 22h/mo | Burst training | $0 (free tier) |

### Tier 3: Local Compute
| Node | Specs | Role | Status |
|------|-------|------|--------|
| Laptop (Aurelien) | Acer Aspire 3, Windows | Local models, Claude Desktop | ACTIVE |
| iPad | Termius SSH | Piloting, monitoring | ACTIVE |
| Brother's PC | TBD | Additional compute | BLOCKED (SSH pending) |

### Tier 4: Paid Burst (Emergency)
| Node | Specs | Cost |
|------|-------|------|
| Vast.ai | Various GPUs | $0.16/hr |
| Modal | A100/H100 | Pay-per-second |
| RunPod | Various | $0.20/hr |

## Storage Layer

### Primary Data Stores
| System | Content | Capacity | Access |
|--------|---------|----------|--------|
| **GitHub** | All code, JSON data, configs | 1GB/repo | git, API |
| **Supabase** (ayqviq) | NBA stats, experiments, proposals | 500MB free | SQL, REST, MCP |
| **Neo4j** (38c949a2) | Knowledge graph | 200K nodes free | Cypher, MCP |

### Secondary/Backup
| System | Content | Capacity | Access |
|--------|---------|----------|--------|
| **Google Drive** | Backups, large files | 15GB free | backup-to-drive.sh |
| **HF Hub** | Model weights, datasets | 100GB free | git lfs, API |
| **Pinecone** | Vector embeddings | 100K vectors free | REST, MCP |

### Knowledge Management (Obsidian-Style)
| Layer | Tool | Content |
|-------|------|---------|
| Structured notes | docs/obsidian/ (13 notes) | Architecture, depts, research |
| Graph relations | Neo4j | Entity relationships |
| Semantic search | Pinecone | Document embeddings |
| Auto-memory | .claude/projects/memory/ | Session insights |
| Agent memory | .claude/agent-memory/ | Per-agent learnings |

## Communication Channels

### Outbound (us → world)
| Channel | Purpose | Frequency |
|---------|---------|-----------|
| @Nomos42 (Telegram) | Public channel | Daily reports |
| @Nomos42Bot | Brain — research, analysis | On-demand |
| @Forge42Bot | SaaS — user picks, tiers | On-demand |
| @RGWAbot | AI Art — generation, gallery | On-demand |
| nomos42.vercel.app | Dashboard — all projects | Live |

### Internal (agents ↔ agents)
| Channel | Purpose |
|---------|---------|
| data/*.json | State sharing via git |
| Supabase tables | Experiment results |
| Neo4j graph | Knowledge sharing |
| council-*.json | Department state |
| guardian-report.json | Cross-dept orchestration |

## Accounts Inventory

### HF Spaces (3 accounts = 300K free credits/month)
| Account | Token Var | Spaces |
|---------|-----------|--------|
| LBJLincoln | HF_TOKEN | Primary dev |
| LBJLincoln26 | HF_TOKEN_2 | Evolution islands |
| Nomos42 | HF_TOKEN_3 | S10-S15 production |

### API Keys
| Service | Key Location | Purpose |
|---------|-------------|---------|
| OpenRouter | .env.local (7 keys) | Multi-model access |
| Supabase | .env.local | Data warehouse |
| Kaggle | ~/.kaggle/kaggle.json | GPU notebooks |
| Neo4j | settings.json | Knowledge graph |
| Pinecone | settings.json | Vector search |

## Monitoring & Alerting

| What | How | Frequency |
|------|-----|-----------|
| Spaces UP/DOWN | agent-health.json via watchdog | Every 5 min |
| Bot fleet alive | watchdog.sh PID checks | Every 5 min |
| Cross-repo sync | cross-repo-monitor.py | Every 2h |
| Telegram daily report | daily_report.py | 09:00 + 21:00 UTC |
| Evolution stagnation | guardian-orchestrator.py | Every 2h |
| Odds freshness | fetch_free_odds.py | Every 30min (game hours) |
| Kaggle kernel status | kaggle-gpu-evolution.sh | Daily 03:00 UTC |

## Cost Summary

| Category | Monthly Cost |
|----------|-------------|
| Compute (VM + HF + Kaggle + Colab) | $0 |
| Storage (GitHub + Supabase + Neo4j + Drive) | $0 |
| APIs (OpenRouter free tier) | $0 |
| Domain (optional) | ~$10 |
| **Total burn rate** | **~$10-30/mo** |
| Colab Pro (optional) | +$10 |
| The Odds API (optional, for props) | +$99 |
