# Session State — 24 Fevrier 2026 (Session 57)

> Last updated: 2026-02-24T17:00:00+01:00

## Current Status: SESSION END — HF Space DOWN, LOCAL fallback DISABLED

### Critical State
- **HF Space**: COMPLETELY DOWN — healthz returns HTTP 000 (connection timeout)
- **All 4 webhooks**: UNREACHABLE (were timing out even before healthz died)
- **LOCAL fallback**: DISABLED in code (Session 57 fix)
- **No eval running**: Previous eval killed (was using LOCAL fallback)

### Session 57 Actions Completed
1. **DISABLED LOCAL fallback** in `eval/run-eval-parallel.py` — Lines 171-183 replaced with comment. The hybrid fallback was calling OpenRouter directly from VM, masking real pipeline failures and producing fake accuracy numbers.
2. **DISABLED `--local-pipelines` flag** — Added guard that ignores the flag with warning.
3. **Fixed .env.local exports** (Session 57 early) — Added `export` to ALL 28 variables so child processes (curl, python, etc.) inherit them after session compaction.
4. **Fixed data.json race condition** (Session 57 early) — `live-writer.py` `_save()` now uses PID+thread+counter for unique tmp filenames, with retry logic and debounced status regeneration.
5. **Killed eval PID 426220** — Was running with LOCAL fallback enabled (batch-size 10, 4 pipelines).
6. **Killed stale processes** — PID 337605 (key rotation test from yesterday).
7. **Committed + pushed** — Commit 2a72686 (race condition + env export fix).

### Pipeline Debug Findings (from background agents)
| Pipeline | Root Cause | Fix Needed |
|----------|-----------|------------|
| Standard | Phase 2 dataset = general trivia NOT in Pinecone. Pipeline correctly returns "Unable to generate answer". | Need domain-specific questions matching Pinecone namespace data (benchmark-squad_v2, etc.) OR verify if benchmark data was ingested |
| Graph | Returns "Information not available in the knowledge graph" | Investigate Neo4j connectivity and data presence from HF Space |
| Quantitative | Context field not parsed from webhook payload. n8n workflow classifier only reads `query` field, doesn't see `table_data` or `context`. | Fix n8n workflow to read all 3 fields from webhook body |
| Orchestrator | Webhook times out. executeWorkflow returns empty when sub-workflow uses respondToWebhook (FIX-34). | Replace executeWorkflow with httpRequest POST to sub-pipeline webhooks |

### API Key Status
- 6 of 7 OpenRouter keys working (~120 req/min aggregate)
- SPARE key (sk-or-v1-27d3f1...) times out
- Per-pipeline key pattern: `$env.OPENROUTER_KEY_<PIPELINE>` in n8n workflows

### Infrastructure State
| Component | Status | Note |
|-----------|--------|------|
| HF Space | **DOWN** | healthz HTTP 000 — needs restart/rebuild |
| VM | **PILOTAGE ONLY** | No eval running, MCP servers active |
| CS rag-tests | **UNKNOWN** | Was available last session |
| CS data-ingestion | **PROVISIONING** | Agent a074e80 was creating it |
| Docker in Codespaces | **BROKEN** | iptables permission denied, cannot start |

### Environment (.env.local)
- All 28 variables have `export` keyword (permanent fix)
- N8N_HOST: https://lbjlincoln-nomos-rag-engine.hf.space
- N8N_API_KEY: Renewed JWT (293 chars, created 2026-02-24)
- OPENROUTER_API_KEY + 6 per-pipeline keys: Set
- All other keys: Set (Jina, Pinecone, Neo4j, Supabase, Cohere, HF, Vercel, Google)

### Files Modified This Session
| File | Change |
|------|--------|
| `.env.local` | Added `export` to all 28 variables |
| `eval/live-writer.py` | Fixed race condition: PID+thread+counter tmp files, retry logic, debounced status regen |
| `eval/run-eval-parallel.py` | DISABLED LOCAL fallback (lines 171-183), DISABLED --local-pipelines flag |

### Next Steps (Priority for Session 58)
1. **CRITICAL: Restart HF Space** — healthz returns 000, all webhooks unreachable. May need rebuild or manual restart via HF dashboard.
2. **Fix Quantitative n8n workflow** — Add `table_data` and `context` field parsing from webhook body (not just `query`)
3. **Fix Orchestrator n8n workflow** — Replace executeWorkflow with httpRequest POST for sub-pipelines (FIX-34)
4. **Verify Standard dataset** — Check if Pinecone has benchmark data (namespace benchmark-squad_v2, benchmark-triviaqa, benchmark-popqa). If not, either ingest or generate domain-specific questions.
5. **Relaunch eval** — Once HF Space is back and at least 1 pipeline is fixed, run `--reset --force --early-stop 15`
6. **Set up 2nd HF Space** — HF_TOKEN_2 needs verification
7. **Never use LOCAL fallback again** — Code is permanently disabled
