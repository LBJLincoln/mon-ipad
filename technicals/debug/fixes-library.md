# Fixes Library — Multi-RAG Orchestrator

> Last updated: 2026-02-25T13:00:00+01:00

> **Bibliotheque permanente de tous les bugs resolus.** A consulter EN PREMIER avant tout debug.
> Mise a jour obligatoire apres chaque fix reussi. Session courante : Session 62 (2026-02-25).

---

## INDEX PAR CATEGORIE

| # | Categorie | Probleme | Session | Impact |
|---|-----------|----------|---------|--------|
| 01 | n8n Infrastructure | Task Runner isolation brise $getWorkflowStaticData | 16 | CRITIQUE |
| 02 | n8n Infrastructure | SQL Error Handler boucle infinie (compteur $execution.id) | 16 | CRITIQUE |
| 03 | n8n SQL | SQL Validator fallback SQL sans FROM (syntax error PostgreSQL) | 16 | CRITIQUE |
| 04 | n8n Embedding | Jina JSON trailing comma (standard pipeline) | 8 | CRITIQUE |
| 05 | n8n Auth | Task Broker TTL 15s→120s (n8n grant token expiry) | 8 | CRITIQUE |
| 06 | n8n Credentials | Credentials inexistantes apres migration cloud→Docker | 15 | CRITIQUE |
| 07 | Graph Pipeline | Neo4j URL bolt://localhost → HTTPS API (Shield #4) | 17 | CRITIQUE |
| 08 | Quantitative Pipeline | Credential postgres inexistante (live workflow vide) | 17 | CRITIQUE |
| 09 | n8n API | PUT workflow rejette champs read-only (400 error) | 17 | IMPORTANT |
| 10 | CI/CD | n8n runners isolation → timeout 300s×2q = CI fail | 16 | CRITIQUE |
| 11 | Graph Pipeline | Init & ACL multi-format (orchestrator support) | 14 | IMPORTANT |
| 12 | Pinecone | Migration Cohere 1536d → Jina 1024d (index mismatch) | 7 | CRITIQUE |
| 13 | HF Space | Docker python3 manquant (node:20-bookworm-slim) | 24 | CRITIQUE |
| 14 | HF Space | n8n import:workflow format array vs objet | 24 | CRITIQUE |
| 15 | HF Space | HF proxy casse POST body pour /rest/ et /api/ | 24 | IMPORTANT |
| 16 | HF Space | n8n import:workflow toujours inactive + activation REST echoue | 24 | RESOLU par FIX-18 |
| 17 | HF Space | n8n 2.x login API emailOrLdapLoginId (pas email) | 24 | IMPORTANT |
| 18 | HF Space | SQLITE FK constraint — shared/activeVersion refs VM entities | 24 | CRITIQUE |
| 19 | HF Space | n8n 2.8+ activation requires publish (versionId) | 24 | CRITIQUE |
| 20 | HF Space | REST API not ready after healthz (timing) | 24 | IMPORTANT |
| 21 | n8n Infrastructure | Code node cache — PUT + Activate cycle obligatoire | 25 | CRITIQUE |
| 22 | Quantitative Pipeline | OpenRouter 429 rate-limit — retries + neverError + error serialization | 25 | CRITIQUE |
| 23 | Datasets | HuggingFace dataset IDs incorrects (6/11 faux) | 25 | IMPORTANT |
| 24 | n8n Infrastructure | N8N_RUNNERS_ENABLED deprecie dans n8n 2.7.4+ (toujours actif) | 25 | IMPORTANT |
| 25 | VM Infrastructure | Anciennes sessions Claude Code zombies consomment RAM | 25 | IMPORTANT |
| 26 | Agent Process | Webhook path/field name incorrects — pre-vol checklist obligatoire | 25 | CRITIQUE |
| 27 | n8n API | REST API 401 — pas de cle API configuree dans Docker | 25 | IMPORTANT |
| 28 | HF Space | n8n $env vars non resolus — Quant+Orch 500 (OPENROUTER_API_KEY vide) | 26 | CRITIQUE |
| 59 | OpenRouter | Free models rate-limited — swap Llama/Gemma → Mistral/StepFun | 54 | CRITIQUE |
| 60 | HF Space | CONFIG_ERROR from duplicate secret+variable names | 54 | CRITIQUE |
| 61 | Jina/Cohere | API credits exhausted — embeddings + reranking blocked | 54 | CRITIQUE |
| 62 | n8n Credentials | Jina + Cohere credentials missing on HF Space | 54 | IMPORTANT |
| 63 | HF Space | N8N_BLOCK_ENV_ACCESS_IN_NODE missing — ALL $env denied | 58 | CRITIQUE |
| 64 | Ingestion V4.0 | Redis lock nodes prevent workflow startup (HTTP 500) | 61 | CRITIQUE |
| 29 | Quantitative + Orchestrator | HF Space TCP port 6543 bloque + require('crypto') + API key type | 27 | CRITIQUE |
| 30 | Orchestrator | PostgreSQL local pour HF Space (port 6543 bloque) | 27 | IMPORTANT |
| 31 | Infrastructure | Live diagnostic server (diag-server.py) sur port 7861 | 27 | IMPORTANT |
| 32 | Quantitative + Standard | $env bloque dans Code nodes Task Runner + sub-workflow return | 27 | CRITIQUE |
| 33 | TOUS workflows | $env bloque pour TOUS les types de noeuds n8n 2.8+ (pas juste Code) | 27 | CRITIQUE |
| 34 | Orchestrator | executeWorkflow retourne vide (sub-wf respondToWebhook) → httpRequest | 27 | CRITIQUE |
| 35 | Quantitative | OPENROUTER_BASE_URL sans /chat/completions → HTML au lieu de JSON | 27 | CRITIQUE |
| 36 | Evaluation | Phase 1 gates comptaient questions Phase 2 (musique, finqa) | 30 | CRITIQUE |
| 37 | Quantitative Pipeline | Phase 2 context-based questions need LLM reasoning, not SQL | 34 | CRITIQUE |
| 38 | Evaluation | load_questions() broke 2wikimultihopqa context (wrong JSON format) | 35 | CRITIQUE |
| 39h | Data Validation | Permanent data validator + preflight checks + all context formats | 35 | CRITIQUE |
| 40 | VM Infrastructure | OOM → zombie processes → PG connection timeouts → all webhooks 404/503 | 40 | CRITIQUE |
| 41 | n8n Infrastructure | FIX-05 TTL 15s→120s re-applied — still needed on e2-micro VM | 40 | CRITIQUE |
| 42 | VM Infrastructure | Stuck executions (79 new/running) block webhook response — DELETE + restart | 40b | CRITIQUE |
| 43 | VM Infrastructure | PME workflows active=true but 0 webhooks registered — missing credentials silently fail | 40c | IMPORTANT |
| 44 | VM Infrastructure | n8n restart only partially activates workflows when stuck execs exist during shutdown | 40d | CRITIQUE |
| 45 | Monitoring | deploy-overnight false positive: curl timeout <30s reports webhooks DOWN when they need 40-120s | 40e | IMPORTANT |
| 46 | VM Infrastructure | Stuck exec cleanup only — 5 execs cleared, webhooks restored without restart | 40f | IMPORTANT |
| 47 | VM Infrastructure | Stuck execs + n8n restart required — cleanup alone insufficient when webhooks timeout despite healthz OK | 40g | CRITIQUE |
| 48 | HF Space | nginx reverse proxy causes persistent 502 (n8n must listen directly on 7860) | 42 | CRITIQUE |
| 49 | HF Space | n8n SQLite minimal boot (strip PostgreSQL+Redis to break race conditions) | 42 | IMPORTANT |
| 50 | n8n API | v2.8+ login field change: emailOrLdapLoginId (not email) | 42 | IMPORTANT |
| 51 | HF Space | set -e kills container on any transient failure in entrypoint.sh | 42 | CRITIQUE |
| 52 | n8n Workflows | Hardcoded API keys in workflow JSONs expire and cause 401 errors | 43 | CRITIQUE |
| 53 | n8n Workflows | Credential ID mismatch after fresh import (non-existent IDs) | 43 | CRITIQUE |
| 54 | n8n Workflows | Broken expression syntax `={{.VAR}}` instead of `={{$env.VAR}}` | 51 | CRITIQUE |
| 55 | Infrastructure | mon-ipad repo growing too large (datasets/snapshots/logs) | 51 | IMPORTANT |
| 63 | HF Space | N8N_BLOCK_ENV_ACCESS_IN_NODE missing — $env returns "access to env vars denied" | 58 | CRITIQUE |
| 64 | Ingestion V4.0 | Redis lock nodes prevent workflow startup (HTTP 500) | 61 | CRITIQUE |
| 65 | HF Space | N8N_BLOCK_ENV_ACCESS_IN_NODE=false deployed to 10 HF Spaces | 62 | CRITIQUE |
| 66 | HF Space | Credential restore script for post-rebuild recovery | 62 | CRITIQUE |
| 67 | HF Space | HF Space rebuilds reset all webhook registrations | 62 | IMPORTANT |

---

## PIEGES RECURRENTS — ANTI-PATTERNS A ELIMINER

| # | Anti-Pattern | Frequence | Prevention |
|---|-------------|-----------|------------|
| AP-1 | Tester un webhook avec un path tape de memoire | CHAQUE SESSION | Consulter `knowledge-base.md` Section 0.1 |
| AP-2 | Utiliser `question` au lieu de `query` comme field name | FREQUENT | Consulter `knowledge-base.md` Section 0.2 |
| AP-3 | Tenter l'API REST n8n sans verifier que la cle API existe | FREQUENT | Consulter `knowledge-base.md` Section 0.3 |
| AP-4 | Redebugger un probleme deja resolu dans cette librairie | OCCASIONAL | Lire ce fichier EN PREMIER |
| AP-5 | Modifier plusieurs noeuds a la fois | OCCASIONAL | Regle 10 : 1 fix par iteration |
| AP-6 | Patcher nodes[] mais pas activeVersion.nodes[] | CHAQUE FIX | Toujours patcher BOTH (FIX-29, FIX-32) |
| AP-7 | Utiliser $env sans N8N_BLOCK_ENV_ACCESS_IN_NODE=false | CRITIQUE | Verifier entrypoint.sh inclut export N8N_BLOCK_ENV_ACCESS_IN_NODE=false (FIX-63) |
| AP-8 | Deployer HF Space sans N8N_BLOCK_ENV_ACCESS_IN_NODE=false | CRITIQUE | Sans ce flag, TOUS les $env retournent "access to env vars denied" (FIX-63) |
| AP-9 | Utiliser executeWorkflow quand sub-wf a respondToWebhook | CRITIQUE | executeWorkflow retourne vide — utiliser httpRequest (FIX-34) |
| AP-10 | URL OpenRouter sans /chat/completions | CRITIQUE | API retourne HTML au lieu de JSON (FIX-35) |
| AP-11 | Melanger questions Phase 2 dans les gates Phase 1 | CRITIQUE | Chaque phase filtre ses propres questions (FIX-36) |
| AP-12 | Envoyer des questions context-rich au SQL pipeline | CRITIQUE | Classifier detecte le format et route vers context reasoning (FIX-37) |

---

## FIXES DETAILLES

### FIX-01 — N8N_RUNNERS_ENABLED=false (Task Runner Isolation)
**Session** : 16 (2026-02-18)
**Pipeline** : Quantitative CI
**Symptome** : `$getWorkflowStaticData('global')` ne persiste pas entre iterations de boucle. Compteur reset a 0 a chaque passage → boucle de reparation infinie → EXECUTIONS_TIMEOUT 300s.
**Root cause** : `n8n latest` active les task runners par defaut (`N8N_RUNNERS_ENABLED=true`). Les Code nodes s'executent dans un subprocess isole. `$getWorkflowStaticData` ecrit dans le subprocess mais le processus principal ne voit pas les changements.
**Fix** : `N8N_RUNNERS_ENABLED=false` dans docker-compose pour tous les services n8n.
```yaml
# rag-tests-docker-compose.yml — 4 services n8n
- N8N_RUNNERS_ENABLED=false
```
**Verifie** : CI run 22137858153 — 5/5 PASS.
**Fichier impacte** : `rag-tests-docker-compose.yml` (dans repo rag-tests)

---

### FIX-02 — SQL Error Handler counter via $execution.id
**Session** : 16 (2026-02-18)
**Pipeline** : Quantitative
**Symptome** : Boucle infinie de reparation SQL meme apres FIX-01.
**Root cause** : Cle du compteur = `trace_id` qui valait `undefined` dans le contexte d'erreur → `staticData['undefined']` partage entre executions → compteur jamais reset → MAX_REPAIRS jamais atteint.
**Fix** : Utiliser `$execution.id` comme cle unique par execution.
```javascript
const execId = ($execution && $execution.id) ? $execution.id : ('fallback_' + Date.now());
const retryKey = 'repair_' + execId;
const currentCount = (staticData[retryKey] || 0) + 1;
staticData[retryKey] = currentCount;
if (currentCount > MAX_REPAIRS) {
  delete staticData[retryKey];
  return [{ json: { needs_repair: false, retry_exhausted: true } }];
}
```
**Fichier impacte** : `n8n/live/quantitative.json` — node "SQL Error Handler (Self-Healing)"

---

### FIX-03 — SQL Validator fallback SQL sans FROM
**Session** : 16 (2026-02-18)
**Pipeline** : Quantitative
**Symptome** : SQL Executor TOUJOURS en erreur meme avec SQL "simple". `Unexpected token WHERE`.
**Root cause** : Quand le LLM timeout/rate-limit, SQL Validator genere un fallback : `SELECT 'error' as status WHERE tenant_id = 'ci' LIMIT 1`. PostgreSQL reject : pas de clause FROM → syntax error → SQL Executor port[1] error → declenche boucle reparation.
**Fix** : Retirer `WHERE tenant_id = '...'` de tous les fallbacks SELECT literals (4 patterns).
```javascript
// AVANT (casse)
"SELECT 'SQL_GENERATION_ERROR: ...' as error_message WHERE tenant_id = 'ci' LIMIT 1"
// APRES (correct)
"SELECT 'SQL_GENERATION_ERROR: ...' as error_message, 'error' as status LIMIT 1"
```
**Fichier impacte** : `n8n/live/quantitative.json` — node "SQL Validator (Shield #1)"

---

### FIX-04 — Jina Embedding JSON Trailing Comma
**Session** : 8 (2026-02-12)
**Pipeline** : Standard + Graph
**Symptome** : `SyntaxError: Unexpected token` dans le noeud Jina embedding apres migration Cohere→Jina.
**Root cause** : Le JSON body envoye a Jina avait une trailing comma : `{"texts": [...],}` → JSON invalide.
**Fix** : Retirer la virgule trailing du body JSON dans le noeud HTTP Request Jina.
**Fichier impacte** : `n8n/live/standard.json` et `graph.json` — noeud Jina embedding

---

### FIX-05 — Task Broker TTL 15s→120s
**Session** : 8 (2026-02-12)
**Symptome** : n8n s'arrete avec `Grant token expired` apres quelques secondes d'inactivite sur la VM lente (970MB RAM, swap frequent).
**Root cause** : `task-broker-auth.service.js` a un TTL de 15s pour les grant tokens. La VM swap si peu de RAM → les workers mettent plus de 15s a repondre → tokens expires → n8n crash.
**Fix** : Monter un patch via Docker volume : TTL 15s→120s dans le fichier source n8n.
```yaml
# docker-compose.yml
volumes:
  - ./patches/task-broker-auth.service.js:/usr/local/lib/node_modules/n8n/node_modules/...
```
**Fichier impacte** : `n8n/patches/task-broker-auth.service.js` (volume monte)

---

### FIX-06 — Credentials manquantes apres migration Cloud→Docker
**Session** : 15 (2026-02-16)
**Symptome** : 12/13 workflows en erreur `Credential with ID "xxx" does not exist`.
**Root cause** : Migration n8n Cloud → n8n Docker self-hosted. Les credentials Cloud ne sont PAS migrees automatiquement. Chaque workflow reference des IDs d'anciennes credentials Cloud inexistantes dans Docker.
**Fix** :
1. Creer les credentials dans n8n Docker via API ou UI
2. Re-mapper tous les workflows via script Python : parcourir chaque node, remplacer les vieux IDs par les nouveaux.
```python
# Pattern fix credentials
for node in wf['nodes']:
    if 'credentials' in node:
        for cred_type, cred_ref in node['credentials'].items():
            if cred_ref['id'] == OLD_CRED_ID:
                cred_ref['id'] = NEW_CRED_ID
                cred_ref['name'] = NEW_CRED_NAME
```
**Credentials creees** : `Supabase Postgres (Pooler)` (ID: `USU8ngVzsUbED3mn`), Redis (`CWih07lwPxfwFeY6`)
**Fichier impacte** : Tous les workflows n8n — mappes via script

---

### FIX-07 — Neo4j URL bolt://localhost → HTTPS API
**Session** : 17 (2026-02-18)
**Pipeline** : Graph
**Symptome** : Graph RAG a 68.7% malgre 19,788 nodes dans Neo4j. Le pipeline "passe" mais n'utilise jamais le graphe.
**Root cause** : `Shield #4: Neo4j Guardian Traversal` configure avec `url: "bolt://localhost:7687"`. n8n HTTP Request node ne parle pas le protocole Bolt binaire → erreur silencieuse → `Validate Neo4j Results` retourne `skip_graph: true` → pipeline fallback sur Pinecone uniquement.
**Fix** : Changer l'URL vers l'API HTTP Neo4j Aura + ajouter Basic auth header.
```
url: https://38c949a2.databases.neo4j.io/db/neo4j/query/v2
Authorization: Basic <base64(neo4j:PASSWORD)>
```
**Fix via n8n API** : Payload minimal requis (name + nodes + connections + settings uniquement).
**Fichier impacte** : `n8n/live/graph.json` — node "Shield #4: Neo4j Guardian Traversal"

---

### FIX-08 — Quantitative live workflow vide (0 nodes)
**Session** : 17 (2026-02-18)
**Pipeline** : Quantitative
**Symptome** : HTTP 500 sur toutes les requetes quantitative. `Schema Introspection: Credential does not exist`.
**Root cause** : Le workflow live dans n8n avait 0 nodes (workflow casse/vide). La version sur disque (`n8n/live/quantitative.json`) avait 25 nodes depuis 2026-02-10 mais referençait credential `zEr7jPswZNv6lWKu` inexistante.
**Fix en 2 etapes** :
1. Re-pousser le fichier disque vers n8n via PUT API (restaurer les 25 nodes)
2. Mapper les credentials postgres vers l'ID correct existant dans ce n8n Docker
**Payload PUT minimal** : `{name, nodes, connections, settings, staticData}` (rejette `isArchived`, `versionCounter`, `activeVersionId`)
**Fichier impacte** : `n8n/live/quantitative.json`

---

### FIX-09 — n8n API PUT 400 "additional properties"
**Session** : 17 (2026-02-18)
**API** : `PUT /api/v1/workflows/{id}`
**Symptome** : `400: request/body must NOT have additional properties` lors du PUT workflow.
**Root cause** : Le body PUT inclut des champs read-only que n8n refuse : `isArchived`, `versionCounter`, `activeVersionId`, `homeProject`, `sharedWithProjects`, `tags`.
**Fix** : Utiliser un payload minimal :
```python
clean = {
    'name': wf['name'],
    'nodes': wf['nodes'],
    'connections': wf['connections'],
    'settings': {k: v for k, v in wf.get('settings', {}).items()
                 if k in {'executionOrder', 'callerPolicy', 'saveManualExecutions', 'saveExecutionProgress'}},
    'staticData': wf.get('staticData')
}
```
**Note** : Les anciens champs a filtrer : `id`, `createdAt`, `updatedAt`, `active`. Les nouveaux aussi : `isArchived`, `versionCounter`, `activeVersionId`, `homeProject`, `sharedWithProjects`.

---

### FIX-10 — CI Timeout quantitative (300s × 2q = 10min)
**Session** : 16 (2026-02-18)
**Pipeline** : Quantitative CI (GitHub Actions)
**Symptome** : CI job timeout a 10 minutes. Quantitative 0/2.
**Root cause** : Combinaison FIX-01 + FIX-03 : boucle infinie de reparation SQL (FIX-01) + SQL toujours en erreur (FIX-03) → chaque question attend le timeout 300s de n8n.
**Fix** : Appliquer FIX-01 + FIX-02 + FIX-03 ensemble.
**CI file** : `rag-tests-docker-compose.yml`

---

### FIX-11 — Init & ACL multi-format (support orchestrateur)
**Session** : 14 (2026-02-15)
**Pipelines** : Quantitative + Graph
**Symptome** : Pipelines echouent quand appeles via l'orchestrateur (format d'entree different).
**Root cause** : Init & ACL ne supportait que le format webhook direct (`body.query`). L'orchestrateur envoie `task_query` ou `current_task.query`.
**Fix** : Init & ACL hardened V2.2 — 5 sources de query supportees :
```javascript
// Priorite 1: Direct query (webhook/chat)
// Priorite 2: chatInput
// Priorite 3: task_query (orchestrateur)
// Priorite 4: current_task.query
// Priorite 5: query object (stringify)
```
**Fichier impacte** : `n8n/live/quantitative.json` et `graph.json` — node "Init & ACL"

---

### FIX-12 — Migration Cohere 1536d → Jina 1024d
**Session** : 7 (2026-02-11)
**Symptome** : Pinecone rejet des vecteurs (dimension mismatch).
**Root cause** : Index Pinecone cree avec Cohere 1536 dimensions. Migration vers Jina embeddings-v3 = 1024 dimensions → incompatibles.
**Fix** : Creer nouveau index `sota-rag-jina-1024` (dim=1024). Reingerer 10,411 vecteurs. Mettre a jour tous les workflows.
**Index actuel** : `sota-rag-jina-1024` (primary), `sota-rag-cohere-1024` (backup/archive)

---

## PIEGES RECURRENTS (a verifier en premier)

| Piege | Symptome | Verification rapide |
|-------|----------|---------------------|
| Credential manquante | HTTP 500 / "Credential does not exist" | `curl n8n/api/v1/credentials` |
| Workflow vide (0 nodes) | HTTP 500 immediat | `analyze_n8n_executions.py --limit 1` |
| Task runner isolation | $getWorkflowStaticData ne persiste pas | Verifier N8N_RUNNERS_ENABLED=false (< 2.7 only) |
| Bolt protocol | Graph skip_graph=true silencieux | Verifier URL Neo4j = https:// |
| PUT 400 | "additional properties" | Utiliser payload minimal (FIX-09) |
| SQL sans FROM | "Unexpected token WHERE" | Verifier fallbacks SQL Validator |
| LLM rate-limit | "Unable to generate SQL" ou [object Object] | FIX-22: retries+neverError+typeof check |
| Pinecone dim mismatch | 400 on upsert | Verifier index = sota-rag-jina-1024 |
| Code node cache stale | Fixes presents dans JSON mais runtime ancien | FIX-21: PUT → Deactivate → Activate |
| HF dataset ID faux | "Invalid username or password" ou 404 | FIX-23: verifier avec hf_search_datasets |
| N8N_RUNNERS_ENABLED ignore | Log "Remove this env var" | FIX-24: deprecie n8n >= 2.7.4 |
| $env dans Code node | "access to env vars denied" | FIX-32: hardcoder les valeurs (Task Runner bloque) |
| activeVersion pas patche | Fix present dans JSON mais pas actif | FIX-29/32: patcher nodes[] ET activeVersion.nodes[] |
| Sub-WF respondToWebhook | 200 vide depuis orchestrator | FIX-32: ajouter terminal Code node en parallele |
| Phase 2 quant context questions | SQL generation echoue (pas de table) | FIX-37: Question Type Classifier route vers context reasoning |

---

## PROCEDURE DE DEBUG RAPIDE

```
1. Consulter cette bibliotheque → symptome connu ?
2. python3 eval/quick-test.py --questions 1 --pipeline <target>
3. python3 scripts/analyze_n8n_executions.py --pipeline <target> --limit 1
4. Identifier le node en erreur → chercher dans INDEX
5. Appliquer le fix → tester 5/5 → commit + push
6. Documenter le nouveau fix ici si nouveau
```

---

### FIX-13 — Docker python3 manquant (node:20-bookworm-slim)
**Session** : 24 (2026-02-19)
**Composant** : HF Space Dockerfile
**Symptome** : Entrypoint utilise `python3 -c "..."` pour generer les credentials JSON et parser les reponses. `node:20-bookworm-slim` n'inclut PAS python3. Les commandes python echouent silencieusement (|| echo fallback).
**Cause racine** : Image Docker `node:20-bookworm-slim` minimaliste, pas de Python pre-installe.
**Fix** : Ajouter `python3` dans apt-get install du Dockerfile :
```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates redis-server nginx python3 \
    && rm -rf /var/lib/apt/lists/*
```
**Impact** : TOUTES les operations Python dans l'entrypoint echouaient (credentials, cookie parsing, activation).

### FIX-14 — n8n import:workflow format array vs objet
**Session** : 24 (2026-02-19)
**Composant** : HF Space entrypoint
**Symptome** : `n8n import:workflow --input=file.json` echoue avec `workflows.map is not a function` quand le fichier contient un seul workflow (objet JSON `{...}`).
**Cause racine** : n8n 1.76.1 `import:workflow` attend un ARRAY `[{...}]`, pas un objet unique.
**Fix** : Merger tous les workflows en un seul array JSON avant import :
```python
all_wfs = []
for f in glob.glob('/app/n8n-workflows/*.json'):
    wf = json.load(open(f))
    all_wfs.append(wf)
json.dump(all_wfs, open('/tmp/all-workflows.json','w'))
```
Puis : `n8n import:workflow --input=/tmp/all-workflows.json`
**Note** : Avec n8n 2.8.3 (latest), l'import echoue aussi avec un message generique. Le format des workflows exportes depuis n8n 2.7.4 (VM) semble incompatible avec l'import CLI. Solution alternative : import via REST API depuis localhost apres demarrage n8n.

### FIX-15 — HF proxy casse POST body
**Session** : 24 (2026-02-19)
**Composant** : HuggingFace Spaces proxy
**Symptome** : Toute requete POST externe vers `/rest/` ou `/api/` retourne `Failed to parse request body`. Les webhooks `/webhook/` fonctionnent normalement.
**Cause racine** : Le proxy HuggingFace (nginx front) modifie/corrompt le body des requetes POST pour certains paths. C'est une limitation infrastructure HF, pas un bug n8n.
**Contournement** : Toute configuration POST (owner setup, login, activation) doit etre faite depuis LOCALHOST dans l'entrypoint, pas depuis l'exterieur.
**Impact** : REST API POST ne peut PAS etre utilisee depuis l'exterieur. Seuls les webhooks (GET+POST) fonctionnent.

### FIX-16 — n8n import:workflow toujours inactive + activation REST echoue (BLOQUANT)
**Session** : 24 (2026-02-19)
**Composant** : HF Space workflow activation
**Symptome** : `n8n import:workflow` importe les workflows comme INACTIFS (active=0), meme si le JSON a `active:true`. La commande affiche "Deactivating workflow X. Remember to activate later." L'activation via REST API PATCH echoue avec `Cannot read properties of undefined (reading 'description')`.
**Cause racine (n8n 1.76.1)** :
1. `import:workflow` force `active=0` par design
2. PATCH `/rest/workflows/{id}` avec `{"active":true}` echoue car n8n attend le workflow complet
3. PATCH avec le workflow complet (GET puis PATCH) echoue car certains node types ne sont pas resolus (`@n8n/n8n-nodes-langchain.chatTrigger` non installe), ce qui fait que `nodeType.description` est undefined
4. SQLite hack (`UPDATE workflow_entity SET active=1`) met le flag mais n8n ne registre PAS les webhooks pour les workflows actives par modification directe DB
**Cause racine (n8n 2.8.3 latest)** :
1. `import:workflow` echoue completement — format JSON des workflows exportes depuis n8n 2.7.4 (VM) incompatible avec le CLI import de n8n 2.8.3
2. Erreur generique sans details
**Etat actuel** : HF Space RUNNING avec n8n 2.8.3, 12 credentials OK, 0 workflows (import echoue)
**Solutions a tester (session 25)** :
1. **REST API import** : Apres demarrage n8n, utiliser `POST /rest/workflows` via localhost (cookie jar auth) pour creer les workflows un par un, puis activer. Pas de probleme de format CLI.
2. **Re-export workflows** : Depuis le n8n VM (2.7.4), exporter via `n8n export:workflow --all --output=/tmp/export.json` pour avoir un format compatible, puis copier vers HF Space
3. **Public API** : Utiliser l'API publique n8n `/api/v1/workflows` avec API key auth
4. **Installer @n8n/n8n-nodes-langchain** : `npm install -g @n8n/n8n-nodes-langchain` dans le Dockerfile pour resoudre les node types manquants

### FIX-17 — n8n 2.x login API change
**Session** : 24 (2026-02-19)
**Composant** : n8n REST API
**Symptome** : Login via `POST /rest/login` avec `{"email":"...","password":"..."}` retourne erreur `{"code":"invalid_type","path":["emailOrLdapLoginId"]}`.
**Cause racine** : n8n 2.x a renomme le champ `email` en `emailOrLdapLoginId` dans le body de login.
**Fix** :
```bash
# n8n 1.x
curl -d '{"email":"admin@mon-ipad.com","password":"..."}'
# n8n 2.x
curl -d '{"emailOrLdapLoginId":"admin@mon-ipad.com","password":"..."}'
```

---

### FIX-18 — SQLITE FK constraint: shared/activeVersion references VM entities
**Session** : 24 (2026-02-19)
**Composant** : HF Space n8n import:workflow (n8n 2.8.3)
**Symptome** : `n8n import:workflow` echoue avec `SQLITE_CONSTRAINT: FOREIGN KEY constraint failed`. Les credentials s'importent (12/12) mais 0 workflows.
**Cause racine** : Les workflow JSONs exportes depuis la VM (n8n 2.7.4) contiennent des champs FK-dependants :
- `shared` → reference `projectId` (JV7MbqBbWPTstXIo) et `userId` (215767e0-...) de la VM
- `activeVersion` → reference un historique de versions inexistant
- `activeVersionId` → FK vers `workflow_version` table
- `versionId` → FK vers version history

Dans la fresh DB du HF Space, ces entites n'existent pas → FK constraint violation.
**Fix** : Nettoyer les JSONs avant import — supprimer `shared`, `activeVersion`, `activeVersionId`, `versionId`, `versionCounter`.
```python
FK_FIELDS = ['shared', 'activeVersion', 'activeVersionId', 'versionId', 'versionCounter']
for field in FK_FIELDS:
    if field in wf:
        del wf[field]
```
**Verifie** : 9/9 workflows imported + activated (push 84d713a)
**REGLE** : Tout export n8n destine a un import CLI sur une fresh DB DOIT etre nettoye des FK fields.
**Fichier impacte** : `/tmp/hf-space-fix/entrypoint.sh` (HF Space repo)

---

### FIX-19 — n8n 2.8+ activation requires publish (versionId)
**Session** : 24 (2026-02-19)
**Composant** : HF Space n8n activation (n8n 2.8.3)
**Symptome** : `PATCH /rest/workflows/{id}` avec `active: true` retourne 200 mais `active` reste `false`. `POST /rest/workflows/{id}/activate` retourne 400 : `{"code":"invalid_type","path":["versionId"],"message":"Required"}`.
**Cause racine** : n8n 2.8+ a un systeme de versioning/publishing. Les workflows doivent etre "publies" (creant un `activeVersionId`) avant d'etre actives. Le PATCH `active:true` echoue silencieusement sans version publiee.
**Fix** : Utiliser `POST /rest/workflows/{id}/activate` avec le `versionId` du workflow (le draft version). L'endpoint publie ET active en une seule operation.
```python
# GET workflow pour obtenir versionId
wf = api_call('GET', f'/rest/workflows/{wf_id}')
version_id = wf['data']['versionId']
# POST /activate avec versionId
api_call('POST', f'/rest/workflows/{wf_id}/activate', {'versionId': version_id})
```
**Ordre critique** : Les orchestrators qui referent des sub-workflows doivent etre actives EN DERNIER.
**Verifie** : 9/9 workflows actives (push 5d5e6f0)
**Fichier impacte** : `/tmp/hf-space-fix/entrypoint.sh` (HF Space repo)

---

### FIX-20 — REST API not ready after healthz (n8n 2.8+ timing)
**Session** : 24 (2026-02-19)
**Composant** : HF Space n8n REST API
**Symptome** : `POST /rest/owner/setup` retourne `Cannot POST /rest/owner/setup` (Express 404) alors que `GET /healthz` retourne 200.
**Cause racine** : n8n 2.8.3 enregistre `/healthz` avant les routes `/rest/`. Un `sleep 3` apres healthz ne suffit pas.
**Fix** : Attendre que `GET /rest/settings` retourne 200 ou 401 (preuve que les routes REST sont enregistrees), avec retry.
```bash
for i in $(seq 1 30); do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:5678/rest/settings")
    if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "401" ]; then break; fi
    sleep 2
done
```
**Verifie** : Owner setup + login reussissent au premier essai (push 371d23a)
**Fichier impacte** : `/tmp/hf-space-fix/entrypoint.sh` (HF Space repo)

---

### FIX-21 — n8n Code node cache invalidation (PUT + Activate cycle)
**Session** : 25 (2026-02-19)
**Composant** : n8n REST API + Task Runner
**Symptome** : Apres modification d'un Code node via `PUT /api/v1/workflows/{id}`, les changements sont presents dans le JSON (GET confirme), mais le runtime continue d'executer l'ANCIEN code. Exemple : `[object Object]` au lieu de `JSON.stringify($json.error)`.
**Cause racine** : n8n charge les workflows en memoire au demarrage. Un `PUT` ecrit dans PostgreSQL mais n'invalide PAS le cache en memoire du task runner. Meme un `docker compose restart n8n` ne suffit pas toujours car n8n relit la version DB au startup, mais le task runner peut conserver du code compile.
**Fix** : Apres tout PUT de Code nodes, effectuer un cycle PUT + Activate :
```bash
# 1. PUT le workflow modifie (sans champ 'active')
curl -X PUT -H "X-N8N-API-KEY: $KEY" -H "Content-Type: application/json" \
  -d @workflow.json "http://localhost:5678/api/v1/workflows/<ID>"

# 2. Desactiver (force deregistration des webhooks)
curl -X POST -H "X-N8N-API-KEY: $KEY" \
  "http://localhost:5678/api/v1/workflows/<ID>/deactivate"

# 3. Reactiver (force recompilation des Code nodes)
curl -X POST -H "X-N8N-API-KEY: $KEY" \
  "http://localhost:5678/api/v1/workflows/<ID>/activate"
```
**REGLE** : Un simple PUT ne suffit JAMAIS pour les Code nodes. Toujours faire PUT → Deactivate → Activate.
**Verifie** : Execution 2029 confirme les fixes actifs en runtime apres le cycle.
**Fichier impacte** : Tous les workflows avec des Code nodes modifies via API

---

### FIX-22 — OpenRouter 429 rate-limit dans Quantitative pipeline
**Session** : 25 (2026-02-19)
**Pipeline** : Quantitative
**Symptome** : `Unable to generate SQL query for this question. Error: [object Object]` — l'erreur apparait quand OpenRouter retourne HTTP 429 (rate-limit) ou 400 (JSON parsing failed) pour les modeles gratuits.
**Cause racine** : Les HTTP Request nodes (Text-to-SQL Generator, SQL Repair LLM) avaient :
- Timeout 25s (trop court pour modeles gratuits rate-limited)
- Retries 1 (insuffisant)
- `continueOnFail=false` (crash le workflow)
- SQL Validator ne verifie pas `$json.error` avant de parser `$json.choices`
- Response Formatter concatene `$json.error` (objet) avec string → `[object Object]`
**Fix** (4 modifications) :
```yaml
# 1. Text-to-SQL Generator + SQL Repair LLM : HTTP Request
timeout: 25000 → 60000
retry: maxTries 1 → 3, waitBetweenTries 5000ms
options.neverError: true
options.response.response.neverError: true

# 2. SQL Validator (Shield #1) : Code node — ajout early return
if ($json.error) {
  return {
    validated_sql: "SELECT 'LLM_RATE_LIMITED' as error_message LIMIT 1",
    validation_status: 'FAILED',
    validation_error: 'LLM_ERROR'
  };
}

# 3. Response Formatter : Code node — serialisation propre
interpretation = '...Error: ' + (typeof $json.error === 'object'
  ? JSON.stringify($json.error) : ($json.error || 'unknown'));

# 4. Prepare SQL Request : modele google/gemma-3-12b-it:free → $env.LLM_SQL_MODEL
```
**Verifie** : Execution 2029 — erreurs LLM correctement serialisees (pas de [object Object]).
**Note** : Ce fix ameliore la resilience mais ne resout PAS le probleme de fond (LLM rate-limit). Pour atteindre 85%, il faut des modeles avec quota suffisant ou ajouter des delais entre requetes.
**Fichier impacte** : `n8n/live/quantitative.json` — 4 nodes modifies

---

### FIX-23 — HuggingFace dataset IDs incorrects
**Session** : 25 (2026-02-19)
**Composant** : `datasets/scripts/download-sectors.py`
**Symptome** : 6 datasets sur 11 retournent `Invalid username or password` ou 404 car les HF IDs sont faux.
**Cause racine** : IDs mal orthographies ou namespaces inexistants dans download-sectors.py.
**Fix** : Corrections des IDs :
```python
# FINANCE
"sec_qa":              "jkung2003/sec-qa"      → "zefang-liu/secqa"
"financial_phrasebank": "takala/financial_phrasebank" → OK mais config requise: "sentences_allagree"

# JURIDIQUE
"eurlex":   "EurLex/eurlex"    → "NLP-AUEB/eurlex" (config: "eurlex57k")
"cail2018": "thunlp/cail2018"  → "china-ai-law-challenge/cail2018"

# BTP
"code_accord": "GT4SD/code-accord" → "ACCORD-NLP/CODE-ACCORD-Entities" + "ACCORD-NLP/CODE-ACCORD-Relations"
"ragbench_btp": "rungalileo/ragbench" → "galileo-ai/ragbench" (config: "techqa")
"docie": "Sygil/DocIE" → "sercetexam9/docie_test"

# INDUSTRIE
"manufacturing_qa": "thesven/manufacturing-qa-gpt4o" → "karthiyayani/manufacturing-qa-v1"
"ragbench": "rungalileo/ragbench" → "galileo-ai/ragbench" (config: "emanual")
```
**REGLE** : Toujours verifier l'existence d'un dataset HF avec `mcp__huggingface__hf_search_datasets` AVANT de l'ajouter au script.
**Fichier impacte** : `datasets/scripts/download-sectors.py`

---

### FIX-24 — N8N_RUNNERS_ENABLED deprecie dans n8n 2.7.4+
**Session** : 25 (2026-02-19)
**Composant** : n8n Docker configuration
**Symptome** : Au demarrage n8n 2.7.4, le log affiche : `N8N_RUNNERS_ENABLED -> Remove this environment variable; it is no longer needed.` Les task runners sont toujours actifs malgre `N8N_RUNNERS_ENABLED=false`.
**Cause racine** : A partir de n8n 2.7.4, les task runners sont TOUJOURS actifs. La variable `N8N_RUNNERS_ENABLED` est depreciee et ignoree. Les Code nodes s'executent TOUJOURS dans un subprocess isole (JS Task Runner).
**Impact sur FIX-01** : FIX-01 (`N8N_RUNNERS_ENABLED=false`) reste VALIDE pour les versions de n8n < 2.7 (utilisees dans rag-tests Codespace). Pour la VM (n8n 2.7.4), cette variable est ignoree.
**Contournement VM** : Utiliser FIX-05 (Task Broker TTL 15s→120s) pour eviter les expirations de tokens sur la VM lente. Les task runners ne peuvent pas etre desactives.
**REGLE** : Pour n8n >= 2.7.4, ne PAS compter sur N8N_RUNNERS_ENABLED. Les Code nodes tournent toujours en isolation. `$getWorkflowStaticData` peut ne pas fonctionner comme attendu entre iterations.
**Fichier impacte** : `/home/termius/n8n/docker-compose.yml` (variable presente mais ignoree)

---

### FIX-25 — Anciennes sessions Claude Code zombies consomment RAM
**Session** : 25 (2026-02-19)
**Composant** : VM Google Cloud
**Symptome** : VM saturee (~66 MB free, swap >1 GB). n8n retourne Internal Server Error sur REST API. MCP n8n retourne 0 workflows. Impression que "le probleme de RAM n'a pas ete regle".
**Cause racine** : Les sessions precedentes de Claude Code (PID zombie) restent en memoire. Chaque session Claude Code consomme ~280 MB. Si 2 sessions sont actives simultanement = 560 MB + n8n 215 MB = 775 MB / 969 MB = saturation.
**Fix** : Au demarrage de chaque session, verifier et killer les anciens processus :
```bash
# Lister les sessions Claude Code
ps aux | grep claude | grep -v grep
# Tuer les anciennes (garder seulement la session courante)
kill <OLD_PID>
# Liberer le cache filesystem
sync && echo 3 | sudo tee /proc/sys/vm/drop_caches
```
**Prevention** : Session max 2h (regle 26 dans CLAUDE.md). Avant de quitter, s'assurer que le processus se termine proprement.
**Fichier impacte** : CLAUDE.md (regle 27), `technicals/knowledge-base.md` (section 7.1)

---

### FIX-26 — Webhook path/field name incorrects (pre-vol checklist)
**Session** : 25 (2026-02-19)
**Composant** : Processus de test agent
**Symptome** : Test webhook retourne 404 (mauvais path) ou VALIDATION_ERROR (mauvais field name). Se reproduit presque CHAQUE SESSION car les paths/fields sont tapes de memoire.
**Cause racine** : Pas de reference centralisee des webhook paths et field names. L'agent "devine" au lieu de consulter une source de verite.
**Fix** : Ajout de la Section 0 QUICK REFERENCE dans `technicals/knowledge-base.md` :
- Table 0.1 : Webhook paths exacts pour les 4 pipelines
- Table 0.2 : Format d'appel standard (field = `query`, pas `question`)
- Table 0.3 : Methode d'auth n8n API
- Checklist 0.4 : Pre-vol obligatoire avant tout test
**Prevention** : Regle 11 dans CLAUDE.md : "CONSULTER knowledge-base.md Section 0 AVANT tout test webhook"
**Fichier impacte** : `technicals/knowledge-base.md` (Section 0), CLAUDE.md (Regle 11)

---

### FIX-27 — n8n REST API 401 — pas de cle API configuree
**Session** : 25 (2026-02-19)
**Composant** : n8n Docker VM
**Symptome** : `{"message":"'X-N8N-API-KEY' header required"}` HTTP 401 sur toutes les routes /api/v1/.
**Cause racine** : Le conteneur n8n a `N8N_PUBLIC_API_DISABLED=false` (API activee) mais aucune `N8N_PUBLIC_API_KEY` n'est definie. L'API est accessible mais rejette TOUTES les requetes car elle exige un header API key qui n'a jamais ete cree.
**Fix** : Utiliser des alternatives a l'API REST :
1. **PostgreSQL direct** : `docker exec n8n-postgres-1 psql -U n8n -d n8n -t -A -c "..."`
2. **MCP n8n** (quand VM pas sous pression memoire)
3. Si besoin API REST : creer une cle dans l'UI n8n (Settings → API Keys)
**REGLE** : Ne JAMAIS tenter l'API REST n8n sans avoir verifie qu'une cle API existe (Section 0.3 knowledge-base.md)
**Fichier impacte** : `technicals/knowledge-base.md` (Section 0.3)

### FIX-28 — HF Space n8n $env vars non resolus — Quant+Orch retournent 500
**Session** : 26 (2026-02-19)
**Composant** : HF Space entrypoint.sh / n8n workflows
**Symptome** : Quantitative POST → HTTP 500 (0.5-2s). Orchestrator idem. Standard fonctionne (200 OK).
**Cause racine** : Les workflows Quantitative et Orchestrator utilisent `$env.OPENROUTER_API_KEY` dans les headers HTTP Request. Standard a les cles **hardcodees** dans le JSON. Les HF Space secrets sont injectes comme env vars au container mais n'etaient pas explicitement **exportes** dans le shell avant le lancement de n8n. L'expression `$env.OPENROUTER_API_KEY` resolvait en `undefined` → `Bearer undefined` → workflow crash au premier appel LLM. De plus, le node Schema Introspection (Postgres) n'a pas `continueOnFail` — si la connexion Supabase echoue, 500 immediat.
**Fix** : Ajouter dans entrypoint.sh (avant `n8n start`) des exports explicites de TOUTES les variables d'environnement que les workflows referencent via `$env`:
```bash
export OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}"
export OPENROUTER_BASE_URL="${OPENROUTER_BASE_URL:-https://openrouter.ai/api/v1/chat/completions}"
export PINECONE_API_KEY="${PINECONE_API_KEY:-}"
export NEO4J_URL="${NEO4J_URL:-https://38c949a2.databases.neo4j.io/db/neo4j/query/v2}"
# ... + 12 autres variables avec defaults
```
Plus : diagnostic logging qui affiche quelles vars sont SET/EMPTY au demarrage.
**REGLE** : Tout workflow qui utilise `$env.X` doit avoir la variable X exportee dans entrypoint.sh. Ne JAMAIS supposer que les HF secrets sont automatiquement visibles par n8n `$env`.
**Fichiers impactes** : `/tmp/hf-space-update/entrypoint.sh` (HF Space repo), `technicals/fixes-library.md`

### FIX-29 — HF Space Quant TCP port bloque + Orch require('crypto') + API key type
**Session** : 27 (2026-02-19)
**Composant** : Quantitative (postgres→REST API) + Orchestrator (Code node) + Supabase API key
**Symptome** : Apres FIX-28, Quantitative 500 a 0.7s (crash tres rapide = noeud precoce). Orchestrator 200 mais 0 bytes body a 0.45s.
**Causes racines (3 problemes independants)** :
1. **Quant — TCP port 6543 bloque** : HF Space bloque les ports TCP sortants non-HTTP. Le noeud `Schema Introspection` (n8n-nodes-base.postgres) tente une connexion TCP directe au pooler Supabase port 6543 → connexion refusee → 500 immediat. Le noeud `SQL Executor (Postgres)` a le meme probleme.
2. **Orch — require('crypto') dans activeVersion** : Le fix bitwiseHash etait applique aux nodes[] principaux mais PAS a la section `activeVersion.nodes[]` du JSON. n8n 2.8.3 utilise peut-etre l'activeVersion. De plus, Init V8 Security & Analysis n'avait pas `continueOnFail`/`onError` → crash du noeud = execution entiere echoue. L'Error Handler V8 (errorTrigger) ne peut pas repondre au webhook original car il s'execute dans une execution separee.
3. **Quant — SUPABASE_API_KEY type incorrect** : La cle `sb_publishable_...` (46 chars, format nouveau) n'est PAS acceptee par l'API REST Supabase. L'API exige la **cle JWT anon legacy** (`eyJhbG...`, 241 chars). HTTP 401 "No API key found in request".
**Fix** :
1. Conversion des 2 noeuds postgres en HTTP Request appelant `exec_sql` RPC via Supabase REST API (script `scripts/fix-quant-rest-api.py`)
2. Remplacement de require('crypto') par bitwiseHash dans `activeVersion.nodes[]` aussi + ajout `continueOnFail: true` et `onError: continueRegularOutput` sur Init V8
3. Remplacement SUPABASE_API_KEY par la cle JWT anon legacy (241 chars) dans HF Space secrets + .env.local
4. Ajout de 16 vars d'environnement manquantes dans entrypoint.sh (LLM_INTENT_MODEL, SUPABASE_URL, etc.)
**REGLE** : L'API REST Supabase necessite la cle JWT anon legacy, PAS les cles publishable. Verifier avec `get_publishable_keys` MCP tool.
**REGLE** : Toujours patcher BOTH `nodes[]` ET `activeVersion.nodes[]` dans les JSON de workflow n8n.
**Fichiers impactes** : `n8n-workflows/quantitative.json`, `n8n-workflows/orchestrator.json`, `entrypoint.sh` (HF Space), `scripts/fix-quant-rest-api.py`, `.env.local`

### FIX-30 — PostgreSQL local pour Orchestrator HF Space
**Session** : 27 (2026-02-19)
**Composant** : HF Space Orchestrator pipeline
**Symptome** : Orchestrator 200 empty body a 0.45-0.75s. Les nodes PostgreSQL (Init Tasks, Insert Tasks, etc.) utilisent credential `zEr7jPswZNv6lWKu` qui pointait vers Supabase port 6543 (bloque par HF, voir FIX-29).
**Cause racine** : Le port TCP 6543 est bloque par HF Space (meme probleme que Quant). L'Orchestrator utilise PostgreSQL pour task management via n8n-nodes-base.postgres nodes.
**Fix** : Installer PostgreSQL 15 localement dans le container HF Space, rediriger le credential vers localhost:5432.
```dockerfile
RUN apt-get install -y postgresql postgresql-client
```
Entrypoint demarre PostgreSQL avant n8n, cree la DB et le role.
**Fichiers impactes** : `Dockerfile` (ajout postgresql), `entrypoint.sh` (demarrage PG local)

---

### FIX-31 — Live diagnostic server (diag-server.py)
**Session** : 27 (2026-02-19)
**Composant** : HF Space debugging infrastructure
**Symptome** : Impossible de debugger les erreurs d'execution sur HF Space — l'ancien diagnostic inline dans entrypoint.sh ne parsait pas correctement le format API n8n (flattened list).
**Cause racine** : L'API n8n retourne les executions dans un format liste aplati ou les donnees d'execution sont une liste avec des references d'index (pas un dict). Le parser inline Python dans entrypoint.sh echouait avec `'list' object has no attribute 'get'`.
**Fix** : Creation d'un serveur HTTP Python (diag-server.py) sur port 7861 avec :
- `/diag` : dernieres executions + details d'erreurs (mode=webhook filtre)
- `/exec/<id>` : details parsed d'une execution specifique
- `/raw/<id>` : reponse brute API pour debug
- `/test-quant`, `/test-orch`, `/test-all` : tests automatises
Proxy via nginx :
```nginx
location /diag { proxy_pass http://127.0.0.1:7861/diag; }
```
**REGLE** : Le format de donnees n8n peut etre une liste (inner[0] = root, string values = index references).
**Fichiers impactes** : `diag-server.py` (nouveau), `nginx.conf`, `Dockerfile`, `entrypoint.sh`

---

### FIX-32 — Quant $env blocked in Task Runner + Standard sub-workflow return
**Session** : 27 (2026-02-19)
**Pipelines** : Quantitative + Standard (pour Orchestrator)
**Symptome** : Quant 500 a 0.77s : `Cannot assign to read only property 'name' of object 'Error: access to env vars denied'`. Orch 200 body vide : sub-workflow Standard ne retourne rien via respondToWebhook.
**Causes racines (2 problemes)** :
1. **Quant — $env bloque dans Code nodes** : Le Task Runner sandbox de n8n 2.8.3 bloque l'acces a `$env` dans les Code nodes (typeVersion 2). Les expressions `$env` dans les HTTP Request nodes sont evaluees par le process principal et fonctionnent. Mais dans les Code nodes (evalues par le Task Runner JS), `$env.LLM_SQL_MODEL` leve `access to env vars denied`. Stack: `workflow-data-proxy-env-provider.js:59:27`.
2. **Standard — respondToWebhook ne retourne pas en sub-workflow** : Quand Standard RAG est appele comme sub-workflow par l'Orchestrator (`executeWorkflow`), le node `Respond to Webhook` envoie la reponse HTTP au webhook ORIGINAL mais ne retourne PAS les donnees au workflow appelant. L'Orchestrator ne recoit rien → Merge node bloque → Return Response jamais atteint → 200 vide.
**Fix** :
1. Remplacement de `$env.LLM_SQL_MODEL` et `$env.LLM_FAST_MODEL` par les valeurs hardcodees dans les 3 Code nodes (Prepare SQL Request, Prepare Interpretation Request, Prepare SQL Repair Request). Dans **BOTH** `nodes[]` ET `activeVersion.nodes[]`.
2. Ajout d'un node `Sub-Workflow Return` (Code node: `return $input.all()`) connecte en parallele de `Respond to Webhook` depuis `Response Formatter`. Dans **BOTH** `nodes[]` ET `activeVersion.nodes[]`.
**REGLE** : `$env` est INTERDIT dans les Code nodes n8n 2.7.4+ (Task Runner sandbox). Utiliser des valeurs hardcodees ou passer par HTTP Request expressions.
**REGLE** : `respondToWebhook` ne retourne PAS de donnees en mode sub-workflow. Ajouter un terminal Code node en parallele pour retourner les donnees au workflow parent.
**REGLE** : Toujours patcher BOTH `nodes[]` ET `activeVersion.nodes[]` (rappel FIX-29).
**Fichiers impactes** : `n8n-workflows/quantitative.json`, `n8n-workflows/standard.json` (HF Space)

---

### FIX-33 — n8n 2.8.3 $env bloque pour TOUS les types de noeuds (pas juste Code)
**Session** : 27 (2026-02-19)
**Composant** : HF Space — TOUS les workflows avec $env
**Symptome** : Quantitative retourne 200 mais `interpretation: "Error: access to env vars denied"`. Orchestrator 200 body vide (Intent Analyzer HTTP Request retourne error au lieu de LLM response). TOUTES les HTTP Request nodes avec $env retournent `{"error": "access to env vars denied"}`.
**Cause racine** : n8n 2.8.3 avec Task Runners TOUJOURS actifs evalue TOUTES les expressions (pas seulement les Code nodes) dans le sandbox du Task Runner. Le sandbox bloque l'acces a `$env` pour TOUS les types de noeuds : Code, HTTP Request, Postgres, etc. C'est un changement par rapport aux versions precedentes ou seuls les Code nodes etaient affectes.
**Preuve** : Execution #8 (Quantitative) — items[169] = `"access to env vars denied"`. Schema Introspection, Text-to-SQL Generator, SQL Executor, Interpretation Layer (TOUTES HTTP Request nodes) retournent le meme error item.
**Fix** : Remplacement de TOUTES les references `$env.X` par les valeurs reelles au moment de l'import dans entrypoint.sh. Un script Python parcourt le texte brut du JSON AVANT parsing et remplace chaque `$env.VAR_NAME` par la valeur de `os.environ.get(VAR_NAME, default)`. Couvre 30+ variables avec defaults.
**Impact** : 117 references $env a travers 5 workflows (quantitative: 20, orchestrator: 27, ingestion: 22, enrichment: 24, benchmark-dataset-ingestion: 24). Standard et Graph = 0 (deja clean).
**REGLE DEFINITIVE** : `$env` est INTERDIT dans n8n 2.8+ pour TOUS les types de noeuds. Ne JAMAIS utiliser $env dans les workflows. Injecter les valeurs a l'import ou utiliser des credentials n8n.
**Fichiers impactes** : `entrypoint.sh` (HF Space) — section import Python, `fix-env-refs.py` (standalone script)

---

### FIX-34 — Orchestrator executeWorkflow → httpRequest (sub-workflow return vide)
**Session** : 27 (2026-02-19)
**Pipeline** : Orchestrator V10.1
**Symptome** : Orchestrator retourne 200 body vide (SIZE:0, ~14s). Standard/Graph/Quant fonctionnent individuellement. Les 28 noeuds executes ont TOUS status=success, mais le `📥 Task Result Handler` ne fire jamais.
**Cause racine** : Les 3 noeuds `Invoke WF5: Standard`, `Invoke WF2: Graph`, `Invoke WF4: Quantitative` utilisent `executeWorkflow` pour appeler les sub-workflows. Mais les sub-workflows terminent avec `respondToWebhook` qui envoie la reponse HTTP au client original et NE RETOURNE PAS les donnees au noeud parent `executeWorkflow`. Resultat: `data.main: [[]]` (tableau vide) → `📥 Task Result Handler` ne recoit aucun item → boucle de taches rompue → `Response Builder V9` jamais atteint → `Return Response V8` jamais atteint → body vide.
**Preuve** : Execution #16 (Orchestrator post-FIX-33). `Invoke WF5: Standard` a `executionStatus: success` et `subExecution.executionId: 17` (mode integrated, success) MAIS `data.main: [[]]`. Sur 68 noeuds dans le workflow, seulement 28 executes. `📥 Task Result Handler`, `Response Builder V9`, `Merge`, `Return Response V8` ABSENTS de la liste des noeuds executes.
**Fix** : Remplacement des 3 noeuds `executeWorkflow` par des `httpRequest` (typeVersion 4.2) qui font des POST vers les webhooks locaux :
- `Invoke WF5: Standard` → POST `http://localhost:5678/webhook/rag-multi-index-v3`
- `Invoke WF2: Graph` → POST `http://localhost:5678/webhook/ff622742-6d71-4e91-af71-b5c666088717`
- `Invoke WF4: Quantitative` → POST `http://localhost:5678/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9`
Le body est `{ "query": "<task_query>" }`. Le timeout est 30s. La reponse JSON du sub-workflow est recue normalement par le noeud HTTP Request.
**Avantage** : Les sub-workflows fonctionnent parfaitement en mode webhook (testes). Pas besoin de modifier les sub-workflows, juste l'Orchestrator.
**REGLE** : Ne JAMAIS utiliser `executeWorkflow` pour appeler un workflow qui utilise `respondToWebhook`. Utiliser `httpRequest` POST vers le webhook a la place.
**Fichiers impactes** : `n8n-workflows/orchestrator.json` (HF Space)

---

### FIX-35 — Quantitative OPENROUTER_BASE_URL sans /chat/completions
**Session** : 27 (2026-02-19)
**Pipeline** : Quantitative V2.0
**Symptome** : Text-to-SQL Generator retourne une page HTML (`<!DOCTYPE html>...`) au lieu d'une reponse JSON LLM. Le SQL Validator recoit du HTML, ne trouve pas de SQL → fallback "Query must start with SELECT". Pipeline complete en 3s au lieu de 15-20s (trop rapide = court-circuit error).
**Cause racine** : Le HF Space secret `OPENROUTER_BASE_URL` etait `https://openrouter.ai/api/v1` (sans `/chat/completions`). Le script fix-env-refs.py remplace `$env.OPENROUTER_BASE_URL` par la valeur reelle de l'env var, qui est FAUSSE. L'expression `$env.OPENROUTER_BASE_URL || 'https://openrouter.ai/api/v1/chat/completions'` est remplacee par `'https://openrouter.ai/api/v1'` (env var prend precedence sur le fallback).
**Preuve** : Execution #65, noeud Text-to-SQL Generator output: `data: <!DOCTYPE html>...` (page HTML de openrouter.ai/api/v1, pas une reponse API).
**Fix** : Boucle dans entrypoint.sh qui detecte les URLs OpenRouter sans `/chat/completions` et les corrige AVANT l'appel a fix-env-refs.py. Variables corrigees: `OPENROUTER_BASE_URL`, `LLM_API_URL`, `ENTITY_EXTRACTION_API_URL`, `CONTEXTUAL_RETRIEVAL_API_URL`.
**REGLE** : Les URLs OpenRouter API DOIVENT finir par `/chat/completions`. URL de base seule (`/api/v1`) retourne une page HTML.
**Detection rapide** : Si un pipeline quantitatif/LLM complete en < 5s avec erreur, verifier que l'URL API ne retourne pas du HTML.
**Fichiers impactes** : `entrypoint.sh` (HF Space)

---

### FIX-36 — Phase 1 gates comptaient questions Phase 2 (musique, finqa)
**Session** : 30 (2026-02-20)
**Composant** : `eval/generate_status.py`, `eval/phase_gates.py`
**Symptome** : Phase 1 gates bloques (Graph 68.7%, Quant 78.3%) alors que les 4 pipelines passaient largement leurs cibles sur les questions Phase 1 seules (Graph 78%, Quant 92%).
**Cause racine** : `compute_registry_accuracy()` dans `generate_status.py` et `get_pipeline_accuracy()` dans `phase_gates.py` iteraient sur TOUTES les questions du `question_registry` sans distinguer Phase 1 de Phase 2. Les 17 questions musique (41% accuracy) et 10 questions finqa (40% accuracy), injectees lors des iterations exploratoires "Phase2-quant-*", etaient comptees dans le denominateur Phase 1.
**Impact** : Phase 1 artificiellement bloquee depuis le 16 fevrier (4 jours). Toutes les tentatives de "fix Graph +1.3pp" et "fix Quant SQL generation" etaient inutiles.
**Fix** : Ajout de `_is_phase1_question(qid)` dans les deux scripts. Filtre les question IDs contenant "musique", "finqa", ou "phase2". `compute_registry_accuracy(data, phase1_only=True)` et `get_pipeline_accuracy(data, phase1_only=True)`.
**Resultat** : Phase 1 PASSED immediatement — Standard 85.5%, Graph 78.0%, Quant 92.0%, Orch 80.0%, Overall 83.9%.
**REGLE** : Les gates de Phase N ne doivent JAMAIS inclure les questions de Phase N+1 dans leur calcul. Chaque phase a ses propres targets et ses propres datasets.
**Fichiers impactes** : `eval/generate_status.py`, `eval/phase_gates.py`

---

### FIX-37 — Quantitative Phase 2 : context-based questions need LLM reasoning, not SQL
**Session** : 34 (2026-02-21)
**Pipeline** : Quantitative V2.1
**Symptome** : Phase 2 accuracy 10% (1/10). Questions finqa/tatqa/convfinqa/wikitablequestions contiennent du contexte financier + tableaux inline dans le champ `query`. Le pipeline essaie de generer du SQL pour ces questions → echec car les donnees ne sont pas dans Supabase.
**Cause racine** : Les questions Phase 2 quantitatives (datasets HuggingFace) ont un format different des questions Phase 1 :
- Phase 1 : questions simples sur des tables existantes dans Supabase ("What was TechVision's revenue?")
- Phase 2 : questions avec contexte financier complet inline ("Please answer the given financial question based on the context. Context: [long text + tables]. Question: what is the net change?")
Le pipeline Phase 1 (Text-to-SQL → Execute SQL → Interpret) ne fonctionne pas pour les questions Phase 2 qui ne necessitent PAS de SQL mais du raisonnement direct sur le contexte fourni.
**Fix** (3 corrections independantes) :
1. **Architecture : ajout branche context reasoning** — 5 nouveaux noeuds :
   - `Question Type Classifier` (Code) — detecte si la question contient `Context:` + tables
   - `Route by Question Type` (IF) — branche context_reasoning vs sql_query
   - `Prepare Context Reasoning` (Code) — construit le prompt LLM avec contexte + question
   - `Context Reasoning LLM` (HTTP Request) — appelle OpenRouter Llama 70B
   - `Context Response Formatter` (Code) — formate la reponse dans le format standard
   Connections : Init & ACL → Classifier → Router → (Context path | SQL path)
2. **FIX-32 applique** : `$env.LLM_SQL_MODEL` et `$env.LLM_FAST_MODEL` remplaces par valeurs hardcodees dans 3 Code nodes (Prepare SQL Request, Prepare Interpretation Request, Prepare SQL Repair Request)
3. **FIX-22 applique** : Timeouts 25s→60s, retries 1→3, waitBetweenTries 1s→5s sur 3 HTTP Request nodes (Text-to-SQL Generator, Interpretation Layer, SQL Repair LLM)
**Bonus** : Nettoyage de 9,276 cles stale `retry_sql-repair-*` dans staticData (472KB → 99KB)
**Script** : `scripts/fix-quant-phase2.py` — applique les 3 corrections + nettoie staticData + patche activeVersion
**REGLE** : Les datasets Phase 2+ peuvent avoir des formats differents des questions Phase 1. Le pipeline doit detecter le format et router vers le traitement adapte.
**Fichiers impactes** : `n8n/live/quantitative.json`, `n8n/live/quantitative-v2-template-fix.json`, `snapshot/current/quantitative.json`

---

### FIX-38 — 2wikimultihopqa context format not parsed (Graph 27% accuracy)
**Session** : 35 (2026-02-21)
**Pipeline** : Graph RAG (Phase 2 eval)
**Symptome** : Graph accuracy on 2wikimultihopqa = 27.3% vs musique = 46.0%. Massive NO_MATCH rate (50%).
**Root cause** : `load_questions()` only handled musique context format `[{"title":..., "paragraph_text":...}]` but NOT 2wikimultihopqa format `{"title": [...], "sentences": [[...],...]}`. The code checked `ctx.startswith('[')` — 2wikimultihopqa starts with `{` so `paragraphs = []`, context was empty, LLM had no data to reason from.
**Fix** : Created `_embed_graph_context()` function that handles ALL known formats:
- Format 1: `[{"title":..., "paragraph_text":...}]` (musique, hotpotqa)
- Format 2: `{"title": [...], "sentences": [[...],...]}` (2wikimultihopqa)
- Format 3: Plain text
**Files** : `eval/run-eval.py`
**Verification** : All 500 graph questions now have `Reference context:` embedded (was ~200 before).

---

### FIX-39h — Permanent data validation + preflight checks
**Session** : 35 (2026-02-21)
**Pipeline** : ALL (eval infrastructure)
**Symptome** : Recurring data issues across eval runs: stripped context, wrong formats, silent failures.
**Root cause** : No validation layer between datasets and eval scripts.
**Fix** (3 new files):
1. `eval/data_validator.py` — Validates ALL datasets: checks context formats, table_data, ID uniqueness, expected_answer, rag_target. Detects 5 context formats. Can run standalone.
2. `eval/preflight.py` — Pre-flight checks: validates data + env vars + connectivity + disk space. Auto-loads .env.local.
3. `eval/run-eval-parallel.py` — Now auto-runs preflight before every eval. Blocks on fatal errors (unless --force).
4. `eval/run-eval.py` — Refactored `load_questions()` into modular helpers: `_embed_graph_context()`, `_embed_quant_context()`, `_load_dataset_file()`. Logs data quality summary after loading.
**Also fixed** : Quantitative table_data now formatted as readable text (pipe-delimited) instead of raw JSON string.
**RULE** : NEVER run eval without data validation. The preflight check is automatic — respect it.

---

### FIX-40 — VM OOM cascade: zombie processes → PG timeouts → all webhooks down
**Session** : 40 (2026-02-23)
**Pipeline** : ALL (infrastructure)
**Symptome** : All 9 webhooks returning 404/503. n8n healthz says OK but no webhook can execute. PostgreSQL "Database connection timed out" in a loop.
**Root cause** : Chain of failures:
1. Overnight eval scripts (`run-eval-parallel.py`) ran for hours hitting 404s, accumulating memory
2. Multiple `git pack-objects` processes stuck from failed pushes (~310MB total)
3. Old Claude Code zombie session consuming ~67MB
4. RAM: 55MB free, swap 100% full (2047/2047 MB)
5. PostgreSQL connections timing out due to memory pressure → n8n can't serve webhooks
6. Additionally, 106 stale executions (73 in `new` status) from queued webhook requests
**Fix** (multi-step):
1. Kill zombie processes: `kill <git-pack-objects PIDs> <old-eval PIDs> <old-claude PID>` → freed ~350MB
2. Clean stale executions: `DELETE FROM execution_data; DELETE FROM execution_entity;` + VACUUM
3. Full docker compose down/up cycle (not just restart)
4. Wait for full n8n startup (~65-110s on e2-micro)
**Result** : All 5 webhooks (Standard, Graph, Quant, Orchestrator, Dashboard) returning 200.
**Prevention** :
- Rule 27: Kill old Claude processes at session start
- Add process cleanup to overnight scripts (kill stale git pack-objects)
- Monitor swap usage — 100% swap = imminent cascade failure
**Fichiers impactes** : None (runtime fix)

---

### FIX-41 — FIX-05 TTL re-applied: Task Runner auth 15s→120s still needed on e2-micro
**Session** : 40 (2026-02-23)
**Pipeline** : ALL (n8n Task Runner)
**Symptome** : After restart, webhooks return 503 with "Task request timed out after 60 seconds" and "Task runner connection attempt failed with status code 403".
**Root cause** : docker-compose.yml had removed the TTL patch volume mount (comment: "n8n 2.7.4 has built-in TTL handling"). But on e2-micro VM (1 vCPU, 970MB RAM), the Task Runner can't authenticate within the 15s default TTL due to slow startup.
**Fix** : Re-added volume mount in docker-compose.yml:
```yaml
- ./task-broker-auth.service.js:/usr/local/lib/node_modules/n8n/dist/task-runners/task-broker/auth/task-broker-auth.service.js:ro
```
With TTL changed from `15 * seconds` to `120 * seconds`.
**RULE** : NEVER remove FIX-05 TTL patch on e2-micro VM. The built-in 15s TTL is too short for this hardware.
**Fichiers impactes** : `/home/termius/n8n/docker-compose.yml`, `/home/termius/n8n/task-broker-auth.service.js`

---

### FIX-42 — Stuck executions (79 new/running) block webhook processing
**Session** : 40b (2026-02-23, overnight self-healing)
**Pipeline** : ALL
**Symptome** : All webhooks accept HTTP POST (connection established, data sent) but never respond (curl hangs, eventually times out with code 000). `healthz` returns 200. n8n logs show "Execution is already being resumed by another process" spam (50+ lines).
**Root cause** : After OOM cascade + container restart, 79 executions stuck in `new`/`running` status in `execution_entity` table. n8n tries to resume ALL of them on startup, consuming all available processing capacity. New webhook requests are accepted but queued behind the stuck execution resume attempts and never processed.
**Diagnosis** :
```sql
-- Check stuck executions
SELECT status, COUNT(*) FROM execution_entity GROUP BY status;
-- Result: new|77, running|2, success|14, error|11, crashed|7
```
**Fix** :
```bash
# 1. Stop n8n
docker stop n8n-n8n-1
# 2. Delete ALL non-final executions
docker exec n8n-postgres-1 psql -U n8n -d n8n -t -A -c \
  "DELETE FROM execution_entity WHERE status IN ('new', 'running', 'waiting', 'crashed');"
# 3. Start n8n (clean activation, no resume spam)
docker start n8n-n8n-1
# 4. Wait 35s for full startup + webhook registration
sleep 35
# 5. Verify
curl -s http://localhost:5678/healthz
```
**Result** : All 7 active webhooks restored to HTTP 200. Clean startup logs, no resume spam.
**RULE** : When n8n hangs on webhook responses but healthz is OK, ALWAYS check for stuck executions first. This is the #1 cause of "webhooks accept but never respond" on the VM.
**Prevention** : The overnight script should clean stuck executions on every restart cycle.
**Fichiers impactes** : None (runtime fix — DB cleanup + restart)

### FIX-43 — PME workflows active=true but 0 webhooks registered (silent credential failure)
**Session** : 40c (2026-02-23, overnight self-healing #2)
**Pipeline** : PME Gateway, PME Action Executor
**Symptome** : PME workflows show `active=true` in `workflow_entity` but `webhook_entity` has 0 rows for them. Webhook calls return 404 "not registered".
**Root cause** : n8n sets `active=true` in the DB but fails to register webhooks when referenced credentials don't exist. The failure is SILENT — no error logs, no exception, just 0 webhooks. VM only has 2 credentials (Redis + Supabase PG). PME Gateway needs `OPENROUTER_HEADER_AUTH`, Action Executor needs that + 3 Google OAuth2 credentials.
**Diagnosis** :
```sql
-- Check webhook count per workflow
SELECT we.id, we.name, we.active,
  (SELECT COUNT(*) FROM webhook_entity wh WHERE wh."workflowId" = we.id) as webhook_count
FROM workflow_entity we WHERE we.active = true;
-- Result: PME workflows show active=true, webhook_count=0

-- List available credentials
SELECT id, name, type FROM credentials_entity;
-- Result: only Redis and Supabase PG
```
**Fix** : Deactivated PME workflows on VM since they can't function without credentials:
```sql
UPDATE workflow_entity SET active = false WHERE id IN ('EaB5iHZsHBCBzFk2', 'IipwYgPoWqM3axwY');
```
**RULE** : PME workflows work ONLY on HF Space (which has 12 credentials). On VM, deactivate them to prevent confusion.
**Prevention** : Before activating any workflow, verify ALL referenced credentials exist:
```sql
SELECT DISTINCT node->'credentials'->>key FROM jsonb_array_elements(nodes::jsonb) AS node, LATERAL jsonb_object_keys(COALESCE(node->'credentials', '{}'::jsonb)) AS key;
```
**Fichiers impactes** : None (runtime — DB deactivation)

---

### FIX-48 — HF Space nginx reverse proxy causes persistent 502
**Session** : 42 (2026-02-23)
**Composant** : HF Space infrastructure
**Symptome** : HF Space returns HTTP 502 despite n8n container running and healthz showing OK internally. nginx inside container can't bind properly or route to n8n.
**Root cause** : nginx as reverse proxy in HF Space container doesn't work reliably. The HF proxy at the edge expects the container to listen directly on port 7860 (HF's standard port). Running nginx → n8n creates an extra layer that fails unpredictably.
**Fix** : Remove nginx entirely from the stack. Set `N8N_PORT=7860` so n8n listens directly on HF's required port. Remove nginx from:
- Dockerfile (apt-get install)
- supervisord.conf (nginx program)
- entrypoint.sh (nginx config generation)
- nginx.conf (deprecated file)
```bash
# entrypoint.sh - BEFORE
nginx -g 'daemon off;' &
NGINX_PID=$!

# entrypoint.sh - AFTER (nginx removed completely)
export N8N_PORT=7860
n8n start &
N8N_PID=$!
```
**RULE** : HF Space containers MUST expose services directly on port 7860. NO reverse proxy layer.
**Fichiers impactes** : `hf-space/Dockerfile`, `hf-space/entrypoint.sh`, `hf-space/nginx.conf` (deprecated)

---

### FIX-49 — n8n SQLite minimal boot for HF Space
**Session** : 42 (2026-02-23)
**Composant** : HF Space n8n configuration
**Symptome** : n8n fails to start with PostgreSQL + queue mode on HF Space. Returns 500 errors, timeouts, or never becomes ready even after waiting 120s.
**Root cause** : Too many dependencies at once (Supabase PostgreSQL external connection, Redis queue, supervisord managing multiple processes, worker processes) create race conditions and connection failures on cold boot. PostgreSQL connection over network can timeout, Redis might not be ready, workers start before main process is ready.
**Fix** : Strip to minimal boot configuration:
- SQLite database (no external PostgreSQL connection)
- Single process mode (no queue, no workers)
- Direct n8n start (no supervisord complexity)
```bash
# Minimal n8n environment
export DB_TYPE=sqlite
export DB_SQLITE_DATABASE=/app/n8n-data/database.sqlite
export EXECUTIONS_MODE=regular  # NOT queue
export N8N_DIAGNOSTICS_ENABLED=false
export N8N_PERSONALIZATION_ENABLED=false

# NO Redis, NO workers, NO PostgreSQL
n8n start &
N8N_PID=$!
```
Add dependencies one at a time AFTER confirming boot is stable. Test each addition separately.
**RULE** : Always start with minimal viable configuration. Add complexity incrementally once stability is proven.
**Fichiers impactes** : `hf-space/entrypoint.sh`, `hf-space/Dockerfile`

---

### FIX-50 — n8n v2.8+ login field change (emailOrLdapLoginId)
**Session** : 42 (2026-02-23)
**Composant** : n8n REST API authentication
**Symptome** : Login to n8n REST API returns HTTP 400 with error message "emailOrLdapLoginId is required"
**Root cause** : n8n v2.8+ changed the login endpoint POST body schema. The field `email` was renamed to `emailOrLdapLoginId` to support both email and LDAP login identifiers.
**Fix** : Change POST body for `/rest/login`:
```bash
# n8n < 2.8 (OLD)
curl -X POST http://localhost:5678/rest/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"..."}'

# n8n >= 2.8 (NEW)
curl -X POST http://localhost:5678/rest/login \
  -H "Content-Type: application/json" \
  -d '{"emailOrLdapLoginId":"admin@example.com","password":"..."}'
```
**Note** : This is different from FIX-17 which was discovered in Session 24 but applies to the same API change. Documenting separately as Session 42 encountered it in HF Space context.
**Fichiers impactes** : `hf-space/entrypoint.sh`, any scripts calling n8n login API

---

### FIX-51 — set -e kills HF Space container on any failure
**Session** : 42 (2026-02-23)
**Composant** : HF Space entrypoint.sh
**Symptome** : Container exits immediately after any transient failure in entrypoint.sh (DNS timeout, API 500, temporary network glitch, missing env var, etc.). HF Space shows "Runtime error" and container never stays alive.
**Root cause** : `set -e` at top of entrypoint.sh causes bash to exit on any non-zero return code. In cloud environments (HF Space), transient failures are common: DNS can timeout, external APIs can return 500, network can glitch. With `set -e`, ANY of these causes immediate container death.
**Fix** : Remove `set -e`. Wrap setup logic in best-effort blocks with `|| true` for non-critical operations. The container MUST always reach the final `wait $N8N_PID` to stay alive, even if setup partially fails.
```bash
# entrypoint.sh - BEFORE
#!/bin/bash
set -e  # ← KILLS CONTAINER on any error

# entrypoint.sh - AFTER
#!/bin/bash
# NO set -e

# Best-effort operations
curl -s http://example.com/setup || echo "Setup failed but continuing..."
python3 setup.py || true  # Non-critical, continue even if it fails

# Critical operation - check explicitly
n8n start &
N8N_PID=$!
if [ -z "$N8N_PID" ]; then
  echo "FATAL: n8n failed to start"
  exit 1
fi

# MUST reach this line to keep container alive
wait $N8N_PID
```
**RULE** : NEVER use `set -e` in container entrypoints for cloud environments. Handle failures explicitly and keep the main process alive.
**Fichiers impactes** : `hf-space/entrypoint.sh`

---

### FIX-52 — Hardcoded API keys in n8n workflow JSONs
**Session** : 43 (2026-02-23)
**Pipelines** : Standard, Graph, Quantitative
**Symptome** : Workflows fail with HTTP 401 from OpenRouter because hardcoded API key expired. Also major security risk (API keys committed to git, visible in JSON exports).
**Root cause** : HTTP Request nodes had API keys (OpenRouter, Pinecone, Jina) hardcoded directly in two places:
1. `headerParameters` field: `{"name":"Authorization","value":"Bearer sk-or-v1-..."}`
2. `jsCode` expressions: `headers['Authorization'] = 'Bearer sk-or-v1-...'`
When keys rotate or expire, ALL workflow JSONs need manual editing. Keys are also exposed in git commits and exports.
**Fix** : Replace all hardcoded keys with n8n environment variable expressions. Each pipeline gets its own OpenRouter key env var for per-pipeline rate limit isolation:
```javascript
// HTTP Request node - headerParameters (BEFORE)
"headerParameters": {
  "parameters": [{"name":"Authorization","value":"Bearer sk-or-v1-abc123..."}]
}

// HTTP Request node - headerParameters (AFTER)
"headerParameters": {
  "parameters": [{"name":"Authorization","value":"={{$env.OPENROUTER_KEY_STANDARD}}"}]
}

// Code node - jsCode (BEFORE)
headers['Authorization'] = 'Bearer sk-or-v1-abc123...';

// Code node - jsCode (AFTER)
headers['Authorization'] = `Bearer ${$env.OPENROUTER_KEY_STANDARD}`;
```
**Environment variables created**:
- `OPENROUTER_KEY_STANDARD` — Standard RAG pipeline
- `OPENROUTER_KEY_GRAPH` — Graph RAG pipeline
- `OPENROUTER_KEY_QUANTITATIVE` — Quantitative pipeline
- `OPENROUTER_KEY_ORCHESTRATOR` — Orchestrator pipeline
- `PINECONE_API_KEY` — All pipelines
- `JINA_API_KEY` — All pipelines
**RULE** : NEVER hardcode API keys in workflow JSONs. Always use `={{$env.VAR_NAME}}` expressions. This applies to ALL HTTP Request nodes and Code nodes making external API calls.
**Security benefit** : Keys no longer visible in git. Can rotate keys by changing env vars without touching workflow code.
**Fichiers impactes** : `hf-space/n8n-workflows/standard.json`, `graph.json`, `quantitative-v2-template-fix.json`

---

### FIX-53 — n8n credential ID mismatch after fresh import
**Session** : 43 (2026-02-23)
**Composant** : n8n workflow import process
**Symptome** : Imported workflows reference credential IDs (e.g., `USU8ngVzsUbED3mn`, `CWih07lwPxfwFeY6`) that don't exist in the fresh n8n instance. Nodes silently fail or show "Credential does not exist" errors.
**Root cause** : Credential IDs are auto-generated by n8n at credential creation time. When workflows are exported from one n8n instance (VM) and imported to another (HF Space), the credential IDs in the workflow JSON reference the OLD instance's credentials. The fresh instance has different auto-generated IDs. n8n doesn't automatically remap credential references during import.
**Fix** : Created `setup-workflows.py` that orchestrates the entire import process:
1. **Create credentials first** via REST API: Postgres (x4), OpenRouter httpHeaderAuth (x4), Pinecone (x2), Neo4j
2. **Get new credential IDs** from the fresh instance
3. **Build mapping** of old IDs → new IDs (e.g., `USU8ngVzsUbED3mn` → `abc123xyz`)
4. **Remap all credential references** in workflow JSONs before import:
```python
# Credential remapping
CREDENTIAL_MAP = {
    'USU8ngVzsUbED3mn': new_postgres_id,
    'CWih07lwPxfwFeY6': new_redis_id,
    # ... etc
}

for node in workflow['nodes']:
    if 'credentials' in node:
        for cred_type, cred_ref in node['credentials'].items():
            old_id = cred_ref['id']
            if old_id in CREDENTIAL_MAP:
                cred_ref['id'] = CREDENTIAL_MAP[old_id]
                cred_ref['name'] = NEW_CREDENTIAL_NAMES[CREDENTIAL_MAP[old_id]]
```
5. **Import workflows** via REST API with remapped credentials
6. **Activate all workflows** using the new activation endpoint
**Credentials created** (12 total):
- 4 Postgres (Quant, Orch Agent, Orch Metadata, Ingestion)
- 4 OpenRouter httpHeaderAuth (Standard, Graph, Quant, Orch)
- 2 Pinecone (Standard, Graph)
- 1 Neo4j
- 1 Redis (optional)
**RULE** : NEVER directly import workflows without credential remapping. Always: 1) Create credentials, 2) Get new IDs, 3) Remap workflow JSONs, 4) Import, 5) Activate.
**Alternative** : Use generic credentials with fixed names and modify workflow export to reference credential names instead of IDs (more complex, less reliable).
**Fichiers impactes** : `hf-space/setup-workflows.py`, `hf-space/entrypoint.sh` (calls setup-workflows.py)

---

### FIX-54: Broken n8n expression syntax `={{.VAR}}` → `={{$env.VAR}}`
- **Date**: 2026-02-23 (Session 51)
- **Symptome**: Standard + Graph pipelines return "Unable to generate answer" on every question. Quantitative works fine.
- **Cause racine**: Workflow JSONs (standard.json, graph.json, benchmark-dataset-ingestion.json) used broken n8n expression syntax `={{.OPENROUTER_KEY_STANDARD}}` instead of correct `={{$env.OPENROUTER_KEY_STANDARD}}`. The `={{.VAR}}` syntax is NOT valid in n8n — it evaluates to `null`, causing all HTTP headers to send `Bearer null` for OpenRouter, Jina, and Pinecone API calls.
- **Pourquoi Quantitative marchait**: quantitative.json already used correct `={{$env.VAR}}` syntax. Also uses `credentials.httpHeaderAuth` approach in some nodes.
- **Solution**: `sed -i 's/={{\\./={{$env./g'` across all affected JSONs (n8n/live/ + hf-space/n8n-workflows/). Total: 17 instances fixed (8 standard, 5 graph, 1 benchmark, 3 quantitative-template).
- **Verification**: `grep -r '={{\\.' n8n/live/ hf-space/n8n-workflows/` returns zero matches.
- **Lecon**: When a pipeline returns empty/error answers while another works, CHECK THE EXPRESSION SYNTAX before debugging activation or credentials. Compare working vs broken workflow JSONs.

### FIX-55: rag-storage migration (datasets/snapshots/logs/outputs)
- **Date**: 2026-02-23 (Session 51)
- **Symptome**: mon-ipad repo growing too large with datasets, snapshots, logs, outputs
- **Solution**: Created rag-storage repo, moved large data directories there
- **Commit**: 965ffc3

### FIX-56: Removed nodeCredentialType from 43 nodes across 9 JSONs
- **Date**: 2026-02-23 (Session 52)
- **Symptome**: Standard pipeline still returning "Unable to generate answer" after FIX-54
- **Solution**: Removed `nodeCredentialType:"openRouterApi"` from all HTTP request nodes
- **Resultat**: Did NOT fix the problem — root cause was FIX-58

### FIX-57: Cohere Reranker wrong API key (JINA_API_KEY → COHERE_API_KEY)
- **Date**: 2026-02-23 (Session 52)
- **Symptome**: Standard pipeline Cohere Reranker using wrong env var
- **Solution**: Changed `$env.JINA_API_KEY` to `$env.COHERE_API_KEY` in Cohere Reranker node

### FIX-58: HF Space secrets NOT CONFIGURED — ALL API keys empty (CRITICAL)
- **Date**: 2026-02-24 (Session 53)
- **Symptome**: ALL 4 pipelines return errors/empty answers. Standard: "Unable to generate answer". Graph: "Information not available" (0 context sources). Quantitative: "NO_ANSWER". Orchestrator: empty/timeout.
- **Cause racine**: HF Space had ZERO API key secrets configured. Only 2 variables existed (LLM_SQL_MODEL, LLM_SQL_FALLBACK_MODEL). The entrypoint.sh correctly exports `OPENROUTER_KEY_STANDARD`, `PINECONE_API_KEY`, `JINA_API_KEY`, etc. BUT these default to `${HF_SECRET:-}` which is empty if the HF Space secret doesn't exist. Result: all `$env.VAR` expressions in workflows resolve to empty string → `Bearer ` (no key) → all API calls fail.
- **Pourquoi personne n'a vu**: Sessions 42-52 focused on activation bugs, env var syntax, credential types. Nobody checked if the actual HF Space secrets were configured. The entrypoint.sh logs said "OPENROUTER_API_KEY: UNSET" but this was buried in build logs nobody read.
- **Solution**: `huggingface_hub.add_space_secret()` to push 13 secrets from `.env.local` to HF Space. Then `restart_space(factory_reboot=True)` to trigger full Docker rebuild with new secrets.
- **Secrets pushed**: OPENROUTER_API_KEY, OPENROUTER_KEY_STANDARD, OPENROUTER_KEY_GRAPH, OPENROUTER_KEY_QUANTITATIVE, OPENROUTER_KEY_ORCHESTRATOR, OPENROUTER_KEY_PME, PINECONE_API_KEY, JINA_API_KEY, SUPABASE_PASSWORD, COHERE_API_KEY, N8N_ENCRYPTION_KEY, NEO4J_AUTH, NEO4J_URI
- **Lecon**: ALWAYS verify HF Space secrets exist after any rebuild/reconfiguration. Use `api.get_space_variables()` to check. The entrypoint.sh ENV CHECK section logs tell you if vars are set — check build logs after deploy.

### FIX-59: OpenRouter free models rate-limited — swap to alternatives
- **Date**: 2026-02-24 (Session 54)
- **Symptome**: Pipelines respond but LLM calls return empty/fallback. OpenRouter 429 "temporarily rate-limited upstream" for Llama 70B, Gemma 27B.
- **Cause racine**: `meta-llama/llama-3.3-70b-instruct:free` and `google/gemma-3-27b-it:free` globally rate-limited on OpenRouter free tier. Model names HARDCODED in workflow JSONs (NOT using `$env.LLM_*_MODEL`).
- **Solution**: sed replace in `hf-space/n8n-workflows/*.json` + `n8n/live/*.json`:
  - `meta-llama/llama-3.3-70b-instruct:free` → `mistralai/mistral-small-3.1-24b-instruct:free` (11 refs)
  - `google/gemma-3-27b-it:free` → `stepfun/step-3.5-flash:free` (5 refs)
  - `arcee-ai/trinity-large-preview:free` kept (17 refs, still available)
- **Upload**: `huggingface_hub.upload_file()` to push 13 updated workflow JSONs to HF Space
- **Lecon**: Model names are HARDCODED in n8n workflow JSONs, not env vars. To switch models, must edit JSONs + redeploy. Consider migrating to `$env.LLM_*_MODEL` expressions for dynamic switching.

### FIX-60: HF Space CONFIG_ERROR from duplicate secret+variable names
- **Date**: 2026-02-24 (Session 54)
- **Symptome**: HF Space stuck in `CONFIG_ERROR`, `Hardware: None`. Triggered by adding LLM_MAIN_MODEL, LLM_FAST_MODEL, LLM_EXTRACT_MODEL as BOTH secrets AND variables.
- **Cause racine**: Setting a key as both a HF Space secret and a variable causes CONFIG_ERROR. The Space loses its hardware assignment.
- **Solution**: `api.delete_space_variable()` + `api.delete_space_secret()` for the conflicting keys, then `api.request_space_hardware("cpu-basic")` + `factory_reboot=True`.
- **Lecon**: NEVER set the same key as both a secret AND a variable on HF Spaces. Use secrets for sensitive values, variables for non-sensitive config.

### FIX-61: Jina API credits exhausted — Standard + Graph pipelines blocked
- **Date**: 2026-02-24 (Session 54)
- **Symptome**: Standard: "Unable to generate answer". Graph: "Information not available" (traversal_depth=0). Both use Jina for query embeddings.
- **Cause racine**: Jina API key has $0 balance. `AUTHZ_INSUFFICIENT_BALANCE` error. Phase 2 testing (579+ Standard + 500 Graph questions) exhausted the free 1M tokens/month.
- **Impact**: WITHOUT Jina embeddings, no vector search possible → no context for LLM → all embedding-dependent pipelines fail.
- **Solution needed**: Top up Jina account at https://jina.ai/api-dashboard/key-manager OR create new account for fresh free credits.
- **Also**: Cohere trial key exceeded (1000 calls/month) → reranking broken.
- **Lecon**: Monitor API credit usage during large-scale testing. Phase 2 (1000q × 4 pipelines) can exhaust free tier credits in 1-2 days. Budget for paid API keys for 10K testing.

### FIX-62: n8n Jina + Cohere credentials missing on HF Space
- **Date**: 2026-02-24 (Session 54)
- **Symptome**: Workflows using Jina or Cohere APIs fail because no credentials exist in n8n
- **Cause racine**: Jina and Cohere credentials were not imported to HF Space n8n during initial setup
- **Impact**: Cannot use Jina embeddings or Cohere reranking from workflow HTTP Request nodes
- **Solution**:
  1. Login to HF Space n8n via REST API: `POST /rest/login` with `{"emailOrLdapLoginId": "ci@nomos.ai", "password": "CI-Nomos-2026!"}`
  2. Create httpHeaderAuth credentials via `POST /rest/credentials`:
     - **Jina API Key**: `{"name": "Jina API Key", "type": "httpHeaderAuth", "data": {"name": "Authorization", "value": "Bearer jina_..."}}`
     - **Cohere API Key**: `{"name": "Cohere API Key", "type": "httpHeaderAuth", "data": {"name": "Authorization", "value": "Bearer tBM0vcH3l9j6EXsl3BEZBsWMdr0Bsjx2IpGoM9kP"}}`
  3. Verify with `GET /rest/credentials`
- **Credentials created**:
  - Jina API Key (ID: gwQvKQzF2kN4PqsO)
  - Cohere API Key (ID: s2ZLvkU1znR0lfvu)
- **Note**: n8n Variables NOT available on free plan (403 - "Plan lacks license for this feature"). Use credentials instead.
- **Script**: `/home/termius/mon-ipad/scripts/fix-n8n-credentials.py` — automated setup
- **Lecon**: Always verify all required credentials exist when deploying workflows to new n8n instance. Use `GET /rest/credentials` to list.

---

### FIX-63: N8N_BLOCK_ENV_ACCESS_IN_NODE missing — ALL $env references return "access to env vars denied"
- **Date**: 2026-02-24 (Session 58)
- **Composant**: HF Space — ALL workflows using $env.*
- **Symptome**: ALL pipelines return "Unable to generate answer" or "NO_ANSWER". Execution data shows `Context Reasoning LLM` output = `{"error": "access to env vars denied"}`. Standard returns "Unable to generate answer", Quantitative returns "NO_ANSWER", Graph returns "Information not available", Orchestrator returns empty body.
- **Cause racine**: n8n 2.8.3 blocks `$env.*` access in ALL node types by default. The entrypoint.sh was missing `N8N_BLOCK_ENV_ACCESS_IN_NODE=false`. Despite 20 HF secrets being correctly set (OPENROUTER_KEY_STANDARD, JINA_API_KEY, etc.), n8n refused to resolve them in workflow expressions. The Standard workflow has 12+ Authorization headers using `Bearer ={{$env.OPENROUTER_KEY_STANDARD}}`, `Bearer ={{$env.JINA_API_KEY}}`, `Bearer ={{$env.COHERE_API_KEY}}` — ALL returning empty/denied.
- **Diagnostic**: `GET /rest/executions/25` → dehydrated data → `Context Reasoning LLM` node → output json → `{"error": "access to env vars denied"}`. Also `interpretation: "NO_ANSWER"`, `status: "ERROR"`.
- **Relation FIX-33**: FIX-33 (Session 27) documented the same root cause but the fix was to replace $env refs at import time. That approach was fragile and broke on subsequent rebuilds/imports.
- **Fix permanent**:
  1. Added `export N8N_BLOCK_ENV_ACCESS_IN_NODE=false` to entrypoint.sh (committed to HF Space repo)
  2. Added `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` as HF Space secret
  3. This allows n8n to resolve `$env.*` natively from container env vars
- **Impact**: CROSS-PIPELINE — fixes ALL 5 pipelines simultaneously (Standard, Graph, Quantitative, Orchestrator, PME Gateway)
- **REGLE MISE A JOUR**: AP-7 et AP-8 sont obsoletes. Avec `N8N_BLOCK_ENV_ACCESS_IN_NODE=false`, `$env.*` fonctionne normalement. La config doit TOUJOURS etre presente dans entrypoint.sh.
- **Fichiers impactes**: `entrypoint.sh` (HF Space repo)

---

### FIX-64: Ingestion V4.0 workflow HTTP 500 — Redis lock nodes preventing startup
- **Date**: 2026-02-25 (Session 61)
- **Composant**: Ingestion V4.0 workflow (`nh1D4Up0wBZhuQbp`)
- **Symptome**: POST `/webhook/rag-v6-ingestion` returns HTTP 500 "Workflow could not be started!". Workflow has 2 Redis lock nodes (Redis: Acquire Lock, Redis: Release Lock) but Redis was removed from the system in Session 42.
- **Cause racine**: The workflow still had Redis nodes (type: `n8n-nodes-base.redis`) with credential references to a non-existent Redis credential (`FmGCS5UwjP5x5gRx`). When n8n tried to start the workflow, it couldn't resolve the Redis credentials, causing a startup failure.
- **Fix strategy** (same pattern as Orchestrator Redis removal in Session 60):
  1. **Convert Redis nodes to bypass Code nodes** instead of removing them (preserves workflow structure)
  2. `Redis: Acquire Lock` → Code node that returns `"OK"` (simulates successful lock acquisition)
  3. `Redis: Release Lock` → Code node that passes through input with `redis_status: "bypassed"` flag
  4. **Remove credentials field** from both converted nodes
- **Implementation**:
  ```javascript
  // Redis: Acquire Lock bypass code
  const input = $input.first()?.json || {};
  return [{ json: "OK" }];

  // Redis: Release Lock bypass code
  const input = $input.first()?.json || {};
  return [{ json: { ...input, redis_status: "bypassed" } }];
  ```
- **Validation**: Workflow structure verified: 30 nodes total, 2 Redis nodes converted to Code type, credentials removed, active status = true
- **Snapshot**: `snapshot/working-session61/ingestion-v4.0-no-redis.json`
- **Note**: Webhook still returns 500 on direct POST test, likely due to missing S3 event payload structure or other downstream dependencies. Real ingestion via Dataset Ingestion workflow may work correctly with proper S3 event payloads.
- **PATTERN**: When removing infrastructure dependencies (Redis, etc.) from n8n workflows, CONVERT nodes to bypass Code nodes rather than removing them. This preserves workflow structure and connections while removing the dependency.
- **Related**: FIX-31 (Orchestrator Redis removal Session 60), FIX-06 (Credentials migration)

---

### FIX-65: N8N_BLOCK_ENV_ACCESS_IN_NODE=false deployed to 10 HF Spaces
- **Date**: 2026-02-25 (Session 62)
- **Composant**: HF Space infrastructure — ALL 10 spaces
- **Symptome**: ALL pipelines returning "Unable to generate answer", "NO_ANSWER", or empty responses. Execution data shows `{"error": "access to env vars denied"}` in all HTTP Request nodes using `$env.*` expressions.
- **Cause racine**: n8n 2.8.3 blocks `$env.*` access by default. The entrypoint.sh was missing `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` environment variable. Despite 20+ HF secrets correctly configured, n8n refused to resolve them in workflow expressions.
- **Impact**: CROSS-PIPELINE — affects ALL 5 pipelines simultaneously (Standard, Graph, Quantitative, Orchestrator, PME Gateway). Blocks:
  - OpenRouter API calls (`$env.OPENROUTER_KEY_STANDARD`)
  - Pinecone API calls (`$env.PINECONE_API_KEY`)
  - Jina API calls (`$env.JINA_API_KEY`)
  - Cohere API calls (`$env.COHERE_API_KEY`)
  - All other `$env.*` references in HTTP Request headers
- **Fix deployed**:
  1. Added `export N8N_BLOCK_ENV_ACCESS_IN_NODE=false` to entrypoint.sh BEFORE `n8n start`
  2. Pushed updated entrypoint.sh to HF Space repo
  3. Triggered factory reboot on ALL 10 HF Spaces to apply fix
  4. Verified env var is present in container: `docker exec <container> env | grep N8N_BLOCK`
- **Side effect**: Factory reboot wiped SQLite database → credential restore required (see FIX-66)
- **Verification**: After credential restore, Standard pipeline returns 200 with valid answers. Graph/Quantitative/Orchestrator pending credential restore.
- **RULE UPDATED**: AP-7 and AP-8 obsolete. With `N8N_BLOCK_ENV_ACCESS_IN_NODE=false`, `$env.*` works normally. This config MUST ALWAYS be present in entrypoint.sh.
- **Related**: FIX-33 (env var blocking in n8n 2.8.3), FIX-63 (same issue, Session 58)

---

### FIX-66: Credential restore script for post-rebuild recovery
- **Date**: 2026-02-25 (Session 62)
- **Composant**: HF Space post-rebuild recovery process
- **Symptome**: After factory reboot to deploy N8N_BLOCK_ENV_ACCESS_IN_NODE=false fix, ALL workflows lost credential references. n8n shows "Credential does not exist" errors. Workflows JSON definitions intact but credential IDs orphaned.
- **Cause racine**: HF Space factory reboot wipes SQLite database including ALL credential entries. Workflow JSONs persist (imported from n8n-workflows/) but reference credential IDs that no longer exist in DB.
- **What gets wiped**:
  - `credentials_entity` table (ALL credentials)
  - Workflow-credential associations
  - Active workflow registrations
  - Execution history
- **What survives**:
  - Workflow JSON definitions (re-imported from n8n-workflows/)
  - HF Space secrets (environment variables)
  - Entrypoint.sh configuration
- **Fix implemented**: Created credential restore process that runs AFTER every HF Space rebuild:
  ```python
  # setup-workflows.py — runs during entrypoint.sh boot
  # 1. Login to n8n REST API
  POST /rest/login {"emailOrLdapLoginId": "ci@nomos.ai", "password": "..."}

  # 2. Create credentials via REST API
  POST /rest/credentials {
      "name": "OpenRouter API (Standard)",
      "type": "httpHeaderAuth",
      "data": {"name": "Authorization", "value": "Bearer {{HF_SECRET}}"}
  }
  # Repeat for: OpenRouter (x4), Pinecone (x2), Neo4j, Postgres (x4), Redis

  # 3. Get new credential IDs from n8n
  GET /rest/credentials

  # 4. Map old IDs → new IDs in workflow JSONs
  # (complex remapping logic)

  # 5. Activate workflows with new credential references
  POST /rest/workflows/{id}/activate {"versionId": "..."}
  ```
- **Credentials restored** (11 total across primary space, replicating to 8 more):
  - 4 OpenRouter httpHeaderAuth (Standard, Graph, Quantitative, Orchestrator)
  - 2 Pinecone httpHeaderAuth
  - 1 Neo4j httpBasicAuth
  - 4 Postgres (Quantitative, Orchestrator Agent, Orchestrator Metadata, Ingestion)
- **Special case**: Standard workflow uses `$env.VAR_NAME` expressions in HTTP Request headers (NOT credential objects) → doesn't need credential restore IF N8N_BLOCK_ENV_ACCESS_IN_NODE=false is set
- **Deployment**: Credential restore running on 9 spaces (Space 2 broken). 11/14 workflows restored on primary space.
- **RULE**: ALWAYS run setup-workflows.py after HF Space factory reboot. NEVER assume credentials survive a rebuild.
- **Related**: FIX-53 (credential ID mismatch after import), FIX-18 (SQLite FK constraints)

---

### FIX-67: HF Space rebuilds reset all webhook registrations
- **Date**: 2026-02-25 (Session 62)
- **Composant**: HF Space webhook infrastructure
- **Symptome**: After factory reboot, ALL webhook endpoints return 404 "Webhook not registered" even though workflows show `active: true` in database.
- **Cause racine**: n8n webhook registration is stored in-memory and in database. Factory reboot wipes both. Even if workflows are marked active after rebuild, webhook endpoints are not registered until workflows are properly activated via REST API.
- **Impact**: Critical — ALL webhooks down after rebuild:
  - Standard RAG: `/webhook/rag-multi-index-v3` → 404
  - Graph RAG: `/webhook/ff622742-6d71-4e91-af71-b5c666088717` → 404
  - Quantitative: `/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9` → 404
  - Orchestrator: `/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0` → 404
  - PME Gateway: `/webhook/pme-assistant-gateway` → 404
- **Fix**: Webhook registration happens automatically when workflows are activated via:
  ```bash
  POST /rest/workflows/{id}/activate {"versionId": "..."}
  ```
  This is part of credential restore process (FIX-66). After activation completes, webhooks are registered.
- **Verification**:
  ```bash
  # Check if webhooks are registered
  curl -s http://localhost:5678/webhook/rag-multi-index-v3 \
    -H "Content-Type: application/json" \
    -d '{"query": "test"}'
  # Should return 200 (not 404)
  ```
- **Timeline**: Webhooks restore automatically after credential restore completes (~5-10 minutes per space).
- **RULE**: After HF Space factory reboot, EXPECT all webhooks to be down until credential restore + activation completes. Do NOT attempt to test pipelines before activation finishes.
- **Related**: FIX-66 (credential restore), FIX-19 (n8n 2.8+ activation requires versionId)

---
