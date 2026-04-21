# Proposal — ITF ingests POL 44-category engine features

**Date:** 2026-04-21
**Author:** HAWKEYE (user-prompted insight, not arXiv scan)
**Owner for impl:** DR FRANKENSTEIN (per v4 ROSTER — ITF scope)
**Classification:** Pure feature addition → **EXEMPT from RCA-first gate** (v4 protocol).

## Hypothesis
ITF's current intraday context (`scripts/arena/shared/context_bus.py`) ingests:
- NBA top-5 edges
- POL TF **analytics** (= downstream bets by 17 POL LLM agents)
- Alpaca live news (last hour)
- Polymarket gamma markets
- Live quotes (Alpaca)

It does NOT ingest `political_engine.build_features()` output — the 44-category /
~3,200-candidate raw signal stream. The POL TF analytics is DOWNSTREAM of the
engine (bets, not signal). ITF is blind to the upstream macro/political catalyst
layer.

Result: persona `macro-rotate-1`, `carry-1`, `news-catalyst-1`, `crypto-whale-1`,
and options personas are missing material signal that POL islands compute daily:
tariff regime (Cat 26, Liberation Day / 90d-pause / China 34%), Iran war
catalyst (Cat 36, ceasefire prob + oil), executive order timeline (Cat 25),
Polymarket delta 24h (Cat 11), Kalshi/Polymarket insider anomalies (Cat 27),
gov contract awards (Cat 13), FEC donation velocity 48h (Cat 23), Form 4 insider
cluster velocity (Cat 6 + 35).

## Expected intraday lift
- 3 personas (`macro-rotate-1`, `carry-1`, `news-catalyst-1`) currently routed to
  POL winners (gemini-3-flash, cerebras:qwen-3-235b) will have genuine macro
  signal to reason over instead of market-micro alone.
- `crypto-whale-1` gets Cat 36 Iran + Cat 26 Tariff → BTC/SOL catalyst reads.
- Options personas (`options-1`, `vol-1`, `iv-crush-1`, `earnings-gap-1`) get
  Cat 7 MACRO (VIX regime) + Cat 11 Polymarket delta for vol reads.

Quantitative target: +5% WR on news-driven ticks (measured on `news-catalyst-1`,
`macro-rotate-1`) over 7-day baseline. Kill criterion: no WR lift by day 14 →
feature disabled (revert).

## Implementation spec

### Phase 1 — "Hot signals" extractor (HAWKEYE/FRANKENSTEIN shared)
Running `political_engine.build_features()` every 5-min tick is too slow (designed
for daily batch). Instead, extract the **realtime-updating categories** into a
lightweight hot-signals export:

**File:** `nomos-political-alpha/scripts/export_hot_signals.py` (new)

**Cron:** `5,20,35,50 * * * *` (every 15min on POL VM)

**Output:** `data/political/hot-signals-latest.json`
```json
{
  "ts": "2026-04-21T14:35:00Z",
  "cat7_macro": {"vix": 18.2, "us10y": 4.12, "sector_rotation_z": 0.8},
  "cat11_poly_delta_24h": [{"market": "Iran-ceasefire-Jun", "delta": +0.07, "vol_usd": 2.4e5}, ...],
  "cat25_eo_timeline": {"days_since_last": 3, "sector_velocity": {"XLE": 0.12, "XLF": -0.03}},
  "cat26_tariff_regime": {"regime": "90d_pause", "days_left": 14, "china_rate": 0.34},
  "cat27_poly_insider": [{"market": "...", "anomaly_z": 2.1, "reason": "Kalshi/Poly divergence"}],
  "cat36_iran": {"ceasefire_prob": 0.72, "poly_vol_usd": 2.55e8, "oil_z": 1.1, "defense_z": 0.8},
  "cat37_tariff_per_ticker": {"MSFT": 0.02, "AAPL": 0.15, "NVDA": 0.22, ...},
  "cat23_fec_velocity": {"top_tickers": [{"ticker": "GEO", "pac_usd_48h": 1.2e5}, ...]},
  "cat6_form4": {"cluster_events": [{"ticker": "PLTR", "n_insiders": 3, "net_buy_usd": 4.2e6}, ...]},
  "cat13_contracts": {"recent_awards": [{"ticker": "LMT", "usd": 2.1e8, "days": 1}, ...]},
  "cat44_youtube_finbert": {"top_tickers": [{"ticker": "TSLA", "polarity_3d": 0.44}, ...]}
}
```

Size budget: ≤ 8KB (every tick → injected into 10 personas → 80KB/tick is tolerable).

### Phase 2 — ITF bridge
**File:** `scripts/arena/shared/context_bus.py` (edit)

Add `_top_pol_engine_hot_signals()` that reads `hot-signals-latest.json` and
returns a dict. Wire into `build_intraday_context()` alongside existing POL bets
(don't replace — complement).

**File:** `scripts/arena/hf-intraday-trading-floor/app.py` (edit `_build_prompt`)

Add `POL ENGINE HOT SIGNALS` block after `LIVE NEWS`:
```
POL ENGINE HOT SIGNALS (macro/political catalysts, refreshed 15min):
  Tariff regime: 90d_pause, 14 days left, China 34%
  Iran ceasefire prob: 0.72 (Polymarket $255M vol, oil z=1.1)
  Last EO: 3 days ago, XLE sector velocity +0.12
  Polymarket Δ24h: Iran-ceasefire +0.07 on $240K vol
  Poly insider anomaly: [market] z=2.1 (Kalshi divergence)
  Form 4 clusters: PLTR +3 insiders $4.2M net buy
  Gov contracts: LMT $210M (1d ago), HII $85M (2d ago)
```

### Phase 3 — persona-aware filter
Not every persona needs all 44 categories. Route:
- `macro-rotate-1`, `carry-1`: Cat 7, 11, 12, 26, 36 (macro)
- `news-catalyst-1`: Cat 13, 23, 25, 44 (event-driven)
- `crypto-whale-1`: Cat 11, 27, 36 (prediction markets + Iran)
- `options-1`, `vol-1`, `iv-crush-1`: Cat 7, 11, 36 (vol drivers)
- `earnings-gap-1`: Cat 6, 13, 44 (idiosyncratic)
- Others: Cat 7 only (macro baseline)

Implementation: per-persona filter in `_build_prompt` based on `persona["style"]`
tag.

## Rollout

1. **Phase 1** — HAWKEYE writes `export_hot_signals.py` on nomos-political-alpha
   repo. Cron every 15min on POL VM. Validate output size + schema.
2. **Phase 2** — FRANKENSTEIN wires `context_bus._top_pol_engine_hot_signals()` +
   ITF `_build_prompt` injection. Deploy to `LBJLincoln26/intraday-trading-floor`
   via HfApi.upload_file + SWITCHBOARD factory_reboot.
3. **Phase 3** — Persona filter (narrower prompts). Measure WR delta per-persona
   over 7 days.
4. **Kill criterion** — no WR lift by day 14 → disable via
   `ITF_POL_ENGINE_ENABLED=0` env flag (gate it behind env).

## Why this is exempt from RCA-first gate (v4 protocol)
Per `.claude/agents/ROSTER.md` v4: "Infra restarts (dead Space → factory_reboot)
and pure feature additions from HAWKEYE's research queue are exempt." This is a
pure feature addition (net-new signal injection), not a TF tune in response to
drawdown. No loser-RCA MD required.

## Priority
HIGH — user raised this 2026-04-21 with urgency. Gap is material. Estimated
effort: 1-2 FRANKENSTEIN 12h slots.
