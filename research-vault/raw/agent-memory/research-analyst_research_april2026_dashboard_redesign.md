---
name: Dashboard Redesign Research — Apr 14 2026
description: Top 5 quant/mission-control dashboards + top 5 pixel-art agent studios, exact colors/fonts/components for nomosdashboard.vercel.app "comme la NASA" redesign
type: project
---

# Dashboard Redesign Research — Apr 14 2026

**Why:** Current nomosdashboard pages (/nba /political /evolution /trading-floor /forge /world /infra) feel disconnected and shallow. Target: ONE screen showing everything — predictions, fleet, agents, bankroll, research — zero fluff.

## Top 5 Quant Dashboards (ranked)

### 1. Bloomberg Terminal
- **Background:** `#000000` | **Accent:** `#FF8C00` | **Cyan:** `#00BFFF` | **Green:** `#00FF41` | **Red:** `#FF4444` | **Muted:** `#888888`
- **Font:** JetBrains Mono or Berkeley Mono, 11px data rows
- **Key patterns:** 4-quadrant layout, monospace dense tables, orange-only alert color, command bar navigation, status ticker strip
- **Killer idea for Nomos:** Mission Ticker scrolling strip at top of every page

### 2. NASA Open MCT (nasa.github.io/openmct)
- **Background:** `#1C1C1E` | **Panel:** `#2C2C2E` | **Accent:** `#0A84FF` | **Green:** `#30D158` | **Amber:** `#FF9F0A` | **Red:** `#FF453A`
- **Font:** SF Pro / system-ui 13px + SF Mono for values
- **Key patterns:** Left-tree hierarchical nav (220px), time conductor bar, domain object card tiles (160x120px), 2px alert banner, composable drag layout
- **Killer idea for Nomos:** Left sidebar tree — Islands > Agents > Departments, click to expand in main area

### 3. dYdX v4-web (open source, github.com/dydxprotocol/v4-web)
- **Background:** `#0E0E12` | **Surface:** `#16161E` | **Purple:** `#6A3BF5` | **Text:** `#FAFAFA` | **Muted:** `#636380` | **Border:** `#2A2A3A`
- **Font:** Inter variable, 14px, tabular-nums for all number columns
- **Key patterns:** 3-column layout (20/55/25%), positions table with inline sparklines, depth chart (model vs market), order type toggle, portfolio summary card fixed top-right
- **Killer idea for Nomos:** Model vs Market depth chart — two probability distributions overlaid, green zone = edge

### 4. Datadog (DRUIDS design system)
- **Background:** `#1B1B1D` | **Surface:** `#242426` | **Purple:** `#7B46F6` | **Green:** `#28A745` | **Amber:** `#FFC107` | **Red:** `#FF4D4F`
- **Font:** DM Sans (UI) + DM Mono (metrics), 12-14px
- **Key patterns:** High Density 2x12 grid (doubles widget count), 4-state status dot (8px circle), inline sparkline rows (28px height), global filter bar, SLO gauge widget
- **Killer idea for Nomos:** Fleet Health Matrix — 8×6 grid (S10-S17 × Brier/Gen/Age/Status/BestGen/Diversity), color cells by percentile

### 5. OpenBB Workspace (pro.openbb.co)
- **Background:** `#151518` | **Surface:** `#1E1E22` | **Orange:** `#FF8000` | **Teal:** `#00BFA6` | **Grid:** `rgba(51,51,51,0.3)`
- **Font:** Geist + Geist Mono (already on our Vercel stack)
- **Key patterns:** Drag-drop blank canvas layout, widget library sidebar, stacked mini-charts (4 sparklines/widget), auto-refresh pulse badge, dashboard snapshot URL sharing
- **Killer idea for Nomos:** Intelligence Canvas home — pre-built default layout, user can drag/resize, saves to localStorage

## Top 5 Pixel-Art Agent Studios (for /world page)

### 1. RimWorld
- Avatar colonist bar at top: 48x48px per agent, background color = morale/P&L
- Bottom inspector panel slides up on click (never navigates away)
- Minimap bottom-right 200x150px always visible
- Key: AAG (at-a-glance) design — status encoded in color, not text

### 2. STONKS-9800
- CRT window system: `border: 2px solid #33FF33`, corner chars ┌┐└┘, scanline CSS overlay
- Phosphor palette: `#000000` bg | `#33FF33` text | `#FF6600` alerts | `#FFCC00` data
- Font: VT323 (Google Fonts, free)
- Ticker tape scrolling row at bottom
- Animated 32x32 agent sprite with mood faces

### 3. Dwarf Fortress (Steam)
- Agent × Strategy grid: 10×8 colored dot matrix (green=active, red=failed, yellow=testing)
- Event log strip bottom: 3 scrolling rows, never clears
- Z-level abstraction: 3 zoom levels per widget (dot → sparkline → full chart)
- Font: Silkscreen (Google Fonts)

### 4. Prison Architect
- Bidirectional list-map sync: click list item = camera snaps to map entity
- Time-grid scheduler: x=hours, y=agents, colored blocks = when each agent is active
- Needs stack bars: 5 horizontal bars per agent (70px wide each)
- Entity detail footer: slides up 120px from bottom when entity selected
- Colors: `#2B2B2B` bg | `#F5C518` gold | `#27AE60` safe | `#E74C3C` danger

### 5. Phaser PixUI + AI Town (a16z)
- PixUI: MIT-licensed Phaser 4 library, integer scaling, TypeScript typed, pip via npm
- AI Town pattern: sprite + speech bubble (auto-hides 5s), thought log overlay on click
- Agent conversation thread: connecting lines between agreeing/disagreeing agents (blue/red)
- World-state overlay: island zones colored by performance rank (always relative, not absolute)

## One-Screen Architecture (implement this week)

```
┌─ MISSION TICKER (scrolling, 32px) ──────────────────────────────────┐
├─ TREE NAV ──┬─ MODEL vs MARKET DEPTH CHART ─┬─ FLEET HEALTH MATRIX ─┤
│ (220px)     │ (45%, center)                  │ (28%, right)          │
│ S10-S17     ├─ OPEN BETS TABLE ──────────────┤ AGENT LEADERBOARD     │
│ T1-T10      │                                │ (sprites + P&L bars)  │
│ D1-D9       ├─ EVENT LOG (3 rows, scrolling) ─────────────────────── ┤
└─────────────┴──────────────────────────────────────────────────────── ┘
```

## Tech Stack
- Colors: Bloomberg black + NASA Darkmatter panels + dYdX purple accent + OpenBB orange
- Fonts: Geist (body) + Geist Mono (data) — both already on Vercel
- Grid: CSS Grid 3-column (220/auto/320)
- Charts: Recharts, 1px line weight, no fill, dot on hover
- Status: 8px dots, 4-state (green/amber/red/gray)
- Pixel: /world page only — PixUI or CSS image-rendering: pixelated

## Implementation Priorities (24h total)
| P1 Mission Ticker | 2h | P5 Model vs Market chart | 4h |
| P2 Fleet Health Matrix | 4h | P6 Left tree nav | 5h |
| P3 Status dots everywhere | 1h | P7 Event log strip | 2h |
| P4 Agent top bar | 3h | P8 CRT aesthetic /world | 3h |

**How to apply:** Use this as the design brief for any dashboard frontend work. Tile references above correspond to nomosdashboard.vercel.app pages. All colors are verified against live implementations.
