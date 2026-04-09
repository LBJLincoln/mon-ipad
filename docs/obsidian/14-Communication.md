---
tags: [communication, social-media, telegram, marketing, nomos42]
date: 2026-04-04
aliases: [Communication, Social Media, Marketing, Telegram, D9 Comms]
---

# 14 -- Communication

> Social media strategy, Telegram bots, investor deck, content pipeline.
> D9 Communication dept | Status: PRE-LAUNCH

---

## Communication Channels

| Platform | Account/Handle | Status | Purpose |
|----------|---------------|--------|---------|
| Telegram Bot | @Nomos42Bot | ACTIVE | NBA predictions, analysis, research |
| Telegram Bot | @RGWAbot | ACTIVE | AI art generation |
| Telegram Channel | @Nomos42 | ACTIVE | Public predictions + daily summary |
| X/Twitter | -- | NO API KEY | **USER: provide API key** |
| LinkedIn | -- | NO API KEY | **USER: provide API key** |
| TikTok | -- | LATER | Video content pipeline |
| YouTube | -- | LATER | Demo videos |
| Instagram | -- | LATER | Visual content |

> [!warning] Manual blockers
> X/Twitter and LinkedIn require API keys from the user. Type `! export TWITTER_API_KEY=xxx` in Claude Code.

---

## Telegram Bot Commands

### @Nomos42Bot (NBA Brain)

| Command | Purpose |
|---------|---------|
| `/predict` | Today's game predictions |
| `/bankroll` | Current bankroll state |
| `/pick [game]` | Specific game analysis |
| `/evolution` | Fleet status (6 islands) |
| `/alert on/off` | Subscribe to alerts |

### @RGWAbot (AI Art)

| Command | Purpose |
|---------|---------|
| `/generate` | Generate new artwork |
| `/gallery` | Browse gallery |
| `/quality` | Quality scores |

---

## Content Strategy

### Target Audiences

| Audience | Content Type | Channel | Frequency |
|----------|-------------|---------|-----------|
| Technical bettors | Predictions, Brier scores, methodology | Telegram, X | Daily |
| Casual bettors | Simple picks, win/loss record | Telegram, X | Daily |
| Quant developers | API docs, model details, research papers | LinkedIn, Blog | Weekly |
| Investors / VCs | Traction metrics, vision, TAM | LinkedIn, Deck | Monthly |
| Friends/family | High-level progress, visual dashboard | Personal | As needed |

### Pre-Drafted Content

| File | Type | Status |
|------|------|--------|
| `docs/social-media/launch-thread-twitter.md` | 10-tweet thread | DRAFT |
| `docs/social-media/linkedin-post.md` | Professional announcement | DRAFT |
| `docs/social-media/telegram-announcement.md` | @Nomos42 channel post | DRAFT |
| `docs/deck/nomos42-deck.md` | VC pitch deck outline | DRAFT |

> [!info] Autonomy rule
> Full autonomy on all work EXCEPT communications. Prepare but don't publish.
> All social media posts and investor content need user review before going live.

---

## Investor Deck (Draft)

| Section | Content |
|---------|---------|
| Pain | Insider trading advantages, market inefficiencies |
| Solution | AI models that beat markets + democratize access |
| Product | NBA predictions (Brier 0.215 vs market 0.25) |
| Traction | 6 HF islands, 934 backtested games, 5-AI competition |
| Business model | SaaS tiers ($19/$49/$149) |
| Market size | $100B+ sports betting + prediction markets |
| Ask | Seed round for GPU infrastructure + team |

See: [[15-Business-Plan]] | [[08-API-Vision]]

---

## Daily Report Template

```markdown
# Nomos42 Daily Report - [DATE]

## Predictions
- Games today: [N]
- Value bets: [N] (avg edge [X]%)
- Total exposure: [X]%

## Results (yesterday)
- Record: [W]-[L]
- Bankroll: $[X] (ROI [X]%)

## Evolution
- Fleet best: [X] (S[N])
- Total gens: [N]
- New ATR: [yes/no]

## Trading Floor
- NBA iter: [N] | Grok: $[X]
- Political iter: [N] | Leader: [Name]
```

---

## Presentation Templates

### For Technical Audiences
- Brier score methodology
- Walk-forward validation results
- Feature engine architecture
- Evolution GA parameters

### For Non-Technical Audiences
- Win/loss record visualization
- Bankroll growth chart
- AI competition leaderboard
- Simple "we predict sports games" narrative

### For Investors
- TAM/SAM/SOM analysis
- Revenue projections (see [[15-Business-Plan]])
- Competitive moat (IP, data, evolution)
- Team and advisory (AI-first, single founder)

---

## Links

[[00-Dashboard]] | [[08-API-Vision]] | [[15-Business-Plan]] | [[04-Departments]] | [[18-Creative-RGWA]]
