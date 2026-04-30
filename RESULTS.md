# Nomos42 — Live Results & Doctrine Reference

**Last updated:** 2026-04-30 (post-carte-blanche reset + Tauric architecture A/B)
**Read this first for the current state of every Trading Floor.**

---

## TL;DR for the CEO

| Surface | Status | Equity | Architecture | URL |
|---|---|---|---|---|
| **NBA TF** | LIVE | ~$1,028 / $1,700 seed | Carte-blanche solo (1 LLM/agent/day) | [nba-llm-trading-floor](https://huggingface.co/spaces/LBJLincoln26/nba-llm-trading-floor) |
| **NBA Tauric** | LIVE | $1,700 (just started) | Bull/Bear/Synthesis (3 LLM/agent/day) | [nba-tauric-trading-floor](https://huggingface.co/spaces/LBJLincoln26/nba-tauric-trading-floor) |
| **ITF** | LIVE | ~$94K / $100K Alpaca paper | Alpha-Arena doctrine, 30s tick | [intraday-trading-floor](https://huggingface.co/spaces/LBJLincoln26/intraday-trading-floor) |
| **ITF Tauric** | DEPLOYING | — | Bull/Bear/Synthesis, 60s tick | [itf-tauric-trading-floor](https://huggingface.co/spaces/TESTforge42/itf-tauric-trading-floor) |
| **PQTF** | FROZEN | $602,354 (validation) | Original 4-agent | [hf-political-quant-trading-floor](https://huggingface.co/spaces/LBJLincoln26/hf-political-quant-trading-floor) — DO NOT TOUCH |
| **POL TF** | LIVE | qwen-arb compound alpha | v5_restored doctrine | [political-llm-trading-floor](https://huggingface.co/spaces/LBJLincoln26/political-llm-trading-floor) |

---

## The carte-blanche doctrine (2026-04-30)

After 5 days of forensic audit (79.2% of NBA bets were `engine_forced_floor` server-injected lockstep), shipped a structural fix:

### What was killed
- `engine_forced_floor` (the lockstep generator)
- `engine_parlay_floor` (1% server-injected parlay)
- `engine_min_bets_inject` (server top-3 fill)
- `engine_breadth_inject` (server cross-family fill)
- INVERSE-CALIBRATION PROBATION prompt addendum
- Edge ≤0.20 calibration filter

### What was kept / added
- **30% deploy mandate** (env `NBA_MIN_DEPLOY_PCT=0.30`) — server scales LLM picks UP, never injects new bets
- **3 bets + 1 parlay/day** prompt mandate (rationale-required if any agent refuses)
- **Personality Kelly cap** (Axelrod-tier 0.04-0.17) preserved
- **No PASS days without justified rationale** (≥40 chars citing concrete data)

### Verified day-0,1,2 audit post-reset
| metric | pre-reset | post-reset |
|---|---|---|
| forced bets | **79.2%** | **0.0%** |
| lockstep agents/day | 9/17 (identical bets) | 0 |
| real LLM rationale | template | concrete (player out, ref tendency, line move) |
| sovereign PASS allowed | yes (broken) | yes (rationale-justified) |

---

## TauricResearch architecture (NEW 2026-04-30)

A/B science test against the carte-blanche solo doctrine. Inspired by [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) (55.7K stars on GitHub, arXiv 2412.20138).

### The chain
Per agent per decision:
1. **BULL ANALYST** — same LLM, prompt = "find the strongest bullish case"
2. **BEAR ANALYST** — same LLM, prompt = "counter-argue"
3. **TRADER (synthesis)** — same LLM, prompt = "decide given both arguments → JSON"

All 3 text blobs persist in `day_log[tauric_bull_case]`, `day_log[tauric_bear_case]`, parsed allocations from synthesis. Full audit trail.

### Cost vs benefit
- 3× LLM calls/agent vs 1× (carte-blanche solo)
- Cheap providers (Cerebras llama3.1-8b) handle bull+bear; agent's primary handles synthesis
- 17 agents × 3 calls × 1/day = 51 calls/day on NBA (free tier easily handles)
- ITF: 17 agents × 3 calls × 60s tick = 51 calls/min (tighter, slowed tick from 30s → 60s)

---

## Math — race to $1M

| daily rate | $100 → $1M | $94K → $1M (ITF) |
|---|---|---|
| 5% | 189 days | 48 days |
| 7% | 136 days | 35 days |
| **10%** | **97 days** | **25 days** |
| 15% | 66 days | 17 days |

**What 10%/day requires** (Kelly arithmetic, calibrated probabilities):

| scenario | win prob | Kelly cap | E[r]/bet | bets needed/day |
|---|---|---|---|---|
| edge 0.05 floor (current parser) | 55% | 6% | 0.28% | 36 ❌ |
| **edge 0.08, Kelly 10% (PQTF doctrine)** | **58%** | **10%** | **1.08%** | **9** ✅ |
| edge 0.10, Kelly 15% | 60% | 15% | 2.19% | 5 ✅ |
| edge 0.15, Kelly 20% | 62% | 20% | 3.68% | 3 ✅ |

The PQTF $244K winner ran row 3 (edge ≥0.08, Kelly 10%, 5-9 bets) — that's the proven path.

---

## Where to look

### Live data
- **CEO audit page (Vercel):** [nomosdashboard.vercel.app/audit](https://nomosdashboard.vercel.app/audit) — structured per-day per-agent per-trade view with rationale text, lockstep detector, forced-bet ratio
- **NBA TF leaderboard:** [/api/leaderboard](https://lbjlincoln26-nba-llm-trading-floor.hf.space/api/leaderboard)
- **ITF Alpaca truth:** Query `/api/account` directly on Alpaca (multi-worker LB makes Space `/api/status` unreliable for equity)

### Code
- **NBA TF:** `scripts/arena/hf-llm-trading-floor/app.py` (~5300 lines)
- **NBA Tauric:** `scripts/arena/hf-llm-trading-floor-tauric/app.py` (forked + 3-pass debate in `_agent_llm_worker`)
- **ITF:** `scripts/arena/hf-intraday-trading-floor/app.py`
- **ITF Tauric:** `scripts/arena/hf-intraday-trading-floor-tauric/app.py`
- **Dashboard:** `~/nomos-dashboard/` (separate repo, Next.js)

### Audit data
- Per-day decisions: `data/decisions/day-XXX.json` on each TF Space's HF Hub repo
- Audit MD files: `data/audit/per-agent-deep/{nba,pol,itf,pqtf}/{agent}.md` (synced from `mon-ipad` to dashboard via cron)

### Memory for the AI assistant
- `CLAUDE.md` — architecture overview, doctrine, rules
- `~/.claude/projects/-home-termius-mon-ipad/memory/MEMORY.md` — incident reports, doctrine evolution, rules

---

## Quarantine status (2026-04-30)

| TF | Quarantine until | Override key |
|---|---|---|
| NBA TF | 2026-05-24 (until carte-blanche replay completes) | `NOMOS_QUARANTINE_OVERRIDE=1` |
| ITF | 2026-05-29 (compounding protection) | same |
| POL TF | 2026-05-22 (qwen-arb $10K alpha) | same |
| PQTF | FROZEN FOREVER | NEVER |

Reset signal phrases blocked by `safe_commit.sh`: `factory_reboot`, `reset-state`, `reset-bankrolls`, `state wipe`, `fresh state`. Override only when user explicitly authorizes — document in commit msg.

---

## What's running where

**4 HF accounts × 8 cpu-basic free-tier slots = 32 max:**

| Account | Saturation | What's there |
|---|---|---|
| LBJLincoln | ~5/8 | political-alpha islands (P1/P2/P4/P5/P7), 3 selfhost LLMs, browser-nba |
| LBJLincoln26 | ~saturated | NBA TF, NBA Tauric, POL TF, ITF, llm-gateway, 2 oracles, hermes-agent, gemma3-4b-cpu, S17 island |
| TESTforge42 | 6/6 (capped) | ITF Tauric (NEW), nba-evo S18/S22, qwen3-4b, browser-qa, llama32-1b paused (slot freed for Tauric ITF) |
| Nomos42 | 21 spaces, mostly paused | pixel-world, langfuse, 10 paused selfhosts |

---

## Recent commits (search "carte-blanche" or "tauric" in git log)

- `0feb92a27` HARD_RESET NBA TF — carte-blanche doctrine clean Day-0
- `5cc0ceef0` TAURIC NBA Trading Floor — Bull/Bear/Synthesis chain
- `72dece376` TAURIC ITF Trading Floor — same chain on intraday

---

**For deeper forensics:** [/audit page](https://nomosdashboard.vercel.app/audit) on the dashboard.
**For incident history:** `MEMORY.md` in the assistant memory dir.
**For the doctrine debate:** this file's "carte-blanche" + "Tauric" sections above.
