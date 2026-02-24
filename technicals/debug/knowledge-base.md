# Knowledge Base — Cerveau Persistant Multi-RAG

> Last updated: 2026-02-24T03:10:00+01:00 (Session 55 — Chatbot live, n8n Code node lessons, ingestion tests)
> **Ce document est VIVANT.** Il s'enrichit a CHAQUE session avec les solutions, patterns
> et connaissances techniques decouvertes. A lire EN PREMIER avec `fixes-library.md`.
> Objectif : ameliorer la performance de l'agent a chaque session.

---

## SECTION 0 — QUICK REFERENCE (CONSULTER AVANT TOUT TEST)

> **REGLE ABSOLUE** : Avant chaque curl/webhook test, verifier cette section.
> Ne JAMAIS deviner un webhook path, un field name, ou une methode d'auth.

### 0.1 Webhook Paths — Pipelines RAG (VM localhost:5678)

| Pipeline | Workflow ID | Webhook Path | Field Name | Methode |
|----------|-------------|--------------|------------|---------|
| **Standard** | `TmgyRP20N4JFd9CB` | `/webhook/rag-multi-index-v3` | `query` | POST |
| **Graph** | `6257AfT1l4FMC6lY` | `/webhook/ff622742-6d71-4e91-af71-b5c666088717` | `query` | POST |
| **Quantitative** | `e465W7V9Q8uK6zJE` | `/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9` | `query` | POST |
| **Orchestrator** | `aGsYnJY9nNCaTM82` | `/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0` | `query` | POST |

### 0.1b Support Webhooks (VM localhost:5678)

| Workflow | Workflow ID | Webhook Path | Methode | Status |
|----------|-------------|--------------|---------|--------|
| **Dashboard Status** | `KcfzvJD6yydxY9Uk` | `/webhook/nomos-status` | **GET** (not POST!) | Active |
| **Benchmark V3.0** | `LKZO1QQY9jvBltP0` | `/webhook/benchmark-v2` | POST | Active (hangs ~90s) |
| **SQL Executor** | `22k9541l9mHENlLD` | `/webhook/benchmark-sql-exec` | POST | Active (returns 500 — app-level) |
| **PME Gateway** | `IipwYgPoWqM3axwY` | `/webhook/pme-assistant-gateway` | POST | **DEACTIVATED** — needs OpenRouter credential (VM has none) |
| **Project Chatbot** | `chatbot-webhook` | `/webhook/project-chatbot` | POST | **LIVE** — keyword Q&A, no external API needed, bilingual FR/EN |
| **Ingestion** | `nh1D4Up0wBZhuQbp` | `/webhook/rag-v6-ingestion` | POST | Reachable but processing needs real documents |
| **PME Action** | `EaB5iHZsHBCBzFk2` | `/webhook/pme-action-executor` | POST | **DEACTIVATED** — needs OpenRouter + Google OAuth2 creds |

> **FIX-43 (Session 40c)**: PME workflows set `active=true` in DB but n8n silently fails to register webhooks when credentials are missing. Deactivated PME on VM — they work only on HF Space (12 creds).

### 0.1c Stuck Execution Pattern (CRITICAL — recurrent)

> **Stuck executions (status='new' or 'running') block ALL webhook processing.**
> After any n8n restart, OOM, or heavy load, always clean stuck executions:
> ```bash
> docker exec n8n-postgres-1 psql -U n8n -d n8n -t -A -c "DELETE FROM execution_entity WHERE status IN ('new', 'running');"
> ```
> Then wait 10-15s for n8n to re-register webhooks. This is FIX-42/43 combined pattern.
>
> **FIX-44 (Session 40d)**: After cleaning stuck executions, n8n restart only activates SOME workflows.
> A second restart (after another stuck exec clean) activates ALL 7 workflows. The pattern is:
> 1. Clean stuck executions → 2. Restart n8n → 3. Clean any new stuck execs created during shutdown → 4. Wait 25s → 5. Verify all activated in logs
> The "Waiting for N active executions to finish" during shutdown can CREATE new stuck executions that block the next startup.
>
> **FIX-45 (Session 40e)**: HF Space webhooks are NOT actually down — they just need >30s timeout.
> Previous overnight scripts used 10-30s timeout which causes HTTP 000 (timeout). Use `-m 120` for pipeline curls.
> The deploy-overnight script must NOT report webhooks as DOWN if they just need longer timeout.
> HF Space `/activate` endpoint confirms all 9 workflows are active. `/diag` shows recent successful executions.
> **Quick HF Space check**: `curl -s -m 10 "https://lbjlincoln-nomos-rag-engine.hf.space/activate"` — if it returns "already active", webhooks are fine.
>
> **FIX-47 (Session 40g)**: Sometimes stuck exec cleanup alone is NOT enough — n8n healthz returns OK but webhooks
> still timeout (HTTP 000). In this case, a full n8n restart is required (docker restart n8n-n8n-1). After restart,
> 4 new stuck execs appear from the shutdown process — clean those too, then wait 20s for all workflows to activate.
> **Decision tree**: stuck execs → clean → test Dashboard (fast) → if still timeout → restart n8n → clean new stuck execs → verify.

### 0.2 Format d'appel standard

```bash
# TOUJOURS utiliser 'query' (jamais 'question')
curl -s -X POST "http://localhost:5678/webhook/<PATH>" \
  -H "Content-Type: application/json" \
  -d '{"query": "votre question ici"}'

# Avec formatage JSON
curl -s -X POST "http://localhost:5678/webhook/<PATH>" \
  -H "Content-Type: application/json" \
  -d '{"query": "votre question ici"}' | python3 -m json.tool
```

### 0.3 n8n API Authentication (VM)

```bash
# L'API publique n8n sur la VM n'a PAS de cle API configuree.
# Methode 1 : MCP n8n (prefere — mais parfois vide sous pression memoire)
# Methode 2 : PostgreSQL direct
docker exec n8n-postgres-1 psql -U n8n -d n8n -t -A -c "SELECT ..."
# Methode 3 : Si besoin API REST, creer une API key dans l'UI n8n
# JAMAIS utiliser Authorization: Bearer ou X-N8N-API-KEY sans avoir verifie que la cle existe
```

### 0.4 Protocole de pre-vol AVANT tout test

```
CHECKLIST PRE-TEST :
[ ] 1. Webhook path verifie dans Section 0.1 ci-dessus
[ ] 2. Field name = 'query' (pas 'question')
[ ] 3. Content-Type: application/json
[ ] 4. n8n est up : curl -s http://localhost:5678/healthz
[ ] 5. Workflow est actif : docker exec n8n-postgres-1 psql -U n8n -d n8n -t -A -c "SELECT active FROM workflow_entity WHERE id = '<ID>';"
```

---

## TABLE DES MATIERES

0. [Quick Reference — Pre-vol](#section-0--quick-reference-consulter-avant-tout-test)
1. [Modeles LLM — Catalogue & Comportement](#1-modeles-llm)
2. [Patterns de Resolution — Solutions Recurrentes](#2-patterns-de-resolution)
3. [n8n — Pieges & Best Practices](#3-n8n-pieges--best-practices)
4. [APIs Externes — Limites & Contournements](#4-apis-externes)
5. [Databases — Schemas & Requetes Connues](#5-databases)
6. [Evaluation — Methodologie & Interpretation](#6-evaluation)
7. [Infrastructure — Contraintes & Optimisations](#7-infrastructure)

---

## 1. MODELES LLM

### 1.1 Catalogue des modeles deployes (OpenRouter Free Tier)

| Modele | ID OpenRouter | Params | Context | Forces | Faiblesses | Rate Limit |
|--------|---------------|--------|---------|--------|------------|------------|
| **Llama 3.3 70B** | `meta-llama/llama-3.3-70b-instruct:free` | 70B | 128K | SQL generation, reasoning multi-step, planning | Rate-limit frequent (429), parfois JSON malformé | ~20 req/min |
| **Gemma 3 27B** | `google/gemma-3-27b-it:free` | 27B | 8K | Classification rapide, routing, reponses courtes | Contexte court (8K), pas ideal pour SQL complexe | ~20 req/min |
| **Trinity Large** | `arcee-ai/trinity-large-preview:free` | ~7B | 32K | Extraction entites, summaries, structured output | Raisonnement limite, pas pour SQL | ~20 req/min |

### 1.2 Modeles candidats (testes ou identifies, pas deployes)

| Modele | ID OpenRouter | Params | Context | Potentiel | Note |
|--------|---------------|--------|---------|-----------|------|
| **Qwen 3 235B** | `qwen/qwen3-235b-a22b:free` | 235B (22B actifs) | 40K | Meilleur SQL que Llama? A tester | MoE, gratuit, bon benchmark SQL |
| **Qwen 2.5 Coder 32B** | `qwen/qwen-2.5-coder-32b-instruct:free` | 32B | 32K | SQL + code generation | Specialise code, pourrait etre meilleur que Llama pour SQL |
| **DeepSeek V3** | `deepseek/deepseek-chat-v3-0324:free` | 671B MoE | 128K | Raisonnement avance | Gros modele, peut etre lent |
| **Mistral Small 3.1** | `mistralai/mistral-small-3.1-24b-instruct:free` | 24B | 128K | Bon rapport taille/qualite | Contexte long, multilingue |

### 1.3 Matrice d'assignation Workflow x Modele

| Variable Env | Modele Actuel | Role | Workflow(s) | Alternatives Testees |
|--------------|---------------|------|-------------|---------------------|
| `LLM_SQL_MODEL` | Llama 70B | SQL generation | Quantitative | gemma-3-12b (trop faible), a tester: qwen3-235b |
| `LLM_FAST_MODEL` | Gemma 27B | Classification rapide | Orchestrator, Quantitative | — |
| `LLM_INTENT_MODEL` | Llama 70B | Intent classification | Orchestrator | — |
| `LLM_PLANNER_MODEL` | Llama 70B | Task planning | Orchestrator | — |
| `LLM_AGENT_MODEL` | Llama 70B | Agent reasoning | Orchestrator | — |
| `LLM_HYDE_MODEL` | Llama 70B | HyDE queries | Standard | — |
| `LLM_EXTRACTION_MODEL` | Trinity | Entity extraction | Enrichment | — |
| `LLM_COMMUNITY_MODEL` | Trinity | Community summaries | Graph | — |
| `LLM_FALLBACK_INTENT` | Trinity | Fallback intent | Orchestrator | — |
| `LLM_FALLBACK_AGENT` | Trinity | Fallback agent | Orchestrator | — |
| `LLM_LITE_MODEL` | Gemma 27B | Lightweight tasks | General | — |
| `LLM_CHUNKING_MODEL` | Trinity | Chunking | Ingestion | — |

### 1.4 Comportements observes par modele

#### Llama 3.3 70B
- **SQL generation** : Genere du SQL correct ~80% du temps. Echoue sur :
  - Requetes multi-tables avec JOIN complexes
  - Aggregations sur periodes (FY vs Q1-Q4) — confond souvent
  - Noms d'entites avec variantes (TechVision vs TechVision Inc)
- **Rate-limit** : ~20 req/min. Au-dela → 429. Retries 3x avec 8s wait fonctionne.
- **JSON output** : Parfois genere JSON invalide (trailing comma, single quotes).
  Contournement : parser avec try/catch + regex cleanup.
- **Timeout** : 25s trop court sous charge. 60-90s recommande.

#### Gemma 3 27B
- **Classification** : Excellente pour intent detection (standard/graph/quant/orchestrator)
- **Contexte court** : 8K tokens = probleme si le schema DB est long.
  Contournement : schema statique compact dans le prompt.
- **Rapidite** : ~2x plus rapide que Llama 70B en temps de reponse.

#### Trinity Large
- **Entity extraction** : Bonne pour NER structure (personnes, orgs, lieux).
- **Summaries** : Genere des community summaries coherents pour le Graph RAG.
- **Limite** : Pas fiable pour du raisonnement complexe ou du SQL.

### 1.5 Strategies de resilience LLM

| Strategie | Implementation | Impact |
|-----------|---------------|--------|
| **Retry avec backoff** | maxTries=3, waitBetweenTries=8000ms | Elimine ~80% des 429 |
| **neverError=true** | Sur les HTTP Request nodes n8n | Empeche le crash du workflow |
| **Rotation de modeles** | Alterner Llama/Qwen/Gemma par minute | Repartit la charge rate-limit |
| **Fallback cascade** | Primary → Fallback → Template SQL | Garantit toujours une reponse |
| **Template matching** | Bypass LLM pour questions simples (single metric + company + year) | +2pp accuracy |
| **Schema statique** | Prompt inclut schema compact pre-calcule | Reduit tokens, ameliore SQL |
| **Sample data in prompt** | Inclure 3-5 lignes de donnees reelles dans le prompt | Ancre les attentes du LLM |

### 1.6 Rate-Limit OpenRouter — Ce qu'on sait

- **Limite globale** : ~20 req/min par API key (tous modeles confondus)
- **429 response** : `{"error":{"message":"Rate limit exceeded","type":"rate_limit_error"}}`
- **Headers utiles** : `x-ratelimit-remaining`, `x-ratelimit-reset`
- **Contournement OLD** : delai 8s entre requetes quantitatives (3 calls LLM par question)
- **Impact** : Le Quantitative fait 2-3 calls LLM par question (SQL gen + validation/repair + interpretation). A 20 req/min, max ~7 questions/minute.
- **Multi-key IMPLEMENTED** : **7 keys (3 accounts) → ~140 req/min aggregate** (Session 43)

**Key Rotation System (NEW — Session 43)**:
```python
from openrouter_key_rotation import get_rotator

rotator = get_rotator()  # Loads all keys from env
api_key = rotator.get_next_key()  # Returns least-used key
# ... make request ...
rotator.record_usage(api_key)  # Track usage
```

**Environment vars**:
```bash
OPENROUTER_API_KEY=sk-or-v1-xxxxx          # Main (Account 1)
OPENROUTER_KEY_STANDARD=sk-or-v1-xxxxx    # Standard pipeline
OPENROUTER_KEY_GRAPH=sk-or-v1-xxxxx       # Graph pipeline
OPENROUTER_KEY_QUANTITATIVE=sk-or-v1-xxxxx  # Quantitative (Account 2)
OPENROUTER_KEY_ORCHESTRATOR=sk-or-v1-xxxxx  # Orchestrator (Account 2)
OPENROUTER_KEY_PME=sk-or-v1-xxxxx           # PME (Account 3)
OPENROUTER_KEY_ACCOUNT3=sk-or-v1-xxxxx      # Additional key
```

**Features**:
- Automatic load distribution (least-recently-used algorithm)
- Rate limit protection (warns at 80%, waits if all keys at 100%)
- Thread-safe for parallel eval scripts
- Usage tracking and statistics (`rotator.print_status()`)

**Files**:
- `/home/termius/mon-ipad/scripts/openrouter-key-rotation.py` — Core implementation
- `/home/termius/mon-ipad/scripts/openrouter-key-rotation-README.md` — Full documentation
- `/home/termius/mon-ipad/scripts/openrouter-key-rotation-example.py` — Integration examples

**Result**: 7x throughput increase (20 req/min → 140 req/min)

---

## 2. PATTERNS DE RESOLUTION

### 2.1 Pattern : "Le fix est la mais le runtime utilise l'ancien code"
**Symptome** : Code modifie via REST API, GET confirme le changement, mais le comportement runtime ne change pas.
**Solution** : Cycle PUT → Deactivate → Activate (FIX-21).
**Lecon** : n8n cache les Code nodes compiles en memoire. Un simple PUT ne recompile pas.

### 2.2 Pattern : "[object Object]" dans une reponse
**Symptome** : L'output contient `[object Object]` au lieu de details d'erreur.
**Cause** : JavaScript concatene un objet Error avec une string.
**Solution** : `typeof obj === 'object' ? JSON.stringify(obj) : obj`
**Prevention** : Toujours serialiser avec typeof check avant concatenation string.

### 2.3 Pattern : "SQL valide mais resultat faux"
**Symptome** : Le SQL s'execute sans erreur mais retourne une mauvaise valeur.
**Cause** : Le LLM genere un WHERE qui matche le mauvais enregistrement (ex: `company_name = 'TechVision'` au lieu de `'TechVision Inc'`).
**Solution** :
- Utiliser `ILIKE '%keyword%'` au lieu de `= 'exact match'`
- Inclure des sample data rows dans le prompt LLM
- SQL templates pour les patterns connus

### 2.4 Pattern : "HuggingFace dataset introuvable"
**Symptome** : `Invalid username or password` ou 404 lors du download.
**Cause** : HF ID incorrect (namespace/nom changes).
**Solution** : Toujours verifier avec `mcp__huggingface__hf_search_datasets` AVANT d'ajouter un dataset.
**Lecon** : Les HF IDs changent souvent (redirects, renames). 6/11 etaient faux en session 25.

### 2.5 Pattern : "Workflow n8n import echoue sur fresh DB"
**Symptome** : `SQLITE_CONSTRAINT: FOREIGN KEY constraint failed`.
**Cause** : Les workflows exportes contiennent des FK vers des entites de la source DB (shared, activeVersion, versionId).
**Solution** : Strip FK fields avant import (FIX-18).

### 2.6 Pattern : "Variable d'environnement inaccessible dans Code node"
**Symptome** : `access to env vars denied` dans un Code node n8n.
**Cause** : Task runners (n8n >= 2.7.4) isolent les Code nodes. `$env.VAR` fonctionne mais `process.env.VAR` non.
**Solution** : Utiliser `$env.VAR_NAME` (pas `process.env`). FIX-01/FIX-24.

### 2.7 Pattern : "Test passe en quick-test mais echoue en eval complete"
**Symptome** : 5/5 PASS en smoke test, mais accuracy basse en eval 50q+.
**Cause** : Quick-test utilise des questions "faciles" avec `expected_contains: ""` (vide).
L'eval complete a des expected values precises.
**Solution** : Toujours valider avec eval complete (50q minimum) avant de declarer un fix reussi.

### 2.9 Pattern : "Test webhook avec mauvais path ou field name"
**Symptome** : 404 "webhook not registered" ou VALIDATION_ERROR "query is required".
**Cause** : Webhook path tape de memoire (ou copie d'une ancienne session), ou field name incorrect (`question` au lieu de `query`).
**Solution** : TOUJOURS consulter Section 0.1 QUICK REFERENCE avant tout test.
**Frequence** : TRES ELEVEE — se reproduit presque chaque session.
**Prevention** : Ajouter un pre-flight check automatique dans les scripts eval.

### 2.11 Pattern : "n8n Task Runner execute l'ancien code malgre restart complet"
**Symptome** : Le code du Code node a ete mis a jour dans PostgreSQL (verifie via psql). n8n a ete redemarre (docker restart ou docker compose restart). Mais l'execution utilise toujours l'ANCIEN code.
**Cause** : Le Task Runner (subprocess isole, n8n >= 2.7.4) cache le code compile. Meme un redemarrage complet du container ne garantit PAS la recompilation. Le cycle PUT → Deactivate → Activate (FIX-21) ne fonctionne pas via PostgreSQL direct car il faut passer par l'API REST n8n qui n'a pas de cle API configuree sur la VM.
**Solution** : NE PLUS MODIFIER LES WORKFLOWS SUR LA VM. Modifier directement sur le HF Space n8n (16 GB RAM, API REST fonctionnelle, pas de cache issue car fresh import).
**Prevention** : Regle architecturale — VM = pilotage UNIQUEMENT. Modifications workflow = HF Space.

### 2.10 Pattern : "n8n REST API 401 — header required"
**Symptome** : `{"message":"'X-N8N-API-KEY' header required"}` lors d'appels REST API.
**Cause** : La VM n8n n'a pas de `N8N_PUBLIC_API_KEY` configuree dans Docker. L'API publique est activee (`N8N_PUBLIC_API_DISABLED=false`) mais sans cle.
**Solution** : Utiliser PostgreSQL direct (`docker exec n8n-postgres-1 psql ...`) ou MCP n8n.
**Prevention** : Section 0.3 QUICK REFERENCE — ne jamais tenter l'API REST sans verifier l'auth.

### 2.8 Pattern : "curl retourne 200 mais body vide"
**Symptome** : HTTP 200 mais pas de contenu dans la reponse.
**Cause** : n8n webhook retourne un array vide `[]` ou le workflow n'a pas de noeud Respond.
**Solution** : Verifier que le workflow a un noeud "Respond to Webhook" correctement configure.

---

## 3. N8N — PIEGES & BEST PRACTICES

### 3.1 Modification de workflows via API
```
PROCEDURE OBLIGATOIRE :
1. GET /api/v1/workflows/{id} → sauvegarder l'etat actuel
2. Modifier les nodes necessaires (1 node a la fois)
3. PUT /api/v1/workflows/{id} avec payload minimal (FIX-09)
4. POST /api/v1/workflows/{id}/deactivate
5. POST /api/v1/workflows/{id}/activate
6. Tester → 5/5 minimum
7. python3 n8n/sync.py → sauvegarder
```

### 3.2 Payload PUT minimal (n8n 2.7+)
```json
{
  "name": "...",
  "nodes": [...],
  "connections": {...},
  "settings": {
    "executionOrder": "v1",
    "callerPolicy": "workflowsFromSameOwner"
  },
  "staticData": null
}
```
Champs INTERDITS dans PUT : `id`, `createdAt`, `updatedAt`, `active`, `isArchived`, `versionCounter`, `activeVersionId`, `homeProject`, `sharedWithProjects`, `tags`.

### 3.3 n8n 2.7+ vs 2.8+ differences
| Feature | n8n 2.7.4 (VM) | n8n 2.8.3 (HF Space) |
|---------|----------------|----------------------|
| Task Runners | Toujours ON (env var ignore) | Toujours ON |
| **$env access** | **Bloque Code nodes** | **Bloque TOUS noeuds (FIX-33)** |
| Login API | `emailOrLdapLoginId` | `emailOrLdapLoginId` |
| Activation | PATCH active:true OK | Requires versionId (FIX-19) |
| Import CLI | Fonctionne (array format) | Echoue souvent (FK issues) |
| REST API | Stable | Stable apres warmup (FIX-20) |

### 3.5 $env interdit dans n8n 2.8+ (CRITIQUE — FIX-33)
```
n8n 2.8.3 Task Runner evalue TOUTES les expressions dans le sandbox.
$env est bloque pour TOUS les types de noeuds :
- Code nodes (typeVersion 2)
- HTTP Request (URL, headers, body expressions)
- Postgres nodes
- Tout noeud avec des expressions {{ }}

ERREUR RUNTIME : "access to env vars denied"
STACK : workflow-data-proxy-env-provider.js:59:27

SOLUTION : Ne JAMAIS utiliser $env dans les workflows n8n 2.8+.
Options :
1. Injecter les valeurs au moment de l'import (FIX-33, recommande)
2. Utiliser des credentials n8n (pour les secrets)
3. Hardcoder les valeurs dans le JSON du workflow

Le FIX-33 dans entrypoint.sh remplace $env.X par os.environ values
AVANT le JSON parsing, couvrant 30+ variables.
Script: fix-env-refs.py (standalone, appele depuis entrypoint.sh)
```

### 3.6 executeWorkflow retourne vide avec respondToWebhook (CRITIQUE — FIX-34)
```
Quand un workflow est appele via executeWorkflow (n8n Execute Workflow node),
et que le sub-workflow utilise respondToWebhook pour envoyer sa reponse :

PROBLEME : respondToWebhook envoie la reponse HTTP au client original
mais NE RETOURNE PAS les donnees au noeud executeWorkflow parent.
Resultat : data.main = [[]] (tableau vide).

CONSEQUENCE : Tout noeud en aval du executeWorkflow ne recoit aucun item
et ne s'execute jamais.

SOLUTION : Remplacer executeWorkflow par httpRequest POST vers le webhook
du sub-workflow. L'httpRequest recoit la reponse JSON normalement.
  - URL: http://localhost:5678/webhook/<path>
  - Method: POST
  - Body: { "query": "<task_query>" }
  - Timeout: 30000ms

REGLE : Ne JAMAIS utiliser executeWorkflow pour appeler un workflow
qui utilise respondToWebhook. Utiliser httpRequest a la place.
```

### 3.4 HTTP Request node — config recommandee
```json
{
  "timeout": 60000,
  "retry": { "maxTries": 3, "waitBetweenTries": 8000 },
  "options": { "response": { "response": { "neverError": true } } }
}
```

### 3.7 n8n Queue Mode Performance — 2026 Best Practices

**Current Setup**:
- VM: main process (webhooks) + 0 workers (executions pass to main)
- HF Space: main process + 0 workers + SQLite (NOT queue mode)
- Bottleneck: Sequential execution, no parallelization

**Queue Mode Architecture** (target for Phase 2+):
```
┌─ Main Instance ────────────────────────────────┐
│ - Receives webhooks/timers                     │
│ - Generates execution ID                       │
│ - Pushes to Redis queue                        │
│ - NO execution (delegates to workers)          │
└─────────────────┬──────────────────────────────┘
                  │
         ┌────────▼─────────┐
         │   Redis Queue    │  (execution IDs)
         └────────┬─────────┘
                  │
    ┌─────────────┼─────────────┐
    │             │             │
┌───▼────┐  ┌────▼───┐  ┌─────▼──┐
│Worker 1│  │Worker 2│  │Worker 3│
│ n8n    │  │ n8n    │  │ n8n    │
└────────┘  └────────┘  └────────┘
  (actual execution)
```

**Performance Gains** (n8n official benchmarks 2026):
- Single instance: 23 req/s
- Queue mode (3 workers): 162 req/s (7x improvement)
- Max tested: 220 req/s on single machine

**Configuration Requirements**:
```bash
# .env for ALL instances (main + workers)
EXECUTIONS_MODE=queue
N8N_ENCRYPTION_KEY=<same-everywhere>  # CRITICAL
DB_TYPE=postgresdb  # SQLite NOT recommended for queue
QUEUE_BULL_REDIS_HOST=localhost
QUEUE_BULL_REDIS_PORT=6379

# Main instance
N8N_SKIP_WEBHOOK_DEREGISTRATION_SHUTDOWN=true

# Worker instances
EXECUTIONS_PROCESS=main
N8N_WORKER_CONCURRENCY=3  # Tune based on workflow complexity
```

**Worker Concurrency Tuning**:
| Workflow Type | Recommended Concurrency | Rationale |
|---------------|------------------------|-----------|
| I/O-bound (HTTP requests, DB queries) | 5-10 | Waiting time dominates |
| CPU-bound (LLM local, heavy compute) | 1-2 | Avoid resource contention |
| Mixed (current RAG pipelines) | 3-5 | Balance parallelism vs stability |

**Critical Considerations**:
1. **Webhook latency**: Queue mode adds overhead (main → Redis → worker → response)
   - Baseline: 100-200ms per webhook
   - Queue mode: +50-100ms overhead
   - Acceptable for batch/async workflows, not for real-time chat

2. **PostgreSQL required**: SQLite does NOT support queue mode reliably
   - Current HF Space uses SQLite → MUST migrate to Supabase PostgreSQL (improvement H3)

3. **Redis memory**: Each execution ID in queue = ~1KB
   - 1000 concurrent executions = ~1MB Redis
   - Not a bottleneck for current scale

**Implementation Priority**:
- **Phase 1**: SKIP (200q baseline, sequential OK)
- **Phase 2**: EVALUATE (1000q, 3 workers = 3x throughput)
- **Phase 3+**: REQUIRED (10Kq+, 10 workers minimum)

**HF Space Deployment** (docker-compose.yml):
```yaml
services:
  n8n-main:
    image: n8nio/n8n:2.8.3
    environment:
      - EXECUTIONS_MODE=queue
      - DB_TYPE=postgresdb
      - DB_POSTGRESDB_HOST=external-postgres  # Supabase
    ports:
      - "5678:5678"

  n8n-worker-1:
    image: n8nio/n8n:2.8.3
    command: worker
    environment:
      - EXECUTIONS_MODE=queue
      - N8N_WORKER_CONCURRENCY=3

  n8n-worker-2:
    image: n8nio/n8n:2.8.3
    command: worker
    environment:
      - EXECUTIONS_MODE=queue
      - N8N_WORKER_CONCURRENCY=3

  redis:
    image: redis:7-alpine
```

**References (2026)**:
- n8n queue mode docs: https://docs.n8n.io/hosting/scaling/queue-mode/
- Performance benchmarks: https://docs.n8n.io/hosting/scaling/performance-benchmarking/
- Worker concurrency guide: https://evalics.com/blog/n8n-queue-mode-explained-scale-workers-and-avoid-pitfalls
- Production setup: https://nextgrowth.ai/scaling-n8n-queue-mode-docker-compose/

---

## 4. APIS EXTERNES

### 4.1 OpenRouter

**Basic info**:
- **URL** : `https://openrouter.ai/api/v1/chat/completions`
- **Auth** : `Authorization: Bearer sk-or-v1-...`
- **Rate limit** : ~20 req/min per key (free tier)
- **Erreurs courantes** :
  - 429 : Rate limit → use key rotation system (see below)
  - 400 : JSON parsing failed → verifier le body
  - 502/503 : Serveur temporairement indisponible → retry
- **Quota** : Illimite en requetes/jour, mais rate-limited par minute

**Key Rotation System (Session 43)**:
- **7 keys across 3 accounts** → **~140 req/min aggregate throughput**
- **Implementation**: `/home/termius/mon-ipad/scripts/openrouter-key-rotation.py`
- **Usage**:
  ```python
  from openrouter_key_rotation import get_rotator

  rotator = get_rotator()
  api_key = rotator.get_next_key()  # Automatic load balancing
  # ... make request ...
  rotator.record_usage(api_key)
  ```
- **Features**:
  - Least-recently-used selection algorithm
  - Automatic rate limit protection (warns at 80%, waits at 100%)
  - Thread-safe for parallel execution
  - Real-time statistics: `python3 scripts/openrouter-key-rotation.py --status`
- **Integration**: See `scripts/openrouter-key-rotation-README.md` for full guide
- **Testing**: `python3 scripts/openrouter-key-rotation.py --test 50`

### 4.2 Jina AI
- **Embeddings** : `https://api.jina.ai/v1/embeddings` (model: `jina-embeddings-v3`, dim 1024)
- **Reranker** : `https://api.jina.ai/v1/rerank` (model: `jina-reranker-v2-base-multilingual`)
- **Quota** : 10M tokens/mois (free)
- **Erreur courante** : `trailing comma` dans le JSON body (FIX-04)

### 4.3 Cohere
- **Reranker** : `https://api.cohere.ai/v1/rerank`
- **Status** : Trial QUASI-EPUISE. 2 keys, les deux proches de l'expiration.
- **Alternative** : Jina reranker est le primary maintenant.

### 4.4 Pinecone
- **Index primary** : `sota-rag-jina-1024` (dim=1024, free tier, 10,411 vecteurs)
- **Erreur courante** : Dimension mismatch si on envoie des vecteurs Cohere (1536d) vers un index Jina (1024d) (FIX-12)
- **Namespaces** : 12 ns actifs (squad, hotpotqa, musique, etc.)

### 4.5 Neo4j Aura
- **URL API** : `https://38c949a2.databases.neo4j.io/db/neo4j/query/v2`
- **Auth** : Basic (neo4j:password)
- **PIEGE** : Le protocole bolt:// ne fonctionne PAS via HTTP Request n8n. Toujours HTTPS API (FIX-07).
- **Contenu** : 19,788 nodes, 76,717 relations

### 4.6 Supabase
- **URL** : `https://ayqviqmxifzmhphiqfmj.supabase.co`
- **Tables cles** : financials (24 rows), balance_sheet (12), sales_data (1152), employees (150), products (18)
- **Entreprises** : TechVision Inc, GreenEnergy Corp, HealthPlus Labs
- **Periodes** : FY 2020-2023, Q1-Q4 2023

### 4.7 HuggingFace
- **Datasets** : `trust_remote_code` deprecie dans les versions recentes de la lib `datasets`
- **Loading scripts** : Certains datasets (legalbench, eurlex, financial_phrasebank) utilisent des loading scripts depreciees → ne peuvent plus etre telecharges
- **Solution** : Chercher des alternatives Parquet-based (ex: galileo-ai/ragbench)

---

## 5. DATABASES

### 5.1 Schema Supabase — Quantitative Pipeline
```sql
-- Entreprises et periodes disponibles
SELECT DISTINCT company_name, fiscal_year, period FROM financials ORDER BY company_name, fiscal_year, period;
-- Resultat : 3 companies x (4 FY + 4 Q) = 24 rows

-- Colonnes financials les plus requetees
-- revenue, net_income, gross_profit, operating_income, research_development, diluted_eps, basic_eps

-- SQL pattern le plus fiable
SELECT metric FROM financials
WHERE company_name ILIKE '%keyword%' AND fiscal_year = YYYY AND period = 'FY'
LIMIT 1;
```

### 5.2 Neo4j — Entites Graph RAG
```cypher
// Types de noeuds
MATCH (n) RETURN DISTINCT labels(n), count(n) ORDER BY count(n) DESC;
// __Entity__ (7628), __Community__ (6143), Document (3176), Chunk (2841)

// Relations
MATCH ()-[r]->() RETURN type(r), count(r) ORDER BY count(r) DESC;
// RELATED_TO (57,000+), IN_COMMUNITY, HAS_ENTITY, etc.
```

### 5.3 Pinecone — Namespaces
```
sota-rag-jina-1024 : 10,411 vecteurs
  Namespaces: squad, hotpotqa, musique, nq, finqa, cuad, covidqa,
              pubmedqa, techqa, tatqa, emanual, doqa
```

---

## 6. EVALUATION

### 6.1 Interpretation des resultats
- **5/5 PASS en quick-test** ≠ pipeline OK. Les smoke questions sont faciles.
- **Accuracy evaluation** : Comparer `response` avec `expected_answer` via fuzzy matching.
- **Quantitative** : Les expected values sont des nombres precis. Meme une reponse "presque correcte" (mauvaise entreprise, mauvaise periode) est un FAIL.
- **Graph** : Les reponses sont souvent des phrases. Le matching cherche des keywords.

### 6.2 Causes de faux negatifs
- OpenRouter 429 → timeout → "Unable to generate SQL" → FAIL (pas une vraie erreur pipeline)
- n8n 503 transitoire → timeout → FAIL
- Matching trop strict (ex: "6.7 billion" vs "6,745,000,000")

### 6.4 CRITIQUE — Filtrage Phase 1 vs Phase 2 dans les scripts eval (FIX-36, Session 30)
**Symptome** : Phase 1 gates bloques (Graph 68.7%, Quant 78.3%) alors que les pipelines
passent largement leurs cibles sur les questions Phase 1.
**Cause racine** : `generate_status.py` et `phase_gates.py` comptaient TOUTES les questions
du `question_registry` (y compris musique, finqa = datasets Phase 2) dans le calcul
des gates Phase 1. Les 17 questions musique (41% acc) et 10 questions finqa (40% acc)
trainaient les scores vers le bas.
**Fix** : Ajout de `_is_phase1_question(qid)` qui exclut les IDs contenant "musique",
"finqa", ou "phase2" du calcul Phase 1. Les deux scripts filtrent maintenant correctement.
**Resultat** : Phase 1 PASSED — Standard 85.5%, Graph 78.0%, Quant 92.0%, Orch 80.0%, Overall 83.9%.
**REGLE** : Les questions Phase 2 (HF datasets) NE DOIVENT JAMAIS etre incluses dans le
calcul Phase 1. Phase 2 a ses propres targets (Graph 60%, Quant 70%, Overall 65%).

### 6.3 Delais recommandes entre questions
| Pipeline | Delai | Raison |
|----------|-------|--------|
| Standard | 3s | Pas de LLM OpenRouter |
| Graph | 5s | 1 call LLM (community synthesis) |
| Quantitative | 8-10s | 2-3 calls LLM (SQL gen + interpretation + repair) |
| Orchestrator | 5s | 1-2 calls LLM (routing + delegation) |

### 6.5 RAG Evaluation Metrics — 2026 Best Practices (CRITICAL MISSING)

**Current Gap**: Project only tracks **accuracy** (1 metric). Enterprise production requires **6 metrics**.

| Metric | Description | Target 2026 | Tool | Priority | Status |
|--------|-------------|-------------|------|----------|--------|
| **Accuracy** | Correct answer match | >= 75% | Manual | — | ✅ IMPLEMENTED |
| **Faithfulness** | Response grounded in context (no hallucinations) | >= 95% | Ragas | HIGH | ❌ MISSING |
| **Context Recall** | Context contains ALL info for ideal answer | >= 85% | Ragas | HIGH | ❌ MISSING |
| **Context Precision** | Retrieved docs ranked correctly | >= 80% | Ragas | MEDIUM | ❌ MISSING |
| **Answer Relevancy** | Response addresses the query | >= 90% | Ragas | MEDIUM | ❌ MISSING |
| **Hallucination Rate** | Unsupported/fabricated text | <= 2% | Ragas | HIGH | ❌ MISSING |
| **Latency (p95)** | End-to-end response time | <= 2.5s | Custom | MEDIUM | ❌ MISSING |

**Implementation Roadmap** (Session 40+):
```bash
# 1. Install Ragas
pip install ragas

# 2. Add to eval/quick-test.py
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_recall, context_precision

# 3. Collect per-question metrics
metrics_data = {
    "question": question,
    "answer": response["answer"],
    "contexts": response.get("retrieved_contexts", []),
    "ground_truth": expected_answer
}

# 4. Compute metrics
result = evaluate(
    dataset=Dataset.from_dict(metrics_data),
    metrics=[faithfulness, answer_relevancy, context_recall, context_precision]
)

# 5. Store in docs/status.json alongside accuracy
```

**Advanced RAG Techniques — 2026 SOTA**:

1. **Adaptive RAG** (priority: HIGH):
   - Dynamically adjust retrieval strategy based on query complexity
   - SELF-RAG: Critique outputs for alignment with retrieved data
   - Corrective RAG (CRAG): Evaluate and correct retrieved data before generation
   - Implementation: Add confidence scoring to Orchestrator (improvement O2)

2. **Hybrid Retrieval** (priority: HIGH):
   - Dense (embeddings) + Sparse (BM25 keyword search)
   - Impact: +10-15% accuracy on domain-specific queries
   - Status: PLANNED for Standard (improvement S2), Quantitative (improvement Q9)

3. **Late Chunking** (priority: MEDIUM):
   - Jina v3 feature: chunk AFTER embedding computation (preserves context)
   - Parameter: `late_chunking=True` in Jina embeddings API
   - Status: PLANNED for re-ingestion Phase 2+ (improvement S1)

4. **Reranking Optimization** (priority: MEDIUM):
   - Cross-encoder models outperform bi-encoder for final ranking
   - Current: Cohere rerank (trial exhausted)
   - Alternative: Jina Reranker v2 (free tier, multilingual)
   - Impact: +3-5% accuracy, +10-15% context precision

**References (2026)**:
- Ragas metrics: https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/
- RAG evaluation guide: https://www.evidentlyai.com/llm-guide/rag-evaluation
- Enterprise best practices: https://labelyourdata.com/articles/llm-fine-tuning/rag-evaluation
- Adaptive RAG research: https://arxiv.org/abs/2501.07391
- RAG 2026 trends: https://squirro.com/squirro-blog/state-of-rag-genai
- Hybrid retrieval: https://www.edenai.co/post/the-2025-guide-to-retrieval-augmented-generation-rag

---

## 7. INFRASTRUCTURE

### 7.1 VM Google Cloud — Contraintes
- **RAM** : 969 MB total, ~100 MB libre. Claude Code = ~280 MB. n8n = ~215 MB. Task runner = ~38 MB.
- **REGLE** : Jamais de tests lourds sur la VM. Pilotage UNIQUEMENT.
- **Swap** : ~1 GB utilise en permanence. Les operations memoire-intensives sont lentes.
- **Disque** : 30 GB, 17 GB libres. Les datasets sectoriels font ~27 MB total — OK.
- **PIEGE RECURRENT** : Les anciennes sessions Claude Code restent en memoire (PID zombie). Au demarrage de session : `ps aux | grep claude | grep -v grep` et killer les anciens PID. Chaque session = ~280 MB.
- **Nettoyage RAM** : `sync && echo 3 | sudo tee /proc/sys/vm/drop_caches` libere 20-50 MB de cache filesystem.
- **OOM CASCADE (FIX-40)** : Quand swap atteint 100%, PostgreSQL connections timeout → n8n webhooks 404. Symptomes : healthz=OK mais "Cannot POST /webhook/..." ou 503. Fix : 1) Kill zombies (git pack-objects, old eval scripts, old claude sessions), 2) Clean execution_entity table, 3) Full docker compose down/up, 4) Wait ~65-110s startup.
- **STUCK EXECUTION HANG (FIX-42)** : Webhooks accept HTTP connection but NEVER respond (curl hangs, HTTP code 000 on timeout). Healthz=200. Logs show "Execution is already being resumed by another process" spam. Root cause: 79+ stuck executions in `new`/`running` status. Fix: `docker stop n8n-n8n-1 && docker exec n8n-postgres-1 psql -U n8n -d n8n -c "DELETE FROM execution_entity WHERE status IN ('new','running','waiting','crashed');" && docker start n8n-n8n-1`. **This is DIFFERENT from FIX-40**: FIX-40 is 404/503, FIX-42 is "accepts but never responds" (HTTP 000).
- **PIEGE git pack-objects** : Des `git push` echoues laissent des `git pack-objects` zombie (~80MB chacun). Overnight scripts qui push en boucle peuvent creer 4+ processus = 320MB perdus. Verifier avec `ps aux | grep pack-objects`.
- **FIX-05 TTL OBLIGATOIRE** : Le patch task-broker-auth.service.js (15s→120s) est OBLIGATOIRE sur e2-micro. Ne JAMAIS le retirer — le Task Runner n8n ne peut pas s'authentifier en 15s sur ce hardware.

### 7.2 Session Claude Code — Limites
- **Duree max** : 2h par session pour conserver l'efficacite (eviter context overflow)
- **A 1h45** : finaliser les taches en cours, push, MAJ session-state.md et status.md
- **Avant /compact** : TOUJOURS s'assurer que tous les fichiers technicals/ sont a jour et pushes dans GitHub

### 7.2 HF Space — Capacites
- **RAM** : 16 GB (cpu-basic, $0)
- **n8n** : 2.8.3 (latest), SQLite, Redis
- **Limitation** : HF proxy casse les POST body pour /rest/ et /api/ (FIX-15)
- **Webhooks** : Fonctionnent normalement (Standard, Graph OK ; Quantitative 500 car manque Supabase data)

### 7.3 Codespaces — Quand les utiliser
| Scenario | Ou executer |
|----------|-------------|
| Quick-test 1-5q | HF Space (webhooks) |
| Eval 50q | Codespace rag-tests |
| Eval 200q+ | Codespace rag-tests (nohup) |
| Ingestion massive | Codespace rag-data-ingestion |
| Pilotage / monitoring | VM (ce repo) |

### 7.4 Concurrent Load Testing Results (Session 27)

Tested on HF Space (cpu-basic, 16GB RAM) with parallel-pipeline-test.py v2.

| Config | Pipelines | Concurrency | Total Concurrent | Standard | Graph | Orchestrator |
|--------|-----------|-------------|-----------------|----------|-------|--------------|
| Baseline | 3 | 1 | 3 | 100% (9s) | 100% (18s) | 100% (14s) |
| Moderate | 3 | 3 | 9 | 100% (23s) | 90% (26s) | 70% (35s) |
| Stress | 3 | 5 | 15 | 100% (29s) | 90% (44s) | 0% AUTO-STOP |
| Solo | 1 | 5 | 5 | 100% (16s) | N/A | N/A |

Key findings:
- **Standard pipeline is rock solid** at any concurrency level (100% even at 15 concurrent)
- **Graph pipeline** drops 1 question (keyword mismatch, test data issue, not pipeline issue)
- **Orchestrator degrades under concurrent load** because it delegates to sub-pipelines that are already serving direct requests → empty responses → auto-stop
- **Latency scales linearly** with concurrency: ~2-3x at concurrency=5
- **HF Space cpu-basic handles 15 concurrent n8n workflow executions** without crashing (16GB RAM is sufficient)

Recommended concurrency for production testing:
- Standard: concurrency=5 (safe)
- Graph: concurrency=3 (safe)
- Orchestrator: concurrency=1 (must not compete with sub-pipelines)
- Cross-pipeline: max 9 concurrent total (3 pipelines x 3 questions)

---

## 8. NEO4J — GRAPH DATA QUALITY (SESSION 35)

### 8.1 Critical Finding: Neo4j 98.27% Generic Relationships

**Diagnostic run revealed**:
- **19,788 nodes** (8,531 Person, 8,331 Entity, 1,775 Organization, etc.)
- **76,769 relationships** total
- **75,442 CONNECTE** (generic) = **98.27%** of all relationships
- Only **1,327 semantic relationships** (1.73%) — A_CREE, UTILISE, ETEND, ETUDIE, etc.

**Impact on Graph pipeline**:
- Phase 2 accuracy = **0%** (0/58 questions)
- Root cause: No semantic signal in graph. CONNECTE edges are noise.
- Example: "Who voiced SpongeBob?" requires VOICED_BY relationship, not CONNECTE.

### 8.2 Entity Disambiguation Failure

Sample findings:
- "Plankton" entity exists with biological description ("organisms in water column")
- Same database has SpongeBob-related entities (show, episodes, cast)
- Plankton is incorrectly linked to SpongeBob via CONNECTE (false connection)
- Movie titles labeled as :Person nodes (e.g., "The SpongeBob SquarePants Movie")

**Solution**: Re-ingestion with:
1. Fine-grained entity labels (:Person:Actor, :Entity:Movie, :Entity:TV_Show)
2. Semantic relationship extraction (VOICED_BY, DIRECTED_BY, WRITTEN_BY, etc.)
3. Entity disambiguation via dbpedia_uri or wikidata_id
4. Deduplication logic to prevent duplicate "Plankton" entities

### 8.3 Semantic Relationships That DO Exist

Distribution of 1,327 semantic relationships:
- A_CREE (created by): 497 — good quality (Michelangelo → Sistine Chapel)
- SOUS_ENSEMBLE_DE (subset): 554 — good quality
- UTILISE (uses): 99 — Technology-to-Technology mostly
- ETEND (extends): 66 — rare, some incorrect (Entity ETEND City)
- CIBLE (targets): 52 — sparse
- ETUDIE (studies): 38 — sparse
- Others (6 types): 21 total

**Quality**: A_CREE and SOUS_ENSEMBLE_DE are solid. Others are sparse and sometimes incorrect.

### 8.4 Re-ingestion Strategy

Full analysis: `/home/termius/mon-ipad/technicals/debug/neo4j-data-quality-analysis.md`

**Target** (after re-ingestion):
- Semantic relationships >= 50% of total
- Generic CONNECTE <= 30%
- 20+ relationship types with clear semantics
- Fine-grained entity labels (12+ types)
- Graph RAG accuracy: 0% → 60%+

**Effort**: 5-8 hours (Codespace rag-data-ingestion)

**Steps**:
1. Export current graph for analysis
2. Re-ingest Phase 2 graph datasets (musique, 2wikimultihopqa) with semantic extraction
3. Import to Neo4j with proper relationship typing
4. Validate with diagnostic queries
5. Re-test Graph pipeline

**Decision required**: Proceed with re-ingestion? (Blocking Phase 2 overall accuracy)

---

## 9. HF SPACES — N8N DEPLOYMENT PATTERNS

### 9.1 HF Space Persistent Storage (CRITICAL SESSION 39 FINDING)

**Problem**: HF Space rebuild wiped ALL n8n workflow activations → ALL webhooks 404.

**Root cause**: Docker containers on HF Spaces are ephemeral by default. Data written to disk is lost on restart unless persistent storage is configured.

**Solutions** (ranked by reliability):

| Approach | Pros | Cons | Status |
|----------|------|------|--------|
| **External Supabase DB** | Survives all restarts, same DB as Quantitative pipeline | Requires network latency, setup complexity | RECOMMENDED |
| **HF /data volume** | Built-in persistence, opt-in via Space settings | Must enable in Space UI, limited to /data directory | ALTERNATIVE |
| **Robust entrypoint.sh** | Works with any DB, retry + verification | Doesn't prevent data loss, only fixes activation | CURRENT (broken) |

**Best practice (2026)**:
1. Use external PostgreSQL (Supabase) instead of SQLite for n8n database
2. Configure `DB_TYPE=postgresdb` and connection string in HF Space secrets
3. Add `/data` persistent volume for binary files (if needed)
4. Implement health checks in entrypoint.sh: verify workflow activation succeeded before exit

**References**:
- [HuggingFace Docker Spaces](https://huggingface.co/docs/hub/main/spaces-sdks-docker)
- [Free n8n deployment on HF with Supabase](https://www.ubitools.com/deploy-n8n-huggingface-supabase-guide/)
- [n8n on HF Spaces community thread](https://community.n8n.io/t/how-to-deploy-n8n-in-hugging-face-space/35961)

### 9.2 HF Space Activation Verification Pattern

**Failure mode**: Entrypoint.sh activates workflows via REST API, exits with success, but activation fails silently.

**Diagnostic**:
```bash
# Check if workflow is actually active (inside HF container)
curl -s http://localhost:5678/api/v1/workflows/<ID> | jq '.active'

# Test webhook responds
curl -s -X POST http://localhost:5678/webhook/<PATH> \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}' | jq .
```

**Robust activation pattern** (from ci_full_setup.py):
```python
# 1. Login to get cookie
login_resp = requests.post(f"{n8n_url}/login", json={"email": email, "password": password})
cookie = login_resp.cookies.get("n8n-auth")

# 2. Activate workflow with cookie auth
activate_resp = requests.patch(
    f"{n8n_url}/api/v1/workflows/{workflow_id}",
    headers={"cookie": f"n8n-auth={cookie}"},
    json={"active": True}
)

# 3. VERIFY activation succeeded
verify_resp = requests.get(
    f"{n8n_url}/api/v1/workflows/{workflow_id}",
    headers={"cookie": f"n8n-auth={cookie}"}
)
if not verify_resp.json().get("active"):
    raise Exception(f"Workflow {workflow_id} failed to activate")

# 4. Test webhook endpoint
test_resp = requests.post(f"{n8n_url}/webhook/<PATH>", json={"query": "test"})
if test_resp.status_code != 200:
    raise Exception(f"Webhook test failed: {test_resp.status_code}")
```

**Action for Session 40**: Apply this pattern to scripts/migrate-to-hf-spaces.sh

### 9.3 n8n Queue Mode on HF Spaces

**Current**: HF Space runs n8n with NO workers (single-process mode).

**Target**: 3 workers for 3x throughput.

**Docker Compose pattern**:
```yaml
services:
  n8n-main:
    image: n8nio/n8n:latest
    environment:
      - EXECUTIONS_MODE=queue
      - QUEUE_BULL_REDIS_HOST=redis
    depends_on:
      - redis
      - postgres

  n8n-worker-1:
    image: n8nio/n8n:latest
    command: worker
    environment:
      - EXECUTIONS_MODE=queue
      - QUEUE_BULL_REDIS_HOST=redis
    depends_on:
      - redis
      - postgres

  n8n-worker-2:
    image: n8nio/n8n:latest
    command: worker
    # same config as worker-1

  redis:
    image: redis:7-alpine

  postgres:
    image: postgres:15-alpine
```

**HF Spaces limitation**: Multi-container setup requires Docker-in-Docker or separate Space for each worker.

**Alternative**: Single container with multiple n8n processes via supervisor or PM2.

**Performance gain**: 3 workers = ~3x throughput for parallel question batches.

**References**:
- [n8n Queue Mode Guide](https://docs.n8n.io/hosting/scaling/queue-mode/)
- [n8n Performance Optimization](https://www.wednesday.is/writing-articles/n8n-performance-optimization-for-high-volume-workflows)

---

## 10. RAG EVALUATION 2026 — INDUSTRY STANDARDS

### 10.1 Enterprise Production Metrics (Missing in Current Implementation)

**Current state**: Only accuracy is measured (78.1% overall, Phase 1).

**Enterprise 2026 standard** (from Patronus AI, Confident AI, EvidentlyAI):

| Metric | Definition | Threshold | Measurement Method |
|--------|------------|-----------|-------------------|
| **Faithfulness** | % of claims supported by retrieved context (anti-hallucination) | >= 95% | LLM-as-judge + programmatic checks |
| **Context Recall** | % of ground-truth info present in retrieved context | >= 85% | Compare retrieved chunks vs. golden answers |
| **Context Precision** | Relevance ranking quality (high-relevance chunks first) | >= 80% | nDCG or MRR on chunk rankings |
| **Answer Relevancy** | Generated answer matches user intent | >= 90% | LLM-as-judge + keyword overlap |
| **Latency** | End-to-end response time | <= 2.5s | Median p50 + p95 tracking |
| **Hallucination Rate** | % of responses with unsupported claims | <= 2% | Inverse of faithfulness |

**Impact on project**:
- Current 78.1% accuracy doesn't reveal if answers are hallucinated, have correct context, or are just lucky guesses
- Phase Gate criteria include faithfulness >= 95%, context recall >= 85%, latency <= 2.5s (see CLAUDE.md)
- **None of these are measured yet** → blocking enterprise production readiness

### 10.2 Component-Level Evaluation Pattern

**Best practice 2026**: Evaluate retriever and generator separately.

**Retriever metrics**:
- Context Recall: Did we retrieve the right chunks?
- Context Precision: Are relevant chunks ranked higher?
- Hit Rate: % of queries where at least 1 relevant chunk is in top-k

**Generator metrics**:
- Faithfulness: No hallucinations
- Answer Relevancy: Matches user intent
- Format Correctness: Valid JSON, proper structure

**Why separate?**:
- Pinpoint whether failure is retrieval (wrong chunks) or generation (LLM hallucination)
- Example: Standard pipeline might have 90% retrieval recall but 70% generator faithfulness → fix LLM prompt, not retrieval

**Implementation**: Add separate test suite for retriever-only (check Pinecone/Neo4j results before LLM generation).

### 10.3 LLM-as-Judge Calibration (Critical for Faithfulness)

**Problem**: LLM-as-judge has systematic biases:
- Prefers longer responses
- Positional bias (favors first option in multiple choice)
- Self-preference (favors outputs from same model family)

**Solution (2026 best practice)**:
1. Use human-verified golden dataset to calibrate judge
2. Mix LLM-as-judge with programmatic checks (e.g., claim extraction + fact verification)
3. Use different model for judge than generator (e.g., judge = GPT-4o, generator = Llama 70B)
4. Track judge agreement rate with human labels (target >= 85%)

**For this project**:
- Current eval uses exact string match (0 or 1) → brittle, misses semantically correct answers
- Should add LLM-as-judge for semantic equivalence (e.g., "2019" vs "in 2019" should both be correct)
- Calibrate judge on 50-100 human-labeled examples from Phase 1

### 10.4 Evaluation Frameworks Comparison

| Framework | Language | Features | Integration | Best For |
|-----------|----------|----------|-------------|----------|
| **RAGAS** | Python | Faithfulness, context recall/precision, answer relevancy | pytest, Haystack | Comprehensive offline eval |
| **DeepEval** | Python | LLM-as-judge, CI/CD integration, custom metrics | pytest, GitHub Actions | Developer-first, unit testing |
| **TruLens** | Python | Real-time monitoring, chain-of-thought tracing | LangChain, LlamaIndex | Production observability |
| **Braintrust** | Python/TS | Dataset management, A/B testing, prompt versioning | API-first | Enterprise teams |

**Recommendation for Session 40+**:
- Add RAGAS for offline batch evaluation (faithfulness, context recall)
- Keep current quick-test.py for fast iteration
- Use DeepEval in GitHub Actions CI for regression detection

**References**:
- [RAG Evaluation Metrics Guide (Patronus AI)](https://www.patronus.ai/llm-testing/rag-evaluation-metrics)
- [RAG Evaluation Best Practices (EvidentlyAI)](https://www.evidentlyai.com/llm-guide/rag-evaluation)
- [RAGAS Framework](https://haystack.deepset.ai/cookbook/rag_eval_ragas)
- [DeepEval CI/CD Guide](https://www.confident-ai.com/blog/how-to-evaluate-rag-applications-in-ci-cd-pipelines-with-deepeval)

### 10.5 Autonomous Testing Architecture (Session 39 Lesson)

**Problem**: All 4 pipeline PIDs died in Session 39 (git locks, HF overload). Claude Code had to manually restart.

**2026 Best Practice**: Autonomous evaluation with self-healing.

**Pattern**:
```python
# eval/autonomous_runner.py
class AutonomousEvaluator:
    def __init__(self, pipeline, max_retries=3, auto_commit_interval=900):
        self.pipeline = pipeline
        self.max_retries = max_retries
        self.auto_commit_interval = auto_commit_interval
        self.consecutive_failures = 0

    def run(self):
        while not self.is_complete():
            try:
                result = self.test_next_question()
                if result.success:
                    self.consecutive_failures = 0
                else:
                    self.consecutive_failures += 1

                # Auto-stop on 3 consecutive failures
                if self.consecutive_failures >= 3:
                    self.stop_and_report("3 consecutive failures")
                    break

            except Exception as e:
                self.handle_error(e)

            # Auto-commit every 15 min
            if time.time() - self.last_commit > self.auto_commit_interval:
                self.commit_and_push()

    def handle_error(self, error):
        if "rate limit" in str(error):
            time.sleep(60)  # Wait 1 min, retry
        elif "connection refused" in str(error):
            self.stop_and_report("n8n unreachable")
        else:
            self.consecutive_failures += 1
```

**Implementation for Session 40**:
1. Wrap run-eval-parallel.py with auto-recovery logic
2. Add structured logging (JSON) for monitoring
3. POST progress to n8n webhook every 15 min (for dashboard)
4. Kill switch: if VM disk > 90% or RAM > 95%, auto-stop

**Expected outcome**: 10+ hours of autonomous testing without manual intervention.

---

## HISTORIQUE DES AJOUTS

| Session | Ajouts | Date |
|---------|--------|------|
| 25 | Creation du document, modeles LLM, 8 patterns, APIs, schemas | 2026-02-19 |
| 27 | $env interdit tous noeuds (3.5), executeWorkflow vide (3.6) | 2026-02-19 |
| 39 | HF Spaces persistence (9.1-9.3), RAG eval 2026 standards (10.1-10.5) | 2026-02-22 |
| 27 | Concurrent load testing results (7.4), Orchestrator concurrency limits | 2026-02-19 |
| 30 | Phase1 vs Phase2 question filtering (6.4), FIX-36 | 2026-02-20 |
| 35 | Neo4j data quality analysis (8.1-8.4), 98% generic relationships critical issue | 2026-02-21 |
| 54 | HF Space secrets management, API credit monitoring, model availability, repo cleanup | 2026-02-24 |

---

## SECTION 11 — HF SPACE SECRETS & API CREDIT MANAGEMENT (Session 54)

### 11.1 HF Space Secrets vs Variables
- **Secrets**: Injected as env vars at container runtime. Not visible in UI. Use `api.add_space_secret()`.
- **Variables**: Visible in UI and settings. Use `api.add_space_variable()`.
- **CRITICAL**: NEVER set same key as both secret AND variable — causes CONFIG_ERROR with `Hardware: None`.
- **After any rebuild**: Verify secrets with `api.get_space_variables()` (only shows variables, not secrets). Check entrypoint ENV CHECK logs.

### 11.2 API Credit Monitoring
| API | Free Tier | Monthly Reset | Phase 2 Usage (est.) |
|-----|-----------|---------------|---------------------|
| Jina Embeddings | 1M tokens/month | Monthly | ~2M tokens (1000q × 2 embeddings × 1K tokens) |
| Cohere Reranker | 1000 calls/month | Monthly | ~2000 calls (1000q × 2 reranks) |
| OpenRouter Free | 20 req/min per model | Rolling | N/A (rate-limited, not quota) |

**Rule**: Before starting any >200 question eval run, check API credit balances. Phase 2 (1000q) WILL exhaust Jina free tier. Plan for paid keys for Phase 3 (10K).

### 11.3 OpenRouter Free Model Availability (Feb 2026)
| Model | Status | Use Case |
|-------|--------|----------|
| `arcee-ai/trinity-large-preview:free` | AVAILABLE | Extraction, generation |
| `mistralai/mistral-small-3.1-24b-instruct:free` | AVAILABLE | SQL, instruction following |
| `stepfun/step-3.5-flash:free` | AVAILABLE | Fast inference |
| `nousresearch/hermes-3-llama-3.1-405b:free` | AVAILABLE | Heavy reasoning |
| `openai/gpt-oss-120b:free` | AVAILABLE | General purpose |
| `qwen/qwen3-coder:free` | AVAILABLE | Code/SQL generation |
| `meta-llama/llama-3.3-70b-instruct:free` | RATE-LIMITED | Was primary SQL/reasoning model |
| `google/gemma-3-27b-it:free` | RATE-LIMITED | Was primary fast model |

**Note**: Model availability fluctuates. Test before committing to large runs. Models are HARDCODED in workflow JSONs (not env vars).

### 11.4 Pinecone Host Naming
- Correct host: `sota-rag-jina-1024-a4mkzmz.svc.aped-4627-b74a.pinecone.io`
- OLD/wrong host in some configs: `sota-rag-jina-1024-czwk7da.svc.aped-4627-b74a.pinecone.io`
- The workflow JSONs have the CORRECT host hardcoded. The `.env.local` PINECONE_HOST may be stale.
- Pinecone SDK (MCP) auto-discovers correct host. REST API requires exact match.

## SECTION 12 — N8N CODE NODE LIMITATIONS (Session 55)

### 12.1 Code Node v2 — What Works and What Doesn't
- **Works**: `return { ... }` (sync), `$json`, `$input.item.json`, `$node['Name'].json`, `$env.VAR`, `new Date()`, `Math.*`, `JSON.*`, `require('crypto')`
- **Does NOT work**: `fetch()` (not available in sandbox), `await` at top level (may silently fail), `require('https')` (limited)
- **Workaround for external API calls**: Use HTTP Request node instead of Code node. If credentials are stripped by entrypoint, use `$env.API_KEY` in header expression.

### 12.2 Credential Stripping + Restoration Flow
1. `entrypoint.sh` strips ALL `credentials` fields from nodes during CLI import (to avoid FK errors with fresh SQLite)
2. `setup-workflows.py` restores credentials by matching original JSON → DB workflow by name
3. New workflows added to `n8n-workflows/` are auto-imported but may fail credential restoration if their credential IDs aren't in the `id_map`
4. **The `OPENROUTER_HEADER_AUTH` ID IS mapped** (line 119 of setup-workflows.py) → new workflows using this ID should get credentials restored
5. **If credentials fail**: Use `$env.VAR` expressions in HTTP Request header parameters instead. Format: `"value": "=Bearer {{$env.OPENROUTER_API_KEY}}"`

### 12.3 Webhook responseMode: "responseNode"
- If workflow errors BEFORE reaching a respondToWebhook node, n8n returns HTTP 200 with empty body or generic error
- **Always add error handling** (onError, try/catch) between webhook and respondToWebhook
- For simple workflows: use a single Code node between webhook and respondToWebhook to avoid routing issues

### 12.4 Project Chatbot Architecture Decision
- **v1 (failed)**: LLM call via HTTP Request + httpHeaderAuth credential → credential stripped, 401
- **v2 (failed)**: LLM call via fetch() in Code node → fetch() not available in n8n sandbox
- **v3 (works)**: Pure keyword-based Q&A in Code node → zero external dependencies, <100ms, bilingual
- **Future LLM upgrade path**: Fix setup-workflows.py to handle chatbot credential, or use HTTP Request with `$env.OPENROUTER_API_KEY` expression

---

> **REGLE** : Mettre a jour ce fichier IMMEDIATEMENT apres chaque decouverte technique.
> Pas en fin de session. PENDANT la session, des que la solution est confirmee.
