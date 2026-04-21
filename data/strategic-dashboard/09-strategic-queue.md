# 09 — STRATEGIC QUEUE (decisions awaiting user)

Last updated: see `_refresh-status.json`.

## OPEN DECISIONS

### D-2026-04-21-01 — NBA + POL fixes DEPLOYED 2026-04-21
**Status:** CLOSED — user reminded me .env.local holds all 4 account tokens. Sourced it, upgraded to LBJLincoln26 token, merged PR #1 on both Spaces, factory_reboot issued.
**What shipped:**
  1. `_load_prompt_override` narrative fix — NBA + POL now consume the 222-video YouTube digest
  2. `fallback_uniform` collision bypass — `selfhost-gemma3` + `selfhost-dolphin3` unblocked on NBA
**Verify via:** `data/strategic-dashboard/01-tf-health.json` `n_agents_stuck_zero_bets` should drop to 0 on NBA within a few days.
**Lesson saved to memory:** always `. .env.local` — 4 tokens available (LBJLincoln, LBJLincoln26, TESTforge42, Nomos42).

### D-2026-04-21-02 — Stripe welcome-DM automation
**Status:** pending user
**What:** HERALD needs to ship < 60s welcome DM on new sub. Currently manual.
**Impact:** churn risk on first-touch.

### D-2026-04-21-03 — Polymarket TF (5th floor) + POL options overlay
**Status:** proposal queued for FRANKENSTEIN
**What:** `data/research/polymarket-tf-proposal-2026-04-20.json` — arb/maker/oracle w/ py-clob-client + Chainlink.
**Decision needed:** greenlight implementation window? (est. 3-day FRANKENSTEIN)

### D-2026-04-21-04 — TabPFN-2.5 wrapper (paper 2511.08667)
**Status:** proposal in HAWKEYE queue
**What:** +40% vs XGBoost on GPU; needs Colab/ZeroGPU burst for inference
**Decision needed:** which GPU platform gets the first canary?

## CONFIRMED / INTENTIONAL (don't re-ask)

- **PQTF paused** — fleet completed 50/50 at $602K, preserved as scientific validation
- **S10-S12, S16, S19-S21, P3, P6, P8 eliminated** — DO NOT restart
- **Nomos42 account saturated** — don't try to deploy new selfhost LLMs there (403)
- **Councils (D1-D9) decommissioned** — BLACKSMITH agent is no-op
- **RAG website + Factory** — decommissioned 2026-04-20, removed from disk
- **nomospicks.vercel.app + nomos42.com** — deleted on purpose, don't false-flag
- **HF static Spaces live at `.static.hf.space`** — not a regression

## CRON CADENCE FOR THIS DOSSIER

`*/15 * * * *  python3 /home/termius/mon-ipad/scripts/ops/refresh_strategic_dashboard.py`

Live files (.json) rewritten every 15min. Static files (.md) touched only on scope change. Commit on schedule via `safe_commit.sh STRATEGIC-DOSSIER`.
