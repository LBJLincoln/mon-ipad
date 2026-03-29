#!/bin/bash
# ══════════════════════════════════════════════════════════════
# NOMOS42 COMPUTE CLI — Unified platform management
# ══════════════════════════════════════════════════════════════
# Usage: compute-cli.sh <platform> <action> [args]
#
# Platforms: spaces | kaggle | modal | codespace
# ══════════════════════════════════════════════════════════════

set -uo pipefail

# ── Env & Paths ───────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$REPO_DIR/logs"
mkdir -p "$LOG_DIR"

source "$REPO_DIR/.env.local" 2>/dev/null || true

# ── Colors ────────────────────────────────────────────────────
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

ok()   { echo -e "${GREEN}[OK]${RESET} $*"; }
err()  { echo -e "${RED}[ERR]${RESET} $*" >&2; }
warn() { echo -e "${YELLOW}[WARN]${RESET} $*"; }
info() { echo -e "${BLUE}[INFO]${RESET} $*"; }
hdr()  { echo -e "\n${BOLD}${CYAN}$*${RESET}"; }

# ── Island map ────────────────────────────────────────────────
# Format: ID:slug:url:role
declare -A SPACE_SLUG=(
  [S10]="Nomos42/nba-quant"
  [S11]="Nomos42/nba-quant-2"
  [S12]="Nomos42/nba-evo-3"
  [S13]="Nomos42/nba-evo-4"
  [S14]="Nomos42/nba-evo-5"
  [S15]="Nomos42/nba-evo-6"
)

declare -A SPACE_URL=(
  [S10]="https://nomos42-nba-quant.hf.space"
  [S11]="https://nomos42-nba-quant-2.hf.space"
  [S12]="https://nomos42-nba-evo-3.hf.space"
  [S13]="https://nomos42-nba-evo-4.hf.space"
  [S14]="https://nomos42-nba-evo-5.hf.space"
  [S15]="https://nomos42-nba-evo-6.hf.space"
)

declare -A SPACE_ROLE=(
  [S10]="exploitation (mut=0.09, feat=63)"
  [S11]="exploration  (mut=0.15, feat=80)"
  [S12]="extra_trees  (mut=0.08, feat=60)"
  [S13]="catboost     (mut=0.10, feat=66)"
  [S14]="lightgbm     (mut=0.08, feat=55)"
  [S15]="wide_search  (mut=0.18, feat=80)"
)

SPACE_ORDER=(S10 S11 S12 S13 S14 S15)

# Kaggle kernels
KAGGLE_NBA="alexismoret6/nba-karpathy-loop"
KAGGLE_POL="alexismoret6/political-alpha-karpathy-loop"
KAGGLE_BACKTEST="alexismoret6/nba-season-backtest"

# Modal app
MODAL_APP="nba-tabicl-evolution"
MODAL_SCRIPT="$SCRIPT_DIR/modal_tabicl_evolution.py"

# Codespace repo
GH_REPO="LBJLincoln/mon-ipad"
CS_MACHINE="basicLinux32gb"

# ══════════════════════════════════════════════════════════════
# SPACES COMMANDS
# ══════════════════════════════════════════════════════════════

spaces_usage() {
  cat <<EOF
Usage: compute-cli.sh spaces <action> [args]

Actions:
  status          Health check all 6 NBA islands
  keepalive       Ping all islands (prevent sleep)
  restart <id>    Restart a specific island (S10-S15)
  logs <id>       Get recent logs from a space
  config <id>     Show current evolution config
  deploy          Push feature engine to all spaces (via HF subtree push)
  list            List all islands with roles
EOF
}

spaces_list() {
  hdr "HF Evolution Islands"
  printf "  %-6s  %-40s  %s\n" "ID" "Slug" "Role"
  printf "  %-6s  %-40s  %s\n" "──" "────" "────"
  for ID in "${SPACE_ORDER[@]}"; do
    printf "  %-6s  %-40s  %s\n" "$ID" "${SPACE_SLUG[$ID]}" "${SPACE_ROLE[$ID]}"
  done
}

spaces_status() {
  hdr "HF Spaces Status — $(date -u +"%Y-%m-%d %H:%M UTC")"
  local HEALTHY=0 TOTAL=0

  for ID in "${SPACE_ORDER[@]}"; do
    URL="${SPACE_URL[$ID]}"
    TOTAL=$((TOTAL + 1))

    # Fetch /api/status JSON
    STATUS_JSON=$(curl -s --max-time 15 "$URL/api/status" 2>/dev/null)
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 15 "$URL/api/status" 2>/dev/null)

    if [ "$HTTP_CODE" = "200" ]; then
      BRIER=$(echo "$STATUS_JSON" | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin)
    v=d.get('best_brier', d.get('best','?'))
    print(f'{float(v):.5f}' if v != '?' else '?')
except: print('?')
" 2>/dev/null)
      GEN=$(echo "$STATUS_JSON" | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin)
    print(d.get('generation', d.get('gen','?')))
except: print('?')
" 2>/dev/null)
      ok "$ID (${SPACE_ROLE[$ID]%% *}) — brier=${BRIER}  gen=${GEN}  [${HTTP_CODE}]"
      HEALTHY=$((HEALTHY + 1))
    else
      err "$ID (${SPACE_ROLE[$ID]%% *}) — DOWN  [HTTP ${HTTP_CODE}]  ${SPACE_URL[$ID]}"
    fi
  done

  echo ""
  info "Summary: ${HEALTHY}/${TOTAL} islands healthy"
}

spaces_keepalive() {
  hdr "HF Spaces Keepalive — $(date -u +"%Y-%m-%d %H:%M UTC")"
  for ID in "${SPACE_ORDER[@]}"; do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "${SPACE_URL[$ID]}/" 2>/dev/null)
    if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "302" ]; then
      ok "$ID: ${HTTP_CODE}"
    else
      warn "$ID: ${HTTP_CODE} (may be waking)"
    fi
  done
}

spaces_restart() {
  local ID="${1:-}"
  if [ -z "$ID" ]; then err "Usage: compute-cli.sh spaces restart <S10|S11|...|S15>"; exit 1; fi
  ID="${ID^^}"
  if [ -z "${SPACE_SLUG[$ID]+x}" ]; then err "Unknown space: $ID. Valid: S10-S15"; exit 1; fi

  SLUG="${SPACE_SLUG[$ID]}"
  hdr "Restarting $ID ($SLUG)"

  if [ -z "${HF_TOKEN:-}" ]; then
    err "HF_TOKEN not set — cannot call HF API"
    exit 1
  fi

  # Use HF Hub API to restart the space runtime
  RESPONSE=$(curl -s -w "\nHTTP:%{http_code}" -X POST \
    "https://huggingface.co/api/spaces/${SLUG}/restart?factory=true" \
    -H "Authorization: Bearer ${HF_TOKEN}" 2>/dev/null)

  HTTP_STATUS=$(echo "$RESPONSE" | grep "HTTP:" | cut -d: -f2)
  BODY=$(echo "$RESPONSE" | grep -v "HTTP:")

  if [ "$HTTP_STATUS" = "200" ] || [ "$HTTP_STATUS" = "204" ]; then
    ok "$ID restarted successfully"
  else
    warn "$ID restart response HTTP ${HTTP_STATUS}: ${BODY}"
    info "Trying wake via curl ping..."
    curl -s --max-time 30 "${SPACE_URL[$ID]}/" > /dev/null 2>&1
    ok "$ID ping sent"
  fi
}

spaces_logs() {
  local ID="${1:-}"
  if [ -z "$ID" ]; then err "Usage: compute-cli.sh spaces logs <S10|S11|...|S15>"; exit 1; fi
  ID="${ID^^}"
  if [ -z "${SPACE_SLUG[$ID]+x}" ]; then err "Unknown space: $ID. Valid: S10-S15"; exit 1; fi

  SLUG="${SPACE_SLUG[$ID]}"
  hdr "Logs for $ID ($SLUG)"
  info "URL: ${SPACE_URL[$ID]}/api/status"

  # Get status endpoint for live data
  STATUS_JSON=$(curl -s --max-time 20 "${SPACE_URL[$ID]}/api/status" 2>/dev/null)
  if [ -n "$STATUS_JSON" ]; then
    echo "$STATUS_JSON" | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin)
    for k,v in d.items():
        print(f'  {k}: {v}')
except Exception as e:
    print(sys.stdin.read())
" 2>/dev/null
  else
    warn "No response from /api/status — space may be sleeping"
    info "Try: curl ${SPACE_URL[$ID]}/api/status"
  fi

  # HF Hub API logs (requires token)
  if [ -n "${HF_TOKEN:-}" ]; then
    info "Fetching HF build logs..."
    curl -s --max-time 20 \
      "https://huggingface.co/api/spaces/${SLUG}/runtime" \
      -H "Authorization: Bearer ${HF_TOKEN}" 2>/dev/null | \
      python3 -c "
import sys,json
try:
    d=json.load(sys.stdin)
    print(f'  stage: {d.get(\"stage\",\"?\")}')
    print(f'  hardware: {d.get(\"hardware\",{}).get(\"current\",\"?\")}')
    err=d.get('errorMessage','')
    if err: print(f'  error: {err}')
except: pass
" 2>/dev/null
  fi
}

spaces_config() {
  local ID="${1:-}"
  if [ -z "$ID" ]; then err "Usage: compute-cli.sh spaces config <S10|S11|...|S15>"; exit 1; fi
  ID="${ID^^}"
  if [ -z "${SPACE_SLUG[$ID]+x}" ]; then err "Unknown space: $ID. Valid: S10-S15"; exit 1; fi

  hdr "Config for $ID — ${SPACE_SLUG[$ID]}"
  echo -e "  Role:  ${SPACE_ROLE[$ID]}"
  echo -e "  URL:   ${SPACE_URL[$ID]}"

  STATUS_JSON=$(curl -s --max-time 15 "${SPACE_URL[$ID]}/api/status" 2>/dev/null)
  if [ -n "$STATUS_JSON" ]; then
    echo ""
    info "Live config from /api/status:"
    echo "$STATUS_JSON" | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin)
    cfg=d.get('config', d)
    for k,v in cfg.items():
        print(f'  {k}: {v}')
except: print('  (could not parse JSON)')
" 2>/dev/null
  fi
}

spaces_deploy() {
  hdr "Deploy Feature Engine to All Spaces"
  warn "This pushes the feature engine via HF Space subtree (see feedback_hf_deploy_subtree.md)"

  FEATURE_ENGINE="$REPO_DIR/features/engine.py"
  if [ ! -f "$FEATURE_ENGINE" ]; then
    err "Feature engine not found: $FEATURE_ENGINE"
    exit 1
  fi

  info "Engine: $FEATURE_ENGINE"
  ENGINE_VERSION=$(python3 -c "
import re, sys
txt = open('$FEATURE_ENGINE').read()
m = re.search(r'version\s*=\s*[\"\\x27]([^\"\\x27]+)', txt)
print(m.group(1) if m else 'unknown')
" 2>/dev/null || echo "unknown")
  info "Version: $ENGINE_VERSION"

  # Deploy via huggingface-hub CLI (subtree push per feedback rules)
  if ! command -v huggingface-cli &>/dev/null; then
    err "huggingface-cli not found — install with: pip install huggingface-hub"
    exit 1
  fi

  for ID in "${SPACE_ORDER[@]}"; do
    SLUG="${SPACE_SLUG[$ID]}"
    info "Pushing to $ID ($SLUG)..."
    # Upload just the engine file
    python3 -c "
from huggingface_hub import HfApi
import os
api = HfApi(token=os.environ.get('HF_TOKEN',''))
api.upload_file(
    path_or_fileobj='$FEATURE_ENGINE',
    path_in_repo='features/engine.py',
    repo_id='$SLUG',
    repo_type='space',
    commit_message='feat: engine v${ENGINE_VERSION} deploy via compute-cli'
)
print('  pushed OK')
" 2>/dev/null && ok "$ID: deployed" || err "$ID: deploy failed"
  done
}

# ══════════════════════════════════════════════════════════════
# KAGGLE COMMANDS
# ══════════════════════════════════════════════════════════════

kaggle_usage() {
  cat <<EOF
Usage: compute-cli.sh kaggle <action> [args]

Actions:
  status [kernel]  Check kernel status (default: nba-karpathy-loop)
  list             List all kernels
  push <dir>       Push and run a notebook from a directory
  logs <kernel>    Get kernel output
  run-nba          Push NBA Karpathy loop
  run-pol          Push Political Karpathy loop
  run-backtest     Push NBA season backtest

Kernels:
  nba     = $KAGGLE_NBA
  pol     = $KAGGLE_POL
  backtest= $KAGGLE_BACKTEST
EOF
}

_kaggle_kernel_alias() {
  case "${1:-nba}" in
    nba|karpathy) echo "$KAGGLE_NBA" ;;
    pol|political) echo "$KAGGLE_POL" ;;
    backtest) echo "$KAGGLE_BACKTEST" ;;
    *) echo "$1" ;;
  esac
}

kaggle_status() {
  local TARGET="${1:-}"
  hdr "Kaggle Kernel Status — $(date -u +"%Y-%m-%d %H:%M UTC")"

  if [ -n "$TARGET" ]; then
    KERNEL=$(_kaggle_kernel_alias "$TARGET")
    info "Checking: $KERNEL"
    kaggle kernels status "$KERNEL" 2>/dev/null || err "Could not get status for $KERNEL"
  else
    # Check all known kernels
    for K in "$KAGGLE_NBA" "$KAGGLE_POL" "$KAGGLE_BACKTEST"; do
      info "Checking: $K"
      STATUS=$(kaggle kernels status "$K" 2>/dev/null | grep -oP 'KernelWorkerStatus\.\K\w+' || echo "UNKNOWN")
      case "$STATUS" in
        RUNNING)  ok "$K: RUNNING" ;;
        COMPLETE) warn "$K: COMPLETE (relaunch with: compute-cli.sh kaggle run-nba)" ;;
        ERROR)    err "$K: ERROR" ;;
        CANCEL*)  warn "$K: CANCELLED" ;;
        *)        info "$K: $STATUS" ;;
      esac
    done
  fi
}

kaggle_list() {
  hdr "Kaggle Kernels"
  kaggle kernels list --mine 2>/dev/null || err "kaggle CLI not configured"
}

kaggle_push() {
  local DIR="${1:-}"
  if [ -z "$DIR" ]; then err "Usage: compute-cli.sh kaggle push <directory>"; exit 1; fi
  if [ ! -d "$DIR" ]; then err "Directory not found: $DIR"; exit 1; fi

  hdr "Pushing Kaggle Kernel from $DIR"
  (cd "$DIR" && kaggle kernels push -p . 2>&1) && ok "Kernel pushed" || err "Push failed"
}

kaggle_logs() {
  local TARGET="${1:-nba}"
  KERNEL=$(_kaggle_kernel_alias "$TARGET")
  hdr "Kaggle Logs: $KERNEL"
  kaggle kernels output "$KERNEL" -p /tmp/kaggle-output-$$ 2>/dev/null && \
    ls /tmp/kaggle-output-$$/ 2>/dev/null && \
    cat /tmp/kaggle-output-$$/*.log 2>/dev/null || \
    info "No output available yet (kernel may still be running)"
  rm -rf /tmp/kaggle-output-$$ 2>/dev/null || true
}

kaggle_run_nba() {
  hdr "Launching NBA Karpathy Loop on Kaggle"
  kaggle_push "$SCRIPT_DIR/kaggle"
}

kaggle_run_pol() {
  hdr "Launching Political Karpathy Loop on Kaggle"
  local POL_DIR
  POL_DIR="$(dirname "$REPO_DIR")/nomos-political-alpha/scripts/kaggle"
  if [ ! -d "$POL_DIR" ]; then err "Political kaggle dir not found: $POL_DIR"; exit 1; fi
  kaggle_push "$POL_DIR"
}

kaggle_run_backtest() {
  hdr "Launching NBA Season Backtest on Kaggle"
  kaggle_push "$SCRIPT_DIR/kaggle-backtest"
}

# ══════════════════════════════════════════════════════════════
# MODAL COMMANDS
# ══════════════════════════════════════════════════════════════

modal_usage() {
  cat <<EOF
Usage: compute-cli.sh modal <action> [args]

Actions:
  status         Check Modal app status / active runs
  run [--gens N] Run NBA TabICL evolution (default: 200 gens)
  run-resume     Resume evolution from last checkpoint
  logs           Get recent Modal app logs
  deploy         Deploy/update Modal app
  stop           Stop running Modal app

App: $MODAL_APP
Script: $MODAL_SCRIPT
EOF
}

modal_status() {
  hdr "Modal Status — $(date -u +"%Y-%m-%d %H:%M UTC")"

  if ! command -v modal &>/dev/null; then
    err "modal CLI not found — install with: pip install modal"
    exit 1
  fi

  info "Active apps:"
  modal app list 2>/dev/null | grep -E "nba|$MODAL_APP" || info "  (none matching nba)"

  info "All recent apps:"
  modal app list 2>/dev/null | head -20 || err "Could not list Modal apps"
}

modal_run() {
  local EXTRA_ARGS="$*"
  hdr "Running Modal NBA TabICL Evolution"

  if ! command -v modal &>/dev/null; then err "modal not installed"; exit 1; fi
  if [ ! -f "$MODAL_SCRIPT" ]; then err "Script not found: $MODAL_SCRIPT"; exit 1; fi

  info "Script: $MODAL_SCRIPT"
  info "Args: ${EXTRA_ARGS:-<defaults>}"
  info "Launching in background..."

  # Run in background and tail logs
  nohup modal run "$MODAL_SCRIPT" $EXTRA_ARGS >> "$LOG_DIR/modal-run.log" 2>&1 &
  MODAL_PID=$!
  ok "Modal launched (PID $MODAL_PID)"
  info "Logs: tail -f $LOG_DIR/modal-run.log"
}

modal_run_resume() {
  modal_run "--resume"
}

modal_logs() {
  hdr "Modal Logs"
  if [ -f "$LOG_DIR/modal-run.log" ]; then
    tail -50 "$LOG_DIR/modal-run.log"
  else
    info "No local modal log found at $LOG_DIR/modal-run.log"
    info "Try: modal app logs $MODAL_APP"
    modal app logs "$MODAL_APP" 2>/dev/null || true
  fi
}

modal_deploy() {
  hdr "Deploying Modal App"
  if ! command -v modal &>/dev/null; then err "modal not installed"; exit 1; fi
  modal deploy "$MODAL_SCRIPT" 2>&1 && ok "Modal app deployed" || err "Deploy failed"
}

modal_stop() {
  hdr "Stopping Modal App: $MODAL_APP"
  modal app stop "$MODAL_APP" 2>/dev/null && ok "Stopped" || warn "Could not stop (may not be running)"
}

# ══════════════════════════════════════════════════════════════
# CODESPACE COMMANDS
# ══════════════════════════════════════════════════════════════

codespace_usage() {
  cat <<EOF
Usage: compute-cli.sh codespace <action> [args]

Actions:
  create         Create a new Codespace for $GH_REPO
  status         List all Codespaces and their status
  ssh [name]     SSH into a Codespace (default: first active)
  stop [name]    Stop a Codespace
  delete [name]  Delete a Codespace
  ports [name]   List forwarded ports

Repo: $GH_REPO
Machine: $CS_MACHINE
EOF
}

codespace_create() {
  hdr "Creating Codespace for $GH_REPO"

  if ! command -v gh &>/dev/null; then err "gh CLI not found"; exit 1; fi

  info "Machine: $CS_MACHINE"
  info "Branch: main"

  gh codespace create \
    --repo "$GH_REPO" \
    --machine "$CS_MACHINE" \
    --branch main \
    --idle-timeout 120m \
    2>&1 && ok "Codespace created" || err "Creation failed"
}

codespace_status() {
  hdr "Codespace Status"
  if ! command -v gh &>/dev/null; then err "gh CLI not found"; exit 1; fi
  gh codespace list 2>/dev/null || err "Could not list codespaces"
}

codespace_ssh() {
  local NAME="${1:-}"
  hdr "SSH into Codespace"
  if ! command -v gh &>/dev/null; then err "gh CLI not found"; exit 1; fi

  if [ -n "$NAME" ]; then
    gh codespace ssh --codespace "$NAME"
  else
    # Auto-pick first running codespace for this repo
    CS_NAME=$(gh codespace list --json name,repository,state \
      --jq ".[] | select(.repository==\"$GH_REPO\" and .state==\"Available\") | .name" \
      2>/dev/null | head -1)
    if [ -z "$CS_NAME" ]; then
      err "No available Codespace found for $GH_REPO"
      info "Run: compute-cli.sh codespace create"
      exit 1
    fi
    info "Connecting to: $CS_NAME"
    gh codespace ssh --codespace "$CS_NAME"
  fi
}

codespace_stop() {
  local NAME="${1:-}"
  hdr "Stopping Codespace"
  if ! command -v gh &>/dev/null; then err "gh CLI not found"; exit 1; fi

  if [ -n "$NAME" ]; then
    gh codespace stop --codespace "$NAME" && ok "Stopped: $NAME" || err "Failed to stop $NAME"
  else
    CS_NAME=$(gh codespace list --json name,repository,state \
      --jq ".[] | select(.repository==\"$GH_REPO\") | .name" \
      2>/dev/null | head -1)
    if [ -z "$CS_NAME" ]; then
      warn "No Codespace found for $GH_REPO"
    else
      gh codespace stop --codespace "$CS_NAME" && ok "Stopped: $CS_NAME" || err "Failed"
    fi
  fi
}

codespace_delete() {
  local NAME="${1:-}"
  if [ -z "$NAME" ]; then err "Usage: compute-cli.sh codespace delete <name>"; exit 1; fi
  hdr "Deleting Codespace: $NAME"
  gh codespace delete --codespace "$NAME" --force && ok "Deleted: $NAME" || err "Delete failed"
}

codespace_ports() {
  local NAME="${1:-}"
  hdr "Codespace Ports"
  if [ -n "$NAME" ]; then
    gh codespace ports --codespace "$NAME" 2>/dev/null || err "Could not list ports"
  else
    CS_NAME=$(gh codespace list --json name,repository \
      --jq ".[] | select(.repository==\"$GH_REPO\") | .name" \
      2>/dev/null | head -1)
    [ -n "$CS_NAME" ] && gh codespace ports --codespace "$CS_NAME" 2>/dev/null || err "No codespace found"
  fi
}

# ══════════════════════════════════════════════════════════════
# GLOBAL COMMANDS
# ══════════════════════════════════════════════════════════════

cmd_all_status() {
  hdr "=== NOMOS42 COMPUTE STATUS ==="
  spaces_status
  echo ""
  kaggle_status
  echo ""
  modal_status
  echo ""
  codespace_status
}

usage() {
  cat <<EOF

${BOLD}NOMOS42 Compute CLI${RESET} — Unified platform management
Usage: $(basename "$0") <platform> <action> [args]

${BOLD}Platforms:${RESET}
  spaces     HF Spaces (6 NBA evolution islands)
  kaggle     Kaggle GPU notebooks
  modal      Modal serverless GPU
  codespace  GitHub Codespaces

${BOLD}Quick commands:${RESET}
  all status       Check all platforms at once

${BOLD}Examples:${RESET}
  $(basename "$0") spaces status
  $(basename "$0") spaces restart S10
  $(basename "$0") spaces logs S13
  $(basename "$0") spaces keepalive
  $(basename "$0") kaggle status
  $(basename "$0") kaggle run-nba
  $(basename "$0") kaggle logs nba
  $(basename "$0") modal status
  $(basename "$0") modal run --gens 300
  $(basename "$0") modal logs
  $(basename "$0") codespace create
  $(basename "$0") codespace ssh
  $(basename "$0") all status

Run '$(basename "$0") <platform>' for platform-specific help.
EOF
}

# ══════════════════════════════════════════════════════════════
# DISPATCH
# ══════════════════════════════════════════════════════════════

PLATFORM="${1:-}"
ACTION="${2:-}"
shift 2 2>/dev/null || true
ARGS="$*"

case "$PLATFORM" in

  # ── All platforms ──
  all)
    case "$ACTION" in
      status) cmd_all_status ;;
      *)      usage ;;
    esac
    ;;

  # ── HF Spaces ──
  spaces|space|hf)
    case "$ACTION" in
      status)    spaces_status ;;
      keepalive) spaces_keepalive ;;
      list)      spaces_list ;;
      restart)   spaces_restart "$ARGS" ;;
      logs)      spaces_logs "$ARGS" ;;
      config)    spaces_config "$ARGS" ;;
      deploy)    spaces_deploy ;;
      ""|help)   spaces_usage ;;
      *)         err "Unknown spaces action: $ACTION"; spaces_usage; exit 1 ;;
    esac
    ;;

  # ── Kaggle ──
  kaggle|kgl)
    case "$ACTION" in
      status)     kaggle_status $ARGS ;;
      list)       kaggle_list ;;
      push)       kaggle_push "$ARGS" ;;
      logs)       kaggle_logs "${ARGS:-nba}" ;;
      run-nba)    kaggle_run_nba ;;
      run-pol)    kaggle_run_pol ;;
      run-backtest) kaggle_run_backtest ;;
      ""|help)    kaggle_usage ;;
      *)          err "Unknown kaggle action: $ACTION"; kaggle_usage; exit 1 ;;
    esac
    ;;

  # ── Modal ──
  modal)
    case "$ACTION" in
      status)     modal_status ;;
      run)        modal_run $ARGS ;;
      run-resume) modal_run_resume ;;
      logs)       modal_logs ;;
      deploy)     modal_deploy ;;
      stop)       modal_stop ;;
      ""|help)    modal_usage ;;
      *)          err "Unknown modal action: $ACTION"; modal_usage; exit 1 ;;
    esac
    ;;

  # ── Codespace ──
  codespace|cs)
    case "$ACTION" in
      create)  codespace_create ;;
      status)  codespace_status ;;
      ssh)     codespace_ssh $ARGS ;;
      stop)    codespace_stop $ARGS ;;
      delete)  codespace_delete $ARGS ;;
      ports)   codespace_ports $ARGS ;;
      ""|help) codespace_usage ;;
      *)       err "Unknown codespace action: $ACTION"; codespace_usage; exit 1 ;;
    esac
    ;;

  ""|help|--help|-h)
    usage
    ;;

  *)
    err "Unknown platform: $PLATFORM"
    usage
    exit 1
    ;;
esac
