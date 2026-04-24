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

# ---- Quarantine gate (2026-04-22 post-mortem) -----------------------------
# Block destructive commits (factory_reboot, DAY-0 RESET, reset-state, ...)
# on quarantined Spaces unless the caller passes NOMOS_QUARANTINE_OVERRIDE=1.
# check-msg returns 0 when the message is non-destructive OR the Space is
# clear. Returns 1 only when destructive + quarantined. Each NBA/POL/ITF/PQTF
# is tested separately so a message mentioning NBA doesn't block a POL action.
if [ "${NOMOS_QUARANTINE_OVERRIDE:-0}" != "1" ] && [ -x "scripts/ops/tf_quarantine.py" ]; then
  for space in NBA POL ITF PQTF; do
    # Only gate if the message actually names the Space — a generic "fix test"
    # commit shouldn't be blocked because another Space is quarantined.
    if echo "$MSG" | grep -qwi "$space"; then
      if ! python3 scripts/ops/tf_quarantine.py check-msg "$space" "$MSG" >/dev/null 2>&1; then
        echo "[safe_commit/$AGENT] BLOCKED: quarantine gate triggered on $space"
        echo "[safe_commit/$AGENT] msg: $MSG"
        python3 scripts/ops/tf_quarantine.py check "$space"
        echo "[safe_commit/$AGENT] override: re-run with NOMOS_QUARANTINE_OVERRIDE=1 and document why in the commit message."
        exit 10
      fi
    fi
  done
fi
# ---- end quarantine gate --------------------------------------------------

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
