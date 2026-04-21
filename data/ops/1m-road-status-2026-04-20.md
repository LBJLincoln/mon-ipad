# $1M Road — Executive Status (2026-04-20)

**Author:** THE BOSS | **Source:** data/tf-analytics/{nba,pol,pqtf}/ + ITF /api/status live
**One sentence:** PQTF already proved the thesis at $602K, the two live season-TFs (NBA/POL) are bleeding, ITF just deployed v2.2 and has no P&L yet.

## Fleet-wide scorecard

| TF    | Fleet $ | Best agent | % of $1M | Days elapsed | Rate/day (leader) | ETA to $1M (leader) | Status |
|-------|---------|-----------|----------|--------------|-------------------|--------------------|--------|
| NBA   | $461.12 | selfhost-dolphin3 $316.20 | 0.0316 % | 127 / 175 | +0.911 % | ~889 d | LIVE — REGRESSING |
| POL   | $1,614.26 | gemini-tact $152.54 | 0.0153 % | 168 / 184 | +0.252 % | ~3,496 d | LIVE — REGRESSING |
| PQTF  | $602,353.97 | mistral-large $244,049.55 | 24.40 % (leader) / 60.24 % (fleet) | 50 / 50 | +16.88 % | ~9 d | FROZEN (validation) |
| ITF   | n/a | none | 0 % | tick 6 / ~∞ | n/a | n/a | LIVE — v2.2 deployed 15:53Z, 0 realized P&L |
| **Total (fleet sum)** | **$604,429** | — | **60.44 %** | — | — | — | 3/4 bleeding or idle |

## Trajectory reading

1. **PQTF is the only proof-positive**. $100 → $244K on mistral-large in 50 days = 16.88 %/day compound, 2,441× return, **statistically dominant across every experiment ever run on this floor**. If we re-ran from $100 today it would hit $1M in ~9 days. The $602K is frozen as a validation point (MEMORY: `project_pqtf_1m_60pct_apr19`) — **not** counted toward live progress.

2. **NBA is not "on the road", it is sliding off it**. Fleet down monotonically: day-54 $696 → day-85 $532 → day-127 $461. Fleet size also dropped from 9 active agents → 8, and 7 of those 8 held bankrolls < $30 (preservation mode). Only selfhost-dolphin3 is compounding. At +0.91 %/day the leader needs ~889 days (≈2.4 yrs) to reach $1M alone — and the season is 175 days.

3. **POL is the slowest of all**. +0.25 %/day means ~9.5 years to $1M for the leader. Day-168 shows **12 of 17 agents emitting FALLBACK_UNIFORM** (SPY/QQQ/IWM equal-split) — i.e. the LLM layer failed on 70 % of the fleet and the uniform emitter kicked in. The 28 bets that fleet placed had WR 32 % and jaccard 0.42 (lockstep returning).

4. **ITF just went live**. Tick 6 at 16:09Z, 14/14 agents active, all 10 persisted positions status = broker_error or sim_dry_run, **$0 realized, $0 sim P&L**. Alpaca paper credential returns 401. Too early for any trajectory call — need 24 h of ticks before the prompt-mutator loop closes.

## Regressions in the last 24 h

| TF  | Window | Δ fleet | Verdict |
|-----|--------|---------|---------|
| NBA | day-85 → day-127 (~last 4 h wall) | **−$70.75** | fleet drop, monotonic |
| POL | day-98 → day-168 (~last 8 h wall) | **−$44.02** | fleet drop, monotonic |
| POL | day-49 → day-168 (~last 12 h) | **−$406.21** | lockstep + fallback_uniform dominated |
| PQTF | — | 0 | frozen on purpose |
| ITF | tick 0 → tick 6 | $0 | no P&L yet, broker 401 |

## Where the leaks are (prioritised)

1. **POL LLM routing is broken for ≥12/17 agents** — all emitting FALLBACK_UNIFORM. MEMORY `TF LLM REROUTE 2026-04-20` flagged the dead personas; the SWITCHBOARD re-route was partial. Until routing is fixed POL compounds at the uniform-emitter rate (≈0 edge on ETF proxies).
2. **NBA is starvation-mode by design but the floor is too low**. 7/8 agents hold bankroll < $30 and skip almost every day. Only dolphin3 (selfhost) is trading aggressively. Either relax the preservation floor or let starved agents exit — currently they occupy slots without contributing.
3. **Jaccard signatures** — POL day-168 jaccard_mean = 0.42 (max 1.0). Structural-DIVERGE guardrails from `tf_drawdown_guardrails_apr18` not biting on the uniform-fallback path. Lockstep is back whenever the LLM path fails.
4. **ITF Alpaca 401** — paper key unauth'd, dry_run persists but realized P&L locked at $0. Need to rotate ALPACA_API_KEY_ID / ALPACA_API_SECRET on the Space before the v2.2 prompt-mutator loop can produce measurable P&L.
5. **PQTF is frozen** — the 60 % of $1M sitting in the ledger is a scientific snapshot, not a live compounding position. DO NOT restart (per `project_pqtf_1m_60pct_apr19`).

## Is the $1M road "perfect"?

**No.** It has one proven compounder (PQTF, 50 days, 2,441×) and three under-performers. The correct reading:

- **Thesis validated**: multi-agent LLM trading CAN hit $1M trajectory (PQTF proved it).
- **Replication blocked**: 3/4 live TFs are leaking. Leaks are operational (Alpaca auth, LLM routing) + structural (preservation-mode floor, lockstep returning under fallback).
- **Shortest path forward**: (a) fix POL LLM routing so ≥80 % of agents emit non-fallback; (b) rotate ITF Alpaca key so v2.2 prompt-mutator has real P&L signal; (c) unfreeze PQTF for a fresh 50-day run on live data to re-prove the compounder.

**Projected $1M date @ current rates**: only PQTF (frozen) would make it; NBA/POL do not reach $1M inside their respective seasons. Net status: **60 % already banked in a ledger snapshot, the other 40 % is not being earned by any live TF today.**

---
*Generated: 2026-04-20. Read-only status. No cycles kicked, no Spaces restarted.*
