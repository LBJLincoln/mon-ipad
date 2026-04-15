# Calibration & Drift Monitoring

> Snapshot at 2026-04-15 22:23 UTC

## Drift Summary

- **state**: PARTIAL
- **recalibration_needed**: True
### signals
- concept: STABLE
- calibration: INSUFFICIENT
- data: INSUFFICIENT
- label: INSUFFICIENT
### metrics
- trades: 85
- baseline_brier: 0.0
- cusum_peak: None
- psi: 0.0
- label_z: 0.0
- rolling_ece: 0.14135
- rolling_ece_window: 50
- recal_trigger_ece: 0.03
### sources
- backtest: data/nba-agent/full-season-backtest.json
- papers: ['arXiv:2510.25573 (CUSUM calibration drift)', 'arXiv:2303.06021 (Wilkens NBA calibration)']

## Drift Calibration

### cusum
- state: INSUFFICIENT
- cusum: 0.0
- baseline_brier: 0.0
- n: 85
### rolling_ece
- ece: 0.14135
- window: 50
- n: 85
- recal_needed: True
- trigger: 0.03

## Drift Data

### psi
- psi: 0.0
- state: INSUFFICIENT
- n: 85
### label
- z: 0.0
- state: INSUFFICIENT
- n: 85

## Drift Concept

- **detector**: fallback.DDM
- **state**: STABLE
- **alert_index**: None
- **n**: 85
