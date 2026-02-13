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

Details complets : `technicals/phases-overview.md`

---

## Pipelines RAG (4) — Docker n8n (34.136.180.66:5678)

| Pipeline | Role | Base de donnees | Webhook | Cible Phase 1 |
|----------|------|-----------------|---------|---------------|
| **Standard** | RAG vectoriel classique | Pinecone (10.4K vecteurs) | `/webhook/rag-multi-index-v3` | >= 85% |
| **Graph** | RAG sur graphe d'entites | Neo4j (110 entites) | `/webhook/ff622742-...` | >= 70% |
| **Quantitative** | RAG SQL sur tables financieres | Supabase (88 lignes) | `/webhook/3e0f8010-...` | >= 85% |
| **Orchestrator** | Route vers les 3 pipelines | Aucune (meta-pipeline) | `/webhook/92217bb8-...` | >= 70% |

## Workflow IDs — Docker (source de verite)

| Pipeline | Docker ID | Verifie |
|----------|-----------|---------|
| **Standard** | `M12n4cmiVBoBusUe` | 2026-02-13 via API |
| **Graph** | `Vxm4TDdOLdb7j3Jy` | 2026-02-13 via API |
| **Quantitative** | `nQnAJyT06NTbEQ3y` | 2026-02-13 via API |
| **Orchestrator** | `P1no6VZkNtnRdlBi` | 2026-02-13 via API |

### Trace Cloud (anciens IDs — OBSOLETE, reference uniquement)

| Pipeline | Cloud ID | Executions reussies |
|----------|----------|---------------------|
| Standard | `IgQeo5svGlIAPkBc` | #19404 |
| Graph | `95x2BBAbJlLWZtWEJn6rb` | #19305 |
| Quantitative | `E19NZG9WfM7FNsxr` | #19326 |
| Orchestrator | `ALd4gOEqiKL5KR1p` | #19323 |

## Workflows supplementaires (9)

| Workflow | Role | Docker ID |
|----------|------|-----------|
| **Ingestion V3.1** | Ingestion de documents | `6lPMHEYyWh1v34ro` |
| **Enrichissement V3.1** | Enrichissement donnees | `KXnQKuKw8ZUbyZUl` |
| **Feedback V3.1** | Boucle de feedback | `cMlr32Qq7Sgy6Xq8` |
| **Benchmark V3.0** | Benchmark automatise | `tygzgU4i67FU6vm2` |
| **Dataset Ingestion** | Ingestion datasets HF | `S4FFbvx9Mn7DRkgk` |
| **Monitoring** | Monitoring workflows | `xFAcxnFS5ISnlytH` |
| **Orchestrator Tester** | Tests orchestrateur | `R0HRiLQmL3FoCNKg` |
| **RAG Batch Tester** | Tests batch RAG | `k7jHXRTypXAQOreJ` |
| **SQL Executor** | Execution SQL | `Dq83aCiXCfymsgCV` |

---

## Situation Actuelle

> **Lire `docs/status.json` pour les metriques live.**

### Clean reset (13 fev 2026)
- Migration Docker terminee (12 fev)
- Repo nettoye et reorganise
- 4 executions cloud de reference conservees : #19404, #19326, #19323, #19305
- Tests Docker a recommencer de zero

### Prochaine action prioritaire
**Tester chaque pipeline 1/1 sur Docker**, analyser avec les deux outils, puis iterer.
Suivre le processus : `directives/workflow-process.md`

---

## Etat des BDD (verifie le 2026-02-10)

### Pinecone
- 10,411 vecteurs, 12 namespaces, dimension 1536
- Index Docker : `sota-rag-cohere-1024` (Cohere 1024-dim)
- **Attention** : verifier coherence dimension embedding vs index

### Neo4j
- 110 entites, 151 relations
- Acces : via n8n Docker (bolt://localhost:7687 sur la VM)

### Supabase
- 88 lignes, 5 tables
- Acces : direct via n8n Docker

---

## Stack Technique

Voir `technicals/stack.md` pour le detail complet.

**Resume** :
- **Workflows** : n8n Docker self-hosted (34.136.180.66:5678)
- **LLM** : Modeles gratuits via OpenRouter ($0)
- **Embeddings** : Cohere embed-english-v3.0 (1024-dim) + Jina (backup)
- **Vector DB** : Pinecone (free tier, serverless)
- **Graph DB** : Neo4j (via n8n Docker)
- **SQL DB** : Supabase (free tier)
- **Eval** : Python scripts locaux
- **Dev** : Claude Code (Max plan) via Termius

---

## Analyse Nodulaire Double — OBLIGATOIRE

A chaque question testee, executer **LES DEUX ANALYSES** :

### 1. node-analyzer.py (diagnostics auto)
```bash
python3 eval/node-analyzer.py --execution-id <ID>
```

### 2. analyze_n8n_executions.py (donnees brutes)
```bash
python3 scripts/analyze_n8n_executions.py --execution-id <ID>
```

Les deux outils sont complementaires et DOIVENT etre utilises systematiquement.
