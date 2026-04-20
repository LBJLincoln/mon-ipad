---
name: Cat66 pace-normalized per-100 implemented 2026-04-19
description: Cat66 pace-normalized per-100 box-score differentials added to engine v3.1-66cat at 12:00 UTC 2026-04-19
type: project
---

Cat66 (12 features: p100_66_h/a/diff for pts/ast/tov/reb) added to NBA engine.

**Why:** MDPI Jan 2026 paper (doi:10.3390/info17010056) normalizes all stats per 100 possessions to remove pace confounding. Source proposal: data/research-proposals/2026-04-13-cycle99-pace-norm-ev-filter.md Key Finding #1.

**How to apply:** Engine is now v3.1-66cat, 6446 features. sha256 25d59790... on both engine.py + hf-space/engine.py. Commits: nomos-nba-agent 52af300, mon-ipad 63516124e. Ledger entry appended with verdict=pending. Brier delta expected within 2 island cycles.
