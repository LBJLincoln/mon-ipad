# Cross-repo cleanup audit — 2026-04-17

**Scope**: 7 Nomos42 repos on VM. Flag-only — nothing deleted without approval.

**Totals**: 6,910 files / 401,763 LOC / 510 MB

## Per-repo summary

| Repo | Files | LOC | Size | Top bloat |
|------|-------|-----|------|-----------|
| mon-ipad | 2,888 | 282k | 262 MB | 857 json, 742 md, 216 log |
| nomos-political-alpha | 2,664 | 22k | **194 MB** | **2,479 json**, 113 log |
| nomos-nba-agent | 1,052 | 62k | 41 MB | 880 json |
| nomos-dashboard | 168 | 30k | 5 MB | (clean) |
| nomos-picks | 63 | 2k | 0.3 MB | (clean) |
| rgwa | 53 | 3k | 7 MB | (clean) |
| nomos-pierre | 22 | 111 | 0 MB | **stub repo** |

## Cleanup candidates (ranked by payoff)

### 1. nomos-political-alpha — 194 MB → target ~20 MB
- 2,479 committed `.json` files (events/history data). Should move to HF Dataset or `.gitignore` runtime outputs.
- 113 `.log` files committed. Should be ignored.

### 2. mon-ipad — 262 MB → target ~150 MB
- 216 `.log` files: likely runtime logs committed (should be gitignored).
- 742 `.md` files: many likely old memory snapshots / plan dumps. Need audit pass.
- 857 `.json`: a chunk is legit data (full-odds, model-predictions), but plenty is runtime.

### 3. nomos-nba-agent — 41 MB
- 880 `.json` likely daily odds/predictions snapshots. Should rotate or move to Dataset.

### 4. nomos-pierre — 22 files / 111 LOC
- Looks like an abandoned stub. Decide: keep as-placeholder, archive, or delete.

## Suggested next step
Per-repo `.gitignore` + `git rm --cached` pass to stop tracking runtime artifacts, then `git gc --aggressive` to reclaim. Needs explicit user approval per repo.

Source: `data/repo-inventory.json` (regenerates daily via `.github/workflows/repo-inventory.yml`).
