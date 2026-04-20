---
name: pixel-world architecture map
description: Where zones/AGENTS/ENDPOINTS live in hf-pixel-world/index.html + deploy recipe for future edits
type: reference
---

Single file: `/home/termius/mon-ipad/hf-pixel-world/index.html` (~2800 lines, all inline JS inside one `(async () => {…})()` IIFE).

Canonical anchors (as of v2.17, 2026-04-19):
- `TILE = 32` + `GRID_W=52, GRID_H=32` near top of IIFE.
- `KIND_COLORS` + `KIND_COLORS_HEX` + `KIND_GLYPHS` one-liner dicts — keys MUST match the value returned by `zoneIdToKind(zoneId)`.
- `ZONES` dict — zone layout grid. Rows currently: 1..4 infra / 5..8 councils / 9..19 trading floors / 20..23 itf / 24..30 control-room.
- `NBA_TRADERS` / `POL_TRADERS` / `ITF_TRADERS` — trader id arrays (strings).
- `ISLANDS` — `[[label, url]]` of SURVIVOR islands only. Never re-add eliminated nuls.
- `ENDPOINTS` — all TF status/leaderboard/day-decisions URLs.
- `TRADER_PERSONAS` — `{id: {persona, model, provider, risk, style}}` rendered in inspect card.
- `AGENTS` — flat array built from the spreads of trader arrays + ISLANDS + COUNCIL_DEPTS. Each entry needs `id`, `key`, `kind`, `zone`, `idx`, `char`, `tint`.
- `assignSeats()` — positions agents within their zone via cols/rows based on `z.w / z.h`.
- `zoneIdToKind(zoneId)` — maps zone id → kind (used for KIND_COLORS lookup).
- `refresh()` — main poll loop. Each TF has its own branch that reads `ENDPOINTS.{tf}` then updates `a.data`, `a.state`, `a.bubble` for matching agents.
- `showInspectPanel(a)` — fills the trainer card. Reads fields out of `a.data`. For kinds lacking bankroll (itf), use `a.kind === "itf"` branch in the `extra` array.
- Bloomberg ticker segments defined in `#bloomberg-ticker` HTML (line ~290) + written by `setTx()` in refresh().

Deploy recipe (HF-only, never Vercel):
```python
from huggingface_hub import HfApi
import os
api = HfApi(token=os.environ['HF_TOKEN_LLM'])  # Nomos42 account
api.upload_file(
    path_or_fileobj="/home/termius/mon-ipad/hf-pixel-world/index.html",
    path_in_repo="index.html",
    repo_id="Nomos42/pixel-world",
    repo_type="space",
    commit_message="PIXEL vX.Y: …",
)
```
Git subtree push is blocked by 13MB LFS-free Space limit — use HfApi only.

Git commit (repo side) uses the mandatory mutex:
```
bash scripts/lib/safe_commit.sh PIXEL "feat(pixel-world): …" hf-pixel-world/index.html
```

Verification commands:
- Live HTML: `curl -s https://nomos42-pixel-world.static.hf.space/ | grep -c <marker>`
- HF Space commit log: `api.list_repo_commits("Nomos42/pixel-world", repo_type="space")[:3]`
- Endpoint status: `curl -s -o /dev/null -w "%{http_code}" $ENDPOINT`
- CORS probe: `curl -s -D - -H "Origin: https://nomos42-pixel-world.static.hf.space" $ENDPOINT | grep access-control`

URL note (always): `nomos42-pixel-world.static.hf.space` — the `.static.` segment matters. Plain `.hf.space` 404s on static Spaces.
