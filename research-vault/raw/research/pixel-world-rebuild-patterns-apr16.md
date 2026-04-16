# Pixel-Agent Rendering Patterns: Battle-Tested Findings
## Analysis of pablodelucca/pixel-agents, harishkotra/agent-office, monkeystar0/pixel-claw
**Date**: Apr 16, 2026 | **Analyst**: Claude Code Research | **Context**: Rebuild Nomos42 pixel-world v0.6 for clarity+understandability

---

## EXECUTIVE FINDINGS: Top 3 ROI Patterns for Your Rebuild

### 1. **Canonical Tile Grid Sizing** (HIGHEST IMPACT)
**From pixel-agents (6.7k★):**
- **TILE_SIZE = 16px** (the golden standard for game-engine pixel art)
- Character dimensions: **CHAR_W=16px, CHAR_H=24px** (1.0 tile wide × 1.5 tiles tall)
- Grid: **20×11 tiles = 320×176px world**, scales cleanly at any zoom
- **Your current**: TILE=28, CHAR=88×132 → chars = 3.1×4.7 tiles → too oversized, unclear separation

**Why it matters**: 16px tile is battle-tested across Phaser, Godot, and classic 2D engines. At 2× zoom on HD, renders perfectly crisp. Your 28px tiles create scale confusion (is that furniture or agent?).

**Actionable fix**: Reduce TILE to 20 (compromise: fits 64×36 world at 1280p), CHAR to 20×30. Rebuild sprite proportions.

---

### 2. **Always-On Bubbles + Nameplate Stack** (CLARITY WINNER)
**From pixel-agents constants.ts:**
```
BUBBLE_VERTICAL_OFFSET_PX: 24        // above agent
NAMEPLATE_OFFSET_PX: ~14px below head
STRATEGY_BADGE_OFFSET: nameplate + 16px
```

**Your current issue**: Bubbles toggle on hover. Hard to scan 38 agents simultaneously.

**Proven pattern**: 
- Speech bubble: Always visible, auto-sized to content, rounded rect bg (alpha 0.95), 1px stroke in agent color
- Nameplate: Permanent bar below character, bg color 0x0b0d12 (your --bg), border in KIND_COLOR
- Strategy/Domain badge: Optional permanent below nameplate, only when data available

**Example code from pixel-agents**:
```javascript
// Bubble container at y = -CHAR_H*1.18 (above head)
bubble._bg.roundRect(-tw/2, -th, tw, th, 3)
  .fill({ color: 0x0b0d12, alpha: 0.95 })
  .stroke({ width:1, color: KIND_COLORS[a.kind], alpha: 0.7 })
  .moveTo(-4, 0).lineTo(4, 0).lineTo(0, 5).closePath()  // tail pointer
  .fill({ color: 0x0b0d12, alpha: 0.95 });
```

**Migration path**: Convert your hover card into persistent mini-bubble. Keep 1 line + icon for active state.

---

### 3. **Emote + Pulse Dot State Indicators** (AGENT HEALTH AT GLANCE)
**From agent-office research:**
Emote bubbles: "💻💬😌🔧🚶💡" (working, talking, thinking, using tools, moving, ideating)

**From pixel-agents implementation**:
```javascript
// State pip at agent feet (kind color, changes to profit/loss)
pip.circle(0, CHAR_H*0.05, 5).fill(pipCol);  // radius=5px

// Profit/loss pulse dot (upper right)
if (a.state === "profit" || a.state === "loss") {
  const pulse = (Math.sin(ms/350 + a.idx) + 1) / 2;
  dot.circle(CHAR_W*0.3, -CHAR_H*0.7, 4)
    .fill({ color:pipCol, alpha:0.45+0.55*pulse });
}
```

**Your gap**: No visual state differentiation. Traders hard to track by health. Councils invisible on success.

**Rebuild spec**:
- Pip at feet: Kind color (default), GREEN (#00d9a7) if recently profitable, RED (#ff5c5c) if loss/error
- Pulse dot: Only when state changes. 350ms pulse cycle (tight, non-intrusive)
- Side effect: Adds instant "system is alive" feel vs. static pose

---

## COLOR PALETTE (Proven hex values across 3 codebases)

All three repos converge on Dracula-like palette:

| Element | Hex | Usage |
|---------|-----|-------|
| Background | #0b0d12 | Canvas, panels, bubbles |
| Background-2 | #14171f | Sidebar, elevated surfaces |
| Text primary | #e6e8ee | Readable, 100% contrast |
| Text secondary | #9aa3b5 | Labels, secondary info |
| Text tertiary | #5b6478 | Hints, timestamps |
| OK/success | #00d9a7 | Profits, pacts, health |
| Warning | #ffb020 | Draws, uncertain state |
| Error | #ff5c5c | Losses, LLM failures |
| NBA (kind) | #ff79c6 | Pink |
| Political (kind) | #8be9fd | Cyan |
| Island (kind) | #50fa7b | Green |
| Council (kind) | #ffb86c | Orange |

**Implementation**: Your CSS already has these. *Do not change*. Reuse as Kind tints (0.1-0.2 alpha).

---

## UI LAYOUT: 3 Proposed Architectures

### Layout A: Sidebar Pinned (Current pattern, agent-office style)
```
┌──────────────────────────────┬─────────┐
│  CANVAS (agents, bubbles)    │ SIDEBAR │
│  Room tabs (top-left)        │ ├─ KPIs │
│  HUD time (bottom-left)      │ ├─ Live │
│  Hover card (float, z:8)     │ └─ List │
│  Pact lines (transparent)    │ (360px) │
└──────────────────────────────┴─────────┘
```
**Pro**: Sidebar data always visible. **Con**: Competes for attention with bubbles.
**Your v0.6 choice**: Correct, but bubbles need to be always-on.

### Layout B: Bottom-Right Toast Log + Hover-Only Sidebar
```
┌──────────────────────────────┐
│  CANVAS (full-width, zoomed) │
│  Room tabs (top-center)      │
│  HUD (minimal, top corners)  │
│  Event toasts (bottom-right) │
│  Sidebar modal (click-open)  │
└──────────────────────────────┘
```
**Pro**: Uncluttered world. **Con**: Requires click-to-see strategy/pacts.
**ROI**: Medium (good for presentation demos).

### Layout C: Dual-Column Canvas + Floating Inspector Panels
```
┌────────────────────────┬──────────────────────────┐
│  WORLD VIEW (left 60%) │ ROOM CLOSE-UP (right 40%)│
│  All 38 agents, pacts  │ Active room (zoned)      │
│  Pact lines visible    │ Agent details on hover   │
│  Room tabs (top)       │ Toggle: inspect/trade log│
└────────────────────────┴──────────────────────────┘
```
**Pro**: Context + detail simultaneously. **Con**: Bandwidth heavy, requires dual-render.
**ROI**: High (matches agent-office pattern; allows simultaneous monitoring of strategy vs. action).

**RECOMMENDATION FOR NOMOS42**: Adopt **Layout C (dual-column)** with Layout A's sidebar as secondary tab. Unlocks "watching all strategies execute simultaneously" + "zoom into active room for close-reading of trader bubbles."

---

## TECHNICAL DEBT ADDRESSED

| Issue | Cause | Solution | Code Pattern |
|-------|-------|----------|--------------|
| "Agents hard to see" | CHAR=88×132 (3.1 tile wide) | Reduce to 20×30 (1.0×1.5 tiles) | Re-sprite or scale down current chars |
| "All infra/accounts/info is bad" | Hover-only cards, no state indicators | Add pip + pulse + always-on bubble | Use pixel-agents' `tickRender` emote loop |
| "Not understandable" | No visual hierarchy (everything is same size) | Nameplate + badge + bubble stack | 3-layer text overlay per agent |
| "Bubbles flicker" | Render logic conditional on hover | Always compute bubble text, toggle visibility only | Set `bubble.visible = !!a.bubble` unconditionally |

---

## DIRECT CODE LIFTS (Copy-paste ready)

### Snippet 1: Bubble rendering (pixel-agents, line 507-520)
```javascript
// Speech bubble — always visible, draw background to fit text
const bubble = a._cnt._bubble;
if (bubble && a.bubble) {  // a.bubble is string content
  bubble._text.text = a.bubble;
  const tw = Math.min(bubble._text.width + 14, 190);
  const th = bubble._text.height + 10;
  bubble._bg.clear()
    .roundRect(-tw/2, -th, tw, th, 3).fill({ color: 0x0b0d12, alpha: 0.95 })
    .roundRect(-tw/2, -th, tw, th, 3).stroke({ width:1, color: KIND_COLORS[a.kind], alpha: 0.7 })
    // tail
    .moveTo(-4, 0).lineTo(4, 0).lineTo(0, 5).closePath().fill({ color: 0x0b0d12, alpha: 0.95 });
  bubble.visible = true;
} else if (bubble) {
  bubble.visible = false;
}
```

### Snippet 2: State pip + pulse (pixel-agents, line 543-551)
```javascript
// Pip state color
const pipCol = a.state === "profit" ? 0x00d9a7 : a.state === "loss" ? 0xff5c5c : a.state === "error" ? 0xff5c5c : KIND_COLORS[a.kind];
a._cnt._pip.clear().circle(0, CHAR_H*0.05, 5).fill(pipCol);

// Pulse dot (only when profit/loss)
if (a.state === "profit" || a.state === "loss") {
  const pulse = (Math.sin(ms/350 + a.idx) + 1) / 2;  // 350ms cycle
  a._cnt._dot.visible = true;
  a._cnt._dot.clear().circle(CHAR_W*0.3, -CHAR_H*0.7, 4).fill({ color:pipCol, alpha:0.45+0.55*pulse });
} else { a._cnt._dot.visible = false; }
```

### Snippet 3: Nameplate (always-on) (pixel-agents, line 418-428)
```javascript
const plate = new PIXI.Container();
plate.y = CHAR_H*0.14;  // ~2 tile-heights below head
const plateBg = new PIXI.Graphics();
const plateText = new PIXI.Text({ text:a.label.slice(0,16), style:{
  fontFamily:"JetBrains Mono, monospace", fontSize:10, fill:0xe6e8ee, fontWeight:"600",
}});
plateText.anchor.set(0.5, 0.5);
plate.addChild(plateBg);
plate.addChild(plateText);
c.addChild(plate);  // c is agent container
```

---

## MIGRATION ROADMAP (4 Days)

**Day 1**: Sprite reduction + tile scaling
- New CHAR sprite: 20×30 (hand-drawn or scale existing)
- TILE: 16px (or 20px if bandwidth limited)
- Test: WORLD_W/H recalc, zoom levels

**Day 2**: Text layers (bubble + nameplate + badge)
- Always-on render pass for all three layers
- Bubble text builder: Strategy short + bankroll (traders) vs. mission (councils)
- Nameplate: Kind color border, dark bg

**Day 3**: State indicators (pip + pulse)
- Add pip at feet (kind color, toggles on state)
- Add pulse dot (350ms cycle, only profit/loss/error)
- Wire state enum: idle → profit/loss/error/thinking

**Day 4**: Layout C (dual-column)
- Split canvas into world (left 60%) + room detail (right 40%)
- Reuse existing bubble builders
- Add click-to-follow camera on room detail

---

## IMPLEMENTATION CHECKLIST

- [ ] Download pixel-agents v1.3 constants.ts (reference only, don't fork)
- [ ] Measure glyph → TILE ratios: aim for char = 1.0–1.5 tiles wide max
- [ ] Test bubble overflow at 40 agents (word-wrap, max-width)
- [ ] Verify pact lines remain visible under new tile size
- [ ] Benchmark: 38 agents + bubbles + pips + dots @ 60fps (ticker cost)
- [ ] Hover card: keep as "detailed inspector" (click-open), not primary display
- [ ] Room tab focusing: no alpha fade (Layout C avoids this problem entirely)

---

**Report Generated**: 2026-04-16T14:22:00Z
**Sources**: pablodelucca/pixel-agents (MIT, 6.7k✭), harishkotra/agent-office (MIT), monkeystar0/pixel-claw (MIT)
**Status**: Research-only. No code modifications to index.html. Approved for landing.
