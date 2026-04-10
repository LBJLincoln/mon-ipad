---
name: multi_target_trainer
description: Multi-target training design — patch written for HF Space GA evolution, 9 targets, 23K games. app.py not yet patched.
type: project
---

Multi-target evolution patch completed 2026-04-05.

**Why:** Current GA trains one model (P(home_win)) per individual. Multi-task learning across 9 targets forces features to generalize across spread, total, margin betting — literature precedent shows Brier gains of 0.005-0.015.

**How to apply:**
- Patch file: /home/lahargnedebartoli/mon-ipad/scripts/patches/multi_target_patch.py
- Integration target: nba-quant-space/app.py
- NOT engine.py (this is an evolution loop change, not a feature engineering change)
- Self-test passes on 23,038 real games from nba_2008-2025.csv

Key facts — Phase 1 (patch written, app.py NOT yet patched):
- 9 targets: home_win (primary), margin_1_5, margin_6_10, blowout_15, both_100 (JSON-always), spread_cover, total_over, q1_home_win, h1_home_win (CSV-enriched)
- All 9 targets validated on 23,038 games: positive rates 26-58%, all in 5-95% valid range
- Weighted Brier composite: home_win=0.35, spread_cover=0.17, total_over=0.13, margins=0.07-0.09, quarters=0.04
- Auxiliary models: ExtraTreesClassifier 40 estimators (fast, ~40ms each vs 400ms for primary)
- Time budget: Mode A (5 targets, JSON) ~5x, Mode B (9 targets, CSV) ~9x per individual eval
- fitness['brier'] unchanged (home_win primary) — Pareto ranking backward compatible
- fitness['multi_brier'], fitness['target_briers'] added as new keys
- fitness['composite'] gets bonus up to 0.05 when multi_brier < primary_brier
- CSV enrichment: load_csv_games() + merge_csv_into_games() available in patch file

Key facts — Cat 52-54 engine features (implemented 2026-04-05):
- Engine is v3.1-54cat (6312 features)
- Cat 52-54: odds line features, ATS record, O/U record (39 features)
- Engine parity verified: sha256 857e234dc908b66b53b54f2934101cc69af3df8224001929af583225f04c9836
- Only 994 games have odds data for spread_cover/total_over in engine features (2025-26 only)
- Historical odds 2018-2024 with opening lines remains the #1 data priority
