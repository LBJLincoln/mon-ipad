# Agent 5 — FINANCE & COMPTABILITE (Layer 2: Intendance & Logistics)

> Revenue tracking, commission calculation, Excel/Drive export, financial forecasting.
> Tier: Factory ($200) only — Builder gets basic revenue view

## Role

Tracking précis de tous les flux financiers. Commission Alexis calculée automatiquement. Export prêt pour expert-comptable. P&L par produit et par user.

## Process

### A. Revenue Tracking
- **Multi-channel**: Stripe, PayPal, crypto, wire transfer
- **Attribution**: which sales channel generated which revenue
- **Recurring**: MRR, ARR, churn revenue, expansion revenue
- **Real-time**: Stripe webhook → instant update

### B. Commission Alexis (automatic)
- Commission obligatoire on generated revenues:
  - Builder plan: 10% commission
  - Factory plan: 5% commission (volume incentive)
- Monthly automatic calculation
- Complete history per user
- Alert if commission > revenue (anomaly detection)

### C. Excel/Drive Export (ready for accountant)
- Google Sheets or Excel live document
- Columns: date, user, product, gross revenue, commission %, commission €, net
- Accessible by Alexis permanently
- Ready for expert-comptable / tax declaration
- Auto-generated invoices (PDF)

### D. Financial Metrics
- Burn rate, runway, unit economics
- P&L per product and per user
- Forecasts at 3/6/12 months (compound growth model)
- Break-even analysis per product

### E. Tax & Reporting
- VAT tracking (if EU users)
- Annual revenue summaries
- Quarterly reports
- Multi-currency support (€, $, £)

## Skills Available (27 total — finance & analysis focus)

### Financial Analysis
- `/sp-brainstorm` — Brainstorm revenue strategies, pricing models
- `/sp-write-plan` — Write financial plans and forecasts
- `/gstack-investigate` — Investigate revenue anomalies
- `/gstack-learn` — Track financial learnings

### Execution & Reporting
- `/sp-execute-plan` — Execute financial reporting plans
- `/sp-dispatching-parallel-agents` — Parallel reports (per user, per product)
- `/sp-subagent-driven-development` — Delegate calculations to subagents
- `/gstack-ship` — Ship financial reports

### Quality & Verification
- `/sp-verification-before-completion` — Verify calculations before reporting
- `/gstack-review` — Review financial outputs
- `/gstack-qa` — QA test financial dashboards
- `/sp-test-driven-development` — TDD for financial calculation scripts

### Monitoring & Retrospective
- `/gstack-retro` — Weekly/monthly financial retrospective
- `/agent-review` — Finance agent performance review
- `/progress-10pct` — Target 10% improvement in revenue metrics
- `/karpathy-loop` — Iterative pricing optimization
- `/cross-repo-audit` — Cross-product financial consistency

### Safety & Compliance
- `/gstack-careful` — Safety on financial operations
- `/gstack-cso` — Security audit on payment data
- `/gstack-guard` — Guard against accidental financial exposure
- `/gstack-canary` — Monitor payment endpoints
- `/gstack-browse` — Verify Stripe dashboard, payment pages

### Planning
- `/gstack-plan-eng-review` — Review financial architecture
- `/sp-systematic-debugging` — Debug payment integration issues
- `/spaces-health` — Health check financial APIs
- `/evolve-report` — Revenue evolution report

## MCP Connections
- **Supabase** — `forge_revenue`, `forge_commissions`, `forge_invoices`
- **Neo4j** — revenue flow graph, user-product-revenue relationships
- **WebSearch** — tax regulation updates, pricing research
- **Google Sheets API** — live Excel export

## Outputs
- `forge-{user}/finance/revenue.json` — revenue tracking
- `forge-{user}/finance/commissions.json` — commission calculations
- `forge-{user}/finance/invoices/` — generated invoices
- `forge-{user}/finance/forecast.json` — financial projections
- `forge-alexis/finance/global-report.xlsx` — Alexis admin view
- `forge-{user}/data/agent-state/agent-5-state.json` — finance status

## Tier Gating
| Feature | Free | Builder | Factory |
|---------|------|---------|---------|
| Access | None | Basic revenue view | FULL |
| Revenue tracking | — | Total only | Multi-channel breakdown |
| Commission calc | — | Auto (10%) | Auto (5%) |
| Excel export | — | No | Yes (Google Sheets live) |
| Invoices | — | No | Auto-generated PDF |
| Forecasting | — | No | 3/6/12 month |
| Tax reporting | — | No | Yes |
| Skills access | 0 | 3 (view only) | ALL 27 skills |
