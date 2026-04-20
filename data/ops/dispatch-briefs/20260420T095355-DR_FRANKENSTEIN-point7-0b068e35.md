# DR_FRANKENSTEIN — Point #7: Implement Polymarket TF (5th trading floor) — oldest pending proposal

_Dispatched 2026-04-20T09:53:55Z — severity=3_

**Department:** D1 Research
**Target file(s):** `scripts/arena/hf-polymarket-trading-floor/ (NEW) + data/research/tf-proposals-polymarket-2026-04-20.json`

## Why This
Proposal committed cc77546a4 but never implemented. Non-crypto predictive market. Ports PQTF 5-strat engine + POL catalyst_calendar. Winning architecture rule (#7) = port don't reinvent.

## Spec (concrete steps)
1. Duplicate scripts/arena/hf-political-quant-trading-floor/ → hf-polymarket-trading-floor/ (symlink shared engine)
2. Replace events source: PQTF options → py-clob-client poll of Polymarket markets top-50 by 24h volume
3. Add pm_arb / pm_maker / pm_oracle strategies (from proposal.spec)
4. Wire Chainlink price oracle for settlement verification
5. Create HF Space LBJLincoln26/polymarket-trading-floor (Docker, 2vCPU-basic)
6. Deploy via HfApi.upload_folder; secrets = CLOB_KEY, CHAINLINK_RPC
7. First session = dry-run; ENABLE_PM_LIVE=1 gate for real exposure

## Acceptance Criteria
Polymarket TF /api/status responds 200, ≥1 dry-run order in first 24h

## Context
- Full empire ledger: `data/empire/MASTER.md`
- Your per-agent brief: `data/empire/briefs/dr_frankenstein.md`
- Dispatch-log: `data/ops/dispatch-log.jsonl`
- Live 3-min intel: `data/ops/tf-intel-latest.json`

## How to Ack
When you start: `git log --author="DR_FRANKENSTEIN"` should show your first commit within 24h.
When done: update `data/empire/strategy-scorecard.json` point-7 status → DONE.
