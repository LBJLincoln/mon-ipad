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

### Infrastructure State
| Component | Status | Note |
|-----------|--------|------|
| HF Space | **REBUILDING** | Restart triggered, all webhooks down |
| VM | **PILOTAGE ONLY** | MCP servers active |
| GH Actions | **WORKING** | eval-1000q.yml completed successfully |
| Codespaces | **AVAILABLE** | Not yet utilized this session |

### Webhook Status (as of 22:00 UTC+1)
| Pipeline | HTTP Code | Status |
|----------|-----------|--------|
| Standard | 000 | TIMEOUT — HF Space rebuilding |
| Graph | 000 | TIMEOUT — HF Space rebuilding |
| Quantitative | 000 | TIMEOUT — HF Space rebuilding |
| Orchestrator | 000 | TIMEOUT — HF Space rebuilding |
| PME Gateway | 000 | TIMEOUT — HF Space rebuilding |

### Key Findings from GH Actions Eval
- **Graph 78% → 22%**: Major regression. Needs investigation — possible Phase 2 question format mismatch or HyDE node failure
- **Standard 92% → 80%**: Moderate drop. May be harder Phase 2 questions
- **Quantitative 0%**: Init & ACL node was hot-patched to accept `question` field but still fails
- **Orchestrator 0%**: Returns empty body — sub-workflow calls broken
- **PME Gateway 0%**: Not properly activated/configured

### BLOCKERS
1. **HF Space rebuild** — All webhooks down until rebuild completes and workflows activate
2. **Graph accuracy regression** — 78% → 22%, needs root cause analysis
3. **Quantitative still broken** — 0% despite hot-patch fix
4. **Orchestrator empty body** — Sub-workflow execution mechanism broken

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
