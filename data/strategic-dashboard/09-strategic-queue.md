# 09 — STRATEGIC QUEUE (decisions awaiting user)

Last updated: see `_refresh-status.json`.

## OPEN DECISIONS

### D-2026-04-21-01 — MERGE HF PRs on NBA + POL Spaces
**Status:** PRs open, awaiting user merge on HF UI
**NBA PR:** https://huggingface.co/spaces/LBJLincoln26/nba-llm-trading-floor/discussions/1
**POL PR:** https://huggingface.co/spaces/LBJLincoln26/political-llm-trading-floor/discussions/1
**What ships when merged:**
  1. `_load_prompt_override` narrative fix — both TFs finally consume the 222-video YouTube digest (NBA had never seen it)
  2. `fallback_uniform` collision bypass — unblocks `selfhost-gemma3` + `selfhost-dolphin3` on NBA (0 bets / 17 days root cause: collision limiter wiped 14/17 agents on LLM-outage days)
**Why PR not direct push:** token in this shell (TESTforge42) has PR-only access on LBJLincoln26 Spaces
**Impact until merged:** NBA's 2 selfhost agents keep trading $0 and NBA/POL still miss YouTube narrative

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
