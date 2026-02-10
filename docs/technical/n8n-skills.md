# n8n Community Skills & Repos à Télécharger

> **Ce fichier DOIT être mis à jour** après chaque découverte de nœud ou template utile.
> Dernière mise à jour : 2026-02-10

---

## Repos GitHub officiels n8n

| Repo | Contenu | URL |
|------|---------|-----|
| **n8n-io/n8n** | Code source n8n | `https://github.com/n8n-io/n8n` |
| **n8n-io/n8n-nodes-langchain** | Nœuds LangChain (RAG, embeddings, etc.) | `https://github.com/n8n-io/n8n-nodes-langchain` |
| **n8n-io/n8n-docs** | Documentation officielle | `https://github.com/n8n-io/n8n-docs` |

---

## Templates communautaires utiles pour le projet

### RAG & LLM
| Template | Description | Source |
|----------|-------------|--------|
| **AI Agent with RAG** | Agent LLM avec retrieval Pinecone/Weaviate | n8n templates gallery |
| **Multi-source RAG** | RAG combinant plusieurs bases vectorielles | n8n community |
| **SQL Agent** | Génération SQL depuis langage naturel | n8n templates |
| **Graph RAG** | Extraction d'entités + Neo4j | Custom (notre projet) |

### Nœuds communautaires à installer (n8n self-hosted)

```bash
# Dans le dossier n8n Docker
cd ~/.n8n

# Pinecone (natif dans n8n >= 1.20)
# Pas besoin d'installer, utiliser le nœud "Pinecone Vector Store"

# Neo4j
npm install n8n-nodes-neo4j

# Supabase (natif dans n8n >= 1.15)
# Utiliser le nœud "Supabase" natif

# HuggingFace Inference
npm install n8n-nodes-huggingface

# Redis (pour cache)
# Natif dans n8n >= 1.18, nœud "Redis"
```

---

## Nœuds n8n natifs utilisés dans nos workflows

| Nœud | Usage dans le projet | Pipeline |
|------|---------------------|----------|
| **HTTP Request** | Appels OpenRouter, webhooks | Tous |
| **Code (JavaScript)** | Logique custom, routing, parsing | Tous |
| **Webhook** | Points d'entrée des pipelines | Tous |
| **Respond to Webhook** | Retour des réponses | Tous |
| **If** | Routing conditionnel | Orchestrator |
| **Switch** | Multi-routing | Orchestrator |
| **Merge** | Fusion des résultats | Orchestrator |
| **Set** | Transformation de données | Tous |
| **Pinecone Vector Store** | Recherche vectorielle | Standard |
| **Embeddings** | Génération d'embeddings | Standard |

---

## Techniques avancées n8n

### 1. Sub-workflows (Orchestrator pattern)
```
Orchestrator → Execute Workflow → Pipeline spécifique
```
- Permet de découpler les pipelines
- Chaque sous-workflow a son propre webhook
- L'orchestrateur route via HTTP Request vers les webhooks

### 2. Error handling avec continueOnFail
```javascript
// Dans un nœud Code, gérer l'erreur du nœud précédent
const items = $input.all();
for (const item of items) {
    if (item.json.error) {
        // Fallback logic
        item.json.answer = "Unable to process";
        item.json.confidence = 0;
    }
}
return items;
```

### 3. Variables dynamiques
```javascript
// Accéder aux variables n8n dans un nœud Code
const embeddingModel = $vars.EMBEDDING_MODEL;
const apiKey = $vars.OPENROUTER_API_KEY;
```

### 4. Webhook avec timeout custom
```javascript
// Dans le nœud Webhook, paramètre responseTimeoutMs
// Par défaut 30000 (30s), augmenter pour les pipelines lents
"responseTimeoutMs": 120000
```

---

## Ressources en ligne

- **n8n Docs** : https://docs.n8n.io
- **n8n Community** : https://community.n8n.io
- **n8n Templates** : https://n8n.io/workflows
- **n8n API Reference** : https://docs.n8n.io/api/
- **LangChain nodes** : https://docs.n8n.io/integrations/builtin/cluster-nodes/root-nodes/n8n-nodes-langchain/
