# POL — combination coverage report
Generated 2026-04-25 16:20 UTC

**Theoretical universe per match-day**: 22 event types × ~30 events/day × 8 ETFs × {long,short} ≈ 100k combos/week

Reads: for each agent, how much of the 100k+ combination space did they actually explore?
Homogeneity = share of total bets in the agent's most-picked single category. >50% = template-bleed.

## Activity + coverage table

| agent | bets | par.legs | distinct_cats | distinct_combos | distinct_events | homogeneity | top class |
|---|---:|---:|---:|---:|---:|---:|---|
| `qwen-quant` | 244 | 0 | 1 | 20 | 20 | 100% |  |
| `llama-contra` | 217 | 0 | 1 | 28 | 28 | 100% |  |
| `qwen-arb` | 195 | 0 | 1 | 20 | 20 | 100% |  |
| `gemini-anl` | 154 | 0 | 1 | 20 | 20 | 100% |  |
| `gemini-tact` | 83 | 0 | 1 | 21 | 21 | 100% |  |
| `mistral-large` | 74 | 0 | 1 | 17 | 17 | 100% |  |
| `mistral-small` | 65 | 0 | 1 | 26 | 26 | 100% |  |
| `mistral-medium` | 51 | 0 | 1 | 18 | 18 | 100% |  |
| `mistral-ministral` | 50 | 0 | 1 | 21 | 21 | 100% |  |
| `nemotron-120b` | 40 | 0 | 1 | 11 | 11 | 100% |  |
| `mistral-nemo` | 31 | 0 | 1 | 15 | 15 | 100% |  |
| `nvidia-minimax` | 16 | 0 | 1 | 6 | 6 | 100% |  |
| `selfhost-gemma3` | 14 | 0 | 1 | 10 | 10 | 100% |  |
| `selfhost-qwen06` | 14 | 0 | 1 | 8 | 8 | 100% |  |
| `selfhost-qwen4b` | 6 | 0 | 1 | 6 | 6 | 100% |  |
| `nvidia-llama70` | 6 | 0 | 1 | 6 | 6 | 100% |  |
| `selfhost-dolphin3` | 1 | 0 | 1 | 1 | 1 | 100% |  |

## Per-agent category-class breakdown

**`qwen-quant`** (244 bets): 
**`llama-contra`** (217 bets): 
**`qwen-arb`** (195 bets): 
**`gemini-anl`** (154 bets): 
**`gemini-tact`** (83 bets): 
**`mistral-large`** (74 bets): 
**`mistral-small`** (65 bets): 
**`mistral-medium`** (51 bets): 
**`mistral-ministral`** (50 bets): 
**`nemotron-120b`** (40 bets): 
**`mistral-nemo`** (31 bets): 
**`nvidia-minimax`** (16 bets): 
**`selfhost-gemma3`** (14 bets): 
**`selfhost-qwen06`** (14 bets): 
**`selfhost-qwen4b`** (6 bets): 
**`nvidia-llama70`** (6 bets): 
**`selfhost-dolphin3`** (1 bets): 

## Per-agent top-20 categories (with count)

### `qwen-quant`
- distinct cats: 1 — distinct combos: 20 — homogeneity: 100%
  - `insider_trade`: 244 (100.0%)

### `llama-contra`
- distinct cats: 1 — distinct combos: 28 — homogeneity: 100%
  - `insider_trade`: 217 (100.0%)

### `qwen-arb`
- distinct cats: 1 — distinct combos: 20 — homogeneity: 100%
  - `insider_trade`: 195 (100.0%)

### `gemini-anl`
- distinct cats: 1 — distinct combos: 20 — homogeneity: 100%
  - `insider_trade`: 154 (100.0%)

### `gemini-tact`
- distinct cats: 1 — distinct combos: 21 — homogeneity: 100%
  - `insider_trade`: 83 (100.0%)

### `mistral-large`
- distinct cats: 1 — distinct combos: 17 — homogeneity: 100%
  - `insider_trade`: 74 (100.0%)

### `mistral-small`
- distinct cats: 1 — distinct combos: 26 — homogeneity: 100%
  - `insider_trade`: 65 (100.0%)

### `mistral-medium`
- distinct cats: 1 — distinct combos: 18 — homogeneity: 100%
  - `insider_trade`: 51 (100.0%)

### `mistral-ministral`
- distinct cats: 1 — distinct combos: 21 — homogeneity: 100%
  - `insider_trade`: 50 (100.0%)

### `nemotron-120b`
- distinct cats: 1 — distinct combos: 11 — homogeneity: 100%
  - `insider_trade`: 40 (100.0%)

### `mistral-nemo`
- distinct cats: 1 — distinct combos: 15 — homogeneity: 100%
  - `insider_trade`: 31 (100.0%)

### `nvidia-minimax`
- distinct cats: 1 — distinct combos: 6 — homogeneity: 100%
  - `insider_trade`: 16 (100.0%)

### `selfhost-gemma3`
- distinct cats: 1 — distinct combos: 10 — homogeneity: 100%
  - `insider_trade`: 14 (100.0%)

### `selfhost-qwen06`
- distinct cats: 1 — distinct combos: 8 — homogeneity: 100%
  - `insider_trade`: 14 (100.0%)

### `selfhost-qwen4b`
- distinct cats: 1 — distinct combos: 6 — homogeneity: 100%
  - `insider_trade`: 6 (100.0%)

### `nvidia-llama70`
- distinct cats: 1 — distinct combos: 6 — homogeneity: 100%
  - `insider_trade`: 6 (100.0%)

### `selfhost-dolphin3`
- distinct cats: 1 — distinct combos: 1 — homogeneity: 100%
  - `insider_trade`: 1 (100.0%)
