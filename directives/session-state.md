# Session State — 23 Fevrier 2026 (Session 44 — Env Var Fix + Repo Restructure + Dashboard)

> Last updated: 2026-02-23T19:15:00+01:00

## Objectif de session : Fix deploy overwrite bug + restructure repos + new dashboard

### Session 44 — Deploy Fix + Lean Repo + Control Panel (2026-02-23 18:30-19:15 UTC)

#### What was done:
1. **Fixed critical deploy overwrite bug**: `deploy-hf-space.sh` copied unfixed `n8n/live/*.json` over the env-var-migrated `hf-space/n8n-workflows/*.json` on every deploy. Fixed by migrating the SOURCE files (`n8n/live/`) to use `$env.*` expressions.
2. **n8n/live/ fully migrated**: Zero hardcoded keys remain:
   - standard.json: 16 replacements (OR per-pipeline, Jina, Pinecone key+host)
   - graph.json: 10 replacements
   - quantitative-v2-template-fix.json: 3 replacements
   - benchmark-dataset-ingestion.json: 2 replacements
3. **Created rag-storage repo**: New GitHub repo for centralized data archive. Per-repo directory structure + global metrics.
4. **Cleaned mon-ipad**: Removed 3 website directories (1.5GB) — already in satellite repos. Added .gitignore entries. Dashboard assets moved to docs/.
5. **Built control-panel.html**: 33KB self-contained dark-theme dashboard with 8 repo tabs, pipeline gauges, phase gates, HF Space status, fixes timeline, infrastructure overview. Auto-refreshes from rag-storage.
6. **Improved entrypoint.sh**: Added REST API readiness check, 10 login retries, verbose logging, CLI fallback import, post-setup webhook verification.
7. **Deployed to HF Space**: Quantitative webhook works (200). Standard responds but "Unable to generate answer" (Jina issue). Orchestrator + PME still 404.
8. **Saved HF_TOKEN_2**: Second HF account for potential second Space.

#### Current HF Space status (after deploy):
- **healthz**: HTTP 200
- **Standard**: HTTP 200 — "Unable to generate answer" (Jina key not resolving or IP-blocked)
- **Graph**: Timeout at 10s (likely works but slow)
- **Quantitative**: HTTP 200 — WORKING
- **Orchestrator**: HTTP 404 — workflow not activated (credential/sub-workflow issue)
- **PME**: HTTP 404 — workflow not activated

#### What was NOT completed:
- [ ] Fix Standard pipeline (Jina $env expression not resolving or key IP-blocked from HF Space)
- [ ] Fix Orchestrator 404 (needs debug of setup-workflows.py activation)
- [ ] Fix PME 404 (same)
- [ ] Clean rag-dashboard satellite repo (still has old mon-ipad files — needs full reset)
- [ ] Clean other satellite repos (rag-tests, rag-data-ingestion also have old files)
- [ ] Push control-panel.html to rag-dashboard for Vercel deployment
- [ ] Large-scale Phase 2 testing
- [ ] PostgreSQL migration (deferred)
- [ ] Second HF Space for parallel execution

### Phase 2 Cumulative Results
| Pipeline | Tested | Total | Accuracy | Status |
|----------|--------|-------|----------|--------|
| Standard | 579 | 1000 | ~36% | STOPPED — Jina issue |
| Graph | 500 | 500 | 78.0% | COMPLETE |
| Quantitative | 500 | 500 | 92.0% | COMPLETE |
| Orchestrator | 57 | 1000 | 0% | BROKEN — 404 |
| PME Gateway | 0 | — | — | NOT ACTIVATED |

### OpenRouter Keys (7 total — all verified working)
| Key | Pipeline | Status |
|-----|----------|--------|
| OPENROUTER_API_KEY | Main/Fallback | OK |
| OPENROUTER_KEY_STANDARD | Standard | OK |
| OPENROUTER_KEY_GRAPH | Graph | OK |
| OPENROUTER_KEY_QUANTITATIVE | Quantitative | OK |
| OPENROUTER_KEY_ORCHESTRATOR | Orchestrator | OK |
| OPENROUTER_KEY_PME | PME | OK |
| OPENROUTER_KEY_SPARE | Spare | OK |

### New Repos
| Repo | Created | Purpose |
|------|---------|---------|
| rag-storage | Session 44 | Centralized data archive (per-repo dirs + global metrics) |

### Architecture (current)
- **Workflows**: 13 JSONs with ALL keys as `$env.*` refs (zero hardcoded) in `n8n/live/`
- **Credentials**: Auto-created by setup-workflows.py (Postgres, httpHeaderAuth, Pinecone, Neo4j, Redis)
- **Boot**: SQLite + single process + CLI fallback import + activation
- **Deploy**: `scripts/deploy-hf-space.sh` — copies from n8n/live/ (now env-var clean), sets 19 HF secrets, pushes
- **Dashboard**: `docs/control-panel.html` — polls rag-storage for live data
- **Storage**: `rag-storage` repo — per-repo dirs (7) + global status/fixes/summary
- **mon-ipad**: Lean pilotage (~50MB tracked, removed 1.5GB website code)

### Git Commits This Session
- `677c8ec` fix: migrate n8n/live/ to env vars — deploy overwrite bug
- `67731fc` refactor: remove website source code from mon-ipad (lives in satellites)
- `4f0b71a` fix: add CLI fallback + verbose logging to entrypoint
- `4b98db9` feat: multi-repo control panel dashboard + updated repos config

---

### OPTIMAL PROMPT FOR SESSION 45 — COPY-PASTE THIS TO START

```
Session 45. Read CLAUDE.md first then:

1. cat directives/session-state.md
2. cat docs/status.json
3. cat directives/status.md

=== PRIORITY 1 — FIX SATELLITE REPOS (ALL BROKEN) ===
The satellite repos (rag-dashboard, rag-tests, rag-data-ingestion) still contain
ALL old mon-ipad files from before the Session 41 separation. They need to be
properly cleaned — each should contain ONLY its own code.

rag-dashboard: Should ONLY have docs/control-panel.html + index.html.
  Currently has ALL old mon-ipad directories (eval/, scripts/, n8n/, etc.).
  Fix: gh api + reset with only dashboard files.

rag-tests: Should ONLY have eval scripts + test datasets.
  Fix: check what's there, remove non-test files.

rag-data-ingestion: Should ONLY have ingestion scripts + configs.

=== PRIORITY 2 — FIX HF SPACE WEBHOOKS ===
Current state:
- Quantitative: HTTP 200 (WORKING)
- Standard: "Unable to generate answer" — Jina embeddings failing
  - Cause: either $env.JINA_API_KEY not resolving in n8n, or Jina key blocked from HF IP
  - Debug: check if env var is set in container (entrypoint.sh exports it)
  - Fix: may need to use credential-based auth instead of $env expression for Jina
- Orchestrator: HTTP 404 — workflow not activated
  - Cause: setup-workflows.py import/activation failing for this workflow
  - Debug: check entrypoint logs (/tmp/setup-workflows.log inside container)
  - The orchestrator references sub-workflows by ID — IDs change on import
- PME: HTTP 404 — same as orchestrator

entrypoint.sh has verbose logging + CLI fallback + post-setup webhook check.
The CLI fallback (n8n import:workflow) works for simple workflows but may fail for
orchestrator (sub-workflow references).

=== PRIORITY 3 — DEPLOY DASHBOARD TO VERCEL ===
Push docs/control-panel.html to rag-dashboard repo.
The dashboard auto-refreshes from rag-storage GitHub raw URLs.

=== PRIORITY 4 — SCALING ARCHITECTURE ===
User has a second HF account (HF_TOKEN_2 in .env.local).
Could create a second HF Space for PME workflows + ingestion.
Architecture:
  HF Space 1: Standard + Graph + Quantitative + Orchestrator
  HF Space 2: PME + Ingestion + Enrichment
  Each with their own n8n instance.

=== KEY FILES ===
- hf-space/entrypoint.sh — boot script with CLI fallback
- hf-space/setup-workflows.py — credential creation + workflow import
- n8n/live/*.json — workflow definitions (all use $env.* now)
- scripts/deploy-hf-space.sh — deployment script
- docs/control-panel.html — new multi-repo dashboard
- scripts/sync-to-storage.sh — sync data to rag-storage

=== NEW REPO ===
rag-storage: github.com/LBJLincoln/rag-storage
  Per-repo data archive + global metrics.
  Sync: bash scripts/sync-to-storage.sh

=== MULTI-KEY OPENROUTER (7 keys — all verified) ===
OPENROUTER_KEY_STANDARD, _GRAPH, _QUANTITATIVE, _ORCHESTRATOR, _PME, _SPARE + main

=== JINA KEY ===
JINA_API_KEY in .env.local — works from non-VM IPs (VM IP blocked by Cloudflare 1010).
Must be tested from HF Space, not from VM.

source .env.local before ANY script.
```
