#!/bin/bash
# weekly_oracle_retrain.sh — runs the Kaggle kernel that retrains the NBA
# oracle RF from scratch, downloads the fresh pickle, uploads to HF dataset,
# and restarts the oracle Space so it reloads.
#
# Runs via cron: 0 3 * * 0 (every Sunday 03:00 UTC).
# Manual: bash scripts/ops/weekly_oracle_retrain.sh
#
# Zero billing dependency: Kaggle free CPU, HF free tier. No GH Actions minutes.

set -euo pipefail
REPO="/home/termius/mon-ipad"
cd "$REPO"

KERNEL="alexismoret6/nba-oracle-train"
KERNEL_DIR="scripts/kaggle/train_nba_oracle"
OUT_DIR="/tmp/kaggle-oracle-out"
TS=$(date -u +%FT%H:%MZ)

log() { echo "[$TS] $*" >&2; }

log "pushing Kaggle kernel $KERNEL"
(cd "$KERNEL_DIR" && kaggle kernels push 2>&1 | tail -3)

# Poll for completion (up to 15 min; CPU RF takes ~2-4 min usually)
log "waiting for kernel completion..."
for i in $(seq 1 30); do
  status=$(kaggle kernels status "$KERNEL" 2>&1 | grep -oE 'KernelWorkerStatus\.[A-Z]+' | head -1)
  log "  poll $i: $status"
  case "$status" in
    *COMPLETE*) log "kernel complete"; break ;;
    *ERROR*|*CANCELLED*)
      log "kernel FAILED with $status — aborting"
      exit 1 ;;
  esac
  sleep 30
done

rm -rf "$OUT_DIR"; mkdir -p "$OUT_DIR"
kaggle kernels output "$KERNEL" -p "$OUT_DIR" 2>&1 | tail -3
if [ ! -f "$OUT_DIR/nba-oracle.pkl" ]; then
  log "FATAL: no pickle in kernel output"
  exit 2
fi

CV_BRIER=$(python3 -c "import json; print(json.load(open('$OUT_DIR/summary.json'))['cv_brier_mean'])")
log "fresh CV Brier: $CV_BRIER"

# Upload to HF dataset + restart oracle Space
source "$REPO/.env.local" 2>/dev/null || true
python3 <<PY
import os, json
from huggingface_hub import HfApi
api = HfApi(token=os.environ.get("HF_TOKEN_NBA") or os.environ.get("HF_TOKEN"))
api.upload_file(
    path_or_fileobj="$OUT_DIR/nba-oracle.pkl",
    path_in_repo="nba-oracle.pkl",
    repo_id="LBJLincoln26/nba-oracle-model", repo_type="dataset",
    commit_message="weekly retrain: CV brier=$CV_BRIER",
)
api.upload_file(
    path_or_fileobj="$OUT_DIR/summary.json", path_in_repo="summary.json",
    repo_id="LBJLincoln26/nba-oracle-model", repo_type="dataset",
    commit_message="weekly summary: CV brier=$CV_BRIER",
)
# Restart oracle Space to reload
api.restart_space("LBJLincoln26/nba-oracle", factory_reboot=False)
print("ok")
PY

log "DONE. retrained + uploaded + Space restart triggered"
