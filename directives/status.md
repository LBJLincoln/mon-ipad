# Status — 23 Fevrier 2026 (Session 51)

> Last updated: 2026-02-23T23:30:00+01:00

### Session 51 — 23 fevrier 2026 (23:30+)
- **Objectif**: Fix broken pipelines (env var syntax), redeploy HF Space v5.4
- **Root cause found**: Standard + Graph workflow JSONs used `={{.VAR}}` instead of `={{$env.VAR}}` — caused Bearer null on all API calls
- **Actions**: Fixed 17 instances across 6 JSON files, updated entrypoint to v5.4, redeploying HF Space
- **Resultat**: Fix applied, deploy in progress

### Session 50 — 23 fevrier 2026 (~21:00)
- **Objectif**: Deploy v5.3 with per-pipeline OpenRouter keys
- **Actions**: Added 6 per-pipeline credential creation in setup-workflows.py, 7 env vars for key rotation
- **Resultat**: Deployed but Standard/Graph still broken (root cause was env var syntax, not keys)

### Session 49 — 23 fevrier 2026 (~19:00)
- **Objectif**: Deploy v5.2 with 2-pass activation
- **Actions**: Fixed httpHeaderAuth type mapping, removed duplicate quantitative workflow
- **Resultat**: 4/5 webhooks responding but Standard/Graph return empty answers

## Session 42 = VM Cleanup, HF Space Rebuild, Anti-VM Guards, Multi-Key OpenRouter

### What happened
- **n8n REMOVED from VM** — Freed ~270MB RAM (n8n Docker + workers + postgres + redis all removed)
- **VM is now pilotage-only** — NO eval scripts run on VM, all tests point to HF Space
- **Anti-VM guards added** — All eval scripts (quick-test, iterative-eval, run-eval-parallel) now check N8N_HOST and refuse to run if pointing to localhost
- **HF Space rebuilt** with new architecture:
  - Queue mode: 1 main + 2 workers (3 total)
  - Database: Supabase PostgreSQL (not SQLite) — 40 tables, 17K+ rows migrated
  - 7 OpenRouter keys configured: 5 pipeline-specific + 1 main + 1 spare
  - Multi-key rotation to prevent rate limits
- **All eval scripts updated** to default to HF_SPACE_URL (no more VM fallback)
- **RAM freed on VM** — ~270MB available now (was ~100MB before)

### Critical blocker status
**HF Space ALL WEBHOOKS 404** — entrypoint.sh activation broken after rebuild (Session 39).
NO pipelines can run until this is fixed. This is the #1 cross-pipeline bottleneck.

### Phase 2 cumulative results
| Pipeline | Tested | Total | Accuracy | Status |
|----------|--------|-------|----------|--------|
| Standard | 579 | 1000 | ~36% | STOPPED (HF Space 404) |
| Graph | **500** | 500 | **78.0%** | COMPLETE |
| Quantitative | **500** | 500 | **92.0%** | COMPLETE |
| Orchestrator | 57 | 1000 | 0% | BROKEN (returns empty/404) |
| PME Gateway | 0 | — | — | NOT ACTIVATED (HF rebuild didn't activate) |

### Infrastructure changes (Session 42)
| Component | Before (Session 39) | After (Session 42) | Change |
|-----------|-------------------|-------------------|--------|
| **VM n8n** | Running (Docker, 5678) | **REMOVED** | Freed ~270MB RAM |
| **VM eval scripts** | Could run tests | **BLOCKED** (anti-VM guards) | Force HF Space usage |
| **HF Space n8n** | SQLite + 1 worker | **Supabase PG + 3 workers** | Better scaling |
| **OpenRouter keys** | 1 shared key | **7 keys** (5 pipelines + 1 main + 1 spare) | Multi-key rotation |
| **VM RAM available** | ~100MB | **~370MB** | +270MB freed |
| **Default N8N_HOST** | localhost:5678 | **HF_SPACE_URL** | All scripts updated |

### Architecture clarity (Session 42)
```
VM (34.136.180.66) — PILOTAGE ONLY
  - Claude Code (Termius)
  - Git repos (mon-ipad + 4 satellites)
  - MCP servers (Pinecone, Neo4j, Supabase, Jina, Cohere, HF)
  - NO n8n (removed)
  - NO eval scripts (anti-VM guards block execution)
  - RAM: ~370MB available

HF Space (lbjlincoln-nomos-rag-engine.hf.space) — EXECUTION
  - n8n 2.8.3 (queue mode: 3 workers)
  - Supabase PostgreSQL (40 tables, 17K+ rows)
  - Redis (external, cloud)
  - 7 OpenRouter keys (multi-key rotation)
  - 16GB RAM
  - ALL WEBHOOKS 404 (activation broken — needs entrypoint.sh fix)

Codespaces (ephemeral) — HEAVY TESTING
  - rag-tests: Phase 2 runs (1000q per pipeline)
  - rag-data-ingestion: Dataset downloads (3/5 done, 669MB)
  - 8GB RAM per codespace
```

### Session 42 achievements
1. ✅ Removed n8n from VM (freed ~270MB RAM)
2. ✅ Added anti-VM guards to all eval scripts
3. ✅ Updated all scripts to default to HF_SPACE_URL
4. ✅ Configured 7 OpenRouter keys for multi-key rotation
5. ✅ Rebuilt HF Space with queue mode (3 workers) + Supabase PG
6. ✅ Documented VM = pilotage ONLY (no execution)
7. ⏳ HF Space activation still broken (entrypoint.sh needs fix)

### Session 43 priorities
1. **Fix HF Space entrypoint.sh** — activate all workflows with retry logic + verification
2. **Test multi-key OpenRouter** — verify rotation works, no rate limits
3. **Relaunch Standard Phase 2** — continue from 579/1000 (batch-size 5)
4. **Debug Orchestrator** — fix 0% accuracy (returns empty/404)
5. **Activate PME workflows** — 3 PME pipelines need activation on HF Space
6. **Resume data-ingestion downloads** — fix musique + finqa datasets (deprecated loading scripts)

### Key files updated (Session 42)
- `eval/quick-test.py` — Anti-VM guard, default HF_SPACE_URL
- `eval/iterative-eval.py` — Anti-VM guard, default HF_SPACE_URL
- `eval/run-eval-parallel.py` — Anti-VM guard, default HF_SPACE_URL
- `directives/repos/rag-data-ingestion.md` — Updated infrastructure section
- `directives/status.md` — This file (Session 42 summary)
- `.env.local` — Added 7 OpenRouter keys (LLM_STANDARD_KEY, LLM_GRAPH_KEY, etc.)

### Running processes
- Auto-push (PID varies) — every 20 min to GitHub
- No eval processes running (all blocked by HF Space 404)

### RAM usage (Session 42)
```
VM before:  ~100MB available, ~865MB used (n8n + Claude Code + OS)
VM after:   ~370MB available, ~595MB used (Claude Code + OS only)
Change:     +270MB freed (n8n + workers + postgres + redis removed)
```

### Documentation debt (to address Session 43)
- Update `CLAUDE.md` main file with Session 42 architecture changes
- Update `technicals/infra/architecture.md` with VM n8n removal
- Update `technicals/infra/n8n-topology.md` with HF Space as single source
- Update `technicals/debug/fixes-library.md` with FIX-XX (HF Space activation broken)
- Update `docs/executive-summary.md` with current Phase 2 state

### Lessons learned (Session 42)
1. **VM RAM is precious** — Removing n8n freed massive RAM (~270MB = 28% of total)
2. **Centralize execution** — HF Space 16GB >> VM 970MB. VM should only pilot.
3. **Anti-pattern guards work** — Scripts now refuse to run on VM, force correct infrastructure
4. **Multi-key rotation** — 7 OpenRouter keys prevent rate limit bottlenecks
5. **Supabase PG > SQLite** — Better for distributed n8n (3 workers), no lock issues
