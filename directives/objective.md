# Objectif Final & Situation Actuelle

## Objectif

Construire un **Multi-RAG Orchestrator SOTA** capable de router intelligemment des questions vers 4 pipelines RAG specialisees (Standard, Graph, Quantitative, Orchestrator) et d'atteindre des performances state-of-the-art sur des benchmarks HuggingFace progressifs.

**Cible finale** : 1M+ questions, accuracy > 75% overall, cout $0 en LLM.

---

## Plan global en 3 phases

```
PHASE A : RAG Pipeline Iteration (prioritaire)
  1/1 -> 5/5 -> 10/10 -> 200q -> 1000q -> 10Kq -> 100Kq -> 1M+q

PHASE B : Analyse SOTA 2026 (recherche academique)
  Papiers recents -> Techniques SOTA -> Design optimise

PHASE C : Ingestion & Enrichment (post-analyse SOTA)
  Analyse des workflows existants -> Nouvelles BDD -> Tests iteratifs
```

Details complets : `phases/overview.md`

---

## Pipelines RAG (4)

| Pipeline | Role | Base de donnees | Webhook | Cible Phase 1 |
|----------|------|-----------------|---------|---------------|
| **Standard** | RAG vectoriel classique | Pinecone (10.4K vecteurs) | `/webhook/rag-multi-index-v3` | >= 85% |
| **Graph** | RAG sur graphe d'entites | Neo4j (110 entites) | `/webhook/ff622742-...` | >= 70% |
| **Quantitative** | RAG SQL sur tables financieres | Supabase (88 lignes) | `/webhook/3e0f8010-...` | >= 85% |
| **Orchestrator** | Route vers les 3 pipelines | Aucune (meta-pipeline) | `/webhook/92217bb8-...` | >= 70% |

## Workflows supplementaires (9)

| Workflow | Role | Phase d'utilisation |
|----------|------|---------------------|
| **Ingestion V3.1** | Ingestion de documents dans les BDD | Phase C |
| **Enrichissement V3.1** | Enrichissement des donnees existantes | Phase C |
| **Feedback V3.1** | Boucle de feedback des resultats | Phase C |
| **Benchmark V3.0** | Benchmark automatise | Toutes phases |
| **Dataset Ingestion Pipeline** | Ingestion de datasets HF | Phase 2+ |
| **Monitoring & Alerting** | Monitoring des workflows | Toutes phases |
| **Orchestrator Tester** | Tests de l'orchestrateur | Phase A |
| **RAG Batch Tester** | Tests batch des pipelines RAG | Phase A |
| **SQL Executor Utility** | Execution SQL utilitaire | Debug |

---

## Situation Actuelle

> **Lire `docs/status.json` pour les metriques live.**

### Ce qui marche
- Graph RAG : 76.5% (17q testees) - PASSE la gate Phase 1
- Infrastructure d'eval complete (quick-test, fast-iter, iterative-eval, parallel eval)
- Analyse granulaire node-par-node fonctionnelle
- Sync n8n <-> GitHub operationnel (13 workflows importes)
- MCP embeddings + Pinecone fonctionnel

### Ce qui bloque
- Standard : 0% (pas teste recemment)
- Quantitative : 0% sur 8q testees (6 erreurs)
- Orchestrator : 0% (pas teste)
- Overall : 38.2% vs 75% cible

### Prochaine action prioritaire
**Fixer le pipeline Standard** (plus gros gap : -85pp), puis Quantitative, puis Orchestrator.
Suivre le processus : `context/workflow-process.md`

---

## Etat des BDD (verifie le 2026-02-10)

### Pinecone
- 10,411 vecteurs, 12 namespaces, dimension 1536
- Couverture : Phase 1 + donnees partielles Phase 3 (vecteurs Tier 3)
- **Attention** : dimension 1536, verifier coherence avec le modele d'embedding

### Neo4j
- 110 entites, 151 relations
- Couverture : Phase 1 uniquement
- Phase 2 necessite ~2,500 nouvelles entites (extraction depuis HF)

### Supabase
- 88 lignes, 5 tables
- Couverture : Phase 1 uniquement
- Phase 2 necessite ~10,000 lignes (tables financieres HF)

### Datasets locaux
- Phase 1 : 200q (PRET)
- Phase 2 : 1,000q (PRET)
- Phase 3-5 : A generer via `db/populate/push-datasets.py`

---

## Stack Technique

Voir `context/stack.md` pour le detail complet.

**Resume** :
- **Workflows** : n8n (cloud actuel, migration self-hosted prevue)
- **LLM** : arcee-ai/trinity-large-preview:free via OpenRouter ($0)
- **Embeddings** : Jina AI (free, 1024-dim) ou Cohere (free, 1024-dim)
- **Vector DB** : Pinecone (free tier, serverless)
- **Graph DB** : Neo4j (via n8n)
- **SQL DB** : Supabase (free tier)
- **Eval** : Python scripts locaux
- **CI/CD** : GitHub Actions
- **Dev** : Claude Code (Max plan) via terminal ou web
- **Terminal** : Termius / GCloud Console / Oracle Cloud (iPad)

---

## Workflow IDs n8n (verifies via API)

| Pipeline | Workflow ID | Statut |
|----------|-------------|--------|
| **Standard** | `IgQeo5svGlIAPkBc` | ✅ Verifie via API |
| **Graph** | `95x2BBAbJlLWZtWEJn6rb` | ✅ Verifie via API |
| **Quantitative** | `E19NZG9WfM7FNsxr` | ✅ Verifie via API |
| **Orchestrator** | `ALd4gOEqiKL5KR1p` | ✅ Verifie via API |

---

## Analyse Nodulaire Double - OBLIGATOIRE

**⚠️ MODIFICATION ESSENTIELLE :** A chaque fois qu'une question est testee, il faut effectuer **LES DEUX ANALYSES** suivantes :

### 1. Analyse via node-analyzer.py (existante)
```bash
python3 eval/node-analyzer.py --execution-id <ID>
```

### 2. Analyse via analyze_n8n_executions.py (NOUVEAU - OBLIGATOIRE)
```bash
python3 analyze_n8n_executions.py --execution-id <ID>
```

### Ou analyse par pipeline (pour les tests multiples)
```bash
# Analyser les 5 dernieres executions d'un pipeline
python3 analyze_n8n_executions.py --pipeline <standard|graph|quantitative|orchestrator> --limit 5
```

### Pourquoi les deux analyses ?

| Outil | Donnees fournies | Usage |
|-------|------------------|-------|
| **node-analyzer.py** | Diagnostics automatiques, detection d'issues, recommandations | Vue d'ensemble rapide, identification des problemes |
| **analyze_n8n_executions.py** | Donnees brutes completes (input/output), extraction LLM detaillee, flags de routage | Analyse profonde, debugging complexe |

**Les deux outils sont complementaires et DOIVENT etre utilises systematiquement.**
