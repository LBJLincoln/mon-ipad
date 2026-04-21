#!/bin/bash
# nomos42 YouTube ingest + HF deploy cycle — every 6h
# 1. Pull fresh uploads from seeded channels
# 2. Rebuild fleet digests + inject narrative into data/prompts/overrides.json
# 3. Upload overrides.json + manual-ingested.json to all 4 TF Spaces so live
#    runs pick up the new videos on next LLM call.
set -euo pipefail

REPO=/home/termius/mon-ipad
cd "$REPO"
# shellcheck disable=SC1091
source "$REPO/.env.local"

LOG=/tmp/youtube-ingest-deploy.log
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "[$TS] === start ===" >> "$LOG"

# 1. Autofetch recent uploads (per-channel cap 5, 7d lookback)
python3 scripts/youtube_channel_autofetch.py --max 5 >> "$LOG" 2>&1 || echo "[$TS] autofetch FAILED" >> "$LOG"

# 2. Rebuild per-fleet digests + inject into overrides.json (all 4 TFs)
python3 scripts/youtube_feeder.py --fleet all --inject >> "$LOG" 2>&1 || echo "[$TS] feeder FAILED" >> "$LOG"

# 3. Upload to each Space (account-correct HF token per space)
python3 - <<'PYEOF' >> "$LOG" 2>&1 || echo "[$TS] hf upload FAILED" >> "$LOG"
import os, sys
from huggingface_hub import HfApi

REPO_ROOT = "/home/termius/mon-ipad"
OVERRIDES = f"{REPO_ROOT}/data/prompts/overrides.json"
MANUAL = f"{REPO_ROOT}/data/youtube/manual-ingested.json"

# space_id -> hf_token env var (account that owns the space)
TARGETS = [
    ("LBJLincoln26/nba-llm-trading-floor", "HF_TOKEN_NBA"),
    ("LBJLincoln26/political-llm-trading-floor", "HF_TOKEN_NBA"),
    ("LBJLincoln26/intraday-trading-floor", "HF_TOKEN_NBA"),
    ("LBJLincoln26/political-quant-trading-floor", "HF_TOKEN_NBA"),
]

errors = []
for space_id, tok_var in TARGETS:
    tok = os.environ.get(tok_var)
    if not tok:
        errors.append(f"{space_id}: no {tok_var}")
        continue
    api = HfApi(token=tok)
    try:
        api.upload_file(
            path_or_fileobj=OVERRIDES,
            path_in_repo="data/prompts/overrides.json",
            repo_id=space_id, repo_type="space",
            commit_message="[YT-INGEST] refresh overrides.json (channel autofetch + feeder)",
        )
        api.upload_file(
            path_or_fileobj=MANUAL,
            path_in_repo="data/youtube/manual-ingested.json",
            repo_id=space_id, repo_type="space",
            commit_message="[YT-INGEST] refresh manual-ingested.json library",
        )
        print(f"uploaded overrides+manual -> {space_id}")
    except Exception as e:
        errors.append(f"{space_id}: {type(e).__name__}: {str(e)[:180]}")

if errors:
    print("ERRORS:", errors)
    sys.exit(2)
PYEOF

# 4. Commit updated digest + library via safe_commit (git mutex)
bash "$REPO/scripts/lib/safe_commit.sh" YT-INGEST \
    "[YT-INGEST] autofetch + feeder refresh $(date -u +%Y-%m-%dT%H:%MZ)" \
    data/youtube/manual-ingested.json \
    data/youtube/autofetch-log.jsonl \
    "data/youtube/$(date -u +%Y-%m-%d)-nba.json" \
    "data/youtube/$(date -u +%Y-%m-%d)-pol.json" \
    "data/youtube/$(date -u +%Y-%m-%d)-itf.json" \
    "data/youtube/$(date -u +%Y-%m-%d)-pqtf.json" \
    data/prompts/overrides.json >> "$LOG" 2>&1 || echo "[$TS] safe_commit FAILED (likely nothing to commit)" >> "$LOG"

echo "[$TS] === end ===" >> "$LOG"
