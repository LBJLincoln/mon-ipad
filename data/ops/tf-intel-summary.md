# TF Intel Snapshot
_generated 2026-04-20T02:56:01+00:00_

**Alerts:** 20   (S5×1  S3×4  S2×15)

## NBA
- **S2 agent_silent** [qwen-quant] — Agent qwen-quant has 0 bets across last 3 snapshot days
    → Check agent qwen-quant LLM route — may be timing out; reroute via /api/mutate or prompt override
- **S2 agent_silent** [nemotron-120b] — Agent nemotron-120b has 0 bets across last 3 snapshot days
    → Check agent nemotron-120b LLM route — may be timing out; reroute via /api/mutate or prompt override
- **S2 agent_silent** [selfhost-qwen4b] — Agent selfhost-qwen4b has 0 bets across last 3 snapshot days
    → Check agent selfhost-qwen4b LLM route — may be timing out; reroute via /api/mutate or prompt override

## POL
- **S3 category_collapse** — POL fleet only trades 1 distinct categories (['insider_trade'])
    → Inject POL prompt override: 'You MUST bet on >=2 distinct POL categories per day'

## PQTF
- **S3 pqtf_zombie_rows** — 14/36 PQTF order rows have type=null or strike=0
    → Patch pqtf engine: enforce explicit type+strike fields in LLM JSON contract
- **S3 pqtf_no_multileg** — PQTF emitted 36 bets, 0 multi-leg structures despite Phase-2 support
    → Inject PQTF prompt override mandating >=1 multi-leg structure per session
- **S2 agent_silent** [mistral-large] — Agent mistral-large has 0 bets across last 3 snapshot days
    → Check agent mistral-large LLM route — may be timing out; reroute via /api/mutate or prompt override
- **S2 agent_silent** [gemini-anl] — Agent gemini-anl has 0 bets across last 3 snapshot days
    → Check agent gemini-anl LLM route — may be timing out; reroute via /api/mutate or prompt override
- **S2 agent_silent** [llama-contra] — Agent llama-contra has 0 bets across last 3 snapshot days
    → Check agent llama-contra LLM route — may be timing out; reroute via /api/mutate or prompt override
- **S2 agent_silent** [mistral-medium] — Agent mistral-medium has 0 bets across last 3 snapshot days
    → Check agent mistral-medium LLM route — may be timing out; reroute via /api/mutate or prompt override
- **S2 agent_silent** [qwen-quant] — Agent qwen-quant has 0 bets across last 3 snapshot days
    → Check agent qwen-quant LLM route — may be timing out; reroute via /api/mutate or prompt override
- **S2 agent_silent** [mistral-nemo] — Agent mistral-nemo has 0 bets across last 3 snapshot days
    → Check agent mistral-nemo LLM route — may be timing out; reroute via /api/mutate or prompt override

## ITF
- **S5 broker_401** — Alpaca broker returned 401 on 5/10 orders (50%)
    → Regenerate ALPACA_API_KEY_ID+SECRET, re-set as Space secrets on Nomos42/intraday-trading-floor, redeploy
- **S3 itf_no_crypto** — ITF emitted 10 orders but 0 crypto trades (24/7 universe unused)
    → Verify CRYPTO_PIVOT_CLAUSE deployment + _off_hours_crypto_signal threshold (BTC/ETH/SOL |change_pct|>0.2%)
- **S2 itf_agent_silent** [vol-1] — ITF agent vol-1 silent in last 1 decision files + 0 positions
    → Check gateway routing for vol-1's model_primary; consult data/ops/llm-deadlist.json
- **S2 itf_agent_silent** [mean-rev-1] — ITF agent mean-rev-1 silent in last 1 decision files + 0 positions
    → Check gateway routing for mean-rev-1's model_primary; consult data/ops/llm-deadlist.json
- **S2 itf_agent_silent** [momentum-1] — ITF agent momentum-1 silent in last 1 decision files + 0 positions
    → Check gateway routing for momentum-1's model_primary; consult data/ops/llm-deadlist.json
- **S2 itf_agent_silent** [scalper-1] — ITF agent scalper-1 silent in last 1 decision files + 0 positions
    → Check gateway routing for scalper-1's model_primary; consult data/ops/llm-deadlist.json
- **S2 itf_agent_silent** [options-1] — ITF agent options-1 silent in last 1 decision files + 0 positions
    → Check gateway routing for options-1's model_primary; consult data/ops/llm-deadlist.json
- **S2 itf_agent_silent** [breakout-1] — ITF agent breakout-1 silent in last 1 decision files + 0 positions
    → Check gateway routing for breakout-1's model_primary; consult data/ops/llm-deadlist.json
