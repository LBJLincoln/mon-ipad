# Nomos42 Departments — Karpathy Real Loop Architecture

> v19 — 9 departments x 5-min iterative loops x Guardian Orchestrator v3

## Architecture

```
Guardian Orchestrator v3 (cron every 4h)
├── D1 Research      — paper→extract→propose→measure
├── D2 Engineering   — code→test→measure Brier→keep/revert
├── D3 Evolution     — mutate→eval→measure fitness→select
├── D4 Product       — build→test→ship→measure
├── D5 Business      — price→onboard→convert→optimize
├── D6 Evaluation    — audit→identify→fix→verify
├── D7 Infra         — check→detect→fix→verify
├── D8 Finance       — track→report→reconcile→forecast
└── D9 Cross-Repo    — sync→audit→fix→verify
```

## File Layout

```
scripts/departments/
├── guardian-orchestrator.py          # Master runner (9 departments x 5min)
├── research/research-loop.sh
├── engineering/engineering-loop.sh
├── evolution/evolution-loop.sh
├── product/product-loop.sh
├── business/business-loop.sh
├── evaluation/evaluation-loop.sh
├── infra/infra-loop.sh
├── finance/finance-loop.sh
└── cross-repo/cross-repo-loop.sh

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

### D4 — Product
- **Loop**: Build feature → test → ship → measure adoption
- **Metric**: features_shipped, brier_delta, user_satisfaction
- **Agent swarm**: Product Builder, Karpathy loop on feature requests
- **Scripts**: `scripts/departments/product/product-loop.sh`
- **Data**: `data/departments/council-product.json`

### D5 — Business
- **Loop**: Price → onboard → convert → optimize
- **Metric**: MRR, conversion_rate, ARPU
- **Agent swarm**: Business Strategist, pricing optimizer
- **Scripts**: `scripts/departments/business/business-loop.sh`
- **Data**: `data/departments/council-business.json`

### D6 — Evaluation
- **Loop**: Audit predictions → identify weaknesses → propose fixes → verify improvement
- **Metric**: calibration_error, false_positive_rate, brier_improvement
- **Agent swarm**: Q1 (Quality Auditor), Q2 (Benchmark Tracker)
- **Scripts**: `scripts/departments/evaluation/evaluation-loop.sh`
- **Data**: `data/nba-agent/latest-eval.json`

### D7 — Infra
- **Loop**: Health check all systems → detect issues → auto-fix → verify restoration
- **Metric**: uptime_pct, restart_count, response_time_ms
- **Agent swarm**: I1 (Fleet Manager), I2 (Infra Agent)
- **Scripts**: `scripts/departments/infra/infra-loop.sh`
- **Data**: `data/infra-status.json`, `data/agent-health.json`

### D8 — Finance
- **Loop**: Track revenue/costs → report → reconcile → forecast
- **Metric**: financial_accuracy, burn_rate, MRR
- **Agent swarm**: Finance & Comptabilité agent
- **Scripts**: `scripts/departments/finance/finance-loop.sh`
- **Data**: `data/departments/council-finance.json`

### D9 — Cross-Repo
- **Loop**: Sync → audit → fix → verify parity across all repos
- **Metric**: parity_score, uncommitted_changes, cross_repo_health
- **Agent swarm**: Cross-repo health monitor
- **Scripts**: `scripts/councils/cross-repo-councils.sh`
- **Data**: `data/cross-repo-health.json`

## Guardian Orchestrator

`scripts/departments/guardian-orchestrator.py`

- Runs each department in sequence, 5-min timeout per department
- Collects JSON metrics from each loop's stdout (last line must be valid JSON)
- Cross-pollinates wins: departments that report `"improved": true` write to `data/departments/wins-latest.json`
- Writes full cycle result to `data/departments/guardian-status.json`
- Total max wall-clock: 9 x 5min = 45min (in practice much less — most loops are fast checks)

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
| product | product-loop.sh | placeholder | features_shipped |
| business | business-loop.sh | placeholder | MRR |
| evaluation | evaluation-loop.sh | placeholder | calibration_error |
| infra | infra-loop.sh | placeholder | uptime_pct |
| finance | finance-loop.sh | placeholder | burn_rate |
| cross-repo | cross-repo-loop.sh | placeholder | parity_score |

All loops are currently in placeholder state — they read existing data files and report current
state without making modifications. Promote to active loops by adding the modify→measure→revert
logic inside each script.
