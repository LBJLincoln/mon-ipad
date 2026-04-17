# Proposal: RPG Click-to-Inspect Panel for /world Agent Sprites

**Date:** 2026-04-17  
**Scout:** nomos-scout  
**Status:** OPEN  
**Priority:** MEDIUM  

## Problem

In the Nomos42 pixel world, users can see agents walking around but cannot inspect what they are doing. Clicking on an island sprite or TF agent sprite does nothing. This breaks the mental model of "I can understand my system by looking at it." The /world is visual but not informational. Nomos42Picks subscribers would benefit from being able to click any agent and see current status without leaving the page.

## Proposed Fix

Implement a DOM overlay info panel that appears on sprite click, following the RPG-interaction-menu pattern from geezerrrr/agent-town (127 stars, v0.4.1 March 2026) and confirmed in claw-empire (1.1k stars), harishkotra/agent-office (68 stars), and pablodelucca/pixel-agents (6.8k stars).

### For Evolution Island sprites (21 total, S10-S22 + P1-P8):
- Island ID + HF Space URL
- Current Brier score (bold, colored: green if < fleet avg, red if > fleet avg)
- Gen count
- Strategy name (ensemble, catboost, lightgbm, etc.)
- Last mutation type
- Current state (idle/training/evaluating/promoting/error/syncing)
- Sparkline: last 20 gens Brier trend (tiny SVG, inline)
- Button: "View full history →" links to /evolution filtered to this island

### For Trading Floor agent sprites (16 total, T1-T16):
- Trader ID + model name (e.g., "T1: qwen-quant | Qwen 3 235B")
- Current bankroll (bold, green/red vs starting $100k)
- Today's bets (count + total staked)
- Personality + risk level
- Win rate (all-time for this season run)
- Pact status (cooperating with N agents)
- Button: "View trade log →" links to /trading-floor filtered to this agent

## Implementation Pattern

All 5 confirmed repos use the same DOM-overlay-on-canvas approach:
1. PixiJS canvas handles sprite rendering + hit detection (`sprite.eventMode = 'static'; sprite.on('pointerdown', handleClick)`)
2. Click event passes agent ID to React state (`setSelectedAgent(id)`)
3. React renders a position-absolute div over the canvas (not inside PixiJS)
4. Panel styled with Pixelact UI card or XP.css window chrome for retro feel
5. Close on ESC or click-outside

This is the **existing architecture** of our pixel-world (DOM overlay confirmed correct per project memory). Zero new patterns needed.

## Implementation Target

- Repo: `Nomos42/pixel-world` (HF Space)
- File: `hf-pixel-world/index.html` — add click handler + panel HTML/CSS
- Data source: Same `/api/status` polling used by 6-state machine proposal
- No new dependencies: PixiJS pointer events + vanilla DOM overlay

## Brier Impact Estimate

None direct. High subscriber UX value: turns /world from a screensaver into an interactive monitoring tool. Directly supports the Nomos42Picks $19/mo pitch ("you can watch your AI fleet in real time and inspect every agent").

## Effort Estimate

**Low — 1 day**. The click handler and DOM panel are vanilla JS/HTML. The data is already available from `/api/status` polling. The main work is panel layout and responsive positioning (keep panel inside viewport on edge-of-screen sprite clicks).

## Evidence

- agent-town: RPG-style interaction menus on worker click is core UX driver (127 stars, v0.4.1)
- claw-empire: agent KPI panel on click is listed as a primary dashboard feature (1.1k stars)
- pablodelucca/pixel-agents: click on character shows activity detail (6.8k stars)
- harishkotra/agent-office: drag-drop layout editor + inspector panel confirms pattern at prod quality
- Source: `/home/termius/mon-ipad/data/research/dashboard-pixel-sota-apr17.md` Findings D2, D3, P1

## Not duplicate of

- No existing proposal covers click-to-inspect UX for /world sprites.
- `pixel-world-diegetic-panels-apr17.md` covers always-visible status panels; this covers on-demand click inspection.
- `proposal-2026-04-17-pixel-world-6state-sprite-machine.md` covers animation states; this covers the inspection UX layer.
