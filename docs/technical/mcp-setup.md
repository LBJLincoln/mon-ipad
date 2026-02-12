# MCP Servers - Configuration Complète 2026

> **Dernière mise à jour** : 2026-02-12  
> **Version** : SOTA 2026 Multi-RAG Orchestrator

Ce document fournit les scripts exacts pour installer et configurer les MCP servers pour notre stack technique : Neo4j, Supabase, n8n, Pinecone, et plus.

---

## 🚀 Installation Rapide (Script Automatique)

```bash
#!/bin/bash
# mcp-install.sh - Script d'installation automatique des MCP servers
# Usage : chmod +x mcp-install.sh && ./mcp-install.sh

set -e

echo "=== Installation des MCP Servers pour SOTA 2026 ==="

# Vérifier Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js n'est pas installé. Installation..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y nodejs
fi

NODE_VERSION=$(node --version | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
    echo "❌ Node.js 18+ requis. Version actuelle : $(node --version)"
    exit 1
fi

echo "✅ Node.js $(node --version) détecté"

# Créer le répertoire MCP
mkdir -p ~/mcp-servers
cd ~/mcp-servers

# === MCP NEO4J (Officiel) ===
echo "📦 Installation MCP Neo4j..."
NEO4J_MCP_VERSION="1.0.0"  # Vérifier la dernière version sur https://github.com/neo4j/mcp/releases
curl -L -o neo4j-mcp.tar.gz "https://github.com/neo4j/mcp/releases/download/v${NEO4J_MCP_VERSION}/neo4j-mcp_${NEO4J_MCP_VERSION}_linux_amd64.tar.gz"
tar -xzf neo4j-mcp.tar.gz
chmod +x neo4j-mcp
sudo mv neo4j-mcp /usr/local/bin/
rm neo4j-mcp.tar.gz
echo "✅ MCP Neo4j installé"

# === MCP N8N ===
echo "📦 Installation MCP n8n..."
npm install -g @leonardsellem/n8n-mcp-server
echo "✅ MCP n8n installé"

# === MCP PINECONE ===
echo "📦 Installation MCP Pinecone..."
# NPX - pas besoin d'installation globale, utilisé via npx
echo "✅ MCP Pinecone disponible via npx"

# === MCP SUPABASE ===
echo "📦 Configuration MCP Supabase..."
# Supabase utilise une URL HTTP - configuration uniquement
echo "✅ MCP Supabase configuré (mode HTTP)"

echo ""
echo "=== Installation terminée ==="
echo "Prochaine étape : Configurer les variables d'environnement"
echo "Voir la section 'Configuration' ci-dessous"


---

## 📋 Configuration Claude Desktop / CLI

### Fichier de configuration

**Linux/macOS** : `~/.config/claude/config.json`  
**Windows** : `%APPDATA%\Claude\config.json`

### Configuration Complète

```json
{
  "mcpServers": {
    "neo4j": {
      "command": "neo4j-mcp",
      "env": {
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USERNAME": "neo4j",
        "NEO4J_PASSWORD": "votre_mot_de_passe_neo4j",
        "NEO4J_DATABASE": "neo4j",
        "NEO4J_READ_ONLY": "false",
        "NEO4J_TELEMETRY": "true",
        "NEO4J_TRANSPORT_MODE": "stdio"
      }
    },
    "supabase": {
      "type": "http",
      "url": "https://mcp.supabase.com/mcp?project_ref=votre-project-ref&read_only=false&features=database,docs,debugging,development"
    },
    "pinecone": {
      "command": "npx",
      "args": ["-y", "@pinecone-database/mcp"],
      "env": {
        "PINECONE_API_KEY": "votre_cle_pinecone"
      }
    },
    "n8n": {
      "command": "n8n-mcp-server",
      "env": {
        "N8N_API_URL": "https://amoret.app.n8n.cloud/api/v1",
        "N8N_API_KEY": "votre_cle_api_n8n",
        "N8N_WEBHOOK_USERNAME": "",
        "N8N_WEBHOOK_PASSWORD": "",
        "DEBUG": "false"
      }
    }
  }
}
```

---

## 🔧 Configuration par Service

### 1. Neo4j MCP (Officiel)

**Repo** : https://github.com/neo4j/mcp  
**Docs** : https://neo4j.com/developer/genai-ecosystem/model-context-protocol-mcp/

#### Installation manuelle

```bash
# Télécharger la dernière version
VERSION=$(curl -s https://api.github.com/repos/neo4j/mcp/releases/latest | grep '"tag_name":' | sed -E 's/.*"v([^"]+)".*/\1/')
curl -L -o neo4j-mcp.tar.gz "https://github.com/neo4j/mcp/releases/download/v${VERSION}/neo4j-mcp_${VERSION}_linux_amd64.tar.gz"

# Extraire et installer
tar -xzf neo4j-mcp.tar.gz
chmod +x neo4j-mcp
sudo mv neo4j-mcp /usr/local/bin/

# Vérifier l'installation
neo4j-mcp --version
```

#### Variables d'environnement

| Variable | Description | Défaut |
|----------|-------------|--------|
| `NEO4J_URI` | URI de connexion Neo4j | `bolt://localhost:7687` |
| `NEO4J_USERNAME` | Nom d'utilisateur | `neo4j` |
| `NEO4J_PASSWORD` | Mot de passe | - |
| `NEO4J_DATABASE` | Base de données | `neo4j` |
| `NEO4J_READ_ONLY` | Mode lecture seule | `false` |
| `NEO4J_TELEMETRY` | Télémétrie activée | `true` |
| `NEO4J_TRANSPORT_MODE` | Mode transport | `stdio` |

#### Outils disponibles

- `get-schema` : Obtenir le schéma de la base
- `execute-read` : Exécuter une requête Cypher en lecture
- `execute-write` : Exécuter une requête Cypher en écriture
- `list-gds-procedures` : Lister les procédures GDS

---

### 2. Supabase MCP (Officiel)

**Repo** : https://github.com/supabase-community/supabase-mcp  
**Docs** : https://supabase.com/docs/guides/ai/mcp

#### Configuration

```bash
# Obtenir le project_ref depuis les paramètres du projet Supabase
PROJECT_REF="votre-project-ref"  # Ex: abcdefghijklmnopqrst

# Mode lecture seule (recommandé par défaut)
SUPABASE_MCP_URL="https://mcp.supabase.com/mcp?project_ref=${PROJECT_REF}&read_only=true"

# Mode lecture/écriture
SUPABASE_MCP_URL_RW="https://mcp.supabase.com/mcp?project_ref=${PROJECT_REF}&read_only=false"
```

#### Feature Groups

| Feature | Description |
|---------|-------------|
| `account` | Gestion des projets et organisations |
| `docs` | Recherche dans la documentation |
| `database` | Opérations sur la base de données |
| `debugging` | Logs et advisors |
| `development` | URLs, clés API, types TypeScript |
| `functions` | Edge Functions |
| `storage` | Gestion du stockage |
| `branching` | Gestion des branches |

#### Outils disponibles

- `list_tables` : Lister les tables
- `execute_sql` : Exécuter du SQL
- `apply_migration` : Appliquer une migration
- `get_logs` : Obtenir les logs
- `search_docs` : Rechercher dans la doc

---

### 3. Pinecone MCP (Officiel)

**Repo** : https://github.com/pinecone-io/pinecone-mcp

#### Installation

```bash
# Pas d'installation nécessaire - utilisé via npx
# Nécessite Node.js 18+

# Vérifier la disponibilité
npx -y @pinecone-database/mcp --help
```

#### Configuration

```json
{
  "mcpServers": {
    "pinecone": {
      "command": "npx",
      "args": ["-y", "@pinecone-database/mcp"],
      "env": {
        "PINECONE_API_KEY": "pcsk_..."
      }
    }
  }
}
```

#### Outils disponibles

- `search-docs` : Rechercher dans la documentation Pinecone
- `list-indexes` : Lister les indexes
- `describe-index` : Décrire un index
- `describe-index-stats` : Statistiques d'un index
- `create-index-for-model` : Créer un index avec modèle intégré
- `upsert-records` : Insérer/mettre à jour des enregistrements
- `search-records` : Rechercher des enregistrements
- `cascading-search` : Recherche en cascade
- `rerank-documents` : Re-ranker des documents

---

### 4. n8n MCP (Communauté)

**Repo** : https://github.com/leonardsellem/n8n-mcp-server

#### Installation

```bash
# Installation globale via npm
npm install -g @leonardsellem/n8n-mcp-server

# Ou depuis Docker
docker pull leonardsellem/n8n-mcp-server
```

#### Variables d'environnement

| Variable | Description | Requis |
|----------|-------------|--------|
| `N8N_API_URL` | URL de l'API n8n (avec /api/v1) | ✅ |
| `N8N_API_KEY` | Clé API n8n | ✅ |
| `N8N_WEBHOOK_USERNAME` | Username webhook (optionnel) | ❌ |
| `N8N_WEBHOOK_PASSWORD` | Password webhook (optionnel) | ❌ |
| `DEBUG` | Mode debug | ❌ |

#### Configuration pour n8n Cloud

```json
{
  "mcpServers": {
    "n8n-cloud": {
      "command": "n8n-mcp-server",
      "env": {
        "N8N_API_URL": "https://amoret.app.n8n.cloud/api/v1",
        "N8N_API_KEY": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "DEBUG": "false"
      }
    }
  }
}
```

#### Outils disponibles

- `workflow_list` : Lister les workflows
- `workflow_get` : Obtenir un workflow
- `workflow_create` : Créer un workflow
- `workflow_update` : Mettre à jour un workflow
- `workflow_delete` : Supprimer un workflow
- `workflow_activate` : Activer un workflow
- `workflow_deactivate` : Désactiver un workflow
- `execution_list` : Lister les exécutions
- `execution_get` : Obtenir une exécution
- `run_webhook` : Exécuter un workflow via webhook

---

## 🔌 Mode HTTP (Alternative au STDIO)

Pour les environnements où STDIO n'est pas pratique (serveurs, CI/CD), certains MCP supportent le mode HTTP.

### Neo4j MCP en mode HTTP

```bash
# Démarrer le serveur HTTP
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_TRANSPORT_MODE="http"
export NEO4J_MCP_HTTP_PORT="8080"
neo4j-mcp

# Le serveur écoute sur http://localhost:8080
```

Configuration Claude :

```json
{
  "mcpServers": {
    "neo4j-http": {
      "type": "http",
      "url": "http://localhost:8080"
    }
  }
}
```

---

## 🧪 Scripts de Test

### Test Neo4j

```bash
#!/bin/bash
# test-neo4j-mcp.sh

echo "=== Test MCP Neo4j ==="

export NEO4J_URI="${NEO4J_URI:-bolt://localhost:7687}"
export NEO4J_USERNAME="${NEO4J_USERNAME:-neo4j}"
export NEO4J_PASSWORD="${NEO4J_PASSWORD}"

if [ -z "$NEO4J_PASSWORD" ]; then
    echo "❌ NEO4J_PASSWORD non défini"
    exit 1
fi

# Test de connexion
neo4j-mcp --neo4j-uri "$NEO4J_URI" --neo4j-username "$NEO4J_USERNAME" --neo4j-password "$NEO4J_PASSWORD" --help
echo "✅ MCP Neo4j fonctionnel"
```

### Test n8n

```bash
#!/bin/bash
# test-n8n-mcp.sh

echo "=== Test MCP n8n ==="

export N8N_API_URL="${N8N_API_URL:-https://amoret.app.n8n.cloud/api/v1}"
export N8N_API_KEY="${N8N_API_KEY}"

if [ -z "$N8N_API_KEY" ]; then
    echo "❌ N8N_API_KEY non défini"
    exit 1
fi

# Vérifier que le serveur démarre
which n8n-mcp-server
echo "✅ MCP n8n installé"
```

### Test Pinecone

```bash
#!/bin/bash
# test-pinecone-mcp.sh

echo "=== Test MCP Pinecone ==="

export PINECONE_API_KEY="${PINECONE_API_KEY}"

if [ -z "$PINECONE_API_KEY" ]; then
    echo "❌ PINECONE_API_KEY non défini"
    exit 1
fi

# Test via npx
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | npx -y @pinecone-database/mcp
echo "✅ MCP Pinecone fonctionnel"
```

---

## 🐛 Dépannage

### Problème : "command not found: neo4j-mcp"

```bash
# Vérifier que /usr/local/bin est dans le PATH
echo $PATH | grep /usr/local/bin

# Si non, ajouter au .bashrc ou .zshrc
export PATH="/usr/local/bin:$PATH"
```

### Problème : "Invalid API key" (Pinecone)

```bash
# Vérifier la clé API
export PINECONE_API_KEY="votre_cle"
echo $PINECONE_API_KEY | wc -c  # Devrait afficher ~60 caractères

# Tester la clé
curl -H "Api-Key: $PINECONE_API_KEY" https://api.pinecone.io/indexes
```

### Problème : "Cannot find module" (n8n MCP)

```bash
# Réinstaller le module
npm uninstall -g @leonardsellem/n8n-mcp-server
npm install -g @leonardsellem/n8n-mcp-server

# Vérifier l'installation
which n8n-mcp-server
n8n-mcp-server --version
```

### Problème : Supabase MCP ne répond pas

```bash
# Vérifier l'URL
curl -I "https://mcp.supabase.com/mcp?project_ref=votre-project-ref"

# Vérifier les permissions du projet dans Supabase Dashboard
```

---

## 📚 Références

| Service | Repo | Documentation | Statut |
|---------|------|---------------|--------|
| **Neo4j** | [neo4j/mcp](https://github.com/neo4j/mcp) | [Docs](https://neo4j.com/developer/genai-ecosystem/model-context-protocol-mcp/) | ✅ Officiel |
| **Supabase** | [supabase-community/supabase-mcp](https://github.com/supabase-community/supabase-mcp) | [Docs](https://supabase.com/docs/guides/ai/mcp) | ✅ Officiel |
| **Pinecone** | [pinecone-io/pinecone-mcp](https://github.com/pinecone-io/pinecone-mcp) | [Docs](https://docs.pinecone.io/guides/mcp) | ✅ Officiel |
| **n8n** | [leonardsellem/n8n-mcp-server](https://github.com/leonardsellem/n8n-mcp-server) | [README](https://github.com/leonardsellem/n8n-mcp-server#readme) | 🌐 Communauté |
| **Jina AI** | [jina-ai/MCP](https://github.com/jina-ai/MCP) | [Docs](https://github.com/jina-ai/MCP#readme) | ✅ Officiel |
| **Chroma** | [chroma-core/chroma-mcp](https://github.com/chroma-core/chroma-mcp) | [README](https://github.com/chroma-core/chroma-mcp#readme) | ✅ Officiel |
| **Cohere** | [hrco-cohere-mcp-server](https://github.com/hrco-dev/cohere-mcp-server) | - | 🌐 Communauté |

---

## 📝 Checklist de Configuration

- [ ] Node.js 18+ installé
- [ ] MCP Neo4j installé (`neo4j-mcp --version`)
- [ ] MCP n8n installé (`n8n-mcp-server --version`)
- [ ] MCP Pinecone disponible (`npx @pinecone-database/mcp --help`)
- [ ] Variables d'environnement configurées
- [ ] Fichier `~/.config/claude/config.json` créé
- [ ] Test de connexion Neo4j réussi
- [ ] Test de connexion n8n réussi
- [ ] Test de connexion Pinecone réussi
- [ ] Test de connexion Supabase réussi

---

## 🔐 Sécurité

**⚠️ Ne jamais commiter les fichiers de configuration contenant des clés API !**

```bash
# Ajouter au .gitignore
echo "*.mcp.json" >> .gitignore
echo ".claude/config.json" >> .gitignore
```

**Bonnes pratiques :**
1. Utiliser des variables d'environnement pour les clés
2. Activer le mode `read_only` par défaut pour Supabase
3. Utiliser des clés API avec les permissions minimales
4. Rotation régulière des clés

---

*Document généré pour le projet SOTA 2026 Multi-RAG Orchestrator*
