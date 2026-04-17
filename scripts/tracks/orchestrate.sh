#!/usr/bin/env bash
# 4-Track Opus orchestrator — runs every 8h (00:30, 08:30, 16:30 UTC).
#
# Reads data/tracks/t{1..4}-latest.json (refreshed hourly by write_track_status.py),
# composes a single prompt for Opus 4.7 (claude -p), and appends the response to
# data/tracks/orchestrator-log.jsonl.
#
# Replaces 9 dept-council loops. Budget target: ~3 runs/day × ~5k tokens ≈ $1/day.
#
# Usage:
#   scripts/tracks/orchestrate.sh          # run once
#   scripts/tracks/orchestrate.sh --dry    # print prompt, don't call claude
set -euo pipefail

cd "$(dirname "$0")/../.."
ROOT="$(pwd)"
TRACKS="${ROOT}/data/tracks"
LOG="${TRACKS}/orchestrator-log.jsonl"
DRY="${1:-}"

# Refresh status files first (idempotent, cheap).
python3 "${ROOT}/scripts/tracks/write_track_status.py" >/dev/null 2>&1 || true

TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Compose the prompt. Opus reads 4 summaries + TRACKS.md spec, emits ONE plan
# touching 1-2 tracks max.
PROMPT="$(cat <<EOF
You are the Nomos42 4-Track Orchestrator. You run once every 8h and must emit a
TERSE plan (≤300 words) touching 1-2 tracks MAX — not all 4.

Context (data/tracks/TRACKS.md spec):
$(cat "${TRACKS}/TRACKS.md")

=== T1 SCIENCE ===
$(cat "${TRACKS}/t1-latest.json")

=== T2 PLATFORM ===
$(cat "${TRACKS}/t2-latest.json")

=== T3 MARKET ===
$(cat "${TRACKS}/t3-latest.json")

=== T4 CAPITAL ===
$(cat "${TRACKS}/t4-latest.json")

Your output MUST be valid JSON:
{
  "ts": "${TS}",
  "focus_tracks": ["T1"|"T2"|"T3"|"T4"],   // 1 or 2 tracks only
  "decision": "<one sentence>",
  "actions": [
    {"track": "T1", "cmd": "<shell or code path>", "why": "<why>"}
  ],
  "skip_reason_for_other_tracks": "<one sentence>"
}

Rules:
- Bias toward T3 MARKET if paying_subs < 5 (May 1 deadline).
- Bias toward T4 CAPITAL if either TF bankroll < \$80.
- Bias toward T1 SCIENCE if fleet_best_brier has stalled >24h.
- T2 PLATFORM only if sha_match=false or deploy failed.
- Maximum 2 actions per cycle. Small, reversible diffs only.
EOF
)"

if [ "$DRY" = "--dry" ]; then
  echo "$PROMPT"
  exit 0
fi

# Call claude CLI (free tier / Max subscription). -p = print mode, no REPL.
if ! command -v claude >/dev/null 2>&1; then
  echo "[orchestrate] ERROR: claude CLI not found in PATH"
  exit 1
fi

RESPONSE="$(printf '%s' "$PROMPT" | claude -p --dangerously-skip-permissions --model opus 2>&1 || true)"

# Append raw response to log for audit.
jq -n \
  --arg ts "$TS" \
  --arg response "$RESPONSE" \
  '{ts: $ts, response: $response}' \
  >> "$LOG" 2>/dev/null || echo "{\"ts\":\"${TS}\",\"response\":$(printf '%s' "$RESPONSE" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')}" >> "$LOG"

echo "[orchestrate] ${TS} — logged $(wc -c <<<"$RESPONSE") bytes to ${LOG}"
