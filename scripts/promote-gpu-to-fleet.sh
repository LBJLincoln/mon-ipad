#!/bin/bash
# promote-gpu-to-fleet.sh — Promote best Karpathy GPU config to all HF islands.
# Reads data/karpathy/nba-best-config.json and POSTs to /api/promote-config.
#
# Runs hourly via cron (see crontab). Only promotes if Brier < current fleet best.
#
# Usage:
#   bash scripts/promote-gpu-to-fleet.sh            # auto: NBA+POL, all islands
#   bash scripts/promote-gpu-to-fleet.sh --nba-only # only NBA
#   bash scripts/promote-gpu-to-fleet.sh --dry-run  # log what would happen

set -euo pipefail
cd "$(dirname "$0")/.."

ARGS="${1:-}"
NBA_ONLY=0; POL_ONLY=0; DRY=0
case "$ARGS" in
  --nba-only) NBA_ONLY=1 ;;
  --pol-only) POL_ONLY=1 ;;
  --dry-run)  DRY=1 ;;
esac

ts=$(date -u +%FT%H:%MZ)
log() { echo "[$ts] $*"; }

NBA_ISLANDS=(
  "nomos42-nba-quant"
  "nomos42-nba-quant-2"
  "nomos42-nba-evo-3"
  "nomos42-nba-evo-4"
  "nomos42-nba-evo-5"
  "nomos42-nba-evo-6"
  "lbjlincoln26-nba-evo-s16"
  "lbjlincoln26-nba-evo-s17"
)
POL_ISLANDS=(
  "nomos42-political-alpha"
  "nomos42-political-alpha-2"
  "lbjlincoln-political-alpha-3"
  "lbjlincoln-political-alpha-4"
  "lbjlincoln-political-alpha-5"
  "lbjlincoln-political-alpha-6"
  "lbjlincoln-political-alpha-7"
  "lbjlincoln-political-alpha-8"
)

promote() {
  local cfg_file="$1"; local -n islands=$2; local label="$3"
  if [ ! -f "$cfg_file" ]; then log "SKIP $label: $cfg_file missing"; return; fi
  local br=$(python3 -c "import json;print(json.load(open('$cfg_file'))['best_brier'])")
  local model=$(python3 -c "import json;print(json.load(open('$cfg_file'))['model_type'])")
  local src="karpathy_lightning_${br}"
  log "$label source: $cfg_file (brier=$br model=$model)"

  local payload=$(python3 -c "
import json
d=json.load(open('$cfg_file'))
print(json.dumps({
  'model_type': d['model_type'],
  'n_estimators': d['n_estimators'],
  'max_depth': d['max_depth'],
  'min_samples_leaf': d['min_samples_leaf'],
  'max_features_ratio': d['max_features_ratio'],
  'feature_indices': d['feature_indices'],
  'brier_source': 'karpathy_lightning_'+str(d['best_brier'])[:7],
}))")

  local ok=0; local skip=0
  for host in "${islands[@]}"; do
    if [ "$DRY" = "1" ]; then
      log "  [dry-run] would POST to https://$host.hf.space/api/promote-config"
      continue
    fi
    local br_cur=$(curl -sf --max-time 5 "https://$host.hf.space/api/status" 2>/dev/null \
      | python3 -c "import json,sys;print(json.load(sys.stdin).get('best_brier',1.0))" 2>/dev/null || echo "1.0")
    # Only promote if Karpathy is meaningfully better (≥0.005)
    local is_better=$(python3 -c "print('y' if $br < ($br_cur - 0.005) else 'n')")
    if [ "$is_better" != "y" ]; then
      log "  $host brier=$br_cur (karpathy $br not ≥0.005 better) SKIP"
      skip=$((skip+1))
      continue
    fi
    local resp=$(curl -s --max-time 10 -X POST "https://$host.hf.space/api/promote-config" \
      -H "Content-Type: application/json" -d "$payload" 2>&1 || echo "")
    if echo "$resp" | grep -q '"status":"queued"'; then
      log "  $host brier=$br_cur → promoted (expected $br)"
      ok=$((ok+1))
    elif echo "$resp" | grep -q "Not Found"; then
      log "  $host NO /api/promote-config endpoint yet (needs redeploy)"
    else
      log "  $host FAIL: ${resp:0:120}"
    fi
  done
  log "$label done: $ok promoted, $skip skipped"
}

if [ "$POL_ONLY" = "0" ]; then
  promote "data/karpathy/nba-best-config.json" NBA_ISLANDS "NBA"
fi
if [ "$NBA_ONLY" = "0" ]; then
  promote "data/karpathy/political-best-config.json" POL_ISLANDS "POL"
fi

log "done"
