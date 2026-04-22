---
name: Cat67 YouTube FinBERT + W3 OAuth subscriptions (2026-04-21)
description: Shipped HAWKEYE Tier 1 proposal — 6 rolling finBERT sentiment features (3/7/14d polarity + abs-polarity) wired to NBA engine.py v3.2-67cat. OAuth subscriptions puller is PRIMARY channel seed path per user course-correction.
type: project
---

Commit e1120d98b. Files:

- `features/engine.py` + `hf-space/features/engine.py` — sha256 `0fa89873...` parity OK. `ENGINE_VERSION v3.2-67cat`. New: `_load_youtube_sentiment()` + `_youtube_sentiment_features(game_date, sim_cutoff)` + 6 feature names. `NBAFeatureEngine.__init__(enable_youtube=True, sim_date_cutoff=None, youtube_sentiment_path=None)`.
- `scripts/youtube_sentiment_precompute.py` — ProsusAI/finbert CPU, writes `data/youtube/sentiment.parquet`. Idempotent.
- `scripts/youtube_oauth_subscriptions.py` — GOOGLE_CLIENT_ID/SECRET from `.env.local` project 549962199864. OAuth out-of-band flow (`urn:ietf:wg:oauth:2.0:oob`). Refresh token at `data/credentials/youtube-oauth-refresh.json` (GITIGNORED). PRIMARY channel seed — does NOT fall back to guessed channels when user has 0 subs.

**Why:** HAWKEYE 2026-04-21 proposal `data/research/youtube-to-training-features-2026-04-21.md` + user course-correction rejecting mainstream NBA channels (@NBA, @BleacherReport etc) as "generalist, will over-pollute feeds and datasets."

**How to apply:**
- Do NOT add mainstream NBA channels to `scripts/youtube_channel_autofetch.py` CHANNELS dict without user approval. OAuth script now fills that role from user's actual subscriptions.
- S14 A/B sandbox is the kill-criterion gate: 200 GA gens with `enable_youtube=True` vs baseline — if Δ < +0.0005 Brier, revert.
- POL political_engine.py (687 LOC, different schema) not mirrored yet — queue for Tier 2 cycle.
- Leakage pattern reused: sim_date_cutoff is hard gate (published_at <= cutoff), same class as 2026-04-18 POL excess_return and 2026-04-21 market_narrative strips.

**Baseline counts for verification delta (before OAuth run):** 223 videos, NBA kw=16, POL kw=49. User must paste `--auth-code <CODE>` for W3 completion.
