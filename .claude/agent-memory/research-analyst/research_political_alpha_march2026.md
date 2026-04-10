---
name: Political Alpha Research — March 2026
description: Trump donor -> political favor -> stock alpha pipeline: key papers, documented cases, feature engineering ideas, and data sources for nomos-political-alpha project
type: project
---

# Political Alpha Research Summary (March 2026)

**Context:** Research conducted 2026-03-27 for nomos-political-alpha project (4,392 LOC, active). Output written to `/home/lahargnedebartoli/nomos-political-alpha/data/research/political-alpha-research-march2026.json`.

## Key Papers Found

1. **Koch & Schiereck (2025)** — "How CEO Donations Drive Stock Prices" (Finance Research Letters). CEO Republican donations => +3.5 pp CAR over 5 days post-election. CEO personal affiliation, not firm-level PAC, is the driver. Russell 3000 sample.

2. **Ferriani, Gazzani, Taboga (2025)** — Bank of Italy. Agenda-47 textual proximity (Hassan 2019 method) => +7% abnormal return per 1 SD on Nov 6 2024, peaking at +10% day 3. Energy/FinTech/Industrials = high proximity; Renewables/Pharma = low.

3. **Aktug & Torul (2025)** — SSRN:5234903. Corporate political alignment effects emerge WITHIN HOURS of Polymarket probability shifts. Dose-response relationship with partisan alignment. Persists for weeks.

4. **Krause (2025)** — Columbia Law. Crypto industry $200M donations => $160B BTC market cap = 800:1 ROI. Event study: Nov 15 meeting +5.63%, Inauguration +2.92%. SEC dropped 60% of crypto cases.

5. **Roodman et al. (2026)** — arXiv:2602.05514, ICLR 2026. Congressional trading TGN: GAP-TGN F1=0.440 vs XGBoost F1=0.291 (+51%) at 24-month horizon. Data: SEC Edgar + LobbyView + VoteView + FEC.

6. **Tariff Exposure (2025)** — ScienceDirect. Text-based tariff exposure from 10-K predicts Liberation Day reactions. Long-short TPU portfolio earns 3.6-6.2% annually.

## Documented Cases (donation -> favor -> stock move)
- GEO/CXW: $500K inaugural -> ICE contracts -> GEO +200%
- COIN: $1M inaugural -> SEC case dropped Feb 2025 -> +147% Nov-Feb
- MO (Altria): $1M inaugural -> menthol ban rescinded -> +12% est.
- META: $1M inaugural -> FTC antitrust softened -> +55% Nov-Mar
- TSLA/Musk: $290M PAC -> DOGE lead, SpaceX contracts -> +97% Nov-Dec 2024
- Pfizer: 3 DOJ enforcement actions canceled (top beneficiary, no large donation listed — soft lobbying channel)
- 17 total inauguration donor corps had enforcement cases dropped (Public Citizen 2025)

## Highest-Alpha Event Types (by evidence strength)
1. **Enforcement dismissal**: +5-15% CAR within 5 days (most documented)
2. **Board nominee connection**: >100% annualized CAR around announcement (Bacon 2020)
3. **CEO political alignment**: +3.5pp CAR on election-type events
4. **Polymarket whale movement**: price move within hours on policy probability change
5. **Government contract award**: +2-8% stock reaction

## Free Data Sources
- FEC API: api.open.fec.gov/v1/ (no key for low volume)
- Public Citizen enforcement tracker: citizen.org
- Polymarket CLOB: clob.polymarket.com
- USASpending.gov API: api.usaspending.gov (no auth)
- QuiverQuant congressional trades: quiverquant.com/congress/
- TPU Index: policyuncertainty.com/trade_cimpr.html
- Federal Register API: federalregister.gov/api/v1/

## Existing Infrastructure
- `nomos-political-alpha/models/donor_power_index.py` — DPI already implemented (0-100 composite score)
- `nomos-political-alpha/features/political_engine.py` — 2,000-feature engine (8 categories) already designed
- `nomos-political-alpha/ops/fetch_political_data.py` — DONOR_UNIVERSE with 40+ tickers, all data fetch APIs

**Why:** This research cycle established the academic foundation for the political alpha model and confirmed the existing DPI/feature architecture is well-aligned with documented evidence.

**How to apply:** When working on nomos-political-alpha, prioritize: (1) enforcement_dismissed event watcher, (2) Polymarket CLOB integration, (3) CEO FEC matching, (4) USASpending contract monitoring, (5) TPU index as macro feature.
