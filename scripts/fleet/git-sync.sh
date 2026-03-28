#!/bin/bash
# ══════════════════════════════════════════════════════════════
# FLEET GIT SYNC — Pull latest changes, push local changes
# ══════════════════════════════════════════════════════════════
# Runs on each machine (VM + MacBooks + Acer) via cron.
# Handles merge conflicts gracefully by favoring remote.
# Usage: bash scripts/fleet/git-sync.sh [--repos all|mon-ipad|nba-agent|...]
set -uo pipefail

LOG="/tmp/fleet-git-sync.log"
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

log() { echo "[$TIMESTAMP] $1" >> "$LOG"; }

# Detect base directory (different on VM vs local machines)
if [ -d "/home/termius/mon-ipad" ]; then
    BASE="/home/termius"  # VM
elif [ -d "$HOME/nomos42/mon-ipad" ]; then
    BASE="$HOME/nomos42"  # Local machines
else
    BASE="$HOME"
fi

REPOS=(
    "$BASE/mon-ipad"
    "$BASE/nomos-nba-agent"
    "$BASE/nomos-dashboard"
    "$BASE/nomos-political-alpha"
    "$BASE/rgwa"
)

sync_repo() {
    local repo_dir="$1"
    local repo_name
    repo_name=$(basename "$repo_dir")

    if [ ! -d "$repo_dir/.git" ]; then
        log "[$repo_name] Not a git repo, skipping"
        return
    fi

    cd "$repo_dir" || return

    # Stash any local changes
    local stash_output
    stash_output=$(git stash 2>&1)
    local had_stash=false
    if [[ "$stash_output" != *"No local changes"* ]]; then
        had_stash=true
    fi

    # Pull with rebase
    local pull_output
    pull_output=$(git pull --rebase --quiet 2>&1)
    local pull_rc=$?

    if [ $pull_rc -ne 0 ]; then
        log "[$repo_name] Pull failed: $pull_output"
        git rebase --abort 2>/dev/null
        # Try merge instead
        pull_output=$(git pull --quiet 2>&1)
        pull_rc=$?
        if [ $pull_rc -ne 0 ]; then
            log "[$repo_name] Pull (merge) also failed, skipping"
            [ "$had_stash" = true ] && git stash pop --quiet 2>/dev/null
            return
        fi
    fi

    # Pop stash if we had one
    if [ "$had_stash" = true ]; then
        git stash pop --quiet 2>/dev/null
    fi

    # Check for changes to push
    local ahead
    ahead=$(git rev-list --count @{u}..HEAD 2>/dev/null || echo "0")

    if [ "$ahead" -gt 0 ]; then
        git push --quiet 2>&1
        log "[$repo_name] Pushed $ahead commit(s)"
    else
        log "[$repo_name] Up to date"
    fi
}

log "=== GIT SYNC START ==="

for repo in "${REPOS[@]}"; do
    if [ -d "$repo" ]; then
        sync_repo "$repo"
    fi
done

log "=== GIT SYNC DONE ==="
