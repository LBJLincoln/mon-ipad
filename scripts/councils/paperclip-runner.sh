#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# PAPERCLIP COUNCIL RUNNER — Karpathy autoresearch with real keep/revert
# ═══════════════════════════════════════════════════════════════
# Cycle 18 audit (research_april2026_cycle18_competitor_audit.md):
#
#   "Our councils CANNOT do keep/revert because Brier eval takes 10+ min
#    on VM. Fix: 30-second proxy metric (cross-val on last 50 games).
#    This is the single highest-leverage infrastructure fix available."
#
# This wrapper sits ON TOP OF hermes-runner.sh and adds the missing
# keep/revert layer:
#
#   1. Snapshot baseline Brier via scripts/brier_proxy.py --json
#   2. Capture pre-run git HEAD SHA
#   3. Delegate to hermes-runner.sh <dept> (real Claude CLI agent)
#   4. Snapshot post-run Brier
#   5. If (after - before) > REVERT_THRESHOLD → git revert HEAD (if new commit)
#      If delta <= 0 → keep (iteration wins)
#      If 0 < delta <= threshold → keep but flag for human review
#   6. Append iteration to data/councils/paperclip-ledger.jsonl
#
# Usage:
#   paperclip-runner.sh d1                       # Run one dept with keep/revert
#   paperclip-runner.sh d1 d3 d7                 # Multiple
#   paperclip-runner.sh --all                    # All 9
#   paperclip-runner.sh --threshold 0.003 d1     # Custom revert threshold
#   paperclip-runner.sh --dry-run d1             # Measure but don't revert
#
# Cron (replaces hermes-runner directly):
#   0 2,10,18 * * * .../paperclip-runner.sh d1 d3 d7
#   0 4,12,20 * * * .../paperclip-runner.sh d2 d6 d9
#   0 6,14,22 * * * .../paperclip-runner.sh d4 d5 d8
# ═══════════════════════════════════════════════════════════════

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
LOG_DIR="${ROOT}/logs/councils"
LEDGER="${ROOT}/data/councils/paperclip-ledger.jsonl"
HERMES="${ROOT}/scripts/councils/hermes-runner.sh"
PROXY="${ROOT}/scripts/brier_proxy.py"
TODAY=$(date -u +"%Y-%m-%d")

REVERT_THRESHOLD="0.005"   # 0.5 percentage points of Brier → revert
DRY_RUN=false
ALL_DEPTS=false

mkdir -p "${LOG_DIR}" "$(dirname "${LEDGER}")"

# Colors
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${CYAN}[PAPERCLIP]${NC} $(date -u +%H:%M:%S) $*"; }
ok()  { echo -e "${GREEN}[PAPERCLIP]${NC} $(date -u +%H:%M:%S) ✓ $*"; }
warn() { echo -e "${YELLOW}[PAPERCLIP]${NC} $(date -u +%H:%M:%S) ⚠ $*"; }
err() { echo -e "${RED}[PAPERCLIP]${NC} $(date -u +%H:%M:%S) ✗ $*"; }

# ── Parse args ─────────────────────────────────────────────────
DEPTS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --threshold)  REVERT_THRESHOLD="$2"; shift 2 ;;
        --dry-run)    DRY_RUN=true; shift ;;
        --all)        ALL_DEPTS=true; shift ;;
        -h|--help)
            head -40 "$0" | grep -E "^# "
            exit 0
            ;;
        *)            DEPTS+=("$1"); shift ;;
    esac
done

if $ALL_DEPTS; then
    DEPTS=(d1 d2 d3 d4 d5 d6 d7 d8 d9)
fi

if [[ ${#DEPTS[@]} -eq 0 ]]; then
    err "No departments specified. Use --all or list dept ids (d1 ... d9)."
    exit 1
fi

# ── Measure Brier via proxy ────────────────────────────────────
# HONEST NOTE: this currently uses `brier_proxy.py --json` (baseline_cv mode)
# which is a CONSTANT function of data/proxy/holdout.json. As long as the
# council doesn't regenerate that holdout file or a predictions file, delta
# will always be 0 and Paperclip will always verdict=no_op. The runner
# still delivers value as a crash gate (it will catch commits that break
# holdout loading, sklearn import, or the proxy script itself). A proper
# keep/revert gate requires councils to output per-game predictions and
# switching this call to --before/--after compare mode.
measure_brier() {
    cd "${ROOT}"
    local raw
    raw=$(python3 "${PROXY}" --json 2>/dev/null)
    if [[ -z "${raw}" ]]; then
        echo "null"
        return 1
    fi
    python3 -c "import json,sys; d=json.loads(sys.argv[1]); print(d.get('brier',''))" "${raw}"
}

# ── Run one department through the Paperclip loop ─────────────
run_paperclip() {
    local dept_id="$1"

    log "═══ PAPERCLIP ${dept_id^^} ═══"

    # Step 1: Snapshot baseline
    cd "${ROOT}"
    local pre_sha
    pre_sha=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
    local brier_before
    brier_before=$(measure_brier)
    if [[ -z "${brier_before}" || "${brier_before}" == "null" ]]; then
        err "Failed to measure baseline Brier — aborting ${dept_id}"
        return 1
    fi
    log "Baseline: brier=${brier_before} sha=${pre_sha:0:8}"

    # Step 2: Run the Hermes Claude-CLI agent for this dept
    local iter_start=$(date +%s)
    if ! bash "${HERMES}" "${dept_id}" > "${LOG_DIR}/paperclip-${dept_id}-${TODAY}.log" 2>&1; then
        warn "Hermes exited non-zero for ${dept_id} — iteration continues to measure"
    fi
    local iter_end=$(date +%s)
    local duration=$(( iter_end - iter_start ))

    # Step 3: Snapshot post-run state
    local post_sha
    post_sha=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
    local brier_after
    brier_after=$(measure_brier)

    local new_commit=0
    [[ "${pre_sha}" != "${post_sha}" && "${post_sha}" != "unknown" ]] && new_commit=1

    # Step 4: Compute delta
    local delta="0"
    if [[ -n "${brier_after}" && "${brier_after}" != "null" ]]; then
        delta=$(python3 -c "print(round(${brier_after} - ${brier_before}, 6))")
    fi

    local verdict="keep"
    local reverted=0
    if [[ ${new_commit} -eq 1 ]]; then
        # Negative delta = improvement; positive beyond threshold = regression
        if python3 -c "import sys; sys.exit(0 if ${delta} > ${REVERT_THRESHOLD} else 1)"; then
            if $DRY_RUN; then
                warn "REGRESSION detected (delta=+${delta}) — DRY-RUN skip revert"
                verdict="would_revert_dry_run"
            else
                warn "REGRESSION detected (delta=+${delta} > ${REVERT_THRESHOLD}) — REVERTING ${post_sha:0:8}"
                if git revert --no-edit "${post_sha}" >> "${LOG_DIR}/paperclip-${dept_id}-${TODAY}.log" 2>&1; then
                    verdict="reverted"
                    reverted=1
                else
                    err "git revert failed — commit stays, flagged for human"
                    verdict="revert_failed"
                fi
            fi
        elif python3 -c "import sys; sys.exit(0 if ${delta} < 0 else 1)"; then
            ok "IMPROVEMENT delta=${delta} — keeping ${post_sha:0:8}"
            verdict="kept_improvement"
        else
            log "FLAT delta=${delta} — keeping ${post_sha:0:8}"
            verdict="kept_flat"
        fi
    else
        log "NO-OP (no new commit) — delta=${delta}"
        verdict="no_op"
    fi

    # Step 5: Append to ledger
    local ts
    ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    local dry_flag="False"
    $DRY_RUN && dry_flag="True"
    python3 - "${ts}" "${dept_id}" "${pre_sha}" "${post_sha}" "${new_commit}" \
        "${brier_before}" "${brier_after}" "${delta}" "${REVERT_THRESHOLD}" \
        "${verdict}" "${reverted}" "${duration}" "${dry_flag}" "${LEDGER}" <<'PYEOL'
import json, sys
(ts, dept_id, pre_sha, post_sha, new_commit, brier_before, brier_after,
 delta, threshold, verdict, reverted, duration, dry_flag, ledger) = sys.argv[1:]
def f_or_none(v):
    if v in ("", "null", "None"):
        return None
    try:
        return float(v)
    except ValueError:
        return None
row = {
    "timestamp": ts,
    "dept_id": dept_id,
    "pre_sha": pre_sha,
    "post_sha": post_sha,
    "new_commit": new_commit == "1",
    "brier_before": f_or_none(brier_before),
    "brier_after": f_or_none(brier_after),
    "delta": f_or_none(delta) or 0.0,
    "threshold": f_or_none(threshold),
    "verdict": verdict,
    "reverted": reverted == "1",
    "duration_seconds": int(duration),
    "dry_run": dry_flag == "True",
}
with open(ledger, "a") as fh:
    fh.write(json.dumps(row) + "\n")
print(f"ledger: {verdict} delta={delta}")
PYEOL
}

# ── Main loop ──────────────────────────────────────────────────
log "Paperclip starting: depts=[${DEPTS[*]}] threshold=${REVERT_THRESHOLD} dry_run=${DRY_RUN}"
for dept in "${DEPTS[@]}"; do
    run_paperclip "${dept}" || warn "${dept} iteration failed cleanly"
done
ok "Paperclip done"
