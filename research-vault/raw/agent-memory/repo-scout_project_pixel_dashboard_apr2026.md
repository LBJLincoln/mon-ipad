---
name: Pixel Dashboard Deep Dive (Apr 2026)
description: Best pixel-art game-like dashboard references for Nomos42 Trading Floor rebuild
type: project
---

Comprehensive scan of pixel-art game dashboards as references for rebuilding the "catastrophic" Trading Floor page.

**Why:** Trading Floor dashboard has no visual appeal. Target: pixel game world with 9 dept offices + 5 AI traders + infra buildings.

**How to apply:** Use pixel-agents as base clone, add Moltcraft building metaphors, STONKS CRT ticker, Pixelact UI chrome.

## Winner Stack
Next.js 15 App Router + Canvas 2D (start) or @pixi/react v8 (if >50 sprites) + Pixelact UI + Tailwind CSS 4

Note: @pixi/react v8 had React 19 issues (Issue #551) — use @pixi/react@latest which is a full rewrite.

## Top References (with stars)
1. **pixel-agents** (pablodelucca) — 6.1k stars, MIT, React 19, Canvas 2D, JIK-A-4 Metro City assets INCLUDED, office editor, BFS pathfinding, state machine. Clone this as base.
2. **Moltcraft** (askmojo) — 24 stars, MIT, isometric buildings, zero npm deps, clickable buildings=live data. Steal: building-per-concept metaphor.
3. **ClawBoard** (kirillkuzin) — 1 star, MIT, Next.js 15 App Router + PixiJS 8 native. Exact pattern for embedding PixiJS in App Router.
4. **AI Town** (a16z-infra) — 9.7k stars, MIT, PixiJS rendering, 16x16 tiles, Vercel deployable. Best visual quality, too heavy to clone wholesale.
5. **Claw Empire** (GreenSheep01201) — 1k stars, Apache 2.0, React 19 + PixiJS 8, 6 dept rooms. Extend 6→9 depts.
6. **AgentRoom** (liuyixin-louis) — 5 stars, MIT, SkyOffice 32x32 tileset, distinct agent visual styles per provider, sub-agents as linked children.
7. **pixel-claw** (monkeystar0) — 1 star, MIT, Matrix spawn/despawn, z-sorting with furniture, wardrobe palette system.
8. **Phaser Next.js Template** (phaserjs) — 145 stars, MIT, Next.js 15, full game engine. Use only for EventBus pattern reference.
9. **IsoCity** (victorqribeiro) — 3.2k stars, MIT, isometric vanilla JS, Kenney CC0 assets. Use if going isometric.
10. **Pixelact UI** (pixelact-ui) — 79 stars, MIT, pixel-art shadcn components. Install via npx for UI chrome.
11. **STONKS-9800** — commercial reference. Steal: CRT scanline CSS, Press Start 2P font, ticker tape component.
12. **openclaw-pixel-agents-dashboard** (jaffer1979) — 2 stars, MIT. Steal: breaker panel for HF Space controls.

## Free Assets
- **JIK-A-4 Metro City** — already in pixel-agents repo under MIT
- **Kenney.nl** — CC0, no attribution, commercial OK
- **LimeZu Modern Interiors** — commercial OK but attribution required, no redistribution
- **Press Start 2P / VT323** — Google Fonts, OFL license
- **OpenGameArt.org** — CC0 collection

## Implementation Order (20+6+8=34 hours total)
1. Clone pixel-agents (20h): 9-room layout, wire to bloomberg-api.py WebSocket
2. Add Moltcraft infra map + STONKS ticker (6h)
3. Pixelact UI chrome + distinct trader colors from AgentRoom (8h)

Full report: /home/lahargnedebartoli/nomos-nba-agent/data/results/pixel-dashboard-scout.json
