# Patterns SOTA 2026 Manquants - Complement au Document Principal

Ce document complete les specifications du fichier `n8n Multi-Tenant Document Workflows.docx`
avec les patterns RAG state-of-the-art 2025-2026 non couverts.

---

## 1. Agentic RAG (CRITIQUE)

**Concept**: Au lieu d'un pipeline RAG fixe, un agent IA decide dynamiquement
quelles sources interroger, quand re-formuler la requete, et quand le resultat est suffisant.

**Implementation n8n**:
- Utiliser le node `AI Agent` (LangChain) comme orchestrateur
- Sub-tools: Pinecone search, Neo4j Cypher, Supabase SQL, Web search
- L'agent decide quel outil utiliser selon la requete
- Pattern ReAct (Reasoning + Acting) integre dans le node Agent

```
User Query
    |
    v
[AI Agent Node] -- decides --> [Tool: Pinecone Search]
    |                          [Tool: Neo4j Cypher]
    |                          [Tool: SQL Query]
    |                          [Tool: Web Search]
    |
    v (iterates until satisfied)
[Final Answer]
```

**Nodes n8n requis**:
- `@n8n/n8n-nodes-langchain.agent` (AI Agent)
- `@n8n/n8n-nodes-langchain.toolWorkflow` (Sub-workflow as Tool)

---

## 2. Contextual Retrieval (Anthropic, 2024)

**Concept**: Avant l'embedding, ajouter un contexte explicatif a chaque chunk
en utilisant le document parent comme reference.

**Implementation n8n**:
```javascript
// Dans le workflow d'enrichissement, avant l'embedding
const contextualChunk = {
  original: chunk.text,
  context: await llm.generate(
    `Voici le document complet: ${document.fullText.substring(0, 5000)}
     Voici un extrait de ce document: ${chunk.text}
     Genere un contexte court (2-3 phrases) situant cet extrait dans le document.`
  ),
  enhanced_text: `${context}\n\n${chunk.text}` // Ceci est embeddé
};
```

**Impact**: +49% de precision de retrieval selon les benchmarks Anthropic.

---

## 3. Self-RAG / Corrective RAG (CRAG)

**Concept**: Le systeme evalue sa propre reponse et corrige si necessaire.

**Pipeline n8n**:
```
[Retrieval] -> [Generate Response] -> [Self-Evaluate]
                                          |
                                    [Score < threshold?]
                                     /              \
                              [Yes: Re-retrieve]   [No: Return]
                                     |
                              [Web Search / Expand Query]
                                     |
                              [Re-generate with new context]
```

**Implementation**: Code Node avec boucle de retry conditionnelle.

---

## 4. Reranking (CRITIQUE - partiellement present)

**Concept**: Apres le retrieval initial (top-K), un modele de reranking
re-ordonne les resultats par pertinence reelle.

**Implementation n8n**:
```javascript
// Apres Pinecone search, avant la generation
const reranked = await httpRequest({
  url: "https://api.cohere.ai/v1/rerank",
  method: "POST",
  body: {
    model: "rerank-english-v3.0", // ou rerank-multilingual-v3.0
    query: userQuery,
    documents: retrievedChunks.map(c => c.text),
    top_n: 5
  }
});
```

**Alternatives**:
- Cohere Rerank v3 (recommande pour multilingual)
- Cross-encoder reranking via HuggingFace
- BGE Reranker via Ollama
- FlashRank (open-source, local)

---

## 5. RAPTOR (Recursive Abstractive Processing)

**Concept**: Creer un arbre hierarchique de resumes du corpus.
Les feuilles sont les chunks originaux, les noeuds intermediaires sont des
resumes de clusters de chunks, et la racine est un resume global.

**Implementation n8n**:
```
[Documents] -> [Chunk] -> [Cluster (KMeans)]
                              |
                        [Summarize each cluster]
                              |
                        [Re-cluster summaries]
                              |
                        [Store tree in Neo4j]
```

**Avantage**: Permet de repondre a des questions de haut niveau
("Quel est le theme principal?") et de bas niveau ("Quel est le montant exact?").

---

## 6. ColBERT / ColPali (Late Interaction)

**Concept**: Au lieu d'un seul vecteur par chunk, representer chaque token
individuellement. Le matching se fait token par token (MaxSim).

**Implementation n8n**: Necessite un service de serving ColBERT
(ex: RAGatouille, Vespa, ou API custom). Integration via HTTP Request node.

---

## 7. Observability (LangFuse / LangSmith / Arize)

**Concept**: Tracer chaque etape du pipeline RAG (retrieval, reranking,
generation) avec metriques de latence, qualite, et cout.

**Implementation n8n**:
```javascript
// Au debut de chaque workflow
const trace = await httpRequest({
  url: "https://cloud.langfuse.com/api/public/traces",
  method: "POST",
  body: {
    name: "rag-query",
    metadata: { tenant_id, workflow: "standard-rag" },
    input: { query: userQuery }
  }
});

// A chaque etape, creer un span
const span = await httpRequest({
  url: "https://cloud.langfuse.com/api/public/spans",
  method: "POST",
  body: {
    traceId: trace.id,
    name: "retrieval",
    input: { query: userQuery, topK: 10 },
    output: { chunks_found: results.length }
  }
});
```

**Nodes recommandes**: HTTP Request vers LangFuse API ou integration native
via n8n-nodes-langfuse (community node si disponible).

---

## 8. Late Chunking

**Concept**: Au lieu de chunker avant l'embedding, passer le document entier
dans le modele d'embedding (si la fenetre le permet) et extraire les
representations des chunks apres le passage dans le transformer.

**Avantage**: Chaque chunk conserve le contexte du document entier.

**Implementation**: Necessite un modele d'embedding supportant le late chunking
(ex: jina-embeddings-v3). Integration via HTTP Request node.

---

## 9. Speculative RAG

**Concept**: Generer d'abord un brouillon de reponse rapide (modele leger),
puis verifier/ameliorer avec un modele plus puissant.

**Implementation n8n**:
```
[Query] -> [Haiku: Draft Response] -> [Opus: Verify & Enhance]
                                           |
                                     [Draft OK?]
                                      /        \
                               [Yes: Return]  [No: Re-generate with Opus]
```

---

## Resume des Priorites d'Implementation

| Pattern | Priorite | Effort | Impact Qualite |
|---------|----------|--------|---------------|
| Reranking | P0 | Faible | +15-25% precision |
| Agentic RAG | P0 | Moyen | +30% flexibilite |
| Contextual Retrieval | P1 | Faible | +49% retrieval |
| Self-RAG/CRAG | P1 | Moyen | +20% fiabilite |
| Observability | P1 | Faible | Monitoring |
| RAPTOR | P2 | Eleve | +15% questions haut-niveau |
| ColBERT/ColPali | P2 | Eleve | +10% precision |
| Late Chunking | P3 | Moyen | +10% coherence |
| Speculative RAG | P3 | Faible | Optimisation cout |
