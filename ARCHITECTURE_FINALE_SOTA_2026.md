# Architecture Finale SOTA 2026 — Ingestion V4 & Enrichissement V4

> **Objectif** : Référence complète pour produire des patchs n8n JSON dans une session future.  
> Chaque nœud nouveau ou modifié est spécifié avec son `jsCode`, ses connexions, et sa position dans le DAG.

---

## TABLE DES MATIÈRES

1. [Vue d'ensemble des changements](#1-vue-densemble)
2. [Variables d'environnement ajoutées](#2-variables-denvironnement)
3. [Pipeline Ingestion V4 — Architecture cible](#3-ingestion-v4)
4. [Pipeline Enrichissement V4 — Architecture cible](#4-enrichissement-v4)
5. [Index des patchs](#5-index-des-patchs)

---

## 1. Vue d'ensemble

### Ingestion V3.1 → V4

```
ACTUEL (V3.1):
Webhook → Init Lock → Redis Lock → Lock Check → MIME Detector → OCR
→ PII Fortress → Semantic Chunker (LLM) → Chunk Enricher (prefix statique)
→ Version Manager → Q&A Generator (5 chunks) → Q&A Enricher
→ Embeddings (text-embedding-3-small) → Prepare Vectors → [Pinecone + Postgres]
→ Lock Release → OTEL

CIBLE (V4) — nœuds NOUVEAUX en ★, nœuds MODIFIÉS en ◆:
Webhook → Init Lock → Redis Lock → Lock Check → MIME Detector → OCR
→ PII Fortress → ◆ Semantic Chunker (LLM + Fallback + Validation)
→ ★ Contextual Retrieval (LLM par chunk) → ◆ Q&A Generator (par chunk)
→ ◆ Q&A Enricher → Version Manager
→ ◆ Embeddings (Qwen3-Embedding-8B / configurable)
→ ★ BM25 Sparse Vectors Generator
→ Prepare Vectors → [Pinecone (dense+sparse) + Postgres]
→ Lock Release → OTEL
```

### Enrichissement V3.1 → V4

```
ACTUEL (V3.1):
Chat Trigger → OTEL Init → Lock → Lock Check
→ [Fetch Internal ∥ Fetch External] → Normalize & Merge
→ AI Entity Enrichment (6000 chars) → Relationship Mapper
→ [Pinecone ∥ Postgres ∥ Neo4j] → Community Detection Trigger
→ Lock Release → Log → OTEL

CIBLE (V4) — nœuds NOUVEAUX en ★, nœuds MODIFIÉS en ◆:
Chat Trigger → OTEL Init → Lock → Lock Check
→ [Fetch Internal ∥ Fetch External] → Normalize & Merge
→ ★ Chunk-level Entity Extraction (Loop) → ★ Global Entity Resolution
→ ◆ Relationship Mapper (avec résolution)
→ [Pinecone ∥ Postgres ∥ Neo4j]
→ ◆ Community Detection → ★ Community Summary Generator (LLM)
→ ★ Store Community Summaries (Neo4j + Postgres)
→ Lock Release → Log → OTEL
```

### Résumé des patchs par priorité

| ID | Priorité | Pipeline | Nœud | Action |
|----|----------|----------|------|--------|
| P01 | P0 | Ingestion | Contextual Retrieval LLM | NOUVEAU |
| P02 | P0 | Ingestion | BM25 Sparse Vectors | NOUVEAU |
| P03 | P0 | Ingestion | Embedding Model Upgrade | MODIFIER |
| P04 | P0 | Ingestion | Semantic Chunker Fallback | MODIFIER |
| P05 | P0 | Ingestion | Q&A Generator per-chunk | MODIFIER |
| P06 | P1 | Enrichissement | Chunk-level Entity Extraction | NOUVEAU |
| P07 | P1 | Enrichissement | Global Entity Resolution | NOUVEAU |
| P08 | P1 | Enrichissement | Community Summary Generator | NOUVEAU |
| P09 | P1 | Enrichissement | Store Community Summaries | NOUVEAU |
| P10 | P1 | Enrichissement | Entity Extraction Loop | MODIFIER |

---

## 2. Variables d'environnement ajoutées

```
# === NOUVELLES VARIABLES ===

# Contextual Retrieval (P01)
CONTEXTUAL_RETRIEVAL_API_URL=https://api.deepseek.com/v1/chat/completions
CONTEXTUAL_RETRIEVAL_MODEL=deepseek-chat
# Alternative: https://api.anthropic.com/v1/messages avec claude-haiku

# BM25 / Sparse Vectors (P02)
# Option A: Pinecone sparse (hybrid index)
PINECONE_HYBRID_ENABLED=true
# Option B: Elasticsearch standalone
ELASTICSEARCH_URL=https://elasticsearch.internal:9200
ELASTICSEARCH_INDEX=rag-chunks-bm25

# Embedding Model (P03)
EMBEDDING_API_URL=http://embedding-server.internal:8080/v1/embeddings
EMBEDDING_MODEL=Qwen3-Embedding-8B
EMBEDDING_DIMENSION=4096
# Fallback: text-embedding-3-small (dim 1536)

# Reranker (pour retrieval, pas dans ingestion mais à préparer)
RERANKER_API_URL=http://reranker-server.internal:8080/v1/rerank
RERANKER_MODEL=Qwen3-Reranker-8B

# Community Summaries (P08)
COMMUNITY_SUMMARY_API_URL=https://api.deepseek.com/v1/chat/completions
COMMUNITY_SUMMARY_MODEL=deepseek-chat
```

---

## 3. Pipeline Ingestion V4 — Architecture cible

### 3.1. DAG complet (connexions)

```
S3 Event Webhook
  → Init Lock & Trace
    → Redis: Acquire Lock
      → Lock Result Handler
        → Lock Acquired?
          ├─ TRUE → MIME Type Detector
          │           → OCR Extraction
          │             → PII Fortress
          │               → Semantic Chunker V4 (Adaptive + Fallback)    ◆ PATCH P04
          │                 → Contextual Retrieval (LLM per chunk)       ★ PATCH P01
          │                   → Q&A Generator V4 (per chunk)             ◆ PATCH P05
          │                     → Q&A Enricher V4
          │                       → Version Manager
          │                         → Generate Embeddings V4             ◆ PATCH P03
          │                           → BM25 Sparse Vector Generator     ★ PATCH P02
          │                             → Prepare Vectors V4 (Hybrid)
          │                               ├─ Pinecone Upsert (dense+sparse)
          │                               └─ Postgres Store
          │                             → Prepare Lock Release
          │                               → Redis: Release Lock
          │                                 → Export Trace OTEL
          └─ FALSE → Return Skip Response
```

### 3.2. PATCH P01 — Contextual Retrieval (LLM per chunk) ★ NOUVEAU

**Position dans le DAG** : après `Semantic Chunker V4` → avant `Q&A Generator V4`

**Type** : `n8n-nodes-base.code` (typeVersion 2)

**Logique** : Pour chaque chunk, appeler un LLM avec le document complet + le chunk, et obtenir 1-2 phrases de contexte situant le chunk dans le document. Le `contextual_content` qui sera embedé est `contextual_header + "\n" + chunk.content`.

```javascript
// PATCH P01: Contextual Retrieval — Anthropic Pattern (Sept 2024)
// Impact: -35% échecs retrieval (dense), -49% avec BM25, -67% avec reranking
// Coût: ~$0.04/document avec DeepSeek-V3

const chunks = $json.chunks || [];
const fullDocument = $json.full_document_text || '';
const documentTitle = $json.document_title || '';
const traceId = $json.trace_id || '';

// Configuration
const API_URL = $vars.CONTEXTUAL_RETRIEVAL_API_URL || 'https://api.deepseek.com/v1/chat/completions';
const MODEL = $vars.CONTEXTUAL_RETRIEVAL_MODEL || 'deepseek-chat';
const MAX_DOC_CHARS = 60000; // ~15k tokens pour DeepSeek
const CONCURRENCY = 5; // Appels parallèles

// Tronquer le document si nécessaire (garder début + fin)
let docContext = fullDocument;
if (docContext.length > MAX_DOC_CHARS) {
  const half = Math.floor(MAX_DOC_CHARS / 2);
  docContext = docContext.substring(0, half) + '\n[...]\n' + docContext.substring(docContext.length - half);
}

const enrichedChunks = [];

// Traitement par batch pour rester dans les limites de rate-limit
for (let i = 0; i < chunks.length; i += CONCURRENCY) {
  const batch = chunks.slice(i, i + CONCURRENCY);
  
  const promises = batch.map(async (chunk, batchIdx) => {
    const globalIdx = i + batchIdx;
    
    try {
      const response = await fetch(API_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${$credentials.contextual_retrieval_api?.apiKey || $vars.DEEPSEEK_API_KEY}`
        },
        body: JSON.stringify({
          model: MODEL,
          messages: [
            {
              role: 'system',
              content: 'Tu reçois un document complet et un chunk extrait de ce document. Génère 1-2 phrases concises qui situent ce chunk dans le contexte global du document. Ces phrases seront préfixées au chunk pour améliorer la recherche sémantique. Réponds UNIQUEMENT avec les phrases de contexte, rien d\'autre.'
            },
            {
              role: 'user',
              content: `<document>\n${docContext}\n</document>\n\n<chunk>\n${chunk.content}\n</chunk>\n\nSitue ce chunk dans le contexte du document "${documentTitle}".`
            }
          ],
          temperature: 0.0,
          max_tokens: 200
        })
      });
      
      const data = await response.json();
      const contextualHeader = data.choices?.[0]?.message?.content?.trim() || '';
      
      return {
        ...chunk,
        contextual_header: contextualHeader,
        contextual_content: contextualHeader 
          ? `${contextualHeader}\n\n${chunk.content}` 
          : chunk.content,
        contextual_prefix: contextualHeader, // Remplace l'ancien prefix statique
        contextual_retrieval_applied: !!contextualHeader
      };
    } catch (error) {
      console.error(`Contextual retrieval failed for chunk ${globalIdx}:`, error.message);
      // Fallback: garder le contenu original
      return {
        ...chunk,
        contextual_header: '',
        contextual_content: chunk.content,
        contextual_prefix: chunk.contextual_prefix || '', // Garder l'ancien prefix statique comme fallback
        contextual_retrieval_applied: false,
        contextual_error: error.message
      };
    }
  });
  
  const results = await Promise.all(promises);
  enrichedChunks.push(...results);
}

const successCount = enrichedChunks.filter(c => c.contextual_retrieval_applied).length;

return {
  ...$json,
  chunks: enrichedChunks,
  contextual_retrieval_stats: {
    total: enrichedChunks.length,
    success: successCount,
    failed: enrichedChunks.length - successCount,
    model: MODEL
  }
};
```

**Note d'implémentation n8n** : Ce nœud nécessite un appel HTTP par chunk. Dans n8n, les `fetch` natifs ne sont pas disponibles dans les Code nodes. Il faut donc implémenter ceci comme un **sub-workflow** appelé en boucle, OU utiliser un nœud HTTP Request dans un **Loop Over Items** (SplitInBatches). La structure recommandée est :

```
Semantic Chunker V4
  → Split Chunks (SplitInBatches, batchSize=5)
    → HTTP Request: Contextual LLM Call
      → Aggregate Contextual Chunks (Code)
        → Q&A Generator V4
```

**Alternative n8n (plus simple)** : Un seul nœud HTTP Request avec une boucle manuelle dans le Code node en utilisant `$getWorkflowStaticData` et `this.helpers.httpRequest` disponible dans n8n :

```javascript
// Version n8n-compatible utilisant this.helpers.httpRequest
// (Nécessite typeVersion 2 du Code node)

const chunks = $json.chunks || [];
const fullDocument = $json.full_document_text || '';
const documentTitle = $json.document_title || '';

const API_URL = '{{ $vars.CONTEXTUAL_RETRIEVAL_API_URL || "https://api.deepseek.com/v1/chat/completions" }}';
const MODEL = '{{ $vars.CONTEXTUAL_RETRIEVAL_MODEL || "deepseek-chat" }}';

const MAX_DOC_CHARS = 60000;
let docContext = fullDocument;
if (docContext.length > MAX_DOC_CHARS) {
  const half = Math.floor(MAX_DOC_CHARS / 2);
  docContext = docContext.substring(0, half) + '\n[...]\n' + docContext.substring(docContext.length - half);
}

// Dans n8n Code node, on retourne un tableau d'items
// Chaque chunk sera traité par le nœud HTTP suivant via SplitInBatches
const items = chunks.map((chunk, idx) => ({
  json: {
    ...chunk,
    _contextual_prompt: JSON.stringify({
      model: MODEL,
      messages: [
        {
          role: 'system',
          content: 'Tu reçois un document complet et un chunk. Génère 1-2 phrases qui situent ce chunk dans le contexte du document. Réponds UNIQUEMENT avec les phrases de contexte.'
        },
        {
          role: 'user',
          content: `<document>\n${docContext}\n</document>\n<chunk>\n${chunk.content}\n</chunk>\nSitue ce chunk dans le contexte du document "${documentTitle}".`
        }
      ],
      temperature: 0.0,
      max_tokens: 200
    }),
    _chunk_index: idx,
    _parent_data: {
      parent_id: $json.parent_id,
      parent_filename: $json.parent_filename,
      document_title: $json.document_title,
      total_chunks: chunks.length,
      trace_id: $json.trace_id,
      tenant_id: $json.tenant_id,
      lock_key: $json.lock_key,
      lock_value: $json.lock_value
    }
  }
}));

return items;
```

### 3.3. PATCH P02 — BM25 Sparse Vectors Generator ★ NOUVEAU

**Position dans le DAG** : après `Generate Embeddings V4` → avant/parallèle à `Prepare Vectors V4`

**Type** : `n8n-nodes-base.code` (typeVersion 2)

**Option A — Pinecone Hybrid (sparse vectors intégrés)**

```javascript
// PATCH P02: BM25 Sparse Vector Generator pour Pinecone Hybrid Search
// Impact: +30-50% recall combiné avec dense embeddings
// Utilise une implémentation BM25 simplifiée côté client
// Les sparse values sont passées à Pinecone lors de l'upsert

const chunks = $json.chunks || [];

// === BM25 PARAMETERS ===
const K1 = 1.2;
const B = 0.75;

// === Tokenizer simple (adapté FR+EN) ===
const STOP_WORDS = new Set([
  'le', 'la', 'les', 'un', 'une', 'des', 'de', 'du', 'au', 'aux',
  'et', 'ou', 'mais', 'donc', 'car', 'ni', 'que', 'qui', 'quoi',
  'ce', 'cette', 'ces', 'mon', 'ton', 'son', 'ma', 'ta', 'sa',
  'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to',
  'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be',
  'it', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she',
  'nous', 'vous', 'ils', 'elles', 'je', 'tu', 'il', 'elle',
  'est', 'sont', 'a', 'ont', 'être', 'avoir', 'faire', 'dire',
  'pas', 'ne', 'plus', 'très', 'bien', 'aussi', 'comme'
]);

function tokenize(text) {
  return text
    .toLowerCase()
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '') // Retirer accents
    .replace(/[^a-z0-9\s]/g, ' ')
    .split(/\s+/)
    .filter(t => t.length > 2 && !STOP_WORDS.has(t));
}

// Simple hash function pour convertir des tokens en indices sparse
// Pinecone attend des indices entiers pour les sparse vectors
function hashToken(token) {
  let hash = 0;
  for (let i = 0; i < token.length; i++) {
    const char = token.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32bit integer
  }
  return Math.abs(hash) % 100000; // Espace de 100k dimensions
}

// === Calculer les Document Frequencies ===
const allTokenSets = chunks.map(chunk => {
  const text = chunk.contextual_content || chunk.content;
  return new Set(tokenize(text));
});

const df = {};
for (const tokenSet of allTokenSets) {
  for (const token of tokenSet) {
    df[token] = (df[token] || 0) + 1;
  }
}

const N = chunks.length;
const avgDl = chunks.reduce((sum, c) => {
  return sum + tokenize(c.contextual_content || c.content).length;
}, 0) / Math.max(N, 1);

// === Calculer les sparse vectors BM25 pour chaque chunk ===
const sparseVectors = chunks.map((chunk) => {
  const text = chunk.contextual_content || chunk.content;
  const tokens = tokenize(text);
  const dl = tokens.length;
  
  // Term frequencies
  const tf = {};
  for (const token of tokens) {
    tf[token] = (tf[token] || 0) + 1;
  }
  
  // BM25 scores par terme
  const indices = [];
  const values = [];
  
  for (const [term, freq] of Object.entries(tf)) {
    const idf = Math.log((N - (df[term] || 0) + 0.5) / ((df[term] || 0) + 0.5) + 1);
    const tfNorm = (freq * (K1 + 1)) / (freq + K1 * (1 - B + B * (dl / avgDl)));
    const score = idf * tfNorm;
    
    if (score > 0) {
      indices.push(hashToken(term));
      values.push(Math.round(score * 1000) / 1000);
    }
  }
  
  return { indices, values };
});

// Ajouter les sparse vectors aux chunks
const enrichedChunks = chunks.map((chunk, idx) => ({
  ...chunk,
  sparse_values: sparseVectors[idx],
  bm25_token_count: tokenize(chunk.contextual_content || chunk.content).length
}));

return {
  ...$json,
  chunks: enrichedChunks,
  bm25_stats: {
    vocabulary_size: Object.keys(df).length,
    avg_doc_length: Math.round(avgDl),
    total_chunks: N
  }
};
```

**Option B — Elasticsearch (index BM25 séparé)**

```javascript
// PATCH P02-B: Indexation Elasticsearch pour BM25
// À utiliser si Pinecone sparse n'est pas disponible
// Ce nœud est un HTTP Request vers Elasticsearch bulk API

const chunks = $json.chunks || [];
const ES_URL = $vars.ELASTICSEARCH_URL || 'https://elasticsearch.internal:9200';
const ES_INDEX = $vars.ELASTICSEARCH_INDEX || 'rag-chunks-bm25';

// Préparer le bulk request
const bulkBody = chunks.flatMap(chunk => [
  { index: { _index: ES_INDEX, _id: chunk.id } },
  {
    content: chunk.content,
    contextual_content: chunk.contextual_content || chunk.content,
    parent_id: chunk.parent_id,
    parent_filename: chunk.parent_filename,
    document_title: chunk.document_title || '',
    section: chunk.section || '',
    topic: chunk.topic || '',
    tenant_id: chunk.tenant_id || 'default',
    hypothetical_questions: (chunk.hypothetical_questions || []).join(' '),
    ingested_at: new Date().toISOString()
  }
]);

return {
  elasticsearch_bulk_body: bulkBody.map(line => JSON.stringify(line)).join('\n') + '\n',
  elasticsearch_url: `${ES_URL}/${ES_INDEX}/_bulk`,
  chunk_count: chunks.length
};
```

### 3.4. PATCH P03 — Embedding Model Upgrade ◆ MODIFIER

**Nœud existant** : `Generate Embeddings V3.1 (Contextual)`

**Changements** :
1. URL et model configurables via variables
2. Gestion de la dimension différente (4096 pour Qwen3 vs 1536 pour OpenAI)
3. Batch processing pour les limites d'API

```json
{
  "jsonBody": "={\n  \"model\": \"{{ $vars.EMBEDDING_MODEL || 'text-embedding-3-small' }}\",\n  \"input\": {{ JSON.stringify(($json.chunks || []).slice(0, 100).map(c => c.contextual_content || c.content)) }}\n}",
  "url": "={{ $vars.EMBEDDING_API_URL || 'https://api.openai.com/v1/embeddings' }}"
}
```

**Modification `Prepare Vectors V4`** — le nœud doit inclure `sparse_values` si disponibles :

```javascript
// Prepare Vectors V4 - Hybrid (Dense + Sparse)
const chunkData = $node['Q&A Enricher V4'].json;
const embeddings = $json.data || [];
const chunks = chunkData.chunks || [];
const hybridEnabled = chunks[0]?.sparse_values?.indices?.length > 0;

const vectors = chunks.slice(0, 100).map((chunk, idx) => {
  const vector = {
    id: chunk.id,
    values: embeddings[idx]?.embedding || [],
    metadata: {
      content: chunk.content.substring(0, 1000),
      contextual_content: (chunk.contextual_content || chunk.content).substring(0, 1500),
      contextual_prefix: chunk.contextual_prefix || '',
      contextual_header: chunk.contextual_header || '',
      parent_id: chunk.parent_id,
      parent_filename: chunk.parent_filename,
      document_title: chunk.document_title || '',
      document_type: chunk.document_type || '',
      section: chunk.section || '',
      chunk_index: chunk.chunk_index,
      total_chunks: chunk.total_chunks,
      topic: chunk.topic || 'general',
      hypothetical_questions: chunk.hypothetical_questions || [],
      tenant_id: chunk.tenant_id || 'default',
      allowed_groups: ['default', 'admin'],
      quality_score: chunk.quality_score || 0.5,
      ingested_at: new Date().toISOString(),
      version: chunk.version || 1
    }
  };
  
  // Ajouter sparse values si hybrid search activé
  if (hybridEnabled && chunk.sparse_values) {
    vector.sparseValues = {
      indices: chunk.sparse_values.indices,
      values: chunk.sparse_values.values
    };
  }
  
  return vector;
});

return {
  vectors,
  trace_id: chunkData.trace_id,
  chunk_count: vectors.length,
  hybrid_enabled: hybridEnabled,
  contextual_retrieval_enabled: true
};
```

### 3.5. PATCH P04 — Semantic Chunker V4 (Fallback + Validation) ◆ MODIFIER

**Nœud existant** : `Semantic Chunker V3.1 (Adaptive)`

**Changements** :
1. Envoyer tout le document (pas seulement 15000 chars) si possible
2. Ajouter un fallback robuste vers RecursiveCharacterTextSplitter
3. Valider les chunks (taille, overlap, cohérence)

Le nœud HTTP reste identique, mais le nœud Code **après** le chunker (actuellement `Chunk Enricher`) doit intégrer la validation. On ajoute un nœud intermédiaire :

```javascript
// PATCH P04: Chunk Validator & Fallback
// Inséré entre Semantic Chunker et Contextual Retrieval

const crypto = require('crypto');
const mimeData = $node['MIME Type Detector'].json;
const piiData = $node['PII Fortress'].json;
const fullContent = piiData.processed_content || '';

let chunksData;
try {
  chunksData = JSON.parse($json.choices?.[0]?.message?.content || '{}');
} catch (e) {
  chunksData = null;
}

let chunks = chunksData?.chunks || [];

// === VALIDATION ===
const MIN_CHUNK_SIZE = 50;    // Caractères minimum
const MAX_CHUNK_SIZE = 3000;  // Caractères maximum
const IDEAL_MIN = 200;
const IDEAL_MAX = 1500;

const isValid = chunks.length > 0 && chunks.every(c => 
  c.content && 
  c.content.length >= MIN_CHUNK_SIZE && 
  c.content.length <= MAX_CHUNK_SIZE * 2
);

// === FALLBACK: RecursiveCharacterTextSplitter ===
if (!isValid || chunks.length === 0) {
  console.warn('LLM chunking failed or invalid, falling back to recursive splitter');
  
  const CHUNK_SIZE = 800;
  const OVERLAP = 200;
  const SEPARATORS = ['\n\n', '\n', '. ', '! ', '? ', '; ', ', ', ' '];
  
  function recursiveSplit(text, separators, chunkSize, overlap) {
    if (text.length <= chunkSize) return [text];
    
    const results = [];
    let currentSep = separators[0] || ' ';
    
    for (const sep of separators) {
      if (text.includes(sep)) {
        currentSep = sep;
        break;
      }
    }
    
    const parts = text.split(currentSep);
    let currentChunk = '';
    
    for (const part of parts) {
      const candidate = currentChunk ? currentChunk + currentSep + part : part;
      
      if (candidate.length > chunkSize && currentChunk) {
        results.push(currentChunk.trim());
        // Overlap: garder la fin du chunk précédent
        const overlapText = currentChunk.substring(Math.max(0, currentChunk.length - overlap));
        currentChunk = overlapText + currentSep + part;
      } else {
        currentChunk = candidate;
      }
    }
    
    if (currentChunk.trim()) {
      results.push(currentChunk.trim());
    }
    
    return results;
  }
  
  const splitTexts = recursiveSplit(fullContent, SEPARATORS, CHUNK_SIZE, OVERLAP);
  chunks = splitTexts.map((text, idx) => ({
    content: text,
    topic: 'auto-split',
    start_index: fullContent.indexOf(text)
  }));
}

// === POST-VALIDATION: split oversized, merge undersized ===
const validatedChunks = [];
for (const chunk of chunks) {
  if (chunk.content.length > MAX_CHUNK_SIZE) {
    // Split oversized chunk
    const mid = chunk.content.lastIndexOf('. ', Math.floor(chunk.content.length / 2));
    const splitPoint = mid > 0 ? mid + 2 : Math.floor(chunk.content.length / 2);
    validatedChunks.push({ ...chunk, content: chunk.content.substring(0, splitPoint) });
    validatedChunks.push({ ...chunk, content: chunk.content.substring(splitPoint), topic: chunk.topic + ' (cont.)' });
  } else if (chunk.content.length < MIN_CHUNK_SIZE && validatedChunks.length > 0) {
    // Merge undersized with previous
    const prev = validatedChunks[validatedChunks.length - 1];
    prev.content += '\n' + chunk.content;
  } else {
    validatedChunks.push(chunk);
  }
}

// === ENRICH CHUNKS ===
const parentId = crypto.createHash('sha256').update(mimeData.objectKey).digest('hex').substring(0, 32);
const documentTitle = mimeData.objectKey.split('/').pop().replace(/\.[^/.]+$/, '');
const documentType = mimeData.mime_type || 'UNKNOWN';

// Detect sections
const sections = [];
const sectionRegex = /^(#{1,3}\s+|\d+\.\s+|[A-Z][A-Z\s]+:)/gm;
let match;
while ((match = sectionRegex.exec(fullContent)) !== null) {
  sections.push({ index: match.index, header: match[0].trim() });
}

const enrichedChunks = validatedChunks.map((chunk, idx) => {
  const chunkId = `${parentId}-chunk-${idx}`;
  
  let currentSection = 'Introduction';
  for (const section of sections) {
    if (section.index <= (chunk.start_index || 0)) {
      currentSection = section.header;
    } else break;
  }
  
  return {
    id: chunkId,
    content: chunk.content,
    contextual_content: chunk.content, // Sera enrichi par P01
    contextual_prefix: '',              // Sera enrichi par P01
    topic: chunk.topic,
    section: currentSection,
    parent_id: parentId,
    parent_filename: mimeData.objectKey,
    document_title: documentTitle,
    document_type: documentType,
    quality_score: mimeData.quality_score,
    version: 1,
    is_obsolete: false,
    chunk_method: isValid ? mimeData.chunking_method : 'recursive_fallback',
    chunk_index: idx,
    total_chunks: validatedChunks.length,
    tenant_id: mimeData.tenant_id,
    trace_id: mimeData.traceId,
    pii_count: piiData.pii_count || 0,
    created_at: new Date().toISOString()
  };
});

return {
  chunks: enrichedChunks,
  full_document_text: fullContent, // Passé à P01 pour contextual retrieval
  parent_id: parentId,
  parent_filename: mimeData.objectKey,
  document_title: documentTitle,
  total_chunks: enrichedChunks.length,
  trace_id: mimeData.traceId,
  tenant_id: mimeData.tenant_id,
  lock_key: mimeData.lockKey,
  lock_value: mimeData.lockValue,
  chunking_method: isValid ? 'llm_semantic' : 'recursive_fallback',
  sections_detected: sections.length
};
```

### 3.6. PATCH P05 — Q&A Generator V4 (per chunk) ◆ MODIFIER

**Nœud existant** : `Q&A Generator`

**Changements** :
1. Générer des questions pour CHAQUE chunk (pas seulement les 5 premiers)
2. Appel individuel par chunk (via SplitInBatches) ou batch intelligent

**Option SplitInBatches (recommandée)** :

Le nœud HTTP Request est modifié pour traiter un chunk à la fois :

```json
{
  "jsonBody": "={\n  \"model\": \"{{ $vars.QA_MODEL || 'deepseek-chat' }}\",\n  \"messages\": [\n    {\n      \"role\": \"system\",\n      \"content\": \"Génère exactement 3 questions auxquelles ce chunk de texte répond directement. Les questions doivent être spécifiques et refléter le contenu exact du chunk. Format JSON: {\\\"questions\\\": [\\\"Q1?\\\", \\\"Q2?\\\", \\\"Q3?\\\"]}\"\n    },\n    {\n      \"role\": \"user\",\n      \"content\": \"{{ $json.content.substring(0, 1500) }}\"\n    }\n  ],\n  \"temperature\": 0.3,\n  \"max_tokens\": 300,\n  \"response_format\": { \"type\": \"json_object\" }\n}"
}
```

**Q&A Enricher V4** modifié en conséquence :

```javascript
// Q&A Enricher V4 — per-chunk assignment
// Ce nœud reçoit les résultats de Q&A individuels par chunk

let qaData;
try {
  qaData = JSON.parse($json.choices?.[0]?.message?.content || '{}');
} catch (e) {
  qaData = { questions: [] };
}

const questions = qaData.questions || [];

// Assigner directement au chunk courant
return {
  ...$json,
  hypothetical_questions: questions.slice(0, 3) // Garder max 3
};
```

---

## 4. Pipeline Enrichissement V4 — Architecture cible

### 4.1. DAG complet (connexions)

```
When chat message received
  → Init OT Trace
    → Prepare Lock
      → Redis: Acquire Lock
        → Lock Result Handler
          → Lock Acquired?
            ├─ TRUE → [Fetch Internal ∥ Fetch External]
            │           → Normalize & Merge
            │             → ★ Split Sources (SplitInBatches)         P06
            │               → ★ Chunk-level Entity Extraction (HTTP) P06
            │                 → ★ Aggregate Entities (Code)          P06
            │                   → ★ Global Entity Resolution         P07
            │                     → ◆ Relationship Mapper V4
            │                       ├─ Upsert Vectors Pinecone
            │                       ├─ Store Metadata Postgres
            │                       └─ Update Graph Neo4j
            │                     → ◆ Community Detection (Louvain)
            │                       → ★ Fetch Communities (HTTP)     P08
            │                         → ★ Community Summary Gen.     P08
            │                           → ★ Store Summaries          P09
            │                             → Prepare Lock Release
            │                               → Redis: Release Lock
            │                                 → Log Success
            │                                   → Export Trace OTEL
            └─ FALSE → (end, skip)
```

### 4.2. PATCH P06 — Chunk-level Entity Extraction ★ NOUVEAU

**Remplace** : `AI Entity Enrichment V3.1 (Enhanced)` qui tronquait à 6000 chars.

**Architecture n8n** : 3 nœuds

#### P06a — Split Sources (SplitInBatches)
Type: `n8n-nodes-base.splitInBatches`, batchSize=1

#### P06b — Entity Extraction HTTP (per source)
Le même prompt que V3.1 mais sur un seul document/source complet :

```json
{
  "jsonBody": "={\n  \"model\": \"{{ $vars.ENTITY_EXTRACTION_MODEL || 'deepseek-chat' }}\",\n  \"messages\": [\n    {\n      \"role\": \"system\",\n      \"content\": \"Tu es un expert en extraction d'entités et relations...\\n[MÊME PROMPT QUE V3.1]...\"\n    },\n    {\n      \"role\": \"user\",\n      \"content\": \"{{ JSON.stringify($json).substring(0, 30000) }}\"\n    }\n  ],\n  \"temperature\": 0.1,\n  \"response_format\": { \"type\": \"json_object\" },\n  \"max_tokens\": 3000\n}"
}
```

**Changement clé** : `substring(0, 30000)` au lieu de `6000`, et traitement par source individuelle.

#### P06c — Aggregate Entities (Code)
Collecte toutes les extractions individuelles :

```javascript
// Agrège les résultats d'extraction de toutes les sources
const allItems = $input.all();
const allEntities = [];
const allRelationships = [];

for (const item of allItems) {
  let extracted = {};
  try {
    extracted = JSON.parse(item.json.choices?.[0]?.message?.content || '{}');
  } catch (e) {
    continue;
  }
  
  allEntities.push(...(extracted.entities || []));
  allRelationships.push(...(extracted.relationships || []));
}

return {
  raw_entities: allEntities,
  raw_relationships: allRelationships,
  source_count: allItems.length,
  total_raw_entities: allEntities.length,
  total_raw_relationships: allRelationships.length
};
```

### 4.3. PATCH P07 — Global Entity Resolution ★ NOUVEAU

**Position** : après Aggregate Entities → avant Relationship Mapper V4

```javascript
// PATCH P07: Global Entity Resolution
// Dédoublonne et fusionne les entités extraites de multiples sources
// Utilise normalisation de noms + alias matching + similarité

const crypto = require('crypto');
const rawEntities = $json.raw_entities || [];
const rawRelationships = $json.raw_relationships || [];

// === NORMALISATION ===
const normalizeEntityName = (name) => {
  return name
    .trim()
    .replace(/\s+/g, ' ')
    .replace(/['']/g, "'")
    .toUpperCase();
};

// === ENTITY RESOLUTION ===
// Phase 1: Grouper par nom normalisé + type
const entityGroups = new Map(); // key: normalized_name+type → entity[]

for (const entity of rawEntities) {
  const key = `${normalizeEntityName(entity.name)}::${entity.type}`;
  
  if (!entityGroups.has(key)) {
    entityGroups.set(key, {
      canonical_name: entity.name,
      normalized_name: normalizeEntityName(entity.name),
      type: entity.type,
      aliases: new Set(),
      contexts: [],
      occurrence_count: 0
    });
  }
  
  const group = entityGroups.get(key);
  group.occurrence_count++;
  if (entity.context) group.contexts.push(entity.context);
  if (entity.aliases) {
    for (const alias of entity.aliases) {
      group.aliases.add(alias);
    }
  }
}

// Phase 2: Résoudre les alias cross-groupes
const aliasToCanonical = new Map();

for (const [key, group] of entityGroups) {
  aliasToCanonical.set(group.normalized_name, key);
  for (const alias of group.aliases) {
    const normAlias = normalizeEntityName(alias);
    if (!aliasToCanonical.has(normAlias)) {
      aliasToCanonical.set(normAlias, key);
    }
  }
}

// Phase 3: Fusionner les groupes qui ont des alias communs
const mergedGroups = new Map();
const visited = new Set();

for (const [key, group] of entityGroups) {
  if (visited.has(key)) continue;
  visited.add(key);
  
  const merged = { ...group, aliases: new Set(group.aliases) };
  
  // Chercher les groupes qui sont des alias de celui-ci
  for (const alias of group.aliases) {
    const normAlias = normalizeEntityName(alias);
    const aliasKey = `${normAlias}::${group.type}`;
    
    if (entityGroups.has(aliasKey) && !visited.has(aliasKey)) {
      const aliasGroup = entityGroups.get(aliasKey);
      visited.add(aliasKey);
      merged.occurrence_count += aliasGroup.occurrence_count;
      merged.contexts.push(...aliasGroup.contexts);
      for (const a of aliasGroup.aliases) merged.aliases.add(a);
    }
  }
  
  mergedGroups.set(key, merged);
}

// Phase 4: Générer les entités canoniques finales
const resolvedEntities = [];
const entityIdMap = new Map(); // normalized_name → canonical_id

for (const [key, group] of mergedGroups) {
  const entityId = crypto.createHash('md5')
    .update(group.normalized_name + group.type)
    .digest('hex').substring(0, 16);
  
  entityIdMap.set(group.normalized_name, entityId);
  for (const alias of group.aliases) {
    entityIdMap.set(normalizeEntityName(alias), entityId);
  }
  
  resolvedEntities.push({
    id: entityId,
    name: group.canonical_name,
    normalized_name: group.normalized_name,
    type: group.type,
    aliases: [...group.aliases],
    contexts: group.contexts.slice(0, 5), // Garder les 5 premiers contextes
    occurrence_count: group.occurrence_count,
    confidence: Math.min(1.0, 0.5 + group.occurrence_count * 0.1) // Plus d'occurrences = plus confiant
  });
}

// Phase 5: Résoudre les relations vers les entités canoniques
const resolvedRelationships = rawRelationships
  .map(rel => {
    const sourceId = entityIdMap.get(normalizeEntityName(rel.source));
    const targetId = entityIdMap.get(normalizeEntityName(rel.target));
    
    if (!sourceId || !targetId) return null;
    if (sourceId === targetId) return null; // Pas de self-loop
    
    return {
      source_id: sourceId,
      source_name: rel.source,
      target_id: targetId,
      target_name: rel.target,
      type: rel.type.toUpperCase().replace(/[^A-Z_]/g, '_'),
      confidence: rel.confidence || 0.7,
      evidence: rel.evidence || ''
    };
  })
  .filter(Boolean);

// Dédoublonner les relations (garder la plus haute confidence)
const relMap = new Map();
for (const rel of resolvedRelationships) {
  const key = `${rel.source_id}-${rel.type}-${rel.target_id}`;
  if (!relMap.has(key) || relMap.get(key).confidence < rel.confidence) {
    relMap.set(key, rel);
  }
}

return {
  resolved_entities: resolvedEntities,
  resolved_relationships: [...relMap.values()],
  resolution_stats: {
    raw_entities: rawEntities.length,
    resolved_entities: resolvedEntities.length,
    dedup_ratio: rawEntities.length > 0 
      ? Math.round((1 - resolvedEntities.length / rawEntities.length) * 100) + '%'
      : '0%',
    raw_relationships: rawRelationships.length,
    resolved_relationships: relMap.size
  }
};
```

### 4.4. PATCH P08 — Community Summary Generator ★ NOUVEAU

**Position** : après Community Detection Trigger → avant Store Summaries

**Architecture** : 2 nœuds

#### P08a — Fetch Communities from Neo4j

```javascript
// Requête Cypher pour récupérer les communautés détectées
// Ce nœud prépare la requête pour Neo4j

const tenantId = $node['Lock Result Handler']?.json?.trace_id?.split('-')[0] || 'default';

return {
  cypher_query: JSON.stringify({
    statements: [{
      statement: `
        MATCH (e:Entity)
        WHERE e.community_id IS NOT NULL
        WITH e.community_id AS communityId, 
             collect({name: e.name, type: e.type}) AS members
        WHERE size(members) >= 3
        RETURN communityId, members
        ORDER BY size(members) DESC
        LIMIT 50
      `
    }]
  }),
  tenant_id: tenantId
};
```

Ce sera un HTTP Request vers `{{ $vars.NEO4J_URL }}/db/neo4j/tx/commit`.

#### P08b — Generate Community Summaries (LLM)

```javascript
// PATCH P08: Community Summary Generator
// Pour chaque communauté, générer un résumé via LLM
// Impact: Permet le Global Search (questions de haut niveau)

const neo4jResponse = $json;
const communities = neo4jResponse?.results?.[0]?.data || [];

if (communities.length === 0) {
  return { summaries: [], status: 'NO_COMMUNITIES' };
}

// Préparer les prompts pour chaque communauté
const summaryRequests = communities.map((community, idx) => {
  const members = community.row?.[1] || [];
  const communityId = community.row?.[0] || `community-${idx}`;
  
  const memberList = members
    .map(m => `- ${m.name} (${m.type})`)
    .join('\n');
  
  return {
    community_id: communityId,
    member_count: members.length,
    members: members,
    prompt: JSON.stringify({
      model: '{{ $vars.COMMUNITY_SUMMARY_MODEL || "deepseek-chat" }}',
      messages: [
        {
          role: 'system',
          content: 'Tu reçois une liste d\'entités qui forment une communauté dans un knowledge graph. Génère un résumé concis (3-5 phrases) qui décrit: 1) Le thème principal de cette communauté, 2) Les entités clés et leurs rôles, 3) Les relations importantes entre elles. Format JSON: {"title": "string", "summary": "string", "key_themes": ["string"]}'
        },
        {
          role: 'user',
          content: `Communauté #${communityId} (${members.length} membres):\n${memberList}`
        }
      ],
      temperature: 0.2,
      max_tokens: 500,
      response_format: { type: 'json_object' }
    })
  };
});

return summaryRequests;
```

**Note n8n** : Ceci sera implémenté via un `SplitInBatches` + HTTP Request LLM + Aggregate.

### 4.5. PATCH P09 — Store Community Summaries ★ NOUVEAU

**Position** : après Community Summary Generator → avant Prepare Lock Release

**2 stores en parallèle** :

#### P09a — Neo4j (pour graph traversal)

```javascript
// Prépare les statements Cypher pour stocker les community summaries
const summaries = $json.summaries || [];

const statements = summaries.map((s, idx) => ({
  statement: `
    MERGE (c:Community {id: $communityId_${idx}})
    SET c.title = $title_${idx},
        c.summary = $summary_${idx},
        c.key_themes = $themes_${idx},
        c.member_count = $memberCount_${idx},
        c.updated_at = datetime()
    WITH c
    UNWIND $memberIds_${idx} AS memberId
    MATCH (e:Entity {id: memberId})
    MERGE (e)-[:BELONGS_TO]->(c)
  `,
  parameters: {
    [`communityId_${idx}`]: s.community_id,
    [`title_${idx}`]: s.title,
    [`summary_${idx}`]: s.summary,
    [`themes_${idx}`]: s.key_themes,
    [`memberCount_${idx}`]: s.member_count,
    [`memberIds_${idx}`]: s.member_ids || []
  }
}));

return { statements };
```

#### P09b — Postgres (pour retrieval rapide)

```sql
INSERT INTO community_summaries (community_id, title, summary, key_themes, member_count, tenant_id, updated_at)
VALUES ($1, $2, $3, $4, $5, $6, NOW())
ON CONFLICT (community_id, tenant_id) 
DO UPDATE SET title = $2, summary = $3, key_themes = $4, member_count = $5, updated_at = NOW()
```

---

## 5. Index des patchs

### Convention de nommage des nœuds

| Patch | Node ID (pour le JSON) | Node Name | Type |
|-------|------------------------|-----------|------|
| P01 | `contextual-retrieval-prep` | Prepare Contextual Prompts | code |
| P01 | `contextual-retrieval-split` | Split Chunks for Context | splitInBatches |
| P01 | `contextual-retrieval-llm` | Contextual LLM Call | httpRequest |
| P01 | `contextual-retrieval-agg` | Aggregate Contextual Chunks | code |
| P02 | `bm25-sparse-gen` | BM25 Sparse Vector Generator | code |
| P03 | (modifier existant) | Generate Embeddings V4 | httpRequest |
| P03 | (modifier existant) | Prepare Vectors V4 (Hybrid) | code |
| P04 | (remplacer existant) | Chunk Validator & Enricher V4 | code |
| P05 | `qa-split` | Split Chunks for Q&A | splitInBatches |
| P05 | (modifier existant) | Q&A Generator V4 | httpRequest |
| P05 | (modifier existant) | Q&A Enricher V4 | code |
| P06 | `entity-split` | Split Sources | splitInBatches |
| P06 | (modifier existant) | Entity Extraction (per source) | httpRequest |
| P06 | `entity-aggregate` | Aggregate Entities | code |
| P07 | `global-entity-resolution` | Global Entity Resolution | code |
| P08 | `fetch-communities` | Fetch Communities | httpRequest |
| P08 | `community-split` | Split Communities | splitInBatches |
| P08 | `community-summary-llm` | Community Summary LLM | httpRequest |
| P08 | `community-summary-agg` | Aggregate Summaries | code |
| P09 | `store-summaries-neo4j` | Store Summaries Neo4j | httpRequest |
| P09 | `store-summaries-postgres` | Store Summaries Postgres | postgres |

### Ordre d'implémentation recommandé

```
SESSION 1 (P0 — Impact maximum):
  1. P04 — Chunker Fallback (prérequis, rend le pipeline robuste)
  2. P01 — Contextual Retrieval (le gain le plus important: -49% erreurs)
  3. P03 — Embedding Model Upgrade (modif simple, +15 pts MTEB)
  4. P02 — BM25 Sparse Vectors (+30-50% recall)
  5. P05 — Q&A per-chunk (correctif, gain modéré)

SESSION 2 (P1 — GraphRAG complet):
  6. P06 — Chunk-level Entity Extraction
  7. P07 — Global Entity Resolution
  8. P08 — Community Summary Generator
  9. P09 — Store Community Summaries
  10. Modifier Relationship Mapper pour utiliser P07

SESSION 3 (P2 — Avancé, hors scope actuel):
  - Agentic RAG / CRAG (pipeline de retrieval, pas d'ingestion)
  - Late Interaction / ColBERT
  - Bayesian RAG
```

### Connexions JSON à modifier

#### Ingestion V4 — Nouvelles connexions

```json
{
  "Semantic Chunker V4": {
    "main": [[ { "node": "Chunk Validator & Enricher V4", "type": "main", "index": 0 } ]]
  },
  "Chunk Validator & Enricher V4": {
    "main": [[ { "node": "Prepare Contextual Prompts", "type": "main", "index": 0 } ]]
  },
  "Prepare Contextual Prompts": {
    "main": [[ { "node": "Split Chunks for Context", "type": "main", "index": 0 } ]]
  },
  "Split Chunks for Context": {
    "main": [
      [ { "node": "Contextual LLM Call", "type": "main", "index": 0 } ],
      [ { "node": "Aggregate Contextual Chunks", "type": "main", "index": 0 } ]
    ]
  },
  "Contextual LLM Call": {
    "main": [[ { "node": "Split Chunks for Context", "type": "main", "index": 0 } ]]
  },
  "Aggregate Contextual Chunks": {
    "main": [[ { "node": "Split Chunks for Q&A", "type": "main", "index": 0 } ]]
  },
  "Split Chunks for Q&A": {
    "main": [
      [ { "node": "Q&A Generator V4", "type": "main", "index": 0 } ],
      [ { "node": "Q&A Enricher V4", "type": "main", "index": 0 } ]
    ]
  },
  "Q&A Generator V4": {
    "main": [[ { "node": "Split Chunks for Q&A", "type": "main", "index": 0 } ]]
  },
  "Q&A Enricher V4": {
    "main": [[ { "node": "Version Manager", "type": "main", "index": 0 } ]]
  },
  "Version Manager": {
    "main": [[ { "node": "Generate Embeddings V4", "type": "main", "index": 0 } ]]
  },
  "Generate Embeddings V4": {
    "main": [[ { "node": "BM25 Sparse Vector Generator", "type": "main", "index": 0 } ]]
  },
  "BM25 Sparse Vector Generator": {
    "main": [[ { "node": "Prepare Vectors V4 (Hybrid)", "type": "main", "index": 0 } ]]
  },
  "Prepare Vectors V4 (Hybrid)": {
    "main": [
      [ { "node": "Pinecone Upsert", "type": "main", "index": 0 },
        { "node": "Postgres Store", "type": "main", "index": 0 } ]
    ]
  }
}
```

#### Enrichissement V4 — Nouvelles connexions

```json
{
  "Normalize & Merge": {
    "main": [[ { "node": "Split Sources", "type": "main", "index": 0 } ]]
  },
  "Split Sources": {
    "main": [
      [ { "node": "Entity Extraction (per source)", "type": "main", "index": 0 } ],
      [ { "node": "Aggregate Entities", "type": "main", "index": 0 } ]
    ]
  },
  "Entity Extraction (per source)": {
    "main": [[ { "node": "Split Sources", "type": "main", "index": 0 } ]]
  },
  "Aggregate Entities": {
    "main": [[ { "node": "Global Entity Resolution", "type": "main", "index": 0 } ]]
  },
  "Global Entity Resolution": {
    "main": [[ { "node": "Relationship Mapper V4", "type": "main", "index": 0 } ]]
  },
  "Relationship Mapper V4": {
    "main": [
      [ { "node": "Upsert Vectors Pinecone", "type": "main", "index": 0 } ],
      [ { "node": "Store Metadata Postgres", "type": "main", "index": 0 } ],
      [ { "node": "Update Graph Neo4j", "type": "main", "index": 0 } ]
    ]
  },
  "Update Graph Neo4j": {
    "main": [[ { "node": "Community Detection Trigger", "type": "main", "index": 0 } ]]
  },
  "Community Detection Trigger": {
    "main": [[ { "node": "Fetch Communities", "type": "main", "index": 0 } ]]
  },
  "Fetch Communities": {
    "main": [[ { "node": "Split Communities", "type": "main", "index": 0 } ]]
  },
  "Split Communities": {
    "main": [
      [ { "node": "Community Summary LLM", "type": "main", "index": 0 } ],
      [ { "node": "Aggregate Summaries", "type": "main", "index": 0 } ]
    ]
  },
  "Community Summary LLM": {
    "main": [[ { "node": "Split Communities", "type": "main", "index": 0 } ]]
  },
  "Aggregate Summaries": {
    "main": [
      [ { "node": "Store Summaries Neo4j", "type": "main", "index": 0 },
        { "node": "Store Summaries Postgres", "type": "main", "index": 0 } ]
    ]
  },
  "Store Summaries Neo4j": {
    "main": [[ { "node": "Prepare Lock Release", "type": "main", "index": 0 } ]]
  },
  "Store Summaries Postgres": {
    "main": [[ { "node": "Prepare Lock Release", "type": "main", "index": 0 } ]]
  }
}
```

---

## Annexe A — Schéma Postgres pour Community Summaries

```sql
CREATE TABLE IF NOT EXISTS community_summaries (
  id SERIAL PRIMARY KEY,
  community_id VARCHAR(64) NOT NULL,
  title VARCHAR(500),
  summary TEXT,
  key_themes JSONB DEFAULT '[]',
  member_count INTEGER DEFAULT 0,
  tenant_id VARCHAR(64) NOT NULL DEFAULT 'default',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(community_id, tenant_id)
);

CREATE INDEX idx_community_summaries_tenant ON community_summaries(tenant_id);
CREATE INDEX idx_community_summaries_themes ON community_summaries USING GIN(key_themes);
```

## Annexe B — Index Elasticsearch pour BM25 (Option B)

```json
{
  "settings": {
    "number_of_shards": 2,
    "number_of_replicas": 1,
    "analysis": {
      "analyzer": {
        "rag_analyzer": {
          "type": "custom",
          "tokenizer": "standard",
          "filter": ["lowercase", "asciifolding", "french_stop", "french_stemmer"]
        }
      },
      "filter": {
        "french_stop": { "type": "stop", "stopwords": "_french_" },
        "french_stemmer": { "type": "stemmer", "language": "light_french" }
      }
    }
  },
  "mappings": {
    "properties": {
      "content": { "type": "text", "analyzer": "rag_analyzer" },
      "contextual_content": { "type": "text", "analyzer": "rag_analyzer" },
      "parent_id": { "type": "keyword" },
      "parent_filename": { "type": "keyword" },
      "document_title": { "type": "text" },
      "section": { "type": "keyword" },
      "topic": { "type": "keyword" },
      "tenant_id": { "type": "keyword" },
      "hypothetical_questions": { "type": "text", "analyzer": "rag_analyzer" },
      "ingested_at": { "type": "date" }
    }
  }
}
```

## Annexe C — Credentials à ajouter dans n8n

| Credential Name | Type | Usage |
|----------------|------|-------|
| DeepSeek API Key | httpHeaderAuth | Contextual Retrieval, Community Summaries |
| Elasticsearch | httpHeaderAuth | BM25 Index (Option B) |
| Qwen Embedding Server | httpHeaderAuth | Self-hosted embedding |
| Qwen Reranker Server | httpHeaderAuth | Self-hosted reranker (retrieval pipeline) |
