# Incremental Evaluation Plan — SOTA 2026

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
- Neo4j : 110 entites, 151 relations (PRET pour Phase 1)
- Supabase : 88 lignes, 5 tables (PRET pour Phase 1)

**Exit criteria** :
- Tous les pipelines >= leur target
- 3 iterations stables consecutives (pas de regression)
- Eval complete 200q passee

### Phase 2 — Expand (1,000 questions)

**Prerequis** : Phase 1 gates passees.

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
| **Ingestion V3.1** | `nh1D4Up0wBZhuQbp` | 28 | Ingestion de documents dans les BDD |
| **Enrichissement V3.1** | `ORa01sX4xI0iRCJ8` | 29 | Enrichissement des donnees existantes |
| **Feedback V3.1** | `iVsj6dq8UpX5Dk7c` | 13 | Boucle de feedback des resultats |
| **Benchmark V3.0** | `qUm28nhq62SxVWHe` | 9 | Benchmark automatise |

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
| **Total** | **10,411** | Dimension: 1536 |

**Note** : Les vecteurs sont en dimension 1536 (pas 1024). Verifier la coherence avec le modele d'embedding utilise.

### Neo4j (via n8n)
- 110 entites, 151 relations
- Couverture Phase 1 uniquement
- Phase 2+ necessite extraction d'entites depuis les contextes HF

### Supabase (via n8n)
- 88 lignes, 5 tables
- Couverture Phase 1 uniquement
- Phase 2+ necessite ingestion des tables financieres HF

### Datasets locaux

| Fichier | Questions | Couverture |
|---------|-----------|------------|
| `datasets/phase-1/standard-orch-50x2.json` | 100 | Phase 1 |
| `datasets/phase-1/graph-quant-50x2.json` | 100 | Phase 1 |
| `datasets/phase-2/hf-1000.json` | 1,000 | Phase 2 |
| **Manquant** | Phase 3-5 | A generer via `db/populate/push-datasets.py` |

---

## Workflows n8n complets (13 actifs)

### Pipelines RAG (4)
| Nom | ID | Nodes |
|-----|-----|-------|
| Standard RAG V3.4 | `IgQeo5svGlIAPkBc` | 23 |
| Graph RAG V3.3 | `95x2BBAbJlLWZtWEJn6rb` | 26 |
| Quantitative V2.0 | `E19NZG9WfM7FNsxr` | 25 |
| Orchestrator V10.1 | `ALd4gOEqiKL5KR1p` | 68 |

### Ingestion/Enrichment (4)
| Nom | ID | Nodes |
|-----|-----|-------|
| Ingestion V3.1 | `nh1D4Up0wBZhuQbp` | 28 |
| Enrichissement V3.1 | `ORa01sX4xI0iRCJ8` | 29 |
| Feedback V3.1 | `iVsj6dq8UpX5Dk7c` | 13 |
| Benchmark V3.0 | `qUm28nhq62SxVWHe` | 9 |

### Benchmark/Support (5)
| Nom | ID | Nodes |
|-----|-----|-------|
| Dataset Ingestion Pipeline | `L8irkzSrfLlgt2Bt` | 23 |
| Monitoring & Alerting | `8a72LTsYvsH2X79d` | 19 |
| Orchestrator Tester | `7UMkzbjkkYZAUzPD` | 15 |
| RAG Batch Tester | `QCHKdqnTIEwEN1Ng` | 16 |
| SQL Executor Utility | `3O2xcKuloLnZB5dH` | 2 |

---

## Projection de croissance des BDD

| Metrique | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Phase 5 |
|----------|---------|---------|---------|---------|---------|
| Pinecone vecteurs | 10,411 | 10,411 | ~15,000 | ~100,000 | ~500,000+ |
| Neo4j entites | 110 | ~2,500 | ~4,000 | ~15,000 | ~50,000+ |
| Neo4j relations | 151 | ~3,000 | ~5,000 | ~20,000 | ~75,000+ |
| Supabase lignes | 88 | ~10,000 | ~12,000 | ~50,000 | ~200,000+ |
| Questions testees | 200 | 1,200 | ~11,500 | ~100,000 | ~2,200,000 |
