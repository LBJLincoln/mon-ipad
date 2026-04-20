# Cross-Repo Improvement Sweep — 2026-04-20 (LAUNCHPAD)

Deep audit across 6 repos (`mon-ipad`, `nomos-dashboard`, `nomos-political-alpha`,
`nomos-nba-agent`, `rgwa`, `rag-website`). Summary table + proposals for items that
were too risky to ship without human review.

## Summary table

| Category | mon-ipad | nomos-dashboard | nomos-political-alpha | nomos-nba-agent | rgwa | rag-website |
|----------|----------|-----------------|-----------------------|-----------------|------|-------------|
| CI/CD parity | 22 workflows (rich) | 2 workflows | **SHIPPED** `check.yml` (was 1 restore-only) | 1 workflow (engine parity) | **SHIPPED** `check.yml` (was 0) | REPO MISSING (skip) |
| Feature engine parity | v3.1-65cat | n/a | n/a | v3.1-66cat (ahead by Cat66 MDPI) | n/a | n/a |
| Stale docs purge | ok | ok | **SHIPPED** (fixed S10-S15 island table) | **SHIPPED** (v14→v15, ENGINE 54cat→66cat, S10/S11/S12 removed) | ok (no README, minimal repo) | n/a |
| Dep hygiene | — | Next 15.1 / React 19 / Pixi 8 | numpy≥2 xgboost≥3 | — (no requirements.txt) | — | n/a |
| Secrets parity | 31 secrets, 31 referenced | 1 referenced (BROWSER_QA_URL has default — no gap) | GITHUB_TOKEN only — ok | 0 secrets referenced | 0 | n/a |
| Dead code purge | 2 stale `.pyc` in `scripts/arena/__pycache__/` (gitignored, not tracked — harmless) | ok | ok | ok | ok | n/a |
| Commit cadence (7d) | 694 | 67 | 44 | 15 | 7 | n/a |

Legend: **SHIPPED** = committed this sweep. Items without SHIPPED were already healthy
or are PROPOSAL-ONLY (see below).

## SHIPPED changes (this sweep)

1. **`rgwa/.github/workflows/check.yml`** — minimal Python syntax lint + secret scan
   on push/PR. Closes CI gap flagged by LAUNCHPAD audit (rgwa had 0 workflows).
2. **`nomos-political-alpha/.github/workflows/check.yml`** — minimal lint +
   political_engine.py size guard + secret scan. Complements existing
   `restore-political-engine.yml` (disaster-recovery only, no CI gate).
3. **`nomos-political-alpha/CLAUDE.md`** — HF Spaces table rewritten: removed
   eliminated islands S10/S11/S12/S16/S19/S20/S21 + P3/P6/P8, added surviving
   S13-S22 + P1/P2/P4/P5/P7 with their current Brier scores. Added explicit
   "do NOT restart" banner per the 2026-04-17 cull doctrine.
4. **`nomos-nba-agent/CLAUDE.md`** — v14→v15, updated island roster to 6 NBA
   survivors with current Brier scores, bumped `ENGINE_VERSION` from `v3.1-54cat`
   to `v3.1-66cat` (matches actual engine header), renamed "S10 Public API"
   to "Fleet Public API" (S10 is dead).

## PROPOSAL-ONLY (risky — human review needed)

### P1. Feature engine drift: `mon-ipad/features/engine.py` is BEHIND `nomos-nba-agent/features/engine.py`

- `mon-ipad/features/engine.py`: `ENGINE_VERSION = "v3.1-65cat"`, 8017 lines,
  sha256 `fe85d15e…`. Also mirrored identically to
  `mon-ipad/hf-space/features/engine.py` and `mon-ipad/nba-quant-space/features/engine.py`.
- `nomos-nba-agent/features/engine.py`: `ENGINE_VERSION = "v3.1-66cat"`, 8084 lines,
  sha256 `25d59790…`. Has an extra category **Cat 66: Pace-Normalized Per-100
  Box-Score Differentials** (12 features) citing MDPI Information 17(1):56 Jan 2026.
- Rule #2 violation: `features/engine.py` across repos must match.

**Why risky**: mon-ipad is the upstream for all 6 NBA HF islands. A diff that adds
12 features changes the feature count exposed to every island's GA. CPU islands
are tree-only with MAX_FEATURES=200 cap; adding 12 candidates is safe on that front,
but (a) it must be ingested through a GA round to be selected, (b) any in-flight
checkpoints reference the current 65-cat schema and will need a shim or re-train.

**Proposed path**:
1. DR FRANKENSTEIN reviews `nomos-nba-agent` Cat 66 diff for paper correctness.
2. Port to `mon-ipad/features/engine.py` + `hf-space/features/engine.py` in a single commit.
3. Bump Supabase `feature_engine_version` tag globally before redeploy.
4. SWISH restarts one NBA island (S22, fleet best) first; observe 1 day for
   breakage before broadcasting to the other 5.

Do NOT ship without DR FRANKENSTEIN + SWISH sign-off.

### P2. `nomos-nba-agent` CI check references `hf-space/features/engine.py` parity

The workflow in `nomos-nba-agent/.github/workflows/check.yml` asserts sha256 equality
between `features/engine.py` and `hf-space/features/engine.py`. That guard is correct
but currently only enforces parity WITHIN `nomos-nba-agent`, not across
`nomos-nba-agent` ↔ `mon-ipad`. Proposal: add a nightly cron workflow in mon-ipad
that curls raw file from nomos-nba-agent and asserts sha256 match, failing the
job if drift exceeds a single commit lag.

### P3. `nomos-dashboard` lacks a lockfile check in CI

`package.json` pins Next 15.1 / React 19 / Pixi 8. Build runs `npm ci` which needs
`package-lock.json`. No CI step asserts lockfile is in sync with `package.json`
(`npm ci --dry-run` would catch drift). Low-risk to add but user may prefer to
handle on next dashboard touch.

### P4. `rag-website` repo is missing entirely from `/home/termius/`

CLAUDE.md says "SHELVED", and the repo isn't checked out. Nothing actionable
unless user wants it revived. Flag for de-reference in CLAUDE.md if it's formally dead.

## Remaining gaps (escalate to user)

- **Engine parity** (P1 above) — needs DR FRANKENSTEIN + SWISH to unlock.
- **mon-ipad ↔ nomos-nba-agent cross-repo sha check workflow** (P2) — add when
  engine is re-synced.
- **rag-website** (P4) — confirm officially dead or needs clone.
