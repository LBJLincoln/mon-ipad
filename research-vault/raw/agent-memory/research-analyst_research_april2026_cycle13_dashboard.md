---
name: research_april2026_cycle13_dashboard
description: Apr 7 2026 cycle 13: SOTA 2026 quant dashboard patterns — chart library picks, color tokens, empty/skeleton states, CPCV visualization, agent swarm grid, reliability diagrams
type: project
---

# Cycle 13: Dashboard Visualization Patterns (Apr 7 2026)

## Library Decision (final)
- **recharts** (already installed): reliability diagram, drawdown overlay, sparklines, CPCV strip chart — covers 80% of cases
- **lightweight-charts** (TradingView, 45KB canvas): swap in if equity curve data exceeds 1K points or needs crosshair/zoom
- **@xyflow/react** (already installed): Karpathy DAG visualization on /councils — 9 dept loops as directed graphs
- **ApexCharts** (already in use): keep for 102-cat heatmap, add radar chart for 5-trader comparison
- **visx @visx/treemap**: only if adding donor universe treemap on /political — 15KB, D3 squarified, click-zoom

## Top 10 Concrete Improvements

1. **ReliabilityDiagram component** — `/nba/page.tsx` — ComposedChart: calibration curve + perfect diagonal + sharpness bars. Colors: over-confident=#FF6B35, under-confident=#00BFFF. ~1.5h
2. **Drawdown overlay** — extend existing `EquityCurve` SVG in `/nba/page.tsx` to add 60px sub-chart below showing `curve.drawdown` field. Red fill, shared x-axis. ~1h
3. **CPCVStripChart** — `/trading-floor/page.tsx` — thin horizontal bars (4px height, 2px gap), one per fold, green=pass/#00FF88, red=fail/#FF4444, gold threshold line. ~2h
4. **AgentSwarmGrid** — `/world/page.tsx` — dot grid 20x10 for 200 agents, grouped by role, with pulse animation via framer-motion. ~2h
5. **DeptKarpathyDAG** — `/councils/page.tsx` — 9 depts x 5 nodes (SCAN/PROPOSE/EXECUTE/EVALUATE/KEEP+REVERT) using @xyflow/react. ~3h
6. **CSS color token system** — `globals.css` — 8 tokens: --color-gain, --color-loss, --color-bg-dark, etc. Replaces all hardcoded hex. ~0.5h
7. **TraderSparkline** — `TradingFloor.tsx` — 60x28px inline sparklines per trader row in leaderboard. rolling_pnl_7d field needed. ~1.5h
8. **DualArenaEquityPanel** — `/trading-floor/page.tsx` — NBA + Political on same Y-scale ($0-$150K) side-by-side. ~2h
9. **102-cat heatmap drill-down** — `StrategyCharts.tsx` — click cell = slide-over panel with last 5 bets. Add row/col avg ROI summaries. ~2h
10. **Skeleton + empty-state** — all 6 pages — tri-state pattern: loading=skeleton, empty=explanation+CTA, error=last-known timestamp. ~2h total

## Color Token System
```
--color-bg-dark: #0A0E1A      (not pure black — navy like Bloomberg)
--color-card-bg: #111827
--color-border: rgba(255,255,255,0.08)
--color-gain: #00FF88          (already used in nba/page.tsx)
--color-loss: #FF4444          (already used in nba/page.tsx)
--color-warning: #FFD700       (CPCV threshold, target lines)
--color-confidence-hi: #00BFFF
--color-confidence-lo: #FF8C00
--color-neutral: #A0AEC0
--color-text-muted: #4A5568
```

## Empty State Pattern (Grafana SAGA)
- LOADING (null): show Skeleton.tsx ghost layout matching real content shape
- EMPTY ([]): icon + title + 1-sentence explanation + optional CTA button
- ERROR (undefined): "Last known: X min ago" in --color-neutral + retry button
- Do NOT conflate null/undefined — use tri-state { loading, error, data }

## Key Sources
- Grafana SAGA: https://grafana.com/developers/saga/patterns/empty-state/
- TradingAgents v0.2.3: https://github.com/TauricResearch/TradingAgents
- LangGraph Studio: https://blog.langchain.com/langgraph-studio-the-first-agent-ide/
- shadcn sparkline: https://www.shadcn.io/blocks/stats-sparkline
- Apple calibration: https://github.com/apple/ml-calibration

**Why:** The dashboard has evolved organically — some pages have blank holes on API timeout, equity curve lacks drawdown context, CPCV gate is invisible to viewers, 200 agents render as a list (unreadable). These 10 improvements make the dashboard match Bloomberg/Grafana/LangGraph Studio standards.
**How to apply:** All improvements use already-installed libraries (recharts, framer-motion, @xyflow/react). No new npm installs needed except optional lightweight-charts swap.
