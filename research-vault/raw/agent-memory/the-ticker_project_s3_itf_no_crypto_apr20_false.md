---
name: S3 itf_no_crypto 2026-04-20 false alarm
description: S3 ITF no-crypto alert was stale/single-tick. Live Space showed 31/38 non-pass trades on crypto (AVAX dominant), 14 personas not 7.
type: project
---

**Fact:** S3 itf_no_crypto alert on 2026-04-20 12:55Z was a false alarm. Over the last 40 ITF decisions, 31 crypto trades vs 7 equity (AVAX/USD dominant). All 14 personas have CRYPTO_PIVOT_CLAUSE injected + crypto block always visible in `_build_prompt`.

**Why:** Alert trigger samples a single tick. When the ticks of a given cycle happen to land on equity-hours while VIX quiet, one tick can look crypto-empty even though the surrounding window is saturated. The memory `project_itf_crypto_pivot_apr20.md` remains correct — just verify live sample before acting.

**How to apply:**
- Before patching, always count crypto share across last ≥20 decisions via `/api/decisions?n=40`, not a single tick.
- Personas: 14 now (scalper/momentum/mean-rev/breakout/pairs/vol/options/arbitrage/news-catalyst/crypto-whale/earnings-gap/iv-crush/macro-rotate/leveraged-momentum). The memory `project_itf_powerup_apr19.md` saying "7 personas + GammaOptions" is stale on count — actual is 14.
- `_OFF_HOURS_STYLE_BY_TID` covers all 14 tids (app.py:121-199). options-1 + iv-crush-1 correctly forced to pass off-hours (no 24/7 options market).
- Off-hours gate: `abs(change_pct) > 0.2%` on any of BTC/ETH/SOL (app.py:439-446) AND weekday-hour check `8 <= hour < 24 UTC` (app.py:464).
