#!/usr/bin/env bash
# Autonomous hourly executor — LASER-FOCUSED on visible product
# Pivoted 2026-04-15: user explicitly banned talk-only + feature-cat procrastination.

set -euo pipefail

TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
LOG_DIR="/home/termius/mon-ipad/logs"
LOG="$LOG_DIR/autonomous-hourly.log"
mkdir -p "$LOG_DIR"

LOCK="/tmp/autonomous-hourly.lock"
exec 9>"$LOCK"
if ! flock -n 9; then
    echo "[$TS] SKIP: previous run still active" >> "$LOG"
    exit 0
fi

echo "" >> "$LOG"
echo "════════════════════════════════════════════════════════════" >> "$LOG"
echo "[$TS] AUTONOMOUS HOURLY — start" >> "$LOG"
echo "════════════════════════════════════════════════════════════" >> "$LOG"

set -a
. /home/termius/mon-ipad/.env.local
set +a

cd /home/termius/mon-ipad

PROMPT=$(cat <<'EOF'
You are executing autonomously. May 1 2026 revenue deadline.

STOP shipping new NBA feature categories (Cat 60-65 were procrastination — the user explicitly called this out). The engine is at 65 cats, 6434 features. The model is already good enough. The PRODUCT is broken.

Work ONLY on the VISIBLE-PRODUCT fix list below. Each run, pick the FIRST item that is still broken. Verify it's broken by reading the relevant file/API. Fix it. Commit + push. Exit.

VERIFIED-BROKEN CHECKLIST (2026-04-15, ordered by severity):

  [0] /political PAGE HAS 14-DAY-OLD FAKE DATA (HIGHEST SEVERITY)
      File: /home/termius/nomos-dashboard/src/app/political/page.tsx:693
      Contains `ARENA_SNAPSHOT` const dated 2026-04-01 with fake champion
      "Prop_2.5pct_mut0 +550% ROI" that contradicts its own bankroll $16.48.
      5 top traders + 33 rounds all hardcoded. Page presents this as live truth.
      DONE WHEN: ARENA_SNAPSHOT replaced with either live fetch OR empty state
      "Arena v2 archive 2026-04-01 — new run in progress. Check /floor instead."
      This takes priority over all other items because it's the biggest lie.


  [1] HOMEPAGE HARDCODED FALLBACK
      File: /home/termius/nomos-dashboard/src/app/page.tsx
      Line 33: DEFAULT_PROJECTS const — contains hardcoded bankroll, agent counts, spaces counts
      Line ~337: banner "Brier 0.215 · 51.3% walk-forward ROI" — hardcoded string
      DONE WHEN: homepage renders "data unavailable" instead of fake fallback numbers
      when /api/dashboard/home returns null, AND banner text is sourced from live /api/nba/metrics.

  [2] /trading-floor + /floor PAGES SHOW STALE DATA
      Files: /home/termius/nomos-dashboard/src/app/trading-floor/page.tsx, floor/page.tsx
      The backend JSON (data/arena/trading-floor-status.json) shows day-bucket-v3
      FINISHED on Apr 14 with 9/10 agents bankrupted. Display needs a clear
      "RUN ENDED · 1/10 profitable · stake-sizing bug fixed, restart pending"
      banner at top, with timestamp of last run.
      DONE WHEN: pages clearly communicate the run ended + which agent won,
      instead of looking "live".

  [3] /world LACKS SOTA PIXEL ASSETS
      File: /home/termius/nomos-dashboard/src/components/pixel/PixelWorldPixi.tsx
      Currently uses programmatic PixiJS Graphics only — no Kenney 1-Bit sprites,
      no XP.css window chrome (both specified in reference_sota_pixel_stack_apr11.md).
      DONE WHEN: either (a) Kenney 1-Bit sprite sheet vendored + used for agent
      characters, OR (b) at least one XP.css window/title-bar component wraps
      an overlay (leaderboard or agent detail).

  [4] NBA TF v4 NOT RUNNING
      HF Space: LBJLincoln26/nba-llm-trading-floor (design = 10agents-real-llm)
      Current state: running=false, games_processed=null, stake-sizing fix
      (commit 0893bb83 in scripts/arena/hf-llm-trading-floor/app.py) NEVER
      deployed to the HF subtree.
      DONE WHEN: git subtree push to LBJLincoln26/nba-llm-trading-floor from
      scripts/arena/hf-llm-trading-floor/, then curl POST /api/run, then
      curl GET /api/status shows running=true.

  [5] DASHBOARD CLAIMED METRICS vs REALITY
      CLAUDE.md claims "Political TF llama-contra +223.5% ROI" — the current
      data/arena/political/political-trading-floor-latest.json shows 0 trades
      on 11 agents. Either re-run the engine or edit CLAUDE.md to tell the truth.
      DONE WHEN: CLAUDE.md text matches the JSON state file.

RULES:
- Pick the lowest-numbered item that is still broken. Verify by reading. Fix.
- One concrete change. Commit. Push.
- DO NOT add new NBA feature categories (Cat 66+). Banned.
- DO NOT write new research vault entries. Banned.
- DO NOT write new memory files. Banned.
- 10 min budget max. Stop and exit when one ship is done.
- ALWAYS `git push` after committing.

Before picking, run: `git log --oneline -6` in nomos-dashboard to see what
the last hours shipped. Do something different.
EOF
)

echo "$PROMPT" | timeout 900 /usr/bin/claude \
    --print \
    --dangerously-skip-permissions \
    --add-dir /home/termius/nomos-political-alpha \
    --add-dir /home/termius/nomos-dashboard \
    >> "$LOG" 2>&1 || echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] claude exited non-zero (likely timeout, that's OK)" >> "$LOG"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] AUTONOMOUS HOURLY — done" >> "$LOG"
