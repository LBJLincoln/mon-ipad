---
title: Nomos42 Pixel World
emoji: 🏙️
colorFrom: indigo
colorTo: purple
sdk: static
pinned: false
license: mit
short_description: 38 AI agents walking a pixel office, live thinking visible
---

# Nomos42 Pixel World (crash-test staging)

Live agent simulation: 21 Trading-Floor traders (12 NBA + 10 Political) + 8
evolution islands + 9 department councils = 38 sprites walking a pixel office.
Every 30s fetches `/api/status` from the real HF Spaces and renders each
agent's last thought as a speech bubble.

This Space is the staging env that replaces Vercel `/world` during the free-tier
deploy rate-limit window. Once iterated here, the same render loop ports
1:1 into the Next.js dashboard.

## Attribution
- Sprites (characters, floors, furniture) adapted from
  [pablodelucca/pixel-agents](https://github.com/pablodelucca/pixel-agents)
  (MIT). See `assets/LICENSE-pablodelucca-pixel-agents.txt`.
- Room-routing concept inspired by
  [monkeystar0/pixel-claw](https://github.com/monkeystar0/pixel-claw) (MIT).
- Thought-schema `{thought, action, target, toolCall}` inspired by
  [harishkotra/agent-office](https://github.com/harishkotra/agent-office) (MIT).

## Live data sources
- `https://lbjlincoln26-nba-llm-trading-floor.hf.space/api/status`
- `https://lbjlincoln26-political-llm-trading-floor.hf.space/api/status`
- `https://nomos42-nba-quant.hf.space/api/status` (+ 7 sibling islands)
- `https://testforge42-nomos-dept-d1-research.hf.space/api/status` (+ 8 depts)

Fallback JSON baked in so the render works even when Spaces are cold.
