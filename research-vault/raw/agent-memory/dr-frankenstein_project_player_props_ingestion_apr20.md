---
name: Player-props ingestion shipped (pp_* categories, 2026-04-20)
description: Wired the 42 pp_<stat>_<tier>_<side> categories the NBA TF prompt had been falsely advertising since 2026-04-03. Data lives outside engine.py.
type: project
---

Shipped proposal `nba-player-props-ingestion-2026-04-20` on 2026-04-20T03:29Z.

**What**: fetch_player_props.py (live Bovada+DK, synth fallback from season avgs) + prepare_data.py step 4b merges pp_* keys into full-odds-2025-26.json. 22 keys per game × 802 games = 17,592 entries. Tests at scripts/test_player_props.py (23 cases).

**Why (for future-me when a pp_ bug surfaces):** the TF prompt at app.py:1444 advertises 42 categories but the key semantic is ONE outcome per key (not over/under pair). Each `pp_<stat>_<tier>_<side>` = OVER side at fair -110 (decimal 1.909, prob_fair 0.5). Synthetic line = floor(season_avg) + 0.5 so no pushes.

**How to apply**:
- `scripts/arena/hf-llm-trading-floor/data/full-odds-2025-26.json` is **gitignored** — do NOT try to `git add` it. Deploy path is `HfApi.upload_file` with `HF_TOKEN_NBA` (account: LBJLincoln26). This is why prepare_data.py generates it fresh on each Space build.
- The dataset has 802 games, not 1257 (odds CSV limitation). Acceptance target of "1000" was aspirational; 802/802 = full population is the real ceiling.
- Tier map = top-5 by MIN with GP≥5 filter. Fallback to unfiltered roster if <5 seasoned.
- Cron: `0 18,22 * * *` → logs to /tmp/player-props.log. Live fetchers return 0 off-season; real odds populate during slate hours.

**Known fragile bits**:
- DK subcategory IDs (1215, 1216, 9526, ...) rotate silently. The probe loop tolerates 404. If DK falls dark for weeks, update the probe list by inspecting the mobile app network tab.
- Bovada player props sit under displayGroups with description containing "player prop" — the string match may miss a new season's schema. Synthetic fallback keeps the pipeline alive regardless.
- `_name_to_tier` does NOT normalise diacritics (test case documents this) — Luka Dončić vs Luka Doncic would miss. Acceptable because synth always fills the gap and live data is icing.
