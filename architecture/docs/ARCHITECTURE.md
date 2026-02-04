# Architecture Multi-Agents RAG SOTA 2026

## Vue d'ensemble

Ce système utilise un orchestrateur central qui coordonne 5 sous-agents spécialisés pour analyser, améliorer et déployer des workflows n8n.

## Diagramme d'architecture

```
                    ┌─────────────────────────────────┐
                    │      ORCHESTRATOR (Haiku)       │
                    │    Coordination & Séquençage    │
                    └───────────────┬─────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐          ┌───────────────┐          ┌───────────────┐
│   ANALYZER    │          │  DB READER    │          │  PATCH WRITER │
│  (Opus 4.5)   │─────────▶│  (Opus 4.5)   │─────────▶│  (Opus 4.5)   │
│               │          │               │          │               │
│ Analyse des   │          │ Extraction    │          │ Génération    │
│ workflows     │          │ données BDD   │          │ des patches   │
└───────────────┘          └───────────────┘          └───────┬───────┘
                                                              │
                           ┌──────────────────────────────────┘
                           │
                           ▼
                  ┌───────────────┐          ┌───────────────┐
                  │ PATCH APPLIER │          │  N8N TESTER   │
                  │   (Haiku)     │─────────▶│  (Opus 4.5)   │
                  │               │          │               │
                  │ Application   │          │ Tests &       │
                  │ des patches   │          │ Validation    │
                  └───────────────┘          └───────────────┘
```

## Agents

### 1. Orchestrator (Haiku)
- **Rôle**: Coordination pure
- **Modèle**: Haiku (rapide, économique)
- **Responsabilités**:
  - Lancer les agents dans l'ordre
  - Gérer les dépendances
  - Collecter les résultats
  - Gérer les erreurs

### 2. Workflow Analyzer (Opus 4.5)
- **Rôle**: Analyse approfondie
- **Outputs**: `analysis-report.json`
- **Critères d'analyse**:
  - Performance (timeouts, parallélisation)
  - Résilience (error handling, retries)
  - Sécurité (validation, sanitization)
  - Maintenabilité (nommage, modularité)
  - Architecture (patterns, évolutivité)

### 3. DB Reader (Opus 4.5)
- **Rôle**: Extraction des données
- **Bases**: Pinecone, Neo4j, Supabase
- **Outputs**: `db-inventory.json`, `db-corrections.json`
- **Analyses**:
  - Cohérence cross-database
  - Data quality
  - Mapping workflows ↔ données

### 4. Patch Writer (Opus 4.5)
- **Rôle**: Génération des corrections
- **Format**: JSON Patch (RFC 6902)
- **Outputs**: `patches/*.json`, `patches-manifest.json`
- **Inclut**:
  - Patches de modification
  - Patches de rollback
  - Documentation des changements
  - Cas de test

### 5. Patch Applier (Haiku)
- **Rôle**: Application des corrections
- **Modèle**: Haiku (tâches simples)
- **Outputs**: `modified-workflows/`, `backups/`
- **Outils**: Python jsonpatch

### 6. N8N Tester (Opus 4.5)
- **Rôle**: Validation finale
- **Outputs**: `test-results.json`, `final-workflows/`
- **Tests**:
  - Import réussi
  - Validation des credentials
  - Exécution dry-run
  - Corrections automatiques mineures

## Serveurs MCP

| Serveur | Base | Fonctionnalités clés |
|---------|------|---------------------|
| pinecone-mcp | Pinecone | query, upsert, delete, stats |
| neo4j-mcp | Neo4j | Cypher queries, schema, paths |
| supabase-mcp | PostgreSQL | SQL queries, schema, data ops |
| n8n-enhanced-mcp | n8n | Logs, node patching, tests |

## Flux de données

```
[Workflows JSON] ──▶ [Analyzer] ──▶ [analysis-report.json]
                                            │
[Bases de données] ──▶ [DB Reader] ──▶ [db-inventory.json]
                                            │
                                            ▼
                              [Patch Writer] ──▶ [patches/*.json]
                                            │
                                            ▼
[Workflows + Patches] ──▶ [Patch Applier] ──▶ [modified-workflows/]
                                            │
                                            ▼
                              [N8N Tester] ──▶ [final-workflows/]
                                            │
                                            ▼
                                    [Rapport final]
```

## Configuration

### Variables d'environnement requises

```bash
PINECONE_API_KEY=...
NEO4J_USER=...
NEO4J_PASSWORD=...
SUPABASE_PASSWORD=...
N8N_API_KEY=...
ANTHROPIC_API_KEY=...
```

### Installation des MCP

```bash
cd architecture/mcp-servers
npm install
```

### Lancement

```bash
# Via Claude Code avec la config MCP
claude --mcp-config architecture/config/claude-mcp-config.json
```

## Gestion des erreurs

1. **Retry automatique**: 3 tentatives par agent
2. **Fallback**: Continue si agent non-critique échoue
3. **Backups**: Créés avant toute modification
4. **Rollback**: Patches de rollback fournis

## Sécurité

- Credentials gérés via variables d'environnement
- Pas de secrets dans les fichiers de config
- Accès MCP en lecture seule par défaut
- Validation des inputs avant exécution
