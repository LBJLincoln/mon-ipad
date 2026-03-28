# Research Cycle 7 — YouTube & Academic Feature Mining

**Complete:** 2026-03-28 | **Current Best Brier:** 0.21570 | **Target:** < 0.20

## Quick Start

### 1. View All Proposals
```bash
# JSON format (machine-readable)
cat /home/termius/mon-ipad/data/cycle7_actionable_proposals.json

# Human-readable summary
cat /home/termius/mon-ipad/docs/RESEARCH_CYCLE7_SUMMARY.md
```

### 2. List Recommended YouTube Channels
```bash
python3 /home/termius/mon-ipad/scripts/youtube_feature_extractor.py --channels
```

### 3. Quick-Win Implementation (4 hours, -0.002 Brier)
```bash
# CAT 49 (Game Flow) — 2h
# CAT 53 (Rest Nonlinear) — 1h
# CAT 61 (Vegas Consensus) — 1h

# See: docs/RESEARCH_CYCLE7_SUMMARY.md (Implementation Path section)
```

---

## Files Generated

| File | Purpose | Format |
|------|---------|--------|
| `docs/RESEARCH_CYCLE7_SUMMARY.md` | Executive summary, quick wins, implementation roadmap | Markdown |
| `docs/RESEARCH_CYCLE7_SOURCES.md` | 40+ academic papers, YouTube channels, APIs, tools | Markdown |
| `data/cycle7_actionable_proposals.json` | 18 feature categories with implementation details | JSON |
| `data/research_cycle7_feature_proposals.json` | Detailed proposals, data sources, timeline | JSON |
| `.claude/agent-memory/karpathy-researcher/research_cycle7_youtube_features.md` | Full technical specifications, priority matrix | Markdown |
| `scripts/youtube_feature_extractor.py` | Extract features from YouTube transcripts | Python |

---

## Key Findings

### Current Status
- **Engine Version:** v3.0-43cat (6,211 raw features)
- **Best Brier:** 0.21570 (Colab TabICL)
- **Gap to SOTA:** 0.0157 (Montrucchio 2026: 0.199)

### New Categories: 18 (CAT 47-64)

**Quick Wins (4h, -0.002 expected):**
1. **CAT 49: Game Flow** — halftime margin, garbage time, game phases
2. **CAT 53: Rest Nonlinear** — rest_squared, exponential fatigue decay
3. **CAT 61: Vegas Consensus** — implied prob consensus, line movement

**High-Priority (10-12h, -0.004 to -0.006):**
1. **CAT 47: Clutch Dynamics** — ECC metric, pressure effects, close-game metrics
2. **CAT 48: Referee Bias** — home foul delta, FTA advantage, crew patterns
3. **CAT 50: Market Micro** — sharp money, steam moves, polymarket signals ⭐ HIGHEST ROI
4. **CAT 54: Shot Quality** — xEFG, shot location distribution, quality delta
5. **CAT 57: Injury Impact** — WAR lost, position weighting, rust factors

---

## Implementation Checklist

- [ ] **Phase 1 (Day 1):** Implement CAT 49, 53, 61
  - [ ] Add features to `hf-space/features/engine.py`
  - [ ] Sync to `features/engine.py` on VM
  - [ ] Deploy to S10/S11 (test islands)

- [ ] **Phase 2 (Days 2-3):** Implement CAT 47, 48, 50, 54, 57
  - [ ] CAT 47 (clutch): 2h
  - [ ] CAT 48 (refs): 3h + NBA L2M scraper
  - [ ] CAT 50 (market): 2h + API integration
  - [ ] CAT 54 (shots): 2h + pbpstats integration
  - [ ] CAT 57 (injuries): 3h + daily scraper

- [ ] **Phase 3:** Validate & Deploy
  - [ ] Monitor Brier on validation set
  - [ ] Walk-forward backtest on 2025-26 season
  - [ ] Compare vs baseline (0.21570)
  - [ ] Deploy to all 6 HF islands

---

## YouTube Channel Directory

| Channel | Focus | Feature Categories |
|---------|-------|-------------------|
| **Thinking Basketball** (Ben Taylor) | Shot quality, lineups, metrics | CAT 54, CAT 51 |
| **Cleaning the Glass** (Ben Falk) | Game flow, situational D, bench | CAT 49, CAT 51, CAT 60 |
| **The Athletic** (Seth Partnow) | Injuries, player impact, Bayes | CAT 57, CAT 55, calibration |
| **BBall Index** | Clutch, game flow, metrics | CAT 47, CAT 49 |
| **Half Court Hoops** | Refs, market analytics | CAT 48, CAT 50 |

---

## Expected Gains

| Category | Effort | Brier Delta | Effort/Delta | Priority |
|----------|--------|-------------|--------------|----------|
| CAT 49 | 2h | -0.0007 | 2.9h per -0.001 | HIGH |
| CAT 53 | 1h | -0.0008 | 1.2h per -0.001 | **BEST VALUE** |
| CAT 61 | 1h | -0.0005 | 2.0h per -0.001 | HIGH |
| CAT 47 | 2h | -0.0010 | 2.0h per -0.001 | HIGH |
| CAT 50 | 2h | -0.0012 | 1.7h per -0.001 | **HIGHEST PRIORITY** |
| CAT 54 | 2h | -0.0008 | 2.5h per -0.001 | HIGH |
| CAT 57 | 3h | -0.0010 | 3.0h per -0.001 | HIGH |

**Realistic Combined:** -0.004 to -0.006 Brier (accounting for redundancy, overfitting)
**Timeline:** 2-3 days focused implementation

---

## Data Sources Status

| Source | Coverage | Status | Notes |
|--------|----------|--------|-------|
| nba_api | Box, PBP, lineups | ✓ Working | Verified functional |
| NBA L2M | Ref crew, fouls | ⚠ Requires scraper | Web scrape ready |
| pbpstats | Shots, zones, xEFG | API available | Requires key |
| BetMGM/DK | Lines | ✓ Configured | Already integrated |
| Polymarket | Prediction markets | API available | Via REST |
| NBA injury | Health data | ⚠ Web scrape | ESPN tracker available |
| Basketball-Ref | Historical | CSV export | Available |

---

## Key Research Insights

### Calibration > Accuracy
Walsh & Joshi 2024 showed calibration optimization yields **69.86% higher ROI** than accuracy optimization. All new features prioritized for calibration, not raw accuracy.

### Market Efficiency
Vegas lines incorporate ~90% of public info, but market microstructure (CAT 50) provides **non-redundant signal** for betting. Expected Brier delta: -0.0012 (highest ROI).

### State-of-Art Benchmark
Montrucchio 2026 achieves **0.199 Brier** with focus on:
- xEFG (expected field goal %)
- Nonlinear rest effects
- Game flow context
- Clutch adjustment

Our gap: 0.0157. Top 5 new categories target these exact areas.

### Recent Referee Research
Belasen et al. 2025 and Sabag et al. 2026 confirm home favoritism is **persistent, measurable, and exploitable** in modern NBA (2025-2026).

---

## Tools & Utilities

### YouTube Feature Extraction
```bash
# List recommended channels
python3 scripts/youtube_feature_extractor.py --channels

# Analyze specific video for feature insights
python3 scripts/youtube_feature_extractor.py --video dQw4w9WgXcQ
```

### YouTube Transcript Mining (Enhanced)
```bash
# Search for videos on a topic (Cycle 7 keywords)
python3 scripts/youtube_transcript_miner.py --search "NBA clutch analysis" --max 20

# Mine transcripts from specific channel
python3 scripts/youtube_transcript_miner.py --channel UCzzz --max 50
```

---

## References

### Key Papers
- **Montrucchio 2026** (SOTA: 0.199) — Shot quality, rest models, game flow
- **Belasen et al. 2025** — Referee bias in last 2 minutes
- **Sabag et al. 2026** — Officiating mechanics and bias
- **PLOS One 2025** — Game pace dynamics and flow analysis
- **MDPI 2025** — Clutch performance metrics

### YouTube Channels (40+ hours)
Thinking Basketball, Cleaning the Glass, The Athletic, BBall Index, Half Court Hoops, Nylon Calculus alumni

### Academic Conferences
MIT Sloan Sports Analytics, Wharton Moneyball, American Soccer Analysis (xG methodology)

---

## Next Steps

1. **Read the summary:** `docs/RESEARCH_CYCLE7_SUMMARY.md`
2. **Review proposals:** `data/cycle7_actionable_proposals.json`
3. **Implement quick wins:** CAT 49, 53, 61 (4 hours)
4. **Deploy to test islands:** S10/S11
5. **Validate gains:** Monitor Brier on holdout set
6. **Implement high-priority:** CAT 47, 48, 50, 54, 57 (10-12 hours)
7. **Full deployment:** All 6 HF islands + walk-forward backtest

---

## Questions?

- **Feature specifications:** See `research_cycle7_youtube_features.md`
- **Implementation details:** See individual proposals in `cycle7_actionable_proposals.json`
- **Data sources:** See `RESEARCH_CYCLE7_SOURCES.md`
- **Research artifacts:** All memory at `.claude/agent-memory/karpathy-researcher/`

---

**Memory:** This research cycle is fully documented in agent memory for future reference.
