# Objectif Final & Situation Actuelle

> Last updated: 2026-02-25T11:30:00+00:00

---

## 1. Vision Globale

Construire un **Multi-RAG Orchestrator SOTA** capable de router intelligemment des questions vers 4 pipelines RAG specialisees (Standard, Graph, Quantitative, Orchestrator) et d'atteindre des performances state-of-the-art sur des benchmarks HuggingFace progressifs.

**Cible finale** : 1M+ questions, accuracy > 75% overall, cout $0 en LLM.

---

## 2. mon-ipad — Tour de Controle Centrale

| | |
|-|-|
| **Role** | Pilotage, stockage n8n final, sync GitHub/VM, ZERO tests lourds |
| **Localisation** | VM Google Cloud permanente (34.136.180.66) |
| **n8n** | Docker permanent — 9 workflows actifs (4 RAG + 5 support), cible 16 |
| **Actions** | Fix workflows, sync repos, analyser resultats, distribuer directives |
| **Interdit** | Tests lourds (RAM ~100MB dispo), calcul intensif |

---

## 3. rag-tests — Mesure Performance 4 Pipelines

| | |
|-|-|
| **Role** | Executer tests, mesurer accuracy, rapporter resultats |
| **Localisation** | Codespace ephemere (8GB RAM, docker-compose) |
| **n8n** | Local dans Codespace (n8n-main + 3 workers + Redis + PostgreSQL) |
| **Phase 1** | BLOQUEE — Graph 68.7% < 70%, Quantitative 78.3% < 85% |
| **Phase 2** | En attente — 1000q HuggingFace (prerequis : Phase 1 gates) |
| **Donnees** | 932 questions testees, 42 iterations, docs/data.json |

---

## 4. rag-website — Site Vitrine 4 Secteurs

| | |
|-|-|
| **Role** | Site business, chatbots sectoriels, dashboard SSE live |
| **Localisation** | Codespace (dev) + Vercel (prod : nomos-ai-pied.vercel.app) |
| **Secteurs** | BTP/Construction, Industrie, Finance, Juridique |
| **MVP** | Live — Hero, SectorCards, HowItWorks, Dashboard SSE (932q) |
| **Manquant** | Vrais documents sectoriels dans les demos chatbot |

---

## 5. rag-data-ingestion — Ingestion 5.4GB Datasets

| | |
|-|-|
| **Role** | Telecharger datasets HuggingFace, ingerer dans BDD separees |
| **Localisation** | Codespace ephemere (a creer) |
| **n8n** | Local COMPLET (n8n + 2 workers, queue mode Redis) |
| **Volume** | ~4 GB benchmarks Phase 2 + ~1.4 GB docs sectoriels = **5.4 GB** |
| **BDD cibles** | Pinecone (vectors), Neo4j (graph), Supabase (tables) |

---

## 6. rag-dashboard — Metriques Live Read-Only

| | |
|-|-|
| **Role** | Dashboard technique affichant les metriques en temps reel |
| **Localisation** | Statique — GitHub Pages ou Vercel |
| **Source** | Webhook VM `/webhook/nomos-status` + fallback `status.json` GitHub |
| **n8n** | AUCUN — consomme uniquement |

---

## Plan global en 4 phases

```
PHASE A : RAG Pipeline Iteration (prioritaire)
  Phase 1 (200q) ← BLOQUEE — Graph 68.7%, Quant 78.3%
  Phase 2 (1000q HuggingFace) ← prerequis Phase 1
  Phase 3 (~10Kq) → Phase 4 (~100Kq) → Phase 5 (1M+)
  Repo : rag-tests (Codespaces pour 500q+)

PHASE B : Analyse SOTA 2026 (recherche academique)
  Papiers recents → Techniques SOTA → Design optimise
  Repo : mon-ipad (controle) — FAIT (session 13)

PHASE C : Ingestion & Enrichment (post-analyse SOTA)
  14 benchmarks HuggingFace + 20 datasets sectoriels
  Repo : rag-data-ingestion (Codespaces)

PHASE D : Production & Deploiement
  Site business + Dashboard live + Monitoring
  Repos : rag-website + rag-dashboard (Vercel)
```

Details complets : `technicals/project/phases-overview.md`

---

## Pipelines RAG (4) — Docker n8n (localhost:5678)

| Pipeline | Role | Base de donnees | Webhook | Cible Phase 1 |
|----------|------|-----------------|---------|---------------|
| **Standard** | RAG vectoriel classique | Pinecone (10,411 vecteurs, 12 ns) | `/webhook/rag-multi-index-v3` | >= 85% |
| **Graph** | RAG sur graphe d'entites | Neo4j (19,788 nodes, 76,717 rels) | `/webhook/ff622742-...` | >= 70% |
| **Quantitative** | RAG SQL sur tables | Supabase (40 tables, ~17,000+ lignes) | `/webhook/3e0f8010-...` | >= 85% |
| **Orchestrator** | Route vers les 3 pipelines | Aucune (meta-pipeline) | `/webhook/92217bb8-...` | >= 70% |

## Workflow IDs — Docker (source de verite)

| Pipeline | Docker ID | Verifie |
|----------|-----------|---------|
| **Standard** | `TmgyRP20N4JFd9CB` | 2026-02-14 via API |
| **Graph** | `6257AfT1l4FMC6lY` | 2026-02-14 via API |
| **Quantitative** | `e465W7V9Q8uK6zJE` | 2026-02-14 via API |
| **Orchestrator** | `aGsYnJY9nNCaTM82` | 2026-02-14 via API |

### Trace Cloud (anciens IDs — OBSOLETE, reference uniquement)

| Pipeline | Cloud ID | Executions reussies |
|----------|----------|---------------------|
| Standard | `IgQeo5svGlIAPkBc` | #19404 |
| Graph | `95x2BBAbJlLWZtWEJn6rb` | #19305 |
| Quantitative | `E19NZG9WfM7FNsxr` | #19326 |
| Orchestrator | `ALd4gOEqiKL5KR1p` | #19323 |

## Workflows actifs — Actuels (9) et Cible (16)

### Actuels (9 apres audit session 18)
| Workflow | Role | Docker ID |
|----------|------|-----------|
| **Ingestion V3.1** | Ingestion de documents | `15sUKy5lGL4rYW0L` |
| **Enrichissement V3.1** | Enrichissement donnees | `9V2UTVRbf4OJXPto` |
| **Benchmark V3.0** | Benchmark automatise | `LKZO1QQY9jvBltP0` |
| **Dataset Ingestion** | Ingestion datasets HF | `YaHS9rVb1osRUJpE` |
| **SQL Executor** | Execution SQL (sub-workflow) | `22k9541l9mHENlLD` |

Supprimes (session 18) : Feedback V3.1, Monitoring, Orchestrator Tester, RAG Batch Tester — voir `technicals/infra/architecture.md` pour raisons.

### Cible (16 workflows en 3 categories)
Voir `technicals/infra/architecture.md` section "Architecture 16 Workflows".

---

## Situation Actuelle

> **Lire `docs/status.json` pour les metriques live.**

### Session 62 (25 fev 2026) — 10 HF Space Cluster + Phase 2 Progress
- **10 HF Spaces deployed** — distributed load balancing across 2 accounts (LBJLincoln + LBJLincoln26)
- **Phase 1 PASSED** — Overall 83.9%, all pipelines meet targets (20 fév 2026)
- **Phase 2 IN PROGRESS** — 100+ tested IDs, Graph+Quant partial completion
- **All 4 pipelines working** — Standard, Graph, Quantitative, Orchestrator (Orchestrator Redis-free mode)
- **14 workflows total** — 4 RAG + 10 support workflows across cluster
- **Incremental eval strategy** — deduplication + no-force policy + preflight checks

### Session 24 (19 fev 2026 — 3h10)
- **HF Space n8n DEPLOYE** — 9/9 workflows importes + 8 bugs resolus (FIX-13 a FIX-20)
- **n8n 2.8.3** (latest) + 12/12 credentials importes

### Session 18 (18 fev 2026 — Restructuration)
- **Restructuration profonde** documentation + directives + processus
- **Audit 13→9 workflows** (4 supprimes : feedback, monitoring, orch-tester, rag-tester)
- **Architecture 16 workflows** documentee (A: Test-RAG, B: Sector, C: Ingestion)

### Session 17 (18 fev 2026)
- **CI smoke test ALL GREEN** (commit 630f81f) — 4/4 pipelines 5/5 via GitHub Actions
- **Graph bolt→https fix APPLIED** — Neo4j URL corrigee
- **Quantitative 0-nodes fix APPLIED** — workflow live restaure

### Prochaine action prioritaire (Session 37+)

#### Phase 1 STATUS : PASSED ✅ (20 fev 2026)
- Overall 83.9% >= 75% PASS
- Standard 85.5% >= 85% PASS
- Graph 78.0% >= 70% PASS
- Quantitative 92.0% >= 85% PASS
- Orchestrator 80.0% >= 70% PASS

#### Phase 2 STATUS : EN COURS (v11 running)
- v10 completed : 1263q, 57% overall
- v11 running : Standard 335/537 tested (45.7%)
- Target : >= 75% overall, >= 55% Graph, >= 65% Quant
- Actions : Finaliser v11, documenter limites connues, analyser écart Phase 1 → Phase 2

#### Website/Dashboard (livres en session 13)
- Hero redesigne (problem-first, dual CTA, pain points cycliques)
- 4 sector cards Apple-style (pain point BIG + ROI chips + video modal)
- Dashboard SSE (evalStore, useEvalStream, XPProgressionBar, live Q&A feed)

Suivre le processus : `directives/workflow-process.md`

---

## Etat des BDD (verifie le 2026-02-18)

### Pinecone
- **10,411 vecteurs**, 12 namespaces, dimension **1024** (Jina embeddings-v3)
- Index principal : `sota-rag-jina-1024` (host: `sota-rag-jina-1024-a4mkzmz.svc.aped-4627-b74a.pinecone.io`)
- Index backup : `sota-rag-cohere-1024` (Cohere embed-english-v3.0, conserve)
- Namespaces : benchmark-msmarco (1000), benchmark-frames (824), benchmark-asqa (948), benchmark-squad_v2 (1000), benchmark-triviaqa (1000), default (639), benchmark-popqa (1000), benchmark-narrativeqa (1000), benchmark-natural_questions (1000), benchmark-finqa (500), benchmark-hotpotqa (1000), benchmark-pubmedqa (500)

### Neo4j
- **19,788 noeuds**, **76,717 relations**
- Top types : Person (8,531), Entity (8,218), Organization (1,775), City (840), Technology (139)
- Top relations : CONNECTE (75,205), SOUS_ENSEMBLE_DE (554), A_CREE (497)
- Acces : HTTPS API `https://38c949a2.databases.neo4j.io/db/neo4j/query/v2`

### Supabase
- **40 tables**, **~17,000+ lignes**
- Tables principales : benchmark_datasets (9,772), rag_task_executions (1,596), transactions (1,515), sales_data (1,152), financials (24), quarterly_revenue (12), community_summaries (9)
- Acces : PostgreSQL pooler `aws-1-eu-west-1.pooler.supabase.com:6543`
- Credential n8n Docker : `Supabase Postgres (Pooler)` (ID: `USU8ngVzsUbED3mn`)

---

## Enterprise Production Gates 2026 (Standard industrie)

### Phase 1 Gates (PASSED ✅)
| Metrique | Seuil | Etat actuel |
|---------|-------|-------------|
| Accuracy (overall) | >= 75% | **83.9% PASS** |
| Accuracy Standard | >= 85% | **85.5% PASS** |
| Accuracy Graph | >= 70% | **78.0% PASS** |
| Accuracy Quantitative | >= 85% | **92.0% PASS** |
| Accuracy Orchestrator | >= 70% | **80.0% PASS** |

### Phase 2 Gates (EN COURS)
| Metrique | Seuil | v10 (1263q) | v11 (en cours) |
|---------|-------|-------------|----------------|
| Accuracy (overall) | >= 75% | 57.0% | TBD |
| Accuracy Standard | >= 75% | 60.4% | 45.7% (335/537) |
| Accuracy Graph | >= 55% | 55.7% | TBD |
| Accuracy Quantitative | >= 65% | 53.3% | TBD |
| Accuracy Orchestrator | >= 70% | 58.2% | TBD |

### Métriques avancées (à implémenter)
| Metrique | Seuil | Status |
|---------|-------|--------|
| Faithfulness | >= 95% | Non mesuré |
| Context Recall | >= 85% | Non mesuré |
| Hallucination Rate | <= 2% | Non mesuré |
| Mean Latency | <= 2.5s | Non mesuré |

## Stack Technique

Voir `technicals/infra/stack.md` pour le detail complet.

**Resume** :
- **Workflows** : n8n Docker self-hosted (localhost:5678)
- **LLM** : 3 modeles gratuits via OpenRouter ($0) — Llama 70B, Gemma 27B, Trinity
- **Embeddings** : Jina embeddings-v3 (1024-dim, primary) + Cohere (backup)
- **Vector DB** : Pinecone (free tier, serverless)
- **Graph DB** : Neo4j Aura Free (HTTPS API)
- **SQL DB** : Supabase (free tier)
- **Eval** : Python scripts locaux
- **Dev** : Claude Code (Max plan, Opus 4.6) via Termius

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
