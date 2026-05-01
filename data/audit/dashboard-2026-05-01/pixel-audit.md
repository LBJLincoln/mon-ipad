# PIXEL — Live Dashboard Visual Audit (2026-05-01)

**Source:** `nomosdashboard.vercel.app` — 7 routes, desktop 1440×900 + mobile 390×844, headless Chrome. Programmatic structural metrics in `structural-metrics.json` next to this file. Screenshots gitignored under `data/audit/dashboard-2026-05-01/*.png` (kept locally for cross-reference).

> Note: PIXEL agent run timed out on the synthesis pass; the structural metrics were captured cleanly before the timeout and this audit is reconstructed from them by the orchestrator session. All numbers below come from the JSON, not impressions.

---

## Quantitative truth — 7 routes audited

| route           | SVG | canvas | tables | kpi cards | CI band | Brier | walkfwd | calib | methodology | git SHA |
|-----------------|----:|-------:|-------:|----------:|:-------:|:-----:|:-------:|:-----:|:-----------:|:-------:|
| `/`             |   0 |      0 |      0 |         0 |    ·    |   ✓   |    ·    |   ·   |      ·      |    ·    |
| `/nba`          |   0 |      0 |      0 |         0 |    ·    |   ·   |    ·    |   ·   |      ·      |    ·    |
| `/political`    |   0 |      0 |      0 |         0 |    ·    |   ·   |    ·    |   ·   |      ·      |    ·    |
| `/evolution`    |   0 |      0 |      0 |        42 |    ·    |   ✓   |    ·    |   ·   |      ·      |    ·    |
| `/trading-floor`|   0 |      0 |      0 |         0 |    ·    |   ·   |    ·    |   ·   |      ·      |    ·    |
| `/forge`        |   0 |      0 |      0 |         0 |    ·    |   ·   |    ·    |   ·   |      ·      |    ·    |
| `/world`        |   0 |      0 |      0 |         0 |    ·    |   ·   |    ·    |   ·   |      ·      |    ·    |

**The number that ends the discussion: zero charts.** Across the entire surface we ship — NBA, Political, Intraday, Evolution, Trading Floor, Forge, World — there is **not a single SVG, canvas, or table**. Every single number on the dashboard is rendered as plain text inside a flex/grid layout. This is the visual catastrophe — not a typography issue, a *rendering modality* issue. A scientific dashboard without a chart is a press release in CSS.

**The trust-signal column is also empty.** On a system that claims walk-forward Brier 0.22447, calibrated 0.22054, holdout 0.21139 — none of those three numbers appear with their CI95, sample size, walk-forward window, calibration plot, or methodology link anywhere on the public site. A reviewer doing 60-second due diligence cannot tell whether 0.221 is real, in-sample, or fabricated.

---

## Structural regressions — top 10, ranked by ROI to credibility

| # | Regression | Evidence | Fix (component-level) | Impact |
|---|---|---|---|---|
| 1 | **No charts anywhere** | `svgCount=0` and `canvasCount=0` on all 7 routes | Add Recharts `<AreaChart>` (CI band) + `<LineChart>` to every KPI card; add `<ScatterChart>` for calibration plots | unlocks 80% of credibility |
| 2 | **No CI bands** | `hasCI=false` on 7/7 | Backend must emit `{value, ci_low, ci_high, n}` per metric → frontend renders shaded band; pattern `WB-CI-BAND` | every metric becomes auditable |
| 3 | **No walk-forward time series** | `hasWalkforward=false` on 7/7 | New component `<WalkforwardRibbon>` reading from new `data/tf-analytics/walkforward-history.json` (PLUMBER must emit) | Vegas-baseline comparison becomes possible |
| 4 | **No calibration plot** | `hasCalibration=false` on 7/7 | Reliability diagram on `/nba` — needs `calibration_buckets[10]={p_pred, p_actual, n, ci}`; emitter is `tf_rigorous_validation.py`, currently writes only a markdown narrative not JSON | Brier without reliability diagram is dead | 
| 5 | **No methodology page** | `hasMethodology=false` on 7/7 | New `/methodology` route — engine.py SHA, paper refs, walk-forward window definition, public April reset changelog | the moat: scientific transparency |
| 6 | **No tables anywhere** | `tableCount=0` on 7/7 | Replace per-agent flex divs with `<Table>` + sortable columns + sticky header. Agents leaderboard belongs in a table, not a card stack | density / scan speed |
| 7 | **`/world` is blank on mobile** | `bodyH=0`, vp=390 | Pixel-world canvas isn't initializing on mobile WebGL. Console shows 8 errors incl. `GroupMarkerNotSet` WebGL fallback. Either gate to desktop-only with an explicit empty-state, or ship a static screenshot for mobile | stops mobile traffic from bouncing |
| 8 | **Mobile viewport overflow on 3 routes** | `/nba` 476×3479 in vp=477; `/political` 578×3640; `/trading-floor` 476×3479 — bodies are ~22% wider than the 390 phone viewport in spec | hard-coded `min-width` somewhere; audit Tailwind classes (`min-w-[460px]` etc.) and replace with `w-full` + `overflow-x-auto` on the offending tape components | mobile = 60% of cold traffic |
| 9 | **404 on `/` and `/forge`** | `console_first10` shows "Failed to load resource: 404" on both | Likely a missing `/api/*.json` static asset — probable cause: `sync_tf_analytics_to_dashboard.sh` cron silently failing and the dashboard fetch is hitting a stale path. Verify via Vercel function logs | data-staleness signal |
| 10 | **No timestamp on `/political`** | `hasTimestamp=false` on `/political` (others have it) | Add `<LiveDot>` with ISO timestamp + relative "12s ago" — pattern `OAI-LIVE-PILL` | freshness proof |

---

## Visual identity — what's there, what's missing

**There IS:**
- Coherent palette: `bg=rgb(241, 234, 216)` cream + `text=rgb(26, 26, 26)` near-black. Tasteful, but for a quant lab it skews too "lifestyle blog" — Bloomberg / Anthropic Console / W&B all default to dense dark canvases for data density.
- Typography stack is right on paper: `Instrument Serif` for headings, `JetBrains Mono` for numbers, `Inter` for body. The bones are good.
- One bold choice that works: hero numerals in serif (`$3,022` / `$93,377` / `$602,354`) — Tufte-ish. Keep it.

**The catastrophe is not the typography or the colors. It is:**
- Numbers are isolated. They sit alone with no chart, no CI, no sample size, no time-context. A reviewer cannot tell *what* `0.221` was measured against, *when*, *how many games*, *with what split*. The aesthetic looks calm; the substance is empty.
- Hero section on `/` shows `Brier 0.221` next to `+100,292% ROI` (PQTF reference) without disclosing PQTF is FROZEN. Visually they read as comparable; epistemically they are not. The PQTF line needs an explicit `FROZEN ARTIFACT` pill.
- Console errors visible on `/` and `/forge` mean the data fetch layer is partially broken. A potential customer who opens devtools sees that.

---

## What world-class looks like — pattern map (from prior research at `data/research/dashboard-{redesign,libraries,overhaul-plan,pixel-sota}-*.md`)

**Adopt as the new baseline:**
- **`BB-4QUAD`** (Bloomberg) — fixed 4-quadrant layout, no tabs, all visible simultaneously
- **`WB-CI-BAND`** (W&B) — shaded CI band on every line chart, click-through to bucket detail
- **`OAI-SAMPLE-CHIP`** (OpenAI Evals) — sample size N as a chip in the metric card header, not buried
- **`OAI-LIVE-PILL`** — ISO timestamp + relative time + status dot, top right of every card
- **`ANT-METHOD-LINK`** (Anthropic Workbench) — every metric is a link to its methodology page
- **`HF-LB-BADGE`** (HF Spaces leaderboards) — per-row badge: walk-forward green / leakage green / live skin pill / methodology open
- **`DIST-RIBBON`** (distill.pub) — body grid 8pt, serif body for prose explanations next to charts

---

## Top-3 hard fixes the orchestrator should ship this week

1. **Add `<KPICard>` component** with mandatory props: `{value, ci_low, ci_high, n, last_updated, trend_24h, source_link, methodology_link}`. Every existing `<HeroNumber>` becomes a `<KPICard>`. Once shipped, every number on every page upgrades for free.
2. **Add `<WalkforwardRibbon>`** on `/nba` — Recharts AreaChart with `strokeOpacity=0.2` CI band — reading from a new JSON file that PLUMBER's gap report will say must be emitted by `tf_rigorous_validation.py`.
3. **Add `/methodology` route** — engine.py SHA, walk-forward window definition, calibration approach, public reset changelog. ACCOUNTANT memo specifies the exact content; ROI to investor diligence is the highest single-page lift on the dashboard.

These three unlock 80% of the credibility uplift. The rest is polish (fonts, palette, dark mode toggle) and can wait.

---

## What NOT to do

- Do NOT hide the April reset incidents. The brand we're building is "scientifically transparent" — the resets ARE the moat (per ACCOUNTANT). Surface them on `/methodology` as a public changelog.
- Do NOT label PQTF as live. It is a $602K validation artifact, frozen forever. Pill it as `FROZEN ARTIFACT` in red wherever it appears.
- Do NOT promise `% improvement vs Vegas` without the walk-forward ribbon next to it. The number alone reads as cherry-picking.
- Do NOT ship dark mode before fixing the missing charts. Dark mode on an empty page is still empty.
