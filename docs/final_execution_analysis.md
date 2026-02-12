# Analyse Finale des Exécutions N8n - Référence pour Tests

**Date d'analyse:** 2026-02-12  
**Exécutions analysées:**
- Standard RAG (fonctionne): ID#19404
- Quantitative RAG (fonctionne): ID#19326
- Orchestrator RAG (fonctionne): ID#19323
- Graph RAG (semi-échoué): ID#19305

---

## 1. FORMAT EXACT DES QUERIES WEBHOOK

### 1.1 Standard RAG (WF5)
**Endpoint:** `POST https://amoret.app.n8n.cloud/webhook/rag-multi-index-v3`

**Format minimal requis:**
```json
{
  "question": "What is the capital of Japan?"
}
```

**Format complet accepté:**
```json
{
  "question": "string",
  "tenant_id": "string (optional, default: 'default')",
  "top_k": "number (optional, default: 10)",
  "user_context": {
    "groups": ["admin", "guest"]
  }
}
```

**Réponse attendue:**
```json
{
  "answer": "string",
  "sources": [...],
  "trace_id": "string"
}
```

---

### 1.2 Graph RAG (WF2)
**Endpoint:** `POST https://amoret.app.n8n.cloud/webhook/ff622742-6d71-4e91-af71-b5c666088717`

**Format minimal requis:**
```json
{
  "query": "What disease is caused by mosquitoes?"
}
```

**Format complet (benchmark):**
```json
{
  "query": "string",
  "tenant_id": "benchmark",
  "top_k": 10,
  "include_sources": true,
  "benchmark_mode": true
}
```

---

### 1.3 Orchestrator (WF1)
**Endpoint:** `POST https://amoret.app.n8n.cloud/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0`

**Format requis:**
```json
{
  "query": "What is the capital of Japan?",
  "tenant_id": "benchmark",
  "top_k": 10,
  "include_sources": true,
  "benchmark_mode": true
}
```

**Paramètres importants:**
- `query`: La question principale (obligatoire)
- `tenant_id`: Identifiant du tenant (défaut: "default")
- `top_k`: Nombre de résultats à récupérer
- `include_sources`: Inclure les sources dans la réponse
- `benchmark_mode`: Mode benchmark pour les métriques

---

### 1.4 Quantitative RAG (WF4)
**Endpoint:** Appelé UNIQUEMENT via l'orchestrator (pas de webhook public)

**Format d'entrée depuis l'orchestrator:**
```json
{
  "query": "Retrieve TechVision Inc's total revenue for 2023",
  "original_query": "What was TechVision Inc's total revenue in 2023?",
  "task_id": 1,
  "intent_id": "intent-1",
  "rag_called": "QUANTITATIVE",
  "user_context": {
    "tenant_id": "benchmark",
    "groups": ["default"]
  },
  "topK": 20
}
```

---

## 2. SNAPSHOTS FINAUX - WORKFLOWS FONCTIONNELS

### 2.1 Standard RAG V3.4 (ID#19404)

**Workflow:** TEST - SOTA 2026 - WF5 Standard RAG V3.4 - CORRECTED  
**Status:** ✅ SUCCESS (7.923s)  
**18 nodes exécutés**

**Pipeline de données:**
```
Webhook → Init & ACL → Needs Decomposition? → Query Decomposer → Query Merger 
→ HyDE Generator → HyDE Embedding → HTTP Pinecone Query HyDE (parallèle)
→ Original Embedding → HTTP Pinecone Query Original (parallèle)
→ Wait All Branches → RRF Merge & Rank → Cohere Reranker → Rerank Merger
→ Skip LLM? → LLM Generation → Response Formatter
```

**Points clés de fonctionnement:**
- **Query Decomposer:** Détecte si la question est simple (`is_simple: true`)
- **HyDE Generator:** Crée un document hypothétique pertinent
- **Double embedding:** HyDE + Original query en parallèle
- **RRF Merge:** Fusion des résultats HyDE et Original
- **Cohere Reranker:** Re-classement des documents

**Résultat Pinecone HyDE (pertinent):**
```json
{
  "matches": [
    {
      "id": "wikihop-00015-7238f5cc-chunk-0",
      "score": 0.648,
      "metadata": {
        "content": "WikiHop Query: capital :: Japan\nAnswer: Tokyo"
      }
    }
  ]
}
```

**Tokens LLM:**
- Query Decomposer: 212 tokens (154 prompt, 58 completion)
- HyDE Generator: 90 tokens (42 prompt, 48 completion)
- LLM Generation: ~200 tokens

---

### 2.2 Quantitative RAG V2.0 (ID#19326)

**Workflow:** TEST - SOTA 2026 - WF4 Quantitative V2.0  
**Status:** ✅ SUCCESS (33.301s)  
**12 nodes exécutés**

**Pipeline de données:**
```
When Executed by Another Workflow → Init & ACL → Schema Introspection 
→ Schema Context Builder → Prepare SQL Request → Text-to-SQL Generator 
→ SQL Validator → SQL Executor → Result Aggregator 
→ Prepare Interpretation Request → Interpretation Layer → Response Formatter
```

**Points clés de fonctionnement:**
- **Schema Introspection:** Récupère 90 colonnes de métadonnées (balance_sheet, employees, financials, products, sales_data)
- **Text-to-SQL Generator:** Génère la requête SQL avec CoT (25.6s - le plus lent)
- **SQL Validator:** Vérifie la syntaxe et la sécurité
- **Interpretation Layer:** Transforme les résultats SQL en réponse naturelle (6.9s)

**Exemple de requête générée:**
```sql
SELECT revenue FROM financials 
WHERE company_name = 'TechVision Inc' 
AND fiscal_year = 2023
```

**Input depuis orchestrateur:**
```json
{
  "query": "Retrieve TechVision Inc's total revenue for 2023",
  "original_query": "What was TechVision Inc's total revenue in 2023?",
  "route_to": "QUANTITATIVE",
  "task_id": 1
}
```

---

### 2.3 Orchestrator V10.1 (ID#19323)

**Workflow:** V10.1 orchestrator copy  
**Status:** ✅ SUCCESS (62.204s)  
**43 nodes exécutés**

**Pipeline de données:**
```
Webhook V8 → Input Merger → Init V8 Security → Postgres/RDMS Memory + Redis Fetch
→ Redis Failure Handler → Rate Limit Guard → Memory Merger → Context Compression
→ Advanced Guardrails → Query Classifier → Query Router → Cache Semantic Search
→ Redis Cache + Generator → Cache Parser → IF Cache Hit? → LLM Intent Analyzer
→ Intent Parser → Postgres Init Tasks → Format & Dispatch → Postgres Insert Tasks
→ Postgres Get Current Tasks → Execution Engine → Dynamic Switch 
→ [INVOKE SUB-WORKFLOW: Standard/Graph/Quantitative] → Task Result Handler
→ Postgres Update Task → Fallback Monitor → Task Status Aggregator 
→ Response Builder → Execution Summary → Redis Store + Postgres Update Context
→ Cache Storage → Output Router → Return Response
```

**Points clés de fonctionnement:**
- **Intent Analyzer (30.2s):** Détermine le type de requête et le RAG approprié
- **Cache Check:** Vérifie si une réponse similaire existe déjà
- **Task System:** Crée des tâches dans Postgres pour chaque intent
- **Dynamic Switch:** Route vers le sous-workflow approprié (STANDARD/GRAPH/QUANTITATIVE)
- **Fallback Monitor:** Gère les échecs et les tentatives

**Exemple de classification d'intent:**
```json
{
  "intents": [
    {
      "id": "intent-1",
      "description": "Find the capital city of Japan",
      "type": "FACTUAL",
      "suggested_rag": "STANDARD",
      "priority": 1
    }
  ],
  "complexity": "SIMPLE",
  "has_parallel_intents": false
}
```

**Invocation sous-workflow Standard:**
```json
{
  "trace_id": "trace-1770728480585-y0k96j",
  "query": "Find the capital city of Japan",
  "rag_called": "STANDARD",
  "task_id": 1
}
```

---

## 3. ANALYSE DU GRAPH RAG - PROBLÈME IDENTIFIÉ

### 3.1 Résumé du problème

**Workflow:** TEST - SOTA 2026 - WF2 Graph RAG V3.3 - CORRECTED  
**Status:** ⚠️ SEMI-ÉCHEC (36.514s)  
**Question:** "What disease is caused by mosquitoes?"  
**21 nodes exécutés**

### 3.2 Le problème: Dissonance embedding ↔ documents retrieved

**🔴 PROBLÈME CRITIQUE:** Les embeddings retrieved par Pinecone n'ont **STRICTEMENT RIEN À VOIR** avec la question initiale.

#### Chaîne de traitement:

**1. Question initiale:**
```
"What disease is caused by mosquitoes?"
```

**2. HyDE Generator (33.6s) - ✅ CORRECT:**
Le LLM génère un document hypothétique pertinent sur les maladies transmises par les moustiques:
```
"Mosquitoes are responsible for transmitting several serious diseases to humans, 
with malaria being one of the most well-known and deadly... [Dengue, Zika, 
West Nile, Chikungunya, Yellow fever]"
```

**3. Embedding généré (192ms) - ✅ CORRECT:**
Embedding 768-dimensions généré à partir du texte HyDE.

**4. Pinecone HyDE Search (615ms) - 🔴 ÉCHEC:**
**Résultats retournés:**
```json
{
  "matches": [
    {
      "id": "climate-00018-1a18d37c-chunk-0",
      "score": 0.346,
      "metadata": {
        "content": "Climate Claim: Climate change affects human health."
      }
    },
    {
      "id": "msmarco-00004-14493533-chunk-0", 
      "score": 0.315,
      "metadata": {
        "content": "Query: how do vaccines work"
      }
    },
    {
      "id": "msmarco-00003-772fa031-chunk-0",
      "score": 0.300,
      "metadata": {
        "content": "Query: what is the function of the liver"
      }
    },
    {
      "id": "stratqa-00020-c71a9ab9-chunk-0",
      "score": 0.292,
      "metadata": {
        "content": "Question: Can you actually catch a cold from being in cold weather?"
      }
    }
  ]
}
```

**❌ AUCUN document sur les moustiques, le paludisme, ou les maladies vectorielles!**

**5. Neo4j Query (380ms) - 🔴 ÉCHEC:**
Les entités extraites du document HyDE (Mosquitoes, Malaria, Dengue, etc.) sont utilisées pour interroger Neo4j.  
**Résultat:** Des données sur "1964 Georgia Tech Yellow Jackets football team" - complètement hors sujet!

### 3.3 Diagnostic racine

| Composant | Statut | Problème |
|-----------|--------|----------|
| HyDE Generator | ✅ OK | Génère un document pertinent |
| Embedding Generator | ✅ OK | Crée un embedding valide |
| **Pinecone Index** | 🔴 **CRITIQUE** | **L'index ne contient pas de documents sur les maladies/moustiques** |
| **Neo4j Graph** | 🔴 **CRITIQUE** | **Les entités médicales n'existent pas dans le graphe** |
| Entity Extraction | ⚠️ Mineur | Extrait trop d'entités non pertinentes ("Other", "Caused", "Symptoms") |

### 3.4 Preuve du problème

**Question:** "What disease is caused by mosquitoes?"  
**Documents retrouvés:** Climate change, Vaccines, Liver function, Cold weather  
**Score max:** 0.346 (très faible - indique aucune correspondance pertinente)

**Comparaison avec Standard RAG (qui fonctionne):**
- Question: "What is the capital of Japan?"
- Document retrouvé: "WikiHop Query: capital :: Japan | Answer: Tokyo"
- Score: 0.714 (bonne correspondance)

### 3.5 Causes possibles

1. **Pinecone Index incomplet:** L'index vectoriel ne contient pas les documents médicaux/biologiques attendus
2. **Mauvais namespace/index:** Le workflow pourrait interroger le mauvais index Pinecone
3. **Problème de dimension:** L'embedding généré (768-dim) pourrait ne pas correspondre à l'index
4. **Données Neo4j incomplètes:** Le graphe ne contient pas les entités médicales nécessaires

### 3.6 Recommandations de correction

#### Priorité 1: Vérifier le Pinecone Index
```python
# Vérifier que l'index contient des documents médicaux
# Namespace utilisé par Graph RAG vs Standard RAG
```

#### Priorité 2: Vérifier les entités Neo4j
```cypher
// Vérifier si les entités médicales existent
MATCH (n) WHERE n.name CONTAINS 'malaria' OR n.name CONTAINS 'mosquito'
RETURN count(n)
```

#### Priorité 3: Améliorer l'extraction d'entités
- Filtrer les entités trop génériques ("Other", "Caused", "Symptoms")
- Ne garder que les entités nommées spécifiques

---

## 4. SPÉCIFICATIONS POUR LES SCRIPTS DE TEST

### 4.1 Format de requête recommandé

Pour tous les tests, utiliser ce format standardisé:

```python
test_payload = {
    "query": question,
    "tenant_id": "benchmark",
    "top_k": 10,
    "include_sources": True,
    "benchmark_mode": True
}
```

### 4.2 Mapping des endpoints

| Pipeline | Webhook Path | Workflow ID |
|----------|-------------|-------------|
| Standard | `/webhook/rag-multi-index-v3` | IgQeo5svGlIAPkBc |
| Graph | `/webhook/ff622742-6d71-4e91-af71-b5c666088717` | 95x2BBAbJlLWZtWEJn6rb |
| Quantitative | N/A (appel interne) | E19NZG9WfM7FNsxr |
| Orchestrator | `/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0` | ALd4gOEqiKL5KR1p |

### 4.3 Vérifications à implémenter

**Pour chaque exécution de test:**
1. Vérifier que `trigger_query` correspond à la question envoyée
2. Vérifier que les documents retrieved sont pertinents (score > 0.5)
3. Vérifier que la réponse contient une réponse et des sources
4. Mesurer la latence totale et par node

**Spécifiquement pour Graph RAG:**
```python
def check_graph_rag_relevance(execution_data, original_question):
    """Vérifie que les documents retrieved sont pertinents."""
    for node in execution_data['nodes']:
        if 'pinecone' in node['name'].lower():
            matches = node.get('full_output_data', [[]])[0][0]['json']['matches']
            for match in matches:
                content = match['metadata']['content'].lower()
                score = match['score']
                # Vérifier la pertinence
                if score < 0.4:
                    return False, f"Score trop faible: {score}"
    return True, "OK"
```

---

## 5. RÉFÉRENCES

**Fichiers sources:**
- `n8n_analysis_results/execution_19404.json` - Standard RAG
- `n8n_analysis_results/execution_19326.json` - Quantitative RAG  
- `n8n_analysis_results/execution_19323.json` - Orchestrator
- `n8n_analysis_results/execution_19305.json` - Graph RAG

**Workflow IDs (node-analyzer.py):**
```python
WORKFLOW_IDS = {
    "standard": "IgQeo5svGlIAPkBc",
    "graph": "95x2BBAbJlLWZtWEJn6rb",
    "quantitative": "E19NZG9WfM7FNsxr",
    "orchestrator": "ALd4gOEqiKL5KR1p",
}
```

---

*Document généré automatiquement à partir de l'analyse des exécutions n8n.*
