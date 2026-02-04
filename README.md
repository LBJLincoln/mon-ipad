# Multi-RAG Orchestrator - SOTA 2026

Système multi-agents pour l'amélioration automatisée des workflows n8n RAG.

## Structure du projet

```
.
├── architecture/
│   ├── PLAN_MASTER.md          # Plan d'architecture complet
│   ├── agents/                  # Définitions des agents
│   │   ├── orchestrator.yaml
│   │   ├── workflow-analyzer.yaml
│   │   ├── db-reader.yaml
│   │   ├── patch-writer.yaml
│   │   ├── patch-applier.yaml
│   │   └── n8n-tester.yaml
│   ├── mcp-servers/            # Serveurs MCP
│   │   ├── pinecone-mcp.ts
│   │   ├── neo4j-mcp.ts
│   │   ├── supabase-mcp.ts
│   │   ├── n8n-enhanced-mcp.ts
│   │   └── package.json
│   ├── config/                 # Configuration
│   │   ├── agents-config.yaml
│   │   ├── claude-mcp-config.json
│   │   └── .env.example
│   └── docs/                   # Documentation
│       └── ARCHITECTURE.md
├── TEST - SOTA 2026 - *.json   # Workflows n8n
├── V10.1 orchestrator copy (5).json
└── n8n Multi-Tenant Document Workflows.docx
```

## Agents

| Agent | Modèle | Rôle |
|-------|--------|------|
| Orchestrator | Haiku | Coordination des agents |
| Workflow Analyzer | Opus 4.5 | Analyse des workflows |
| DB Reader | Opus 4.5 | Extraction données BDD |
| Patch Writer | Opus 4.5 | Génération des patches |
| Patch Applier | Haiku | Application des patches |
| N8N Tester | Opus 4.5 | Tests et validation |

## Bases de données

- **Pinecone**: Vector embeddings
- **Neo4j**: Graph RAG knowledge
- **Supabase**: Metadata & configuration

## Installation

```bash
# Cloner le repo
git clone git@github.com:LBJLincoln/mon-ipad.git
cd mon-ipad

# Installer les dépendances MCP
cd architecture/mcp-servers
npm install

# Configurer les credentials
cp ../config/.env.example ../.env
# Éditer ../.env avec vos credentials
```

## Usage

```bash
# Avec Claude Code
claude --mcp-config architecture/config/claude-mcp-config.json
```

## Documentation

- [Plan Master](architecture/PLAN_MASTER.md) - Plan d'architecture détaillé
- [Architecture](architecture/docs/ARCHITECTURE.md) - Documentation technique

## Workflows inclus

1. **Ingestion V3.1** - Pipeline d'ingestion de documents
2. **Enrichissement V3.1** - Enrichissement des données
3. **Feedback V3.1** - Gestion des feedbacks utilisateurs
4. **Graph RAG V3.3** - RAG basé sur graphe (Neo4j)
5. **Quantitative V2.0** - Analyses quantitatives
6. **Standard RAG V3.4** - RAG standard (Pinecone)
7. **Orchestrator V10.1** - Orchestrateur principal
