# Political Trading Season 2025-26 -- Agent GEMMA 3 27B

## Executive Summary
- **Provider:** hf:google/gemma-3-27b-it
- **Personality:** analytical
- **Risk Tolerance:** 0.6
- **Primary Strategy:** momentum
- **Secondary:** sector_rotation, vol_scaled
- **Initial Capital:** $100,000.00
- **Final Capital:** $100,236.42
- **ROI:** +0.2364%
- **Sharpe Ratio:** 6.827
- **Record:** 7W-3L
- **Win Rate:** 70.0%
- **Peak Capital:** $100,236.42
- **Max Drawdown:** 0.1%
- **Wagered:** $27,683.82

## Peer Comparison
| Rank | Agent | Capital | ROI | Sharpe | WR | Trades |
|------|-------|---------|-----|--------|-----|--------|
| 1 | Llama 3.3 70B | $100,562.16 | +0.5622% | 5.620 | 60.0% | 5 |
| 2 | Gemma 3 27B ** | $100,236.42 | +0.2364% | 6.827 | 70.0% | 10 |
| 3 | Mistral Large 2 | $100,009.22 | +0.0092% | 4.786 | 50.0% | 2 |
| 4 | Qwen 3 72B | $100,302.13 | +0.3021% | 9.651 | 66.7% | 9 |
| 5 | Claude Code CLI | $100,000.00 | +0.0000% | 0.000 | 0.0% | 0 |

## Strategy Performance
| Strategy | Trades | P&L | Win Rate |
|----------|--------|-----|----------|
| momentum | 9 | $+209.42 | 66.7% |
| sector_rotation | 1 | $+27.00 | 100.0% |

## Sector Performance
| Sector | P&L |
|--------|-----|
| technology | $+139.31 |
| broad | $+136.51 |
| defense | $-39.40 |

## Day-by-Day Results
| Day | Date | Events | Trades | P&L | Capital |
|-----|------|--------|--------|-----|---------|
| 1 | 2026-03-12 | 3 | 1 | $+14.76 | $100,014.76 |
| 2 | 2026-03-13 | 10 | 1 | $+80.89 | $100,095.65 |
| 3 | 2026-03-16 | 10 | 1 | $+12.40 | $100,108.05 |
| 4 | 2026-03-17 | 16 | 1 | $-14.39 | $100,093.66 |
| 5 | 2026-03-18 | 16 | 1 | $-39.40 | $100,054.26 |
| 6 | 2026-03-19 | 6 | 0 | $+0.00 | $100,054.26 |
| 7 | 2026-03-20 | 10 | 0 | $+0.00 | $100,054.26 |
| 8 | 2026-03-23 | 34 | 1 | $+11.69 | $100,065.95 |
| 9 | 2026-03-24 | 26 | 1 | $-8.25 | $100,057.70 |
| 10 | 2026-03-25 | 10 | 1 | $+39.41 | $100,097.11 |
| 11 | 2026-03-26 | 971 | 2 | $+139.31 | $100,236.42 |
| 12 | 20260326 | 8 | 0 | $+0.00 | $100,236.42 |

## Trade Log (first 30 + last 30 of 10 total)

### 2026-03-12 | SPY | long
- **Strategy:** momentum | **Signal:** 0.750
- **Size:** $3,000.00 | **Return:** +0.492%
- **Win** -> P&L $+14.76
- **Reasoning:** strategy=momentum | signal=0.750 long | event=fed_rule | beta=1.0

### 2026-03-13 | SPY | long
- **Strategy:** momentum | **Signal:** 1.000
- **Size:** $3,000.44 | **Return:** +2.696%
- **Win** -> P&L $+80.89
- **Reasoning:** strategy=momentum | signal=1.000 long | event=fed_rule | beta=1.0

### 2026-03-16 | SPY | long
- **Strategy:** momentum | **Signal:** 1.000
- **Size:** $3,002.87 | **Return:** +0.413%
- **Win** -> P&L $+12.40
- **Reasoning:** strategy=momentum | signal=1.000 long | event=fed_rule | beta=1.0

### 2026-03-17 | SPY | short
- **Strategy:** momentum | **Signal:** 1.000
- **Size:** $3,003.24 | **Return:** -0.479%
- **Loss** -> P&L $-14.39
- **Reasoning:** strategy=momentum | signal=1.000 short | event=fed_rule | beta=1.0

### 2026-03-18 | BA | short
- **Strategy:** momentum | **Signal:** 1.000
- **Size:** $3,002.81 | **Return:** -1.312%
- **Loss** -> P&L $-39.40
- **Reasoning:** strategy=momentum | signal=1.000 short | event=exec_order | beta=1.2

### 2026-03-23 | SPY | long
- **Strategy:** momentum | **Signal:** 1.000
- **Size:** $3,001.63 | **Return:** +0.389%
- **Win** -> P&L $+11.69
- **Reasoning:** strategy=momentum | signal=1.000 long | event=fed_rule | beta=1.0

### 2026-03-24 | SPY | long
- **Strategy:** momentum | **Signal:** 1.000
- **Size:** $3,001.98 | **Return:** -0.275%
- **Loss** -> P&L $-8.25
- **Reasoning:** strategy=momentum | signal=1.000 long | event=fed_rule | beta=1.0

### 2026-03-25 | SPY | long
- **Strategy:** momentum | **Signal:** 1.000
- **Size:** $3,001.73 | **Return:** +1.313%
- **Win** -> P&L $+39.41
- **Reasoning:** strategy=momentum | signal=1.000 long | event=fed_rule | beta=1.0

### 2026-03-26 | AMZN | long
- **Strategy:** sector_rotation | **Signal:** 0.168
- **Size:** $1,209.13 | **Return:** +2.233%
- **Win** -> P&L $+27.00
- **Reasoning:** strategy=sector_rotation | signal=0.168 long | event=insider_trade | beta=1.2

### 2026-03-26 | TSLA | short
- **Strategy:** momentum | **Signal:** 0.410
- **Size:** $2,459.99 | **Return:** +4.565%
- **Win** -> P&L $+112.31
- **Reasoning:** strategy=momentum | signal=0.410 short | event=insider_trade | beta=1.8
