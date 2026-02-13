# MCP Servers — Status et Configuration

> Derniere mise a jour : 2026-02-13 (post-migration Docker)

---

## MCP Configures (`.claude/settings.json`)

| # | MCP Server | Type | Status | Outils principaux |
|---|------------|------|--------|-------------------|
| 1 | **n8n** | streamableHttp | ACTIF | search_workflows, execute_workflow, get_workflow_details |
| 2 | **jina-embeddings** | Python custom | ACTIF | embed, pinecone CRUD, n8n API helpers |
| 3 | **neo4j** | Binary (neo4j-mcp) | CONFIGURE | get-schema, execute-read, execute-write |
| 4 | **pinecone** | NPX | CONFIGURE | list-indexes, search-records, rerank-documents |
| 5 | **supabase** | HTTP | CONFIGURE | list_tables, execute_sql, get_logs |
| 6 | **cohere** | Python custom | CONFIGURE | embed, rerank, generate |
| 7 | **huggingface** | Python custom | CONFIGURE | search_models, search_datasets |

---

## Analyse d'acces reel (depuis Claude Code sur cette VM)

### ACTIF — Confirme fonctionnel
- **n8n MCP** : Acces direct via `http://34.136.180.66:5678/mcp-server/http` (Docker natif)
  - Token MCP Bearer separe du API Key
  - Outils : search_workflows, execute_workflow, get_workflow_details

### CONFIGURE — A valider
- **jina-embeddings** : Script Python custom dans `mcp/jina-embeddings-server.py`
- **neo4j** : Binary `neo4j-mcp` — necessite que Neo4j soit accessible via `bolt://localhost:7687`
- **pinecone** : Via `npx @pinecone-database/mcp` — devrait fonctionner directement
- **supabase** : HTTP vers `mcp.supabase.com` — project_ref: `ayqviqmxifzmhphiqfmj`
- **cohere** : Script Python custom dans `mcp/cohere-mcp-server.py`
- **huggingface** : Script Python custom dans `mcp/huggingface-mcp-server.py`

---

## Fichiers dans ce dossier

| Fichier | Description |
|---------|-------------|
| `jina-embeddings-server.py` | Serveur MCP custom : embeddings Jina + Pinecone CRUD + n8n API |
| `cohere-mcp-server.py` | Serveur MCP custom : embeddings + reranking Cohere |
| `huggingface-mcp-server.py` | Serveur MCP custom : recherche modeles/datasets HF |
| `setup.md` | Guide d'installation complet des MCP servers |
| `servers-status.md` | Status detaille par serveur |
| `analysis-complete.md` | Analyse MCP vs API directe |
| `termius-setup.md` | Configuration Termius + MCP |

---

## Configuration actuelle (`.claude/settings.json`)

```json
{
  "mcpServers": {
    "n8n": {
      "type": "streamableHttp",
      "url": "http://34.136.180.66:5678/mcp-server/http",
      "headers": { "Authorization": "Bearer <MCP_TOKEN>" }
    },
    "jina-embeddings": {
      "command": "python3",
      "args": ["mcp/jina-embeddings-server.py"],
      "env": { "JINA_API_KEY": "...", "PINECONE_API_KEY": "...", "N8N_HOST": "..." }
    },
    "neo4j": {
      "command": "neo4j-mcp",
      "env": { "NEO4J_URI": "bolt://localhost:7687", "NEO4J_READ_ONLY": "true" }
    },
    "pinecone": {
      "command": "npx",
      "args": ["-y", "@pinecone-database/mcp"],
      "env": { "PINECONE_API_KEY": "..." }
    },
    "supabase": {
      "type": "http",
      "url": "https://mcp.supabase.com/mcp?project_ref=ayqviqmxifzmhphiqfmj&read_only=true"
    },
    "cohere": {
      "command": "python3",
      "args": ["mcp/cohere-mcp-server.py"],
      "env": { "COHERE_API_KEY": "..." }
    },
    "huggingface": {
      "command": "python3",
      "args": ["mcp/huggingface-mcp-server.py"],
      "env": { "HF_TOKEN": "..." }
    }
  }
}
```
