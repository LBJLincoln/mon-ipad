# Workflow Diff Engine

Compare live HF Space workflows against golden reference (22 Feb baselines that scored 55-64% on Phase 2).

## Features

- Connects to all 10 HF Spaces via n8n REST API
- Downloads current workflow state for 4 core pipelines (Standard, Graph, Quantitative, Orchestrator)
- Compares structurally against golden reference in `/home/termius/mon-ipad/hf-space/n8n-workflows/`
- Diagnoses differences with detailed categorization
- Can auto-revert workflows to golden state
- Color-coded terminal output + detailed JSON reports

## Difference Types

- **CREDENTIAL_MISSING** (Critical): Node references credential ID that doesn't exist
- **NODE_TYPE_CHANGED** (High): Node type changed (e.g., Code → Postgres)
- **NODE_REMOVED** (High): Node exists in golden but not in current
- **NODE_ADDED** (Medium): Node exists in current but not in golden
- **NODE_MODIFIED** (Medium): Node parameters changed
- **CONNECTION_CHANGED** (Medium): Node connections modified
- **WORKFLOW_INACTIVE** (High): Workflow imported but not activated

## Usage

### Compare all spaces against golden reference
```bash
python3 scripts/workflow-diff-engine.py
```

### Compare single space
```bash
python3 scripts/workflow-diff-engine.py --space https://lbjlincoln-nomos-rag-engine.hf.space
```

### Compare single pipeline
```bash
python3 scripts/workflow-diff-engine.py --pipeline standard
```

### Verbose mode (for debugging)
```bash
python3 scripts/workflow-diff-engine.py --space https://lbjlincoln-nomos-rag-engine.hf.space --verbose
```

### Dry-run (show what would be reverted)
```bash
python3 scripts/workflow-diff-engine.py --pipeline quantitative --dry-run
```

### Revert workflows to golden state
```bash
# Revert all workflows with differences
python3 scripts/workflow-diff-engine.py --revert

# Revert only quantitative pipeline
python3 scripts/workflow-diff-engine.py --pipeline quantitative --revert

# Revert on specific space
python3 scripts/workflow-diff-engine.py --space https://lbjlincoln-nomos-rag-engine.hf.space --pipeline orchestrator --revert
```

## Output

### Terminal (color-coded)
- Green ✓: No differences (100% match)
- Cyan ⚠: Low/medium severity differences
- Yellow ⚠: High severity differences
- Red ✗: Critical differences or errors

### JSON Report
Saved to `/home/termius/mon-ipad/logs/workflow-diff-TIMESTAMP.json`

Contains:
- Full difference details
- Severity counts
- Parameter changes (with before/after values)
- Node modifications
- Connection changes

## Ignored Fields

The comparison ignores volatile fields that change on every deploy:
- `id` (Node IDs)
- `versionId`
- `updatedAt` / `createdAt`
- `webhookId`
- `position` (UI coordinates)

Credential IDs are normalized by type:name signature.

## Golden Reference

Located in `/home/termius/mon-ipad/hf-space/n8n-workflows/`:
- `standard.json` - Standard RAG V3.4
- `graph.json` - Graph RAG V3.3
- `quantitative.json` - Quantitative V2.0
- `orchestrator-v10.json` - Orchestrator V10.1

These are the 22 Feb 2026 baselines that achieved 55-64% accuracy on Phase 2 eval.

## Safety

- `--dry-run` shows what would be reverted without making changes
- Revert preserves workflow IDs and regenerates credential references
- Workflows are backed up in JSON report before revert
- Only reverts workflows that have differences detected

## Integration with Session Workflow

Add to session startup checklist:

```bash
# After session intelligence
python3 scripts/workflow-diff-engine.py --pipeline standard

# If differences detected, investigate with verbose
python3 scripts/workflow-diff-engine.py --space <SPACE_URL> --pipeline <PIPELINE> --verbose

# Revert if needed
python3 scripts/workflow-diff-engine.py --pipeline <PIPELINE> --revert
```
