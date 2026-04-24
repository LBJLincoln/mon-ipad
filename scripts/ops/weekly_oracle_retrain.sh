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

TS=$(date -u +%FT%H:%MZ)
log() { echo "[$TS] $*" >&2; }

# Retrain NBA + POL oracles. Each takes ~3-5 min on Kaggle CPU.
retrain_one() {
  local tf="$1"             # nba | pol
  local kernel="alexismoret6/${tf}-oracle-train"
  local kernel_dir="scripts/kaggle/train_${tf}_oracle"
  local out_dir="/tmp/kaggle-${tf}-oracle-out"
  local hf_dataset="LBJLincoln26/${tf}-oracle-model"
  local space_id="LBJLincoln26/${tf}-oracle"
  local pickle_name="${tf}-oracle.pkl"

  log "[${tf}] pushing kernel $kernel"
  (cd "$kernel_dir" && kaggle kernels push 2>&1 | tail -3)

  for i in $(seq 1 30); do
    status=$(kaggle kernels status "$kernel" 2>&1 | grep -oE 'KernelWorkerStatus\.[A-Z]+' | head -1)
    log "  [${tf}] poll $i: $status"
    case "$status" in
      *COMPLETE*) break ;;
      *ERROR*|*CANCELLED*) log "[${tf}] kernel FAILED with $status"; return 1 ;;
    esac
    sleep 30
  done

  rm -rf "$out_dir"; mkdir -p "$out_dir"
  kaggle kernels output "$kernel" -p "$out_dir" 2>&1 | tail -3
  if [ ! -f "$out_dir/$pickle_name" ]; then
    log "[${tf}] FATAL: no pickle"; return 2
  fi
  CV_BRIER=$(python3 -c "import json; print(json.load(open('$out_dir/summary.json'))['cv_brier_mean'])")
  log "[${tf}] fresh CV Brier: $CV_BRIER"

  python3 <<PY
import os
from huggingface_hub import HfApi
api = HfApi(token=os.environ.get("HF_TOKEN_NBA") or os.environ.get("HF_TOKEN"))
api.upload_file(
    path_or_fileobj="$out_dir/$pickle_name", path_in_repo="$pickle_name",
    repo_id="$hf_dataset", repo_type="dataset",
    commit_message="weekly retrain: CV brier=$CV_BRIER",
)
api.upload_file(
    path_or_fileobj="$out_dir/summary.json", path_in_repo="summary.json",
    repo_id="$hf_dataset", repo_type="dataset",
    commit_message="weekly summary: CV brier=$CV_BRIER",
)
api.restart_space("$space_id", factory_reboot=False)
print("[${tf}] ok")
PY
}

source "$REPO/.env.local" 2>/dev/null || true

log "=== weekly retrain NBA ==="
retrain_one nba || log "NBA retrain FAILED (continuing)"
log "=== weekly retrain POL ==="
retrain_one pol || log "POL retrain FAILED (continuing)"
log "DONE both oracles"
exit 0

# below is the legacy single-target code, unreachable now but kept for reference:
# shellcheck disable=SC2317
KERNEL="alexismoret6/nba-oracle-train"
KERNEL_DIR="scripts/kaggle/train_nba_oracle"
OUT_DIR="/tmp/kaggle-oracle-out"

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
