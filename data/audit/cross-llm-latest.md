# Cross-TF LLM Scorecard -- 2026-04-25 12:55 UTC

Same LLM tested across NBA / POL / ITF. Higher total_bankroll = better LLM across markets.

| LLM | TFs | NBA $ | POL $ | ITF $ | Total $ | Combined WR | Bets |
|---|---|---:|---:|---:|---:|---:|---:|
| `mistral:large` | itf,nba,pol | $57 | $100 | $7795 | $39695 | 30.2% | 43 |
| `mistral:medium` | itf,nba,pol | $86 | $102 | $7884 | $31632 | 45.0% | 20 |
| `cerebras:qwen-3-235b` | itf,nba,pol | $67 | $91 | $7857 | $23121 | 42.6% | 195 |
| `github:mistral-medium` | itf | - | - | $7849 | $7849 | - | - |
| `github:gpt-4.1-nano` | itf | - | - | $7796 | $7796 | - | - |
| `github:llama-3.3-70b` | itf | - | - | $7457 | $7457 | - | - |
| `github:gpt-4.1-mini` | itf | - | - | $5857 | $5857 | - | - |
| `selfhost:phi-4-mini` | itf | - | - | $5857 | $5857 | - | - |
| `google:gemini-3-flash` | nba,pol | $82 | $73 | - | $317 | 37.9% | 95 |
| `nvidia:llama-3.3-70b` | nba,pol | $103 | $101 | - | $204 | 52.8% | 36 |
| `cerebras:llama3.1-8b` | nba,pol | $97 | $104 | - | $201 | 48.7% | 78 |
| `nvidia:minimax-m2.7` | nba,pol | $91 | $105 | - | $196 | 44.4% | 9 |
| `selfhost:dolphin3-l32-3b` | nba,pol | $82 | $100 | - | $182 | 29.6% | 27 |
| `selfhost:qwen3-4b` | nba,pol | $72 | $100 | - | $173 | 36.4% | 22 |
| `selfhost:gemma-3-4b` | nba,pol | $40 | $104 | - | $143 | 7.7% | 39 |
| `mistral:small` | nba,pol | $31 | $104 | - | $135 | 12.0% | 50 |
| `mistral:ministral-8b` | nba,pol | $24 | $104 | - | $129 | 15.8% | 57 |
| `mistral:nemo` | nba,pol | $25 | $104 | - | $129 | 7.8% | 51 |
| `selfhost:qwen3-0.6b` | nba,pol | $24 | $103 | - | $127 | 4.2% | 48 |
| `openrouter:nemotron-120b` | nba,pol | $24 | $91 | - | $115 | 12.9% | 62 |