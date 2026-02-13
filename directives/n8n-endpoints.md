# n8n API Endpoints & Reference Complete

> **Ce fichier est la reference unique** pour les scripts Python de test.
> Les scripts doivent s'y referer pour formater les requetes et utiliser les bons points d'entree.
> Derniere mise a jour : 2026-02-13 (session reorganisation)

---

## Configuration — Docker self-hosted (post-migration 2026-02-12)

```bash
export N8N_HOST="http://34.136.180.66:5678"
export N8N_API_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2M2ZhN2FjNS1lOTJkLTQ2MjAtOGZkYS05Zjg0MWI1Y2VjZjYiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiNzc0NzYyNmItNTNjYi00ZDU0LTkxYmItYjZkYmE1NjdmZGVmIiwiaWF0IjoxNzcwOTM4NDExfQ.77sRd0mK_ShypXUibu4GpKbyKFXTzCE9mLa7940nUAw"
```

---

## Format de Requete pour Scripts Python (REFERENCE)

### Format de body webhook (VERIFIE FONCTIONNEL)

```python
# Format qui FONCTIONNE — verifie le 2026-02-12 a 11:19:49 CET (Paris)
payload = {"question": "Your question here"}
# Content-Type: application/json
# Method: POST
```

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
    payload = json.dumps({"question": question}).encode()
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

## Workflow IDs — Docker self-hosted (verifie 2026-02-13)

### IDs actifs (n8n Docker sur 34.136.180.66:5678)
| Pipeline | Workflow ID | Verifie API |
|----------|-------------|-------------|
| Standard | `M12n4cmiVBoBusUe` | Oui (2026-02-13) |
| Graph | `Vxm4TDdOLdb7j3Jy` | Oui (2026-02-13) |
| Quantitative | `nQnAJyT06NTbEQ3y` | Oui (2026-02-13) |
| Orchestrator | `P1no6VZkNtnRdlBi` | Oui (2026-02-13) |

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
| Standard | `/webhook/rag-multi-index-v3` | 2026-02-12 | 11:19:49 CET |
| Graph | `/webhook/ff622742-6d71-4e91-af71-b5c666088717` | 2026-02-12 | 09:27:03 CET |
| Quantitative | `/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9` | 2026-02-12 | 11:11:36 CET |
| Orchestrator | `/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0` | 2026-02-10 | — |

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
