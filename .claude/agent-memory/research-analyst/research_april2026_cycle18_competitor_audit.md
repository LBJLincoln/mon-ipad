---
name: April 2026 Cycle 18 — Competitor Audit + Council Honest Assessment
description: Mirofish=not a competitor (zero metrics, academic toy), Sportstensor=real threat (Sortino ensemble, 14% ROI), Hermes councils partially broken (D3 copy-paste loop, D2 opaque commits, no fast Brier proxy breaks keep/revert), political AI unique but unvalidated
type: project
---

# Cycle 18: Competitor Audit + Council Honest Assessment (Apr 11 2026)

## Mirofish — NOT a competitor
- Academic project by undergrad at Beijing U of Posts and Telecom
- Social simulation engine (GraphRAG + OASIS agents simulating societies)
- ZERO published accuracy metrics, zero Brier scores, zero sports capabilities
- Their demos: public opinion simulation, literary endings for classic novels
- Threat level: ZERO

## Sportstensor SN41 — Real competitor
- Bittensor subnet: 100+ miner ensemble, Sortino+PnL incentive v2.5
- Published NBA ROI 14%, best miner 69% accuracy/59% ROI
- Most sophisticated open sports betting architecture
- Adoptable: Sortino-ratio island weighting (10 lines Python, 4h, -0.0015 Brier)

## Karpathy Autoresearch Pattern — Sound but our implementation is broken
- Original: 700 experiments/2 days, 20 improvements kept, 11% speedup
- Measurement step takes 5 minutes (training loss)
- Our councils CANNOT do keep/revert because Brier eval takes 10+ minutes on VM
- Fix: 30-second proxy metric (cross-val on last 50 games) enables real keep/revert
- **This is the single highest-leverage infrastructure fix available**

## Council Honest Status (as of Apr 11)
| Dept | Streak | Real Verdict |
|------|--------|--------------|
| D1 Research | 12 | Misleading — D1 is writing output but using "completed" not "shipped". Real issue: research goes into void, D2 never reads it. |
| D2 Engineering | 10 | Opaque — making real commits (10 SHAs) but exit_code=1 every time, never writes status. Commits may be real. |
| D3 Evolution | 0 (but hallucinated Apr 11) | STUCK IN COPY-PASTE LOOP — exact same reason string for 10 consecutive runs. Apr 11 hallucination: tried to write 6 out-of-scope files. |
| D7 Infra | 10 no_ops + Apr 11 hallucination | Stall is legitimate (infra fine). Hallucination: manufactured work by writing cross-island-sync.py outside scope. |
| D5 Business | 9 | Legitimately blocked — correctly identifies Kelly over-aggression and D4 dependency. Escalation mechanism missing. |

## Root Causes
1. No fast measurement signal -> keep/revert never happens
2. D3 reads own previous output as "latest metrics" -> proposes same action forever
3. D1->D2 pipeline not wired -> research writes to void
4. After stall_streak>8, agents hallucinate work (scope enforcement catches it correctly)
5. No inter-department dependency resolution (D5 blocked on D4 with no escalation)

## Political Alpha Competitor Landscape
- Polymarket bots: prediction markets (binary), NOT equity alpha signals. Different product.
- Metaculus FutureEval: political/scientific event forecasting benchmark. Different end goal.
- TradingAgents: stock trading on fundamentals + sentiment, not political signals.
- Our 22-category donor->favor->stock pipeline: unique in documented literature. No direct competitor found.
- Weakness: $0 live validated returns, 0 live trades executed.

## Priority Fix List
1. Fast Brier proxy (30s eval, 8h) — enables real keep/revert fleet-wide
2. D3 deduplication guard (2h) — stop repeating same action
3. D1->D2 pipeline wire (2h) — make research feed engineering
4. D2 status string fix (1h) — add explicit status field to prompt
5. Shot-chart PCA-20 Cat50 (20h) — -0.005 Brier, decisive for breaching 0.20

## How to apply
When advising on council health: cite the specific stall patterns above (D3 copy-paste, D2 opaque, D7 hallucination-under-pressure). The framing the user wants is brutal honesty — these councils are NOT running the Karpathy loop correctly because the measurement step is broken. Fix the proxy metric first.
