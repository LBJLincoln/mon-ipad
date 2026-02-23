# Session State — 23 Fevrier 2026 (Session 45 — HF Space Debug + Ideas)

> Last updated: 2026-02-23T20:45:00+01:00

## Objectif de session : Fix HF Space ALL 404 + capture user ideas

### Session 45 — HF Space Deep Debug (2026-02-23 19:15-20:45 UTC)

#### What was done:
1. **Rewrote entrypoint.sh v3.1**: Strip credential refs from workflow JSONs BEFORE CLI import to prevent FOREIGN KEY constraint errors. Import cleaned files from /tmp/n8n-clean-workflows/ instead of /app/n8n-workflows/.
2. **Rewrote setup-workflows.py v3**: No longer imports — updates EXISTING workflows (from CLI import) with new credential IDs, remaps sub-workflow references, activates.
3. **Fixed Neo4j auth separator**: Added `/` separator support (HF secrets use `neo4j/password` format).
4. **Fixed versionId for activation**: n8n 2.8.4 requires versionId in POST /activate. Added `wf.get("versionId", "")`.
5. **Added debug-status.json**: Zero-credential test workflow to verify import/activation chain.
6. **Updated Dockerfile**: Added sqlite3, chmod 777 for /home/node/.n8n.
7. **Discovered HF Space SSE logs**: `curl -N -s "https://huggingface.co/api/spaces/LBJLincoln/nomos-rag-engine/logs/run" -H "Authorization: Bearer $HF_TOKEN"`.
8. **Pushed to GitHub**: Commit `68e1f73`.

#### ROOT CAUSES IDENTIFIED (from container logs):
1. **FOREIGN KEY constraint failed**: CLI import fails for 9/13 workflows because they reference credential IDs (like `USU8ngVzsUbED3mn`) that don't exist in fresh SQLite. Only 4 import.
2. **versionId required**: n8n 2.8.4 activation POST requires versionId. Empty string fails with `invalid_type`.
3. **Deploy timing**: v3.1 entrypoint may not have been deployed — logs showed "Boot v3" not "Boot v3.1".

#### STILL BROKEN — NEEDS FIX IN SESSION 46:
- **FOREIGN KEY**: v3.1 credential stripping should fix it — need to VERIFY it's deployed
- **Activation**: versionId from list endpoint is empty. Solutions:
  - **Option A (BEST)**: Use `PATCH /rest/workflows/{id}` with `{"active": true}` instead of POST activate
  - **Option B**: GET full workflow details for each workflow to obtain versionId
- **Neo4j auth**: Shows "SKIP: Neo4j (no NEO4J_AUTH)" despite env var being set — check HF secret format
- **Result**: ALL webhooks 404, zero pipelines working

### Phase 2 Cumulative Results
| Pipeline | Tested | Total | Accuracy | Status |
|----------|--------|-------|----------|--------|
| Standard | 579 | 1000 | ~36% | STOPPED — ALL 404 |
| Graph | 500 | 500 | 78.0% | COMPLETE |
| Quantitative | 500 | 500 | 92.0% | COMPLETE |
| Orchestrator | 57 | 1000 | 0% | BROKEN — 404 |
| PME Gateway | 0 | — | — | NOT ACTIVATED |

### USER IDEAS (5 total — DO NOT LOSE):

**Idea 1 — New LLM Chatbot Repo**:
Currently, website visitors get errors when using any chatbot. Create a new repo with n8n workflows that use executive summaries + CLAUDE.md files as knowledge base, and a free OpenRouter LLM to respond. Replace broken website endpoints. PME-connectors site needs to be up-to-date but not necessarily re-deployed.

**Idea 2 — Ingestion Test Workflow**:
n8n workflow that tests ingested documents with targeted questions to verify they work correctly. ALSO include ability for user to add random files and test them manually.

**Idea 3 — Sub-Agents as Restrictors**:
The 2 startup sub-agents should prevent repeating documented-failed fixes by checking fixes-library.md. Also add VM monitoring agent 24/7 for all infrastructure.

**Idea 4 — CLAUDE.md Cleanup**:
Too many rules and too many files. Restructure after massive cleanup — better ordering, fewer rules. User frustrated that rules aren't followed.

**Idea 5 — Maintain 8-10 Step Plan**:
Always have a structured plan of 8-10 steps visible.

### Keys Added This Session
- JINA_API_KEY_2: `Jina_612a1894ec49431ab0e7a6b4dd9d7ebcTj7ocaeOewcnBAV3oZzjPHJ68Ej3`
- HF_TOKEN_2: `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` (second HF account for second Space)
- Jina key already in .env.local: `jina_4c85f15ab9c2436f87b037065eae41b22VYgmsj_6weB3JMCUsTX6n3Rvcfn`

### OpenRouter Keys (7 total — all verified)
OPENROUTER_KEY_STANDARD, _GRAPH, _QUANTITATIVE, _ORCHESTRATOR, _PME, _SPARE + main

### Git Commits This Session
- `68e1f73` session 45: HF Space entrypoint v3.1 + credential stripping + activation fix

---

### OPTIMAL PROMPT FOR SESSION 46 — COPY-PASTE THIS TO START

```
Session 46. Read CLAUDE.md first then:

1. cat directives/session-state.md
2. cat docs/status.json
3. cat hf-space/entrypoint.sh
4. cat hf-space/setup-workflows.py

=== CRITICAL FIX — HF Space ALL webhooks 404 ===

ROOT CAUSE: 3 issues found from container logs (Session 45):

ISSUE 1 — FOREIGN KEY constraint: CLI import fails for workflows with credential
references. Fix ALREADY in entrypoint.sh v3.1: strips credentials before import.
VERIFY it's actually deployed by checking container logs for "Boot v3.1" header.

ISSUE 2 — Activation fails: n8n 2.8.4 requires versionId for POST /activate.
The list endpoint returns empty versionId. FIX: Change setup-workflows.py to use
PATCH /rest/workflows/{id} with {"active": true} INSTEAD of POST /activate.
This avoids the versionId requirement entirely.

ISSUE 3 — Neo4j auth skipped: "SKIP: Neo4j (no NEO4J_AUTH)" despite env var set.
Check: is the HF secret NEO4J_AUTH actually set? Verify with deploy-hf-space.sh.

DEPLOY + VERIFY STEPS:
1. Fix setup-workflows.py: PATCH activation instead of POST
2. Deploy: set -a && source .env.local && set +a && bash scripts/deploy-hf-space.sh
3. Wait 4 minutes for build + boot (NOT 30 seconds!)
4. Monitor build: curl -N -s "https://huggingface.co/api/spaces/LBJLincoln/nomos-rag-engine/logs/build" -H "Authorization: Bearer $HF_TOKEN" | head -50
5. Monitor runtime: curl -N -s "https://huggingface.co/api/spaces/LBJLincoln/nomos-rag-engine/logs/run" -H "Authorization: Bearer $HF_TOKEN" | head -100
6. Look for: "Boot v3.1", "Cleaned: *.json", "CLI import: 13 workflows", activation successes
7. Test webhooks: curl -s -X POST https://lbjlincoln-nomos-rag-engine.hf.space/webhook/debug-status -H "Content-Type: application/json" -d '{"test":true}'

=== AFTER HF SPACE IS FIXED ===

PRIORITY 2 — Scale to 1000 requests per workflow (user wants this badly):
- Use both HF accounts for parallel execution
- Second HF Space for PME + overflow

PRIORITY 3 — User Ideas (5 ideas captured in session-state.md):
1. New LLM chatbot repo for websites (knowledge base = executive summaries + CLAUDE.md)
2. Ingestion test workflow with random file upload
3. Sub-agents as restrictors (prevent repeating failures)
4. CLAUDE.md cleanup (too many rules, restructure)
5. Always maintain 8-10 step visible plan

PRIORITY 4 — Clean satellite repos (rag-dashboard has 1098 files, should be ~150)

PRIORITY 5 — Deploy control-panel.html to Vercel via rag-dashboard

=== KEY FILES ===
- hf-space/entrypoint.sh — v3.1 with credential stripping
- hf-space/setup-workflows.py — v3 needs PATCH activation fix
- scripts/deploy-hf-space.sh — deployment script (sets 19 HF secrets)
- hf-space/n8n-workflows/debug-status.json — zero-cred test workflow

source .env.local before ANY script. Use set -a for unexported vars.
```
