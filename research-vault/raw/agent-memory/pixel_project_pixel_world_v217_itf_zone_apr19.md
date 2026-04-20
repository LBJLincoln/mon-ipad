---
name: pixel-world v2.17 itf-zone shipped
description: What shipped in pixel-world v2.17 (ITF zone + island cleanup) 2026-04-19, and what's left in the 3-phase hoop-land plan
type: project
---

Shipped 2026-04-19 to Nomos42/pixel-world (HF Space commit 3312b47fa8, mon-ipad commit 09696a538):

- New zone `itf` at grid y=20..23 (w=50, full width). Shrunk `control-room` from y=20..30 → y=24..30 (h=7).
- 7 ITF traders wired (scalper-1, momentum-1, mean-rev-1, breakout-1, pairs-1, vol-1, options-1) with personas matching the live `/api/config_agents`.
- `ENDPOINTS.itf` + `.itfLB` point to `lbjlincoln26-intraday-trading-floor.hf.space/api/{status,leaderboard}`.
- `refresh()` ITF branch: schema has no bankroll — state derives from (open_positions, trades, passes). Bubble shows `N trades · N pass · N open`.
- ISLANDS list trimmed 21 → 11 survivors. Removed eliminated nuls S10/S11/S12/S16/S19/S20/S21 + P3/P6/P8.
- HUD: new `k-itf` row, new Bloomberg ticker segments `bt-itf-trades` + `bt-itf-open`.
- ITF-specific tilemap (candlestick silhouettes + scan lines), decor (ticker board + bull/bear horns), kind color `#ffa94d`.
- Inspect card: ITF agents show `N trades / N passes / N open / tier X / N decisions` since bankroll is null.
- `k-evo` no longer hardcoded to `/21` — now `${evoOK}/${ISLANDS.length}` (11).

**Why:** The hoop-land plan (`reference_hoop_land_pixel_apr19.md`) called for a 3-zone world — NBA / POL / ITF — with data-driven state→animation. Pre-v2.17 the world had NBA + POL + evo + councils + control room but zero ITF reference.

**How to apply:** Next edits to pixel-world follow the same pattern: ZONES (top of the `(async () => {…})()` IIFE) → AGENTS array (kind + zone) → ENDPOINTS → refresh() branch → HUD/ticker wiring → zoneIdToKind + KIND_COLORS + tilemap + decor. Changes go to `hf-pixel-world/index.html`, deployed via `HfApi.upload_file(repo_type="space")` using `HF_TOKEN_LLM`. Git subtree push blocked by 13MB LFS-free limit.

**QA status:** Chrome MCP extension not connected at ship time — no visual confirmation nor GIF. Live deploy verified via curl + CORS probe:
- `https://nomos42-pixel-world.static.hf.space/` returns v2.17 markup
- `ITF_TRADERS` (4×), `"itf"` (8×), `INTRADAY TRADING FLOOR` (1×) all present in live HTML
- ITF endpoints return 200 with `access-control-allow-origin: https://nomos42-pixel-world.static.hf.space`
- All 6 character sprites + referenced floor tiles load 200

**Known risk:** thin 4-tall ITF strip may visually overlap with the wider `political` zone bottom row if agents wander outside seats. Watch for this in first Chrome QA.

**3-phase plan status:**
- Phase 1 (PixiJS v8 + NBA zone): already done before v2.17 (NBA zone pre-existed, PixiJS 8.6.6 already on CDN).
- Phase 2 (POL zone): already done before v2.17.
- Phase 3 (ITF zone): **shipped this pass**.

**Next:**
1. Restore Chrome MCP connection → record GIF of all 3 zones with live agents → attach regression baseline.
2. Consider widening ITF from h=4 to h=5 if 7 agents feel cramped (would further shrink control-room to h=6).
3. ITF `/api/leaderboard` currently reports 0 trades across all agents (fleet warming up). Once trades start landing, visually verify `spawnPulseRing` + orange tint fire correctly.
4. Chart widgets in control-room could render live NBA/POL/ITF bankroll sparklines (currently just decor silhouette).
