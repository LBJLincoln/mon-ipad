# n8n Workflow Modifications for Website Artifacts

## Objectif

Enrichir les reponses des workflows n8n pour alimenter le panneau **Artifacts** du site web (sidebar droite type claude.ai).

Actuellement, les workflows retournent : `{ response, sources?, confidence? }`
Le site web a besoin de donnees supplementaires pour les onglets **Pipeline** et **Metriques**.

---

## Schema de reponse enrichi (cible)

```json
{
  "response": "La reponse textuelle...",
  "sources": [
    {
      "title": "Document XYZ",
      "content": "Extrait pertinent du document...",
      "score": 0.92,
      "metadata": {
        "source_db": "pinecone",
        "chunk_id": "abc-123",
        "page": 4
      }
    }
  ],
  "confidence": 0.87,

  "_pipeline": {
    "selected": "standard|graph|quantitative",
    "reason": "Question factuelle detectee, pipeline standard optimal",
    "databases_queried": ["pinecone", "neo4j", "supabase"],
    "execution_time_ms": 3200
  },

  "_metrics": {
    "tokens_input": 450,
    "tokens_output": 280,
    "retrieval_count": 12,
    "reranked_count": 4,
    "model": "arcee-ai/trinity-large-preview:free",
    "latency_breakdown": {
      "classification": 120,
      "retrieval": 1800,
      "generation": 1200,
      "total": 3200
    }
  },

  "_trace": [
    { "node": "Webhook", "status": "ok", "duration_ms": 5 },
    { "node": "Classifier", "status": "ok", "duration_ms": 120 },
    { "node": "Vector Search", "status": "ok", "duration_ms": 800 },
    { "node": "Reranker", "status": "ok", "duration_ms": 400 },
    { "node": "LLM Generation", "status": "ok", "duration_ms": 1200 },
    { "node": "Response Formatter", "status": "ok", "duration_ms": 50 }
  ]
}
```

---

## Modifications par workflow

### 1. Orchestrator (ID: workflow a identifier)
**Webhook**: `/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0`

**Ajouter un noeud "Response Enricher" avant le noeud de sortie** :
- Collecte le nom du pipeline selectionne depuis le Classifier
- Ajoute `_pipeline.selected` et `_pipeline.reason`
- Ajoute `_pipeline.databases_queried` selon le pipeline
- Calcule `_pipeline.execution_time_ms` (timestamp fin - timestamp debut)

### 2. Standard Pipeline
**Webhook**: `/webhook/rag-multi-index-v3`

**Modifier le noeud de sortie** pour inclure :
- `_metrics.retrieval_count` : nombre de chunks retournes par Pinecone
- `_metrics.reranked_count` : nombre apres reranking
- `_trace` : status de chaque noeud traverse

### 3. Graph Pipeline
**Webhook**: `/webhook/ff622742-...`

**Modifier le noeud de sortie** pour inclure :
- `_metrics.retrieval_count` : nombre d'entites Neo4j traversees
- `_pipeline.databases_queried`: ["neo4j", "supabase"]
- `_trace` avec les noeuds specifiques graph (Cypher Query, Entity Resolution, etc.)

### 4. Quantitative Pipeline
**Webhook**: `/webhook/3e0f8010-...`

**Modifier le noeud de sortie** pour inclure :
- `_metrics` avec les metriques de calcul
- `_pipeline.databases_queried`: ["supabase"]

---

## Implementation cote site web

Le fichier `src/lib/parseResponse.ts` doit etre mis a jour pour extraire ces nouveaux champs :

```typescript
// Dans parseN8nResponse():
const pipeline = data._pipeline ?? null
const metrics = data._metrics ?? null
const trace = data._trace ?? null
```

Le `RightSidebar.tsx` (panneau Artifacts) est deja prepare avec 3 onglets :
- **Sources** : fonctionne deja
- **Pipeline** : actuellement hardcode, a connecter a `_pipeline`
- **Metriques** : actuellement placeholder, a connecter a `_metrics`

---

## Priorite d'implementation

1. **Phase 1** (immediat) : Ajouter `_pipeline.selected` dans l'Orchestrator
2. **Phase 2** : Ajouter `_metrics.execution_time_ms` et `_trace` basique
3. **Phase 3** : Ajouter `_metrics` complet (tokens, latency_breakdown)

Les champs prefixes par `_` sont optionnels — le site fonctionne sans eux mais affiche des placeholders.
