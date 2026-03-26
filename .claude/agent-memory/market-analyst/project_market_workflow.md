---
name: Market Analysis Workflow
description: How to detect steam moves, CLV opportunities, and sharp/square divergence from NBA odds data
type: project
---

## Steam Move Detection (no historical snapshot needed)
When only one odds snapshot is available, detect steam via **line splits across books**:
- If Pinnacle + 2-3 other books have moved to a new line while 2-3 soft books are still at old line = active steam
- 1pt spread split (e.g. -3.5 vs -4.5) across 7 books = HIGH confidence steam signal
- 2pt total split across books = MEDIUM confidence

**Why:** Pinnacle reacts first to sharp money. Betway/Unibet/Betclic are slowest to update (~15-30 min lag).

## CLV Logic
- Best CLV bet = grab the line at a soft book BEFORE it moves to Pinnacle level
- 1pt of spread CLV at -110 odds ≈ +5% EV gain
- Urgency window: typically closes within 1-2 hours of sharp action

## Sharp/Square Divergence
- Sharp = Pinnacle consensus + market direction
- Square = public money on favorites, high-profile teams, or inflated underdogs at soft books
- 43% ML price gap between books on same team = soft books inflating underdog for public action

## Model vs Market Divergence Warning
- If model and Pinnacle diverge by >20pp on a moneyline, DO NOT fade Pinnacle
- Most likely cause: model lacks real-time injury/roster news
- Action: note warning in report, do not include as actionable bet, flag for investigation

## No-Vig Implied Probability
- Always use Pinnacle as reference for true probability
- Formula: p1_nv = (1/dec1) / (1/dec1 + 1/dec2)
- Edge = model_prob - pinnacle_nv_prob
- Quarter-Kelly: edge / (decimal_odds - 1) * 0.25

## Bankroll: $100, Kelly fraction 0.25, min edge threshold 0.02
