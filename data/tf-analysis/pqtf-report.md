# PQTF Post-Mortem — 2 days analyzed
Space: `LBJLincoln26/political-quant-trading-floor`
Agents: gemini-anl, llama-contra, mistral-large, mistral-medium, mistral-nemo, qwen-quant

## Leaderboard (by final bankroll)
| rank | trader | start | final | ROI% | peak | max_dd | sharpe | peak_day |
|------|--------|-------|-------|------|------|--------|--------|----------|
| 1 | `mistral-large` | $118,144 | $413,087 | +249.6% | $413,087 | 0.0% | 14.936 | None |
| 2 | `mistral-medium` | $125,669 | $270,316 | +115.1% | $270,316 | 0.0% | 10.736 | None |
| 3 | `gemini-anl` | $113,104 | $262,017 | +131.7% | $262,017 | 0.0% | 10.253 | None |
| 4 | `mistral-nemo` | $121,671 | $230,081 | +89.1% | $230,081 | 0.0% | 48.051 | None |
| 5 | `qwen-quant` | $101,198 | $124,204 | +22.7% | $124,204 | 0.0% | -21.319 | None |
| 6 | `llama-contra` | $98,542 | $105,481 | +7.0% | $105,481 | 0.0% | -11.225 | None |

## Sharpe ranking
- `mistral-nemo`: Sharpe=48.051, ROI=+89.1%, max_dd=0.0%, recovery=1d
- `mistral-large`: Sharpe=14.936, ROI=+249.6%, max_dd=0.0%, recovery=1d
- `mistral-medium`: Sharpe=10.736, ROI=+115.1%, max_dd=0.0%, recovery=1d
- `gemini-anl`: Sharpe=10.253, ROI=+131.7%, max_dd=0.0%, recovery=1d
- `llama-contra`: Sharpe=-11.225, ROI=+7.0%, max_dd=0.0%, recovery=1d
- `qwen-quant`: Sharpe=-21.319, ROI=+22.7%, max_dd=0.0%, recovery=1d

## Multi-leg strategy breakdown
- **call**: 23 positions (69.7%) — PnL contribution: $0.00
- **put**: 10 positions (30.3%) — PnL contribution: $0.00

## Session-Jaccard lockstep detection
- Max session-Jaccard: 0.156 — Mean: 0.091 — Status: **OK**

## Peak-day rationales (top 2 agents)

### mistral-large — peak $413,087 on day None
- dNone ($413,087): 8 positions — ETFs: XLC, XLE, XLF, XLK
- dNone ($119,057): 8 positions — ETFs: XLE, XLK

### mistral-medium — peak $270,316 on day None
- dNone ($270,316): 10 positions — ETFs: XLC, XLE, XLF, XLK, XLP
- dNone ($125,465): 7 positions — ETFs: XLE, XLF, XLK

## Top 10 single-day gainers (≥+5% daily)
- `mistral-medium` dNone 2026-04-02: $251,988→$270,316 (+7.27%) — 10 positions
- `mistral-large` dNone 2026-04-02: $391,740→$413,087 (+5.45%) — 8 positions

## Top 10 single-day crashes (≤−15% daily)