# Repository Archival Analysis - Visual Summary

## MON-IPAD BREAKDOWN

```
mon-ipad/ (24 MB total)
├── datasets/            105 MB   ARCHIVE ✓
│   ├── hf/              ~100 MB  (13 benchmark datasets)
│   ├── sectors/         ~5 MB    (BTP, Finance, Industrie, Juridique)
│   ├── phase-1/         ~0.5 MB  (evaluation data)
│   ├── phase-2/         ~0.5 MB  (evaluation data)
│   └── scripts/         KEEP     (generation/download scripts)
│
├── logs/                12 MB    ARCHIVE (old >30d) ✓
│   ├── sessions/        (session logs)
│   ├── db-snapshots/    (N8N execution snapshots)
│   ├── errors/          (error traces)
│   ├── executions/      (execution logs)
│   ├── pipeline-results/(pipeline outputs)
│   ├── diagnostics/     KEEP (recent)
│   ├── tests/           (test logs)
│   └── iterative-eval/  KEEP (recent)
│
├── snapshot/            14 MB    MIXED
│   ├── good/            1-2 MB   KEEP (reference)
│   └── db/              12-13 MB ARCHIVE ✓
│
├── outputs/             168 KB   ARCHIVE ✓
│   ├── session-*.md
│   ├── *-analysis.md
│   └── *-workflow.json
│
├── directives/          ~1 MB    KEEP (active)
├── technicals/          ~2 MB    KEEP (active)
├── eval/                ~0.5 MB  KEEP (active)
├── scripts/             ~0.5 MB  KEEP (active)
├── n8n/                 ~0.5 MB  KEEP (active)
└── docs/                ~1 MB    KEEP (active)

ARCHIVABLE TOTAL: 131 MB (datasets 105 + logs 12 + snapshot/db 13 + outputs 0.2)
KEEP TOTAL:       ~5 MB (code, directives, active tools)
```

## SATELLITE REPOS

```
rag-tests          40 MB    [ ] Audit needed → est. 5-15 MB archivable
rag-website        38 MB    [ ] Check for node_modules → est. 0-2 MB
rag-data-ingestion 37 MB    [ ] Audit for logs/data → est. 5-15 MB
rag-pme-connectors 39 MB    [ ] Check for node_modules → est. 0-1 MB
rag-pme-usecases   43 KB    ✓ Already minimal
rag-dashboard      ?  MB    [ ] Check for logs → est. minimal
```

## MIGRATION TARGETS

```
rag-storage/
└── repos/
    ├── mon-ipad/
    │   ├── datasets/           (105 MB)
    │   ├── logs/archive/       (8+ MB old logs)
    │   ├── outputs/            (168 KB)
    │   └── snapshot/db/        (12-13 MB)
    ├── rag-tests/
    │   ├── outputs/
    │   └── logs/
    ├── rag-data-ingestion/
    │   └── logs/
    └── [other repos as needed]
```

## BEFORE & AFTER

| Repo | Before | After | Reduction |
|------|--------|-------|-----------|
| mon-ipad | 24 MB | 2-5 MB | **79-92%** ↓ |
| rag-tests | 40 MB | 35-38 MB | 5-12% ↓ |
| rag-storage | 25 MB | 160 MB | **540%** ↑ |
| **TOTAL** | **203 MB** | **~300 MB** | Organized |

## ARCHIVE CATEGORIES

### Category 1: Regenerable (Low Risk)
- Datasets: HF benchmarks can be re-downloaded
- Snapshot DB: Can be regenerated from execution logs
- **SAFE TO MOVE**

### Category 2: Historical (Reference Value)
- Session logs: Useful for debugging, auditing
- Analysis reports: Document project evolution
- **SAFE TO MOVE** to rag-storage

### Category 3: Active (Must Keep)
- Code: evaluation scripts, workflow definitions
- Directives: CLAUDE.md, session-state.md, status.md
- Current logs: Last 30 days for debugging
- Good snapshots: Reference for validation
- **MUST KEEP** in mon-ipad

## RISK ASSESSMENT

| Item | Size | Risk | Impact |
|------|------|------|--------|
| datasets/ | 105 MB | LOW | Regenerable via scripts |
| logs (old) | 8+ MB | LOW | Archived copy in rag-storage |
| snapshot/db | 12 MB | LOW | Regenerable from logs |
| outputs/ | 168 KB | NONE | Pure reference |
| snapshot/good | - | NONE | Staying in mon-ipad |
| Recent logs | - | NONE | Staying in mon-ipad |

**Overall Risk**: **VERY LOW** — all archived content is either regenerable or safely referenced in rag-storage

## TIMELINE

- **Week 1**: Move 131 MB from mon-ipad → rag-storage
- **Week 1**: Audit satellite repos
- **Week 2**: Implement automation (daily log archival)
- **Week 3**: Verify all systems working, update documentation

## Success Criteria

- [ ] mon-ipad reduced to <10 MB
- [ ] All 131 MB successfully in rag-storage
- [ ] No loss of functionality or data
- [ ] Git operations 5x faster
- [ ] rag-storage becomes single source of truth for historical data
- [ ] Automation working (daily log push)

