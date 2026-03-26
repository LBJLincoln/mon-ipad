---
name: tony-bloom
description: Run one Tony Bloom cycle: ingest latest stats/odds → recalibrate models → scan for value bets �
---

Run one Tony Bloom cycle: ingest latest stats/odds → recalibrate models → scan for value bets → select top picks via Kelly.

Arguments: $ARGUMENTS (optional: "odds-only", "recalibrate-only", or "full")

This is the Starlizard-inspired operational loop for daily NBA betting.

## Steps

1. **Ingest latest data** (skip if $ARGUMENTS = "recalibrate-only"):
   ```bash
   cd /home/termius/nomos-nba-agent && source .env.local && python3 ops/ingest-nba.py
   ```
   Pulls: latest game results, player stats, odds from The Odds API.

2. **Fetch live odds**:
   ```bash
   cd /home/termius/nomos-nba-agent && source .env.local && python3 ops/fetch-odds.py --once
   ```
   Sources: Bovada, DraftKings, FanDuel, BetMGM, The Odds API.

3. **Run predictions** (the core model):
   ```bash
   cd /home/termius/nomos-nba-agent && source .env.local && python3 predict_today.py
   ```
   This uses the S10 evolved model (60/40 blend) + ensemble (ELO, Poisson, MC, Power).

4. **Analyze output** — read the predictions JSON:
   - `/home/termius/nomos-nba-agent/data/predictions/predictions-YYYY-MM-DD.json`
   - Extract: games, home_prob, away_prob, evolved_prob, edge, kelly_size
   - Flag value bets: edge > 2% AND kelly_size > 0

5. **Generate picks report**:
   ```
   ## Tony Bloom Daily Picks — YYYY-MM-DD

   **Bankroll**: $XXX | **Model**: v3.0-35cat evolved
   **Games today**: X

   ### Value Bets (edge > 2%)
   | Game | Pick | Prob | Line | Edge | Kelly | Bet |
   |------|------|------|------|------|-------|-----|

   ### Pass (no edge)
   | Game | Best Prob | Line | Edge |
   ```

6. **Update data server files**:
   ```bash
   cp /home/termius/nomos-nba-agent/data/predictions/predictions-*.json /home/termius/mon-ipad/data/nba-agent/latest-picks.json
   ```

7. **Push to git** for Vercel to pick up:
   ```bash
   cd /home/termius/mon-ipad && git add data/nba-agent/latest-picks.json && git commit -m "data: daily picks $(date +%Y-%m-%d)" && git push
   ```

## Constraints
- ZERO ML on VM — predictions use pre-trained models only (no training)
- All predictions tagged with feature_engine_version
- Kelly fraction: 0.25 (quarter Kelly for safety)
- Min edge: 2% | Max bet: 5% of bankroll
