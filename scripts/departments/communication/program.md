# Department: COMMUNICATION (D9)

## Mission
Prepare, optimize, and schedule content across all channels (X, LinkedIn, TikTok, YouTube, Instagram, Telegram) to build Nomos42's audience and establish technical credibility in the AI quant space.

## Primary Metric
- **Name:** engagement_rate_weekly
- **Current:** 0
- **Target:** 5%
- **Direction:** higher_is_better

## Secondary Metrics
| Metric | Current | Target |
|--------|---------|--------|
| posts_prepared_per_week | 0 | 14 |
| channels_active | 2 | 7 |
| followers_total | 0 | 1000 |
| vc_deck_views | 0 | 50 |
| content_quality_score | 0 | 8.0 |

## Search Space
| Parameter | Current | Range | Step |
|-----------|---------|-------|------|
| post_frequency_twitter | 0 | [1, 5] | 1 |
| post_frequency_linkedin | 0 | [1, 3] | 1 |
| post_frequency_tiktok | 0 | [1, 3] | 1 |
| technical_depth | 0.7 | [0.3, 0.9] | 0.1 |
| meme_ratio | 0.1 | [0.0, 0.3] | 0.05 |
| cta_placement | 0.5 | [0.0, 1.0] | 0.1 |
| hashtag_count | 3 | [1, 8] | 1 |
| post_hour_utc | 14 | [8, 22] | 1 |

## Experiment Protocol
1. Load current best posting config (frequency, depth, timing)
2. Mutate one parameter from the search space
3. Generate posts with mutated config (max 5 min)
4. Measure engagement metrics (likes, shares, clicks)
5. If improved -> keep config, commit
6. If not -> revert
7. Log to data/departments/communication/karpathy-output.json

## Channels
| Channel | Status | Auth Required | Bot |
|---------|--------|---------------|-----|
| Telegram | ACTIVE | Already connected | @Nomos42Bot, @RGWAbot |
| X/Twitter | PREPARED | Manual unlock needed | -- |
| LinkedIn | PREPARED | Manual unlock needed | -- |
| TikTok | PREPARED | Manual unlock needed | -- |
| YouTube | PREPARED | Manual unlock needed | -- |
| Instagram | PREPARED | Manual unlock needed | -- |
| GitHub | ACTIVE | Already connected | -- |

## Content Types
1. **Performance Updates** — Weekly trading floor results, Brier improvements
2. **Technical Deep Dives** — Feature engineering, evolution algorithms, Karpathy loops
3. **VC Deck Slides** — Cross-repo diagrams explaining the ecosystem
4. **Agent Spotlights** — 22 agents, their roles, wins, personalities
5. **Market Analysis** — NBA value bets, political alpha signals

## Tools & Paths
- **Loop script:** scripts/departments/communication/comm-loop.sh
- **Output:** data/departments/communication/karpathy-output.json
- **Pre-written posts:** docs/social-media-posts.md
- **VC deck:** docs/vc-deck-2026.md
- **Telegram bots:** @Nomos42Bot (NBA), @RGWAbot (RGWA)

## Dependencies
- **Upstream:** D4 (Betting results), D1 (Research findings), D8 (Creative assets)
- **Downstream:** D10 (Business — drives user acquisition)
- **External:** Social media APIs (auth needed), Telegram Bot API
- **Compute:** CPU only
