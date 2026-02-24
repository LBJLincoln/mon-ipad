# Scaling Bottlenecks — Comment aller x2, x5, x10, x20, x100

> Last updated: 2026-02-24T18:30:00+01:00
> Session 58 — Document de reference pour acceleration des tests

---

## ETAT ACTUEL (baseline)

| Metrique | Valeur actuelle |
|----------|----------------|
| Pipelines fonctionnels | **0/5** (0% accuracy Phase 2) |
| Questions testees/heure | ~30 (avec early-stop) |
| Instances n8n | **1** (HF Space 16GB) |
| Workers n8n par instance | **1** |
| OpenRouter keys | **6** (~120 req/min aggregate) |
| Execution vectors | VM script + GH Actions |

**VERITE FONDAMENTALE** : On ne peut pas scaler 0% accuracy. Les pipelines doivent d'abord FONCTIONNER avant de scaler.

---

## BOTTLENECK 0 — PREREQUIS (accuracy > 0%)

> **Qui gere** : Claude (Opus) + Agents Sonnet
> **Low-hanging fruit** : OUI — ces fix sont documentes

| Pipeline | Probleme | Fix | Effort | Gerant |
|----------|----------|-----|--------|--------|
| Quantitative | webhook ignore context/table_data | Patch n8n node | Quick-win | Claude |
| Orchestrator | executeWorkflow → vide (FIX-34) | Remplacer par httpRequest | Quick-win | Claude |
| Standard | Questions Phase 2 ≠ donnees Pinecone | Regenerer questions ou ingerer data | Moyen | Claude |
| Graph | Neo4j "information not available" | Verifier connectivity + Cypher queries | Moyen | Claude |
| PME Gateway | Workflow inactif (FIX-19) | Activer via session cookie ou entrypoint.sh | Quick-win | Claude |

**Impact** : Debloquer 5 pipelines → baseline ~70-85% accuracy (comme Phase 1)

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

## DECISIONS ALEXIS REQUISES

- [ ] Creer 2eme compte HuggingFace + HF Space
- [ ] Budget OpenRouter Pro ? ($50/mois = 200 req/min/key)
- [ ] Budget VPS ? (Hetzner $7-21/mois = 3 n8n workers)
- [ ] Timeline : Quand faut-il les 1M questions ? Phase 3 (10K) ou final ?
