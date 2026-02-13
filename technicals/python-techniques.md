# Techniques Python, Limites & Contournements

> **Ce fichier DOIT être mis à jour** après chaque problème rencontré et sa solution.
> Dernière mise à jour : 2026-02-10

---

## Environnement

- Python 3.10+ (GCloud Shell) ou 3.11+ (Oracle Cloud)
- Pas de GPU disponible (embeddings locaux = CPU only)
- Proxy HTTP peut bloquer certaines connexions (Supabase, Neo4j)
- `pip install --user` si pas de sudo

---

## Librairies requises

```bash
pip install --user requests pinecone-client python-dotenv
# Optionnel pour embeddings locaux
pip install --user sentence-transformers torch
# Pour MCP servers
pip install --user mcp
```

---

## Limites connues et contournements

### 1. Proxy 403 sur Supabase/Neo4j

**Problème** : Depuis Claude Code (cloud), les requêtes directes vers Supabase et Neo4j retournent 403.

**Contournement** :
```python
# Au lieu de requêtes directes, passer par les webhooks n8n
# qui eux ont accès aux DB

# Mauvais (403) :
# requests.post("https://xxx.supabase.co/rest/v1/rpc/...", ...)

# Bon :
requests.post(f"{N8N_HOST}/webhook/3e0f8010-...", json={"question": query})
```

**Contournement alternatif** : Avec n8n self-hosted sur Oracle Cloud, les DB sont accessibles directement.

### 2. Rate limiting OpenRouter

**Problème** : 20 req/min, 50 req/jour (sans crédit), 1000/jour (avec $10+)

**Contournement** :
```python
import time

def call_with_retry(fn, max_retries=3, base_delay=2):
    for i in range(max_retries):
        try:
            return fn()
        except Exception as e:
            if "429" in str(e):
                time.sleep(base_delay * (2 ** i))
            else:
                raise
    raise Exception("Max retries exceeded")
```

### 3. urllib vs requests

**Problème** : `requests` pas toujours installé dans les environnements minimaux.

**Contournement** :
```python
# Toujours utiliser urllib.request comme fallback
import urllib.request, json

def http_get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())

def http_post(url, data, headers=None):
    h = {"Content-Type": "application/json"}
    h.update(headers or {})
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers=h)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())
```

### 4. Timeout sur les webhooks n8n

**Problème** : Les pipelines RAG peuvent prendre > 30s, causant des timeout côté client.

**Contournement** :
```python
# Augmenter le timeout urllib
with urllib.request.urlopen(req, timeout=120) as resp:
    ...

# Ou avec requests
response = requests.post(url, json=data, timeout=120)
```

### 5. JSON trop gros pour stdout

**Problème** : Les exécutions n8n avec données peuvent faire > 1MB.

**Contournement** :
```python
# Écrire dans un fichier au lieu d'afficher
with open(f"logs/executions/exec-{exec_id}.json", "w") as f:
    json.dump(exec_data, f, indent=2)

# Ou extraire seulement les données utiles
run_data = exec_data["data"]["resultData"]["runData"]
for node_name, node_runs in run_data.items():
    print(f"{node_name}: {len(node_runs)} runs")
    for run in node_runs:
        print(f"  Output keys: {list(run.get('data', {}).get('main', [[]])[0][0].get('json', {}).keys()) if run.get('data') else 'N/A'}")
```

### 6. Encodage UTF-8

**Problème** : Caractères spéciaux dans les réponses LLM.

**Contournement** :
```python
# Toujours ouvrir les fichiers en UTF-8
with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False)
```

---

## Patterns utiles

### Parallélisme avec ThreadPoolExecutor
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def test_pipeline(pipeline, question):
    resp = requests.post(ENDPOINTS[pipeline], json={"question": question}, timeout=120)
    return pipeline, resp.json()

with ThreadPoolExecutor(max_workers=4) as executor:
    futures = {executor.submit(test_pipeline, p, q): (p, q) for p, q in tasks}
    for future in as_completed(futures):
        pipeline, result = future.result()
        print(f"{pipeline}: {result}")
```

### Extraction node-par-node d'une exécution
```python
def extract_node_io(exec_data):
    """Extrait input/output de chaque nœud d'une exécution n8n."""
    run_data = exec_data.get("data", {}).get("resultData", {}).get("runData", {})
    nodes = {}
    for name, runs in run_data.items():
        for run in runs:
            data = run.get("data", {}).get("main", [[]])
            output = data[0] if data and data[0] else []
            nodes[name] = {
                "startTime": run.get("startTime"),
                "executionTime": run.get("executionTime"),
                "output_count": len(output),
                "first_output": output[0].get("json", {}) if output else {},
                "error": run.get("error"),
            }
    return nodes
```

---

## Erreurs fréquentes

| Erreur | Cause | Solution |
|--------|-------|----------|
| `ConnectionError: 403` | Proxy bloquant | Passer par n8n webhook |
| `JSONDecodeError` | Réponse vide ou HTML | Vérifier le status code d'abord |
| `TimeoutError` | Pipeline lent | Augmenter timeout à 120s |
| `KeyError: 'data'` | Exécution sans `includeData` | Ajouter `?includeData=true` |
| `ModuleNotFoundError` | Package manquant | `pip install --user <pkg>` |
| `SSL: CERTIFICATE_VERIFY_FAILED` | Env minimal | `import ssl; ssl._create_default_https_context = ssl._create_unverified_context` |
