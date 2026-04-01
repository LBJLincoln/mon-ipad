# Department: BUSINESS (D10)

## Mission
Establish and optimize Nomos42's product-market fit, pricing strategy, and user acquisition. Build addictive pricing tiers that convert free users to paid, maximize LTV, and prepare for VC fundraising.

## Primary Metric
- **Name:** monthly_recurring_revenue
- **Current:** $0
- **Target:** $5,000
- **Direction:** higher_is_better

## Secondary Metrics
| Metric | Current | Target |
|--------|---------|--------|
| active_users | 1 | 100 |
| paid_users | 0 | 20 |
| conversion_rate | 0% | 15% |
| churn_rate | 0% | < 5% |
| avg_revenue_per_user | $0 | $45 |
| ltv_to_cac_ratio | 0 | > 3.0 |

## Product Tiers
| Tier | Price | Target Persona | Key Hook |
|------|-------|----------------|----------|
| STARTER | $19/mo | Casual bettor | Daily picks + confidence scores |
| BUILDER | $49/mo | Serious bettor | Full ensemble + Kelly + API |
| FACTORY | $149/mo | Pro/Fund | Trading Floor + custom islands + white-label |

## Search Space
| Parameter | Current | Range | Step |
|-----------|---------|-------|------|
| starter_price | 19 | [9, 29] | 2 |
| builder_price | 49 | [29, 79] | 5 |
| factory_price | 149 | [99, 299] | 10 |
| free_trial_days | 7 | [0, 30] | 7 |
| api_calls_starter | 100 | [50, 500] | 50 |
| api_calls_builder | 1000 | [500, 5000] | 500 |
| onboarding_steps | 5 | [3, 10] | 1 |
| email_drip_frequency | 3 | [1, 7] | 1 |

## Experiment Protocol
1. Load current pricing/onboarding config
2. Mutate one parameter
3. Analyze impact on conversion funnel (5 min budget)
4. Measure MRR delta (projected from funnel metrics)
5. If improved -> keep, commit
6. If not -> revert
7. Log to data/departments/business/karpathy-output.json

## Payment Infrastructure
| Component | Status | Notes |
|-----------|--------|-------|
| Stripe Account | CONNECTED | User's Stripe account |
| Payment Links | TODO | Generate for each tier |
| Webhook Handler | TODO | Process subscription events |
| Usage Metering | TODO | Track API calls per user |
| Invoice Generation | TODO | Monthly billing cycle |

## VC Preparation
- Deck: docs/vc-deck-2026.md
- Metrics dashboard: nomosdashboard.vercel.app
- Technical proof: walk-forward Brier 0.22447 over 19 weeks
- Market sizing: $100B sports betting TAM

## Tools & Paths
- **Loop script:** scripts/departments/business/business-loop.sh
- **Output:** data/departments/business/karpathy-output.json
- **Pricing config:** data/departments/business/pricing.json
- **Stripe:** Connected via user's account
- **Dashboard:** nomosdashboard.vercel.app/forge (CLIENT tab)

## Dependencies
- **Upstream:** D9 (Communication — drives traffic), D4 (Betting — provides product value)
- **Downstream:** D11 (Finance — processes revenue)
- **External:** Stripe API, email provider
- **Compute:** CPU only
