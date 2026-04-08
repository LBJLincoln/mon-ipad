---
name: Model Game ID Mismatch Check
description: Always verify that latest-picks.json home team matches live-odds.json home team before using model probs
type: feedback
---

Always cross-check game identity between `latest-picks.json` and `live-odds.json` before computing edges.

**Why:** On 2026-03-26, latest-picks.json referenced "NYK @ BKN" (Brooklyn Nets as home) while live-odds.json showed Charlotte Hornets as home for the same game slot. Using model probs against wrong team odds would produce false edge signals.

**How to apply:** For each game, confirm home_team string matches between the two files before computing model_prob vs implied_prob edges. If mismatch found: flag as DATA_QUALITY stale pick, exclude from actionable bets, recommend re-running predict_today.py.
