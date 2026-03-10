#!/bin/bash
# S96 Comprehensive Ingestion — Target: 16,018 → 50K vectors
# Runs in 3 phases:
#   Phase 1: Local JSONL files (all sectors, ~12K records)
#   Phase 2: HF sujet-ai/Sujet-Finance-Instruct-177k (10K records for finance)
#   Phase 3: HF harvard-lil/cold-french-law (10K records for juridique)
#
# Usage: source .env.local && nohup bash ops/ingest-s96.sh &
# Monitor: tail -f data/ingest/ingest-s96.log
#          cat data/ingest/progress.json

set -uo pipefail
cd /home/termius/mon-ipad

LOG=/home/termius/mon-ipad/data/ingest/ingest-s96.log
SCRIPT=ops/fast-ingest.py

# Redirect ALL output to log file (no tee buffering issues)
exec >> "$LOG" 2>&1

echo "========================================"
echo "  S96 INGESTION START: $(date -u)"
echo "  Target: 16,018 → 50,000 vectors"
echo "========================================"

# Check E5 vector count before
echo ""
echo "--- PRE-INGESTION VECTOR COUNT ---"
python3 -u -c "
import urllib.request, json, os
key = os.environ.get('PINECONE_API_KEY','')
host = 'https://sectors-e5-multilingual-a4mkzmz.svc.aped-4627-b74a.pinecone.io'
req = urllib.request.Request(f'{host}/describe_index_stats', headers={'Api-Key': key}, method='POST', data=b'{}')
resp = urllib.request.urlopen(req, timeout=15)
data = json.loads(resp.read().decode())
count = data.get('totalVectorCount', 0)
print(f'  E5 vectors: {count:,}')
"

# ── Phase 1: Local JSONL files ──────────────────────────────
echo ""
echo "========================================"
echo "  PHASE 1: Local JSONL (all sectors)"
echo "========================================"
echo "  Start: $(date -u)"

python3 -u "$SCRIPT" --all --workers 4 --skip-existing --delay 0

echo "  Phase 1 done: $(date -u)"

# Check vector count after phase 1
echo ""
echo "--- POST-PHASE-1 VECTOR COUNT ---"
python3 -u -c "
import urllib.request, json, os
key = os.environ.get('PINECONE_API_KEY','')
host = 'https://sectors-e5-multilingual-a4mkzmz.svc.aped-4627-b74a.pinecone.io'
req = urllib.request.Request(f'{host}/describe_index_stats', headers={'Api-Key': key}, method='POST', data=b'{}')
resp = urllib.request.urlopen(req, timeout=15)
data = json.loads(resp.read().decode())
count = data.get('totalVectorCount', 0)
print(f'  E5 vectors: {count:,}')
"

# ── Phase 2: HF Sujet Finance (10K) ────────────────────────
echo ""
echo "========================================"
echo "  PHASE 2: HF Sujet Finance (10K)"
echo "========================================"
echo "  Start: $(date -u)"

python3 -u "$SCRIPT" --hf-dataset sujet-ai/Sujet-Finance-Instruct-177k --hf-sector finance --max 10000 --workers 4 --skip-existing --delay 0

echo "  Phase 2 done: $(date -u)"

# Check vector count after phase 2
echo ""
echo "--- POST-PHASE-2 VECTOR COUNT ---"
python3 -u -c "
import urllib.request, json, os
key = os.environ.get('PINECONE_API_KEY','')
host = 'https://sectors-e5-multilingual-a4mkzmz.svc.aped-4627-b74a.pinecone.io'
req = urllib.request.Request(f'{host}/describe_index_stats', headers={'Api-Key': key}, method='POST', data=b'{}')
resp = urllib.request.urlopen(req, timeout=15)
data = json.loads(resp.read().decode())
count = data.get('totalVectorCount', 0)
print(f'  E5 vectors: {count:,}')
"

# ── Phase 3: HF Cold French Law for Juridique (10K) ────────
echo ""
echo "========================================"
echo "  PHASE 3: HF Cold French Law (10K)"
echo "========================================"
echo "  Start: $(date -u)"

python3 -u "$SCRIPT" --hf-dataset harvard-lil/cold-french-law --hf-sector juridique --max 10000 --workers 4 --skip-existing --delay 0

echo "  Phase 3 done: $(date -u)"

# ── Final count ─────────────────────────────────────────────
echo ""
echo "========================================"
echo "  S96 INGESTION COMPLETE: $(date -u)"
echo "========================================"
python3 -u -c "
import urllib.request, json, os
key = os.environ.get('PINECONE_API_KEY','')
host = 'https://sectors-e5-multilingual-a4mkzmz.svc.aped-4627-b74a.pinecone.io'
req = urllib.request.Request(f'{host}/describe_index_stats', headers={'Api-Key': key}, method='POST', data=b'{}')
resp = urllib.request.urlopen(req, timeout=15)
data = json.loads(resp.read().decode())
count = data.get('totalVectorCount', 0)
print(f'  FINAL E5 vectors: {count:,}')
print(f'  Target: 50,000')
print(f'  Gap: {max(0, 50000 - count):,}')
"
