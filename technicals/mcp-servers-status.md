# MCP Servers - Status et Installation

**Date:** 2026-02-12  
**Environnement:** Termius / mon-ipad

---

## 🎯 MCP Servers à Installer

D'après `docs/technical/mcp-setup.md`, il y a **5 MCP servers** à configurer:

| # | MCP Server | Type | Status | Fichier/Commande |
|---|------------|------|--------|------------------|
| 1 | **Jina Embeddings** | Python | ✅ PRÊT | `mcp/jina-embeddings-server.py` |
| 2 | **Neo4j** | Binary | ⏳ À installer | `neo4j-mcp` |
| 3 | **Pinecone** | NPX | ⏳ À installer | `npx @pinecone-database/mcp` |
| 4 | **n8n** | NPM | ⏳ À installer | `npm install -g @leonardsellem/n8n-mcp-server` |
| 5 | **Supabase** | HTTP | ⏳ À configurer | URL directe |

---

## ✅ MCP Déjà Prêt

### 1. Jina Embeddings MCP

**Fichier:** `/home/termius/mon-ipad/mcp/jina-embeddings-server.py`

**Configuration:**
```json
{
  "mcpServers": {
    "jina-embeddings": {
      "command": "python3",
      "args": ["/home/termius/mon-ipad/mcp/jina-embeddings-server.py"],
      "env": {
        "PINECONE_API_KEY": "pcsk_...",
        "PINECONE_HOST": "https://sota-rag-a4mkzmz.svc.aped-4627-b74a.pinecone.io",
        "OPENROUTER_API_KEY": "sk-or-v1-...",
        "JINA_API_KEY": "jina_...",
        "N8N_API_KEY": "eyJhb...",
        "N8N_HOST": "https://amoret.app.n8n.cloud"
      }
    }
  }
}
```

**Outils disponibles:**
- `embed` - Générer des embeddings
- `pinecone_upsert` - Insérer dans Pinecone
- `pinecone_query` - Requête vectorielle
- `pinecone_stats` - Statistiques index
- `n8n_workflow_list` - Lister workflows
- `n8n_workflow_get` - Obtenir workflow

---

## ⏳ MCP à Installer

### 2. Neo4j MCP (Officiel)

**Installation:**
```bash
# Télécharger la dernière version
VERSION=$(curl -s https://api.github.com/repos/neo4j/mcp/releases/latest | grep '"tag_name":' | sed -E 's/.*"v([^"]+)".*/\1/')
curl -L -o neo4j-mcp.tar.gz "https://github.com/neo4j/mcp/releases/download/v${VERSION}/neo4j-mcp_${VERSION}_linux_amd64.tar.gz"
tar -xzf neo4j-mcp.tar.gz
chmod +x neo4j-mcp
sudo mv neo4j-mcp /usr/local/bin/
rm neo4j-mcp.tar.gz
```

**Configuration:**
```json
{
  "mcpServers": {
    "neo4j": {
      "command": "neo4j-mcp",
      "env": {
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USERNAME": "neo4j",
        "NEO4J_PASSWORD": "jV_zGdxbu-emQZM-ZSQux19pTZ5QLKejR2IHSzsbVak",
        "NEO4J_DATABASE": "neo4j",
        "NEO4J_READ_ONLY": "true",
        "NEO4J_TELEMETRY": "true",
        "NEO4J_TRANSPORT_MODE": "stdio"
      }
    }
  }
}
```

**Note:** L'URI Neo4j doit être mis à jour avec l'URL réelle (accessible via n8n actuellement).

### 3. Pinecone MCP (Officiel)

**Installation:**
```bash
# Pas d'installation - utilisé via npx
npx -y @pinecone-database/mcp --help
```

**Configuration:**
```json
{
  "mcpServers": {
    "pinecone": {
      "command": "npx",
      "args": ["-y", "@pinecone-database/mcp"],
      "env": {
        "PINECONE_API_KEY": "pcsk_6GzVdD_BbHsYNvpcngMqAHH5EvEa9XLnmFpEK9cx5q5xkMp72z5KFQ1q7dEjp8npWhJGBY"
      }
    }
  }
}
```

### 4. n8n MCP (Communauté)

**Installation:**
```bash
npm install -g @leonardsellem/n8n-mcp-server
```

**Configuration:**
```json
{
  "mcpServers": {
    "n8n": {
      "command": "n8n-mcp-server",
      "env": {
        "N8N_API_URL": "https://amoret.app.n8n.cloud/api/v1",
        "N8N_API_KEY": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyMTU3NjdlMC05NThhLTRjNzQtYTY3YS1lMzM1ODA3ZWJhNjQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY5MDQ2NTExLCJleHAiOjE3NzE2Mjg0MDB9.fyOBVwb32HlzwQhSxCxoKsmMlYcxppTFGbj6S01AX2A",
        "N8N_WEBHOOK_USERNAME": "",
        "N8N_WEBHOOK_PASSWORD": "",
        "DEBUG": "false"
      }
    }
  }
}
```

### 5. Supabase MCP (Officiel - HTTP)

**Configuration:**
```json
{
  "mcpServers": {
    "supabase": {
      "type": "http",
      "url": "https://mcp.supabase.com/mcp?project_ref=YOUR_PROJECT_REF&read_only=true&features=database,docs,debugging,development"
    }
  }
}
```

**Note:** Nécessite le project_ref du projet Supabase.

---

## 🔧 Commande d'Installation Automatique

```bash
# Rendre exécutable et lancer
chmod +x /home/termius/mon-ipad/scripts/install-mcp-servers.sh
/home/termius/mon-ipad/scripts/install-mcp-servers.sh
```

Cela installera:
- ✅ Neo4j MCP (binary)
- ✅ n8n MCP (npm global)
- ✅ Vérification Pinecone MCP (npx)
- ✅ Vérification Jina MCP (existent)

---

## 📁 Fichiers de Configuration

| Fichier | Description |
|---------|-------------|
| `.claude/settings.json` | Configuration MCP pour Claude Code |
| `scripts/install-mcp-servers.sh` | Script d'installation automatique |
| `docs/technical/mcp-setup.md` | Documentation complète MCP |

---

## ⚠️ Problèmes Connus

### 1. Accès Neo4j
- **Problème:** Accès direct bloqué (proxy 403)
- **Solution:** Passer par n8n ou attendre migration self-hosted
- **Alternative:** Utiliser workflow n8n `BENCHMARK - SQL Executor Utility`

### 2. Supabase Project Ref
- **Problème:** project_ref inconnu
- **Solution:** Trouver dans Supabase Dashboard ou utiliser SQL Executor n8n

### 3. Clé Cohere
- **Problème:** Nécessaire pour migration embeddings
- **Solution:** Créer compte sur https://cohere.com/

---

## 🎯 Prochaines Étapes

1. **Exécuter le script d'installation:**
   ```bash
   ./scripts/install-mcp-servers.sh
   ```

2. **Configurer les variables d'environnement:**
   ```bash
   export COHERE_API_KEY="votre_cle"
   export N8N_API_KEY="eyJhb..."
   export PINECONE_API_KEY="pcsk_..."
   ```

3. **Relancer Claude Code** pour charger les nouveaux MCP

4. **Vérifier les outils MCP:**
   - Devraient apparaître dans l'interface Claude Code

---

*Document créé pour faciliter la configuration des MCP servers sur Termius*
