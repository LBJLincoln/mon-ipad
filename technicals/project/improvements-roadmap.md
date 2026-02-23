# Improvements Roadmap — Centralized

> Last updated: 2026-02-23T17:00:00+01:00 (Session 42 — Major infra deployment)
> **Document centralisé de TOUTES les améliorations possibles**, classées par catégorie et priorité.
> Référencé par CLAUDE.md. Mis à jour à chaque session.

---

## TABLE DES MATIERES

1. [Pipelines RAG — Accuracy](#1-pipelines-rag--accuracy)
2. [Infrastructure — Scalabilité 1000q+](#2-infrastructure--scalabilite)
3. [n8n Workflows — Optimisations](#3-n8n-workflows)
4. [Databases — Enrichissement](#4-databases)
5. [Evaluation — Méthodologie](#5-evaluation)
6. [Website — Contenu & UX](#6-website)
7. [Documentation — Structure](#7-documentation)
8. [DevOps — CI/CD & Monitoring](#8-devops)

---

## 1. PIPELINES RAG — ACCURACY

### 1.1 Quantitative (78.3% → 85%) — PRIORITE 1

| # | Amélioration | Impact | Effort | Statut |
|---|-------------|--------|--------|--------|
| Q1 | Timeouts/retries HTTP Request (90s, 3 retries, 8s wait) | +3pp | Fait | APPLIQUE session 25 |
| Q2 | SQL templates pour questions simples (bypass LLM) | +2pp | Fait | APPLIQUE session 25 |
| Q3 | Sample data dans le prompt LLM | +1pp | Fait | APPLIQUE session 25 |
| Q4 | Rotation multi-modeles (Llama/Qwen/Gemma par minute) | +2pp | Moyen | A FAIRE |
| Q5 | Schema statique compact dans le prompt | +1pp | Faible | A FAIRE |
| Q6 | ILIKE au lieu de = pour les noms d'entreprise | +0.5pp | Faible | A FAIRE |
| Q7 | Delai inter-questions dans eval scripts (8s pour quant) | +1pp | Faible | A FAIRE |
| Q8 | CompactRAG : pre-compute QA pairs pour questions frequentes | +2pp | Eleve | PLANIFIE |
| Q9 | BM25 hybrid search pour contexte SQL | +1pp | Moyen | PLANIFIE |

### 1.2 Graph (68.7% → 70%) — PRIORITE 2

| # | Amélioration | Impact | Effort | Statut |
|---|-------------|--------|--------|--------|
| G1 | Entity disambiguation Neo4j (fuzzy matching) | +1.5pp | Moyen | A FAIRE |
| G2 | Enrichir graph avec sector datasets (juridique, finance) | +2pp | Eleve | DATASETS PRETS |
| G3 | Community summaries multilingual (fr/en) | +0.5pp | Moyen | A FAIRE |
| G4 | Traversal depth adaptatif (2→3 hops pour questions complexes) | +0.5pp | Faible | A FAIRE |

### 1.3 Standard (85.5% — PASS)

| # | Amélioration | Impact | Effort | Statut |
|---|-------------|--------|--------|--------|
| S1 | Late chunking (Jina late_chunking=True) | +1pp | Moyen | PLANIFIE |
| S2 | Hybrid search (dense + sparse) | +1pp | Moyen | A FAIRE |
| S3 | Reranking ameliore (cross-encoder) | +0.5pp | Faible | A FAIRE |

### 1.4 Orchestrator (80.0% — PASS)

| # | Amélioration | Impact | Effort | Statut |
|---|-------------|--------|--------|--------|
| O1 | A-RAG (agentic hierarchical retrieval) | +3pp | Eleve | PLANIFIE |
| O2 | Routing dynamique base sur confidence scores | +1pp | Moyen | A FAIRE |

---

## 2. INFRASTRUCTURE — SCALABILITE

### 2.1 Capacité actuelle vs cible

| Composant | Actuel | Cible 1000q | Cible 10Kq | Action |
|-----------|--------|------------|------------|--------|
| **n8n concurrency** | **3 workers (queue mode)** | 5 workers | 10 workers | **DEPLOYED Session 42** |
| **OpenRouter rate** | ~20 req/min (1 key) → **~100 req/min (5 keys)** | ~100 req/min | ~200 req/min | **Multi-key DEPLOYED Session 42** |
| **RAM** | **~400MB (VM, n8n removed)** / 16GB (HF) | 16GB | 32GB | **VM n8n removed Session 42** |
| **PostgreSQL** | Supabase free | Supabase free | Supabase Pro | OK pour 1000q |
| **Pinecone** | 10K vecteurs | 50K vecteurs | 100K vecteurs | Ingestion Phase 2 |
| **Neo4j** | 19K nodes | 50K nodes | 200K nodes (max free) | Ingestion secteurs |
| **Eval parallelism** | Sequential | 3 parallel | 10 parallel | asyncio + aiohttp |

### 2.2 HF Space — Améliorations possibles

| # | Amélioration | Impact | Effort | Statut | Session |
|---|-------------|--------|--------|--------|---------|
| H1 | Connecter Supabase depuis HF Space (env vars) | Quantitative fonctionne | Faible | **FAIT Session 42** | 42 |
| H2 | Ajouter 3 workers n8n dans le Dockerfile | 3x throughput | Moyen | **FAIT Session 42** | 42 |
| H3 | Migrer SQLite → PostgreSQL persistant (Supabase externe) | **CRITICAL** — Pas de perte au reboot | Moyen | **FAIT Session 42** (schema `n8n_engine`) | 42 |
| H4 | Exporter les fixes VM vers HF Space | Workflow a jour | Faible | **FAIT Session 42** (13 workflows) | 42 |
| H5 | Multi-API-key OpenRouter (5 per-pipeline keys) | 5x rate limit | Faible | **FAIT Session 42** (env vars ready) | 42 |
| H6 | Keep-alive plus fiable (webhook interne) | Uptime 99.9% | Faible | FAIT (cron VM) | — |
| H7 | HF /data persistent volume activation | Survit aux rebuilds (alternative à H3) | Faible | **SUPERSEDED by H3** | 39 |
| **H8** | **Robust entrypoint.sh avec verification** | Detect failed activations | Faible | **FAIT Session 42** (import+activate+verify) | 42 |
| **H9** | **Activation health check POST-deploy** | Test webhooks before marking success | Faible | **FAIT Session 42** (9 webhooks verified) | 42 |
| **H10** | **Queue mode (3 workers, concurrency=3 each)** | 7x throughput (23→162 req/s) | Moyen | **FAIT Session 42** | 42 |
| **H11** | **Worker concurrency tuning** | Optimize per-workflow type (I/O vs CPU) | Faible | Phase 2+ | Session analyzer |

### 2.3 Estimation temps pour 1000q par pipeline

| Config | Standard | Graph | Quantitative | Orchestrator | Total 4000q |
|--------|----------|-------|-------------|-------------|-------------|
| **Actuel** (seq, 1 worker) | ~3h | ~5h | ~8h | ~5h | ~21h |
| **Optimise** (3 workers, 8s delay) | ~1h | ~2h | ~3h | ~2h | ~8h |
| **Ideal** (10 workers, multi-key) | ~20min | ~40min | ~1h | ~40min | ~2.5h |

### 2.4 n8n Queue Mode — 7x Performance Multiplier (2026 Best Practice)

**RESEARCH INSIGHT (Session Analyzer 40)**: n8n official benchmarks show **7x throughput** with queue mode.

**Current Setup** (Sequential, Single Instance):
- VM n8n: main process handles webhooks + executions (no workers)
- HF Space n8n: main process handles webhooks + executions (no workers)
- Throughput: 23 req/s (n8n baseline)

**Queue Mode Architecture** (Target Phase 2+):
```
Main Instance (receives webhooks) → Redis Queue → 3 Workers (execute workflows)
```

**Performance Gains**:
| Config | Workers | Throughput | Multiplier | Source |
|--------|---------|------------|------------|--------|
| Baseline | 0 | 23 req/s | 1x | n8n docs [7] |
| Queue mode | 3 | 162 req/s | 7x | n8n docs [7] |
| Max tested | 10 | 220 req/s | 9.5x | n8n docs [7] |

**Configuration Requirements**:
```bash
# ALL instances (main + workers) need:
EXECUTIONS_MODE=queue
N8N_ENCRYPTION_KEY=<same-key-everywhere>  # CRITICAL
DB_TYPE=postgresdb  # SQLite NOT supported
QUEUE_BULL_REDIS_HOST=localhost
QUEUE_BULL_REDIS_PORT=6379

# Worker-specific:
N8N_WORKER_CONCURRENCY=3  # Tune per workflow type
```

**Worker Concurrency Tuning**:
| Workflow Type | Concurrency | Rationale | Current Pipelines |
|---------------|-------------|-----------|-------------------|
| I/O-bound (HTTP, DB) | 5-10 | Waiting time dominates | Standard, Graph, Quant |
| CPU-bound (local LLM) | 1-2 | Avoid resource contention | None (all use OpenRouter) |
| Mixed | 3-5 | Balance | Orchestrator (routing + HTTP) |

**Trade-offs**:
| Aspect | Baseline | Queue Mode | Impact |
|--------|----------|------------|--------|
| Throughput | 23 req/s | 162 req/s | +700% |
| Latency | 100-200ms | +50-100ms overhead | Acceptable for batch |
| Complexity | Low | Medium | PostgreSQL + Redis required |
| DB requirement | SQLite OK | PostgreSQL ONLY | HF Space migration needed |

**Implementation Priority**:
- **Phase 1 (200q)**: SKIP (sequential OK, baseline sufficient)
- **Phase 2 (1000q)**: **EVALUATE** (3 workers = 3-5x faster, 1000q in ~3h instead of ~15h)
- **Phase 3+ (10Kq)**: **REQUIRED** (10 workers minimum, 10Kq in ~5h instead of ~150h)

**HF Space Deployment** (docker-compose.yml):
```yaml
services:
  n8n-main:
    image: n8nio/n8n:2.8.3
    environment:
      EXECUTIONS_MODE: queue
      DB_TYPE: postgresdb
      DB_POSTGRESDB_HOST: external-supabase  # NOT SQLite
    ports:
      - "5678:5678"

  n8n-worker-1:
    image: n8nio/n8n:2.8.3
    command: worker
    environment:
      EXECUTIONS_MODE: queue
      N8N_WORKER_CONCURRENCY: 3

  n8n-worker-2:
    image: n8nio/n8n:2.8.3
    command: worker
    environment:
      EXECUTIONS_MODE: queue
      N8N_WORKER_CONCURRENCY: 3

  n8n-worker-3:
    image: n8nio/n8n:2.8.3
    command: worker
    environment:
      EXECUTIONS_MODE: queue
      N8N_WORKER_CONCURRENCY: 3

  redis:
    image: redis:7-alpine
```

**Blocking Dependencies**:
1. HF Space must migrate SQLite → PostgreSQL (improvement H3)
2. External PostgreSQL (Supabase) must be configured as n8n DB
3. Redis container added to docker-compose
4. N8N_ENCRYPTION_KEY must be synchronized across all instances

**References**:
- [7] n8n queue mode docs: https://docs.n8n.io/hosting/scaling/queue-mode/
- [8] Performance benchmarks: https://docs.n8n.io/hosting/scaling/performance-benchmarking/
- [9] Worker concurrency guide: https://evalics.com/blog/n8n-queue-mode-explained-scale-workers-and-avoid-pitfalls
- [10] Production setup: https://nextgrowth.ai/scaling-n8n-queue-mode-docker-compose/

### 2.5 Architecture cible pour Phase 2 (1000q)

```
VM (mon-ipad)
  └─ Pilotage + monitoring

HF Space (nomos-rag-engine) — 16GB RAM, $0
  ├─ n8n main + 3 workers
  ├─ PostgreSQL (local, persistent volume)
  ├─ Redis (queue mode)
  └─ Nginx (reverse proxy)

Cloud DBs
  ├─ Pinecone (50K vecteurs)
  ├─ Neo4j Aura (50K nodes)
  └─ Supabase (40 tables, 17K+ rows)

Eval
  └─ VM ou Codespace envoie les questions → HF Space webhooks
```

---

## 3. N8N WORKFLOWS

### 3.1 Core Optimizations

| # | Amélioration | Impact | Effort | Statut |
|---|-------------|--------|--------|--------|
| N1 | Workflow versioning automatique (snapshot avant chaque modification) | Fiabilite | Moyen | A FAIRE |
| N2 | Health check endpoint dedié (/webhook/health) | Monitoring | Faible | A FAIRE |
| N3 | Metrics Prometheus via n8n metrics endpoint | Observabilite | Faible | PARTIEL (N8N_METRICS=true) |
| N4 | Error notification webhook (Slack/Discord) | Alerting | Faible | A FAIRE |
| N5 | Workflow export automatique apres chaque activation | Backup | Moyen | A FAIRE |

### 3.2 Queue Mode & Scalability (2026 Best Practices)

| # | Amélioration | Impact | Effort | Statut |
|---|-------------|--------|--------|--------|
| **N6** | **Configurer QUEUE_HEALTH_CHECK_ACTIVE=true** pour /healthz readiness | Detect worker failures | Faible | RECOMMANDE |
| **N7** | **Worker count = CPU cores** (3 workers sur HF Space 2-core) | Optimal throughput | Faible | A FAIRE |
| **N8** | **Binary data → S3 external storage** (required for queue mode) | Prevent file system errors | Moyen | SI BINARIES NEEDED |
| **N9** | **Concurrency control per workflow** (limite 5 executions simultanées) | Prevent rate-limit cascade | Faible | RECOMMANDE |
| **N10** | **Redis queue persistence** (AOF enabled) | Survive Redis restarts | Faible | A FAIRE |

---

## 4. DATABASES

| # | Amélioration | Impact | Effort | Statut |
|---|-------------|--------|--------|--------|
| D1 | Ingerer 7,609 items sectoriels dans Pinecone | +2pp accuracy | Eleve | DATASETS PRETS |
| D2 | Enrichir Neo4j avec entites juridiques francaises | +1pp Graph | Eleve | DATASETS PRETS |
| D3 | Ajouter BM25 index dans Pinecone (sparse vectors) | +1pp hybrid | Moyen | PLANIFIE |
| D4 | Indexer les 14 benchmarks Phase 2 dans Pinecone | Phase 2 requis | Eleve | A FAIRE |
| D5 | Creer des tables Supabase pour les donnees sectorielles | Quant sector | Moyen | A FAIRE |

---

## 5. EVALUATION

### 5.1 Enterprise Production Metrics (2026 Standards) — BLOCKING PHASE GATE

**CRITICAL INSIGHT (Session Analyzer 40)**: Current system only tracks 1/7 enterprise metrics. Phase 2+ gates REQUIRE comprehensive metrics.

| # | Métrique | Cible 2026 | Outil | Effort | Statut | Recherche |
|---|----------|-----------|-------|--------|--------|-----------|
| **E0** | **Accuracy** | >= 75% | Manual fuzzy match | — | ✅ IMPLEMENTED | — |
| **E1** | **Faithfulness** | >= 95% | Ragas | Moyen | ❌ **BLOCKING Phase 2+** | [1] [2] [3] |
| **E2** | **Context Recall** | >= 85% | Ragas | Moyen | ❌ **BLOCKING Phase 2+** | [1] [2] [3] |
| **E3** | **Context Precision** | >= 80% | Ragas | Moyen | ❌ HIGH Priority | [1] [2] |
| **E4** | **Answer Relevancy** | >= 90% | Ragas | Moyen | ❌ HIGH Priority | [1] [2] |
| **E5** | **Hallucination Rate** | <= 2% | Ragas (inverse faithfulness) | Moyen | ❌ **BLOCKING Phase 2+** | [1] [3] |
| **E6** | **Latency (p95)** | <= 2.5s | Custom (track execution time) | Faible | ❌ MEDIUM Priority | [3] |

**References**:
- [1] Ragas metrics: https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/
- [2] RAG evaluation guide: https://www.evidentlyai.com/llm-guide/rag-evaluation
- [3] Enterprise best practices: https://labelyourdata.com/articles/llm-fine-tuning/rag-evaluation

**Implementation Roadmap** (Session 40+):
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

# Step 4: Store in docs/status.json
{
    "faithfulness": result["faithfulness"],
    "context_recall": result["context_recall"],
    "context_precision": result["context_precision"],
    "answer_relevancy": result["answer_relevancy"],
    "hallucination_rate": 1 - result["faithfulness"]
}
```

### 5.2 Advanced RAG Techniques — 2026 Research Insights

**Sources**: arXiv 2026, industry benchmarks, n8n queue mode docs

| # | Technique | Impact | Effort | Pipeline | Priorité | Recherche |
|---|-----------|--------|--------|----------|----------|-----------|
| **E7** | **Adaptive RAG** (SELF-RAG, CRAG) | +5-10% accuracy | Élevé | Orchestrator | Phase 3+ | [4] [5] |
| **E8** | **Hybrid Retrieval** (dense + BM25) | +10-15% domain queries | Moyen | Standard, Quant | **Phase 2** | [5] [6] |
| **E9** | **Late Chunking** (Jina v3) | +3-5% context precision | Faible | Standard | **Phase 2+** | [5] |
| **E10** | **Cross-encoder Reranking** | +3-5% accuracy, +15% precision | Faible | All pipelines | **Phase 2** | [5] [6] |
| E11 | Evaluation parallele avec asyncio | 3x speedup eval | Moyen | Infrastructure | A FAIRE | — |
| E12 | Dashboard live accuracy en temps reel | Visibilite | Faible | PARTIEL (SSE) | — | — |
| E13 | A/B testing entre versions de workflows | Qualite | Eleve | Infrastructure | PLANIFIE | [2] |
| **E14** | **Integrer RAGAS dans CI/CD** | Regression detection | Moyen | **RECOMMANDE** | [1] [2] |
| **E15** | **Component-level eval** (retriever-only) | Pinpoint failures | Moyen | A FAIRE | [2] |

**References**:
- [4] Adaptive RAG: https://arxiv.org/abs/2501.07391
- [5] RAG 2026 trends: https://squirro.com/squirro-blog/state-of-rag-genai
- [6] Hybrid retrieval: https://www.edenai.co/post/the-2025-guide-to-retrieval-augmented-generation-rag

**Details**:
- **Adaptive RAG**: Dynamically adjusts retrieval strategy based on query complexity (SELF-RAG critiques outputs, CRAG corrects retrieved data)
- **Hybrid Retrieval**: Combines semantic search (embeddings) + keyword search (BM25) for +10-15% on domain-specific queries
- **Late Chunking**: Jina v3 feature — chunk AFTER embedding (preserves context), parameter: `late_chunking=True`
- **Cross-encoder Reranking**: Outperforms bi-encoder for final ranking (current: Cohere exhausted, alternative: Jina Reranker v2 free)

### 5.3 Autonomous Testing Architecture (Prevent Session 39 PID Deaths)

**ROOT CAUSE ANALYSIS (Sessions 33, 38, 39)**:
- All 4 pipeline PIDs died prematurely (graph, quant completed; standard, orch died)
- Causes: git index.lock conflicts (parallel --push), HF Space overload, Orchestrator timeouts, rate-limits
- Data loss: ZERO (tested_ids.json saved), but TIME loss: ~6 hours wasted

**SOLUTION**: Self-healing autonomous architecture

| # | Amélioration | Impact | Effort | Statut | Session |
|---|-------------|--------|--------|--------|---------|
| **E16** | **Auto-recovery logic** (retry on rate-limit, stop on 3 failures) | No manual restart | Moyen | **PRIORITE 1** | 40 |
| **E17** | **Structured JSON logging** (not just print) | Observability | Faible | A FAIRE | 40 |
| **E18** | **Auto-commit every 15 min** during long runs | Never lose results | Faible | **PRIORITE 1** | 40 |
| **E19** | **Progress webhook POST to n8n** every 15 min | Real-time dashboard | Faible | RECOMMANDE | 40 |
| **E20** | **Kill switch** (auto-stop if disk > 90% or RAM > 95%) | Prevent VM crash | Faible | RECOMMANDE | 40 |
| **E21** | **Self-healing nohup wrapper** around run-eval-parallel.py | 10+ hrs autonomous | Moyen | **PRIORITE 1** | 40 |
| **E22** | **Git lock file avoidance** (single commit thread, not per-pipeline) | No conflicts | Faible | **PRIORITE 1** | 40 |
| **E23** | **HF Space health check** before every batch (webhook 200 test) | Early failure detection | Faible | **PRIORITE 1** | 40 |

**Implementation Template** (Session 40):
```python
# eval/autonomous_wrapper.py
import subprocess, time, json, os
from pathlib import Path

def auto_commit_thread():
    """Commit every 15 min, single thread to avoid git lock conflicts"""
    while True:
        time.sleep(900)  # 15 min
        subprocess.run(["python3", "eval/generate_status.py"])
        subprocess.run(["git", "add", "docs/", "logs/"])
        subprocess.run(["git", "commit", "-m", "auto: eval progress checkpoint"])
        subprocess.run(["git", "push", "origin", "main"])

def health_check(n8n_host, webhook_path):
    """Test webhook responds before starting batch"""
    resp = requests.post(f"{n8n_host}{webhook_path}", json={"query": "test"}, timeout=10)
    return resp.status_code == 200

def run_autonomous(pipeline, max_questions, batch_size):
    """Self-healing wrapper with auto-recovery"""
    # Start auto-commit thread
    import threading
    threading.Thread(target=auto_commit_thread, daemon=True).start()

    # Pre-flight health check
    if not health_check(N8N_HOST, WEBHOOK_PATHS[pipeline]):
        print(f"ABORT: {pipeline} webhook not responding")
        return

    # Run with retries
    consecutive_failures = 0
    tested = 0
    while tested < max_questions:
        try:
            result = test_question(pipeline, batch_size)
            if result["success"]:
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                if consecutive_failures >= 3:
                    print(f"AUTO-STOP: {pipeline} 3 consecutive failures")
                    break
            tested += batch_size

            # Resource check
            disk_usage = os.statvfs('/').f_bavail / os.statvfs('/').f_blocks
            if disk_usage < 0.1:  # < 10% free
                print("KILL SWITCH: disk > 90%")
                break

        except Exception as e:
            print(f"ERROR: {e}, retrying in 30s...")
            time.sleep(30)
```

---

## 6. WEBSITE

| # | Amélioration | Impact | Effort | Statut |
|---|-------------|--------|--------|--------|
| W1 | Integrer vrais docs sectoriels (BTP/Industrie/Finance/Juridique) | Business | Moyen | DATASETS PRETS |
| W2 | Chat live avec pipeline selection | UX | Moyen | PARTIEL |
| W3 | Dashboard public avec metriques accuracy | Credibilite | Faible | FAIT (Vercel) |
| W4 | Videos sectorielles (scripts Kimi) | Marketing | Moyen | SCRIPTS PRETS |

---

## 7. DOCUMENTATION

| # | Amélioration | Impact | Effort | Statut |
|---|-------------|--------|--------|--------|
| DOC1 | knowledge-base.md enrichi a chaque session | Performance agent | Continu | EN COURS |
| DOC2 | fixes-library.md enrichi a chaque fix | Debug rapide | Continu | EN COURS |
| DOC3 | improvements-roadmap.md (CE FICHIER) | Vision produit | Continu | EN COURS |
| DOC4 | Architecture decision records (ADRs) | Tracabilite | Moyen | A FAIRE |
| DOC5 | API documentation des webhooks | Integration | Faible | A FAIRE |

---

## 8. DEVOPS

| # | Amélioration | Impact | Effort | Statut |
|---|-------------|--------|--------|--------|
| CI1 | CI smoke tests toutes les 4 pipelines | Regression | Fait | ACTIF (GitHub Actions) |
| CI2 | Nightly eval (50q) automatique | Monitoring | Moyen | A FAIRE |
| CI3 | Auto-deploy HF Space depuis GitHub push | DevOps | Moyen | A FAIRE |
| CI4 | Alertes si accuracy drop > 2pp | Regression | Faible | A FAIRE |

---

## STATS REPO (inventaire)

| Dossier | Fichiers | Role |
|---------|----------|------|
| technicals/ | ~15 | Documentation technique |
| directives/ | ~10 | Mission control |
| eval/ | ~8 | Scripts evaluation Python |
| scripts/ | ~12 | Utilitaires + pilotage |
| n8n/ | ~15 | Workflows JSON |
| datasets/ | ~20 | Donnees de test + secteurs |
| website/ | ~50 | Next.js site ETI |
| website-pme-*/ | ~90 | Next.js sites PME |
| docs/ | ~5 | Dashboard data |
| snapshot/ | ~10 | References |
| mcp/ | ~5 | Serveurs MCP |
| infra/ | ~8 | Infrastructure docs |

**Total repo** : ~500+ fichiers core (mon-ipad)

---

---

## 9. SESSION 39 LESSONS — CRITICAL FIXES

### 9.1 HF Space Reliability (ALL WEBHOOKS 404 After Rebuild)

| # | Amélioration | Impact | Effort | Statut |
|---|-------------|--------|--------|--------|
| **S39-1** | **Migrate HF Space to external Supabase DB** (same as improvements-roadmap.md H3) | **CRITICAL** — Prevent data loss | Moyen | **MUST DO Session 40** |
| **S39-2** | **Add /data persistent volume** (HF Spaces setting) | Alternative to S39-1 | Faible | **ALTERNATIVE** |
| **S39-3** | **Fix entrypoint.sh activation verification** (see knowledge-base.md 9.2) | Detect silent failures | Faible | **MUST DO Session 40** |
| **S39-4** | **POST-deploy webhook health check** (test all 7 webhooks before success) | Prevent 404 surprise | Faible | **MUST DO Session 40** |

### 9.2 Orchestrator Failure (0% Phase 2)

| # | Amélioration | Impact | Effort | Statut |
|---|-------------|--------|--------|--------|
| **S39-5** | **Debug Orchestrator intent classifier** (why 404 on every Phase 2 question?) | Fix 0% accuracy | Moyen | **PRIORITE 1 Session 40** |
| **S39-6** | **Add intent classifier unit tests** (independent of full pipeline) | Regression detection | Faible | RECOMMANDE |

### 9.3 Standard Pipeline Degradation (85.5% → 36%)

| # | Amélioration | Impact | Effort | Statut |
|---|-------------|--------|--------|--------|
| **S39-7** | **Diagnose Standard pipeline Phase 2 degradation** (retrieval or LLM?) | +49pp accuracy | Moyen | **PRIORITE 1 Session 40** |
| **S39-8** | **Component-level eval** (test retriever separately from generator) | Pinpoint root cause | Moyen | RECOMMANDE |

### 9.4 PME Workflows (Imported but NOT Activated)

| # | Amélioration | Impact | Effort | Statut |
|---|-------------|--------|--------|--------|
| **S39-9** | **Configure Google API credentials** in HF Space (key exists: AIzaSyBWN3...) | PME workflows functional | Faible | Session 40 |
| **S39-10** | **GitHub Actions CI for PME workflows** (validate before HF deploy) | Prevent broken imports | Moyen | RECOMMANDE |
| **S39-11** | **PME independent test suite** in rag-pme-connectors repo | Decouple from rag-tests | Moyen | RECOMMANDE |

---

## HISTORIQUE DES AJOUTS

| Session | Ajouts | Date |
|---------|--------|------|
| 25 | Creation du document, 50+ ameliorations listees | 2026-02-19 |
| 39 | +20 ameliorations (HF persistence, RAG eval 2026, autonomous testing, Session 39 lessons) | 2026-02-22 |

---

> **REGLE** : Mettre a jour ce fichier apres chaque session avec les nouvelles ameliorations identifiees.
> Marquer le statut (A FAIRE → EN COURS → APPLIQUE) au fur et a mesure.

---

## REFERENCES WEB (Session 39 Research)

### RAG Evaluation 2026
- [RAG Evaluation Metrics (Patronus AI)](https://www.patronus.ai/llm-testing/rag-evaluation-metrics)
- [RAG Evaluation Best Practices (EvidentlyAI)](https://www.evidentlyai.com/llm-guide/rag-evaluation)
- [RAG Evaluation Complete Guide (Maxim AI)](https://www.getmaxim.ai/articles/rag-evaluation-a-complete-guide-for-2025/)
- [Faithfulness, Context Recall Guide (Kinde)](https://www.kinde.com/learn/ai-for-software-engineering/best-practice/rag-evaluation-in-practice-faithfulness-context-recall-answer-relevancy/)
- [DeepEval CI/CD Integration](https://www.confident-ai.com/blog/how-to-evaluate-rag-applications-in-ci-cd-pipelines-with-deepeval)
- [RAGAS Framework Cookbook](https://haystack.deepset.ai/cookbook/rag_eval_ragas)

### n8n Optimization & Queue Mode
- [n8n Queue Mode Documentation](https://docs.n8n.io/hosting/scaling/queue-mode/)
- [n8n Scaling & Reliability Guide (Medium)](https://medium.com/@orami98/the-n8n-scaling-reliability-guide-queue-mode-topologies-error-handling-at-scale-and-production-9f33b13d2be8)
- [n8n Performance Optimization Guide](https://www.wednesday.is/writing-articles/n8n-performance-optimization-for-high-volume-workflows)
- [n8n Concurrency Control](https://docs.n8n.io/hosting/scaling/concurrency-control/)

### HuggingFace Spaces n8n Deployment
- [Free n8n Deployment on HF with Supabase](https://www.ubitools.com/deploy-n8n-huggingface-supabase-guide/)
- [How to Deploy n8n on HF Spaces (Apidog)](https://apidog.com/blog/deploy-n8n-free-huggingface/)
- [HF Docker Spaces Documentation](https://huggingface.co/docs/hub/main/spaces-sdks-docker)
- [n8n on HF Community Thread](https://community.n8n.io/t/how-to-deploy-n8n-in-hugging-face-space/35961)

---

## 10. REPO HEALTH & ARCHITECTURE CLEANLINESS

> Based on comprehensive repo inspection (Session 42)

### 10.1 Mon-ipad Repo (Control Tower)

| # | Issue/Improvement | Impact | Effort | Statut |
|---|-------------------|--------|--------|--------|
| RH1 | All directives fresh (<48h) except rag-data-ingestion.md (46h) | Health ✓ | — | OK |
| RH2 | 5,405 Python/MD files, 11MB logs, no dead .log files | Clean ✓ | — | OK |
| RH3 | Git pack file 16MB (.git/objects/pack) — consider gc | Disk space | Faible | Optional |
| RH4 | Update directives/repos/rag-data-ingestion.md timestamp | Consistency | Faible | Next session |
| RH5 | No __pycache__ or .pyc cleanup needed (gitignored) | Clean ✓ | — | OK |
| RH6 | Create automated weekly git gc cron job | Disk hygiene | Faible | RECOMMANDE |
| RH7 | Add pre-commit hook to check directive timestamps | Prevent staleness | Faible | RECOMMANDE |

### 10.2 Rag-tests Repo

| # | Issue/Improvement | Impact | Effort | Statut |
|---|-------------------|--------|--------|--------|
| RT1 | Last push: 2026-02-22 18:43 (today) — Active ✓ | Health ✓ | — | OK |
| RT2 | 0 open issues, single main branch — Clean ✓ | Health ✓ | — | OK |
| RT3 | Size: 34,719 KB (~34MB) — Normal | Health ✓ | — | OK |
| RT4 | Add GitHub Actions CI for eval scripts linting | Code quality | Faible | RECOMMANDE |
| RT5 | Create CONTRIBUTING.md for external contributors | Documentation | Faible | Future |
| RT6 | Add pytest unit tests for quick-test.py, iterative-eval.py | Reliability | Moyen | RECOMMANDE |
| RT7 | Document expected Codespace setup in README.md | Onboarding | Faible | RECOMMANDE |

### 10.3 Rag-data-ingestion Repo

| # | Issue/Improvement | Impact | Effort | Statut |
|---|-------------------|--------|--------|--------|
| DI1 | Last push: 2026-02-21 05:50 (2 days ago) — Stale warning | Activity ⚠ | — | Monitor |
| DI2 | 0 open issues, single main branch — Clean ✓ | Health ✓ | — | OK |
| DI3 | Size: 31,842 KB (~31MB) — Normal | Health ✓ | — | OK |
| DI4 | No Codespace created yet (per CLAUDE.md) | Workflow blocked | Moyen | Session 40+ |
| DI5 | Create sample ingestion job for testing (100 docs) | Testing | Faible | RECOMMANDE |
| DI6 | Document dataset download process (14 benchmarks ~4GB) | Documentation | Faible | A FAIRE |
| DI7 | Add dry-run mode for ingestion (preview without write) | Safety | Faible | RECOMMANDE |

### 10.4 Rag-pme-connectors Repo

| # | Issue/Improvement | Impact | Effort | Statut |
|---|-------------------|--------|--------|--------|
| PME1 | Last push: 2026-02-21 05:50 (2 days ago) — Recent ✓ | Health ✓ | — | OK |
| PME2 | 0 open issues, single main branch — Clean ✓ | Health ✓ | — | OK |
| PME3 | Size: 32,211 KB (~31MB) — Normal | Health ✓ | — | OK |
| PME4 | CLAUDE.md exists ✓ | Documentation ✓ | — | OK |
| PME5 | n8n/pme-connectors workflows present ✓ | Infrastructure ✓ | — | OK |
| **PME6** | **NO directives/repos/rag-pme-connectors.md in mon-ipad** | Missing directive | Faible | **CREATE Session 40** |
| **PME7** | **Add test infrastructure** (eval scripts for PME workflows) | Quality | Moyen | **PRIORITE 2** |
| PME8 | GitHub Actions CI for Next.js build | Regression | Faible | RECOMMANDE |
| PME9 | Vercel deployment health check in CI | Deployment safety | Faible | RECOMMANDE |
| PME10 | Document 15 connectors with test scenarios | Testing | Moyen | A FAIRE |
| PME11 | Add E2E tests for chatbot MacBook-style interface | UX quality | Moyen | RECOMMANDE |

### 10.5 Rag-dashboard Repo

| # | Issue/Improvement | Impact | Effort | Statut |
|---|-------------------|--------|--------|--------|
| RD1 | Last push: 2026-02-22 18:44 (today) — Active ✓ | Health ✓ | — | OK |
| RD2 | 0 open issues, single main branch — Clean ✓ | Health ✓ | — | OK |
| RD3 | Size: 37,285 KB (~36MB) — Normal | Health ✓ | — | OK |
| RD4 | PUBLIC repo (unlike others) — Intentional ✓ | Visibility | — | OK |
| RD5 | GitHub Pages enabled ✓ | Deployment ✓ | — | OK |
| RD6 | Vercel deployment: nomos-dashboard.vercel.app ✓ | Production ✓ | — | OK |
| RD7 | Add uptime monitoring (UptimeRobot free tier) | Reliability | Faible | RECOMMANDE |
| RD8 | Implement fallback if n8n webhook fails | Resilience | Faible | RECOMMANDE |

### 10.6 Rag-website Repo

| # | Issue/Improvement | Impact | Effort | Statut |
|---|-------------------|--------|--------|--------|
| RW1 | Last push: 2026-02-21 05:50 (2 days ago) — Recent ✓ | Health ✓ | — | OK |
| RW2 | 0 open issues, single main branch — Clean ✓ | Health ✓ | — | OK |
| RW3 | Size: 31,872 KB (~31MB) — Normal | Health ✓ | — | OK |
| RW4 | Vercel deployment: nomos-ai-pied.vercel.app ✓ | Production ✓ | — | OK |
| RW5 | Add Playwright E2E tests for 4 sector pages | Quality | Moyen | RECOMMANDE |
| RW6 | Lighthouse CI for performance tracking | Performance | Faible | RECOMMANDE |

### 10.7 Rag-pme-usecases Repo (NEW)

| # | Issue/Improvement | Impact | Effort | Statut |
|---|-------------------|--------|--------|--------|
| PU1 | Basic Next.js structure present ✓ | Infrastructure ✓ | — | OK |
| **PU2** | **Missing CLAUDE.md** | Documentation | Faible | **CREATE Session 40** |
| **PU3** | **Missing directives/repos/rag-pme-usecases.md in mon-ipad** | Missing directive | Faible | **CREATE Session 40** |
| PU4 | NO deployment URL configured yet | Deployment | Faible | TODO Session 40+ |
| PU5 | Add 200 use cases content (JSON or markdown) | Content | Eleve | A FAIRE |
| PU6 | Implement filtering by sector (8 sectors) | UX | Moyen | A FAIRE |
| PU7 | Add Vercel deployment configuration | Deployment | Faible | Session 40+ |

---

## 11. CROSS-REPO CONSISTENCY & GOVERNANCE

> Ensuring all satellite repos follow the same standards

### 11.1 Missing Governance Files

| # | Issue | Impact | Effort | Statut |
|---|-------|--------|--------|--------|
| **GOV1** | **Create directives/repos/rag-pme-connectors.md** | Consistency | Faible | **Session 40** |
| **GOV2** | **Create directives/repos/rag-pme-usecases.md** | Consistency | Faible | **Session 40** |
| GOV3 | Standardize .gitignore across all 7 repos | Hygiene | Faible | RECOMMANDE |
| GOV4 | Create template CLAUDE.md for new repos | Onboarding | Faible | RECOMMANDE |
| GOV5 | Add CODE_OF_CONDUCT.md for public repos | Community | Faible | Future |

### 11.2 CI/CD Standardization

| # | Improvement | Impact | Effort | Statut |
|---|-------------|--------|--------|--------|
| CI5 | Template GitHub Actions workflow for all repos | Consistency | Faible | RECOMMANDE |
| CI6 | Pre-commit hooks config (black, ruff, prettier) | Code quality | Faible | RECOMMANDE |
| CI7 | Dependabot for all repos (Python, Node.js) | Security | Faible | RECOMMANDE |
| CI8 | Branch protection rules (require CI pass) | Quality | Faible | Future |

### 11.3 Documentation Completeness Matrix

| Repo | CLAUDE.md | Directive (mon-ipad) | README.md | .env.example | Status |
|------|-----------|---------------------|-----------|--------------|--------|
| rag-tests | ✓ | ✓ | ? | ✓ | Good |
| rag-data-ingestion | ✓ | ✓ (46h old) | ? | ✓ | OK |
| rag-pme-connectors | ✓ | ✗ **MISSING** | ? | ✓ | **Action needed** |
| rag-pme-usecases | ✗ **MISSING** | ✗ **MISSING** | ? | ? | **Action needed** |
| rag-dashboard | ✓ | ✓ | ? | N/A | Good |
| rag-website | ✓ | ✓ | ? | ✓ | Good |

**Priority Action**: Create missing directives and CLAUDE.md files for rag-pme-* repos.

---

## 12. INFRASTRUCTURE & RESOURCE OPTIMIZATION

> Based on repo sizes, file counts, and resource usage patterns

### 12.1 Disk Space Management

| # | Improvement | Impact | Effort | Statut |
|---|-------------|--------|--------|--------|
| DISK1 | Git gc monthly on all repos (pack optimization) | Free 20-30% disk | Faible | RECOMMANDE |
| DISK2 | Logs rotation policy (delete >30 days) | Free 11MB (mon-ipad) | Faible | RECOMMANDE |
| DISK3 | Node_modules cleanup script for website repos | Free ~200MB per repo | Faible | RECOMMANDE |
| DISK4 | .venv excluded from git (check .gitignore) | Prevent bloat | Faible | OK |
| DISK5 | Outputs/ archive compression (gzip old sessions) | Free ~50MB | Faible | RECOMMANDE |

### 12.2 Multi-Repo Operations Efficiency

| # | Improvement | Impact | Effort | Statut |
|---|-------------|--------|--------|--------|
| MR1 | Improve scripts/push-directives.sh error handling | Reliability | Faible | RECOMMANDE |
| MR2 | Add scripts/bulk-status.sh (git status all 7 repos) | Visibility | Faible | RECOMMANDE |
| MR3 | Add scripts/bulk-pull.sh (fetch all repos) | Sync | Faible | RECOMMANDE |
| MR4 | Create GitHub Actions workflow to sync directives | Automation | Moyen | Future |

---

## 13. TESTING & QUALITY ASSURANCE GAP ANALYSIS

> Critical testing gaps identified across repos

### 13.1 Missing Test Coverage

| Repo | Unit Tests | Integration Tests | E2E Tests | CI/CD | Gap Score |
|------|-----------|------------------|-----------|-------|-----------|
| rag-tests | ✗ | Partial (eval scripts) | ✗ | Partial | **HIGH** |
| rag-data-ingestion | ✗ | ✗ | ✗ | ✗ | **CRITICAL** |
| rag-pme-connectors | ✗ | ✗ | ✗ | ✗ | **CRITICAL** |
| rag-pme-usecases | ✗ | ✗ | ✗ | ✗ | **CRITICAL** |
| rag-dashboard | ✗ | ✗ | ✗ | ✗ | HIGH |
| rag-website | ✗ | ✗ | ✗ | ✗ | HIGH |
| mon-ipad | Partial | Partial | ✗ | Partial | MEDIUM |

### 13.2 Priority Test Implementation

| # | Test to Implement | Repo | Impact | Effort | Statut |
|---|-------------------|------|--------|--------|--------|
| **TEST1** | **Unit tests for PME workflows** | rag-pme-connectors | Prevent regressions | Moyen | **PRIORITE 1** |
| **TEST2** | **Component tests for eval scripts** | rag-tests | Reliability | Moyen | **PRIORITE 2** |
| TEST3 | E2E tests for website chatbots | rag-website, pme-connectors | UX quality | Eleve | RECOMMANDE |
| TEST4 | Integration tests for ingestion pipeline | rag-data-ingestion | Data quality | Eleve | RECOMMANDE |
| TEST5 | Smoke tests for all n8n webhooks | All repos | Infrastructure | Faible | RECOMMANDE |

---

---

## 14. USER-DRIVEN IMPROVEMENTS (Session 45)

> User-generated ideas from 2026-02-23 (ajd23feb file)

### 14.1 New LLM Chatbot Repo — Website Error Replacement

| # | Detail | Value |
|---|--------|-------|
| **Title** | **New LLM Chatbot Repo for Website Endpoints** | |
| **Description** | Create new dedicated repository containing n8n workflows that serve as chatbot backend for all website endpoints. Knowledge base: executive summaries (docs/executive-summary.md) + CLAUDE.md files from all repos. Use free OpenRouter LLMs (Llama 3.3 70B, Gemma 3 27B). Replace all broken website chatbot endpoints (rag-website, rag-pme-connectors) with working ones. PME-connectors site must be kept up-to-date but doesn't need immediate re-deployment. | |
| **Priority** | **HIGH** | User-facing errors blocking website credibility |
| **Blocked By** | None | Can start immediately |
| **Estimated Complexity** | **MEDIUM** | New repo + 2-3 n8n workflows + website endpoint updates |
| **Estimated Effort** | 4-6 hours | Repo setup (1h) + n8n workflows (2h) + endpoint migration (1-2h) + testing (1h) |
| **Status** | **NOT STARTED** | User requested 2026-02-23 20:28 |
| **Impact** | Fix user-facing chatbot errors, improve website credibility, decouple chatbot from main RAG pipelines | |
| **Dependencies** | - Free OpenRouter API keys (already have 7)<br>- Executive summaries up-to-date (done)<br>- CLAUDE.md files accessible | |
| **Implementation Notes** | - Repo name: `rag-chatbot-backend` or `nomos-chatbot-engine`<br>- Workflows: 1 per site (website, pme-connectors) + shared knowledge base loader<br>- Knowledge base indexing: Pinecone or simple vector search<br>- Rate limiting: use multiple OpenRouter keys for load balancing<br>- Deployment: HF Space or GitHub Actions self-hosted runner | |

### 14.2 Ingestion Test Workflow — Document Quality Verification

| # | Detail | Value |
|---|--------|-------|
| **Title** | **n8n Workflow for Testing Ingested Documents** | |
| **Description** | Create n8n workflow in rag-data-ingestion repo that tests ingested documents with targeted questions to verify ingestion quality. Must include: (1) Automated test suite with pre-defined questions per document type (2) Manual test mode allowing user to upload random files and test them with custom questions (3) Quality metrics: retrieval accuracy, answer relevance, context precision (4) Report generation with pass/fail results. | |
| **Priority** | **MEDIUM** | Improves data quality assurance, prevents bad ingestions from reaching production |
| **Blocked By** | None | Can start after HF Space is fixed |
| **Estimated Complexity** | **MEDIUM** | n8n workflow + test question database + metrics calculation |
| **Estimated Effort** | 3-5 hours | Workflow design (1h) + test questions (1h) + metrics (1-2h) + manual upload UI (1h) |
| **Status** | **NOT STARTED** | User requested 2026-02-23 20:28 |
| **Impact** | Catch ingestion errors early, verify document quality before indexing, improve data pipeline reliability | |
| **Dependencies** | - rag-data-ingestion workflows functional<br>- Test question database (JSON format)<br>- Metrics library (Ragas or custom) | |
| **Implementation Notes** | - Workflow triggers: (a) webhook POST with file upload (b) scheduled test of recent ingestions<br>- Store test results in Supabase `ingestion_tests` table<br>- Integration with CI/CD: fail pipeline if ingestion test accuracy < 80%<br>- Manual mode: web UI with drag-drop file upload + question input field | |

### 14.3 Sub-Agents as Restrictors — Prevent Repeated Failures

| # | Detail | Value |
|---|--------|-------|
| **Title** | **Sub-Agents as Debug Restrictors + VM Monitoring** | |
| **Description** | Modify the 2 startup sub-agents (Session Analyzer, Repo Health Inspector) to act as restrictors: BEFORE any debug attempt, check fixes-library.md for documented failed fixes and BLOCK Opus from repeating them. Add warning if fix was attempted >3 times with no success. ALSO add third sub-agent: VM Monitoring Agent 24/7 that tracks RAM, disk, CPU, n8n status, and alerts on anomalies (OOM, disk >90%, process crashes). | |
| **Priority** | **HIGH** | Prevents wasted time on known-failed fixes, improves VM reliability |
| **Blocked By** | None | Can start immediately |
| **Estimated Complexity** | **MEDIUM** | Modify existing sub-agents + add VM monitoring agent + alert system |
| **Estimated Effort** | 4-6 hours | Sub-agent modifications (2h) + VM monitoring agent (2h) + alert integration (1-2h) |
| **Status** | **NOT STARTED** | User requested 2026-02-23 20:39 |
| **Impact** | Stop infinite debug loops, improve agent efficiency, prevent VM crashes, early warning system for infrastructure failures | |
| **Dependencies** | - fixes-library.md up-to-date and structured<br>- VM monitoring tools (psutil, docker stats)<br>- Alert mechanism (webhook to n8n, Discord, or email) | |
| **Implementation Notes** | - Session Analyzer: add pre-flight check that reads fixes-library.md, extracts failed fix patterns, compares against planned actions, warns Opus if match found<br>- VM Monitoring Agent: Python daemon running 24/7, collects metrics every 60s, stores in time-series DB (Supabase or local SQLite), triggers webhook if threshold exceeded<br>- Alert thresholds: RAM >95% (5 min), disk >90%, CPU >90% (10 min), n8n down (1 min), process crash (immediate)<br>- Integration: VM monitoring webhook → n8n workflow → Discord alert + auto-action (restart service, kill process) | |

### 14.4 CLAUDE.md Cleanup — Simplification and Restructuring

| # | Detail | Value |
|---|--------|-------|
| **Title** | **CLAUDE.md Massive Cleanup and Restructuring** | |
| **Description** | Current CLAUDE.md has 40+ rules and too many files to read (15+ directives, 20+ technical docs). User frustrated that rules aren't followed. Restructure: (1) Reduce to essential rules only (<20 rules) (2) Better ordering: critical rules first, nice-to-haves last (3) Consolidate multi-file documentation (merge related docs) (4) Add quick-reference section at top (5) Remove redundant/outdated rules. ALSO update all satellite repo CLAUDE.md files accordingly. | |
| **Priority** | **MEDIUM** | Improves agent effectiveness, reduces cognitive load, increases rule adherence |
| **Blocked By** | Requires analysis of which rules are actually followed vs ignored | Session 46+ |
| **Estimated Complexity** | **HIGH** | Requires deep analysis + consensus on what's essential + rewrite + sync to 7 repos |
| **Estimated Effort** | 8-12 hours | Analysis (2h) + restructuring (3-4h) + consolidation (2-3h) + satellite sync (1-2h) + testing (1-2h) |
| **Status** | **NOT STARTED** | User requested 2026-02-23 20:41 |
| **Impact** | Better agent performance, clearer onboarding for new agents, reduced session startup time, higher rule compliance | |
| **Dependencies** | - Session log analysis (which rules are followed?)<br>- User feedback on which rules are critical<br>- Sub-agent to analyze rule adherence over 10+ sessions | |
| **Implementation Notes** | - Create CLAUDE-v2.md with restructured content, keep v1 for comparison<br>- Essential rules categories: (1) Infrastructure & Safety (credentials, VM limits) (2) Testing & Evaluation (sequential, validation) (3) Commit & Sync (frequency, multi-repo) (4) Documentation (staleness, updates) (5) Process (bottlenecks, prioritization)<br>- Quick reference: 1-page cheatsheet with top 10 rules + common commands<br>- Deprecate: verbose explanations (move to separate doc), example code snippets (move to knowledge-base.md)<br>- Validation: Run 3 sessions with v2, compare performance vs v1 | |

### 14.5 OpenRouter Key Rotation in n8n — Bypass Rate Limits

| # | Detail | Value |
|---|--------|-------|
| **Title** | **OpenRouter Key Turnover Within n8n Workflows** | |
| **Description** | Implement key rotation mechanism within n8n workflows to bypass OpenRouter rate limit (20 req/min/key). System has 7 OpenRouter keys available. Rotation strategies: (1) Round-robin per request (2) Sticky per pipeline (Standard uses key1, Graph uses key2, etc.) (3) Failover on 429 (switch to next key) (4) Load balancing based on usage counters. Goal: achieve ~140 req/min aggregate (7 keys × 20 req/min). Store key usage state in Redis or Supabase. | |
| **Priority** | **HIGH** | Unblocks 1000q Phase 2+ testing, 7x throughput increase |
| **Blocked By** | None | All 7 keys already configured in .env.local |
| **Estimated Complexity** | **MEDIUM** | n8n workflow modifications + state management + retry logic |
| **Estimated Effort** | 3-5 hours | Design (1h) + n8n implementation (2-3h) + testing (1h) |
| **Status** | **NOT STARTED** | User requested 2026-02-23 21:34 |
| **Impact** | 7x throughput for LLM-heavy pipelines (Quantitative, Orchestrator), faster Phase 2+ testing, no single-key bottleneck | |
| **Dependencies** | - 7 OpenRouter keys verified working<br>- Redis or Supabase table for key usage state<br>- n8n workflow nodes updated to use dynamic key selection | |
| **Implementation Notes** | - **Strategy 1 (Simplest)**: Sticky per pipeline — Standard uses OPENROUTER_KEY_STANDARD, Graph uses _GRAPH, etc. Already configured, just verify all workflows use correct env var<br>- **Strategy 2 (Best for burst)**: Round-robin — n8n workflow reads counter from Redis (GET pipeline:standard:key_index), increments, uses key[index % 7], writes back. Add retry on 429: switch to (index+1) % 7<br>- **Strategy 3 (Future)**: Load balancing — track requests per key per minute in Redis, select key with lowest usage<br>- Implementation: Add "Select OpenRouter Key" node at start of each LLM call in n8n workflows, replace hardcoded credential with dynamic lookup<br>- Testing: Rapid-fire 100 requests to single pipeline, verify 429 errors disappear, measure throughput increase | |

### 14.6 User Willing to Create Credentials — Expose Bottleneck Actions

| # | Detail | Value |
|---|--------|-------|
| **Title** | **User-Actionable Bottlenecks in Executive Summary** | |
| **Description** | User willing to create new accounts/credentials to resolve bottlenecks or simplify agent operations. Examples: second HF account, additional API keys, new Pinecone indexes, paid tiers for rate limits. TASK: Maintain a section in docs/executive-summary.md titled "USER ACTION REQUIRED" that lists concrete actions user can take to unblock progress. Each item must include: (1) What to create (2) Why it's needed (3) Estimated impact (4) Step-by-step instructions (5) Where to paste the credential. Update this section REAL-TIME as bottlenecks emerge. | |
| **Priority** | **MEDIUM** | Empowers user to unblock progress, reduces dependency on agent capabilities |
| **Blocked By** | None | Executive summary already exists |
| **Estimated Complexity** | **LOW** | Documentation + process discipline |
| **Estimated Effort** | 1-2 hours | Initial section creation (30 min) + process documentation (30 min) + testing (30 min) |
| **Status** | **NOT STARTED** | User requested 2026-02-23 21:34 |
| **Impact** | Faster bottleneck resolution, better user-agent collaboration, leverage paid services when free tier blocks progress | |
| **Dependencies** | - Executive summary kept up-to-date (Rule 38)<br>- Agent discipline to update USER ACTION REQUIRED section whenever bottleneck identified | |
| **Implementation Notes** | - Add section to docs/executive-summary.md after "Current Bottlenecks"<br>- Format: Checkbox list with priority (HIGH/MEDIUM/LOW)<br>- Example entry: "[ ] **HIGH**: Create second HF account (parallel n8n execution). Why: Current HF Space at capacity, second Space = 2x throughput. Impact: +50% faster Phase 2 testing. Steps: (1) Go to huggingface.co/join (2) Verify email (3) Settings → Access Tokens → New token (write) (4) Paste token in .env.local as HF_TOKEN_2"<br>- Update triggers: (1) Any rate-limit error (2) Resource exhaustion (RAM, disk, API quota) (3) New bottleneck identified in session-state.md<br>- Agent must CHECK this section at session start and ask user if actions completed | |

---

## HISTORIQUE DES AJOUTS

| Session | Ajouts | Date |
|---------|--------|------|
| 25 | Creation du document, 50+ ameliorations listees | 2026-02-19 |
| 42 | Repo health inspection: 70+ nouveaux items (sections 10-13) | 2026-02-22 |
| 45 | User-driven improvements: 6 ideas from ajd23feb file (section 14) | 2026-02-23 |

---

> **REGLE** : Mettre a jour ce fichier apres chaque session avec les nouvelles ameliorations identifiees.
> Marquer le statut (A FAIRE → EN COURS → APPLIQUE) au fur et a mesure.
