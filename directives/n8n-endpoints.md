# n8n API Endpoints & Reference Complete

> Last updated: 2026-02-25T11:30:00+00:00

> **Ce fichier est la reference unique** pour les scripts Python de test.
> Les scripts doivent s'y referer pour formater les requetes et utiliser les bons points d'entree.
> Derniere mise a jour : 2026-02-25 (10 HF Space cluster deployed)

---

## Configuration — 10 HF Space Cluster (deployed 2026-02-25)

```bash
# 10 HF Spaces deployed for distributed load
# Space 1-10 URLs in .env.local
source .env.local  # charge N8N_HOST, N8N_API_KEY, N8N_HOST_1 through N8N_HOST_10
```

### 10 HF Space Endpoints
| Space | URL | Account | Status |
|-------|-----|---------|--------|
| Space 1 | https://lbjlincoln-nomos-rag-engine.hf.space | LBJLincoln | ACTIVE |
| Space 2 | https://lbjlincoln26-nomos-rag-engine-2.hf.space | LBJLincoln26 | ACTIVE |
| Space 3 | https://lbjlincoln-nomos-rag-engine-3.hf.space | LBJLincoln | ACTIVE |
| Space 4 | https://lbjlincoln26-nomos-rag-engine-4.hf.space | LBJLincoln26 | ACTIVE |
| Space 5 | https://lbjlincoln-nomos-rag-engine-5.hf.space | LBJLincoln | ACTIVE |
| Space 6 | https://lbjlincoln26-nomos-rag-engine-6.hf.space | LBJLincoln26 | ACTIVE |
| Space 7 | https://lbjlincoln-nomos-rag-engine-7.hf.space | LBJLincoln | ACTIVE |
| Space 8 | https://lbjlincoln26-nomos-rag-engine-8.hf.space | LBJLincoln26 | ACTIVE |
| Space 9 | https://lbjlincoln-nomos-rag-engine-9.hf.space | LBJLincoln | ACTIVE |
| Space 10 | https://lbjlincoln26-nomos-rag-engine-10.hf.space | LBJLincoln26 | ACTIVE |

> **IMPORTANT** : Load balancing across 10 spaces. Use round-robin or least-loaded strategy.

---

## Format de Requete pour Scripts Python (REFERENCE)

### Format de body webhook (VERIFIE FONCTIONNEL — Session 25)

```python
# Format qui FONCTIONNE — verifie le 2026-02-19 (Session 25)
# ATTENTION : le field name est "query" (PAS "question")
payload = {"query": "Your question here"}
# Content-Type: application/json
# Method: POST
```

> **PIEGE RECURRENT** : Utiliser `question` au lieu de `query` provoque une VALIDATION_ERROR.
> Toujours utiliser `query` pour les 4 pipelines.

### Timestamps — Fuseau horaire Paris (CET/CEST)

| Champ | Format | Exemple |
|-------|--------|---------|
| `startedAt` (n8n API) | ISO 8601 UTC | `2026-02-12T10:19:49.123Z` |
| Conversion Paris (CET = UTC+1) | +1h | `2026-02-12T11:19:49.123 CET` |
| Conversion Paris (CEST = UTC+2) | +2h | (ete uniquement) |
| Format pour logs | ISO local | `2026-02-12T11-19-49` |

### Pattern Python pour appeler un webhook

```python
import urllib.request, json
from datetime import datetime, timezone, timedelta

N8N_HOST = "http://34.136.180.66:5678"
PARIS_TZ = timezone(timedelta(hours=1))  # CET (hiver), +2 pour CEST (ete)

def call_webhook(path, question, timeout=120):
    """Appel webhook n8n avec timestamp Paris."""
    url = f"{N8N_HOST}{path}"
    payload = json.dumps({"query": question}).encode()
    req = urllib.request.Request(url, data=payload, method="POST",
        headers={"Content-Type": "application/json"})
    timestamp_paris = datetime.now(PARIS_TZ).strftime("%Y-%m-%dT%H:%M:%S")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read()), timestamp_paris
```

---

## REST API Endpoints (tous testés et fonctionnels)

### Workflows

```bash
# Lister tous les workflows
curl -s "$N8N_HOST/api/v1/workflows" -H "X-N8N-API-KEY: $N8N_API_KEY" | python3 -m json.tool

# Récupérer un workflow spécifique
curl -s "$N8N_HOST/api/v1/workflows/<WF_ID>" -H "X-N8N-API-KEY: $N8N_API_KEY"

# Mettre à jour un workflow (PUT)
curl -s -X PUT "$N8N_HOST/api/v1/workflows/<WF_ID>" \
  -H "X-N8N-API-KEY: $N8N_API_KEY" \
  -H "Content-Type: application/json" \
  -d @workflow.json

# Activer un workflow
curl -s -X POST "$N8N_HOST/api/v1/workflows/<WF_ID>/activate" \
  -H "X-N8N-API-KEY: $N8N_API_KEY"

# Désactiver un workflow
curl -s -X POST "$N8N_HOST/api/v1/workflows/<WF_ID>/deactivate" \
  -H "X-N8N-API-KEY: $N8N_API_KEY"
```

### Exécutions

```bash
# Lister les dernières exécutions
curl -s "$N8N_HOST/api/v1/executions?limit=10" -H "X-N8N-API-KEY: $N8N_API_KEY"

# Récupérer une exécution avec données complètes (CRITIQUE pour l'analyse)
curl -s "$N8N_HOST/api/v1/executions/<EXEC_ID>?includeData=true" \
  -H "X-N8N-API-KEY: $N8N_API_KEY"

# Filtrer par workflow
curl -s "$N8N_HOST/api/v1/executions?workflowId=<WF_ID>&limit=5" \
  -H "X-N8N-API-KEY: $N8N_API_KEY"

# Filtrer par status
curl -s "$N8N_HOST/api/v1/executions?status=error&limit=10" \
  -H "X-N8N-API-KEY: $N8N_API_KEY"
```

### Variables

```bash
# Lister les variables
curl -s "$N8N_HOST/api/v1/variables" -H "X-N8N-API-KEY: $N8N_API_KEY"

# Créer/mettre à jour une variable
curl -s -X POST "$N8N_HOST/api/v1/variables" \
  -H "X-N8N-API-KEY: $N8N_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"key": "EMBEDDING_MODEL", "value": "jina-embeddings-v3"}'
```

---

## Webhooks (endpoints de test)

```bash
# Standard RAG
curl -s -X POST "$N8N_HOST/webhook/rag-multi-index-v3" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the capital of Japan?"}'

# Graph RAG
curl -s -X POST "$N8N_HOST/webhook/ff622742-6d71-4e91-af71-b5c666088717" \
  -H "Content-Type: application/json" \
  -d '{"query": "Who founded Microsoft?"}'

# Quantitative RAG
curl -s -X POST "$N8N_HOST/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9" \
  -H "Content-Type: application/json" \
  -d '{"query": "What was Apple revenue in 2023?"}'

# Orchestrator (route vers les 3)
curl -s -X POST "$N8N_HOST/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the capital of Japan?"}'
```

---

## Pattern Python pour modifier un nœud

```python
import urllib.request, json, os

N8N_HOST = os.environ["N8N_HOST"]
API_KEY = os.environ["N8N_API_KEY"]

def n8n_api(method, path, data=None):
    url = f"{N8N_HOST}{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method,
        headers={"X-N8N-API-KEY": API_KEY, "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

# 1. Télécharger le workflow
wf = n8n_api("GET", f"/api/v1/workflows/{WF_ID}")

# 2. Trouver et modifier le nœud cible
for node in wf["nodes"]:
    if node["name"] == "Target Node Name":
        node["parameters"]["jsCode"] = NEW_CODE
        break

# 3. Nettoyer le payload (n8n rejette certains champs en PUT)
ALLOWED_SETTINGS = {"executionOrder", "callerPolicy", "saveManualExecutions", "saveExecutionProgress"}
clean = {k: v for k, v in wf.items() if k not in ("id", "createdAt", "updatedAt", "active")}
if "settings" in clean:
    clean["settings"] = {k: v for k, v in clean["settings"].items() if k in ALLOWED_SETTINGS}

# 4. Déployer
n8n_api("POST", f"/api/v1/workflows/{WF_ID}/deactivate")
n8n_api("PUT", f"/api/v1/workflows/{WF_ID}", clean)
n8n_api("POST", f"/api/v1/workflows/{WF_ID}/activate")
```

---

## Pièges connus

| Piège | Solution |
|-------|----------|
| PUT workflow rejette `id`, `createdAt`, `updatedAt` | Filtrer ces champs du payload |
| PUT workflow rejette certains `settings` | Ne garder que `ALLOWED_SETTINGS` |
| `active` dans le body cause conflit | Le retirer du payload PUT |
| Timeout webhook (30s par défaut) | Configurer `responseTimeoutMs` dans le nœud Webhook |
| Variables n8n pas visibles dans le code | Utiliser `$vars.NOM_VARIABLE` dans les expressions |
| Exécution sans données | Ajouter `?includeData=true` au GET execution |
| `$env.X` bloqué en Docker self-hosted | Remplacer par valeurs hardcodées dans les nœuds |
| Credentials n8n inexistantes après migration | **RESOLU 15-fev** : Postgres `USU8ngVzsUbED3mn` + Redis `CWih07lwPxfwFeY6` creees, 12/13 workflows remappes |
| `require('crypto')` bloqué dans Code nodes | Utiliser fonction hash custom (bitwise) |
| Pinecone dim 1024 (Jina) vs 1536 (ancien) | Utiliser index `sota-rag-jina-1024` (primary) |
| Jina embedding JSON trailing comma | Verifier pas de trailing comma dans body JSON apres migration |
| Tests parallèles → 503 n8n overload | Toujours tester les pipelines séquentiellement |
| Free models OpenRouter changent souvent | Vérifier disponibilité avant de fixer le modèle |
| Neo4j URL `bolt://` | `skip_graph=true` silencieux — Graph renvoie réponse vide sans erreur | Changer URL → `https://...neo4j.io/db/neo4j/query/v2` |
| Workflow live vide (0 nodes) | HTTP 500 immédiat sur tout appel webhook | Re-pousser depuis `n8n/live/` via PUT API |
| PUT 400 "additional properties" | `isArchived`, `versionCounter` rejetés par l'API | Payload minimal : `name` + `nodes` + `connections` + `settings` + `staticData` |
| `N8N_RUNNERS_ENABLED` (CI) | `$getWorkflowStaticData` ne persiste pas entre runs | Ajouter `N8N_RUNNERS_ENABLED=false` dans docker-compose |

---

## Workflow IDs — Docker self-hosted (verifie 2026-02-13)

### IDs actifs (n8n Docker sur 34.136.180.66:5678)
| Pipeline | Workflow ID | Verifie API |
|----------|-------------|-------------|
| Standard | `TmgyRP20N4JFd9CB` | Oui (2026-02-14) |
| Graph | `6257AfT1l4FMC6lY` | Oui (2026-02-14) |
| Quantitative | `e465W7V9Q8uK6zJE` | Oui (2026-02-14) |
| Orchestrator | `aGsYnJY9nNCaTM82` | Oui (2026-02-14) |

### IDs anciens (n8n Cloud — OBSOLETE, ne plus utiliser)
| Pipeline | Workflow ID | Notes |
|----------|-------------|-------|
| Standard | `IgQeo5svGlIAPkBc` / `LnTqRX4LZlI009Ks-3Jnp` | Cloud, obsolete |
| Graph | `95x2BBAbJlLWZtWEJn6rb` | Cloud, obsolete |
| Quantitative | `E19NZG9WfM7FNsxr` | Cloud, obsolete |
| Orchestrator | `ALd4gOEqiKL5KR1p` | Cloud, obsolete |

> **IMPORTANT** : Toujours utiliser les IDs Docker (premiere table).
> Mapping complet des 13 workflows : `n8n/docker-workflow-ids.json`.

---

## Webhook Paths (VERIFIE FONCTIONNEL)

| Pipeline | Path | Dernier test OK | Timestamp Paris |
|----------|------|-----------------|-----------------|
| Standard | `/webhook/rag-multi-index-v3` | 2026-02-16 | 19:19 CET |
| Graph | `/webhook/ff622742-6d71-4e91-af71-b5c666088717` | 2026-02-16 | 19:21 CET |
| Quantitative | `/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9` | 2026-02-16 | 19:18 CET |
| Orchestrator | `/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0` | 2026-02-16 | — |

---

## Chemins des scripts de test (POST-REORGANISATION)

| Script | Chemin | Usage |
|--------|--------|-------|
| Quick test (1-5q) | `eval/quick-test.py` | Smoke test |
| Iterative eval | `eval/iterative-eval.py` | Progressif 5→10→50 |
| Parallel eval (200q) | `eval/run-eval-parallel.py` | Full eval |
| Node analyzer | `eval/node-analyzer.py` | Analyse node-par-node |
| N8n execution analyzer | `scripts/analyze_n8n_executions.py` | Analyse brute complete |
| Status generator | `eval/generate_status.py` | Regenere status.json |
| Phase gates | `eval/phase_gates.py` | Verification gates |
