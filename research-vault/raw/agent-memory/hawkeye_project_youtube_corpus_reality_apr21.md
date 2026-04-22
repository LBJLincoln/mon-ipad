---
name: YouTube corpus composition reality-check (2026-04-21)
description: Measured keyword distribution of data/youtube/manual-ingested.json — corpus is macro/crypto, not NBA
type: project
---

Measured 2026-04-21 on 223-video corpus (20 channels):
- NBA keyword hits (NBA/Lakers/Celtics/LeBron/playoffs/...): **0 / 223 (0.0%)**
- POL keyword hits (Trump/Biden/Fed/Powell/Congress): 17 / 223 (7.6%)
- Macro/crypto/finance (SPY/BTC/VIX/yield/...): 119 / 223 (53.4%)
- Top channels by volume: Bravos 26, warikoo 26, Moon Dev 25, Tech Jarves 25, Altcoin 25, Kanata 25, Bloomberg 15, rest single-digit.
- Date skew: 152/223 published 2026-04 (sim-window-future for anything training on <=Feb 2026 sim dates → same class as 2026-04-18 POL excess_return leakage, same class as 2026-04-21 NBA market_narrative strip).

**Why:** Asked to scout YouTube → tabular training features; before proposing, measured what the corpus actually contains.

**How to apply:** Any future YouTube-based NBA feature story is fabrication until `scripts/youtube_channel_autofetch.py` CHANNELS dict is seeded with NBA-specific channels (@HoopsHype/@ESPNNBA/@TheRingerNBA). For POL, 7.6% coverage supports rolling-sentiment features but not ticker/entity co-mention (too sparse). Proposal at `data/research/youtube-to-training-features-2026-04-21.md`. Tier-1 ship is FinBERT rolling aggregates; Tier-3 NBA co-mention is blocked on channel-seed expansion.
