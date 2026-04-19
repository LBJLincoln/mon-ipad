#!/bin/bash
# safe_commit.sh — mutex-locked git commit+push for the 14-agent crew.
#
# Every agent (SWISH, LOBBYIST, INTERNAL AFFAIRS, …) that writes to the repo
# MUST shell through this. Enforces:
#   1. File-lock (flock) so only one agent writes at a time.
#   2. pull --rebase --autostash before push (avoids race rejections).
#   3. Retry push on non-fast-forward (up to 3 attempts).
#   4. Per-agent [<AGENT>] prefix in commit message.
#
# Usage:
#   scripts/lib/safe_commit.sh <AGENT_CODENAME> "<commit message>" [paths...]
# Example:
#   scripts/lib/safe_commit.sh SWISH "checkpoint S14 Brier 0.22186" data/fleet-matrix-latest.json
#
# If no paths given, commits currently-staged files.

set -euo pipefail

LOCKFILE="/tmp/nomos-git.lock"
LOCK_TIMEOUT=120    # seconds — max wait for another agent to release
REPO="/home/termius/mon-ipad"

AGENT="${1:-UNKNOWN}"
MSG="${2:-auto commit}"
shift 2 || true

cd "$REPO"

(
  # Block up to LOCK_TIMEOUT; fail loudly if can't acquire.
  flock -w "$LOCK_TIMEOUT" 9 || {
    echo "[safe_commit/$AGENT] LOCK TIMEOUT after ${LOCK_TIMEOUT}s — another agent still writing. Skipping."
    exit 2
  }

  # Pull first so our push won't be rejected. autostash keeps uncommitted work.
  git pull --rebase --autostash origin main 2>&1 | tail -3 || {
    echo "[safe_commit/$AGENT] pull --rebase failed — aborting to avoid clobber."
    exit 3
  }

  # Stage the provided paths (or do nothing if caller pre-staged).
  if [ "$#" -gt 0 ]; then
    git add "$@"
  fi

  # Exit clean if nothing to commit (no-op is success).
  if git diff --cached --quiet; then
    echo "[safe_commit/$AGENT] nothing to commit — clean exit."
    exit 0
  fi

  # Commit with agent prefix.
  git commit -m "[$AGENT] $MSG" --no-verify >/dev/null

  # Push with retry on non-fast-forward.
  for attempt in 1 2 3; do
    if git push origin main 2>&1 | tail -3; then
      echo "[safe_commit/$AGENT] push ok (attempt $attempt)"
      exit 0
    fi
    echo "[safe_commit/$AGENT] push rejected attempt $attempt — rebase + retry"
    git pull --rebase --autostash origin main 2>&1 | tail -2 || exit 4
  done

  echo "[safe_commit/$AGENT] push FAILED after 3 attempts"
  exit 5
) 9>"$LOCKFILE"
