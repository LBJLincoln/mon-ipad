# Scaling Bottlenecks — Comment aller x2, x5, x10, x20, x100

> Last updated: 2026-02-24T19:30:00+01:00
> Session 58 — Document de reference pour acceleration des tests

---

## ETAT ACTUEL (baseline — mis a jour Session 58 v2)

| Metrique | Valeur actuelle |
|----------|----------------|
| Pipelines fonctionnels | **0/5** (TOUS bloques par $env denied — FIX-63 deploye) |
| ROOT CAUSE IDENTIFIEE | **N8N_BLOCK_ENV_ACCESS_IN_NODE manquant** → "access to env vars denied" |
| FIX DEPLOYE | entrypoint.sh + HF secret poussees, **HF Space en rebuild** |
| Questions testees/heure | ~30 (avec early-stop) |
| Instances n8n | **1** (HF Space 16GB) |
| Workers n8n par instance | **1** |
| OpenRouter keys | **6** (~120 req/min aggregate) |
| Execution vectors | VM script + GH Actions |
| HF Space env vars | **21 secrets configures** (20 API keys + N8N_BLOCK_ENV_ACCESS_IN_NODE) |
| Webhooks actifs | 4/5 HTTP 200 mais $env denied → 0% accuracy |
| Dashboard live | https://nomos-dashboard-alexis-morets-projects.vercel.app |

**VERITE FONDAMENTALE** : On ne peut pas scaler 0% accuracy. Les pipelines doivent d'abord FONCTIONNER avant de scaler.

**PROGRES SESSION 58** :
1. 20 env vars pushes vers HF Space secrets (OpenRouter x6, Jina, Pinecone, Neo4j, Cohere, Supabase)
2. Webhooks reactives via POST /activate avec versionId (session cookie auth)
3. **ROOT CAUSE TROUVEE** : `N8N_BLOCK_ENV_ACCESS_IN_NODE` manquant dans entrypoint.sh
   - n8n 2.8.3 bloque $env par defaut dans TOUS les types de noeuds
   - Standard workflow : 12 headers `Bearer ={{$env.OPENROUTER_KEY_STANDARD}}` → tous denied
   - Execution #25 : `Context Reasoning LLM` → `{"error": "access to env vars denied"}`
4. **FIX DEPLOYE** : `export N8N_BLOCK_ENV_ACCESS_IN_NODE=false` ajoute a entrypoint.sh + secret HF
5. HF Space en rebuild automatique (commit pousse au repo HF)
6. 6 agents Sonnet lances en parallele (diagnostics, fixes, tests)

---

## BOTTLENECK 0 — PREREQUIS (accuracy > 0%) — FIX-63 DEPLOYE

> **Qui gere** : Claude (Opus) — fix deploye, en attente rebuild
> **Low-hanging fruit** : OUI — **FIX DEJA DEPLOYE**

| Pipeline | Probleme | Fix | Effort | Status |
|----------|----------|-----|--------|--------|
| **TOUS** | $env bloque → "access to env vars denied" | N8N_BLOCK_ENV_ACCESS_IN_NODE=false | Quick-win | **FIX DEPLOYE, REBUILD EN COURS** |
| Orchestrator | Retourne body vide (executeWorkflow) | httpRequest au lieu de executeWorkflow (FIX-34) | Moyen | **FIX APPLIQUE par agent** |
| Quantitative | Classifier ne route pas les questions Phase 2 | Classifier fix applique par agent | Moyen | **FIX APPLIQUE par agent** |
| PME Gateway | "Could not find property option" sur activate | Fix node config ou credentials | Moyen | **WORKFLOW IMPORTE, ACTIVATION REQUISE** |

**Impact attendu** : FIX-63 debloque TOUS les pipelines → baseline ~70-85% accuracy (comme Phase 1)

---

## BOTTLENECK 1 — x2 VITESSE

> **Qui gere** : Alexis (HF account #2) + Claude
> **Low-hanging fruit** : OUI

| Levier | Situation actuelle | Apres | Impact |
|--------|-------------------|-------|--------|
| **2eme HF Space** | 1 instance (16GB) | 2 instances | x2 throughput |
| **Per-pipeline routing** | Code pret (N8N_HOST_STANDARD etc.) | Route 2-3 pipelines par HF Space | Deja fait dans eval scripts |
| **Batch size optimal** | Auto mode deja code | Std=10, Graph=5, Quant=3, Orch=2 | x3-5 vs batch=1 |
| **GH Actions parallele** | 5 jobs configures | Declencher en parallele du VM script | x2 tests simultanes |

**Actions Alexis** :
1. Creer 2eme HF Space avec meme Dockerfile
2. Configurer `HF_TOKEN_2` dans secrets
3. Setter `N8N_HOST_STANDARD` et `N8N_HOST_GRAPH` vers HF Space #2

**Actions Claude** :
1. Mettre a jour eval scripts pour round-robin entre 2 HF Spaces
2. Tester load balancing

**Resultat** : ~60 questions/heure → ~120 questions/heure

---

## BOTTLENECK 2 — x5 VITESSE

> **Qui gere** : Claude + Alexis
> **Low-hanging fruit** : Moyen

| Levier | Comment | Prerequis |
|--------|---------|-----------|
| **3+ HF Spaces** | 1 par pipeline type (std, graph, quant, orch) | Comptes HF additionnels |
| **Codespace Docker** | n8n local dans Codespace (8GB) pour 1-2 pipelines | Docker-in-Docker fonctionnel |
| **GH Actions matrix x5** | 5 pipelines × 2 runs = 10 jobs paralleles | 2 HF Spaces minimum |
| **Timeout optimization** | Standard 45s→30s, Graph 45s→30s (fail fast) | Tuner per-pipeline |
| **OpenRouter key pooling** | 6 keys × 20 req/min = 120 req/min → distribuer equitablement | Deja en place |

**Resultat** : ~120 q/h → ~600 q/h

---

## BOTTLENECK 3 — x10 VITESSE

> **Qui gere** : Alexis (infra) + Claude (code)
> **Low-hanging fruit** : NON — necessite infra additionnelle

| Levier | Comment | Cout |
|--------|---------|------|
| **n8n multi-worker** | `N8N_CONCURRENCY=5` par HF Space | Config Docker |
| **4 HF Spaces** | 1 dedie par pipeline | 4 comptes HF |
| **Codespace fleet** | 3 Codespaces simultanes (60h/mois limite) | Gratuit mais limite |
| **Pre-computed embeddings** | Cacher embeddings Jina pour questions recurrentes | Stockage Pinecone |
| **OpenRouter Pro** | Passer paid keys (200 req/min par key) | ~$50/mois |

**Resultat** : ~600 q/h → ~6,000 q/h (~100/min)

---

## BOTTLENECK 4 — x20 VITESSE

> **Qui gere** : Alexis (budget) + Claude (archi)
> **Necessite investissement**

| Levier | Comment | Cout |
|--------|---------|------|
| **Dedicated GPU** | HF Space A10G (24GB) — 2x faster inference | $1.05/h |
| **Self-hosted n8n cluster** | 3 workers Docker sur VPS (Hetzner CX31 = 8GB, $7/mois) | ~$21/mois |
| **Connection pooling** | Neo4j/Supabase connection pool (max_connections=20) | Config |
| **Parallel DB queries** | Async Supabase + Neo4j dans n8n Code nodes | Code change |
| **Result caching** | Redis cache pour questions deja evaluees | Redis instance |

**Resultat** : ~6,000 q/h → ~12,000 q/h

---

## BOTTLENECK 5 — x100 VITESSE

> **Qui gere** : Alexis (budget significatif)
> **Transformation architecturale**

| Levier | Comment | Cout |
|--------|---------|------|
| **Kubernetes cluster** | 10+ n8n workers auto-scaling | $100-300/mois |
| **Dedicated LLM** | vLLM self-hosted (Llama 70B sur A100) — 0 rate limits | $2-4/h GPU |
| **Sharded databases** | Pinecone p2 (100K+ vectors), Neo4j Enterprise | $200+/mois |
| **Queue-based architecture** | RabbitMQ/Redis queue → n8n workers pull | Code refactor majeur |
| **Batch API calls** | OpenRouter batch endpoint (si disponible) | API change |
| **CDN pour static data** | Pre-calcul embeddings + cache CloudFlare | $0-20/mois |

**Resultat** : ~12,000 q/h → ~120,000+ q/h (2,000/min)

---

## MATRICE RESUMEE

| Niveau | Questions/heure | Cout mensuel | Effort | Qui gere |
|--------|----------------|-------------|--------|----------|
| **Actuel** | ~30 | $0 | - | - |
| **x2** | ~120 | $0 | 1-2h | Alexis + Claude |
| **x5** | ~600 | $0 | 3-5h | Alexis + Claude |
| **x10** | ~6,000 | ~$50 | 1 jour | Alexis + Claude |
| **x20** | ~12,000 | ~$100 | 2-3 jours | Alexis + Claude |
| **x100** | ~120,000 | ~$500 | 1 semaine | Alexis + Claude |

---

## LOW-HANGING FRUIT (faire EN PREMIER)

1. **Fix 5 pipelines** (prerequis absolu) → 0% → 70-85%
2. **2eme HF Space** → x2 throughput (Alexis : 10 min setup)
3. **Batch size auto** → x3-5 (deja code)
4. **GH Actions matrix** → x2 (deja configure)
5. **Timeout tuning** → +20% (fail fast = more questions tested)

## PARALLELISATION ACTUELLE (Session 58)

### Agents en parallele (Opus pilote, Sonnet execute)
| Agent | Tache | Status |
|-------|-------|--------|
| a3fd7e1 | Debug Standard+Graph 401 auth nodes | **EN COURS** |
| a7055f1 | Quick-test Quant+Orch (5q chacun) | **EN COURS** |
| ae4c865 | Fix Quantitative classifier Phase 2 | **EN COURS** |
| a28dfa3 | Fix Orchestrator FIX-34 | **EN COURS** |

### Infrastructure parallele disponible
| Vecteur | Capacite | Status |
|---------|----------|--------|
| VM (ce terminal) | Opus pilotage + 4-6 agents Sonnet | **ACTIF** |
| GH Actions | 5 jobs paralleles (eval-1000q.yml) | **PRET** |
| Codespace rag-tests | 2 cores, 8GB, Docker-in-Docker | **DISPONIBLE** |
| Codespace data-ingestion | 2 cores, 8GB | **DISPONIBLE** |
| HF Space | 1 instance 16GB, webhooks actifs | **ACTIF** |

### Parallelisation maximale immediate (sans cout)
1. **VM** : 6 agents Sonnet simultanes (recherche, fix, tests)
2. **GH Actions** : 5 pipelines en matrix parallele
3. **Codespace** : Tests lourds (500q+) en background
4. **nohup** : Eval scripts en background avec auto-commit

### Pour aller plus loin (necessite Alexis)
1. **2eme HF Space** : x2 throughput, 10 min setup
2. **2eme Codespace** : x2 tests paralleles
3. **OpenRouter Pro** : x3 rate limit per key

---

## DECISIONS ALEXIS REQUISES

- [ ] Creer 2eme compte HuggingFace + HF Space
- [ ] Budget OpenRouter Pro ? ($50/mois = 200 req/min/key)
- [ ] Budget VPS ? (Hetzner $7-21/mois = 3 n8n workers)
- [ ] Timeline : Quand faut-il les 1M questions ? Phase 3 (10K) ou final ?
