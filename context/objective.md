# Objectif Final & Situation Actuelle

## Objectif

Construire un **Multi-RAG Orchestrator SOTA** capable de router intelligemment des questions vers 4 pipelines RAG spécialisées (Standard, Graph, Quantitative, Orchestrator) et d'atteindre des performances state-of-the-art sur des benchmarks HuggingFace progressifs.

**Cible finale** : 1M+ questions, accuracy > 75% overall, coût $0 en LLM.

---

## Pipelines

| Pipeline | Rôle | Base de données | Cible Phase 1 |
|----------|------|-----------------|---------------|
| **Standard** | RAG vectoriel classique | Pinecone (10.4K vecteurs) | >= 85% |
| **Graph** | RAG sur graphe d'entités | Neo4j (4884 entités) | >= 70% |
| **Quantitative** | RAG SQL sur tables financières | Supabase (538 lignes) | >= 85% |
| **Orchestrator** | Route vers les 3 pipelines ci-dessus | Aucune (méta-pipeline) | >= 70% |

---

## Phases du Projet

| Phase | Questions | Status | Gate |
|-------|-----------|--------|------|
| **1** | 200 (50/pipeline) | EN COURS | >= 75% overall |
| **2** | 1,000 (HuggingFace) | Prêt (DB peuplées) | Graph >= 60%, Quant >= 70% |
| **3** | ~10K (16 datasets) | Futur | Tous pipelines >= cibles |
| **4** | ~100K | Futur | Pas de régression |
| **5** | 1M+ | Futur | Production stable |

---

## Situation Actuelle

> **Lire `docs/status.json` pour les métriques live.**

### Ce qui marche
- Graph RAG : 76.5% (17q testées) - PASSE la gate Phase 1
- Infrastructure d'éval complète (quick-test, fast-iter, iterative-eval, parallel eval)
- Analyse granulaire node-par-node fonctionnelle
- Sync n8n <-> GitHub opérationnel
- MCP embeddings + Pinecone fonctionnel

### Ce qui bloque
- Standard : 0% (pas testé récemment, probablement cassé)
- Quantitative : 0% sur 8q testées (6 erreurs)
- Orchestrator : 0% (pas testé)
- Overall : 38.2% vs 75% cible

### Prochaine action prioritaire
**Fixer le pipeline Standard** (plus gros gap : -85pp), puis Quantitative, puis Orchestrator.

---

## Stack Technique

Voir `context/stack.md` pour le détail complet.

**Résumé** :
- **Workflows** : n8n (self-hosted ou cloud)
- **LLM** : arcee-ai/trinity-large-preview:free via OpenRouter ($0)
- **Embeddings** : Jina AI (free, 1024-dim) ou Cohere (free, 1024-dim)
- **Vector DB** : Pinecone (free tier)
- **Graph DB** : Neo4j (free via n8n)
- **SQL DB** : Supabase (free tier)
- **Eval** : Python scripts locaux
- **CI/CD** : GitHub Actions
- **Dev** : Claude Code (Max plan) via terminal ou web
- **Terminal** : Termius / GCloud Console / Oracle Cloud (iPad)
