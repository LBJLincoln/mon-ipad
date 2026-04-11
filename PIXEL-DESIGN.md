# PIXEL-DESIGN.md — Nomos42 Pixel World (207 AI Trading Agents)

> Architecture for a professional pixel-art agent world on Vercel/Next.js
> Last updated: 2026-04-10

---

## 1. REFERENCE PROJECTS (2024–2026)

### Tier 1 — Clone / Steal Directly

| Project | Stars | License | Stack | What to steal |
|---------|-------|---------|-------|---------------|
| **pixel-agents** (pablodelucca) | 6.1k | MIT | React 19, Canvas 2D, Vite | Entire base: office editor, BFS pathfinding, state machine, JIK-A-4 Metro City assets |
| **AI Town** (a16z-infra / get-convex) | 9.7k | MIT | Convex, pixi-react, 32x32folk.png | pixi-react rendering pattern, world-state sync, smooth 60Hz lerp with 1s DB tick |
| **Miniverse** (ianscott313/minivrs.com) | — | MIT | REST+WS, Canvas renderer | Full agent API spec (heartbeat, act, observe, inbox), world.json format, anchor system |
| **Claw Empire** (GreenSheep01201) | 1k | Apache 2.0 | React 19, PixiJS 8 | 6-department room layout; extend to 9 depts + trading floor zone |
| **AgentRoom** (liuyixin-louis) | — | MIT | Canvas 2D, SkyOffice 32x32 | Distinct per-provider agent visual style, sub-agent child-linking |
| **agent-town** (geezerrrr) | — | — | Next.js 16, Phaser 3, Tiled | Tiled map integration, task bubble states (queued→running→done), React+Canvas hybrid overlay |
| **AgentOffice** (harishkotra) | — | — | Phaser, React, Colyseus, Ollama | perceive→think→act→remember loop, delta-compressed WebSocket sync, camera lerp |

### Tier 2 — Reference Only

| Project | What to steal |
|---------|---------------|
| **STONKS-9800** (Ternox) | CRT scanline CSS overlay, Press Start 2P font, 80s Japan stock ticker UI, anime portrait panels |
| **Moltcraft** (askmojo) | Isometric building = live data source metaphor, zero-dependency render |
| **Dwarf Fortress** | Information density philosophy: every tile carries meaning, agents have professions/moods |
| **Theme Hospital / Two Point Hospital** | Zone-based behavior (agents go to room type by role), room unlocking progression |
| **pixel-claw** (monkeystar0) | Matrix spawn/despawn effect, z-sorting with furniture occlusion, wardrobe palette swap system |
| **ClawBoard** (kirillkuzin) | Next.js 15 App Router + PixiJS 8 embedding pattern (exact pattern for our stack) |
| **IsoCity** (victorqribeiro) | 3.2k stars, if going isometric; Kenney CC0 assets included |
| **Pixelact UI** (pixelact-ui) | Pixel-art shadcn components: `npx pixelact-ui add button` — use for HUD chrome |

---

## 2. RENDERING ENGINE DECISION

### Benchmark Data (AMD Ryzen 5 4500U, 10,000 sprites)

| Engine | FPS @ 10k sprites | Bundle | Verdict |
|--------|-------------------|--------|---------|
| Canvas 2D | ~10–15 | 0 KB | Dead above 100 agents |
| **PixiJS 8** | **47 FPS** | 450 KB | Winner for 200+ agents |
| Phaser 3/4 | 43 FPS | 1.2 MB | Good; adds 700KB for unused physics |
| Babylon.js | 56 FPS | 2.1 MB | Overkill; optimized for 3D |
| Kaboom/Kaplay | 3 FPS @ 10k | — | Do NOT use |

### For 207 agents: Use @pixi/react v8 + PixiJS 8

**Rationale:**
- 207 sprites is well within PixiJS's comfort zone (47fps at 10k means ~200fps at 200 sprites)
- `@pixi/react` v8 is a ground-up rewrite for PixiJS v8 + React 19
- Custom JSX pragma: `<pixi-sprite>`, `<pixi-container>` — no wrapper components
- `extend()` API: import only what you use, keeping bundle lean
- WebGPU support built in (future-proof)
- Next.js App Router integration: use `ClawBoard` pattern (dynamic import with `ssr: false`)

**Next.js integration:**
```typescript
// app/trading-floor/page.tsx
import dynamic from 'next/dynamic'
const PixelWorld = dynamic(() => import('@/components/PixelWorld'), { ssr: false })
```

**Phaser 3 is valid alternative if:**
- You need Tiled map editor support (agent-town pattern)
- You want built-in audio system
- Use the `phaserjs/phaser-next.js` template EventBus pattern for React↔Phaser bridge

---

## 3. SPRITE DESIGN STANDARDS

### 3.1 Resolution: 32×32 is the standard

| Size | Use case | Reason |
|------|----------|--------|
| 16×16 | Tiles (floors, walls, furniture small) | Efficient, 4096 tiles per 1MB atlas |
| **32×32** | **Agent characters** | Sweet spot: enough pixels for face, clothing, tier badge |
| 48×64 | Premium agents (top 5 traders) | Extra detail for main characters |
| 64×64 | Miniverse spec for walk+action sheets | Use 256×256 sheet = 4×4 grid of 64×64 frames |

**Modern screen note:** Always render to a low-res canvas (e.g. 320×180 or 640×360) then scale up with CSS `image-rendering: pixelated`. This preserves crisp pixels at any DPI.

```css
canvas {
  image-rendering: pixelated;
  image-rendering: crisp-edges;
  width: 100%;
  height: 100%;
}
```

### 3.2 Walk Cycle Frames

| Frame count | Use case | Notes |
|-------------|----------|-------|
| 2-frame | Minimal agents (background) | Cheapest: alternate feet |
| **4-frame** | **Standard agents** | Industry standard; works down to 32×32 |
| 8-frame | Premium agents (top traders, named AIs) | Smoother; head bob, arm swing |
| 16-frame total | Full 4-direction walk | 4 frames × 4 directions |

**Miniverse spec (proven in production):**
- Walk sheet: 256×256px, 4 rows × 4 cols = 16 frames of 64×64
- Action sheet: 256×256px, 4 rows × 4 cols covering sit/sleep/talk/idle
- For 32×32 agents: 128×128 sheet, 4×4 grid of 32×32 frames

### 3.3 Color Palette

**Strict limits for retro feel:**
- Tiles: 8–16 colors per tileset
- Agent base palette: 4–8 colors per character
- World palette: 32–64 colors total (use a named palette: PICO-8, Sweetie-16, or Endesga-32)

**Recommended palette: Sweetie-16 (16 colors)**
- Free on Lospec.com
- Professional retro look, warm office tones

**Per-tier differentiation via palette swap only:**
- Load one base sprite sheet
- Apply CSS filter or WebGL uniform to swap hues per agent tier
- No need for 207 separate sprite files

### 3.4 Agent Tier Differentiation

| Tier | Visual treatment | Badge |
|------|-----------------|-------|
| **T5 — Champion** | Gold outline + sparkle particle | Crown 👑 (2×2 pixels) |
| **T4 — Elite** | Silver outline | Star (2×2) |
| **T3 — Standard** | No outline | Dot |
| **T2 — Rookie** | Slightly desaturated | No badge |
| **T1 — Spectator** | Semi-transparent | X mark |

**Implementation:** Use PixiJS `tint` property on Container — zero extra draw calls:
```typescript
agentSprite.tint = tierColors[agent.tier] // 0xFFD700 for gold
```

### 3.5 Procedural vs Hand-Drawn

**Recommendation: Hybrid approach**
1. Use LimeZu Modern Office (16×16, $2.50) for all furniture/tiles
2. Use JIK-A-4 Metro City pack (free, MIT) for base agent characters
3. Generate 5–10 color variations per character using palette swap shaders
4. Use Stable Diffusion 3.5 with PixelLock conditioning for unique tier-5 portraits

---

## 4. WORLD LAYOUT — 207 AGENTS

### 4.1 Zone Map (top-down, 80×60 tile grid = 2560×1920 px at 32px/tile)

```
┌─────────────────────────────────────────────────────┐
│  LOBBY / TICKER TAPE (full width, 4 tiles high)     │
│  [scrolling stock prices + prediction scores]        │
├──────────────┬──────────────┬────────────────────────┤
│  D1 RESEARCH │  D2 ENGINEER │  D3 EVOLUTION          │
│  (12×12)     │  (12×12)     │  (12×12)               │
│  📚 desks    │  💻 monitors │  🧬 evolution chamber   │
├──────────────┼──────────────┼────────────────────────┤
│  D4 PRODUCT  │  D5 BUSINESS │  D6 EVALUATION         │
│  (12×12)     │  (12×12)     │  (12×12)               │
├──────────────┴──────────────┴────────────────────────┤
│  TRADING FLOOR (full width, 20 tiles high)           │
│  T1-T5 traders × 5 stations + 5 political traders   │
│  Central arena with big board (12 tiles wide)        │
├──────────────┬──────────────┬────────────────────────┤
│  D7 INFRA    │  D8 FINANCE  │  D9 CROSS-REPO         │
│  (12×12)     │  (12×12)     │  (12×12)               │
│  🖥️ servers  │  💰 ledgers  │  🔄 sync terminals     │
├──────────────┴──────────────┴────────────────────────┤
│  CANTEEN + SOCIAL ZONE (full width, 6 tiles high)   │
│  Agents gossip, share wins, idle animations          │
└─────────────────────────────────────────────────────┘
```

### 4.2 Agent Distribution (207 total)

| Zone | Agents | Behavior |
|------|--------|----------|
| Trading Floor | 10 (5 NBA + 5 Political) | Highly active: run to board, debate |
| D1–D9 (9 depts × ~20) | 180 | Dept-specific anchor points |
| Canteen | 10 rotating | Idle gossip, speech bubbles |
| Lobby | 7 | Greet visitors, display scores |

### 4.3 Anchor System (Miniverse pattern)

Each prop has named anchors with type:
- `work` — desks (agent shows current task in speech bubble)
- `rest` — couches (sleeping particles, Zzz animation)
- `social` — meeting tables (conversation bubbles, laugh emotes)
- `utility` — whiteboard/server rack (thinking particles, `...` bubble)

---

## 5. AGENT BEHAVIOR SYSTEM

### 5.1 Finite State Machine (FSM) — Recommended over Behavior Trees

**Why FSM over BT for this use case:**
- 207 agents → simplicity wins; BTs add complexity without benefit
- Agent states are well-defined and mutually exclusive
- FSM maps directly to visual states (one state = one animation row)

**State machine (extends Miniverse spec):**
```
IDLE → WALKING → WORKING
IDLE → WALKING → SOCIAL
IDLE → SLEEPING
IDLE → THINKING
WORKING → CELEBRATING (on win)
WORKING → ERROR (on fail)
CELEBRATING → IDLE
ERROR → IDLE
```

**State-to-animation row mapping (walk sheet):**
```
Row 0: walk_south (toward viewer)
Row 1: walk_north (away)
Row 2: walk_west
Row 3: walk_east

Action sheet:
Row 0: working/typing (4 frames)
Row 1: sleeping (2) + idle_stand (2)
Row 2: talking gesture (4 frames)
Row 3: celebrating (4 frames) — arms up, bounce
```

### 5.2 Pathfinding: BFS for this world

| Algorithm | Use case | Notes |
|-----------|----------|-------|
| **BFS** | Short paths, simple grid | Used by pixel-agents, AgentRoom — correct choice |
| A* | Large open worlds, obstacles | Overkill for office rooms |
| JPS | 4-directional, large maps | Grid Engine recommends for 4-dir movement, faster than A* |
| Steering | Flocking, smooth crowds | Nice for canteen zone; add as secondary behavior |

**BFS implementation:** Pre-compute walkability grid from world.json floor array. 1=walkable, 0=wall. Cache paths since agents repeat same routes.

**Collision avoidance:** When two agents collide, one re-plans (AI Town pattern). Simple: check next tile before moving; if occupied, wait 2 frames then re-plan.

### 5.3 Zone-Based Behavior

Agents know their dept zone and spend 80% of time within it:
```typescript
const AGENT_ZONES = {
  'gemini':    { zone: 'trading_floor', station: {x: 45, y: 30} },
  'grok':      { zone: 'trading_floor', station: {x: 50, y: 30} },
  'd1_agent_1': { zone: 'research',    desk: {x: 5,  y: 10} },
  // ...
}

// Every N seconds, each agent picks an action:
// 70%: return to desk → work
// 15%: go to social zone → chat
// 10%: go to utility anchor → think
//  5%: wander → canteen
```

### 5.4 Agent Loop (AgentOffice pattern, adapted)

```
Every 15s per agent:
  1. PERCEIVE: check world state, nearby agents, incoming messages
  2. THINK: compute next state based on dept role + recent events
  3. ACT: move to anchor + display state visuals
  4. REMEMBER: update agent's last action (lightweight, no LLM per tick)

For trading agents (active events only):
  On new prediction → CELEBRATING or ERROR state → speech bubble with result
  On new bet → run to trading board → display Kelly size
```

### 5.5 Speech Bubbles

**Implementation pattern:**
```typescript
// Render as PixiJS Text + Graphics above agent
class SpeechBubble {
  text: string       // content
  type: 'say' | 'think' | 'shout'  // think = cloud shape, shout = spiky
  ttl: number        // frames until auto-dismiss
  maxWidth: 80       // pixels
}
```

**Bubble types by event:**
- Win prediction → `shout` bubble, gold text: "CORRECT! +$420"
- Working → `think` bubble, gray: "Analyzing..."
- Social → `say` bubble, white: agent's last message (trimmed to 40 chars)
- Error → `say` bubble, red: "MISS: -$50"

**Bitmap text required** (not regular Text) — PixiJS performance tip: regular Text redraws canvas every frame change. Use `BitmapText` with Press Start 2P bitmap font.

---

## 6. VISUAL POLISH STANDARDS

### 6.1 Day/Night Cycle

**Phaser approach (also applicable to PixiJS):**
```typescript
// Overlay a dark rectangle on the world container
// Tween alpha 0→0.6 over 30s (accelerated time: 1 game day = 4 real minutes)
const nightOverlay = new PIXI.Graphics()
nightOverlay.beginFill(0x001133, 1)
nightOverlay.drawRect(0, 0, WORLD_WIDTH, WORLD_HEIGHT)
nightOverlay.alpha = 0  // daylight

// Tween via GSAP or custom lerp
// At night: add point lights around monitors (orange glow circles, alpha 0.3)
```

**Visual phases:**
- 00:00–06:00 (game): Deep night, agents sleep, servers glow blue
- 06:00–18:00: Daylight, full activity
- 18:00–22:00: Evening, orange tint, trading floor lights up
- 22:00–00:00: Night, reduced activity, 40% agents sleeping

### 6.2 Particle Effects

| Event | Effect | Implementation |
|-------|--------|----------------|
| Win prediction | Gold confetti burst (20 particles) | PixiJS ParticleContainer |
| Big win (>$1000) | Fireworks (3 bursts) | Emitter with gravity |
| Loss | Gray smoke puff | 5 rising particles, fade out |
| Agent thinking | `...` dots float up | 3 particles, slow rise |
| Sleeping | Zzz rising | 2-3 'z' chars, drift right + fade |
| Error | Red ! pop | Scale 0→2→1, quick |
| Level up / new champion | Star burst + rank text | Full-screen momentary flash |

**PixiJS ParticleContainer:** Up to 100k sprites with zero overhead — use for all particles. Key: all particles in same container share one draw call.

```typescript
const particles = new PIXI.ParticleContainer(1000, {
  scale: true, position: true, alpha: true, tint: true
})
```

### 6.3 Camera / Viewport

**Recommended approach: Scrollable world + fixed HUD**

```
Canvas (1920×1080 logical)
├── WorldContainer (2560×1920, scrollable)
│   ├── TileLayer (floors, walls)
│   ├── PropLayer (furniture, desks)
│   ├── AgentLayer (207 sprites)
│   └── EffectLayer (particles, bubbles)
└── HUDContainer (fixed, always on top)
    ├── Minimap (top-right, 200×150)
    ├── Ticker (bottom, full width)
    ├── Leaderboard (top-left, 200px wide)
    └── EventFeed (right side, 250px)
```

**Smooth camera scroll:**
```typescript
// Lerp camera to follow active trader or clicked agent
camera.x += (targetX - camera.x) * 0.08  // AgentOffice formula
camera.y += (targetY - camera.y) * 0.08
```

**Viewport culling:** Only render agents within camera bounds + 2-tile buffer. PixiJS `cullable = true` per agent sprite, or manual check:
```typescript
const isVisible = (agent) =>
  agent.x > camera.x - TILE && agent.x < camera.x + VIEW_W + TILE &&
  agent.y > camera.y - TILE && agent.y < camera.y + VIEW_H + TILE
```

### 6.4 Minimap

**Phaser built-in pattern (also PixiJS equivalent):**
```typescript
// Second camera at 0.2x zoom, rendered to texture
// In PixiJS: RenderTexture updated every 10 frames (not every frame)
const minimapTexture = PIXI.RenderTexture.create({ width: 200, height: 150 })

// Each agent = 2×2 colored dot on minimap
// Color = dept color (research=blue, engineering=green, trading=red)
```

### 6.5 UI Overlay Patterns

**Ticker tape (STONKS-9800 style):**
```typescript
// CSS marquee or PixiJS BitmapText scrolling left
// Content: "NBA: LAL +4.5 → 63% | GSW ML → 71% | D1-Gemini: +$1,204 | D5-Grok: -$88 | ..."
// Green for positive, red for negative, white for neutral
// Font: Press Start 2P, 8px, scanline effect via CSS
```

**Leaderboard panel (top-left):**
```
┌─────────────────────┐
│ TRADERS LEADERBOARD │
├─────────────────────┤
│ 1 🥇 Gemini  $302K  │
│ 2 🥈 Grok    $210K  │
│ 3    Claude  $185K  │
│ 4    OR      $142K  │
│ 5    Codex    $98K  │
└─────────────────────┘
```

**Event feed (right side):**
- Last 10 events, newest at top
- Fade out old events after 30s
- Color-coded by type (win=gold, loss=red, info=white)

### 6.6 Sound Design (optional, chiptune)

**Sources:**
- itch.io: [Top assets tagged chiptune + pixel-art](https://itch.io/game-assets/tag-chiptune/tag-pixel-art)
- itch.io: [JDSherbert Pixel Explosions SFX Pack](https://jdsherbert.itch.io/pixel-explosions-sfx-pack) (80 sounds, free)
- Use Howler.js for Web Audio API management

**Sound events:**
- Agent walks: soft footstep tick (muted by default)
- Win: 3-note ascending chiptune fanfare
- Big win: 8-note victory jingle
- Error: descending bloop
- New trading day: gentle clock chime
- Background: ambient office hum (looping)

---

## 7. FREE ASSET SOURCES

### 7.1 Primary (use these)

| Asset | Source | License | What |
|-------|--------|---------|------|
| **JIK-A-4 Metro City** | Already in pixel-agents repo | MIT | 6 diverse character sprites, office furniture |
| **LimeZu Modern Office** | [limezu.itch.io/modernoffice](https://limezu.itch.io/modernoffice) | Commercial OK, attr required | 300+ office sprites: desks, PCs, chairs, dividers — $2.50 |
| **LimeZu Modern Interiors** | [limezu.itch.io/moderninteriors](https://limezu.itch.io/moderninteriors) | Commercial OK, attr required | Extensive interior pack; office NOT included (buy both) |
| **Kenney Game Assets** | [kenney.nl/assets](https://kenney.nl/assets) or [kenney.itch.io](https://kenney-assets.itch.io/) | CC0 (no attribution) | 60k+ assets, Tiny City pack, top-down characters |
| **OpenGameArt Interior 16×16** | [opengameart.org/content/interior-tileset-16x16](https://opengameart.org/content/interior-tileset-16x16) | CC0 | Interior tileset with Tiled sample map |
| **Anokolisa Free Pack** | [anokolisa.itch.io/free-pixel-art-asset-pack-topdown-tileset-rpg-16x16-sprites](https://anokolisa.itch.io/free-pixel-art-asset-pack-topdown-tileset-rpg-16x16-sprites) | Free | 500+ sprites, 3 heroes, 8 enemies |
| **Press Start 2P** | Google Fonts | OFL | Pixel font for all UI text |
| **VT323** | Google Fonts | OFL | Terminal-style pixel font for tickers |

### 7.2 Color Palettes

| Palette | Colors | Source | Use |
|---------|--------|--------|-----|
| PICO-8 | 16 | lospec.com/palette-list/pico-8 | Strict retro |
| **Sweetie-16** | 16 | lospec.com/palette-list/sweetie-16 | Warm office tones (recommended) |
| Endesga-32 | 32 | lospec.com/palette-list/endesga-32 | More range, still coherent |

### 7.3 AI-Assisted Sprite Generation (2025-2026)

- **Stable Diffusion 3.5 + PixelLock** — grid-aligned edges, enforced palette limits
- **Sprite-AI** (sprite-ai.art) — purpose-built for walk cycles and sprite sheets
- Workflow: Generate 20 variants → pick 3 → refine in Aseprite/Piskel → palette-constrain
- For unique tier-5 agent portraits: AI-generate, then hand-pixel 32×32 version

---

## 8. PERFORMANCE OPTIMIZATION (207 sprites target)

### 8.1 Rendering Architecture

**Target: 60fps with 207 animated agents + particles + HUD**

At 207 sprites, PixiJS handles this trivially. The bottleneck is NOT rendering; it is state update logic per frame. Keep the game loop lean.

### 8.2 Sprite Batching (most important)

**PixiJS batches sprites automatically if they share a texture atlas.**

Rules:
1. Pack ALL agent sprites into ONE spritesheet (TexturePacker or free.texturepacker.com)
2. Pack ALL tile textures into ONE tileset PNG
3. Max 16 different textures per batch — you have floor tiles + agent sheet + UI = 3 textures → single batch
4. Never mix blend modes in same layer (breaks batching)
5. Group by draw order: tiles first, then agents, then effects, then HUD

```typescript
// GOOD: single spritesheet, single draw call for all agents
const sheet = await Assets.load('agents-spritesheet.json')
agents.forEach(a => {
  a.sprite = new Sprite(sheet.textures[`${a.type}_walk_0.png`])
})

// BAD: individual PNG per agent = 207 draw calls
agents.forEach(a => {
  a.sprite = new Sprite(await Assets.load(`agent_${a.id}.png`))
})
```

### 8.3 Culling Off-Screen Agents

```typescript
// Check every 10 frames (not every frame)
let frame = 0
app.ticker.add(() => {
  frame++
  if (frame % 10 === 0) {
    agents.forEach(agent => {
      agent.sprite.visible = isInViewport(agent, camera)
    })
  }
  // Update positions every frame for smoothness
  agents.forEach(agent => {
    if (agent.sprite.visible) updateAgentAnimation(agent)
  })
})
```

### 8.4 Object Pooling

Pre-allocate speech bubbles, particles, and path markers:
```typescript
class SpeechBubblePool {
  pool: SpeechBubble[] = []
  get(): SpeechBubble {
    return this.pool.pop() || new SpeechBubble()
  }
  release(b: SpeechBubble) {
    b.reset(); this.pool.push(b)
  }
}
```

### 8.5 Animation Optimization

- **Do NOT animate off-screen agents** — check visible flag before updating frame index
- **Stagger update ticks**: Agents are split into 4 groups, each updated on alternating frames
  ```typescript
  // Group 0: updates on frames 0,4,8...
  // Group 1: updates on frames 1,5,9...
  // Reduces CPU per frame by 75% for state machine logic
  agents[i].updateGroup = i % 4
  app.ticker.add(() => {
    const group = Math.floor(Date.now() / 16) % 4
    agents.filter(a => a.updateGroup === group).forEach(updateAgent)
  })
  ```
- **Bitmap text for all labels**: Never use `new PIXI.Text()` for dynamic values — use `BitmapText`
- **CacheAsBitmap** for static furniture props — they never animate
  ```typescript
  deskSprite.cacheAsBitmap = true  // Huge win for 200+ static props
  ```

### 8.6 WebGL vs Canvas 2D

**Always use WebGL (PixiJS default). Never fall back to Canvas 2D for 200+ sprites.**

For older devices (mobile fallback): Reduce to 50 visible agents + lower resolution canvas.

### 8.7 State Update Budget

```
Frame budget at 60fps: 16.7ms
  Rendering (PixiJS):    ~3ms  (GPU-bound, very fast)
  Agent FSM updates:     ~2ms  (207 state machines, staggered)
  Pathfinding:           ~1ms  (pre-computed BFS, cached paths)
  Particle updates:      ~1ms  (pooled, simple physics)
  Network/data sync:     ~0ms  (async, never blocks render loop)
  TOTAL:                 ~7ms  (50% headroom for UI + GC)
```

### 8.8 Network: Never block the render loop

```typescript
// GOOD: async data fetch, update agent state when ready
setInterval(async () => {
  const state = await fetch('/api/agents').then(r => r.json())
  agentStateQueue.push(state)  // process on next tick
}, 4000)  // poll every 4s

app.ticker.add(() => {
  if (agentStateQueue.length) {
    const update = agentStateQueue.shift()
    applyStateUpdate(update)  // fast, synchronous state apply
  }
  renderAgents()
})
```

### 8.9 requestAnimationFrame Best Practices

- Never use `setInterval` or `setTimeout` for animation — use `app.ticker` (PixiJS wrapper for rAF)
- PixiJS ticker automatically pauses when tab is hidden (Page Visibility API)
- Use `PIXI.Ticker.shared` for non-render updates that must stay in sync
- Separate ticker for HUD animations (can run at 30fps) vs world at 60fps

---

## 9. IMPLEMENTATION STACK (Final Recommendation)

```
Next.js 15 App Router (Vercel)
├── @pixi/react v8 (PixiJS 8 + React 19)
│   └── Dynamic import with ssr: false
├── Tailwind CSS 4 (HUD chrome + panels)
├── Pixelact UI (pixel-art shadcn components)
├── Howler.js (chiptune SFX, optional)
└── WebSocket to bloomberg-api.py (port 8042)
    └── Miniverse-style agent state protocol
        (heartbeat every 15s, act on events)
```

### File Structure

```
hf-pixel-world/  (or app/trading-floor/)
├── components/
│   ├── PixelWorld.tsx          # Main PixiJS canvas (dynamic import)
│   ├── AgentSprite.tsx         # Single agent: FSM + animation
│   ├── SpeechBubble.tsx        # Bitmap text + Graphics bubble
│   ├── WorldMap.tsx            # Tile renderer from world.json
│   ├── Minimap.tsx             # RenderTexture minimap
│   └── HUD/
│       ├── Ticker.tsx          # Scrolling predictions
│       ├── Leaderboard.tsx     # Top 5 trader rankings
│       └── EventFeed.tsx       # Win/loss stream
├── engine/
│   ├── pathfinding.ts          # BFS on walkability grid
│   ├── fsm.ts                  # AgentState machine
│   ├── particlePool.ts         # Object pool for effects
│   └── agentSync.ts            # WebSocket ↔ agent state
├── assets/
│   ├── agents-spritesheet.json # TexturePacker atlas
│   ├── agents-spritesheet.png  # All 207 agent types
│   ├── office-tileset.png      # LimeZu Modern Office
│   └── world.json              # Miniverse-format world
└── data/
    ├── arena/agent-states-v5.json
    └── nba-agent/bankroll-state.json
```

---

## 10. QUICK-START IMPLEMENTATION ORDER

**Phase 1 — Scaffold (Day 1, 4h)**
1. Clone pixel-agents base, strip VS Code extension, keep Canvas 2D renderer
2. Replace with PixiJS 8 + @pixi/react — use ClawBoard pattern for Next.js integration
3. Load LimeZu Modern Office tileset, render static world

**Phase 2 — Agents (Day 2, 6h)**
1. Load 5 named trader sprites (Gemini/Grok/Claude/OpenRouter/Codex)
2. Implement FSM: idle→walk→work
3. BFS pathfinding on office grid
4. Speech bubbles via BitmapText

**Phase 3 — Data (Day 3, 4h)**
1. WebSocket to bloomberg-api.py
2. Wire agent states to real prediction events
3. Win/loss particle effects
4. Ticker tape with live predictions

**Phase 4 — Polish (Day 4, 4h)**
1. 207 agents (bulk, procedural colors)
2. Day/night cycle tint
3. Minimap
4. Leaderboard + event feed HUD

**Phase 5 — Performance (Day 5, 2h)**
1. Texture atlas packing (TexturePacker or free.texturepacker.com)
2. Culling pass
3. Animation staggering
4. Profile: should hit 60fps well before optimization

---

## 11. DESIGN PRINCIPLES (never violate)

1. **One spritesheet** — all agent types in one atlas. Zero per-agent PNG loads.
2. **FSM not spaghetti** — every agent behavior is one of 8 states. No exceptions.
3. **BitmapText only** — no canvas-drawn Text for dynamic values.
4. **Async everything** — data fetch never blocks render loop.
5. **32×32 agents on 16×16 tiles** — characters are 2 tiles tall. Standard.
6. **Sweetie-16 palette** — all sprites must use colors from this palette.
7. **Culling at 10-frame intervals** — not every frame (wasted CPU).
8. **PixiJS tint for tiers** — one base sprite, seven tier tints. Not seven sprites.
9. **Press Start 2P for ALL text** — consistency. BitmapFont loaded once.
10. **CacheAsBitmap for furniture** — static props are free after first frame.

---

## Sources

- [pixel-agents (pablodelucca)](https://github.com/pablodelucca/pixel-agents) — 6.1k stars, base reference
- [AI Town (a16z-infra)](https://github.com/a16z-infra/ai-town) — pixi-react, Convex sync
- [AI Town Architecture](https://github.com/a16z-infra/ai-town/blob/main/ARCHITECTURE.md)
- [agent-town (geezerrrr)](https://github.com/geezerrrr/agent-town) — Next.js 16 + Phaser 3
- [AgentOffice (harishkotra)](https://dev.to/harishkotra/how-i-built-agentoffice-self-growing-ai-teams-in-a-pixel-art-virtual-office-4o0p)
- [Miniverse (ianscott313)](https://github.com/ianscott313/miniverse) + [docs](https://www.minivrs.com/docs/)
- [agentroom (liuyixin-louis)](https://github.com/liuyixin-louis/agentroom)
- [JS Game Rendering Benchmark](https://github.com/Shirajuki/js-game-rendering-benchmark)
- [PixiJS 8 Performance Tips](https://pixijs.com/8.x/guides/concepts/performance-tips)
- [@pixi/react v8 announcement](https://pixijs.com/blog/pixi-react-v8-live)
- [Phaser vs PixiJS comparison](https://generalistprogrammer.com/comparisons/phaser-vs-pixijs)
- [Aircada: PixiJS vs Phaser](https://aircada.com/blog/pixijs-vs-phaser)
- [Sprite-AI: 2D pixel art style guide](https://www.sprite-ai.art/blog/2d-pixel-art-style-guide)
- [Sprite-AI: Animation principles](https://www.sprite-ai.art/guides/animation-principles)
- [Grid Engine Pathfinding Performance](https://annoraaq.github.io/grid-engine/p/pathfinding-performance/index.html)
- [LimeZu Modern Office](https://limezu.itch.io/modernoffice) — $2.50
- [LimeZu Modern Interiors](https://limezu.itch.io/moderninteriors)
- [Kenney Game Assets](https://kenney.nl/assets)
- [OpenGameArt Interior 16x16](https://opengameart.org/content/interior-tileset-16x16)
- [Anokolisa Free Topdown Pack](https://anokolisa.itch.io/free-pixel-art-asset-pack-topdown-tileset-rpg-16x16-sprites)
- [itch.io chiptune + pixel-art assets](https://itch.io/game-assets/tag-chiptune/tag-pixel-art)
- [JDSherbert Pixel Explosions SFX](https://jdsherbert.itch.io/pixel-explosions-sfx-pack)
- [Phaser Minimap Camera](https://phaser.io/examples/v3/view/camera/minimap-camera)
- [Phaser Day/Night Cycle](https://www.joshmorony.com/how-to-create-a-day-night-cycle-in-phaser/)
- [STONKS-9800 on Steam](https://store.steampowered.com/app/1539140/STONKS9800_Stock_Market_Simulator/)
- [Lospec Palette List](https://lospec.com/palette-list)
- [Sprite-AI Best Generators 2026](https://www.sprite-ai.art/blog/best-pixel-art-generators-2026)
- [Crisp pixel art on MDN](https://developer.mozilla.org/en-US/docs/Games/Techniques/Crisp_pixel_art_look)
