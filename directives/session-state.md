# Session State — 24 Fevrier 2026 (Session 59)

> Last updated: 2026-02-25T00:15:00+01:00

## Current Status: POST-RECOMPOSITION AUDIT COMPLETE — Critical gaps identified in pme-connectors + data-ingestion

### Session 59 Progress

1. **GH Actions eval completed** (100q per pipeline):
   - Standard: **80/100 = 80.0%** (was 92% Phase 1 — slight drop)
   - Graph: **11/50 = 22.0%** (was 78% Phase 1 — MAJOR regression)
   - Quantitative: **0/12 = 0.0%** (12 questions attempted, all failed)
   - Orchestrator: **0/12 = 0.0%** (12 errors)
   - PME Gateway: **0/11 = 0.0%** (11 errors)

2. **Session Intelligence System deployed** (Session 58):
   - `scripts/session-intelligence.py` — 40 sessions analyzed, 1022 commits, 59 fixes, 12 recurring issues
   - `scripts/node-tracker.py` — 98 nodes tracked across 35 executions
   - Reports: `logs/session-intelligence-report.json`, `logs/node-tracker-report.json`
   - CLAUDE.md Rules 24-26 added (intelligence first, snapshot after fix, hot-patch via REST)

3. **Working workflow snapshots saved** (Session 58):
   - `snapshot/working-session58/` — 4 validated workflow JSONs for instant rollback

4. **File cleanup executed** (Session 59):
   - Deleted 180 old db-snapshots (kept latest 5)
   - Deleted old diagnostics, mass-test files, stale analyses
   - Cleaned 109 old error logs (kept Feb 22-24)
   - Trimmed pipeline-results to latest 5 per pipeline (70→33)

5. **HF Space restart triggered** — Stage: BUILDING (as of 22:15 UTC+1)

### Infrastructure State (updated 22:45 UTC+1)
| Component | Status | Note |
|-----------|--------|------|
| HF Space | **RUNNING** | Rebuilt, webhooks active for Standard+Graph |
| VM | **PILOTAGE ONLY** | MCP servers active |
| GH Actions | **WORKING** | eval-1000q.yml runs completed |
| Codespaces | **AVAILABLE** | 1 shutdown codespace (rag-tests-eval) |

### Webhook Status (as of 22:45 UTC+1)
| Pipeline | HTTP Code | Status |
|----------|-----------|--------|
| Standard | 200 | WORKING — real answers, 78% accuracy |
| Graph | 200 | WORKING — real answers, 26% accuracy (hard multi-hop questions) |
| Quantitative | 200 | PARTIAL — returns NO_ANSWER (data retrieval broken, not auth) |
| Orchestrator | 200 | BROKEN — empty body (sub-workflow chain fails silently) |
| PME Gateway | OFF | Can't activate ("Could not find property option" validation error) |

### Latest GH Actions Eval (run 22370664312)
| Pipeline | Tested | Correct | Accuracy | Issue |
|----------|--------|---------|----------|-------|
| Standard | 50 | 39 | **78.0%** | Working. Hard Phase 2 questions lower accuracy |
| Graph | 50 | 13 | **26.0%** | Working. Multi-hop questions need precise entity resolution |
| Quantitative | 20 | 0 | **0.0%** | NO_ANSWER — SQL generation not producing queries |
| Orchestrator | 20 | 0 | **0.0%** | 20 errors — sub-workflow execution chain broken |
| PME | 20 | 0 | **0.0%** | 20 errors — workflow can't activate |

### Root Cause Analysis (session 59 continued)
- **Graph 26%**: NOT a regression. Phase 2 questions are much harder multi-hop (MuSiQue/2WikiMultiHop). Answers are reasonable but imprecise (e.g., "Slovakia" vs "Senica District")
- **Standard 78%**: Working correctly. 22% failures are harder Phase 2 questions
- **Quantitative 0%**: Init & ACL node fixed to accept query, but downstream SQL/data retrieval returns NO_ANSWER consistently. Supabase data retrieval chain broken
- **Orchestrator 0%**: Empty body. Execute sub-workflows → some fail → error handler uses respondToWebhook which can't find webhook context in error trigger path
- **PME 0%**: Workflow validation error prevents activation ("Could not find property option" in n8n v2.8.4)

### BLOCKERS
1. **Quantitative data retrieval** — Pipeline accepts queries but SQL generation returns nothing
2. **Orchestrator sub-workflow chain** — Error handler can't send response (n8n limitation)
3. **PME Gateway activation** — Node parameter validation error prevents workflow activation

### Session 59b — Post-Recomposition Audit (Feb 25)

6. **Deep audit of rag-pme-connectors**:
   - 15 connectors = LANDING PAGE ONLY (static icons, zero integration code, zero SDKs)
   - Chatbot = REAL (proxies to Orchestrator RAG, works)
   - 1 API route only (n8n proxy). No OAuth, no connector backends
   - n8n PME workflows NOT in this repo (zero JSON files)

7. **Deep audit of rag-data-ingestion**:
   - ingestion.json = REAL CODE (30 nodes, BM25, NER, chunking) but handles 11 file types NOT 500
   - enrichment.json = BROKEN (placeholder URLs: internal-api.company.com)
   - "500 file types x 4 sectors" = MISSING (5 referenced scripts DO NOT EXIST)
   - Dataset download scripts = FUNCTIONAL (4 real Python scripts)
   - Docker/Codespace infra = FUNCTIONAL but no workflow import script
   - Test environment = MISSING (no pytest, no CI, no test data)

8. **All repos committed + pushed + CLAUDE.md synced**

### PRIORITY #1 NEXT SESSION — Project Chatbot (all sites)

**Concept** : Un chatbot client-facing sur chaque site web, connecté au repo mon-ipad (source de vérité unique). Le chatbot peut répondre à toute question sur le projet Nomos AI, ses capacités, les repos, les déploiements.

**Architecture** :
- **Knowledge source** : repo mon-ipad (directives/, technicals/, docs/, CLAUDE.md)
- **n8n workflow** : 1 workflow dédié (~8 noeuds) — webhook → RAG over mon-ipad content → LLM → response
- **Frontend** : Copier le pattern TermiusModal (déjà fonctionnel dans rag-pme-connectors) sur chaque site
- **Déploiement** : 1 webhook, répliqué sur ETI site, PME Connectors, PME Use Cases, Dashboard

**Dataset de test : 1000 questions** (à créer) :
- Range : des plus basiques ("C'est quoi Nomos AI?") aux plus complexes ("Quelle est l'architecture de réplication cross-index entre Pinecone et Neo4j pour le pipeline Graph?")
- **3 catégories d'utilisateurs** :
  - **ETI** (grandes entreprises) — questions stratégiques, ROI, intégration SI, conformité, scale
  - **PME** (petites/moyennes) — questions pratiques, connecteurs, automatisation, coût, simplicité
  - **Individus** — questions basiques, démo, curiosité, cas d'usage personnel
- Couvre : tous les 7 repos, finalité du projet, déploiements possibles, capacités par secteur (BTP, Finance, Juridique, Industrie)

**Structure 1000q** :
| Catégorie | Facile | Moyen | Complexe | Total |
|-----------|--------|-------|----------|-------|
| ETI | 100 | 100 | 130 | 330 |
| PME | 100 | 100 | 130 | 330 |
| Individus | 130 | 100 | 110 | 340 |
| **Total** | **330** | **300** | **370** | **1000** |

### Other Next Steps
1. **rag-data-ingestion**: enrichment.json placeholder nodes disabled (DONE), build 500-filetype scripts, add tests
2. **HF Space**: Test webhooks (healthz was 200 but webhooks still timing out)
3. **Phase 2**: Unblock Standard + Orchestrator pipelines

### Dataset Files (unchanged)
| File | Pipelines | Questions |
|------|-----------|-----------|
| datasets/phase-2/hf-1000.json | graph(500), quant(500) | 1000 |
| datasets/phase-2/graph-quant-expansion-500x2.json | graph(500), quant(500) | 1000 |
| datasets/phase-2/standard-orch-1000x2.json | standard(1000), orch(1000) | 2000 |
| datasets/phase-2/pme-gateway-1000.json | pme-gateway(1000) | 1000 |
| **TOTAL** | **5 pipelines** | **5000** |
