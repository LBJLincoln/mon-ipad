#!/usr/bin/env bash
# =============================================================================
# sync-all.sh — Nomos42 Master Cross-Repo Sync
#
# Pulls latest from all 5 repos, copies shared configs for feature engine
# parity, aggregates cross-repo health, and pushes changes back.
#
# Usage:
#   /home/lahargnedebartoli/mon-ipad/scripts/sync/sync-all.sh
#   /home/lahargnedebartoli/mon-ipad/scripts/sync/sync-all.sh --dry-run
#   /home/lahargnedebartoli/mon-ipad/scripts/sync/sync-all.sh --no-push
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BRAIN="/home/lahargnedebartoli/mon-ipad"
REPOS=(
    "/home/lahargnedebartoli/mon-ipad"
    "/home/lahargnedebartoli/nomos-nba-agent"
    "/home/lahargnedebartoli/nomos-political-alpha"
    "/home/lahargnedebartoli/rgwa"
    "/home/lahargnedebartoli/nomos-dashboard"
)
REPO_NAMES=("mon-ipad" "nomos-nba-agent" "nomos-political-alpha" "rgwa" "nomos-dashboard")

LOGDIR="${BRAIN}/logs"
LOGFILE="${LOGDIR}/sync-all.log"
HEALTH_OUTPUT="${BRAIN}/data/cross-repo-health.json"
SYNC_DIR="${BRAIN}/scripts/sync"

DRY_RUN=false
NO_PUSH=false
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# ---------------------------------------------------------------------------
# Parse args
# ---------------------------------------------------------------------------
for arg in "$@"; do
    case "$arg" in
        --dry-run)  DRY_RUN=true ;;
        --no-push)  NO_PUSH=true ;;
        --help|-h)
            echo "Usage: $0 [--dry-run] [--no-push]"
            echo "  --dry-run   Show what would happen without making changes"
            echo "  --no-push   Pull and sync but do not push to remotes"
            exit 0
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
mkdir -p "${LOGDIR}"

log() {
    local msg="[$(date -u +"%Y-%m-%d %H:%M:%S")] $1"
    echo "$msg" | tee -a "${LOGFILE}"
}

log_section() {
    log "================================================================"
    log "$1"
    log "================================================================"
}

# ---------------------------------------------------------------------------
# Start
# ---------------------------------------------------------------------------
log_section "SYNC-ALL START — ${TIMESTAMP}"
if $DRY_RUN; then
    log "MODE: DRY RUN (no changes will be made)"
fi

ERRORS=0
WARNINGS=0
SYNCED=0

# ---------------------------------------------------------------------------
# Phase 1: Pull latest from all repos
# ---------------------------------------------------------------------------
log_section "PHASE 1: Git Pull (all 5 repos)"

for i in "${!REPOS[@]}"; do
    repo="${REPOS[$i]}"
    name="${REPO_NAMES[$i]}"

    if [ ! -d "$repo/.git" ]; then
        log "WARN: ${name} — not a git repo at ${repo}, skipping"
        ((WARNINGS++))
        continue
    fi

    log "Pulling ${name}..."
    if $DRY_RUN; then
        log "  [DRY RUN] Would run: git -C ${repo} pull --rebase --autostash"
    else
        if git -C "$repo" pull --rebase --autostash >> "${LOGFILE}" 2>&1; then
            log "  OK: ${name} pulled successfully"
        else
            log "  ERROR: ${name} pull failed (may have conflicts)"
            ((ERRORS++))
        fi
    fi
done

# ---------------------------------------------------------------------------
# Phase 2: Feature engine parity sync
# ---------------------------------------------------------------------------
log_section "PHASE 2: Feature Engine Parity Sync"

if $DRY_RUN; then
    log "[DRY RUN] Would run: ${SYNC_DIR}/sync-features.sh"
else
    if [ -x "${SYNC_DIR}/sync-features.sh" ]; then
        if "${SYNC_DIR}/sync-features.sh" >> "${LOGFILE}" 2>&1; then
            log "OK: Feature engine sync completed"
        else
            log "WARN: Feature engine sync reported mismatches"
            ((WARNINGS++))
        fi
    else
        log "WARN: sync-features.sh not found or not executable"
        ((WARNINGS++))
    fi
fi

# ---------------------------------------------------------------------------
# Phase 3: Read department karpathy outputs from all repos
# ---------------------------------------------------------------------------
log_section "PHASE 3: Collect Department Karpathy Outputs"

# mon-ipad departments (local)
DEPT_DIRS=(
    "research" "engineering" "evolution" "betting"
    "evaluation" "infra" "political" "creative" "trading_floor"
)

for dept in "${DEPT_DIRS[@]}"; do
    kfile="${BRAIN}/data/departments/${dept}/karpathy-output.json"
    if [ -f "$kfile" ]; then
        log "  Found: mon-ipad/${dept}/karpathy-output.json"
        ((SYNCED++))
    else
        log "  Missing: mon-ipad/${dept}/karpathy-output.json"
    fi
done

# Satellite repos
declare -A SATELLITE_KARPATHY=(
    ["nomos-nba-agent"]="/home/lahargnedebartoli/nomos-nba-agent/data/departments/prediction/karpathy-output.json"
    ["nomos-political-alpha"]="/home/lahargnedebartoli/nomos-political-alpha/data/departments/signals/karpathy-output.json"
    ["rgwa"]="/home/lahargnedebartoli/rgwa/data/departments/creative/karpathy-output.json"
)

for repo_name in "${!SATELLITE_KARPATHY[@]}"; do
    kfile="${SATELLITE_KARPATHY[$repo_name]}"
    if [ -f "$kfile" ]; then
        log "  Found: ${repo_name} karpathy output"
        ((SYNCED++))
    else
        log "  Missing: ${repo_name} karpathy output at ${kfile}"
    fi
done

# ---------------------------------------------------------------------------
# Phase 4: Aggregate cross-repo health
# ---------------------------------------------------------------------------
log_section "PHASE 4: Aggregate Cross-Repo Health"

if $DRY_RUN; then
    log "[DRY RUN] Would run: python3 ${SYNC_DIR}/aggregate-health.py"
else
    if python3 "${SYNC_DIR}/aggregate-health.py" >> "${LOGFILE}" 2>&1; then
        log "OK: Health aggregation complete -> ${HEALTH_OUTPUT}"
    else
        log "ERROR: Health aggregation failed"
        ((ERRORS++))
    fi
fi

# ---------------------------------------------------------------------------
# Phase 5: Run guardian cross-pollination
# ---------------------------------------------------------------------------
log_section "PHASE 5: Guardian Cross-Pollination"

if $DRY_RUN; then
    log "[DRY RUN] Would run: python3 ${SYNC_DIR}/guardian-cross-pollinate.py"
else
    if python3 "${SYNC_DIR}/guardian-cross-pollinate.py" >> "${LOGFILE}" 2>&1; then
        log "OK: Guardian cross-pollination complete"
    else
        log "WARN: Guardian cross-pollination had issues"
        ((WARNINGS++))
    fi
fi

# ---------------------------------------------------------------------------
# Phase 6: Push changes back to all repos
# ---------------------------------------------------------------------------
log_section "PHASE 6: Git Push (all repos with changes)"

if $NO_PUSH || $DRY_RUN; then
    log "SKIPPED: Push disabled (--no-push or --dry-run)"
else
    for i in "${!REPOS[@]}"; do
        repo="${REPOS[$i]}"
        name="${REPO_NAMES[$i]}"

        if [ ! -d "$repo/.git" ]; then
            continue
        fi

        # Check if there are changes to commit
        cd "$repo"
        if git diff --quiet && git diff --staged --quiet; then
            # Check for untracked data/logs files worth committing
            untracked=$(git ls-files --others --exclude-standard -- "data/" "logs/" 2>/dev/null | head -5)
            if [ -z "$untracked" ]; then
                log "  SKIP: ${name} — no changes to push"
                continue
            fi
        fi

        # Stage data and config files (never stage secrets)
        git add -A -- "data/" "logs/" "*.json" 2>/dev/null || true
        git add -A -- "features/" "hf-space/features/" 2>/dev/null || true

        if git diff --staged --quiet; then
            log "  SKIP: ${name} — nothing staged to commit"
            continue
        fi

        commit_msg="sync: cross-repo sync ${TIMESTAMP}"
        if git commit -m "$commit_msg" >> "${LOGFILE}" 2>&1; then
            if git push >> "${LOGFILE}" 2>&1; then
                log "  OK: ${name} — committed and pushed"
            else
                log "  ERROR: ${name} — commit OK but push failed"
                ((ERRORS++))
            fi
        else
            log "  WARN: ${name} — commit failed (nothing to commit?)"
            ((WARNINGS++))
        fi
    done
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
log_section "SYNC-ALL COMPLETE"
log "Timestamp:     ${TIMESTAMP}"
log "Repos synced:  ${#REPOS[@]}"
log "Outputs found: ${SYNCED}"
log "Warnings:      ${WARNINGS}"
log "Errors:        ${ERRORS}"

if [ "$ERRORS" -gt 0 ]; then
    log "STATUS: COMPLETED WITH ERRORS"
    exit 1
elif [ "$WARNINGS" -gt 0 ]; then
    log "STATUS: COMPLETED WITH WARNINGS"
    exit 0
else
    log "STATUS: ALL GREEN"
    exit 0
fi
