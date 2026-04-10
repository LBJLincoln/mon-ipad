# Political Trading Season 2025-26 -- Agent QWEN 3 72B

## Executive Summary
- **Provider:** hf:Qwen/Qwen2.5-72B-Instruct
- **Personality:** diversified
- **Risk Tolerance:** 0.5
- **Primary Strategy:** sector_rotation
- **Secondary:** insider_follow, pairs_trading
- **Initial Capital:** $100,000.00
- **Final Capital:** $100,302.13
- **ROI:** +0.3021%
- **Sharpe Ratio:** 9.651
- **Record:** 6W-3L
- **Win Rate:** 66.7%
- **Peak Capital:** $100,302.13
- **Max Drawdown:** 0.0%
- **Wagered:** $24,528.77

## Peer Comparison
| Rank | Agent | Capital | ROI | Sharpe | WR | Trades |
|------|-------|---------|-----|--------|-----|--------|
| 1 | Llama 3.3 70B | $100,562.16 | +0.5622% | 5.620 | 60.0% | 5 |
| 2 | Gemma 3 27B | $100,236.42 | +0.2364% | 6.827 | 70.0% | 10 |
| 3 | Mistral Large 2 | $100,009.22 | +0.0092% | 4.786 | 50.0% | 2 |
| 4 | Qwen 3 72B ** | $100,302.13 | +0.3021% | 9.651 | 66.7% | 9 |
| 5 | Claude Code CLI | $100,000.00 | +0.0000% | 0.000 | 0.0% | 0 |

## Strategy Performance
| Strategy | Trades | P&L | Win Rate |
|----------|--------|-----|----------|
| sector_rotation | 5 | $+272.67 | 80.0% |
| pairs_trading | 1 | $+30.81 | 100.0% |
| insider_follow | 3 | $-1.35 | 33.3% |

## Sector Performance
| Sector | P&L |
|--------|-----|
| broad | $+219.09 |
| energy | $+83.04 |

## Day-by-Day Results
| Day | Date | Events | Trades | P&L | Capital |
|-----|------|--------|--------|-----|---------|
| 1 | 2026-03-12 | 3 | 1 | $+57.82 | $100,057.82 |
| 2 | 2026-03-13 | 10 | 1 | $+30.81 | $100,088.63 |
| 3 | 2026-03-16 | 10 | 1 | $-18.19 | $100,070.44 |
| 4 | 2026-03-17 | 16 | 1 | $+70.27 | $100,140.71 |
| 5 | 2026-03-18 | 16 | 0 | $+0.00 | $100,140.71 |
| 6 | 2026-03-19 | 6 | 0 | $+0.00 | $100,140.71 |
| 7 | 2026-03-20 | 10 | 0 | $+0.00 | $100,140.71 |
| 8 | 2026-03-23 | 34 | 1 | $-40.98 | $100,099.73 |
| 9 | 2026-03-24 | 26 | 1 | $+21.42 | $100,121.15 |
| 10 | 2026-03-25 | 10 | 1 | $+97.94 | $100,219.09 |
| 11 | 2026-03-26 | 971 | 2 | $+83.04 | $100,302.13 |
| 12 | 20260326 | 8 | 0 | $+0.00 | $100,302.13 |

## Trade Log (first 30 + last 30 of 9 total)

### 2026-03-12 | SPY | long
- **Strategy:** insider_follow | **Signal:** 0.998
- **Size:** $2,500.00 | **Return:** +2.313%
- **Win** -> P&L $+57.82
- **Reasoning:** strategy=insider_follow | signal=0.998 long | event=fed_rule | beta=1.0

### 2026-03-13 | SPY | long
- **Strategy:** pairs_trading | **Signal:** 1.000
- **Size:** $2,001.16 | **Return:** +1.540%
- **Win** -> P&L $+30.81
- **Reasoning:** strategy=pairs_trading | signal=1.000 long | event=fed_rule | beta=1.0

### 2026-03-16 | SPY | long
- **Strategy:** insider_follow | **Signal:** 1.000
- **Size:** $2,502.22 | **Return:** -0.727%
- **Loss** -> P&L $-18.19
- **Reasoning:** strategy=insider_follow | signal=1.000 long | event=fed_rule | beta=1.0

### 2026-03-17 | SPY | short
- **Strategy:** sector_rotation | **Signal:** 1.000
- **Size:** $3,002.11 | **Return:** +2.341%
- **Win** -> P&L $+70.27
- **Reasoning:** strategy=sector_rotation | signal=1.000 short | event=fed_rule | beta=1.0

### 2026-03-23 | SPY | long
- **Strategy:** insider_follow | **Signal:** 1.000
- **Size:** $2,503.52 | **Return:** -1.637%
- **Loss** -> P&L $-40.98
- **Reasoning:** strategy=insider_follow | signal=1.000 long | event=fed_rule | beta=1.0

### 2026-03-24 | SPY | long
- **Strategy:** sector_rotation | **Signal:** 1.000
- **Size:** $3,002.99 | **Return:** +0.713%
- **Win** -> P&L $+21.42
- **Reasoning:** strategy=sector_rotation | signal=1.000 long | event=fed_rule | beta=1.0

### 2026-03-25 | SPY | long
- **Strategy:** sector_rotation | **Signal:** 1.000
- **Size:** $3,003.63 | **Return:** +3.261%
- **Win** -> P&L $+97.94
- **Reasoning:** strategy=sector_rotation | signal=1.000 long | event=fed_rule | beta=1.0

### 2026-03-26 | CVX | short
- **Strategy:** sector_rotation | **Signal:** 1.000
- **Size:** $3,006.57 | **Return:** +3.564%
- **Win** -> P&L $+107.15
- **Reasoning:** strategy=sector_rotation | signal=1.000 short | event=insider_trade | beta=0.9

### 2026-03-26 | OXY | long
- **Strategy:** sector_rotation | **Signal:** 1.000
- **Size:** $3,006.57 | **Return:** -0.802%
- **Loss** -> P&L $-24.11
- **Reasoning:** strategy=sector_rotation | signal=1.000 long | event=insider_trade | beta=1.4
