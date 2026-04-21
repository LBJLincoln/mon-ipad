---
name: pixel-world v2.24 AR-lock fix (Apr 20 2026)
description: v2.23 regression — sprite forced 80×112 on 28×24 native frames stretched non-uniformly (heads huge, looked like "3/4 hat"). v2.24 locks to native AR via uniform scale.
type: project
---

v2.23 broke sprites by setting `spr.width=CHAR_W; spr.height=CHAR_H` with CHAR_W=80, CHAR_H=112 — the native spritesheet frame is 28×24 (from a 112×96 4×4 sheet extracted at (0,0,28,24) — see TEX.chars loader around line 1066). Stretch ratios were Y=4.67× / X=2.86× → heads/hats appeared enormous relative to bodies. User called this "3/4 de hat, horrible".

**Why:** non-uniform stretch. Native aspect 28:24 = 7:6. Rendering into 80:112 = 5:7 flips the aspect from wide-short to narrow-tall, distorting the figure.

**How to apply:** any future CHAR_W / CHAR_H tuning MUST preserve AR. Rule: `CHAR_W = round(CHAR_H * 28/24)` AND sprite drawn via `spr.scale.set(CHAR_H/24)` NOT via `spr.width/height = …`. Applied to both `scripts/arena/hf-pixel-world/index.html` and `hf-pixel-world/index.html` (line 434-438 constants, line ~1600 sprite render).

Deploy: HfApi.upload_file with HF_TOKEN_LLM (Nomos42/pixel-world). HF SHA ee7d5a80f6. Git sha 780e743cb.

Key values (v2.24): CHAR_H=112, CHAR_W=131, CHAR_SCALE=4.667.
Keep v2.23 click-to-stop, unified style, typewriter — this patch is scoped to sprite geometry only.
