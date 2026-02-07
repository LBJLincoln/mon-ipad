# Incremental Evaluation Plan — SOTA 2026

## Overview

This document defines the phased evaluation strategy for the 4 RAG pipelines.
Each phase increases question volume and complexity. **A phase is only started
when its data requirements are fully met in all target databases, and the
previous phase has reached its accuracy gate.**

Phase 1 is the iterative improvement loop: workflows are tuned, re-evaluated,
and tuned again until targets are met. Only then does evaluation scale up.

---

## Phase Summary

| Phase | Questions | Datasets | DB Requirement | Accuracy Gate |
|---|---|---|---|---|
| **1 — Baseline** | 200 (50/pipeline) | Hand-crafted + curated HF | Existing seed data | ≥75% overall, all pipelines ≥ their target |
| **2 — Expand** | 1,000 (500 graph + 500 quant) | musique, 2wiki, finqa, tatqa, convfinqa, wikitablequestions | Ingest question contexts into DBs | Phase 1 gates passed |
| **3 — Scale** | ~9,500 (16 HF datasets) | All 16 datasets from push-all-datasets.py | Full dataset ingestion via Benchmark workflows | Phase 2 ≥70% per pipeline |
| **4 — Full HF** | ~100K+ (expanded samples) | Same 16 datasets, 10× larger samples | Extended ingestion + DB capacity | Phase 3 ≥75% per pipeline |
| **5 — Million** | 1M+ (full datasets) | All available HF splits | Full production infrastructure | Phase 4 ≥80% per pipeline |

---

## Phase 1: Baseline (200 Questions)

### Purpose
Establish a reliable baseline AND iteratively improve all 4 workflows until
each pipeline meets its accuracy target. This phase is the improvement loop —
evaluation and workflow patching alternate until targets are reached.

### Question Breakdown

| Pipeline | Count | Source File | Source |
|---|---|---|---|
| Standard | 50 | `benchmark-standard-orchestrator-questions.json` | Curated from Pinecone namespaces (squad_v2, triviaqa, popqa) |
| Graph | 50 | `benchmark-50x2-questions.json` | Curated for Neo4j seeded entities |
| Quantitative | 50 | `benchmark-50x2-questions.json` | Curated for Supabase financial tables |
| Orchestrator | 50 | `benchmark-standard-orchestrator-questions.json` | Mix: routing across all pipelines |

### DB Data Readiness

#### Pinecone (Standard RAG) ✅ READY
- **10,411 vectors** across 12 namespaces
- Standard questions reference namespaces: `benchmark-squad_v2` (1,000 vectors), `benchmark-triviaqa` (1,000), `benchmark-popqa` (1,000)
- All 50 standard questions have matching content in Pinecone

#### Neo4j (Graph RAG) ✅ READY
- **110 entities, 151 relationships** (post-enrichment)
- 11 relationship types: A_CREE, CONNECTE, CAUSE_PAR, PROTEGE_CONTRE, ETUDIE, UTILISE, CIBLE, EXPOSE_A, VISE_A_LIMITER, SOUS_ENSEMBLE_DE, ETEND
- Entity types: Person (41), Organization (21), Technology (19), City (16), Concept (12), Disease (6), Museum (6), Rate (4), Molecule (3), Award (3), Artwork (2), Law (2), Country (2), Discovery (2), Agreement (1), Treatment (1), Article (1), Monument (1), Theory (1), Element (1)
- All 50 graph questions reference entities present in Neo4j (Einstein, Curie, Fleming, Tesla, Turing, etc.)
- Community summaries: 9 summaries in Supabase covering all entity clusters

#### Supabase (Quantitative RAG) ✅ READY
- **5 tables, 88 rows total**
  - `financials`: 24 rows (3 companies × 4 years × 2 periods)
  - `balance_sheet`: 12 rows (3 companies × 4 years)
  - `sales_data`: 16 rows (transaction-level data)
  - `products`: 18 rows (product catalog)
  - `employees`: 9 rows (employee records)
- Companies: TechVision Inc, GreenEnergy Corp, HealthPlus Labs
- All 50 quant questions target these exact tables and companies
- **Known gap**: `employees` table has only 9 rows — some employee-specific questions may fail

### Accuracy Targets (Gate Criteria)

| Pipeline | Baseline | Target | Gap | Status |
|---|---|---|---|---|
| Standard | 78% | ≥85% | -7% | ITERATING |
| Graph | 50% | ≥70% | -20% | ITERATING |
| Quantitative | 80% | ≥85% | -5% | ITERATING |
| Orchestrator | 48% | ≥70% | -22% | ITERATING |
| **Overall** | **64%** | **≥75%** | **-11%** | **ITERATING** |

### Iteration Strategy
1. Run evaluation → analyze failures
2. Identify root cause (entity miss, timeout, SQL error, retrieval miss)
3. Apply targeted workflow patch
4. Record change in `workflow_changes` (dashboard tracks before/after)
5. Re-run evaluation on same 200 questions
6. Repeat until all gates pass

### Phase 1 Exit Criteria
- [ ] Standard ≥ 85% accuracy
- [ ] Graph ≥ 70% accuracy
- [ ] Quantitative ≥ 85% accuracy
- [ ] Orchestrator ≥ 70% accuracy, <15s P95 latency, <5% error rate
- [ ] Overall ≥ 75% accuracy
- [ ] At least 3 consecutive evaluation runs with stable results (no regression)

---

## Phase 2: Expand (1,000 Questions)

### Purpose
Test pipelines against diverse, real-world questions from HuggingFace benchmark
datasets. These questions are harder and more varied than Phase 1.

### Question Breakdown

| Pipeline | Count | Datasets | Source File |
|---|---|---|---|
| Graph | 500 | musique (multi-hop), 2wikimultihopqa (multi-hop) | `rag-1000-test-questions.json` |
| Quantitative | 500 | finqa, tatqa, convfinqa, wikitablequestions | `rag-1000-test-questions.json` |

**Note**: Standard and Orchestrator are NOT tested in Phase 2 — they continue
iterating on Phase 1 questions until Phase 3.

### DB Data Readiness

#### Neo4j (Graph — 500 questions) ❌ NOT READY — Ingestion Required

**Problem**: Phase 2 graph questions come from musique and 2wikimultihopqa
datasets. These questions reference completely different entities than those
seeded in Phase 1 (SpongeBob characters, historical rabbis, Slovak districts,
etc.). The current Neo4j graph has NO data for these questions.

**Each question includes its own context** (supporting paragraphs) but this
context has NOT been ingested into Neo4j.

**Required Actions**:
1. Extract entities from each question's `context` field (20 paragraphs/question)
2. Build entity relationships from supporting_facts
3. Seed into Neo4j with proper labels and relationship types
4. Update community summaries in Supabase

**Estimated Neo4j growth**: ~500 questions × ~5 entities/question = ~2,500 new entities + ~3,000 relationships

**Implementation path**:
- Option A: Extend `populate-neo4j-entities.py` with LLM-based entity extraction from context
- Option B: Use `WF-Benchmark-Dataset-Ingestion` workflow to ingest via n8n
- Option C: Pre-process questions, extract entities, batch-create Cypher

#### Supabase (Quantitative — 500 questions) ❌ NOT READY — Ingestion Required

**Problem**: Phase 2 quantitative questions come from FinQA, TAT-QA, ConvFinQA,
and WikiTableQuestions. These questions reference financial reports, tables, and
data that do NOT exist in the current Supabase tables.

**Each question includes its own `table_data`** (structured tables from
financial reports) but these tables have NOT been created in Supabase.

**Required Actions**:
1. Parse `table_data` from each question
2. Create dynamic tables or a universal table schema in Supabase
3. Insert table data per question/dataset
4. Ensure WF4's SQL generation can query these new tables

**Estimated Supabase growth**: ~500 questions × ~1 table/question = ~500 new tables or ~10,000 rows in a universal table

**Implementation path**:
- Option A: Create per-dataset tables (finqa_reports, tatqa_tables, etc.)
- Option B: Universal `benchmark_tables` table with JSONB column for flexible data
- Option C: Use `WF-Benchmark-Dataset-Ingestion` workflow

#### Pinecone (not directly tested in Phase 2) ✅ NO CHANGE NEEDED

### Accuracy Targets (Gate Criteria)

| Pipeline | Target | Note |
|---|---|---|
| Graph | ≥60% | Lower than Phase 1 target because questions are harder (multi-hop from unfamiliar domains) |
| Quantitative | ≥70% | Lower because financial report questions are more complex than simple lookups |

### Phase 2 Exit Criteria
- [ ] All 1,000 questions' data has been ingested into target DBs
- [ ] Graph ≥ 60% on 500 new questions
- [ ] Quantitative ≥ 70% on 500 new questions
- [ ] Phase 1 results have NOT regressed (re-run 200q to confirm)
- [ ] Combined (Phase 1 + Phase 2 = 1,200 questions): ≥65% overall

---

## Phase 3: Scale (~9,500 Questions)

### Purpose
Full evaluation across all 16 HuggingFace datasets defined in `push-all-datasets.py`.
This validates the system against the standard RAG benchmarks used by the research
community.

### Question Breakdown

| Tier | Pipeline | Datasets | Sample Size |
|---|---|---|---|
| Tier 1 — Graph | Graph | musique (200), 2wikimultihopqa (300), hotpotqa (1,000) | 1,500 |
| Tier 2 — Quant | Quantitative | finqa (200), tatqa (150), convfinqa (100), wikitablequestions (50) | 500 |
| Tier 3 — Standard | Standard | frames (1,000), triviaqa (1,000), squad_v2 (1,000), popqa (1,000), msmarco (1,000), asqa (1,000), narrativeqa (1,000), pubmedqa (500), natural_questions (1,000) | 8,500 |
| Cross-pipeline | Orchestrator | Random mix from all tiers | ~1,000 |
| **Total** | | **16 datasets** | **~11,500** |

### DB Data Readiness

#### Pinecone (Standard — 8,500 questions) ⚠️ PARTIAL — Ingestion Required

**Current state**: 10,411 vectors across 12 namespaces. Some namespaces already
have data from prior ingestion:
- `benchmark-squad_v2`: 1,000 vectors
- `benchmark-triviaqa`: 1,000 vectors
- `benchmark-popqa`: 1,000 vectors
- `benchmark-msmarco`: 1,000 vectors
- `benchmark-asqa`: 948 vectors
- `benchmark-narrativeqa`: 1,000 vectors
- `benchmark-pubmedqa`: 500 vectors
- `benchmark-natural_questions`: 1,000 vectors
- `benchmark-hotpotqa`: 1,000 vectors
- `benchmark-frames`: 824 vectors

**Assessment**: ~9,272 vectors already exist for these datasets. However, the
current vectors are from context documents, not necessarily the specific
documents needed to answer the sampled questions.

**Required Actions**:
1. Verify that existing Pinecone vectors cover the Phase 3 questions
2. For any gaps, embed additional context documents
3. For FRAMES (824/1000), may need to embed additional documents
4. Run `push-all-datasets.py` Phase 2 (ingest) for any missing datasets

**Estimated Pinecone growth**: ~2,000-5,000 additional vectors

#### Neo4j (Graph — 1,500 questions) ❌ REQUIRES PHASE 2 COMPLETION + EXPANSION

- Phase 2 ingests musique + 2wiki entities
- Phase 3 adds hotpotqa (1,000 questions) requiring ~1,000 new entities
- Total expected: ~4,000+ entities, ~5,000+ relationships

#### Supabase (Quantitative — 500 questions) ⚠️ PARTIAL — Depends on Phase 2

- Phase 2 creates the table infrastructure for HF financial datasets
- Phase 3 uses the SAME datasets with slightly larger samples (some overlap)
- finqa: Phase 2 used 200, Phase 3 also 200 (same or overlapping)
- New: wikitablequestions (50) may need additional table structures

#### Orchestrator — Depends on all above pipelines being ready

### Accuracy Targets

| Pipeline | Target | Justification |
|---|---|---|
| Standard | ≥75% | Research benchmarks are harder than curated questions |
| Graph | ≥55% | Multi-hop from diverse domains is significantly harder |
| Quantitative | ≥65% | Complex financial calculations across varied table schemas |
| Orchestrator | ≥60% | Must route correctly across diverse question types |
| **Overall** | **≥65%** | |

### Phase 3 Exit Criteria
- [ ] All 16 datasets ingested into target DBs (verified by `push-all-datasets.py`)
- [ ] Standard ≥ 75% on 8,500 questions
- [ ] Graph ≥ 55% on 1,500 questions
- [ ] Quantitative ≥ 65% on 500 questions
- [ ] Orchestrator ≥ 60% on 1,000 questions
- [ ] Error rate < 10% across all pipelines
- [ ] P95 latency < 20s for orchestrator

---

## Phase 4: Full HuggingFace (~100K+ Questions)

### Purpose
Expand sample sizes by 10× to validate robustness at scale and identify
long-tail failure patterns not visible in smaller samples.

### Question Volumes

| Dataset | Phase 3 Sample | Phase 4 Sample | Full HF Size |
|---|---|---|---|
| musique | 200 | 2,000 | ~25,000 |
| 2wikimultihopqa | 300 | 3,000 | ~167,000 |
| hotpotqa | 1,000 | 10,000 | ~113,000 |
| finqa | 200 | 2,000 | ~8,000 |
| tatqa | 150 | 1,500 | ~16,000 |
| convfinqa | 100 | 1,000 | ~3,000 |
| wikitablequestions | 50 | 500 | ~22,000 |
| frames | 1,000 | All (824) | ~824 |
| triviaqa | 1,000 | 10,000 | ~95,000 |
| squad_v2 | 1,000 | 10,000 | ~130,000 |
| popqa | 1,000 | 10,000 | ~14,000 |
| msmarco | 1,000 | 10,000 | ~1,000,000 |
| asqa | 1,000 | 6,000 | ~6,000 |
| narrativeqa | 1,000 | 10,000 | ~46,000 |
| pubmedqa | 500 | 5,000 | ~212,000 |
| natural_questions | 1,000 | 10,000 | ~307,000 |
| **Total** | **~10,500** | **~91,824** | **~2,165,000** |

### DB Requirements
- **Pinecone**: ~100K vectors (may need paid tier upgrade from free)
- **Neo4j**: ~15,000+ entities, ~20,000+ relationships (may need Aura Pro)
- **Supabase**: ~50,000+ rows across financial tables (within free tier)
- **Cost estimate**: ~$5-15 for LLM/embedding API calls

### Accuracy Targets
Same as Phase 3 (maintain, not improve — the goal is scale validation).

### Phase 4 Exit Criteria
- [ ] No accuracy regression vs Phase 3 (within 5% margin)
- [ ] Error rate stable (no new error categories emerging)
- [ ] Latency P95 remains within acceptable bounds
- [ ] Cost per question documented

---

## Phase 5: Million+ Questions (Full Production)

### Purpose
Full-scale production evaluation using complete HuggingFace dataset splits.
This is the final validation before the system is considered production-ready.

### Scope
- All available questions from all 16 datasets (~2.2M)
- Requires production-grade infrastructure
- Estimated duration: days (not hours) of continuous evaluation
- Full cost tracking becomes critical

### Infrastructure Requirements
- **Pinecone**: Paid plan (Standard tier minimum)
- **Neo4j**: Aura Professional (increased storage + query performance)
- **Supabase**: Pro plan (connection pooling for sustained load)
- **n8n**: Cloud plan may need upgrade for concurrent execution limits
- **Estimated cost**: $50-200 for API calls + potential infrastructure upgrades

### Phase 5 Exit Criteria
- [ ] All pipelines maintain Phase 4 accuracy levels at scale
- [ ] System sustains evaluation throughput (>100 questions/hour)
- [ ] Total cost documented and within budget
- [ ] Comprehensive failure analysis report generated

---

## Database Growth Projection

| Metric | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Phase 5 |
|---|---|---|---|---|---|
| **Pinecone vectors** | 10,411 | 10,411 | ~15,000 | ~100,000 | ~500,000+ |
| **Neo4j nodes** | 110 | ~2,500 | ~4,000 | ~15,000 | ~50,000+ |
| **Neo4j relationships** | 151 | ~3,000 | ~5,000 | ~20,000 | ~75,000+ |
| **Supabase rows** | 88 | ~10,000 | ~12,000 | ~50,000 | ~200,000+ |
| **Community summaries** | 9 | ~50 | ~100 | ~300 | ~1,000+ |
| **Questions tested** | 200 | 1,200 | ~11,500 | ~100,000 | ~2,200,000 |

---

## Ingestion Dependencies Diagram

```
Phase 1 (200q)
  └── DB: Seed data ✅ READY
  └── Gate: All pipelines ≥ target
        │
        ▼
Phase 2 (1,000q)
  ├── REQUIRES: Entity extraction from question contexts → Neo4j
  ├── REQUIRES: Table data parsing from questions → Supabase
  └── Gate: Graph ≥60%, Quant ≥70%, no Phase 1 regression
        │
        ▼
Phase 3 (~9,500q)
  ├── REQUIRES: push-all-datasets.py execution (all 16 datasets)
  ├── REQUIRES: Pinecone embedding for new context documents
  ├── REQUIRES: Neo4j expansion for hotpotqa entities
  └── Gate: All pipelines ≥ targets, error rate <10%
        │
        ▼
Phase 4 (~100Kq)
  ├── REQUIRES: 10× data ingestion (LLM + embedding costs)
  ├── REQUIRES: Pinecone plan upgrade (if >100K vectors)
  └── Gate: No regression from Phase 3
        │
        ▼
Phase 5 (1M+q)
  ├── REQUIRES: Production infrastructure (all DBs)
  ├── REQUIRES: Multi-day evaluation scheduling
  └── Gate: Sustained accuracy + throughput
```

---

## Cost Projections Per Phase

| Phase | LLM Calls | Embedding Calls | DB Operations | Est. Total |
|---|---|---|---|---|
| 1 (200q) | ~$0.03 | $0.00 | $0.00 | **~$0.03** |
| 2 (1,000q) | ~$0.15 | ~$0.05 | $0.00 | **~$0.20** |
| 3 (~10Kq) | ~$1.50 | ~$0.50 | $0.00 | **~$2.00** |
| 4 (~100Kq) | ~$15.00 | ~$5.00 | $0.00 | **~$20.00** |
| 5 (1M+q) | ~$150.00 | ~$50.00 | Infrastructure | **~$200+** |

*Note: Costs assume Google Gemini Flash ($0.075/1M input, $0.30/1M output)
and OpenAI text-embedding-3-small ($0.02/1M tokens). Infrastructure costs
(Pinecone paid, Neo4j Pro, Supabase Pro) are additional.*

---

## Dashboard Integration

The dashboard (`docs/index.html`) tracks phase progression with:

1. **Phase Progress Bar** — Current phase, completion %, gate status
2. **Phase-Specific Metrics** — Each pipeline's accuracy vs its phase target
3. **DB Readiness Indicators** — Per-database status for current + next phase
4. **Scaling Chart** — Questions tested over time across phases
5. **Gate Checklist** — Visual checklist of exit criteria for current phase

Data stored in `docs/data.json` under:
- `evaluation_phases` — Phase definitions, gates, status
- `current_phase` — Active phase number and iteration count
- History entries tagged with phase number for trend analysis
