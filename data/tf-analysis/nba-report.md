# NBA TF Post-Mortem — 55 days analyzed
Space: `LBJLincoln26/nba-llm-trading-floor`

## Leaderboard (by final bankroll)
| rank | trader | final | peak | drawdown | peak_day |
|------|--------|-------|------|----------|----------|
| 1 | `nvidia-llama70` | $166.12 | $166.12 | 0.0% | 41 |
| 2 | `selfhost-qwen06` | $113.79 | $113.79 | 0.0% | 31 |
| 3 | `nemotron-120b` | $100.00 | $100.00 | 0.0% | 0 |
| 4 | `selfhost-dolphin3` | $100.00 | $100.00 | 0.0% | 0 |
| 5 | `qwen-quant` | $97.99 | $164.64 | 40.5% | 40 |
| 6 | `selfhost-gemma3` | $64.53 | $224.16 | 71.2% | 51 |
| 7 | `mistral-large` | $46.13 | $85.10 | 45.8% | 0 |
| 8 | `mistral-nemo` | $26.66 | $106.27 | 74.9% | 7 |
| 9 | `gemini-tact` | $18.97 | $72.00 | 73.7% | 0 |
| 10 | `llama-contra` | $18.34 | $85.69 | 78.6% | 0 |
| 11 | `qwen-arb` | $16.08 | $117.24 | 86.3% | 7 |
| 12 | `mistral-ministral` | $10.66 | $100.44 | 89.4% | 7 |
| 13 | `mistral-small` | $4.63 | $580.07 | 99.2% | 7 |
| 14 | `gemini-anl` | $4.60 | $74.55 | 93.8% | 0 |
| 15 | `nvidia-minimax` | $3.18 | $100.00 | 96.8% | 0 |
| 16 | `selfhost-qwen4b` | $3.03 | $88.47 | 96.6% | 7 |
| 17 | `mistral-medium` | $2.81 | $149.46 | 98.1% | 3 |

## Top peak-rationales (what winners thought at their best day)

### nvidia-llama70 — peak $166.12 on day 41
- d41 ($166.12): STRUCTURAL DIVERGE [qwen-quant]: My EV-threshold-first approach prioritizes ml_home in game 1 (LAC @ BOS) due to a 6.2% edge, while qwen-quant may focus on other categories. Today, I will allocate on high-edge moneylines and spreads.
- d42 ($166.12): 

### selfhost-qwen06 — peak $113.79 on day 31
- d31 ($113.79): STRUCTURAL DIVERGE [SelfHost Gemma-3-4B]: My approach focuses on wide flat-stake coverage across many categories, while Gemma-3-4B uses high-conviction bets. I will spread tiny flat bets across multiple categories to diversify risk.
- d32 ($113.79): 

### nemotron-120b — peak $100.00 on day 0
- d0 ($100.00): 
- d1 ($100.00): 

## Top 10 gainers (single-day jumps ≥+10%)
- `mistral-ministral` d38 2025-11-13: $6.95→$13.68 (+96.83%) — STRUCTURAL DIVERGE [Momentum Hunter]: my KL‑divergence edge detector flags game2 ml_home and game3 ml_away as high‑conviction despite their modest mar
- `mistral-nemo` d45 2025-11-20: $29.13→$53.65 (+84.17%) — STRUCTURAL DIVERGE [SelfHost Gemma-3-4B]: My approach focuses on high-conviction allocations based on momentum and player matchups, diverging from the
- `mistral-ministral` d45 2025-11-20: $29.43→$51.90 (+76.35%) — STRUCTURAL DIVERGE [Qwen Quant]: my KL‑divergence edge detector flags games where the model probability exceeds market implied odds, producing picks t
- `mistral-nemo` d43 2025-11-18: $20.39→$35.85 (+75.82%) — STRUCTURAL DIVERGE [SelfHost Gemma-3-4B]: My approach focuses on high-conviction bets with significant edges, particularly in player-influenced totals
- `nvidia-minimax` d43 2025-11-18: $13.73→$24.01 (+74.87%) — STRUCTURAL DIVERGE [qwen-quant]: My long-context scan prioritizes alt-spreads and half-kelly sizing, diverging from qwen-quant's EV-threshold-first ap
- `mistral-ministral` d24 2025-10-30: $48.99→$84.51 (+72.5%) — STRUCTURAL DIVERGE [qwen-quant]: my KL-divergence edge model flags high probability ml_away for ORL@CHA whereas qwen-quant focuses on spreads, so I pi
- `mistral-ministral` d43 2025-11-18: $16.76→$27.53 (+64.26%) — STRUCTURAL DIVERGE [Qwen Quant]: my KL-divergence edge detector flags game2 ml_away and game5 ml_home as high‑edge picks unlike Qwen Quant who focused
- `selfhost-gemma3` d51 2025-11-26: $140.13→$224.16 (+59.97%) — STRUCTURAL DIVERGE [nvidia-llama70]: My weighted-factor model (0.4 form, 0.3 rest, 0.3 home) prioritizes ml_away on underdogs with strong rest advanta
- `mistral-ministral` d41 2025-11-16: $12.05→$17.50 (+45.23%) — STRUCTURAL DIVERGE [Momentum Hunter]: my KL-divergence edge detector flags game2 ml_home as high edge while Momentum Hunter focuses on spreads, giving
- `mistral-small` d0 2025-10-03: $100.00→$139.71 (+39.71%) — STRUCTURAL DIVERGE [qwen-quant] — Today’s council plan focuses on correlated parlays, but I prioritize single-leg edges with higher confidence and low

## Top 10 crashes (single-day drops ≤−20%)
- `gemini-anl` d23 2025-10-29: $15.32→$4.60 (-69.97%) — STRUCTURAL COMPLEMENT [mistral-small]: While the leader targets high-volume favorites, my FIRST-PRINCIPLES DECOMPOSITION focuses on mispriced moneylin
- `mistral-medium` d29 2025-11-04: $9.34→$2.81 (-69.91%) — STRUCTURAL DIVERGE [Mistral Small]: My diversified portfolio approach focuses on spreading risk across multiple games and categories, avoiding high co
- `selfhost-qwen4b` d37 2025-11-12: $10.03→$3.03 (-69.79%) — STRUCTURAL DIVERGE [qwen-quant]: My eighth_kelly KL-divergence template flags high-conviction edges in team totals and halves, where market inefficien
- `mistral-medium` d26 2025-11-01: $27.56→$8.86 (-67.85%) — STRUCTURAL DIVERGE [Mistral Small]: My diversified portfolio approach focuses on spreading risk across multiple games and categories, avoiding high-ri
- `mistral-small` d28 2025-11-03: $14.11→$4.63 (-67.19%) — STRUCTURAL DIVERGE [qwen-quant]: My eighth_kelly + drawdown_adjusted template targets alt-markets and halves where model edges are softest, avoiding c
- `mistral-small` d3 2025-10-06: $15.90→$5.28 (-66.79%) — STRUCTURAL DIVERGE [mistral-medium]: Today’s council plan targets home moneyline favorites, but my Cooperator template prioritizes alt-markets and tea
- `mistral-small` d27 2025-11-02: $38.75→$14.11 (-63.59%) — STRUCTURAL DIVERGE [qwen-quant]: My eighth_kelly + drawdown_adjusted template targets high-conviction edges in alt-markets (team totals, halves) where
- `mistral-nemo` d29 2025-11-04: $37.61→$14.45 (-61.58%) — STRUCTURAL DIVERGE [SelfHost Gemma-3-4B]: My approach focuses on high-conviction allocations based on player matchups and form streaks, diverging from
- `mistral-ministral` d35 2025-11-10: $14.50→$6.03 (-58.41%) — STRUCTURAL DIVERGE [qwen-quant]: I use a flat_1pct sizing based on KL‑divergence rather than eighth_kelly, leading me to pick the next‑best high‑edge 
- `nvidia-minimax` d38 2025-11-13: $71.14→$31.00 (-56.42%) — STRUCTURAL DIVERGE [qwen-quant]: My long-context scan prioritizes alt-spreads and team totals where qwen-quant’s flat_1pct template underweights cross