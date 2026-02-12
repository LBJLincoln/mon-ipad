# Guide des Workflows Benchmark - Administration des Bases de Données

**Date de création:** 2026-02-12  
**Version:** 1.0  
**Auteur:** Claude Code

---

## 📋 Vue d'ensemble

Ce guide documente les workflows n8n créés pour l'administration et l'introspection des bases de données du projet SOTA 2026 Multi-RAG Orchestrator.

### Workflows disponibles

| Workflow | Fichier | Description | Webhook |
|----------|---------|-------------|---------|
| **Supabase Introspection** | `supabase-introspection-v1.json` | Administration complète PostgreSQL | `benchmark-supabase-admin` |
| **Neo4j Introspection** | `neo4j-introspection-v1.json` | Administration graphe Neo4j | `benchmark-neo4j-admin` |
| **Pinecone Introspection** | `pinecone-introspection-v1.json` | Administration vecteurs Pinecone | `benchmark-pinecone-admin` |
| **Unified Dashboard** | `unified-db-dashboard-v1.json` | Dashboard unifié cross-DB | `benchmark-db-dashboard` |

---

## 🚀 Installation

### 1. Importer les workflows dans n8n

```bash
# Via l'API n8n (depuis le repo)
cd /home/termius/mon-ipad

export N8N_API_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
export N8N_HOST="https://amoret.app.n8n.cloud"

# Importer un workflow
python3 -c "
import json
import urllib.request
import os

workflow_file = 'workflows/benchmarks/supabase-introspection-v1.json'
with open(workflow_file) as f:
    workflow_data = json.load(f)

# Remove n8n-specific IDs for clean import
for node in workflow_data.get('nodes', []):
    if 'id' in node:
        del node['id']

url = f\"{os.environ['N8N_HOST']}/api/v1/workflows\"
req = urllib.request.Request(
    url,
    data=json.dumps(workflow_data).encode(),
    headers={
        'X-N8N-API-KEY': os.environ['N8N_API_KEY'],
        'Content-Type': 'application/json'
    },
    method='POST'
)

with urllib.request.urlopen(req) as resp:
    result = json.loads(resp.read())
    print(f\"Workflow imported: {result['id']}\")
"
```

### 2. Configurer les credentials

Chaque workflow nécessite les credentials configurés dans n8n :

| Service | Credential Type | Variables requises |
|---------|-----------------|-------------------|
| **Supabase** | Postgres | Host, Port, Database, User, Password |
| **Neo4j** | Neo4j | Host, Port, Username, Password |
| **Pinecone** | HTTP Header | Api-Key header |

---

## 📊 Supabase Introspection API

**Webhook:** `POST /webhook/benchmark-supabase-admin`

### Actions disponibles

#### 1. Lister toutes les tables
```json
{
  "action": "list_tables",
  "schema": "public"
}
```

**Réponse:**
```json
{
  "timestamp": "2026-02-12T13:00:00Z",
  "action": "list_tables",
  "schema": "public",
  "data": [
    {"schemaname": "public", "tablename": "financials", "size": "8192 bytes"},
    {"schemaname": "public", "tablename": "balance_sheet", "size": "4096 bytes"}
  ],
  "row_count": 2
}
```

#### 2. Décrire une table
```json
{
  "action": "describe_table",
  "schema": "public",
  "table_name": "financials"
}
```

#### 3. Obtenir les statistiques de la base
```json
{
  "action": "get_stats"
}
```

#### 4. Récupérer un échantillon de données
```json
{
  "action": "sample_data",
  "schema": "public",
  "table_name": "financials",
  "limit": 5
}
```

#### 5. Compter les lignes par table
```json
{
  "action": "get_row_counts"
}
```

#### 6. Lister les contraintes
```json
{
  "action": "list_constraints",
  "schema": "public",
  "table_name": "financials"
}
```

#### 7. Exécuter du SQL personnalisé
```json
{
  "action": "execute_sql",
  "sql": "SELECT company_name, SUM(revenue) FROM financials GROUP BY company_name"
}
```

---

## 🕸️ Neo4j Introspection API

**Webhook:** `POST /webhook/benchmark-neo4j-admin`

### Actions disponibles

#### 1. Résumé du graphe
```json
{
  "action": "summary"
}
```

**Réponse:**
```json
{
  "timestamp": "2026-02-12T13:00:00Z",
  "action": "summary",
  "database": "neo4j",
  "data": [{
    "summary": {
      "total_nodes": 19788,
      "total_relationships": 21625,
      "labels": {
        "Person": 2467,
        "Organization": 199,
        "Entity": 2047
      },
      "total_property_keys": 45
    }
  }],
  "result_count": 1
}
```

#### 2. Lister les labels de nœuds
```json
{
  "action": "list_labels"
}
```

#### 3. Lister les types de relations
```json
{
  "action": "list_relationships"
}
```

#### 4. Compter par label
```json
{
  "action": "count_by_label"
}
```

#### 5. Obtenir le schéma complet
```json
{
  "action": "get_schema"
}
```

#### 6. Échantillon de nœuds
```json
{
  "action": "sample_nodes",
  "label": "Person",
  "limit": 10
}
```

#### 7. Rechercher des nœuds
```json
{
  "action": "search_nodes",
  "search_term": "Alan Turing",
  "limit": 5
}
```

#### 8. Obtenir les voisins
```json
{
  "action": "get_neighbors",
  "node_id": 12345,
  "max_depth": 2,
  "limit": 10
}
```

#### 9. Exécuter du Cypher personnalisé
```json
{
  "action": "execute_cypher",
  "cypher": "MATCH (p:Person)-[:A_CREE]->(t:Technology) RETURN p.name, t.name LIMIT 10"
}
```

#### 10. Lister les indexes
```json
{
  "action": "get_indexes"
}
```

---

## 🎯 Pinecone Introspection API

**Webhook:** `POST /webhook/benchmark-pinecone-admin`

### Actions disponibles

#### 1. Statistiques de l'index
```json
{
  "action": "index_stats"
}
```

**Réponse:**
```json
{
  "timestamp": "2026-02-12T13:00:00Z",
  "action": "index_stats",
  "database": "pinecone",
  "total_vectors": 10411,
  "dimension": 1536,
  "index_fullness": 0.0,
  "namespaces": {
    "benchmark-squad_v2": {"vectorCount": 1000},
    "benchmark-triviaqa": {"vectorCount": 1000}
  }
}
```

#### 2. Lister les namespaces
```json
{
  "action": "list_namespaces"
}
```

#### 3. Lister les indexes
```json
{
  "action": "list_indexes"
}
```

#### 4. Rechercher des vecteurs similaires
```json
{
  "action": "search_similar",
  "namespace": "benchmark-triviaqa",
  "query_vector": [0.1, 0.2, ...],  // 1536 dimensions
  "top_k": 5,
  "filter": {"category": {"$eq": "factoid_qa"}}
}
```

#### 5. Récupérer un vecteur par ID
```json
{
  "action": "fetch_vector",
  "namespace": "benchmark-triviaqa",
  "vector_id": "trivia-00001"
}
```

#### 6. Lister les IDs de vecteurs
```json
{
  "action": "list_vector_ids",
  "namespace": "benchmark-triviaqa",
  "limit": 100
}
```

#### 7. Vérifier la dimension
```json
{
  "action": "check_dimension",
  "index_name": "sota-rag"
}
```

---

## 📈 Unified Dashboard API

**Webhook:** `POST /webhook/benchmark-db-dashboard`

### Types de rapports

#### 1. Résumé complet (défaut)
```json
{
  "report_type": "full_summary"
}
```

**Réponse:**
```json
{
  "timestamp": "2026-02-12T13:00:00Z",
  "report_type": "full_summary",
  "overall_status": "complete",
  "databases": {
    "pinecone": {
      "status": "healthy",
      "total_vectors": 10411,
      "dimension": 1536,
      "namespaces": ["benchmark-squad_v2", "benchmark-triviaqa", ...],
      "namespace_count": 12
    },
    "neo4j": {
      "status": "healthy",
      "total_nodes": 19788,
      "total_relationships": 21625,
      "labels": ["Person", "Organization", "Entity", ...],
      "relationships": ["A_CREE", "CONNECTE", ...]
    },
    "supabase": {
      "status": "healthy",
      "total_tables": 10,
      "database_size": "45 MB",
      "tables": [
        {"schemaname": "public", "table_name": "financials", "row_count": 24},
        {"schemaname": "public", "table_name": "balance_sheet", "row_count": 12}
      ]
    }
  },
  "cross_db_analysis": {
    "total_entities_across_dbs": 30224,
    "embedding_dimension_match": "ok"
  }
}
```

#### 2. Rapport spécifique par base
```json
{
  "report_type": "pinecone_only"
}
```

```json
{
  "report_type": "neo4j_only"
}
```

```json
{
  "report_type": "supabase_only"
}
```

#### 3. Analyse cross-DB
```json
{
  "report_type": "cross_db_analysis"
}
```

#### 4. Vérification qualité des données
```json
{
  "report_type": "data_quality_check"
}
```

#### 5. Analyse des embeddings
```json
{
  "report_type": "embedding_analysis",
  "check_embeddings": true
}
```

#### 6. Rapport des données manquantes
```json
{
  "report_type": "missing_data_report"
}
```

---

## 🔧 Utilisation avec curl

### Exemples de requêtes

```bash
# Configuration
N8N_HOST="https://amoret.app.n8n.cloud"

# 1. Dashboard unifié
curl -X POST "${N8N_HOST}/webhook/benchmark-db-dashboard" \
  -H "Content-Type: application/json" \
  -d '{"report_type": "full_summary"}'

# 2. Lister les tables Supabase
curl -X POST "${N8N_HOST}/webhook/benchmark-supabase-admin" \
  -H "Content-Type: application/json" \
  -d '{"action": "list_tables"}'

# 3. Résumé Neo4j
curl -X POST "${N8N_HOST}/webhook/benchmark-neo4j-admin" \
  -H "Content-Type: application/json" \
  -d '{"action": "summary"}'

# 4. Statistiques Pinecone
curl -X POST "${N8N_HOST}/webhook/benchmark-pinecone-admin" \
  -H "Content-Type: application/json" \
  -d '{"action": "index_stats"}'

# 5. Exécuter du SQL personnalisé
curl -X POST "${N8N_HOST}/webhook/benchmark-supabase-admin" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "execute_sql",
    "sql": "SELECT table_name, COUNT(*) FROM information_schema.columns GROUP BY table_name"
  }'

# 6. Rechercher dans Neo4j
curl -X POST "${N8N_HOST}/webhook/benchmark-neo4j-admin" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "search_nodes",
    "search_term": "MIT",
    "limit": 5
  }'
```

---

## 📝 Notes importantes

### Dimensions des embeddings

⚠️ **Attention**: Les vecteurs Pinecone sont actuellement en dimension **1536** (anciens embeddings OpenAI), mais la migration vers **1024** (Cohere/Jina) est prévue.

Pour vérifier la dimension actuelle :
```bash
curl -X POST "${N8N_HOST}/webhook/benchmark-pinecone-admin" \
  -H "Content-Type: application/json" \
  -d '{"action": "check_dimension", "index_name": "sota-rag"}'
```

### Permissions requises

- **Supabase**: Accès lecture sur `information_schema` et `pg_stat_user_tables`
- **Neo4j**: Accès lecture sur les métadonnées du graphe (procédures APOC)
- **Pinecone**: Clé API avec accès lecture sur l'index

### Limites de rate

- Pinecone: 100 requêtes/minute (free tier)
- Neo4j: Dépend de la connexion n8n
- Supabase: Dépend de la connexion n8n

---

## 🐛 Dépannage

### Problème: "Error in workflow" sur SQL Executor

**Cause**: Le workflow existant `BENCHMARK - SQL Executor Utility` a un problème de credentials.

**Solution**: Utiliser le nouveau workflow `Supabase Introspection` qui inclut une meilleure gestion d'erreurs.

### Problème: "No items returned" sur Neo4j

**Cause**: APOC n'est peut-être pas installé sur l'instance Neo4j.

**Solution**: Vérifier avec l'action `check_connectivity` ou utiliser `execute_cypher` avec des requêtes Cypher standards.

### Problème: "Unauthorized" sur Pinecone

**Cause**: Clé API incorrecte ou expirée.

**Solution**: Vérifier la clé dans les credentials n8n et la variable `PINECONE_API_KEY`.

---

## 🔄 Prochaines améliorations

- [ ] Ajouter la possibilité d'insérer/modifier des données via les workflows
- [ ] Ajouter des actions de maintenance (vacuum, réindexation)
- [ ] Créer un dashboard visuel HTML
- [ ] Ajouter des alertes automatiques sur anomalies
- [ ] Intégrer avec le workflow de monitoring existant

---

## 📚 Références

- [Documentation Pinecone API](https://docs.pinecone.io/reference/api/)
- [Documentation Neo4j APOC](https://neo4j.com/docs/apoc/current/)
- [Documentation PostgreSQL System Catalogs](https://www.postgresql.org/docs/current/catalogs.html)

---

*Document créé automatiquement par Claude Code pour le projet SOTA 2026 Multi-RAG Orchestrator*
