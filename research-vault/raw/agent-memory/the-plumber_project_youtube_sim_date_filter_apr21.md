---
name: YouTube narrative sim-date filter (2026-04-21)
description: How NBA+POL TFs consume sim-date-aware YouTube narrative without lookahead leakage; structured videos list + per-day filter in _load_prompt_override
type: project
---

Sim-date-aware YouTube narrative filter deployed 2026-04-21 (commit 91ddf696e) to unblock the market_narrative kill-switch INTERNAL AFFAIRS set after finding 152/229 videos were future-dated relative to NBA/POL sim windows.

**Why:** fleets NBA (sim Oct 2025 - Apr 2026) + POL (sim Jul 2025 - Apr 2026) were seeing YouTube digests containing videos published *after* the simulated game date -> lookahead leakage, same class as the POL excess_return bug fixed 2026-04-18.

**How to apply:**
- Source of truth for video metadata: `data/youtube/manual-ingested.json` (ingested every 6h by `scripts/youtube_channel_autofetch.py`).
- `data/prompts/overrides.json` now carries TWO narrative forms per fleet:
  - `market_narrative` (flat string) -- used by ITF/PQTF (live-dated, no filter needed).
  - `market_narrative_videos` (list of `{id,title,channel,published_at,line}`) -- used by NBA/POL sim-dated fleets.
- `_load_prompt_override(fleet, sim_date=None)` on both NBA app.py (line 153) and POL app.py (line 140) filters `market_narrative_videos` by `published_at[:10] <= sim_date[:10]` when sim_date is given; falls back to flat `market_narrative` when not. Kill-switch `market_narrative_disabled` still suppresses the block entirely.
- Call sites pass `day_date` from the `for day_idx, day_date in enumerate(dates_sorted):` loop (NBA line ~3207, POL line ~2571).
- `scripts/youtube_feeder.py inject_override(fleet, narrative, videos)` writes BOTH forms automatically.
- Offline verifier: `scripts/audit/verify_youtube_narrative_leakage.py --repopulate` — tested 178 NBA sim_dates + 184 POL sim_dates, 0 leakage post-filter, 222 max pre-filter leakage (worst-case day would have leaked 222/223 videos without the gate).
- Deploy recipe: HfApi.upload_file with HF_TOKEN_NBA to BOTH `LBJLincoln26/nba-llm-trading-floor` and `LBJLincoln26/political-llm-trading-floor` (app.py + data/prompts/overrides.json).
- Re-enable is bookkept via `market_narrative_reenabled` sub-object (preserves the prior `market_narrative_disabled` info for audit trail).
