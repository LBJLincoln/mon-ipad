# PROJECT ROADMAP — Multi-RAG Orchestrator 2026

> Last updated: 2026-03-07T20:15:00Z
>
> Consolidated roadmap covering: evaluation phases, improvement priorities, bottleneck resolution, team process, and SOTA research insights.

---

## TABLE OF CONTENTS

1. [Evaluation Phases (A → D)](#1-evaluation-phases-a--d)
2. [Improvements Roadmap](#2-improvements-roadmap)
3. [Scaling Bottlenecks](#3-scaling-bottlenecks)
4. [Bottleneck Actions Playbook](#4-bottleneck-actions-playbook)
5. [Team Agentic Process](#5-team-agentic-process)
6. [RAG Research 2026](#6-rag-research-2026)

---

## 1. EVALUATION PHASES (A → D)

### Overview

```
PHASE A : RAG Pipeline Iteration (Phases 1-5)
  Phase 1 (200q) → Phase 2 (1,000q) → Phase 3 (~10Kq) → Phase 4 (~100Kq) → Phase 5 (1M+q)

PHASE B : SOTA 2026 Research Analysis
  Analyse des meilleurs papiers de recherche → Identification des techniques SOTA
  → Design des pipelines d'ingestion/enrichissement optimises

PHASE C : Ingestion & Enrichment Pipelines
  Nouvelles BDD pour ingestion/enrichment → Tests iteratifs → Production

PHASE D : Website & Business
  4 secteurs ETI + PME connectors + Use cases
```

---

### Phase 1 — Baseline (200 questions)

**Objectif**: Atteindre les targets sur 200 questions curated via iteration 1/1 → 5/5 → 10/10.

| Pipeline | Questions | Source | Target |
|----------|-----------|--------|--------|
| Standard | 50 | `datasets/phase-1/standard-orch-50x2.json` | >= 85% |
| Graph | 50 | `datasets/phase-1/graph-quant-50x2.json` | >= 70% |
| Quantitative | 50 | `datasets/phase-1/graph-quant-50x2.json` | >= 85% |
| Orchestrator | 50 | `datasets/phase-1/standard-orch-50x2.json` | >= 70% |
| **Overall** | **200** | | **>= 75%** |

**Etat des BDD**:
- Pinecone: 10,411 vecteurs, 12 namespaces (PRET)
- Neo4j: 19,788 nodes, 76,717 relations (PRET pour Phase 1)
- Supabase: ~17,000+ lignes, 40 tables (PRET pour Phase 1)

**Exit criteria**:
- Tous les pipelines >= leur target
- 3 iterations stables consecutives (pas de regression)
- Eval complete 200q passee

**STATUS: PASSED** (20 fev 2026, session 30). Overall 83.9% >= 75%.

---

### Phase 2 — Expand (1,000 questions)

**Prerequis**: Phase 1 gates passees. **PASSED 20 fev 2026.**

**STATUS ACTUEL (22 fev 2026)**:
| Pipeline | Tested | Total | Accuracy | Status |
|----------|--------|-------|----------|--------|
| Standard | 579 | 1000 | ~36% | STOPPED (HF Space 404) |
| Graph | 500 | 500 | 78.0% | COMPLETE |
| Quantitative | 500 | 500 | 92.0% | COMPLETE |
| Orchestrator | 57 | 1000 | 0% | BROKEN (workflow bug) |

| Pipeline | Questions | Datasets HuggingFace |
|----------|-----------|---------------------|
| Graph | 500 | musique (200), 2wikimultihopqa (300) |
| Quantitative | 500 | finqa (200), tatqa (150), convfinqa (100), wikitablequestions (50) |

**Ingestion necessaire**:
- Neo4j: extraction d'entites depuis les contextes des questions (~2,500 entites)
- Supabase: creation de tables dynamiques pour les donnees financieres (~10,000 lignes)

**Exit criteria**: Graph >= 60%, Quant >= 70%, pas de regression Phase 1.

---

### Phase 3 — Scale (~10,700 questions)

**Prerequis**: Phase 2 gates passees.

Tous les 16 datasets HuggingFace (3 tiers).

| Tier | Pipeline | Datasets | Questions |
|------|----------|----------|-----------|
| 1 | Graph | musique, 2wikimultihopqa, hotpotqa | 1,500 |
| 2 | Quantitative | finqa, tatqa, convfinqa, wikitablequestions | 500 |
| 3 | Standard | frames, triviaqa, squad_v2, popqa, msmarco, asqa, narrativeqa, pubmedqa, natural_questions | 8,700 |

**Exit criteria**: Standard >= 75%, Graph >= 55%, Quant >= 65%, Orchestrator >= 60%.

**STATUS (6 mars 2026)**:
| Pipeline | Tested | Total | Accuracy | Status |
|----------|--------|-------|----------|--------|
| Standard | **8,006** | 8,700 | **87.5%** | **COMPLETE** — above 85% target |
| Graph | **1,500** | 1,500 | **40.9%** | **COMPLETE** — accuracy drop vs Phase 2 (hard questions) |
| Quantitative | 500 | 500 | 30% | **INVALID** — synthetic dataset wrong expected answers |
| Orchestrator | 0 | 1,000 | — | ON HOLD |

---

### Phase 4 — Full HF (~100K questions)

**Prerequis**: Phase 3 gates passees. Echantillons 10x plus grands.

**Infrastructure possible**:
- Pinecone: ~100K vecteurs (free tier suffisant avec serverless)
- Neo4j: ~15K entites (Aura Free = 50K max, suffisant)
- Supabase: ~50K lignes (free tier = 500MB, suffisant)

**Exit criteria**: Pas de regression vs Phase 3.

---

### Phase 5 — Million+ (production)

**Prerequis**: Phase 4 gates passees. Infrastructure payante requise.

**Cout estime**: $215-455/mois (Pinecone Standard + Neo4j Pro + Supabase Pro).

---

### Triggers Downstream — Actions déclenchées par les phases

#### Tests site ETI (4 secteurs)

**Trigger**: Phase 4 PASSED + rag-data-ingestion COMPLETE

| Condition | Pourquoi |
|-----------|----------|
| Phase 4 PASSED | Prouve que les pipelines RAG sont fiables à l'échelle (100K questions). Lancer les tests site sur des pipelines non validés donne des faux négatifs. |
| rag-data-ingestion COMPLETE | Garantit que les données sectorielles (finance, santé, industrie, juridique) sont présentes dans Pinecone, Neo4j et Supabase. Sans données, les chatbots ETI répondent dans le vide. |

**Action**: Lancer les tests E2E des sites ETI:
- `nomos-ai-pied.vercel.app` (4 secteurs)
- `nomos-pme-connectors-alexis-morets-projects.vercel.app` (connecteurs PME)

**Vérification**:
```bash
python3 eval/phase_gates.py --trigger eti_site_tests --repo-complete rag-data-ingestion
```

**Historique**: Anciennement déclenché après Phase 2. Modifié le 2026-03-03 (session 69) car Phase 2 ne teste que des benchmarks HF génériques, insuffisant pour valider les réponses sectorielles.

---

### Projection de croissance des BDD

| Metrique | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Phase 5 |
|----------|---------|---------|---------|---------|---------|
| Pinecone vecteurs | 10,411 | 10,411 | ~15,000 | ~100,000 | ~500,000+ |
| Neo4j entites | 19,788 | ~25,000 | ~30,000 | ~50,000 | ~200,000+ |
| Neo4j relations | 76,717 | ~100,000 | ~120,000 | ~200,000 | ~400,000+ |
| Supabase lignes | ~17,000 | ~30,000 | ~50,000 | ~100,000 | ~500,000+ |
| Questions testees | 200 | 1,200 | ~11,500 | ~100,000 | ~2,200,000 |

---

## 2. IMPROVEMENTS ROADMAP

### 2.1 Pipelines RAG — Accuracy

#### Quantitative (78.3% → 85%)

| # | Amélioration | Impact | Effort | Statut |
|---|-------------|--------|--------|--------|
| Q1 | Timeouts/retries HTTP Request (90s, 3 retries, 8s wait) | +3pp | Fait | APPLIQUE session 25 |
| Q2 | SQL templates pour questions simples (bypass LLM) | +2pp | Fait | APPLIQUE session 25 |
| Q3 | Sample data dans le prompt LLM | +1pp | Fait | APPLIQUE session 25 |
| Q4 | Rotation multi-modeles (Llama/Qwen/Gemma par minute) | +2pp | Moyen | A FAIRE |
| Q5 | Schema statique compact dans le prompt | +1pp | Faible | A FAIRE |
| Q6 | ILIKE au lieu de = pour les noms d'entreprise | +0.5pp | Faible | A FAIRE |
| Q7 | Delai inter-questions dans eval scripts (8s pour quant) | +1pp | Faible | A FAIRE |
| Q8 | CompactRAG: pre-compute QA pairs pour questions frequentes | +2pp | Eleve | PLANIFIE |
| Q9 | BM25 hybrid search pour contexte SQL | +1pp | Moyen | PLANIFIE |

#### Graph (68.7% → 70%)

| # | Amélioration | Impact | Effort | Statut |
|---|-------------|--------|--------|--------|
| G1 | Entity disambiguation Neo4j (fuzzy matching) | +1.5pp | Moyen | A FAIRE |
| G2 | Enrichir graph avec sector datasets (juridique, finance) | +2pp | Eleve | DATASETS PRETS |
| G3 | Community summaries multilingual (fr/en) | +0.5pp | Moyen | A FAIRE |
| G4 | Traversal depth adaptatif (2→3 hops pour questions complexes) | +0.5pp | Faible | A FAIRE |

#### Standard (85.5% — PASS)

| # | Amélioration | Impact | Effort | Statut |
|---|-------------|--------|--------|--------|
| S1 | Late chunking (Jina late_chunking=True) | +1pp | Moyen | PLANIFIE |
| S2 | Hybrid search (dense + sparse) | +1pp | Moyen | A FAIRE |
| S3 | Reranking ameliore (cross-encoder) | +0.5pp | Faible | A FAIRE |

#### Orchestrator (80.0% — PASS)

| # | Amélioration | Impact | Effort | Statut |
|---|-------------|--------|--------|--------|
| O1 | A-RAG (agentic hierarchical retrieval) | +3pp | Eleve | PLANIFIE |
| O2 | Routing dynamique base sur confidence scores | +1pp | Moyen | A FAIRE |

---

### 2.2 Infrastructure — Scalabilité

#### Capacité actuelle vs cible

| Composant | Actuel | Cible 1000q | Cible 10Kq | Action |
|-----------|--------|------------|------------|--------|
| **n8n concurrency** | **3 workers (queue mode)** | 5 workers | 10 workers | **DEPLOYED Session 42** |
| **OpenRouter rate** | ~20 req/min (1 key) → **~100 req/min (5 keys)** | ~100 req/min | ~200 req/min | **Multi-key DEPLOYED Session 42** |
| **RAM** | **~400MB (VM, n8n removed)** / 16GB (HF) | 16GB | 32GB | **VM n8n removed Session 42** |
| **PostgreSQL** | Supabase free | Supabase free | Supabase Pro | OK pour 1000q |
| **Pinecone** | 10K vecteurs | 50K vecteurs | 100K vecteurs | Ingestion Phase 2 |
| **Neo4j** | 19K nodes | 50K nodes | 200K nodes (max free) | Ingestion secteurs |
| **Eval parallelism** | Sequential | 3 parallel | 10 parallel | asyncio + aiohttp |

#### Estimation temps pour 1000q par pipeline

| Config | Standard | Graph | Quantitative | Orchestrator | Total 4000q |
|--------|----------|-------|-------------|-------------|-------------|
| **Actuel** (seq, 1 worker) | ~3h | ~5h | ~8h | ~5h | ~21h |
| **Optimise** (3 workers, 8s delay) | ~1h | ~2h | ~3h | ~2h | ~8h |
| **Ideal** (10 workers, multi-key) | ~20min | ~40min | ~1h | ~40min | ~2.5h |

---

### 2.3 n8n Workflows

#### Core Optimizations

| # | Amélioration | Impact | Effort | Statut |
|---|-------------|--------|--------|--------|
| N1 | Workflow versioning automatique (snapshot avant chaque modification) | Fiabilite | Moyen | A FAIRE |
| N2 | Health check endpoint dedié (/webhook/health) | Monitoring | Faible | A FAIRE |
| N3 | Metrics Prometheus via n8n metrics endpoint | Observabilite | Faible | PARTIEL (N8N_METRICS=true) |
| N4 | Error notification webhook (Slack/Discord) | Alerting | Faible | A FAIRE |
| N5 | Workflow export automatique apres chaque activation | Backup | Moyen | A FAIRE |

#### Queue Mode & Scalability

| # | Amélioration | Impact | Effort | Statut |
|---|-------------|--------|--------|--------|
| **N6** | **Configurer QUEUE_HEALTH_CHECK_ACTIVE=true** pour /healthz readiness | Detect worker failures | Faible | RECOMMANDE |
| **N7** | **Worker count = CPU cores** (3 workers sur HF Space 2-core) | Optimal throughput | Faible | A FAIRE |
| **N8** | **Binary data → S3 external storage** (required for queue mode) | Prevent file system errors | Moyen | SI BINARIES NEEDED |
| **N9** | **Concurrency control per workflow** (limite 5 executions simultanées) | Prevent rate-limit cascade | Faible | RECOMMANDE |
| **N10** | **Redis queue persistence** (AOF enabled) | Survive Redis restarts | Faible | A FAIRE |

---

### 2.4 Databases

| # | Amélioration | Impact | Effort | Statut |
|---|-------------|--------|--------|--------|
| D1 | Ingerer 7,609 items sectoriels dans Pinecone | +2pp accuracy | Eleve | DATASETS PRETS |
| D2 | Enrichir Neo4j avec entites juridiques francaises | +1pp Graph | Eleve | DATASETS PRETS |
| D3 | Ajouter BM25 index dans Pinecone (sparse vectors) | +1pp hybrid | Moyen | PLANIFIE |
| D4 | Indexer les 14 benchmarks Phase 2 dans Pinecone | Phase 2 requis | Eleve | A FAIRE |
| D5 | Creer des tables Supabase pour les donnees sectorielles | Quant sector | Moyen | A FAIRE |

---

### 2.5 Evaluation — Méthodologie

#### Enterprise Production Metrics (2026 Standards)

**CRITICAL INSIGHT**: Current system only tracks 1/7 enterprise metrics. Phase 2+ gates REQUIRE comprehensive metrics.

| # | Métrique | Cible 2026 | Outil | Effort | Statut |
|---|----------|-----------|-------|--------|--------|
| **E0** | **Accuracy** | >= 75% | Manual fuzzy match | — | ✅ IMPLEMENTED |
| **E1** | **Faithfulness** | >= 95% | Ragas | Moyen | ❌ **BLOCKING Phase 2+** |
| **E2** | **Context Recall** | >= 85% | Ragas | Moyen | ❌ **BLOCKING Phase 2+** |
| **E3** | **Context Precision** | >= 80% | Ragas | Moyen | ❌ HIGH Priority |
| **E4** | **Answer Relevancy** | >= 90% | Ragas | Moyen | ❌ HIGH Priority |
| **E5** | **Hallucination Rate** | <= 2% | Ragas (inverse faithfulness) | Moyen | ❌ **BLOCKING Phase 2+** |
| **E6** | **Latency (p95)** | <= 2.5s | Custom (track execution time) | Faible | ❌ MEDIUM Priority |

**Implementation Roadmap**:
```python
# Step 1: Install Ragas
pip install ragas

# Step 2: Modify eval/quick-test.py to collect contexts
response_data = {
    "question": question,
    "answer": pipeline_response["answer"],
    "contexts": pipeline_response.get("retrieved_contexts", []),  # NEW
    "ground_truth": expected_answer
}

# Step 3: Evaluate with Ragas
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_recall, context_precision

result = evaluate(
    dataset=Dataset.from_dict([response_data]),
    metrics=[faithfulness, answer_relevancy, context_recall, context_precision]
)
```

#### Advanced RAG Techniques — 2026 Research Insights

| # | Technique | Impact | Effort | Pipeline | Priorité |
|---|-----------|--------|--------|----------|----------|
| **E7** | **Adaptive RAG** (SELF-RAG, CRAG) | +5-10% accuracy | Élevé | Orchestrator | Phase 3+ |
| **E8** | **Hybrid Retrieval** (dense + BM25) | +10-15% domain queries | Moyen | Standard, Quant | **Phase 2** |
| **E9** | **Late Chunking** (Jina v3) | +3-5% context precision | Faible | Standard | **Phase 2+** |
| **E10** | **Cross-encoder Reranking** | +3-5% accuracy, +15% precision | Faible | All pipelines | **Phase 2** |
| E11 | Evaluation parallele avec asyncio | 3x speedup eval | Moyen | Infrastructure | A FAIRE |
| E12 | Dashboard live accuracy en temps reel | Visibilite | Faible | PARTIEL (SSE) | — |
| E13 | A/B testing entre versions de workflows | Qualite | Eleve | Infrastructure | PLANIFIE |
| **E14** | **Integrer RAGAS dans CI/CD** | Regression detection | Moyen | **RECOMMANDE** |
| **E15** | **Component-level eval** (retriever-only) | Pinpoint failures | Moyen | A FAIRE |

---

### 2.6 Website — Contenu & UX

| # | Amélioration | Impact | Effort | Statut |
|---|-------------|--------|--------|--------|
| W1 | Integrer vrais docs sectoriels (BTP/Industrie/Finance/Juridique) | Business | Moyen | DATASETS PRETS |
| W2 | Chat live avec pipeline selection | UX | Moyen | PARTIEL |
| W3 | Dashboard public avec metriques accuracy | Credibilite | Faible | FAIT (Vercel) |
| W4 | Videos sectorielles (scripts Kimi) | Marketing | Moyen | SCRIPTS PRETS |
| **W5** | **GEO optimization** (TLDR-first, structured data, FAQ schema) | **SEO+GEO** | Moyen | **PLANIFIE S79** |
| **W6** | **Nano Banana 2 video demos** (4 sectors) | **Marketing** | Moyen | **PLANIFIE S79** |
| **W7** | **Per-product color differentiation** (psychology-driven palettes) | **Conversion** | Moyen | **BRIEF CREE S79** |
| **W8** | **Product persona alignment** (ETI vs PME vs technique) | **Brand** | Moyen | **BRIEF CREE S79** |

---

### 2.7 DevOps — CI/CD & Monitoring

| # | Amélioration | Impact | Effort | Statut |
|---|-------------|--------|--------|--------|
| CI1 | CI smoke tests toutes les 4 pipelines | Regression | Fait | ACTIF (GitHub Actions) |
| CI2 | Nightly eval (50q) automatique | Monitoring | Moyen | A FAIRE |
| CI3 | Auto-deploy HF Space depuis GitHub push | DevOps | Moyen | A FAIRE |
| CI4 | Alertes si accuracy drop > 2pp | Regression | Faible | A FAIRE |

---

## 3. SCALING BOTTLENECKS

### État Actuel (baseline)

| Metrique | Valeur actuelle |
|----------|----------------|
| Pipelines fonctionnels | Standard ✓, Graph ✓, Quant ✓ (S75 fixed), Orch BROKEN |
| Questions testees/heure | ~30 (avec early-stop) |
| Instances n8n | **1** (HF Space 16GB) |
| Workers n8n par instance | **1** |
| OpenRouter keys | **6** (~120 req/min aggregate) |
| Execution vectors | VM script + GH Actions |
| Dashboard live | https://nomos-dashboard-alexis-morets-projects.vercel.app |

**VERITE FONDAMENTALE**: On ne peut pas scaler 0% accuracy. Les pipelines doivent d'abord FONCTIONNER avant de scaler.

---

### x2 Vitesse (LOW-HANGING FRUIT)

> **Qui gere**: Alexis (HF account #2) + Claude
> **Low-hanging fruit**: OUI

| Levier | Situation actuelle | Apres | Impact |
|--------|-------------------|-------|--------|
| **2eme HF Space** | 1 instance (16GB) | 2 instances | x2 throughput |
| **Per-pipeline routing** | Code pret (N8N_HOST_STANDARD etc.) | Route 2-3 pipelines par HF Space | Deja fait dans eval scripts |
| **Batch size optimal** | Auto mode deja code | Std=10, Graph=5, Quant=3, Orch=2 | x3-5 vs batch=1 |
| **GH Actions parallele** | 5 jobs configures | Declencher en parallele du VM script | x2 tests simultanes |

**Actions Alexis**:
1. Creer 2eme HF Space avec meme Dockerfile
2. Configurer `HF_TOKEN_2` dans secrets
3. Setter `N8N_HOST_STANDARD` et `N8N_HOST_GRAPH` vers HF Space #2

**Actions Claude**:
1. Mettre a jour eval scripts pour round-robin entre 2 HF Spaces
2. Tester load balancing

**Resultat**: ~60 questions/heure → ~120 questions/heure

---

### x5 Vitesse

> **Qui gere**: Claude + Alexis
> **Low-hanging fruit**: Moyen

| Levier | Comment | Prerequis |
|--------|---------|-----------|
| **3+ HF Spaces** | 1 par pipeline type (std, graph, quant, orch) | Comptes HF additionnels |
| **Codespace Docker** | n8n local dans Codespace (8GB) pour 1-2 pipelines | Docker-in-Docker fonctionnel |
| **GH Actions matrix x5** | 5 pipelines × 2 runs = 10 jobs paralleles | 2 HF Spaces minimum |
| **Timeout optimization** | Standard 45s→30s, Graph 45s→30s (fail fast) | Tuner per-pipeline |
| **OpenRouter key pooling** | 6 keys × 20 req/min = 120 req/min → distribuer equitablement | Deja en place |

**Resultat**: ~120 q/h → ~600 q/h

---

### x10 Vitesse

> **Qui gere**: Alexis (infra) + Claude (code)
> **Low-hanging fruit**: NON — necessite infra additionnelle

| Levier | Comment | Cout |
|--------|---------|------|
| **n8n multi-worker** | `N8N_CONCURRENCY=5` par HF Space | Config Docker |
| **4 HF Spaces** | 1 dedie par pipeline | 4 comptes HF |
| **Codespace fleet** | 3 Codespaces simultanes (60h/mois limite) | Gratuit mais limite |
| **Pre-computed embeddings** | Cacher embeddings Jina pour questions recurrentes | Stockage Pinecone |
| **OpenRouter Pro** | Passer paid keys (200 req/min par key) | ~$50/mois |

**Resultat**: ~600 q/h → ~6,000 q/h (~100/min)

---

### x20 Vitesse

> **Qui gere**: Alexis (budget) + Claude (archi)
> **Necessite investissement**

| Levier | Comment | Cout |
|--------|---------|------|
| **Dedicated GPU** | HF Space A10G (24GB) — 2x faster inference | $1.05/h |
| **Self-hosted n8n cluster** | 3 workers Docker sur VPS (Hetzner CX31 = 8GB, $7/mois) | ~$21/mois |
| **Connection pooling** | Neo4j/Supabase connection pool (max_connections=20) | Config |
| **Parallel DB queries** | Async Supabase + Neo4j dans n8n Code nodes | Code change |
| **Result caching** | Redis cache pour questions deja evaluees | Redis instance |

**Resultat**: ~6,000 q/h → ~12,000 q/h

---

### x100 Vitesse

> **Qui gere**: Alexis (budget significatif)
> **Transformation architecturale**

| Levier | Comment | Cout |
|--------|---------|------|
| **Kubernetes cluster** | 10+ n8n workers auto-scaling | $100-300/mois |
| **Dedicated LLM** | vLLM self-hosted (Llama 70B sur A100) — 0 rate limits | $2-4/h GPU |
| **Sharded databases** | Pinecone p2 (100K+ vectors), Neo4j Enterprise | $200+/mois |
| **Queue-based architecture** | RabbitMQ/Redis queue → n8n workers pull | Code refactor majeur |
| **Batch API calls** | OpenRouter batch endpoint (si disponible) | API change |
| **CDN pour static data** | Pre-calcul embeddings + cache CloudFlare | $0-20/mois |

**Resultat**: ~12,000 q/h → ~120,000+ q/h (2,000/min)

---

### Matrice Resumee

| Niveau | Questions/heure | Cout mensuel | Effort | Qui gere |
|--------|----------------|-------------|--------|----------|
| **Actuel** | ~30 | $0 | - | - |
| **x2** | ~120 | $0 | 1-2h | Alexis + Claude |
| **x5** | ~600 | $0 | 3-5h | Alexis + Claude |
| **x10** | ~6,000 | ~$50 | 1 jour | Alexis + Claude |
| **x20** | ~12,000 | ~$100 | 2-3 jours | Alexis + Claude |
| **x100** | ~120,000 | ~$500 | 1 semaine | Alexis + Claude |

---

## 4. BOTTLENECK ACTIONS PLAYBOOK

### Goal
Give Alexis a fast, practical list of actions to unblock throughput/reliability without deep debugging.

---

### 1) API Throughput Bottlenecks (LLM)

**Symptoms**:
- 429 rate limits
- latency spikes
- sudden drop in successful responses

**Fast actions you can do**:
1. Create/add new provider keys (OpenRouter, Groq) and place them in `.env.local`.
2. Increase key pool variables (`OPENROUTER_KEY_*`, `GROQ_API_KEY_*`).
3. Re-run key pool discovery + health checks.
4. Switch heavy pipelines to faster models temporarily.

**Impact**: Immediate req/min increase, better resilience under parallel load.

---

### 2) Compute Bottlenecks (HF Space / workers)

**Symptoms**:
- timeouts on Standard/Graph
- webhook 500 under concurrency

**Fast actions you can do**:
1. Start additional HF Spaces (already using 10 when available).
2. Increase worker count only after passing smoke tests.
3. Reduce concurrency per unstable pipeline, keep high for stable ones.
4. Add/scale Google Run worker services for burst tasks.

**Impact**: Better stability and sustained throughput.

---

### 3) Activation / webhook Bottlenecks

**Symptoms**:
- 404 on webhook path
- workflow not started
- credentials not loaded

**Fast actions you can do**:
1. Re-activate workflows with launch/restore scripts.
2. Verify webhook IDs did not drift after imports.
3. Rebind credentials and re-test with 1-question smoke.

---

### 4) Data bottlenecks (ingestion/enrichment)

**Symptoms**:
- ingest 500 errors
- enrichment partial outputs

**Fast actions you can do**:
1. Run ingestion on Codespaces/GH Actions (not only HF).
2. Split datasets by sector/type and process in parallel batches.
3. Keep garbage outputs archived to rag-storage autosync for forensics.

---

### 5) What to prioritize first (operator order)

1. Restore red pipelines (health)
2. Restore correctness (golden checks)
3. Increase throughput safely (workers/keys)
4. Scale expensive experiments

---

### 6) Toward full mathematical autofix (target architecture)

Yes, target is: **auto-detect → auto-fix code/config → auto-validate** with minimal CLI intervention.

Required components:
- Signature engine (OpenRouter/webhook/n8n/db errors)
- Confidence-scored fix planner
- Auto-apply safe patches
- Automatic rollback on regression
- Golden-based acceptance gate

This means:
- CLI remains for oversight/emergency,
- normal corrections become autonomous by policy.

---

## 5. TEAM AGENTIC PROCESS

### 5.1 Philosophie Multi-Model (Session 26)

**Principe fondamental**: **Opus 4.6 est le cerveau. Sonnet 4.5 et Haiku 4.5 sont les bras.**

Chaque agent Claude Code deploye (VM, Codespace, HF Space) tourne en **Opus 4.6** comme modele principal. Mais pour les taches d'**execution** (pas d'analyse), l'agent Opus delegue a des sous-agents plus rapides et moins couteux via le `Task` tool.

#### Arbre de decision — Quel modele pour quelle tache?

```
                       TACHE RECUE
                           |
                    Analyse / Decision ?
                    /              \
                  OUI              NON (Execution)
                   |                   |
            OPUS 4.6 DIRECT      Complexite ?
            (PAS de delegation)   /          \
                              Simple      Moyen/Complexe
                                |              |
                          HAIKU 4.5      SONNET 4.5
                          via Task       via Task
                          tool           tool
```

#### Quand Opus 4.6 delegue (UNIQUEMENT ces cas)

| Tache | Modele delegue | Mecanisme | Justification |
|-------|---------------|-----------|---------------|
| Recherche internet/web | Sonnet 4.5 | `Task(model: "sonnet", subagent_type: "general-purpose")` | Pas besoin d'analyse profonde pour fetch+summarize |
| Exploration codebase simple | Haiku 4.5 | `Task(model: "haiku", subagent_type: "Explore")` | Pattern matching rapide |
| Glob/Grep paralleles | Haiku 4.5 | `Task(model: "haiku", subagent_type: "Explore")` | Recherches simples en batch |
| Execution commandes batch | Sonnet 4.5 | `Task(model: "sonnet", subagent_type: "Bash")` | npm install, pip install, docker ops |
| Reformattage/Generation repetitive | Sonnet 4.5 | `Task(model: "sonnet", subagent_type: "general-purpose")` | Generation de contenu standard |
| Calculs / verifications numeriques | Haiku 4.5 | `Task(model: "haiku", subagent_type: "general-purpose")` | Arithmetique simple |

#### Quand Opus 4.6 NE delegue PAS (fait lui-meme)

| Tache | Raison |
|-------|--------|
| Analyse de workflows n8n | Necessite comprehension architecturale |
| Decisions de debug / fix | Necessite raisonnement causal |
| Redaction de directives | Necessite coherence globale |
| Pilotage de session | Necessite memoire de session |
| Evaluation de resultats | Necessite jugement qualite |
| Modification de code critique | Necessite precision + contexte |
| Communication avec l'utilisateur | Necessite empathie + contexte |

---

### 5.2 Roles

| Agent | Repo | Localisation | Role | Modele Principal | Delegation |
|-------|------|-------------|------|-----------------|------------|
| **Orchestrateur** | mon-ipad | VM Google Cloud (Termius) | Pilotage UNIQUEMENT, sync, directives, analyse. ZERO tests, ZERO fix workflow | `claude-opus-4-6` | Sonnet/Haiku pour recherches web + exploration |
| **Testeur** | rag-tests | Codespace ephemere / HF Space | Executer tests, mesurer accuracy, rapporter resultats | `claude-opus-4-6` | Haiku pour exploration codebase rapide |
| **Developpeur Web** | rag-website | Codespace ephemere + Vercel | Construire site business, integrer chatbots sectoriels | `claude-opus-4-6` | Sonnet pour generation composants repetitifs |
| **Ingesteur** | rag-data-ingestion | Codespace ephemere | Telecharger datasets, ingerer dans BDD, enrichir | `claude-opus-4-6` | Sonnet pour batch downloads + transformations |
| **Dashboard** | rag-dashboard | Statique (GitHub Pages/Vercel) | Afficher metriques live (read-only) | N/A | N/A |

---

### 5.3 Communication

#### Source de verite partagee

**GitHub est le canal de communication unique entre agents.** Chaque agent:
1. Lit les directives depuis son `CLAUDE.md` (pousse par l'orchestrateur)
2. Ecrit ses resultats dans ses fichiers de sortie (`docs/`, `logs/`, `n8n/`)
3. Commit + push vers GitHub
4. L'orchestrateur lit les resultats depuis GitHub

#### Distribution des directives

```bash
# Depuis mon-ipad (VM) — met a jour les CLAUDE.md de chaque repo satellite
bash scripts/push-directives.sh
```

---

### 5.4 Auto-Stop Protocol

**Regle**: 3 echecs consecutifs → STOP

L'arret premature s'applique a **toutes les echelles de test**:

| Echelle | Seuil d'arret | Raison |
|---------|---------------|--------|
| 5/5 tests | 3 echecs consecutifs | Pipeline fondamentalement casse |
| 10/10 tests | 3 echecs consecutifs apres Q4 | Donnees ou prompt systemique |
| 200q eval | 4 echecs consecutifs (early-stop default) | Eviter gaspillage de temps |
| 1000q eval | 4 echecs consecutifs | Idem |

#### Procedure apres auto-stop

1. **Documenter** le pattern d'echec dans `logs/diagnostics/`
2. **Analyser** les executions avec les 2 outils (node-analyzer + analyze_n8n_executions)
3. **Signaler** a l'orchestrateur (commit + push)
4. **NE PAS retenter** tant que le fix n'est pas applique par l'orchestrateur

---

### 5.5 Bottleneck Resolution Protocol

**Principe**: Tests en background, agent sur les problèmes

**L'agent ne doit JAMAIS rester passif pendant qu'un test tourne.**
Les pipelines fonctionnels sont lancés en `nohup` background avec auto-commit.
Le temps de l'agent est consacré à:
1. Diagnostiquer et résoudre les pipelines bloqués
2. Améliorer la documentation (CLAUDE.md, knowledge-base, fixes-library)
3. Préparer la phase suivante

#### Classification des bottlenecks

| Type | Priorité | Temps résolution | Exemples |
|------|----------|-----------------|----------|
| **Infrastructure** | P0 — Immédiat | 10-30 min | TCP bloqué, OOM, Docker crash, n8n down |
| **Rate-limit** | P1 — Court terme | 5-15 min | OpenRouter 429, Jina quota, API throttle |
| **Code workflow** | P2 — Moyen terme | 30-60 min | [object Object], node crash, cache stale |
| **Data** | P3 — Ponctuel | 10-20 min | IDs collision, dedup cassé, dataset manquant |
| **Modèle LLM** | P4 — Long terme | 1h+ | Hallucinations, mauvais scores, prompt tuning |

#### Procédure de résolution

```
BOTTLENECK DÉTECTÉ
    |
    ├─ Est-ce dans fixes-library ? → OUI → Appliquer le fix documenté
    |                              → NON → Investiguer
    |
    ├─ Classification (P0-P4)
    |
    ├─ P0/P1 : Résoudre IMMÉDIATEMENT
    |   ├─ Contourner si possible (autre host, autre modèle)
    |   └─ Documenter le contournement
    |
    ├─ P2/P3 : Résoudre pendant que les tests tournent en background
    |   ├─ Isoler le pipeline bloqué
    |   ├─ Lancer les autres en background
    |   └─ Diagnostiquer avec node-analyzer + analyze_n8n_executions
    |
    └─ P4 : Planifier pour la session suivante
        ├─ Documenter dans improvements-roadmap.md
        └─ Continuer avec les pipelines actuels
```

---

### 5.6 Priorisation Cross-Pipeline et Low-Hanging Fruit

**Principe**: Impact transversal AVANT fix isole

Avant chaque fix, repondre: **"Ce fix debloque combien de pipelines ?"**
Un fix qui debloque 4 pipelines passe TOUJOURS avant un fix qui en debloque 1.

**Principe**: Quick-win AVANT fix complexe

A impact egal, commencer par le fix le plus rapide. Reevaluer apres chaque quick-win.

#### Matrice de decision

```
Impact transversal HAUT + Quick-win  → GOLD   (faire en PREMIER)
Impact transversal HAUT + Long       → SILVER (faire en SECOND)
Impact transversal BAS  + Quick-win  → BRONZE (faire en TROISIEME)
Impact transversal BAS  + Long       → BACKLOG (faire en DERNIER)
```

---

### 5.7 Fixes Library Partagee

**Architecture**:
```
mon-ipad/technicals/fixes-library.md  ← MASTER (source de verite)
  |
  +-- rag-tests/technicals/fixes-library.md       (copie en lecture)
  +-- rag-website/technicals/fixes-library.md      (copie en lecture)
  +-- rag-data-ingestion/technicals/fixes-library.md (copie en lecture)
```

**Workflow**:
1. **Decouverte**: n'importe quel agent decouvre un bug et le documente
2. **Remontee**: l'agent commit le diagnostic dans son repo + push
3. **Documentation**: l'orchestrateur ajoute le fix dans `technicals/fixes-library.md` (master)
4. **Distribution**: `push-directives.sh` pousse la copie vers les satellites
5. **Consultation**: chaque agent consulte sa copie locale avant tout debug (ETAPE 0)

---

### 5.8 Protocole de Session Type

#### Demarrage (5 min)

```
1. Lire session-state.md (memoire de travail)
2. Lire docs/status.json (metriques live)
3. Lire directives/status.md (resume session precedente)
4. Verifier fixes-library.md pour symptomes connus
5. Identifier objectif de session + pipeline prioritaire
```

#### Execution (boucle)

```
6. DIAGNOSTIQUER → double analyse (node-analyzer + analyze_n8n_executions)
7. FIXER → API REST n8n (1 noeud a la fois)
8. TESTER → quick-test.py --questions 5 minimum
9. VALIDER → quick-test.py --questions 10 (5/5 minimum)
10. SYNC → n8n/sync.py
11. COMMIT+PUSH → origin + repos concernes
```

#### Fin de session (10 min)

```
12. Sync workflows finaux
13. Generer status (generate_status.py)
14. MAJ session-state.md
15. MAJ technicals/ si decouvertes
16. MAJ fixes-library.md si fixes
17. Commit + push TOUS repos impactes
18. MAJ directives/status.md (DERNIER)
```

---

## 6. RAG RESEARCH 2026

### 6.1 Multi-Agent RAG Patterns

#### MA-RAG (arXiv:2505.20096)

- Pattern: **Specialized agents per pipeline stage** — one agent retrieves, one re-ranks, one generates.
- Key finding: Stage-level specialization reduces hallucination by 23% vs. monolithic RAG.
- Relevance: Our Orchestrator V10.1 already approximates this; formalize with explicit agent roles per n8n sub-workflow.

#### A-RAG — Adaptive RAG (arXiv:2602.03442)

- Pattern: **Hierarchical retrieval tools, LLM selects which tool to invoke at runtime.**
- LLM receives tool descriptions (vector search, graph query, SQL) and picks based on query type.
- Key finding: Reduces unnecessary retrieval calls by 31% while maintaining accuracy within 2%.
- Relevance: Direct blueprint for Orchestrator's query routing logic — replace heuristic routing with LLM tool-call routing.

#### RouteRAG — Per-Query Adaptive Routing

- Rule-based classifier assigns each query to the optimal pipeline:
  - Simple factual → vector (Standard RAG)
  - Multi-hop / entity-rich → graph (Graph RAG)
  - Numerical / formula → SQL (Quantitative RAG)
- Key finding: Adaptive routing alone gains +6.2% accuracy over static pipeline assignment.
- Relevance: Implement as a lightweight pre-classifier node in Orchestrator before dispatching to sub-workflows.

---

### 6.2 Retrieval Fusion Techniques

#### RRF — Reciprocal Rank Fusion

```
Score(d) = Σ  1 / (60 + rank_i(d))
           i
```

- Fuse results from vector search + BM25 (keyword) before re-ranking.
- Key finding: +18.5% MRR over single-retrieval baseline on BEIR benchmark.
- Implementation: Add a Merge node in Standard RAG V3.4 that combines Pinecone results (semantic) with BM25 results (keyword), then RRF-score before passing to LLM.
- Cost: Zero external API calls — pure math over ranked lists.

---

### 6.3 GraphRAG vs Standard RAG Benchmarks

#### Entity-Rich Query Performance (arXiv:2502.11371)

| Pipeline | Accuracy | Query Type |
|----------|----------|------------|
| GraphRAG | 80.0% | Entity-rich, multi-hop |
| Vector RAG | 50.83% | Same queries |

- GraphRAG wins on: relationship chains, entity disambiguation, multi-hop reasoning.
- Vector RAG wins on: semantic similarity, paraphrased factual questions.
- Combined (Graph + Vector): 85.2% on mixed benchmarks.

#### Our Current State vs Targets

| Pipeline | Accuracy | Target | Status | Priority Action |
|----------|----------|--------|--------|-----------------|
| Standard | 87.5% | 85% | PASS | Add RRF fusion (+2-3%) |
| Graph | 40.9% | 70% | FAIL | Fix entity disambiguation in Neo4j |
| Quantitative | 30% | 85% | INVALID | Apply CompactRAG for formula queries |
| Orchestrator | ON HOLD | 70% | BROKEN | Add RouteRAG classifier |

---

### 6.4 Structured Data: CompactRAG

- Pattern: **Pre-compute QA pairs offline** for structured/tabular data; store in vector index alongside raw documents.
- Process: At ingestion time, generate synthetic Q&A from tables, formulas, financial reports → embed → store in Pinecone.
- Key finding: +12% accuracy on formula/numerical queries vs. raw-document retrieval.
- Relevance: **Highest ROI fix for Quantitative pipeline.** Ingestion V3.1 should generate QA pairs during enrichment, stored under `doc_type: compact_qa` in Pinecone metadata.

---

### 6.5 Late Chunking (Jina AI, arXiv:2409.04701)

- Embed le document entier → **puis** chunker les embeddings (inverse du pipeline classique)
- **+10-12% retrieval accuracy** sur docs avec références anaphoriques (pronoms → entités antérieures)
- **Jina API supporte nativement**: `late_chunking=True` dans les paramètres d'API
- **Pas de coût LLM** (vs Contextual Retrieval d'Anthropic qui nécessite LLM call par chunk)
- Action: Ré-ingérer les 3 plus grands namespaces avec late chunking, mesurer amélioration

---

### 6.6 RAGAS Metrics — Standard 2026 Obligatoire

La simple métrique "accuracy" est **insuffisante en 2026**. Standard enterprise:

| Métrique | Définition | Seuil enterprise |
|---------|-----------|-----------------|
| **Faithfulness** | % statements dans la réponse sourcés dans le contexte | >= 95% |
| **Context Recall** | % infos pertinentes effectivement récupérées | >= 85% |
| **Hallucination rate** | 1 - Faithfulness | <= 2% |
| **Mean latency** | Temps moyen par question | <= 2.5s |
| **Context Precision** | % docs récupérés qui sont pertinents | >= 80% |

**Action immédiate**: Ajouter RAGAS à `eval/quick-test.py` et `eval/iterative-eval.py`. Tracker faithfulness et context_recall en plus de accuracy. Ces métriques sont requises pour Phase Gate eligibility.

---

### 6.7 Enterprise Production Gates 2026

Ces seuils définissent la "production readiness" en 2026:

```
Faithfulness     >= 95%   (actuellement non mesuré)
Hallucination    <= 2%    (actuellement non mesuré)
Helpfulness      >= 90%   (actuellement non mesuré)
Mean latency     <= 2.5s  (actuellement non mesuré)
Accuracy         >= 85%   (Standard: PASS, Quant/Graph: FAIL)
```

---

### 6.8 Top 10 Actions Prioritaires (Classées par Impact) — Updated Session 79

| Rank | Action | Impact | Effort | Target | Source |
|------|--------|--------|--------|--------|--------|
| **1** | **Cohere Rerank 3.5** post-retrieval | +23-30% precision | LOW (MCP tool ready) | Std+Graph+Orch | Cohere blog 2025 |
| **2** | **CRAG grading layer** — filter irrelevant retrievals | +10-15% accuracy | LOW-MED (LLM grading prompt) | **Graph (40.9%)** | arXiv:2401.15884 |
| **3** | **Late chunking Jina** `late_chunking=True` | +2-4% retrieval | LOW (parameter flag) | Standard | arXiv:2409.04701 |
| **4** | **RAGAS faithfulness + context recall** | Enterprise gates | MED (2-4h) | All | RAGAS 2026 |
| **5** | **Adaptive Routing (Higress-RAG)** — intent classifier + semantic cache | +5-10% routing | MED | Orchestrator | arXiv:2602.23374 |
| **6** | **A-RAG hierarchical tools** — multi-turn agentic retrieval | +8-12% accuracy | MED (open-source) | Std+Orch | arXiv:2602.03442 |
| **7** | **BM25/keyword + RRF fusion** | +15-25% domain queries | MED | Std+Quant | RRF literature |
| **8** | **Website GEO optimization** — TLDR-first, structured data, FAQ schema | SEO/GEO traffic | MED | rag-website | GEO 2026 guides |
| **9** | **Nano Banana video demos** — 4 sector product videos | Marketing | MED | rag-website | Google Nano Banana 2 |
| **10** | **Per-product color/UX differentiation** — psychology-driven palettes | Conversion +2-3% | LOW-MED | All 3 sites | JMSR 2025 |

**Previous top 10 items moved to backlog where not superseded.**

---

### 6.9 Key Papers References

| Paper | arXiv ID | Key Contribution |
|-------|----------|-----------------|
| MA-RAG: Multi-Agent RAG | arXiv:2505.20096 | Stage-level specialization, -23% hallucination |
| A-RAG: Adaptive RAG | arXiv:2602.03442 | LLM tool selection, -31% unnecessary calls |
| DeepRead: Document Structure-Aware | arXiv:2602.05014 | Document hierarchy priors, multi-turn evidence |
| Agentic-R: Learning to Retrieve | arXiv:2601.11888 | Retriever fine-tuning pour agentic search |
| Agentic RAG Survey | arXiv:2501.09136 | Taxonomie complète: reflection, planning, tool use |
| GraphRAG vs Vector RAG | arXiv:2502.11371 | GraphRAG 80% vs 50.83% on entity queries |
| Late Chunking | arXiv:2409.04701 | +10-12% retrieval accuracy, no LLM cost |
| RAG-Studio: Domain Adaptation | ACL EMNLP 2024 | Synthetic data pour fine-tuning domain-specific RAG |
| RRF: Reciprocal Rank Fusion | Cormack et al. | +18.5% MRR, fuse vector + BM25 |
| Higress-RAG | arXiv:2602.23374 | MCP-based dual hybrid retrieval + adaptive routing + CRAG |
| RouteRAG (RL routing) | arXiv:2512.09487 | RL-based text/graph routing, +7.7 F1, GRPO training |
| RAGLens | arXiv:2512.08892 | Sparse autoencoders for hallucination detection in RAG |
| RAGRouter | arXiv:2505.23052 | Contrastive learning query router for multiple RAG LLMs |
| CRAG | arXiv:2401.15884 | Corrective RAG with retrieval quality evaluation + fallback |
| Cohere Rerank 3.5 | Cohere blog 2025 | +26.4% cross-lingual, +23.4% vs hybrid search |
| RAG-MCP | arXiv:2505.03275 | Semantic retrieval for MCP server selection, -50% tokens |
| RoutIR | arXiv:2601.10644 | Fast serving framework for retrieval pipelines |
| Self-Healing RAG | AIAnytime 2025 | 3-layer auto-recovery: retrieval, ranking, learning |

---

## APPENDIX: Document History

| Session | Changes | Date |
|---------|---------|------|
| 79 | SOTA research update: 12 new papers, top 10 reprioritized, GEO+marketing | 2026-03-07 |
| 73 | Consolidated 6 separate project docs into single roadmap | 2026-03-07 |
| 42 | Repo health inspection, 70+ new items | 2026-02-22 |
| 40 | Cross-pipeline bottleneck prioritization | 2026-02-22 |
| 39 | Enterprise metrics 2026 standards | 2026-02-22 |
| 26 | Multi-model delegation strategy | 2026-02-19 |
| 25 | Initial improvements roadmap created | 2026-02-19 |

---
