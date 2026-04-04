---
tags: [legal, finance, holding, BPI, deeptech, nomos42]
date: 2026-04-03
aliases: [Legal, Finance, Holding Structure, BPI Deeptech]
---

# 09 — Legal & Finance

> Holding structure | BPI Deeptech | 150€ greffe | Burn rate tracking

## Corporate Structure

### Holding Plan

```
[Holding SAS / SASU]  ← 150€ greffe (immatriculation)
    ├── Nomos42 (NBA Quant AI + Trading)
    ├── Political Alpha (ETF / Signal Service)
    ├── RGWA (AI Art Generation)
    └── Nomos Dashboard (SaaS API Platform)
```

**Entity type:** SASU (Société par Actions Simplifiée Unipersonnelle) — recommended for single founder, simplest structure for tech startup in France

**Registration cost:** ~150€ greffe (Tribunal de Commerce)

---

## BPI France Deeptech Program

**Target:** BPI Deeptech Innovation grant / loan

Eligibility criteria met:
- AI/ML technology with measurable performance metrics (Brier score)
- Walk-forward validated predictions (19 weeks, 934 games)
- Active R&D loop (18 techniques, 14 papers, 6 HF islands)
- Quantifiable IP: feature engine v3.1-46cat, 6,253 features, TabICL adaptation
- International market potential (NBA = US market, $100B+ sports betting)

**Grant range:** €30,000 - €500,000 (seed) + optional loan up to 2×
**Application requirements:**
- Detailed technical dossier (Brier 0.21570 documented)
- Research paper references (Montrucchio SOTA reference)
- Market sizing (TAM = $180B global sports betting)
- 3-year financial projections

---

## Financial Tracking

### Virtual Bankrolls (for product validation)
- NBA bankroll: $91.89 / $100 start (real tracking, small amounts)
- Political virtual: $100,000 virtual (simulation only)
- Trading Floor season: $3,687.51 (Grok champion, simulation)

### Infrastructure Costs
| Item | Cost | Frequency |
|------|------|-----------|
| VM (cloud VPS) | ~$5-20/mo | Monthly |
| HF Spaces | $0 (free tier) | — |
| Kaggle | $0 (free, P100 9h) | Per session |
| Colab | $0-$10/session | On demand |
| Vast.ai GPU | $0.16/hr | On demand |
| Supabase | $0 (free tier) | — |
| Vercel (dashboard) | $0 (hobby) | — |
| Domain / misc | ~$10/yr | Annual |
| **Total burn** | **~$20-30/mo** | Monthly |

### Revenue
- Current: $0 (pre-revenue)
- First paying user: Pierre (test user, pending)
- Target MRR: $23,310 (Year 1 target, see [[08-API-Vision]])

---

## Intellectual Property

### Core IP Assets

| Asset | Description | Status |
|-------|-------------|--------|
| Feature engine v3.1-46cat | 46 categories, 6,253 NBA features | DEPLOYED |
| TabICL adaptation | In-context learning for NBA tabular data | ATR (0.21570) |
| Karpathy autoresearch loop | 5-min autonomous research cycles | RUNNING |
| Trading Floor v4 | 5-AI competition architecture | RUNNING |
| Guardian Orchestrator v3 | Cross-dept resource allocation | RUNNING |
| Political Alpha engine | 22-cat, 743-feature ETF signals | RUNNING |

### Documentation for BPI
- Technical: `CLAUDE.md`, `docs/obsidian/`
- Performance: `data/nba-agent/quant-summary.json`
- Walk-forward: Kaggle 19-week backtest
- Research: Research Cycle 7 (18 techniques, 14 papers)

---

## $100 → $1M Financial Model

See detailed model in [[07-Betting#$100 → $1M Roadmap]]

| Year | Bankroll | Key Milestone |
|------|----------|---------------|
| 2026 | $100→$500 | Fix bugs, beat Brier 0.21 |
| 2026 | $500→$5K | 20+ bets/week, edge >5% |
| 2027 | $5K→$50K | Brier 0.20, API launch |
| 2027 | $50K→$500K | 100 SaaS users, institutional pilot |
| 2028 | $500K→$1M+ | Full API, international expansion |

---

## Legal Compliance Notes

### Sports Betting
- Virtual bankroll / simulation = no legal issue
- Live betting (real money) = jurisdiction-specific
- France: betting via licensed operator (FDJ / Winamax / PMU) = legal
- US: state-by-state (legal in 30+ states as of 2026)
- API selling predictions = information service (legal in most jurisdictions)

### Data Sources
- NBA.com/stats: public API, terms allow non-commercial research
- Basketball-Reference: public data, attribution required
- Odds data: purchased or scraped (verify terms per provider)
- Political data (FEC): public government data, unrestricted

### Privacy / GDPR
- No personal user data collected (yet)
- When SaaS launches: GDPR-compliant data handling required
- Telegram bot: no user data stored beyond session

---

## Key Contacts & Accounts

| Service | Account | Status |
|---------|---------|--------|
| GitHub | LBJLincoln | ACTIVE |
| HuggingFace | LBJLincoln, LBJLincoln26, Nomos42 | ACTIVE |
| Kaggle | alexismoret6 | ACTIVE |
| Supabase | project xivvnr (pooler) | ACTIVE |
| Vercel | connected to nomos-dashboard | ACTIVE |
| Google Drive | backup destination | ACTIVE |

---

## Links

[[README]] | [[08-API-Vision]] | [[07-Betting]] | [[10-Repos]]
