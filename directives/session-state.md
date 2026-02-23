# Session State — 23 Fevrier 2026 (Session 43 — Credential Fix + Single Deploy)

> Last updated: 2026-02-23T18:50:00+01:00

## Objectif de session : Fix workflow credentials + env var migration + single batched deploy

### Session 43 — Credential Fix + Env Var Migration (2026-02-23 17:30-19:00 UTC)

#### What was done:
1. **Diagnosed real blocker**: Standard returns 200 but "Unable to generate answer" — hardcoded OpenRouter key EXPIRED (401)
2. **Replaced ALL hardcoded API keys** in workflow JSONs with `$env.*` references:
   - OpenRouter: `={{$env.OPENROUTER_KEY_STANDARD}}`, `_GRAPH`, `_QUANTITATIVE` per pipeline
   - Pinecone: `={{$env.PINECONE_API_KEY}}` and `={{$env.PINECONE_HOST}}`
   - Jina: `={{$env.JINA_API_KEY}}`
3. **Created setup-workflows.py**: Auto-creates n8n credentials (Postgres, OpenRouter httpHeaderAuth, Pinecone, Neo4j) with ID remapping before workflow import
4. **Rewrote entrypoint.sh v2**: Exports all env vars workflows need ($env.PINECONE_HOST, $env.JINA_API_KEY, etc.), calls setup-workflows.py for credential creation + import + activation
5. **Updated Dockerfile**: Added setup-workflows.py COPY
6. **Added Supabase connection details** as HF secrets (SUPABASE_HOST, SUPABASE_PORT, SUPABASE_DB, SUPABASE_USER)
7. **Updated fixes-library.md**: FIX-48 through FIX-53 (6 new fixes documented)
8. **Single batched deploy**: All fixes deployed in ONE push (SHA fe0aed9)
9. **Factory restart triggered**: Clean boot with new setup-workflows.py
10. **All 7 OpenRouter keys verified**: All return 200 with Gemma 27B

#### Current HF Space status:
- **healthz**: HTTP 200 (n8n is UP on port 7860)
- **Standard**: HTTP 200 (41.5s) — "Unable to generate answer" (Jina key expired → no embeddings)
- **Graph**: HTTP 200 (39s) — "Information not available" (needs Neo4j creds + Jina)
- **Quantitative**: HTTP 200 — WORKING
- **Orchestrator**: HTTP 404 — workflow not activated (setup-workflows.py may have failed for this one)
- **PME**: HTTP 404 — same
- **Factory restart**: Triggered, waiting for clean boot with new setup-workflows.py
- **Blocker**: Jina API key expired (403). User says they have a new one — needs to be added to .env.local

#### What was NOT completed:
- [ ] New Jina API key — user has it, needs to add to .env.local + redeploy
- [ ] Orchestrator activation — waiting for factory restart with setup-workflows.py
- [ ] PME activation — same
- [ ] PostgreSQL migration — deferred (SQLite works for now)
- [ ] Queue mode + workers — deferred
- [ ] Large-scale testing — needs all webhooks + valid Jina key first

### Phase 2 Cumulative Results
| Pipeline | Tested | Total | Accuracy | Status |
|----------|--------|-------|----------|--------|
| Standard | 579 | 1000 | ~36% | STOPPED — Jina key expired |
| Graph | 500 | 500 | 78.0% | COMPLETE |
| Quantitative | 500 | 500 | 92.0% | COMPLETE |
| Orchestrator | 57 | 1000 | 0% | BROKEN — 404 on HF Space |
| PME Gateway | 0 | — | — | NOT YET ACTIVATED |

### OpenRouter Keys (7 total — all verified working 2026-02-23)
| Key | Account | Pipeline | Status |
|-----|---------|----------|--------|
| OPENROUTER_API_KEY | Main | Fallback | OK |
| OPENROUTER_KEY_STANDARD | Termius1 | Standard RAG | OK |
| OPENROUTER_KEY_GRAPH | Termius2 | Graph RAG | OK |
| OPENROUTER_KEY_QUANTITATIVE | Termius3 | Quantitative | OK |
| OPENROUTER_KEY_ORCHESTRATOR | Termius4 | Orchestrator | OK |
| OPENROUTER_KEY_PME | Termius5 | PME Gateway | OK |
| OPENROUTER_KEY_SPARE | Termius6 | Spare/rotation | OK |

### Architecture (current)
- **Workflows**: 13 JSONs with all API keys as `$env.*` references (zero hardcoded keys)
- **Credentials**: Auto-created by setup-workflows.py (Postgres, httpHeaderAuth, Pinecone, Neo4j)
- **Boot**: SQLite + single process (minimal, reliable)
- **Deploy**: `scripts/deploy-hf-space.sh` — copies workflows, sets 19 HF secrets, pushes via git
- **Sub-agents**: 2 mandatory startup (Session Analyzer + Repo Health Inspector) + task-specific

### Critical Next Steps (Session 44)
1. **Add new Jina API key** to .env.local → redeploy with `deploy-hf-space.sh`
2. **Verify Orchestrator + PME** after factory restart with setup-workflows.py
3. **If Orchestrator still 404**: Debug setup-workflows.py import/activation logs
4. **Switch to PostgreSQL** for persistence
5. **Add queue mode + workers** for parallel execution
6. **Launch Standard Phase 2** (remaining 421 questions) with valid Jina key
7. **Fix Orchestrator** (0% accuracy — investigate intent classifier)
8. **All pipelines nohup with auto-commit**

### Git Commits This Session
- `ab7235a` fix: use emailOrLdapLoginId for n8n login (newer API field name)
- (pending) feat: env var migration + setup-workflows.py + credential auto-creation

---

### OPTIMAL PROMPT FOR SESSION 44 — COPY-PASTE THIS TO START

```
Session 44. Read CLAUDE.md first then:

1. cat directives/session-state.md
2. cat docs/status.json
3. cat directives/status.md
4. cat technicals/debug/knowledge-base.md | head -100

PRIORITY 1 — JINA KEY:
The current JINA_API_KEY in .env.local is EXPIRED (403).
User created a new Jina key. Update .env.local with the new key.
Then: source .env.local && bash scripts/deploy-hf-space.sh
This will push the new key as HF secret and redeploy.

PRIORITY 2 — CHECK HF SPACE:
curl -s "https://lbjlincoln-nomos-rag-engine.hf.space/healthz"
curl -s -m 60 -X POST "https://lbjlincoln-nomos-rag-engine.hf.space/webhook/rag-multi-index-v3" -H "Content-Type: application/json" -d '{"query":"What is EBITDA?"}'

All webhooks should work after Jina key is fixed. Timeouts are normal (30-60s for LLM calls).

PRIORITY 3 — IF ORCHESTRATOR STILL 404:
Check setup-workflows.py output in HF Space container logs.
The orchestrator.json may need a different import approach.

PRIORITY 4 — LARGE SCALE:
Once all 5 webhooks return 200:
1. PostgreSQL migration (Supabase)
2. Queue mode + workers (supervisord)
3. Launch all pipelines nohup with auto-commit
4. Each pipeline uses its own OR key (zero rate-limit collisions)

MULTI-KEY OPENROUTER (7 keys ready — all verified):
- OPENROUTER_KEY_STANDARD (Termius1)
- OPENROUTER_KEY_GRAPH (Termius2)
- OPENROUTER_KEY_QUANTITATIVE (Termius3)
- OPENROUTER_KEY_ORCHESTRATOR (Termius4)
- OPENROUTER_KEY_PME (Termius5)
- OPENROUTER_KEY_SPARE (Termius6)

ARCHITECTURE DONE:
- All workflow JSONs use $env.* for API keys (zero hardcoded keys)
- setup-workflows.py creates credentials + remaps IDs + imports + activates
- entrypoint.sh v2 exports all env vars + calls setup-workflows.py
- deploy-hf-space.sh sets 19 HF secrets + pushes in one go

source .env.local before ANY Python script.
```
