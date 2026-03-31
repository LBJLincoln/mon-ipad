# Nomos42 Departments — Karpathy Real Loop Architecture

> v18 — 8 departments x 5-min iterative loops x Guardian Orchestrator

## Architecture

```
Guardian Orchestrator (cron every 30min)
├── D1 Research      — paper→extract→propose→measure
├── D2 Engineering   — code→test→measure Brier→keep/revert
├── D3 Evolution     — mutate→eval→measure fitness→select
├── D4 Betting       — strategy→backtest→measure ROI→keep/revert
├── D5 Evaluation    — audit→identify→fix→verify
├── D6 Infra         — check→detect→fix→verify
├── D7 Political     — signal→feature→measure alpha→keep/revert
└── D8 Creative      — generate→quality→curate→publish
```

## File Layout

```
scripts/departments/
├── guardian-orchestrator.py          # Master runner (8 departments x 5min)
├── research/research-loop.sh
├── engineering/engineering-loop.sh
├── evolution/evolution-loop.sh
├── betting/betting-loop.sh
├── evaluation/evaluation-loop.sh
├── infra/infra-loop.sh
├── political/political-loop.sh
└── creative/creative-loop.sh

data/departments/
├── guardian-status.json              # Latest full cycle result
└── wins-latest.json                  # Cross-pollination wins
```

## Department Specs

### D1 — Research
- **Loop**: Scan papers/repos → extract techniques → generate proposals → measure expected impact
- **Metric**: proposals_generated, papers_scanned, techniques_extracted
- **Agent swarm**: R1 (Analyst), R2 (Karpathy), R3 (Repo Scout), R4 (Market)
- **Scripts**: `scripts/departments/research/research-loop.sh`
- **Data**: `data/research/latest-improvements-*.json`

### D2 — Engineering
- **Loop**: Modify code → run tests → measure Brier delta → keep if improved, revert if not
- **Metric**: brier_delta, test_pass_rate, features_added
- **Agent swarm**: E1 (Feature), E2 (Evolution Opt), E3 (Pipeline), E4 (Backtest), E5 (Data)
- **Scripts**: `scripts/departments/engineering/engineering-loop.sh`
- **Guardrail**: ZERO ML on VM (1 vCPU / 969 MB). Feature code only, no training.

### D3 — Evolution
- **Loop**: Mutate GA config → run evaluation → measure fitness → select best
- **Metric**: best_brier, generations_per_hour, population_diversity
- **Agent swarm**: V1 (Island Coordinator), V2 (GPU Trainer), V3 (Political Evo)
- **Scripts**: `scripts/departments/evolution/evolution-loop.sh`
- **Islands**: S10–S15 on HF Spaces (Nomos42 account), data in `data/swarm-metrics.json`

### D4 — Betting
- **Loop**: Tweak strategy → backtest on historical → measure ROI/Sharpe → keep/revert
- **Metric**: roi_delta, sharpe_ratio, kelly_edge, win_rate
- **Agent swarm**: B1 (Odds), B2 (Value), B3 (Kelly), B4 (Strategist), B5 (Evaluator)
- **Scripts**: `scripts/departments/betting/betting-loop.sh`
- **Data**: `data/nba-agent/bankroll-state.json`, `data/nba-agent/live-odds.json`

### D5 — Evaluation
- **Loop**: Audit predictions → identify weaknesses → propose fixes → verify improvement
- **Metric**: calibration_error, false_positive_rate, brier_improvement
- **Agent swarm**: Q1 (Quality Auditor), Q2 (Benchmark Tracker)
- **Scripts**: `scripts/departments/evaluation/evaluation-loop.sh`
- **Data**: `data/nba-agent/latest-eval.json`

### D6 — Infra
- **Loop**: Health check all systems → detect issues → auto-fix → verify restoration
- **Metric**: uptime_pct, restart_count, response_time_ms
- **Agent swarm**: I1 (Fleet Manager), I2 (Infra Agent)
- **Scripts**: `scripts/departments/infra/infra-loop.sh`
- **Data**: `data/infra-status.json`, `data/agent-health.json`

### D7 — Political
- **Loop**: Scan political signals → test new features → measure alpha → keep/revert
- **Metric**: political_brier, etf_roi, signal_accuracy
- **Agent swarm**: 4 political agents (signals, social, insider, prices)
- **Scripts**: `scripts/departments/political/political-loop.sh`
- **Repo**: /home/termius/nomos-political-alpha

### D8 — Creative (RGWA)
- **Loop**: Generate art → quality check → curate → publish
- **Metric**: quality_score, pieces_per_day, diversity_index
- **Agent swarm**: 5 RGWA agents (visual-artist, music-composer, video-director, quality-critic, style-curator)
- **Scripts**: `scripts/departments/creative/creative-loop.sh`
- **Repo**: /home/termius/rgwa

## Guardian Orchestrator

`scripts/departments/guardian-orchestrator.py`

- Runs each department in sequence, 5-min timeout per department
- Collects JSON metrics from each loop's stdout (last line must be valid JSON)
- Cross-pollinates wins: departments that report `"improved": true` write to `data/departments/wins-latest.json`
- Writes full cycle result to `data/departments/guardian-status.json`
- Total max wall-clock: 8 x 5min = 40min (in practice much less — most loops are fast checks)

### Cron setup (add to crontab)

```bash
# Guardian Orchestrator — every 30min
*/30 * * * * /usr/bin/python3 /home/termius/mon-ipad/scripts/departments/guardian-orchestrator.py >> /home/termius/mon-ipad/logs/guardian.log 2>&1
```

## Karpathy Loop Contract

Each department loop MUST:
1. Be a valid bash script at `scripts/departments/{name}/{name}-loop.sh`
2. Complete within 300 seconds (guardian enforces timeout)
3. Print valid JSON as the LAST line of stdout:
   ```json
   {"status": "completed|placeholder", "department": "name", "metric": "metric_name", "improved": true|false, ...}
   ```
4. Exit 0 on success, non-zero on failure
5. Never run ML training (VM rule: ZERO ML on VM)

## Status

| Department | Script | Status | Primary Metric |
|------------|--------|--------|----------------|
| research | research-loop.sh | placeholder | proposals_generated |
| engineering | engineering-loop.sh | placeholder | brier_delta |
| evolution | evolution-loop.sh | placeholder | best_brier |
| betting | betting-loop.sh | placeholder | roi_delta |
| evaluation | evaluation-loop.sh | placeholder | calibration_error |
| infra | infra-loop.sh | placeholder | uptime_pct |
| political | political-loop.sh | placeholder | political_brier |
| creative | creative-loop.sh | placeholder | quality_score |

All loops are currently in placeholder state — they read existing data files and report current
state without making modifications. Promote to active loops by adding the modify→measure→revert
logic inside each script.
