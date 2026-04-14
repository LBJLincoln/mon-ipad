#!/usr/bin/env bash
# Autonomous hourly PLAN.md executor — spans 3 projects
# Invokes claude CLI non-interactively with full env, picks one PLAN.md item,
# executes it across mon-ipad + nomos-political-alpha + nomos-dashboard, commits.

set -euo pipefail

TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
LOG_DIR="/home/termius/mon-ipad/logs"
LOG="$LOG_DIR/autonomous-hourly.log"
mkdir -p "$LOG_DIR"

# Lock to avoid overlap
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

# Load all API keys (HF, Google, Supabase, Stripe, Telegram, Twitter, Vercel…)
set -a
. /home/termius/mon-ipad/.env.local
set +a

cd /home/termius/mon-ipad

# Prompt: pick the highest-leverage PLAN.md / MONETIZATION item and execute it.
# Monetization deadline May 1 takes precedence. But also: improve website design
# and improve experiments every hour — never stop.
PROMPT=$(cat <<'EOF'
You are running autonomously. DEADLINE IS MAY 1 2026 — revenue or project shutdown.
Every hour through the night, ship ONE concrete improvement. No plans, no reports.

Context files (read in this order):
1. /home/termius/mon-ipad/MONETIZATION.md — revenue path
2. /home/termius/mon-ipad/PLAN.md — W1..W16 workstreams (W16 = revenue ship)
3. /home/termius/mon-ipad/CLAUDE.md — architecture rules (ZERO ML on VM, rules 1-10)
4. /home/termius/nomos-dashboard/DESIGN.md — Bloomberg palette, type scale
5. /home/termius/nomos-dashboard/PIXEL-DESIGN.md — pixel/world styling

You have write access to THREE repos:
- /home/termius/mon-ipad (NBA quant engine)
- /home/termius/nomos-political-alpha (political engine)
- /home/termius/nomos-dashboard (Next.js UI deployed to Vercel)

Pick EXACTLY ONE of these three tracks each run, rotating across runs:

  TRACK A — REVENUE (W16): anything shipping @Nomos42Picks — /subscribe copy
    polish, Stripe webhook hardening, Telegram bot whitelist logic, 09:00 ET
    auto-post cron, landing-page proof widgets wired to real /api/* endpoints.

  TRACK B — DESIGN: visually improve nomos-dashboard. Pick one page (/, /nba,
    /evolution, /trading-floor, /subscribe, /political, /infra, /floor) and
    make a measurable design improvement: tighter spacing, better typography
    hierarchy, replace placeholder text with real data, add loading skeletons,
    remove dead sections, improve color contrast per WCAG, add empty states.
    DO NOT run `next build` or `tsc` on the VM — they OOM. Trust TypeScript
    errors are caught by Vercel's CI.

  TRACK C — EXPERIMENTS: improve one NBA or political experiment — feature
    engineering (new category), better walk-forward split, improved CPCV fold
    logic, calibration fix, or HF Space script tweak (push via subtree).

RULES:
- Do ONE concrete change. Commit. Push.
- ALWAYS `git push` after committing — otherwise Vercel doesn't redeploy and
  the user sees "nothing changed". A commit without a push is a failure.
- Never edit .env.local. Never run training on the VM.
- Never push to HF subtrees unless the task explicitly requires it (it rarely does).
- Budget: 10 min max. Stop and exit when one ship is done.
- If a track is blocked (file missing, unclear target), switch to another track.

Rotate tracks across hours: glance at `git log --oneline -6` in /home/termius/nomos-dashboard
to see what the last hours shipped; do something DIFFERENT.

Do not ask questions. Do not produce a plan. Ship and push.
EOF
)

# Run claude non-interactively, all 3 dirs in scope, 10 min timeout.
# Prompt piped via stdin — more reliable than positional arg with flags.
echo "$PROMPT" | timeout 900 /usr/bin/claude \
    --print \
    --dangerously-skip-permissions \
    --add-dir /home/termius/nomos-political-alpha \
    --add-dir /home/termius/nomos-dashboard \
    >> "$LOG" 2>&1 || echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] claude exited non-zero (likely timeout, that's OK)" >> "$LOG"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] AUTONOMOUS HOURLY — done" >> "$LOG"
