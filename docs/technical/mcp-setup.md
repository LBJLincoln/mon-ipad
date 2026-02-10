# Configuration MCP (Model Context Protocol)

> **Ce fichier DOIT être mis à jour** après chaque ajout/modification de serveur MCP.
> Dernière mise à jour : 2026-02-10

---

## Qu'est-ce que MCP ?

MCP (Model Context Protocol) permet à Claude Code d'appeler des outils externes directement. Au lieu de passer par des commandes bash, Claude peut appeler des fonctions Python qui interagissent avec Pinecone, n8n, etc.

---

## Configuration actuelle (`.claude/settings.json`)

```json
{
  "mcpServers": {
    "jina-embeddings": {
      "command": "python3",
      "args": ["/home/user/mon-ipad/mcp/jina-embeddings-server.py"],
      "env": {
        "PINECONE_API_KEY": "...",
        "OPENROUTER_API_KEY": "...",
        "JINA_API_KEY": "...",
        "N8N_API_KEY": "...",
        "N8N_HOST": "https://amoret.app.n8n.cloud"
      }
    }
  }
}
```

---

## Serveurs MCP disponibles

### 1. jina-embeddings (ACTIF)
**Fichier** : `mcp/jina-embeddings-server.py`

| Outil | Description | Quand l'utiliser |
|-------|-------------|-----------------|
| `jina_embed` | Générer des embeddings (Jina free 1024d) | Indexation, test de similarité |
| `pinecone_upsert` | Insérer des vecteurs dans Pinecone | Peuplement de la base |
| `pinecone_query` | Chercher dans Pinecone | Debug retrieval Standard RAG |
| `pinecone_index_stats` | Stats de l'index | Vérifier l'état de la base |
| `pinecone_list_namespaces` | Lister les namespaces | Explorer la structure |
| `n8n_fetch_execution` | Récupérer une exécution n8n | Analyse granulaire |
| `n8n_set_workflow_vars` | Modifier les variables n8n | Changer le modèle d'embedding |
| `n8n_activate_workflow` | Activer/désactiver un workflow | Déploiement |

### 2. Serveurs MCP à ajouter (recommandés)

#### n8n-workflow-manager
Pour gérer les workflows n8n directement depuis Claude Code.
```json
{
  "n8n-workflows": {
    "command": "python3",
    "args": ["/home/user/mon-ipad/mcp/n8n-workflow-server.py"],
    "env": {
      "N8N_API_KEY": "...",
      "N8N_HOST": "..."
    }
  }
}
```
Outils à implémenter :
- `n8n_list_workflows` : Lister tous les workflows
- `n8n_get_workflow` : Récupérer un workflow complet
- `n8n_update_node` : Modifier un nœud spécifique
- `n8n_deploy_workflow` : Déployer (deactivate → PUT → activate)
- `n8n_list_executions` : Lister les dernières exécutions
- `n8n_get_execution_nodes` : Analyse node-par-node d'une exécution

#### Serveurs communautaires via npx (si npm disponible)

```json
{
  "supabase": {
    "command": "npx",
    "args": ["-y", "@supabase/mcp-server"],
    "env": {
      "SUPABASE_URL": "https://xxx.supabase.co",
      "SUPABASE_KEY": "..."
    }
  },
  "redis": {
    "command": "npx",
    "args": ["-y", "@redis/mcp-server"],
    "env": {
      "REDIS_URL": "redis://..."
    }
  }
}
```

**Note** : Supabase et Neo4j MCP nécessitent un accès direct (pas possible avec le proxy actuel). Disponible uniquement avec n8n self-hosted.

---

## Comment ajouter un nouveau serveur MCP

1. Créer le fichier Python dans `mcp/`
2. Utiliser le SDK MCP :
```python
from mcp.server import Server
from mcp.types import Tool, TextContent

server = Server("my-server")

@server.list_tools()
async def list_tools():
    return [Tool(name="my_tool", description="...", inputSchema={...})]

@server.call_tool()
async def call_tool(name, arguments):
    if name == "my_tool":
        result = do_something(arguments)
        return [TextContent(type="text", text=json.dumps(result))]

if __name__ == "__main__":
    import asyncio
    from mcp.server.stdio import stdio_server
    async def main():
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())
    asyncio.run(main())
```
3. Ajouter la config dans `.claude/settings.json`
4. Redémarrer Claude Code

---

## Debugging MCP

```bash
# Tester un serveur MCP manuellement
python3 mcp/jina-embeddings-server.py

# Vérifier que le module mcp est installé
pip install --user mcp

# Logs MCP dans Claude Code
# Les erreurs MCP apparaissent dans le terminal Claude Code au démarrage
```

---

## Priorisation des MCP à implémenter

| Priorité | Serveur | Raison |
|----------|---------|--------|
| **P0** | jina-embeddings (existant) | Déjà fonctionnel, couvre embeddings + Pinecone + n8n |
| **P1** | n8n-workflow-manager | Permettrait de modifier les workflows directement |
| **P2** | supabase (si self-hosted) | Requêtes SQL directes pour debug Quantitative |
| **P3** | neo4j (si self-hosted) | Requêtes Cypher directes pour debug Graph |
| **P4** | redis | Cache pour accélérer les itérations |
