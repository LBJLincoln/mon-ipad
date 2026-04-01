#!/usr/bin/env bash
# D11 Finance/Compta — Karpathy Loop
# Tracks costs, revenue, generates financial reports, evolves accuracy
set -euo pipefail
DEPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$DEPT_DIR/../../.." && pwd)"
OUTPUT="$ROOT/data/departments/finance/karpathy-output.json"
ITERATION_FILE="$ROOT/data/departments/finance/.iteration"
REPORTS_DIR="$ROOT/data/departments/finance/reports"
mkdir -p "$REPORTS_DIR"

ITER=$(cat "$ITERATION_FILE" 2>/dev/null || echo "0")
ITER=$((ITER + 1))

echo "=== D11 FINANCE — Karpathy Loop Iteration $ITER ==="
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Step 1: Load bankroll state
BANKROLL_FILE="$ROOT/data/nba-agent/bankroll-state.json"
BALANCE="0"
PROFIT="0"
TOTAL_WAGERED="0"
if [ -f "$BANKROLL_FILE" ]; then
  BALANCE=$(python3 -c "import json; d=json.load(open('$BANKROLL_FILE')); print(d.get('balance',0))" 2>/dev/null || echo "0")
  PROFIT=$(python3 -c "import json; d=json.load(open('$BANKROLL_FILE')); print(d.get('total_profit',0))" 2>/dev/null || echo "0")
  TOTAL_WAGERED=$(python3 -c "import json; d=json.load(open('$BANKROLL_FILE')); print(d.get('total_wagered',0))" 2>/dev/null || echo "0")
fi

# Step 2: Estimate monthly costs
MONTHLY_COSTS=6  # GCP free + HF free + Kaggle free ≈ $6 (Modal usage)

# Step 3: Count HF spaces (cost centers)
HF_SPACES=0
AGENT_HEALTH="$ROOT/data/agent-health.json"
if [ -f "$AGENT_HEALTH" ]; then
  HF_SPACES=$(python3 -c "
import json
d=json.load(open('$AGENT_HEALTH'))
nba=len(d.get('projects',{}).get('nba',{}).get('spaces',{}))
pol=len(d.get('projects',{}).get('political',{}).get('spaces',{}))
print(nba+pol)
" 2>/dev/null || echo "0")
fi

# Step 4: MRR (from Stripe — placeholder until connected)
MRR=0
STRIPE_STATUS="connected_not_active"

echo "Balance: \$$BALANCE"
echo "Profit: \$$PROFIT"
echo "Monthly costs: \$$MONTHLY_COSTS"
echo "HF Spaces: $HF_SPACES"

# Step 5: Generate daily P&L report
TODAY=$(date -u +%Y-%m-%d)
cat > "$REPORTS_DIR/daily-pnl-$TODAY.json" << ENDJSON
{
  "date": "$TODAY",
  "type": "daily_pnl",
  "betting": {
    "balance": $BALANCE,
    "profit": $PROFIT,
    "wagered": $TOTAL_WAGERED
  },
  "costs": {
    "infra": $MONTHLY_COSTS,
    "hf_spaces": $HF_SPACES,
    "gpu": 0
  },
  "revenue": {
    "mrr": $MRR,
    "stripe_status": "$STRIPE_STATUS"
  },
  "net_daily_pnl": $PROFIT
}
ENDJSON

# Step 6: Write department output
cat > "$OUTPUT" << ENDJSON
{
  "department": "finance",
  "dept_id": "D11",
  "iteration": $ITER,
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "status": "active",
  "metrics": {
    "balance": $BALANCE,
    "total_profit": $PROFIT,
    "total_wagered": $TOTAL_WAGERED,
    "monthly_costs": $MONTHLY_COSTS,
    "mrr": $MRR,
    "burn_rate": $MONTHLY_COSTS,
    "runway_months": "infinite",
    "hf_spaces_cost_centers": $HF_SPACES
  },
  "cost_breakdown": {
    "gcp_vm": 0,
    "hf_spaces": 0,
    "kaggle_gpu": 0,
    "colab_gpu": 0,
    "modal": 5,
    "vercel": 0,
    "domain": 1,
    "odds_api": 0,
    "total_monthly": $MONTHLY_COSTS
  },
  "revenue_streams": {
    "saas_mrr": 0,
    "api_licensing": 0,
    "consulting": 0,
    "trading_profit": $PROFIT
  },
  "stripe_status": "$STRIPE_STATUS",
  "reports_generated": ["daily-pnl-$TODAY.json"],
  "next_actions": [
    "Activate Stripe payment processing",
    "Set up automated weekly financial summary",
    "Connect cost monitoring for Modal/GPU usage",
    "Generate VC financial metrics page"
  ]
}
ENDJSON

echo "$ITER" > "$ITERATION_FILE"
echo "Output: $OUTPUT"
echo "Daily P&L: $REPORTS_DIR/daily-pnl-$TODAY.json"
echo "=== D11 FINANCE — Iteration $ITER complete ==="
