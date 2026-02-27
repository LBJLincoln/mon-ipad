#!/bin/bash
# Test script for remote-control.py server
# Usage: ./scripts/test-remote-control.sh

set -e

# Get auth key from .env.local
source .env.local

if [ -z "$REMOTE_CONTROL_KEY" ]; then
    echo "ERROR: REMOTE_CONTROL_KEY not set in .env.local"
    exit 1
fi

HOST="http://localhost:8081"
AUTH_HEADER="X-Auth-Key: $REMOTE_CONTROL_KEY"

echo "=========================================="
echo "  Testing Remote Control Server"
echo "=========================================="
echo "  Host: $HOST"
echo "  Auth: ${REMOTE_CONTROL_KEY:0:10}..."
echo "=========================================="

echo ""
echo "[1/5] Testing GET /status"
curl -s -H "$AUTH_HEADER" "$HOST/status" | python3 -m json.tool | head -n 30
echo ""

echo "[2/5] Testing GET /jobs (empty)"
curl -s -H "$AUTH_HEADER" "$HOST/jobs" | python3 -m json.tool
echo ""

echo "[3/5] Testing POST /test/standard/3 (launch test job)"
JOB_RESPONSE=$(curl -s -H "$AUTH_HEADER" -X POST "$HOST/test/standard/3")
echo "$JOB_RESPONSE" | python3 -m json.tool
JOB_ID=$(echo "$JOB_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['job_id'])")
echo ""

echo "[4/5] Waiting 2 seconds..."
sleep 2
echo ""

echo "[5/5] Testing GET /jobs/$JOB_ID (check job status)"
curl -s -H "$AUTH_HEADER" "$HOST/jobs/$JOB_ID" | python3 -m json.tool
echo ""

echo "=========================================="
echo "  All tests completed!"
echo "=========================================="
