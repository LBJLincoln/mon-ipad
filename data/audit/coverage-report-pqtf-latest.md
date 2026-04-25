# PQTF — combination coverage report
Generated 2026-04-25 16:20 UTC

**Theoretical universe per match-day**: 12 ETFs × {call,put} × multi-strike × tte 2-5d ≈ 50k positions/session

Reads: for each agent, how much of the 100k+ combination space did they actually explore?
Homogeneity = share of total bets in the agent's most-picked single category. >50% = template-bleed.

## Activity + coverage table

| agent | bets | par.legs | distinct_cats | distinct_combos | distinct_events | homogeneity | top class |
|---|---:|---:|---:|---:|---:|---:|---|
| `mistral-large` | 505 | 0 | 3 | 29 | 12 | 45% |  |
| `mistral-medium` | 497 | 0 | 3 | 29 | 11 | 46% |  |
| `mistral-nemo` | 266 | 0 | 3 | 28 | 11 | 49% |  |
| `gemini-anl` | 87 | 0 | 3 | 18 | 10 | 67% |  |
| `qwen-quant` | 4 | 0 | 2 | 3 | 3 | 75% |  |
| `llama-contra` | 2 | 0 | 2 | 2 | 2 | 50% |  |

## Per-agent category-class breakdown

**`mistral-large`** (505 bets): 
**`mistral-medium`** (497 bets): 
**`mistral-nemo`** (266 bets): 
**`gemini-anl`** (87 bets): 
**`qwen-quant`** (4 bets): 
**`llama-contra`** (2 bets): 

## Per-agent top-20 categories (with count)

### `mistral-large`
- distinct cats: 3 — distinct combos: 29 — homogeneity: 45%
  - `call`: 225 (44.6%)
  - `?`: 221 (43.8%)
  - `put`: 59 (11.7%)

### `mistral-medium`
- distinct cats: 3 — distinct combos: 29 — homogeneity: 46%
  - `?`: 231 (46.5%)
  - `call`: 168 (33.8%)
  - `put`: 98 (19.7%)

### `mistral-nemo`
- distinct cats: 3 — distinct combos: 28 — homogeneity: 49%
  - `?`: 131 (49.2%)
  - `call`: 92 (34.6%)
  - `put`: 43 (16.2%)

### `gemini-anl`
- distinct cats: 3 — distinct combos: 18 — homogeneity: 67%
  - `?`: 58 (66.7%)
  - `call`: 22 (25.3%)
  - `put`: 7 (8.0%)

### `qwen-quant`
- distinct cats: 2 — distinct combos: 3 — homogeneity: 75%
  - `call`: 3 (75.0%)
  - `put`: 1 (25.0%)

### `llama-contra`
- distinct cats: 2 — distinct combos: 2 — homogeneity: 50%
  - `call`: 1 (50.0%)
  - `put`: 1 (50.0%)
