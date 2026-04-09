#!/bin/bash
# Verify all 9 department council spaces are alive and running.
# Exit 0 = all healthy, Exit 1 = failures detected.
# Can be added to cron: 0 * * * * /home/termius/mon-ipad/scripts/councils/verify-councils.sh

TS=$(date -u +"%Y-%m-%d %H:%M UTC")
echo "=== Council Verification $TS ==="
echo ""

SPACES=(
    "D1:research:lbjlincoln-nomos-dept-d1-research"
    "D2:engineering:lbjlincoln-nomos-dept-d2-engineering"
    "D3:evolution:lbjlincoln26-nomos-dept-d3-evolution"
    "D4:product:lbjlincoln26-nomos-dept-d4-product"
    "D5:business:nomos42-nomos-dept-d5-business"
    "D6:evaluation:nomos42-nomos-dept-d6-evaluation"
    "D7:infra:testforge42-nomos-dept-d7-infra"
    "D8:finance:testforge42-nomos-dept-d8-finance"
    "D9:cross-repo:testforge42-nomos-dept-d9-cross-repo"
)

healthy=0
failed=0
total=${#SPACES[@]}

printf "%-4s %-14s %-6s %s\n" "DEPT" "NAME" "HTTP" "STATUS"
printf "%-4s %-14s %-6s %s\n" "----" "--------------" "------" "------"

for entry in "${SPACES[@]}"; do
    IFS=':' read -r dept name host <<< "$entry"
    url="https://${host}.hf.space/"

    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$url" 2>/dev/null)

    if [ "$code" = "200" ]; then
        status="OK"
        healthy=$((healthy + 1))
    else
        status="FAIL ($code)"
        failed=$((failed + 1))
    fi

    printf "%-4s %-14s %-6s %s\n" "$dept" "$name" "$code" "$status"
done

echo ""
echo "Summary: ${healthy}/${total} healthy, ${failed} failed"

if [ "$failed" -gt 0 ]; then
    echo "[ALERT] $failed council space(s) unhealthy!"
    exit 1
fi

echo "[OK] All council spaces healthy."
exit 0
