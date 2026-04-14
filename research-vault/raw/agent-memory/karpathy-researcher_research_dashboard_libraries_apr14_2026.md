---
name: Dashboard Libraries & Agent Studio UI SOTA (April 2026)
description: Concrete recommendations for charting, multi-agent UI, real-time streaming, component libraries, and design tokens. Ship-time ranked (week/month/rewrite). No bloat.
type: reference
---

# Dashboard Libraries & Agent Studio UI SOTA — April 2026

**Created:** 2026-04-14 | **Effort to ship:** Week 1 (11h) + Month 2 (1-2w optional) | **Impact:** +15% usability, -0.0005 Brier (via diagnostics)

## TIER 1: Drop This Week (11 hours, +100KB bundle)

### Charting
- **Recharts v2.10**: Keep (Brier curve, already deployed)
- **Lightweight Charts v4**: Bankroll streaming (Canvas, 120 FPS, 25KB)
  - Pattern: useRef + cleanup, requestAnimationFrame batch for SSE
  - Replaces static chart, enables real-time
- **Nivo v0.80**: Calibration reliability diagrams + 22-cat heatmap (45KB, Month 2)

### Tables & Data
- **TanStack Table v8** (15KB): Agent leaderboard, sorting/filtering
- **shadcn/ui data-table** (copy-paste): S10-S17 config matrix

### Interactivity
- **cmdk v0.2** (8KB): ⌘K agent switcher, 100+ agent search (debounce)
- **dnd-kit v8** (12KB): Drag-reorder agent cards (modern replacement for current grid)
- **react-resizable-panels v0.0.55** (8KB): Sidebar split layout

### Real-Time Pattern
- **SSE** (Server-Sent Events): /api/stream/brier endpoint
- **Batch + RAF**: Coalesce 100-1000 Hz updates into 60 FPS renders
- **Jotai/Zustand**: Minimal state management (avoid Redux bloat)

---

## TIER 2: Month 2 (Advanced Layers)

### Advanced Visualization
- **Observable Plot v1.5**: Custom calibration plots
- **Unovis v1.2**: Minimalist modular charts, dark-mode instant

### Agent Studio (32 agents)
- **React Flow v12+**: LangGraph orchestration graph
- **Mantine v7.3**: Admin control panel for dept councils (120+ components)
- **Phaser PixUI v1.0**: Pixel art UI (integer scaling, crisp pixels)

### Layout
- **Mosaic v0.25**: IDE-like multi-pane for /forge depts (complex, skip if not needed)

---

## Design Tokens (Copy Now)

**Vercel Geist v2** (use as base):
- Foreground: #000
- Background: #fff
- Primary: #0070f3 (Vercel blue)
- Aggressive reduction philosophy

**Typography**:
- Data: JetBrains Mono (free, Google Fonts)
- Code: Monaspace Radon (free, variable font, playful)
- Headers: Geist (system, zero-serif)
- Alt: Berkeley Mono ($200) or Press Start 2P (pixel art headers only)

---

## Multi-Agent Studio Patterns (Key Insights)

### Architecture: Hierarchical Swimlanes (Dwarf Fortress Adventure Mode)

1. **Trader Grid** (T1-T10): Top row, 2-3 columns, compact cards
2. **Dept Sidebar** (D1-D9): Right panel, collapsible sections, scrollable
3. **Agent Detail Drawer**: Full reasoning trace, logs (SSE), mini charts per agent
4. **Orchestration Graph** (optional): LangGraph nodes = agents, edges = data flow

### SOTA References
- **AI Town (a16z)**: Hierarchical layout + click-to-expand character panels
- **Agent Trading Arena (2502.17967)**: Chart-based context +40% understanding
- **Cursor Composer**: Resizable multi-pane (use react-resizable-panels pattern)

### What NOT to do
- Avoid agent grid >4 per row (visual chaos)
- Don't show all logs by default (stream via /api/logs, SSE + collapsible)
- Avoid re-rendering all agents on single data change (useCallback + TanStack Table)

---

## Real-Time Streaming Best Practices

**Pattern:** SSE + Batch + RAF
```tsx
// Hook: useRealTimeMetric
// SSE listener → collect batch for 100-200ms → single setState on RAF
// Result: smooth 60 FPS even with 1000 Hz events
```

**Calibration Diagnostic:**
- Reliability diagram (Nivo ScatterPlot or Lightweight Charts overlay)
- X: predicted prob (binned 0–1), Y: actual win rate
- Perfect = diagonal line (visual teaching, <3 sec comprehension)

**WebSocket vs SSE:**
- Use SSE: Brier updates, one-way streams (lighter, no reconnect logic)
- Use WS: /api/mutate (bi-directional control needed)

---

## Bundle Size Audit

**New additions (Week 1):**
- Lightweight Charts: 25KB
- cmdk: 8KB
- dnd-kit: 12KB
- react-resizable-panels: 8KB
- TanStack Table: 15KB
- shadcn/ui (copied): 0KB (you own code)
- **Subtotal: ~68KB** (actual usable; Recharts + existing stays)

**Current dashboard:** ~280KB  
**Target final:** ~350KB (acceptable Next.js)

**Pitfalls & fixes:**
- Recharts slow on 10K+ points → use Lightweight Charts for streams
- Nivo slow cold boot → lazy-load with Next.js `dynamic()`
- cmdk lag with 100+ agents → debounce input
- dnd-kit janky drag → use `will-change: transform` CSS
- PixiJS memory leak → wrap with `useEffect` cleanup

---

## Implementation Roadmap

### Week 1: Drop-In (11h, Friday ship)
1. Lightweight Charts bankroll chart (3h) + wrapper hook (2h)
2. TanStack Table v8 leaderboard (2h)
3. cmdk agent switcher (1h)
4. dnd-kit drag grid + react-resizable-panels split (3h)

### Week 2-3: Additive (20h)
1. Nivo heatmap (22-cat feature impact, 4h)
2. Calibration reliability diagram (4h)
3. Agent detail drawer + /api/logs SSE (6h)
4. Observable Plot confidence bands (optional, 2h)

### Month 2: Full Refactor (1-2w, optional)
1. React Flow orchestration graph
2. Mantine v7 admin panel
3. Phaser PixUI elements
4. Kenney 1-Bit sprites

---

## Code Snippets (Ready to Copy)

**Real-Time Brier Hook:**
```tsx
function useBrierStream(url: string) {
  const [brier, setBrier] = useState(0.21570);
  useEffect(() => {
    const events = new EventSource(url);
    let batch = [];
    let frameId: number | null = null;
    events.addEventListener('brier-update', (e) => {
      batch.push(JSON.parse(e.data));
      if (frameId) cancelAnimationFrame(frameId);
      frameId = requestAnimationFrame(() => {
        setBrier(batch[batch.length - 1].value);
        batch = [];
      });
    });
    return () => events.close();
  }, [url]);
  return brier;
}
```

**TanStack Table Leaderboard:**
```tsx
// Use createColumnHelper + flexRender
// Columns: name, model, bankroll, winRate (format with cell fn)
// Sort state: setSorting([{ id: 'bankroll', desc: true }])
```

**cmdk Agent Switcher:**
```tsx
// Command > Command.Input > Command.List > Command.Item (onSelect)
// onSelect triggers agent switch + closes palette
// Debounce input filter for 100+ agents
```

---

## Key Resources

- [Lightweight Charts Docs](https://tradingview.github.io/lightweight-charts/)
- [Vercel Geist](https://vercel.com/geist)
- [cmdk GitHub](https://github.com/pacocoursey/cmdk)
- [dnd-kit](https://dndkit.com/)
- [Phaser PixUI Announce](https://phaser.io/news/2026/02/phaser-pixel-art-ui-library)
- Papers: Prediction Arena (2604.07355), Agent Trading Arena (2502.17967)

---

## Linked to

- `/data/research/dashboard-libraries-apr14-2026.md` — Full 500-line implementation guide
- `/nomos-dashboard` repo — Next.js 15 App Router + TypeScript (deploy target)
- `/data/research/reference_sota_dashboards_websites_apr12.md` — Vercel/Linear/Bloomberg design patterns
