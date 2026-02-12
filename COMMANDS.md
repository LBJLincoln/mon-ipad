# Commandes Essentielles - SOTA 2026

> VM: Google Cloud (34.136.180.66)  
> Dernière mise à jour: 2026-02-12

---

## 🚀 Démarrage Rapide

```bash
# 1. Se connecter à la VM
ssh termius@34.136.180.66

# 2. Lancer la session (charge tout automatiquement)
source /home/termius/mon-ipad/start-session.sh

# 3. Vérifier le statut
cat docs/status.json
```

---

## 🐳 n8n Docker

### Statut & Contrôle
```bash
n8n-status              # Voir les conteneurs actifs
n8n-logs                # Voir les logs en temps réel
n8n-restart             # Redémarrer n8n
```

### Manuellement
```bash
cd ~/n8n
docker-compose ps       # Statut
docker-compose logs -f  # Logs
docker-compose up -d    # Démarrer
docker-compose down     # Arrêter
```

### URLs
- **Local**: http://localhost:5678
- **Externe**: http://34.136.180.66:5678 (⚠️ firewall GCP requis)
- **Login**: admin / SotaRAG2026!

### Setup Initial (une seule fois)
```bash
# 1. Créer un compte sur http://localhost:5678
# 2. Settings (roue dentée) > API > Create API Key
# 3. Copier la clé et l'exporter:
export N8N_API_KEY="n8n_api_<votre-cle>"

# 4. Importer tous les workflows
bash /home/termius/mon-ipad/scripts/setup-n8n-docker.sh
```

---

## 🔗 MCP Servers

### Vérification
```bash
mcp-status              # Vérifier tous les MCP
```

### Manuellement
```bash
# Neo4j MCP
neo4j-mcp --version

# n8n MCP
N8N_API_URL=http://localhost:5678/api/v1 N8N_API_KEY=$N8N_API_KEY n8n-mcp-server

# Jina Embeddings MCP (nécessite le venv)
source /home/termius/mon-ipad/.venv/bin/activate
python3 /home/termius/mon-ipad/mcp/jina-embeddings-server.py

# Hugging Face MCP
source /home/termius/mon-ipad/.venv/bin/activate
python3 /home/termius/mcp-servers/custom/huggingface-mcp-server.py

# Cohere MCP
source /home/termius/mon-ipad/.venv/bin/activate
python3 /home/termius/mcp-servers/custom/cohere-mcp-server.py

# Pinecone MCP (via npx)
npx -y @pinecone-database/mcp
```

---

## ⚡ Skills CLI

### Liste
```bash
skills-list             # Lister tous les skills
```

### Disponibles
| Skill | Fichier | Description |
|-------|---------|-------------|
| mcp-manager | `~/skills/mcp-manager.sh` | Gestion des serveurs MCP |
| git-advanced | `~/skills/git-advanced.js` | Opérations Git avancées |
| docker-manager | `~/skills/docker-manager.js` | Gestion Docker |
| web-search-fetch | `~/skills/web-search-fetch.js` | Recherche web |

### Usage
```bash
# MCP Manager
bash ~/skills/mcp-manager.sh status
bash ~/skills/mcp-manager.sh start
bash ~/skills/mcp-manager.sh stop

# Autres skills (modules Node.js)
node ~/skills/git-advanced.js
node ~/skills/docker-manager.js
node ~/skills/web-search-fetch.js
```

---

## 🧪 Tests & Évaluation

### Tests Rapides
```bash
sota-test               # Test 1 question par pipeline
sota-test-5             # Test 5 questions
```

### Manuellement
```bash
cd /home/termius/mon-ipad

# Test 1 question
python3 eval/quick-test.py --questions 1

# Test 5 questions
python3 eval/quick-test.py --questions 5

# Test 10 questions
python3 eval/fast-iter.py --label "test-$(date +%Y%m%d)"

# Test complet (200 questions)
python3 eval/run-eval-parallel.py --reset --label "full-$(date +%Y%m%d)"
```

---

## 📦 Workflows

### Sync depuis n8n
```bash
python3 workflows/sync.py
```

### Import vers n8n
```bash
# 1. Exporter la clé API
export N8N_API_KEY="votre-cle"
export N8N_HOST="http://localhost:5678"

# 2. Importer tous les workflows
for wf in workflows/live/*.json; do
  curl -s -X POST "$N8N_HOST/api/v1/workflows" \
    -H "X-N8N-API-KEY: $N8N_API_KEY" \
    -H "Content-Type: application/json" \
    -d @"$wf"
done
```

---

## 📊 Status & Monitoring

```bash
sota-status             # Voir le status du projet
cat docs/status.json    # Version compacte
```

---

## 🔧 Variables d'Environnement

### Chargement automatique
```bash
source /home/termius/mon-ipad/.env.local
```

### Principales variables
```bash
export N8N_HOST="http://localhost:5678"
export PINECONE_API_KEY="..."
export OPENROUTER_API_KEY="..."
export COHERE_API_KEY="..."
export JINA_API_KEY="..."
export NEO4J_PASSWORD="..."
export HF_TOKEN="..."
export SUPABASE_API_KEY="..."
```

---

## 🔥 Firewall GCP (si besoin)

```bash
# Ouvrir le port 5678 pour n8n
gcloud compute firewall-rules create allow-n8n \
  --allow tcp:5678 \
  --source-ranges 0.0.0.0/0 \
  --description "Allow n8n access"

# Vérifier les règles
gcloud compute firewall-rules list
```

---

## 📁 Fichiers Importants

| Fichier | Description |
|---------|-------------|
| `CLAUDE.md` | Guide de démarrage session |
| `start-session.sh` | Script d'initialisation complet |
| `docs/status.json` | Status live du projet |
| `docs/n8n-docker-workflow-ids.json` | IDs des workflows n8n |
| `.env.local` | Credentials (non commité) |
| `COMMANDS.md` | Ce fichier |

---

## 🆘 Dépannage

### n8n ne démarre pas
```bash
cd ~/n8n
docker-compose down
docker-compose up -d
docker-compose logs -f
```

### MCP ne répondent pas
```bash
# Vérifier les installations
which neo4j-mcp
which n8n-mcp-server
ls ~/mcp-servers/custom/

# Vérifier le venv Python
source /home/termius/mon-ipad/.venv/bin/activate
python3 -c "from mcp.server import Server; print('OK')"
```

### Permissions Docker
```bash
sudo usermod -aG docker $USER
# Puis reconnexion SSH
```

---

*Généré automatiquement le 2026-02-12*
