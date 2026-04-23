---
name: POL TF record — qwen-arb $3,119 (2026-04-22)
description: New Political Trading Floor all-time high, day 129/184, $100 seed → $3,119 (+3,019%). Supersedes prior highs.
type: project
---

POL TF record holder as of 2026-04-22: **qwen-arb at $3,119.11** (live `best_bankroll`
on `LBJLincoln26/political-llm-trading-floor`, day 129/184, 311 bets,
LLM 101/129=78% OK, max_drawdown 18.8%).

**Why:** Prior POL TF high previously referenced was ~$470 (gemini-3-flash,
cited in `feedback_itf_follow_winners_apr19.md`). qwen-arb is **6.6× that** —
a material regime change that should be preserved against future Space resets.
Fleet totals on same tick: qwen-quant $924, gemini-anl $462, mistral-small $239,
fleet $5,599 / $1,700 seed = +229%. The run is still live (55 days remaining).

**How to apply:**
- Any factory_reboot / `/api/reset` proposal on the POL TF must cite this
  checkpoint and copy agent-ledger state to Hub before reboot, or we lose the
  record (see `project_tf_state_persistence_apr19.md` for persistence recipe).
- When ranking "cross-fleet aggressive winners" for ITF model routing, promote
  **cerebras:qwen-3-235b-a22b** (qwen-arb's primary) above the stale
  `gemini-3-flash` seed. Update `feedback_itf_follow_winners_apr19.md` downstream.
- The arb persona running 235B at risk=0.65 + arbitrage rationale is the
  template for POL high-variance success — do NOT relax its risk cap.
- qwen-arb's 78% llm_ok (22% degraded) means EMERGENCY_POOL["L"]
  mistral:large fallback is carrying ~1/5 of its calls — don't break that.
