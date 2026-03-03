# Incremental Evaluation Plan — SOTA 2026

> Last updated: 2026-03-03T21:30:00Z

## Vue d'ensemble

```
PHASE A : RAG Pipeline Iteration (Phases 1-5)
  Phase 1 (200q) → Phase 2 (1,000q) → Phase 3 (~10Kq) → Phase 4 (~100Kq) → Phase 5 (1M+q)

PHASE B : SOTA 2026 Research Analysis
  Analyse des meilleurs papiers de recherche → Identification des techniques SOTA
  → Design des pipelines d'ingestion/enrichissement optimises

PHASE C : Ingestion & Enrichment Pipelines
  Nouvelles BDD pour ingestion/enrichment → Tests iteratifs → Production
```

---

## PHASE A : RAG Pipeline Iteration

### Phase 1 — Baseline (200 questions)

**Objectif** : Atteindre les targets sur 200 questions curated via iteration 1/1 → 5/5 → 10/10.

| Pipeline | Questions | Source | Target |
|----------|-----------|--------|--------|
| Standard | 50 | `datasets/phase-1/standard-orch-50x2.json` | >= 85% |
| Graph | 50 | `datasets/phase-1/graph-quant-50x2.json` | >= 70% |
| Quantitative | 50 | `datasets/phase-1/graph-quant-50x2.json` | >= 85% |
| Orchestrator | 50 | `datasets/phase-1/standard-orch-50x2.json` | >= 70% |
| **Overall** | **200** | | **>= 75%** |

**Etat des BDD** :
- Pinecone : 10,411 vecteurs, 12 namespaces (PRET)
- Neo4j : 19,788 nodes, 76,717 relations (PRET pour Phase 1)
- Supabase : ~17,000+ lignes, 40 tables (PRET pour Phase 1)

**Exit criteria** :
- Tous les pipelines >= leur target
- 3 iterations stables consecutives (pas de regression)
- Eval complete 200q passee

**STATUS : PASSED** (20 fev 2026, session 30). Overall 83.9% >= 75%.

### Phase 2 — Expand (1,000 questions) — EN COURS

**Prerequis** : Phase 1 gates passees. **PASSED 20 fev 2026.**

**STATUS ACTUEL (22 fev 2026)** :
| Pipeline | Tested | Total | Accuracy | Status |
|----------|--------|-------|----------|--------|
| Standard | 579 | 1000 | ~36% | STOPPED (HF Space 404) |
| Graph | 500 | 500 | 78.0% | COMPLETE |
| Quantitative | 500 | 500 | 92.0% | COMPLETE |
| Orchestrator | 57 | 1000 | 0% | BROKEN (workflow bug) |

**BLOCKER** : HF Space ALL WEBHOOKS 404 after rebuild. Standard + Orchestrator cannot continue.

| Pipeline | Questions | Datasets HuggingFace |
|----------|-----------|---------------------|
| Graph | 500 | musique (200), 2wikimultihopqa (300) |
| Quantitative | 500 | finqa (200), tatqa (150), convfinqa (100), wikitablequestions (50) |

**Ingestion necessaire** :
- Neo4j : extraction d'entites depuis les contextes des questions (~2,500 entites)
- Supabase : creation de tables dynamiques pour les donnees financieres (~10,000 lignes)

**Exit criteria** : Graph >= 60%, Quant >= 70%, pas de regression Phase 1.

### Phase 3 — Scale (~10,700 questions)

**Prerequis** : Phase 2 gates passees.

Tous les 16 datasets HuggingFace (3 tiers).

| Tier | Pipeline | Datasets | Questions |
|------|----------|----------|-----------|
| 1 | Graph | musique, 2wikimultihopqa, hotpotqa | 1,500 |
| 2 | Quantitative | finqa, tatqa, convfinqa, wikitablequestions | 500 |
| 3 | Standard | frames, triviaqa, squad_v2, popqa, msmarco, asqa, narrativeqa, pubmedqa, natural_questions | 8,700 |

**Exit criteria** : Standard >= 75%, Graph >= 55%, Quant >= 65%, Orchestrator >= 60%.

### Phase 4 — Full HF (~100K questions)

**Prerequis** : Phase 3 gates passees. Echantillons 10x plus grands.

**Infrastructure possible** :
- Pinecone : ~100K vecteurs (free tier suffisant avec serverless)
- Neo4j : ~15K entites (Aura Free = 50K max, suffisant)
- Supabase : ~50K lignes (free tier = 500MB, suffisant)

**Exit criteria** : Pas de regression vs Phase 3.

### Phase 5 — Million+ (production)

**Prerequis** : Phase 4 gates passees. Infrastructure payante requise.

**Cout estime** : $215-455/mois (Pinecone Standard + Neo4j Pro + Supabase Pro).

---

## TRIGGERS DOWNSTREAM — Actions déclenchées par les phases

### Tests site ETI (4 secteurs)

**Trigger** : Phase 4 PASSED + rag-data-ingestion COMPLETE

| Condition | Pourquoi |
|-----------|----------|
| Phase 4 PASSED | Prouve que les pipelines RAG sont fiables à l'échelle (100K questions). Lancer les tests site sur des pipelines non validés donne des faux négatifs. |
| rag-data-ingestion COMPLETE | Garantit que les données sectorielles (finance, santé, industrie, juridique) sont présentes dans Pinecone, Neo4j et Supabase. Sans données, les chatbots ETI répondent dans le vide. |

**Action** : Lancer les tests E2E des sites ETI :
- `nomos-ai-pied.vercel.app` (4 secteurs)
- `nomos-pme-connectors-alexis-morets-projects.vercel.app` (connecteurs PME)

**Vérification** :
```bash
python3 eval/phase_gates.py --trigger eti_site_tests --repo-complete rag-data-ingestion
```

**Historique** : Anciennement déclenché après Phase 2. Modifié le 2026-03-03 (session 69) car Phase 2 ne teste que des benchmarks HF génériques, insuffisant pour valider les réponses sectorielles.

---

## PHASE B : SOTA 2026 Research Analysis

> **AVANT** de travailler sur l'ingestion/enrichissement, produire une analyse SOTA 2026 basee sur les meilleurs papiers de recherche.

### Objectif

Analyser les techniques de pointe 2025-2026 en RAG, ingestion, et enrichissement de donnees pour informer la conception des pipelines optimises.

### Papiers et techniques a analyser

| Domaine | Papiers cles | Technique |
|---------|-------------|-----------|
| **RAG avance** | RAPTOR, Self-RAG, CRAG | Retrieval adaptatif, arbre hierarchique |
| **Chunking** | Late Chunking, Contextual Retrieval | Chunking semantique, metadata enrichment |
| **Graph RAG** | Microsoft GraphRAG, KG-RAG | Community detection, hierarchical summarization |
| **Query routing** | Adaptive-RAG, RAG-Fusion | Classification de requete, fusion de resultats |
| **Embeddings** | Matryoshka, ColBERT v2 | Embeddings multi-resolution, late interaction |
| **Reranking** | Cohere Rerank v3, Cross-encoders | Reranking multi-stage |
| **Evaluation** | RAGAS, ARES | Metriques de qualite RAG |
| **Ingestion** | Unstructured.io, LangChain docs | Parsing multi-format, metadata extraction |

### Livrables attendus

1. **`docs/sota-analysis.md`** : Analyse complete avec recommendations
2. **Design des pipelines ingestion/enrichment optimises** base sur l'analyse
3. **Plan d'implementation** avec priorite des techniques a integrer

---

## PHASE C : Ingestion & Enrichment Pipelines

> **APRES** l'analyse SOTA et une fois les pipelines RAG valides (Phase 1 minimum).

### Workflows existants (importes depuis n8n)

| Workflow | ID n8n | Nodes | Role |
|----------|--------|-------|------|
| **Ingestion V3.1** | `15sUKy5lGL4rYW0L` | 28 | Ingestion de documents dans les BDD |
| **Enrichissement V3.1** | `9V2UTVRbf4OJXPto` | 29 | Enrichissement des donnees existantes |
| **Feedback V3.1** | `F70g14jMxIGCZnFz` | 13 | Boucle de feedback des resultats |
| **Benchmark V3.0** | `LKZO1QQY9jvBltP0` | 9 | Benchmark automatise |

### Plan

1. **Analyser** les workflows ingestion/enrichment importes (node-par-node)
2. **Creer de nouvelles BDD** specifiques pour ces pipelines si necessaire
3. **Appliquer les techniques SOTA** identifiees en Phase B
4. **Tester iterativement** (1/1 → 5/5 → 10/10) comme pour les pipelines RAG
5. **Valider** sur les datasets des phases suivantes

### Nouvelles BDD potentielles

| BDD | Usage | Service |
|-----|-------|---------|
| Cache Redis | Cache des embeddings et resultats frequents | Redis Cloud Free (30MB) |
| Document Store | Stockage de documents bruts pre-ingestion | Supabase Storage (free) |
| Metadata Index | Index des metadonnees de documents | Supabase table |
| Feedback Store | Historique des feedbacks et corrections | Supabase table |

---

## Etat actuel des BDD (verifie)

### Pinecone

| Namespace | Vecteurs | Phase |
|-----------|----------|-------|
| benchmark-squad_v2 | 1,000 | 3+ |
| benchmark-natural_questions | 1,000 | 3+ |
| benchmark-narrativeqa | 1,000 | 3+ |
| benchmark-hotpotqa | 1,000 | 3+ |
| (default) | 639 | 1 |
| benchmark-finqa | 500 | 2+ |
| benchmark-popqa | 1,000 | 3+ |
| benchmark-triviaqa | 1,000 | 3+ |
| benchmark-msmarco | 1,000 | 3+ |
| benchmark-frames | 824 | 3+ |
| benchmark-pubmedqa | 500 | 3+ |
| benchmark-asqa | 948 | 3+ |
| **Total** | **10,411** | Dimension: 1024 |

**Note** : Les vecteurs sont en dimension **1024** (Jina-embeddings-v3, dim=1024 confirmé).

### Neo4j (via n8n)
- **19,788 nodes, 76,717 relations** (Phase 1 actuel)
- Phase 2+ : +4,884 entities, +21,810 relations prévus

### Supabase (via n8n)
- ~17,000+ lignes, 40 tables
- Couverture Phase 1 + benchmark datasets ingeres
- Phase 2+ necessite ingestion des tables financieres HF

### Datasets locaux

| Fichier | Questions | Couverture |
|---------|-----------|------------|
| `datasets/phase-1/standard-orch-50x2.json` | 100 | Phase 1 |
| `datasets/phase-1/graph-quant-50x2.json` | 100 | Phase 1 |
| `datasets/phase-2/hf-1000.json` | 1,000 | Phase 2 (Graph 500 + Quant 500) |
| `datasets/phase-2/standard-orch-1000x2.json` | 2,000 | Phase 2 (Standard 1000 + Orch 1000) |
| `datasets/sectors/*.jsonl` | 7,609 | Secteurs (Finance 2250, Juridique 2500, BTP 1844, Industrie 1015) |
| **Manquant** | Phase 3-5 | A generer via `db/populate/push-datasets.py` |

---

## Workflows n8n (9 actifs apres audit session 18)

### Pipelines RAG (4) — Actifs
| Nom | ID Docker | Nodes | Status |
|-----|-----------|-------|--------|
| Standard RAG V3.4 | `TmgyRP20N4JFd9CB` | 23 | ON |
| Graph RAG V3.3 | `6257AfT1l4FMC6lY` | 26 | ON |
| Quantitative V2.0 | `e465W7V9Q8uK6zJE` | 25 | ON |
| Orchestrator V10.1 | `aGsYnJY9nNCaTM82` | 68 | ON |

### Support (5) — Mixte
| Nom | ID Docker | Nodes | Status |
|-----|-----------|-------|--------|
| Dashboard Status API | `KcfzvJD6yydxY9Uk` | — | ON |
| Benchmark V3.0 | `LKZO1QQY9jvBltP0` | 9 | ON |
| Ingestion V3.1 | `15sUKy5lGL4rYW0L` | 28 | OFF (pret) |
| Enrichissement V3.1 | `9V2UTVRbf4OJXPto` | 29 | OFF (pret) |
| Dataset Ingestion | `YaHS9rVb1osRUJpE` | 23 | OFF (pret) |

### Utilitaire
| Nom | ID Docker | Nodes | Status |
|-----|-----------|-------|--------|
| SQL Executor Utility | `22k9541l9mHENlLD` | 2 | ON |

### Supprimes (session 18, desactives session 20)
- Feedback V3.1 (`F70g14jMxIGCZnFz`) — desactive
- Monitoring & Alerting (`tLNh3wTty7sEprLj`) — desactive
- Orchestrator Tester (`m9jaYzWMSVbBFeSf`) — desactive
- RAG Batch Tester (`y2FUkI5SZfau67dN`) — desactive

---

## Projection de croissance des BDD

| Metrique | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Phase 5 |
|----------|---------|---------|---------|---------|---------|
| Pinecone vecteurs | 10,411 | 10,411 | ~15,000 | ~100,000 | ~500,000+ |
| Neo4j entites | 19,788 | ~25,000 | ~30,000 | ~50,000 | ~200,000+ |
| Neo4j relations | 76,717 | ~100,000 | ~120,000 | ~200,000 | ~400,000+ |
| Supabase lignes | ~17,000 | ~30,000 | ~50,000 | ~100,000 | ~500,000+ |
| Questions testees | 200 | 1,200 | ~11,500 | ~100,000 | ~2,200,000 |
