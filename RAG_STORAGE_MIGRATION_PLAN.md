# RAG Storage Migration Plan

**Date**: 2026-02-23  
**Status**: Analysis Complete, Ready for Implementation  
**Scope**: Archive ~131 MB from mon-ipad control tower to rag-storage

## Quick Summary

| Metric | Value |
|--------|-------|
| **Archivable from mon-ipad** | ~131 MB |
| **Target reduction** | mon-ipad: 24 MB → 2-5 MB (code-only) |
| **Primary datasets** | HuggingFace benchmarks (11 datasets, 105 MB total) |
| **Largest single item** | datasets/hf/ (105 MB) |
| **Safe to remove** | Yes - all scripts retained, data regenerable |

## Files to Archive

### High Priority (>5 MB each)

1. **datasets/** (105 MB) ✓
   - HuggingFace: asqa, tatqa, pubmedqa, squad_v2, finqa, msmarco, 2wikimultihopqa, convfinqa, frames, wikitablequestions, musique, popqa, hotpotqa
   - Sector data: BTP, Finance, Industrie, Juridique
   - **Destination**: `rag-storage/repos/mon-ipad/datasets/`
   - **Action**: Move entire directory

2. **snapshot/db/** (12-13 MB) ✓
   - Database snapshots (32 files)
   - **Destination**: `rag-storage/repos/mon-ipad/snapshot/db/`
   - **Action**: Move directory, keep `snapshot/good/` for reference

3. **logs/** - Older than 2026-02-16 (8+ MB) ✓
   - Sessions, errors, executions, db-snapshots, etc.
   - **Destination**: `rag-storage/repos/mon-ipad/logs/archive/`
   - **Action**: Archive old files, keep recent for debugging

### Lower Priority (<1 MB each)

4. **outputs/** (168 KB) ✓
   - Session reports and analysis
   - **Destination**: `rag-storage/repos/mon-ipad/outputs/`
   - **Action**: Move entire directory

## Impact

### Before Migration
```
mon-ipad:      24 MB  (bloated with data)
rag-storage:   25 MB  (minimal)
Total:         203 MB (scattered)
```

### After Migration
```
mon-ipad:      2-5 MB  (code-only, lean)
rag-storage:   160 MB  (centralized data lake)
Total:         ~300 MB (organized, discoverable)
```

## Why This Matters

1. **Lean Control Tower**: mon-ipad stays fast and responsive (2-5 MB vs 24 MB)
2. **Single Source of Truth**: All historical data in rag-storage
3. **Better Organization**: Clear separation of code (active repos) vs data (rag-storage)
4. **Faster Operations**: Git clone/pull/push 5-10x faster with smaller repos
5. **Audit Trail**: Complete history preserved in rag-storage

## Implementation Steps

### Step 1: Prepare rag-storage Structure
```bash
mkdir -p rag-storage/repos/mon-ipad/{datasets,outputs,logs/archive,snapshot/db}
```

### Step 2: Move Data
```bash
# Datasets
mv mon-ipad/datasets/* rag-storage/repos/mon-ipad/datasets/

# Snapshot DB files
mv mon-ipad/snapshot/db/* rag-storage/repos/mon-ipad/snapshot/db/

# Old logs (before 2026-02-16)
find mon-ipad/logs -type f -newermt "2026-02-16" ! -newer ... \
  | xargs mv -t rag-storage/repos/mon-ipad/logs/archive/

# Outputs
mv mon-ipad/outputs/* rag-storage/repos/mon-ipad/outputs/
```

### Step 3: Update .gitignore (mon-ipad)
```
# Archived directories
datasets/
snapshot/db/
outputs/

# Old logs (keep recent)
logs/*
!logs/sessions
!logs/diagnostics
!logs/pipeline-results
!logs/iterative-eval
```

### Step 4: Commit & Push
```bash
# In mon-ipad
git add .gitignore ARCHIVAL_ANALYSIS_2026-02-23.txt
git commit -m "archive: move large datasets to rag-storage (105 MB reduction)"
git push origin main

# In rag-storage
git add repos/mon-ipad/
git commit -m "archive: ingest mon-ipad datasets, snapshots, outputs"
git push origin main
```

## Satellite Repos (TBD)

Additional archival candidates in other repos:
- **rag-tests**: 5-15 MB (outputs, logs)
- **rag-data-ingestion**: 5-15 MB (logs, processed data)
- **rag-website**: 0-2 MB (cleanup if node_modules committed)
- **rag-pme-connectors**: 0-1 MB (cleanup if node_modules committed)

## Automation (Future)

Add GitHub Action to auto-archive:
1. Every 24h: Push logs older than 30 days to rag-storage
2. After session: Auto-commit outputs/ to rag-storage
3. Quarterly: Archive snapshot/db/ to rag-storage

## Verification Checklist

- [ ] rag-storage/repos/mon-ipad/ structure created
- [ ] All datasets moved (105 MB)
- [ ] snapshot/db/ archived (12-13 MB)
- [ ] outputs/ archived (168 KB)
- [ ] Old logs archived (8+ MB)
- [ ] .gitignore updated in mon-ipad
- [ ] snapshot/good/ retained in mon-ipad
- [ ] Recent logs (last 30 days) retained in mon-ipad
- [ ] All commits pushed
- [ ] Verify mon-ipad is now <10 MB

## References

- Full analysis: `/home/termius/mon-ipad/ARCHIVAL_ANALYSIS_2026-02-23.txt`
- rag-storage repo: https://github.com/LBJLincoln/rag-storage
