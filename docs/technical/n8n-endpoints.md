# n8n API Endpoints & Commandes Fonctionnelles

> **Ce fichier DOIT être mis à jour** après chaque découverte d'endpoint ou technique qui marche.
> Dernière mise à jour : 2026-02-10

---

## Configuration

```bash
export N8N_HOST="https://amoret.app.n8n.cloud"  # Changer après migration self-hosted
export N8N_API_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyMTU3NjdlMC05NThhLTRjNzQtYTY3YS1lMzM1ODA3ZWJhNjQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY5MDQ2NTExLCJleHAiOjE3NzE2Mjg0MDB9.fyOBVwb32HlzwQhSxCxoKsmMlYcxppTFGbj6S01AX2A"
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
  -d '{"question": "What is the capital of Japan?"}'

# Graph RAG
curl -s -X POST "$N8N_HOST/webhook/ff622742-6d71-4e91-af71-b5c666088717" \
  -H "Content-Type: application/json" \
  -d '{"question": "Who founded Microsoft?"}'

# Quantitative RAG
curl -s -X POST "$N8N_HOST/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9" \
  -H "Content-Type: application/json" \
  -d '{"question": "What was Apple revenue in 2023?"}'

# Orchestrator (route vers les 3)
curl -s -X POST "$N8N_HOST/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the capital of Japan?"}'
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

---

## Workflow IDs actuels

| Pipeline | Workflow ID | Notes |
|----------|-------------|-------|
| Standard | `LnTqRX4LZlI009Ks-3Jnp` | V3.4 |
| Graph | `95x2BBAbJlLWZtWEJn6rb` | V3.3 |
| Quantitative | `LjUz8fxQZ03G9IsU` | V2.0 |
| Orchestrator | `FZxkpldDbgV8AD_cg7IWG` | V10.1 |

> **IMPORTANT** : Ces IDs changeront après migration self-hosted. Mettre à jour ce fichier.
