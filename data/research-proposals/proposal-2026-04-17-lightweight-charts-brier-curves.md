# Proposal: Replace recharts with TradingView Lightweight Charts on /evolution

**Date:** 2026-04-17  
**Scout:** nomos-scout  
**Status:** OPEN  
**Priority:** HIGH  

## Problem

The /evolution page uses recharts `<LineChart>` SVG rendering for Brier curves across 21 islands. Recharts creates one SVG DOM node per data point. At 1000+ generations per island × 21 islands = 21,000+ DOM nodes when comparing islands. This causes layout thrashing, janky scrubbing, and freezes on mobile (likely Nomos42Picks subscriber use case). Recharts is documented in 2026 benchmarks as freezing above 5,000 data points.

## Proposed Fix

Swap `/evolution` and `/nba` Brier timeline charts from recharts to **TradingView Lightweight Charts** (Canvas-based, 45KB, 60fps at millions of data points).

- Package: `lightweight-charts` + `@tradingview-tools/lightweight-charts-react`
- Chart type: Line series (primary) + Histogram series for gen-count distribution
- Optional: OHLC/Candlestick per week (open=Monday Brier, close=Friday, high/low=week extremes across all islands)

## Implementation Target

- Repo: `nomos-dashboard`
- File: `app/evolution/page.tsx` + `components/charts/BrierCurve.tsx` (new component)
- Keep recharts for simple low-density charts (pie charts on /forge, bar charts with <100 points)
- Lightweight Charts only for time-series dense data: Brier curves, gen timelines, bankroll history

## Brier Impact Estimate

None direct. Indirect: enables smoother analysis of 21-island Brier progression, making it easier to spot which island diverges — potentially catching stagnation faster and triggering mutations sooner.

## Effort Estimate

**Low — 1 day**. The lightweight-charts-react wrapper is drop-in. The main work is mapping our existing `{week, brier}` data structure to LW Charts `{time: 'YYYY-MM-DD', value: 0.221}` format.

## Evidence

- TradingView Lightweight Charts: 9k+ stars, actively maintained 2026, free open source
- claw-empire (1.1k stars, PixiJS 8 production project) confirms Canvas-based rendering stack for data-heavy dashboards
- 2026 benchmark: recharts freezes >5k SVG nodes; LW Charts handles millions via Canvas
- Source: `/home/termius/mon-ipad/data/research/dashboard-pixel-sota-apr17.md` Finding D5

## Not duplicate of

- `dashboard-libraries-apr14-2026.md` mentions recharts as current tier-1 but does not propose a replacement for dense time-series. This proposal is specifically about the Brier curve use case.
