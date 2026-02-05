# Multi-RAG Orchestrator - SOTA 2026

## Project Overview
Systeme multi-agents pour l'amelioration automatisee des workflows n8n RAG.
Orchestrateur + 5 sous-agents specialises qui analysent, ameliorent et deploient des workflows n8n.

## Architecture
- **Orchestrator** (Haiku) : Coordination des agents
- **Workflow Analyzer** (Opus 4.5) : Analyse des workflows JSON
- **DB Reader** (Opus 4.5) : Extraction donnees BDD (Pinecone, Neo4j, Supabase)
- **Patch Writer** (Opus 4.5) : Generation des patches RFC 6902
- **Patch Applier** (Haiku) : Application des patches via Python
- **N8N Tester** (Opus 4.5) : Tests et validation sur n8n cloud

## Key Files
- `architecture/agents/*.yaml` - Definitions des agents
- `architecture/mcp-servers/*.ts` - Serveurs MCP (Pinecone, Neo4j, Supabase, N8N)
- `architecture/config/claude-mcp-config.json` - Config MCP pour Claude Code
- `architecture/config/agents-config.yaml` - Config globale agents
- `TEST - SOTA 2026 - *.json` - Workflows n8n a analyser
- `V10.1 orchestrator copy (5).json` - Orchestrateur principal n8n

## Running Agents
```bash
# Lancer avec les MCP servers configures
claude --mcp-config architecture/config/claude-mcp-config.json

# Ou via le runner
node architecture/runner/run-agent.mjs <agent-name>
```

## MCP Servers
Installer les dependances avant de lancer :
```bash
cd architecture/mcp-servers && npm install
```

## Conventions
- Les workflows JSON ne doivent PAS etre modifies directement - utiliser le pipeline de patches
- Toujours creer des backups avant modification
- Les credentials sont geres via variables d'environnement uniquement
- Ne jamais committer de secrets ou mots de passe

## Databases
- **Pinecone**: Vector embeddings (namespace par tenant)
- **Neo4j**: Graph RAG knowledge (Cypher queries)
- **Supabase**: Metadata, configuration, metriques

## Best Practices Reference
Le fichier `n8n Multi-Tenant Document Workflows.docx` contient les specifications SOTA 2026
pour chaque type de workflow (ingestion, enrichissement, graph RAG, quantitative, fallback,
monitoring, dataset import, batch evaluation). Un fichier supplémentaire nommé SOTA 2026 vient ajouter tout ce qui était manqué par le précédent doc.
