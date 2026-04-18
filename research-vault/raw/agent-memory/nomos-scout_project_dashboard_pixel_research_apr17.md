---
name: dashboard-pixel-sota-research-apr17
description: Apr 17 2026 scout run on game-like dashboards + pixel agent visualization — key repos, confirmed stack, 3 proposals
type: project
---

Scout run 2026-04-17 covering SOTA game-feel dashboards and pixel agent visualization repos.

Key finds:
- pablodelucca/pixel-agents (6.8k stars, v1.3.0 Apr 14 2026): VS Code pixel office. MIT assets. rolandal/pixel-agents-standalone is the web-deployable fork.
- ringhyacinth/Star-Office-UI (6.8k stars, v1.0.0 Mar 6 2026): 6-state taxonomy (idle/writing/researching/executing/syncing/error). Flask backend, HTML/JS frontend. Art assets non-commercial only — use Kenney CC0 instead.
- GreenSheep01201/claw-empire (1.1k stars): **PixiJS 8 + React 19 confirmed production-ready** for multi-agent office dashboards. Has Quant context. BSL 1.1 license.
- geezerrrr/agent-town (127 stars, v0.4.1 Mar 11 2026): Next.js 16 + Phaser 3 + Tiled maps. RPG click-to-inspect pattern. Visible execution pipeline states. Best architectural reference for /world.
- TradingView Lightweight Charts: Canvas-based recharts replacement. 60fps at millions of points. recharts freezes at 5k SVG nodes — relevant for 21-island Brier curve comparison.
- XP.css + Pixelact UI: retro OS aesthetic + pixel-art shadcn components. Low effort, high personality for /floor terminal feel.

Confirmed architecture for /world:
- PixiJS 8 + @pixi/react (WebGPU, React 19, used by claw-empire)
- Kenney 1-Bit Pack sprites (CC0, commercial OK)
- 6 states per agent: idle/training/evaluating/promoting/error/syncing
- DOM overlay panels on sprite click (confirmed pattern in all 5 repos)
- TradingView LW Charts for Brier curves (replace recharts on /evolution)

3 proposals written 2026-04-17:
1. proposal-2026-04-17-lightweight-charts-brier-curves.md (1 day, LOW effort)
2. proposal-2026-04-17-pixel-world-6state-sprite-machine.md (3-4 days, MEDIUM effort)
3. proposal-2026-04-17-pixel-world-rpg-click-panel.md (1 day, LOW effort)

**Why:** pixel-world UX drives Nomos42Picks subscriber retention ($19/mo). May 1 revenue deadline.
**How to apply:** nomos-lab should prioritize proposals 1+3 (2 days combined) before May 1 deadline. Proposal 2 is the 3-day stretch goal.

Full findings at: /home/termius/mon-ipad/data/research/dashboard-pixel-sota-apr17.md
