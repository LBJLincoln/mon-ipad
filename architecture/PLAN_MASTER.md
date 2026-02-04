# Plan Architecture Multi-Agents RAG SOTA 2026

## Vue d'ensemble

Architecture orchestrateur + 6 sous-agents spécialisés pour l'analyse, l'amélioration et le déploiement des workflows n8n.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR (Modèle Faible)                     │
│         Gère le séquencement et la coordination des agents          │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        │                         │                         │
        ▼                         ▼                         ▼
┌───────────────┐       ┌─────────────────┐       ┌─────────────────┐
│   AGENT 1     │       │    AGENT 2      │       │    AGENT 3      │
│  ANALYZER     │──────▶│   DB READER     │──────▶│  PATCH WRITER   │
│  (Opus 4.5)   │       │  (Opus 4.5)     │       │   (Opus 4.5)    │
└───────────────┘       └─────────────────┘       └────────┬────────┘
                                                           │
        ┌─────────────────────────────────────────────────┘
        │
        ▼
┌───────────────┐       ┌─────────────────┐
│   AGENT 4     │       │    AGENT 5      │
│ PATCH APPLIER │──────▶│   N8N TESTER    │
│(Modèle Faible)│       │   (Opus 4.5)    │
└───────────────┘       └─────────────────┘
```

---

## 1. ORCHESTRATOR MASTER

**Modèle:** Haiku (faible coût, rapide)

**Rôle:** Coordonne le pipeline d'amélioration des workflows

**Responsabilités:**
- Lancer les agents dans l'ordre correct
- Gérer les dépendances entre agents
- Collecter les résultats de chaque étape
- Gérer les erreurs et les reprises
- Produire un rapport final

**Fichier config:** `agents/orchestrator.yaml`

---

## 2. AGENT 1 - WORKFLOW ANALYZER (Opus 4.5)

**Nom:** `workflow-analyzer`

**Rôle:** Analyse approfondie des workflows n8n existants

**Inputs:**
- Tous les fichiers JSON des workflows
- Best practices documents
- Stack technique à respecter
- Variables d'environnement

**Outputs:**
- Rapport d'analyse détaillé par workflow
- Liste des améliorations nécessaires
- Propositions de nouvelle architecture si besoin
- Scoring de qualité

**Skills requis:**
- n8n workflow expertise
- JSON Schema validation
- Architecture design patterns
- Best practices RAG/LLM

**Accès MCP:**
- Lecture fichiers GitHub
- (optionnel) N8N API pour lecture metadata

**Fichier:** `agents/workflow-analyzer.yaml`

---

## 3. AGENT 2 - DATABASE READER (Opus 4.5)

**Nom:** `db-reader`

**Rôle:** Extraction et analyse des données de toutes les bases

**Bases de données accessibles:**

| Base | Connexion | Usage |
|------|-----------|-------|
| **Pinecone** | `https://n8nultimate-a4mkzmz.svc.aped-4627-b74a.pinecone.io` | Embeddings vectors |
| **Neo4j** | `https://a9a062c3.databases.neo4j.io/db/neo4j/query/v2` | Graph RAG knowledge |
| **Supabase** | `postgresql://postgres:***@db.ayqviqmxifzmhphiqfmj.supabase.co:5432/postgres` | Metadata & config |

**Outputs:**
- Inventaire complet des données existantes
- Incohérences détectées
- Correctifs nécessaires sur les données
- Mapping data <-> workflows

**Fichier:** `agents/db-reader.yaml`

---

## 4. AGENT 3 - PATCH WRITER (Opus 4.5)

**Nom:** `patch-writer`

**Rôle:** Génération des patches JSON pour les workflows

**Inputs:**
- Rapport de l'Agent 1 (Analyzer)
- Rapport de l'Agent 2 (DB Reader)

**Outputs:**
- Fichiers JSON Patch (RFC 6902) pour chaque workflow
- Documentation précise des changements
- Instructions de déploiement
- Fichier de rollback

**Format des patches:**
```json
{
  "workflow": "TEST - SOTA 2026 - Ingestion V3.1.json",
  "patches": [
    {
      "op": "replace",
      "path": "/nodes/5/parameters/timeout",
      "value": 30000,
      "reason": "Augmenter timeout pour gros fichiers"
    }
  ]
}
```

**Fichier:** `agents/patch-writer.yaml`

---

## 5. AGENT 4 - PATCH APPLIER (Modèle Faible)

**Nom:** `patch-applier`

**Modèle:** Haiku

**Rôle:** Application des patches via Python

**Skills:**
- Python jsonpatch library
- Backup avant modification
- Validation JSON Schema
- Git operations

**Script principal:**
```python
import jsonpatch
import json
import shutil
from pathlib import Path

def apply_patches(workflow_file, patch_file):
    # Backup
    shutil.copy(workflow_file, f"{workflow_file}.backup")

    # Load & patch
    with open(workflow_file) as f:
        workflow = json.load(f)
    with open(patch_file) as f:
        patches = json.load(f)

    # Apply
    patched = jsonpatch.apply_patch(workflow, patches['patches'])

    # Save
    with open(workflow_file, 'w') as f:
        json.dump(patched, f, indent=2)
```

**Fichier:** `agents/patch-applier.yaml`

---

## 6. AGENT 5 - N8N TESTER (Opus 4.5)

**Nom:** `n8n-tester`

**Rôle:** Validation et test des workflows modifiés

**Connexion N8N:** `https://amoret.app.n8n.cloud/`

**Responsabilités:**
- Importer les workflows modifiés
- Exécuter des tests basiques
- Vérifier les connexions
- Corriger les erreurs mineures
- Produire rapport de validation

**MCP amélioré requis:** Voir section MCP N8N

**Fichier:** `agents/n8n-tester.yaml`

---

## 7. MCP SERVERS

### 7.1 MCP Pinecone

**Fichier:** `mcp-servers/pinecone-mcp.ts`

**Fonctionnalités:**
- `pinecone_list_indexes` - Lister les index
- `pinecone_describe_index` - Décrire un index
- `pinecone_query` - Requête vectorielle
- `pinecone_fetch` - Récupérer des vectors par ID
- `pinecone_upsert` - Insérer/MAJ vectors
- `pinecone_delete` - Supprimer vectors
- `pinecone_stats` - Statistiques de l'index

**Config:**
```json
{
  "pinecone": {
    "command": "npx",
    "args": ["-y", "@anthropic/mcp-pinecone"],
    "env": {
      "PINECONE_API_KEY": "${PINECONE_API_KEY}",
      "PINECONE_HOST": "https://n8nultimate-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
    }
  }
}
```

### 7.2 MCP Neo4j

**Fichier:** `mcp-servers/neo4j-mcp.ts`

**Fonctionnalités:**
- `neo4j_query` - Exécuter Cypher
- `neo4j_read_nodes` - Lire des noeuds
- `neo4j_read_relationships` - Lire relations
- `neo4j_schema` - Obtenir le schéma
- `neo4j_write` - Écriture transactionnelle
- `neo4j_stats` - Statistiques graph

**Config:**
```json
{
  "neo4j": {
    "command": "npx",
    "args": ["-y", "@anthropic/mcp-neo4j"],
    "env": {
      "NEO4J_URI": "https://a9a062c3.databases.neo4j.io",
      "NEO4J_DATABASE": "neo4j",
      "NEO4J_USER": "${NEO4J_USER}",
      "NEO4J_PASSWORD": "${NEO4J_PASSWORD}"
    }
  }
}
```

### 7.3 MCP Supabase/PostgreSQL

**Fichier:** `mcp-servers/supabase-mcp.ts`

**Fonctionnalités:**
- `pg_query` - Exécuter SQL
- `pg_tables` - Lister tables
- `pg_schema` - Décrire schéma table
- `pg_insert` - Insert data
- `pg_update` - Update data
- `pg_delete` - Delete data
- `pg_functions` - Lister functions RPC

**Config:**
```json
{
  "supabase": {
    "command": "npx",
    "args": ["-y", "@anthropic/mcp-postgres"],
    "env": {
      "POSTGRES_CONNECTION_STRING": "postgresql://postgres:***@db.ayqviqmxifzmhphiqfmj.supabase.co:5432/postgres"
    }
  }
}
```

### 7.4 MCP N8N ENHANCED

**Fichier:** `mcp-servers/n8n-enhanced-mcp.ts`

**L'API n8n standard ne permet pas:**
- Lecture des logs d'exécution détaillés
- Modification inline des nodes
- Déclenchement de tests unitaires

**Fonctionnalités étendues à implémenter:**

```typescript
// Core API (existant)
n8n_list_workflows()
n8n_get_workflow(id)
n8n_create_workflow(json)
n8n_update_workflow(id, json)
n8n_delete_workflow(id)
n8n_activate_workflow(id)
n8n_deactivate_workflow(id)
n8n_execute_workflow(id, data?)

// EXTENSIONS (à créer)
n8n_get_execution_logs(execution_id)  // Logs détaillés par node
n8n_get_node_output(execution_id, node_id)  // Output d'un node spécifique
n8n_patch_node(workflow_id, node_id, patch)  // Modifier UN node
n8n_validate_workflow(json)  // Validation sans import
n8n_test_workflow(id, test_cases)  // Tests avec assertions
n8n_get_credentials_info()  // Info credentials (sans secrets)
n8n_check_connections(workflow_id)  // Vérifier toutes les connexions
```

**Implémentation requise:**
- Utiliser l'API REST n8n existante
- Wrapper les exécutions pour capturer les logs
- Parser les résultats pour extraction node par node
- Créer endpoint de validation custom

**Config:**
```json
{
  "n8n-enhanced": {
    "command": "node",
    "args": ["mcp-servers/n8n-enhanced-mcp.js"],
    "env": {
      "N8N_HOST": "https://amoret.app.n8n.cloud",
      "N8N_API_KEY": "${N8N_API_KEY}"
    }
  }
}
```

---

## 8. CONFIGURATION GLOBALE

**Fichier:** `config/agents-config.yaml`

```yaml
orchestrator:
  model: haiku
  max_retries: 3
  timeout_per_agent: 300  # seconds

agents:
  workflow-analyzer:
    model: opus-4.5
    priority: 1
    dependencies: []

  db-reader:
    model: opus-4.5
    priority: 2
    dependencies: [workflow-analyzer]

  patch-writer:
    model: opus-4.5
    priority: 3
    dependencies: [workflow-analyzer, db-reader]

  patch-applier:
    model: haiku
    priority: 4
    dependencies: [patch-writer]

  n8n-tester:
    model: opus-4.5
    priority: 5
    dependencies: [patch-applier]

mcp_servers:
  - pinecone
  - neo4j
  - supabase
  - n8n-enhanced

workflows_to_analyze:
  - "TEST - SOTA 2026 - Enrichissement V3.1.json"
  - "TEST - SOTA 2026 - Feedback V3.1.json"
  - "TEST - SOTA 2026 - Ingestion V3.1.json"
  - "TEST - SOTA 2026 - WF2 Graph RAG V3.3 - CORRECTED (1).json"
  - "TEST - SOTA 2026 - WF4 Quantitative V2.0 (1).json"
  - "TEST - SOTA 2026 - WF5 Standard RAG V3.4 - CORRECTED.json"
  - "V10.1 orchestrator copy (5).json"
```

---

## 9. VARIABLES D'ENVIRONNEMENT

**Fichier:** `config/.env.example`

```bash
# Pinecone
PINECONE_API_KEY=your_pinecone_api_key

# Neo4j
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_neo4j_password

# Supabase
SUPABASE_DB_PASSWORD=LxtBJKljhhBassDS

# N8N
N8N_API_KEY=your_n8n_api_key

# Claude API
ANTHROPIC_API_KEY=your_anthropic_api_key
```

---

## 10. SÉQUENCE D'EXÉCUTION

```
1. ORCHESTRATOR démarre
   │
2. ├─► Lance WORKFLOW-ANALYZER
   │   └─► Produit: analysis-report.json
   │
3. ├─► Lance DB-READER (parallèle possible)
   │   └─► Produit: db-inventory.json
   │
4. ├─► Lance PATCH-WRITER
   │   └─► Input: analysis + inventory
   │   └─► Produit: patches/*.json
   │
5. ├─► Lance PATCH-APPLIER
   │   └─► Applique les patches
   │   └─► Produit: workflows modifiés
   │
6. ├─► Lance N8N-TESTER
   │   └─► Teste les workflows
   │   └─► Produit: test-results.json
   │
7. └─► ORCHESTRATOR compile rapport final
       └─► Produit: final-report.md
```

---

## 11. PROCHAINES ÉTAPES

### Phase 1: Infrastructure MCP
- [ ] Créer MCP Pinecone
- [ ] Créer MCP Neo4j
- [ ] Créer MCP Supabase
- [ ] Créer MCP N8N Enhanced

### Phase 2: Agents
- [ ] Définir prompts système de chaque agent
- [ ] Implémenter workflow-analyzer
- [ ] Implémenter db-reader
- [ ] Implémenter patch-writer
- [ ] Implémenter patch-applier
- [ ] Implémenter n8n-tester
- [ ] Implémenter orchestrator

### Phase 3: Intégration
- [ ] Tests unitaires par agent
- [ ] Tests d'intégration pipeline complet
- [ ] Documentation utilisateur

### Phase 4: Déploiement
- [ ] Configuration CI/CD
- [ ] Monitoring
- [ ] Alerting
