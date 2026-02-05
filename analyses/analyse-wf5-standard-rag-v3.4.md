# Analyse Workflow: WF5 Standard RAG V3.4

> **Workflow Analyzer Report** | Date: 2026-02-05
> **Fichier source**: `TEST - SOTA 2026 - WF5 Standard RAG V3.4 - CORRECTED.json`
> **ID n8n**: `qtBs2Wbi_raU2o_dqfdDC`

---

## 1. Vue d'ensemble

### Architecture actuelle (DAG)

```
ENTRY POINTS (3 triggers):
├─ Sub-Workflow Trigger ──┐
├─ Webhook ────────────────┼─> Init & ACL Pre-Filter V3.4
└─ When chat message received ─┘

Init & ACL Pre-Filter V3.4 (complexity detection, adaptive topK)
  -> Needs Decomposition?
    |-- TRUE -> Query Decomposer (V.3.4) [LLM - Gemini Flash]
    |             -> Query Merger V3.4
    |-- FALSE -> HyDE Generator / Original Embedding / BM25 (direct)

Query Merger V3.4
  |
  ├──> HyDE Generator [LLM] -> HyDE Embedding [API] -> Pinecone HyDE Search
  ├──> Original Embedding [API] -> Pinecone Original Search
  └──> BM25 Search Postgres
  |
  -> Wait All Branches (Merge)
    -> RRF Merge & Rank V3.4 (Reciprocal Rank Fusion)
      -> Cohere Reranker
        -> Rerank Merger (40% RRF + 60% Cohere)
          -> Skip LLM?
            |-- NO results -> Response Formatter (empty)
            |-- HAS results -> LLM Generation [LLM]
            |                    -> Response Formatter
```

**Nombre de noeuds**: 21 (dont 1 sticky note)
**Noeuds actifs**: 20
**Parallélisation**: Oui (HyDE + Original + BM25 en parallele)
**Hybrid Search**: Oui (Dense Pinecone + Sparse BM25 + HyDE)

---

## 2. Score global

| Catégorie | Score | Commentaire |
|-----------|-------|-------------|
| Performance | 65/100 | Hybrid search (HyDE+Pinecone+BM25), RRF fusion, adaptive topK |
| Résilience | 60/100 | Reranker fallback OK, mais BM25 sans tenant, query decomposer pas de fallback |
| Sécurité | 50/100 | ACL inverted logic bug, BM25 sans tenant filter |
| Maintenabilité | 55/100 | Code clair avec versions dans les noms, mais routing complexe |
| Architecture | 65/100 | Meilleure architecture RAG du projet (HyDE + RRF + Reranking) |
| **SCORE GLOBAL** | **59/100** | **Le plus avance des RAG queries, quelques bugs critiques** |

---

## 3. Issues identifiées

### CRITIQUE (P0)

#### ISSUE-SR-01: BM25 sans tenant_id filter
- **Sévérité**: critical
- **Catégorie**: sécurité
- **Noeud**: `BM25 Search Postgres`
- **Description**: La requete SQL BM25 est `WHERE is_obsolete = false AND to_tsvector(...)`. Aucune clause `AND tenant_id = '...'` n'est presente. En mode multi-tenant, les resultats BM25 peuvent contenir des documents d'autres tenants.
- **Impact**: Fuite de donnees cross-tenant via les resultats BM25
- **Recommandation**: Ajouter `AND tenant_id = $2` dans la clause WHERE, avec le tenant_id de l'utilisateur courant.
- **Effort**: easy

#### ISSUE-SR-02: ACL filter logic inversee
- **Sévérité**: critical
- **Catégorie**: sécurité
- **Noeud**: `Init & ACL Pre-Filter V3.4`
- **Description**: Le code fait `disableAcl = input.disable_acl !== false`. Cela signifie:
  - `disable_acl` non fourni -> `undefined !== false` -> `true` -> ACL desactivee
  - `disable_acl = false` -> `false !== false` -> `false` -> ACL activee
  - `disable_acl = true` -> `true !== false` -> `true` -> ACL desactivee
  - Semantiquement inversé: quand on ne precise pas, l'ACL est desactivee par defaut.
- **Impact**: ACL desactivee par defaut en production
- **Recommandation**: Corriger en `disableAcl = (input.disable_acl === true)` pour que l'ACL soit activee par defaut.
- **Effort**: easy

### HAUTE (P1)

#### ISSUE-SR-03: False branch de "Needs Decomposition?" mal routee
- **Sévérité**: high
- **Catégorie**: architecture
- **Noeud**: `Needs Decomposition?`
- **Description**: La branche FALSE connecte directement vers HyDE Generator, Original Embedding et BM25 Search, mais ces noeuds lisent les parametres (queries, topK) depuis `Query Merger V3.4`. Or, quand decomposition=false, Query Merger n'est pas executé. Les noeuds de retrieval utiliseront des donnees stale ou vides.
- **Impact**: Requetes simples (sans decomposition) ne recoivent pas les parametres corrects
- **Recommandation**: Router la branche FALSE vers Query Merger V3.4 aussi (le merger gere le cas non-decompose), ou faire en sorte que les noeuds de retrieval lisent directement depuis Init & ACL.
- **Effort**: medium

#### ISSUE-SR-04: Cohere Reranker recoit placeholder quand skip
- **Sévérité**: high
- **Catégorie**: résilience
- **Noeud**: `Cohere Reranker`
- **Description**: Quand `skip_reranker=true`, le noeud envoie `["placeholder"]` comme documents a Cohere au lieu de ne pas appeler du tout. Cohere repondra avec un resultat invalide ou une erreur.
- **Impact**: Appel API inutile, erreur Cohere, fallback systematique
- **Recommandation**: Ajouter un noeud IF avant Cohere qui skip l'appel si `skip_reranker=true`.
- **Effort**: easy

#### ISSUE-SR-05: Pas de OTEL Export
- **Sévérité**: high
- **Catégorie**: maintenabilité
- **Description**: Contrairement aux autres workflows, WF5 n'a aucun noeud OTEL Export. Aucune trace n'est envoyee. Zero observabilite.
- **Impact**: Impossible de diagnostiquer les problemes ou mesurer les performances
- **Recommandation**: Ajouter un noeud OTEL Export en fin de pipeline.
- **Effort**: easy

#### ISSUE-SR-06: RRF weights non justifies
- **Sévérité**: high
- **Catégorie**: performance
- **Noeud**: `RRF Merge & Rank V3.4`
- **Description**: Les boost factors (hyde=1.3, bm25=1.2, pinecone=1.0) sont arbitraires. Pas de benchmark ni d'A/B testing pour justifier ces valeurs. De plus, le decomposition_boost (1.1) est applique uniformement a tous les resultats.
- **Recommandation**: Implementer un systeme d'evaluation offline (patch S01) pour calibrer les poids optimaux sur un jeu de donnees de test.
- **Effort**: hard

### MOYENNE (P2)

#### ISSUE-SR-07: Score fusion Rerank hardcodee (40/60)
- **Sévérité**: medium
- **Catégorie**: performance
- **Noeud**: `Rerank Merger`
- **Description**: La fusion est fixee a 40% RRF + 60% Cohere. Ces poids ne sont pas configurables et ne s'adaptent pas au type de requete.
- **Recommandation**: Rendre les poids configurables via variables, ou adapter dynamiquement (plus de poids RRF pour les requetes techniques, plus de Cohere pour les requetes semantiques).
- **Effort**: easy

#### ISSUE-SR-08: Query Decomposer sans validation JSON
- **Sévérité**: medium
- **Catégorie**: résilience
- **Noeud**: `Query Decomposer (V.3.4)`
- **Description**: Le LLM est cense retourner un JSON `{is_simple, sub_queries}`, mais il n'y a pas de validation du format avant parsing dans Query Merger. Un JSON malformed crashera le merger.
- **Recommandation**: Ajouter un try/catch avec fallback vers la query originale dans le Query Merger (existe partiellement mais pas complet).
- **Effort**: easy

#### ISSUE-SR-09: Confidence par defaut a 0.5
- **Sévérité**: medium
- **Catégorie**: maintenabilité
- **Noeud**: `Response Formatter`
- **Description**: Quand aucune source n'est disponible, la confidence est mise a 0.5 au lieu de 0. Cela donne une fausse impression de confiance quand il n'y a aucune evidence.
- **Recommandation**: Mettre la confidence a 0 quand il n'y a aucune source.
- **Effort**: easy

#### ISSUE-SR-10: Excerpt tronque a 200 chars
- **Sévérité**: medium
- **Catégorie**: maintenabilité
- **Noeud**: `Response Formatter`
- **Description**: Les excerpts des sources sont tronques a 200 caracteres. Cela peut couper au milieu d'un mot ou d'une phrase, reduisant l'utilite de la source pour l'utilisateur.
- **Recommandation**: Tronquer au dernier espace avant 200 chars, ou au dernier point.
- **Effort**: easy

#### ISSUE-SR-11: Messages hardcodes en francais
- **Sévérité**: medium
- **Catégorie**: maintenabilité
- **Noeud**: `Rerank Merger`, `Response Formatter`
- **Description**: Les messages de fallback ("Je n'ai trouve aucun document pertinent", "Aucun document pertinent trouve") sont hardcodes en francais. Pas d'internationalisation.
- **Recommandation**: Rendre les messages configurables via variables ou les adapter a la langue de la requete.
- **Effort**: easy

### BASSE (P3)

#### ISSUE-SR-12: Embedding API appelee 2 fois separement
- **Sévérité**: low
- **Catégorie**: performance
- **Noeud**: `HyDE Embedding`, `Original Embedding`
- **Description**: Deux appels separes a l'API d'embedding (un pour le HyDE document, un pour la query originale). Ces deux appels pourraient etre batches en un seul appel API.
- **Impact**: +100-200ms latence evitable
- **Recommandation**: Batcer les deux embeddings en un seul appel API avec `input: [hyde_doc, original_query]`.
- **Effort**: medium

#### ISSUE-SR-13: console.log en production
- **Sévérité**: low
- **Catégorie**: sécurité
- **Description**: Tous les code nodes utilisent `console.log()` pour le debugging. En production, cela peut exposer des donnees sensibles dans les logs n8n.
- **Recommandation**: Supprimer les console.log ou les conditionner a un mode debug.
- **Effort**: easy

---

## 4. Patchs SOTA 2026 applicables

| Patch ID | Nom | Priorité | Statut actuel | Impact estimé |
|----------|-----|----------|---------------|---------------|
| S01 | RRF Weight Calibration (offline eval) | P2 | Poids arbitraires | Optimal fusion weights |

---

## 5. Architecture cible recommandée

```
Entry Points (3 triggers)
  -> Init & ACL Pre-Filter V4 (ACL fixed)
    -> Needs Decomposition?
      |-- TRUE -> Query Decomposer (avec validation JSON)
      |-- FALSE -> (continue)
    -> Query Merger V4 (toujours execute)
      |
      ├──> HyDE Generator -> HyDE + Original Embedding (BATCHED)
      |      -> Pinecone HyDE Search
      |      -> Pinecone Original Search
      ├──> BM25 Search Postgres (avec tenant_id filter)
      |
      -> Wait All Branches
        -> RRF Merge & Rank V4 (calibrated weights)
          -> IF skip_reranker?
            |-- FALSE -> Cohere Reranker V3.5
            |-- TRUE -> (skip)
          -> Rerank Merger (configurable fusion)
            -> Skip LLM?
              |-- NO -> Response Formatter (confidence=0)
              |-- YES -> LLM Generation
              |            -> Response Formatter
                             -> OTEL Export (NEW)
```

---

## 6. Priorités d'action

1. **IMMÉDIAT** (P0):
   - Ajouter tenant_id filter dans BM25 Postgres (ISSUE-SR-01)
   - Corriger ACL logic inversee (ISSUE-SR-02)

2. **COURT TERME** (P1):
   - Corriger routing Needs Decomposition FALSE branch (ISSUE-SR-03)
   - Ajouter IF avant Cohere pour skip (ISSUE-SR-04)
   - Ajouter OTEL Export (ISSUE-SR-05)
   - Evaluer et calibrer RRF weights (ISSUE-SR-06)

3. **MOYEN TERME** (P2):
   - Rendre score fusion configurable (ISSUE-SR-07)
   - Ajouter validation JSON Query Decomposer (ISSUE-SR-08)
   - Fixer confidence default a 0 (ISSUE-SR-09)
   - Ameliorer excerpt truncation (ISSUE-SR-10)
   - Batch embedding API calls (ISSUE-SR-12)

---

## 7. Résumé JSON (format agent)

```json
{
  "workflow": "TEST - SOTA 2026 - WF5 Standard RAG V3.4 - CORRECTED.json",
  "workflow_id": "qtBs2Wbi_raU2o_dqfdDC",
  "version": "3.4",
  "score": 59,
  "node_count": 21,
  "active_nodes": 20,
  "issues_count": {
    "critical": 2,
    "high": 4,
    "medium": 5,
    "low": 2,
    "total": 13
  },
  "strengths": [
    "Best hybrid search implementation (HyDE + Pinecone + BM25)",
    "RRF fusion with adaptive boost factors",
    "Cohere reranking with fallback to RRF-only",
    "Query decomposition for complex queries",
    "Adaptive topK based on query complexity"
  ],
  "blocking_bugs": [
    "BM25 Postgres query has no tenant_id filter - cross-tenant data leak",
    "ACL filter logic inverted - ACL disabled by default in production"
  ],
  "priority_actions": [
    "Add tenant_id filter in BM25 Postgres query",
    "Fix ACL logic: disableAcl = (input.disable_acl === true)",
    "Fix Needs Decomposition? FALSE branch routing",
    "Add IF node before Cohere Reranker to skip when no results",
    "Add OTEL Export node for observability",
    "Calibrate RRF weights with offline evaluation"
  ]
}
```
