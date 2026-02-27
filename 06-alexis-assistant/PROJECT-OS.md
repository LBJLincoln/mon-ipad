# PROJECT-OS (Alexis + Assistant)

Updated: 2026-02-27T16:10:00Z

## Mission
Single shared understanding between Alexis and assistant for full project execution.

## Current top priorities
1. Restore critical red pipelines: Standard, Graph, Ingestion, PME gateway.
2. Nomos42 (ex-pme-connectors) tomorrow-ready for ~20 close-user tests.
3. Dashboard trading-board style with BEST/WORST fixed + MIDDLE rolling.
4. Enforce DIFF-first + incremental + golden checks everywhere.

## Governance
- Keep root architecture at max 7 logical folders.
- Use this folder for high-signal shared decisions and handoff notes.
- Every milestone must update `docs/executive-summary.md` and this file.

## Immediate truth snapshot
- Quantitative/Orchestrator currently respond 200.
- Standard/Graph currently failing.
- Ingestion 500, PME gateway 404.

## Next actions
- Rollback Standard/Graph to last stable snapshot.
- Repair ingestion activation + webhook mapping.
- Reactivate/recreate PME gateway webhook.
- Rerun smoke (5q) then incremental campaign.
