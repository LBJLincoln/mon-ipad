# Cross-TF LLM Scorecard -- 2026-04-24 17:01 UTC

Same LLM tested across NBA / POL / ITF. Higher total_bankroll = better LLM across markets.

| LLM | TFs | NBA $ | POL $ | ITF $ | Total $ | Combined WR | Bets |
|---|---|---:|---:|---:|---:|---:|---:|
| `mistral:large` | itf,nba,pol | $56 | $127 | $5826 | $29313 | 51.6% | 128 |
| `mistral:medium` | itf,nba,pol | $77 | $96 | $5826 | $23476 | 47.7% | 107 |
| `cerebras:qwen-3-235b` | itf,nba,pol | $77 | $194 | $5826 | $18254 | 52.3% | 776 |
| `github:gpt-4.1-nano` | itf | - | - | $5826 | $5826 | - | - |
| `github:mistral-medium` | itf | - | - | $5826 | $5826 | - | - |
| `github:gpt-4.1-mini` | itf | - | - | $5826 | $5826 | - | - |
| `github:llama-3.3-70b` | itf | - | - | $5826 | $5826 | - | - |
| `selfhost:phi-4-mini` | itf | - | - | $5826 | $5826 | - | - |
| `google:gemini-3-flash` | nba,pol | $84 | $66 | - | $326 | 47.8% | 429 |
| `cerebras:llama3.1-8b` | nba,pol | $40 | $116 | - | $156 | 50.0% | 412 |
| `selfhost:gemma-3-4b` | nba,pol | $41 | $113 | - | $155 | 38.0% | 50 |
| `selfhost:qwen3-4b` | nba,pol | $59 | $95 | - | $154 | 50.0% | 38 |
| `nvidia:llama-3.3-70b` | nba,pol | $46 | $98 | - | $144 | 31.8% | 22 |
| `mistral:ministral-8b` | nba,pol | $22 | $120 | - | $143 | 36.6% | 93 |
| `selfhost:dolphin3-l32-3b` | nba,pol | $46 | $95 | - | $141 | 29.6% | 27 |
| `nvidia:minimax-m2.7` | nba,pol | $44 | $96 | - | $140 | 34.0% | 50 |
| `mistral:small` | nba,pol | $39 | $98 | - | $137 | 41.4% | 111 |
| `selfhost:qwen3-0.6b` | nba,pol | $30 | $104 | - | $134 | 23.9% | 46 |
| `openrouter:nemotron-120b` | nba,pol | $26 | $104 | - | $129 | 34.7% | 95 |
| `mistral:nemo` | nba,pol | $25 | $98 | - | $123 | 34.6% | 81 |