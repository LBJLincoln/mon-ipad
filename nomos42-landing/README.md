# Handoff: Nomos42 — AI Agent Security Landing Page

## Overview
A dark, cinematic single-page marketing site for **Nomos42**, a sovereign security product for agentic AI. The product positions itself as **two layers in one product**: a **Red Team** (autonomous offensive agents that attack your AI) and a **Guard** (runtime defense deployed inside your environment), plus a sovereign, signed audit layer. The page is a long-scroll narrative: hook → live attack/defense demos → product breakdown → coverage → CTA.

## About the Design Files
The files in this bundle are **design references created in HTML/React-via-Babel** — prototypes that show the intended **look, motion, and behavior**. They are **not** production code to drop in as-is (they transpile JSX in the browser with `@babel/standalone`, which is fine for a prototype but not for production).

Your task is to **recreate these designs in the target codebase's environment** using its established patterns, component library, and build tooling. If there is no existing environment yet, pick an appropriate modern stack (e.g. Next.js/React + CSS Modules or Tailwind, or Astro for a static marketing site) and implement the designs there. Match the visuals and motion precisely; re-architect the code to production standards (real bundler, no in-browser Babel, componentized, accessible).

## Fidelity
**High-fidelity (hifi).** Final colors, typography, spacing, motion, and interactions are all specified here and in the CSS. Recreate the UI pixel-perfectly, then wire the interactive demos to the same behavior. All "data" in the demos is illustrative/mocked — there is no backend.

---

## Tech at a glance (prototype)
- **React 18** (UMD) + **ReactDOM**, JSX transpiled in-browser by **@babel/standalone**. Each section is a separate `*.jsx` file loaded via `<script type="text/babel">`; components attach to `window` (e.g. `window.Hero`, `window.Squad`) so sibling files can use them.
- **One global stylesheet** `styles.css` (no CSS framework). Heavy use of CSS custom properties, `clamp()` fluid type, CSS grid/flex with `gap`, and keyframe animations.
- **Font:** "Sora" (Google Fonts, weights 300–700).
- **Tweaks panel** (`tweaks-panel.jsx`): an optional in-page control panel (accent color, density, hero headline) used during design review. It persists to `localStorage` and talks to a host via `postMessage`. **This is a prototyping tool — you can omit it in production**, but keep the underlying theming hooks (accent color + density as CSS variables) if you want a themeable build.

---

## Design Tokens

All tokens live in `:root` in `styles.css`. Reproduce them as your theme.

### Colors
| Token | Value | Use |
|---|---|---|
| `--bg` | `#000000` | Page background (true black) |
| `--bg-1` | `#050505` | Alt section background |
| `--bg-2` | `#0A0A0A` | Panels / stages |
| `--bg-3` | `#111111` | Raised surfaces |
| `--bg-card` | `#0C0C0D` | Cards |
| `--fg` | `#FFFFFF` | Primary text |
| `--fg-2` | `#B6B6B8` | Secondary text |
| `--fg-3` | `#7A7A7C` | Tertiary / labels |
| `--fg-4` | `#4A4A4C` | Faint / disabled |
| `--line` | `rgba(255,255,255,0.06)` | Hairline dividers |
| `--line-2` | `rgba(255,255,255,0.10)` | Borders |
| `--line-3` | `rgba(255,255,255,0.18)` | Stronger borders |
| `--accent` | `#E8FFF6` (cool white) | Brand accent / glow. **Themeable** |
| `--accent-rgb` | `232, 255, 246` | RGB form for `rgba()` glows |
| `--signal-bad` | `#FF5A4E` | Threat / critical (red) |
| `--signal-warn` | `#FFB547` | Warning (amber) |
| `--signal-good` | `#6BE6A6` | Safe / blocked-by-guard (green) |
| `--bad-rgb` | `255, 90, 78` | Red glow base |
| `--warn-rgb` | `255, 181, 71` | Amber glow base |
| `--good-rgb` | `107, 230, 166` | Green glow base |

Accent options offered in the prototype: `#E8FFF6` (default), `#7DF9FF` (cyan), `#FF8A3D` (orange), `#39FF7A` (green). Changing `--accent`/`--accent-rgb` re-themes all glows.

### Typography
- **Family:** `'Sora', system-ui, sans-serif`. Logo monogram uses a **serif** (`'Times New Roman', Georgia, serif`) for the imperial "N".
- **Feature settings:** `"ss01","ss02","tnum"`; tabular numerals via `.tlog` (`font-variant-numeric: tabular-nums`) for all metrics/logs.
- **Display H1** `.h-display`: `clamp(40px, 7.2vw, 116px)`, weight 500, line-height 0.94, letter-spacing -0.035em.
- **Section H2** `.h-section`: `clamp(34px, 5vw, 72px)`, weight 500, line-height 1.0, letter-spacing -0.03em.
- **Eyebrow** `.h-eyebrow`: 12px, uppercase, letter-spacing 0.24em, with a pulsing accent dot.
- **System label** `.sys-label` / `.coverage-n` etc.: 10–11px, uppercase, letter-spacing 0.2–0.24em, `--fg-3`.
- **Lede** `.lede`: `clamp(16px, 1.4vw, 20px)`, line-height 1.5, `--fg-2`, max-width ~56ch.
- Emphasis pattern: in headings, `<em>` is **not italic** — it's `font-style: normal; color: var(--fg-3)` (a dimmed second clause). The hero headline splits on `//` into a bold line + a dimmed line.

### Spacing / layout
- `--pad: clamp(20px, 4vw, 80px)` — page gutter.
- `--grid: 1280px` — max content width. Container = `min(var(--grid), 100% - var(--pad)*2)`, centered.
- Section vertical rhythm via density: `--section-pad` = **180px (airy) / 140px (default) / 90px (dense)**, set by `body[data-density=…]`.
- Radii: cards/panels `6px`, large frames `10–12px`, pills `999px`.
- Standard panel: `1px solid var(--line)` border, `var(--bg-card)` bg, `6px` radius.

### Shadows / glows
- Big frame shadow (dashboard): `0 80px 160px -40px rgba(0,0,0,0.85), 0 0 0 1px rgba(255,255,255,0.02), 0 0 120px -60px rgba(var(--accent-rgb),0.25)`.
- Accent glow on hover: `0 0 50px rgba(var(--accent-rgb),0.25)`.
- Signal glows use the matching `--bad/warn/good-rgb`.

### Motion
- Primary easing `--ease: cubic-bezier(.2,.7,.2,1)`; cinematic `--ease-cine: cubic-bezier(.16,.84,.24,1)`.
- **All decorative motion must be gated behind `@media (prefers-reduced-motion: no-preference)` / disabled under `reduce`** — the stylesheet already does this; preserve it.

---

## Global Atmosphere (cinematic layer)
Applied site-wide via `body::before` / `body::after` (see "CINEMATIC + ATTACK-URGENCY LAYER" in `styles.css`):
- **Film grain**: fixed full-viewport animated fractal-noise SVG, `opacity ~0.045`, `pointer-events:none`.
- **Lens vignette**: fixed radial gradient darkening the frame edges.
- **Breathing bloom**: hero & CTA radial glows scale/opacity-pulse on a slow loop.
- Recreate these as two non-interactive fixed overlay layers above content; keep them subtle.

---

## Screens / Sections (in scroll order)

> All sections are full-width `<section class="section …">` with an inner `.container`. Most lead with a two-column `.section-head` (eyebrow on the left, H2 + lede on the right; collapses to one column < 880px).

### 0. Nav (`app.jsx` → `Nav`)
- Fixed top bar, `z-index:50`, blurred translucent black gradient background (`backdrop-filter: blur(14px) saturate(140%)`).
- Left: **logo** = imperial **"N" monogram** (serif N inside a circular double-ring, accent-colored, subtle glow) + wordmark **"NOMOS42"** (14px, uppercase, letter-spacing 0.18em, weight 600).
- Center: links — **Red Team · Guard · Coverage · Trust** (13px, `--fg-2`, hover → `--fg`). Hidden < 760px.
- Right: pill CTA **"Book a briefing"** (border pill; hover fills with accent, text → black).

### 1. Hero (`hero.jsx`)
- Full-viewport (`min-height:100vh`), content bottom-aligned. Layered backgrounds: faint **grid** (80px, radial-masked), **bloom** glow, and an animated **ambient node graph** (SVG: 8 drifting nodes connected when close — `requestAnimationFrame` loop).
- Top row: eyebrow "Agentic AI Security · Sovereign · EU-hosted" + a `.tlog` location/clock line; on the right two buttons — primary **"Book a briefing →"**, ghost **"Read the brief"**.
- **Headline** `.h-display.glow-text`: **"Protect your AI agents"** (white) / **"and workflows."** (dimmed `<em>`). Driven by a `headline` string split on `//`; subtle accent text-shadow. (Editable via Tweaks in the prototype.)
- Lede paragraph (the "one product, two layers" pitch).
- **Readout**: 4-column stat strip (`.hero-readout`), collapses to 2 cols < 720px. Stats: "Specialized agents 8", "Attack classes 200+", "Runtime intercept 12ms", "Data residency EU". Each = uppercase label + big `.tlog` value with a dimmed unit.

### 2. Marquee (`sections.jsx` → `Marquee`)
- Full-width hairline-bordered strip; infinite horizontal scroll (`@keyframes marquee`, 36s linear) of uppercase compliance/keyword chips separated by a small ◆.

### 3. Live Intercept (`intercept.jsx`)
- **Cinematic 4-step looping demo** of an agent being compromised and contained. Steps: `01 Idle → 02 Inject → 03 Scan → 04 Contain` (auto-advances; clicking a step pill pauses auto and jumps).
- A large `.intercept-stage` (clamped height 420–640px, bordered, radial bg) holds an **SVG scene**: human → agent → shield → resource, with scan beams, an agent that turns from accent-glow to **red** when breached, attack particles, and a shield/quarantine state.
- Stage gets state classes: `.under-attack` (steps 1–2) → frame flares **red** + throb animation; `.contained` (step 3) → frame settles **green**. A scanning sweep beam animates across the stage.
- Caption (bottom): current state + detail on the left; `T+NNNms` timer + session id on the right.

### 4. Threat Surface — MAP (`surface.jsx`)
- Eyebrow "Map · 04". H2 "Every agent is an attack surface / we render it as one."
- `.surface-canvas` (clamped 440–680px): an **SVG force-graph** — central **TENANT** square, orbiting **agent** nodes (circle; stroke = risk: red/amber/accent; high-risk pulses), outer **data/resource** nodes (square with "document" lines). Edges colored by risk; high/medium edges have a particle traveling along them (`<animateMotion>`). Concentric dashed rings behind.
- **MAP HUD treatment (CSS):** faint coordinate-grid backdrop (96px + 24px grids, radial-masked), focal vignette (inset shadow), corner **frame brackets** on `.surface-wrap`, and floating glass **HUD chips** for the legend (high/med/low swatches) and the meta label. A scanning sweep beam crosses the canvas.
- Below: 4-column stat strip ("Total reachable systems 142", "Cross-tenant edges 3" [red], "Avg permissions/agent 8.2", "Detected drifts (24h) 11").

### 5. Squad — THE TWO LAYERS (`squad.jsx`)
- Eyebrow "Two layers, one product · 07". H2 "A red team that attacks. / A guard that protects."
- **`.twolayer` cinematic CSS diagram** (no SVG — pure HTML + keyframes), the centerpiece of the two-layer story:
  - Center: circular **"AI" core** (serif glyph) labeled "agent secured", accent glow.
  - Around it: a green dashed **Guard shield ring** ("L2 · Guard" tag) that slowly rotates and breathes.
  - Outer: faint red **perimeter rings** ("L1 · Red Team" tag) and **8 attack spokes** rotated at 45° increments. Each spoke has a red **streak** that fires inward from the rim and **flashes out at the shield membrane** (staggered `animation-delay`), plus a tiny uppercase attack-vector label (Prompt injection, Tool abuse, Jailbreak, RAG exfil, Excessive agency, Supply chain, Crescendo, Data extraction).
  - Right column copy: red bullet "The red team finds every way in…", green bullet "The Guard shuts each one down inline, in **12 ms**…", and a strong closing line "One product. Two layers. Zero standing exposure."
  - Geometry note: spoke = 50% of stage width, `transform-origin:0 50%`, rotated; streak animates `right: 0% → 38%` so it dies exactly at the 62%-diameter shield. Collapses to single column < 860px; streaks freeze at mid-radius under reduced-motion.
- **Squad grid**: 4-col (→2 < 980px) of 8 agent cards — 4 `layer:'red'` (Red Team), 4 `layer:'guard'` (Guard). Each card: glyph badge, a red/green "Red Team"/"Guard" chip, role title, footer with KPI value/label. Hover/click sets the active card (accent edge + glow).
- **Focus panel** below the grid (1.4fr/1fr): left = active agent's layer·role, big role title, description; right = a KPI (label/value) and a "Last 60 seconds" list of `.tlog` activity bullets.

### 6. Coordination — RED TEAM OPS (`coordination.jsx`)
- Eyebrow "Red Team · Continuous · 08". H2 "Every attack class. / Fired at your AI, on repeat."
- **`.redops-console`**: a live attack-matrix console (frame styled like the dashboard, with a grid backdrop and a subtle red inner glow).
  - **Top bar**: pulsing **LED** (red = "RED TEAM ACTIVE · target: ops-bot-3"; turns green + "ASSESSMENT COMPLETE · SYSTEM HARDENED" when done) + running counters (blocked / findings→patched / classes tested).
  - **Progress bar** (red→accent gradient) tracks % of classes tested.
  - **Phase matrix**: responsive grid (`repeat(auto-fill, minmax(220px,1fr))`) of **7 phases** (P1 Recon … P7 Pivot, each with its OWASP/ATLAS tag). The active phase highlights (accent inset edge). Each phase lists its **attack classes** as rows: a status **dot** + name + status text. Row states: default ("—"), **`.firing`** (red, pulsing, "TESTING" — an attack being fired now), **`.blocked`** (green dot, "BLOCKED"), **`.finding`** (amber dot, "PATCHED").
  - **Live payload feed**: newest-first rows (code · name · `↳ vector` · verdict), verdict colored green/amber.
  - **Footer**: result summary + ghost buttons **"↻ Re-run"** and **"❚❚ Pause / ▶ Resume"**.
  - Behavior: a timer steps through all 23 classes (~360ms each), assigning a verdict (~88% blocked, ~12% finding→patched), updating the matrix, feed, counters, and active phase; loops after a pause when complete.

### 7. Dashboard (`dashboard.jsx`)
- A faux SOC web-app inside a browser-chrome frame (`.dashboard-frame` with the big cinematic shadow). Left **sidebar** nav (Overview/Agents/Threats[badge "7", pulsing red]/Policies/Audit log); main area: topbar, **4 KPI cards** (one `.alert` KPI breathes red), an **agent table** (risk bars + status pills; `.bad` pills ember-glow), a **live threat feed** (`.bad` rows get a blinking red alert rail), a **sparkline**, plus extra panels: a **gauge ring** (SVG), a 24-col **heatmap**, and a labeled **distribution bar** set. Numbers animate/update on an interval.

### 8. Globe — GLOBAL OPS MAP (`globe.jsx`)
- Eyebrow "Sovereign footprint · 09". H2 "Your region. / Your tenancy. Your sovereignty."
- `.globe-grid` (2fr/1fr → 1col < 980px): left **`.globe-canvas`** = SVG **dot-grid world map** (abstract continents) with ~12 city **sites** (pulsing rings, labels) and severity-colored **arc links** with traveling particles; right **`.globe-feed`** = live event list (site · message · severity tag CRIT/WARN/OK), prepended on an interval.
- Same **MAP HUD treatment** as the Threat Surface (coordinate grid, focal vignette, glass meta chip).

### 9. Coverage (`coverage.jsx`)
- Eyebrow "Coverage · 10". H2 "One product. / Test. Protect. Prove."
- 3-col card grid (→1col < 880px): **L1 Test — Red Team**, **L2 Protect — Guard**, **L3 Prove — Sovereign**. Each card: number tag, sys-label lead, title, sub, description, and a bulleted list (bullets prefixed with an accent "→").
- Below: a wrap **logo/keyword strip** (`.coverage-strip`) of integrations & frameworks (OpenAI, Anthropic, Bedrock, Azure AI, LangChain, MCP, browser-use, Ollama, OWASP LLM, MITRE ATLAS, NIST AI RMF, EU AI Act).

### 10. Protocol (`sections.jsx` → `Protocol`)
- 3-step grid (hairline-separated, each `min-height:460px`): numbered step, title, paragraph, and a bottom uppercase "visual" meta line. Hover darkens the cell.

### 11. CTA (`sections.jsx` → `CTA`)
- Centered, with a bottom-anchored radial **bloom** (breathing). Big H2 (`clamp(40px,6vw,96px)`, dimmed `<em>` clause), centered button row. Copy: design-partner pitch ("Bring your most adversarial AI workload — we'll bring the red team and the guard.").

### 12. Footer (`sections.jsx` → `Footer`)
- 4-col link grid (→2col < 720px): brand block (N monogram + wordmark + one-liner) and Platform / Company / Trust columns. Below, a `.footer-bottom` bar: "© 2026 Nomos42" + a `.tlog` "v1.0 · EU-hosted · sovereign".

---

## Interactions & Behavior (summary)
- **Intercept**: auto-looping 4-step state machine (3s/step, 4.2s on contain); step pills pause + jump. Stage frame color reflects state.
- **Squad**: hover/click a card → sets active agent → updates the focus panel. Two-layer diagram is autonomous CSS animation.
- **Red Team Ops**: interval-driven run through 23 attack classes; Re-run resets; Pause/Resume toggles the timer.
- **Dashboard / Globe**: interval-driven mock updates (feeds prepend, numbers tick). All data is fake.
- **Hero ambient graph**: rAF loop animating node positions + proximity links.
- **Nav CTA / buttons / cards**: hover transitions (~0.25s) — accent fill, glow, slight lift.
- **Responsive**: documented breakpoints 980 / 880 / 860 / 760 / 720px collapse multi-column grids to fewer columns; nav links hide < 760px.
- **Reduced motion**: a `prefers-reduced-motion: reduce` block disables grain, bloom, sweeps, alarm pulses, attack streaks, etc. — keep this.

## State Management
Local component state only (React `useState`/`useEffect`), no external store, no network:
- `Intercept`: `step`, `auto`.
- `Squad`: `active` (agent id).
- `RedTeamOps`: `run` (index), `done` (id→verdict map), `feed` (array), `playing`, `activePhase`.
- `Globe`: `events` (array, interval-prepended).
- `Dashboard`: interval-updated metrics/feed.
- `Hero`: `t` (animation clock via rAF).
- `App`: theme tweaks `{ accent, density, headline }` → applied as CSS variables + `data-density` on `<body>` (prototype-only; keep if you want theming).

## Assets
- **Font:** Google Fonts "Sora" (300–700). In production, self-host or use your font pipeline.
- **No raster images or icon fonts.** All visuals are CSS or inline SVG drawn from data. The film-grain texture is an inline SVG `feTurbulence` data-URI.
- **No external logos shipped** — the integration strip is plain text labels.

## Files (in this bundle)
- `index.html` — document shell: fonts, `styles.css`, React/Babel script tags, and the ordered `<script type="text/babel">` includes.
- `styles.css` — **the entire design system + all section styles** (single source of truth for tokens, layout, and animation).
- `app.jsx` — `App` (theme state + Tweaks wiring), `Nav`, and the root render.
- `tweaks-panel.jsx` — prototype-only theming panel (safe to drop in production).
- `components/hero.jsx` — Hero + ambient node graph.
- `components/squad.jsx` — Squad grid/focus **+ the `TwoLayer` CSS diagram**.
- `components/intercept.jsx` — Live Intercept demo + SVG stage.
- `components/coordination.jsx` — Red Team Ops attack-matrix console.
- `components/dashboard.jsx` — SOC dashboard mock.
- `components/surface.jsx` — Threat Surface force-graph map.
- `components/globe.jsx` — Global ops map + live feed.
- `components/coverage.jsx` — Coverage cards + integration strip.
- `components/sections.jsx` — Marquee, Protocol, CTA, Footer.

> Tip for implementation: start from `styles.css` (it's framework-agnostic and carries all tokens, layout, and motion), then port each `*.jsx` section into your component model, keeping the class names so the CSS maps over directly.
