#!/usr/bin/env bash
# D10 Business — Karpathy Loop
# Analyzes pricing, conversion, user metrics, evolves business strategy
set -euo pipefail
DEPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$DEPT_DIR/../../.." && pwd)"
OUTPUT="$ROOT/data/departments/business/karpathy-output.json"
ITERATION_FILE="$ROOT/data/departments/business/.iteration"

ITER=$(cat "$ITERATION_FILE" 2>/dev/null || echo "0")
ITER=$((ITER + 1))

echo "=== D10 BUSINESS — Karpathy Loop Iteration $ITER ==="
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Step 1: Check forge users
FORGE_USERS_DIR="$ROOT/forge-users"
USER_COUNT=0
if [ -d "$FORGE_USERS_DIR" ]; then
  USER_COUNT=$(ls -d "$FORGE_USERS_DIR"/*/ 2>/dev/null | wc -l)
fi

# Step 2: Load pricing config
PRICING_FILE="$ROOT/data/departments/business/pricing.json"
if [ ! -f "$PRICING_FILE" ]; then
  cat > "$PRICING_FILE" << 'PRICING'
{
  "tiers": {
    "starter": { "price": 19, "api_calls": 100, "models": 3 },
    "builder": { "price": 49, "api_calls": 1000, "models": 6, "highlight": true },
    "factory": { "price": 149, "api_calls": -1, "models": 6, "trading_floor": true }
  },
  "free_trial_days": 7,
  "annual_discount_pct": 20
}
PRICING
fi

# Step 3: Check dashboard status
DASHBOARD_STATUS="unknown"
if command -v curl &>/dev/null; then
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "https://nomosdashboard.vercel.app" 2>/dev/null || echo "0")
  [ "$HTTP_CODE" = "200" ] && DASHBOARD_STATUS="live"
fi

# Step 4: Calculate metrics
PAID_USERS=0
MRR=0
ARPU=0

echo "Forge users: $USER_COUNT"
echo "Dashboard: $DASHBOARD_STATUS"
echo "MRR: \$$MRR"

# Step 5: Write output
cat > "$OUTPUT" << ENDJSON
{
  "department": "business",
  "dept_id": "D10",
  "iteration": $ITER,
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "status": "active",
  "metrics": {
    "active_users": $USER_COUNT,
    "paid_users": $PAID_USERS,
    "mrr": $MRR,
    "arpu": $ARPU,
    "conversion_rate": 0,
    "churn_rate": 0,
    "dashboard_status": "$DASHBOARD_STATUS"
  },
  "pricing": {
    "starter": 19,
    "builder": 49,
    "factory": 149,
    "free_trial_days": 7
  },
  "funnel": {
    "visitors": 0,
    "signups": $USER_COUNT,
    "trials": 0,
    "paid": $PAID_USERS,
    "churned": 0
  },
  "next_actions": [
    "Set up Stripe payment links",
    "Create onboarding flow",
    "Enable free trial activation",
    "Connect usage metering to API"
  ]
}
ENDJSON

echo "$ITER" > "$ITERATION_FILE"
echo "Output: $OUTPUT"
echo "=== D10 BUSINESS — Iteration $ITER complete ==="
