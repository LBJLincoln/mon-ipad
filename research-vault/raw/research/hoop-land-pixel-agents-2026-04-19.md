# Research Scan: hoop-land-pixel-agents-2026-04-19


## report_id
hoop-land-pixel-agents-2026-04-19


## author
HAWKEYE


## date
2026-04-19


## mission
Replicate Hoop Land aesthetic for Nomos42/pixel-world — 40 trader-agents (17 NBA TF + 17 POL TF + 6 ITF) walking a persistent pixel world on an HF static Space.


## tldr

- Hoop Land is almost certainly built in GameMaker Studio 2 (Koality Game's prior titles Prizefighters, Hoop League Tactics, Ice League Hockey are GMS2). It is a native mobile app — NOT a web stack. Dir
- The *look* — 32x32 top-down pixel characters, 8-bit palette, 2-4 frame walk cycle — is fully reproducible with free CC0 assets on an HF static Space.
- Recommended stack: KEEP current React+Canvas2D (already shipped), ADD PixiJS v8 for 40-agent sprite batching (2x faster than vanilla canvas, 3x smaller than Phaser). Do NOT introduce Phaser — overkill
- Recommended sprite pack: KEEP pablodelucca base + LAYER chasersgaming Basketball NES (£2, CC0, 7 animations incl. IDLE/RUN/DRIBBLE/SHOOT/BLOCK — this is the Hoop Land aesthetic exactly).
- Reference architecture to clone: pablodelucca/pixel-agents (6.9k stars, MIT, React 19 + Canvas 2D + manifest.json asset system + BFS pathfinding + state machine) — SAME stack we already have. Their ma
- No open-source Hoop Land clone exists. OpenClaw ecosystem (pixel-claw, agents-in-the-office, agent-town) is the closest multi-agent pixel-world prior art — all shipped Q1 2026.

## q3_sprite_packs_direct_download

- **Basketball NES Asset Pack**: 
  - URL: https://chasersgaming.itch.io/asset-pack-basketball-nes
- **MetroCity - Free Top Down Character Pack**: 
  - URL: https://jik-a-4.itch.io/metrocity-free-topdown-character-pack
- **CraftPix Top-Down Sprites (free tier)**: 
  - URL: https://craftpix.net/freebies/

## q4_open_source_pixel_agent_frameworks_top3

- **pablodelucca/pixel-agents**: 
  - URL: https://github.com/pablodelucca/pixel-agents
- **monkeystar0/pixel-claw (the 'OpenClaw visualizer')**: 
  - URL: https://github.com/monkeystar0/pixel-claw
- **geezerrrr/agent-town**: 
  - URL: https://github.com/geezerrrr/agent-town

## q4_honorable_mentions

- **89sphuho-web/pixel-agents-openclaw**: 
  - URL: https://github.com/89sphuho-web/pixel-agents-openclaw
- **ohvignas/openclaw-pixel**: 
  - URL: https://github.com/ohvignas/openclaw-pixel
- **DevvGwardo/openclaw-pixel-agents**: 
  - URL: https://github.com/DevvGwardo/openclaw-pixel-agents

## anti_recommendations

- **?**: 
- **?**: 
- **?**: 
- **?**: 
- **?**: 

## open_questions_for_user

- Budget approval for chasersgaming Basketball NES £2 pack? (Or produce our own NES-palette sprites with PixelLab.ai — free but 1 extra day of iteration.)
- Should all 40 agents share ONE giant pixel-world, OR do we keep the existing /world layout and add separate /court + /floor + /pit rooms? (Recommend: single world, 3 zones, doorways — matches Hoop Lan
- Keep pablodelucca Metro City sprites as the office/idle default, or replace entirely with NES-palette for Hoop Land consistency? (Recommend: keep both — NES on-court, Metro City in lounges, gives the 

## sources

- **Hoop Land on Steam**: 
  - URL: https://store.steampowered.com/app/2453660/Hoop_Land/
- **Koality Game official — Hoop Land**: 
  - URL: https://www.koalitygame.com/hoop-land
- **Koality Game on gmgames.org (GameMaker developer directory)**: 
  - URL: https://gmgames.org/developer/koality-game/
- **TouchArcade — Hoop Land beta thread**: 
  - URL: https://toucharcade.com/community/threads/beta-hoop-land-2d-pixel-basketball-simulation-by-koality-game.427946/
- **chasersgaming Basketball NES Asset Pack (itch.io)**: 
  - URL: https://chasersgaming.itch.io/asset-pack-basketball-nes
- **JIK-A-4 MetroCity Free Top Down Character Pack (itch.io)**: 
  - URL: https://jik-a-4.itch.io/metrocity-free-topdown-character-pack
- **pablodelucca/pixel-agents (GitHub, 6.9k stars)**: 
  - URL: https://github.com/pablodelucca/pixel-agents
- **monkeystar0/pixel-claw (GitHub)**: 
  - URL: https://github.com/monkeystar0/pixel-claw
- **geezerrrr/agent-town (GitHub, 129 stars)**: 
  - URL: https://github.com/geezerrrr/agent-town
- **89sphuho-web/pixel-agents-openclaw (GitHub, single HTML file reference)**: 
  - URL: https://github.com/89sphuho-web/pixel-agents-openclaw
- **ohvignas/openclaw-pixel (GitHub, Docker compose reference)**: 
  - URL: https://github.com/ohvignas/openclaw-pixel
- **gukosowa/agents-in-the-office (GitHub, Tauri desktop — NOT web)**: 
  - URL: https://github.com/gukosowa/agents-in-the-office
- **PixiJS v8 performance benchmark (Shirajuki js-game-rendering-benchmark)**: 
  - URL: https://github.com/Shirajuki/js-game-rendering-benchmark
- **Phaser vs PixiJS comparison (Medium, Selina Byeon)**: 
  - URL: https://selinabyeon.medium.com/pixi-js-vs-phaser-3-519eba2f9817