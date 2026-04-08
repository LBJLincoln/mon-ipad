---
name: research_april2026_cycle14_drift_monitoring
description: Apr 7 2026 cycle 14: drift/calibration monitoring SOTA — Frouros winner (HIGH fit), CUSUM paper arXiv:2510.25573, Wilkens ECE>0.03 recal trigger, ship plan for nba_drift_monitor.py
type: project
---

Frouros v0.9.0 is the winner library for VM drift monitoring (HIGH fit): numpy+scipy only, <30MB RAM, pip install, supports DDM (concept drift), PSI (data drift), 20+ statistical tests. Last release Sep 2024 — maintained.

TOP PAPER: arXiv:2510.25573 — CUSUM with dynamic limits on (p_hat, y_t) stream. No model access needed. Implements as S_t = (p_t - y_t)^2 - baseline_Brier, accumulate C_t = max(0, C_{t-1} + S_t - k), alert at C_t > h for 3 consecutive runs. ~50 lines numpy.

RECALIBRATION TRIGGER RULE (Wilkens arXiv:2303.06021): rolling 50-game ECE > 0.03 = PAV isotonic refit. This threshold separates +34% ROI from -35% ROI.

SHIP PLAN:
- Script: scripts/monitoring/nba_drift_monitor.py
- Reads: data/nba-agent/full-season-backtest.json
- Writes: data/monitoring/drift-{calibration,concept,data,summary}.json
- Cron: */30 (8s runtime, 35MB RAM)
- 4 signals: concept drift (DDM), calibration drift (CUSUM), prediction drift (PSI), label drift (home win rate z-score)
- Auto-triggers PAV refit when recalibration_needed=true in drift-summary.json
- Telegram alert via @Nomos42Bot on red signal

LIBRARIES EVALUATED:
- Frouros v0.9.0: HIGH — winner
- River v0.22.0 ADWIN/KSWIN: HIGH — lightest option, O(log N) memory, good for streaming
- Menelaus v0.2.0: MEDIUM — stale (no update since Dec 2022)
- NannyML v0.13.1: LOW for cron (300MB+ install), ok for weekly Kaggle batch
- alibi-detect v0.13.0: LOW-MEDIUM — classical mode borderline at 200MB limit

**Why:** Manual PAV recalibration every few days is the single largest operational risk — Wilkens showed ECE drift 2-3 pts turns +34% ROI to -35%.
**How to apply:** Next D2 Engineering cycle should implement nba_drift_monitor.py before any other feature work. This is defensive infrastructure, not alpha generation.
