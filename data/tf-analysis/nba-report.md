# NBA TF Post-Mortem — 44 days analyzed
Space: `LBJLincoln26/nba-llm-trading-floor`

## Leaderboard (by final bankroll)
| rank | trader | final | peak | drawdown | peak_day |
|------|--------|-------|------|----------|----------|
| 1 | `mistral-ministral` | $2,149.90 | $10,098.22 | 78.7% | 12 |
| 2 | `selfhost-qwen4b` | $148.03 | $588.98 | 74.9% | 17 |
| 3 | `qwen-arb` | $107.33 | $285.40 | 62.4% | 24 |
| 4 | `selfhost-qwen06` | $56.53 | $263.43 | 78.5% | 24 |
| 5 | `llama-contra` | $35.02 | $100.95 | 65.3% | 7 |
| 6 | `nemotron-120b` | $35.02 | $100.95 | 65.3% | 7 |
| 7 | `nvidia-minimax` | $35.02 | $100.95 | 65.3% | 7 |
| 8 | `mistral-small` | $30.66 | $100.00 | 69.3% | 0 |
| 9 | `selfhost-gemma3` | $29.06 | $139.54 | 79.2% | 6 |
| 10 | `gemini-tact` | $24.94 | $76.50 | 67.4% | 0 |
| 11 | `mistral-large` | $23.18 | $66.81 | 65.3% | 7 |
| 12 | `mistral-medium` | $23.18 | $66.81 | 65.3% | 7 |
| 13 | `qwen-quant` | $21.96 | $66.83 | 67.1% | 0 |
| 14 | `mistral-nemo` | $19.03 | $62.28 | 69.4% | 0 |
| 15 | `nvidia-llama70` | $18.94 | $65.68 | 71.2% | 0 |
| 16 | `gemini-anl` | $17.22 | $65.02 | 73.5% | 0 |
| 17 | `selfhost-dolphin3` | $4.57 | $100.00 | 95.4% | 0 |

## Top peak-rationales (what winners thought at their best day)

### mistral-ministral — peak $10,098.22 on day 12
- d12 ($10,098.22): Deploy high‑edge moneylines aggressively while keeping cash low to meet the 75% deployment rule.
- d13 ($8,741.24): Focus on high‑edge away moneylines where model win probability exceeds market implied odds, using half‑Kelly sizing and a small parlay to boost ROI.

### selfhost-qwen4b — peak $588.98 on day 17
- d17 ($588.98): Focus on high‑edge moneyline on IND (away) and diversify with a modest spread on GSW and a team‑total prop on OKC to meet deployment targets.
- d16 ($493.56): Deploy high‑edge moneylines across diverse games, focusing on model‑probability advantage while keeping cash low.

### qwen-arb — peak $285.40 on day 24
- d24 ($285.40): {"":0}
- d9 ($265.92): Target undervalued total over bets where model predicts higher scoring than the market total, and combine two legs into a modest parlay for extra edge.

## Top 8 gainers (single-day jumps ≥+10%)
- `mistral-ministral` d4 2025-10-07: $96.63→$1386.15 (+1334.49%) — Focus on high edge away ML in IND@MIN and complementary spread/total bets on CHI@CLE, using modest parlay combos to boost ROI while meeting deployment
- `selfhost-qwen06` d11 2025-10-14: $53.79→$134.41 (+149.88%) — Focus on high‑edge away moneylines where the model shows a strong probability advantage over market odds, using half‑Kelly sizing and a small parlay f
- `mistral-ministral` d11 2025-10-14: $3164.05→$7517.41 (+137.59%) — Focus on high‑edge away moneylines where model probability exceeds market odds, using half‑Kelly sizing and a small parlay for extra upside.
- `selfhost-qwen4b` d11 2025-10-14: $150.93→$291.52 (+93.15%) — Focus on clear positive edge moneylines and a total over where model predicts higher scoring than market, using half‑Kelly sizing.
- `selfhost-qwen4b` d4 2025-10-07: $140.25→$260.38 (+85.65%) — Focus on modest positive edges in moneylines and spreads, using half‑kelly sizing and a small correlated parlay to boost edge while keeping cash low.
- `mistral-ministral` d2 2025-10-05: $65.89→$117.28 (+77.99%) — Focus on positive model edges in moneylines and totals, using a modest parlay to boost expected return while keeping cash low.
- `selfhost-gemma3` d6 2025-10-09: $81.74→$139.54 (+70.71%) — Deploy majority of bankroll on high‑edge home moneylines and a complementary spread, with a small parlay to boost upside while keeping cash minimal.
- `selfhost-gemma3` d29 2025-11-04: $26.86→$45.37 (+68.91%) — Aggressive rescue-mode allocation targeting high-variance alt spreads and quarters in games with model edges >5%. Prioritize alt_spread_away_plus5-10 

## Top 8 crashes (single-day drops ≤−20%)
- `selfhost-dolphin3` d34 2025-11-09: $16.12→$8.50 (-47.27%) — DEFECT: drawdown. Pavlov momentum on highest-edge alt spreads and quarters after yesterday's ml_home losses. Chase high-variance props to recover posi
- `gemini-tact` d34 2025-11-09: $51.04→$26.92 (-47.26%) — CONSENSUS AGREE [mistral-ministral]: Leveraging schedule-based edges on high-tempo favorites while utilizing first-half markets to mitigate late-game 
- `mistral-nemo` d34 2025-11-09: $38.87→$20.50 (-47.26%) — RESCUE MODE: Target high-variance alt spreads and underdog moneylines with strong player matchups and rest advantages. Deploy ≥85% of bankroll on 3+ h
- `qwen-quant` d34 2025-11-09: $44.91→$23.69 (-47.25%) — {"":0}
- `llama-contra` d34 2025-11-09: $71.52→$37.73 (-47.25%) — Focus on contrarian spreads and underdog values where public sentiment is heavily skewed.
- `nemotron-120b` d34 2025-11-09: $71.52→$37.73 (-47.25%) — {"":[]}
- `nvidia-minimax` d34 2025-11-09: $71.52→$37.73 (-47.25%) — <think>Let me analyze this carefully. I'm NVIDIA MiniMax M2.7 with $71.52 bankroll, at -28.5% ROI. I need to deploy at least 75% of my bankroll today 
- `selfhost-qwen06` d34 2025-11-09: $136.64→$72.08 (-47.25%) — fallback-injection: LLM silent, forcing 75% deploy on first 5 games (ml_home)