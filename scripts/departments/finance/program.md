# Department: FINANCE / COMPTA (D11)

## Mission
Track all financial flows (revenue, costs, investments), maintain clean books, generate cross-department financial reports, and ensure regulatory compliance. Provide real-time financial health visibility.

## Primary Metric
- **Name:** financial_accuracy
- **Current:** 0%
- **Target:** 100%
- **Direction:** higher_is_better

## Secondary Metrics
| Metric | Current | Target |
|--------|---------|--------|
| revenue_tracked | $0 | all |
| cost_tracked | $0 | all |
| reports_generated_per_week | 0 | 4 |
| reconciliation_lag_hours | -- | < 1 |
| budget_variance_pct | -- | < 5% |

## Cost Structure
| Item | Monthly Cost | Category |
|------|-------------|----------|
| GCP VM (e2-micro) | $0 (free tier) | Infra |
| HF Spaces (6 NBA + 4 Political) | $0 (free CPU) | Compute |
| Kaggle GPU | $0 (free 30h/week) | Compute |
| Colab GPU | $0 (free T4) | Compute |
| Lightning AI | $0 (free 22h) | Compute |
| Modal | ~$5 (pay-per-use) | Compute |
| Vercel (5 deployments) | $0 (hobby) | Hosting |
| Domain (nomosdashboard.vercel.app) | ~$1/mo | Hosting |
| The Odds API | $0 (free tier) | Data |
| GitHub (5 repos) | $0 | DevOps |
| Supabase | $0 (free tier) | Database |
| **Total Burn Rate** | **~$6/mo** | |

## Revenue Streams
| Stream | Status | Projection |
|--------|--------|------------|
| SaaS Subscriptions ($19-149) | TODO | $5K MRR target |
| B2B API Licensing | TODO | $10K+ |
| Consulting/Strategy | TODO | Variable |
| Trading Profits (real) | ACTIVE | -$2.96 total |

## Search Space
| Parameter | Current | Range | Step |
|-----------|---------|-------|------|
| report_frequency_hours | 24 | [1, 168] | 1 |
| cost_alert_threshold | 10 | [1, 50] | 5 |
| reconciliation_window_min | 60 | [5, 1440] | 30 |
| budget_category_count | 5 | [3, 15] | 1 |
| forecast_window_days | 30 | [7, 90] | 7 |

## Experiment Protocol
1. Load current reporting config
2. Mutate one parameter
3. Generate financial report (5 min budget)
4. Measure accuracy + completeness vs manual audit
5. If improved -> keep, commit
6. If not -> revert
7. Log to data/departments/finance/karpathy-output.json

## Reports Generated
1. **Daily P&L** — Betting results + costs
2. **Weekly Summary** — Cross-department costs, revenue, projections
3. **Monthly Close** — Full reconciliation, Stripe vs actual
4. **VC Metrics** — Burn rate, runway, unit economics

## Tools & Paths
- **Loop script:** scripts/departments/finance/finance-loop.sh
- **Output:** data/departments/finance/karpathy-output.json
- **Reports:** data/departments/finance/reports/
- **Stripe data:** Via Stripe API
- **Bankroll:** data/nba-agent/bankroll-state.json

## Dependencies
- **Upstream:** D10 (Business — revenue data), D6 (Infra — cost data)
- **Downstream:** All departments (budget allocation)
- **External:** Stripe API, bank reconciliation
- **Compute:** CPU only
