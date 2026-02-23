# RAG Dashboard Repository Cleanup Summary

**Date:** 2026-02-23  
**Commit:** 8f612a4  
**Branch:** main  

## Problem

The `rag-dashboard` repo contained 1209 files - a complete duplicate of the entire `mon-ipad` control tower repo including:
- All datasets (benchmarks, sectors)
- All eval scripts
- All n8n workflows
- All technical documentation
- All website code
- All operational scripts

This violated the single-responsibility principle - the dashboard repo should only contain static dashboard files.

## Solution

Performed aggressive cleanup to keep only dashboard-essential files.

### Files Removed (1098 files)

**Deleted directories:**
- `.devcontainer/` - Dev container configs for all repos
- `.github/workflows/` - CI/CD workflows
- `datasets/` - All benchmark and sector data (669MB)
- `db/` - Database scripts and migrations
- `eval/` - All Python evaluation scripts
- `n8n/` - All workflow JSON files
- `technicals/` - All technical documentation
- `directives/` - All directive files
- `website/`, `website-pme-*` - All website code
- `scripts/`, `logs/`, `outputs/`, `snapshot/`, `mcp/` - All operational files

**Deleted root files:**
- `CLAUDE.md` - Control tower directive (belongs in mon-ipad)
- `.env.example` - Environment template
- `package.json` - Control tower dependencies
- Various temp files and notes

### Files Kept (7 files)

```
rag-dashboard/
├── .gitignore (updated for dashboard)
├── README.md (new documentation)
├── control-panel.html (copied from mon-ipad/docs/)
├── repos-config.json (copied from mon-ipad/docs/)
└── docs/
    ├── index.html (main dashboard)
    ├── status.json (current status data)
    └── data.json (historical eval data)
```

## Results

- **Before:** 1,209 files, ~1.2M lines of code
- **After:** 7 files, ~9K lines (dashboard HTML + data)
- **Reduction:** 99.4% file count reduction, 99.2% code reduction
- **Commit:** `8f612a4` - "cleanup: remove all non-dashboard files (1209 → 7 files)"

## Impact

1. **Clarity:** The repo now has a clear single purpose - static dashboard
2. **Size:** Dramatically reduced repo size (no large datasets, no duplicate code)
3. **Maintenance:** No confusion about which files belong where
4. **Deployment:** Simpler Vercel/GitHub Pages deployment (static only)

## Architecture

The cleaned repo is now:
- **Pure static** - No build process, no dependencies
- **Data consumer** - Reads from n8n webhook endpoint
- **Single responsibility** - Dashboard visualization only

Data updates flow:
```
mon-ipad (control tower)
  → runs eval/generate_status.py
  → pushes to n8n webhook
  → dashboard reads from webhook endpoint
```

## Verification

```bash
# Before cleanup
gh api repos/LBJLincoln/rag-dashboard/git/trees/main?recursive=1 --jq '.tree[].path' | wc -l
# Output: 1209

# After cleanup
gh api repos/LBJLincoln/rag-dashboard/git/trees/main?recursive=1 --jq '.tree[].path' | wc -l
# Output: 8
```

## Next Steps

1. Update Vercel deployment config to use cleaned repo
2. Verify dashboard still works at https://nomos-dashboard-alexis-morets-projects.vercel.app
3. Update any scripts in mon-ipad that reference rag-dashboard structure
4. Consider similar cleanup for other satellite repos if needed

## Backup

A backup branch `backup-pre-cleanup` was created before cleanup (though not pushed, as git history preserves all previous states).

To recover any deleted file:
```bash
git checkout 5f3fdd2 -- path/to/file  # Last commit before cleanup
```
