# NOMOS42 → TRUMP CORPORATE ALPHA
## Duplication de l'Architecture NBA vers le Political Trading

---

## TON ARSENAL RÉEL (GitHub LBJLincoln + HF LBJLincoln26)

### nomos-nba-agent (GitHub) — Le système complet

| Module | Lignes | Duplicable pour Finance ? |
|--------|--------|--------------------------|
| `models/kelly.py` — Kelly avec odds réelles, multi-bet optimization | 16K | ✅ **Tel quel** — même formule |
| `models/odds_analyzer.py` — Comparaison 24+ bookmakers, CLV, line movement | 26K | 🔄 **Adapter** → broker spread analyzer |
| `models/power_ratings.py` — Elo composite, force relative | 22K | 🔄 **Adapter** → Political Power Index |
| `models/predictor.py` — Ensemble prediction pipeline | 26K | 🔄 **Adapter** → sector momentum predictor |
| `ops/bankroll-manager.py` — P&L tracking, daily snapshots, compound | 17K | ✅ **Tel quel** — même gestion |
| `ops/karpathy-loop.py` — Self-improving cycle nightly | 102K | ✅ **Même pattern** — collect→train→predict→eval |
| `ops/fetch-odds.py` — The Odds API integration | 21K | 🔄 **Remplacer** → Yahoo Finance / Polygon.io API |
| `ops/daily-board.py` — Dashboard prédictions quotidiennes | 25K | 🔄 **Adapter** → sector daily signals |
| `features/engine.py` — 6,129 features, 36 catégories | 305K | 🆕 **Réécrire** — nouvelles features politiques |
| `features/odds_market.py` — Market microstructure features | 79K | 🔄 **Adapter** → options flow, dark pool signals |
| `calibration/conformal.py` — Conformal prediction | 62K | ✅ **Tel quel** |
| `evolution/genetic_loop_v3.py` — GA island model | 90K | ✅ **Tel quel** — même NSGA-II |
| `hf-space/app.py` — Gradio + FastAPI evolution server | 148K | ✅ **Dupliquer** un nouveau space |

**Total duplicable immédiatement : ~60%**
**Total nécessitant adaptation : ~30%**
**Total à réécrire : ~10% (feature engine spécifique)**

### ApophisFIN (GitHub) — Ingestion RAG n8n

7 workflows n8n (137 nodes) prêts pour import :
- **Orchestrator V6.0** — Route vers Standard RAG, Graph RAG, ou Quant RAG
- **Ingestion V3.0** — Documents, Late Chunking, MinHashLSH dedup
- **Graph RAG V3.0** — Entités, communautés Louvain, Neo4j
- **RAG Quantitatif V1.0** — SQL queries, données structurées

**Pour le Trump thesis** : Ce système peut ingérer executive orders, SEC filings, budget proposals, tariff announcements, lobbying disclosures, et construire un graph de relations Trump ↔ corporates ↔ sectors.

---

## LA THÈSE TRUMP → MAPPING SUR TON INFRA

### Ce que la Recherche Dit (papers 2025-2026)

**Sparkline Capital** : Les actions "nonpartisanes" (donnant aux deux partis) surperforment les actions purement partisanes. MAIS les actions alignées Trump bénéficient de catalyseurs politiques spécifiques.

**Secteurs gagnants documentés (mars 2026)** :
- **Défense** : ITA +55% sur 1 an, budget $1.01T→$1.5T proposé
- **Énergie fossile** : Dérégulation EPA, expansion drilling fédéral
- **Finance/Banking** : Dérégulation Dodd-Frank, crypto-friendly SEC
- **Crypto** : WLFI (World Liberty Financial), USD1 stablecoin, pro-crypto legislation
- **Small caps US** : Tarifs = reshoring = IWM beneficiary

**Actifs Trump directs (DANGER)** :
- DJT : $70.90 → $8.58 (-88%), revenu $3.7M vs perte $712M
- $TRUMP memecoin : $74.27 → $3.24 (-96%)
- Lesson : Le "Trump premium" est priced in immédiatement, puis mean-reverts

### L'Insight Clé pour Toi

**Tu ne dois PAS parier sur DJT ou $TRUMP.** Tu dois faire pour les secteurs Trump-linked ce que tu fais pour la NBA : construire un modèle de prédiction avec features politiques + market microstructure, trouver le edge vs le marché, et appliquer Kelly.

---

## ARCHITECTURE DUPLIQUÉE : "NOMOS POLITICAL ALPHA"

```
╔══════════════════════════════════════════════════════════════╗
║                    NOMOS42 NBA (EXISTANT)                    ║
╠══════════════════════════════════════════════════════════════╣
║ Feature Engine    → 6,129 features NBA (35 cat)             ║
║ GA Evolution      → 6 islands HF Spaces                    ║
║ Kelly + Odds      → Odds API → edge → sizing               ║
║ Karpathy Loop     → collect→train→predict→eval              ║
║ Bankroll Manager  → P&L, compound, daily snapshots          ║
║ Dashboard         → nomosdashboard.vercel.app/nba           ║
╚══════════════════════════════════════════════════════════════╝
                         │
                    DUPLIQUER
                         │
                         ▼
╔══════════════════════════════════════════════════════════════╗
║               NOMOS42 POLITICAL ALPHA (NOUVEAU)             ║
╠══════════════════════════════════════════════════════════════╣
║ Feature Engine    → ~2,000 features politiques (voir §ci)   ║
║ GA Evolution      → 2 islands HF Spaces (1 gratuit suffit)  ║
║ Kelly + Broker    → Options flow → edge → sizing            ║
║ Karpathy Loop     → MÊME CODE, nouvelles data sources       ║
║ Bankroll Manager  → MÊME CODE (tel quel)                    ║
║ Dashboard         → nomosdashboard.vercel.app/political     ║
║                                                              ║
║ + ApophisFIN RAG  → Ingestion policy signals via n8n        ║
║ + Freqtrade       → Execution crypto/ETF automatisée        ║
╚══════════════════════════════════════════════════════════════╝
```

---

## FEATURE ENGINE POLITIQUE (~2,000 features)

Voici comment mapper tes 36 catégories NBA vers des catégories financières :

| Cat NBA | Cat Politique | Features |
|---------|--------------|----------|
| Rolling Performance (96) | **Sector Rolling Returns** (120) | ITA/XLE/XLF/IWM returns sur 3/5/7/10/15/20 jours, vol, Sharpe rolling |
| Four Factors (32) | **Macro Four Factors** (40) | VIX, DXY, 10Y yield, credit spreads × 2 windows × long/short |
| Pace & Efficiency (24) | **Market Microstructure** (60) | Options flow ratio, dark pool %, volume profile, bid-ask spreads |
| Momentum & Streaks (16) | **Sector Momentum** (30) | Cross-sectional momentum, relative strength vs SPY, streak days |
| Rest & Schedule (20) | **Calendar & Seasonality** (40) | Day of week, month, FOMC proximity, earnings calendar, OpEx |
| Matchup & H2H (18) | **Cross-Sector Correlations** (30) | Defense-Energy correlation, Finance-Crypto beta, rotation signals |
| Market Microstructure (30) | **Options Flow Signals** (80) | Put/call ratio, unusual activity, whale trades, GEX, DIX, VIX term |
| Context & Situational (20) | **Political Event Signals** (100) | Executive orders count, tariff announcements, Congressional votes, SCOTUS |
| Referee Features (10) | **Regulatory Signals** (30) | SEC enforcement actions, EPA permits, DOD contracts awarded |
| Polymarket (8) | **Prediction Markets** (20) | Polymarket political contracts, Kalshi macro events, PredictIt |
| Interaction Features (200) | **Cross-Feature Interactions** (300) | VIX × sector momentum, tariff news × IWM, crypto × regulatory |
| Time Series Decomp (320) | **Regime Detection** (200) | Hidden Markov, trend/seasonal/residual, change-point detection |
| Bayesian Priors (220) | **Political Cycle Priors** (100) | Historical sector returns under GOP/DEM, midterm effects, year 2/3/4 |
| Network/Graph (220) | **Trump Network Graph** (200) | Neo4j corporate connections, lobbying graph, donor network via ApophisFIN |

**Total : ~1,350 features structurées + ~650 interactions = ~2,000**

---

## DATA SOURCES (gratuites ou quasi-gratuites)

| Source | Data | Coût | Fréquence |
|--------|------|------|-----------|
| **yfinance** | Prix, volumes, fondamentaux ETFs/actions | Gratuit | Daily |
| **Polygon.io** (free tier) | Intraday, options flow | Gratuit (5 calls/min) | Daily |
| **FRED API** | Macro (VIX, yields, DXY, unemployment) | Gratuit | Daily |
| **Polymarket API** | Prediction markets politics | Gratuit | Real-time |
| **Congress.gov API** | Bills, votes, committee hearings | Gratuit | Daily |
| **Federal Register API** | Executive orders, rules | Gratuit | Daily |
| **OpenSecrets API** | Lobbying, donations, PACs | Gratuit (limited) | Weekly |
| **SEC EDGAR** | Filings, insider trades, 13F | Gratuit | Daily |
| **USAspending.gov** | Government contracts par entreprise | Gratuit | Daily |
| **CoinGecko API** | Crypto prices (TRUMP, WLFI) | Gratuit | Hourly |
| **ApophisFIN RAG** | Ingestion news, analysis via n8n | Ton infra | Continu |

---

## PLAN DE DUPLICATION — 5 Étapes

### Étape 1 : Fork le Feature Engine (Semaine 1)
```bash
# Dans nomos-nba-agent/
cp features/engine.py features/political_engine.py
# Réécrire les catégories avec les sources ci-dessus
# Garder la même interface : build_features(events) → X, y, feature_names
```

**L'objectif de prédiction change** :
- NBA : `y = 1 si home_team gagne` (classification binaire)
- Political Alpha : `y = 1 si sector_return > SPY_return sur N jours` (classification binaire)
- Ou : `y = sector_return_excess` (régression, puis Kelly sur les cotes implicites)

### Étape 2 : Adapter les Data Ingestion (Semaine 2)
```bash
# Nouveau fichier
cp ops/fetch-odds.py ops/fetch-political-data.py
# Remplacer The Odds API par yfinance + FRED + Polymarket + Congress API
# Stocker dans data/political/
```

**Connecter ApophisFIN** : Tes 7 workflows n8n ingèrent les executive orders, SEC filings, tariff announcements. Le Graph RAG construit le réseau Trump ↔ entreprises. Le RAG Quantitatif query les données structurées. Output → features pour le political engine.

### Étape 3 : Déployer 1 Island HF (Semaine 3)
```bash
# Dupliquer le space existant
cp -r hf-space/ political-space/
# Modifier app.py pour utiliser political_engine
# Deploy sur HF : LBJLincoln26/nomos-political-alpha
```

Un seul space HF gratuit suffit pour commencer (vs 6 pour NBA). Le GA tourne avec 60 individus, même NSGA-II, même island model réduit à 2-3 îles.

### Étape 4 : Kelly + Execution (Semaine 4)
```bash
# models/kelly.py → AUCUNE MODIFICATION nécessaire
# La formule Kelly est universelle : f* = (bp - q) / b
# Simplement changer la source des "odds" :
#   NBA : bookmaker odds via Odds API
#   Political : implied odds via options market (IV, put/call skew)
#                ou via ETF momentum signals
```

**Execution via Freqtrade** (crypto/ETF) ou **IBKR API** (options/ETFs) :
```python
# Même bankroll-manager.py, juste changer le broker
from freqtrade.exchange import Exchange  # crypto
# ou
from ib_insync import IB  # stocks/options
```

### Étape 5 : Dashboard + Compound (Semaine 5+)
Ajouter une section `/political` sur nomosdashboard.vercel.app, même pattern que `/nba`.

---

## LES TRADES CONCRETS SELON LES PAPERS

### Tier 1 : High Conviction (papers + data confirm)

| Trade | Véhicule | Edge Source | Kelly Input |
|-------|----------|-------------|-------------|
| Long Défense US | ITA (ETF), LMT, NOC, HII | Budget $1T→$1.5T, NATO 5% | Sector momentum vs SPY |
| Long Small Caps US | IWM (ETF) | Tarifs = reshoring | Regression on tariff news flow |
| Long Crypto infra | Coinbase (COIN), MicroStrategy | Pro-crypto SEC/legislation | Regulatory sentiment score |
| Long Financial dereg | XLF, KRE (regional banks) | Dodd-Frank rollback | Policy change probability |

### Tier 2 : Opportunistic (event-driven)

| Trade | Trigger | Duration | Sizing |
|-------|---------|----------|--------|
| Short SPY / Long IWM | Tariff escalation | 1-3 semaines | 1/4 Kelly |
| Long VIX calls | SCOTUS ruling, trade war | 1-5 jours | 1/8 Kelly (binary) |
| Long crypto après crash | Executive order pro-crypto | 2-4 semaines | 1/4 Kelly |
| Long energy après EPA rule | Dérégulation annonce | 1-2 semaines | 1/4 Kelly |

### Tier 3 : ÉVITER (papers confirment la destruction de valeur)

| Actif | Raison | Evidence |
|-------|--------|----------|
| DJT (Trump Media) | -88%, revenu $3.7M, no moat | Pure meme stock |
| $TRUMP memecoin | -96%, insiders dumped | Retail trap |
| SPAC Trump-affiliated | Track record catastrophique | Priced in immédiatement |

---

## BUDGET ET TIMELINE

| Phase | Capital | Allocation | Outils |
|-------|---------|-----------|--------|
| **Semaine 1-4** : Build | 0€ (paper trading) | Code seulement | Claude Code + VM existante |
| **Mois 2** : Paper test | 0€ | Simuler 100+ trades | political-space HF + dashboard |
| **Mois 3** : Go live | 200€ | 50% NBA bets + 50% crypto/ETF | Betclic + Kraken |
| **Mois 4-6** : Scale | Capital compound | Ajouter forex + defense ETFs | +XTB + IBKR (quand >500€) |
| **Mois 6-24** : Compound | Reinvest 100% | Multi-asset Kelly portfolio | Full stack |

**Coût infrastructure supplémentaire : 0€**
- HF Space gratuit (1 space political alpha)
- VM GCP existante (ajouter cron pour political data)
- Supabase existant (nouvelles tables)
- Dashboard Vercel existant (nouvelle route)
- ApophisFIN n8n sur ton instance n8n existante (amoret.app.n8n.cloud)

---

## RÉSUMÉ

Ton avantage unique est que tu as **déjà construit le système le plus difficile** — un genetic evolution engine avec 6,000+ features, NSGA-II, Kelly sizing, Karpathy self-improvement loop, et bankroll management. La NBA était le proving ground. Maintenant, tu dupliques l'architecture pour les marchés financiers en gardant 60% du code identique, adaptant 30%, et réécrivant seulement le feature engine (10%).

La thèse Trump n'est PAS de parier sur DJT/$TRUMP (destruction de valeur prouvée). C'est de construire un **modèle de timing sectoriel** qui détecte quand les policy signals créent un edge sur les ETFs défense/énergie/finance/crypto, et d'appliquer exactement le même Kelly discipliné que pour la NBA. Le compound vient de la diversification : NBA (non-corrélé aux marchés) + secteurs politiques + crypto = drawdowns non-simultanés = croissance géométrique plus stable.
