# DESIGN.md - Nomos42

> Bloomberg Terminal meets Quantitative Trading Floor. Dark, data-dense, professional.

## 1. Visual Theme & Atmosphere

**Mood:** High-frequency trading terminal. Information-dense, zero decoration. Every pixel earns its place.
**Density:** Ultra-high. Multiple data panels visible simultaneously. No whitespace padding beyond 8px.
**Philosophy:** "If Bloomberg had a dark mode designed by a quant." Respect the user's expertise — no tooltips on obvious metrics, no confirmation dialogs on read operations.
**Motion:** Minimal. Data updates in-place with 150ms fade transitions. No page transitions, no skeleton loaders — show stale data with a staleness indicator until fresh data arrives.

## 2. Color Palette & Roles

| Name | Hex | Role |
|------|-----|------|
| Background | `#0a0a0f` | Main surface — near-black with blue undertone |
| Surface | `#12121a` | Cards, panels, elevated containers |
| Surface-2 | `#1a1a2e` | Nested panels, table rows (alternate) |
| Border | `#2a2a3e` | Panel borders, dividers — subtle, not prominent |
| Text Primary | `#e4e4ef` | Main text, numbers, labels |
| Text Secondary | `#8888a0` | Descriptions, timestamps, secondary labels |
| Green / Profit | `#00d26a` | Positive PnL, wins, improvements, healthy status |
| Red / Loss | `#ff4757` | Negative PnL, losses, regressions, errors |
| Amber / Warning | `#ffa502` | Caution states, stale data, approaching limits |
| Blue / Accent | `#3b82f6` | Links, active tabs, selected states, primary actions |
| Purple / AI | `#8b5cf6` | AI-generated content, model outputs, predictions |
| Cyan / Live | `#06b6d4` | Live data, real-time indicators, streaming |

### Signal Colors (for charts and heatmaps)
| Range | Color | Meaning |
|-------|-------|---------|
| 0.0 - 0.20 | `#00d26a` | Excellent (Brier, drawdown) |
| 0.20 - 0.23 | `#ffa502` | Acceptable |
| 0.23+ | `#ff4757` | Poor |
| ROI > 5% | `#00d26a` | Target met |
| ROI < 0% | `#ff4757` | Losing money |

## 3. Typography Rules

| Element | Font | Weight | Size | Line Height |
|---------|------|--------|------|-------------|
| Page Title | JetBrains Mono | 700 | 20px | 1.2 |
| Section Header | JetBrains Mono | 600 | 16px | 1.3 |
| Card Title | Inter | 600 | 14px | 1.4 |
| Body / Data | JetBrains Mono | 400 | 13px | 1.5 |
| Table Numbers | JetBrains Mono | 500 | 13px | 1.4 |
| Small Label | Inter | 500 | 11px | 1.3 |
| Badge / Tag | Inter | 600 | 10px | 1.0 |

**Rules:**
- ALL numbers use `JetBrains Mono` (monospace alignment in tables)
- Tabular numbers (`font-variant-numeric: tabular-nums`) on all numeric displays
- No font size below 10px
- Fallback stack: `'JetBrains Mono', 'Fira Code', 'SF Mono', monospace`

## 4. Component Stylings

### Cards (Data Panels)
```
background: var(--surface);
border: 1px solid var(--border);
border-radius: 8px;
padding: 12px 16px;
```
- No box-shadow (flat design, depth via border only)
- Header: flex row with title left, status badge right
- Hover: `border-color: var(--blue)` with 150ms transition

### Buttons
| Variant | Background | Border | Text |
|---------|-----------|--------|------|
| Primary | `var(--blue)` | none | white |
| Ghost | transparent | 1px `var(--border)` | `var(--text-primary)` |
| Danger | transparent | 1px `var(--red)` | `var(--red)` |
| Success | transparent | 1px `var(--green)` | `var(--green)` |

- Height: 32px (compact), 36px (default)
- Border-radius: 6px
- No uppercase transforms

### Tables
- Header: `var(--surface-2)`, `font-weight: 600`, sticky
- Rows: alternating `var(--background)` / `var(--surface)`
- Numbers right-aligned, text left-aligned
- Positive values: `var(--green)`, negative: `var(--red)`
- Hover row: `background: var(--surface-2)`

### Status Badges
| Status | Background | Text |
|--------|-----------|------|
| LIVE | `#00d26a20` | `var(--green)` |
| STALE | `#ffa50220` | `var(--amber)` |
| DOWN | `#ff475720` | `var(--red)` |
| BUILDING | `#3b82f620` | `var(--blue)` |

- Border-radius: 4px, padding: 2px 8px, font-size: 10px, uppercase

### Charts (Recharts)
- Grid: `stroke: var(--border)`, `strokeDasharray: "3 3"`
- Axis labels: `var(--text-secondary)`, 11px
- Tooltip: `background: var(--surface)`, `border: 1px solid var(--border)`
- Line colors: cycle through `[blue, green, purple, cyan, amber]`
- Area fills: 10% opacity of line color

## 5. Layout Principles

**Grid:** CSS Grid with `gap: 12px`
- Dashboard: 3-column on desktop, 2-column on tablet, 1-column on mobile
- Trading Floor: 2-column (leaderboard left, detail right)
- Evolution: 3x2 grid (one card per island)

**Spacing Scale:** `4px, 8px, 12px, 16px, 24px, 32px, 48px`
- Card padding: 12px-16px
- Section gap: 24px
- Page margin: 16px (desktop), 12px (mobile)

**Navigation:**
- Top bar: 48px height, fixed, `var(--surface)` background
- Tabs: inline, no dropdown menus
- Active tab: bottom border `2px solid var(--blue)`

## 6. Depth & Elevation

No shadows. Depth communicated via:
1. **Border contrast**: brighter border = more prominent
2. **Background lightness**: `background` < `surface` < `surface-2`
3. **Position**: fixed elements (nav, footer) use `var(--surface)` + bottom border

Exception: Tooltips and dropdowns get `box-shadow: 0 4px 12px rgba(0,0,0,0.5)`

## 7. Do's and Don'ts

### Do
- Show raw numbers — quants want precision, not "approximately 22%"
- Use sparklines inline with metrics for trend-at-a-glance
- Color-code ALL numeric values (green=good, red=bad, white=neutral)
- Show timestamps in UTC with relative time in tooltip
- Display staleness: "Updated 3m ago" with amber if >10m

### Don't
- Don't round Brier scores below 4 decimal places (0.2157 not 0.22)
- Don't use pie charts (ever)
- Don't add loading spinners — show stale data with indicator
- Don't use modals — use inline expansion or slide panels
- Don't add decorative icons — only functional indicators
- Don't use gradients on backgrounds
- Don't put important data below the fold

## 8. Responsive Behavior

| Breakpoint | Name | Columns | Nav |
|-----------|------|---------|-----|
| >= 1200px | Desktop | 3 | Top bar |
| 768-1199px | Tablet | 2 | Top bar (compact) |
| < 768px | Mobile | 1 | Bottom tabs |

- Tables: horizontal scroll on mobile, sticky first column
- Charts: full-width, min-height 200px
- Cards: stack vertically, maintain padding
- Touch targets: minimum 44px on mobile

## 9. Agent Prompt Guide

When generating UI for Nomos42:
- **Framework**: Next.js 15 + Tailwind CSS + Recharts
- **Theme**: Always dark mode. No light mode toggle.
- **Data format**: All API responses are JSON. Timestamps are ISO 8601 UTC.
- **Key metrics**: Brier score (lower=better), ROI% (higher=better), Sharpe ratio (>1.5=good), Max drawdown (<0.5=good)
- **Color rule**: If a number represents performance, color it green (good) or red (bad). Never leave performance numbers in default text color.
- **Number formatting**: Brier=4 decimals, ROI=1 decimal + %, PnL=$ with commas, Sharpe=3 decimals
- **Layout priority**: Leaderboard/ranking tables first, charts second, controls last
- **No skeletons**: Show `--` placeholder, never animated skeleton loaders
- **Terminal aesthetic**: This is a Bloomberg terminal for NBA quant trading. Every component should feel like it belongs in a trading floor, not a consumer app.
