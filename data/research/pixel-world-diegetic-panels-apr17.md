# Diegetic Data Panels for Pixel-Art Multi-Agent Trading Floors
**Date**: 2026-04-17 | **Author**: nomos-scout | **Type**: UX/Viz Research Proposal
**Target file**: `hf-pixel-world/index.html` (PixiJS canvas + DOM overlay)
**Brier-impact**: indirect — makes fake/stale data visible to operators, accelerates debug cycles
**Effort**: M (3-5 days for panel catalog v1, 7-10 days for full agent-walk state machine)

---

## TOP 5 SOTA REFS

### 1. pablodelucca/pixel-agents (6.7k stars, active Apr 2026)
**URL**: https://github.com/pablodelucca/pixel-agents
**What it is**: VS Code extension that watches Claude Code JSONL transcripts and renders each agent as a pixel sprite in a canvas office. The canonical "agent-as-pixel-character" reference.
**What to steal**:
- Character state machine: `idle → walk → type/read` maps directly to `scan → propose → decide → bet → resolve`
- Debug View toggle shows per-agent diagnostics inline: JSONL file status, lines parsed, last data timestamp. This is the seed of "NO SIGNAL" UX — when a field is stale the panel dims.
- Canvas + BFS pathfinding already battle-tested. TILE=16, CHAR=16×24, world=320×176.
- Gear icon opens per-panel settings — steal for panel mode switching (live/frozen/fake-detect).

### 2. Stanford Generative Agents / Smallville (Park et al., UIST 2023 — still best public reference)
**URL**: https://github.com/joonspk-research/generative_agents
**What it is**: 25 LLM agents in a 2D tile world. Agents have memory streams, current-action labels, and a web dashboard showing all prompts + memory accesses per agent per tick.
**What to steal**:
- Hierarchical world labels: root → area (Market Room, Council Chamber) → object (Ticker Board, Strategy Terminal). Our world should mirror this — zones, not free space.
- The dashboard-as-separate-page pattern is exactly what we want to *eliminate*. Smallville's insight was that all dashboard content should be inspectable *in world* by clicking an agent. Translate: click on a panel sprite to expand it, not a sidebar route.
- Per-agent "current action" label always visible above sprite. Steal verbatim.

### 3. AgentLens — Visual Analysis for Agent Behaviors in LLM-based Autonomous Systems (arXiv 2402.08995, IEEE TVCG 2025)
**URL**: https://arxiv.org/abs/2402.08995
**What it is**: Research system classifying every LLM action as Perceive / Think / Act, then building a hierarchical event stack with causal annotations per agent per timestep.
**What to steal**:
- The Perceive/Think/Act trichotomy maps cleanly onto our 5-stage pipeline: Perceive = `scan odds + game context`, Think = `propose + decide`, Act = `bet + resolve`. Use these 3 icons as the agent "aura" color: teal (perceive), amber (think), green (act).
- "Drill-down reveals prompts, responses, and memory accesses" — implement as click-to-expand on agent sprite, not sidebar.
- Hierarchical temporal visualization: panels stacked vertically in each zone, time flowing left-to-right on the Resolve Wall (Panel P20).

### 4. Factorio Display Panel (Factorio 2.0 FFF-419)
**URL**: https://www.factorio.com/blog/post/fff-419
**What it is**: In-game circuit-network entity that displays configurable icons + text based on live signal conditions. Shows "READY / WARN / ERROR" states as pixel glyphs on a CRT-style curved screen.
**What to steal**:
- Condition-evaluated message cascade: "show first message whose condition passes, else show default". Apply to every panel: if `data_age > 300s` show STALE glyph, if `value === null` show NO_SIGNAL glyph, else show live value.
- CRT-curved face aesthetic (achieved in CSS via `border-radius` + scanline overlay, already present in our `#scanlines` div).
- Rotation-stable design: screen content never rotates even when the base sprite does. For us: panel content orientation is always reader-facing regardless of agent facing direction.

### 5. STONKS-9800: Stock Market Simulator (Steam / GameMaker, modding via Catspeak)
**URL**: https://stonks.jp/mod + https://store.steampowered.com/app/1765680
**What it is**: Pixel-art 1980s Japanese stock market game. UI is entirely text windows and simple candlestick charts rendered in pixel glyphs. Investor panels auto-refresh, company research tree is clickable.
**What to steal**:
- Every data source is *a named machine* in the world: "REUTERS TERMINAL", "COMPANY RESEARCH DESK", "ANALYST BOOTH". We should give each panel a diegetic name plate.
- Candlestick chart in 8×8 pixel budget — use for bankroll sparkline inside each agent's nameplate.
- "Hover over company name to highlight graph line" — apply to agent name highlighting all panels that agent is currently "reading".

---

## PROPOSED PANEL CATALOG

### Zone A — Market Data (left wall, 5 panels)

**P01: ODDS BOARD**
- Data source: `data/nba-agent/live-odds.json`, `odds-latest.json`
- Shows: Today's games, home/away moneyline, implied prob, market movement arrows
- Glyph: tall arcade marquee with scrolling game rows, green/red arrows for line movement
- Size: 4×6 tiles. Agents visit when in `scan` stage.
- Fake-detect: if `odds_fetched_at` > 10 min ago, replace odds with "----" and show amber STALE banner

**P02: MARKET SPREAD TICKER**
- Data source: `/api/nba/odds` + `data/nba-agent/market-data.json`
- Shows: Opening line, current line, delta, sharp money indicator
- Glyph: horizontal CRT ticker strip, numbers scroll right-to-left
- Size: 8×2 tiles (horizontal band). Mounted above P01.
- Fake-detect: static text "NO FEED" with scanline glitch animation if endpoint 404

**P03: EDGE MATRIX**
- Data source: model predicted prob vs implied market prob, per game
- Shows: 4×N grid — game / model_edge / kelly_fraction / recommended_stake
- Glyph: spreadsheet with colored cells (green = +edge, red = negative edge, grey = no bet)
- Size: 5×5 tiles. Agents in `propose` stage stand here.
- Fake-detect: if all edges identical or edge = 0.000 on all rows, red border + "SUSPECT" glyph

**P04: LIVE ODDS API STATUS**
- Data source: `data/nba-agent/tf-llm-health.json`, API health from `/api/status`
- Shows: Each LLM provider (Cerebras, Google, Mistral, OpenRouter, selfhost) as a status LED
- Glyph: vertical rack of server LEDs — green blinking = live, amber = slow, red = down
- Size: 2×5 tiles. Mounted right of P01. No agent stands here — it's ambient infrastructure.
- Fake-detect: if provider last_response_at > 60s, LED turns amber and blinks faster

**P05: BANKROLL MASTER**
- Data source: current bankroll from TF `/api/status`
- Shows: Total pool, daily P&L, season P&L, $1M goal progress bar (pixel bar chart)
- Glyph: large dollar display (like arcade high score board), bar fills green/empties red
- Size: 4×4 tiles. Agents visit after `resolve` stage.
- Fake-detect: if bankroll = exactly $100,000.00 (never moved), flash "SIMULATION?" warning

---

### Zone B — Model Intelligence (center-left, 4 panels)

**P06: BRIER LEADERBOARD**
- Data source: `data/monitoring/metrics.csv`, evolution island API `/api/status`
- Shows: 13 NBA islands ranked by Brier, current gen, trend sparkline (8-px height)
- Glyph: retro high-score list (S17: 0.22085 ★), gold/silver/bronze pixel crowns for top 3
- Size: 5×6 tiles. Agents in `propose` stage reference this to weight their picks.
- Fake-detect: if all Brier values identical or last_updated > 1h, asterisk + "CACHED" tag

**P07: FEATURE ENGINE TERMINAL**
- Data source: features/engine.py version hash from `data/.last-engine-hash`
- Shows: engine version, cat count (65), feature count (6434), last mutation timestamp, parity status
- Glyph: terminal window with green-on-black text, blinking cursor when engine is running
- Size: 4×4 tiles.
- Fake-detect: if engine hash mismatches between island and VM copy, red "PARITY BROKEN" glyph

**P08: EVOLUTION PROGRESS WALL**
- Data source: all 13 island `/api/status` endpoints
- Shows: Each island as a column. Gen number as height (pixel bar). Color = algorithm type.
- Glyph: bar-chart cityscape — taller bars = more generations. Brier improvement as green halo.
- Size: 10×4 tiles (wide). Mounted on back wall of center zone.
- Fake-detect: if gen count has not changed in >2h, bar turns grey with "STALLED" label

**P09: CALIBRATION DIAL**
- Data source: `data/monitoring/drift-calibration.json`
- Shows: Expected calibration error (ECE), reliability curve rendered as 8-step histogram
- Glyph: circular dial with needle (like speedometer). Needle swings between "SHARP" and "OVERFIT".
- Size: 3×3 tiles.
- Fake-detect: if ECE = 0.000 exactly, needle pins to left + "UNCALIBRATED" warning

---

### Zone C — Agent Internal State (center, per-agent desks, 4 panels)

**P10: AGENT DESK TERMINAL** (one instance per agent — 16 total, arranged in 4×4 grid)
- Data source: TF `/api/leaderboard`, `/api/day-decisions`
- Shows: Agent ID, LLM model, today's bets (list), win rate, bankroll, last reasoning excerpt (20 chars)
- Glyph: mini CRT monitor sitting on a pixel desk. Agent sprite stands in front when in `decide` stage.
- Size: 3×3 tiles per desk. 16 desks tile-packed into center zone.
- Fake-detect: if reasoning_text = "" or "None" or repeats verbatim from prior day, monitor shows static

**P11: SYSTEM PROMPT BOARD**
- Data source: TF agent config, COLLECTIVE_MISSION preamble text
- Shows: First 200 chars of active system prompt, scrolling. Highlights AXELROD_CANON keywords.
- Glyph: tall bulletin board with pinned paper sprites. Keywords glow amber.
- Size: 3×5 tiles. Fixed reference — agents never "stand" here but glance at it.
- Fake-detect: if system_prompt is empty or default placeholder, board is blank with big "NO PROMPT" pin

**P12: DECISION LOG FEED**
- Data source: TF `/api/logs`, bet decisions from each agent
- Shows: Real-time scroll of agent decisions — "qwen-quant: BET $240 LAL -5.5, edge=0.031"
- Glyph: console terminal with amber scrolling text, newest at bottom
- Size: 4×5 tiles. Agents pass by this during `resolve`.
- Fake-detect: if 0 decisions logged today, feed shows "NO BETS TODAY" in red with timestamp

**P13: REASONING WINDOW**
- Data source: last LLM response per agent (from TF logs)
- Shows: Click-to-expand — full LLM reasoning text for selected agent, token count, latency
- Glyph: large monitor that activates on agent click. Default shows condensed summary.
- Size: 6×5 tiles (expandable). Mounted on right wall, center zone.
- Fake-detect: if reasoning is identical across 3+ agents (groupthink), border turns red + DMAD warning

---

### Zone D — Cooperation / Council (right side, 3 panels)

**P14: AXELROD PACT BOARD**
- Data source: TF `/api/status` → `cooperation_pacts_count`, `reputation` per agent
- Shows: Agent pairs with active pacts as colored lines between sprites. Reputation bars.
- Glyph: relationship graph overlaid on miniature agent grid (16 dots + lines)
- Size: 5×5 tiles. Council chamber zone.
- Fake-detect: if pact_count = 0 after day 5, board shows "ZERO COOPERATION" warning

**P15: MORNING COUNCIL TRANSCRIPT**
- Data source: TF council log (qwen-235B moderator decisions)
- Shows: Council agenda, votes, final directive for the day
- Glyph: round table with chairs (pixel sprites), transcript scroll on wall screen
- Size: 5×4 tiles. Agents visit before `propose` stage (council phase).
- Fake-detect: if council produced no output or skipped, "COUNCIL ADJOURNED" card on table

**P16: ROGUE TRIGGER ALERT BOARD**
- Data source: TF drawdown monitoring (<$25 threshold, peer >$250K)
- Shows: Each agent's drawdown status. When rogue trigger fires, alert board lights up red.
- Glyph: fire-alarm style panel — normal state = all green, triggered = red flashing with agent name
- Size: 3×3 tiles. Mounted near exit of council zone.
- Fake-detect: if rogue logic never fires across 100 days, board dims with "TRIGGER INACTIVE" note

---

### Zone E — History / Resolve Wall (far right, 3 panels)

**P17: SEASON P&L CHART**
- Data source: TF leaderboard, historical bankroll snapshots
- Shows: Each agent as a colored line over 1257-game season. Current day highlighted.
- Glyph: full-width line chart, retro grid, each agent color-coded. $1M target line dashed gold.
- Size: 8×5 tiles. Mounted as large mural on back wall.
- Fake-detect: if all lines flat (no trades), mural shows "SEASON NOT STARTED" grayed out

**P18: POST-MORTEM TICKER**
- Data source: TF post-mortem log (incorrect bets + reasoning analysis)
- Shows: Yesterday's worst bet, reason it failed, which agent, probability vs outcome
- Glyph: "YESTERDAY'S L" retro arcade sign with loss amount blinking
- Size: 4×3 tiles.
- Fake-detect: if no post-mortems (0 bets), shows "NO TRADES, NO LESSONS" in grey

**P19: POLITICAL SIGNAL FEED**
- Data source: `data/political-fleet-status.json`, political island Brier scores
- Shows: Top 5 political prediction categories, implied ETF signals, P7 best model
- Glyph: news ticker with political icons (Capitol, chart, flag glyph)
- Size: 6×2 tiles (horizontal band). Bottom of far right wall.
- Fake-detect: if political data older than 24h, entire strip dims with "POL FEED STALE"

**P20: RESOLVE WALL** (outcome confirmation)
- Data source: game results from `predict_today.py`, Brier per game
- Shows: Today's resolved games: prediction vs outcome, individual Brier score, correct/wrong icon
- Glyph: scoreboard grid, correct = green checkmark pixel, wrong = red X pixel
- Size: 8×4 tiles. Agents arrive here at end of day cycle (`resolve` stage).
- Fake-detect: if results not yet available, board shows "AWAITING OUTCOMES" with spinning gear

---

## LAYOUT MAP

ASCII sketch of pixel world zones (each cell = ~4×4 tiles):

```
┌─────────────────────────────────────────────────────────────┐
│  BLOOMBERG TICKER (horizontal band, top)                     │
├──────────────┬────────────────────────┬──────────────────────┤
│  ZONE A      │  ZONE B                │  ZONE D              │
│  MARKET DATA │  MODEL INTELLIGENCE    │  COOPERATION         │
│              │                        │                      │
│  [P01]       │  [P06] BRIER BOARD     │  [P14] PACT BOARD    │
│  ODDS BOARD  │                        │                      │
│  [P02]ticker │  [P07] ENGINE TERM     │  [P15] COUNCIL TABLE │
│              │                        │                      │
│  [P03] EDGE  │  [P08] EVO WALL ──────►│  [P16] ROGUE ALERT   │
│  MATRIX      │  (spans B+D back wall) │                      │
│  [P04] API   │                        │                      │
│  STATUS      │  [P09] CALIB DIAL      │                      │
│  [P05] BANKR │                        │                      │
├──────────────┴────────────────────────┴──────────────────────┤
│  ZONE C — AGENT DESKS (center, 4×4 grid of 16 terminals)    │
│                                                              │
│  [P10×16] ████████████████  [P11] SYSTEM PROMPT BOARD       │
│           ████████████████                                   │
│           ████████████████  [P12] DECISION LOG FEED         │
│           ████████████████                                   │
│                             [P13] REASONING WINDOW          │
├──────────────────────────────────────────────────────────────┤
│  ZONE E — HISTORY / RESOLVE WALL (bottom band)              │
│  [P17] SEASON P&L MURAL ─────────────────────────────────── │
│  [P18] POST-MORTEM      [P19] POLITICAL FEED  [P20] RESULTS │
└──────────────────────────────────────────────────────────────┘
                         [RIGHT SIDEBAR — shrinks to 240px]
                         Fleet status / quick KPIs / trade list
```

Agent walk paths by stage:
- `scan`: Zone A (P01, P02, P03) — agent faces odds board
- `propose`: Zone B (P06, P07) — agent faces brier/engine panels
- `council`: Zone D (P14, P15) — agents cluster around council table
- `decide`: Zone C (P10 own desk) — agent sits at personal terminal
- `bet`: Zone C (P12) — agent walks past decision log, "files" bet
- `resolve`: Zone E (P20) — agent faces resolve wall to see outcome

---

## IMPLEMENTATION NOTES

### Architecture: DOM-overlay-first, canvas for sprites only

The existing index.html already uses the correct split:
- `<canvas>` handles agent sprites + tile backgrounds via PixiJS (WebGL, hardware-accelerated)
- `<div id="sidebar">` is DOM
- Scanlines, vignette, minimap, hover card are absolute-positioned DOM divs

**Extend this pattern — do not move panels into canvas.** Reason: text-heavy panels (odds grids, reasoning windows, log feeds) are faster to render, easier to update, and more accessible as DOM divs with `position:absolute` overlaid on the canvas. Canvas-native text in PixiJS requires manual string wrapping, font loading, and re-render on every data change.

Recommended approach per panel type:
- Panel frame + border + header glyph: CSS `::before` / `::after` pseudo-elements with `border: 1px solid` in zone-color
- Data content: plain DOM — `<table>`, `<pre>`, `<span>` with `color: var(--ok|warn|err)`
- Animations (blinking LEDs, scrolling tickers): CSS `@keyframes` on individual spans
- "NO SIGNAL" glitch: CSS `@keyframes glitch` that shifts `transform: translateX(2px)` at random intervals
- Panel position in world: `position:absolute; left: tileX*TILE_PX + STAGE_OFFSET_X; top: tileY*TILE_PX + STAGE_OFFSET_Y`

### Data binding

Use a single `WorldState` object polled every 10s from `/api/status` and `/api/leaderboard`. Each panel subscribes to a slice:

```javascript
const WorldState = {
  odds: null,            // P01, P02, P03
  modelBrier: null,      // P06, P08
  engineHash: null,      // P07
  agents: [],            // P10×16, P12, P13
  council: null,         // P15
  pacts: null,           // P14
  seasonPnL: [],         // P17
  results: []            // P20
};

function refreshPanel(panelId, data) {
  if (!data || isStale(data)) { showNoSignal(panelId); return; }
  renderPanel(panelId, data);
}
```

Poll budget: 10s interval for live data (odds, agent bankrolls), 60s for slow data (Brier scores, season P&L). Never block the PixiJS game loop — all fetches are `async`, updates applied via `requestAnimationFrame`.

### Animation budget

PixiJS runs at 60fps for sprites. DOM panels should NOT animate at 60fps — use CSS transitions (16ms) only for:
- LED color transitions (300ms ease)
- Bankroll number countup (500ms)
- Toast notifications (300ms slide-in, 400ms fade-out after 4.5s — already implemented)

Glitch animations for NO_SIGNAL panels: 150ms interval, `translate(-2px)` / `translate(2px)` alternating, CSS only.

### PixiJS panel frame sprites

Each zone should have a colored frame around its DOM panels, rendered as a PixiJS `Graphics` object (4 `drawRect` calls per panel, drawn once at init). Zone colors:
- Zone A (Market): `#ffa500` (Bloomberg amber)
- Zone B (Model): `#00d9a7` (our `--ok` green)
- Zone C (Agent Desks): `#bd93f9` (purple, per-agent)
- Zone D (Cooperation): `#ff79c6` (pink, social)
- Zone E (History): `#8be9fd` (blue, cold/past)

---

## FAKE-DATA DETECTION UX

### Detection rules (applied per panel on every refresh)

| Condition | Visual response |
|-----------|----------------|
| `data === null` | Full panel replaced by "NO SIGNAL" screen: static grey noise `background-image: url(noise.png)`, white "NO SIGNAL" text centered |
| `data_age > threshold` | Panel header turns amber, value fields replaced by "----", STALE badge appears top-right |
| All numeric values identical (e.g., all edges = 0) | Red border + "SUSPECT DATA" watermark diagonal across panel |
| Value unchanged for N consecutive polls | Pulse animation stops, value color fades to `var(--ink-3)` with "FROZEN" indicator |
| Endpoint 404 / network error | Panel frame turns red, inner text shows error code + last successful timestamp |
| Value is placeholder string ("None", "N/A", "undefined") | Value replaced by `???` in red, panel logs to console with source field name |

### "NO SIGNAL" animation (CSS, reuse existing scanlines pattern)

```css
.panel-no-signal {
  background: repeating-linear-gradient(
    0deg, #111 0px, #111 2px, #1a1a1a 2px, #1a1a1a 4px
  );
  animation: static-noise 0.1s steps(2) infinite;
}
@keyframes static-noise {
  0%   { background-position: 0 0; }
  50%  { background-position: 0 3px; }
  100% { background-position: 0 -3px; }
}
.panel-no-signal::after {
  content: "NO SIGNAL";
  position: absolute; top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  color: white; font-size: 11px; letter-spacing: 0.2em;
  text-shadow: 0 0 8px rgba(255,255,255,0.6);
}
```

### Threshold table (per panel)

| Panel | Stale threshold | Suspect condition |
|-------|----------------|-------------------|
| P01 Odds Board | 10 min | Any implied prob outside [0.01, 0.99] |
| P06 Brier Board | 60 min | All Brier values within 0.001 of each other |
| P10 Agent Desk | 5 min | reasoning_text length < 20 chars |
| P12 Decision Log | 1 day | 0 bets logged for active game day |
| P14 Pact Board | 6 hours | pact_count = 0 after day 5 |
| P20 Resolve Wall | — | results_count = 0 after 22:00 UTC on game day |

---

## OPEN QUESTIONS FOR nomos-lab

1. Do agent sprites need their own PixiJS `Container` per desk (P10), or can we use the existing agent map and add a "standing at panel" flag?
2. Is the TF `/api/day-decisions` endpoint returning per-agent reasoning text, or only bet amounts? If only amounts, P13 Reasoning Window needs a new endpoint.
3. Panel interactivity: click-to-expand on panel frame vs click-on-agent sprite to expand their desk panel — which UX model?
4. 16 agent desks (P10) at 3×3 tiles each = 144 tile-units for Zone C alone. At TILE=20px, that is 2880px × 2880px. Scrollable world or zoom-out mode needed — recommend viewport scroll with minimap already in index.html.

---

## PRIORITY ORDER (for nomos-lab implementation)

**Day 1** — P01 (Odds Board) + P04 (API Status LEDs) + NO_SIGNAL CSS
**Day 2** — P06 (Brier Board) + P10 (Agent Desks, single instance first, then ×16)
**Day 3** — P12 (Decision Log) + P14 (Pact Board) + P20 (Resolve Wall)
**Day 4** — P02/P03/P05 (remaining market zone) + P07/P08 (model zone)
**Day 5** — P15/P16 (council zone) + P17/P18/P19 (history wall) + agent walk state machine

Minimum viable "diegetic floor" = P01 + P04 + P06 + P10 + P12 + P20. Six panels, all with fake-detect. Everything else is progressive enhancement.
