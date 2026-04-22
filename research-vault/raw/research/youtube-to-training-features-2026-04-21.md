# YouTube Corpus → Tabular Training Features
**Author:** HAWKEYE (D1 Research)
**Date:** 2026-04-21
**Status:** READY FOR IMPLEMENTATION — not yet coded
**Consumer:** THE BOSS → delegates to DR FRANKENSTEIN (impl), SWISH/LOBBYIST (evolve)
**Kill criterion:** If no feature family ≥ +0.0005 Brier gate after 200 GA gens on S14 sandbox, revert.

---

## 0. TL;DR (30 sec)

- **Corpus reality-check is brutal.** 223 videos, 20 channels. **0 NBA mentions (0.0%)**, 17 POL mentions (7.6%), 119 FIN/macro mentions (53%). Distribution: Bravos 26, warikoo 26, Moon Dev 25, Tech Jarves 25, Altcoin 25, Kanata 25, Bloomberg 15. This corpus is **a macro/crypto/dev-tools trough, not an NBA signal source.** For NBA, expected Brier delta from YouTube features is ≤+0.0005 (noise floor). For POL, realistic ceiling is +0.001 to +0.003. Do not oversell.
- **N=223 is below the productivity threshold** for catboost/lightgbm to extract text features alone (typical minimum ~2k per class). Features must be extremely low-cardinality and aggregated across many games, not per-video.
- **Ship-first (Tier 1, highest ROI/lowest risk):** per-day **rolling sentiment aggregates** over 3/7/14-day windows using FinBERT (ProsusAI/finBERT, already HF-hosted). 6 scalar features total. Expected POL Brier delta: **+0.0015 to +0.0030** (anchored on Yang 2025 FinBERT+XGBoost replication, SHAP top-10). NBA: probable noise.
- **Tier 2 (queued behind Tier 1 validation):** BERTopic topic-presence flags + ticker/team co-mention counts.
- **Tier 3 (research, not ship):** sentence-transformer embeddings → PCA-8. Dataset is too small; PCA components will overfit. Only revisit if N>1000.

---

## 1. Problem statement

`data/youtube/manual-ingested.json` has **223 videos** (20 channels, 2024-11 → 2026-04). Today they are injected into LLM prompts as `market_narrative` only — zero training-data path. Grep on 2026-04-21 confirms `features/engine.py` (8089 LOC), `scripts/kaggle/`, `scripts/gpu-burst/`, `scripts/lightning/` contain **no reference** to `youtube` or `market_narrative`. The catboost/lightgbm/xgboost/tabicl islands (S13-S18, S22, P1/P2/P4/P5/P7) never see this data.

The ask: convert unstructured (title + description + no transcript — YouTube IP-blocks the cloud) into tabular features joinable to game rows in the feature engine.

---

## 2. Reality-check

### 2.1 Corpus composition (measured 2026-04-21)
| Metric | Value |
|---|---|
| Total videos | 223 |
| NBA keyword hits (team/player/"NBA"/"playoffs") | **0 / 223 (0.0%)** |
| POL keyword hits (Trump/Biden/Fed/Powell/Congress) | 17 / 223 (7.6%) |
| Macro/crypto/finance hits (SPY/BTC/VIX/yield/...) | 119 / 223 (53.4%) |
| Channels | 20 |
| Top 3 channels by count | Bravos (26), warikoo (26), Moon Dev (25) |

**Implication:** current ingest is a **macro-signal stream, not an NBA oracle**. Any NBA-feature story is fabrication. Correct framing: the corpus informs **POL** (politician mentions, Fed narrative) and **ITF/PQTF** (macro regime). NBA gets, at best, second-order VIX/risk-off context. State this honestly in the engine feature-doc.

### 2.2 Sample size adequacy
- **Catboost with text_features**: empirically needs ≥5k rows of text per class. We have 223 documents total.
- **Sentence embeddings + PCA**: 223 rows × 384-dim embedding → PCA will overfit unless we keep ≤5 components and regularize heavily. Not a Tier-1 path.
- **FinBERT sentiment → scalar aggregated over rolling window**: this is the **only** family where N=223 is OK, because each game row pulls an aggregate across a 3/7/14-day window, not a per-video feature. Feature cardinality stays at ~6 scalars, which tabular models handle at any N.

### 2.3 Join-key & leakage gate
- **JOIN key:** `published_at.date() <= game_date` AND `game_date - published_at <= window_days`. Walk-forward safe by construction because `published_at` is immutable UTC timestamp.
- **Leakage risk** (same class as 2026-04-18 POL `excess_return` bug and today's 2026-04-21 `market_narrative` strip): NBA has 152/229 videos published **after** the sim window (Oct 2025 - Feb 2026). **Reuse the sim-date filter already shipped today** — `data/prompts/overrides.json` stripper is the pattern. Feature engine must accept `sim_date_cutoff` kwarg and refuse any `published_at > sim_date_cutoff`. Hard-fail, not silent-skip — log count of filtered videos to `data/youtube/features-audit-<date>.json` so INTERNAL AFFAIRS can gate.
- **Political leakage is subtler**: political videos published `D+0` about an event on day `D` can contain the outcome. Use `min(published_at + 1 day, article_date)` as earliest-usable. Conservative.

---

## 3. SOTA scan (arXiv + ACL 2025-2026)

| # | Paper / Repo | Technique | Relevance |
|---|---|---|---|
| 1 | Yang et al. 2025, **MDPI Mathematics 13:17** — "Stock Price Prediction Using FinBERT-Enhanced Sentiment with SHAP" | FinBERT → daily sentiment scalar → XGBoost. SHAP confirms sentiment features rank top-10 predictors. | **Tier 1 anchor.** POL Brier parallel. |
| 2 | `ProsusAI/finBERT` (HF, BERT-base fine-tuned Financial PhraseBank) | Ready-to-call 3-class (pos/neu/neg) on title+description, CPU-OK (~30ms/doc × 223 = 7s one-shot) | Tier 1 model choice. No training. |
| 3 | arXiv 2410.21484 — "Systematic Review of ML in Sports Betting" | Sentiment+external-data fusion into gradient-boosted models; Brier improvements 0.001-0.005 when social/news signal is **sport-specific** | Confirms NBA upside requires **NBA-specific channels we don't have yet** |
| 4 | BERTopic (Grootendorst 2022, still SOTA for short docs per 2025 Nature Sci. Rep. survey) | UMAP+HDBSCAN on sentence-transformers → stable topic clusters, then per-doc topic distribution | Tier 2. Keep top-10 topics, one-hot per game window. |
| 5 | `sentence-transformers/all-MiniLM-L6-v2` + PCA-8 | Baseline embedding compression | Tier 3 (too few docs). Re-evaluate at N>1000. |
| 6 | arXiv 2306.02136 — FinBERT stock-movement study | Confirms **rolling aggregation** > per-doc injection for small corpora | Shapes our join design. |
| 7 | HF `yiyanghkust/finbert-tone` | 3-tone classifier, faster than ProsusAI, 2024 update | Fallback if ProsusAI rate-limits. |

**Not recommended (now):**
- GPT-4 / Claude-Haiku as extractor: cost blows up if we re-run on every ingest, and output non-determinism breaks reproducibility unless we cache. Revisit only if FinBERT Tier-1 under-delivers.
- Voyage / OpenAI embeddings: paid, overkill for N=223.
- Full-on TopicGPT / Hierarchical LDA: N too small for hierarchy to converge.

---

## 4. Recommended feature families (priority order)

### **Tier 1 — SHIP FIRST: FinBERT rolling sentiment (6 scalars)**
**Expected Brier delta:** POL **+0.0015 to +0.0030**; NBA +0.0000 to +0.0005 (noise).
**Effort:** 0.5 day.
**Risk:** Very low. 6 scalars can be nan-dropped cleanly.

Precompute once nightly (idempotent):
1. Load `data/youtube/manual-ingested.json`.
2. For each video, run `ProsusAI/finBERT` on `title + ". " + description[:512]`. Store `{id, published_at, sent_pos, sent_neu, sent_neg, polarity = pos - neg}` to `data/youtube/sentiment.parquet`.
3. For each game row `g` at `game_date`:
   - Filter `sentiment.parquet` to `published_at <= game_date AND game_date - published_at <= W days`.
   - Filter `published_at <= sim_date_cutoff` (leakage gate).
   - Per window `W ∈ {3, 7, 14}`, emit: `yt_pol_mean_W`, `yt_abs_pol_mean_W` (volatility proxy).
   - **6 features total** (`yt_pol_mean_3/7/14`, `yt_abs_pol_mean_3/7/14`).

Feature-engine integration:
```python
# features/engine.py — new category 55: YOUTUBE SENTIMENT (6 features)
def _youtube_sentiment_features(self, game_date, sim_cutoff=None) -> dict:
    df = self._yt_sent_cache  # loaded once in __init__ from data/youtube/sentiment.parquet
    if sim_cutoff is not None:
        df = df[df['published_at'] <= sim_cutoff]
    out = {}
    for w in (3, 7, 14):
        window = df[(df['published_at'] <= game_date) &
                    (game_date - df['published_at'].dt.date <= pd.Timedelta(days=w))]
        out[f'yt_pol_mean_{w}'] = window['polarity'].mean() if len(window) else 0.0
        out[f'yt_abs_pol_mean_{w}'] = window['polarity'].abs().mean() if len(window) else 0.0
    return out
```
Wire into `build_game_features()` with a flag `enable_youtube=True`. Default **off** in walk-forward baseline, **on** in a sandbox island (S14 lightgbm has text_features=None, handles numeric fine) so we can A/B.

### **Tier 2 — QUEUED: BERTopic topic-presence (5 flags)**
**Expected Brier delta:** POL +0.0005 to +0.0015. NBA: negligible.
**Effort:** 1.5 days (model training + stability check).
**Ship only if Tier 1 clears +0.0005 gate.**

1. Train BERTopic on full 223 corpus → keep top 5 stable topics (min_cluster_size=8).
2. Label topics by HAWKEYE manually (e.g., "Fed-policy", "crypto-BTC-macro", "election-2024-fallout", "recession-yield-curve", "tech-AI").
3. Per game row, per 7-day window: binary `yt_topic_<k>_present_7d` (1 if ≥1 video in window tagged topic k).
4. **5 features**, low-cardinality, cat-boost native handling.
5. Re-train BERTopic monthly; freeze topic IDs across re-trains via centroid-nearest remap (stable IDs matter for feature-column persistence across walk-forward splits).

### **Tier 3 — RESEARCH, NOT SHIP: ticker/entity co-mention**
**Expected Brier delta:** POL +0.0003 to +0.0010 for event-specific games. NBA: **need NBA-specific channels** (see §6).
**Effort:** 1 day for extraction + 0.5 day for join logic.

- Run regex + simple NER (`en_core_web_sm`) on title+description for: NBA team names/abbrevs, star player surnames, politician surnames, ticker symbols ($SPY, $AAPL).
- Per game row: `yt_home_team_mentions_7d`, `yt_away_team_mentions_7d`, `yt_ticker_spy_mentions_7d` (POL), `yt_politician_key_mentions_7d`.
- **Blocker for NBA**: corpus has 0 NBA mentions. Feature will be constantly zero. **DO NOT ship to NBA engine** until §6 is done.

### **Skipped — embeddings + PCA**
N=223 too small. PCA components will overfit on walk-forward. Revisit when N>1000.

---

## 5. Exact implementation steps for DR FRANKENSTEIN

1. **Create** `scripts/youtube_sentiment_precompute.py` (~80 LOC):
   - Loads `data/youtube/manual-ingested.json`.
   - Runs `ProsusAI/finBERT` (via `transformers` pipeline, CPU) on every video, caches by `id` into `data/youtube/sentiment.parquet`.
   - Re-runs only on new ids (idempotent). Appends, never rewrites.
   - Wire into cron after `scripts/ops/youtube_ingest_and_deploy.sh` at `:20 */6 * * *`.
2. **Extend** `features/engine.py`:
   - Load `sentiment.parquet` lazily in `__init__`.
   - Add `_youtube_sentiment_features()` (code above).
   - Register category **55** in the docstring header.
   - Bump `FEATURE_ENGINE_VERSION` to `v3.2` (triggers Supabase re-tagging per Rule 4).
3. **A/B on S14** (lightgbm sandbox): run 200 GA gens w/ `enable_youtube=True`, compare Brier vs S14 baseline fork. Kill criterion: Δ < +0.0005 on walk-forward after 200 gens → revert + close proposal.
4. **Mirror to POL engine** (`nomos-political-alpha/features/engine.py`) with sim_cutoff gate reusing the same pattern as `scripts/arena/hf-political-trading-floor/data/political_events.json` filter.
5. **Audit entry**: INTERNAL AFFAIRS adds check #6 — "yt sentiment features non-null count per sim day" in `scripts/audit/run_audit.py`, alerts if >10% rows have 0-denominator window (silent failure).

**Est. total effort:** 2 days (Tier 1 only). Tier 2 adds 1.5. Tier 3 blocked by §6.

---

## 6. Cross-reference: user channels + corpus gap

- **Ingestion path** for all auto-pulled channels is `scripts/youtube_channel_autofetch.py` — seeded CHANNELS dict. User's own YouTube handle (`lahargnedebartoli`) is **not** currently in the CHANNELS dict. If user wants personal-channel public uploads ingested, add the handle → channel_id to that file (one-line change, public API, no OAuth).
- **Private/subscription content** (user's YouTube subscriptions, unlisted videos, members-only uploads) **requires OAuth 2.0 flow** — not supported by current YouTube Data API v3 key path. Blocker, not solvable this cycle. If user wants it: spec a separate proposal for Google OAuth client + `youtube.readonly` scope + refresh-token storage.
- **Corpus-gap remediation for NBA**: seed CHANNELS with `@HoopsHype`, `@ESPNNBA`, `@TheRingerNBA`, `@BleacherReport`. Until then, Tier 3 NBA path is dead.

---

## 7. Kill criteria (explicit)

- Tier 1 S14 A/B fails to reach Δ ≥ +0.0005 Brier after 200 gens → revert, close this proposal.
- Audit shows silent-zero rate >10% → feature misjoined, debug or pull.
- INTERNAL AFFAIRS flags leakage (any `published_at > sim_cutoff` in a training split) → immediate revert, sev-1 alert to THE BOSS.

---

## 8. References

- Yang et al. 2025 — [FinBERT + XGBoost + SHAP stock prediction](https://www.mdpi.com/2227-7390/13/17/2747)
- [ProsusAI/finBERT](https://github.com/ProsusAI/finBERT) — MIT, CPU-safe
- arXiv [2306.02136](https://arxiv.org/html/2306.02136v3) — FinBERT rolling-agg > per-doc injection
- arXiv [2410.21484](https://arxiv.org/html/2410.21484v1) — ML sports-betting systematic review (Brier deltas +0.001-0.005 for sport-specific signal)
- Ingest path: `scripts/youtube_channel_autofetch.py` (channels), `scripts/youtube_feeder.py` (prompt injection)
- Leakage precedent: `project_youtube_leakage_apr21.md` (stripped `market_narrative` from NBA+POL overrides)
