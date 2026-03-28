# Research Cycle 7 Summary — YouTube + Academic Feature Mining

**Date:** 2026-03-28 | **Current Brier:** 0.21570 | **Target:** < 0.20

## Executive Summary

Extracted **18 new feature categories (CAT 47-64)** from NBA analytics YouTube channels and recent academic research (2025-2026). Identified **3 quick-win categories** (4 hours effort, -0.002 Brier expected), and 5 high-priority categories (10-12 hours, -0.004 to -0.006 expected).

**Gap to State-of-Art:** -0.0157 (published best: 0.199 by Montrucchio 2026)

---

## Quick Wins (4 Hours, -0.0020 Brier)

| Category | Effort | Expected Delta | Data Source | Implementation |
|----------|--------|-----------------|-------------|-----------------|
| **CAT 49: Game Flow** | 2h | -0.0007 | nba_api | Halftime margin, garbage time flag, game phase segments |
| **CAT 53: Rest Nonlinear** | 1h | -0.0008 | Existing | rest_squared, cumulative fatigue (exponential decay) |
| **CAT 61: Vegas Consensus** | 1h | -0.0005 | BetMGM/DK | Implied prob consensus, line movement, sharp vs public |

**Expected Result:** 0.21570 → 0.21370 Brier

---

## High-Priority Categories (10-12 Hours, -0.004 to -0.006 Brier)

### 1. CAT 47: Advanced Clutch Dynamics (2h, -0.0010)
**Source:** MDPI 2025, NBER
- Estimation of Clutch Competency (ECC) metric
- 3-point decline under pressure
- Last 5-minute free throw reliability
- Close-game win % (within 5 pts)
- Clutch holding %

**Key Insight:** Clutch performance has demonstrated predictive power in recent empirical research

### 2. CAT 48: Referee Crew Bias (3h, -0.0008)
**Source:** Belasen et al. 2025, Sabag et al. 2026 (MIT Sloan)
- Home foul calling bias (home fouls - away fouls)
- Free throw advantage for home teams
- Total fouls per game (tight vs loose)
- Home team win % with this crew
- Technical foul rates
- Playoff bias patterns

**Key Insight:** 2026 study confirms home favoritism is persistent and measurable

### 3. CAT 50: Market Microstructure & Sharp Money (2h, -0.0012) ⭐ HIGHEST PRIORITY
**Source:** Sports AI 2026, Polymarket, SBR
- Sharp move detection (line >1.5 pts away from steam)
- Late money direction (home vs away)
- Steam velocity (pts/hour)
- Reverse line movement flag
- Polymarket vs books divergence
- Prediction market volume & confidence
- Historical CLV performance

**Key Insight:** Market microstructure is complementary signal to model; sharp money detectable

### 4. CAT 54: Shot Quality & Location Splits (2h, -0.0008)
**Source:** Montrucchio 2026 (SOTA: 0.199), Thinking Basketball
- Rim attempts & efficiency (%)
- Mid-range attempts & efficiency
- 3-point attempts & efficiency
- Expected FG% (xEFG) from shot chart
- Shot quality delta (actual vs expected)

**Key Insight:** Shot location is strongly predictive; xEFG appears in SOTA models

### 5. CAT 57: Player Health & Injury Impact (3h, -0.0010)
**Source:** NBA injury reports, FiveThirtyEight RAPTOR, Seth Partnow
- WAR lost from injuries (weighted by position importance)
- All-Star level players out (count)
- Bench depth (quality of backup unit)
- Days since key player return (rust factor)
- Preseason lineup availability %

**Key Insight:** Injuries are massive signal; recent work weights by position impact

---

## Medium-Priority Categories

| Category | Effort | Delta | Notes |
|----------|--------|-------|-------|
| CAT 51: Lineup Continuity | 2h | -0.0006 | Lineup-level data from nba_api |
| CAT 52: Hustle Metrics | 3h | -0.0005 | Player tracking, contested shots, deflections |
| CAT 55: H2H Matchup | 1h | -0.0004 | Historical games, style clash |
| CAT 56: Season Phase | 1h | -0.0005 | Playoff implications, tanking flags |
| CAT 58: Pace Dynamics | 2h | -0.0005 | Tempo-free analysis, transition rates |
| CAT 59: Defensive Splits | 2.5h | -0.0004 | Perimeter D, paint D, transition D |

---

## YouTube Channel Insights

### Thinking Basketball (Ben Taylor)
- **Focus:** Shot quality, lineup analysis, advanced metrics
- **Feature Relevance:** CAT 54 (shot zones), CAT 51 (lineups)

### Cleaning the Glass (Ben Falk)
- **Focus:** Garbage time filtering, situational defense, bench depth
- **Feature Relevance:** CAT 49 (game flow), CAT 51 (lineups), CAT 60 (bench)

### The Athletic / Seth Partnow
- **Focus:** Player impact, injury adjustments, Bayesian methods
- **Feature Relevance:** CAT 57 (injuries), CAT 55 (H2H), calibration

### BBall Index
- **Focus:** Advanced metrics, game flow, clutch dynamics
- **Feature Relevance:** CAT 47 (clutch), CAT 49 (game flow)

### Half Court Hoops
- **Focus:** Niche analytics deep dives
- **Feature Relevance:** CAT 48 (refs), CAT 50 (market micro)

---

## Research Findings

### State-of-Art Benchmark
- **Author:** Montrucchio 2026
- **Best Brier:** 0.199
- **Our Gap:** 0.0157
- **Key Features:** xEFG, nonlinear rest, game flow, clutch adjustment

### Calibration > Accuracy
- **Finding:** Model calibration produces 69.86% higher ROI than accuracy optimization (Walsh & Joshi 2024)
- **Implication:** All new features prioritized for calibration, not raw accuracy

### Market Efficiency
- **Finding:** Vegas lines incorporate ~90% of public information
- **Implication:** Market micro features likely <0.001 delta, but non-redundant

### Recent Referee Research
- **Finding:** Home favoritism persistent in 2025-2026 games
- **Implication:** Referee bias is real, measurable, and exploitable

---

## Data Source Checklist

| Source | Coverage | API | Status |
|--------|----------|-----|--------|
| nba_api | Box, PBP, lineups, hustle | YES | ✓ Working |
| NBA.com L2M | Ref crew, fouls | Scrape | Ready |
| Basketball-Reference | Historical | CSV | Available |
| pbpstats.com | Shots, zones, xEFG | YES | Requires key |
| BetMGM/DraftKings | Lines, moneylines | YES | ✓ Configured |
| Polymarket | Prediction markets | YES | Available |
| NBA injury report | Player health | Web | Scrape-ready |

---

## Implementation Path

### Phase 1: Quick Wins (Day 1, 4h)
```bash
# Add to hf-space/features/engine.py and features/engine.py (sync)
1. CAT 49 (game flow) — halftime margin, garbage time, game phases
2. CAT 53 (rest nonlinear) — rest^2, cumulative fatigue decay
3. CAT 61 (Vegas consensus) — implied prob avg, line move magnitude
```

### Phase 2: High-Priority (Days 2-3, 10-12h)
```bash
# Implement in parallel
1. CAT 47 (clutch) — 2h
2. CAT 48 (refs) — 3h (requires L2M scraper)
3. CAT 50 (market micro) — 2h (fetch lines)
4. CAT 54 (shot zones) — 2h (pbpstats integration)
5. CAT 57 (injuries) — 3h (daily injury scraper)
```

### Phase 3: Deployment & Validation
```bash
# Test on islands S10/S11 first
python3 hf-space/prepare_nba.py
# Monitor Brier on validation set
# Walk-forward backtest on 2025-26 season
```

---

## Expected Outcomes

| Scenario | Brier | Gain | Notes |
|----------|-------|------|-------|
| **Pessimistic** | 0.2147 | -0.0010 | Only quick-wins stick, redundancy high |
| **Realistic** | 0.2117 | -0.0040 | 60% of expected gains, some feature interaction |
| **Optimistic** | 0.2077 | -0.0080 | All high-priority categories deliver, low redundancy |
| **Best Case** | 0.2040 | -0.0117 | All categories stick, synergistic effects |

**Most Likely:** -0.004 to -0.006 Brier (0.2115 to 0.2097)

---

## Tools & Artifacts

### Python Scripts
- **youtube_feature_extractor.py** — Extract feature insights from transcripts
- **youtube_transcript_miner.py** — Mine transcripts (enhanced keywords)

### Documentation
- **research_cycle7_youtube_features.md** — Full feature specifications
- **data/research_cycle7_feature_proposals.json** — Structured JSON proposals

### Usage
```bash
# List recommended analytics channels
python3 scripts/youtube_feature_extractor.py --channels

# Extract features from a specific video
python3 scripts/youtube_feature_extractor.py --video dQw4w9WgXcQ

# Search for videos on a topic
python3 scripts/youtube_transcript_miner.py --search "NBA clutch analysis" --max 20
```

---

## Risk Factors

| Risk | Mitigation |
|------|-----------|
| **Feature redundancy** | Use genetic algorithm to cull low performers |
| **Data quality (refs, injuries)** | Pre-validate scraped data against official sources |
| **Market data staleness** | Fetch lines pre-game + halftime, cache locally |
| **Overfitting** | Use strict validation set; walk-forward backtest |
| **Integration complexity** | Test each category independently before full deploy |

---

## Next Meeting Checklist

- [ ] Implement CAT 49, 53, 61 (quick wins)
- [ ] Deploy to S10/S11 for testing
- [ ] Validate -0.002 Brier gain
- [ ] Begin CAT 47-48 implementation
- [ ] Set up NBA L2M scraper
- [ ] Validate market data pipeline
- [ ] Report findings in 5-7 days

---

**Memory:** Detailed findings stored at `/home/termius/mon-ipad/.claude/agent-memory/karpathy-researcher/research_cycle7_youtube_features.md`

**Proposals JSON:** `/home/termius/mon-ipad/data/research_cycle7_feature_proposals.json`
