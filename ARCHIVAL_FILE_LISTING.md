# Archival File Listing - Detailed Breakdown

Generated: 2026-02-23

## DATASETS/ - 105 MB (44 files total)

### HuggingFace Benchmarks (~100 MB)
```
datasets/hf/
├── asqa.jsonl              (Large benchmark)
├── convfinqa.jsonl
├── finqa.jsonl
├── frames.jsonl
├── hotpotqa.jsonl
├── 2wikimultihopqa.jsonl
├── msmarco.jsonl
├── musique.jsonl
├── popqa.jsonl
├── pubmedqa.jsonl
├── squad_v2.jsonl
├── tatqa.jsonl
├── wikitablequestions.jsonl
└── .gitkeep

TOTAL: 13 datasets
SOURCE: HuggingFace Hub
STATUS: Regenerable via scripts/download-*.py
```

### Sector Data (~5 MB)
```
datasets/sectors/
├── btp/                    (Construction industry docs)
├── finance/                (Financial sector docs)
├── industrie/              (Industrial sector docs)
└── juridique/              (Legal sector docs)

TOTAL: ~5 MB across 4 sectors
STATUS: Downloaded from various sources, documents regenerable
```

### Phase Data (~1 MB)
```
datasets/phase-1/           Phase 1 evaluation set
├── standard-orch-50x2.json
└── graph-quant-50x2.json

datasets/phase-2/           Phase 2 evaluation set
├── hf-1000.json
├── standard-orch-1000x2.json
└── phase-4-questions.json

TOTAL: ~1 MB
STATUS: Generated via scripts
```

### Scripts (KEEP)
```
datasets/scripts/
├── download-benchmarks.py
├── generate-phase-datasets.py
├── download-sectors.py
├── check-ingestion-status.py
└── manifest.json

TOTAL: Essential for regeneration
ACTION: KEEP in mon-ipad
```

---

## LOGS/ - 12 MB (636 files total)

### Subdirectories
```
logs/
├── sessions/               (Session logs from each Claude Code session)
├── db-snapshots/           (Database snapshots from n8n)
├── errors/                 (Error traces and debug logs)
├── executions/             (n8n execution traces)
├── pipeline-results/       (Pipeline output results)
├── diagnostics/            (Diagnostic analysis)
├── tests/                  (Test execution logs)
└── iterative-eval/         (Evaluation iteration logs)

TOTAL: 636 files across 8 subdirectories
DATE RANGE: 2026-02-10 to 2026-02-22
ARCHIVABLE: All files dated before 2026-02-16 (8+ MB)
KEEP: Recent logs (last 30 days) for debugging
```

### Recommended Keep vs Archive
```
KEEP (Recent, active):
  logs/diagnostics/*        (Active iteration logs)
  logs/pipeline-results/*   (Current pipeline outputs)
  logs/iterative-eval/*     (Current evaluation logs)
  logs/**/*2026-02-2[0-3]*  (Last 3-4 days)

ARCHIVE (Historical):
  logs/sessions/*           (All — useful for audits)
  logs/db-snapshots/*       (All — regenerable)
  logs/errors/*             (All — useful for debugging)
  logs/executions/*         (All — useful for tracing)
  logs/**/*2026-02-1[0-9]*  (Before Feb 20)
```

---

## SNAPSHOT/ - 14 MB (56 files total)

### Good Snapshots (KEEP - 1-2 MB)
```
snapshot/good/
├── standard-final.json     (Reference: Standard RAG final state)
├── quantitative-final.json (Reference: Quantitative RAG final state)
├── execution_19326.json    (Good execution #1)
├── execution_19323.json    (Good execution #2)
├── execution_19404.json    (Good execution #3)
[... 42 more good executions ...]

TOTAL: ~45 validated execution snapshots
ACTION: KEEP in mon-ipad (reference for validation)
```

### Database Snapshots (ARCHIVE - 12-13 MB)
```
snapshot/db/
├── snap-2026-02-10T00-07-21.json
├── snap-2026-02-12T02-32-22.json
├── snap-2026-02-12T02-33-50.json
[... 29 more snapshots ...]

TOTAL: 32 database snapshots
ACTION: ARCHIVE to rag-storage
REASONING: Regenerable from execution logs
```

---

## OUTPUTS/ - 168 KB (10 files total)

### Session Analysis Reports
```
outputs/
├── session-analyzer-report-40.md           (16 KB)
├── 13-fev-final-execution-analysis.md      (16 KB)
├── 13-fev-next-session-prep.md             (8 KB)
├── 13-fev-website-session.md               (4 KB)
├── session-37-log.md                       (4 KB)
└── session-33-log.md                       (4 KB)

### Workflow & Data Files
├── 13-fev-standard-rag-workflow.json       (92 KB)
├── 13-fev-commands.md                      (8 KB)
├── 13-fev-tested-ids.json                  (4 KB)
└── kimi-video-scripts-2026-02-17.md        (8 KB)

TOTAL: 10 files, 168 KB
ACTION: ARCHIVE entire directory to rag-storage
REASONING: Historical analysis, safe to move
```

---

## DIRECTORIES TO KEEP (Code & Active)

```
KEEP IN MON-IPAD:
├── .github/               (CI/CD workflows)
├── directives/            (Mission control)
├── technicals/            (Technical docs)
├── eval/                  (Evaluation scripts)
├── scripts/               (Utility scripts)
├── n8n/                   (Workflow definitions)
├── mcp/                   (MCP server configs)
├── website/               (Next.js code)
├── website-pme-*/         (PME site code)
├── snapshot/good/         (Reference snapshots)
├── docs/                  (Documentation)
├── logs/                  (Recent only - last 30d)
└── [all code files]
```

---

## MIGRATION COMMANDS

### Copy to rag-storage (assuming it's cloned at same level)

```bash
# Archive datasets
cp -r datasets/ ../rag-storage/repos/mon-ipad/
rm -rf datasets/

# Archive snapshot DB
cp -r snapshot/db/ ../rag-storage/repos/mon-ipad/snapshot/
rm -rf snapshot/db/

# Archive outputs
cp -r outputs/ ../rag-storage/repos/mon-ipad/
rm -rf outputs/

# Archive old logs (before Feb 16)
find logs -type f -not -newermt "2026-02-16" -exec cp --parents {} ../rag-storage/repos/mon-ipad/logs/archive/ \;
find logs -type f -not -newermt "2026-02-16" -delete
```

---

## VERIFICATION CHECKLIST

After archival:

```
[ ] All datasets/* moved to rag-storage
[ ] All snapshot/db/* moved to rag-storage
[ ] All outputs/* moved to rag-storage
[ ] Old logs (>30 days) moved to rag-storage
[ ] Recent logs retained in mon-ipad
[ ] snapshot/good/ still in mon-ipad
[ ] All scripts retained
[ ] .gitignore updated
[ ] mon-ipad disk < 10 MB
[ ] rag-storage disk ~160 MB
[ ] All commits pushed
[ ] Verify no data loss
```

---

## FILE COUNT SUMMARY

| Directory | Files | Size | Action |
|-----------|-------|------|--------|
| datasets/ | 44 | 105 MB | Archive |
| logs/ | 636 | 12 MB | Archive (old) |
| snapshot/db/ | 32 | 12-13 MB | Archive |
| outputs/ | 10 | 168 KB | Archive |
| snapshot/good/ | 47 | 1-2 MB | Keep |
| [Code + directives] | ~500 | ~5 MB | Keep |
| **TOTAL** | ~1,300 | **24 MB** | - |

**ARCHIVE TOTAL**: 131 MB  
**KEEP TOTAL**: 5 MB  
**REDUCTION**: ~82%

