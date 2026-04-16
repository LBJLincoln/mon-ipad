# Nomos42 Dashboard Overhaul — Ship Plan (Apr 16 2026)

**Problem:** Current dashboard shows infra + accounts + live data poorly. No single-pane-of-glass for cross-account resources (Nomos42, LBJLincoln, LBJLincoln26, TESTforge42). Live KPIs scattered. The /world iframe steals focus; /infra page is wall-of-JSON; homepage doesn't surface "what happened today."

**Deliverable:** Rebuild /infra, /, and /world pages using Vercel Geist + Bloomberg terminal aesthetics (per SOTA reference). Apply Moltbook Reddit-dark card grid, dYdX TradingView charting, and OpenBB draggable grid patterns. Target: all 38 agents + 33 HF Spaces + 5 repos + 21 evolution islands + 9 councils + cron schedule visible in <3 seconds.

---

## 1. The /infra Page Rebuild — Single-Pane-of-Glass

**Goal:** Replace the current 53KB JSON wall with a Bloomberg terminal × OpenBB hybrid. Show every HF Space, GitHub Action, Kaggle kernel, Colab notebook, Modal job, and VM cron in one sortable table. Add health badges (🟢 running / 🟡 stale / 🔴 error).

### Design Pattern
- **Header bar (40px):** Account tabs (Nomos42 | LBJLincoln | LBJLincoln26 | TESTforge42)
- **Filter strip:** Resource type (Spaces | Workflows | Kernels | Crons | VMs) + sort (Health | Last Updated | Type)
- **Main table:** 
  - Account × Resource columns (cross-account drill-down)
  - Status badge: 🟢 OK / 🟡 warn / 🔴 error / ⚫ offline
  - Last update timestamp (relative: "5min ago")
  - Quick-action buttons: "Restart" / "Logs" / "Repo" (skip, don't implement—just layout)

### ASCII Sketch (Terminal feeling)
```
┌─ INFRA DASHBOARD ──────────────────────────────────────────────────────────┐
│ [Nomos42] [LBJLincoln] [LBJLincoln26] [TESTforge42]                        │
├─ Type: [All ▼] Sort: [Health ▼]  🔍 Search... ──────────────────────────────┤
├─────────────────────────────────────────────────────────────────────────────┤
│ ACCOUNT │ RESOURCE ID              │ STATUS│ TYPE      │ LAST UPDATE│ DETAIL│
├─────────────────────────────────────────────────────────────────────────────┤
│ Nomos42 │ nba-evolution-island-1   │ 🟢   │ HF Space  │ 2min ago  │ →     │
│ Nomos42 │ political-island-5       │ 🟡   │ HF Space  │ 1hr ago   │ →     │
│ Nomos42 │ daily-predict.yml        │ 🟢   │ GH Action │ now       │ →     │
│ LBJLinc │ kaggle-nba-kernel        │ 🟢   │ Kaggle    │ 12min ago │ →     │
│ TESTfor │ forge-training-vm        │ 🔴   │ VM Cron   │ 3d ago    │ →     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Color Scheme
- Background: `#000000` (true Bloomberg black)
- Status bar: `#111111` (panel surface)
- Monospace numbers: `#FF6600` (Bloomberg amber) for live data
- Border: `#333333` (subtle)
- Table alt-rows: `#0a0a0a` / `#111111` (no harsh contrast)
- Success badge: `#4AF6C3` (teal)
- Warning badge: `#FF9500` (orange)
- Error badge: `#FF433D` (red)
- Font: IBM Plex Mono, 11px, line-height 1.4

### Implementation Details
- **File:** `src/app/infra/page.tsx` (replace entire current 53KB)
- **New component:** `src/components/infra/InfraTableRow.tsx` (single row)
- **New component:** `src/components/infra/AccountFilter.tsx` (tabs + filter)
- **Data source:** `/api/infra/live` (already exists or will be wired)
- **Styling:** Use `.terminal-panel` CSS class from globals.css (Bloomberg theme)

---

## 2. The Homepage Rebuild — "What Happened in Last 24h"

**Goal:** Replace the current calm Anthropic-inspired hero with a **Moltbook Reddit-dark card grid** that surface recent events across all infras. Make it scrollable, not just metrics row.

### Layout
- **Top row (sticky):** Live KPIs in monospace (6 metrics: Best Brier, Walk-forward, OOS ROI, HF Spaces Up, Crons Active, Agents Online)
- **Card grid (4 columns on desktop):** Each card = one event category:
  - 🚀 **Latest Evolution Moves** (card: best Brier island + generation + mutation)
  - 📊 **Trading Floor Leaderboard Snapshot** (card: top 3 agents by P&L)
  - 🔧 **Infra Status** (card: Spaces up/down, last cron run, GPU status)
  - 📱 **Recent Commits** (card: latest git activity across 5 repos)
  - 🎯 **Council Health** (card: 9 dept statuses in mini-grid)
  - ⚡ **Alerts** (card: bottlenecks, failures, manual actions needed)

### Design Pattern (per Moltbook)
Each card:
```tsx
<div className="bg-[#1a1a1b] border border-[#343536] rounded-lg p-4 space-y-3">
  <div className="font-mono text-xs text-[#7C7C7C] uppercase tracking-wide">
    LATEST EVOLUTION
  </div>
  <div className="space-y-2">
    <div className="flex justify-between items-baseline">
      <span className="font-mono text-sm text-[#D7DADC]">island-7</span>
      <span className="font-mono text-xs text-[#4AF6C3]">↑ 0.0047</span>
    </div>
    <div className="text-xs text-[#7C7C7C]">
      Gen 342 · Mutation 0.08 · Brier 0.1892
    </div>
  </div>
  <button className="text-xs text-[#00B8D9] hover:underline">View details →</button>
</div>
```

### Color Scheme (Moltbook + Geist blend)
- Background: `#0a0a0a` (Geist dark default)
- Card bg: `#1a1a1b` (Moltbook Reddit-dark)
- Border: `#343536`
- Primary text: `#D7DADC`
- Muted text: `#7C7C7C`
- Accent cyan: `#22D3EE`
- Accent green: `#22C55E` (profit)
- Accent red: `#EF4444` (loss)
- Font: Geist Mono for numbers, Geist Sans for labels

### Implementation Details
- **File:** `src/app/page.tsx` (refactor existing)
- **New component:** `src/components/home/EventCard.tsx`
- **New component:** `src/components/home/LiveKpiBar.tsx` (sticky top)
- **Data source:** `/api/dashboard/home` (already exists)
- **Styling:** Mix `--ant-*` (existing Mistral tokens) with new Geist/Moltbook tokens defined below

---

## 3. The /world Page Frame — Top Bar + Live KPIs Above Iframe

**Goal:** Add a 40px fixed top bar above the pixel-world iframe showing room tabs (NBA | Political | Evolution) + 4 live KPIs, then full-bleed iframe below.

### Top Bar Design
```
┌─ PIXEL WORLD ──────────────────────────────────────────────────────────────┐
│ [NBA (38)] [Political (36)] [Evolution (21)] [Councils (9)]    Best: 0.1892│
├─────────────────────────────────────────────────────────────────────────────┤
│                      [FULL-BLEED IFRAME BELOW]                             │
│                      https://lbjlincoln26-pixel-world                       │
│                                                                             │
```

- **Left tabs:** Room selectors (CSS only, no route changes — iframe uses hash)
- **Right KPIs:** "Best Brier: 0.1892 | Agents: 38 | Fleet Avg: 0.1876 | Uptime: 99.2%"
- **Font:** Geist Mono for numbers, tabular-nums for alignment
- **Height:** Fixed 40px (no padding, tight density)
- **Sticky:** Yes, always visible
- **Click behavior:** Tab click sends postMessage to iframe (leave as TODO; separate agent handles Pixi)

### Implementation Details
- **File:** `src/app/world/page.tsx` (add top bar before iframe)
- **New component:** `src/components/world/WorldHeader.tsx`
- **Styling:** `.terminal-panel` base + `bg-[#000000]` + `border-b border-[#333333]`
- **Data source:** Refetch `/api/status` every 10s, or SWR hook
- **Note:** Iframe src stays as-is. Do NOT touch Pixi/Canvas content.

---

## 4. File-by-File Change List

### Pages to Overhaul
| File | Change | Reason |
|------|--------|--------|
| `src/app/page.tsx` | Refactor into card grid (Moltbook pattern) | Replace static hero + metrics row |
| `src/app/infra/page.tsx` | Replace 53KB JSON with table UI | Single-pane-of-glass |
| `src/app/world/page.tsx` | Add 40px top bar + sticky header | Surface live KPIs |

### Components to Create
| File | Purpose |
|------|---------|
| `src/components/home/EventCard.tsx` | Reusable card for home grid (evolution, leaderboard, infra, commits, alerts) |
| `src/components/home/LiveKpiBar.tsx` | Sticky top bar with 6 live metrics |
| `src/components/infra/InfraTable.tsx` | Main table wrapper (sortable, filterable) |
| `src/components/infra/InfraTableRow.tsx` | Single row (account + resource + status + actions) |
| `src/components/infra/AccountFilter.tsx` | Tab-based account selector |
| `src/components/world/WorldHeader.tsx` | 40px bar with room tabs + live KPIs |

### Routes That Go Away (consolidate)
- `/nba` → `/markets?tab=nba` (already done)
- `/political` → `/markets?tab=political` (already done)
- `/trading-floor` → `/floor` (rename in nav)
- Keep: `/`, `/markets`, `/floor`, `/evolution`, `/forge`, `/infra`, `/world`, `/subscribe`, `/council`, `/agents`

### API Endpoints Used (no changes needed)
- `GET /api/dashboard/home` — live metrics, trading floor leaderboard, bottlenecks
- `GET /api/infra/live` — all HF Spaces, GPU platforms, status
- `GET /api/status` — overall health for world header
- `GET /api/evolution/islands` — island stats for home card

---

## 5. Install Order (from SOTA memory)

Run these in sequence (no deps between them):
```bash
# Fonts — Geist Sans + Mono
npm install geist

# Real-time polling (replacing setInterval)
npm install swr

# Draggable panel grid (for future /forge page, but doesn't hurt here)
npm install react-grid-layout

# Number animations (countup effect on KPI change)
npm install motion

# Already in your stack — just ensure installed
npm install framer-motion recharts zustand next@15
```

Then add shadcn components:
```bash
npx shadcn@latest add sheet scroll-area tabs badge
```

Update `src/app/globals.css` to define new Geist tokens (see below).

---

## 6. CSS Token Contract (Add to globals.css)

Extend the `:root` block with these new variables (keep existing `--ant-*` tokens):

```css
:root {
  /* Existing Anthropic-warm palette (DO NOT TOUCH) */
  --ant-bg: #faf8f3;
  --ant-accent: #fa500f;
  /* ... etc ... */

  /* NEW: Geist/Moltbook dark palette for infra + world pages */
  --geist-bg: #0a0a0a;          /* Page background (Geist default dark) */
  --geist-panel: #111111;        /* Panel/card surface (Bloomberg panel) */
  --geist-border: #27272a;       /* Border (zinc-800) */
  --geist-text: #fafafa;         /* Primary text (white) */
  --geist-text-secondary: #999999; /* Secondary text */
  
  /* Bloomberg Terminal (for /infra page specifically) */
  --bloomberg-bg: #000000;       /* True black */
  --bloomberg-panel: #111111;    /* Panel surface */
  --bloomberg-amber: #FF6600;    /* Live data numbers */
  --bloomberg-border: #333333;   /* Borders */
  --bloomberg-teal: #4AF6C3;     /* Positive/success */
  --bloomberg-red: #FF433D;      /* Negative/error */
  --bloomberg-warn: #FF9500;     /* Warning/stale */
  
  /* Moltbook Reddit-dark (for home + agent cards) */
  --moltbook-bg: #0a0a0a;
  --moltbook-card: #1a1a1b;
  --moltbook-border: #343536;
  --moltbook-text: #D7DADC;
  --moltbook-muted: #7C7C7C;
  --moltbook-cyan: #22D3EE;      /* Primary accent */
  --moltbook-orange: #FF6B00;    /* Secondary accent */
  
  /* Functional color tokens */
  --color-positive: #22c55e;     /* Green / Profit */
  --color-negative: #ef4444;     /* Red / Loss */
  --color-amber: #f59e0b;        /* Amber / Live data */
}

.terminal-panel {
  background: var(--bloomberg-bg);
  border: 1px solid var(--bloomberg-border);
  font-family: 'IBM Plex Mono', 'Geist Mono', monospace;
  font-size: 11px;
  line-height: 1.4;
  color: var(--bloomberg-amber);
  padding: 8px;
}

.terminal-label {
  color: var(--bloomberg-border);
}

.terminal-positive {
  color: var(--bloomberg-teal);
}

.terminal-negative {
  color: var(--bloomberg-red);
}

.geist-card {
  background: var(--geist-panel);
  border: 1px solid var(--geist-border);
  border-radius: 8px;
  padding: 16px;
}

.moltbook-card {
  background: var(--moltbook-card);
  border: 1px solid var(--moltbook-border);
  border-radius: 8px;
  padding: 16px;
}
```

---

## 7. Top 5 Lines-of-Code Wins (flip "horrible" → "Vercel-Geist clean")

### Win #1: Bloomberg Terminal Monospace Panel (2 CSS rules)
```css
.infra-table {
  font-family: 'IBM Plex Mono', monospace;
  font-variant-numeric: tabular-nums; /* numbers align vertically */
}
```
**Why:** Fixes the "wall of text" by making numbers readable at a glance. Instantly looks professional.

---

### Win #2: Card Grid Layout (3 lines JSX)
```tsx
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 p-6">
  {eventCards.map(card => <EventCard key={card.id} {...card} />)}
</div>
```
**Why:** Replaces linear list with scannable grid. Users can see "what happened" in <2s instead of scrolling.

---

### Win #3: Status Badge Component (1 TSX file, 8 lines)
```tsx
function StatusBadge({ status }: { status: 'ok' | 'warn' | 'error' | 'offline' }) {
  const colors = { ok: '#4AF6C3', warn: '#FF9500', error: '#FF433D', offline: '#666666' }
  return <span style={{ color: colors[status], fontWeight: 'bold' }}>● {status.toUpperCase()}</span>
}
```
**Why:** Human-parseable health at a glance. No more "unknown" states.

---

### Win #4: Live KPI Refresh with SWR (4 lines)
```tsx
import useSWR from 'swr'
const { data: live } = useSWR('/api/status', { refreshInterval: 10000 })
// Now every KPI auto-updates. Replaces 30 lines of useEffect + setInterval mess.
```
**Why:** Real-time feel without polling debt. Users see the dashboard as "alive."

---

### Win #5: Sticky Header (1 Tailwind class)
```tsx
<div className="sticky top-0 bg-[#000000] border-b border-[#333333] z-50 p-4">
  {/* Live KPIs + room tabs */}
</div>
```
**Why:** Context never scrolls off-screen. Users always know what page they're on + current state.

---

## 8. What NOT to Touch

- **Phaser 3D game engine** — Keep `src/components/world/` (the pixel-world canvas)
- **Pixi.js rendering loop** — Leave iframe at `/api/pixel` or HF Space alone
- **Existing /floor page** — Agent leaderboard already works; we're just adding infra context
- **FallbackEmpty states** — Keep existing error handling patterns
- **Auth/subscribe flow** — Don't refactor Stripe integration
- **API routes in /api** — No backend changes (all data already exposed)
- **Trading floor leaderboard data** — Just surface it on home page, don't cache it differently

---

## 9. Deployment Checklist

- [ ] Install new packages (geist, swr, react-grid-layout, motion)
- [ ] Add CSS tokens to `globals.css`
- [ ] Create 6 new components (EventCard, LiveKpiBar, InfraTable*, WorldHeader)
- [ ] Refactor `page.tsx` (home), `infra/page.tsx`, `world/page.tsx`
- [ ] Add shadcn components (sheet, scroll-area, tabs, badge)
- [ ] Test infra table sort + filter on prod-like data
- [ ] Verify world header tabs don't break iframe hash navigation
- [ ] Vercel preview deploy → Vercel prod
- [ ] Roll out Slack notif when live

---

## Summary

**From user complaint:** "still horrible and not perfect displaying of all we have"

**To ship-ready state:**
1. **Single-pane-of-glass infra table** — All 33 HF Spaces + 5 repos + 4 accounts visible instantly
2. **Card grid homepage** — "What happened in 24h" across all systems, not just metrics row
3. **World frame header** — Room tabs + live KPIs cement the pixel-world as the "center of gravity"
4. **Bloomberg + Moltbook visual system** — Monospace, dark, scannable, professional
5. **Geist font contract** — Unifies home + infra + world with Vercel/shadcn standard

**Timeline:** 2-3 hours design review + CSS tokens, 3-4 hours component build + refactor, 1 hour testing = **ship by EOD Apr 16**.

