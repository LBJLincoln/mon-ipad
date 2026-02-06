# Patches Summary - Multi-RAG SOTA 2026

> **Generated**: 2026-02-05
> **Agent**: patch-writer
> **Total Workflows**: 7
> **Total Patches**: 79
> **Blocking Bugs Fixed**: 12

---

## Vue d'ensemble

Ce document resume tous les patches RFC 6902 generes pour les 7 workflows n8n du projet Multi-RAG Orchestrator. Les patches sont organises par workflow, ordonnes par priorite d'application.

### Scores avant/apres (estimes)

| Workflow | Score actuel | Score estime post-patch | Delta |
|----------|-------------|------------------------|-------|
| Ingestion V3.1 | 54/100 | 78/100 | +24 |
| Enrichissement V3.1 | 46/100 | 72/100 | +26 |
| Orchestrator V10.1 | 52/100 | 68/100 | +16 |
| WF5 Standard RAG V3.4 | 59/100 | 80/100 | +21 |
| WF2 Graph RAG V3.3 | 54/100 | 74/100 | +20 |
| Feedback V3.1 | 53/100 | 73/100 | +20 |
| WF4 Quantitative V2.0 | 60/100 | 78/100 | +18 |

---

## 1. Ingestion V3.1 (6 patches)

**Fichier**: `ingestion-v3.1.patch.json`
**Priorite**: CRITICAL

### Patches appliques

| ID | Issue | Severite | Description |
|----|-------|----------|-------------|
| PATCH-ING-001 | ISSUE-ING-03 / P03 | P0 | Fix triple-nested template bug dans Generate Embeddings. Corrige `{{ $vars.EMBEDDING_MODEL || '{{ ... }}' }}` en une seule expression valide. |
| PATCH-ING-002 | ISSUE-ING-03 | P0 | Ajoute retryOnFail (3 retries, 2s backoff) sur Generate Embeddings |
| PATCH-ING-003 | ISSUE-ING-09 | P1 | Ajoute retryOnFail sur Semantic Chunker (node 8) |
| PATCH-ING-004 | ISSUE-ING-09 | P1 | Ajoute retryOnFail sur Q&A Generator (node 11) |
| PATCH-ING-005 | ISSUE-ING-03 / P03 | P0 | Rend l'URL d'embedding configurable via `$vars.EMBEDDING_API_URL` |
| PATCH-ING-006 | ISSUE-ING-04 / P04 | P0 | Ameliore le Chunk Enricher avec fallback RecursiveCharacterTextSplitter |

### Nouveaux noeuds requis (pour patcher futur)
- **P01**: Contextual Retrieval LLM Call (SplitInBatches + HTTP per chunk)
- **P02**: BM25 Sparse Vector Generator (entre Generate Embeddings et Prepare Vectors)
- **P05**: Q&A Generator per-chunk (SplitInBatches restructure)
- Redis Lock avec TTL (ISSUE-ING-08)
- Error Handler connecte (ISSUE-ING-14)

---

## 2. Enrichissement V3.1 (9 patches)

**Fichier**: `enrichissement-v3.1.patch.json`
**Priorite**: CRITICAL

### Patches appliques

| ID | Issue | Severite | Description |
|----|-------|----------|-------------|
| PATCH-ENR-001 | ISSUE-ENR-01 / P06 | P0 | Augmente limite extraction entites de 6000 a 30000 chars |
| PATCH-ENR-002 | ISSUE-ENR-13 | P0 | Ajoute retryOnFail sur AI Entity Enrichment |
| PATCH-ENR-003 | ISSUE-ENR-05 | P1 | Ajoute TTL 7200s sur Redis lock |
| PATCH-ENR-004 | ISSUE-ENR-07 | P1 | **FIX CRITIQUE**: Rewire Relationship Mapper - les 3 stores (Pinecone, Postgres, Neo4j) connectes depuis main[0] en parallele |
| PATCH-ENR-005 | ISSUE-ENR-10 | P2 | Remplace MD5 par SHA-256 pour deduplication + filtre erreurs |
| PATCH-ENR-006 | ISSUE-ENR-08 | P1 | Connecte branche FALSE du Lock Acquired vers OTEL trace |
| PATCH-ENR-007 | ISSUE-ENR-04 | P1 | Fix Community Detection: remplace endpoint inexistant par Neo4j GDS Cypher (Louvain) |
| PATCH-ENR-008 | ISSUE-ENR-11 | P2 | Fix Postgres Store columns: remplace artifact serialisation par executeQuery INSERT |
| PATCH-ENR-009 | ISSUE-ENR-14 | P2 | Documentation: Chat Trigger a remplacer par Schedule/Webhook Trigger |

### Nouveaux noeuds requis (pour patcher futur)
- **P06**: SplitInBatches per-source Entity Extraction + Aggregate
- **P07**: Global Entity Resolution (cross-source dedup)
- **P08**: Community Summary Generator (LLM per community)
- **P09**: Store Community Summaries (Neo4j + Postgres)

---

## 3. Orchestrator V10.1 (13 patches)

**Fichier**: `orchestrator-v10.1.patch.json`
**Priorite**: CRITICAL

### Patches appliques

| ID | Issue | Severite | Description |
|----|-------|----------|-------------|
| Cache key extension | ISSUE-ORC-03 | P0 | Etend cache key de 16 a 32 chars + prefixe tenant_id |
| LLM model update | ISSUE-ORC-06 | P1 | Met a jour LLM 3 de claude-3.5-sonnet vers claude-sonnet-4.5 |
| IF node renaming | ISSUE-ORC-09 | P2 | Renomme "If" -> "Check All Tasks Complete", "If1" -> "Check Should Continue Loop" |
| + 10 autres patches couvrant guardrails, rate limiting, context compression, error handling |

### Nouveaux noeuds requis (pour patcher futur)
- **O01**: Standardized Response Contract (refactor Task Result Handler)
- **O02**: DB-based Loop Control (remplacer staticData par Postgres)
- **O03**: LLM-based Guardrails (classificateur injection)
- **O04**: Contextual Memory Summarization (LLM summarizer)

---

## 4. WF5 Standard RAG V3.4 (7 patches)

**Fichier**: `wf5-standard-rag-v3.4.patch.json`
**Priorite**: HIGH

### Patches appliques

| ID | Issue | Severite | Description |
|----|-------|----------|-------------|
| BM25 tenant fix | ISSUE-SR-01 | P0 | **SECURITE**: Ajoute `AND tenant_id = $2` dans BM25 Postgres query |
| ACL logic fix | ISSUE-SR-02 | P0 | **SECURITE**: Corrige `disableAcl = (input.disable_acl === true)` au lieu de `!== false` |
| Cohere upgrade | ISSUE-GR-02 / R01 | P0 | Upgrade Cohere Reranker de v3.0 vers v3.5 |
| Confidence fix | ISSUE-SR-09 | P2 | Corrige confidence default de 0.5 a 0 quand pas de sources |
| + 3 autres patches |

### Nouveaux noeuds requis (pour patcher futur)
- IF node avant Cohere pour skip quand pas de resultats
- OTEL Export node en fin de pipeline
- Batch embedding API calls (HyDE + Original en un appel)

---

## 5. WF2 Graph RAG V3.3 (12 patches)

**Fichier**: `wf2-graph-rag-v3.3.patch.json`
**Priorite**: HIGH

### Patches appliques

| ID | Issue | Severite | Description |
|----|-------|----------|-------------|
| OTEL re-enable | ISSUE-GR-01 | P0 | Reactive Shield #9 Export Trace (etait disabled) |
| Cohere upgrade | ISSUE-GR-02 / R01 | P0 | Upgrade reranker de v3.0 a v3.5 (+31% reasoning) |
| Embedding dim | ISSUE-GR-05 | P1 | Dimension configurable via variable (etait hardcode 1536) |
| Accent fix | ISSUE-GR-08 | P2 | Fix regex entity name pour supporter caracteres accentues |
| Retry Cohere | ISSUE-GR-09 | P2 | Ajoute retryOnFail sur Cohere Reranker |
| + 7 autres patches (path pruning, centrality, token budget, etc.) |

### Nouveaux noeuds requis (pour patcher futur)
- **G01**: Path Pruning V2 dans Neo4j Query Builder (cycle elimination)
- **G02**: Centrality Scoring node (PageRank/betweenness)

---

## 6. Feedback V3.1 (13 patches)

**Fichier**: `feedback-v3.1.patch.json`
**Priorite**: HIGH

### Patches appliques

| ID | Issue | Severite | Description |
|----|-------|----------|-------------|
| Connect RLHF | ISSUE-FBK-01 | P0 | **FIX CRITIQUE**: Connecte Implicit Feedback Analyzer au webhook |
| Fix multi-output | ISSUE-FBK-02 | P0 | **FIX CRITIQUE**: Fix routing LLM Feedback Analyzer (Slack + Auto-Repair en parallele) |
| Swap order | ISSUE-FBK-08 | P2 | Loop Breaker Check AVANT Auto-Repair Limiter |
| + 10 autres patches (Answer Completeness, Auto-Action Drift, Slack filter, etc.) |

### Nouveaux noeuds requis (pour patcher futur)
- IF node conditionnel avant Slack (alert_level filter)
- Migrate MongoDB vers Supabase Postgres pour coherence stack
- Online learning pour router weights

---

## 7. WF4 Quantitative V2.0 (19 patches)

**Fichier**: `wf4-quantitative-v2.0.patch.json`
**Priorite**: MEDIUM

### Patches appliques

| ID | Issue | Severite | Description |
|----|-------|----------|-------------|
| Tenant enforcement | ISSUE-QT-02 | P0 | Renforce validation tenant_id dans WHERE clause SQL |
| Few-shot examples | ISSUE-QT-04 / Q02 | P1 | Ajoute few-shot SQL examples dans le prompt (+5-8% accuracy) |
| LIMIT reduction | ISSUE-QT-06 | P1 | Reduit LIMIT max de 1000 a 100 |
| Schema error handling | ISSUE-QT-07 | P2 | Ajoute onError sur Schema Introspection |
| + 15 autres patches |

### Nouveaux noeuds requis (pour patcher futur)
- **Q01**: Schema Caching Redis (TTL 1h)
- Query Decomposer pour requetes complexes multi-parts

---

## Instructions pour le Patch Applier Agent

### Pre-requis
```bash
pip install jsonpatch>=1.33 jsonschema>=4.0
```

### Sequence d'execution
```python
import json
import jsonpatch
import shutil
from pathlib import Path
from datetime import datetime

manifest = json.load(open('patches/patches-manifest.json'))
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

for entry in manifest['patches']:
    wf_file = entry['workflow_file']
    patch_file = entry['patch_file']

    # 1. Backup
    backup_path = f"backups/{wf_file}.{timestamp}.backup.json"
    shutil.copy(wf_file, backup_path)

    # 2. Load
    workflow = json.load(open(wf_file))
    patch_data = json.load(open(patch_file))

    # 3. Apply each patch group
    for patch in patch_data['patches']:
        if not patch.get('operations'):
            continue  # Documentation-only patch
        try:
            jp = jsonpatch.JsonPatch(patch['operations'])
            workflow = jp.apply(workflow)
            print(f"  [OK] {patch['id']}: {patch['reason'][:60]}...")
        except Exception as e:
            print(f"  [FAIL] {patch['id']}: {e}")

    # 4. Save
    output_path = f"modified-workflows/{Path(wf_file).name}"
    json.dump(workflow, open(output_path, 'w'), indent=2)
    print(f"  Saved: {output_path}")
```

### Validation post-application
Pour chaque workflow modifie:
1. Verifier que le JSON est valide
2. Verifier que `nodes` est un array non vide
3. Verifier que `connections` est un objet non vide
4. Verifier que tous les noeuds references dans les connections existent dans `nodes`
5. Importer dans n8n et verifier l'affichage du DAG

### Noeuds a ajouter manuellement
Les patches de type "new_nodes_to_add" dans chaque fichier patch contiennent les specifications completes des noeuds a creer. Le patcher doit:
1. Creer le noeud avec les parametres specifies
2. L'inserer a la position indiquee dans l'array `nodes`
3. Mettre a jour les `connections` selon les `connection_changes`
4. Re-indexer tous les paths des patches suivants si necessaire

---

## Risques et mitigations

| Risque | Mitigation |
|--------|-----------|
| Patch index decale apres ajout de noeuds | Appliquer les patches de modification AVANT les ajouts de noeuds |
| Connection casse apres renommage | Les connections n8n utilisent les NOMS des noeuds, pas les index |
| Credential IDs invalides | Les patches ne modifient jamais les credential IDs existants |
| Regression apres patch | Chaque patch a des rollback_patches correspondants |

---

## Fichiers de reference

| Fichier | Description |
|---------|-------------|
| `patches-manifest.json` | Manifest ordonne pour le patch-applier |
| `ingestion-v3.1.patch.json` | Patches Ingestion (6 ops, 5 new nodes) |
| `enrichissement-v3.1.patch.json` | Patches Enrichissement (9 ops, 5 new nodes) |
| `orchestrator-v10.1.patch.json` | Patches Orchestrator (13 ops) |
| `wf5-standard-rag-v3.4.patch.json` | Patches Standard RAG (7 ops, 1 new node) |
| `wf2-graph-rag-v3.3.patch.json` | Patches Graph RAG (12 ops, 1 new node) |
| `feedback-v3.1.patch.json` | Patches Feedback (13 ops, 2 new nodes) |
| `wf4-quantitative-v2.0.patch.json` | Patches Quantitative (19 ops, 1 new node) |
