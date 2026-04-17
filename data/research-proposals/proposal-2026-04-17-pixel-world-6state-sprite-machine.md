# Proposal: 6-State Sprite State Machine for Evolution Island Agents in /world

**Date:** 2026-04-17  
**Scout:** nomos-scout  
**Status:** OPEN  
**Priority:** HIGH  

## Problem

Our pixel-world (`Nomos42/pixel-world`) currently shows 21 evolution islands and 16 TF agents as static or minimally-animated sprites. The agents do not visually reflect what is actually happening (training, evaluating, stagnating, crashed). The /world feels like a screenshot, not a living system. For Nomos42Picks subscriber retention, the world needs to feel alive.

## Proposed Fix

Implement a 6-state sprite animation state machine for all 21 evolution island sprites (and optionally the 16 TF agents), derived from the Star-Office-UI taxonomy (6.8k stars, v1.0.0 March 2026) and agent-town (127 stars, v0.4.1 March 2026):

| State | Trigger condition | Sprite animation | HF Space signal |
|-------|------------------|-----------------|----------------|
| `idle` | No active games today | Sprite sitting, blinking | Space sleeping / no recent gen |
| `training` | GA generation running | Sprite typing rapidly at desk | gen count incrementing |
| `evaluating` | Backtest running | Sprite reading stack of papers | Brier recomputed this cycle |
| `promoting` | New Brier champion achieved | Sprite celebration, star burst | Brier improved vs last checkpoint |
| `error` | Space crashed / 502 | Sprite slumped, red X above head | /api/status non-200 |
| `syncing` | GPU promote-config pushed | Sprite carrying weights to board | POST /api/config received |

State is derived from existing `/api/status` polling (already running every 30 min via keepalive cron). No new backend needed.

## Implementation Target

- Repo: `Nomos42/pixel-world` (HF Space)
- File: `hf-pixel-world/index.html` (main pixel world source)
- Sprite source: Kenney.nl 1-Bit Pack (CC0, commercial OK — 1000+ sprites). Download free from kenney.nl/assets/1-bit-pack.
- Rendering: PixiJS 8 + @pixi/react (already in stack per CLAUDE.md) via AnimatedSprite frames
- State polling: fetch `/api/status` from each of the 21 island HF Spaces every 5 min → update sprite state
- Frame count: 4 frames per state × 6 states = 24 frames per island sprite sheet

## Brier Impact Estimate

None direct. Estimated subscriber retention improvement: high. The "living system" narrative is central to Nomos42Picks marketing. Reference: pablodelucca/pixel-agents went from 0 to 6.8k stars specifically because watching agents work is compelling even when nothing is changing.

## Effort Estimate

**Medium — 3-4 days**. Breakdown:
- Day 1: Download Kenney 1-Bit sprites, create 6-state sprite sheet in Aseprite, export JSON
- Day 2: Implement `AgentStateMachine` class in pixel-world JS, wire to `/api/status` polling
- Day 3: PixiJS AnimatedSprite integration, test all 6 transitions
- Day 4: Deploy to HF Space, verify Chrome QA before ship (mandatory per pixel panel regression lesson)

## Evidence

- Star-Office-UI (6.8k stars): 6-state taxonomy is validated at scale
- agent-town (127 stars, Next.js + Phaser 3): visible execution pipeline drives engagement
- pablodelucca/pixel-agents (6.8k stars): state→animation mapping is the core value proposition
- Source: `/home/termius/mon-ipad/data/research/dashboard-pixel-sota-apr17.md` Findings P1, P2

## Not duplicate of

- `pixel-world-rebuild-patterns-apr16.md` covers general rebuild patterns; does not spec the state machine.
- `pixel-world-diegetic-panels-apr17.md` covers panel content; does not spec agent animation states.
- `proposal-2026-04-17-pixel-world-rpg-click-panel.md` covers click-to-inspect UX; this covers the animation layer.
