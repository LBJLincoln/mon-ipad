# Forensic Cross-TF Summary — 2026-04-24

17 agents × 3 Trading Floors (NBA + POL + ITF). Top findings by severity.

## Top findings (by severity)

| sev | category | detail |
|---|---|---|
| S1 | POL MONOCULTURE | `qwen-quant` — category=`insider_trade` 96.0% (143/149 bets), PnL=-902.7 |
| S1 | POL MONOCULTURE | `qwen-arb` — category=`insider_trade` 99.3% (134/135 bets), PnL=-5650.0 |
| S1 | NBA SINGLE-DAY-BLOWUP | `mistral-small` worst day d17=-423.1 (total PnL -357.2, 13 bets) |
| S1 | POL SINGLE-DAY-BLOWUP | `qwen-quant` worst day d303=-998.7 (total PnL -902.7, 149 bets) |
| S1 | POL SINGLE-DAY-BLOWUP | `qwen-arb` worst day d303=-6861.6 (total PnL -5650.0, 135 bets) |
| S2 | NBA MONOCULTURE | `nvidia-minimax` — category=`ml_home` 84.2% (101/120 bets), PnL=+17.0 |
| S2 | NBA MONOCULTURE | `nvidia-llama70` — category=`ml_home` 82.0% (105/128 bets), PnL=+12.4 |
| S2 | NBA MONOCULTURE | `selfhost-qwen06` — category=`ml_home` 82.6% (100/121 bets), PnL=+65.0 |
| S2 | POL MONOCULTURE | `llama-contra` — category=`insider_trade` 94.2% (146/155 bets), PnL=+0.4 |
| S2 | POL MONOCULTURE | `gemini-anl` — category=`insider_trade` 95.5% (105/110 bets), PnL=+65.4 |
| S2 | POL MONOCULTURE | `gemini-tact` — category=`insider_trade` 98.1% (106/108 bets), PnL=-12.4 |
| S2 | POL MONOCULTURE | `mistral-large` — category=`insider_trade` 99.0% (97/98 bets), PnL=-11.6 |
| S2 | POL MONOCULTURE | `mistral-medium` — category=`insider_trade` 97.4% (76/78 bets), PnL=+34.7 |
| S2 | POL MONOCULTURE | `mistral-small` — category=`insider_trade` 95.0% (96/101 bets), PnL=+32.6 |
| S2 | POL MONOCULTURE | `mistral-nemo` — category=`insider_trade` 98.5% (65/66 bets), PnL=-3.9 |

## TF roll-up

| TF | days | total bets | total PnL | anomalies |
|---|---:|---:|---:|---:|
| NBA | 54 | 1154 | -245.49 | 18 |
| POL | 55 | 1618 | -6559.44 | 33 |
| ITF | 1 | 40 | +0.00 | 0 |
