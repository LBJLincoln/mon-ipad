# 09 — STRATEGIC QUEUE (decisions awaiting user)

Last updated: see `_refresh-status.json`.

## OPEN DECISIONS

### D-2026-04-21-01 — NBA TF `app.py` upload after reset
**Status:** pending (HF_TOKEN_2 returned 401 on `LBJLincoln26/nba-llm-trading-floor`, 429 on other tokens)
**What:** `_load_prompt_override` fix — currently NBA is the only TF NOT consuming the 222-video YouTube `market_narrative` field (POL/ITF already patched).
**Impact:** NBA 17 LLM agents miss 223-video context for each decision until upload lands.
**Next try:** 15-min rate cooldown, then retry `HF_TOKEN` on LBJLincoln26 write perms.

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
