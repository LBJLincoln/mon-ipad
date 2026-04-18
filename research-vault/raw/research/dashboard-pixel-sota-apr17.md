# SOTA Game-Like Dashboards + Pixel Agent Visualization — April 17, 2026

**Scout:** nomos-scout | **Date:** 2026-04-17 | **Sources scanned:** 18
**Scope:** Game-feel dashboards + pixel agent simulations for Nomos42 /world (21 islands + 16 TF agents + 9 depts)

---

## TOPIC 1: SOTA Game-Like Dashboards

### Finding D1 — pablodelucca/pixel-agents (VS Code Extension)
- **URL:** https://github.com/pablodelucca/pixel-agents
- **Stars:** 6.8k | **Last release:** v1.3.0 (2026-04-14) — **updated 3 days ago**
- **Tech:** TypeScript + VS Code Webview API + React 19 + Vite + Canvas 2D (esbuild)
- **What it does:** Each Claude Code agent becomes an animated pixel sprite in a 64x64 grid office. State maps to character animations (typing = writing, searching = reading, blocked = waiting). Speech bubbles, sound notifications, sub-agent spawning with linked characters.
- **What to steal for Nomos42:**
  - The **state→animation mapping** pattern: idle/running/blocked/done = distinct sprite frames. Apply to our 16 TF agents (idle=sleeping at desk, betting=running to board, winning=celebration, losing=head in hands).
  - The **64x64 expandable grid**: our pixel-world could grow as islands are added.
  - All office assets are **MIT open-source** (furniture, floors, walls) under `webview-ui/public/assets/`. No LimeZu license issues for commercial use — unlike Star-Office-UI.
  - **Sub-agent visualization with linked character spawning** — maps directly to our 9 dept councils spawning sub-tasks.
- **Brier/business impact:** Zero direct Brier impact. Dashboard quality drives subscriber conversion ($19/mo Nomos42Picks). High visibility value.
- **Effort:** Low-medium — the Canvas 2D + sprite sheet pattern is already used in our pixel-world; the asset library and state machine can be ported directly.
- **Standalone fork:** rolandal/pixel-agents-standalone (pure web app, no VS Code dependency) — better for our HF Space deployment.

---

### Finding D2 — GreenSheep01201/claw-empire
- **URL:** https://github.com/GreenSheep01201/claw-empire
- **Stars:** 1.1k | **Last update:** Active 2026 (v releases with Docker, stale-agent recovery)
- **Tech:** React 19 + Vite 7 + Tailwind CSS 4 + TypeScript 5.9 + **PixiJS 8** (frontend) + Express 5 + SQLite (backend)
- **What it does:** CEO-desk simulator orchestrating Claude Code, Codex CLI, Gemini CLI, OpenCode agents as a virtual company. Real-time KPI metrics, agent rankings, department status, Kanban drag-drop, pixel-art office with animated agents. WebSocket live updates.
- **What to steal for Nomos42:**
  - **PixiJS 8 + React 19 combo confirmed production-ready** for a project of this scale (1.1k stars, active maintenance). This validates our planned stack.
  - **Department-level KPI tiles** — real-time status for each dept (D1 Research → D9 Cross-repo) with agent ranking tables. Exact match to our 9 dept visualization need.
  - **WebSocket live updates pattern** — push island Brier updates from HF Space `/api/status` to dashboard without polling.
  - **Kanban for tasks** — could become a Research Proposals queue view showing proposal→lab→implemented pipeline.
- **Brier/business impact:** None direct. Enables proposal-to-implementation tracking (our 30% target rate).
- **Effort:** Medium — PixiJS 8 integration is the key lift; rest is React state management we already have.

---

### Finding D3 — harishkotra/agent-office
- **URL:** https://github.com/harishkotra/agent-office
- **Stars:** 68 | **Last commit:** 2026 (10 commits total, newly published)
- **Tech:** Phaser.js + React (TypeScript) + Colyseus (multiplayer sync) + SQLite + Node.js 18+
- **What it does:** Pixel office where agents autonomously hire new team members, walk to desks, execute sandboxed code, and do web search. Colyseus room for real-time multi-client sync. Drag-drop layout editor, task assignment interface.
- **What to steal for Nomos42:**
  - **Colyseus room for multi-client sync** — if we ever want multiple users watching the same /world live (subscriber dashboard use case: Nomos42Picks members watching live predictions come in).
  - **Autonomous agent hiring pattern** — when a new evolution island is promoted (S23+), it could "walk into the office" visually. Satisfying UX for the "living system" narrative.
  - **Sandboxed JS tool execution display** — analogous to showing live feature computation steps.
- **Brier/business impact:** Low direct. Conceptually strong for subscriber retention if /world feels alive.
- **Effort:** High (Colyseus adds real server-side complexity; Phaser full rewrite). Best mined for ideas, not direct port.

---

### Finding D4 — DBell-workshop/AgentFleet
- **URL:** https://github.com/DBell-workshop/AgentFleet
- **Stars:** 57 | **Last release:** v0.1.1 (2026-04-03)
- **Tech:** Python (65%) + TypeScript (32%) + Phaser 3 + multi-LLM (Gemini/Claude/GPT/DeepSeek/Qwen)
- **What it does:** Pixel-art RPG office with pre-built scene templates including **Quantitative Trading** scene specifically. Desktop pet cat companion (12 breeds, activity-reactive). Delegation system + operations dashboard.
- **What to steal for Nomos42:**
  - The **Quantitative Trading scene template** — this is explicitly built for quant contexts. Star count is low but the scene concept is directly applicable: trading desks mapped to agents, order flow visualized as sprites walking to a board.
  - **Activity-reactive pet companion** — a small pixel mascot in the corner of /world that reacts to fleet Brier (happy when improving, sad when regressing). Low effort, high personality.
  - **Per-agent LLM config pattern** — each desk can have a different model badge visible (T1=Qwen, T6=Mistral etc.), which matches our 16-agent architecture exactly.
- **Brier/business impact:** None direct. Strong narrative/UX for Nomos42Picks marketing.
- **Effort:** Low for the scene concept (extract ideas), medium if porting the trading scene template directly.
- **License note:** BSL 1.1 until 2030 then Apache 2.0. Can use for personal/internal; cannot resell. Acceptable for our use.

---

### Finding D5 — TradingView Lightweight Charts (for recharts replacement)
- **URL:** https://github.com/tradingview/lightweight-charts
- **Stars:** 9k+ | **Status:** Actively maintained 2026
- **Tech:** HTML5 Canvas, TypeScript, 45KB bundle, React wrappers available
- **Why it matters:** Recharts (our current lib) renders as SVG — freezes at 5000+ DOM nodes. Lightweight Charts renders via Canvas and handles millions of data points at 60fps. For our Brier timeline (1257 NBA games x 21 islands = 26k data points), SVG will thrash.
- **React wrapper:** `tradingview-tools/lightweight-charts-react` on npm — drop-in.
- **What to steal for Nomos42:**
  - Replace recharts `<LineChart>` on /evolution page (island Brier curves, gen-count x-axis) with LW Charts. Estimated visual improvement: smooth 60fps scrubbing vs current janky re-render.
  - Use for the fleet Brier comparison chart on /nba page — candlestick per generation showing best/worst/median across 21 islands.
  - OHLC/candlestick mode to show Brier range per week (open=Monday Brier, close=Friday Brier, high/low = extremes).
- **Brier impact:** Indirect — enables more granular Brier analysis UI that informs faster iteration decisions.
- **Effort:** Low — 1-day swap on /evolution charts.

---

### Finding D6 — Pixelact UI (component library)
- **URL:** https://www.pixelactui.com/
- **Status:** Active 2026, shadcn/ui based
- **Tech:** React component library with pixel-art aesthetic, built on shadcn/ui primitives
- **What it does:** Retro pixel-flavored UI components (buttons, cards, badges, progress bars) with authentic 2px border pixel style.
- **What to steal for Nomos42:**
  - **Pixel-bordered card components** for the /world diegetic panel overlays — currently our panels are plain divs; Pixelact cards would give the authentic "in-world screen" feel.
  - **Progress bar component** — island Brier progress toward 0.20 target, styled as a retro HP bar.
  - **Badge component** — trader status badge (ACTIVE / IDLE / ROGUE) with pixel-art border.
- **Design tokens (inferred from pixel aesthetic):** `border: 2px solid; box-shadow: 2px 2px 0px #000; font-family: "Press Start 2P", monospace` — the standard pixel-UI spec.
- **Effort:** Very low — drop-in shadcn components, MIT license.

---

### Finding D7 — XP.css / 98.css (retro OS CSS)
- **URL:** https://botoxparty.github.io/XP.css/ | https://jdan.github.io/98.css/
- **Stars:** XP.css ~6k, 98.css ~10k
- **Tech:** Pure CSS, no JS, framework-agnostic
- **What to steal:** The "Bloomberg terminal feels like a retro OS" aesthetic. Our `/floor` Trading Floor page could use XP.css window chrome (title bars, inset panels, system fonts) to make it feel like a Windows 95 trading terminal — deliberately retro, immediately recognizable, unique vs every other "dark mode dashboard."
- **Color palette:** `#000080` (window title bar), `#c0c0c0` (silver surface), `#ffffff` (active text), `#808080` (border shadow), `#008080` (teal accent for selected). These map to a Bloomberg-dark variant if you invert to: `#001020` bg, `#ff6600` accent, `#c0c0c0` text.
- **Effort:** Extremely low — 1 CSS import + semantic HTML. Best for the /floor "terminal mode" toggle.

---

## TOPIC 2: Pixel World / Agent Visualization

### Finding P1 — geezerrrr/agent-town
- **URL:** https://github.com/geezerrrr/agent-town
- **Stars:** 127 | **Last release:** v0.4.1 (2026-03-11)
- **Tech:** Next.js 16 + React 19 + TypeScript + **Phaser 3** (Tiled maps + pixel sprites) + OpenClaw connector
- **What it does:** In-world task assignment via RPG-style interaction menus. Visible execution pipeline: queued → returning → sending → running → done/failed with worker speech bubbles. Idle agents roam naturally; busy workers queue tasks. Multi-agent seats with workspace+memory per agent.
- **What to steal for Nomos42 /world:**
  - **Tiled map integration** — we can design a `.tmx` map file with named zones: RESEARCH WING (D1), ENGINEERING LAB (D2), TRADING FLOOR (center), EVOLUTION ISLANDS (outer ring). Tiled editor is free, maps are JSON.
  - **Visible execution pipeline as sprite states** — when S17 is training a generation, its island sprite shows RUNNING animation with progress number. When promoted, a CELEBRATE state. Exact UX we need.
  - **RPG interaction menus on click** — clicking a TF agent sprite opens a panel showing their current bankroll, last bet, model name, risk level. Click on an island shows Brier history chart.
  - **Token/context metering** — displayed as a stamina bar above agent head. Map to LLM token budget remaining for TF agents.
  - **v0.5.0 roadmap includes Library (long-term memory) + Workshop (skill management) scenes** — will become the Research Proposals scene and Feature Engineering scene for our use case.
- **Brier impact:** None direct. Major UX/narrative value for Nomos42Picks subscribers.
- **Effort:** Medium — Phaser 3 + Tiled is a known stack. Our existing pixel-world uses Canvas2D; migration to Phaser would give tile-based maps, camera, collision, and sprite management for free.

---

### Finding P2 — ringhyacinth/Star-Office-UI
- **URL:** https://github.com/ringhyacinth/Star-Office-UI
- **Stars:** 6.8k | **Last release:** v1.0.0 (2026-03-06)
- **Tech:** Python (Flask) + HTML/JS frontend (no heavy framework) + Gemini API for background generation
- **What it does:** Maps 6 agent states (idle/writing/researching/executing/syncing/error) to office zones with animated sprites. AI-powered background via Gemini image generation. "Yesterday Memo" daily log card. Multi-agent join-key collaboration. Desktop pet via Electron.
- **What to steal for Nomos42:**
  - **6-state taxonomy** is a perfect fit for our islands: `idle` (no games today), `training` (GA running), `evaluating` (backtest), `promoting` (new champion), `error` (space crashed), `syncing` (pushing weights). Map each to a distinct sprite animation.
  - **Yesterday Memo card** — display last night's prediction summary: "S17 ran 12 gens, Brier stable at 0.22085, no improvement." Appears as a scroll/note on the island desk when you hover.
  - **Gemini background generation** — dynamically generate the /world background art based on current fleet state ("16 agents active, 3 islands improving, playoff season"). Low priority but fun differentiator.
  - **License warning:** Art assets are non-commercial learning only. For production /world, use pixel-agents MIT assets or Kenney.nl (CC0) instead.
- **Brier impact:** None direct.
- **Effort:** Low for the state taxonomy + memo card pattern. Medium for Gemini background gen.

---

### Finding P3 — PixiJS React v8 + @pixi/react (confirmed production-ready)
- **URL:** https://github.com/pixijs/pixi-react | https://pixijs.com/blog/pixi-react-v8-live
- **Stars:** 2.5k+
- **Status:** v8 built specifically for React 19, **WebGPU support**, confirmed production-ready 2026
- **Key facts for Nomos42:**
  - Built from ground up for React 19 (we already use React 19 per claw-empire confirmation)
  - **AnimatedSprite** for frame-by-frame walking cycles — load a sprite sheet JSON + PNG, get walking animation in 5 lines
  - **CacheAsBitmap** — treat static background tiles as bitmaps, reduce draw calls by 10x
  - **WebGPU fallback to WebGL fallback to Canvas** — works on all HF Space browsers
  - The claw-empire project (1.1k stars, production) uses **PixiJS 8** — external validation that this is the right stack for our use case
- **Recommended sprite sheet workflow:**
  1. Design sprites in Aseprite (free, pixel-art optimized)
  2. Export sprite sheet with TexturePacker or Aseprite's built-in exporter → JSON + PNG
  3. Load in PixiJS: `Assets.load('spritesheet.json')` → `AnimatedSprite(textures.walk)`
  4. Wrap in `@pixi/react` `<AnimatedSprite>` component for React state integration
- **Effort:** Low if we already have @pixi/react installed. Medium if Canvas2D migration needed.

---

### Finding P4 — rolandal/pixel-agents-standalone
- **URL:** https://github.com/rolandal/pixel-agents-standalone
- **Stars:** ~50 (fork, newer)
- **Tech:** Fork of pablodelucca/pixel-agents adapted as standalone web app (no VS Code dependency)
- **Why it matters:** pablodelucca/pixel-agents is VS Code only. This fork exposes the same pixel-office rendering as a web app — directly deployable to HF Space or Vercel.
- **What to steal:** The exact extraction of Canvas2D rendering logic from VS Code extension into a web component. This is the bridge between "VS Code toy" and "production web dashboard."
- **Effort:** Very low — it's already ported. Study how rolandal extracted the webview-ui layer.

---

## Cross-Reference: Nomos42 /world Architecture Recommendations

Based on all findings, the recommended stack for the Nomos42 pixel world:

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Rendering | PixiJS 8 + @pixi/react | WebGPU, 60fps, React 19 integration, used by claw-empire (1.1k prod) |
| Map | Tiled (.tmx) + phaser-tiled OR PixiJS tilemap | Named zones per dept/island, free editor |
| Sprites | Kenney.nl 1-Bit Pack (CC0) | Commercial OK, consistent pixel style, 1000+ sprites |
| State machine | 6 states per agent: idle/training/evaluating/promoting/error/syncing | Matches Star-Office-UI + agent-town patterns |
| UI overlay | DOM/React on top of canvas | Proven pattern in all 5 repos (agent-office, claw-empire, agent-town, pixel-agents, AgentFleet) |
| Charts | TradingView Lightweight Charts | Replace recharts for Brier curves, 60fps Canvas-based |
| Retro styling | XP.css window chrome + Pixelact UI cards | Terminal feel on /floor, pixel cards on /world panels |
| Agent interaction | RPG click-to-open info panel (agent-town pattern) | Bankroll, model, last-bet on click |

---

## Top 3 Actionable Steals (priority order)

**STEAL 1 — TradingView Lightweight Charts for Brier curves (1 day)**
Replace recharts `<LineChart>` on /evolution with LW Charts Canvas renderer. Immediate 60fps improvement on gen-count timelines. Package: `npm i lightweight-charts @tradingview-tools/lightweight-charts-react`.

**STEAL 2 — 6-state agent sprite taxonomy (2 days)**
Implement: idle → training → evaluating → promoting → error → syncing states for all 21 evolution island sprites. Use Kenney 1-Bit Pack sprites (already referenced in our SOTA stack). Map to PixiJS AnimatedSprite frames. This makes the /world feel alive without Phaser rewrite.

**STEAL 3 — RPG click-to-open info panel (1 day)**
On sprite click, render a DOM overlay panel (React, not PixiJS) with: island ID, current Brier, gen count, status, last mutation. Pattern confirmed in agent-town, agent-office, claw-empire. The DOM overlay on canvas pattern is our existing architecture — zero new deps.

---

## Sources
- [pablodelucca/pixel-agents](https://github.com/pablodelucca/pixel-agents) — 6.8k stars, v1.3.0 Apr 14 2026
- [rolandal/pixel-agents-standalone](https://github.com/rolandal/pixel-agents-standalone) — standalone web fork
- [harishkotra/agent-office DEV post](https://dev.to/harishkotra/how-i-built-agentoffice-self-growing-ai-teams-in-a-pixel-art-virtual-office-4o0p) — Phaser + Colyseus arch
- [geezerrrr/agent-town](https://github.com/geezerrrr/agent-town) — 127 stars, v0.4.1 Mar 11 2026
- [GreenSheep01201/claw-empire](https://github.com/GreenSheep01201/claw-empire) — 1.1k stars, PixiJS 8 confirmed
- [DBell-workshop/AgentFleet](https://github.com/DBell-workshop/AgentFleet) — 57 stars, Quant Trading scene template
- [ringhyacinth/Star-Office-UI](https://github.com/ringhyacinth/Star-Office-UI) — 6.8k stars, v1.0.0 Mar 6 2026
- [harishkotra/agent-office](https://github.com/harishkotra/agent-office) — 68 stars, Colyseus sync
- [PixiJS React v8 announcement](https://pixijs.com/blog/pixi-react-v8-live) — WebGPU + React 19
- [TradingView lightweight-charts](https://github.com/tradingview/lightweight-charts) — Canvas-based, recharts replacement
- [XP.css](https://botoxparty.github.io/XP.css/) — retro OS CSS framework
- [Pixelact UI](https://www.pixelactui.com/) — shadcn/ui pixel art components
- [AgentCrunch Star-Office article](https://agentcrunch.ai/article/star-office-ai-crew) — 6-state taxonomy detail
- [OpenClaw Star-Office-UI tutorial](https://openclawapi.org/en/blog/2026-03-05-star-office-ui-pixel-board) — integration guide
- [Fast Company pixel-agents article](https://www.fastcompany.com/91497413/this-charming-pixel-art-game-solves-one-of-ai-codings-most-annoying-ux-problems) — mainstream coverage
- [Querio React chart libraries 2026](https://querio.ai/articles/top-react-chart-libraries-data-visualization) — recharts vs alternatives
- [LogRocket PixiJS React guide](https://blog.logrocket.com/getting-started-pixijs-react-create-canvas/) — integration patterns
- [PixiJS performance tips](https://pixijs.com/8.x/guides/concepts/performance-tips) — CacheAsBitmap, draw calls
