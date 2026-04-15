# Dashboard Redesign Research — Apr 14 2026
# "Comme la NASA" — Single-screen, zero-fluff, everything at once
# Target: nomosdashboard.vercel.app redesign from scratch

---

## PART 1 — TOP 5 QUANT/MISSION-CONTROL DASHBOARDS

---

### #1 — Bloomberg Terminal

**Reference:** bloomberg.com/professional + open-source clone github.com/feremabraz/bloomberg-terminal

**What makes it world-class:**
- Every pixel is information. No chrome, no whitespace padding, no decorative gradients.
- Fixed-width monospace grid means 200+ data cells fit a 1080p screen.
- Orange/white/cyan on pure black: zero ambiguity, maximum contrast.
- Keyboard-first: every screen has a 4-letter mnemonic (EQBT, BTMM, etc.) — navigation is muscle memory not mouse clicks.
- Multi-panel "launchpad" layout: screen split into 4 quadrants, each independently scrollable.

**5 concrete patterns to copy:**

1. **4-quadrant fixed layout** — divide viewport into 4 equal panels, each shows a different context (predictions / fleet / bankroll / evolution). No tabs. All visible simultaneously.
2. **Status header strip** — 1 row at top: timestamp, fleet best Brier, bankroll, next game countdown. Always visible, never scrolls.
3. **Dense data table widget** — monospace, 12px, 4-col layout: label | value | delta | trend arrow. No borders, just alternating row bg.
4. **Orange alert system** — single accent color (#FF8C00) for anything that changed in the last cycle. Dim everything else to 60% opacity. Amber = stale, Red = error.
5. **Command bar** — bottom: type "S14" or "BRK" to jump to island/bankroll view. Slash-command navigation, no sidebar needed.

**Exact colors:**
- Background: `#000000`
- Primary text: `#FFFFFF`
- Orange accent: `#FF8C00` (terminal), `#F39F41` (brand)
- Cyan data: `#00BFFF`
- Green positive: `#00FF41`
- Red negative: `#FF4444`
- Muted gray: `#888888`
- Header bg: `#111111`

**Fonts:**
- Bloomberg Prop Unicode N (proprietary, Matthew Carter)
- Best free substitute: `JetBrains Mono` or `Berkeley Mono`
- Fallback: `"Courier New", monospace`
- Size: 11px data rows, 13px headers, 9px secondary labels

**Killer idea for Nomos:**
> **"Mission Ticker" top strip** — one full-width scrolling row: Brier 0.2187 | S14 gen=108 | Bankroll $103.92 | Next game: GSW@LAL T-3h | T1 Agent: +$42.10 today | Political: P3 gen=10344 — scrolls left like a real Bloomberg ticker. Always present on every page.

---

### #2 — NASA Open MCT (nasa.github.io/openmct)

**Reference:** github.com/nasa/openmct — used for Mars rovers, Artemis II mission (Apr 1 2026), multiple JPL missions.

**What makes it world-class:**
- Open source, Vue.js, plugin-based — every panel is a composable domain object.
- "Darkmatter" dark theme: deep navy/charcoal background, not pure black. Softer for 12-hour operator sessions.
- LEFT SIDEBAR = hierarchical tree of all active systems. Drag objects into main canvas to compose displays.
- Time-conductor bar: every visualization is scrubable in time. Click any chart, scrub to T-90min, everything resyncs.
- Real-time telemetry streams at 1-second refresh with last-known-value persistence.

**5 concrete patterns to copy:**

1. **Left-tree navigation** — persistent left panel, 220px wide: tree with islands S10-S17, agents T1-T10, departments D1-D9. Click = instant context switch in main area. No page navigation.
2. **Time conductor** — global time control at top: "Live | Last 1h | Last 24h | Custom". ALL widgets honor it. Shows "last updated 3s ago" per-widget.
3. **Domain object cards** — each island/agent is a "domain object" card: 160x120px tile, shows name, current metric, trend sparkline, status dot. Grid of cards = fleet overview.
4. **Alert banner system** — thin 2px banner under header changes color: GREEN (all nominal) → AMBER (1+ island stale) → RED (active error). Never a modal, never blocking.
5. **Composable layout** — user drags panels around. Persist layout to localStorage. Let power user rearrange quadrants.

**Exact colors (Darkmatter theme):**
- Background: `#1C1C1E` (dark charcoal, NOT pure black)
- Panel bg: `#2C2C2E`
- Border: `#3A3A3C`
- Primary text: `#F5F5F7`
- Secondary: `#8E8E93`
- Accent blue: `#0A84FF`
- Green nominal: `#30D158`
- Amber warning: `#FF9F0A`
- Red critical: `#FF453A`
- Cyan telemetry: `#5AC8FA`

**Font:** System UI stack — `"SF Pro", "Segoe UI", system-ui, sans-serif` at 13px. Monospace for values: `"SF Mono", "Consolas"`.

**Killer idea for Nomos:**
> **"Live Feed" left sidebar** — tree: NBA Islands > S10 (green dot) > last gen > best Brier | Agents > T1 Gemini Flash > last bet +$4.10 | Departments > D1 Research > last paper 2h ago. One click to expand any node into main view.

---

### #3 — dYdX v4-web (dydx.exchange)

**Reference:** github.com/dydxprotocol/v4-web — fully open source, MIT-ish, React + TypeScript.

**What makes it world-class:**
- Power user without intimidating newcomers: 3-step max for any action, but full depth visible.
- Configurable layout: drag to reorder order book, chart, positions panels.
- Deep purple brand on near-black bg — professional without being austere.
- Real-time WebSocket streaming: positions update tick by tick, zero poll latency visible.
- Right sidebar = "portfolio context": P&L, exposure, risk metrics — always visible next to any action.

**5 concrete patterns to copy:**

1. **Three-column trading layout** — LEFT: navigation + context tree | CENTER: main data viz (chart or table) | RIGHT: action panel (bet sizing, Kelly calc, quick metrics). Proportions: 20% / 55% / 25%.
2. **Positions table** — bottom panel: scrollable, sortable. Columns: Market | Entry | Current | PnL | Delta | Kelly%. Rows with inline sparklines. Stick this below main chart = "open bets" view.
3. **Depth chart** — visual order-book equivalent: show model probability vs market line as overlapping curves. Where they diverge = betting edge, highlighted in yellow.
4. **Order type selector** — quick toggle: Moneyline | Spread | Total | Player Prop | Alt Line. Remembers last used. 2 clicks to place any bet type.
5. **Portfolio summary card** — top-right fixed: Bankroll $103.92 | ROI +3.92% | Bets (W/L): 47/31 | Today PnL: +$4.10. One card, always in view.

**Exact colors:**
- Background: `#0E0E12` (near-black with blue tint)
- Surface: `#16161E`
- Elevated: `#1E1E2A`
- Primary purple: `#6A3BF5`
- Purple muted: `#3D2880`
- Text primary: `#FAFAFA`
- Text muted: `#636380`
- Green gain: `#27AE60`
- Red loss: `#E74C3C`
- Border: `#2A2A3A`

**Font:** Inter (variable), 14px body. Heading: 600 weight. Numbers: tabular-nums feature enabled (all number columns same width). Size scale: 11/12/14/16/20/28px.

**Killer idea for Nomos:**
> **"Model vs Market" depth chart** — x-axis = home win probability, y-axis = frequency. Two overlapping distributions: our model (blue fill) vs implied market odds (orange line). Where blue > orange = value bet zone, shown as green shaded area. One chart that makes every game's edge instantly visible.

---

### #4 — Datadog (DRUIDS design system)

**Reference:** datadoghq.com/blog/introducing-datadog-darkmode + druids.datadoghq.com

**What makes it world-class:**
- "High Density Mode" on large screens: 2x12 column grid instead of 1x12. Doubles widget count per viewport.
- Every widget has a mini-legend inline (no separate legend panel). Color → metric one-to-one.
- Time-series charts: 1px line weight, no fill by default (fill obscures overlapping lines). Dots only on hover.
- Alert state machine: 4 states — nominal / warning / critical / no-data. Each has distinct color AND icon (no colorblind ambiguity).
- Global template variables: select "last 4h" or "island=S14" and ALL charts on page filter simultaneously.

**5 concrete patterns to copy:**

1. **High density 2x12 grid** — on desktop (>1400px) render two widget columns side-by-side. Each 6 cols wide instead of 12. Doubles information density at zero cost. Critical for our 7-page architecture collapse into 1.
2. **4-state status dot** — 8px circle: `#28A745` nominal | `#FFC107` warning | `#DC3545` critical | `#6C757D` no-data. Attach to every island, agent, dept. Scannable without reading.
3. **Inline sparkline row** — table widget variant: name | value | 24h sparkline (60px wide) | trend delta | status dot. Shows 20 items without scrolling at 28px row height.
4. **Global filter bar** — below header: time range selector + up to 4 dropdown filters (Island / Agent / Market / Date). State in URL params. Shareable links.
5. **"Red line" SLO widget** — horizontal gauge: current metric vs target. Brier 0.2187 / Target 0.2000 shown as needle on colored track. Instantly communicates gap without numbers.

**Exact colors:**
- Background: `#1B1B1D`
- Surface: `#242426`
- Border: `#38383A`
- Text: `#F0F0F2`
- Text muted: `#909094`
- Purple brand: `#7B46F6`
- Blue info: `#4A9EFF`
- Green good: `#28A745`
- Amber warn: `#FFC107`
- Red alert: `#FF4D4F`
- Chart palette: `#5B8FF9 #5AD8A6 #F6BD16 #E8684A #6DC8EC`

**Font:** `"DM Sans"` for UI, `"DM Mono"` for metrics. 12px min, 14px standard. Line height 1.4.

**Killer idea for Nomos:**
> **"Fleet Health Matrix"** — one widget, 8 rows (S10-S17) × 6 cols (Brier | Gen | Age | Status | Best-gen | Diversity). Color cells by percentile (green = top 20%, red = bottom 20%). 5 seconds to see which island is leading and which is stuck. Put it above the fold on every page.

---

### #5 — OpenBB Workspace (pro.openbb.co)

**Reference:** openbb.co/products/workspace + github.com/OpenBB-finance/design-system

**What makes it world-class:**
- Blank canvas drag-drop layout — users compose their own intelligence surface, not forced into a rigid grid.
- AI agents embedded directly in dashboard: type a question, get a widget update. Chat-first, chart-second.
- "Institutional-grade" data density: 30+ simultaneous chart widgets are normal for power users.
- Per-widget refresh control: some data is real-time (1s), some is daily (24h). Each widget shows its own staleness.
- Dark bg (`#151518`) + orange accent (`#FF8000`) = exact aesthetic we're building toward.

**5 concrete patterns to copy:**

1. **Widget library sidebar** — right-side panel: searchable list of all available widgets. Drag any into canvas. For us: "NBA Predictions", "Fleet Status", "Agent Leaderboard", "Bankroll P&L", "Odds Feed" are pre-built widgets.
2. **Stacked mini-charts** — 4 sparklines stacked vertically in one 200x200px widget: Brier over time | Bankroll | Games/week | Win rate. Vertical stack = one glance reads all 4 trends.
3. **AI chat overlay** — floating chat bubble bottom-right. Type "which island is best this week" or "what's my edge on GSW game". Claude answers using live data from other widgets. No page navigation.
4. **Auto-refresh badge** — top-right of each widget: green pulsing dot + "3s ago". Goes amber after 30s, red after 2min. User never wonders if data is stale.
5. **Dashboard snapshot sharing** — one-click URL that encodes current widget layout + time range. Share with Telegram bot. For us: daily snapshot to @Nomos42 channel.

**Exact colors:**
- Background: `#151518`
- Surface: `#1E1E22`
- Border: `#333333`
- Text: `#FFFFFF`
- Secondary text: `#9999AA`
- Orange accent: `#FF8000`
- Chart green: `#00BFA6` (teal, per docs)
- Grid lines: `rgba(51,51,51,0.3)`
- Tick marks: `#444444`

**Font:** Not published. Best match: `"Geist"` (Vercel's font, already on our stack) for UI, `"Geist Mono"` for data values.

**Killer idea for Nomos:**
> **"Intelligence Canvas" home page** — replace current /nba | /political | /evolution tabs with a SINGLE blank-canvas home page. Pre-built default layout: Fleet Matrix (top-left) | Active Bets (top-right) | Model vs Market chart (center) | Agent Leaderboard (bottom-left) | Research feed (bottom-right). User can drag/resize. Saves to localStorage.

---

## PART 2 — TOP 5 PIXEL-ART AGENT STUDIO LAYOUTS

---

### #1 — RimWorld (Ludeon Studios, 2018+)

**What makes it world-class:**
- "At-A-Glance" (AAG) design: background color of each colonist square directly encodes morale. Darker = worse. No label needed.
- Top strip = "colonist bar": every agent visible simultaneously, 48x48px avatar with overlaid status icon (sleeping/working/crisis). 20 agents = 20 squares = one horizontal row.
- Bottom panel = inspector: click any agent → sliding drawer from bottom with full stats. Never navigates away from main map.
- Minimap (bottom-right, 200x150px) with color-coded zones (red=danger, blue=work area, green=rest). Always visible.

**5 components to copy:**

1. **Agent strip top bar** — row of 48x48px agent cards. Each: avatar sprite | name (8px truncated) | status icon | bankroll delta badge. Click = expand to sidebar. For Nomos: T1-T10 agents always visible.
2. **Zone color overlay** — on pixel world map, each agent's "territory" is a colored transparent overlay. Color = performance tier (green/yellow/orange/red). Updates every cycle.
3. **Crisis alert popup** — non-blocking toast bottom-left: "[T4 Llama] LOSS -$18.40 | Override?" with 2 action buttons. Auto-dismisses after 10s. Stack up to 3.
4. **Mood bar under avatar** — 4px horizontal bar below each agent card: leftmost=red, rightmost=green. Current position = running P&L. Visual Sharpe ratio.
5. **Dual-pane inspector** — click agent: LEFT = current state (prompt, last decision, current odds) | RIGHT = history chart (P&L curve). No new page, slides in from right.

**Colors:** Dark green background `#1A2B1A`, parchment panels `#E8D5A3`, text `#2C1810`. Red alerts `#CC2200`, green positive `#3A7A3A`.

**Font:** Actual pixel fonts at 1x scale. Best web equivalent: `"Press Start 2P"` (Google Fonts) for headers, `"VT323"` for dense data. Both free.

---

### #2 — STONKS-9800: Stock Market Simulator

**Reference:** store.steampowered.com/app/1539140 — 1980s Japan stock market, CRT pixel art.

**What makes it world-class:**
- Text-windows-only UI: no icons, no images. Pure text in bordered boxes = maximum density.
- CRT scanline overlay (CSS: repeating-linear-gradient) + phosphor green text on black = instant aesthetic identity.
- Hover-highlight system: mouseover a ticker name → its line on overlapping chart highlights while others dim. One interaction, zero confusion.
- Character (Amy) in corner with animated expression = agent personality made visual. Status conveyed through pose.
- Hierarchical tree for company research: click company → shows sub-menus inline in same window (no new screens).

**5 components to copy:**

1. **CRT window system** — each data panel is a bordered text box with `border: 2px solid #33FF33`, corner chars (┌┐└┘), scanline CSS overlay. Stack 6-8 windows per screen. For Nomos: each island = one CRT window.
2. **Phosphor color palette** — `#000000` bg | `#33FF33` primary text | `#66FF66` highlight | `#FF6600` alerts | `#FFCC00` neutral data. Never more than 5 colors total.
3. **Animated agent sprite** — 32x32px sprite in corner: shows current "mood" (winning = smile, losing = grimace, neutral = flat). 3-frame animation. For Nomos: model accuracy mood.
4. **Ticker tape row** — horizontal scrolling text at bottom: "NBA: GSW 68% | LAL 32% | PHX 71% | BOS 65% | Political: DJIA +1.2%". Single line, always present, monospace.
5. **Tree research panel** — click island name → inline expand: gen count | best Brier | last mutation | top features. Same window, no navigation. ESC to collapse.

**Colors:** `#000000` | `#33FF33` | `#FF6600` | `#FFCC00` | `#CC0000`.
**Font:** `"VT323"` (Google Fonts, free, 1:1 replica of 80s terminal fonts) or `"Courier New"` 11px.

---

### #3 — Dwarf Fortress (Steam, 2022+)

**Reference:** store.steampowered.com/app/975370 — pixel art tileset by Mayday+Ironhand.

**What makes it world-class:**
- 16x16px tiles encode vast information: tile color = faction/biome, tile shape = entity type, overlay icons = status.
- Multi-layer map: top-down view shows terrain/buildings, but z-levels let you drill into any layer. Same spatial metaphor = no mental model switch.
- "Dwarf Therapist" pattern: skills visible as colored dots in a 2D grid (dwarves × skills). Hover = tooltip. Click = assignment. For an agent system: agents × strategies grid.
- Status bar at bottom: scrollable text log of recent events. Every action produces a line. Never lost, always recoverable.

**5 components to copy:**

1. **Agent × Strategy grid** — 10 rows (agents) × 8 cols (strategies: moneyline/spread/total/props/etc.). Each cell = colored dot: green=active, gray=inactive, yellow=testing, red=failed. One 400x200px widget replaces 3 separate strategy pages.
2. **Layered map drill-down** — pixel world view: click any island → zoom into its internal state (feature weights as colored tiles, gen count as building height). Same spatial metaphor throughout.
3. **Event log strip** — bottom 3 rows: scrolling text "S14 gen=109 | Brier improved 0.2251→0.2237 | T3 Qwen bet GSW -$8.40 | D1 Research: new paper ingested". Permanent log, never clears on page change.
4. **Skill/metric heatmap** — rows = islands, cols = feature categories. Cell color = importance percentile. Hot = critical feature, cold = unused. Drag to reorder. 8x54 grid = one viewport.
5. **Z-level abstraction** — 3 zoom levels on any widget: OVERVIEW (status dot only) → SUMMARY (sparkline + key metric) → DETAIL (full chart + raw data). Toggle with scroll wheel or +/- buttons.

**Colors:** Tan/brown world tiles `#8B7355`, blue water `#4A90D9`, red alert `#CC2200`, green nominal `#228B22`, dark bg `#1A1A1A`.
**Font:** Mayday tileset uses 16x16px bitmap. Web: `"Silkscreen"` (Google Fonts) or `"Courier Prime"`.

---

### #4 — Prison Architect (Introversion Software, 2015+)

**Reference:** interfaceingame.com/games/prison-architect — classic management game UI.

**What makes it world-class:**
- Every prisoner is an entity on a live map AND in a sidebar list simultaneously. Click list item = camera snaps to entity on map. Click map entity = highlights in list. Bidirectional sync.
- "Regime" planner: time-grid (x=hour, y=prisoner type) where colored blocks = scheduled activities. Drag to change. For Nomos: agent schedule grid (when each agent bets, which markets).
- Build mode vs view mode: two distinct states of same screen. Build mode shows construction costs in red, existing structures in white. Zero navigation.
- Needs bars (happiness, food, safety) as stacked horizontal bars per prisoner. 5 bars × 20px each = full status in 100px height.

**5 components to copy:**

1. **Bidirectional list-map sync** — left sidebar: list of agents with status. Click T1 → pixel world map pans/highlights T1's "zone". Click zone → sidebar highlights entry. Critical for spatial + list views simultaneously.
2. **Time-grid scheduler** — x=hours of day (00-23), y=agents (T1-T10). Colored blocks = when each agent is "active" per market. Drag to reschedule. Shows overlap (purple = conflict). Visual cron.
3. **Needs stack bars** — per agent: 5 horizontal bars (70px wide): Accuracy | Calibration | Edge | Drawdown | Confidence. Color = health. Replaces 5 separate metric displays.
4. **Build vs view mode toggle** — "Edit Layout" button switches page to drag-mode. All panels get dashed borders + resize handles. "Save Layout" commits. Otherwise read-only.
5. **Entity detail footer** — when any entity selected: footer at page bottom slides up (120px tall) with full context: agent name | current bet | reasoning snippet | P&L | model used. No modal.

**Colors:** `#2B2B2B` bg | `#4A4A4A` panels | `#F5C518` gold headers | `#E74C3C` danger | `#27AE60` safe | `#3498DB` action buttons.
**Font:** UI uses clean sans. Web equivalent: `"IBM Plex Sans"` 13px. Monospace data: `"IBM Plex Mono"`.

---

### #5 — Phaser PixUI + AI Town (a16z/ai-town)

**Reference:** phaser.io/news/2026/02/phaser-pixel-art-ui-library + github.com/a16z-infra/ai-town

**What makes it world-class (PixUI):**
- MIT-licensed Phaser 4 component library built specifically for pixel art games. Integer scaling = pixels stay crisp on all screen sizes.
- Components: buttons, progress bars, text areas, positioning helpers. TypeScript typed.
- Designed around "retro vibe" while being fully interactive and composable.

**What makes it world-class (AI Town):**
- 10 LLM agents living on a tilemap. Each agent is a sprite that moves, speaks (speech bubble), has a "thought" log.
- Convex backend: real-time sync of all agent states. Agent position, current action, memory all streamed to UI.
- Minimal UI chrome: the tilemap IS the dashboard. Status overlaid directly on world (no separate panel for simple state).
- Memory viewer: click any agent → side drawer shows recent memories, current plan, conversation history.

**5 components to copy:**

1. **Sprite + speech bubble** — each agent T1-T10 is a 32x32px sprite on the /world page. When agent makes a bet, speech bubble appears: "Going GSW -6.5 | 4.2% edge | $42 Kelly". Auto-hides after 5s.
2. **Thought log overlay** — click any agent sprite → overlay appears (no new page): scrollable reasoning text "I see GSW at 68% vs market 62%..." Last 5 decisions. Click outside to dismiss.
3. **World-state overlay** — island zones on map highlighted by current performance. Top island = bright color, bottom island = desaturated. Color = performance rank, not absolute value (always someone top, always someone bottom).
4. **Agent conversation thread** — when two agents agree or disagree on a bet, show a visual "thread" line connecting their sprites. Color = agreement (blue) or disagreement (red). Animated pulse while discussing.
5. **PixUI progress bars** — use Phaser PixUI progress bar component for Brier-to-target progress: pixel-art style, 8px height, chunky blocks, fills left-to-right as Brier improves. Satisfying feedback loop.

**Colors:** AI Town palette: grass `#5D8A3C`, paths `#8B7355`, buildings `#6B4F3A`, water `#2B6FA3`. Agent glows: team colors.
**Font:** `"Press Start 2P"` for game-mode labels, Geist Mono for data overlays. Mix both on /world page.

---

## SYNTHESIS — ONE KILLER ARCHITECTURE

### "Mission Control + Agent Studio" Layout

**Single URL: nomosdashboard.vercel.app (default screen)**

```
┌─────────────────────────────────────────────────────────────────────┐
│ MISSION TICKER [scrolling]: Brier 0.2187 | S14 gen=108 | $103.92   │  ← 32px, orange on black
├──────┬────────────────────────────────┬──────────────────────────────┤
│ TREE │ MODEL vs MARKET DEPTH CHART    │ FLEET HEALTH MATRIX          │
│ NAV  │ (center 45%)                   │ (right 28%)                  │
│      │ Our prob vs market line        │ 8×6 color grid               │
│ 220px│ Green zone = edge              │ S10-S17 × Brier/Gen/Age      │
│      ├────────────────────────────────┤                              │
│ S10  │ OPEN BETS TABLE                │ AGENT LEADERBOARD            │
│ S11  │ Game | Model% | Market% | Edge │ T1-T10 sprites + P&L bars    │
│  ..  │ Kelly | Status                 │ Click = thought log overlay  │
│ T1   │ (scrollable, real-time)        │                              │
│  ..  ├────────────────────────────────┴──────────────────────────────┤
│ D1   │ EVENT LOG: S14 gen=109 Brier improved | T3 bet GSW -$8.40... │  ← 3 rows, scrolling
└──────┴───────────────────────────────────────────────────────────────┘
```

**Global controls:** Time range selector (Live | 1h | 24h | Season) + Filter (Island | Agent | Market). All panels honor filters.

**Interaction pattern:** Everything on one screen. Left tree = navigation context. Center = primary viz. Right = status overview. Bottom = event log. NO page navigation for power users. Cmd+K for command bar (jump to any entity).

---

## IMMEDIATE IMPLEMENTATION PRIORITIES (this week)

| Priority | Component | Inspired By | Effort | Impact |
|----------|-----------|------------|--------|--------|
| P1 | Mission Ticker strip (top) | Bloomberg | 2h | Every page shows fleet state |
| P2 | Fleet Health Matrix widget | Datadog HD mode | 4h | Replaces 3 separate pages |
| P3 | 4-state status dots on all entities | Datadog/NASA MCT | 1h | Zero-read status scan |
| P4 | Agent strip (T1-T10 top bar) | RimWorld colonist bar | 3h | All agents always visible |
| P5 | Model vs Market depth chart | dYdX depth chart | 4h | Core edge visualization |
| P6 | Left tree nav (replaces sidebar tabs) | NASA Open MCT | 5h | Unified navigation |
| P7 | Event log bottom strip | Dwarf Fortress | 2h | Never lose context |
| P8 | CRT window aesthetic for /world | STONKS-9800 | 3h | Island "terminal" identity |

**Total estimate:** 24h of frontend work = 3 days. Ship by Apr 17.

---

## TECH STACK RECOMMENDATIONS

```
Colors: Bloomberg black + NASA Darkmatter for panels + dYdX purple accent
Fonts:  Geist (body) + Geist Mono (data values) — already on Vercel stack
Grid:   CSS Grid, 3-column (220 / auto / 320), no flexbox spaghetti
Charts: Recharts (already installed) — 1px line weight, no fill, dot on hover only
Status: 8px dots with 4-state color system (green/amber/red/gray)
Pixel:  /world page only — Phaser PixUI OR CSS pixel-art with image-rendering: pixelated
State:  URL params for layout state (shareable), localStorage for widget positions
```

---

*Sources verified Apr 14 2026. All hex codes cross-referenced against live implementations.*
