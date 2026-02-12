# Migration n8n Cloud → Docker Self-Hosted - Documentation Complète

**Date:** 2026-02-12  
**Statut:** ✅ TERMINÉE  
**Coût:** $0 (100% gratuit)

---

## 🎯 Résumé de la Migration

Migration réussie de **n8n Cloud payant** (~20€/mois) vers **n8n Docker self-hosted gratuit** sur VM Google Cloud (34.136.180.66).

### Avantages obtenus
- ✅ **Coût:** $0/mois (vs ~20€/mois sur Cloud)
- ✅ **Variables:** 54 variables d'environnement configurées (illimité)
- ✅ **Contrôle:** Accès total aux logs, DB, et configuration
- ✅ **Performance:** VM dédiée (4 vCPU, 16GB RAM)
- ✅ **Flexibilité:** Pas de limitations de licences Enterprise

---

## 📁 Fichiers Modifiés/Créés

| Fichier | Description |
|---------|-------------|
| `~/n8n/docker-compose.yml` | Configuration complète avec PostgreSQL + Redis |
| `/home/termius/mon-ipad/.env.local` | Variables d'environnement mises à jour |
| `/home/termius/.kimi/mcp.json` | Config MCP avec nouvelle API Key n8n |
| `/home/termius/mon-ipad/workflows/live/*.json` | Workflows convertis ($vars → $env) |
| `docs/n8n-docker-workflow-ids.json` | Mapping des nouveaux IDs |
| `docs/MIGRATION_N8N_DOCKER_COMPLETE.md` | Ce document |

---

## 🔧 Infrastructure Déployée

### Services Docker

```yaml
Services:
  - n8n: latest (port 5678)
  - postgres: 15-alpine (port 5432)
  - redis: 7-alpine (port 6379)
```

### Configuration Réseau

| Service | Port Interne | Port Externe | Accès |
|---------|--------------|--------------|-------|
| n8n | 5678 | 5678 | http://34.136.180.66:5678 |
| PostgreSQL | 5432 | 5432 | localhost uniquement |
| Redis | 6379 | 6379 | localhost uniquement |

### Credentials de Base

| Service | Username | Password |
|---------|----------|----------|
| n8n | admin | SotaRAG2026! |
| PostgreSQL | n8n | n8n_password_secure_2026 |
| Redis | - | (aucun) |

---

## 🔑 Variables d'Environnement Configurées (54)

### APIs & LLMs
```bash
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1/chat/completions
OPENROUTER_API_KEY=***REDACTED***

LLM_SQL_MODEL=meta-llama/llama-3.3-70b-instruct:free
LLM_FAST_MODEL=google/gemma-3-27b-it:free
LLM_INTENT_MODEL=meta-llama/llama-3.3-70b-instruct:free
LLM_PLANNER_MODEL=meta-llama/llama-3.3-70b-instruct:free
LLM_AGENT_MODEL=meta-llama/llama-3.3-70b-instruct:free
LLM_HYDE_MODEL=meta-llama/llama-3.3-70b-instruct:free
LLM_EXTRACTION_MODEL=arcee-ai/trinity-large-preview:free
LLM_COMMUNITY_MODEL=arcee-ai/trinity-large-preview:free
LLM_FALLBACK_INTENT=arcee-ai/trinity-large-preview:free
LLM_FALLBACK_AGENT=arcee-ai/trinity-large-preview:free
LLM_LITE_MODEL=google/gemma-3-27b-it:free
LLM_CHUNKING_MODEL=arcee-ai/trinity-large-preview:free
```

### Bases de Données
```bash
# Pinecone
PINECONE_URL=https://sota-rag-cohere-1024-a4mkzmz.svc.aped-4627-b74a.pinecone.io
PINECONE_API_KEY=***REDACTED***

# PostgreSQL (local)
DB_TYPE=postgresdb
DB_POSTGRESDB_HOST=postgres
DB_POSTGRESDB_PORT=5432
DB_POSTGRESDB_DATABASE=n8n
DB_POSTGRESDB_USER=n8n
DB_POSTGRESDB_PASSWORD=***REDACTED***

# Supabase (externe)
SUPABASE_URL=https://ayqviqmxifzmhphiqfmj.supabase.co
SUPABASE_API_KEY=***REDACTED***
SUPABASE_PASSWORD=***REDACTED***

# Neo4j
NEO4J_URL=https://38c949a2.databases.neo4j.io/db/neo4j/query/v2

# Redis
QUEUE_BULL_REDIS_HOST=redis
QUEUE_BULL_REDIS_PORT=6379
```

### Embeddings & Reranking
```bash
EMBEDDING_API_URL=https://api.cohere.com/v2/embed
EMBEDDING_MODEL=embed-english-v3.0
EMBEDDING_DIM=1024
EMBEDDING_DIMS=1024
RERANKER_API_URL=https://api.cohere.ai/v1/rerank
RERANKER_MODEL=rerank-multilingual-v3.0

COHERE_API_URL=https://api.cohere.ai/v1/rerank
COHERE_API_KEY=***REDACTED***
COHERE_API_KEY_BACKUP=***REDACTED***
```

### Workflow IDs (pour Orchestrator)
```bash
WF2_GRAPH_RAG_ID=Vxm4TDdOLdb7j3Jy
WF3_ULTIMATE_RAG_ID=M12n4cmiVBoBusUe
WF4_QUANTITATIVE_RAG_ID=nQnAJyT06NTbEQ3y
WF5_STANDARD_RAG_ID=M12n4cmiVBoBusUe
```

### Autres
```bash
HF_TOKEN=***REDACTED***
JINA_API_KEY=***REDACTED***
UNSTRUCTURED_API_URL=https://api.unstructuredapp.io/general/v0/general
```

---

## 📊 Workflows Migrés (13/13)

### Pipelines Principaux (4)

| Workflow | ID | Statut | Description |
|----------|-----|--------|-------------|
| Standard RAG V3.4 | M12n4cmiVBoBusUe | ✅ Actif | RAG vectoriel avec Pinecone |
| Graph RAG V3.3 | Vxm4TDdOLdb7j3Jy | ✅ Actif | RAG graphe avec Neo4j |
| Quantitative RAG V2.0 | nQnAJyT06NTbEQ3y | ✅ Actif | RAG SQL sur données financières |
| Orchestrator V10.1 | P1no6VZkNtnRdlBi | ✅ Actif | Route vers les 3 pipelines |

### Workflows Support (9)

| Workflow | ID | Statut | Description |
|----------|-----|--------|-------------|
| Ingestion V3.1 | 6lPMHEYyWh1v34ro | ✅ Actif | Ingestion de documents |
| Enrichissement V3.1 | KXnQKuKw8ZUbyZUl | ✅ Actif | Enrichissement des données |
| Feedback V3.1 | cMlr32Qq7Sgy6Xq8 | ✅ Actif | Boucle de feedback |
| Benchmark V3.0 | tygzgU4i67FU6vm2 | ✅ Actif | Benchmarks automatiques |
| Dataset Ingestion Pipeline | S4FFbvx9Mn7DRkgk | ✅ Actif | Ingestion datasets HF |
| Monitoring & Alerting | xFAcxnFS5ISnlytH | ✅ Actif | Monitoring des workflows |
| Orchestrator Tester | R0HRiLQmL3FoCNKg | ✅ Actif | Tests de l'orchestrateur |
| RAG Batch Tester | k7jHXRTypXAQOreJ | ✅ Actif | Tests batch RAG |
| SQL Executor Utility | Dq83aCiXCfymsgCV | ✅ Actif | Exécution SQL utilitaire |

**Total: 13 workflows importés et activés**

---

## 🔄 Modification Critique: $vars → $env

### Problème
En n8n self-hosted **gratuit**, les variables `$vars.VAR_NAME` (feature Enterprise) ne fonctionnent pas. Elles nécessitent une licence payante.

### Solution
Tous les workflows ont été convertis pour utiliser `$env.VAR_NAME` qui lit les **variables d'environnement Docker** (gratuit et illimité).

### Exemple de Conversion
```javascript
// AVANT (n8n Cloud - licence Enterprise)
"url": "={{ $vars.OPENROUTER_BASE_URL }}"
"value": "=Bearer {{ $vars.OPENROUTER_API_KEY }}"

// APRÈS (n8n Docker - gratuit)
"url": "={{ $env.OPENROUTER_BASE_URL }}"
"value": "=Bearer {{ $env.OPENROUTER_API_KEY }}"
```

---

## 🔌 API Key n8n

**Nouvelle API Key (générée le 2026-02-12):**
```
eyJ***REDACTED***
```

Cette clé est sauvegardée dans:
- `/home/termius/mon-ipad/.env.local`
- `/home/termius/.kimi/mcp.json`

---

## 🚀 Commandes de Gestion

### Démarrer n8n
```bash
cd ~/n8n
docker-compose up -d
```

### Arrêter n8n
```bash
cd ~/n8n
docker-compose down
```

### Voir les logs
```bash
cd ~/n8n
docker-compose logs -f n8n
```

### Redémarrer complètement
```bash
cd ~/n8n
docker-compose down
docker-compose up -d
```

### Accès direct PostgreSQL
```bash
docker exec -it n8n_postgres_1 psql -U n8n -d n8n
```

### Accès direct Redis
```bash
docker exec -it n8n_redis_1 redis-cli
```

---

## 🧪 Tests Post-Migration

### Test 1: Vérifier que n8n répond
```bash
curl http://localhost:5678/health
# Doit retourner: {"status":"ok"}
```

### Test 2: Lister les workflows
```bash
curl -s "http://localhost:5678/api/v1/workflows" \
  -H "X-N8N-API-KEY: $N8N_API_KEY" | jq '.data[].name'
```

### Test 3: Tester un webhook
```bash
curl -X POST "http://localhost:5678/webhook/rag-multi-index-v3" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the capital of France?"}'
```

### Test 4: Exécution Python
```bash
cd /home/termius/mon-ipad
python3 eval/quick-test.py --questions 1 --pipeline standard
```

---

## 🔧 Configuration MCP Servers

Les MCP servers sont configurés dans `/home/termius/.kimi/mcp.json`:

- **jina-embeddings** - Embeddings et Pinecone CRUD
- **pinecone** - Pinecone officiel (@pinecone-database/mcp)
- **neo4j** - Requêtes Cypher
- **n8n** - Gestion workflows (API key mise à jour)
- **huggingface** - Recherche modèles/datasets
- **cohere** - Embeddings et reranking
- **supabase** - Requêtes SQL directes

**Note:** Kimi Code CLI ne peut pas utiliser les MCP comme outils natifs. Utiliser les fonctions Python à la place.

---

## ⚠️ Points d'Attention

### 1. Orchestrator
L'orchestrator a été corrigé pour pointer vers les bons sous-workflows:
- Invoke WF5: Standard → M12n4cmiVBoBusUe
- Invoke WF2: Graph → Vxm4TDdOLdb7j3Jy
- Invoke WF4: Quantitative → nQnAJyT06NTbEQ3y

### 2. PostgreSQL
PostgreSQL est maintenant inclus en local pour:
- Persistance des données n8n (exécutions, credentials)
- Possibilité de créer des tables pour les workflows Quantitative

### 3. Redis
Redis est utilisé pour:
- Cache des exécutions
- Gestion des files d'attente (queue)
- Session store

### 4. Sauvegardes
Les données persistent dans:
- `./data/` - Données n8n
- `./postgres-data/` - Base PostgreSQL
- `./redis-data/` - Cache Redis

**IMPORTANT:** Sauvegarder régulièrement ces dossiers!

---

## 📈 Prochaines Étapes Recommandées

1. **Tester les workflows** via l'UI n8n
2. **Vérifier les connexions** aux BDD externes (Supabase, Neo4j, Pinecone)
3. **Configurer les backups** automatiques des données Docker
4. **Mettre en place** le monitoring (Grafana/Prometheus)
5. **Documenter** les nouveaux endpoints/webhooks
6. **Mettre à jour** les scripts Python (eval/) avec les nouveaux IDs

---

## 🆘 Dépannage

### Problème: "No item to return was found" (erreur 500)
**Cause:** Le workflow ne trouve pas de nœud de réponse.  
**Solution:** Vérifier que le workflow a un nœud "Respond to Webhook" ou équivalent.

### Problème: "Cannot publish workflow: Node references workflow which is not published"
**Cause:** L'orchestrator fait référence à un sous-workflow inexistant.  
**Solution:** Vérifier les IDs dans les nœuds "Execute Workflow".

### Problème: "Unauthorized" sur l'API
**Cause:** API Key invalide ou expirée.  
**Solution:** Générer une nouvelle clé dans Settings → API.

### Problème: "Your license does not allow for feat:variables"
**Cause:** Les workflows utilisent encore `$vars` au lieu de `$env`.  
**Solution:** Convertir `$vars.VAR_NAME` en `$env.VAR_NAME`.

---

## 📝 Historique des Modifications

| Date | Action | Détail |
|------|--------|--------|
| 2026-02-12 | Création docker-compose | Configuration initiale avec Redis |
| 2026-02-12 | Ajout PostgreSQL | Base de données pour n8n et workflows |
| 2026-02-12 | Migration workflows | 13 workflows importés depuis n8n Cloud |
| 2026-02-12 | Conversion $vars→$env | Tous les workflows convertis pour compatibilité gratuite |
| 2026-02-12 | Correction orchestrator | Liaison des sous-workflows corrigée |
| 2026-02-12 | Création documentation | Ce document |

---

## ✅ Checklist Migration Complète

- [x] VM Google Cloud configurée
- [x] Docker et docker-compose installés
- [x] n8n déployé avec Docker
- [x] PostgreSQL déployé et configuré
- [x] Redis déployé et configuré
- [x] 54 variables d'environnement configurées
- [x] 13 workflows importés
- [x] Workflows convertis ($vars → $env)
- [x] Orchestrator corrigé et activé
- [x] API Key générée et sauvegardée
- [x] MCP config mise à jour
- [x] Documentation créée
- [x] Push GitHub effectué

---

## 📞 Support

En cas de problème:
1. Vérifier les logs: `docker-compose logs -f n8n`
2. Consulter ce document
3. Vérifier la connectivité: `curl http://localhost:5678/health`
4. Redémarrer les services: `docker-compose restart`

---

**Fin du document** - Migration réussie! 🎉
