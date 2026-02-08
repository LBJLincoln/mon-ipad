# Dashboard Spec Analysis — `docs/index.html`

> Generated: 2026-02-08
> Source: `docs/index.html` (1,449 lines, single-file SPA)
> Data source: `docs/data.json` (v2.0, auto-refresh every 15s)

---

## Architecture Overview

The dashboard is a **single-file HTML/CSS/JS application** with no build step.
It loads `data.json` via fetch, renders all tabs client-side, and uses Chart.js
(CDN v4.4.1) for visualizations. No framework — pure vanilla JS with template
literals for HTML generation.

| Aspect | Detail |
|--------|--------|
| **Rendering** | Client-side JS, template literals, DOM innerHTML |
| **Charts** | Chart.js 4.4.1 (CDN) — line, bar charts |
| **Fonts** | Inter (UI) + JetBrains Mono (code/data) via Google Fonts |
| **Theme** | Dark theme only, CSS custom properties (`--bg`, `--ac`, etc.) |
| **Responsive** | Basic — media queries at 1200px and 768px (grid collapse) |
| **Refresh** | Auto-refresh every 15s via `setInterval(loadData, 15000)` |
| **State** | Global `DATA` object, `selectedQuestion`, `charts{}` |
| **Max width** | 1600px container |

---

## Tab Inventory: Spec vs Implementation

### CLAUDE.md specifies 10 tabs:

| # | Spec Tab | Implemented? | Implementation Tab | Status |
|---|----------|-------------|-------------------|--------|
| 1 | **Command Center** | **NO** | — | MISSING |
| 2 | **Test Matrix** | YES | Test Matrix (tab 1) | Complete |
| 3 | **Iterations** | YES | Iterations (tab 3) | Partial |
| 4 | **Pipelines** | YES | Pipelines (tab 5) | Partial |
| 5 | **Error Analysis** | **NO** | — | MISSING |
| 6 | **Phase Tracker** | **NO** | — | MISSING |
| 7 | **Questions Explorer** | YES | Questions (tab 4) | Complete |
| 8 | **Smoke Tests** | YES | Smoke Tests (tab 2) | Complete |
| 9 | **Workflows & Changes** | YES | Workflows + Changes Log (tabs 6-7) | Split into 2 tabs |
| 10 | **AI Insights** | Partial | Agentic API (tab 8) | Downgraded |

### Summary
- **3 tabs entirely missing**: Command Center, Error Analysis, Phase Tracker
- **1 tab downgraded**: AI Insights → static Agentic API docs (no live analysis)
- **1 tab split**: Workflows & Changes → 2 separate tabs (acceptable)
- **5 tabs implemented well**: Test Matrix, Questions, Smoke Tests, Workflows, Changes

---

## Missing Tab #1: Command Center

**Spec description**: Phase progress, pipeline gauges vs targets, blockers, AI recommendations.

**What's missing**:
- Phase progress bar with completion percentage
- Pipeline gauge charts showing current accuracy vs target (radial/gauge style)
- Blockers section (critical issues preventing phase gate passage)
- AI-generated recommendations based on latest data
- Quick-action links (run eval, sync workflows, etc.)

**Impact**: HIGH — This is supposed to be the landing page. Currently, Test Matrix is
the default tab, which is a detailed data view rather than an executive summary.

**Data available in `data.json`**: `meta.phase`, `pipelines.*.target_accuracy`,
`evaluation_phases`, `current_phase` — sufficient to build this tab.

---

## Missing Tab #2: Error Analysis

**Spec description**: Error classification breakdown, timeline, patterns, most-erroring questions.

**What's missing**:
- Error type distribution chart (TIMEOUT, NETWORK, EMPTY_RESPONSE, ENTITY_MISS, SQL_ERROR, etc.)
- Error timeline showing when errors cluster
- Pattern detection (which questions consistently error, which pipelines error most)
- "Most erroring questions" ranked table
- Error correlation matrix (error type vs pipeline)

**Impact**: HIGH — With 102 error trace files and a 38% error rate on Orchestrator,
error analysis is the most critical operational need. Currently there is NO dedicated
view for understanding errors.

**Data available**: Each question result has `error` and `error_type` fields.
The `question_registry` tracks `current_status === 'error'`. Sufficient to build this tab.

---

## Missing Tab #3: Phase Tracker

**Spec description**: 5-phase roadmap, exit criteria checklist (live-computed), DB readiness gauges.

**What's missing**:
- Visual 5-phase roadmap (Phase 1 through Phase 5)
- Live-computed exit criteria checklist per phase (from `phases/overview.md`)
- DB readiness gauges: Pinecone vectors, Neo4j nodes/rels, Supabase rows vs targets
- Phase transition requirements
- Scaling projection chart (questions tested over time)

**Impact**: MEDIUM — The phase system is central to the project strategy. `phases/overview.md`
documents comprehensive phase gates, but the dashboard provides zero visibility into
phase progression.

**Data available**: `evaluation_phases` and `current_phase` fields exist in the
`data.json` schema but are not rendered. `db_snapshots[]` has Pinecone/Neo4j/Supabase
counts that could populate DB readiness gauges.

---

## Downgraded Tab: AI Insights → Agentic API

**Spec description**: Live analysis, auto-generated recommendations, decision rules, API schema.

**What's implemented**: Static documentation only:
- JSON schema reference (hardcoded in JS, not derived from data)
- Static "decision rules" text (8 rules, not computed)
- GitHub Actions integration docs
- API endpoint reference
- Eval command reference

**What's missing**:
- **Live analysis**: No computed insights from current data
- **Auto-generated recommendations**: No analysis engine
- **Trend summaries**: No auto-generated narrative of what's improving/degrading
- **Priority queue**: No computed prioritization of what to fix next

**Impact**: MEDIUM — The static docs are useful for reference, but the spec intended
this tab to provide live, data-driven insights.

---

## Implemented Tabs: Detailed Assessment

### Test Matrix (tab 1) — COMPLETE

Features implemented:
- [x] Questions x Iterations grid with color-coded cells (pass/fail/error)
- [x] F1 scores displayed in cells with hover tooltips
- [x] Pipeline filter, status filter, search
- [x] Pipeline separator rows
- [x] Trend column (UP/DOWN/stable)
- [x] Click-to-expand question detail panel
- [x] Answer comparison (expected vs actual per run)
- [x] Summary cards (accuracy, passing count, failing+errors, improving/regressing)

Quality: Good. The matrix is the most complete tab.

### Smoke Tests (tab 2) — COMPLETE

Features implemented:
- [x] Per-pipeline health status cards (HEALTHY/FAILING/NO DATA)
- [x] Pass count, average latency per pipeline
- [x] Full test history table with timestamp, status, trigger, latency, query, response
- [x] Recent batch grouping (tests within 2 minutes)

Quality: Good. Covers the spec requirements.

### Iterations (tab 3) — PARTIAL

Features implemented:
- [x] Accuracy trend chart (line chart, per-pipeline + overall)
- [x] Iteration comparison tool (select two iterations, see fixed/broken/improved/regressed)
- [x] Reverse-chronological timeline with metrics per pipeline

Missing from spec:
- [ ] **Burndown to targets** — No visualization showing gap-to-target over iterations
- [ ] **Target lines on chart** — The trend chart has no horizontal target lines

Quality: Good for what's there, but missing the target-gap perspective.

### Questions Explorer (tab 4) — COMPLETE

Features implemented:
- [x] Searchable table (ID, question text, expected answer)
- [x] Pipeline filter, status filter
- [x] Columns: ID, Question, Pipeline, Runs, Pass Rate, Best F1, Status, Trend
- [x] Click-to-expand detail panel with all runs

Quality: Good. Full feature parity with spec.

### Pipelines (tab 5) — PARTIAL

Features implemented:
- [x] Per-pipeline cards with accuracy, target, delta, progress bar, error count, latency
- [x] Accuracy per iteration (grouped bar chart)
- [x] Error rate per iteration (grouped bar chart)
- [x] Average latency (line chart)
- [x] Category breakdown table

Missing from spec:
- [ ] **F1 distribution chart** — No histogram/distribution of F1 scores per pipeline
- [ ] **Error type breakdown** — No per-pipeline error classification chart

Quality: Good foundation, but missing the diagnostic depth needed.

### Workflows (tab 6) — COMPLETE

Features implemented:
- [x] Version cards per pipeline (version number, hash, nodes, models, last sync)
- [x] Workflow version history table
- [x] Click-to-expand diff view (added/removed/modified nodes with parameter changes)

Quality: Good. Diff visualization is particularly useful.

### Changes Log (tab 7) — COMPLETE

Features implemented:
- [x] Workflow changes table with timestamp, type, description, affected pipelines, impact
- [x] DB state over time table (Pinecone vectors, Neo4j nodes/rels, Supabase rows)
- [x] Impact column with before/after accuracy deltas

Quality: Good. Completes the workflow tracking story.

### Agentic API (tab 8) — PARTIAL (see above)

Static documentation, no live analysis.

---

## Code Quality Assessment

### Strengths
1. **Clean structure**: Each render function is isolated (`renderMatrix`, `renderIterations`, etc.)
2. **Proper HTML escaping**: `escHtml()` used consistently to prevent XSS
3. **Chart lifecycle**: Charts properly destroyed before recreation (`charts.iter.destroy()`)
4. **Filter reactivity**: Event listeners properly wired for all filter controls
5. **Responsive**: Basic media queries for grid collapse
6. **Auto-refresh**: 15s interval keeps dashboard current during eval runs

### Weaknesses
1. **No error handling in render**: If any `data.json` field is malformed, the entire render silently breaks
2. **innerHTML everywhere**: No DOM diffing, every refresh rebuilds all HTML (performance concern with large datasets)
3. **Global state**: `DATA`, `selectedQuestion`, `charts` are all global variables
4. **No loading state**: No spinner/skeleton while fetching data
5. **No offline handling**: If `data.json` fetch fails, stale data persists with no user indication
6. **Chart.js from CDN**: No fallback if CDN is unavailable
7. **No URL routing**: Tab state is not reflected in URL (can't link to a specific tab)

### Potential Bugs
1. **Line 779**: `ctx.datasetIndex` used to index into `pipes` array, but there are 5 datasets (4 pipes + "Overall") — accessing `pipes[4]` returns `undefined` which is handled, but the logic is fragile
2. **Line 655**: `q.pass_rate * 100` will throw if `pass_rate` is undefined
3. **Line 903**: Single quotes in question text would break the `onclick="showQDetail('${q.id}')"` handler
4. **Line 1237**: Same single-quote issue in `onclick="showWfDiff('${h.pipeline}','${h.snapshot_file}')"`

---

## Data Format Observations (`data.json` v2.0)

The current `data.json` contains:
- **3 iterations**, 396 total test runs, 200 unique questions
- **Iteration 1**: 52 questions (78.8% overall)
- **Iteration 2**: 147 questions (63.9% overall — more questions, harder set)
- **Iteration 3**: 197 questions (67.7% overall — full 200q set)

Notable: The data contains `evaluation_phases` and `current_phase` fields (referenced
in CLAUDE.md) but these are **not rendered** anywhere in the dashboard.

---

## Priority Recommendations

### P0 — Critical Missing Tabs
1. **Add Command Center tab** as default landing page with phase progress, pipeline gauges, blockers
2. **Add Error Analysis tab** — essential for the current debugging phase (38% orchestrator error rate)

### P1 — Important Gaps
3. **Add Phase Tracker tab** — the 5-phase strategy is central but invisible in the dashboard
4. **Upgrade Agentic API to AI Insights** — add live-computed analysis from data

### P2 — Feature Gaps in Existing Tabs
5. **Iterations**: Add target lines on accuracy chart, add burndown-to-target visualization
6. **Pipelines**: Add F1 distribution histogram, add error type breakdown per pipeline

### P3 — Code Quality
7. Fix potential XSS via `onclick` handlers (use `data-*` attributes + event delegation instead)
8. Add loading/error states for data fetch
9. Add URL hash routing for tab deep-linking

---

## Lines of Code Breakdown

| Section | Lines | % |
|---------|-------|---|
| CSS (styles) | 1-142 | 10% |
| HTML (structure) | 143-414 | 19% |
| JS: Data loading + tab switching | 415-464 | 3% |
| JS: Header + Summary Cards | 465-535 | 5% |
| JS: Test Matrix + Detail | 536-690 | 11% |
| JS: Iterations + Chart + Compare | 691-868 | 12% |
| JS: Questions + Detail | 869-963 | 7% |
| JS: Pipelines + Charts + Categories | 964-1127 | 11% |
| JS: Smoke Tests | 1128-1200 | 5% |
| JS: Workflows + Diff | 1201-1295 | 7% |
| JS: Changes Log | 1296-1343 | 3% |
| JS: Agentic API (static) | 1344-1432 | 6% |
| JS: Utilities + Init | 1433-1449 | 1% |
| **Total** | **1,449** | **100%** |
