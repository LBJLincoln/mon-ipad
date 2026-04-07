---
name: Polyrepo Tooling Scan (April 2026)
description: Evaluation of monorepo/polyrepo coordination tools for 5-repo Python+TS+Shell Nomos42 stack. Winner: moon v2.
type: project
---

Winner: moon v2 (moonrepo/moon). VERDICT: HIGH.

**Why:** Only tool that (a) works as polyrepo coordinator without repo migration, (b) natively handles Python+TS+Shell tasks in one dependency graph, (c) shipped stable Feb 2 2026 with v2.1.3 Mar 26 2026, (d) single Rust binary ~15 MB / <50 MB RAM (fits VM), (e) WASM plugin toolchains — community can extend.

**Rejected:**
- Nx Synthetic Monorepos: roadmap-only (Polygraph not shipped), requires Nx Cloud subscription.
- Turborepo: JS-only in practice, no native Python.
- meta (mateodelnorte): abandoned, no dep graph, no caching.
- mise: good toolchain pinning but no cross-repo dep graph (experimental only).

**Type sharing:** JSON Schema (mon-ipad/schemas/) → datamodel-code-generator → Pydantic v2 (Python repos) + json-schema-to-typescript → src/types/generated.ts (nomos-dashboard). This is the type-sharing answer.

**How to apply:** When user asks about cross-repo sync, schema drift, or replacing sync-to-sister-repos.sh — recommend moon v2 + JSON Schema source-of-truth pattern. Full JSON at /home/termius/nomos-nba-agent/data/results/repo-scout-polyrepo.json.

**Why:** bespoke sync-to-sister-repos.sh copies files by hardcoded path with no dep graph, no caching, no type safety. Moon solves all three.

**How to apply:** Effort is 6h total: 3h schema writing + 1h moon install/workspace.yml + 2h task wiring in each repo's moon.yml. Not urgent for Brier improvement but eliminates ongoing schema drift bugs.
