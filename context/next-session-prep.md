# Préparation Next Session - SOTA 2026

**Date de création:** 2026-02-12  
**Status:** Données Phase 2 vérifiées et prêtes

---

## ✅ État des Bases de Données (Vérifié)

### Supabase (PostgreSQL)
**Workflow de test:** `BENCHMARK - SQL Executor Utility` (ID: `3O2xcKuloLnZB5dH`)  
**Webhook:** `POST /webhook/benchmark-sql-exec`

#### Tables Phase 2 confirmées présentes:
| Table | Lignes | Status |
|-------|--------|--------|
| `finqa_tables` | 200 | ✅ |
| `tatqa_tables` | 150 | ✅ |
| `convfinqa_tables` | 100 | ✅ |
| **Total Phase 2** | **450** | ✅ |

#### Exemple de requête SQL (fonctionnel):
```bash
curl -X POST "https://amoret.app.n8n.cloud/webhook/benchmark-sql-exec" \
  -H "Content-Type: application/json" \
  -d '{
    "sql": "SELECT table_name, COUNT(*) as rows FROM information_schema.tables t JOIN pg_stat_user_tables s ON t.table_name = s.relname WHERE t.table_schema = '"'"'public'"'"' GROUP BY table_name ORDER BY rows DESC",
    "tenant_id": "benchmark"
  }'
```

### Pinecone (Vector DB)
**Dimension:** 1024 (✅ Migration Cohere EFFECTUÉE - Index: sota-rag-cohere-1024)  
**Total vectors:** 10,411

#### Namespaces confirmés:
| Namespace | Vectors | Dataset |
|-----------|---------|---------|
| `benchmark-squad_v2` | 1,000 | Phase 1 |
| `benchmark-triviaqa` | 1,000 | Phase 1 |
| `benchmark-hotpotqa` | 1,000 | Phase 1+2 |
| `benchmark-finqa` | 500 | Phase 2 |
| `benchmark-msmarco` | 1,000 | Phase 1+2 |
| ... | ... | ... |
| **Total** | **10,411** | ✅ |

### Neo4j (Graph DB)
**Status:** Connecté et fonctionnel (testé via Graph RAG workflow)

#### Métriques confirmées:
- Total nodes: ~19,788
- Total relationships: ~21,625
- Labels: Person, Organization, Entity, City, Event, etc.

---

## 🔧 MCP Servers Status

### MCP Actif
| Server | Fichier | Status |
|--------|---------|--------|
| **jina-embeddings** | `mcp/jina-embeddings-server.py` | ✅ Prêt |

### Configuration MCP (`.claude/settings.json`)
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

### MCP Recommandés pour installation
Voir `docs/technical/mcp-setup.md` pour:
- **Neo4j MCP** (officiel): `neo4j-mcp` binary
- **Pinecone MCP** (officiel): `npx @pinecone-database/mcp`
- **n8n MCP** (communauté): `npm install -g @leonardsellem/n8n-mcp-server`
- **Supabase MCP** (officiel): Mode HTTP direct

---

## 📋 Commandes pour Next Session

### 1. Démarrage de session (OBLIGATOIRE)
```bash
cd /home/termius/mon-ipad

# Export credentials (copier depuis CLAUDE.md ou credentials.md)
export N8N_HOST="https://amoret.app.n8n.cloud"
export N8N_API_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
export PINECONE_API_KEY="pcsk_6GzVdD_BbHsYNvpcngMqAHH5EvEa9XLnmFpEK9cx5q5xkMp72z5KFQ1q7dEjp8npWhJGBY"
export PINECONE_HOST="https://sota-rag-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
export OPENROUTER_API_KEY="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"
export SUPABASE_PASSWORD="udVECdcSnkMCAPiY"
export NEO4J_PASSWORD="jV_zGdxbu-emQZM-ZSQux19pTZ5QLKejR2IHSzsbVak"

# Lancer le setup de session
python3 scripts/session-start.py
```

### 2. Vérification rapide des données
```bash
# Supabase - utiliser le SQL Executor existant
curl -X POST "https://amoret.app.n8n.cloud/webhook/benchmark-sql-exec" \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT COUNT(*) FROM finqa_tables", "tenant_id": "benchmark"}'

# Pinecone
curl -X POST "https://sota-rag-a4mkzmz.svc.aped-4627-b74a.pinecone.io/describe_index_stats" \
  -H "Api-Key: $PINECONE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{}'
```

### 3. Tests pipelines
```bash
# Quick test (5 questions)
python3 eval/quick-test.py --questions 5 --pipeline standard

# Fast iteration (10 questions)
python3 eval/fast-iter.py --questions 10 --label "test-session-$(date +%Y%m%d)"

# Node analysis
python3 eval/node-analyzer.py --pipeline standard --last 5
```

---

## 🎯 Priorités Next Session

### URGENT (Phase 1 Gates)
1. **Standard Pipeline**: 0% accuracy (target: 85%)
   - Problème: Non testé récemment, probablement cassé
   - Action: Test 1/1 → analyse node → fix

2. **Quantitative Pipeline**: 0% accuracy (target: 85%)
   - Problème: Erreur Init node (validation `query` field)
   - Action: Déboguer node "Init & ACL"

3. **Orchestrator Pipeline**: 0% accuracy (target: 70%)
   - Problème: Non testé récemment
   - Action: Test avec requête simple

### MOYEN (Phase 2 Preparation)
4. **Migration Cohere**: ✅ EFFECTUÉE
   - Index: sota-rag-cohere-1024 (10,411 vecteurs, 1024d)
   - Workflows n8n: Configurés correctement (EMBEDDING_MODEL=embed-english-v3.0)
   - Problème réel: Qualité HyDE / Pertinence des résultats (pas la dimension)

5. **MCP Servers**: Installer les MCP manquants
   - Action: Suivre `docs/technical/mcp-setup.md`

### BAS (Future)
6. **Migration n8n self-hosted**: VM Oracle Cloud
   - Action: Lancer `scripts/n8n-oracle-setup.sh`

---

## 📁 Fichiers Importants

| Fichier | Description |
|---------|-------------|
| `CLAUDE.md` | Point de départ de session |
| `docs/technical/credentials.md` | Clés API et credentials |
| `docs/status.json` | Métriques live des pipelines |
| `context/session-state.md` | État de la dernière session |
| `context/workflow-process.md` | Processus d'itération |
| `docs/technical/mcp-setup.md` | Configuration MCP servers |
| `phases/overview.md` | Stratégie des 5 phases |

---

## ⚠️ Points d'Attention

1. **SQL Executor**: Utiliser le workflow existant `BENCHMARK - SQL Executor Utility` (testé et fonctionnel) plutôt que des solutions custom

2. **Dimensions Embeddings**: 
   - ✅ MIGRATION EFFECTUÉE: 1024d (Cohere embed-english-v3.0)
   - Index actif: sota-rag-cohere-1024
   - Index legacy: sota-rag (1536d, conservé en backup)
   - Impact: Les requêtes HyDE peuvent ne pas matcher correctement

3. **n8n Cloud**:
   - Expiration API Key: 2026-02-21
   - Coût: ~20€/mois
   - Alternative: Self-hosted sur Oracle (gratuit)

4. **Phase 2 Ready**:
   - Données: ✅ Toutes présentes
   - Gates Phase 1: ❌ Non passés (3/4 pipelines < target)
   - Blocker: Doit passer Phase 1 avant Phase 2

---

*Document créé automatiquement - Dernière mise à jour: 2026-02-12*
