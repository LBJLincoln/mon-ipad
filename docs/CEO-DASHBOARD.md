# NOMOS AI — CEO Dashboard
> **Session 77** | 7 mars 2026 | Refresh: avant chaque session

---

## Status Global: PHASE 4 READY

| KPI | Valeur | Tendance |
|-----|--------|----------|
| Phases completees | **3 / 5** | Phase 4 starting |
| Accuracy leader | **Standard 87.5%** (8K questions) | Stable |
| Questions testees | **11,000+** | +8K en 2 semaines |
| Vectors en production | **53,000+** | Pinecone x2 index |
| Sites live | **4** Vercel | All UP |
| Commits totaux | **1,100+** | 77 sessions |

---

## Pipelines RAG

| Pipeline | P1 (200q) | P2 (1Kq) | P3 (10Kq) | P4 (100Kq) | Status |
|----------|-----------|----------|-----------|------------|--------|
| **Standard** | 85.5% | 36%* | **87.5%** | -- | READY |
| **Graph** | 78.0% | 78.0% | **40.9%** | -- | ACCEPTED |
| **Quant** | 92.0% | 92.0% | **95.2%** | -- | READY |
| **Orchestrator** | 80.0% | 0% | -- | -- | ON HOLD |

*P2 Standard stopped early (HF Space issues, not accuracy)

---

## 7 Repos — Etat

| Repo | Role | Completion | Bloqueur | Next Action |
|------|------|------------|----------|-------------|
| **mon-ipad** | Pilotage | 90% | -- | Phase 4 datasets + eval |
| **rag-tests** | Evaluation | 75% | Phase 4 datasets | Generate 100K questions |
| **rag-data-ingestion** | Donnees | 60% | Finance/Juridique Neo4j+Supabase | Ingest sector data |
| **rag-website** | Site ETI | 50% | Waiting rag-data-ingestion | Connect chatbots post-P4 |
| **rag-dashboard** | Metriques | 85% | -- | Add Phase 4 tracking |
| **rag-pme-connectors** | Site PME | 70% | -- | Polish + real integrations |
| **rag-pme-usecases** | Use cases | 80% | -- | Content updates |

---

## Infra

| Composant | Status | Capacite |
|-----------|--------|----------|
| HF Space #1 (n8n) | UP | 3/4 pipelines actifs |
| HF Space #7 (LiteLLM) | UP | 9 modeles, 13 API keys |
| Pinecone | UP | 53K/200K vectors (27%) |
| Neo4j | UP | 71K/200K nodes (35%) |
| Supabase | UP | 12K rows / 500MB |
| VM Google Cloud | UP | 969MB RAM, pilotage only |
| LLM (free tier) | UP | 6 OpenRouter + 5 Groq keys |

---

## Estimation Phase 4 + Ingestion

| Tache | Volume | Throughput estime | Duree |
|-------|--------|-------------------|-------|
| **Phase 4 Standard** | 50K questions | ~800 q/hr (batch=16) | **~3 jours** |
| **Phase 4 Graph** | 20K questions | ~400 q/hr (batch=12) | **~2 jours** |
| **Phase 4 Quant** | 20K questions | ~1,500 q/hr (batch=8, 8s/q) | **~14 heures** |
| **Dataset generation** | Scripts + HF download | -- | **~4 heures** |
| **rag-data-ingestion** | Finance+Juridique→DBs | Direct Python scripts | **~1-2 jours** |
| **Total estimate** | | Parallel pipelines | **~5-7 jours** |

*Avec max parallelisme (3 pipelines simultanes, batch sizing, 429 rotation)*

---

## Chemin Critique → Production

```
MAINTENANT                                          PRODUCTION
    |                                                    |
    v                                                    v
[Phase 4 Eval]──→[rag-data-ingestion]──→[ETI Website]──→[Phase 5]
  ~5-7 jours         ~1-2 jours          ~1 semaine      Scale
    |                     |                    |
    |   Standard 50K      |  Finance→Supabase  |  Connect chatbots
    |   Graph 20K         |  Juridique→Neo4j   |  4 secteurs live
    |   Quant 20K         |  Enrichment fix    |  E2E tests
```

---

## Tooling (Session 77)

| Outil | Version | Nouveaute |
|-------|---------|-----------|
| Claude Code | **2.1.71** | /simplify, /batch, auto-memory |
| Claude Opus | **4.6** | Main brain |
| Claude Sonnet | **4.6** | Delegation (was 4.5) |
| MCP Servers | 4 actifs | Pinecone, Cohere, HF, Jina |
| Termius snippet | `bash ~/mon-ipad/scripts/claude-session.sh` | Quick launch |

---

## Risques

| Risque | Impact | Mitigation |
|--------|--------|------------|
| Free tier LLM rate limits | Ralentit Phase 4 | 13 API keys rotation |
| HF Space sleep/rebuild | Perd config n8n | n8n/sync.py auto-restore |
| Neo4j data gaps (Graph) | 40.9% accuracy | Accept + improve post-P4 |
| VM RAM (969MB) | MCP servers limited | Pilotage only, no compute |

---

*Auto-genere Session 77. Source: `mon-ipad/docs/CEO-DASHBOARD.md`*
