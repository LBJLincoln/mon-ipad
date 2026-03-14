# NOMOS STATUS — Single Source of Truth

> **Auto-updated by Claude Code each session. Dernière MAJ: 2026-03-12T12:15Z (Session 105)**
> **Objectif: +10% accuracy/jour. Docs > 3 jours = obsolètes et supprimables.**

---

## ÉTAT LIVE

| Composant | Status | Détail |
|-----------|--------|--------|
| **Pipelines RAG** | 4/4 UP | Standard ✓ Graph ✓ Quant ✓ Orchestrator ✓ |
| **HF Spaces** | S1 S3 S5 UP | S7 (LiteLLM) UP, S6 (Docling) UP, S9 (Ingest) UP |
| **Pinecone E5** | ~78K vectors | Target 100K (78%) |
| **Supabase** | 43K docs + 225 financials | 3,876 financial tables |
| **Neo4j** | 71,890 nodes | Entity 33K, SectorDoc 30K, Law 5.2K, Org 1.6K |

## ACCURACY (dernière eval)

| Pipeline | Finance | BTP | Juridique | Industrie | Objectif |
|----------|---------|-----|-----------|-----------|----------|
| **Standard** | ~38-50% | ~20% | ~80% | ~80% | ≥90% |
| **Graph** | ~85-90% | ~60% | ~70% | ~70% | ≥75% |
| **Quant** | ~98% | ~98% | N/A | N/A | ≥95% |
| **Orchestrator** | ~85% | ~50% | ~75% | ~75% | ≥85% |

**Bottleneck #1**: Standard Finance (keyword matching strict → faux négatifs)
**Bottleneck #2**: BTP tous pipelines (DATA GAP massif — pas de DTU/Eurocodes)

## PROCESSES EN COURS

| Process | PID | Status | Depuis |
|---------|-----|--------|--------|
| Agentic loop (30min cycles) | 906004 | Running, cycle 18, 8 no-improvement | Mar 11 20:58 |
| Monitor (5min) | 906738 | Running | Mar 11 20:58 |
| Agents (5 spécialisés) | 906739-43 | Running | Mar 11 20:58 |
| Continuous ingest (1h) | 1178647 | Running (Exa.AI 4 sectors) | Mar 12 07:47 |
| Mass eval Standard | 1220081 | Running 155/200 | Mar 12 09:50 |
| Mass eval Graph | 1220080 | Running ~done | Mar 12 09:50 |
| Eval blast (50q/run) | 1253793 | Running | Mar 12 11:17 |
| Exa.AI BTP | 1258980 | Running | Mar 12 ~11:30 |
| Exa.AI Juridique | 1257580 | Running | Mar 12 ~11:15 |

## SÉPARATION RAG vs INGESTION

```
RAG PIPELINES (query-time)          INGESTION (data-time)
━━━━━━━━━━━━━━━━━━━━━━━━          ━━━━━━━━━━━━━━━━━━━━━
Standard → S1/S3/S5                Exa.AI → VM scripts
Graph → S1/S3/S5                   Docling → S6 HF Space
Quant → S1/S3/S5                   fast-ingest → Pinecone E5
Orchestrator → S1/S3/S5            Neo4j enrichment → VM
                                   n8n Ingestion V4.0 (S1)
                                   n8n Enrichment V4.0 (S1)
         ↓ READ                           ↓ WRITE
    ┌─────────────────────────────────────────┐
    │  Pinecone │ Supabase │ Neo4j            │
    └─────────────────────────────────────────┘
```

**100% séparés.** RAG ne modifie jamais les DBs. Ingestion n'appelle jamais les webhooks RAG.

## EVAL QUESTIONS — TRAÇABILITÉ

| Source | Questions | Tracking Origin | Lien BDD |
|--------|-----------|----------------|----------|
| Standard templates | 7,102 | ✓ topic, category | ✗ Pas de doc_id |
| Graph Neo4j entities | 5,946 | ✓ entity name | ✗ Pas de node_id |
| Quant financials | 15,996 | ✓ company+year | ✗ Pas de FK vers table |
| Expert discovery | 280 | ✓✓ URL+hash+domain | ✓ source_hash |
| Orchestrator | 520 | ✓ category | ✗ |
| **TOTAL** | **29,844** | Partiel | **MANQUE: question_source_map** |

### CE QUI MANQUE (recommandations utilisateur)
1. **Table `question_source_map`** — lier chaque question à son document/vector source
2. **Traçabilité Exa.AI→question** — les 78K vectors n'ont pas de lien vers les questions générées
3. **Phases autonomes progressives** — l'agentic loop est bloquée 8 cycles sans progression
4. **Dashboard live Vercel** — deploye mais snapshot statique, pas de refresh automatique

## WORKFLOWS N8N ACTIFS (10)

| ID | Nom | Rôle |
|----|-----|------|
| 9FQdtx38JLPiT3Hx | Standard RAG V3.5 | Pipeline RAG Standard |
| 6257AfT1l4FMC6lY | Graph RAG V3.7 | Pipeline RAG Graph |
| cjhEhVs0KV1ExHqX | Quantitative V3.1 | Pipeline RAG Quant |
| qOSaFFrqO8Jb4VGb | Orchestrator V13 | Routage intelligent |
| Yqw7Pzn0e7m0C6i3 | Auto-Healer V1.2 | Santé automatique |
| AH3eXOmgxt5cOd93 | Error Trigger | Monitoring erreurs |
| nh1D4Up0wBZhuQbp | Ingestion V4.0 | Ingestion documents |
| ORa01sX4xI0iRCJ8 | Enrichment V4.0 | Neo4j enrichment |
| wa2kDSyrTeFZPHyq | Dashboard Status API | API status |
| xNydGvvBkCyB4GhW | Debug Status | Debug endpoint |

## FICHIERS DE RÉFÉRENCE (après nettoyage)

| Fichier | Rôle | MAJ |
|---------|------|-----|
| **STATUS.md** (CE FICHIER) | Vue exécutive unique | Chaque session |
| **CLAUDE.md** | Instructions système | Quand rules changent |
| **directives/PROJECT-STATE.md** | Snapshot session détaillé | Après milestone |
| **technicals/DEBUG-PLAYBOOK.md** | 90+ fixes documentés | Pendant debug |
| **technicals/INFRASTRUCTURE.md** | Stack technique | Quand infra change |
| **technicals/PROGRESSION-PLAN.md** | Stages 0-6, diagnostic | Quand stratégie change |
| **docs/PILOTAGE.md** | Commandes Termius/tmux | Quand ops change |

**7 docs essentiels.** Tout le reste est archivé dans `docs/archive/`.

## RECOMMANDATIONS UTILISATEUR NON IMPLÉMENTÉES

1. ✗ **Codespace ALWAYS ALIVE avec Docling** — Demandé depuis 1+ mois
2. ✗ **8 RAG pipelines (4×2 prod+test)** — Pas de mirror test
3. ✗ **Redis queue workers** — Upstash creds existent, workers pas construits
4. ✗ **Metrics par question dans n8n** — Pas implémenté
5. ✗ **Table question_source_map** — Traçabilité question→document manquante
6. ✗ **Dashboard live auto-refresh** — Vercel = snapshot statique
7. ✓ Commander dashboard → https://lbjlincoln.github.io/rag-dashboard/docs/
8. ✓ Continuous Exa.AI→Ingestion daemon → `ops/continuous-ingest.py`
9. ✓ 29K+ eval questions (objectif 10K dépassé)
10. ✓ Pipelines séparés RAG vs Ingestion

## PROCHAINES ACTIONS

1. **Débloquer l'agentic loop** — 8 cycles sans progression, probablement stuck sur timeouts résolus
2. **Ingérer DTU/Eurocodes pour BTP** — Data gap critique
3. **Implémenter question_source_map** — Traçabilité complète
4. **Dashboard Vercel live** — Connecter à health-status.json via API
5. **Standard accuracy** — Passer de keyword matching → semantic scoring
